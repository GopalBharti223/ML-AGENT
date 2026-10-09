"""SLOPE VALUE ENDPOINTS (offline).

Slope used to draw y from RANKS -- every line stayed flat at its
rank rows regardless of the metric -- and never printed endpoint
values.  These tests pin the fixed behavior: lines follow the
real metric values and start/end values render beside their
endpoints in the right format per indicator type.
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


def _value_pairs(fig):
    """(y0, y1) of every two-point entity line (excludes ticks)."""
    out = []
    for line in fig.axes[0].lines:
        xs, ys = line.get_data()
        if len(ys) == 2 and float(xs[0]) == 0.0:
            out.append((float(ys[0]), float(ys[1])))
    return out


def _slope_data():
    # Ranks are IDENTICAL both years (1, 2 -> 1, 2); only the
    # values move.  Rank-based y renders both lines flat.
    return pd.DataFrame(
        {2018: [100.0, 10.0],
         2022: [200.0, 20.0]},
        index=["Alpha", "Beta"],
    )


def test_slope_lines_follow_values_not_ranks():
    fig, fn, n = _capture("slope", _slope_data())
    fn(n - 1)
    fig.canvas.draw()
    pairs = _value_pairs(fig)
    assert (100.0, 200.0) in pairs, pairs
    assert (10.0, 20.0) in pairs, pairs
    plt.close("all")


def test_slope_start_and_end_values_render():
    fig, fn, n = _capture("slope", _slope_data())
    fn(n - 1)
    fig.canvas.draw()
    texts = _ax_texts(fig)
    assert "100" in texts, texts   # Alpha start
    assert "200" in texts, texts   # Alpha end
    assert "10" in texts, texts    # Beta start
    assert "20" in texts, texts    # Beta end
    plt.close("all")


def test_slope_gdp_endpoints_are_currency():
    data = pd.DataFrame(
        {2016: [18.8e12, 12.0e12],
         2024: [30.8e12, 15.0e12]},
        index=["USA", "Germany"],
    )
    fig, fn, n = _capture(
        "slope", data, indicator="GDP (current US$)"
    )
    fn(n - 1)
    fig.canvas.draw()
    texts = _ax_texts(fig)
    assert "$18.8T" in texts, texts
    assert "$30.8T" in texts, texts
    assert "$12.0T" in texts, texts
    assert "$15.0T" in texts, texts
    plt.close("all")


def test_slope_pageviews_compact_without_currency():
    data = pd.DataFrame(
        {2016: [1.2e9, 5.0e5],
         2024: [8.0e8, 1.24e7]},
        index=["Alpha", "Beta"],
    )
    fig, fn, n = _capture(
        "slope", data,
        indicator="Wikipedia Search Interest (Pageviews)",
    )
    fn(n - 1)
    fig.canvas.draw()
    texts = _ax_texts(fig)
    assert "1.2B" in texts, texts
    assert "800.0M" in texts, texts
    assert "500.0K" in texts, texts
    assert "12.4M" in texts, texts
    assert not any("$" in t for t in texts), texts
    plt.close("all")


def test_slope_year_ticks_frame_the_window():
    fig, fn, n = _capture("slope", _slope_data())
    fn(n - 1)
    fig.canvas.draw()
    ticks = [
        t.get_text()
        for t in fig.axes[0].get_xticklabels()
    ]
    assert "2018" in ticks, ticks
    assert "2022" in ticks, ticks
    plt.close("all")