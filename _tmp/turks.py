import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt

new = mpimg.imread("_tmp/preview_new.png")
h, w = new.shape[:2]
# Just the Turks and Caicos row (label + its value) — tight crop.
fig, ax = plt.subplots(1, 1, figsize=(11, 3), dpi=140)
ax.imshow(new[int(h*0.50):int(h*0.60), int(w*0.03):int(w*0.85)])
ax.set_title("Turks and Caicos Islands  +  its $7 value", fontsize=12)
ax.axis("off")
fig.patch.set_facecolor("black")
plt.tight_layout()
plt.savefig("_tmp/turks_zoom.png", dpi=140, facecolor="black")
print("SAVED")
