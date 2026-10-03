#!/usr/bin/env python3
"""
Phase 11 - Visual Diversity Tests

Verifies that different story types select appropriate visual formats
based on data shape and story characteristics, without randomness.

Tests:
1. fastest_growth selects an appropriate visualization
2. biggest_decline selects an appropriate visualization
3. rank_climber selects an appropriate visualization
4. rank_decline selects an appropriate visualization
5. current_leader selects an appropriate visualization
6. leader_challenge selects an appropriate visualization
7. trend_over_time selects an appropriate visualization
8. Unsuitable chart types are not selected
9. Selection is deterministic
10. Bubble is not selected without multidimensional data
"""

import sys

import pandas as pd

from app.topic.chart_selector import ChartSelector


# =========================================================
# SUPPORTED CHART TYPES (from VisualEngine.render_scenes)
# =========================================================

SUPPORTED_CHARTS = {
    "bar_race",
    "line",
    "slope",
    "bubble",
    "top5_change",
}


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


# =========================================================
# TEST 1: fastest_growth
# =========================================================

def test_1_fastest_growth_appropriate():
    print("=" * 70)
    print("TEST 1: fastest_growth selects appropriate visualization")
    print("=" * 70)

    # Large percent change, small rank movement -> top5_change
    metrics = base_metrics(
        story_type="fastest_growth",
        percentage_change=0.50,
        rank_change=1.0,
        trend_strength=0.60,
    )
    chart = ChartSelector.select_chart(
        "fastest_growth",
        metrics,
        wide_time_series_data()
    )

    print(f"  Selected chart: {chart}")
    assert chart in SUPPORTED_CHARTS, (
        f"Chart '{chart}' is not a supported chart type"
    )
    # Large change + small rank movement should prefer top5_change
    assert chart == "top5_change", (
        f"Expected top5_change for large change + small rank movement, "
        f"got {chart}"
    )
    print(f"✓ fastest_growth with large change → {chart}")
    return True


# =========================================================
# TEST 2: biggest_decline
# =========================================================

def test_2_biggest_decline_appropriate():
    print("\n" + "=" * 70)
    print("TEST 2: biggest_decline selects appropriate visualization")
    print("=" * 70)

    # Large negative change, small rank movement -> top5_change
    metrics = base_metrics(
        story_type="biggest_decline",
        percentage_change=-0.50,
        rank_change=1.0,
        trend_strength=0.60,
    )
    chart = ChartSelector.select_chart(
        "biggest_decline",
        metrics,
        wide_time_series_data()
    )

    print(f"  Selected chart: {chart}")
    assert chart in SUPPORTED_CHARTS, (
        f"Chart '{chart}' is not a supported chart type"
    )
    assert chart == "top5_change", (
        f"Expected top5_change for large decline + small rank movement, "
        f"got {chart}"
    )
    print(f"✓ biggest_decline with large decline → {chart}")
    return True


# =========================================================
# TEST 3: rank_climber
# =========================================================

def test_3_rank_climber_appropriate():
    print("\n" + "=" * 70)
    print("TEST 3: rank_climber selects appropriate visualization")
    print("=" * 70)

    # Significant rank movement -> slope
    metrics = base_metrics(
        story_type="rank_climber",
        rank_change=4.0,
        percentage_change=0.30,
    )
    chart = ChartSelector.select_chart(
        "rank_climber",
        metrics,
        wide_time_series_data()
    )

    print(f"  Selected chart: {chart}")
    assert chart in SUPPORTED_CHARTS, (
        f"Chart '{chart}' is not a supported chart type"
    )
    assert chart == "slope", (
        f"Expected slope for significant rank movement, got {chart}"
    )
    print(f"✓ rank_climber with significant rank movement → {chart}")
    return True


# =========================================================
# TEST 4: rank_decline
# =========================================================

def test_4_rank_decline_appropriate():
    print("\n" + "=" * 70)
    print("TEST 4: rank_decline selects appropriate visualization")
    print("=" * 70)

    # Significant rank movement -> slope
    metrics = base_metrics(
        story_type="rank_decline",
        rank_change=-4.0,
        percentage_change=-0.30,
    )
    chart = ChartSelector.select_chart(
        "rank_decline",
        metrics,
        wide_time_series_data()
    )

    print(f"  Selected chart: {chart}")
    assert chart in SUPPORTED_CHARTS, (
        f"Chart '{chart}' is not a supported chart type"
    )
    assert chart == "slope", (
        f"Expected slope for significant rank movement, got {chart}"
    )
    print(f"✓ rank_decline with significant rank movement → {chart}")
    return True


# =========================================================
# TEST 5: current_leader
# =========================================================

def test_5_current_leader_appropriate():
    print("\n" + "=" * 70)
    print("TEST 5: current_leader selects appropriate visualization")
    print("=" * 70)

    # Clear leader with small gap -> bar_race
    metrics = base_metrics(
        story_type="current_leader",
        leader_separation=0.10,
        trend_strength=0.60,
    )
    chart = ChartSelector.select_chart(
        "current_leader",
        metrics,
        wide_time_series_data()
    )

    print(f"  Selected chart: {chart}")
    assert chart in SUPPORTED_CHARTS, (
        f"Chart '{chart}' is not a supported chart type"
    )
    assert chart == "bar_race", (
        f"Expected bar_race for clear leader, got {chart}"
    )
    print(f"✓ current_leader with clear leader → {chart}")
    return True


# =========================================================
# TEST 6: leader_challenge
# =========================================================

def test_6_leader_challenge_appropriate():
    print("\n" + "=" * 70)
    print("TEST 6: leader_challenge selects appropriate visualization")
    print("=" * 70)

    # Close competition -> bar_race
    metrics = base_metrics(
        story_type="leader_challenge",
        leader_separation=0.10,
        rank_change=1.0,
    )
    chart = ChartSelector.select_chart(
        "leader_challenge",
        metrics,
        wide_time_series_data()
    )

    print(f"  Selected chart: {chart}")
    assert chart in SUPPORTED_CHARTS, (
        f"Chart '{chart}' is not a supported chart type"
    )
    assert chart == "bar_race", (
        f"Expected bar_race for close competition, got {chart}"
    )
    print(f"✓ leader_challenge with close competition → {chart}")
    return True


# =========================================================
# TEST 7: trend_over_time
# =========================================================

def test_7_trend_over_time_appropriate():
    print("\n" + "=" * 70)
    print("TEST 7: trend_over_time selects appropriate visualization")
    print("=" * 70)

    # Strong multi-year trend -> line
    metrics = base_metrics(
        story_type="trend_over_time",
        trend_strength=0.90,
        rank_change=1.0,
    )
    chart = ChartSelector.select_chart(
        "trend_over_time",
        metrics,
        wide_time_series_data()
    )

    print(f"  Selected chart: {chart}")
    assert chart in SUPPORTED_CHARTS, (
        f"Chart '{chart}' is not a supported chart type"
    )
    assert chart == "line", (
        f"Expected line for strong trend, got {chart}"
    )
    print(f"✓ trend_over_time with strong trend → {chart}")
    return True


# =========================================================
# TEST 8: Unsuitable chart types are not selected
# =========================================================

def test_8_unsuitable_charts_not_selected():
    print("\n" + "=" * 70)
    print("TEST 8: Unsuitable chart types are not selected")
    print("=" * 70)

    # Bubble should NOT be selected for standard time-series data
    metrics = base_metrics(
        story_type="fastest_growth",
        percentage_change=0.50,
        rank_change=1.0,
    )
    chart = ChartSelector.select_chart(
        "fastest_growth",
        metrics,
        wide_time_series_data()
    )

    assert chart != "bubble", (
        "Bubble should not be selected for standard time-series data"
    )
    print(f"✓ Bubble not selected for time-series data (got {chart})")

    # Bubble SHOULD be selected for multidimensional data with x/y
    chart_bubble = ChartSelector.select_chart(
        "fastest_growth",
        metrics,
        bubble_data()
    )
    assert chart_bubble == "bubble", (
        f"Expected bubble for x/y data, got {chart_bubble}"
    )
    print(f"✓ Bubble selected for genuine x/y data")
    return True


# =========================================================
# TEST 9: Selection is deterministic
# =========================================================

def test_9_selection_deterministic():
    print("\n" + "=" * 70)
    print("TEST 9: Selection is deterministic")
    print("=" * 70)

    metrics = base_metrics(
        story_type="fastest_growth",
        percentage_change=0.50,
        rank_change=1.0,
    )
    data = wide_time_series_data()

    chart1 = ChartSelector.select_chart(
        "fastest_growth",
        metrics,
        data
    )
    chart2 = ChartSelector.select_chart(
        "fastest_growth",
        metrics,
        data
    )

    assert chart1 == chart2, (
        f"Selection should be deterministic, got {chart1} vs {chart2}"
    )
    print(f"✓ Deterministic selection: {chart1} == {chart2}")
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