import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt

new = mpimg.imread("_tmp/preview_new.png")
h, w = new.shape[:2]
print("new size", w, h)

# Top band (title/year/source) and the Turks row.
fig, axes = plt.subplots(2, 1, figsize=(6, 12), dpi=110)
axes[0].imshow(new[0:int(h*0.20), :])   # top 20%
axes[0].set_title("TOP: title / year / source", fontsize=12)
axes[0].axis("off")
axes[1].imshow(new[int(h*0.30):int(h*0.62), :])  # label rows
axes[1].set_title("LABEL ROWS (incl. Turks and Caicos)", fontsize=12)
axes[1].axis("off")
fig.patch.set_facecolor("black")
plt.tight_layout()
plt.savefig("_tmp/new_zoom.png", dpi=110, facecolor="black")
print("SAVED _tmp/new_zoom.png")
