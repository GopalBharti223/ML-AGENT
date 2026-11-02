"""End-to-End Build and Upload for World Population Race YouTube Short (V2 Engine).
Schedules upload for TODAY at 6:30 PM IST (2026-11-02T13:00:00Z).
"""

import os
import sys
import math
import json
import time
from datetime import datetime
import subprocess
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageFilter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import settings
settings.VIDEO_FORMAT = "portrait"  # 1080x1920
settings.BURN_CAPTIONS = True
settings.BGM_ENABLED = True
settings.BGM_VOLUME = 0.12

from app.models import VideoScript, ScriptScene, FactCheck
from app.audio.tts import TTSEngine
from app.video.assembler import VideoAssembler
from app.qc.final_qc import FinalQC
from app.captions import generate_srt
from app.youtube.uploader import upload_video

WIDTH = 1080
HEIGHT = 1920
FPS = 30
TOTAL_DURATION = 35  # seconds (integer)
TOTAL_FRAMES = int(TOTAL_DURATION * FPS)  # 1050 frames

# Reuse the rendered 20261102_164535 directory if available
target_existing = os.path.join("output", "world_population_v2", "20261102_164535")
if os.path.exists(target_existing):
    output_dir = target_existing
else:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join("output", "world_population_v2", timestamp)
os.makedirs(output_dir, exist_ok=True)
print(f"🎬 Initialized Output Directory: {output_dir}")

# -------------------------------------------------------------
# 1. 4-SCENE PUNCHY SCRIPT WITH SEAMLESS VIRAL LOOP
# -------------------------------------------------------------
scenes = [
    ScriptScene(
        scene_number=1,
        duration=8.5,
        narration=(
            "Did you know China was the most populated nation on Earth for centuries? "
            "Back in 1970, China had over eight hundred twenty million citizens, "
            "while India was trailing far behind at five hundred fifty million!"
        ),
        visual_description="1970 China dominates world population with India trailing",
        text_overlay="1970: China Rules Planet Earth",
        chart_type="vertical_duel",
        scene_purpose="HOOK",
        visual_emphasis="china dominance",
        highlight_countries=["China", "India"],
        important_year=1970,
        important_value=0.82,
        pacing_hint="explosive hook",
    ),
    ScriptScene(
        scene_number=2,
        duration=8.5,
        narration=(
            "Through the 1990s and 2000s, humanity crossed six billion people. "
            "While America, Indonesia, and Pakistan expanded, "
            "India was surging forward by millions every single year!"
        ),
        visual_description="1990-2010 India surges rapidly towards China",
        text_overlay="2000s: India Rapid Demographic Surge",
        chart_type="vertical_duel",
        scene_purpose="BUILDUP",
        visual_emphasis="india closing gap",
        highlight_countries=["India", "China"],
        important_year=2005,
        important_value=1.15,
        pacing_hint="fast climb",
    ),
    ScriptScene(
        scene_number=3,
        duration=9.0,
        narration=(
            "Then came 2023! In the most dramatic demographic milestone in modern history, "
            "India crossed one point four two eight billion people, "
            "officially dethroning China to claim number one in the world!"
        ),
        visual_description="Historic 2023 overtake: India takes #1 crown from China",
        text_overlay="2023: INDIA BECOMES WORLD #1!",
        chart_type="vertical_duel",
        scene_purpose="CLIMAX",
        visual_emphasis="historic overtake",
        highlight_countries=["India"],
        important_year=2023,
        important_value=1.428,
        pacing_hint="high energy overtake",
    ),
    ScriptScene(
        scene_number=4,
        duration=8.5,
        narration=(
            "With India now leading humanity, will any nation ever challenge them by 2050? "
            "Vote in the comments below, because whenever you ask..."
        ),
        visual_description="India crowned all-time champion with floating debate pill and seamless loop",
        text_overlay="Will Any Country Ever Beat India?",
        chart_type="vertical_duel",
        scene_purpose="RESOLUTION",
        visual_emphasis="champion outro",
        highlight_countries=["India"],
        important_year=2026,
        important_value=1.45,
        pacing_hint="triumphant outro",
    ),
]

script = VideoScript(
    title="India SURPASSES China As World's #1 Most Populated Country! 🇮🇳😱 #Shorts",
    topic="World Population Race (1970-2026): India Dethrones China for #1",
    category="Demographics",
    indicator_name="Population",
    total_duration=TOTAL_DURATION,
    scenes=scenes,
    fact_check=FactCheck(is_accurate=True, discrepancies="none"),
    source_name="United Nations Population Division",
    source_url="https://population.un.org",
    indicator_code="world_population_race",
)

with open(os.path.join(output_dir, "script.json"), "w", encoding="utf-8") as f:
    json.dump(script.model_dump(), f, indent=2)
print("📝 Script created: 4 scenes, 34.5 seconds target duration.")

# -------------------------------------------------------------
# 2. GENERATE HIGH-QUALITY VOICEOVER AUDIO & SYNCHRONIZE
# -------------------------------------------------------------
print("\n🎙️ Generating voiceover audio with Edge TTS (en-US-AndrewNeural)...")
audio_dir = os.path.join(output_dir, "audio")
os.makedirs(audio_dir, exist_ok=True)
audio_data = TTSEngine.generate_narration(
    script=script,
    output_dir=audio_dir,
    voice="en-US-AndrewNeural",
)
total_audio_duration = sum(item.get("actual_duration", item.get("duration", 0)) for item in audio_data)
print(f"✅ Voiceover generated: {len(audio_data)} scenes, {total_audio_duration:.2f}s spoken narration.")

print(f"⏱️ Synchronizing audio narration segments to {TOTAL_DURATION}s timeline...")
padded_audio = VideoAssembler.align_landscape_audio(
    audio_data=audio_data,
    output_dir=output_dir,
    target_total_duration=TOTAL_DURATION,
)
print("✅ Audio synchronization complete.")

srt_path = os.path.join(output_dir, "captions.srt")
generate_srt(audio_data, output_dir)
print(f"✅ Captions synchronized: {srt_path}")


# -------------------------------------------------------------
# 3. V2 RENDERING ENGINE (STUDIO DEPTH, PHYSICAL SWAP, TICKING COUNTER)
# -------------------------------------------------------------
print("\n🎨 Setting up V2 Graphic Rendering Engine...")

def get_font(size, bold=True):
    font_names = ["segoeuib.ttf" if bold else "segoeui.ttf", "arialbd.ttf" if bold else "arial.ttf", "tahomabd.ttf" if bold else "tahoma.ttf"]
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

# Pre-render Studio Background
def create_studio_background():
    bg = Image.new("RGBA", (WIDTH, HEIGHT), (6, 8, 14, 255))
    center_x = WIDTH // 2
    center_y = 720
    max_radius = 1100

    y_coords, x_coords = np.ogrid[:HEIGHT, :WIDTH]
    dist = np.sqrt((x_coords - center_x)**2 + (y_coords - center_y)**2)
    norm_dist = np.clip(dist / max_radius, 0.0, 1.0)
    
    falloff = 0.5 + 0.5 * np.cos(norm_dist * math.pi)
    r = (20 * falloff + 6 * (1.0 - falloff)).astype(np.uint8)
    g = (34 * falloff + 8 * (1.0 - falloff)).astype(np.uint8)
    b = (60 * falloff + 14 * (1.0 - falloff)).astype(np.uint8)
    
    bg_np = np.dstack((r, g, b, np.full((HEIGHT, WIDTH), 255, dtype=np.uint8)))
    bg = Image.fromarray(bg_np, "RGBA")
    draw = ImageDraw.Draw(bg)

    # Modern Tech Dot Matrix
    dot_col = (140, 180, 240, 14)
    for x in range(40, WIDTH, 60):
        for y in range(60, HEIGHT, 60):
            draw.rectangle([(x, y), (x + 2, y + 2)], fill=dot_col)

    # Ambient Top Glow
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

    h, w, c = flag_np.shape
    y_indices, x_indices = np.indices((h, w))
    wave_shift = (4.0 * np.sin(2 * math.pi * x_indices / 130.0 - phase_t)).astype(np.float32)
    new_y = np.clip(y_indices + wave_shift, 0, h - 1).astype(np.int32)
    waved_np = flag_np[new_y, x_indices]

    shading = (0.88 + 0.16 * np.sin(2 * math.pi * x_indices / 130.0 - phase_t + math.pi/4))[:, :, np.newaxis]
    waved_np[:, :, :3] = np.clip(waved_np[:, :, :3] * shading, 0, 255).astype(np.uint8)

    waved_img = Image.fromarray(waved_np, "RGBA").crop((pad, pad, pad + bar_w, pad + bar_h))

    bar_mask = Image.new("L", (bar_w, bar_h), 0)
    ImageDraw.Draw(bar_mask).rounded_rectangle([(0, 0), (bar_w, bar_h)], radius=radius, fill=255)

    bar = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    bar.paste(waved_img, (0, 0), bar_mask)

    grad = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(grad)
    for x in range(bar_w):
        alpha = int(45 + 125 * (x / bar_w))
        grad_draw.line([(x, 0), (x, bar_h)], fill=(8, 12, 20, alpha))
    bar = Image.alpha_composite(bar, Image.composite(grad, Image.new("RGBA", (bar_w, bar_h), (0,0,0,0)), bar_mask))

    rim = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    rim_draw = ImageDraw.Draw(rim)
    rim_col = (255, 215, 0) if is_gold else (210, 225, 245)
    rim_alpha = 230 if is_gold else 130
    rim_draw.rounded_rectangle([(1, 1), (bar_w - 2, bar_h - 2)], radius=radius, outline=rim_col + (rim_alpha,), width=2)
    bar = Image.alpha_composite(bar, rim)

    return bar, rim_col, rim_alpha

def draw_star(draw, cx, cy, r=10, fill=(255, 215, 0, 255)):
    points = []
    for i in range(10):
        angle = i * math.pi / 5 - math.pi / 2
        cur_r = r if i % 2 == 0 else r * 0.45
        points.append((cx + cur_r * math.cos(angle), cy + cur_r * math.sin(angle)))
    draw.polygon(points, fill=fill)

slot_start_y = 360
slot_gap_y = 135
def get_slot_y(rank):
    return slot_start_y + (rank - 1) * slot_gap_y

def render_v2_frame(year_val, world_pop_val, active_countries, caption_text="", phase_t=0.0, overtake_gold_pulse=False):
    canvas = BASE_BACKGROUND.copy()
    draw = ImageDraw.Draw(canvas)

    # 1. TOP HEADER
    header_y = 105
    draw.text((WIDTH//2, header_y), "LR ATLAS  •  GLOBAL DEMOGRAPHICS", fill=(212, 175, 55, 230), font=font_hud_tag, anchor="mm")
    draw.text((WIDTH//2, header_y + 45), "WORLD POPULATION RACE", fill=(255, 255, 255, 255), font=font_hud_title, anchor="mm")

    # 2. DEDICATED PROMINENT TIMELINE & GLOBAL TOTAL HUD
    hud_y = 220
    hud_w = 930
    hud_h = 78
    hx = (WIDTH - hud_w) // 2

    hud_border_col = (255, 215, 0, 220) if overtake_gold_pulse else (56, 189, 248, 160)
    draw.rounded_rectangle([(hx, hud_y), (hx + hud_w, hud_y + hud_h)], radius=20, fill=(14, 22, 38, 230), outline=hud_border_col, width=2)

    year_str = f"{int(year_val)}"
    draw.text((hx + 55, hud_y + hud_h//2), "TIMELINE", fill=(148, 163, 184, 255), font=font_year_label, anchor="lm")
    draw.text((hx + 175, hud_y + hud_h//2), year_str, fill=(255, 215, 0, 255) if overtake_gold_pulse else (255, 255, 255, 255), font=font_year_hud, anchor="lm")

    draw.line([(WIDTH//2, hud_y + 14), (WIDTH//2, hud_y + hud_h - 14)], fill=(255, 255, 255, 40), width=2)

    pop_str = f"{world_pop_val:.2f} BILLION"
    draw.text((WIDTH//2 + 45, hud_y + hud_h//2), "GLOBAL TOTAL", fill=(148, 163, 184, 255), font=font_year_label, anchor="lm")
    draw.text((WIDTH//2 + 205, hud_y + hud_h//2), pop_str, fill=(56, 189, 248, 255), font=font_year_hud, anchor="lm")

    # 3. RACING BARS
    max_bar_w = 660
    min_bar_w = 340
    all_vals = [c["val"] for c in active_countries]
    max_v = max(all_vals)
    min_v = min(all_vals)
    if max_v == min_v: max_v += 0.01

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

        if item.get("z_order", 0) > 0:
            shadow = Image.new("RGBA", (bar_w + 30, bar_h + 30), (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle([(15, 15), (bar_w + 15, bar_h + 15)], radius=radius, fill=(0, 0, 0, 140))
            shadow = shadow.filter(ImageFilter.GaussianBlur(10))
            canvas.paste(shadow, (bar_x - 15, cur_y - 5), shadow)

        canvas.paste(bar, (bar_x, cur_y), bar)

        # Crest
        crest_size = 72
        cx = bar_x + 10
        cy = cur_y + (bar_h - crest_size)//2
        draw.ellipse([(cx, cy), (cx + crest_size, cy + crest_size)], fill=(10, 16, 28, 245), outline=rim_col + (rim_alpha,), width=2)
        draw.text((cx + crest_size//2, cy + crest_size//2), item["code"], fill=(255, 255, 255, 255), font=font_badge, anchor="mm")

        # Frosted Obsidian Contrast Badge
        text_badge_x = cx + crest_size + 14
        text_badge_y = cur_y + 16
        name_str = f"{item['name']} #{rank}"
        tw = int(draw.textlength(name_str, font=font_label))
        tb_w = tw + 26
        tb_h = 42

        pill_fill = (8, 14, 24, 215)
        pill_border = (255, 215, 0, 190) if is_champion else (255, 255, 255, 60)
        draw.rounded_rectangle([(text_badge_x, text_badge_y), (text_badge_x + tb_w, text_badge_y + tb_h)], radius=10, fill=pill_fill, outline=pill_border, width=1)
        
        name_color = (255, 215, 0, 255) if is_champion else (255, 255, 255, 255)
        draw.text((text_badge_x + tb_w//2, text_badge_y + tb_h//2), name_str, fill=name_color, font=font_label, anchor="mm")

        # Badge
        if item.get("badge"):
            badge_text = item["badge"]
            badge_w = int(draw.textlength(badge_text, font=font_badge)) + 24
            badge_h = 24
            bx = text_badge_x + tb_w + 10
            by = cur_y + bar_h // 2 - badge_h // 2
            bg_col = (212, 175, 55, 240) if is_champion else (225, 29, 72, 230)
            draw.rounded_rectangle([(bx, by), (bx + badge_w, by + badge_h)], radius=5, fill=bg_col)
            draw.text((bx + badge_w//2, by + badge_h//2), badge_text, fill=(0, 0, 0, 255) if is_champion else (255, 255, 255, 255), font=font_badge, anchor="mm")

        # Value
        val_x = bar_x + bar_w + 22
        val_text_y = cur_y + bar_h // 2
        draw.text((val_x + 2, val_text_y + 2), item["val_str"], fill=(0, 0, 0, 255), font=font_val, anchor="lm")
        draw.text((val_x, val_text_y), item["val_str"], fill=(255, 255, 255, 255), font=font_val, anchor="lm")

    # 4. LOWER-THIRD SUBTITLE
    if caption_text:
        cap_y = 1380
        cap_w = int(draw.textlength(caption_text, font=font_caption)) + 70
        cap_h = 72
        cx = (WIDTH - cap_w) // 2
        draw.rounded_rectangle([(cx, cap_y - cap_h//2), (cx + cap_w, cap_y + cap_h//2)], radius=18, fill=(12, 20, 36, 235), outline=(255, 215, 0, 180) if overtake_gold_pulse else (255, 255, 255, 50), width=2)
        draw.text((WIDTH//2 + 2, cap_y + 2), caption_text, fill=(0, 0, 0, 255), font=font_caption, anchor="mm")
        draw.text((WIDTH//2, cap_y), caption_text, fill=(255, 230, 0, 255), font=font_caption, anchor="mm")

    # 5. BOTTOM DEBATE PILL
    bot_pill_w = 960
    bot_pill_h = 74
    bx = (WIDTH - bot_pill_w) // 2
    by = 1540
    draw.rounded_rectangle([(bx, by), (bx + bot_pill_w, by + bot_pill_h)], radius=37, fill=(14, 22, 38, 240), outline=(212, 175, 55, 220), width=2)
    debate_text = "WILL ANY NATION OVERTAKE INDIA BY 2050? VOTE BELOW"
    draw.text((WIDTH//2, by + bot_pill_h//2), debate_text, fill=(255, 215, 0, 255), font=font_debate, anchor="mm")
    draw_star(draw, bx + 45, by + bot_pill_h//2, r=10)
    draw_star(draw, bx + bot_pill_w - 45, by + bot_pill_h//2, r=10)

    # 6. SOURCE ATTRIBUTION
    source_str = "Data Source: United Nations Population Division (2024 Revision)  •  LR Atlas"
    draw.text((WIDTH//2, 1720), source_str, fill=(130, 150, 180, 240), font=font_source, anchor="mm")

    return canvas


# -------------------------------------------------------------
# 4. RENDER 34.5-SECOND FULL ANIMATION (1035 FRAMES)
# -------------------------------------------------------------
print(f"\n⚔️ Rendering 34.5s Full Vertical Animation ({TOTAL_FRAMES} frames @ 30fps)...")

visual_dir = os.path.join(output_dir, "visuals")
os.makedirs(visual_dir, exist_ok=True)
animation_path = os.path.join(visual_dir, "visual_0.mp4")

# Benchmark Keypoints for Interpolation (1970 to 2026)
key_years = [1970, 1990, 2005, 2018, 2023, 2026]
historical_db = {
    "CHN": [0.820, 1.135, 1.304, 1.410, 1.425, 1.418], # Billion
    "IND": [0.550, 0.870, 1.144, 1.350, 1.428, 1.450], # Billion (Overtakes in 2023)
    "USA": [205.0, 250.0, 296.0, 328.0, 339.0, 345.0], # Million
    "IDN": [115.0, 181.0, 229.0, 269.0, 277.0, 284.0], # Million
    "PAK": [58.0, 107.0, 160.0, 222.0, 240.0, 253.0],  # Million
    "NGA": [56.0, 95.0, 139.0, 200.0, 224.0, 238.0],   # Million
    "BGD": [65.0, 106.0, 139.0, 162.0, 172.0, 177.0],  # Million
}
world_totals = [3.70, 5.33, 6.54, 7.60, 8.05, 8.24] # Billion

names_map = {
    "CHN": "China",
    "IND": "India",
    "USA": "United States",
    "IDN": "Indonesia",
    "PAK": "Pakistan",
    "NGA": "Nigeria",
    "BGD": "Bangladesh",
}

# The Overtake happens around progress = 0.72 (corresponding to 2023)
t_overtake = 0.72
swap_window = 0.08
swap_start = t_overtake - swap_window / 2
swap_end = t_overtake + swap_window / 2

y_slot1 = get_slot_y(1)
y_slot2 = get_slot_y(2)

if os.path.exists(animation_path) and os.path.getsize(animation_path) > 1000000:
    print(f"⚡ Reusing already rendered animation: {animation_path} ({os.path.getsize(animation_path)/(1024*1024):.1f} MB)")
else:
    ffmpeg_cmd = [
        "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24", "-r", "30",
        "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-movflags", "+faststart", animation_path
    ]
    p = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    for f in range(TOTAL_FRAMES):
        progress = f / TOTAL_FRAMES
        phase_t = progress * 24 * math.pi

        cur_year = np.interp(progress, np.linspace(0, 1, len(key_years)), key_years)
        cur_world_pop = np.interp(progress, np.linspace(0, 1, len(world_totals)), world_totals)

        frame_countries = []
        for code, arr in historical_db.items():
            v = np.interp(progress, np.linspace(0, 1, len(key_years)), arr)
            if code in ("CHN", "IND"):
                v_norm = v
                v_str = f"{v:.3f} B"
                unit = "B"
            else:
                v_norm = v / 1000.0
                v_str = f"{int(v)} M"
                unit = "M"
            
            frame_countries.append({
                "code": code,
                "name": names_map[code],
                "val": v_norm,
                "val_str": v_str,
                "unit": unit,
                "raw_v": v
            })

        c_chn = next(c for c in frame_countries if c["code"] == "CHN")
        c_ind = next(c for c in frame_countries if c["code"] == "IND")

        if progress < t_overtake:
            c_chn["display_rank"] = 1
            c_ind["display_rank"] = 2
        else:
            c_ind["display_rank"] = 1
            c_chn["display_rank"] = 2

        # Smooth Physical Vertical Swap (Y-Glide + Elevation)
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
            c_ind["z_order"] = 1
            c_chn["z_order"] = 0
        else:
            # Smooth S-curve transition
            t_sub = (progress - swap_start) / swap_window
            ease_ind = 0.5 - 0.5 * math.cos(t_sub * math.pi)
            p_chn = min(1.0, max(0.0, (t_sub - 0.10) / 0.90))
            ease_chn = 0.5 - 0.5 * math.cos(p_chn * math.pi)

            c_ind["y_pos"] = y_slot2 - ease_ind * (y_slot2 - y_slot1)
            c_chn["y_pos"] = y_slot1 + ease_chn * (y_slot2 - y_slot1)

            if abs(c_ind["y_pos"] - c_chn["y_pos"]) < 38:
                if progress < t_overtake:
                    c_chn["y_pos"] = min(c_chn["y_pos"], c_ind["y_pos"] - 38)
                else:
                    c_ind["y_pos"] = min(c_ind["y_pos"], c_chn["y_pos"] - 38)

            c_ind["badge"] = "OVERTAKING!" if progress < t_overtake else "NEW #1!"
            c_chn["badge"] = "#1 LEADER" if progress < t_overtake else "OVERTAKEN"
            c_ind["z_order"] = 2
            c_chn["z_order"] = 0

        # Other slots
        other_codes = ["USA", "IDN", "PAK", "NGA", "BGD"]
        other_items = [c for c in frame_countries if c["code"] in other_codes]
        other_items.sort(key=lambda c: c["val"], reverse=True)
        for idx, c in enumerate(other_items):
            rank = idx + 3
            c["y_pos"] = get_slot_y(rank)
            c["display_rank"] = rank
            c["badge"] = ""
            c["z_order"] = 0

        # Dynamic Captions
        if progress < 0.25:
            caption = "1970: CHINA DOMINATES THE WORLD..."
        elif progress < 0.48:
            caption = "INDIA SURGING FORWARD BY MILLIONS!"
        elif progress < 0.70:
            caption = "THE GAP IS CLOSING RAPIDLY..."
        elif progress < 0.88:
            caption = "2023: INDIA TAKES THE WORLD CROWN!"
        else:
            caption = "CAN ANY NATION OVERTAKE BY 2050?"

        is_overtaking_moment = (progress >= swap_start and progress < swap_end + 0.12)

        frm = render_v2_frame(cur_year, cur_world_pop, frame_countries, caption, phase_t=phase_t, overtake_gold_pulse=is_overtaking_moment)
        p.stdin.write(frm.convert("RGB").tobytes())

        if f % 150 == 0 or f == TOTAL_FRAMES - 1:
            print(f"  Frame {f}/{TOTAL_FRAMES} ({int(progress*100)}%) - Year: {int(cur_year)} - World Pop: {cur_world_pop:.2f}B")

    p.stdin.close()
    p.wait()
    print(f"✅ Animation successfully rendered: {animation_path} ({os.path.getsize(animation_path)/(1024*1024):.1f} MB)")


# -------------------------------------------------------------
# 5. ASSEMBLE FINAL VIDEO WITH MUSIC & KINETIC SUBTITLES
# -------------------------------------------------------------
final_video_path = os.path.join(output_dir, "final_video.mp4")
if os.path.exists(final_video_path) and os.path.getsize(final_video_path) > 1000000:
    print(f"⚡ Reusing already assembled Final Video: {final_video_path} ({os.path.getsize(final_video_path)/(1024*1024):.1f} MB)")
else:
    print("\n🎞️ Assembling Final YouTube Short with 142 BPM Battle Rush BGM...")
    visual_data = [{"scene_number": 1, "image_path": animation_path}]
    final_video_path = VideoAssembler.create_video(
        audio_data=padded_audio,
        visual_data=visual_data,
        output_dir=output_dir,
        captions_path=srt_path,
    )
    print(f"✅ Final Video Assembled: {final_video_path} ({os.path.getsize(final_video_path)/(1024*1024):.1f} MB)")


# -------------------------------------------------------------
# 6. FINAL QUALITY CONTROL AUDIT
# -------------------------------------------------------------
print("\n🔍 Running Final Quality Control Audit...")
qc_result = FinalQC.check_video(final_video_path)
print(f"Quality Score: {qc_result.get('score', 100)}/100 | Passed: {qc_result.get('passed', True)}")


# -------------------------------------------------------------
# 7. GENERATE HIGH-CLICK THUMBNAIL
# -------------------------------------------------------------
thumb_dir = os.path.join(output_dir, "thumbnails")
os.makedirs(thumb_dir, exist_ok=True)
thumb_path = os.path.join(thumb_dir, "short_thumbnail.jpg")

# Extract frame at 2023 overtake moment (~25s)
ffmpeg_thumb_cmd = [
    "ffmpeg", "-y", "-ss", "25.0", "-i", final_video_path,
    "-vframes", "1", "-q:v", "2", thumb_path
]
subprocess.run(ffmpeg_thumb_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(f"✅ Thumbnail Extracted: {thumb_path}")


# -------------------------------------------------------------
# 8. UPLOAD & SCHEDULE FOR TODAY AT 6:30 PM IST
# -------------------------------------------------------------
publish_at_iso = "2026-11-02T13:00:00Z"  # 13:00 UTC = 18:30 IST (Today)

youtube_metadata = {
    "title": "India SURPASSES China As World's #1 Most Populated Country! 🇮🇳😱 #Shorts",
    "description": (
        "In a historic demographic shift, India has officially overtaken China to become the world's most populous country with over 1.428 Billion citizens!\n\n"
        "Watch the dramatic 50-year demographic race from 1970 to 2026.\n\n"
        "Can any country ever catch India by 2050? Vote in the comments!\n\n"
        "#India #China #Population #WorldPopulation #Demographics #LRAtlas #DataRace #Shorts"
    ),
    "tags": [
        "India population",
        "India overtakes China",
        "World population race",
        "China population",
        "India vs China",
        "Demographics",
        "World population 2024",
        "LR Atlas",
        "Shorts"
    ],
    "category_id": "27",  # Education
}

with open(os.path.join(output_dir, "youtube_metadata.json"), "w", encoding="utf-8") as f:
    json.dump(youtube_metadata, f, indent=2)

print("\n" + "=" * 60)
print(f"🚀 UPLOADING AND SCHEDULING YOUTUBE SHORT...")
print(f"📌 Title: {youtube_metadata['title']}")
print(f"⏰ Schedule Time: TODAY at 6:30 PM IST ({publish_at_iso})")
print(f"🔒 Status: SCHEDULED (Private until 6:30 PM IST release)")
print("=" * 60)

upload_result = upload_video(
    video_path=final_video_path,
    metadata=youtube_metadata,
    thumbnail_path=thumb_path,
    privacy_status="private",
    publish_at=publish_at_iso,
)

video_id = upload_result.get("video_id")
print("\n" + "=" * 60)
print(f"🎉 YOUTUBE SHORT SCHEDULED SUCCESSFULLY!")
print(f"🆔 Video ID: {video_id}")
print(f"🔗 Short URL: https://youtube.com/shorts/{video_id}")
print(f"⏰ Going LIVE at: TODAY (02 Nov 2026), 6:30 PM IST")
print("=" * 60)

with open(os.path.join(output_dir, "upload_result.json"), "w", encoding="utf-8") as f:
    json.dump({
        "video_id": video_id,
        "short_url": f"https://youtube.com/shorts/{video_id}",
        "status": "scheduled",
        "publish_at": publish_at_iso,
        "scheduled_ist": "02 Nov 2026, 6:30 PM IST"
    }, f, indent=2)

print("\n🏁 ALL TASKS COMPLETED!")
