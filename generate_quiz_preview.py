"""Automated 10-Second High-Conversion Quiz / Trivia Engine.
Concept: "Guess The Country in 5 Seconds!"
Structure (Total: 10.0s):
- 0.0s - 3.5s: Hook + Clue 1 & 2 ("Only 5% can guess this country from 3 clues!")
- 3.5s - 7.0s: Clue 3 + Ticking Circular Countdown Bar (5... 4... 3... 2... 1...)
- 7.0s - 10.0s: Answer Reveal with Country Flag Explosion + High-Voltage Voiceover:
  "It's JAPAN! Subscribe if you got it right on the first try!"
"""

import os
import sys
import math
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import settings
settings.VIDEO_FORMAT = "portrait"

from app.audio.tts import TTSEngine
from app.models import VideoScript, ScriptScene, FactCheck
from app.video.assembler import VideoAssembler

WIDTH = 1080
HEIGHT = 1920
FPS = 30
TOTAL_DURATION = 10.0
TOTAL_FRAMES = int(TOTAL_DURATION * FPS)

output_dir = os.path.join("output", "quiz_engine_preview")
os.makedirs(output_dir, exist_ok=True)
print(f"🎬 Initialized Quiz Engine Preview: {output_dir}")

# -------------------------------------------------------------
# 1. 10.0s HIGH-ENERGY SCRIPT
# -------------------------------------------------------------
scenes = [
    ScriptScene(
        scene_number=1,
        duration=3.5,
        narration="Only five percent can guess this country in five seconds! Clue one: It has over six thousand islands.",
        visual_description="Fast hook with clues appearing on screen",
        text_overlay="GUESS THE COUNTRY!",
        chart_type="vertical_duel",
        scene_purpose="HOOK",
        visual_emphasis="quiz hook",
        highlight_countries=["Japan"],
        important_year=2024,
        important_value=1.0,
        pacing_hint="explosive hook",
    ),
    ScriptScene(
        scene_number=2,
        duration=3.5,
        narration="Clue two: Home to the world's most bullet trains. Three, two, one...",
        visual_description="Countdown timer ticking down with final clue",
        text_overlay="CAN YOU GUESS IT?",
        chart_type="vertical_duel",
        scene_purpose="CLIMAX",
        visual_emphasis="ticking countdown",
        highlight_countries=["Japan"],
        important_year=2024,
        important_value=1.0,
        pacing_hint="tension countdown",
    ),
    ScriptScene(
        scene_number=3,
        duration=3.0,
        narration="It's Japan! Subscribe if you got it right!",
        visual_description="Big explosive reveal of Japan flag with subscribe prompt",
        text_overlay="IT'S JAPAN! 🇯🇵",
        chart_type="vertical_duel",
        scene_purpose="RESOLUTION",
        visual_emphasis="answer reveal",
        highlight_countries=["Japan"],
        important_year=2024,
        important_value=1.0,
        pacing_hint="triumphant answer",
    ),
]

script = VideoScript(
    title="Only 5% Can Guess This Country in 5s! 🧠🇯🇵 #Shorts #Quiz",
    topic="Guess the Country Trivia: Japan",
    category="Entertainment",
    indicator_name="Quiz Score",
    total_duration=TOTAL_DURATION,
    scenes=scenes,
    fact_check=FactCheck(is_accurate=True, discrepancies="none"),
    source_name="Geography Trivia Labs",
    source_url="https://geography.org",
    indicator_code="country_quiz_trivia",
)

# -------------------------------------------------------------
# 2. AUDIO GENERATION
# -------------------------------------------------------------
print("\n🎙️ Generating 10s High-Velocity Quiz Narration...")
audio_dir = os.path.join(output_dir, "audio")
os.makedirs(audio_dir, exist_ok=True)
audio_data = TTSEngine.generate_narration(script=script, output_dir=audio_dir, voice="en-US-AndrewNeural")
padded_audio = VideoAssembler.align_landscape_audio(audio_data=audio_data, output_dir=output_dir, target_total_duration=TOTAL_DURATION)

# -------------------------------------------------------------
# 3. QUIZ VISUAL ENGINE (PIL)
# -------------------------------------------------------------
def get_font(size, bold=True):
    for fn in (["segoeuib.ttf", "arialbd.ttf", "tahomabd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]):
        try: return ImageFont.truetype(fn, size)
        except Exception: continue
    return ImageFont.load_default()

font_header = get_font(42, bold=True)
font_sub_header = get_font(26, bold=True)
font_clue_num = get_font(24, bold=True)
font_clue_text = get_font(34, bold=True)
font_timer = get_font(90, bold=True)
font_reveal_title = get_font(48, bold=True)
font_reveal_country = get_font(84, bold=True)
font_sub_btn = get_font(36, bold=True)

# Load Japan flag
flag_path = "assets/flags_hires/jp.png"
if not os.path.exists(flag_path): flag_path = "assets/flags/jp.png"
japan_flag = Image.open(flag_path).convert("RGBA") if os.path.exists(flag_path) else Image.new("RGBA", (300, 200), (255, 255, 255, 255))

def create_studio_bg():
    bg = Image.new("RGBA", (WIDTH, HEIGHT), (10, 12, 22, 255))
    draw = ImageDraw.Draw(bg)
    # Dot pattern
    for x in range(30, WIDTH, 50):
        for y in range(40, HEIGHT, 50):
            draw.rectangle([(x, y), (x+2, y+2)], fill=(120, 140, 220, 15))
    # Ambient Top Gold/Purple Glow
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
    g_draw = ImageDraw.Draw(glow)
    for y in range(300):
        a = int(60 * (1.0 - y/300.0))
        g_draw.line([(0, y), (WIDTH, y)], fill=(138, 43, 226, a))
    return Image.alpha_composite(bg, glow)

BASE_BG = create_studio_bg()

def render_quiz_frame(progress, frame_num):
    canvas = BASE_BG.copy()
    draw = ImageDraw.Draw(canvas)
    
    # 1. TOP HEADER BANNER
    h_w, h_h = 960, 120
    hx = (WIDTH - h_w) // 2
    draw.rounded_rectangle([(hx, 80), (hx + h_w, 80 + h_h)], radius=24, fill=(20, 24, 45, 240), outline=(255, 215, 0, 220), width=3)
    draw.text((WIDTH//2, 115), "⚡ 10-SECOND IQ TEST ⚡", fill=(255, 215, 0, 255), font=font_sub_header, anchor="mm")
    draw.text((WIDTH//2, 160), "GUESS THE COUNTRY IN 5 SECONDS!", fill=(255, 255, 255, 255), font=font_header, anchor="mm")
    
    # PHASE 1: GUESSING MODE (0.0s to 7.0s -> prog < 0.70)
    if progress < 0.70:
        # Clue 1 Card (Appears at 0.0s)
        c1_w, c1_h = 940, 140
        c1_x = (WIDTH - c1_w) // 2
        draw.rounded_rectangle([(c1_x, 260), (c1_x + c1_w, 260 + c1_h)], radius=20, fill=(18, 22, 38, 245), outline=(59, 130, 246, 200), width=2)
        draw.text((c1_x + 40, 260 + 35), "CLUE 1", fill=(96, 165, 250, 255), font=font_clue_num, anchor="lm")
        draw.text((c1_x + 40, 260 + 85), "🏝️ Has Over 6,800 Islands", fill=(255, 255, 255, 255), font=font_clue_text, anchor="lm")
        
        # Clue 2 Card (Appears at 1.8s -> prog > 0.18)
        if progress >= 0.18:
            c2_w, c2_h = 940, 140
            c2_x = (WIDTH - c2_w) // 2
            draw.rounded_rectangle([(c2_x, 430), (c2_x + c2_w, 430 + c2_h)], radius=20, fill=(18, 22, 38, 245), outline=(147, 51, 234, 200), width=2)
            draw.text((c2_x + 40, 430 + 35), "CLUE 2", fill=(192, 132, 252, 255), font=font_clue_num, anchor="lm")
            draw.text((c2_x + 40, 430 + 85), "🚄 World's Most Bullet Trains (Shinkansen)", fill=(255, 255, 255, 255), font=font_clue_text, anchor="lm")
            
        # Clue 3 Card (Appears at 3.5s -> prog > 0.35)
        if progress >= 0.35:
            c3_w, c3_h = 940, 140
            c3_x = (WIDTH - c3_w) // 2
            draw.rounded_rectangle([(c3_x, 600), (c3_x + c3_w, 600 + c3_h)], radius=20, fill=(18, 22, 38, 245), outline=(245, 158, 11, 220), width=2)
            draw.text((c3_x + 40, 600 + 35), "CLUE 3", fill=(251, 191, 36, 255), font=font_clue_num, anchor="lm")
            draw.text((c3_x + 40, 600 + 85), "🍣 Capital Famous For Cherry Blossoms", fill=(255, 255, 255, 255), font=font_clue_text, anchor="lm")
            
        # COUNTDOWN TIMER CIRCLE (Appears from 3.5s to 7.0s)
        if progress >= 0.35:
            timer_prog = (progress - 0.35) / 0.35  # 0.0 to 1.0
            time_left = max(1, math.ceil(5 * (1.0 - timer_prog)))
            
            circle_center = (WIDTH // 2, 940)
            circle_r = 130
            
            # Background track
            draw.ellipse([circle_center[0]-circle_r, circle_center[1]-circle_r, circle_center[0]+circle_r, circle_center[1]+circle_r], fill=(14, 18, 32, 240), outline=(50, 60, 90, 180), width=8)
            
            # Sweeping countdown arc
            start_angle = -90
            end_angle = -90 + int(360 * (1.0 - timer_prog))
            draw.arc([circle_center[0]-circle_r, circle_center[1]-circle_r, circle_center[0]+circle_r, circle_center[1]+circle_r], start=start_angle, end=end_angle, fill=(239, 68, 68) if time_left <= 2 else (245, 158, 11), width=12)
            
            # Timer Number
            draw.text(circle_center, str(time_left), fill=(239, 68, 68, 255) if time_left <= 2 else (255, 255, 255, 255), font=font_timer, anchor="mm")
            
        # Bottom teaser text
        draw.text((WIDTH//2, 1250), "TYPE YOUR GUESS IN THE COMMENTS! 👇", fill=(255, 215, 0, 240), font=get_font(28, True), anchor="mm")
        
    # PHASE 2: ANSWER REVEAL & EXPLOSION (7.0s to 10.0s -> prog >= 0.70)
    else:
        reveal_p = (progress - 0.70) / 0.30
        
        # Big Reveal Card
        rc_w, rc_h = 960, 680
        rc_x = (WIDTH - rc_w) // 2
        rc_y = 280
        draw.rounded_rectangle([(rc_x, rc_y), (rc_x + rc_w, rc_y + rc_h)], radius=32, fill=(16, 20, 36, 250), outline=(255, 215, 0, 250), width=4)
        
        draw.text((WIDTH//2, rc_y + 80), "THE ANSWER IS...", fill=(200, 220, 255, 255), font=font_reveal_title, anchor="mm")
        
        # Big Flag in Center
        flag_scaled = japan_flag.resize((360, 240), Image.Resampling.LANCZOS)
        f_mask = Image.new("L", (360, 240), 0)
        ImageDraw.Draw(f_mask).rounded_rectangle([(0,0),(360, 240)], radius=20, fill=255)
        canvas.paste(flag_scaled, (WIDTH//2 - 180, rc_y + 160), f_mask)
        
        # Flag border
        draw.rounded_rectangle([(WIDTH//2 - 180, rc_y + 160), (WIDTH//2 + 180, rc_y + 400)], radius=20, outline=(255, 215, 0, 220), width=3)
        
        # Huge Country Name
        draw.text((WIDTH//2, rc_y + 490), "JAPAN 🇯🇵", fill=(255, 255, 255, 255), font=font_reveal_country, anchor="mm")
        draw.text((WIDTH//2, rc_y + 580), "Capital: Tokyo  •  Population: 125M", fill=(148, 163, 184, 255), font=get_font(26, True), anchor="mm")
        
        # PULSING HIGH-CONVERSION SUBSCRIBE BUTTON (Below reveal)
        pulse = int(10 * math.sin(reveal_p * 8 * math.pi))
        btn_w, btn_h = 920 + pulse, 110 + pulse
        bx = (WIDTH - btn_w) // 2
        by = 1060
        draw.rounded_rectangle([(bx, by), (bx + btn_w, by + btn_h)], radius=55, fill=(220, 38, 38, 255), outline=(255, 255, 255, 250), width=4)
        draw.text((WIDTH//2, by + btn_h//2), "🔔 SUBSCRIBE IF YOU GOT IT RIGHT! 🧠", fill=(255, 255, 255, 255), font=font_sub_btn, anchor="mm")
        
    return canvas

# -------------------------------------------------------------
# 4. RENDER ANIMATION (300 FRAMES)
# -------------------------------------------------------------
print(f"\n🚀 Rendering 10.0s Quiz Animation ({TOTAL_FRAMES} frames)...")
vis_dir = os.path.join(output_dir, "visuals")
os.makedirs(vis_dir, exist_ok=True)
anim_path = os.path.join(vis_dir, "visual_0.mp4")

ffcmd = [
    "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
    "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24", "-r", "30",
    "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
    "-movflags", "+faststart", anim_path
]
proc = subprocess.Popen(ffcmd, stdin=subprocess.PIPE)

for fr in range(TOTAL_FRAMES):
    prog = fr / TOTAL_FRAMES
    frame = render_quiz_frame(prog, fr)
    proc.stdin.write(frame.convert("RGB").tobytes())

proc.stdin.close()
proc.wait()
print(f"✅ Quiz animation rendered: {anim_path}")

# -------------------------------------------------------------
# 5. ASSEMBLE PREVIEW VIDEO
# -------------------------------------------------------------
print("\n🎞️ Assembling Final Preview Video...")
final_video_path = VideoAssembler.create_video(
    audio_data=padded_audio,
    visual_data=[{"scene_number": 1, "image_path": anim_path}],
    output_dir=output_dir,
    captions_path=None,
    sfx_category="duel_battle",
)

# Extract 3 preview screenshot frames for user review
preview_dir = os.path.join(output_dir, "preview_frames")
os.makedirs(preview_dir, exist_ok=True)
subprocess.run(["ffmpeg", "-y", "-ss", "2.5", "-i", final_video_path, "-vframes", "1", "-q:v", "2", os.path.join(preview_dir, "01_clues_screen.jpg")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["ffmpeg", "-y", "-ss", "5.5", "-i", final_video_path, "-vframes", "1", "-q:v", "2", os.path.join(preview_dir, "02_countdown_timer.jpg")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["ffmpeg", "-y", "-ss", "8.5", "-i", final_video_path, "-vframes", "1", "-q:v", "2", os.path.join(preview_dir, "03_answer_reveal.jpg")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("\n" + "=" * 60)
print("🎉 QUIZ ENGINE PREVIEW READY!")
print(f"📁 Video Path: {final_video_path}")
print(f"🖼️ Preview Screenshots: {preview_dir}")
print("=" * 60)
