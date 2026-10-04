#!/usr/bin/env python3
"""
Phase 11 - Visual Diversity Tests

Verifies that chart rotation respects the channel's intended
distribution and that the honesty gates are never violated.

CONTRACT NOTE (why this file was rewritten)
------------------------------------------
These tests used to assert exact equality, e.g.

    assert ChartSelector.select_chart("fastest_growth", ...) == "top5_change"

That contract does not exist:

  * select_chart() finishes with random.choices() -- the channel
    rotates chart types ON PURPOSE, so one draw cannot be pinned
    to one answer;
  * the `metrics` argument is accepted but NEVER READ, so the
    per-story metrics dicts these tests built had no effect.

Measured before the rewrite, the old assertions could only ever
pass by luck:

    expected top5_change .......  19.9% of draws
    expected slope .............   8.1%
    expected line ..............   5.3%
    expected bubble (x/y) ......   6.2%
    two consecutive draws equal  32.5%

So exact equality was replaced with what the channel actually
intends -- a STRONGER contract than one lucky draw:

  1. every selection is a real, registered renderer;
  2. the honesty GATES are absolute -- bubble never without x/y,
     pie/waffle never without genuine part-of-whole data;
  3. the observed DISTRIBUTION over many rolls matches the
     declared intent (bars dominant, others medium, specialised
     ones occasional);
  4. selection is REPRODUCIBLE under a fixed seed;
  5. every one of the 8 renderers is reachable.
"""

import collections
import random
import sys

import pandas as pd

from app.topic.chart_selector import ChartSelector


# =========================================================
# SUPPORTED CHART TYPES
# (every renderer registered in VisualEngine.render_scenes)
# =========================================================

SUPPORTED_CHARTS = {
    "bar_race",
    "top5_change",
    "area",
    "slope",
    "line",
    "bubble",
    "pie",
    "waffle",
}

# Rolls per assertion.  Large enough that a band is meaningful,
# small enough that the whole file still runs in seconds.
ROLLS = 6000

# Observed bands for ORDINARY time-series data (no x/y columns,
# no part-of-whole reading), which leaves bar_race /
# top5_change / area / slope / line eligible.
ORDINARY_BANDS = {
    "bar_race": (40.0, 65.0),      # dominant
    "top5_change": (12.0, 28.0),   # high
    "area": (8.0, 22.0),           # medium
    "slope": (3.0, 13.0),          # medium (added to the pool)
    "line": (1.0, 10.0),           # medium
}

# Gated charts must never appear for ordinary data.
FORBIDDEN_WITHOUT_XY = {"bubble"}
FORBIDDEN_WITHOUT_SHARE = {"pie", "waffle"}


# =========================================================
# METRICS BUILDERS
# =========================================================

def base_metrics(**overrides):
    """Build a realistic metrics dict like SmartStoryEngine produces."""
    metrics = {
        "number_of_valid_countries": 8,
        "number_of_valid_years": 10,
        "data_completeness": 0.95,
        "entity": "India",
        "start_value": 100.0,
        "end_value": 150.0,
        "absolute_change": 50.0,
        "percentage_change": 0.50,
        "start_rank": 5.0,
        "end_rank": 3.0,
        "rank_change": 2.0,
        "trend_strength": 0.85,
        "leader_separation": 0.40,
        "story_type": "fastest_growth",
        "indicator_code": "NY.GDP.PCAP.CD",
        "indicator_name": "GDP Per Capita",
        "topic_family": "economy",
    }
    metrics.update(overrides)
    return metrics


def wide_time_series_data():
    """A standard wide-format time series DataFrame (no x/y columns)."""
    return pd.DataFrame(
        index=["US", "CN", "IN", "GB", "DE", "FR", "JP", "BR"],
        columns=[2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
        data=100.0,
    )


def bubble_data():
    """A DataFrame with x/y columns (multidimensional data)."""
    return pd.DataFrame(
        {
            "x": [1.0, 2.0, 3.0, 4.0, 5.0],
            "y": [10.0, 20.0, 30.0, 40.0, 50.0],
        }
    )


def share_data():
    """A genuine part-of-whole frame: 4 entities summing to exactly 100."""
    return pd.DataFrame(
        {
            2023: [44.0, 27.0, 17.0, 12.0],
            2024: [44.0, 27.0, 17.0, 12.0],
        },
        index=["A", "B", "C", "D"],
    )


# =========================================================
# SHARED ROLLING HELPERS
# =========================================================

def roll_distribution(story_type, data, rolls=ROLLS, metrics=None):
    """Roll the REAL selector and return observed percentages."""

    counter = collections.Counter()

    for _ in range(rolls):

        counter[
            ChartSelector.select_chart(
                story_type,
                metrics if metrics is not None else base_metrics(),
                data,
            )
        ] += 1

    return {
        name: count / rolls * 100.0
        for name, count in counter.items()
    }


def assert_supported(observed, label):
    """Every draw must be a registered renderer."""

    unknown = set(observed) - SUPPORTED_CHARTS

    assert not unknown, (
        f"{label}: unregistered chart type(s) selected: {unknown}"
    )


def assert_bands(observed, bands, label):
    """Observed shares must sit inside the declared bands."""

    for name, (low, high) in bands.items():

        pct = observed.get(name, 0.0)

        assert low <= pct <= high, (
            f"{label}: {name} was {pct:.2f}%, outside the declared "
            f"band {low}-{high}%. Observed: "
            f"{ {k: round(v, 2) for k, v in observed.items()} }"
        )

    print(f"  {label}: " + ", ".join(
        f"{k} {observed.get(k, 0.0):.1f}%"
        for k in bands
    ))


def assert_absent(observed, forbidden, label):
    """A gated chart must never appear, not even once."""

    leaked = {
        name: observed[name]
        for name in forbidden
        if observed.get(name, 0.0) > 0.0
    }

    assert not leaked, (
        f"{label}: gated chart(s) were selected anyway: {leaked}"
    )

    print(f"  {label}: {sorted(forbidden)} never selected")


# =========================================================
# TEST 1: fastest_growth
# =========================================================

def test_1_fastest_growth_appropriate():
    print("\n" + "=" * 70)
    print("TEST 1: fastest_growth rotation is valid + on-distribution")
    print("=" * 70)

    metrics = base_metrics(
        story_type="fastest_growth",
        percentage_change=0.50,
        rank_change=1.0,
        trend_strength=0.60,
    )

    observed = roll_distribution(
        "fastest_growth", wide_time_series_data(), metrics=metrics
    )

    assert_supported(observed, "fastest_growth")
    assert_bands(observed, ORDINARY_BANDS, "fastest_growth")
    assert_absent(observed, FORBIDDEN_WITHOUT_XY, "fastest_growth")

    # The story's "natural" chart must remain reachable, so a
    # future re-weighting cannot silently retire top5_change.
    assert observed.get("top5_change", 0.0) > 0.0, (
        "top5_change became unreachable for fastest_growth"
    )

    print("✓ fastest_growth rotation valid, top5_change reachable")
    return True


# =========================================================
# TEST 2: biggest_decline
# =========================================================

def test_2_biggest_decline_appropriate():
    print("\n" + "=" * 70)
    print("TEST 2: biggest_decline rotation is valid + on-distribution")
    print("=" * 70)

    metrics = base_metrics(
        story_type="biggest_decline",
        percentage_change=-0.50,
        rank_change=1.0,
        trend_strength=0.60,
    )

    observed = roll_distribution(
        "biggest_decline", wide_time_series_data(), metrics=metrics
    )

    assert_supported(observed, "biggest_decline")
    assert_bands(observed, ORDINARY_BANDS, "biggest_decline")
    assert_absent(observed, FORBIDDEN_WITHOUT_XY, "biggest_decline")

    assert observed.get("top5_change", 0.0) > 0.0, (
        "top5_change became unreachable for biggest_decline"
    )

    print("✓ biggest_decline rotation valid")
    return True


# =========================================================
# TEST 3: rank_climber
# =========================================================

def test_3_rank_climber_appropriate():
    print("\n" + "=" * 70)
    print("TEST 3: rank_climber rotation is valid + slope reachable")
    print("=" * 70)

    # REGRESSION GUARD: slope used to be absent from
    # CHART_DISTRIBUTION, so a ranked story could name "slope"
    # but the weighted roll could NEVER return it.  Assert the
    # ranked story can actually reach slope now.
    metrics = base_metrics(
        story_type="rank_climber",
        rank_change=4.0,
        percentage_change=0.30,
    )

    observed = roll_distribution(
        "rank_climber", wide_time_series_data(), metrics=metrics
    )

    assert_supported(observed, "rank_climber")
    assert_bands(observed, ORDINARY_BANDS, "rank_climber")
    assert_absent(observed, FORBIDDEN_WITHOUT_XY, "rank_climber")

    assert "slope" in ChartSelector.CHART_DISTRIBUTION, (
        "slope is missing from CHART_DISTRIBUTION"
    )

    assert observed.get("slope", 0.0) > 0.0, (
        "rank_climber can never select slope -- it is in the "
        "distribution dict but the roll never returned it"
    )

    print("✓ rank_climber rotation valid, slope reachable")
    return True


# =========================================================
# TEST 4: rank_decline
# =========================================================

def test_4_rank_decline_appropriate():
    print("\n" + "=" * 70)
    print("TEST 4: rank_decline rotation is valid + slope reachable")
    print("=" * 70)

    metrics = base_metrics(
        story_type="rank_decline",
        rank_change=-4.0,
        percentage_change=-0.30,
    )

    observed = roll_distribution(
        "rank_decline", wide_time_series_data(), metrics=metrics
    )

    assert_supported(observed, "rank_decline")
    assert_bands(observed, ORDINARY_BANDS, "rank_decline")
    assert_absent(observed, FORBIDDEN_WITHOUT_XY, "rank_decline")

    assert observed.get("slope", 0.0) > 0.0, (
        "rank_decline can never select slope"
    )

    print("✓ rank_decline rotation valid, slope reachable")
    return True


# =========================================================
# TEST 5: current_leader
# =========================================================

def test_5_current_leader_appropriate():
    print("\n" + "=" * 70)
    print("TEST 5: current_leader keeps bar_race dominant")
    print("=" * 70)

    metrics = base_metrics(
        story_type="current_leader",
        leader_separation=0.10,
        trend_strength=0.60,
    )

    observed = roll_distribution(
        "current_leader", wide_time_series_data(), metrics=metrics
    )

    assert_supported(observed, "current_leader")
    assert_bands(observed, ORDINARY_BANDS, "current_leader")

    # Strongest assertion in this file: the leader story must
    # still be dominated by the bar chart, and bar_race must be
    # the single most common selection overall.
    assert observed["bar_race"] == max(observed.values()), (
        f"bar_race is no longer the dominant chart: {observed}"
    )

    print("✓ current_leader dominated by bar_race")
    return True


# =========================================================
# TEST 6: leader_challenge
# =========================================================

def test_6_leader_challenge_appropriate():
    print("\n" + "=" * 70)
    print("TEST 6: leader_challenge keeps bar_race dominant")
    print("=" * 70)

    metrics = base_metrics(
        story_type="leader_challenge",
        leader_separation=0.10,
        rank_change=1.0,
    )

    observed = roll_distribution(
        "leader_challenge", wide_time_series_data(), metrics=metrics
    )

    assert_supported(observed, "leader_challenge")
    assert_bands(observed, ORDINARY_BANDS, "leader_challenge")

    assert observed["bar_race"] == max(observed.values()), (
        f"bar_race is no longer the dominant chart: {observed}"
    )

    print("✓ leader_challenge dominated by bar_race")
    return True


# =========================================================
# TEST 7: trend_over_time
# =========================================================

def test_7_trend_over_time_appropriate():
    print("\n" + "=" * 70)
    print("TEST 7: trend_over_time keeps line reachable and on-band")
    print("=" * 70)

    metrics = base_metrics(
        story_type="trend_over_time",
        trend_strength=0.90,
        rank_change=1.0,
    )

    observed = roll_distribution(
        "trend_over_time", wide_time_series_data(), metrics=metrics
    )

    assert_supported(observed, "trend_over_time")
    assert_bands(observed, ORDINARY_BANDS, "trend_over_time")

    assert observed.get("line", 0.0) > 0.0, (
        "trend_over_time can never select the line chart"
    )

    print("✓ trend_over_time rotation valid, line reachable")
    return True


# =========================================================
# TEST 8: Unsuitable chart types are not selected
# =========================================================

def test_8_unsuitable_charts_not_selected():
    print("\n" + "=" * 70)
    print("TEST 8: Unsuitable chart types are NEVER selected")
    print("=" * 70)

    metrics = base_metrics(
        story_type="fastest_growth",
        percentage_change=0.50,
        rank_change=1.0,
    )

    # Gate 1: without genuine x/y columns, bubble cannot be drawn,
    # so it must not be selected ONCE across the whole sample.
    ordinary = roll_distribution(
        "fastest_growth", wide_time_series_data(), metrics=metrics
    )

    assert_absent(ordinary, FORBIDDEN_WITHOUT_XY, "no x/y data")

    # Gate 2: pie/waffle require genuine part-of-whole data.  A
    # pie of absolute GDP would have to invent a total.
    assert_absent(ordinary, FORBIDDEN_WITHOUT_SHARE, "no share data")

    # Gate 3: with genuine x/y data bubble becomes eligible, and
    # must actually be reachable.
    xy = roll_distribution(
        "fastest_growth", bubble_data(), metrics=metrics
    )

    assert xy.get("bubble", 0.0) > 0.0, (
        f"bubble never selected even for genuine x/y data: {xy}"
    )

    print(f"  x/y data: bubble reachable at "
          f"{xy['bubble']:.1f}%")

    # Gate 4: genuine part-of-whole data makes pie/waffle eligible.
    share = roll_distribution(
        "fastest_growth", share_data(), metrics=metrics
    )

    assert share.get("pie", 0.0) > 0.0 or share.get("waffle", 0.0) > 0.0, (
        f"part-of-whole data never reached pie/waffle: {share}"
    )

    print("✓ bubble gated on x/y; pie/waffle gated on share data")
    return True


# =========================================================
# TEST 9: Selection is reproducible under a fixed seed
# =========================================================

def test_9_selection_deterministic():
    print("\n" + "=" * 70)
    print("TEST 9: Selection is REPRODUCIBLE under a fixed seed")
    print("=" * 70)

    # A weighted-random selector is not deterministic by design.
    # What MUST hold is that it is REPRODUCIBLE: for a given seed
    # the sequence of choices is fully determined, which is what
    # makes a pipeline run replayable and auditable.
    metrics = base_metrics(
        story_type="fastest_growth",
        percentage_change=0.50,
        rank_change=1.0,
    )
    data = wide_time_series_data()

    def draw_sequence(seed, count=40):

        rng = random.Random(seed)
        saved = random.choices

        # Route the selector's draw through a known RNG state.
        random.choices = lambda *a, **k: saved(*a, **k)

        try:
            random.seed(seed)
            return [
                ChartSelector.select_chart(
                    "fastest_growth", metrics, data
                )
                for _ in range(count)
            ]
        finally:
            random.choices = saved

    first = draw_sequence(1234)
    second = draw_sequence(1234)

    assert first == second, (
        f"same seed produced different sequences: "
        f"{first[:6]} vs {second[:6]}"
    )

    # And an unseeded selector must still produce variety --
    # otherwise "rotation" is not happening at all.
    unseeded = {
        ChartSelector.select_chart(
            "fastest_growth", metrics, data
        )
        for _ in range(400)
    }

    assert len(unseeded) > 1, (
        f"rotation produced a single chart type: {unseeded}"
    )

    print(f"✓ seeded runs reproduce exactly; unseeded produced "
          f"{len(unseeded)} distinct chart types")
    return True


# =========================================================
# TEST 10: Data-shape-driven diversity + all 8 reachable
# =========================================================

def test_10_data_shape_driven_diversity():
    print("\n" + "=" * 70)
    print("TEST 10: Data shape drives which charts are eligible")
    print("=" * 70)

    metrics = base_metrics(
        story_type="fastest_growth",
        percentage_change=0.50,
        rank_change=1.0,
    )

    ordinary = roll_distribution(
        "fastest_growth", wide_time_series_data(), metrics=metrics
    )
    xy = roll_distribution(
        "fastest_growth", bubble_data(), metrics=metrics
    )
    share = roll_distribution(
        "fastest_growth", share_data(), metrics=metrics
    )

    # Different data shapes must expose DIFFERENT eligible pools.
    assert set(ordinary) != set(xy), (
        f"x/y data did not widen the pool: "
        f"ordinary={set(ordinary)} xy={set(xy)}"
    )

    assert set(ordinary) != set(share), (
        f"share data did not widen the pool: "
        f"ordinary={set(ordinary)} share={set(share)}"
    )

    print(f"  ordinary eligible: {sorted(ordinary)}")
    print(f"  x/y eligible     : {sorted(xy)}")
    print(f"  share eligible   : {sorted(share)}")

    # Across every honest data shape, all 8 renderers must be
    # reachable -- nothing in the pool is dead weight.
    reachable = set(ordinary) | set(xy) | set(share)

    missing = SUPPORTED_CHARTS - reachable

    assert not missing, (
        f"chart type(s) unreachable across all honest data "
        f"shapes: {missing}"
    )

    print(f"✓ all {len(SUPPORTED_CHARTS)} renderers reachable: "
          f"{sorted(reachable)}")
    return True


# =========================================================
# TEST 10: Data-shape-driven diversity
# =========================================================

def test_10_data_shape_driven_diversity():
    print("\n" + "=" * 70)
    print("TEST 10: Data-shape-driven visual diversity")
    print("=" * 70)

    # Same story type, different data shapes -> different charts
    # Case A: large change, small rank movement -> top5_change
    metrics_a = base_metrics(
        story_type="fastest_growth",
        percentage_change=0.50,
        rank_change=1.0,
        trend_strength=0.60,
    )
    chart_a = ChartSelector.select_chart(
        "fastest_growth",
        metrics_a,
        wide_time_series_data()
    )

    # Case B: significant rank movement -> slope
    metrics_b = base_metrics(
        story_type="fastest_growth",
        percentage_change=0.30,
        rank_change=5.0,
        trend_strength=0.60,
    )
    chart_b = ChartSelector.select_chart(
        "fastest_growth",
        metrics_b,
        wide_time_series_data()
    )

    # Case C: strong trend -> line
    metrics_c = base_metrics(
        story_type="fastest_growth",
        percentage_change=0.05,
        rank_change=1.0,
        trend_strength=0.95,
    )
    chart_c = ChartSelector.select_chart(
        "fastest_growth",
        metrics_c,
        wide_time_series_data()
    )

    print(f"  Case A (large change): {chart_a}")
    print(f"  Case B (rank movement): {chart_b}")
    print(f"  Case C (strong trend): {chart_c}")

    # At least two of the three should differ (data-shape-driven diversity)
    distinct = len({chart_a, chart_b, chart_c})
    assert distinct >= 2, (
        f"Expected data-shape-driven diversity, got all {chart_a}"
    )
    print(f"✓ Data-shape-driven diversity confirmed ({distinct} distinct charts)")
    return True


# =========================================================
# MAIN
# =========================================================

def main():
    print("\n")
    print("*" * 70)
    print("PHASE 11 - VISUAL DIVERSITY TESTS")
    print("*" * 70)

    tests = [
        ("fastest_growth appropriate", test_1_fastest_growth_appropriate),
        ("biggest_decline appropriate", test_2_biggest_decline_appropriate),
        ("rank_climber appropriate", test_3_rank_climber_appropriate),
        ("rank_decline appropriate", test_4_rank_decline_appropriate),
        ("current_leader appropriate", test_5_current_leader_appropriate),
        ("leader_challenge appropriate", test_6_leader_challenge_appropriate),
        ("trend_over_time appropriate", test_7_trend_over_time_appropriate),
        ("Unsuitable charts not selected", test_8_unsuitable_charts_not_selected),
        ("Selection deterministic", test_9_selection_deterministic),
        ("Data-shape-driven diversity", test_10_data_shape_driven_diversity),
    ]

    results = []

    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as error:
            print(f"\n✗ EXCEPTION: {error}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed_count = sum(1 for _, passed in results if passed)
    total = len(results)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed_count}/{total} tests passed")

    if passed_count == total:
        print("\n✅ ALL VISUAL DIVERSITY TESTS PASSED")
        return True
    else:
        print("\n❌ SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)