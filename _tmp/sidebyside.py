"""Stack OLD (baseline) and NEW (premium v2) final frames side by
side with labels, downscaled, into one comparison PNG.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt

old = mpimg.imread("_tmp/preview_old.png")
new = mpimg.imread("_tmp/preview_new.png")

fig, axes = plt.subplots(1, 2, figsize=(9, 16), dpi=90)
for ax, img, title in [
    (axes[0], old, "OLD (baseline)"),
    (axes[1], new, "NEW (premium v2)"),
]:
    ax.imshow(img)
    ax.set_title(title, fontsize=16, color="white",
                 backgroundcolor="black", pad=8)
    ax.axis("off")
fig.patch.set_facecolor("black")
plt.tight_layout()
plt.savefig("_tmp/compare.png", dpi=90, facecolor="black")
print("SAVED _tmp/compare.png")
