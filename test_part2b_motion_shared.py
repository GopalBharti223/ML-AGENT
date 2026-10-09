"""PART 2b -- FORMATS + BAR/TOP5/TREND MOTION (offline)."""
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from app.visuals import design_system
from app.visuals.scene_engine import VisualEngine
import app.visuals.scene_engine as se
from test_part2a_opening_safeframe import _capture, _extents


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


def _bar_data():
    return pd.DataFrame(
        {2018: [10e6, 20e6, 5e6, 8e6],
         2020: [20e6, 22e6, 12e6, 9e6],
         2022: [36.7e6, 25e6, 15e6, 12e6]},
        index=["Alpha Republic of Testing", "Beta", "Chad", "Niger"],
    )


def _top5_data():
    return pd.DataFrame(
        {2018: [100.0, 50.0, 80.0, 20.0, 60.0],
         2022: [130.0, 30.0, 95.0, 10.0, 61.0]},
        index=["A", "B", "C", "D", "E"],
    )


def _trend():
    return pd.DataFrame(
        {2019: [10.0, 30.0], 2020: [20.0, 25.0],
         2021: [30.0, 20.0], 2022: [40.0, 15.0]},
        index=["Alpha", "Beta"],
    )


@pytest.mark.parametrize("raw,indicator,expect", [
    (1.4e9, "Population", "1.4B"),
    (2.8e12, "GDP current US$", "$2.8T"),
    (98.7, "Share percent", "98.7%"),
    (-12.5, "Change", "-12.5"),
])
def test_p2_numeric_formats_stay_inside(raw, indicator, expect):
    import re
    data = pd.DataFrame(
        {2020: [raw * 0.5, raw * 0.3], 2022: [raw, raw * 0.6]},
        index=["Alpha Republic of Testing", "Beta"],
    )
    fig, fn, n = _capture("bar_race", data, indicator=indicator)
    assert VisualEngine._format_value(raw, indicator) == expect
    w, _h = fig.canvas.get_width_height()
    num = re.compile(r"^[+-]?[$]?[0-9][0-9,]*(\.[0-9])?[KMBT%]?$")
    for f in (0, n - 1):
        fn(f)
        fig.canvas.draw()
        bad = [(t, round(float(b.x1) - w, 1))
               for t, b in _extents(fig)
               if t.strip() and num.match(t.strip())
               and float(b.x1) > w + 1.0]
        assert not bad, f"{expect} f{f}: clipped {bad}"
    plt.close("all")


def test_p2_long_entity_plus_value_both_safe():
    fig, fn, n = _capture("bar_race", _bar_data())
    w, _h = fig.canvas.get_width_height()
    for f in (0, n - 1):
        fn(f)
        fig.canvas.draw()
        for text, box in _extents(fig):
            if text.strip():
                assert float(box.x0) >= -1.0, (text, float(box.x0))
                assert float(box.x1) <= w + 1.0, (text, float(box.x1))
    plt.close("all")


def test_p2_bar_motion_and_final_exact():
    assert VisualEngine._bar_width(0, 100) == 0.0
    assert VisualEngine._bar_width(-5, 100) == 0.0
    assert 0 < abs(VisualEngine._bar_width(51, 100)
                   - VisualEngine._bar_width(50, 100)) < 5
    solved = VisualEngine._solve_label_positions(
        [0.0, 0.4, 1.1, 2.2], 0.72, 0, 3)
    gaps = [solved[i + 1] - solved[i] for i in range(3)]
    assert min(gaps) >= 0.02, solved
    assert VisualEngine.OVERTAKE_EMPHASIS <= 0.65
    assert VisualEngine.LABEL_FONT_BUMP <= 2
    fig, fn, n = _capture("bar_race", _bar_data())
    fn(n - 1)
    fig.canvas.draw()
    shown = sorted(t for t, _b in _extents(fig) if t.strip())
    for expect in ("36.7M", "25.0M", "15.0M", "12.0M"):
        assert any(expect in t for t in shown), (expect, shown)
    # Final YEAR is figure chrome (not an axes text): assert on
    # fig.texts directly instead of the axes-text helper.
    years = [t.get_text() for t in fig.texts]
    assert any("2022" in y for y in years), years
    plt.close("all")


def test_p2_top5_sign_and_final_exact():
    assert VisualEngine._bar_width_signed(5, 10) > 0
    assert VisualEngine._bar_width_signed(-5, 10) < 0
    assert VisualEngine._bar_width_signed(0, 10) == 0.0
    fig, fn, n = _capture("top5_change", _top5_data())
    fn(n - 1)
    fig.canvas.draw()
    shown = [t for t, _b in _extents(fig) if t.strip()]
    assert any("30" in t for t in shown), shown
    plt.close("all")


@pytest.mark.parametrize("chart", ["line", "area"])
def test_p2_trend_final_year(chart):
    fig, fn, n = _capture(chart, _trend())
    fn(n - 1)
    fig.canvas.draw()
    shown = [t for t, _b in _extents(fig)]
    years = [t.get_text() for t in fig.texts]
    assert any("2022" in t for t in shown + years), (chart, shown, years)
    # Final VALUES settle on the true data at progress 1.0.
    assert any("40" in t for t in shown), (chart, shown)
    plt.close("all")
