"""SLOPE ENDPOINT HONESTY + MOTION (offline).

Slope must never fabricate a comparison: entities without a real
first/last observation are excluded (or the chart raises), never
ffilled into looking complete.  Also pins the value-based
animation and the label de-collision the value-based y made
necessary.
"""
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

import app.visuals.scene_engine as se
from test_part2a_opening_safeframe import _capture


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


def _ax_texts(fig):
    return [
        t.get_text().strip()
        for ax in fig.axes
        for t in ax.texts
        if t.get_text().strip()
    ]


def _slope_data():
    return pd.DataFrame(
        {2018: [100.0, 10.0],
         2022: [200.0, 20.0]},
        index=["Alpha", "Beta"],
    )


def test_missing_end_entity_is_excluded_not_filled():
    """Ghost has no end-year value: it must NOT appear (the old
    ffill path drew it with a fabricated flat endpoint)."""
    data = pd.DataFrame(
        {2018: [10.0, 20.0, 30.0],
         2022: [25.0, 15.0, np.nan]},
        index=["Alpha", "Beta", "Ghost"],
    )
    fig, fn, n = _capture("slope", data)
    fn(n - 1)
    fig.canvas.draw()
    texts = _ax_texts(fig)
    assert "Ghost" not in texts, texts
    assert "30" not in texts, texts  # Ghost's start value never
    plt.close("all")


def test_no_shared_edge_raises_rather_than_fabricating():
    """Alpha has no end value, Beta no start value -- nothing is
    comparable, so the renderer raises instead of inventing one."""
    data = pd.DataFrame(
        {2018: [10.0, np.nan],
         2022: [np.nan, 20.0]},
        index=["Alpha", "Beta"],
    )
    with pytest.raises(ValueError, match="values in both"):
        _capture("slope", data)
    plt.close("all")


def test_all_nan_end_year_raises_window_error():
    data = pd.DataFrame(
        {2018: [10.0, 20.0],
         2022: [np.nan, np.nan]},
        index=["Alpha", "Beta"],
    )
    with pytest.raises(ValueError, match="two years"):
        _capture("slope", data)
    plt.close("all")


def test_prepare_chart_data_fill_flag():
    """Default behavior (other charts) still fills; fill=False
    (slope) preserves the real missingness."""
    df = pd.DataFrame(
        {2018: [1.0, 5.0],
         2020: [np.nan, 6.0],
         2022: [3.0, np.nan]},
        index=["A", "B"],
    )
    filled = se.VisualEngine._prepare_chart_data(df.copy())
    assert not filled.isna().any().any(), filled

    raw = se.VisualEngine._prepare_chart_data(
        df.copy(), fill=False
    )
    assert raw.isna().any().any(), raw


def test_animation_interpolates_true_endpoint_values():
    fig, fn, n = _capture("slope", _slope_data())

    fn(0)
    fig.canvas.draw()
    start = {
        (y0, y1)
        for line in fig.axes[0].lines
        for xs, ys in [tuple(line.get_data())]
        if len(ys) == 2 and float(xs[0]) == 0.0
        for y0, y1 in [(float(ys[0]), float(ys[1]))]
    }
    assert (100.0, 100.0) in start, start

    fn(n - 1)
    fig.canvas.draw()
    end = {
        (y0, y1)
        for line in fig.axes[0].lines
        for xs, ys in [tuple(line.get_data())]
        if len(ys) == 2 and float(xs[0]) == 0.0
        for y0, y1 in [(float(ys[0]), float(ys[1]))]
    }
    assert (100.0, 200.0) in end, end
    plt.close("all")


def test_right_value_label_fades_with_the_line():
    fig, fn, n = _capture("slope", _slope_data())

    fn(0)
    fig.canvas.draw()
    at_start = [
        t for t in fig.axes[0].texts
        if t.get_text().strip() == "200"
    ]
    assert at_start, "end value label missing"
    assert float(at_start[0].get_alpha() or 0.0) == 0.0

    fn(n - 1)
    fig.canvas.draw()
    at_end = [
        t for t in fig.axes[0].texts
        if t.get_text().strip() == "200"
    ]
    assert float(at_end[0].get_alpha() or 0.0) == 1.0
    plt.close("all")


def test_tied_values_do_not_stack_labels():
    """Near-identical values share a raw row; the value-scale
    solver must separate the labels (rank rows never collided)."""
    data = pd.DataFrame(
        {2018: [100.0, 100.0001],
         2022: [50.0, 50.0001]},
        index=["Alpha", "Beta"],
    )
    fig, fn, n = _capture("slope", data)
    fn(n - 1)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    names = [
        t for t in fig.axes[0].texts
        if t.get_text().strip() in ("Alpha", "Beta")
    ]
    assert len(names) == 4, [t.get_text() for t in names]
    boxes = [
        t.get_window_extent(renderer=renderer)
        for t in names
    ]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            overlap = not (
                a.y1 <= b.y0 or b.y1 <= a.y0
                or a.x1 <= b.x0 or b.x1 <= a.x0
            )
            assert not overlap, (
                names[i].get_text(),
                names[j].get_text(),
            )
    plt.close("all")