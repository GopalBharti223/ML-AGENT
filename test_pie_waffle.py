"""Regression + contract tests for the chart additions:

  PART 1 -- pie / donut renderer (share-of-total only)
  PART 2 -- waffle renderer + EXACT box-count apportionment
  PART 3 -- navy-tinted background tone
  PART 4 -- multi-colour-per-bar mode for bar_race / top5_change

Run:  python -m pytest test_pie_waffle.py -v
"""
import random

import pandas as pd
import pytest

from app.topic.chart_selector import ChartSelector
from app.visuals.scene_engine import VisualEngine


# ---------------------------------------------------------
# Fixtures
# ---------------------------------------------------------

def share_frame():
    """A genuine part-of-whole: 3 entities summing to 100."""
    return pd.DataFrame(
        {
            2020: [50.0, 30.0, 20.0],
            2021: [45.0, 35.0, 20.0],
        },
        index=["Ireland", "Guyana", "Georgia"],
    )


def absolute_frame():
    """Absolute values -- NOT a share of any total."""
    return pd.DataFrame(
        {
            2020: [1.0, 2.0, 3.0],
            2021: [2.0, 3.0, 4.0],
        },
        index=["Ireland", "Guyana", "Georgia"],
    )


def share_frame_6():
    return pd.DataFrame(
        {
            2020: [30.0, 25.0, 15.0, 12.0, 10.0, 8.0],
            2021: [28.0, 24.0, 16.0, 13.0, 11.0, 8.0],
        },
        index=list("ABCDEF"),
    )


# ---------------------------------------------------------
# PART 2 -- largest remainder is EXACT
# ---------------------------------------------------------

def test_largest_remainder_sums_exactly():
    """Every apportionment must total the requested boxes."""

    random.seed(7)

    for _ in range(300):

        count = random.randint(2, 6)

        shares = [
            random.uniform(0.5, 60.0)
            for _ in range(count)
        ]

        boxes = random.choice([10, 47, 99, 100, 100, 100])

        counts = VisualEngine.largest_remainder(
            shares, boxes
        )

        assert len(counts) == count
        assert sum(counts) == boxes, (
            f"largest_remainder({shares}, {boxes}) -> "
            f"{counts} sums to {sum(counts)}"
        )
        assert all(isinstance(c, int) for c in counts)
        assert all(c >= 0 for c in counts)


def test_largest_remainder_beats_naive_rounding():
    """Classic case where round() loses a box but L-R does not."""

    # 1/3, 1/3, 1/3 of 100 -> 33.33 each.
    # round() -> 33+33+33 = 99.  Largest remainder -> 100.
    thirds = [1.0, 1.0, 1.0]

    naive = [round(v / 3.0 * 100) for v in thirds]

    assert sum(naive) == 99, (
        f"fixture no longer demonstrates the defect: {naive}"
    )

    exact = VisualEngine.largest_remainder(thirds, 100)

    assert sum(exact) == 100, exact


def test_largest_remainder_edge_cases():
    assert VisualEngine.largest_remainder([], 100) == []
    assert VisualEngine.largest_remainder(
        [1.0, 2.0], 0
    ) == [0, 0]
    assert VisualEngine.largest_remainder(
        [0.0, 0.0], 100
    ) == [100, 0]


def test_real_share_data_yields_exact_100_boxes():
    """The exact math on the REAL numbers a share metric gives."""

    labels, values = VisualEngine._share_values(
        share_frame_6()
    )

    counts = VisualEngine.largest_remainder(values, 100)

    assert sum(counts) == 100, counts

    # And the counts track the shares, 1 box == 1 point.
    for value, count in zip(values, counts):
        assert abs(count - value) <= 1, (
            f"1 box should be 1 point: {value} -> {count}"
        )


# ---------------------------------------------------------
# PART 1 + 2 -- share-of-total gating
# ---------------------------------------------------------

def test_is_share_of_total_accepts_only_parts_of_a_whole():
    assert VisualEngine.is_share_of_total(share_frame()) is True
    assert VisualEngine.is_share_of_total(share_frame_6()) is True

    # Absolute series has no total to be a part of.
    assert VisualEngine.is_share_of_total(absolute_frame()) is False

    # Nothing to test.
    assert VisualEngine.is_share_of_total(None) is False
    assert VisualEngine.is_share_of_total(pd.DataFrame()) is False


def test_selector_and_renderer_agree_on_share_of_total():
    """The two implementations of the rule must not drift."""

    for frame in (
        share_frame(),
        share_frame_6(),
        absolute_frame(),
    ):
        assert (
            ChartSelector._share_of_total_data(frame)
            is VisualEngine.is_share_of_total(frame)
        ), "ChartSelector and VisualEngine disagree"


def test_pie_and_waffle_weights_exist():
    assert "pie" in ChartSelector.CHART_DISTRIBUTION
    assert "waffle" in ChartSelector.CHART_DISTRIBUTION

    assert hasattr(VisualEngine, "render_pie")
    assert hasattr(VisualEngine, "render_waffle")


def test_share_renderers_opt_out_of_the_mobile_entity_cap():
    """A part-of-whole chart must never silently DROP a part.

    _prepare_chart_data caps every renderer at
    MAX_CHART_ENTITIES (4).  For a pie that is not a cosmetic
    trim -- the surviving wedges get rescaled into a whole that
    never existed.  Measured before the fix: a 5-entity share set
    rendered only 4 wedges and the 12% slice vanished.
    """
    import inspect

    for name in ("render_pie", "render_waffle"):

        source = inspect.getsource(
            getattr(VisualEngine, name)
        )

        assert "respect_cap=False" in source, (
            f"{name} must opt out of MAX_CHART_ENTITIES"
        )


def test_pie_needs_share_data_waffle_also_accepts_leader_stories():
    """Part 1 vs Part 2 eligibility windows."""

    # Share-of-total data -> both.
    assert sorted(
        ChartSelector._eligible_share_charts(
            "fastest_growth", share_frame()
        )
    ) == ["pie", "waffle"]

    # Absolute data + leader story -> waffle ONLY (no pie).
    assert sorted(
        ChartSelector._eligible_share_charts(
            "current_leader", absolute_frame()
        )
    ) == ["waffle"]

    assert sorted(
        ChartSelector._eligible_share_charts(
            "leader_challenge", absolute_frame()
        )
    ) == ["waffle"]

    # Absolute data + non-leader story -> neither.
    assert (
        ChartSelector._eligible_share_charts(
            "fastest_growth", absolute_frame()
        )
        == set()
    )


def test_entity_count_window_is_enforced():
    """3-6 entities only."""

    two = pd.DataFrame(
        {2021: [60.0, 40.0]}, index=["A", "B"]
    )
    seven = pd.DataFrame(
        {2021: [14.0] * 7}, index=list("ABCDEFG")
    )

    # Two entities is below the floor even though it sums to 100.
    assert VisualEngine.is_share_of_total(two) is False
    assert (
        ChartSelector._eligible_share_charts(
            "current_leader", two
        )
        == set()
    )

    # Seven is above the ceiling.
    assert VisualEngine.is_share_of_total(seven) is False
    assert (
        ChartSelector._eligible_share_charts(
            "current_leader", seven
        )
        == set()
    )


def test_selector_never_emits_impossible_share_charts():
    """Pie/waffle must NEVER come back for absolute data on a
    story type that does not allow them."""

    random.seed(3)

    for _ in range(400):

        chart = ChartSelector.select_chart(
            "fastest_growth",
            {},
            absolute_frame(),
        )

        assert chart not in ("pie", "waffle"), (
            "selector emitted a part-of-whole chart for an "
            "absolute series"
        )


def test_selector_can_emit_share_charts_when_eligible():
    random.seed(11)

    seen = set()

    for _ in range(2000):
        seen.add(
            ChartSelector.select_chart(
                "fastest_growth",
                {},
                share_frame(),
            )
        )

    assert "pie" in seen, sorted(seen)
    assert "waffle" in seen, sorted(seen)


def test_distribution_stays_inside_the_declared_bands():
    """The weight change must not break the channel's ratios:
    horizontal bars 60-80%, area 10-20%, line 2-8%."""

    from collections import Counter

    random.seed(5)

    for frame in (absolute_frame(), share_frame()):

        counter = Counter()

        for _ in range(3000):
            counter[
                ChartSelector.select_chart(
                    "fastest_growth", {}, frame
                )
            ] += 1

        total = sum(counter.values())

        bars = (
            counter.get("bar_race", 0)
            + counter.get("top5_change", 0)
        ) / total * 100
        area = counter.get("area", 0) / total * 100
        line = counter.get("line", 0) / total * 100

        assert 60 <= bars <= 80, (frame.shape, bars)
        assert 10 <= area <= 20, (frame.shape, area)
        assert 2 <= line <= 8, (frame.shape, line)


# ---------------------------------------------------------
# PART 3 -- background tone
# ---------------------------------------------------------

def _rgb(hex_color):
    value = hex_color.lstrip("#")
    return tuple(
        int(value[i:i + 2], 16)
        for i in (0, 2, 4)
    )


def test_background_is_lifted_and_navy_tinted():
    red, green, blue = _rgb(VisualEngine.BG_COLOR)

    # Navy tint: the blue channel dominates and the spread is
    # wide enough to actually read as colour, not grey.
    assert blue > green > red, (red, green, blue)
    assert blue - red >= 20, "tint is too weak to read as navy"

    # Lifted off pure black (the old #0D1117 was 13/17/23).
    assert (red, green, blue) != (13, 17, 23)
    assert red + green + blue > 13 + 17 + 23, (
        "the new tone is not lifted"
    )

    # Still deep: no channel may climb into "mid grey".
    assert max(red, green, blue) <= 70, (red, green, blue)


def test_background_gradient_top_matches_canvas():
    assert (
        VisualEngine.BG_GRADIENT_TOP
        == VisualEngine.BG_COLOR
    ), "vignette must start exactly on the canvas colour"

    top = _rgb(VisualEngine.BG_GRADIENT_TOP)
    bottom = _rgb(VisualEngine.BG_GRADIENT_BOTTOM)

    assert bottom > top, (
        "gradient must still shift toward the bottom"
    )


def test_text_contrast_survives_the_tone_change():
    def _lum(color):
        channels = []
        for value in _rgb(color):
            ratio = value / 255.0
            channels.append(
                ratio / 12.92
                if ratio <= 0.03928
                else ((ratio + 0.055) / 1.055) ** 2.4
            )
        return (
            0.2126 * channels[0]
            + 0.7152 * channels[1]
            + 0.0722 * channels[2]
        )

    def _contrast(one, two):
        first, second = sorted(
            (_lum(one), _lum(two)), reverse=True
        )
        return (first + 0.05) / (second + 0.05)

    assert _contrast(
        VisualEngine.TEXT_COLOR, VisualEngine.BG_COLOR
    ) >= 12.0

    assert _contrast(
        VisualEngine.SECONDARY_TEXT, VisualEngine.BG_COLOR
    ) >= 4.5


# ---------------------------------------------------------
# PART 4 -- multi-colour per bar
# ---------------------------------------------------------

def test_multi_color_palette_is_distinct_and_valid():
    palette = VisualEngine.MULTI_COLOR_PALETTE

    assert 6 <= len(palette) <= 8, palette
    assert len(set(palette)) == len(palette), (
        "palette colours must be distinct"
    )

    for color in palette:
        red, green, blue = _rgb(color)
        assert (red, green, blue) != (0, 0, 0)
        assert max(red, green, blue) >= 150, (
            f"{color} is too dark to read on the canvas"
        )


def test_multi_color_mode_only_ever_affects_bar_charts():
    original = VisualEngine.MULTI_COLOR_PROBABILITY

    try:

        VisualEngine.MULTI_COLOR_PROBABILITY = 1.0

        assert (
            VisualEngine._select_bar_coloring("bar_race") is True
        )
        assert (
            VisualEngine._select_bar_coloring("top5_change")
            is True
        )

        # Every other chart type must switch the mode OFF, so
        # the flag can never leak into them.
        for chart in (
            "line", "area", "slope", "bubble", "pie", "waffle"
        ):
            assert (
                VisualEngine._select_bar_coloring(chart)
                is False
            ), chart

    finally:
        VisualEngine.MULTI_COLOR_PROBABILITY = original
        VisualEngine._select_bar_coloring("line")


def test_multi_color_mode_off_never_selects_it():
    original = VisualEngine.MULTI_COLOR_PROBABILITY

    try:

        VisualEngine.MULTI_COLOR_PROBABILITY = 0.0

        for _ in range(200):
            assert (
                VisualEngine._select_bar_coloring("bar_race")
                is False
            )

    finally:
        VisualEngine.MULTI_COLOR_PROBABILITY = original
        VisualEngine._select_bar_coloring("line")


def test_multi_color_probability_actually_mixes_both_modes():
    """Both looks must really appear across videos."""

    original = VisualEngine.MULTI_COLOR_PROBABILITY

    try:

        VisualEngine.MULTI_COLOR_PROBABILITY = 0.35

        random.seed(23)

        hits = sum(
            1
            for _ in range(2000)
            if VisualEngine._select_bar_coloring("bar_race")
        )

        share = hits / 2000.0

        assert 0.28 <= share <= 0.42, share

    finally:
        VisualEngine.MULTI_COLOR_PROBABILITY = original
        VisualEngine._select_bar_coloring("line")


def test_each_bar_gets_its_own_colour_in_multi_color_mode():
    saved_palette = VisualEngine._ACTIVE_PALETTE
    saved_mode = VisualEngine._MULTI_COLOR_MODE

    try:

        VisualEngine._ACTIVE_PALETTE = ["#111111", "#222222"]
        VisualEngine._MULTI_COLOR_MODE = True

        colors = [
            VisualEngine._get_bar_color(index)
            for index in range(4)
        ]

        assert colors == VisualEngine.MULTI_COLOR_PALETTE[:4]
        assert len(set(colors)) == 4, (
            "multi-colour mode must not repeat a colour per bar"
        )

    finally:
        VisualEngine._ACTIVE_PALETTE = saved_palette
        VisualEngine._MULTI_COLOR_MODE = saved_mode


def test_emphasis_still_wins_over_multi_color():
    saved_palette = VisualEngine._ACTIVE_PALETTE
    saved_mode = VisualEngine._MULTI_COLOR_MODE

    try:

        VisualEngine._ACTIVE_PALETTE = ["#111111"]
        VisualEngine._MULTI_COLOR_MODE = True

        assert (
            VisualEngine._get_bar_color(
                0, is_current_leader=True
            )
            == VisualEngine.LEADER_COLOR
        )

        assert (
            VisualEngine._get_bar_color(0, is_overtake=True)
            == VisualEngine.OVERTAKE_COLOR
        )

    finally:
        VisualEngine._ACTIVE_PALETTE = saved_palette
        VisualEngine._MULTI_COLOR_MODE = saved_mode


def test_single_gradient_mode_is_unchanged():
    """With the mode off, behaviour must be identical to the
    historical single-ramp palette."""

    saved_palette = VisualEngine._ACTIVE_PALETTE
    saved_mode = VisualEngine._MULTI_COLOR_MODE

    try:

        VisualEngine._MULTI_COLOR_MODE = False
        VisualEngine._ACTIVE_PALETTE = ["#AAAAAA", "#BBBBBB"]

        assert VisualEngine._get_bar_color(0) == "#AAAAAA"
        assert VisualEngine._get_bar_color(1) == "#BBBBBB"
        # Out-of-range ranks clamp to the last ramp colour.
        assert VisualEngine._get_bar_color(9) == "#BBBBBB"

    finally:
        VisualEngine._ACTIVE_PALETTE = saved_palette
        VisualEngine._MULTI_COLOR_MODE = saved_mode


if __name__ == "__main__":
    import sys

    sys.exit(
        pytest.main([__file__, "-v", "-p", "no:randomly"])
    )
