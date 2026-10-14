#!/usr/bin/env python3
"""Regression tests for the bar-race transition/label defects.

DEFECT A -- "two countries, one name" (label row collision).
  _solve_label_positions walked down the label stack enforcing
  MIN_LABEL_GAP and then clamped every label with min(y, max_y).
  That clamp silently discarded the gap the loop had just
  enforced, so any transition compressing the stack past the
  bottom of the axis parked two or more labels on the IDENTICAL
  row.  Measured on a 4-bar full reversal: gaps of
  [0.72, 0.72, 0.06] against a required 0.72.  The "bottom
  correction" that followed was dead code -- the clamp made its
  guard condition unreachable.

DEFECT B -- long label + its flag pushed off the left edge.
  _fit_labels_in_frame correctly measured an over-long label and
  shrank it to fit, but returned only a bool.  render_bar_race's
  update() then re-applied set_fontsize(COUNTRY_FONT_SIZE)
  UNCONDITIONALLY on every frame, restoring the unfitted 34pt on
  frame 1 and holding the label off-screen for the whole video.
  Measured for "Turks and Caicos Islands": x0 = -145px at base,
  -191px with the overtake emphasis bump, which places the flag
  icon 264px outside the left canvas edge.

All tests are offline and deterministic: no network (flag
fetching is stubbed), no ffmpeg, no video writing.
"""
import contextlib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import os
import pandas as pd
import pytest

from app.visuals import design_system
from app.visuals.scene_engine import VisualEngine

# The exact label that overflowed in the published-style render.
LONG_LABEL = "Turks and Caicos Islands"

# A 4-entity chart ending in a FULL REVERSAL: the worst case for
# the row solver, because every bar passes through the same y.
REVERSAL_COUNTRIES = [
    "Ireland",
    LONG_LABEL,
    "Georgia",
    "Guyana",
]

REVERSAL_RANKS = {
    # year -> 1-based rank per country
    2018: {"Ireland": 1, LONG_LABEL: 2, "Georgia": 3, "Guyana": 4},
    2019: {"Ireland": 1, LONG_LABEL: 2, "Georgia": 4, "Guyana": 3},
    2020: {"Ireland": 1, LONG_LABEL: 2, "Georgia": 3, "Guyana": 4},
    2021: {"Ireland": 1, LONG_LABEL: 2, "Georgia": 4, "Guyana": 3},
    2022: {"Ireland": 1, LONG_LABEL: 3, "Georgia": 4, "Guyana": 2},
}


# =================================================================
# DEFECT A -- label row collision
# =================================================================


def _interpolated_rows(ranks_by_year, year_a, year_b, t):
    """Row position (0-based) of every country mid-transition."""
    rows = []
    for country in REVERSAL_COUNTRIES:
        start = ranks_by_year[year_a][country] - 1
        end = ranks_by_year[year_b][country] - 1
        rows.append(start + (end - start) * t)
    return rows


def test_defect_a_labels_never_share_a_row():
    """Every label keeps its own row across a full reversal."""
    n = len(REVERSAL_COUNTRIES)

    # The degenerate case that exposed the defect: at the
    # midpoint of a full reversal ALL bars sit on one row.
    raw = [r + ((n - 1 - r) - r) * 0.5 for r in range(n)]
    assert max(raw) - min(raw) == 0.0, (
        "fixture must be a total overlap at t=0.5"
    )

    solved = VisualEngine._solve_label_positions(
        raw, VisualEngine.MIN_LABEL_GAP, 0, n - 1
    )

    assert len(solved) == n, "one position per label"

    for value in solved:
        assert -1e-9 <= value <= n - 1 + 1e-9, (
            f"label row {value} escaped the axis window [0, {n - 1}]"
        )

    ordered = sorted(solved)
    gaps = [
        round(ordered[i + 1] - ordered[i], 6)
        for i in range(n - 1)
    ]
    for gap in gaps:
        assert gap >= VisualEngine.MIN_ROW_SEPARATION, (
            f"DEFECT A: labels share a row -- gap {gap} < "
            f"MIN_ROW_SEPARATION {VisualEngine.MIN_ROW_SEPARATION}; "
            f"rows={ordered}"
        )

    # A degenerate stack must still be spread, not collapsed.
    # A degenerate stack must still be spread, not collapsed.
    assert len(set(ordered)) == n, (
        f"DEFECT A: {n} labels resolved to {len(set(ordered))} "
        f"distinct rows: {ordered}"
    )





def test_defect_a_gap_held_across_every_transition_step():
    """The gap holds at every step of every real transition."""
    n = len(REVERSAL_COUNTRIES)
    years = sorted(REVERSAL_RANKS)

    for year_a, year_b in zip(years, years[1:]):
        for step in range(0, 51):
            t = step / 50.0
            raw = _interpolated_rows(
                REVERSAL_RANKS, year_a, year_b, t
            )
            solved = VisualEngine._solve_label_positions(
                raw, VisualEngine.MIN_LABEL_GAP, 0, n - 1
            )

            ordered = sorted(solved)
            gaps = [
                ordered[i + 1] - ordered[i]
                for i in range(n - 1)
            ]
            worst = min(gaps)
            assert worst > 0.0, (
                f"DEFECT A: two labels on the same row during "
                f"{year_a}->{year_b} at t={t:.2f}: {ordered}"
            )
            assert worst >= VisualEngine.MIN_LABEL_GAP - 1e-6, (
                f"DEFECT A: gap {worst:.4f} < required "
                f"{VisualEngine.MIN_LABEL_GAP} during "
                f"{year_a}->{year_b} at t={t:.2f}: {ordered}"
            )

            for value in solved:
                assert -1e-6 <= value <= n - 1 + 1e-6, (
                    f"label row {value} outside [0, {n - 1}] "
                    f"during {year_a}->{year_b} t={t:.2f}"
                )


def test_defect_a_ordering_and_endpoints_preserved():
    """The solver never reorders labels or moves them at rest."""
    n = len(REVERSAL_COUNTRIES)

    # At rest the raw positions ARE the rows: nothing should move.
    at_rest = [float(r) for r in range(n)]
    solved = VisualEngine._solve_label_positions(
        at_rest, VisualEngine.MIN_LABEL_GAP, 0, n - 1
    )
    assert solved == at_rest, (
        f"a settled chart must not shift: {solved} != {at_rest}"
    )

    # Order is preserved when rows are genuinely shuffled: the
    # entity at raw row 3.0 must still be the lowest label, etc.
    # The result is returned in the ORIGINAL entity order, so
    # check the permutation, not the raw list.
    raw = [3.0, 0.0, 2.0, 1.0]
    solved = VisualEngine._solve_label_positions(
        raw, VisualEngine.MIN_LABEL_GAP, 0, 3
    )
    by_position = sorted(
        range(len(raw)), key=lambda i: raw[i]
    )
    assert [solved[i] for i in by_position] == [0.0, 1.0, 2.0, 3.0], (
        f"relative order changed: raw={raw} solved={solved}"
    )
    assert len(set(solved)) == 4, (
        f"labels collapsed onto shared rows: {solved}"
    )



# =================================================================
# DEFECT B -- long label / flag pushed off the left edge
# =================================================================


def _build_figure(countries, max_val):
    """Reproduce render_bar_race()'s figure exactly."""
    plt.rcParams["figure.facecolor"] = VisualEngine.BG_COLOR
    plt.rcParams["axes.facecolor"] = VisualEngine.BG_COLOR
    plt.rcParams["text.color"] = VisualEngine.TEXT_COLOR
    plt.rcParams["font.family"] = "DejaVu Sans"

    fig = plt.figure(figsize=(10.8, 19.2), dpi=100)
    ax = fig.add_axes(
        [
            VisualEngine.CHART_LEFT,
            VisualEngine.CHART_BOTTOM,
            VisualEngine.CHART_WIDTH,
            VisualEngine.CHART_HEIGHT,
        ]
    )

    n = len(countries)
    ax.set_xlim(0, max_val)
    reference_span = 4 if n >= 3 else 3
    extra_span = max(0.0, reference_span - n)
    ax.set_ylim(
        -0.5 - extra_span / 2.0,
        n - 0.5 + extra_span / 2.0,
    )
    ax.invert_yaxis()

    return fig, ax


def _make_labels(ax, countries, max_val):
    """Above-bar, LEFT-anchored country labels, exactly as the
    PREMIUM UI v2 renderer makes them.

    Phase 1 replaced the old narrow-column layout (labels right-
    anchored in the dead left margin at -max_val * 0.055) with a
    full-width chart whose entity names sit ABOVE their bars,
    left-aligned just inside the chart, with the rank badge and
    flag icon in the left inset.  The fixture has to reproduce the
    NEW geometry or it measures a layout that no longer ships.
    """
    # Same reservation the renderer uses: the flag icon's width,
    # its 6pt offset, plus breathing room, all measured from the
    # axes' left edge in pixels.
    flag_gap_px = 8.3          # 6pt at dpi=100
    axes_left_px = VisualEngine.CHART_LEFT * 1080.0
    axes_w_px = VisualEngine.CHART_WIDTH * 1080.0

    name_x0_px = (
        axes_left_px
        + float(VisualEngine._FLAG_SIZE[0]) * VisualEngine.FLAG_ZOOM
        + flag_gap_px
        + 6.0
    )
    name_x_data = max_val * (
        (name_x0_px - axes_left_px) / axes_w_px
    )

    texts = []
    for index, country in enumerate(countries):
        # Configured short names are applied before measuring, so
        # a curated abbreviation is used instead of shrinking a
        # known-long name (UI_SHORT_NAME_MAP).
        label = design_system.short_name(country)
        texts.append(
            ax.text(
                name_x_data,
                index,
                label,
                va="bottom",
                ha="left",
                color=VisualEngine.TEXT_COLOR,
                fontsize=VisualEngine.COUNTRY_FONT_SIZE,
                fontweight="bold",
                clip_on=False,
            )
        )
    return texts


def _flag_reserve_px():
    """Left-edge x the renderer reserves for the flag icon.

    The flag hangs left of the label inside the left inset, so a
    label's own left edge must never come left of this.
    """
    return (
        VisualEngine.CHART_LEFT * 1080.0
        + float(VisualEngine._FLAG_SIZE[0])
        * VisualEngine.FLAG_ZOOM
        + 8.3
        + 6.0
    )


    # Degenerate input must not raise or truncate.
    assert VisualEngine._solve_label_positions([], 0.72, 0, 3) == []
    single = VisualEngine._solve_label_positions([1.4], 0.72, 0, 3)
    assert len(single) == 1 and 0.0 <= single[0] <= 3.0


def test_defect_b_long_label_stays_on_canvas_after_fitting():
    """The fitted size keeps the label AND its flag on-canvas --
    including under the per-frame leader/overtake emphasis bump."""
    max_val = 131338 * 1.18
    fig, ax = _build_figure(REVERSAL_COUNTRIES, max_val)
    try:
        texts = _make_labels(ax, REVERSAL_COUNTRIES, max_val)

        bases = VisualEngine._fit_labels_in_frame(
            fig,
            ax,
            texts,
            font_bump=VisualEngine.LABEL_FONT_BUMP,
        )

        assert len(bases) == len(texts), (
            "guard must return one fitted size per label"
        )
        assert all(isinstance(b, float) for b in bases), (
            f"fitted sizes must be floats: {bases}"
        )

        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        reserve = _flag_reserve_px()

        # The animation applies base, base+1 and base+2 on
        # different frames; every one must stay on-canvas.
        for bump in range(VisualEngine.LABEL_FONT_BUMP + 1):
            for text, base in zip(texts, bases):
                text.set_fontsize(base + bump)
            fig.canvas.draw()

            for text in texts:
                x0 = float(
                    text.get_window_extent(
                        renderer=renderer
                    ).x0
                )
                assert x0 >= reserve, (
                    f"DEFECT B: {text.get_text()!r} at bump +{bump} "
                    f"has left edge x0={x0:.1f}px, inside the "
                    f"{reserve:.1f}px flag reserve"
                )

        # The full-width PREMIUM UI v2 layout gives a long label
        # enough room that the LEFT-edge guard no longer has to
        # shrink it: it keeps the intended 34pt mobile-legibility
        # size.  Under the old narrow-column layout this label was
        # pushed off the left edge and had to shrink, so the old
        # "must shrink" assertion is exactly what the redesign
        # replaced -- the meaningful contract now is that the
        # label is on-canvas AND at full size.
        long_index = REVERSAL_COUNTRIES.index(LONG_LABEL)
        base_font = float(VisualEngine.COUNTRY_FONT_SIZE)
        assert bases[long_index] == base_font, (
            f"DEFECT B: {LONG_LABEL!r} was shrunk to "
            f"{bases[long_index]}pt on the full-width layout -- "
            f"there is room for the intended {base_font}pt"
        )

        # Short labels keep full-size mobile legibility.
        for index, country in enumerate(REVERSAL_COUNTRIES):
            if country == LONG_LABEL:
                continue
            assert bases[index] == base_font, (
                f"DEFECT B: short label {country!r} was shrunk to "
                f"{bases[index]}pt -- only the overflowing label "
                f"should be touched"
            )
    finally:
        plt.close(fig)


def test_defect_b_fitted_size_is_floor_bounded_and_empty_safe():
    """The returned sizes are usable, and the guard is total."""
    max_val = 131338 * 1.18
    pathological = [
        "International Investment Bank of Testland"
    ]

    fig, ax = _build_figure(pathological, max_val)
    try:
        text = _make_labels(ax, pathological, max_val)[0]
        bases = VisualEngine._fit_labels_in_frame(
            fig, ax, [text],
            font_bump=VisualEngine.LABEL_FONT_BUMP,
        )
        assert len(bases) == 1
        assert bases[0] >= 12.0, (
            f"fitted size {bases[0]} fell below the 12pt floor"
        )
    finally:
        plt.close(fig)

    # No labels -> no work, no crash.
    fig = plt.figure()
    try:
        assert VisualEngine._fit_labels_in_frame(
            fig, fig.add_axes([0, 0, 1, 1]), []
        ) == []
    finally:
        plt.close(fig)


def test_defect_b_flag_anchors_track_the_label_font():
    """The flag icon must follow its label when the font grows."""
    max_val = 131338 * 1.18
    fig, ax = _build_figure(REVERSAL_COUNTRIES, max_val)
    try:
        texts = _make_labels(ax, REVERSAL_COUNTRIES, max_val)
        bases = VisualEngine._fit_labels_in_frame(
            fig, ax, texts,
            font_bump=VisualEngine.LABEL_FONT_BUMP,
        )

        # Stand in for a real AnnotationBbox: the render loop
        # only ever touches `.xy`, and its per-country
        # try/except means a missing flag is simply None.
        flag_boxes = [
            type("Box", (), {"xy": (0.0, 0.0)})()
            for _ in texts
        ]

        anchors = VisualEngine._flag_anchor_data_x(
            ax, fig, texts, flag_boxes, bases
        )

        assert len(anchors) == len(texts)
        for index, row in enumerate(anchors):
            name = texts[index].get_text()
            assert row is not None, f"no anchors for {name!r}"
            assert len(row) == VisualEngine.LABEL_FONT_BUMP + 1, (
                f"expected {VisualEngine.LABEL_FONT_BUMP + 1} "
                f"anchors for {name!r}, got {len(row)}"
            )
            assert all(a is not None for a in row), (
                f"anchor measurement failed for {name!r}: {row}"
            )
            # PREMIUM UI v2 labels are LEFT-anchored, so a bigger
            # font grows the text RIGHTWARDS and its left edge --
            # the flag's anchor -- stays put.  Under the old
            # right-anchored layout the label grew leftwards and
            # the anchor had to strictly decrease to keep the icon
            # from being covered.  The meaningful contract now is
            # that the anchor never moves RIGHT into the label, so
            # the flag can never end up underneath its own name.
            for step in range(1, len(row)):
                assert row[step] <= row[step - 1] + 1e-9, (
                    f"DEFECT B: anchor for {name!r} moved right at "
                    f"bump +{step}: {row} -- the flag would slide "
                    f"under its own label"
                )

        # No flag -> None, and the render loop must cope.
        none_anchors = VisualEngine._flag_anchor_data_x(
            ax, fig, texts, [None] * len(texts), bases
        )
        assert all(a is None for a in none_anchors)
    finally:
        plt.close(fig)


def test_flag_vertical_offsets_land_on_the_label_centre():
    """The flag icon must sit on its label's vertical CENTRE.

    Above-bar labels are va="bottom", so a row's y is the label's
    BOTTOM edge.  Anchoring the icon on the row y parked every flag
    half a label-height too low -- measured 29px on a 34pt label,
    which is why the icons visibly hung under their names.  The
    offsets must be negative (towards the label's centre, on the
    inverted y-axis) and grow as the emphasis bump enlarges the
    text.
    """
    max_val = 131338 * 1.18
    fig, ax = _build_figure(REVERSAL_COUNTRIES, max_val)
    try:
        texts = _make_labels(ax, REVERSAL_COUNTRIES, max_val)
        bases = VisualEngine._fit_labels_in_frame(
            fig, ax, texts,
            font_bump=VisualEngine.LABEL_FONT_BUMP,
        )

        offsets = VisualEngine._flag_vertical_offsets(
            ax, fig, texts, bases
        )

        assert len(offsets) == len(texts)
        for index, row in enumerate(offsets):
            name = texts[index].get_text()
            assert row is not None, f"no offsets for {name!r}"
            assert len(row) == VisualEngine.LABEL_FONT_BUMP + 1, (
                f"expected {VisualEngine.LABEL_FONT_BUMP + 1} "
                f"offsets for {name!r}, got {len(row)}"
            )
            assert all(o is not None for o in row), (
                f"offset measurement failed for {name!r}: {row}"
            )

            # Negative on the inverted axis == UP the screen, i.e.
            # from the label's bottom edge towards its centre.
            assert row[0] < 0.0, (
                f"DEFECT: offset for {name!r} is {row[0]}, which "
                f"would move the flag DOWN, not up to the centre"
            )

            # A larger font is a taller label, so the walk from
            # the bottom edge to the centre gets longer.
            for step in range(1, len(row)):
                assert row[step] <= row[step - 1], (
                    f"DEFECT: offset for {name!r} shrank at bump "
                    f"+{step}: {row}"
                )

        # End-to-end check on real pixels: applying the offset puts
        # the flag exactly on the label's centre.  The offset is in
        # DATA units (that is what .xy uses), so it must be added
        # in data space and THEN transformed -- adding it to a
        # display-pixel value would mix the two spaces.
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        for index, text in enumerate(texts):
            box = text.get_window_extent(renderer=renderer)
            label_center = (box.y0 + box.y1) / 2.0

            flag_data_y = float(index) + offsets[index][0]
            flag_y = ax.transData.transform(
                (0.0, flag_data_y)
            )[1]

            assert abs(flag_y - label_center) <= 1.5, (
                f"DEFECT: flag for {text.get_text()!r} sits at "
                f"y={flag_y:.1f}px, its label's centre is "
                f"{label_center:.1f}px"
            )
    finally:
        plt.close(fig)


def test_short_name_map_is_applied_before_measuring():
    """Configured short names must be USED, not re-derived.

    A known-long name with a curated abbreviation must render that
    abbreviation -- that is the whole point of UI_SHORT_NAME_MAP,
    because it keeps the label at the intended 34pt instead of
    shrinking a name that already has a good short form.  A country
    with no configured entry must keep its full text.
    """
    mapped = "Democratic Republic of the Congo"
    unmapped = LONG_LABEL

    expected = design_system.short_name(mapped)

    assert expected != mapped, (
        "fixture broken: this name has no configured short form, so "
        "the test cannot prove the map is wired in"
    )
    assert design_system.short_name(unmapped) == unmapped, (
        "fixture broken: the 'unmapped' name unexpectedly has a "
        "configured short form"
    )

    max_val = 131338 * 1.18
    countries = [mapped, unmapped]
    fig, ax = _build_figure(countries, max_val)
    try:
        texts = _make_labels(ax, countries, max_val)

        drawn = [t.get_text() for t in texts]
        assert drawn[0] == expected, (
            f"DEFECT: {mapped!r} rendered as {drawn[0]!r} -- the "
            f"configured short name {expected!r} was not applied, "
            f"so the label must shrink instead of abbreviating"
        )
        assert drawn[1] == unmapped, (
            f"DEFECT: {unmapped!r} has no configured short name and "
            f"must keep its full text, got {drawn[1]!r}"
        )
    finally:
        plt.close(fig)


def test_name_never_overlaps_its_own_value():
    """A label must stop short of the number that belongs to it.

    A name is left-anchored at a fixed x while its value rides the
    bar tip, so a long name printed straight through its own
    number.  Measured on the published-style frame: "Turks and
    Caicos Islands" ended at x=672px while its "$7" began at
    x=524px -- 148px of overlap, the value sitting on the text.

    The guard is fitted against each row's SMALLEST value (the
    leftmost its number ever reaches), so the clearance holds on
    every frame of the animation, not just the last one.
    """
    countries = list(REVERSAL_COUNTRIES)
    years = sorted(REVERSAL_RANKS)

    data = pd.DataFrame(
        {
            year: [
                float(10 - REVERSAL_RANKS[year][c])
                for c in countries
            ]
            for year in years
        },
        index=countries,
    )

    # Same headroom the renderer applies, so the fixture measures
    # the axis limit the real chart actually uses.
    max_val = float(data.max().max()) * 1.18

    indicator = "GDP per capita (current US$)"

    def _place_values():
        out = []
        for index, country in enumerate(countries):
            value = float(data.loc[country, years[-1]])
            text = ax.text(
                0, index, "",
                va="center", ha="left",
                fontsize=VisualEngine.VALUE_FONT_SIZE,
                fontweight="bold", clip_on=False,
            )
            text.set_text(
                VisualEngine._format_value(value, indicator)
            )
            text.set_x(
                VisualEngine._bar_width(value, max_val)
                + max_val * 0.012
            )
            out.append(text)
        return out

    fig, ax = _build_figure(countries, max_val)
    try:
        texts = _make_labels(ax, countries, max_val)
        values = _place_values()

        # Sanity: without the guard the long label really does
        # collide with its own value, so this test has teeth.
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        collided = []
        for index, text in enumerate(texts):
            box = text.get_window_extent(renderer=renderer)
            vbox = values[index].get_window_extent(renderer=renderer)
            if vbox.x0 < box.x1:
                collided.append(text.get_text())
        assert collided, (
            "fixture broken: nothing collided before the guard, so "
            "this test cannot prove the guard does anything"
        )

        bases = VisualEngine._fit_labels_in_frame(
            fig, ax, texts,
            font_bump=VisualEngine.LABEL_FONT_BUMP,
        )
        bases, caps = VisualEngine._fit_labels_clear_of_values(
            fig, ax, texts, countries, data, years, max_val,
            pad_px=design_system.VALUE_SAFE_MARGIN_PX,
            base_fonts=bases,
            font_bump=VisualEngine.LABEL_FONT_BUMP,
        )

        assert len(caps) == len(bases)
        for base, cap in zip(bases, caps):
            assert cap >= base, (
                f"ceiling {cap}pt is below the base {base}pt"
            )

        # Every emphasis size the animation can apply must clear.
        # The renderer clamps the bump to the label's own ceiling,
        # so that is what is measured here.
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        for index, text in enumerate(texts):
            for bump in range(VisualEngine.LABEL_FONT_BUMP + 1):
                text.set_fontsize(min(bases[index] + bump, caps[index]))
                fig.canvas.draw()

                box = text.get_window_extent(renderer=renderer)
                vbox = values[index].get_window_extent(
                    renderer=renderer
                )
                assert vbox.x0 >= box.x1, (
                    f"DEFECT: {text.get_text()!r} at bump +{bump} "
                    f"ends at x={box.x1:.1f}px but its own value "
                    f"{values[index].get_text()!r} starts at "
                    f"x={vbox.x0:.1f}px -- "
                    f"{box.x1 - vbox.x0:.1f}px of overlap"
                )

            text.set_fontsize(bases[index])
    finally:
        plt.close(fig)


def test_header_year_and_source_do_not_collide():
    """The big year counter and the credit line need real air.

    Measured on the published-style frame: "2022" spanned
    y=1460..1581 while "Source: World Bank" spanned y=1541..1578 --
    40px of overlap, the credit printed inside the year's digits.
    The race header must keep both inside the frame-safe band with
    genuine clearance between them.
    """
    # The credit must sit BELOW the year (smaller fig-y), because
    # the year is the visual anchor of the composition.
    assert VisualEngine.RACE_SOURCE_Y < VisualEngine.YEAR_Y, (
        f"DEFECT: race source y={VisualEngine.RACE_SOURCE_Y} is not "
        f"below the year y={VisualEngine.YEAR_Y}"
    )

    fig = plt.figure(figsize=(10.8, 19.2), dpi=100)
    try:
        height = float(fig.get_figheight()) * float(fig.dpi)

        year = fig.text(
            VisualEngine.YEAR_X, VisualEngine.YEAR_Y, "2022",
            ha="center", va="center",
            fontsize=VisualEngine.YEAR_SIZE, fontweight="bold",
        )
        source = fig.text(
            0.5, VisualEngine.RACE_SOURCE_Y,
            "Source: World Bank",
            ha="center", va="center",
            fontsize=VisualEngine.SOURCE_SIZE, style="italic",
        )

        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()

        ybox = year.get_window_extent(renderer=renderer)
        sbox = source.get_window_extent(renderer=renderer)

        gap = float(ybox.y0) - float(sbox.y1)
        assert gap >= 8.0, (
            f"DEFECT: only {gap:.1f}px between the year's bottom "
            f"(y={ybox.y0:.1f}) and the source's top "
            f"(y={sbox.y1:.1f})"
        )

        # Both stay inside the frame.
        assert float(ybox.y1) <= height, "year runs off the top"
        assert float(sbox.y0) >= 0.0, "source runs off the bottom"
    finally:
        plt.close(fig)


# =================================================================
# END TO END -- a real render_bar_race() run on the defect
# =================================================================


class _Script:
    title = "GDP per capita"
    source_name = "World Bank"
    indicator_name = "GDP per capita (current US$)"
    total_duration = 6.0


def _render_with_capture(tmp_path, countries, years):
    """Run the real render_bar_race(), capturing every frame.

    ffmpeg and flag fetching are stubbed; the real update()
    closure is what actually runs, once per frame.
    """
    import app.visuals.scene_engine as se

    # Values ordered so the ranks match REVERSAL_RANKS exactly.
    data = pd.DataFrame(
        {
            year: [
                float(10 - REVERSAL_RANKS[year][c])
                for c in countries
            ]
            for year in years
        },
        index=countries,
    )

    frames = []

    real_animation = se.animation.FuncAnimation
    real_writer = se.animation.FFMpegWriter

    class _FakeWriter:
        """Records the real per-frame artist state.

        Matplotlib's FuncAnimation.save() calls _draw_next_frame()
        -- which runs the renderer's real update() -- and then
        grab_frame().  Capturing in grab_frame() therefore records
        exactly the state each rendered frame would have shown,
        without re-implementing any animation machinery.

        Bars and the two text columns are created in a fixed
        order, so the country labels are exactly the artists
        whose text is one of the entity names.
        """

        def __init__(self, *a, **k):
            self.fig = None

        @contextlib.contextmanager
        def saving(self, fig, outfile, dpi=None):
            self.fig = fig
            # The real encoder writes a file here.
            with open(outfile, "wb") as handle:
                handle.write(b"\x00")
            yield

        def grab_frame(self, **kwargs):
            ax = self.fig.axes[0]
            n = len(countries)

            # The renderer creates, per entity, one value text and
            # one name text in a fixed order, so the texts arrive as
            # alternating [value, name] pairs.  Identifying a label
            # by matching its TEXT against the entity names used to
            # work, but the full-width layout now draws the
            # CONFIGURED SHORT NAME (and may ellipsise a label that
            # still cannot clear its own value), so the drawn string
            # is no longer the raw entity name.  Position is the
            # stable identity; every second artist is a name.
            texts = list(ax.texts)
            assert len(texts) == 2 * n, (
                f"expected {2 * n} texts (one value + one name per "
                f"entity), found {len(texts)}: "
                f"{[t.get_text() for t in texts]}"
            )

            value_texts = texts[0::2]
            labels = texts[1::2]

            frames.append(
                {
                    "n": n,
                    "bars": [
                        img for img in ax.images if img.get_zorder() != 0
                    ],
                    "value_texts": value_texts,
                    "label_y": [
                        float(t.get_position()[1])
                        for t in labels
                    ],
                    "label_fonts": [
                        float(t.get_fontsize())
                        for t in labels
                    ],
                    "label_names": [t.get_text() for t in labels],
                    # The entity each label belongs to, in row order.
                    "label_entities": list(countries),
                }
            )

        def _supports_transparency(self):
            return False

        def finish(self):
            pass

    real_prefetch = se.VisualEngine.prefetch_flags
    real_flag_image = se.VisualEngine._get_flag_image
    se.animation.FFMpegWriter = _FakeWriter
    se.VisualEngine.prefetch_flags = classmethod(
        lambda cls, items: None
    )
    se.VisualEngine._get_flag_image = staticmethod(
        lambda name: None
    )

    try:
        se.VisualEngine._duration_override = 0.0
        scenes = se.VisualEngine.render_bar_race(
            _Script(), data, str(tmp_path)
        )
    finally:
        se.animation.FFMpegWriter = real_writer
        se.animation.FuncAnimation = real_animation
        se.VisualEngine.prefetch_flags = real_prefetch
        se.VisualEngine._get_flag_image = real_flag_image

    return scenes, frames


def test_defect_a_and_b_render_bar_race_holds_every_frame(tmp_path):
    """A real render_bar_race() run on a reversal containing a
    long label: every frame keeps all retained entities present,
    on distinct rows, at a font the fit guard signed off."""
    countries = list(REVERSAL_COUNTRIES)
    years = sorted(REVERSAL_RANKS)

    scenes, frames = _render_with_capture(
        tmp_path, countries, years
    )

    assert len(scenes) == 1, "one scene expected"
    assert os.path.exists(scenes[0]["image_path"])

    expected = 180  # 6.0s * 30fps
    assert len(frames) == expected, (
        f"expected {expected} frames, got {len(frames)}"
    )

    n = len(countries)
    base_font = float(VisualEngine.COUNTRY_FONT_SIZE)
    long_index = countries.index(LONG_LABEL)
    budget = base_font + VisualEngine.LABEL_FONT_BUMP

    for number, frame in enumerate(frames):
        # Every retained entity keeps all three of its artists.
        assert len(frame["bars"]) == n, (
            f"frame {number}: {len(frame['bars'])} bars, expected {n}"
        )
        assert len(frame["value_texts"]) == n, (
            f"frame {number}: {len(frame['value_texts'])} value "
            f"texts, expected {n}"
        )
        assert len(frame["label_names"]) == n, (
            f"frame {number}: {len(frame['label_names'])} country "
            f"labels, expected {n}"
        )
        # The DRAWN label is not always the raw entity name: the
        # configured short name is substituted where one exists, and
        # a label that still cannot clear its own value is
        # ellipsised.  Both are intentional, so identity is checked
        # on row order (stable) and each drawn label must still be
        # recognisably its own entity -- either the full name, its
        # configured short form, or a truncation of one of those.
        assert len(frame["label_names"]) == n
        expected_drawn = [
            design_system.short_name(c) for c in countries
        ]
        for entity, drawn, full in zip(
            frame["label_entities"],
            frame["label_names"],
            expected_drawn,
        ):
            assert drawn == full or full.startswith(
                drawn.rstrip(".")
            ) or drawn.rstrip(".").startswith(
                entity[: max(4, len(drawn.rstrip('.')))]
            ), (
                f"frame {number}: label {drawn!r} does not belong "
                f"to {entity!r} (expected {full!r})"
            )
        # Every retained label keeps its own row, every frame.
        rows = sorted(frame["label_y"])
        gaps = [
            rows[i + 1] - rows[i]
            for i in range(n - 1)
        ]
        worst = min(gaps)
        assert worst >= VisualEngine.MIN_ROW_SEPARATION, (
            f"DEFECT A: frame {number} has labels on the same row "
            f"(gap {worst:.4f}); rows={frame['label_y']}"
        )

        # The long label is never restored to the unfitted size.
        # That per-frame reset is what pushed it (and its flag)
        # off the left edge for the whole video; on the full-width
        # layout the same reset would print it straight through
        # its own value, so the fitted size must hold every frame.
        assert frame["label_fonts"][long_index] < base_font, (
            f"DEFECT B: frame {number} restored {LONG_LABEL!r} to "
            f"{frame['label_fonts'][long_index]}pt (unfitted "
            f"{base_font}pt) -- the per-frame reset is back"
        )

        # No label may exceed the budget the guard reserved.
        for name, size in zip(
            frame["label_names"], frame["label_fonts"]
        ):
            assert size <= budget + 1e-6, (
                f"DEFECT B: frame {number} label {name!r} at "
                f"{size}pt exceeds the {budget}pt budget"
            )


if __name__ == "__main__":
    raise SystemExit(
        pytest.main([__file__, "-v", "--no-header", "-x"])
    )

