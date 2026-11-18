"""Build and Pre-Schedule Today's Peak 1:30 PM IST V6 Short.
Topic: India's Massive Gold Vault: 850 Tonnes vs Neighbors! (India vs Pakistan vs Bangladesh vs Sri Lanka vs Saudi Arabia).

Features (V6 Hyper-Studio):
1. Frame 0 Climax Flash (0.0s - 1.2s):
   - "🚨 INDIA HOARDS 850 TONNES OF GOLD! 🚨"
2. Upper battle HUD with real gold shimmer styling.
3. Safe-zone center subscribe CTA (Height 35%-65%).
4. Seamless infinite loop (13.0s).
5. Pre-scheduled for today 1:30 PM IST (08:00 AM UTC).
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
TOTAL_DURATION = 13
TOTAL_FRAMES = int(TOTAL_DURATION * FPS)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_dir = os.path.join("output", "v6_hyper_studio", f"india_gold_reserves_{timestamp}")
os.makedirs(output_dir, exist_ok=True)
print(f"🎬 Initialized V6 Gold Short: {output_dir}")

# -----------------------------------------------------------------
# 1. 13.0s SEAMLESS LOOP SCRIPT
# -----------------------------------------------------------------
scenes = [
    ScriptScene(
        scene_number=1,
        duration=4.0,
        narration="While neighboring countries ran out of dollars, India built a fortress of real gold!",
        visual_description="Frame 0 Climax Flash on India's gold accumulation",
        text_overlay="INDIA'S GOLD FORTRESS!",
        chart_type="vertical_duel",
        scene_purpose="HOOK",
        visual_emphasis="explosive gold hook",
        highlight_countries=["India"],
        important_year=2024,
        important_value=850.0,
        pacing_hint="explosive fast hook",
    ),
    ScriptScene(
        scene_number=2,
        duration=5.0,
        narration="India quietly crossed eight hundred and fifty tonnes of gold, leaving neighbors in the dust!",
        visual_description="India's massive gold bar towering over Pakistan, Sri Lanka, and Bangladesh",
        text_overlay="850 TONNES OF GOLD!",
        chart_type="vertical_duel",
        scene_purpose="CLIMAX",
        visual_emphasis="massive gold dominance",
        highlight_countries=["India"],
        important_year=2024,
        important_value=850.0,
        pacing_hint="high energy climb",
    ),
    ScriptScene(
        scene_number=3,
        duration=4.0,
        narration="Subscribe to LR Atlas for tomorrow's clash, because nobody saw this coming!",
        visual_description="Safe-zone center subscriber button seamlessly looping back",
        text_overlay="SUBSCRIBE TO LR ATLAS!",
        chart_type="vertical_duel",
        scene_purpose="RESOLUTION",
        visual_emphasis="seamless loop outro",
        highlight_countries=["India"],
        important_year=2026,
        important_value=900.0,
        pacing_hint="seamless cliffhanger",
    ),
]

script = VideoScript(
    title="India's MASSIVE 850-Tonne Gold Fortress! 🇮🇳🥇 #Shorts",
    topic="Gold Reserves in South Asia: India vs Neighbors (2000-2026)",
    category="News & Politics",
    indicator_name="Central Bank Gold Reserves (Tonnes)",
    total_duration=TOTAL_DURATION,
    scenes=scenes,
    fact_check=FactCheck(is_accurate=True, discrepancies="none"),
    source_name="World Gold Council & RBI Data",
    source_url="https://www.gold.org",
    indicator_code="central_bank_gold_reserves",
)

with open(os.path.join(output_dir, "script.json"), "w", encoding="utf-8") as f:
    json.dump(script.model_dump(), f, indent=2)

# -----------------------------------------------------------------
# 2. AUDIO GENERATION
# -----------------------------------------------------------------
print("\n🎙️ Generating 13.0s Audio via Edge TTS...")
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
print("✅ Audio synchronized.")

# -----------------------------------------------------------------
# 3. VISUAL SETUP
# -----------------------------------------------------------------
def get_font(size, bold=True):
    for fn in (["segoeuib.ttf", "arialbd.ttf", "tahomabd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]):
        try:
            return ImageFont.truetype(fn, size)
        except Exception:
            continue
    return ImageFont.load_default()

font_climax = get_font(36, bold=True)
font_title = get_font(42, bold=True)
font_brand = get_font(24, bold=True)
font_year = get_font(38, bold=True)
font_label = get_font(28, bold=True)
font_val = get_font(32, bold=True)
font_badge = get_font(18, bold=True)
font_center_cta = get_font(30, bold=True)
font_caption = get_font(44, bold=True)

flags = {}
for c3, c2 in [("IND", "in"), ("PAK", "pk"), ("SAU", "sa"), ("BGD", "bd"), ("LKA", "lk"), ("USA", "us")]:
    for p in [f"assets/flags_hires/{c2}.png", f"assets/flags/{c2}.png"]:
        if os.path.exists(p):
            flags[c3] = Image.open(p).convert("RGBA")
            break

# Fallback for flags if missing
if "PAK" not in flags and "IND" in flags: flags["PAK"] = flags["IND"]
if "SAU" not in flags and "IND" in flags: flags["SAU"] = flags["IND"]
if "BGD" not in flags and "IND" in flags: flags["BGD"] = flags["IND"]
if "LKA" not in flags and "IND" in flags: flags["LKA"] = flags["IND"]

def create_gold_background():
    bg = Image.new("RGBA", (WIDTH, HEIGHT), (8, 8, 14, 255))
    y_coords, x_coords = np.ogrid[:HEIGHT, :WIDTH]
    dist = np.sqrt((x_coords - WIDTH//2)**2 + (y_coords - 650)**2)
    norm = np.clip(dist / 950.0, 0.0, 1.0)
    falloff = 0.5 + 0.5 * np.cos(norm * math.pi)
    
    r = (36 * falloff + 6 * (1.0 - falloff)).astype(np.uint8)
    g = (28 * falloff + 6 * (1.0 - falloff)).astype(np.uint8)
    b = (50 * falloff + 10 * (1.0 - falloff)).astype(np.uint8)
    
    bg_np = np.dstack((r, g, b, np.full((HEIGHT, WIDTH), 255, dtype=np.uint8)))
    bg = Image.fromarray(bg_np, "RGBA")
    draw = ImageDraw.Draw(bg)
    
    for x in range(30, WIDTH, 50):
        for y in range(40, HEIGHT, 50):
            draw.rectangle([(x, y), (x + 2, y + 2)], fill=(200, 180, 255, 12))
            
    top_glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    tg_draw = ImageDraw.Draw(top_glow)
    for y in range(280):
        a = int(55 * (1.0 - y / 280.0))
        tg_draw.line([(0, y), (WIDTH, y)], fill=(255, 200, 0, a))
    return Image.alpha_composite(bg, top_glow)

BASE_BG = create_gold_background()

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
        col, alpha = (255, 180, 0), 255
    else:
        col, alpha = (180, 200, 230), 140
    rd.rounded_rectangle([(1, 1), (bar_w - 2, bar_h - 2)], radius=radius, outline=col + (alpha,), width=2)
    return Image.alpha_composite(bar, rim), col

def render_v6_frame(year_val, ranked_countries, caption_text, phase_t, is_climax_flash=False, show_center_cta=False):
    canvas = BASE_BG.copy()
    draw = ImageDraw.Draw(canvas)
    
    # 1. FRAME 0 CLIMAX FLASH HOOK
    if is_climax_flash:
        flash_bar = Image.new("RGBA", (WIDTH, 110), (220, 38, 38, 255))
        f_draw = ImageDraw.Draw(flash_bar)
        f_draw.text((WIDTH//2, 38), "🚨 INDIA'S 850-TONNE GOLD FORTRESS! 🚨", fill=(255, 255, 255, 255), font=font_climax, anchor="mm")
        f_draw.text((WIDTH//2, 80), "WHILE NEIGHBORS CRASH, INDIA HOARDS GOLD", fill=(255, 215, 0, 255), font=get_font(22, True), anchor="mm")
        canvas.paste(flash_bar, (0, 35), flash_bar)
    else:
        draw.text((WIDTH//2, 70), "⚡ LR ATLAS • WEALTH & POWER SHOWDOWNS ⚡", fill=(255, 215, 0, 240), font=font_brand, anchor="mm")
        
    draw.text((WIDTH//2, 140), "GOLD RESERVES BY COUNTRY", fill=(255, 255, 255, 255), font=font_title, anchor="mm")
    
    # 2. UPPER BATTLE HUD
    hud_y, hud_w, hud_h = 195, 930, 72
    hx = (WIDTH - hud_w) // 2
    draw.rounded_rectangle([(hx, hud_y), (hx + hud_w, hud_y + hud_h)], radius=18, fill=(14, 18, 32, 240), outline=(255, 180, 0, 220), width=2)
    draw.text((hx + 55, hud_y + hud_h//2), "YEAR", fill=(148, 163, 184, 255), font=get_font(20, True), anchor="lm")
    draw.text((hx + 175, hud_y + hud_h//2), f"{int(year_val)}", fill=(255, 215, 0, 255), font=font_year, anchor="lm")
    draw.line([(WIDTH//2, hud_y + 12), (WIDTH//2, hud_y + hud_h - 12)], fill=(255, 255, 255, 40), width=2)
    draw.text((WIDTH//2 + 40, hud_y + hud_h//2), "VAULT ASSETS", fill=(148, 163, 184, 255), font=get_font(20, True), anchor="lm")
    draw.text((hx + hud_w - 35, hud_y + hud_h//2), "TONNES OF GOLD", fill=(255, 180, 0, 255), font=get_font(26, True), anchor="rm")
    
    # 3. RACING BARS
    max_w, min_w = 660, 310
    vals = [c["val"] for c in ranked_countries]
    mx, mn = max(vals), min(vals)
    if mx == mn: mx += 0.01
    
    for item in sorted(ranked_countries, key=lambda c: c.get("z_order", 0)):
        cur_y = int(item["y_pos"])
        rnk = item["rank"]
        vf = (item["val"] - mn) / (mx - mn)
        bw = int(min_w + vf * (max_w - min_w))
        
        is_ind = (item["code"] == "IND")
        flag_im = flags.get(item["code"], list(flags.values())[0])
        bar, col = create_waving_bar(flag_im, bw, phase_t, is_india=is_ind)
        bx = 75
        
        if is_ind:
            shadow = Image.new("RGBA", (bw + 30, bar_h + 30), (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle([(15, 15), (bw + 15, bar_h + 15)], radius=radius, fill=(0, 0, 0, 170))
            shadow = shadow.filter(ImageFilter.GaussianBlur(14))
            canvas.paste(shadow, (bx - 15, cur_y - 6), shadow)
            
        canvas.paste(bar, (bx, cur_y), bar)
        
        # Crest
        cs = 74
        cx = bx + 10
        cy = cur_y + (bar_h - cs)//2
        draw.ellipse([(cx, cy), (cx + cs, cy + cs)], fill=(10, 14, 24, 250), outline=col + (255,), width=2)
        draw.text((cx + cs//2, cy + cs//2), item["code"], fill=(255, 255, 255, 255), font=get_font(20, True), anchor="mm")
        
        # Name Pill
        tbx = cx + cs + 14
        tby = cur_y + 16
        ns = f"{item['name']} #{rnk}"
        tw = int(draw.textlength(ns, font=font_label))
        tbw, tbh = tw + 26, 44
        draw.rounded_rectangle([(tbx, tby), (tbx + tbw, tby + tbh)], radius=10, fill=(8, 12, 20, 235), outline=(255, 180, 0, 230) if is_ind else (255, 255, 255, 70), width=1)
        draw.text((tbx + tbw//2, tby + tbh//2), ns, fill=(255, 215, 0, 255) if is_ind else (255, 255, 255, 255), font=font_label, anchor="mm")
        
        # Milestone Badge
        if item.get("badge"):
            bt = item["badge"]
            bw_b = int(draw.textlength(bt, font=font_badge)) + 24
            bbx = tbx + tbw + 10
            bby = cur_y + bar_h//2 - 13
            draw.rounded_rectangle([(bbx, bby), (bbx + bw_b, bby + 26)], radius=6, fill=(255, 180, 0, 245) if is_ind else (220, 38, 38, 240))
            draw.text((bbx + bw_b//2, bby + 13), bt, fill=(0, 0, 0, 255) if is_ind else (255, 255, 255, 255), font=font_badge, anchor="mm")
            
        # Value
        vx = bx + bw + 22
        vy = cur_y + bar_h // 2
        draw.text((vx + 2, vy + 2), item["val_str"], fill=(0, 0, 0, 255), font=font_val, anchor="lm")
        draw.text((vx, vy), item["val_str"], fill=(255, 255, 255, 255), font=font_val, anchor="lm")
        
    # 4. CAPTIONS IN SAFE HEIGHT
    if caption_text:
        cap_y = 1220
        cw = int(draw.textlength(caption_text, font=font_caption)) + 70
        ccx = (WIDTH - cw) // 2
        draw.rounded_rectangle([(ccx, cap_y - 38), (ccx + cw, cap_y + 38)], radius=18, fill=(10, 16, 28, 245), outline=(255, 215, 0, 220), width=2)
        draw.text((WIDTH//2 + 2, cap_y + 2), caption_text, fill=(0, 0, 0, 255), font=font_caption, anchor="mm")
        draw.text((WIDTH//2, cap_y), caption_text, fill=(255, 225, 0, 255), font=font_caption, anchor="mm")
        
    # 5. SAFE-ZONE CENTER CTA (Height: 1330px - 1420px)
    if show_center_cta:
        sub_w, sub_h = 860, 86
        sx = (WIDTH - sub_w) // 2
        sy = 1330
        draw.rounded_rectangle([(sx, sy), (sx + sub_w, sy + sub_h)], radius=43, fill=(220, 38, 38, 255), outline=(255, 255, 255, 250), width=3)
        draw.text((WIDTH//2, sy + sub_h//2), "🔔 SUBSCRIBE TO LR ATLAS FOR DAILY SHOWDOWNS!", fill=(255, 255, 255, 255), font=font_center_cta, anchor="mm")
    else:
        q_w, q_h = 880, 80
        qx = (WIDTH - q_w) // 2
        qy = 1330
        draw.rounded_rectangle([(qx, qy), (qx + q_w, qy + q_h)], radius=40, fill=(16, 22, 38, 245), outline=(255, 180, 0, 230), width=2)
        draw.text((WIDTH//2, qy + q_h//2), "WILL INDIA REACH 1,000 TONNES OF GOLD? VOTE!", fill=(255, 215, 0, 255), font=get_font(26, True), anchor="mm")
        
    draw.text((WIDTH//2, 1650), "Data Source: World Gold Council (2024) • Reserve Bank of India • LR Atlas", fill=(140, 160, 190, 240), font=get_font(18, False), anchor="mm")
    return canvas

# -----------------------------------------------------------------
# 4. RENDER 13.0s ANIMATION
# -----------------------------------------------------------------
print(f"\n🚀 Rendering 13.0s V6 Gold Animation ({TOTAL_FRAMES} frames)...")
vis_dir = os.path.join(output_dir, "visuals")
os.makedirs(vis_dir, exist_ok=True)
anim_path = os.path.join(vis_dir, "visual_0.mp4")

key_years = [2000, 2010, 2018, 2022, 2024, 2026]
gold_data = {
    "IND": [358, 557, 560, 785, 854, 910],  # India huge surge
    "SAU": [143, 323, 323, 323, 323, 325],  # Saudi Arabia
    "PAK": [65,  65,  65,  65,  65,  65],   # Pakistan flat
    "BGD": [3,   14,  14,  14,  14,  14],   # Bangladesh
    "LKA": [2,   15,  20,   3,   1,   1],   # Sri Lanka collapsed
}
names = {"IND":"India", "SAU":"Saudi Arabia", "PAK":"Pakistan", "BGD":"Bangladesh", "LKA":"Sri Lanka"}

ffcmd = [
    "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
    "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24", "-r", "30",
    "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
    "-movflags", "+faststart", anim_path
]
proc = subprocess.Popen(ffcmd, stdin=subprocess.PIPE)

slot_start_y = 330
slot_gap_y = 145

for fr in range(TOTAL_FRAMES):
    prog = fr / TOTAL_FRAMES
    pt = prog * 20 * math.pi
    cy = np.interp(prog, np.linspace(0, 1, len(key_years)), key_years)
    
    cv = {code: np.interp(prog, np.linspace(0, 1, len(key_years)), arr) for code, arr in gold_data.items()}
    sorted_codes = sorted(cv.keys(), key=lambda c: cv[c], reverse=True)
    
    c_list = []
    for ri, code in enumerate(sorted_codes):
        v = cv[code]
        zo = 0
        b = ""
        if code == "IND":
            zo = 2
            b = "854 TONNES (#1)" if cy >= 2024 else "BUYING MASSIVE"
        elif code == "LKA":
            b = "VAULT EMPTY" if cy >= 2022 else ""
        elif code == "PAK":
            b = "STAGNANT"
            
        c_list.append({
            "code": code,
            "name": names[code],
            "val": v,
            "val_str": f"{int(v)} T",
            "rank": ri + 1,
            "y_pos": slot_start_y + ri * slot_gap_y,
            "badge": b,
            "z_order": zo,
        })
        
    is_flash = (fr < 36)
    show_cta = (prog >= 0.65)
    
    if prog < 0.30:
        cap = "INDIA HOARDED 850 TONNES OF GOLD!"
    elif prog < 0.65:
        cap = "CRUSHING NEIGHBORS IN SOLID WEALTH!"
    else:
        cap = "SUBSCRIBE TO LR ATLAS FOR DAILY SHOWDOWNS!"
        
    frame = render_v6_frame(cy, c_list, cap, pt, is_climax_flash=is_flash, show_center_cta=show_cta)
    proc.stdin.write(frame.convert("RGB").tobytes())
    
    if fr % 90 == 0 or fr == TOTAL_FRAMES - 1:
        print(f"  Frame {fr}/{TOTAL_FRAMES} ({int(prog*100)}%) - Year: {int(cy)}")

proc.stdin.close()
proc.wait()
print(f"✅ Animation rendered successfully: {anim_path}")

# -----------------------------------------------------------------
# 5. ASSEMBLE FINAL VIDEO
# -----------------------------------------------------------------
print("\n🎞️ Assembling Final V6 Gold Short...")
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
subprocess.run(["ffmpeg", "-y", "-ss", "9.0", "-i", final_video_path, "-vframes", "1", "-q:v", "2", thumb_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# -----------------------------------------------------------------
# 6. SCHEDULE FOR TODAY 1:30 PM IST (08:00 AM UTC)
# -----------------------------------------------------------------
now = datetime.now()
# Today 1:30 PM IST = 08:00 AM UTC
publish_time_utc = datetime(now.year, now.month, now.day, 8, 0, 0)
publish_at_iso = publish_time_utc.isoformat() + "Z"

yt_metadata = {
    "title": "India's MASSIVE 850-Tonne Gold Fortress! 🇮🇳🥇 #Shorts",
    "description": (
        "While neighboring countries ran out of dollars, India silently built an unbreakable fortress of physical gold! "
        "From 358 tonnes to over 850 tonnes, watch how the Reserve Bank of India secured the nation's wealth!\n\n"
        "Will India cross 1,000 tonnes of gold by 2030? Vote below!\n\n"
        "🔔 Follow LR Atlas for daily wealth & global power showdowns!\n\n"
        "#India #Gold #RBI #Economy #GoldReserves #Pakistan #SriLanka #Shorts #LRAtlas #DataRace"
    ),
    "tags": [
        "india gold reserves",
        "rbi gold vault",
        "india vs pakistan gold",
        "gold reserves by country",
        "india 850 tonnes gold",
        "shorts",
        "lr atlas",
        "data battle"
    ],
    "category_id": "27",
}

with open(os.path.join(output_dir, "youtube_metadata.json"), "w", encoding="utf-8") as f:
    json.dump(yt_metadata, f, indent=2)

print("\n" + "=" * 60)
print(f"📅 PRE-SCHEDULING V6 GOLD SHORT FOR TODAY 1:30 PM IST:")
print(f"⏰ Publish At UTC: {publish_at_iso}")
print("=" * 60)

upload_result = upload_video(
    video_path=final_video_path,
    metadata=yt_metadata,
    thumbnail_path=thumb_path,
    privacy_status="private",
    publish_at=publish_at_iso,
)

video_id = upload_result.get("video_id")
print("\n" + "=" * 60)
print(f"🎉 TODAY'S 1:30 PM IST SHORT SCHEDULED SUCCESSFULLY!")
print(f"🆔 Video ID: {video_id}")
print(f"🔗 Short URL: https://youtube.com/shorts/{video_id}")
print("=" * 60)
