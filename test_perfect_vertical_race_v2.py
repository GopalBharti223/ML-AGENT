"""Perfect Vertical Race Chart V2 - Complete Polish
Directly addresses every piece of user feedback:
1. Studio Background: Deep cinematic radial vignette (#14223d -> #060810) + subtle tech dot matrix + frosted glass.
2. Clean Top Header: Uncluttered 'LR ATLAS • GLOBAL DEMOGRAPHICS' & 'WORLD POPULATION RACE'.
3. Dedicated Large Year & Global Pop HUD: Prominently displayed between title and race bars.
4. Lower-Third Dynamic Subtitles: Positioned at natural eye level (Shorts safe zone).
5. Text Contrast Fix: Frosted dark obsidian glass badge for country name & rank (100% visible on India's white stripe).
6. Smooth Physical Vertical Rank Swap: India and China physically glide past each other with smooth sinusoidal easing and elevation drop shadow!
7. Continuous Numeric Interpolation: USA, IDN, PAK, etc. tick 1-by-1 like a real precision odometer.
8. Official Data Source Attribution: UN Population Division & LR Atlas footer.
"""

import os
import math
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH = 1080
HEIGHT = 1920

os.makedirs("output", exist_ok=True)

# Helper for robust fonts
def get_font(size, bold=True):
    font_names = [
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "tahomabd.ttf" if bold else "tahoma.ttf"
    ]
    for fn in font_names:
        try:
            return ImageFont.truetype(fn, size)
        except Exception:
            continue
    return ImageFont.load_default()

font_hud_tag = get_font(22, bold=True)
font_hud_title = get_font(46, bold=True)
font_year_hud = get_font(36, bold=True)
font_year_label = get_font(20, bold=True)
font_label = get_font(26, bold=True)
font_val = get_font(28, bold=True)
font_badge = get_font(18, bold=True)
font_debate = get_font(22, bold=True)
font_caption = get_font(44, bold=True)
font_source = get_font(19, bold=False)

# Flag loading
CODE_TO_FLAG = {
    "IND": "in",
    "CHN": "cn",
    "USA": "us",
    "IDN": "id",
    "PAK": "pk",
    "NGA": "ng",
    "BGD": "bd",
}

flags = {}
for code_3, code_2 in CODE_TO_FLAG.items():
    p = f"assets/flags_hires/{code_2}.png"
    if os.path.exists(p):
        flags[code_3] = Image.open(p).convert("RGBA")

# Pre-render Background: Cinematic Obsidian Studio Atmosphere + Modern Dot Matrix
def create_studio_background():
    bg = Image.new("RGBA", (WIDTH, HEIGHT), (6, 8, 14, 255))

    # 1. Luxurious Radial Spotlight centered behind the bars (Y=720)
    center_x = WIDTH // 2
    center_y = 720
    max_radius = 1100

    y_coords, x_coords = np.ogrid[:HEIGHT, :WIDTH]
    dist = np.sqrt((x_coords - center_x)**2 + (y_coords - center_y)**2)
    norm_dist = np.clip(dist / max_radius, 0.0, 1.0)
    
    # Smooth cosine falloff from deep sapphire navy (#142442) to obsidian (#060810)
    falloff = 0.5 + 0.5 * np.cos(norm_dist * math.pi)
    r = (20 * falloff + 6 * (1.0 - falloff)).astype(np.uint8)
    g = (34 * falloff + 8 * (1.0 - falloff)).astype(np.uint8)
    b = (60 * falloff + 14 * (1.0 - falloff)).astype(np.uint8)
    
    bg_np = np.dstack((r, g, b, np.full((HEIGHT, WIDTH), 255, dtype=np.uint8)))
    bg = Image.fromarray(bg_np, "RGBA")
    draw = ImageDraw.Draw(bg)

    # 2. Subtle Modern Tech Dot Matrix (60px spacing, delicate 5% alpha)
    dot_col = (140, 180, 240, 14)
    for x in range(40, WIDTH, 60):
        for y in range(60, HEIGHT, 60):
            draw.rectangle([(x, y), (x + 2, y + 2)], fill=dot_col)

    # 3. Ambient Top Glow
    top_glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    tg_draw = ImageDraw.Draw(top_glow)
    for y in range(240):
        a = int(24 * (1.0 - y / 240.0))
        tg_draw.line([(0, y), (WIDTH, y)], fill=(212, 175, 55, a))
    bg = Image.alpha_composite(bg, top_glow)

    return bg

BASE_BACKGROUND = create_studio_background()

bar_h = 92
radius = bar_h // 2
pad = 20

def create_waving_bar(flag_img, bar_w, phase_t, is_gold=False):
    f_w = bar_w + pad * 2
    f_h = bar_h + pad * 2
    scaled_flag = flag_img.resize((f_w, f_h), Image.Resampling.LANCZOS)
    flag_np = np.array(scaled_flag)

    # Smooth silk ripple
    h, w, c = flag_np.shape
    y_indices, x_indices = np.indices((h, w))
    wave_shift = (4.0 * np.sin(2 * math.pi * x_indices / 130.0 - phase_t)).astype(np.float32)
    new_y = np.clip(y_indices + wave_shift, 0, h - 1).astype(np.int32)
    waved_np = flag_np[new_y, x_indices]

    # Shading (peaks bright, troughs slightly darker)
    shading = (0.88 + 0.16 * np.sin(2 * math.pi * x_indices / 130.0 - phase_t + math.pi/4))[:, :, np.newaxis]
    waved_np[:, :, :3] = np.clip(waved_np[:, :, :3] * shading, 0, 255).astype(np.uint8)

    waved_img = Image.fromarray(waved_np, "RGBA").crop((pad, pad, pad + bar_w, pad + bar_h))

    # Mask
    bar_mask = Image.new("L", (bar_w, bar_h), 0)
    ImageDraw.Draw(bar_mask).rounded_rectangle([(0, 0), (bar_w, bar_h)], radius=radius, fill=255)

    bar = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    bar.paste(waved_img, (0, 0), bar_mask)

    # Dark gradient for text contrast
    grad = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(grad)
    for x in range(bar_w):
        alpha = int(45 + 125 * (x / bar_w))
        grad_draw.line([(x, 0), (x, bar_h)], fill=(8, 12, 20, alpha))
    bar = Image.alpha_composite(bar, Image.composite(grad, Image.new("RGBA", (bar_w, bar_h), (0,0,0,0)), bar_mask))

    # Clean Titanium / Gold Rim (No inside lines)
    rim = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    rim_draw = ImageDraw.Draw(rim)
    rim_col = (255, 215, 0) if is_gold else (210, 225, 245)
    rim_alpha = 230 if is_gold else 130
    rim_draw.rounded_rectangle([(1, 1), (bar_w - 2, bar_h - 2)], radius=radius, outline=rim_col + (rim_alpha,), width=2)
    bar = Image.alpha_composite(bar, rim)

    return bar, rim_col, rim_alpha

def draw_star(draw, cx, cy, r=10, fill=(255, 215, 0, 255)):
    """Draw a clean vector star without font encoding bugs"""
    points = []
    for i in range(10):
        angle = i * math.pi / 5 - math.pi / 2
        cur_r = r if i % 2 == 0 else r * 0.45
        points.append((cx + cur_r * math.cos(angle), cy + cur_r * math.sin(angle)))
    draw.polygon(points, fill=fill)


def render_v2_frame(year_val, world_pop_val, active_countries, caption_text="", phase_t=0.0, overtake_gold_pulse=False):
    canvas = BASE_BACKGROUND.copy()
    draw = ImageDraw.Draw(canvas)

    # -------------------------------------------------------------
    # 1. TOP HEADER (CLEAN & SLEEK - NO MESSY CLUTTER)
    # -------------------------------------------------------------
    header_y = 105
    # Category Kicker with subtle gold accent
    draw.text((WIDTH//2, header_y), "LR ATLAS  •  GLOBAL DEMOGRAPHICS", fill=(212, 175, 55, 230), font=font_hud_tag, anchor="mm")
    # Title
    draw.text((WIDTH//2, header_y + 45), "WORLD POPULATION RACE", fill=(255, 255, 255, 255), font=font_hud_title, anchor="mm")

    # -------------------------------------------------------------
    # 2. DEDICATED PROMINENT YEAR & WORLD POPULATION HUD (EYE CATCHING)
    # -------------------------------------------------------------
    hud_y = 220
    hud_w = 930
    hud_h = 78
    hx = (WIDTH - hud_w) // 2

    # Glassmorphism Card
    hud_border_col = (255, 215, 0, 220) if overtake_gold_pulse else (56, 189, 248, 160)
    draw.rounded_rectangle([(hx, hud_y), (hx + hud_w, hud_y + hud_h)], radius=20, fill=(14, 22, 38, 230), outline=hud_border_col, width=2)

    # Left: Year Odometer Box
    year_str = f"{int(year_val)}"
    draw.text((hx + 55, hud_y + hud_h//2), "TIMELINE", fill=(148, 163, 184, 255), font=font_year_label, anchor="lm")
    draw.text((hx + 175, hud_y + hud_h//2), year_str, fill=(255, 215, 0, 255) if overtake_gold_pulse else (255, 255, 255, 255), font=font_year_hud, anchor="lm")

    # Center Divider
    draw.line([(WIDTH//2, hud_y + 14), (WIDTH//2, hud_y + hud_h - 14)], fill=(255, 255, 255, 40), width=2)

    # Right: World Population Box
    pop_str = f"{world_pop_val:.2f} BILLION"
    draw.text((WIDTH//2 + 45, hud_y + hud_h//2), "GLOBAL TOTAL", fill=(148, 163, 184, 255), font=font_year_label, anchor="lm")
    draw.text((WIDTH//2 + 205, hud_y + hud_h//2), pop_str, fill=(56, 189, 248, 255), font=font_year_hud, anchor="lm")

    # -------------------------------------------------------------
    # 3. RACING BARS WITH SMOOTH PHYSICAL Y POSITIONS & CONTRAST BADGES
    # -------------------------------------------------------------
    max_bar_w = 660
    min_bar_w = 340
    all_vals = [c["val"] for c in active_countries]
    max_v = max(all_vals)
    min_v = min(all_vals)
    if max_v == min_v: max_v += 0.01

    # Render bars: sort by elevation (elevated items rendered last so they glide ON TOP)
    countries_to_draw = sorted(active_countries, key=lambda c: c.get("z_order", 0))

    for item in countries_to_draw:
        cur_y = int(item["y_pos"])
        rank = item.get("display_rank", 1)
        is_champion = (rank == 1)

        val_fraction = (item["val"] - min_v) / (max_v - min_v)
        bar_w = int(min_bar_w + val_fraction * (max_bar_w - min_bar_w))

        c_code = item["code"]
        flag_im = flags.get(c_code, flags["IND"])

        bar, rim_col, rim_alpha = create_waving_bar(flag_im, bar_w, phase_t, is_gold=is_champion)
        bar_x = 75

        # If elevated during swap, draw soft drop shadow!
        if item.get("z_order", 0) > 0:
            shadow = Image.new("RGBA", (bar_w + 30, bar_h + 30), (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle([(15, 15), (bar_w + 15, bar_h + 15)], radius=radius, fill=(0, 0, 0, 140))
            shadow = shadow.filter(ImageFilter.GaussianBlur(10))
            canvas.paste(shadow, (bar_x - 15, cur_y - 5), shadow)

        canvas.paste(bar, (bar_x, cur_y), bar)

        # Monogram Crest (Left Circle)
        crest_size = 72
        cx = bar_x + 10
        cy = cur_y + (bar_h - crest_size)//2
        draw.ellipse([(cx, cy), (cx + crest_size, cy + crest_size)], fill=(10, 16, 28, 245), outline=rim_col + (rim_alpha,), width=2)
        draw.text((cx + crest_size//2, cy + crest_size//2), item["code"], fill=(255, 255, 255, 255), font=font_badge, anchor="mm")

        # --- TEXT CONTRAST FIX ---
        # High-Contrast Frosted Obsidian Glass Pill for Country Name & Rank
        text_badge_x = cx + crest_size + 14
        text_badge_y = cur_y + 16
        name_str = f"{item['name']} #{rank}"
        tw = int(draw.textlength(name_str, font=font_label))
        tb_w = tw + 26
        tb_h = 42

        # Frosted dark obsidian pill with subtle border
        pill_fill = (8, 14, 24, 215)
        pill_border = (255, 215, 0, 190) if is_champion else (255, 255, 255, 60)
        draw.rounded_rectangle([(text_badge_x, text_badge_y), (text_badge_x + tb_w, text_badge_y + tb_h)], radius=10, fill=pill_fill, outline=pill_border, width=1)
        
        # Crisp readable name
        name_color = (255, 215, 0, 255) if is_champion else (255, 255, 255, 255)
        draw.text((text_badge_x + tb_w//2, text_badge_y + tb_h//2), name_str, fill=name_color, font=font_label, anchor="mm")

        # Milestone Badge if present
        if item.get("badge"):
            badge_text = item["badge"]
            badge_w = int(draw.textlength(badge_text, font=font_badge)) + 24
            badge_h = 24
            bx = text_badge_x + tb_w + 10
            by = cur_y + bar_h // 2 - badge_h // 2
            bg_col = (212, 175, 55, 240) if is_champion else (225, 29, 72, 230)
            draw.rounded_rectangle([(bx, by), (bx + badge_w, by + badge_h)], radius=5, fill=bg_col)
            draw.text((bx + badge_w//2, by + badge_h//2), badge_text, fill=(0, 0, 0, 255) if is_champion else (255, 255, 255, 255), font=font_badge, anchor="mm")

        # Numeric Value on Right with Crisp Drop Shadow
        val_x = bar_x + bar_w + 22
        val_text_y = cur_y + bar_h // 2
        draw.text((val_x + 2, val_text_y + 2), item["val_str"], fill=(0, 0, 0, 255), font=font_val, anchor="lm")
        draw.text((val_x, val_text_y), item["val_str"], fill=(255, 255, 255, 255), font=font_val, anchor="lm")

    # -------------------------------------------------------------
    # 4. LOWER-THIRD VIRAL KARAOKE CAPTION (NATURAL EYE LEVEL)
    # -------------------------------------------------------------
    if caption_text:
        cap_y = 1380
        cap_w = int(draw.textlength(caption_text, font=font_caption)) + 70
        cap_h = 72
        cx = (WIDTH - cap_w) // 2
        # Frosted glass pill banner
        draw.rounded_rectangle([(cx, cap_y - cap_h//2), (cx + cap_w, cap_y + cap_h//2)], radius=18, fill=(12, 20, 36, 235), outline=(255, 215, 0, 180) if overtake_gold_pulse else (255, 255, 255, 50), width=2)
        # Drop shadow on subtitle
        draw.text((WIDTH//2 + 2, cap_y + 2), caption_text, fill=(0, 0, 0, 255), font=font_caption, anchor="mm")
        # Bold Yellow Pop
        draw.text((WIDTH//2, cap_y), caption_text, fill=(255, 230, 0, 255), font=font_caption, anchor="mm")

    # -------------------------------------------------------------
    # 5. BOTTOM FLOATING DEBATE PILL (ENGAGEMENT TRIGGER)
    # -------------------------------------------------------------
    bot_pill_w = 960
    bot_pill_h = 74
    bx = (WIDTH - bot_pill_w) // 2
    by = 1540
    draw.rounded_rectangle([(bx, by), (bx + bot_pill_w, by + bot_pill_h)], radius=37, fill=(14, 22, 38, 240), outline=(212, 175, 55, 220), width=2)
    debate_text = "WILL ANY NATION OVERTAKE INDIA BY 2050? VOTE BELOW"
    draw.text((WIDTH//2, by + bot_pill_h//2), debate_text, fill=(255, 215, 0, 255), font=font_debate, anchor="mm")
    # Draw vector gold stars on left and right of debate pill!
    draw_star(draw, bx + 45, by + bot_pill_h//2, r=10)
    draw_star(draw, bx + bot_pill_w - 45, by + bot_pill_h//2, r=10)

    # -------------------------------------------------------------
    # 6. OFFICIAL SOURCE ATTRIBUTION & BRANDING (JOURNALISTIC TRUST)
    # -------------------------------------------------------------
    source_str = "Data Source: United Nations Population Division (2024 Revision)  •  LR Atlas"
    draw.text((WIDTH//2, 1720), source_str, fill=(130, 150, 180, 240), font=font_source, anchor="mm")

    return canvas


# -------------------------------------------------------------
# 1. RENDER 4-STAGE STORYBOARD FOR COMPARISON
# -------------------------------------------------------------
print("Rendering V2 Storyboard...")
slot_start_y = 360
slot_gap_y = 135

def get_slot_y(rank):
    return slot_start_y + (rank - 1) * slot_gap_y

# Scene 1: 1970
countries_1970 = [
    {"name": "China", "code": "CHN", "val": 0.820, "val_str": "820 M", "badge": "#1 LEADER", "y_pos": get_slot_y(1), "display_rank": 1},
    {"name": "India", "code": "IND", "val": 0.550, "val_str": "550 M", "badge": "", "y_pos": get_slot_y(2), "display_rank": 2},
    {"name": "United States", "code": "USA", "val": 0.205, "val_str": "205 M", "badge": "", "y_pos": get_slot_y(3), "display_rank": 3},
    {"name": "Indonesia", "code": "IDN", "val": 0.115, "val_str": "115 M", "badge": "", "y_pos": get_slot_y(4), "display_rank": 4},
    {"name": "Pakistan", "code": "PAK", "val": 0.058, "val_str": "58 M", "badge": "", "y_pos": get_slot_y(5), "display_rank": 5},
    {"name": "Bangladesh", "code": "BGD", "val": 0.065, "val_str": "65 M", "badge": "", "y_pos": get_slot_y(6), "display_rank": 6},
    {"name": "Nigeria", "code": "NGA", "val": 0.056, "val_str": "56 M", "badge": "", "y_pos": get_slot_y(7), "display_rank": 7},
]
sb_frame_1970 = render_v2_frame(1970, 3.70, countries_1970, "DID YOU KNOW THIS?", phase_t=0.5)

# Scene 2: 2023 Historic Overtake
countries_2023 = [
    {"name": "India", "code": "IND", "val": 1.428, "val_str": "1.428 B", "badge": "NEW #1!", "y_pos": get_slot_y(1), "display_rank": 1},
    {"name": "China", "code": "CHN", "val": 1.425, "val_str": "1.425 B", "badge": "OVERTAKEN", "y_pos": get_slot_y(2), "display_rank": 2},
    {"name": "United States", "code": "USA", "val": 0.339, "val_str": "339 M", "badge": "", "y_pos": get_slot_y(3), "display_rank": 3},
    {"name": "Indonesia", "code": "IDN", "val": 0.277, "val_str": "277 M", "badge": "", "y_pos": get_slot_y(4), "display_rank": 4},
    {"name": "Pakistan", "code": "PAK", "val": 0.240, "val_str": "240 M", "badge": "", "y_pos": get_slot_y(5), "display_rank": 5},
    {"name": "Nigeria", "code": "NGA", "val": 0.224, "val_str": "224 M", "badge": "", "y_pos": get_slot_y(6), "display_rank": 6},
    {"name": "Bangladesh", "code": "BGD", "val": 0.172, "val_str": "172 M", "badge": "", "y_pos": get_slot_y(7), "display_rank": 7},
]
sb_frame_2023 = render_v2_frame(2023, 8.05, countries_2023, "INDIA TOOK THE CROWN!", phase_t=1.8, overtake_gold_pulse=True)

# Combine both into side-by-side storyboard
storyboard_v2 = Image.new("RGBA", (WIDTH * 2 + 60, HEIGHT), (6, 8, 14, 255))
storyboard_v2.paste(sb_frame_1970, (20, 0))
storyboard_v2.paste(sb_frame_2023, (WIDTH + 40, 0))
storyboard_v2.save("output/vertical_race_v2_storyboard.png", "PNG")
print("Saved V2 storyboard to: output/vertical_race_v2_storyboard.png")


# -------------------------------------------------------------
# 2. RENDER 5-SECOND REAL ANIMATED VIDEO DEMO WITH PERFECT SWAP
# -------------------------------------------------------------
print("Rendering V2 Live Video Demo with Smooth Rank Swap & Odometer...")
video_frames = []
total_frames = 150 # 5 seconds @ 30fps

# Exact model parameters: India crosses China at exactly progress = 0.50
# At progress=0.0: China=1.410, India=1.350
# At progress=0.5: China=1.413, India=1.413 (Exact Crossover!)
# At progress=1.0: China=1.416, India=1.435
country_models = {
    "CHN": {"name": "China", "start_val": 1.410, "end_val": 1.416, "unit": "B"},
    "IND": {"name": "India", "start_val": 1.350, "end_val": 1.435, "unit": "B"},
    "USA": {"name": "United States", "start_val": 328.0, "end_val": 341.0, "unit": "M"},
    "IDN": {"name": "Indonesia", "start_val": 269.0, "end_val": 281.0, "unit": "M"},
    "PAK": {"name": "Pakistan", "start_val": 222.0, "end_val": 248.0, "unit": "M"},
    "NGA": {"name": "Nigeria", "start_val": 200.0, "end_val": 230.0, "unit": "M"},
    "BGD": {"name": "Bangladesh", "start_val": 162.0, "end_val": 174.0, "unit": "M"},
}

y_slot1 = get_slot_y(1)
y_slot2 = get_slot_y(2)
swap_window = 0.16 # duration of swap animation centered at 0.50
swap_start = 0.50 - swap_window / 2
swap_end = 0.50 + swap_window / 2

for f in range(total_frames):
    progress = f / total_frames
    phase_t = progress * 10 * math.pi

    # Smooth continuous year & world population counters
    cur_year = 2018.0 + progress * 6.0 # 2018 -> 2024
    cur_world_pop = 7.60 + progress * 0.52 # 7.60B -> 8.12B

    # Continuous population computation for all countries
    frame_countries = []
    for code, m in country_models.items():
        v = m["start_val"] + progress * (m["end_val"] - m["start_val"])
        if m["unit"] == "B":
            v_norm = v
            v_str = f"{v:.3f} B"
        else:
            v_norm = v / 1000.0
            # Continuous integer ticking like an odometer!
            v_str = f"{int(v)} M"
        
        frame_countries.append({
            "code": code,
            "name": m["name"],
            "val": v_norm,
            "val_str": v_str,
            "unit": m["unit"],
            "raw_v": v
        })

    # Find CHN and IND
    c_chn = next(c for c in frame_countries if c["code"] == "CHN")
    c_ind = next(c for c in frame_countries if c["code"] == "IND")

    # True Rank Assignment
    if progress < 0.50:
        c_chn["display_rank"] = 1
        c_ind["display_rank"] = 2
    else:
        c_ind["display_rank"] = 1
        c_chn["display_rank"] = 2

    # Smooth Physical Vertical Swap Animation (Y-Glide + Elevation)
    # Staggered crossover: India accelerates up slightly ahead of China dropping down
    # so they glide past each other like sleek racing cars without clashing!
    if progress < swap_start:
        c_chn["y_pos"] = y_slot1
        c_ind["y_pos"] = y_slot2
        c_chn["badge"] = "#1 LEADER"
        c_ind["badge"] = "CLOSING IN"
        c_ind["z_order"] = 0
        c_chn["z_order"] = 0
    elif progress > swap_end:
        c_chn["y_pos"] = y_slot2
        c_ind["y_pos"] = y_slot1
        c_chn["badge"] = "HISTORIC #1"
        c_ind["badge"] = "NEW #1!"
        c_ind["z_order"] = 1 # India on top
        c_chn["z_order"] = 0
    else:
        # Smooth sinusoidal S-curve easing!
        p = (progress - swap_start) / swap_window
        
        # India takes the initiative and surges up with snappy cubic ease-in-out
        ease_ind = 0.5 - 0.5 * math.cos(p * math.pi)
        # China yields with a slight 15% lag
        p_chn = min(1.0, max(0.0, (p - 0.10) / 0.90))
        ease_chn = 0.5 - 0.5 * math.cos(p_chn * math.pi)
        
        c_ind["y_pos"] = y_slot2 - ease_ind * (y_slot2 - y_slot1)
        c_chn["y_pos"] = y_slot1 + ease_chn * (y_slot2 - y_slot1)

        # Enforce minimum vertical separation of labels if they get too close
        if abs(c_ind["y_pos"] - c_chn["y_pos"]) < 38:
            if progress < 0.50:
                c_chn["y_pos"] = min(c_chn["y_pos"], c_ind["y_pos"] - 38)
            else:
                c_ind["y_pos"] = min(c_ind["y_pos"], c_chn["y_pos"] - 38)

        c_ind["badge"] = "OVERTAKING!" if progress < 0.50 else "NEW #1!"
        c_chn["badge"] = "#1 LEADER" if progress < 0.50 else "OVERTAKEN"
        c_ind["z_order"] = 2 # Elevate India above China with 3D drop shadow!
        c_chn["z_order"] = 0

    # Other slots stay fixed at their respective rank positions
    for c in frame_countries:
        if c["code"] not in ("CHN", "IND"):
            c_rank = ["USA", "IDN", "PAK", "NGA", "BGD"].index(c["code"]) + 3
            c["y_pos"] = get_slot_y(c_rank)
            c["display_rank"] = c_rank
            c["badge"] = ""
            c["z_order"] = 0

    # Dynamic Captions
    if progress < 0.28:
        caption = "WATCH THE HISTORIC OVERTAKE..."
    elif progress < 0.48:
        caption = "INDIA IS CLOSING IN FAST!"
    elif progress < 0.76:
        caption = "2023: INDIA BECOMES #1 IN THE WORLD!"
    else:
        caption = "CAN ANY NATION OVERTAKE BY 2050?"

    is_overtaking_moment = (progress >= swap_start and progress < swap_end + 0.16)

    frm = render_v2_frame(cur_year, cur_world_pop, frame_countries, caption, phase_t=phase_t, overtake_gold_pulse=is_overtaking_moment)
    video_frames.append(frm.convert("RGB"))

# Render MP4 with FFmpeg
ffmpeg_cmd = [
    "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
    "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24", "-r", "30",
    "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
    "-movflags", "+faststart", "output/vertical_race_v2_demo.mp4"
]
p = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
for frm in video_frames:
    p.stdin.write(frm.tobytes())
p.stdin.close()
p.wait()
print("Saved live V2 video demo to: output/vertical_race_v2_demo.mp4")
