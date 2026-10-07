"""Focused regression tests for two targeted visual fixes.

1) TOP5 FINAL-VALUE PROGRESS (render_top5_change)

   The payoff replay used ``total_frames - payoff_frames`` as the
   progress denominator, so the FINAL frame landed at
   smoothstep((T - 1 - P) / (T - P)) < 1.0 and the last displayed
   value fell short of the dataset's final value.  The fix divides
   by ``total_frames - 1 - payoff_frames`` so the final frame is
   exactly progress 1.0.

2) LINE END-LABEL BOTTOM CLAMP (render_line)

   ``bottom_room`` subtracted half the name height where it must
   add it (the name is ``va="center"`` on its anchor), so a label
   stack pushed against the chart floor could leave the name label
   BELOW the axes.  The fix restores the correct geometry.

Both tests drive the REAL renderers through the capture helper
reused from ``test_long_label_frame_safety`` (no new framework),
and BOTH MUST FAIL against the pre-fix formulas.
"""
import matplotlib

matplotlib.use("Agg")

import matplotlib.text as mtext

import pandas as pd
import pytest

from app.config import settings
from app.visuals.scene_engine import VisualEngine

from test_long_label_frame_safety import _capture


# ---------------------------------------------------------------
# Network isolation (flags are irrelevant to these fixes; keep the
# tests hermetic the same way test_long_label_frame_safety does).
# ---------------------------------------------------------------
@pytest.fixture(autouse=True)
def _no_network_flags(monkeypatch):
    import app.visuals.scene_engine as se

    monkeypatch.setattr(
        se.VisualEngine,
        "prefetch_flags",
        classmethod(lambda cls, items: None),
    )
    monkeypatch.setattr(
        se.VisualEngine,
        "_get_flag_image",
        staticmethod(lambda name: None),
    )


# ===============================================================
# A) TOP5 FINAL-VALUE TEST
# ===============================================================

# Small known dataset.  The top5_change renderer animates the
# CHANGE (final year minus first year); the known finals are:
#   Alpha 50 - 10 = 40,  Bravo 65 - 15 = 50,
#   Cedar 42 - 12 = 30,  Delta 34 -  8 = 26
TOP5_DATA = pd.DataFrame(
    {
        2019: [10.0, 15.0, 12.0, 8.0],
        2020: [20.0, 25.0, 18.0, 14.0],
        2021: [35.0, 40.0, 30.0, 22.0],
        2022: [50.0, 65.0, 42.0, 34.0],
    },
    index=["Alpha", "Bravo", "Cedar", "Delta"],
)

TOP5_FINAL_CHANGES = [26.0, 30.0, 40.0, 50.0]


def _positive_value_texts(fig):
    """Parse the '+'-prefixed value-gutter labels into floats."""

    values = []

    for text in fig.findobj(mtext.Text):
        content = text.get_text()

        # Only the top5 value gutter writes an explicit "+" sign
        # (positive animated values); the year text, title and
        # country names never start with one.
        if not content.startswith("+"):
            continue

        try:
            values.append(float(content[1:]))
        except ValueError:
            continue

    return sorted(values)


def test_top5_final_frame_shows_exact_final_values(monkeypatch):
    """The final frame must display the dataset's final values
    exactly (progress == 1.0), while the payoff/replay path is
    actually exercised.

    Fails with the old ``total_frames - payoff_frames`` denominator,
    where the last frame lands at smoothstep((T-1-P)/(T-P)) < 1 and
    every displayed value is scaled short of its final.
    """

    # Guarantee the payoff path is ON regardless of the ambient
    # environment (.env may change it), and pin the entity cap so
    # all four rows render.
    monkeypatch.setattr(settings, "OPENING_PAYOFF_SECONDS", 2.5)
    monkeypatch.setattr(settings, "MAX_CHART_ENTITIES", 4)

    fig, fn, frames = _capture(
        "top5_change", list(TOP5_DATA.index), TOP5_DATA
    )

    assert fn is not None and frames >= 2

    payoff_frames = min(
        int(2.5 * VisualEngine.FPS),
        frames // 2,
    )
    assert payoff_frames > 0, "test requires the payoff path to be on"

    # --- replay really runs (mid-replay values are still small) ---
    fn(payoff_frames + 3)
    replayed = _positive_value_texts(fig)
    assert len(replayed) == 4
    assert max(replayed) < 0.5 * min(TOP5_FINAL_CHANGES), (
        f"replay frame not in the growth phase: {replayed}"
    )

    # --- FINAL frame must equal the final dataset values exactly ---
    fn(frames - 1)
    final_shown = _positive_value_texts(fig)

    assert len(final_shown) == 4, (
        f"expected 4 value labels, got {final_shown}"
    )

    expected = sorted(TOP5_FINAL_CHANGES)

    for shown, want in zip(final_shown, expected):
        assert abs(shown - want) < 1e-9, (
            f"final frame shows {final_shown}, dataset final "
            f"changes are {expected} -- final-frame progress is "
            f"not exactly 1.0 (old denominator bug)"
        )


# ===============================================================
# B) LINE BOTTOM-CLAMP TEST
# ===============================================================

# Converging final endpoints: the last year collapses all four
# series into a 0.3-wide band sitting ON the global floor, which
# forces the end-label declutter to push three of the four labels
# away from their true endpoints.
LINE_NAMES = ["Aster", "Birch", "Cedar", "Daisy"]

LINE_DATA = pd.DataFrame(
    {
        2019: [100.0, 90.0, 85.0, 80.0],
        2020: [80.0, 70.0, 65.0, 60.0],
        2021: [60.0, 50.0, 45.0, 40.0],
        2022: [10.0, 10.1, 10.2, 10.3],
    },
    index=LINE_NAMES,
)


def test_line_bottom_clamp_keeps_names_inside_chart(monkeypatch):
    """A declutter stack pushed against the chart floor must leave
    every NAME label fully inside the chart bounds, without label
    overlap.

    Fails with the old ``bottom_room`` geometry, which allowed the
    stack to sit a half name-height too low and left the bottom
    name label below the plot floor.

    Note on geometry: the renderer's y-floor sits a fixed 12%
    of the data range below the minimum, and every clamp quantity
    scales with that range, so with the default layout the bottom
    clamp is mathematically out of reach.  The test therefore
    tightens the lower y-bound (re-read by the real declutter on
    every frame) to bring the chart floor within reach of the
    stack -- the clamp code path itself is the real production
    code.
    """

    monkeypatch.setattr(settings, "MAX_CHART_ENTITIES", 4)
    monkeypatch.setattr(settings, "OPENING_PAYOFF_SECONDS", 2.5)

    fig, fn, frames = _capture("line", LINE_NAMES, LINE_DATA)

    assert fn is not None and frames >= 2

    ax = fig.axes[0]
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    # Final frame: the replay has reached the converged final year.
    fn(frames - 1)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    y_low0, y_high0 = ax.get_ylim()
    axes_box = ax.get_window_extent(renderer=renderer)
    px_to_y = (y_high0 - y_low0) / float(axes_box.height)

    name_set = set(LINE_NAMES)
    names = [t for t in ax.texts if t.get_text() in name_set]
    assert len(names) == len(LINE_NAMES), (
        f"expected {len(LINE_NAMES)} name labels, got "
        f"{[t.get_text() for t in ax.texts]}"
    )

    # The renderer measures its own name height from the FIRST
    # created label; use the same string so the measurement is
    # identical.
    first = [
        t for t in names if t.get_text() == LINE_NAMES[0]
    ][0]
    name_h = float(
        first.get_window_extent(renderer=renderer).height
    ) * px_to_y

    # Offset the FIXED bottom clamp enforces above y_low:
    #   4px margin + half the name height (entity_dy is 0.0).
    margin = 4.0 * px_to_y + 0.5 * name_h

    true_lowest = float(LINE_DATA[2022].min())
    # Half of that offset keeps the stack in reach of BOTH
    # formulas while still sitting below the old clamp's floor.
    y_low_new = true_lowest - 0.5 * margin

    ax.set_ylim(y_low_new, y_high0)

    # Re-run the final frame against the tightened floor: the real
    # declutter re-reads ax.get_ylim() on every frame.
    fn(frames - 1)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    axes_box = ax.get_window_extent(renderer=renderer)
    fig_w = float(fig.get_figwidth()) * float(fig.dpi)
    fig_h = float(fig.get_figheight()) * float(fig.dpi)

    names = [t for t in ax.texts if t.get_text() in name_set]
    boxes = {
        t.get_text(): t.get_window_extent(renderer=renderer)
        for t in names
    }
    assert len(boxes) == len(LINE_NAMES)

    # --- declutter + bottom clamp actually engaged ---------------
    # The stack's lowest label must sit ABOVE its true endpoint:
    # only the bottom clamp raises it (the upward stacking pushes
    # only affect the higher labels).
    lowest_name = min(
        LINE_NAMES, key=lambda n: float(LINE_DATA.loc[n, 2022])
    )
    lowest_center = names[
        [t.get_text() for t in names].index(lowest_name)
    ].get_position()[1]

    assert lowest_center > true_lowest + 1e-12, (
        f"bottom clamp did not raise the stack "
        f"(center={lowest_center}, endpoint={true_lowest})"
    )

    # --- name labels fully inside the chart bounds ---------------
    for text, box in boxes.items():
        # Frame safety (horizontal + overall): inside the figure.
        assert box.x0 >= -0.5 and box.x1 <= fig_w + 0.5, (
            f"{text}: horizontal frame overflow -> "
            f"x0={box.x0:.1f} x1={box.x1:.1f} (W={fig_w})"
        )
        # Bottom/top clamp domain (vertical): inside the PLOT
        # AREA.  The chart floor is the axis the bottom clamp
        # protects.
        assert box.y0 >= axes_box.y0 - 1.0, (
            f"{text}: name label below the chart floor -> "
            f"y0={box.y0:.1f} < axes y0={axes_box.y0:.1f} "
            f"(old bottom-clamp geometry)"
        )
        assert box.y1 <= axes_box.y1 + 1.0, (
            f"{text}: name label above the chart ceiling -> "
            f"y1={box.y1:.1f} > axes y1={axes_box.y1:.1f}"
        )

    # --- pushed labels still do not overlap ----------------------
    ordered = sorted(boxes.values(), key=lambda b: b.y0)
    for prev, nxt in zip(ordered, ordered[1:]):
        assert nxt.y0 >= prev.y1 - 1.0, (
            f"pushed name labels overlap: {prev} vs {nxt}"
        )
