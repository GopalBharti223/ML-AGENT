"""Measure whether name/value bounding boxes ACTUALLY overlap, frame by frame,
on the real pipeline for the tied-values scenario (wide spread, short bars)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.animation as manim
import matplotlib.pyplot as plt
import matplotlib.text as mtext
import pandas as pd
import app.visuals.scene_engine as se
from app.visuals.scene_engine import VisualEngine
from app.visuals import design_system

NAMES = [
    "Democratic Republic of the Congo",
    "Ireland",
    "Guyana",
    "Georgia",
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
                "highlight_countries": [NAMES[0]],
            }
        ]


def _overlaps(a, b):
    return not (a.x1 <= b.x0 or b.x1 <= a.x0 or a.y1 <= b.y0 or b.y1 <= a.y0)


def main():
    data = pd.DataFrame(
        {
            2018: [10e6, 10e6, 5e6, 8e6],
            2020: [20e6, 20e6, 12e6, 9e6],
            2022: [36.7e6, 36.7e6, 15e6, 12e6],
        },
        index=NAMES,
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
        # NOTE: do NOT iterate frames here; we drive them ourselves below.

    manim.Animation.save = isave
    plt.close = lambda *a, **k: None
    se.VisualEngine.prefetch_flags = classmethod(lambda cls, items: None)
    se.VisualEngine._get_flag_image = staticmethod(lambda name: None)
    try:
        se.VisualEngine.render_bar_race(_Script("bar_race"), data, "_tmp/probe_ov")
    finally:
        manim.Animation.save = os_save
        plt.close = os_close

    fig, fn, n = cap["fig"], cap["fn"], cap["n"]
    print("frames:", n)

    for step in (0, n // 2, n - 1):
        fn(step)
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
        ax = fig.axes[0]
        print(f"--- frame {step} ---")
        for t in ax.texts:
            c = t.get_text().strip()
            if not c:
                continue
            b = t.get_window_extent(renderer=r)
            print(f"  {c!r:20s} x0={b.x0:6.1f} x1={b.x1:6.1f} y0={b.y0:6.1f} y1={b.y1:6.1f} fs={t.get_fontsize()}")


main()
