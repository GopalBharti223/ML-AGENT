import contextlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.text as mtext
import pandas as pd
import app.visuals.scene_engine as se
from app.visuals.scene_engine import VisualEngine

# Use real flag-bearing countries.
COUNTRIES = ["Germany", "Japan", "Ireland", "Canada"]
YEARS = [2018, 2020, 2022]
RANKS = {
    2018: {"Germany": 4, "Japan": 3, "Ireland": 2, "Canada": 1},
    2020: {"Germany": 3, "Japan": 4, "Ireland": 1, "Canada": 2},
    2022: {"Germany": 2, "Japan": 1, "Ireland": 3, "Canada": 4},
}


class _Script:
    title = "GDP per capita"
    source_name = "World Bank"
    indicator_name = "GDP per capita (current US$)"
    total_duration = 6.0


def run():
    data = pd.DataFrame(
        {y: [float(10 - RANKS[y][c]) for c in COUNTRIES] for y in YEARS},
        index=COUNTRIES,
    )
    cap = {}
    os_save = se.animation.Animation.save
    # DO NOT stub flags -- use the real _get_flag_image.

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

    se.animation.Animation.save = isave
    try:
        se.VisualEngine._duration_override = 0.0
        se.VisualEngine.render_bar_race(_Script(), data, "_tmp/probe_flag_out")
    finally:
        se.animation.Animation.save = os_save

    fig = cap["fig"]
    fn = cap["fn"]
    n = int(cap["n"])
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    if not isinstance(fig.canvas, FigureCanvasAgg):
        FigureCanvasAgg(fig)
    # Look at final frame.
    fn(n - 1)
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    ax = fig.axes[0]
    # Map each country label to its window extent, and each flag box.
    labels = {}
    for t in ax.texts:
        if t.get_text() in COUNTRIES:
            labels[t.get_text()] = t.get_window_extent(renderer=r)
    # Flags are AnnotationBbox artists.
    from matplotlib.offsetbox import AnnotationBbox
    flag_boxes = [a for a in ax.artists if isinstance(a, AnnotationBbox)]
    print("num flags:", len(flag_boxes))
    for name, box in sorted(labels.items()):
        print(f"LABEL {name:10s}: x0={box.x0:7.1f} x1={box.x1:7.1f} y0={box.y0:7.1f} y1={box.y1:7.1f}")
    for fb in flag_boxes:
        ext = fb.get_window_extent(renderer=r)
        print(f"FLAG  box: x0={ext.x0:7.1f} x1={ext.x1:7.1f} y0={ext.y0:7.1f} y1={ext.y1:7.1f}")


run()
