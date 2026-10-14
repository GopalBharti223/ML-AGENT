import contextlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.text as mtext
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
    title = "GDP per capita"
    source_name = "World Bank"
    indicator_name = "GDP per capita (current US$)"
    total_duration = 6.0


def run():
    years = sorted(RANKS)
    data = pd.DataFrame(
        {y: [float(10 - RANKS[y][c]) for c in COUNTRIES] for y in years},
        index=COUNTRIES,
    )
    cap = {}
    os_save = se.animation.Animation.save
    se.VisualEngine.prefetch_flags = classmethod(lambda cls, items: None)
    se.VisualEngine._get_flag_image = staticmethod(lambda name: None)

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
        se.VisualEngine.render_bar_race(_Script(), data, "_tmp/probe_out")
    finally:
        se.animation.Animation.save = os_save

    fig = cap["fig"]
    fn = cap["fn"]
    n = int(cap["n"])
    print("frames:", n)
    width = float(fig.get_figwidth()) * float(fig.dpi)
    height = float(fig.get_figheight()) * float(fig.dpi)
    print("W,H:", width, height)
    worst = {}
    long_fonts = set()
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    if not isinstance(fig.canvas, FigureCanvasAgg):
        FigureCanvasAgg(fig)
    for step in range(n):
        fn(step)
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
        for t in fig.findobj(mtext.Text):
            c = t.get_text()
            if c not in COUNTRIES:
                continue
            if t.get_alpha() is not None and float(t.get_alpha()) <= 0.01:
                continue
            box = t.get_window_extent(renderer=r)
            key = (c, step)
            x0, y0, x1, y1 = float(box.x0), float(box.y0), float(box.x1), float(box.y1)
            off = x0 < 0 or x1 > width or y0 < 0 or y1 > height
            if off:
                worst[key] = (round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))
            if c == LONG_LABEL:
                long_fonts.add(round(float(t.get_fontsize()), 2))
    print("OFF-FRAME count:", len(worst))
    for k, v in list(worst.items())[:20]:
        print("  OFF", k, v)
    print("LONG label fonts seen:", sorted(long_fonts))


run()
