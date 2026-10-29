"""Render a prototype 1920x1080 widescreen landscape frame with Duel Battle Mode."""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.patheffects as pe
import numpy as np

OUTPUT_PATH = r"C:\Users\gkb16\.gemini\antigravity-ide\brain\ca29c4ce-0c08-4fcc-b693-3829e24c5663\preview_widescreen_duel.png"
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

# 1920x1080 Canvas (16:9 Widescreen)
fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 1920)
ax.set_ylim(0, 1080)
ax.axis("off")

# 1. Background: Deep obsidian navy with subtle radial glow
ax.add_patch(patches.Rectangle((0, 0), 1920, 1080, facecolor="#090D18", zorder=0))

# Blueprint grid lines (subtle sci-fi aesthetic)
for x in range(100, 1920, 160):
    ax.axvline(x, color="#162238", linewidth=0.8, alpha=0.35, zorder=1)
for y in range(80, 1080, 120):
    ax.axhline(y, color="#162238", linewidth=0.8, alpha=0.35, zorder=1)

# Subtle ambient light bloom at top center (Battle focus)
for radius, alpha in [(300, 0.08), (200, 0.12), (100, 0.16)]:
    circle = patches.Circle((960, 960), radius, facecolor="#38BDF8", alpha=alpha, zorder=1)
    ax.add_patch(circle)

# 2. Header: Title & Category (Left aligned, compact & clean)
ax.text(60, 1025, "DATA LABS CINEMATIC  //  ALL-TIME MILESTONE RACE",
        fontsize=12, weight="bold", color="#D4AF37", fontfamily="sans-serif",
        path_effects=[pe.withStroke(linewidth=2, foreground="#000000")], zorder=5)

ax.text(60, 985, "YouTube Subscriber War",
        fontsize=24, weight="bold", color="#FFFFFF", fontfamily="sans-serif",
        path_effects=[pe.withStroke(linewidth=3, foreground="#0A1122")], zorder=5)

ax.text(60, 955, "Live Overtake Clash: MrBeast vs T-Series",
        fontsize=14, weight="bold", color="#94A3B8", fontfamily="sans-serif",
        path_effects=[pe.withStroke(linewidth=2, foreground="#0A1122")], zorder=5)

# 3. ⚔️ DUEL BATTLE HUD (Floating Top Center Card)
hud_w, hud_h = 760, 105
hud_x, hud_y = 1000 - hud_w / 2, 935

# HUD background container with dual-glow border
hud_bg = patches.FancyBboxPatch(
    (hud_x, hud_y), hud_w, hud_h,
    boxstyle="round,pad=0,rounding_size=16",
    facecolor="#0B1326", edgecolor="#38BDF8", linewidth=1.8,
    alpha=0.95, zorder=6
)
ax.add_patch(hud_bg)

# Fighter 1 (MrBeast - Blue)
ax.text(hud_x + 35, hud_y + 65, "MRBEAST", fontsize=17, weight="bold", color="#38BDF8", zorder=7)
ax.text(hud_x + 35, hud_y + 32, "330.4M SUBS", fontsize=15, weight="bold", color="#E2E8F0", zorder=7)
ax.text(hud_x + 35, hud_y + 12, "RANK #1  (+3.2M/mo)", fontsize=9.5, weight="bold", color="#34D399", zorder=7)

# VS Clash Icon in center
vs_circle = patches.Circle((hud_x + hud_w / 2, hud_y + 52), 32, facecolor="#1E293B", edgecolor="#D4AF37", linewidth=2.0, zorder=7)
ax.add_patch(vs_circle)
ax.text(hud_x + hud_w / 2, hud_y + 45, "VS", fontsize=16, weight="bold", color="#F87171", ha="center", va="center", zorder=8)

# Fighter 2 (T-Series - Red)
ax.text(hud_x + hud_w - 35, hud_y + 65, "T-SERIES", fontsize=17, weight="bold", color="#F87171", ha="right", zorder=7)
ax.text(hud_x + hud_w - 35, hud_y + 32, "330.1M SUBS", fontsize=15, weight="bold", color="#E2E8F0", ha="right", zorder=7)
ax.text(hud_x + hud_w - 35, hud_y + 12, "RANK #2  (+1.8M/mo)", fontsize=9.5, weight="bold", color="#94A3B8", ha="right", zorder=7)

# Live Gap Indicator inside HUD
gap_box = patches.FancyBboxPatch(
    (hud_x + hud_w / 2 - 140, hud_y - 20), 280, 26,
    boxstyle="round,pad=0,rounding_size=8",
    facecolor="#F59E0B", edgecolor="#FEF3C7", linewidth=1.2, zorder=9
)
ax.add_patch(gap_box)
ax.text(hud_x + hud_w / 2, hud_y - 9, "GAP: 312,000 SUBS [OVERTAKE!]",
        fontsize=10.5, weight="bold", color="#000000", ha="center", va="center", zorder=10)

# 4. Main Bars (Rank 1 to 8)
competitors = [
    ("MrBeast", 330.4, "#38BDF8", "#0284C7", "★ #1 LEADER", True),
    ("T-Series", 330.1, "#F87171", "#DC2626", "CHALLENGER", True),
    ("Cocomelon", 185.2, "#34D399", "#059669", None, False),
    ("SET India", 180.5, "#FB923C", "#EA580C", None, False),
    ("Kids Diana Show", 127.4, "#A78BFA", "#7C3AED", None, False),
    ("Like Nastya", 122.0, "#F472B6", "#DB2777", None, False),
    ("PewDiePie", 111.0, "#94A3B8", "#475569", "FORMER KING", False),
    ("Vlad and Niki", 108.6, "#38BDF8", "#0284C7", None, False),
]

bar_start_y = 800
bar_h = 58
bar_spacing = 76
max_val = 360.0
bar_max_w = 1180
bar_x = 320

for i, (name, val, c_primary, c_dark, badge, is_duel) in enumerate(competitors):
    y = bar_start_y - (i * bar_spacing)
    w = (val / max_val) * bar_max_w

    # Rank badge on left
    ax.text(bar_x - 35, y + bar_h / 2, f"#{i+1}", fontsize=17, weight="bold",
            color="#D4AF37" if i == 0 else "#94A3B8", ha="right", va="center", zorder=5)

    # Name label on left
    ax.text(bar_x - 85, y + bar_h / 2, name, fontsize=16, weight="bold",
            color="#FFFFFF" if is_duel else "#CBD5E1", ha="right", va="center", zorder=5)

    # Duel highlight aura
    if is_duel and i == 0:
        aura = patches.FancyBboxPatch(
            (bar_x - 4, y - 4), w + 8, bar_h + 8,
            boxstyle="round,pad=0,rounding_size=14",
            facecolor="none", edgecolor="#38BDF8", linewidth=2.5, alpha=0.8, zorder=3
        )
        ax.add_patch(aura)

    # Main bar with rounded corners
    bar = patches.FancyBboxPatch(
        (bar_x, y), w, bar_h,
        boxstyle="round,pad=0,rounding_size=10",
        facecolor=c_primary if is_duel else "#1E293B",
        edgecolor=c_primary if not is_duel else "#FFFFFF",
        linewidth=1.2 if is_duel else 0.8,
        alpha=0.92 if is_duel else 0.75,
        zorder=4
    )
    ax.add_patch(bar)

    # Value counter label (Right of bar)
    val_str = f"{val:.1f}M"
    ax.text(bar_x + w + 18, y + bar_h / 2, val_str, fontsize=18, weight="bold",
            color="#FFFFFF" if is_duel else "#94A3B8", va="center", zorder=5)

    # Optional dynamic badge
    if badge:
        badge_bg = patches.FancyBboxPatch(
            (bar_x + w + 115, y + bar_h / 2 - 12), 140, 24,
            boxstyle="round,pad=0,rounding_size=6",
            facecolor="#D4AF37" if "★" in badge else ("#DC2626" if "CHALLENGER" in badge else "#334155"),
            edgecolor="none", alpha=0.9, zorder=5
        )
        ax.add_patch(badge_bg)
        ax.text(bar_x + w + 185, y + bar_h / 2, badge, fontsize=9.5, weight="bold",
                color="#000000" if "★" in badge else "#FFFFFF", ha="center", va="center", zorder=6)

# 5. 📰 HISTORIC LORE / EVENT NEWS TICKER (Bottom Left Floating Card)
lore_w, lore_h = 1050, 75
lore_x, lore_y = 80, 50

lore_bg = patches.FancyBboxPatch(
    (lore_x, lore_y), lore_w, lore_h,
    boxstyle="round,pad=0,rounding_size=12",
    facecolor="#0F172A", edgecolor="#D4AF37", linewidth=1.5,
    alpha=0.95, zorder=6
)
ax.add_patch(lore_bg)

ax.text(lore_x + 25, lore_y + 48, "BREAKING HISTORIC EVENT  //  JUNE 2, 2024",
        fontsize=10.5, weight="heavy", color="#D4AF37", zorder=7)

ax.text(lore_x + 25, lore_y + 22,
        "MrBeast officially surpasses T-Series to claim the #1 most subscribed title on YouTube.",
        fontsize=14.5, weight="medium", color="#F1F5F9", zorder=7)

# 6. Giant Luxury Year Counter (Bottom Right)
ax.text(1840, 65, "2024", fontsize=74, weight="heavy", color="#38BDF8", alpha=0.88,
        ha="right", va="bottom", fontfamily="sans-serif",
        path_effects=[pe.withStroke(linewidth=3, foreground="#0B1326")], zorder=6)

ax.text(1840, 45, "ANNUAL SUBSCRIBER MILESTONE", fontsize=11, weight="bold", color="#64748B",
        ha="right", va="bottom", fontfamily="sans-serif", zorder=6)

# Save high-definition 1920x1080 frame
plt.savefig(OUTPUT_PATH, dpi=100, facecolor="#090D18", edgecolor="none")
plt.close(fig)
print(f"Frame rendered successfully to: {OUTPUT_PATH}")
