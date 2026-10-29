"""Widescreen (16:9 Landscape) 1920x1080 Data Visualization Engine with Duel Battle Mode.

Features:
- Full 1920x1080 HD resolution at 30 FPS.
- Smooth cubic spline interpolation across years/timepoints.
- Always-On Duel Battle HUD scoreboard with dynamic status pills (Chasing, Closing, Threat, Overtake).
- Topic-Aware Dynamic Thematic Palettes (YouTube Red vs Cyan, Wealth Gold vs Emerald, Gaming Blue vs Lime).
- Champion (#1) vs Challenger (#2) high-contrast rival styling.
- Historic Lore News Ticker floating at bottom left.
- High-contrast, glowing luxury year counter at bottom right.
- Cinematic Outro / End-Screen Card with Champion Announcement & Subscribe CTA.
- High-performance MP4 rendering via Matplotlib FFMpegWriter.
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

# Curated historic lore headlines for viral datasets
VIRAL_LORE_HEADLINES: Dict[str, Dict[int, str]] = {
    "gta_sales": {
        2002: "GTA: Vice City releases, selling 8.5M copies in its debut year",
        2004: "GTA: San Andreas launches on PS2, setting historic sales records",
        2008: "GTA IV introduces high-definition Liberty City to next-gen consoles",
        2013: "GTA V launches: Generates $800M in first 24 hours ($1B in 3 days)",
        2018: "GTA Online updates drive unprecedented multi-year engagement surge",
        2021: "GTA V crosses 155M units, cementing its place as entertainment titan",
        2024: "GTA franchise crosses 430M total copies sold worldwide",
    },
    "top_billionaires_net_worth": {
        2014: "Bill Gates leads global wealth rankings at $76 Billion",
        2018: "Jeff Bezos becomes world's first $100B+ centibillionaire in history",
        2020: "Tech rally during pandemic accelerates billionaire fortunes worldwide",
        2021: "Elon Musk surges past Bezos following historic Tesla stock split",
        2023: "Bernard Arnault claims #1 spot as luxury titan LVMH reaches record highs",
        2024: "Elon Musk reclaims top spot with AI and tech market resurgence",
        2026: "Elon Musk valuation approaches historic $350 Billion threshold",
    },
    "youtube_subscribers_race": {
        2011: "RayWilliamJohnson dominates early YouTube with '=3', crossing 5M subscribers",
        2012: "Smosh and RayWilliamJohnson battle neck-to-neck for the #1 crown",
        2013: "PewDiePie surges past Smosh, claiming the throne as YouTube gaming explodes",
        2015: "PewDiePie cements global dominance, becoming first creator to hit 40M subs",
        2017: "India's digital explosion begins; T-Series rapidly closes the global gap",
        2018: "The Legendary War: PewDiePie vs T-Series captivates global internet audiences",
        2019: "Historic Milestone: T-Series becomes first channel to reach 100M subscribers",
        2020: "Cocomelon and regional entertainment channels experience record lockdown surge",
        2022: "MrBeast reaches 100M subscribers with viral high-stakes mega productions",
        2024: "Historic Overtake: MrBeast officially surpasses T-Series for all-time #1",
        2026: "MrBeast shatters records past 385 Million subscribers, rewriting history",
    },
    "streaming_wars_race": {
        2012: "Netflix gambles on streaming & originals, launching 'House of Cards' globally",
        2014: "Netflix reaches 50M global subscribers as traditional DVD rentals fade away",
        2016: "'Stranger Things' becomes a global phenomenon across 190 countries",
        2018: "Netflix crosses 130M subscribers as Hollywood studios prepare direct competition",
        2019: "Disney+ launches with 'The Mandalorian', signing 26.5M subscribers in 60 days",
        2020: "Global lockdowns trigger historic streaming boom; Disney+ surges past 70M",
        2021: "'Squid Game' becomes the most-watched television series launch in history",
        2022: "Disney+ crosses 160M, closing within striking distance of Netflix",
        2023: "Netflix password crackdown & ad-supported tier trigger massive subscriber surge",
        2024: "Netflix widens lead, smashing past 280M subscribers as rivals struggle with profits",
        2026: "Netflix crowned undisputed all-time King of Streaming, crossing 305 Million",
    },
    "ai_models_race": {
        2021: "Pre-LLM Era: Early NLP research and GPT-3 APIs set the foundation for generative AI",
        2022: "ChatGPT launches on Nov 30, becoming fastest consumer app to cross 100M users",
        2023: "The AI Gold Rush: Google launches Bard, Anthropic unveils Claude, Meta open-sources Llama",
        2024: "Google rebrands to Gemini, Claude 3.5 Sonnet leads coding, Groq shatters inference speeds",
        2025: "Reasoning models emerge with OpenAI o1/o3 and DeepSeek R1 challenging frontier labs",
        2026: "ChatGPT crosses 480 Million active users, reigning as the undisputed AI super-app",
    },
    "most_played_games_mau": {
        2018: "Minecraft and Fortnite battle for the top spot among global gamers",
        2020: "Roblox surges past 150M active players during global lockdowns",
        2022: "Roblox developer economy surpasses $500M annual payouts",
        2024: "Roblox hits 350 Million monthly active users, dominating the market",
    },
    "all_time_gaming_consoles": {
        2005: "PlayStation 2 dominates global gaming living rooms with 100M+ units",
        2010: "Nintendo DS and Wii capture mainstream casual players worldwide",
        2016: "PlayStation 4 crosses 50M units, winning 8th-gen console race",
        2020: "Nintendo Switch accelerates with Animal Crossing during lockdowns",
        2024: "Nintendo Switch crosses 143 Million units, closing in on PS2 record",
    },
    "world_population_giants": {
        1970: "China crosses 800M population as Asia drives global demographics",
        1990: "India crosses 870 Million as global population approaches 5.3 Billion",
        2000: "India crosses 1 Billion population milestone",
        2023: "Historic global milestone: India officially surpasses China in population",
    },
    "tesla_vs_byd_ev_sales": {
        2018: "Tesla Model 3 mass production hell conquered; global EV revolution begins",
        2021: "Tesla delivers nearly 1 Million EVs as Shanghai Gigafactory reaches full capacity",
        2023: "China EV surge: BYD delivers 1.57 Million EVs, breathing down Tesla's neck",
        2024: "Xiaomi enters the arena with SU7 EV; BYD and Tesla trade global quarterly crowns",
        2026: "BYD crosses 2.2 Million annual EV deliveries, solidifying China's global EV leadership",
    },
    "top_companies_market_cap": {
        2018: "Apple becomes the first public company in history to reach $1 Trillion valuation",
        2020: "Apple breaches $2 Trillion as tech giants soar during global remote-work era",
        2022: "Tech valuations recalibrate amidst rising interest rates and inflation",
        2023: "Generative AI boom begins: NVIDIA datacenter GPU demand ignites historic rally",
        2024: "Historic milestone: NVIDIA crosses $3.4 Trillion, briefly eclipsing Apple and Microsoft",
        2026: "The $3.75 Trillion Throne: NVIDIA and Apple battle for the title of world's most valuable company",
    },
    "programming_languages_race": {
        1995: "C and C++ rule enterprise software while Java and JavaScript make their debut",
        2000: "Java dominates enterprise systems, powering the early web and server applications",
        2008: "Python begins steady climb in scientific computing and academia",
        2015: "JavaScript expands beyond the browser with Node.js and modern frontend frameworks",
        2020: "The AI Revolution ignites Python explosive surge past Java and C++",
        2024: "Python claims undisputed #1 crown with 35%+ share driven by AI and data science",
        2026: "Python reigns supreme as global AI standard, while TypeScript and Rust rise rapidly",
    },
    "browser_wars_race": {
        1996: "Netscape Navigator commands 80% of the early World Wide Web",
        1999: "Microsoft bundles Internet Explorer into Windows, igniting First Browser War",
        2002: "Internet Explorer hits unprecedented 95% market monopoly",
        2008: "Google unveils Chrome with blazing V8 engine; Firefox challenges IE dominance",
        2012: "Historic flip: Google Chrome overtakes Internet Explorer as global #1 browser",
        2017: "Chrome cements global dominance, crossing 60% share across desktop and mobile",
        2026: "Chrome reigns with 66% share, while Apple Safari and Microsoft Edge battle for #2",
    },
    "mobile_os_market_share": {
        2006: "Nokia Symbian dominates early smartphones with 67% global market share",
        2008: "Apple launches App Store for iPhone; Google introduces first commercial Android device",
        2010: "Android sales explode globally across HTC, Motorola, and Samsung devices",
        2012: "Android overtakes all legacy platforms, capturing nearly 70% of global smartphone OS",
        2016: "Duopoly era arrives: Android and iOS wipe out Symbian, BlackBerry, and Windows Phone",
        2024: "Android holds ~80% global market share, while iOS commands premium high-value users",
        2026: "Mobile OS Duopoly undisputed: Android leads world volume while Apple leads profits",
    },
    "fastest_apps_100m_users": {
        2015: "Instagram and WhatsApp rewrite consumer adoption speed records",
        2018: "TikTok explodes worldwide, reaching 100M users in just 9 months",
        2022: "ChatGPT detonates AI revolution, reaching 100M users in a blistering 60 days",
        2023: "Meta Threads breaks all human records, crossing 100M signups in just 5 days",
        2026: "ChatGPT crosses 480 Million users as AI applications become universal utilities",
    },
}

# Thematic Color Palettes based on topic category
TOPIC_THEMES = {
    "ai": {
        "hero": "#10A37F",       # OpenAI ChatGPT Emerald Green
        "rival": "#8B5CF6",      # Google Gemini Vivid Violet / Purple
        "accent": "#06B6D4",     # Cyber Cyan Glow
        "hud_border": "#10A37F", # Glowing Emerald HUD
    },
    "coding": {
        "hero": "#38BDF8",       # Python / Developer Cyan Blue
        "rival": "#FBBF24",      # JavaScript / Java Radiant Gold
        "accent": "#A855F7",     # Rust / C++ Neon Purple
        "hud_border": "#38BDF8", # Glowing Dev HUD
    },
    "browser": {
        "hero": "#3B82F6",       # Google Chrome Electric Blue
        "rival": "#F97316",      # Mozilla Firefox Flame Orange
        "accent": "#10B981",     # Safari Emerald
        "hud_border": "#3B82F6", # Browser Glow
    },
    "mobile_os": {
        "hero": "#22C55E",       # Android Cyber Green
        "rival": "#E2E8F0",       # Apple iOS Titanium Platinum
        "accent": "#38BDF8",     # Cyan Accent
        "hud_border": "#22C55E", # Android Neon Glow
    },
    "ev": {
        "hero": "#EF4444",       # Tesla Cyber Red
        "rival": "#0284C7",      # BYD Electric Blue
        "accent": "#10B981",     # Xiaomi SU7 Clean Mint
        "hud_border": "#EF4444", # Turbo Red Border
    },
    "streaming": {
        "hero": "#E50914",       # Iconic Netflix Signature Red
        "rival": "#1D4ED8",      # Disney+ Electric Deep Blue
        "accent": "#FF2A36",     # Neon Red Glow Accent
        "hud_border": "#E50914", # Glowing Netflix Border
    },
    "youtube": {
        "hero": "#38BDF8",       # Electric Cyan (PewDiePie / MrBeast vibe)
        "rival": "#EF4444",      # Vivid YouTube Crimson / Red (T-Series vibe)
        "accent": "#F43F5E",
        "hud_border": "#38BDF8",
    },
    "wealth": {
        "hero": "#FBBF24",       # Luxury Gold
        "rival": "#10B981",      # Wall Street Emerald Green / NVIDIA Green
        "accent": "#D4AF37",
        "hud_border": "#FBBF24",
    },
    "gaming": {
        "hero": "#3B82F6",       # PlayStation / Cyber Blue
        "rival": "#84CC16",      # Xbox / Acid Lime Green
        "accent": "#A855F7",
        "hud_border": "#3B82F6",
    },
    "sports": {
        "hero": "#E11D48",       # Crimson Gold
        "rival": "#38BDF8",      # Sky Blue
        "accent": "#FBBF24",
        "hud_border": "#E11D48",
    },
    "default": {
        "hero": "#38BDF8",
        "rival": "#F87171",
        "accent": "#D4AF37",
        "hud_border": "#38BDF8",
    },
}


def get_topic_theme(indicator_code: str = "", title: str = "") -> Dict[str, str]:
    """Select appropriate high-contrast color scheme for the given topic."""
    txt = f"{indicator_code} {title}".lower()
    if any(k in txt for k in ["ai", "chatgpt", "gemini", "claude", "groq", "openai", "llama", "deepseek"]):
        return TOPIC_THEMES["ai"]
    if any(k in txt for k in ["programming", "coding", "python", "javascript", "java", "c++", "rust", "developer"]):
        return TOPIC_THEMES["coding"]
    if any(k in txt for k in ["browser", "chrome", "firefox", "safari", "edge", "netscape", "opera"]):
        return TOPIC_THEMES["browser"]
    if any(k in txt for k in ["mobile_os", "android", "symbian", "blackberry", "phone os"]):
        return TOPIC_THEMES["mobile_os"]
    if any(k in txt for k in ["ev", "electric car", "tesla", "byd", "xiaomi su7", "rivian"]):
        return TOPIC_THEMES["ev"]
    if any(k in txt for k in ["streaming", "netflix", "disney", "prime_video", "hbo"]):
        return TOPIC_THEMES["streaming"]
    if any(k in txt for k in ["youtube", "subscriber", "mrbeast", "pewdiepie", "t-series"]):
        return TOPIC_THEMES["youtube"]
    if any(k in txt for k in ["billionaire", "wealth", "net_worth", "market_cap", "company", "trillion", "nvidia"]):
        return TOPIC_THEMES["wealth"]
    if any(k in txt for k in ["game", "gta", "minecraft", "roblox", "console", "playstation", "xbox"]):
        return TOPIC_THEMES["gaming"]
    if any(k in txt for k in ["football", "cricket", "goal", "ronaldo", "messi", "run", "sport"]):
        return TOPIC_THEMES["sports"]
    return TOPIC_THEMES["default"]


def format_metric_val(val: float, indicator_code: str = "") -> str:
    """Format numeric values according to topic unit (Trillions, %, Billions, Millions, or raw count)."""
    code = (indicator_code or "").lower()
    if "market_cap" in code or "trillion" in code:
        return f"${val:.2f}T"
    if any(k in code for k in ["share", "percent", "language", "browser", "mobile_os"]):
        return f"{val:.1f}%"
    if "ev_sales" in code or "deliveries" in code:
        if val >= 1000:
            return f"{val/1000:.2f}M"
        return f"{val:.0f}K"
    if "net_worth" in code or "billionaire" in code:
        return f"${val:.1f}B"
    if "box_office" in code:
        return f"${val:.2f}B"
    if "goals" in code or "runs" in code:
        return f"{val:,.0f}"
    if "population" in code:
        if val >= 1000:
            return f"{val/1000:.2f}B"
        return f"{val:,.0f}M"
    # Default for subscribers, copies, users in Millions:
    if val >= 1000:
        return f"{val:,.0f}M"
    return f"{val:,.1f}M" if val < 100 else f"{val:,.0f}M"


def format_gap_val(gap_val: float, indicator_code: str = "") -> str:
    """Format gap difference between leader and rival."""
    code = (indicator_code or "").lower()
    if "market_cap" in code or "trillion" in code:
        return f"${gap_val:.2f}T"
    if any(k in code for k in ["share", "percent", "language", "browser", "mobile_os"]):
        return f"{gap_val:.1f}%"
    if "ev_sales" in code or "deliveries" in code:
        if gap_val >= 1000:
            return f"{gap_val/1000:.2f}M"
        return f"{gap_val:.0f}K"
    if "net_worth" in code or "billionaire" in code:
        return f"${gap_val:.1f}B"
    if "goals" in code or "runs" in code:
        return f"{gap_val:,.0f}"
    if gap_val >= 1000:
        return f"{gap_val:,.0f}M"
    return f"{gap_val:,.1f}M" if gap_val < 100 else f"{gap_val:,.0f}M"


class WidescreenDuelEngine:
    """Renders 1920x1080 widescreen landscape animations with Duel Mode."""

    CANVAS_WIDTH = 1920
    CANVAS_HEIGHT = 1080
    DPI = 100
    DEFAULT_FPS = 30
    NUM_BARS_DISPLAYED = 10

    @classmethod
    def render_landscape_animation(
        cls,
        wide_data: pd.DataFrame,
        output_file: str,
        title: str = "Global Milestone Race",
        category_label: str = "DATA LABS CINEMATIC // ALL-TIME RACE",
        duration_seconds: float = 85.0,
        fps: int = 30,
        indicator_code: str = "",
    ) -> str:
        """Renders complete 1920x1080 MP4 animation with Duel Mode."""
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

        # 1. Clean and validate wide data
        if wide_data.empty:
            raise ValueError("wide_data is empty for landscape render.")

        # Ensure years are sorted ascending
        years = sorted([c for c in wide_data.columns if str(c).isdigit()], key=lambda x: int(x))
        if len(years) < 2:
            years = sorted(list(wide_data.columns), key=lambda x: float(x))

        entities = list(wide_data.index)
        num_entities = len(entities)

        # 2. Build interpolation tables across total_frames
        total_frames = max(30, int(duration_seconds * fps))
        frame_years = np.linspace(float(years[0]), float(years[-1]), total_frames)

        # Precompute interpolated values for each entity at each frame
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
        fig = plt.figure(figsize=(19.2, 10.8), dpi=cls.DPI)
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

        # Bar layout coordinates: +50px left margin for long platform names
        bar_start_y = 800
        bar_h = 52
        bar_spacing = 70
        bar_x = 370
        bar_max_w = 1120

        # Outro configuration
        outro_duration_s = 4.5
        outro_start_frame = max(0, total_frames - int(outro_duration_s * fps))

        print(f"  [WIDESCREEN] Rendering (1920x1080) Animation: {total_frames} frames ({duration_seconds:.1f}s) ...")

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

                max_val = max(1.0, frame_vals[0][1] * 1.12)
                top_entities = frame_vals[: cls.NUM_BARS_DISPLAYED]

                leader_name, leader_val = top_entities[0]
                contender_name, contender_val = top_entities[1] if len(top_entities) > 1 else ("", 0.0)

                # Detect overtake
                if prev_leader is not None and leader_name != prev_leader:
                    overtake_flash_frames = 18  # Glow wave on lead change
                prev_leader = leader_name

                if overtake_flash_frames > 0:
                    overtake_flash_frames -= 1

                # Calculate Gap between #1 and #2
                gap_val = leader_val - contender_val
                gap_pct = (gap_val / max(leader_val, 1e-6)) if leader_val > 0 else 1.0

                # Always-On Duel Battle Mode
                is_duel = len(top_entities) >= 2

                # -------------------------------------------------
                # 1. Background Atmosphere & Grid
                # -------------------------------------------------
                ax.add_patch(patches.Rectangle((0, 0), cls.CANVAS_WIDTH, cls.CANVAS_HEIGHT, facecolor="#090D18", zorder=0))

                for gx in range(120, cls.CANVAS_WIDTH, 180):
                    ax.axvline(gx, color="#162238", linewidth=0.8, alpha=0.30, zorder=1)
                for gy in range(80, cls.CANVAS_HEIGHT, 120):
                    ax.axhline(gy, color="#162238", linewidth=0.8, alpha=0.30, zorder=1)

                # Ambient glow around battle center
                bloom_alpha = 0.16 if overtake_flash_frames > 0 else 0.07
                ax.add_patch(patches.Circle((960, 960), 300, facecolor=theme["hero"], alpha=bloom_alpha, zorder=1))

                # -------------------------------------------------
                # 2. Header (Top Left - Clean & Unobstructed)
                # -------------------------------------------------
                ax.text(60, 1025, category_label, fontsize=12, weight="bold", color="#D4AF37",
                        path_effects=[pe.withStroke(linewidth=2, foreground="#000000")], zorder=5)

                clean_title = title if len(title) <= 52 else (title[:49] + "...")
                ax.text(60, 985, clean_title, fontsize=24, weight="bold", color="#FFFFFF",
                        path_effects=[pe.withStroke(linewidth=3, foreground="#0A1122")], zorder=5)

                sub_status = f"Live Clash: {leader_name} vs {contender_name}" if is_duel else "Historical Performance Race"
                ax.text(60, 955, sub_status, fontsize=14, weight="bold", color="#94A3B8",
                        path_effects=[pe.withStroke(linewidth=2, foreground="#0A1122")], zorder=5)

                # -------------------------------------------------
                # 3. ⚔️ ALWAYS-ON DUEL BATTLE HUD (Top Right Corner)
                # -------------------------------------------------
                if is_duel:
                    hud_w, hud_h = 680, 105
                    hud_x, hud_y = 1860 - hud_w, 940

                    hud_border_color = "#FFFFFF" if overtake_flash_frames > 0 else theme["hud_border"]
                    hud_bg = patches.FancyBboxPatch(
                        (hud_x, hud_y), hud_w, hud_h,
                        boxstyle="round,pad=0,rounding_size=16",
                        facecolor="#0B1326", edgecolor=hud_border_color, linewidth=2.0,
                        alpha=0.96, zorder=6
                    )
                    ax.add_patch(hud_bg)

                    # Fighter 1 (Leader / Champion)
                    ax.text(hud_x + 30, hud_y + 65, leader_name.upper(), fontsize=15, weight="bold", color=theme["hero"], zorder=7)
                    ax.text(hud_x + 30, hud_y + 32, format_metric_val(leader_val, indicator_code), fontsize=15, weight="bold", color="#E2E8F0", zorder=7)
                    ax.text(hud_x + 30, hud_y + 12, "RANK #1 LEADER", fontsize=9.0, weight="bold", color="#34D399", zorder=7)

                    # VS Circle
                    vs_circle = patches.Circle((hud_x + hud_w / 2, hud_y + 52), 30, facecolor="#1E293B", edgecolor="#D4AF37", linewidth=2.0, zorder=7)
                    ax.add_patch(vs_circle)
                    ax.text(hud_x + hud_w / 2, hud_y + 45, "VS", fontsize=15, weight="bold", color="#F87171", ha="center", va="center", zorder=8)

                    # Fighter 2 (Contender / Challenger)
                    ax.text(hud_x + hud_w - 30, hud_y + 65, contender_name.upper(), fontsize=15, weight="bold", color=theme["rival"], ha="right", zorder=7)
                    ax.text(hud_x + hud_w - 30, hud_y + 32, format_metric_val(contender_val, indicator_code), fontsize=15, weight="bold", color="#E2E8F0", ha="right", zorder=7)
                    ax.text(hud_x + hud_w - 30, hud_y + 12, "RANK #2 CONTENDER", fontsize=9.0, weight="bold", color="#FB923C", ha="right", zorder=7)

                    # Dynamic Gap Indicator Pill
                    gap_fmt = format_gap_val(gap_val, indicator_code)
                    if overtake_flash_frames > 0:
                        gap_box_color = "#EF4444"
                        gap_border_color = "#FFFFFF"
                        gap_text_color = "#FFFFFF"
                        gap_label = f"★ OVERTAKE! NEW #1 [{leader_name.upper()}] ★"
                    elif gap_pct < 0.04:
                        gap_box_color = "#DC2626"
                        gap_border_color = "#FECACA"
                        gap_text_color = "#FFFFFF"
                        gap_label = f"GAP: {gap_fmt} [OVERTAKE THREAT!]"
                    elif gap_pct < 0.12:
                        gap_box_color = "#D97706"
                        gap_border_color = "#FEF3C7"
                        gap_text_color = "#000000"
                        gap_label = f"GAP: {gap_fmt} [CLOSING BATTLE]"
                    else:
                        gap_box_color = "#1E3A8A"
                        gap_border_color = "#93C5FD"
                        gap_text_color = "#FFFFFF"
                        gap_label = f"GAP: {gap_fmt} [CHASING LEADER]"

                    gap_box = patches.FancyBboxPatch(
                        (hud_x + hud_w / 2 - 140, hud_y - 20), 280, 26,
                        boxstyle="round,pad=0,rounding_size=8",
                        facecolor=gap_box_color,
                        edgecolor=gap_border_color, linewidth=1.4, zorder=9
                    )
                    ax.add_patch(gap_box)
                    ax.text(hud_x + hud_w / 2, hud_y - 9, gap_label,
                            fontsize=10.0, weight="bold", color=gap_text_color, ha="center", va="center", zorder=10)

                # -------------------------------------------------
                # 4. Bars (Ranked Top 10 with Rival High-Contrast)
                # -------------------------------------------------
                for i, (name, val) in enumerate(top_entities):
                    y = bar_start_y - (i * bar_spacing)
                    w = (val / max_val) * bar_max_w
                    w = max(15.0, w)

                    is_hero = (i == 0)
                    is_rival = (i == 1)

                    if is_hero:
                        color = theme["hero"]
                        edge_c = "#FFFFFF"
                        bar_alpha = 0.98
                        lw = 2.0
                    elif is_rival:
                        color = theme["rival"]
                        edge_c = "#FFD700" if overtake_flash_frames > 0 else "#FFFFFF"
                        bar_alpha = 0.92
                        lw = 1.6
                    else:
                        color = "#1E293B"
                        edge_c = "#334155"
                        bar_alpha = 0.70
                        lw = 0.8

                    # Rank number
                    ax.text(bar_x - 35, y + bar_h / 2, f"#{i+1}", fontsize=16, weight="bold",
                            color="#D4AF37" if is_hero else "#94A3B8", ha="right", va="center", zorder=5)

                    # Entity name
                    name_display = name if len(name) <= 22 else (name[:20] + "..")
                    name_color = "#FFFFFF" if (is_hero or is_rival) else "#94A3B8"
                    ax.text(bar_x - 85, y + bar_h / 2, name_display, fontsize=15, weight="bold",
                            color=name_color, ha="right", va="center", zorder=5)

                    # Dynamic glow around leader or overtake surge
                    if is_hero:
                        glow_border = "#FFFFFF" if overtake_flash_frames > 0 else color
                        aura = patches.FancyBboxPatch(
                            (bar_x - 4, y - 4), w + 8, bar_h + 8,
                            boxstyle="round,pad=0,rounding_size=14",
                            facecolor="none", edgecolor=glow_border, linewidth=2.6, alpha=0.90, zorder=3
                        )
                        ax.add_patch(aura)
                    elif is_rival and gap_pct < 0.08:
                        aura = patches.FancyBboxPatch(
                            (bar_x - 3, y - 3), w + 6, bar_h + 6,
                            boxstyle="round,pad=0,rounding_size=12",
                            facecolor="none", edgecolor=color, linewidth=1.8, alpha=0.80, zorder=3
                        )
                        ax.add_patch(aura)

                    # Main bar body
                    bar = patches.FancyBboxPatch(
                        (bar_x, y), w, bar_h,
                        boxstyle="round,pad=0,rounding_size=10",
                        facecolor=color,
                        edgecolor=edge_c,
                        linewidth=lw,
                        alpha=bar_alpha,
                        zorder=4
                    )
                    ax.add_patch(bar)

                    # Numeric value label
                    val_str = format_metric_val(val, indicator_code)
                    ax.text(bar_x + w + 18, y + bar_h / 2, val_str, fontsize=17, weight="bold",
                            color="#FFFFFF" if (is_hero or is_rival) else "#94A3B8", va="center", zorder=5)

                    # Leader / Contender dynamic badge
                    if is_hero:
                        badge_bg = patches.FancyBboxPatch(
                            (bar_x + w + 120, y + bar_h / 2 - 12), 140, 24,
                            boxstyle="round,pad=0,rounding_size=6",
                            facecolor="#D4AF37", edgecolor="none", alpha=0.95, zorder=5
                        )
                        ax.add_patch(badge_bg)
                        ax.text(bar_x + w + 190, y + bar_h / 2, "★ #1 LEADER", fontsize=9.5, weight="bold",
                                color="#000000", ha="center", va="center", zorder=6)
                    elif is_rival:
                        badge_bg = patches.FancyBboxPatch(
                            (bar_x + w + 120, y + bar_h / 2 - 12), 140, 24,
                            boxstyle="round,pad=0,rounding_size=6",
                            facecolor=theme["rival"], edgecolor="none", alpha=0.95, zorder=5
                        )
                        ax.add_patch(badge_bg)
                        ax.text(bar_x + w + 190, y + bar_h / 2, "CHALLENGER", fontsize=9.5, weight="bold",
                                color="#FFFFFF", ha="center", va="center", zorder=6)

                # -------------------------------------------------
                # 5. Historic Lore / News Ticker (Bottom Docked - Compact)
                # -------------------------------------------------
                if current_lore_text:
                    lore_w, lore_h = 950, 65
                    lore_x, lore_y = 60, 25

                    lore_bg = patches.FancyBboxPatch(
                        (lore_x, lore_y), lore_w, lore_h,
                        boxstyle="round,pad=0,rounding_size=10",
                        facecolor="#0B1326", edgecolor="#D4AF37", linewidth=1.4,
                        alpha=0.96, zorder=6
                    )
                    ax.add_patch(lore_bg)

                    ax.text(lore_x + 20, lore_y + 42, f"BREAKING HISTORIC EVENT  //  YEAR {current_lore_year}",
                            fontsize=9.5, weight="bold", color="#D4AF37", zorder=7)

                    clean_lore = current_lore_text if len(current_lore_text) <= 90 else (current_lore_text[:87] + "...")
                    ax.text(lore_x + 20, lore_y + 18, clean_lore,
                            fontsize=12.5, weight="medium", color="#F1F5F9", zorder=7)

                # -------------------------------------------------
                # 6. Giant Luxury Year Counter (Bottom Right)
                # -------------------------------------------------
                ax.text(1840, 65, f"{current_year_int}", fontsize=72, weight="bold", color=theme["hero"], alpha=0.88,
                        ha="right", va="bottom", fontfamily="sans-serif",
                        path_effects=[pe.withStroke(linewidth=3, foreground="#0B1326")], zorder=6)

                ax.text(1840, 45, "TIMELINE MILESTONE", fontsize=11, weight="bold", color="#64748B",
                        ha="right", va="bottom", fontfamily="sans-serif", zorder=6)

                # -------------------------------------------------
                # 7. Cinematic Outro / End-Screen Card (Last 4.5s)
                # -------------------------------------------------
                if f >= outro_start_frame:
                    outro_prog = min(1.0, (f - outro_start_frame) / (fps * 0.7))
                    dim_mask = patches.Rectangle(
                        (0, 0), cls.CANVAS_WIDTH, cls.CANVAS_HEIGHT,
                        facecolor="#050811", alpha=0.88 * outro_prog, zorder=20
                    )
                    ax.add_patch(dim_mask)

                    card_w, card_h = 1120, 530
                    card_x, card_y = (cls.CANVAS_WIDTH - card_w) / 2, (cls.CANVAS_HEIGHT - card_h) / 2
                    outro_card = patches.FancyBboxPatch(
                        (card_x, card_y), card_w, card_h,
                        boxstyle="round,pad=0,rounding_size=24",
                        facecolor="#0B132B", edgecolor=theme.get("accent", "#38BDF8"), linewidth=3.0,
                        alpha=0.96 * outro_prog, zorder=21
                    )
                    ax.add_patch(outro_card)

                    # Champion announcement
                    ax.text(cls.CANVAS_WIDTH / 2, card_y + 450, "★ ALL-TIME CHAMPION ★",
                            fontsize=20, weight="bold", color="#FBBF24", ha="center", va="center",
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

                    champ_text = f"{leader_name.upper()}  —  {leader_val:,.1f} {unit_str}"
                    ax.text(cls.CANVAS_WIDTH / 2, card_y + 388, champ_text,
                            fontsize=28, weight="bold", color="#FFFFFF", ha="center", va="center",
                            path_effects=[pe.withStroke(linewidth=3, foreground="#000000")], zorder=22)

                    # Separator line
                    ax.plot([card_x + 80, card_x + card_w - 80], [card_y + 330, card_y + 330],
                            color=theme["hero"], linewidth=2.0, alpha=0.7 * outro_prog, zorder=22)

                    # Channel Subscribe CTA
                    ax.text(cls.CANVAS_WIDTH / 2, card_y + 270, "★ SUBSCRIBE TO LR ATLAS ★",
                            fontsize=25, weight="bold", color="#F43F5E", ha="center", va="center",
                            path_effects=[pe.withStroke(linewidth=3, foreground="#000000")], zorder=22)

                    ax.text(cls.CANVAS_WIDTH / 2, card_y + 220, tagline,
                            fontsize=14, weight="bold", color="#94A3B8", ha="center", va="center", zorder=22)

                    # Viewer Engagement Question
                    ax.text(cls.CANVAS_WIDTH / 2, card_y + 150, comm_q,
                            fontsize=16, weight="bold", color="#E2E8F0", ha="center", va="center", zorder=22)

                    # Gratitude / Like & Share
                    ax.text(cls.CANVAS_WIDTH / 2, card_y + 78, "LIKE & SHARE  //  THANK YOU FOR WATCHING",
                            fontsize=15, weight="bold", color=theme["hero"], ha="center", va="center", zorder=22)

                # Grab frame
                writer.grab_frame()

        plt.close(fig)
        print(f"  [WIDESCREEN] Animation successfully saved to: {output_file}")
        return output_file
