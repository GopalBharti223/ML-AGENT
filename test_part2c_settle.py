"""PART 2c -- SLOPE/BUBBLE/PIE/WAFFLE + SHARED INVARIANTS (offline)."""
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from app.visuals import design_system
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


def test_p2_normalized_progress_monotonic_bounded():
    seq = [design_system.normalized_progress(f, 750)
           for f in range(0, 750, 25)]
    assert all(-1e-9 <= v <= 1.0 + 1e-9 for v in seq)
    assert all(b >= a - 1e-9 for a, b in zip(seq, seq[1:]))
    assert seq[0] == pytest.approx(0.0)
    # Last SAMPLE (frame 725 of 749 steps) is eased-near-1; the
    # exact final frame is what must settle at 1.0.
    assert seq[-1] > 0.99
    assert design_system.normalized_progress(749, 750) == pytest.approx(
        1.0
    )


def test_p2_easing_bounded_monotonic_no_nan():
    import math
    for name in ("ease_in_out", "ease_out"):
        fn = getattr(design_system, name)
        prev = -1.0
        for i in range(101):
            v = fn(i / 100.0)
            assert math.isfinite(v)
            assert 0.0 <= v <= 1.0
            assert v >= prev - 1e-9
            prev = v
        assert fn(-0.5) == pytest.approx(0.0)
        assert fn(1.5) == pytest.approx(1.0)


def test_p2_old_payoff_denominator_fails_final_frame():
    T, P = 750, 60
    assert (T - 1 - P) / (T - P) < 1.0
    assert (T - 1 - P) / (T - 1 - P) == pytest.approx(1.0)


def test_p2_slope_bubble_pie_waffle_settle():
    slope = pd.DataFrame({2018: [10.0, 20.0], 2022: [25.0, 15.0]},
                         index=["Alpha", "Beta"])
    fig, fn, n = _capture("slope", slope)
    fn(n - 1)
    fig.canvas.draw()
    assert any(t.strip() in ("Alpha", "Beta")
               for t, _b in _extents(fig))
    plt.close("all")
    share = pd.DataFrame({2022: [50.0, 30.0, 20.0]},
                         index=["A", "B", "C"])
    fig, fn, n = _capture("pie", share)
    fn(n - 1)
    fig.canvas.draw()
    assert any("50.0%" in t for t, _b in _extents(fig))
    plt.close("all")
    # Waffle allocation is exact in the COUNTER text (figure
    # chrome, not an axes text): legend rows are swatches.
    fig, fn, n = _capture("waffle", share)
    fn(n - 1)
    fig.canvas.draw()
    counter = [t.get_text() for t in fig.texts]
    assert any("100 / 100" in t for t in counter), counter
    plt.close("all")
    xy = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [2.0, 3.0, 1.0],
                       "size": [5.0, 10.0, 7.0]}, index=["A", "B", "C"])
    _f1, _fn1, n1 = _capture("bubble", xy)
    _f2, _fn2, n2 = _capture("bubble", xy)
    assert n1 == n2
    plt.close("all")
