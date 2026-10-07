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
    """Right-anchored country labels, exactly as the renderer makes them."""
    return [
        ax.text(
            -max_val * 0.055,
            index,
            country,
            va="center",
            ha="right",
            color=VisualEngine.TEXT_COLOR,
            fontsize=VisualEngine.COUNTRY_FONT_SIZE,
            fontweight="bold",
            clip_on=False,
        )
        for index, country in enumerate(countries)
    ]


def _flag_reserve_px():
    return (
        float(VisualEngine._FLAG_SIZE[0])
        * VisualEngine.FLAG_ZOOM
        + 48.0
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

        # A label that needs shrinking must actually shrink:
        # this is the size the renderer must reuse each frame.
        long_index = REVERSAL_COUNTRIES.index(LONG_LABEL)
        base_font = float(VisualEngine.COUNTRY_FONT_SIZE)
        assert bases[long_index] < base_font, (
            f"DEFECT B: {LONG_LABEL!r} was not shrunk "
            f"({bases[long_index]}pt == {base_font}pt); the guard "
            f"cannot be doing anything"
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
            # A right-anchored label grows LEFTWARDS as the
            # font grows, so the anchor must strictly decrease.
            for step in range(1, len(row)):
                assert row[step] < row[step - 1], (
                    f"DEFECT B: anchor for {name!r} did not move "
                    f"left at bump +{step}: {row}"
                )

        # No flag -> None, and the render loop must cope.
        none_anchors = VisualEngine._flag_anchor_data_x(
            ax, fig, texts, [None] * len(texts), bases
        )
        assert all(a is None for a in none_anchors)
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

            # Country labels are the artists whose text is an
            # entity name; value texts are the formatted numbers.
            names = [t.get_text() for t in ax.texts]
            label_idx = [
                i for i, text in enumerate(names)
                if text in countries
            ]
            assert len(label_idx) == n, (
                f"expected {n} country labels, found {len(label_idx)} "
                f"in {names}"
            )

            labels = [ax.texts[i] for i in label_idx]
            value_texts = [
                t for t in ax.texts
                if t.get_text() not in countries
            ]

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
        assert sorted(frame["label_names"]) == sorted(countries), (
            f"frame {number}: retained entities changed -- "
            f"{frame['label_names']}"
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

        # The long label is never restored to the unfitted size:
        # that per-frame reset is what pushed it (and its flag)
        # off the left edge for the whole video.
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

