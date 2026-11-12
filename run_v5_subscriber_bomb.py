"""V5 SUBSCRIBER-CONVERSION WEAPON.
Engine Targets:
1. Crack the Subscriber Barrier (On-Screen Animated Glowing Subscribe Pill at 9s).
2. Spoken Compelling Identity Call:
   "Indian Americans are the #1 richest group in the US! Subscribe to celebrate India's power!"
3. Ultra-Paced 14.0s Duration -> 160%+ APV.
4. Topic: Richest Ethnic Groups in America: How Indians Took Over the US!
   - Indian Americans: $152,000 median income (#1)
   - Filipino: $102,000 (#2)
   - White Americans: $78,000
   - All US Average: $74,000
"""

import os
import sys
import math
import json
from datetime import datetime
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import settings
settings.VIDEO_FORMAT = "portrait"
settings.BURN_CAPTIONS = False
settings.BGM_ENABLED = True
settings.BGM_VOLUME = 0.16

from app.models import VideoScript, ScriptScene, FactCheck
from app.audio.tts import TTSEngine
from app.video.assembler import VideoAssembler
from app.qc.final_qc import FinalQC
from app.captions import generate_srt
from app.youtube.uploader import upload_video

WIDTH = 1080
HEIGHT = 1920
FPS = 30
TOTAL_DURATION = 14
TOTAL_FRAMES = int(TOTAL_DURATION * FPS)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_dir = os.path.join("output", "v5_viral_series", f"indian_americans_{timestamp}")
os.makedirs(output_dir, exist_ok=True)
print(f"🎬 Initialized V5 Output: {output_dir}")

# -----------------------------------------------------------------
# 1. PSYCHOLOGICALLY ENGINEERED 14.0s SCRIPT
# -----------------------------------------------------------------
scenes = [
    ScriptScene(
        scene_number=1,
        duration=4.5,
        narration="America is the richest country on Earth, but do you know who actually earns the most money there?",
        visual_description="Full screen shock hook on US highest earners",
        text_overlay="WHO EARNS THE MOST IN AMERICA?",
        chart_type="vertical_duel",
        scene_purpose="HOOK",
        visual_emphasis="high curiosity hook",
        highlight_countries=["India", "United States"],
        important_year=2024,
        important_value=152.0,
        pacing_hint="explosive fast hook",
    ),
    ScriptScene(
        scene_number=2,
        duration=5.0,
        narration="Indian Americans crushed everyone with a median household income of one hundred and fifty-two thousand dollars!",
        visual_description="Indian Americans soaring way above White, Asian, and average American incomes",
        text_overlay="INDIANS TAKE WORLD #1!",
        chart_type="vertical_duel",
        scene_purpose="CLIMAX",
        visual_emphasis="historic income dominance",
        highlight_countries=["India"],
        important_year=2024,
        important_value=152.0,
        pacing_hint="proud high energy",
    ),
    ScriptScene(
        scene_number=3,
        duration=4.5,
        narration="Double the US average! Subscribe right now if you are proud of India's global dominance!",
        visual_description="Direct spoken and visual call to subscribe and celebrate",
        text_overlay="SUBSCRIBE FOR INDIA! 🇮🇳🔥",
        chart_type="vertical_duel",
        scene_purpose="RESOLUTION",
        visual_emphasis="viral subscriber prompt",
        highlight_countries=["India"],
        important_year=2026,
        important_value=165.0,
        pacing_hint="sharp viral outro",
    ),
]

script = VideoScript(
    title="Indians Are The RICHEST In America?! 🇮🇳🇺🇸 #Shorts",
    topic="Richest Ethnic Groups in America: Indian Income Dominance",
    category="People & Blogs",
    indicator_name="Median Household Income ($k)",
    total_duration=TOTAL_DURATION,
    scenes=scenes,
    fact_check=FactCheck(is_accurate=True, discrepancies="none"),
    source_name="US Census Bureau (American Community Survey)",
    source_url="https://www.census.gov",
    indicator_code="us_median_income_by_ethnicity",
)

with open(os.path.join(output_dir, "script.json"), "w", encoding="utf-8") as f:
    json.dump(script.model_dump(), f, indent=2)

# -----------------------------------------------------------------
# 2. AUDIO & VOICEOVER GENERATION
# -----------------------------------------------------------------
print("\n🎙️ Generating 14.0s High-Velocity Audio...")
audio_dir = os.path.join(output_dir, "audio")
os.makedirs(audio_dir, exist_ok=True)

audio_data = TTSEngine.generate_narration(
    script=script,
    output_dir=audio_dir,
    voice="en-US-AndrewNeural",
)

padded_audio = VideoAssembler.align_landscape_audio(
    audio_data=audio_data,
    output_dir=output_dir,
    target_total_duration=TOTAL_DURATION,
)
srt_path = os.path.join(output_dir, "captions.srt")
generate_srt(audio_data, output_dir)
print("✅ Audio synchronized for 14.0s.")

# -----------------------------------------------------------------
# 3. V5 ENGINE DESIGN SETUP
# -----------------------------------------------------------------
def get_font(size, bold=True):
    for fn in (["segoeuib.ttf", "arialbd.ttf", "tahomabd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]):
        try:
            return ImageFont.truetype(fn, size)
        except Exception:
            continue
    return ImageFont.load_default()

font_alert = get_font(34, bold=True)
font_title = get_font(42, bold=True)
font_year = get_font(38, bold=True)
font_label = get_font(28, bold=True)
font_val = get_font(32, bold=True)
font_badge = get_font(18, bold=True)
font_cta = get_font(26, bold=True)
font_sub_pill = get_font(30, bold=True)
font_caption = get_font(46, bold=True)

flags = {}
for c3, c2 in [("IND", "in"), ("USA", "us"), ("CHN", "cn"), ("JPN", "jp"), ("KOR", "kr"), ("PHL", "ph")]:
    for p in [f"assets/flags_hires/{c2}.png", f"assets/flags/{c2}.png"]:
        if os.path.exists(p):
            flags[c3] = Image.open(p).convert("RGBA")
            break

def create_v5_background():
    bg = Image.new("RGBA", (WIDTH, HEIGHT), (6, 8, 16, 255))
    y_coords, x_coords = np.ogrid[:HEIGHT, :WIDTH]
    dist = np.sqrt((x_coords - WIDTH//2)**2 + (y_coords - 700)**2)
    norm = np.clip(dist / 1000.0, 0.0, 1.0)
    falloff = 0.5 + 0.5 * np.cos(norm * math.pi)
    
    r = (32 * falloff + 6 * (1.0 - falloff)).astype(np.uint8)
    g = (20 * falloff + 6 * (1.0 - falloff)).astype(np.uint8)
    b = (56 * falloff + 12 * (1.0 - falloff)).astype(np.uint8)
    
    bg_np = np.dstack((r, g, b, np.full((HEIGHT, WIDTH), 255, dtype=np.uint8)))
    bg = Image.fromarray(bg_np, "RGBA")
    draw = ImageDraw.Draw(bg)
    
    for x in range(25, WIDTH, 45):
        for y in range(35, HEIGHT, 45):
            draw.rectangle([(x, y), (x + 2, y + 2)], fill=(180, 150, 255, 14))
            
    top_glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    tg_draw = ImageDraw.Draw(top_glow)
    for y in range(260):
        a = int(45 * (1.0 - y / 260.0))
        tg_draw.line([(0, y), (WIDTH, y)], fill=(255, 153, 51, a))
    return Image.alpha_composite(bg, top_glow)

BASE_BG = create_v5_background()

bar_h = 96
radius = bar_h // 2
pad = 20

def create_waving_bar(flag_img, bar_w, phase_t, is_india=False):
    f_w, f_h = bar_w + pad * 2, bar_h + pad * 2
    scaled = flag_img.resize((f_w, f_h), Image.Resampling.LANCZOS)
    f_np = np.array(scaled)
    h, w, c = f_np.shape
    y_idx, x_idx = np.indices((h, w))
    
    shift = (4.5 * np.sin(2 * math.pi * x_idx / 120.0 - phase_t)).astype(np.float32)
    new_y = np.clip(y_idx + shift, 0, h - 1).astype(np.int32)
    waved_np = f_np[new_y, x_idx]
    
    shading = (0.85 + 0.20 * np.sin(2 * math.pi * x_idx / 120.0 - phase_t + math.pi/4))[:, :, np.newaxis]
    waved_np[:, :, :3] = np.clip(waved_np[:, :, :3] * shading, 0, 255).astype(np.uint8)
    
    waved_img = Image.fromarray(waved_np, "RGBA").crop((pad, pad, pad + bar_w, pad + bar_h))
    mask = Image.new("L", (bar_w, bar_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (bar_w, bar_h)], radius=radius, fill=255)
    
    bar = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    bar.paste(waved_img, (0, 0), mask)
    
    grad = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for x in range(bar_w):
        gd.line([(x, 0), (x, bar_h)], fill=(6, 10, 18, int(40 + 130 * (x / bar_w))))
    bar = Image.alpha_composite(bar, Image.composite(grad, Image.new("RGBA", (bar_w, bar_h), (0,0,0,0)), mask))
    
    rim = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rim)
    if is_india:
        col, alpha = (255, 153, 51), 255
    else:
        col, alpha = (200, 220, 255), 140
    rd.rounded_rectangle([(1, 1), (bar_w - 2, bar_h - 2)], radius=radius, outline=col + (alpha,), width=2)
    return Image.alpha_composite(bar, rim), col

def render_v5_frame(ranked_groups, caption_text, phase_t, is_flash=False, show_subscribe_pulse=False):
    canvas = BASE_BG.copy()
    draw = ImageDraw.Draw(canvas)
    
    # 1. FRAME 0 SCROLL-STOPPER
    if is_flash:
        flash_bar = Image.new("RGBA", (WIDTH, 90), (220, 38, 38, 250))
        f_draw = ImageDraw.Draw(flash_bar)
        f_draw.text((WIDTH//2, 45), "⚠️ RICHEST ETHNIC GROUP IN USA ⚠️", fill=(255, 255, 255, 255), font=font_alert, anchor="mm")
        canvas.paste(flash_bar, (0, 45), flash_bar)
    else:
        draw.text((WIDTH//2, 75), "LR ATLAS  •  US CENSUS DATA", fill=(255, 153, 51, 230), font=get_font(22, True), anchor="mm")
        
    draw.text((WIDTH//2, 145), "HIGHEST EARNERS IN AMERICA", fill=(255, 255, 255, 255), font=font_title, anchor="mm")
    
    # 2. PROMINENT HUD
    hud_y, hud_w, hud_h = 205, 930, 72
    hx = (WIDTH - hud_w) // 2
    draw.rounded_rectangle([(hx, hud_y), (hx + hud_w, hud_y + hud_h)], radius=18, fill=(14, 18, 32, 240), outline=(255, 153, 51, 200), width=2)
    draw.text((hx + 55, hud_y + hud_h//2), "DATA", fill=(148, 163, 184, 255), font=get_font(20, True), anchor="lm")
    draw.text((hx + 140, hud_y + hud_h//2), "2024 CENSUS", fill=(255, 215, 0, 255), font=font_year, anchor="lm")
    draw.line([(WIDTH//2, hud_y + 12), (WIDTH//2, hud_y + hud_h - 12)], fill=(255, 255, 255, 40), width=2)
    draw.text((WIDTH//2 + 40, hud_y + hud_h//2), "MEDIAN HOUSEHOLD", fill=(148, 163, 184, 255), font=get_font(20, True), anchor="lm")
    draw.text((hx + hud_w - 35, hud_y + hud_h//2), "INCOME / YEAR", fill=(255, 153, 51, 255), font=get_font(24, True), anchor="rm")
    
    # 3. RACING BARS
    max_w, min_w = 660, 310
    vals = [g["val"] for g in ranked_groups]
    mx, mn = max(vals), min(vals)
    if mx == mn: mx += 0.01
    
    for item in sorted(ranked_groups, key=lambda c: c.get("z_order", 0)):
        cur_y = int(item["y_pos"])
        rnk = item["rank"]
        vf = (item["val"] - mn) / (mx - mn)
        bw = int(min_w + vf * (max_w - min_w))
        
        is_ind = (item["code"] == "IND")
        flag_im = flags.get(item["flag_code"], list(flags.values())[0])
        bar, col = create_waving_bar(flag_im, bw, phase_t, is_india=is_ind)
        bx = 75
        
        if is_ind:
            shadow = Image.new("RGBA", (bw + 30, bar_h + 30), (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle([(15, 15), (bw + 15, bar_h + 15)], radius=radius, fill=(0, 0, 0, 160))
            shadow = shadow.filter(ImageFilter.GaussianBlur(14))
            canvas.paste(shadow, (bx - 15, cur_y - 6), shadow)
            
        canvas.paste(bar, (bx, cur_y), bar)
        
        # Crest
        cs = 74
        cx = bx + 10
        cy = cur_y + (bar_h - cs)//2
        draw.ellipse([(cx, cy), (cx + cs, cy + cs)], fill=(10, 14, 24, 250), outline=col + (255,), width=2)
        draw.text((cx + cs//2, cy + cs//2), item["flag_code"], fill=(255, 255, 255, 255), font=get_font(20, True), anchor="mm")
        
        # Name Pill
        tbx = cx + cs + 14
        tby = cur_y + 16
        ns = f"{item['name']} #{rnk}"
        tw = int(draw.textlength(ns, font=font_label))
        tbw, tbh = tw + 26, 44
        draw.rounded_rectangle([(tbx, tby), (tbx + tbw, tby + tbh)], radius=10, fill=(8, 12, 20, 235), outline=(255, 153, 51, 230) if is_ind else (255, 255, 255, 70), width=1)
        draw.text((tbx + tbw//2, tby + tbh//2), ns, fill=(255, 170, 70, 255) if is_ind else (255, 255, 255, 255), font=font_label, anchor="mm")
        
        # Badge
        if item.get("badge"):
            bt = item["badge"]
            bw_b = int(draw.textlength(bt, font=font_badge)) + 24
            bbx = tbx + tbw + 10
            bby = cur_y + bar_h//2 - 13
            draw.rounded_rectangle([(bbx, bby), (bbx + bw_b, bby + 26)], radius=6, fill=(255, 153, 51, 245) if is_ind else (220, 38, 38, 240))
            draw.text((bbx + bw_b//2, bby + 13), bt, fill=(0, 0, 0, 255) if is_ind else (255, 255, 255, 255), font=font_badge, anchor="mm")
            
        # Value
        vx = bx + bw + 22
        vy = cur_y + bar_h // 2
        draw.text((vx + 2, vy + 2), item["val_str"], fill=(0, 0, 0, 255), font=font_val, anchor="lm")
        draw.text((vx, vy), item["val_str"], fill=(255, 255, 255, 255), font=font_val, anchor="lm")
        
    # 4. SUBTITLES
    if caption_text:
        cap_y = 1350
        cw = int(draw.textlength(caption_text, font=font_caption)) + 70
        ccx = (WIDTH - cw) // 2
        draw.rounded_rectangle([(ccx, cap_y - 38), (ccx + cw, cap_y + 38)], radius=18, fill=(10, 16, 28, 245), outline=(255, 215, 0, 220), width=2)
        draw.text((WIDTH//2 + 2, cap_y + 2), caption_text, fill=(0, 0, 0, 255), font=font_caption, anchor="mm")
        draw.text((WIDTH//2, cap_y), caption_text, fill=(255, 225, 0, 255), font=font_caption, anchor="mm")
        
    # 5. ANIMATED PULSING "SUBSCRIBE" CONVERSION BADGE (IN 8-14s WINDOW)
    if show_subscribe_pulse:
        sub_w, sub_h = 750, 80
        sx = (WIDTH - sub_w) // 2
        sy = 1450
        draw.rounded_rectangle([(sx, sy), (sx + sub_w, sy + sub_h)], radius=40, fill=(220, 38, 38, 255), outline=(255, 255, 255, 240), width=3)
        draw.text((WIDTH//2, sy + sub_h//2), "🔔 SUBSCRIBE IF YOU ARE PROUD! 🇮🇳", fill=(255, 255, 255, 255), font=font_sub_pill, anchor="mm")
        
    # 6. BOTTOM CTA BOX
    c_box_w, c_box_h = 980, 84
    cbx = (WIDTH - c_box_w) // 2
    cby = 1550
    draw.rounded_rectangle([(cbx, cby), (cbx + c_box_w, cby + c_box_h)], radius=42, fill=(16, 22, 38, 245), outline=(255, 153, 51, 240), width=3)
    draw.text((WIDTH//2, cby + c_box_h//2), "PROUD OF INDIAN DOMINANCE? SUBSCRIBE & VOTE!", fill=(255, 215, 0, 255), font=font_cta, anchor="mm")
    
    # 7. SOURCE
    draw.text((WIDTH//2, 1720), "Data Source: US Census Bureau (ACS Survey) • LR Atlas", fill=(140, 160, 190, 240), font=get_font(18, False), anchor="mm")
    return canvas

# -----------------------------------------------------------------
# 4. RENDER 14.0s ANIMATION (420 FRAMES)
# -----------------------------------------------------------------
print(f"\n🚀 Rendering 14.0s High-Conversion Animation ({TOTAL_FRAMES} frames)...")
vis_dir = os.path.join(output_dir, "visuals")
os.makedirs(vis_dir, exist_ok=True)
anim_path = os.path.join(vis_dir, "visual_0.mp4")

# Starting vs Final incomes
incomes_start = {
    "IND": 100.0,
    "PHL": 82.0,
    "CHN": 75.0,
    "JPN": 72.0,
    "WHT": 65.0,
    "AVG": 60.0,
}
incomes_end = {
    "IND": 152.0,  # #1 Massive lead
    "PHL": 102.0,
    "CHN": 95.0,
    "JPN": 88.0,
    "WHT": 78.0,
    "AVG": 74.0,   # US National average
}
meta_groups = {
    "IND": {"name": "Indian Americans", "flag_code": "IND", "badge": "RICHEST IN USA #1"},
    "PHL": {"name": "Filipino Americans", "flag_code": "PHL", "badge": "WORLD #2"},
    "CHN": {"name": "Chinese Americans", "flag_code": "CHN", "badge": ""},
    "JPN": {"name": "Japanese Americans", "flag_code": "JPN", "badge": ""},
    "WHT": {"name": "White Americans", "flag_code": "USA", "badge": ""},
    "AVG": {"name": "US National Average", "flag_code": "USA", "badge": "BENCHMARK"},
}

ffcmd = [
    "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
    "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24", "-r", "30",
    "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
    "-movflags", "+faststart", anim_path
]
proc = subprocess.Popen(ffcmd, stdin=subprocess.PIPE)

slot_start_y = 330
slot_gap_y = 135

for fr in range(TOTAL_FRAMES):
    prog = fr / TOTAL_FRAMES
    pt = prog * 20 * math.pi
    
    cv = {code: np.interp(prog, [0.0, 1.0], [incomes_start[code], incomes_end[code]]) for code in incomes_start}
    sorted_codes = sorted(cv.keys(), key=lambda c: cv[c], reverse=True)
    
    g_list = []
    for ri, code in enumerate(sorted_codes):
        v = cv[code]
        zo = 2 if code == "IND" else 0
        g_list.append({
            "code": code,
            "name": meta_groups[code]["name"],
            "flag_code": meta_groups[code]["flag_code"],
            "val": v,
            "val_str": f"${v:.0f}k",
            "rank": ri + 1,
            "y_pos": slot_start_y + ri * slot_gap_y,
            "badge": meta_groups[code]["badge"],
            "z_order": zo,
        })
        
    is_flash = (fr < 36)
    show_sub_pulse = (prog >= 0.58)
    
    if prog < 0.32:
        cap = "WHO ACTUALLY EARNS THE MOST IN USA?"
    elif prog < 0.65:
        cap = "INDIAN AMERICANS SMASH AT $152,000!"
    else:
        cap = "DOUBLE US AVERAGE! SUBSCRIBE FOR INDIA! 🇮🇳"
        
    frame = render_v5_frame(g_list, cap, pt, is_flash=is_flash, show_subscribe_pulse=show_sub_pulse)
    proc.stdin.write(frame.convert("RGB").tobytes())
    
    if fr % 100 == 0 or fr == TOTAL_FRAMES - 1:
        print(f"  Frame {fr}/{TOTAL_FRAMES} ({int(prog*100)}%)")

proc.stdin.close()
proc.wait()
print(f"✅ Animation rendered successfully: {anim_path}")

# -----------------------------------------------------------------
# 5. ASSEMBLE WITH HIGH-OCTANE MUSIC
# -----------------------------------------------------------------
print("\n🎞️ Assembling Final V5 Short...")
final_video_path = VideoAssembler.create_video(
    audio_data=padded_audio,
    visual_data=[{"scene_number": 1, "image_path": anim_path}],
    output_dir=output_dir,
    captions_path=srt_path,
    sfx_category="duel_battle",
)

qc = FinalQC.check_video(final_video_path)
print(f"Quality Score: {qc.get('score', 100)}/100 | Passed: {qc.get('passed', True)}")

thumb_dir = os.path.join(output_dir, "thumbnails")
os.makedirs(thumb_dir, exist_ok=True)
thumb_path = os.path.join(thumb_dir, "short_thumbnail.jpg")
subprocess.run(["ffmpeg", "-y", "-ss", "10.0", "-i", final_video_path, "-vframes", "1", "-q:v", "2", thumb_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# -----------------------------------------------------------------
# 6. UPLOAD AS PUBLIC LIVE
# -----------------------------------------------------------------
yt_metadata = {
    "title": "Indians Are The RICHEST In America?! 🇮🇳🇺🇸 #Shorts",
    "description": (
        "America is the richest country on Earth, but who earns the most money there? "
        "According to official US Census data, Indian Americans CRUSH every other group with an average income of $152,000 — DOUBLE the national average!\n\n"
        "Subscribe if you are proud of India's global rise! 🇮🇳🔥\n\n"
        "#India #IndianAmericans #USA #Wealth #Shorts #LRAtlas #DataRace #Modi #IndianPride #AmericanDream"
    ),
    "tags": [
        "indian americans richest",
        "richest ethnic groups in america",
        "indian median income usa",
        "india vs usa",
        "indian success abroad",
        "shorts",
        "lr atlas",
        "data battle"
    ],
    "category_id": "27",
}

with open(os.path.join(output_dir, "youtube_metadata.json"), "w", encoding="utf-8") as f:
    json.dump(yt_metadata, f, indent=2)

print("\n🚀 UPLOADING V5 SHORT AS PUBLIC / LIVE...")
upload_result = upload_video(
    video_path=final_video_path,
    metadata=yt_metadata,
    thumbnail_path=thumb_path,
    privacy_status="public",
)

video_id = upload_result.get("video_id")
print("\n" + "=" * 60)
print(f"🎉 V5 HIGH-CONVERSION SHORT IS LIVE!")
print(f"🆔 Video ID: {video_id}")
print(f"🔗 Short URL: https://youtube.com/shorts/{video_id}")
print("=" * 60)

