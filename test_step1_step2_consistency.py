"""
OFFLINE REGRESSION TEST for the Step1/Step2 consistency fix
(Issue 2) and the manual-topic country-hint fix (Issue 1).

Proves, WITHOUT network, that:

  PART A (Step1/Step2 dataset consistency, both fixes' foundation):
    - The winning candidate's to_topic_data() now emits
      selected_countries (the exact frame it was scored on)
      and selected_min_countries (the min_countries actually
      used by the Step-1 fetch).
    - For EVERY affected provider-story mapping (current_leader,
      leader_challenge, rank_climber, biggest_decline,
      rank_decline), a Step-2 refetch constrained to those
      countries returns a frame that CONTAINS all of Step 1's
      countries -- the refetch can no longer silently replace
      the validated set with a world-wide re-rank.
    - The real WorldBankData.fetch_data honours the required +
      context contract offline.

  PART B (manual-topic country requests):
    - "India vs USA military" carries India + USA through the
      manual path (LLM seam -> Step-1 fetch -> selected_countries
      anchored on the user's request -> Step-2 fetch).
    - Missing/unrecognized countries degrade gracefully.
    - Keywords naming no countries behave exactly as before.

  PART C (single-entity superlative queries):
    - "richest person in India" / "India richest person" /
      "India's richest person" are detected and DECLINED
      honestly before any LLM call (no free, ToS-compliant
      wealth data source; nothing is fabricated).
    - Country-noun wealth ("richest country in Europe") is NOT
      declined -- it stays on the country/indicator path.
    - Other superlatives ("most popular actor in India",
      "tallest building in Dubai") route through the Wikipedia
      pageviews entity pipeline with honest search-interest
      framing, only when >= 2 entities verify; otherwise they
      fall through unchanged.

Run:  python test_step1_step2_consistency.py
Exit: 0 on success, 1 on any failure.
"""

import sys

import pandas as pd

from app.data.providers.base import (
    DataProvider,
    DataProviderResult,
    IndicatorInfo,
    match_country_request,
    normalize_long_data,
    select_required_plus_context,
    to_visual_dataframe,
)
from app.data.providers.health import provider_health
from app.data.providers.registry import DataProviderRegistry
from app.data.worldbank import WorldBankData
from app.topic.manual_topic import (
    ManualTopicEngine,
    ManualTopicError,
)
from app.topic.smart_story import SmartStoryEngine


FAKE_ID = "consistency_fake"

YEARS = list(range(2015, 2025))

# Parity-test series shapes, proven to generate ALL story types
# with passing quality/visual gates when the whole frame is
# used.  Mapped onto realistic ISO3 codes so country-hint
# matching sees a World-Bank-like surface.
SERIES = {
    "Argentina":     [400, 390, 385, 370, 360, 340, 300, 250, 180, 120],
    "Ukraine":       [300, 298, 297, 296, 295, 294, 293, 292, 291, 290],
    "United States": [250, 251, 252, 253, 254, 255, 256, 257, 258, 260],
    "China":         [200, 201, 202, 203, 204, 205, 206, 207, 208, 210],
    "India":         [100, 105, 110, 115, 120, 128, 135, 140, 145, 150],
    "Germany":       [50, 55, 60, 66, 72, 78, 84, 88, 92, 95],
    "Japan":         [10, 14, 20, 28, 36, 44, 52, 62, 76, 90],
    "Canada":        [30, None, 32, None, 34, None, 30, None, 28, 25],
}

CODES = {
    "Argentina": "ARG",
    "Ukraine": "UKR",
    "United States": "USA",
    "China": "CHN",
    "India": "IND",
    "Germany": "DEU",
    "Japan": "JPN",
    "Canada": "CAN",
}

# The exact provider-story mapping the pipeline is SPECED to use
# for refetching (mirror of SmartStoryEngine.PROVIDER_FETCH_STORY).
PROVIDER_FETCH_STORY_REF = {
    "fastest_growth": "fastest_growth",
    "biggest_decline": "most_declined",
    "rank_climber": "biggest_jump",
    "rank_decline": "most_declined",
    "current_leader": "biggest_jump",
    "leader_challenge": "biggest_jump",
    "trend_over_time": "fastest_growth",
}


RESULT = {"passed": 0, "failed": []}


def check(name, condition, detail=""):
    mark = "PASS" if condition else "FAIL"
    print(
        f"  [{mark}] {name}"
        + (f"  -- {detail}" if detail else "")
    )
    if condition:
        RESULT["passed"] += 1
    else:
        RESULT["failed"].append(name)


def _story_value(row, story_type):
    """Mimic IMF/OWID ranking: relative for *_growth, absolute else."""
    values = row.dropna()
    if len(values) < 2:
        return None
    first = float(values.iloc[0])
    last = float(values.iloc[-1])
    if story_type in ("fastest_growth", "fastest_decline"):
        if abs(first) < 1e-9:
            return None
        return (last - first) / abs(first)
    return last - first


def _rank_frame(frame, story_type):
    scored = []
    for index, row in frame.iterrows():
        value = _story_value(row, story_type)
        if value is None:
            continue
        scored.append((index, value))
    if not scored:
        return []
    ascending = story_type in ("most_declined", "fastest_decline")
    scored = sorted(
        scored,
        key=lambda item: item[1],
        reverse=not ascending,
    )
    return [index for index, _ in scored]


class ConsistencyProvider(DataProvider):

    provider_id = FAKE_ID
    provider_name = "World Bank"
    source_url = "https://data.worldbank.org"

    last_call = {}

    INDICATORS = {
        "MS.MIL.XPND.GD.ZS": "Military Expenditure (% of GDP)",
    }

    @classmethod
    def list_indicators(cls):
        return [
            IndicatorInfo(
                code=code,
                name=name,
                category="World Data",
                source_url=cls.source_url,
            )
            for code, name in cls.INDICATORS.items()
        ]

    @classmethod
    def _wide_frame(cls):
        rows = []
        for country, values in SERIES.items():
            for i, year in enumerate(YEARS):
                value = values[i]
                if value is None:
                    continue
                rows.append(
                    {
                        "country": country,
                        "country_code": CODES[country],
                        "year": year,
                        "value": float(value),
                    }
                )
        normalized = normalize_long_data(
            rows=rows,
            provider=cls.provider_id,
            metric_name="Military Expenditure (% of GDP)",
            source_name=cls.provider_name,
            source_url=cls.source_url,
            indicator_code="MS.MIL.XPND.GD.ZS",
        )
        return to_visual_dataframe(normalized)

    @classmethod
    def fetch_normalized(
        cls,
        indicator_code,
        years=10,
        story_type="fastest_growth",
        min_countries=6,
        countries=None,
    ):
        frame = cls._wide_frame()

        ranked_keys = _rank_frame(frame, story_type)

        if countries:
            required_keys, unmatched = match_country_request(
                countries,
                ranked_keys,
            )
            selected_keys, _missing = select_required_plus_context(
                ranked_keys,
                required_keys,
                min_countries,
            )
        else:
            selected_keys = ranked_keys[:min_countries]

        selected = frame.loc[selected_keys].copy()

        selected.attrs["story_type"] = story_type
        selected.attrs["normalized_data"] = frame.attrs.get("normalized_data")

        cls.last_call = {
            "story_type": story_type,
            "min_countries": min_countries,
            "countries": list(countries) if countries else [],
        }

        return DataProviderResult(
            provider=cls.provider_id,
            indicator_code=indicator_code,
            metric_name="Military Expenditure (% of GDP)",
            source_name=cls.provider_name,
            source_url=cls.source_url,
            normalized_data=selected.attrs["normalized_data"],
            wide_data=selected,
            metadata={},
        )


DataProviderRegistry.register(ConsistencyProvider)

provider_health.is_available = lambda pid: True

print("=" * 70)
print("OFFLINE STEP1/STEP2 CONSISTENCY + COUNTRY-HINT REGRESSION")
print("=" * 70)

# =========================================================
print()
print("[1] StoryCandidate -> topic_data carries the SCORED frame")
print("    (selected_countries / selected_min_countries)")
# =========================================================

raw_frame = ConsistencyProvider._wide_frame()

base_candidates = SmartStoryEngine.generate_candidates(
    provider_id=FAKE_ID,
    indicator_code="MS.MIL.XPND.GD.ZS",
    indicator_name="Military Expenditure (% of GDP)",
    category="World Data",
    source_name="World Bank",
    source_url="https://data.worldbank.org",
    data=raw_frame,
    years=10,
    min_countries=SmartStoryEngine.MIN_COUNTRIES,
)

candidates_by_type = {
    candidate.story_type: candidate
    for candidate in base_candidates
}

check(
    "fixture produces a broad candidate pool",
    len(base_candidates) >= 5,
    f"{len(base_candidates)} candidates",
)

selected = candidates_by_type["current_leader"].to_topic_data()

frame_codes = (
    selected["story_metrics"]["data"]
    .index
    .get_level_values("country_code")
)

check(
    "selected_countries equals the scored frame",
    sorted(selected["selected_countries"])
    == sorted(str(code) for code in frame_codes),
    str(selected["selected_countries"]),
)

check(
    "selected_min_countries == MIN_COUNTRIES (6)",
    selected["selected_min_countries"]
    == SmartStoryEngine.MIN_COUNTRIES,
)

# =========================================================
print()
print("[2] THE FIVE AFFECTED MAPPINGS: Step-2 refetch is")
print("    CONSTRAINED to Step-1's countries")
# =========================================================

AFFECTED = [
    "current_leader",
    "leader_challenge",
    "rank_climber",
    "biggest_decline",
    "rank_decline",
]

all_satisfied = True

for story_type in AFFECTED:

    candidate = candidates_by_type.get(story_type)

    if candidate is None:
        print(f"  [FAIL] no candidate for {story_type}")
        all_satisfied = False
        continue

    topic_data = candidate.to_topic_data()

    expected_story = PROVIDER_FETCH_STORY_REF[story_type]

    mapped = SmartStoryEngine.PROVIDER_FETCH_STORY[story_type]

    check(
        f"mapping {story_type} -> {expected_story} intact",
        mapped == expected_story,
    )

    step1_countries = list(topic_data["selected_countries"])

    step1_min = topic_data["selected_min_countries"]

    # Simulate run.py Step 2: a brand-new fetch constrained to
    # Step 1's validated contract.

    provider_result = ConsistencyProvider.fetch_normalized(
        indicator_code="MS.MIL.XPND.GD.ZS",
        years=10,
        story_type=mapped,
        min_countries=step1_min,
        countries=step1_countries,
    )

    step2_frame = provider_result.wide_data

    step2_codes = {
        str(code)
        for code in step2_frame.index.get_level_values("country_code")
    }

    covered = all(
        code in step2_codes
        for code in step1_countries
    )

    check(
        f"{story_type:17s} Step2 frame {len(step2_codes)} countries "
        "contains ALL Step1 countries",
        covered,
        f"{sorted(step2_codes)} supersets {sorted(step1_countries)}",
    )

    check(
        f"{story_type:17s} Step2 was constrained BEFORE ranking "
        "(countries passed to provider)",
        ConsistencyProvider.last_call["countries"]
        == step1_countries,
    )

    if not covered:
        all_satisfied = False

check(
    "ALL 5 affected mappings: Step-2 sanitized to Step-1 set",
    all_satisfied,
)

# =========================================================
print()
print("[3] PART B: 'India vs USA Military' carries the request")
# =========================================================

original_seam = ManualTopicEngine._llm_semantic_pick


def seam_military_usa(keyword, indicator_names):
    return {
        "indicator": "Military Expenditure (% of GDP)",
        "countries": ["India", "USA"],
    }


ManualTopicEngine._llm_semantic_pick = staticmethod(seam_military_usa)

try:

    topic_data = ManualTopicEngine.generate_manual_topic(
        "India vs USA Military",
        provider_ids=[FAKE_ID],
        seed=42,
    )

    resolved_ok = True

except ManualTopicError as err:

    resolved_ok = False

    manual_error = err

check(
    "'India vs USA Military' resolves without error",
    resolved_ok,
    str(manual_error) if not resolved_ok else "",
)

if resolved_ok:

    check(
        "indicator is Military Expenditure",
        topic_data["indicator_code"] == "MS.MIL.XPND.GD.ZS",
    )

    check(
        "selected_countries anchored on the USER's request "
        "(India + USA)",
        topic_data["selected_countries"] == ["India", "USA"],
        str(topic_data["selected_countries"]),
    )

    check(
        "Step-1 fetch received the country restriction",
        ConsistencyProvider.last_call["countries"]
        == ["India", "USA"],
        str(ConsistencyProvider.last_call["countries"]),
    )

    frame_codes_step1 = {
        str(code)
        for code in (
            topic_data["story_metrics"]["data"]
            .index
            .get_level_values("country_code")
        )
    }

    check(
        "Step-1 dataset actually contains India + USA",
        {"IND", "USA"}.issubset(frame_codes_step1),
        str(sorted(frame_codes_step1)),
    )

    check(
        "selected_min_countries still 6",
        topic_data["selected_min_countries"]
        == ManualTopicEngine.MIN_COUNTRIES,
    )

    # Simulate the Step-2 refetch (run.py now passes
    # countries=topic_data['selected_countries']).

    provider_result = ConsistencyProvider.fetch_normalized(
        indicator_code=topic_data["indicator_code"],
        years=10,
        story_type=topic_data["provider_fetch_story_type"],
        min_countries=topic_data["selected_min_countries"],
        countries=topic_data["selected_countries"],
    )

    step2_codes = {
        str(code)
        for code in (
            provider_result.wide_data
            .index
            .get_level_values("country_code")
        )
    }

    check(
        "Step2 frame contains India + USA for the biggest_jump "
        "refetch",
        {"IND", "USA"}.issubset(step2_codes),
        str(sorted(step2_codes)),
    )

# =========================================================
print()
print("[4] GRACEFUL DEGRADATION: requested country missing")
# =========================================================


def seam_brazil(keyword, indicator_names):
    # "Brazil" is a REAL country but has NO data in the fixture.
    return {
        "indicator": "Military Expenditure (% of GDP)",
        "countries": ["Brazil", "India"],
    }


ManualTopicEngine._llm_semantic_pick = staticmethod(seam_brazil)

try:

    topic_data_br = ManualTopicEngine.generate_manual_topic(
        "military spending brazil india",
        provider_ids=[FAKE_ID],
        seed=7,
    )

    degraded_ok = True

except ManualTopicError as err:

    degraded_ok = False

    manual_error = err

check(
    "missing requested country (Brazil) does NOT fail the request",
    degraded_ok,
    str(manual_error) if not degraded_ok else "",
)

if degraded_ok:

    check(
        "surviving requested country (India) is carried",
        "India" in topic_data_br["selected_countries"],
        str(topic_data_br["selected_countries"]),
    )

    frame_codes_dg = {
        str(code)
        for code in (
            topic_data_br["story_metrics"]["data"]
            .index
            .get_level_values("country_code")
        )
    }

    check(
        "Brazil absent, India present in the Step-1 dataset",
        "BRA" not in frame_codes_dg and "IND" in frame_codes_dg,
        str(sorted(frame_codes_dg)),
    )

# =========================================================
print()
print("[5] NO-COUNTRY KEYWORD UNCHANGED")
# =========================================================


def seam_plain(keyword, indicator_names):
    return {
        "indicator": "Military Expenditure (% of GDP)",
        "countries": [],
    }


ManualTopicEngine._llm_semantic_pick = staticmethod(seam_plain)

try:

    topic_data_plain = ManualTopicEngine.generate_manual_topic(
        "military",
        provider_ids=[FAKE_ID],
        seed=1,
    )

    plain_ok = True

except ManualTopicError:

    plain_ok = False

check(
    "'military' (no countries) still resolves",
    plain_ok,
)

if plain_ok:

    check(
        "no country hint passed to the fetch",
        ConsistencyProvider.last_call["countries"] == [],
    )

    check(
        "selected_countries come from the scored frame "
        "(not an empty list)",
        len(topic_data_plain["selected_countries"]) >= 3,
        str(topic_data_plain["selected_countries"]),
    )

# restore seam
ManualTopicEngine._llm_semantic_pick = original_seam

# =========================================================
print()
print("[6] WORLDBANK DATA LAYER: 'required + context' contract")
print("    (offline via mocked _request)")
# =========================================================

ORIGINAL_REQUEST = WorldBankData._request
WorldBankData._countries_cache = None


def fake_worldbank_payload(url, params=None, timeout=None):
    url = str(url)
    if url.endswith("/country"):
        return [
            {"page": 1},
            [
                {
                    "id": code,
                    "name": name,
                    "region": {"id": "ECS"},
                }
                for name, code in CODES.items()
            ],
        ]
    return [
        {"page": 1},
        [
            {
                "countryiso3code": CODES[name],
                "country": {"value": name},
                "date": str(year),
                "value": values[i],
            }
            for name, values in SERIES.items()
            for i, year in enumerate(YEARS)
            if values[i] is not None
        ],
    ]


WorldBankData._request = staticmethod(fake_worldbank_payload)

try:

    wb_result = WorldBankData.fetch_data(
        indicator_code="MS.MIL.XPND.GD.ZS",
        years=10,
        story_type="biggest_jump",
        min_countries=6,
        countries=["India", "USA"],
    )

    wb_codes = {
        str(code)
        for code in wb_result.index.get_level_values("country_code")
    }

    check(
        "WorldBank fetch_data required + context: India + USA "
        "both present",
        {"IND", "USA"}.issubset(wb_codes),
        str(sorted(wb_codes)),
    )

    check(
        "context fill reaches min_countries (>= 6 countries)",
        len(wb_codes) >= 6,
        f"{len(wb_codes)} countries",
    )

    # Missing-country graceful skip at the data layer.

    wb_result_missing = WorldBankData.fetch_data(
        indicator_code="MS.MIL.XPND.GD.ZS",
        years=10,
        story_type="biggest_jump",
        min_countries=6,
        countries=["Brazil", "India"],
    )

    wb_missing_codes = {
        str(code)
        for code in (
            wb_result_missing
            .index
            .get_level_values("country_code")
        )
    }

    check(
        "WorldBank fetch_data: Brazil (no data) dropped, "
        "India kept",
        "BRA" not in wb_missing_codes and "IND" in wb_missing_codes,
        str(sorted(wb_missing_codes)),
    )

except Exception as error:

    check(
        "WorldBank country-constrained fetch ran without error",
        False,
        str(error),
    )

finally:

    WorldBankData._request = ORIGINAL_REQUEST
    WorldBankData._countries_cache = None


# =========================================================
print()
print("[7] DEMONYMS + 'us' STOPWORD + STORY-FOCUS PREFERENCE")
# =========================================================

from app.topic.smart_story import StoryCandidate

check(
    "offline demonym detection: 'American ... vs Chinese' -> "
    "USA, China",
    ManualTopicEngine._detect_country_tokens(
        "american military spending vs chinese"
    ) == ["USA", "China"],
    str(ManualTopicEngine._detect_country_tokens(
        "american military spending vs chinese"
    )),
)

check(
    "exact-name detection unchanged",
    ManualTopicEngine._detect_country_tokens(
        "india vs usa military"
    ) == ["India", "USA"],
)

check(
    "'us' is skipped offline as a stopword (China still found); "
    "LLM-validated answer wins when reachable",
    ManualTopicEngine._detect_country_tokens(
        "us vs china gdp"
    ) == ["China"],
    str(ManualTopicEngine._detect_country_tokens("us vs china gdp")),
)


def seam_us(k, names):
    return {
        "indicator": "Military Expenditure (% of GDP)",
        "countries": ["USA", "China"],
    }


ManualTopicEngine._llm_semantic_pick = staticmethod(seam_us)

try:

    td_us = ManualTopicEngine.generate_manual_topic(
        "US vs China military",
        provider_ids=[FAKE_ID],
        seed=3,
    )

    us_ok = True

except ManualTopicError:

    us_ok = False

check(
    "'US vs China military' resolves via the LLM seam "
    "(LLM-answer-wins over the 'us' stopword)",
    us_ok,
)

if us_ok:

    check(
        "selected_countries == ['USA', 'China'] "
        "despite the 'us' stopword",
        td_us["selected_countries"] == ["USA", "China"],
        str(td_us["selected_countries"]),
    )


def fake_candidate(score, entity):
    return StoryCandidate(
        provider_id="worldbank",
        indicator_code="X",
        indicator_name="X",
        story_type="trend_over_time",
        chart_type="line",
        topic_family="general",
        years=10,
        category="World Data",
        source_name="s",
        source_url="u",
        topic="t",
        score=score,
        metrics={"entity": entity},
    )


other_winner = fake_candidate(60, "Somalia")
india_story = fake_candidate(50, "India")

check(
    "story-focus preference picks the requested-country story "
    "over a higher-scoring other-country story",
    ManualTopicEngine._prefer_requested_country(
        [other_winner, india_story],
        ["India", "USA"],
    ) is india_story,
)

check(
    "graceful fallback: never lowers quality when no requested-"
    "country story exists",
    ManualTopicEngine._prefer_requested_country(
        [other_winner],
        ["India", "USA"],
    ) is other_winner,
)

check(
    "no country hint -> unchanged best candidate",
    ManualTopicEngine._prefer_requested_country(
        [other_winner, india_story],
        None,
    ) is other_winner,
)


# =========================================================
print()
print("[8] SUPERLATIVE QUERIES: detection, wealth decline,")
print("    Wikipedia entity route (all offline seams)")
# =========================================================

# --- [8a] superlative detection (pure regex, no seams) ---

SUPERLATIVE_CASES = [
    # (keyword, expect_detected)
    ("richest person in India", True),
    ("India richest person", True),
    ("India's richest person", True),
    ("tallest building in Dubai", True),
    ("most popular actor in India", True),
    ("most followed athlete in Brazil", True),
    ("biggest company in Japan", True),
    ("Japan's biggest tech company", True),
    ("biggest tech company in China", True),
    ("oldest university in the world", True),
    ("most expensive car in the world", True),
    ("top 5 universities in Europe", True),
    # must NOT detect (stay on existing paths)
    ("gdp of India", False),
    ("biggest gdp in India", False),
    ("India largest population", False),
    ("Tesla vs BYD", False),
    ("India vs USA military", False),
    ("premier league standings", False),
    ("popular video games 2026", False),
]

for _kw, _expect in SUPERLATIVE_CASES:

    _got = ManualTopicEngine._detect_superlative_query(_kw)

    check(
        f"superlative detection {_kw!r} -> "
        f"{'match' if _expect else 'None'}",
        bool(_got) == _expect,
        str(_got) if _got else "",
    )

# --- [8b] wealth queries decline honestly, BEFORE any LLM ---

original_superlative_seam = (
    ManualTopicEngine._llm_superlative_entities
)
original_semantic_seam = (
    ManualTopicEngine._llm_semantic_pick
)


def _seam_must_not_fire(*_args, **_kwargs):
    raise AssertionError(
        "LLM seam reached -- wealth query was not "
        "declined before the LLM stage"
    )


ManualTopicEngine._llm_superlative_entities = (
    staticmethod(_seam_must_not_fire)
)
ManualTopicEngine._llm_semantic_pick = staticmethod(
    _seam_must_not_fire
)

try:

    _label_w, _matches_w, _hint_w = (
        ManualTopicEngine.resolve_topic_path(
            "India richest person"
        )
    )

    check(
        "'India richest person' declines honestly "
        "(no matches, no LLM call)",
        _matches_w == []
        and "wealth ranking declined" in _label_w,
        f"label={_label_w!r}",
    )

    _label_w2, _matches_w2, _ = (
        ManualTopicEngine.resolve_topic_path(
            "India's richest person"
        )
    )

    check(
        "possessive wealth form declines too",
        _matches_w2 == []
        and "wealth ranking declined" in _label_w2,
    )

    # Country-noun wealth ("richest country in Europe") is
    # answerable from GDP/GNI data -- it must NOT decline.
    # The boom seam makes _semantic_matches degrade to
    # (None, [], None), so the resolver falls through to
    # offline behavior instead of the decline label.

    _label_c, _matches_c, _ = (
        ManualTopicEngine.resolve_topic_path(
            "richest country in Europe"
        )
    )

    check(
        "'richest country in Europe' NOT declined "
        "(stays on country/indicator path)",
        "wealth ranking declined" not in _label_c,
        f"label={_label_c!r}",
    )

finally:

    ManualTopicEngine._llm_superlative_entities = (
        original_superlative_seam
    )
    ManualTopicEngine._llm_semantic_pick = (
        original_semantic_seam
    )

# --- [8c] non-wealth superlative -> Wikipedia entity route ---

from app.data.providers.wikipedia import (
    WikipediaPageviewsProvider,
)

_original_probe = WikipediaPageviewsProvider.probe_entities


def _seam_actor_proposals(keyword, superlative, noun, scope):
    return [
        {
            "name": "Shah Rukh Khan",
            "wikipedia_title": "Shah Rukh Khan",
        },
        {
            "name": "Salman Khan",
            "wikipedia_title": "Salman Khan",
        },
        {
            "name": "Aamir Khan",
            "wikipedia_title": "Aamir Khan",
        },
    ]


def _probe_verified_all(proposals):
    verified = {
        p["name"]: p["wikipedia_title"]
        for p in proposals
    }
    return verified, []


def _probe_verified_one(proposals):
    first = proposals[0]
    return (
        {first["name"]: first["wikipedia_title"]},
        [p["name"] for p in proposals[1:]],
    )


def _seam_no_entities(keyword, superlative, noun, scope):
    return None


def _seam_semantic_none(keyword, indicator_names):
    return {"indicator": None, "countries": ["India"]}


def _seam_country_proposals(
    keyword, superlative, noun, scope
):
    return [
        {"name": "India", "wikipedia_title": "India"},
        {"name": "China", "wikipedia_title": "China"},
    ]


ManualTopicEngine._llm_semantic_pick = staticmethod(
    _seam_semantic_none
)
ManualTopicEngine._llm_superlative_entities = staticmethod(
    _seam_actor_proposals
)
WikipediaPageviewsProvider.probe_entities = staticmethod(
    _probe_verified_all
)

try:

    _label_s, _matches_s, _hint_s = (
        ManualTopicEngine.resolve_topic_path(
            "most popular actor in India"
        )
    )

    check(
        "'most popular actor in India' routes to Wikipedia",
        bool(_matches_s)
        and _matches_s[0][0] == "wikipedia",
        f"label={_label_s!r}",
    )

    check(
        "Wikipedia route carries the verified entity hint",
        _hint_s
        == [
            "Shah Rukh Khan",
            "Salman Khan",
            "Aamir Khan",
        ],
        str(_hint_s),
    )

    check(
        "route label is honestly framed (search interest, "
        "NOT verified rankings)",
        "search interest" in _label_s
        and "NOT verified" in _label_s,
    )

    # Fewer than 2 verifiable entities -> fall through
    # unchanged (no wikipedia route).
    WikipediaPageviewsProvider.probe_entities = (
        staticmethod(_probe_verified_one)
    )

    _label_f, _matches_f, _ = (
        ManualTopicEngine.resolve_topic_path(
            "most popular actor in India"
        )
    )

    check(
        "<2 verified entities -> falls through "
        "(no wikipedia route)",
        not _matches_f
        or _matches_f[0][0] != "wikipedia",
        f"label={_label_f!r}",
    )

    # LLM proposes only countries -> keep the country path.
    ManualTopicEngine._llm_superlative_entities = (
        staticmethod(_seam_country_proposals)
    )
    WikipediaPageviewsProvider.probe_entities = (
        staticmethod(_probe_verified_all)
    )

    _label_cn, _matches_cn, _ = (
        ManualTopicEngine.resolve_topic_path(
            "most popular actor in India"
        )
    )

    check(
        "all-country proposals keep the country path",
        not _matches_cn
        or _matches_cn[0][0] != "wikipedia",
        f"label={_label_cn!r}",
    )

    # LLM proposes nothing real -> fall through unchanged.
    ManualTopicEngine._llm_superlative_entities = (
        staticmethod(_seam_no_entities)
    )

    _label_n, _matches_n, _ = (
        ManualTopicEngine.resolve_topic_path(
            "most popular actor in India"
        )
    )

    check(
        "LLM proposes no entities -> falls through unchanged",
        not _matches_n
        or _matches_n[0][0] != "wikipedia",
    )

finally:

    ManualTopicEngine._llm_semantic_pick = (
        original_semantic_seam
    )
    ManualTopicEngine._llm_superlative_entities = (
        original_superlative_seam
    )
    WikipediaPageviewsProvider.probe_entities = (
        _original_probe
    )


# =========================================================
print()
print("=" * 70)
total_failed = len(RESULT["failed"])
print(
    f"RESULT: {RESULT['passed']} PASSED / {total_failed} FAILED"
)
print("=" * 70)

def test_step1_step2_consistency():
    """Real pytest guard for the checks executed at import.

    Same failure mode as test_manual_topic_shape_parity.py: this
    module ended in a bare ``sys.exit(0)``, so importing it under
    pytest killed the whole session (INTERNALERROR: SystemExit)
    and nothing it verifies could ever reach a pytest report.
    The checks still run while the module loads; this turns their
    RESULT tally into an actual assertion instead of an exit code.
    """
    failed = list(RESULT["failed"])
    if failed:
        print("FAILED CHECKS:")
        for name in failed:
            print(f"  - {name}")
    assert not failed, (
        f"{len(failed)} step1/step2 consistency check(s) "
        f"failed: {failed}"
    )


if __name__ == "__main__":
    if total_failed:
        sys.exit(1)

    print("\nPASS: Step1/Step2 consistency and country hints work.")
    sys.exit(0)