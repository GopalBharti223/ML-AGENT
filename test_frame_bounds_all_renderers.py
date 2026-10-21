"""CROSS-RENDERER FRAME-BOUNDS + HARD-VALUE QA (offline).

The existing suites pin pieces of this matrix: entity-name bounds
(test_long_label_frame_safety), bar-race values (test_part2a/2b),
slope endpoints (test_slope_*), top5 finals (test_top5_*).  This
file closes the remaining gaps with ONE scanner that measures every
visible text artist on ALL FOUR frame edges at the OPENING, MIDDLE
and FINAL frames of ALL EIGHT renderers, plus:

  * hard-formatted values (36.7M / 1.4B / $2.8T / 98.7% / signed
    changes / shares) must RENDER at the final frame and stay
    inside the frame on every renderer that displays them;
  * negative endpoints, all-zero flat series, interior NaNs and
    tied values must render clean -- no "nan" strings, no
    exceptions, nothing off-frame;
  * the bubble TIME-SERIES FALLBACK must draw its entity names as
    real artists inside the frame.  It used to render ANONYMOUS
    bars: set_axis_off() silently drops y-tick labels, and their
    geometry was off-frame anyway (x0 ~ -322px measured).

Everything is offline: flags stubbed, no ffmpeg, no network.
"""
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.text as mtext
import numpy as np
import pandas as pd
import pytest

import app.visuals.scene_engine as se
from test_part2a_opening_safeframe import _capture


@pytest.fixture(autouse=True)
def _no_network_flags(monkeypatch):
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


# =================================================================
# Fixtures
# =================================================================

NAMES = [
    "Democratic Republic of the Congo",
    "Ireland",
    "Guyana",
    "Georgia",
]

GDP_NAMES = ["Germany", "Japan", "Ireland", "Canada"]

ALL_CHARTS = [
    "bar_race",
    "top5_change",
    "area",
    "slope",
    "line",
    "bubble",
    "pie",
    "waffle",
]


def _pop_levels():
    """Population levels: finals 102.4M / 5.1M / 36.7M / 1.4B."""
    return pd.DataFrame(
        {
            2018: [40.0e6, 3.0e6, 10.0e6, 800.0e6],
            2020: [71.2e6, 4.05e6, 20.0e6, 1.1e9],
            2022: [102.4e6, 5.1e6, 36.7e6, 1.4e9],
        },
        index=NAMES,
    )


def _gdp_levels():
    """GDP levels: Canada ends at exactly $2.8T."""
    return pd.DataFrame(
        {
            2018: [3.0e12, 3.5e12, 0.35e12, 2.0e12],
            2020: [3.6e12, 3.7e12, 0.42e12, 2.4e12],
            2022: [4.3e12, 4.0e12, 0.50e12, 2.8e12],
        },
        index=GDP_NAMES,
    )


def _percent_levels():
    """Percent metric: tops out at exactly 98.7%."""
    return pd.DataFrame(
        {
            2018: [70.0, 30.0, 55.0, 85.0],
            2020: [84.0, 37.0, 65.0, 49.0],
            2022: [98.7, 45.3, 76.0, 12.9],
        },
        index=NAMES,
    )


def _pop_change():
    """Changes: +62.4M / +2.1M / +36.7M / +1.4B."""
    return pd.DataFrame(
        {
            2018: [40.0e6, 3.0e6, 0.0, 0.0],
            2022: [102.4e6, 5.1e6, 36.7e6, 1.4e9],
        },
        index=NAMES,
    )


def _gdp_change():
    """Changes: +$2.8T / -$1.4T / $0 / $0 (negatives + zeros)."""
    return pd.DataFrame(
        {
            2018: [3.0e12, 4.0e12, 2.0e12, 1.0e12],
            2022: [5.8e12, 2.6e12, 2.0e12, 1.0e12],
        },
        index=GDP_NAMES,
    )


def _share():
    return pd.DataFrame(
        {2021: [44.0, 27.0, 17.0, 12.0]},
        index=NAMES,
    )


def _xy():
    """Genuine x/y bubble frame (bubble's primary format)."""
    return pd.DataFrame(
        {
            "x": [1.0, 2.0, 3.0, 4.0],
            "y": [10.0, 40.0, 25.0, 60.0],
        },
        index=NAMES,
    )


def _data_for(chart):
    if chart in ("pie", "waffle"):
        return _share()
    if chart == "top5_change":
        return _pop_change()
    if chart == "bubble":
        return _xy()
    return _pop_levels()


# =================================================================
# Scanner: every visible text, all four edges, several frames
# =================================================================

def _visible_texts(fig):
    out = []
    for text in fig.findobj(mtext.Text):
        content = text.get_text().strip()
        if not content or not text.get_visible():
            continue
        alpha = text.get_alpha()
        # None means "no explicit alpha" -> fully visible.
        if alpha is not None and float(alpha) <= 0.01:
            continue
        out.append(text)
    return out


def _scan_all(fig, fn, steps):
    """Measure every visible text at each step against the frame.

    Returns (width, height, offenders, seen_texts).
    """
    width = float(fig.get_figwidth()) * float(fig.dpi)
    height = float(fig.get_figheight()) * float(fig.dpi)

    offenders = []
    seen = set()

    for step in steps:
        fn(step)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()

        for text in _visible_texts(fig):
            content = text.get_text().strip()
            box = text.get_window_extent(renderer=renderer)
            x0 = float(box.x0)
            y0 = float(box.y0)
            x1 = float(box.x1)
            y1 = float(box.y1)

            if x0 < -1.0 or y0 < -1.0 or x1 > width + 1.0 or y1 > height + 1.0:
                entry = (
                    content[:48],
                    round(x0, 1),
                    round(y0, 1),
                    round(x1, 1),
                    round(y1, 1),
                    step,
                )
                if entry not in offenders:
                    offenders.append(entry)

            seen.add(content)

    return width, height, offenders, seen


def _final_texts(fig, fn, n):
    """Exact text strings visible at the final frame."""
    fn(n - 1)
    fig.canvas.draw()
    return {t.get_text().strip() for t in _visible_texts(fig)}


def _steps(n):
    return (0, n // 2, n - 1)


# =================================================================
# 1. ALL RENDERERS: every visible text inside all four edges
# =================================================================

@pytest.mark.parametrize("chart", ALL_CHARTS)
def test_all_visible_texts_inside_frame(chart):
    """Opening, middle and final frames: no text may cross any
    edge of the 1080x1920 frame -- values, names, year counter,
    title, source, tick labels and legend rows alike."""
    fig, fn, n = _capture(chart, _data_for(chart), duration=6.0)
    width, height, offenders, seen = _scan_all(fig, fn, _steps(n))

    assert seen, f"{chart}: no visible texts at all (blank chrome?)"
    assert not offenders, f"{chart}: off-frame text -> {offenders}"

    # Final frame keeps its chrome: title + source line.
    final = _final_texts(fig, fn, n)
    assert any("Source:" in t for t in final), sorted(final)[:12]
    assert any("PART 2 MOTION" in t for t in final), sorted(final)[:12]

    plt.close("all")


# =================================================================
# 2. HARD VALUES: formatted strings render AND stay inside
# =================================================================

HARD_CASES = [
    # chart, indicator, data factory, needles expected at FINAL frame
    ("bar_race", "Population", _pop_levels, ("36.7M", "1.4B")),
    ("line", "Population", _pop_levels, ("36.7M", "1.4B")),
    ("area", "Population", _pop_levels, ("36.7M", "1.4B")),
    ("slope", "Population", _pop_levels, ("36.7M", "1.4B")),
    ("bar_race", "GDP (current US$)", _gdp_levels, ("$2.8T",)),
    ("line", "GDP (current US$)", _gdp_levels, ("$2.8T",)),
    ("area", "GDP (current US$)", _gdp_levels, ("$2.8T",)),
    ("area", "Literacy rate (%)", _percent_levels, ("98.7%",)),
    ("slope", "Literacy rate (%)", _percent_levels, ("98.7%",)),
    ("top5_change", "Population", _pop_change, ("+36.7M", "+1.4B")),
    ("top5_change", "GDP (current US$)", _gdp_change,
     ("+$2.8T", "-$1.4T", "$0")),
    ("pie", "Share of total", _share, ("44.0%",)),
    ("waffle", "Share of total", _share, ("44.0%",)),
]


@pytest.mark.parametrize(
    "chart,indicator,factory,needles",
    HARD_CASES,
    ids=[f"{c}-{i.split()[0].lower()}" for c, i, _f, _n in HARD_CASES],
)
def test_hard_values_render_and_stay_inside(chart, indicator, factory, needles):
    """The hard strings named in the QA brief must be on screen at
    the final frame -- fully inside the frame, not clipped."""
    fig, fn, n = _capture(
        chart, factory(), duration=6.0, indicator=indicator
    )
    width, height, offenders, seen = _scan_all(fig, fn, _steps(n))

    assert not offenders, f"{chart}/{indicator}: off-frame -> {offenders}"

    final = _final_texts(fig, fn, n)
    for needle in needles:
        assert any(needle in t for t in final), (
            f"{chart}/{indicator}: {needle!r} missing at final frame; "
            f"texts={sorted(final)}"
        )

    # The needles' own artists must be in-frame too (scan covers all
    # steps, but assert explicitly so a future scan filter can't
    # silently exempt value labels).
    fn(n - 1)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for text in _visible_texts(fig):
        content = text.get_text().strip()
        if not any(needle in content for needle in needles):
            continue
        box = text.get_window_extent(renderer=renderer)
        assert box.x0 >= -1.0 and box.x1 <= width + 1.0, (
            f"{chart}: {content!r} clipped x0={box.x0:.1f} "
            f"x1={box.x1:.1f} (W={width})"
        )
        assert box.y0 >= -1.0 and box.y1 <= height + 1.0, (
            f"{chart}: {content!r} clipped y0={box.y0:.1f} "
            f"y1={box.y1:.1f} (H={height})"
        )

    plt.close("all")


# =================================================================
# 3. NEGATIVE ENDPOINTS (line / area)
# =================================================================

@pytest.mark.parametrize("chart", ["line", "area"])
def test_negative_endpoint_renders_inside(chart):
    """A series that ends below zero must print the negative value
    and keep it inside the frame."""
    data = pd.DataFrame(
        {
            2018: [30.0, 50.0],
            2020: [8.0, 40.0],
            2022: [-12.5, 25.0],
        },
        index=["Alpha", "Beta"],
    )
    fig, fn, n = _capture(
        chart, data, duration=6.0, indicator="Change in output"
    )
    width, height, offenders, seen = _scan_all(fig, fn, _steps(n))

    assert not offenders, f"{chart}: off-frame -> {offenders}"

    final = _final_texts(fig, fn, n)
    assert "-12.5" in final, sorted(final)

    plt.close("all")


# =================================================================
# 4. ALL-ZERO FLAT SERIES
# =================================================================

@pytest.mark.parametrize("chart", ["bar_race", "line", "top5_change"])
def test_all_zero_series_renders_clean(chart):
    """A flat all-zero frame must render (guards exist for the
    max<=0 division) with values on screen and nothing off-frame."""
    data = pd.DataFrame(
        {
            2018: [0.0, 0.0, 0.0, 0.0],
            2020: [0.0, 0.0, 0.0, 0.0],
            2022: [0.0, 0.0, 0.0, 0.0],
        },
        index=NAMES,
    )
    fig, fn, n = _capture(chart, data, duration=6.0)
    width, height, offenders, seen = _scan_all(fig, fn, _steps(n))

    assert not offenders, f"{chart}: off-frame -> {offenders}"

    final = _final_texts(fig, fn, n)
    assert "0" in final, sorted(final)
    assert len(final) >= 3, f"{chart}: blank chrome at final frame"

    plt.close("all")


# =================================================================
# 5. INTERIOR NaNs (filled charts must never print "nan")
# =================================================================

@pytest.mark.parametrize("chart", ["bar_race", "line"])
def test_interior_nan_never_renders(chart):
    data = pd.DataFrame(
        {
            2018: [10e6, 20e6, 5e6, 8e6],
            2020: [np.nan, 22e6, np.nan, 9e6],
            2022: [36.7e6, np.nan, 15e6, 12e6],
        },
        index=NAMES,
    )
    fig, fn, n = _capture(chart, data, duration=6.0)
    width, height, offenders, seen = _scan_all(fig, fn, _steps(n))

    assert not offenders, f"{chart}: off-frame -> {offenders}"

    leaked = sorted(t for t in seen if "nan" in t.lower())
    assert not leaked, f"{chart}: NaN leaked into rendered text: {leaked}"

    final = _final_texts(fig, fn, n)
    # bar_race drops entities lacking every checkpoint year; only
    # Georgia (8e6 / 9e6 / 12e6) has complete data, so its final
    # 12.0M is the rendered value (36.7M was DRC, dropped for the
    # missing 2020 observation).
    assert "12.0M" in final, sorted(final)

    plt.close("all")


# =================================================================
# 6. TIED VALUES (bar_race)
# =================================================================

def test_bar_race_tied_values_render_distinct_rows():
    """Two entities with IDENTICAL values still get their own rows
    (rank method='first') and both stay inside the frame."""
    data = pd.DataFrame(
        {
            2018: [10e6, 10e6, 5e6, 8e6],
            2020: [20e6, 20e6, 12e6, 9e6],
            2022: [36.7e6, 36.7e6, 15e6, 12e6],
        },
        index=NAMES,
    )
    fig, fn, n = _capture("bar_race", data, duration=6.0)
    width, height, offenders, seen = _scan_all(fig, fn, _steps(n))

    assert not offenders, f"off-frame -> {offenders}"

    fn(n - 1)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    # Entities render their CONFIGURED SHORT NAME (UI_SHORT_NAME_MAP),
    # so a known-long name such as "Democratic Republic of the Congo"
    # is drawn as "DR Congo" -- that is what keeps the label at the
    # intended 34pt instead of shrinking it.  Resolve through the
    # same helper the renderer uses; the count and row-separation
    # assertions below are unchanged in strength.
    name_set = {
        se.design_system.short_name(name) for name in NAMES
    }
    labels = [
        t for t in fig.axes[0].texts
        if t.get_text().strip() in name_set
    ]
    assert len(labels) == len(NAMES), [
        t.get_text() for t in fig.axes[0].texts
    ]

    # Distinct display rows for every name.
    ys = sorted(t.get_window_extent(renderer=renderer).y0 for t in labels)
    gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    assert min(gaps) >= 1.0, f"stacked tied labels: gaps={gaps}"

    final = _final_texts(fig, fn, n)
    assert "36.7M" in final, sorted(final)

    plt.close("all")


# =================================================================
# 7. BUBBLE TIME-SERIES FALLBACK: drawn names, inside the frame
# =================================================================

def test_bubble_time_series_fallback_draws_names_inside_frame():
    """render_bubble falls back to a ranked-bar view when the frame
    has no x/y columns.  The old implementation put entity names on
    y-tick labels -- which set_axis_off() NEVER draws (pixel-diff
    verified), and whose geometry was off-frame anyway (x0 ~ -322px
    for the Congo).  The fallback must draw the names as real axes
    texts, inside the frame."""
    fig, fn, n = _capture("bubble", _pop_levels(), duration=6.0)
    ax = fig.axes[0]
    width, height, offenders, _seen = _scan_all(fig, fn, _steps(n))

    assert not offenders, (
        "fallback labels off-frame (tick-label path back?) -> "
        f"{offenders}"
    )

    ax_names = {t.get_text().strip() for t in ax.texts}
    missing = [name for name in NAMES if name not in ax_names]
    assert not missing, (
        "entity names must be DRAWN axes texts -- y-tick labels are "
        f"never rendered with axison=False; missing={missing}"
    )

    # And every drawn name sits inside the frame at the final frame.
    fn(n - 1)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for text in ax.texts:
        content = text.get_text().strip()
        if content not in NAMES:
            continue
        box = text.get_window_extent(renderer=renderer)
        assert box.x0 >= -1.0 and box.x1 <= width + 1.0, (
            f"{content!r}: x0={box.x0:.1f} x1={box.x1:.1f} (W={width})"
        )
        assert box.y0 >= -1.0 and box.y1 <= height + 1.0, (
            f"{content!r}: y0={box.y0:.1f} y1={box.y1:.1f} (H={height})"
        )

    plt.close("all")


if __name__ == "__main__":
    raise SystemExit(
        pytest.main([__file__, "-v", "--no-header", "-p", "no:randomly"])
    )
