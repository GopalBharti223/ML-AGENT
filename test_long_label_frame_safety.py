"""LONG-LABEL FRAME-SAFETY REGRESSION TESTS.

Measures the REAL display-pixel bounding box of every entity
label produced by the REAL renderers, on EVERY animation frame.

These assert measured geometry, not the presence of a helper:
a renderer that merely CONTAINS a fitting call but still emits
an off-canvas label fails here.

matplotlib window extents are bottom-origin, so the assertions
are x0>=0, y0>=0, x1<=W, y1<=H.
"""
import matplotlib

matplotlib.use("Agg")

import matplotlib.animation as manim
import matplotlib.pyplot as plt
import matplotlib.text as mtext

import pandas as pd
import pytest

from app.visuals.scene_engine import VisualEngine
import app.visuals.scene_engine as se


# The exact case named in the investigation.
LONG_NAME = "Democratic Republic of the Congo"

LONG_NAMES = [
    LONG_NAME,
    "Turks and Caicos Islands",
    "Bosnia and Herzegovina",
    "Central African Republic",
]

# Charts whose design shows the COMPLETE entity name.
FULL_LABEL_CHARTS = [
    "bar_race",
    "top5_change",
    "line",
    "area",
    "slope",
    "bubble",
]


class _Script:
    title = "Long Label Safety"
    topic = "economy"
    category = "economy"
    topic_family = "economy"
    source_name = "World Bank"
    indicator_name = "Indicator"
    total_duration = 1.0

    def __init__(self, chart_type):
        self.chart_type = chart_type
        self.scenes = [
            {
                "chart_type": chart_type,
                "narration": "n",
                "highlight_countries": [LONG_NAMES[0]],
            }
        ]


@pytest.fixture(autouse=True)
def _no_network_flags(monkeypatch):
    monkeypatch.setattr(
        se.VisualEngine, "prefetch_flags",
        classmethod(lambda cls, items: None),
    )
    monkeypatch.setattr(
        se.VisualEngine, "_get_flag_image",
        staticmethod(lambda name: None),
    )


def _capture(chart_type, names, data):
    """Run a real renderer and return (fig, update, frames)."""

    cap = {}
    os_save = manim.Animation.save
    os_close = plt.close

    def isave(self, f, *a, **k):
        cap["fig"] = getattr(self, "_fig", None)
        cap["fn"] = getattr(self, "_func", None)
        cap["n"] = getattr(self, "_save_count", None) or 0

        # matplotlib's Animation schedules a '_draw_first_frame'
        # callback on the FIRST draw_event which calls update(0).
        # Leaving it pending silently rewinds the artists after
        # the loop, so consume it now.
        try:
            cap["fig"].canvas.draw()
        except Exception:
            pass

        if cap["fn"] and cap["n"]:
            for i in range(int(cap["n"])):
                cap["fn"](i)

    manim.Animation.save = isave
    plt.close = lambda *a, **k: None

    try:
        getattr(VisualEngine, f"render_{chart_type}")(
            _Script(chart_type), data, "_pytest_label_tmp"
        )
    finally:
        manim.Animation.save = os_save
        plt.close = os_close

    assert cap.get("fig") is not None, f"{chart_type}: no figure"

    return cap["fig"], cap.get("fn"), int(cap.get("n") or 0)


def _timeseries(names):
    base = [10.0, 40.0, 25.0, 60.0]
    return pd.DataFrame(
        {
            year: [
                base[i % len(base)] * (1.0 + 0.13 * i)
                for i in range(len(names))
            ]
            for year in (2019, 2020, 2021, 2022)
        },
        index=list(names),
    )


def _xy(names):
    return pd.DataFrame(
        {
            "x": [float(i + 1) for i in range(len(names))],
            "y": [10.0, 40.0, 25.0, 60.0][: len(names)],
        },
        index=list(names),
    )


def _share(names):
    shares = [44.0, 27.0, 17.0, 12.0][: len(names)]
    return pd.DataFrame(
        {2020: shares, 2021: shares},
        index=list(names),
    )


def _payload(chart_type, names):
    if chart_type == "bubble":
        return _xy(names)
    if chart_type in ("pie", "waffle"):
        return _share(names)
    return _timeseries(names)


def _scan(fig, fn, frames, needles):
    """Measure matching labels on every frame.

    Returns (width, height, offenders, seen_texts).
    """

    width = float(fig.get_figwidth()) * float(fig.dpi)
    height = float(fig.get_figheight()) * float(fig.dpi)

    offenders = []
    seen = set()

    steps = range(frames) if fn and frames else [None]

    for step in steps:

        if step is not None:
            fn(step)

        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()

        for text in fig.findobj(mtext.Text):

            content = text.get_text()

            if not content:
                continue

            if not any(n in content for n in needles):
                continue

            alpha = text.get_alpha()

            # None means "no explicit alpha", i.e. fully visible.
            if alpha is not None and float(alpha) <= 0.01:
                continue

            box = text.get_window_extent(renderer=renderer)

            x0, y0 = float(box.x0), float(box.y0)
            x1, y1 = float(box.x1), float(box.y1)

            if x0 < 0 or x1 > width or y0 < 0 or y1 > height:

                entry = (content, x0, y0, x1, y1, step)

                if entry not in offenders:
                    offenders.append(entry)

            seen.add(content)

    return width, height, offenders, seen


@pytest.mark.parametrize("chart_type", FULL_LABEL_CHARTS)
def test_long_labels_stay_inside_frame(chart_type):
    """Every complete entity label must fit the frame on every
    frame -- including the exact regression case named in the
    investigation report."""

    fig, fn, frames = _capture(
        chart_type, LONG_NAMES, _payload(chart_type, LONG_NAMES)
    )

    width, height, offenders, seen = _scan(
        fig, fn, frames, LONG_NAMES
    )

    assert seen, f"{chart_type}: no entity labels were measured"

    assert offenders == [], (
        f"{chart_type}: off-frame labels -> {offenders}"
    )


@pytest.mark.parametrize("chart_type", FULL_LABEL_CHARTS)
def test_short_labels_are_unaffected(chart_type):
    """Frame-safety work must not disturb the ordinary short-name
    case: short labels still render and still fit."""

    short = ["USA", "China", "India", "Brazil"]

    fig, fn, frames = _capture(
        chart_type, short, _payload(chart_type, short)
    )

    width, height, offenders, seen = _scan(fig, fn, frames, short)

    assert seen, f"{chart_type}: short labels vanished"

    assert offenders == [], (
        f"{chart_type}: short labels broke -> {offenders}"
    )


@pytest.mark.parametrize("chart_type", ["pie", "waffle"])
def test_truncating_charts_stay_inside_frame(chart_type):
    """pie/waffle truncate names BY DESIGN so the legend fits.

    That truncation is intentional, so this test asserts only
    that the truncated result stays inside the frame -- it does
    NOT assert the full name is present.
    """

    names = LONG_NAMES

    prefixes = [n[:18] for n in names] + [n[:22] for n in names]

    fig, fn, frames = _capture(chart_type, names, _share(names))

    width, height, offenders, seen = _scan(
        fig, fn, frames, prefixes
    )

    assert seen, f"{chart_type}: no legend labels were measured"

    assert offenders == [], (
        f"{chart_type}: truncated legend overflowed -> {offenders}"
    )