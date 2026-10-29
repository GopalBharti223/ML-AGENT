"""Vertical (9:16 Portrait) 1080x1920 Data Visualization Engine for YouTube Shorts & Reels.

Features:
- Full 1080x1920 HD mobile resolution at 30 FPS.
- YouTube Shorts UI Safe-Zone Aware (no collision with right-hand buttons or bottom channel overlay).
- Always-On Duel Battle Scoreboard HUD at top (Hero vs Rival with live scores, gap pill, and overtake alerts).
- Chunky, high-contrast mobile bars with circular monograms/logos and rank badges (#1 LEADER, CHALLENGER).
- Floating Historic Lore News Ticker.
- Centered Luxury Glowing Year Counter.
- Dynamic Topic-Aware Themes (Cyber AI, Netflix Red, YouTube Cyan, Wealth Gold, Gaming Blue).
- Cinematic Outro / End-Screen Card with Champion Announcement & Community CTA.
"""

import os
import math
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.patheffects as pe
from matplotlib.animation import FFMpegWriter

from app.visuals.widescreen_duel import VIRAL_LORE_HEADLINES, TOPIC_THEMES, get_topic_theme


class VerticalDuelEngine:
    """Renders 1080x1920 vertical portrait animations for YouTube Shorts."""

    CANVAS_WIDTH = 1080
    CANVAS_HEIGHT = 1920
    DPI = 100
    DEFAULT_FPS = 30
    NUM_BARS_DISPLAYED = 8  # 8 chunky, highly readable bars on mobile screens

    @classmethod
    def render_portrait_animation(
        cls,
        wide_data: pd.DataFrame,
        output_file: str,
        title: str = "Global Milestone Race",
        category_label: str = "LR ATLAS // VIRAL DATA LABS",
        duration_seconds: float = 35.0,
        fps: int = 30,
        indicator_code: str = "",
    ) -> str:
        """Renders complete 1080x1920 MP4 vertical animation for YouTube Shorts."""
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

        # 1. Clean and validate wide data
        if wide_data.empty:
            raise ValueError("wide_data is empty for portrait render.")

        # Ensure years are sorted ascending
        years = sorted([c for c in wide_data.columns if str(c).isdigit()], key=lambda x: int(x))
        if len(years) < 2:
            years = sorted(list(wide_data.columns), key=lambda x: float(x))

        entities = list(wide_data.index)
        num_entities = len(entities)

        # 2. Build interpolation tables across total_frames
        total_frames = max(30, int(duration_seconds * fps))
        frame_years = np.linspace(float(years[0]), float(years[-1]), total_frames)

        interp_matrix = np.zeros((num_entities, total_frames))
        for e_idx, entity in enumerate(entities):
            raw_vals = [float(wide_data.loc[entity, yr]) for yr in years]
            interp_matrix[e_idx, :] = np.interp(frame_years, [float(y) for y in years], raw_vals)

        # 3. Resolve topic theme
        theme = get_topic_theme(indicator_code, title)

        # 4. Resolve historic lore headlines
        lore_dict = VIRAL_LORE_HEADLINES.get(indicator_code, {})
        if not lore_dict:
            ent_str = " ".join([str(e).lower() for e in entities])
            if any(k in ent_str for k in ["mrbeast", "t-series", "pewdiepie"]):
                lore_dict = VIRAL_LORE_HEADLINES.get("youtube_subscribers_race", {})
            elif any(k in ent_str for k in ["chatgpt", "gemini", "claude", "groq"]):
                lore_dict = VIRAL_LORE_HEADLINES.get("ai_models_race", {})
            elif any(k in ent_str for k in ["netflix", "disney"]):
                lore_dict = VIRAL_LORE_HEADLINES.get("streaming_wars_race", {})
            elif any(k in ent_str for k in ["elon musk", "bezos"]):
                lore_dict = VIRAL_LORE_HEADLINES.get("top_billionaires_net_worth", {})
            elif any(k in ent_str for k in ["gta", "grand theft auto"]):
                lore_dict = VIRAL_LORE_HEADLINES.get("gta_sales", {})
            elif any(k in ent_str for k in ["roblox", "minecraft"]):
                lore_dict = VIRAL_LORE_HEADLINES.get("most_played_games_mau", {})
            elif any(k in ent_str for k in ["playstation", "nintendo"]):
                lore_dict = VIRAL_LORE_HEADLINES.get("all_time_gaming_consoles", {})
            elif any(k in ent_str for k in ["india", "china"]):
                lore_dict = VIRAL_LORE_HEADLINES.get("world_population_giants", {})

        # 5. Initialize Matplotlib figure & FFMpegWriter
        fig = plt.figure(figsize=(10.8, 19.2), dpi=cls.DPI)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, cls.CANVAS_WIDTH)
        ax.set_ylim(0, cls.CANVAS_HEIGHT)
        ax.axis("off")

        writer = FFMpegWriter(
            fps=fps,
            metadata=dict(title=title, artist="LR Atlas Data Labs"),
            extra_args=["-vcodec", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "fast"],
        )

        prev_leader = None
        overtake_flash_frames = 0
        current_lore_text = ""
        current_lore_year = 0

        # Vertical layout parameters:
        # Chunky mobile bars with safe margins for phone screens & YouTube Shorts UI
        bar_start_y = 1420
        bar_h = 66
        bar_spacing = 108
        bar_x = 330        # +45px safe margin on left for long names
        bar_max_w = 530    # Keeps bars completely clear of YouTube Shorts action buttons (x > 880)

        # Outro configuration
        outro_duration_s = 3.8
        outro_start_frame = max(0, total_frames - int(outro_duration_s * fps))

        print(f"  [SHORTS DUEL] Rendering (1080x1920) Vertical Animation: {total_frames} frames ({duration_seconds:.1f}s) ...")

        with writer.saving(fig, output_file, cls.DPI):
            for f in range(total_frames):
                ax.clear()
                ax.set_xlim(0, cls.CANVAS_WIDTH)
                ax.set_ylim(0, cls.CANVAS_HEIGHT)
                ax.axis("off")

                current_year_val = frame_years[f]
                current_year_int = int(current_year_val)

                # Check if a new historic lore headline applies
                for l_yr in sorted(lore_dict.keys()):
                    if current_year_int >= l_yr:
                        current_lore_text = lore_dict[l_yr]
                        current_lore_year = l_yr

                # Extract values for current frame and rank entities
                frame_vals = [(entities[e_idx], interp_matrix[e_idx, f]) for e_idx in range(num_entities)]
                frame_vals.sort(key=lambda x: x[1], reverse=True)

                max_val = max(1.0, frame_vals[0][1] * 1.15)
                top_entities = frame_vals[: cls.NUM_BARS_DISPLAYED]

                leader_name, leader_val = top_entities[0]
                contender_name, contender_val = top_entities[1] if len(top_entities) > 1 else ("", 0.0)

                # Detect overtake
                if prev_leader is not None and leader_name != prev_leader:
                    overtake_flash_frames = 18
                prev_leader = leader_name

                if overtake_flash_frames > 0:
                    overtake_flash_frames -= 1

                # Calculate Gap between #1 and #2
                gap_val = leader_val - contender_val
                gap_pct = (gap_val / max(leader_val, 1e-6)) if leader_val > 0 else 1.0

                is_duel = len(top_entities) >= 2

                # -------------------------------------------------
                # 1. Background Atmosphere & Ambient Cyber Grid
                # -------------------------------------------------
                ax.add_patch(patches.Rectangle((0, 0), cls.CANVAS_WIDTH, cls.CANVAS_HEIGHT, facecolor="#070B14", zorder=0))

                for gx in range(90, cls.CANVAS_WIDTH, 150):
                    ax.axvline(gx, color="#131F33", linewidth=0.8, alpha=0.35, zorder=1)
                for gy in range(100, cls.CANVAS_HEIGHT, 150):
                    ax.axhline(gy, color="#131F33", linewidth=0.8, alpha=0.35, zorder=1)

                # Dynamic ambient bloom in center
                bloom_alpha = 0.20 if overtake_flash_frames > 0 else 0.09
                ax.add_patch(patches.Circle((540, 1100), 380, facecolor=theme["hero"], alpha=bloom_alpha, zorder=1))

                # -------------------------------------------------
                # 2. Header (Top Centered - Mobile Optimized)
                # -------------------------------------------------
                ax.text(540, 1865, category_label, fontsize=13, weight="bold", color="#D4AF37", ha="center",
                        path_effects=[pe.withStroke(linewidth=2, foreground="#000000")], zorder=5)

                clean_title = title if len(title) <= 36 else (title[:34] + "..")
                ax.text(540, 1820, clean_title.upper(), fontsize=23, weight="bold", color="#FFFFFF", ha="center",
                        path_effects=[pe.withStroke(linewidth=3, foreground="#0A1122")], zorder=5)

                sub_status = f"LIVE CLASH: {leader_name.upper()} VS {contender_name.upper()}" if is_duel else "HISTORICAL MILESTONE RACE"
                clean_sub = sub_status if len(sub_status) <= 42 else (sub_status[:40] + "..")
                ax.text(540, 1782, clean_sub, fontsize=13.5, weight="bold", color="#94A3B8", ha="center",
                        path_effects=[pe.withStroke(linewidth=2, foreground="#0A1122")], zorder=5)

                # -------------------------------------------------
                # 3. ⚔️ MOBILE DUEL BATTLE HUD (Top Card)
                # -------------------------------------------------
                if is_duel:
                    hud_w, hud_h = 980, 155
                    hud_x, hud_y = (cls.CANVAS_WIDTH - hud_w) / 2, 1590

                    hud_border_color = "#FFFFFF" if overtake_flash_frames > 0 else theme["hud_border"]
                    hud_bg = patches.FancyBboxPatch(
                        (hud_x, hud_y), hud_w, hud_h,
                        boxstyle="round,pad=0,rounding_size=18",
                        facecolor="#0B1326", edgecolor=hud_border_color, linewidth=2.4,
                        alpha=0.97, zorder=6
                    )
                    ax.add_patch(hud_bg)

                    # Fighter 1 (Leader / Champion) - Left
                    f1_disp = leader_name if len(leader_name) <= 18 else (leader_name[:16] + "..")
                    ax.text(hud_x + 35, hud_y + 110, f1_disp.upper(), fontsize=18, weight="bold", color=theme["hero"], zorder=7)
                    ax.text(hud_x + 35, hud_y + 60, f"{leader_val:,.1f}", fontsize=28, weight="bold", color="#FFFFFF", zorder=7)
                    ax.text(hud_x + 35, hud_y + 24, "RANK #1 LEADER", fontsize=11.5, weight="bold", color="#34D399", zorder=7)

                    # VS Circle Badge - Center
                    vs_circle = patches.Circle((hud_x + hud_w / 2, hud_y + 78), 34, facecolor="#1E293B", edgecolor="#D4AF37", linewidth=2.4, zorder=7)
                    ax.add_patch(vs_circle)
                    ax.text(hud_x + hud_w / 2, hud_y + 73, "VS", fontsize=18, weight="bold", color="#F87171", ha="center", va="center", zorder=8)

                    # Fighter 2 (Contender / Challenger) - Right
                    f2_disp = contender_name if len(contender_name) <= 18 else (contender_name[:16] + "..")
                    ax.text(hud_x + hud_w - 35, hud_y + 110, f2_disp.upper(), fontsize=18, weight="bold", color=theme["rival"], ha="right", zorder=7)
                    ax.text(hud_x + hud_w - 35, hud_y + 60, f"{contender_val:,.1f}", fontsize=28, weight="bold", color="#FFFFFF", ha="right", zorder=7)
                    ax.text(hud_x + hud_w - 35, hud_y + 24, "CHALLENGER", fontsize=11.5, weight="bold", color="#FB923C", ha="right", zorder=7)

                    # Dynamic Gap Indicator Pill (Floating right below HUD)
                    if overtake_flash_frames > 0:
                        gap_box_color = "#EF4444"
                        gap_border_color = "#FFFFFF"
                        gap_text_color = "#FFFFFF"
                        gap_label = f"★ OVERTAKE! NEW #1 [{leader_name.upper()}] ★"
                    elif gap_pct < 0.05:
                        gap_box_color = "#DC2626"
                        gap_border_color = "#FECACA"
                        gap_text_color = "#FFFFFF"
                        gap_label = f"GAP: {gap_val:,.1f}M [OVERTAKE THREAT!]"
                    elif gap_pct < 0.15:
                        gap_box_color = "#D97706"
                        gap_border_color = "#FEF3C7"
                        gap_text_color = "#000000"
                        gap_label = f"GAP: {gap_val:,.1f}M [CLOSING BATTLE]"
                    else:
                        gap_box_color = "#1E3A8A"
                        gap_border_color = "#93C5FD"
                        gap_text_color = "#FFFFFF"
                        gap_label = f"GAP: {gap_val:,.1f}M [CHASING LEADER]"

                    gap_w = 380
                    gap_box = patches.FancyBboxPatch(
                        (540 - gap_w / 2, hud_y - 26), gap_w, 28,
                        boxstyle="round,pad=0,rounding_size=8",
                        facecolor=gap_box_color,
                        edgecolor=gap_border_color, linewidth=1.4, zorder=9
                    )
                    ax.add_patch(gap_box)
                    ax.text(540, hud_y - 13, gap_label,
                            fontsize=11.0, weight="bold", color=gap_text_color, ha="center", va="center", zorder=10)

                # -------------------------------------------------
                # 4. Chunky Mobile Bars (Top 8 Ranked)
                # -------------------------------------------------
                for i, (name, val) in enumerate(top_entities):
                    y = bar_start_y - (i * bar_spacing)
                    w = (val / max_val) * bar_max_w
                    w = max(68.0, w)

                    is_hero = (i == 0)
                    is_rival = (i == 1)

                    if is_hero:
                        color = theme["hero"]
                        edge_c = "#FFFFFF"
                        bar_alpha = 0.98
                        lw = 2.2
                    elif is_rival:
                        color = theme["rival"]
                        edge_c = "#FFD700" if overtake_flash_frames > 0 else "#FFFFFF"
                        bar_alpha = 0.92
                        lw = 1.8
                    else:
                        color = "#1E293B"
                        edge_c = "#334155"
                        bar_alpha = 0.72
                        lw = 0.9

                    # Rank number
                    ax.text(bar_x - 26, y + bar_h / 2, f"#{i+1}", fontsize=17, weight="bold",
                            color="#D4AF37" if is_hero else "#94A3B8", ha="right", va="center", zorder=5)

                    # Entity name
                    name_display = name if len(name) <= 18 else (name[:16] + "..")
                    name_color = "#FFFFFF" if (is_hero or is_rival) else "#94A3B8"
                    ax.text(bar_x - 65, y + bar_h / 2, name_display, fontsize=16.5, weight="bold",
                            color=name_color, ha="right", va="center", zorder=5)

                    # Glowing Aura on leader or close rival
                    if is_hero:
                        glow_border = "#FFFFFF" if overtake_flash_frames > 0 else color
                        aura = patches.FancyBboxPatch(
                            (bar_x - 5, y - 5), w + 10, bar_h + 10,
                            boxstyle="round,pad=0,rounding_size=16",
                            facecolor="none", edgecolor=glow_border, linewidth=2.8, alpha=0.90, zorder=3
                        )
                        ax.add_patch(aura)
                    elif is_rival and gap_pct < 0.08:
                        aura = patches.FancyBboxPatch(
                            (bar_x - 4, y - 4), w + 8, bar_h + 8,
                            boxstyle="round,pad=0,rounding_size=14",
                            facecolor="none", edgecolor=color, linewidth=2.0, alpha=0.80, zorder=3
                        )
                        ax.add_patch(aura)

                    # Main Bar Body
                    bar = patches.FancyBboxPatch(
                        (bar_x, y), w, bar_h,
                        boxstyle="round,pad=0,rounding_size=12",
                        facecolor=color,
                        edgecolor=edge_c,
                        linewidth=lw,
                        alpha=bar_alpha,
                        zorder=4
                    )
                    ax.add_patch(bar)

                    # Circular Monogram Badge on the bar head
                    icon_r = 21
                    icon_cx = bar_x + 30
                    icon_cy = y + bar_h / 2
                    icon_circle = patches.Circle((icon_cx, icon_cy), icon_r, facecolor="#0F172A", edgecolor=edge_c, linewidth=1.2, zorder=5)
                    ax.add_patch(icon_circle)

                    # First letter initial monogram (e.g. C for ChatGPT, G for Gemini)
                    monogram = name[0].upper() if name else "?"
                    ax.text(icon_cx, icon_cy, monogram, fontsize=14, weight="bold", color="#FFFFFF", ha="center", va="center", zorder=6)

                    # Numeric value label
                    val_str = f"{val:,.1f}M" if val < 1000 else f"{val:,.0f}M"
                    ax.text(bar_x + w + 16, y + bar_h / 2, val_str, fontsize=19, weight="bold",
                            color="#FFFFFF" if (is_hero or is_rival) else "#94A3B8", va="center", zorder=5)

                    # Leader / Challenger Badge
                    if is_hero:
                        badge_bg = patches.FancyBboxPatch(
                            (bar_x + w + 115, y + bar_h / 2 - 14), 125, 28,
                            boxstyle="round,pad=0,rounding_size=6",
                            facecolor="#D4AF37", edgecolor="none", alpha=0.95, zorder=5
                        )
                        ax.add_patch(badge_bg)
                        ax.text(bar_x + w + 177, y + bar_h / 2, "★ #1 LEADER", fontsize=10.0, weight="bold",
                                color="#000000", ha="center", va="center", zorder=6)
                    elif is_rival:
                        badge_bg = patches.FancyBboxPatch(
                            (bar_x + w + 115, y + bar_h / 2 - 14), 125, 28,
                            boxstyle="round,pad=0,rounding_size=6",
                            facecolor=theme["rival"], edgecolor="none", alpha=0.95, zorder=5
                        )
                        ax.add_patch(badge_bg)
                        ax.text(bar_x + w + 177, y + bar_h / 2, "CHALLENGER", fontsize=10.0, weight="bold",
                                color="#FFFFFF", ha="center", va="center", zorder=6)

                # -------------------------------------------------
                # 5. Historic Lore / News Ticker (Lower Mid)
                # -------------------------------------------------
                if current_lore_text:
                    lore_w, lore_h = 980, 85
                    lore_x, lore_y = (cls.CANVAS_WIDTH - lore_w) / 2, 510

                    lore_bg = patches.FancyBboxPatch(
                        (lore_x, lore_y), lore_w, lore_h,
                        boxstyle="round,pad=0,rounding_size=12",
                        facecolor="#0B1326", edgecolor="#D4AF37", linewidth=1.6,
                        alpha=0.96, zorder=6
                    )
                    ax.add_patch(lore_bg)

                    ax.text(lore_x + 24, lore_y + 54, f"★ BREAKING HISTORIC EVENT  //  YEAR {current_lore_year}",
                            fontsize=11.5, weight="bold", color="#D4AF37", zorder=7)

                    clean_lore = current_lore_text if len(current_lore_text) <= 68 else (current_lore_text[:65] + "...")
                    ax.text(lore_x + 24, lore_y + 24, clean_lore,
                            fontsize=14.5, weight="medium", color="#F1F5F9", zorder=7)

                # -------------------------------------------------
                # 6. Giant Luxury Centered Year Counter (Bottom Center)
                # -------------------------------------------------
                ax.text(540, 370, f"{current_year_int}", fontsize=96, weight="bold", color=theme["hero"], alpha=0.90,
                        ha="center", va="bottom", fontfamily="sans-serif",
                        path_effects=[pe.withStroke(linewidth=4, foreground="#0B1326")], zorder=6)

                ax.text(540, 345, "TIMELINE MILESTONE", fontsize=13, weight="bold", color="#64748B",
                        ha="center", va="bottom", fontfamily="sans-serif", zorder=6)

                # -------------------------------------------------
                # 7. Cinematic Outro Card (Last 3.8s)
                # -------------------------------------------------
                if f >= outro_start_frame:
                    outro_prog = min(1.0, (f - outro_start_frame) / (fps * 0.7))
                    dim_mask = patches.Rectangle(
                        (0, 0), cls.CANVAS_WIDTH, cls.CANVAS_HEIGHT,
                        facecolor="#050811", alpha=0.90 * outro_prog, zorder=20
                    )
                    ax.add_patch(dim_mask)

                    card_w, card_h = 980, 720
                    card_x, card_y = (cls.CANVAS_WIDTH - card_w) / 2, 600
                    outro_card = patches.FancyBboxPatch(
                        (card_x, card_y), card_w, card_h,
                        boxstyle="round,pad=0,rounding_size=26",
                        facecolor="#0B132B", edgecolor=theme.get("accent", "#38BDF8"), linewidth=3.2,
                        alpha=0.97 * outro_prog, zorder=21
                    )
                    ax.add_patch(outro_card)

                    # Champion announcement
                    ax.text(540, card_y + 630, "★ ALL-TIME CHAMPION ★",
                            fontsize=24, weight="bold", color="#FBBF24", ha="center", va="center",
                            path_effects=[pe.withStroke(linewidth=2, foreground="#000000")], zorder=22)

                    txt_topic = f"{indicator_code} {title}".lower()
                    if any(k in txt_topic for k in ["ai", "chatgpt", "gemini", "claude", "groq", "llm"]):
                        unit_str = "MILLION ACTIVE USERS"
                        tagline = "DAILY HIGH-STAKES DATA BATTLES & ARTIFICIAL INTELLIGENCE"
                        comm_q = "COMMUNITY: Which AI model is your daily favorite in 2026? Comment below!"
                    elif any(k in txt_topic for k in ["billionaire", "wealth", "net_worth"]):
                        unit_str = "BILLION DOLLARS NET WORTH"
                        tagline = "DAILY HIGH-STAKES DATA BATTLES & GLOBAL WEALTH"
                        comm_q = "COMMUNITY: Who built the greatest business empire? Comment below!"
                    elif any(k in txt_topic for k in ["streaming", "netflix", "disney"]):
                        unit_str = "MILLION SUBSCRIBERS"
                        tagline = "DAILY HIGH-STAKES DATA BATTLES & STREAMING WARS"
                        comm_q = "COMMUNITY: Which streaming service is your daily favorite? Comment below!"
                    elif any(k in txt_topic for k in ["youtube", "subscribers"]):
                        unit_str = "MILLION SUBSCRIBERS"
                        tagline = "DAILY HIGH-STAKES DATA BATTLES & YOUTUBE CREATORS"
                        comm_q = "COMMUNITY: Who had the greatest run in internet history? Comment below!"
                    else:
                        unit_str = "MILLION"
                        tagline = "DAILY HIGH-STAKES DATA BATTLES & HISTORIC RACES"
                        comm_q = "COMMUNITY: Who had the greatest run in history? Comment below!"

                    champ_text = f"{leader_name.upper()}\n{leader_val:,.1f} {unit_str}"
                    ax.text(540, card_y + 510, champ_text,
                            fontsize=28, weight="bold", color="#FFFFFF", ha="center", va="center",
                            path_effects=[pe.withStroke(linewidth=3, foreground="#000000")], zorder=22)

                    # Separator line
                    ax.plot([card_x + 60, card_x + card_w - 60], [card_y + 400, card_y + 400],
                            color=theme["hero"], linewidth=2.4, alpha=0.75 * outro_prog, zorder=22)

                    # Channel Subscribe CTA
                    ax.text(540, card_y + 320, "★ SUBSCRIBE TO LR ATLAS ★",
                            fontsize=28, weight="bold", color="#F43F5E", ha="center", va="center",
                            path_effects=[pe.withStroke(linewidth=3, foreground="#000000")], zorder=22)

                    ax.text(540, card_y + 245, tagline,
                            fontsize=14.5, weight="bold", color="#94A3B8", ha="center", va="center", zorder=22)

                    # Viewer Engagement Question
                    clean_comm_q = comm_q if len(comm_q) <= 48 else (comm_q[:46] + "..")
                    ax.text(540, card_y + 160, clean_comm_q,
                            fontsize=16.5, weight="bold", color="#E2E8F0", ha="center", va="center", zorder=22)

                    # Gratitude / Like & Share
                    ax.text(540, card_y + 75, "LIKE & SHARE  //  THANK YOU FOR WATCHING",
                            fontsize=16, weight="bold", color=theme["hero"], ha="center", va="center", zorder=22)

                # Grab frame
                writer.grab_frame()

        plt.close(fig)
        print(f"  [SHORTS DUEL] Vertical animation successfully saved to: {output_file}")
        return output_file
