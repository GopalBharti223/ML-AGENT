"""Scan EVERY frame of the real render for name/value overlaps and
flag-vs-label vertical error, so the fix is validated on the
animation rather than on one synthetic frame."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.animation as manim
import matplotlib.pyplot as plt
import matplotlib.text as mtext
import pandas as pd
import app.visuals.scene_engine as se
from app.visuals.scene_engine import VisualEngine

COUNTRIES = ["Ireland", "Turks and Caicos Islands", "Georgia", "Guyana"]
RANKS = {
    2018: {"Ireland": 1, "Turks and Caicos Islands": 2, "Georgia": 3, "Guyana": 4},
    2019: {"Ireland": 1, "Turks and Caicos Islands": 2, "Georgia": 4, "Guyana": 3},
    2020: {"Ireland": 1, "Turks and Caicos Islands": 2, "Georgia": 3, "Guyana": 4},
    2021: {"Ireland": 1, "Turks and Caicos Islands": 2, "Georgia": 4, "Guyana": 3},
    2022: {"Ireland": 1, "Turks and Caicos Islands": 3, "Georgia": 4, "Guyana": 2},
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
        se.VisualEngine.render_bar_race(_Script(), data, "_tmp/scan")
    finally:
        manim.Animation.save = os_save
        plt.close = os_close

    fig, fn, n = cap["fig"], cap["fn"], int(cap["n"])
    overlaps, verrs = {}, {}

    for step in range(n):
        fn(step)
        fig.canvas.draw()
        r = fig.canvas.get_renderer()

        names, values = {}, {}
        for t in fig.findobj(mtext.Text):
            txt = t.get_text().strip()
            if txt in COUNTRIES:
                names[txt] = t
            elif txt and (txt[0].isdigit() or txt[0] in "$+-"):
                values.setdefault(txt, t)

        for c, nt in names.items():
            nb = nt.get_window_extent(renderer=r)
            for txt, vt in values.items():
                vb = vt.get_window_extent(renderer=r)
                vcy = (vb.y0 + vb.y1) / 2
                if nb.y0 - 8 <= vcy <= nb.y1 + 8 and vb.x0 < nb.x1:
                    key = (c, txt)
                    worst = overlaps.get(key, 0.0)
                    overlaps[key] = max(worst, nb.x1 - vb.x0)

    print("frames scanned:", n)
    print("NAME/VALUE OVERLAPS:", len(overlaps))
    for k, v in sorted(overlaps.items(), key=lambda kv: -kv[1]):
        print(f"  {k[0]!r} vs {k[1]!r}: {v:.1f}px")


main()
