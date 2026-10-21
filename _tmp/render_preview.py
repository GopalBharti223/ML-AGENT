"""Render a single final-frame PNG of render_bar_race so the new
PREMIUM UI v2 layout can be judged visually.

Uses the real renderer, real flags, and the exact REVERSAL dataset
(including the long 'Turks and Caicos Islands' label).  Saves the
FINAL frame to the given output path.
"""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.animation as manim
import matplotlib.pyplot as plt
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


def main(out_path):
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
        se.VisualEngine.render_bar_race(_Script(), data, "_tmp/preview")
    finally:
        manim.Animation.save = os_save
        plt.close = os_close

    fig = cap["fig"]
    fn = cap["fn"]
    n = int(cap["n"])
    fn(n - 1)  # final frame
    fig.canvas.draw()
    fig.savefig(out_path, dpi=100, facecolor=fig.get_facecolor())
    print("SAVED", out_path, "frames=", n)


if __name__ == "__main__":
    main(sys.argv[1])
