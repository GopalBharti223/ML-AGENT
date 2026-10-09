"""PART 2a -- OPENING + NUMERIC SAFE FRAME + BAR/TOP5 (offline)."""
import matplotlib

matplotlib.use("Agg")

import matplotlib.animation as manim
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from app.config import settings
from app.visuals import design_system
from app.visuals.scene_engine import VisualEngine
import app.visuals.scene_engine as se


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


class _Script:
    title = "Part 2 Motion"
    topic = "economy"
    category = "economy"
    topic_family = "economy"
    source_name = "World Bank"
    indicator_name = "Population"
    total_duration = 25.0
    chart_type = "bar_race"
    scenes = [{"chart_type": "bar_race", "narration": "n",
               "highlight_countries": []}]

    def __init__(self, chart_type="bar_race", duration=25.0,
                 indicator="Population"):
        self.chart_type = chart_type
        self.total_duration = duration
        self.indicator_name = indicator
        self.scenes = [{"chart_type": chart_type, "narration": "n",
                        "highlight_countries": []}]


def _capture(chart_type, data, duration=25.0, indicator="Population"):
    cap = {}
    os_save = manim.Animation.save
    os_close = plt.close

    def isave(self, f, *a, **k):
        cap["fig"] = getattr(self, "_fig", None)
        cap["fn"] = getattr(self, "_func", None)
        cap["n"] = getattr(self, "_save_count", None) or 0
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
            _Script(chart_type, duration, indicator),
            data, "_pytest_part2_tmp",
        )
    finally:
        manim.Animation.save = os_save
        plt.close = os_close
    assert cap.get("fig") is not None, f"{chart_type}: no figure"
    try:
        cap["fig"].canvas.draw()
    except Exception:
        pass
    return cap["fig"], cap.get("fn"), int(cap.get("n") or 0)


def _extents(fig):
    try:
        renderer = fig.canvas.get_renderer()
    except Exception:
        renderer = None
    out = []
    for ax in fig.axes:
        for t in list(ax.texts):
            try:
                out.append((t.get_text(),
                            t.get_window_extent(renderer=renderer)))
            except Exception:
                continue
    # Year / title / source live as FIGURE texts, not axes texts.
    for t in list(getattr(fig, "texts", [])):
        try:
            out.append((t.get_text(),
                        t.get_window_extent(renderer=renderer)))
        except Exception:
            continue
    return out


def _bar_data():
    return pd.DataFrame(
        {2018: [10e6, 20e6, 5e6, 8e6],
         2020: [20e6, 22e6, 12e6, 9e6],
         2022: [36.7e6, 25e6, 15e6, 12e6]},
        index=["Alpha Republic of Testing", "Beta", "Chad", "Niger"],
    )


def test_p2_answer_hold_is_about_two_seconds():
    secs = float(getattr(settings, "OPENING_PAYOFF_SECONDS", 0.0))
    assert 1.8 <= secs <= 2.2, f"answer hold {secs}s not ~= 2.0s"
    assert design_system.ANSWER_HOLD_SECONDS == pytest.approx(2.0)
    assert design_system.answer_hold_frames(750, fps=30) == 60


def test_p2_opening_frame_shows_final_result():
    fig, fn, n = _capture("bar_race", _bar_data())
    fn(0)
    fig.canvas.draw()
    texts = [t for t, _b in _extents(fig) if t.strip()]
    assert any("36.7M" in t for t in texts), texts[:8]


def test_p2_opening_hold_is_not_empty_but_answer_ready():
    fig, fn, n = _capture("bar_race", _bar_data())
    fn(0)
    fig.canvas.draw()
    b0 = np.asarray(fig.canvas.buffer_rgba()).astype(int)
    fn(15)
    fig.canvas.draw()
    b1 = np.asarray(fig.canvas.buffer_rgba()).astype(int)
    diff = np.abs(b0 - b1).sum(axis=2)
    changed = float((diff.max(axis=1) > 24).mean() * 100.0)
    assert changed > 0.5, f"opening frozen: {changed}%"
    assert any("36.7M" in t for t, _b in _extents(fig))


def test_p2_motion_begins_after_hold():
    fig, fn, n = _capture("bar_race", _bar_data())
    payoff = min(int(2.0 * 30), n // 2)
    fn(payoff - 1)
    fig.canvas.draw()
    before = np.asarray(fig.canvas.buffer_rgba()).astype(int)
    fn(min(n - 1, payoff + 30))
    fig.canvas.draw()
    after = np.asarray(fig.canvas.buffer_rgba()).astype(int)
    changed = float((np.abs(before - after).sum(axis=2) > 24).mean()
                    * 100.0)
    assert changed > 1.0, "no replay after the answer hold"


def test_p2_opening_floor_keeps_answer_readable():
    assert design_system.ENTRANCE_FLOOR >= 0.7


def _assert_inside(fig, label):
    # Numeric VALUE labels only: entity names are covered by the
    # Part 1 left-edge guard; fig-level title/year/source are
    # static chrome.  Values are bold charts text at/near the bar
    # tip -- filter by content shape, not artist parent.
    import re
    w, _h = fig.canvas.get_width_height()
    margin = float(design_system.VALUE_SAFE_MARGIN_PX)
    num = re.compile(r"^[+-]?[$]?[0-9][0-9,]*(\.[0-9])?[KMBT%]?$")
    bad = [(t, round(float(b.x1) - w, 1)) for t, b in _extents(fig)
           if t.strip() and num.match(t.strip())
           and float(b.x1) > w + 1.0]
    assert not bad, f"{label}: value clipped past frame {bad}"
    # Margin is soft headroom (guard aims past it); clipping is hard.


def test_p2_value_36_7M_fully_visible():
    fig, fn, n = _capture("bar_race", _bar_data())
    for f in (0, 15, n // 2, n - 1):
        fn(f)
        fig.canvas.draw()
        _assert_inside(fig, f"frame {f}")
    assert any("36.7M" in t for t, _b in _extents(fig))
    plt.close("all")
