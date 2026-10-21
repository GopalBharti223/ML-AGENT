import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from app.visuals.scene_engine import VisualEngine

LONG = "Turks and Caicos Islands"
COUNTRIES = ["Ireland", LONG, "Georgia", "Guyana"]
max_val = 131338 * 1.18

plt.rcParams["figure.facecolor"] = VisualEngine.BG_COLOR
plt.rcParams["axes.facecolor"] = VisualEngine.BG_COLOR
plt.rcParams["text.color"] = VisualEngine.TEXT_COLOR
plt.rcParams["font.family"] = "DejaVu Sans"

fig = plt.figure(figsize=(10.8, 19.2), dpi=100)
ax = fig.add_axes([
    VisualEngine.CHART_LEFT,
    VisualEngine.CHART_BOTTOM,
    VisualEngine.CHART_WIDTH,
    VisualEngine.CHART_HEIGHT,
])
print("CHART frame:", VisualEngine.CHART_LEFT, VisualEngine.CHART_BOTTOM,
      VisualEngine.CHART_WIDTH, VisualEngine.CHART_HEIGHT)
n = len(COUNTRIES)
ax.set_xlim(0, max_val)
ax.set_ylim(-0.5, n - 0.5)
ax.invert_yaxis()

texts = [
    ax.text(-max_val * 0.055, i, c, va="center", ha="right",
            color=VisualEngine.TEXT_COLOR,
            fontsize=VisualEngine.COUNTRY_FONT_SIZE,
            fontweight="bold", clip_on=False)
    for i, c in enumerate(COUNTRIES)
]

bases = VisualEngine._fit_labels_in_frame(
    fig, ax, texts, font_bump=VisualEngine.LABEL_FONT_BUMP,
)
print("base_font:", VisualEngine.COUNTRY_FONT_SIZE)
print("fitted bases:", bases)

fig.canvas.draw()
r = fig.canvas.get_renderer()
for bump in range(VisualEngine.LABEL_FONT_BUMP + 1):
    for t, b in zip(texts, bases):
        t.set_fontsize(b + bump)
    fig.canvas.draw()
    for t in texts:
        x0 = t.get_window_extent(renderer=r).x0
        print(f"bump+{bump} {t.get_text()[:20]!r}: x0={x0:.1f}")
plt.close(fig)
