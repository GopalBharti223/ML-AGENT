"""
Regression tests for the 3rd solar_system / space_science dominance
report.

Covers the three fixes:

1. YEAR-WINDOW ROTATION (smart_story): every provider used to fetch
   the SAME deterministic window (10y ending at the latest data
   year), so (indicator, start_year, end_year) anti-repeat blocks
   made each indicator usable only ONCE per YEAR_RANGE_DAYS=60.
   Now each indicator gets a per-indicator rotated window.

2. DIVERSITY FLOOR (smart_story._apply_anti_repeat):
   - the old `len(candidates) <= MIN_ANTI_REPEAT_POOL` guard skipped
     topping up exactly when the pool was tiny;
   - re-admission is now category-aware (uncovered categories first).

3. CROSS-RUN HARD CAP (category_rotation): _enforce_hard_cap used to
   read only the in-memory _recent_categories (empty in every fresh
   production process), so the 2-in-8 cap never saw cross-run
   repetition.  It now uses the merged DB + in-session history.
   The CATEGORY ROTATION log also prints the full window (the old
   log printed only the post-trim scoring window, e.g.
   "Recent categories: ['gaming']").

Run:  python test_year_window_and_floor_fixes.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

from app.topic.category_rotation import CategoryRotationSelector
from app.topic.smart_story import SmartStoryEngine, StoryCandidate
from app.data.providers import DataProviderRegistry
from app.data.providers.base import DataProviderResult, IndicatorInfo
from app.topic.topic_families import family_to_category

HEALTH_FILE = os.path.join("data", "provider_health.json")


def make_candidate(provider, indicator, story, family, topic,
                   start=2016, end=2025, entity="e1"):
    return StoryCandidate(
        provider_id=provider,
        indicator_code=indicator,
        indicator_name="Indicator " + indicator,
        story_type=story,
        chart_type="bar_race",
        topic_family=family,
        years=10,
        category="Test",
        source_name="s",
        source_url="u",
        topic=topic,
        score=50.0,
        metrics={
            "entity": entity,
            "start_year": start,
            "end_year": end,
            "number_of_valid_countries": 10,
            "number_of_valid_years": 10,
            "data_completeness": 0.9,
        },
    )


class BlockingDB:
    """Fake db: blocks exactly the (indicator, year-range) pairs in
    blocked_ranges, plus exact topics in blocked_topics."""

    def __init__(self, blocked_ranges=(), blocked_topics=()):
        self.blocked_ranges = set(blocked_ranges)
        self.blocked_topics = set(blocked_topics)

    def is_topic_used(self, topic):
        return str(topic) in self.blocked_topics

    def is_story_type_used_recently(self, indicator, story, days=30):
        return False

    def is_year_range_used_recently(self, indicator, start, end, days=60):
        return (str(indicator), int(start), int(end)) in self.blocked_ranges

    def is_content_combination_used(self, indicator, story, start, end, days=90):
        return False

    def get_recent_records(self, limit=100):
        return []


def test_1_year_window_rotation_varies():
    print("=" * 70)
    print("TEST 1: _pick_fetch_years varies across calls")
    random.seed(20260916)
    pool = set(SmartStoryEngine.YEAR_WINDOW_POOL)
    seen = set()
    for _ in range(200):
        y = SmartStoryEngine._pick_fetch_years()
        assert y in pool, f"year {y} not in pool {pool}"
        seen.add(y)
    assert len(seen) >= 3, f"expected >=3 distinct windows, got {seen}"
    print(f"  distinct windows seen in 200 picks: {sorted(seen)}")
    print("OK")


def test_2_rotation_reaches_provider_fetch():
    print("=" * 70)
    print("TEST 2: automatic rotation passes varied years to the fetch")

    captured = []

    class YearRotProvider:
        provider_id = "yearrot_fake"
        provider_name = "Year Rotation Fake"
        source_url = "https://example.com"

        @classmethod
        def is_configured(cls):
            return True

        @classmethod
        def list_indicators(cls):
            return [
                IndicatorInfo(
                    code="yearrot_indicator",
                    name="Year Rotation Indicator",
                    category="economy",
                    source_url=cls.source_url,
                )
            ]

        @classmethod
        def fetch_normalized(cls, indicator_code, years=10,
                             story_type="fastest_growth",
                             min_countries=5, **kwargs):
            captured.append(int(years))
            return DataProviderResult(
                provider=cls.provider_id,
                indicator_code=indicator_code,
                metric_name="Year Rotation Indicator",
                source_name=cls.provider_name,
                source_url=cls.source_url,
                normalized_data=pd.DataFrame(),
                wide_data=pd.DataFrame(),
                metadata={},
            )

    DataProviderRegistry.register(YearRotProvider)

    # Do not persist health-state changes from this fake provider.
    health_backup = None
    if os.path.exists(HEALTH_FILE):
        with open(HEALTH_FILE, "rb") as fh:
            health_backup = fh.read()

    try:
        from app.data.providers.health import provider_health
        provider_health.is_available = lambda pid: True

        random.seed(20260916)
        for _ in range(30):
            SmartStoryEngine.select_best_candidate(
                provider_ids=["yearrot_fake"],
                max_indicators_per_provider=1,
                min_countries=6,
            )
    finally:
        if health_backup is not None:
            with open(HEALTH_FILE, "wb") as fh:
                fh.write(health_backup)

    assert len(captured) == 30, f"expected 30 fetches, got {len(captured)}"
    distinct = sorted(set(captured))
    assert len(distinct) >= 3, (
        f"year-window rotation did not reach the fetch layer: {distinct}"
    )
    pool = set(SmartStoryEngine.YEAR_WINDOW_POOL)
    assert set(captured) <= pool, f"windows outside pool: {set(captured) - pool}"
    print(f"  30 fetches used windows: {distinct} "
          f"(counts: {[(w, captured.count(w)) for w in distinct]})")
    print("OK")


def test_3_floor_tops_up_small_pools():
    print("=" * 70)
    print("TEST 3: diversity floor tops up a tiny pool (old guard bug)")

    blocked = {
        ("health_ind", 2016, 2025),
        ("energy_ind", 2016, 2025),
        ("companies_ind", 2016, 2025),
    }
    db = BlockingDB(blocked_ranges=blocked)

    candidates = [
        make_candidate("wb", "econ_ind_1", "current_leader",
                       "economy", "Economy Story 1"),
        make_candidate("wb", "econ_ind_2", "current_leader",
                       "economy", "Economy Story 2"),
        make_candidate("wb", "health_ind", "current_leader",
                       "health", "Health Story"),
        make_candidate("wb", "energy_ind", "current_leader",
                       "energy", "Energy Story"),
        make_candidate("wb", "companies_ind", "current_leader",
                       "companies_brands", "Companies Story"),
    ]

    result = SmartStoryEngine._apply_anti_repeat(candidates, database=db)

    assert len(result) == 5, (
        f"floor should top the 2-candidate pool back up to 5, got {len(result)}"
    )
    cats = {
        family_to_category(c.topic_family) for c in result
    }
    assert {"economy", "health", "energy"} <= cats, (
        f"re-admitted candidates must be visible per category, got {cats}"
    )
    print(f"  pool after floor: {len(result)} candidates, categories={sorted(cats)}")
    print("OK")


def test_4_floor_is_category_aware():
    print("=" * 70)
    print("TEST 4: re-admission prefers uncovered categories")

    blocked = {
        ("econ_ind_1", 2016, 2025),
        ("health_1", 2016, 2025),
        ("health_2", 2016, 2025),
        ("health_3", 2016, 2025),
        ("health_4", 2016, 2025),
    }
    db = BlockingDB(blocked_ranges=blocked)

    # 1 energy candidate passes; 5 blocked candidates: 4 health + 1
    # economy.  The floor (6) re-admits 5; the health ones must come
    # first (uncovered category) so health joins the pool before the
    # extra economy duplicates.
    candidates = [
        make_candidate("wb", "energy_ind", "current_leader",
                       "energy", "Energy Story"),
        make_candidate("wb", "econ_ind_1", "current_leader",
                       "economy", "Economy Story"),
        make_candidate("wb", "health_1", "current_leader",
                       "health", "Health Story 1"),
        make_candidate("wb", "health_2", "current_leader",
                       "health", "Health Story 2"),
        make_candidate("wb", "health_3", "current_leader",
                       "health", "Health Story 3"),
        make_candidate("wb", "health_4", "current_leader",
                       "health", "Health Story 4"),
    ]

    result = SmartStoryEngine._apply_anti_repeat(candidates, database=db)

    assert len(result) >= SmartStoryEngine.MIN_ANTI_REPEAT_POOL, (
        f"floor not met: {len(result)}"
    )
    cats = {family_to_category(c.topic_family) for c in result}
    assert "health" in cats, (
        f"uncovered category 'health' must be re-admitted first, got {cats}"
    )
    print(f"  pool after floor: {len(result)} candidates, categories={sorted(cats)}")
    print("OK")


def test_5_hard_cap_sees_cross_run_history():
    print("=" * 70)
    print("TEST 5: hard cap enforces the 2-in-8 rule from DB history")

    CategoryRotationSelector.reset()  # in-memory EMPTY (fresh process)

    # Simulated merged DB+in-session history: space_science picked
    # 3 times in the last 8 published videos.
    recent_full = [
        "space_science", "space_science", "economy",
        "health", "gaming", "space_science", "energy", "sports",
    ]

    groups = {
        "space_science": ["ss_candidate"],
        "economy": ["econ_candidate_1", "econ_candidate_2"],
    }

    rng = random.Random(7)
    result = CategoryRotationSelector._enforce_hard_cap(
        "space_science",
        ["space_science", "economy"],
        recent_full,
        rng,
        groups,
    )

    assert result != "space_science", (
        "hard cap must re-route a category picked 3x in the last 8 "
        "picks even when in-memory history is empty"
    )
    assert result == "economy"
    print(f"  cap re-routed space_science -> {result}")
    print("OK")


def test_6_log_shows_full_recent_window():
    print("=" * 70)
    print("TEST 6: CATEGORY ROTATION log prints the full recent window")

    CategoryRotationSelector.reset()

    candidates = [
        make_candidate("wb", "econ_1", "current_leader",
                       "economy", "Economy 1", entity="econ_1"),
        make_candidate("wb", "econ_2", "current_leader",
                       "economy", "Economy 2", entity="econ_2"),
        make_candidate("wb", "health_1", "current_leader",
                       "health", "Health 1", entity="health_1"),
    ]

    # NEWEST-FIRST DB history (Database.get_recent_records contract):
    # 6 recent picks across 6 distinct categories.
    recent_records = [
        {"indicator_code": "games_popular_ranking"},   # gaming
        {"indicator_code": "NY.GDP.MKTP.CD"},          # economy
        {"indicator_code": "SP.POP.TOTL"},             # population
        {"indicator_code": "SP.DYN.LE00.IN"},          # health
        {"indicator_code": "EG.ELC.ACCS.ZS"},          # energy
        {"indicator_code": "co2_emissions"},           # environment
    ]

    logs = []
    chosen = CategoryRotationSelector.select(
        candidates,
        recent_records=recent_records,
        seed=11,
        logger=logs.append,
    )

    assert chosen is not None, "select() must return a candidate"

    full_lines = [
        ln for ln in logs
        if "Recent history (full window" in ln
    ]
    assert full_lines, (
        f"full-window log line missing; logs={logs}"
    )
    # The full window carries the last 5 derived categories
    # (RECENT_CATEGORY_WINDOW); the SCORING window (2 eligible
    # categories -> dynamic 1) collapses to just the last pick.
    assert "gaming" in full_lines[0], (
        f"full window must retain the last pick: {full_lines[0]}"
    )
    expected_window = (
        "['energy', 'health', 'population_demographics', "
        "'economy', 'gaming']"
    )
    assert expected_window in full_lines[0], (
        f"full window must show all 5 derived picks: {full_lines[0]}"
    )
    scored_lines = [
        ln.strip() for ln in "\n".join(logs).splitlines()
        if ln.strip().startswith("Recent categories:")
    ]
    assert scored_lines and scored_lines[0].count(",") == 0, (
        f"scoring window is dynamically trimmed to 1 with 2 eligible "
        f"categories: {scored_lines}"
    )
    print("  " + full_lines[0])
    print("  (scoring window for comparison: " + scored_lines[0] + ")")
    print("OK")


def test_7_dedup_floor_keeps_pool_diverse():
    print("=" * 70)
    print("TEST 7: dedup stage keeps the pool at the diversity floor")

    # Five candidates across three categories.  The last-10 recent
    # records cover provider/indicator/story combos for all but one
    # candidate, so strict dedup would leave a single-category pool
    # (the exact "Eligible categories: [...]" collapse).
    recent_records = [
        {"provider_id": "wb", "indicator_code": "econ_1",
         "story_type": "current_leader", "topic_family": "economy"},
        {"provider_id": "wb", "indicator_code": "econ_2",
         "story_type": "current_leader", "topic_family": "economy"},
        {"provider_id": "wb", "indicator_code": "hlt_1",
         "story_type": "current_leader", "topic_family": "health"},
        {"provider_id": "wb", "indicator_code": "hlt_2",
         "story_type": "current_leader", "topic_family": "health"},
        {"provider_id": "wb", "indicator_code": "econ_3",
         "story_type": "current_leader", "topic_family": "economy"},
        {"provider_id": "wb", "indicator_code": "hlt_3",
         "story_type": "current_leader", "topic_family": "health"},
    ]

    candidates = [
        make_candidate("wb", "energy_1", "current_leader",
                       "energy", "Energy Story"),
        make_candidate("wb", "econ_1", "current_leader",
                       "economy", "Economy 1"),
        make_candidate("wb", "econ_2", "current_leader",
                       "economy", "Economy 2"),
        make_candidate("wb", "econ_3", "current_leader",
                       "economy", "Economy 3"),
        make_candidate("wb", "hlt_1", "current_leader",
                       "health", "Health 1"),
        make_candidate("wb", "hlt_2", "current_leader",
                       "health", "Health 2"),
        make_candidate("wb", "hlt_3", "current_leader",
                       "health", "Health 3"),
    ]

    result = SmartStoryEngine._deduplicate_candidates(
        candidates, recent_records
    )

    assert len(result) >= SmartStoryEngine.MIN_ANTI_REPEAT_POOL, (
        f"dedup must honour the floor, got {len(result)}"
    )
    cats = {family_to_category(c.topic_family) for c in result}
    assert {"economy", "health"} <= cats, (
        f"re-admitted categories must become visible to the "
        f"rotator, got {cats}"
    )
    print(f"  pool after dedup floor: {len(result)} candidates, "
          f"categories={sorted(cats)}")
    print("OK")


def test_8_dedup_floor_prefers_uncovered_categories():
    print("=" * 70)
    print("TEST 8: dedup re-admission adds missing categories first")

    recent_records = [
        {"provider_id": "wb", "indicator_code": "econ_1",
         "story_type": "current_leader", "topic_family": "economy"},
        {"provider_id": "wb", "indicator_code": "econ_2",
         "story_type": "current_leader", "topic_family": "economy"},
        {"provider_id": "wb", "indicator_code": "econ_3",
         "story_type": "current_leader", "topic_family": "economy"},
        {"provider_id": "wb", "indicator_code": "econ_4",
         "story_type": "current_leader", "topic_family": "economy"},
        {"provider_id": "wb", "indicator_code": "econ_5",
         "story_type": "current_leader", "topic_family": "economy"},
    ]

    # 1 energy survives; 5 blocked economy candidates must NOT be the
    # first re-admissions -- the uncovered energy already leads, so
    # the floor must not just re-add same-category duplicates.
    candidates = [
        make_candidate("wb", "energy_1", "current_leader",
                       "energy", "Energy Story"),
        make_candidate("wb", "econ_1", "current_leader",
                       "economy", "Economy 1"),
        make_candidate("wb", "econ_2", "current_leader",
                       "economy", "Economy 2"),
        make_candidate("wb", "econ_3", "current_leader",
                       "economy", "Economy 3"),
        make_candidate("wb", "econ_4", "current_leader",
                       "economy", "Economy 4"),
        make_candidate("wb", "econ_5", "current_leader",
                       "economy", "Economy 5"),
    ]

    result = SmartStoryEngine._deduplicate_candidates(
        candidates, recent_records
    )

    cats = [family_to_category(c.topic_family) for c in result]
    assert len(result) >= SmartStoryEngine.MIN_ANTI_REPEAT_POOL, (
        f"floor not met: {len(result)}"
    )
    assert cats[0] == "energy", (
        f"the surviving candidate must stay first: {cats}"
    )
    print(f"  categories after dedup floor: {cats}")
    print("OK")


if __name__ == "__main__":
    test_1_year_window_rotation_varies()
    test_2_rotation_reaches_provider_fetch()
    test_3_floor_tops_up_small_pools()
    test_4_floor_is_category_aware()
    test_5_hard_cap_sees_cross_run_history()
    test_6_log_shows_full_recent_window()
    test_7_dedup_floor_keeps_pool_diverse()
    test_8_dedup_floor_prefers_uncovered_categories()
    print()
    print("=" * 70)
    print("ALL YEAR-WINDOW / FLOOR / HARD-CAP REGRESSION TESTS PASSED")
    print("=" * 70)


