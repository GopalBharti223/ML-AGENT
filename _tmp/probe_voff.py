"""Confirm the flag vertical-offset helper measures a real offset."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from app.visuals.scene_engine import VisualEngine

countries = ["Ireland", "Turks and Caicos Islands", "Georgia", "Guyana"]
max_val = 10.62
fig = plt.figure(figsize=(10.8, 19.2), dpi=100)
ax = fig.add_axes([
    VisualEngine.CHART_LEFT,
    VisualEngine.CHART_BOTTOM,
    VisualEngine.CHART_WIDTH,
    VisualEngine.CHART_HEIGHT,
])
ax.set_xlim(0, max_val)
ax.set_ylim(-0.5 - 0.0, 3.5 + 0.0)
ax.invert_yaxis()

name_x0_px = (
    VisualEngine.CHART_LEFT * 1080.0
    + float(VisualEngine._FLAG_SIZE[0]) * VisualEngine.FLAG_ZOOM
    + 8.3 + 6.0
)
name_x_data = max_val * ((name_x0_px - VisualEngine.CHART_LEFT * 1080.0)
                         / (VisualEngine.CHART_WIDTH * 1080.0))

texts = [
    ax.text(name_x_data, i, c, va="bottom", ha="left",
            fontsize=34.0, fontweight="bold", clip_on=False)
    for i, c in enumerate(countries)
]
fig.canvas.draw()
r = fig.canvas.get_renderer()
for t in texts:
    b = t.get_window_extent(renderer=r)
    print(f"  {t.get_text():26s} y0={b.y0:7.1f} y1={b.y1:7.1f} "
          f"ycen={(b.y0+b.y1)/2:7.1f}")

offs = VisualEngine._flag_vertical_offsets(ax, fig, texts, [34.0] * 4)
print("offsets:", offs)

# Reproduce the inner loop with the exception surfaced.
import traceback
renderer = fig.canvas.get_renderer()
invert = ax.transData.inverted()
for i, t in enumerate(texts):
    try:
        t.set_fontsize(34.0)
        fig.canvas.draw()
        extent = t.get_window_extent(renderer=renderer)
        _, yb = invert.transform((0.0, extent.y0))
        _, yc = invert.transform((0.0, (extent.y0 + extent.y1) / 2.0))
        print(f"  row {i}: yb={yb} yc={yc} off={yc - yb}")
    except Exception:
        traceback.print_exc()
        break
