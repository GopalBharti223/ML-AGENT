"""Measure the three reported defects on the REAL final frame.

1. name label vs its own value text overlap
2. flag vertical centre vs its label's vertical centre
3. year label box vs source line box overlap
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.animation as manim
import matplotlib.pyplot as plt
import matplotlib.text as mtext
import numpy as np
import pandas as pd
import app.visuals.scene_engine as se
from app.visuals.scene_engine import VisualEngine

LONG_LABEL = "Turks and Caicos Islands"
COUNTRIES = ["Ireland", LONG_LABEL, "Georgia", "Guyana"]
RANKS = {
    2018: {"Ireland": 1, LONG_LABEL: 2, "Georgia": 3, "Guyana": 4},
    2019: {"Ireland": 1, LONG_LABEL: 2, "Georgia": 4, "Guyana": 3},
    2020: {"Ireland": 1, LONG_LABEL: 2, "Georgia": 3, "Guyana": 4},
    2021: {"Ireland": 1, LONG_LABEL: 2, "Georgia": 4, "Guyana": 3},
    2022: {"Ireland": 1, LONG_LABEL: 3, "Georgia": 4, "Guyana": 2},
}


class _Script:
    title = "Who leads the rankings?"
    source_name = "World Bank"
    indicator_name = "GDP per capita (current US$)"
    total_duration = 6.0


def main():
    years = sorted(RANKS)
    data = pd.DataFrame(
        {y: [float(10 - RANKS[y][c]) for c in COUNTRIES] for y in years},
        index=COUNTRIES,
    )
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
        se.VisualEngine._duration_override = 0.0
        se.VisualEngine.render_bar_race(_Script(), data, "_tmp/diag")
    finally:
        manim.Animation.save = os_save
        plt.close = os_close

    fig, fn, n = cap["fig"], cap["fn"], int(cap["n"])
    fn(n - 1)
    fig.canvas.draw()
    r = fig.canvas.get_renderer()

    names, values = {}, {}
    for t in fig.findobj(mtext.Text):
        txt = t.get_text().strip()
        if txt in COUNTRIES:
            names[txt] = t
        elif txt and txt not in ("",) and txt[0].isdigit() or txt.startswith("$"):
            values[txt] = t

    print("=== NAME / VALUE ===")
    for c in COUNTRIES:
        t = names[c]
        b = t.get_window_extent(renderer=r)
        print(f"  {c:28s} font={float(t.get_fontsize()):5.1f} "
              f"x0={b.x0:7.1f} x1={b.x1:7.1f} y0={b.y0:7.1f} y1={b.y1:7.1f} "
              f"ycen={(b.y0+b.y1)/2:7.1f}")
    print("  --- values ---")
    for txt, t in values.items():
        b = t.get_window_extent(renderer=r)
        print(f"  {txt:28s} font={float(t.get_fontsize()):5.1f} "
              f"x0={b.x0:7.1f} x1={b.x1:7.1f} y0={b.y0:7.1f} y1={b.y1:7.1f}")

    print("=== OVERLAPS (name x1 vs any value x0 on same row band) ===")
    for c in COUNTRIES:
        nb = names[c].get_window_extent(renderer=r)
        for txt, vt in values.items():
            vb = vt.get_window_extent(renderer=r)
            vcy = (vb.y0 + vb.y1) / 2
            if nb.y0 - 6 <= vcy <= nb.y1 + 6 and vb.x0 < nb.x1:
                print(f"  COLLIDE {c!r} x1={nb.x1:.1f} -> {txt!r} x0={vb.x0:.1f}"
                      f"  overlap={nb.x1 - vb.x0:.1f}px")

    print("=== FLAGS ===")
    from matplotlib.offsetbox import AnnotationBbox
    for art in fig.findobj(AnnotationBbox):
        b = art.get_window_extent(renderer=r)
        print(f"  flag x0={b.x0:7.1f} x1={b.x1:7.1f} y0={b.y0:7.1f} y1={b.y1:7.1f}"
              f" ycen={(b.y0+b.y1)/2:7.1f}")

    print("=== HEADER ===")
    for t in fig.findobj(mtext.Text):
        txt = t.get_text().strip()
        if txt and (txt.startswith("Source:") or txt.isdigit() and len(txt) == 4
                    or txt == "WHO LEADS THE RANKINGS?" or txt == "WHO DOMINATED?"):
            b = t.get_window_extent(renderer=r)
            print(f"  {txt[:34]!r:38s} y0={b.y0:7.1f} y1={b.y1:7.1f} x0={b.x0:7.1f} x1={b.x1:7.1f}")

    print("=== frame right edge / safe ===")
    from app.visuals import design_system as ds
    print("  W =", fig.get_figwidth() * fig.dpi, " safe_right_px =",
          ds.safe_right() * fig.get_figwidth() * fig.dpi)


main()
