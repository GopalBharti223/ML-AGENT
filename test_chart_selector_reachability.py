"""
ChartSelector reachability + weight-normalisation contract.

Offline and deterministic: fixtures only, no network.

WHY THESE EXIST
---------------
An earlier audit reported pie/waffle as "effectively unreachable
(0% over 3000 rolls)".  That finding was WRONG, and the cause is
exactly what these tests pin down: the harness had called

    select_chart("current_leader", share_frame)   # 2 positional args

so the DataFrame landed in the `metrics` slot and `data` stayed
None.  With `data=None` the part-of-whole gate correctly reports
no eligible share charts and drops both -- which looks identical
to "pie is unreachable".

Production calls the 3-argument form (app/topic/smart_story.py),
where pie and waffle are reachable at their configured weights.
A test that measures reachability without pinning the argument
position is what let the false finding survive.
"""

import collections
import random

import pandas as pd
import pytest

from app.topic.chart_selector import ChartSelector


def _share_frame():
    """Genuinely part-of-whole: 44+27+17+12 == 100."""
    return pd.DataFrame(
        {2021: [44.0, 27.0, 17.0, 12.0]},
        index=["A", "B", "C", "D"],
    )


def _xy_frame():
    return pd.DataFrame(
        {"x": [1.0, 2.0, 3.0, 4.0], "y": [4.0, 3.0, 2.0, 1.0]},
        index=["A", "B", "C", "D"],
    )


def _ts_frame():
    return pd.DataFrame(
        {2019: [1.0, 2.0, 3.0, 4.0], 2022: [4.0, 3.0, 2.0, 1.0]},
        index=["A", "B", "C", "D"],
    )


def _rolls(story, data, n=4000, seed=7):
    random.seed(seed)
    return collections.Counter(
        ChartSelector.select_chart(story, {}, data)
        for _ in range(n)
    )


# -------------------------------------------------------------
# 1. The call shape matters -- the regression behind the false
#    "unreachable" finding.
# -------------------------------------------------------------

def test_pie_waffle_reachable_with_correct_three_arg_call():
    """data in the 3rd slot -> share charts ARE selectable."""
    counts = _rolls("current_leader", _share_frame())

    assert counts["pie"] > 0, "pie unreachable with valid share data"
    assert counts["waffle"] > 0, "waffle unreachable"


def test_pie_waffle_absent_when_no_data_supplied():
    """data=None -> correctly gated out. This is NOT a bug."""
    counts = _rolls("current_leader", None)

    assert "pie" not in counts
    assert "waffle" not in counts


def test_metrics_argument_alone_cannot_enable_share_charts():
    """A DataFrame in the metrics slot must NOT unlock pie."""
    random.seed(7)
    counts = collections.Counter(
        ChartSelector.select_chart("current_leader", _share_frame())
        for _ in range(2000)
    )

    assert "pie" not in counts, (
        "pie was unlocked by a DataFrame passed as `metrics`"
    )


# -------------------------------------------------------------
# 2. Weights are preserved among the eligible set.
# -------------------------------------------------------------

def test_share_charts_keep_their_relative_weights():
    """pie and waffle have equal global weight -> ~equal share."""
    counts = _rolls("current_leader", _share_frame(), n=8000)
    total = sum(counts.values())

    pie = counts["pie"] / total
    waffle = counts["waffle"] / total

    configured = ChartSelector.CHART_DISTRIBUTION["pie"]

    assert pie == pytest.approx(waffle, abs=0.02)
    assert pie == pytest.approx(configured, abs=0.02)


def test_production_distribution_not_distorted():
    """bar_race must remain dominant for a plain time series."""
    counts = _rolls("rank_climber", _ts_frame(), n=8000)
    total = sum(counts.values())

    bar = (
        counts["bar_race"] + counts["top5_change"]
    ) / total

    assert bar > 0.60, "horizontal-bar character was lost"
    assert "pie" not in counts
    assert "waffle" not in counts


def test_relative_weights_preserved_across_eligible_set():
    """Observed proportions track the NORMALISED configured ones.

    The config sums to 1.04, and gating removes bubble / pie /
    waffle for a plain time series, so the eligible pool sums to
    0.90.  The contract is therefore

        observed(chart) == weight(chart) / sum(eligible weights)

    not "observed == the raw configured number" -- asserting the
    raw value would be wrong whenever any chart is gated out.
    """
    counts = _rolls("rank_climber", _ts_frame(), n=12000)
    total = sum(counts.values())

    # Mirror the production gates to build the eligible pool.
    eligible = dict(ChartSelector.CHART_DISTRIBUTION)

    if not ChartSelector.supports_bubble(_ts_frame()):
        eligible.pop("bubble", None)

    allowed_share = ChartSelector._eligible_share_charts(
        "rank_climber", _ts_frame()
    )

    for chart in ("pie", "waffle"):
        if chart not in allowed_share:
            eligible.pop(chart, None)

    pool = sum(eligible.values())

    for chart, weight in eligible.items():

        observed = counts[chart] / total
        expected = weight / pool

        assert observed == pytest.approx(
            expected, abs=0.025
        ), chart


def test_share_charts_normalise_within_eligible_pool():
    """pie and waffle have equal weight, so equal observed share."""
    counts = _rolls("current_leader", _share_frame(), n=12000)
    total = sum(counts.values())

    eligible = dict(ChartSelector.CHART_DISTRIBUTION)
    allowed = ChartSelector._eligible_share_charts(
        "current_leader", _share_frame()
    )

    for chart in ("pie", "waffle"):
        if chart not in allowed:
            eligible.pop(chart, None)

    pool = sum(eligible.values())

    expected = (
        ChartSelector.CHART_DISTRIBUTION["pie"] / pool
    )

    assert counts["pie"] / total == pytest.approx(
        expected, abs=0.02
    )
    assert counts["waffle"] / total == pytest.approx(
        expected, abs=0.02
    )


# -------------------------------------------------------------
# 3. Gating still forbids invalid charts.
# -------------------------------------------------------------

def test_bubble_requires_xy_columns():
    assert "bubble" in _rolls("fastest_growth", _xy_frame())

    counts = _rolls("fastest_growth", pd.DataFrame(
        {2019: [1.0, 2.0], 2022: [2.0, 1.0]},
        index=["A", "B"],
    ))

    assert "bubble" not in counts


def test_share_charts_rejected_for_non_share_data():
    """Absolute values must not become a pie with an invented total."""
    absolute = pd.DataFrame(
        {2021: [4.0e11, 2.7e11, 1.7e11, 1.2e11]},
        index=["A", "B", "C", "D"],
    )

    counts = _rolls("fastest_growth", absolute)

    assert "pie" not in counts
    assert "waffle" not in counts


# -------------------------------------------------------------
# 4. Determinism.
# -------------------------------------------------------------

def test_seeded_selection_is_reproducible():
    frame = _share_frame()

    random.seed(4242)
    first = [
        ChartSelector.select_chart("current_leader", {}, frame)
        for _ in range(300)
    ]

    random.seed(4242)
    second = [
        ChartSelector.select_chart("current_leader", {}, frame)
        for _ in range(300)
    ]

    assert first == second


def test_unseeded_selection_varies():
    """Otherwise rotation would not be happening at all."""
    random.seed(1)

    draws = [
        ChartSelector.select_chart("current_leader", {}, _share_frame())
        for _ in range(2000)
    ]

    assert len(set(draws)) > 1


# -------------------------------------------------------------
# 5. All eight charts remain reachable where legitimately valid.
# -------------------------------------------------------------

def test_all_eight_chart_types_stay_in_the_distribution():
    """No chart may be silently dropped from the config."""
    for chart in (
        "bar_race", "top5_change", "area", "slope",
        "line", "bubble", "pie", "waffle",
    ):
        assert chart in ChartSelector.CHART_DISTRIBUTION
        assert ChartSelector.CHART_DISTRIBUTION[chart] > 0