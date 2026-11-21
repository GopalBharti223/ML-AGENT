"""Studio-Grade 10/10 Interactive Quiz / Trivia Shorts Engine - Version 2 (Masterpiece).
Redesigned with:
- Obsidian Glassmorphism with Blurred Glowing Ambient Back-Shadows (Netflix / Apple TV UI).
- Unified, non-boxed typography (zero 'stacked boxes' look).
- Clean, borderless Question Presentation.
- Sleek glowing progress countdown bar with millisecond-accurate clock ticking.
- Answer Reveal: The awkward circle and tacky labels are eliminated.
  Option B (Japan) lights up with an intense, soft-blurred emerald neon halo backlight!
- Welcoming, high-conversion daily subscriber CTA (no gatekeeping).
"""

import os
import sys
import math
import wave
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import edge_tts
import asyncio

WIDTH = 1080
HEIGHT = 1920
FPS = 30

output_dir = os.path.join("output", "studio_quiz_masterpiece_v2")
os.makedirs(output_dir, exist_ok=True)
preview_dir = os.path.join(output_dir, "preview_frames")
os.makedirs(preview_dir, exist_ok=True)
audio_dir = os.path.join(output_dir, "audio")
os.makedirs(audio_dir, exist_ok=True)

print("="*60)
print("🚀 BUILDING 10/10 STUDIO-GRADE QUIZ ENGINE V2 (CINEMATIC)")
print("="*60)

# ----------------------------------------------------------------------
# 1. GENERATE CALM, SMOOTH NARRATION (Edge-TTS)
# ----------------------------------------------------------------------
scenes_narration = [
    {
        "id": "scene_1",
        "text": "Can you guess this country in five seconds? It has over six thousand islands and the fastest bullet trains in the world.",
        "pacing": "calm_hook"
    },
    {
        "id": "scene_2",
        "text": "Five seconds on the clock. Make your guess in the comments right now.",
        "pacing": "countdown_suspense"
    },
    {
        "id": "scene_3",
        "text": "Time is up! The answer is B, Japan! Subscribe for your daily trivia quiz, and let us see if you can get tomorrow's challenge right!",
        "pacing": "triumphant_reveal"
    }
]

VOICE = "en-US-BrianNeural"
VOICE_RATE = "-4%"

async def generate_all_tts():
    paths = []
    for s in scenes_narration:
        fp = os.path.join(audio_dir, f"{s['id']}.mp3")
        print(f"🎙️ Generating voiceover for {s['id']} ({VOICE})...")
        comm = edge_tts.Communicate(s['text'], VOICE, rate=VOICE_RATE)
        await comm.save(fp)
        paths.append(fp)
    return paths

asyncio.run(generate_all_tts())

def get_audio_duration(file_path):
    res = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]).decode().strip()
    return float(res)

scene_durations = []
wav_paths = []
for s in scenes_narration:
    mp3_fp = os.path.join(audio_dir, f"{s['id']}.mp3")
    wav_fp = os.path.join(audio_dir, f"{s['id']}.wav")
    subprocess.run(["ffmpeg", "-y", "-i", mp3_fp, "-ar", "44100", "-ac", "2", wav_fp], capture_output=True, check=True)
    dur = get_audio_duration(wav_fp)
    scene_durations.append(dur)
    wav_paths.append(wav_fp)
    print(f"  -> {s['id']}: {dur:.2f}s")

DUR_S1 = scene_durations[0]
DUR_S2 = scene_durations[1]
DUR_S3 = scene_durations[2]
TOTAL_DURATION = DUR_S1 + DUR_S2 + DUR_S3
TOTAL_FRAMES = int(TOTAL_DURATION * FPS)

print(f"\n📊 Exact Timeline:")
print(f"  Scene 1 (Hook & Question): 0.00s -> {DUR_S1:.2f}s")
print(f"  Scene 2 (5s Ticking Timer): {DUR_S1:.2f}s -> {DUR_S1 + DUR_S2:.2f}s")
print(f"  Scene 3 (Reveal & Daily Subscribe CTA): {DUR_S1 + DUR_S2:.2f}s -> {TOTAL_DURATION:.2f}s")
print(f"  Total Video Duration: {TOTAL_DURATION:.2f}s ({TOTAL_FRAMES} frames at 30fps)")

# ----------------------------------------------------------------------
# 2. MASTER AUDIO MIX (Clock Ticks, Impacts, Cash Bell, Music)
# ----------------------------------------------------------------------
sample_rate = 44100
t = np.linspace(0, 0.08, int(sample_rate * 0.08), False)
tick_wave = np.sin(2 * np.pi * 1400 * t) * np.exp(-t * 65)
tick_wave = (tick_wave / np.max(np.abs(tick_wave)) * 28000).astype(np.int16)
tick_fp = os.path.join(audio_dir, "clock_tick.wav")
with wave.open(tick_fp, 'w') as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(sample_rate)
    f.writeframes(tick_wave.tobytes())

sfx_impact = "assets/sfx/shorts_impact.wav"
sfx_cash = "assets/sfx/shorts_cash_bell.wav"
sfx_whoosh = "assets/sfx/shorts_whoosh.wav"
bg_music = "assets/audio/music/tension_riser.wav"

final_audio_fp = os.path.join(output_dir, "mastered_audio.wav")

filter_complex = [
    f"[0:a]adelay=0|0,apad=whole_dur={TOTAL_DURATION}[nar1]",
    f"[1:a]adelay={int(DUR_S1 * 1000)}|{int(DUR_S1 * 1000)},apad=whole_dur={TOTAL_DURATION}[nar2]",
    f"[2:a]adelay={int((DUR_S1 + DUR_S2) * 1000)}|{int((DUR_S1 + DUR_S2) * 1000)},apad=whole_dur={TOTAL_DURATION}[nar3]",
    f"[3:a]volume=0.6,adelay=200|200,apad=whole_dur={TOTAL_DURATION}[sfx_w]",
    f"[4:a]volume=0.8,adelay={int((DUR_S1 + DUR_S2) * 1000)}|{int((DUR_S1 + DUR_S2) * 1000)},apad=whole_dur={TOTAL_DURATION}[sfx_imp]",
    f"[5:a]volume=0.9,adelay={int((DUR_S1 + DUR_S2 + 0.4) * 1000)}|{int((DUR_S1 + DUR_S2 + 0.4) * 1000)},apad=whole_dur={TOTAL_DURATION}[sfx_c]",
    f"[6:a]volume=0.9,adelay={int((DUR_S1 + 0.4) * 1000)}|{int((DUR_S1 + 0.4) * 1000)},apad=whole_dur={TOTAL_DURATION}[tk1]",
    f"[6:a]volume=0.95,adelay={int((DUR_S1 + 1.3) * 1000)}|{int((DUR_S1 + 1.3) * 1000)},apad=whole_dur={TOTAL_DURATION}[tk2]",
    f"[6:a]volume=1.0,adelay={int((DUR_S1 + 2.2) * 1000)}|{int((DUR_S1 + 2.2) * 1000)},apad=whole_dur={TOTAL_DURATION}[tk3]",
    f"[6:a]volume=1.1,adelay={int((DUR_S1 + 3.1) * 1000)}|{int((DUR_S1 + 3.1) * 1000)},apad=whole_dur={TOTAL_DURATION}[tk4]",
    f"[6:a]volume=1.2,adelay={int((DUR_S1 + 4.0) * 1000)}|{int((DUR_S1 + 4.0) * 1000)},apad=whole_dur={TOTAL_DURATION}[tk5]",
    f"[7:a]volume=0.12,atrim=0:{TOTAL_DURATION},afade=t=out:st={TOTAL_DURATION - 1.5}:d=1.5[bgm]",
    f"[nar1][nar2][nar3][sfx_w][sfx_imp][sfx_c][tk1][tk2][tk3][tk4][tk5][bgm]amix=inputs=12:duration=longest:dropout_transition=2,atrim=0:{TOTAL_DURATION},loudnorm=I=-14:LRA=7:tp=-1.5[outa]"
]

cmd_mix = [
    "ffmpeg", "-y",
    "-i", wav_paths[0],
    "-i", wav_paths[1],
    "-i", wav_paths[2],
    "-i", sfx_whoosh,
    "-i", sfx_impact,
    "-i", sfx_cash,
    "-i", tick_fp,
    "-i", bg_music,
    "-filter_complex", ";".join(filter_complex),
    "-map", "[outa]",
    final_audio_fp
]
subprocess.run(cmd_mix, capture_output=True, check=True)
print(f"✅ Mastered Audio Track Ready: {final_audio_fp}")

# ----------------------------------------------------------------------
# 3. HIGH-END FONTS & PRECOMPUTED GLOW SHADOWS
# ----------------------------------------------------------------------
def get_font(size, bold=True):
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    try: return ImageFont.truetype(name, size)
    except: return ImageFont.load_default()

font_badge = get_font(26, bold=True)
font_q_num = get_font(28, bold=True)
font_question = get_font(42, bold=True)
font_hint = get_font(28, bold=True)
font_timer_num = get_font(72, bold=True)
font_timer_label = get_font(24, bold=True)
font_card_letter = get_font(34, bold=True)
font_card_name = get_font(38, bold=True)
font_card_status = get_font(30, bold=True)
font_bottom_main = get_font(34, bold=True)
font_bottom_sub = get_font(24, bold=True)

# Flags
def load_round_flag(code, size=(92, 60)):
    p1 = os.path.join("assets", "flags_hires", f"{code}.png")
    p2 = os.path.join("assets", "flags", f"{code}.png")
    path = p1 if os.path.exists(p1) else p2
    im = Image.open(path).convert("RGBA")
    im = im.resize(size, Image.Resampling.LANCZOS)
    mask = Image.new("L", size, 0)
    draw_m = ImageDraw.Draw(mask)
    draw_m.rounded_rectangle([(0,0), size], radius=12, fill=255)
    im.putalpha(mask)
    border = Image.new("RGBA", size, (0,0,0,0))
    draw_b = ImageDraw.Draw(border)
    draw_b.rounded_rectangle([(0,0), (size[0]-1, size[1]-1)], radius=12, outline=(255,255,255,120), width=2)
    return Image.alpha_composite(im, border)

flag_id = load_round_flag("id")
flag_jp = load_round_flag("jp")
flag_kr = load_round_flag("kr")
flag_nz = load_round_flag("nz")

# Big Japan Flag for Reveal (260x170)
flag_jp_hero = load_round_flag("jp", size=(260, 170))

options_data = [
    {"letter": "A", "code": "id", "name": "INDONESIA", "flag": flag_id, "correct": False},
    {"letter": "B", "code": "jp", "name": "JAPAN", "flag": flag_jp, "correct": True},
    {"letter": "C", "code": "kr", "name": "SOUTH KOREA", "flag": flag_kr, "correct": False},
    {"letter": "D", "code": "nz", "name": "NEW ZEALAND", "flag": flag_nz, "correct": False},
]

# ----------------------------------------------------------------------
# PRECOMPUTE GLOWING BACKLIGHTS (Netflix-style Ambient Back-Glow)
# ----------------------------------------------------------------------
CARD_W = 940
CARD_H = 120
BLUR_PAD = 40

def make_backlight(w, h, pad, color_rgba, blur_r=16):
    img = Image.new("RGBA", (w + pad*2, h + pad*2), (0,0,0,0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([(pad - 4, pad - 4), (pad + w + 4, pad + h + 4)], radius=24, fill=color_rgba)
    return img.filter(ImageFilter.GaussianBlur(blur_r))

# 1. Normal Card Slate Shadow
backlight_normal = make_backlight(CARD_W, CARD_H, BLUR_PAD, (15, 23, 42, 160), blur_r=14)
# 2. Emerald Reveal Halo Backlight
backlight_emerald = make_backlight(CARD_W, CARD_H, BLUR_PAD, (16, 185, 129, 150), blur_r=22)
# 3. Gold Timer Bar Glow
bar_glow = make_backlight(CARD_W, 16, 30, (245, 158, 11, 140), blur_r=14)
bar_glow_red = make_backlight(CARD_W, 16, 30, (239, 68, 68, 160), blur_r=14)

# Pre-generate 35 Ambient Cinematic Golden/Cyan Dust Particles
np.random.seed(55)
PARTICLES = []
for _ in range(35):
    PARTICLES.append({
        "x": np.random.randint(40, WIDTH - 40),
        "base_y": np.random.randint(0, HEIGHT),
        "speed": np.random.uniform(25, 60),
        "radius": np.random.randint(2, 5),
        "alpha": np.random.randint(30, 90),
        "color": (251, 191, 36) if np.random.rand() > 0.5 else (14, 165, 233)
    })

# ----------------------------------------------------------------------
# 4. LUXURY OBSIDIAN CANVAS BASE
# ----------------------------------------------------------------------
def create_luxury_canvas():
    base = Image.new("RGBA", (WIDTH, HEIGHT), (8, 10, 18, 255))
    draw = ImageDraw.Draw(base)
    # Deep midnight vignette
    for y in range(0, HEIGHT, 4):
        ratio = y / HEIGHT
        r = int(10 * (1 - ratio) + 5 * ratio)
        g = int(14 * (1 - ratio) + 7 * ratio)
        b = int(26 * (1 - ratio) + 13 * ratio)
        draw.rectangle([(0, y), (WIDTH, y+4)], fill=(r, g, b, 255))
        
    # Top Subtle Ambient Sapphire Spotlight
    spotlight = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
    s_draw = ImageDraw.Draw(spotlight)
    for r_i in range(400, 0, -15):
        a = int(25 * (1 - r_i/400))
        s_draw.ellipse([(WIDTH//2 - r_i, 180 - r_i), (WIDTH//2 + r_i, 180 + r_i)], fill=(37, 99, 235, a))
        
    return Image.alpha_composite(base, spotlight)

BASE_STUDIO = create_luxury_canvas()

# ----------------------------------------------------------------------
# 5. RENDER FRAME PIPELINE
# ----------------------------------------------------------------------
def render_frame(cur_time, frame_num):
    canvas = BASE_STUDIO.copy()
    draw = ImageDraw.Draw(canvas)
    
    # 0. Floating Ambient Dust Particles
    for p in PARTICLES:
        y_pos = (p["base_y"] - cur_time * p["speed"]) % HEIGHT
        x_wobble = p["x"] + int(math.sin(cur_time * 1.5 + p["radius"]) * 8)
        draw.ellipse([
            (x_wobble - p["radius"], y_pos - p["radius"]),
            (x_wobble + p["radius"], y_pos + p["radius"])
        ], fill=(*p["color"], p["alpha"]))
        
    # ------------------------------------------------------------------
    # TOP HEADER: CLEAN MINIMALIST BADGE (Y: 100)
    # ------------------------------------------------------------------
    badge_w, badge_h = 360, 48
    bx = (WIDTH - badge_w) // 2
    by = 110
    draw.rounded_rectangle([(bx, by), (bx + badge_w, by + badge_h)], radius=24, fill=(18, 26, 44, 200), outline=(245, 158, 11, 160), width=2)
    draw.text((WIDTH//2, by + badge_h//2), "⚡ DAILY GEOGRAPHY TRIVIA ⚡", fill=(251, 191, 36, 255), font=font_badge, anchor="mm")
    
    # ------------------------------------------------------------------
    # BORDERLESS CLEAN QUESTION TYPOGRAPHY (Y: 200 to 420)
    # ------------------------------------------------------------------
    # No bulky box! Just pure, crisp, drop-shadowed typography
    draw.text((WIDTH//2, 210), "QUESTION #1", fill=(147, 197, 253, 230), font=font_q_num, anchor="mm")
    
    q_line1 = "Which country has over 6,800 islands"
    q_line2 = "and the world's fastest bullet trains?"
    
    # Soft text shadow
    draw.text((WIDTH//2 + 2, 280 + 2), q_line1, fill=(0, 0, 0, 220), font=font_question, anchor="mm")
    draw.text((WIDTH//2, 280), q_line1, fill=(255, 255, 255, 255), font=font_question, anchor="mm")
    
    draw.text((WIDTH//2 + 2, 345 + 2), q_line2, fill=(0, 0, 0, 220), font=font_question, anchor="mm")
    draw.text((WIDTH//2, 345), q_line2, fill=(255, 255, 255, 255), font=font_question, anchor="mm")
    
    # Hint Sub-Pill
    hint_w, hint_h = 720, 52
    hx = (WIDTH - hint_w) // 2
    hy = 415
    draw.rounded_rectangle([(hx, hy), (hx + hint_w, hy + hint_h)], radius=16, fill=(15, 22, 36, 180), outline=(245, 158, 11, 100), width=1)
    draw.text((WIDTH//2, hy + hint_h//2), "💡 Clue: Famous for Mount Fuji & Cherry Blossoms", fill=(253, 230, 138, 255), font=font_hint, anchor="mm")

    # ------------------------------------------------------------------
    # CENTER CONSOLE: SLEEK PROGRESS COUNTDOWN OR REVEAL SHOWCASE (Y: 510 to 860)
    # ------------------------------------------------------------------
    is_scene_1 = cur_time < DUR_S1
    is_scene_2 = (cur_time >= DUR_S1) and (cur_time < DUR_S1 + DUR_S2)
    is_scene_3 = cur_time >= (DUR_S1 + DUR_S2)
    
    center_y = 680
    
    if is_scene_1:
        # Pre-countdown status: Clean floating indicator
        draw.text((WIDTH//2, center_y - 20), "CHOOSE YOUR ANSWER", fill=(148, 163, 184, 255), font=font_badge, anchor="mm")
        draw.text((WIDTH//2, center_y + 25), "5-Second Countdown Starting Soon...", fill=(203, 213, 225, 200), font=font_bottom_sub, anchor="mm")
        
    elif is_scene_2:
        # High-Voltage 5-Second Countdown
        t_elapsed = cur_time - DUR_S1
        t_prog = min(1.0, max(0.0, t_elapsed / DUR_S2))
        seconds_left = max(1, math.ceil(5.0 * (1.0 - t_prog)))
        
        timer_col = (239, 68, 68) if seconds_left <= 2 else (245, 158, 11)
        
        # Large Digital Countdown Number
        draw.text((WIDTH//2 + 3, center_y - 40 + 3), str(seconds_left), fill=(0, 0, 0, 200), font=font_timer_num, anchor="mm")
        draw.text((WIDTH//2, center_y - 40), str(seconds_left), fill=timer_col, font=font_timer_num, anchor="mm")
        
        draw.text((WIDTH//2, center_y + 30), "SECONDS REMAINING", fill=(148, 163, 184, 255), font=font_timer_label, anchor="mm")
        
        # Glowing Sleek Horizontal Progress Bar (Width 940)
        bar_w = 940
        bar_x = (WIDTH - bar_w) // 2
        bar_y = center_y + 70
        bar_h = 14
        
        # Track
        draw.rounded_rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h)], radius=7, fill=(24, 32, 50, 220))
        
        # Active Progress
        active_w = int(bar_w * (1.0 - t_prog))
        if active_w > 10:
            # Paste soft glow behind bar
            active_glow = bar_glow_red if seconds_left <= 2 else bar_glow
            canvas.paste(active_glow, (bar_x - 30, bar_y - 30), active_glow)
            draw = ImageDraw.Draw(canvas)
            draw.rounded_rectangle([(bar_x, bar_y), (bar_x + active_w, bar_y + bar_h)], radius=7, fill=timer_col)
            
    else:
        # Scene 3: ANSWER REVEAL HERO SHOWCASE (No awkward circle!)
        # The flag floats cleanly with a soft golden halo and celebratory sparkles
        t_rev = cur_time - (DUR_S1 + DUR_S2)
        fw, fh = flag_jp_hero.size
        fx = (WIDTH - fw) // 2
        fy = center_y - fh // 2 - 15
        
        # Soft Golden Halo behind flag
        halo = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
        h_draw = ImageDraw.Draw(halo)
        for r_i in range(160, 0, -10):
            a = int(35 * (1 - r_i/160))
            h_draw.ellipse([(WIDTH//2 - r_i, center_y - 15 - r_i), (WIDTH//2 + r_i, center_y - 15 + r_i)], fill=(245, 158, 11, a))
        canvas = Image.alpha_composite(canvas, halo)
        draw = ImageDraw.Draw(canvas)
        
        # Paste Hero Japan Flag
        canvas.paste(flag_jp_hero, (fx, fy), flag_jp_hero)
        draw = ImageDraw.Draw(canvas)
        
        # Minimalist clean country name banner below flag (No tacky "correct answer" text!)
        draw.text((WIDTH//2, fy + fh + 35), "JAPAN 🇯🇵", fill=(255, 255, 255, 255), font=font_question, anchor="mm")

    # ------------------------------------------------------------------
    # ZONE 4: 4 OBSIDIAN FLOATING CARDS (Y: 920 to 1520)
    # ------------------------------------------------------------------
    card_x = (WIDTH - CARD_W) // 2
    start_y = 920
    gap_y = 145
    
    for i, opt in enumerate(options_data):
        cy = start_y + i * gap_y
        
        # Smooth slide-in easing during Scene 1
        slide_start = 0.3 + i * 0.3
        if cur_time < slide_start:
            card_draw_x = card_x - int(450 * (1.0 - cur_time / slide_start))
            alpha_ratio = cur_time / slide_start
        else:
            card_draw_x = card_x
            alpha_ratio = 1.0
            
        if alpha_ratio < 0.1:
            continue
            
        if is_scene_3:
            # REVEAL STATE
            if opt["correct"]:
                # OPTION B: EMERALD BACKLIGHT HALO (Netflix-style)
                canvas.paste(backlight_emerald, (card_draw_x - BLUR_PAD, cy - BLUR_PAD), backlight_emerald)
                draw = ImageDraw.Draw(canvas)
                
                # Deep Emerald Obsidian Card Body
                draw.rounded_rectangle([(card_draw_x, cy), (card_draw_x + CARD_W, cy + CARD_H)], radius=20, fill=(6, 44, 30, 245), outline=(52, 211, 153, 240), width=2)
                
                # Letter Badge [ B ]
                draw.rounded_rectangle([(card_draw_x + 20, cy + 20), (card_draw_x + 95, cy + CARD_H - 20)], radius=12, fill=(16, 185, 129, 240))
                draw.text((card_draw_x + 57, cy + CARD_H // 2), opt["letter"], fill=(255, 255, 255, 255), font=font_card_letter, anchor="mm")
                
                # Flag
                canvas.paste(opt["flag"], (card_draw_x + 120, cy + (CARD_H - 60)//2), opt["flag"])
                draw = ImageDraw.Draw(canvas)
                
                # Country Name
                draw.text((card_draw_x + 240, cy + CARD_H // 2), opt["name"], fill=(255, 255, 255, 255), font=font_card_name, anchor="lm")
                
                # Clean Minimalist Checkmark
                draw.text((card_draw_x + CARD_W - 60, cy + CARD_H // 2), "✓", fill=(52, 211, 153, 255), font=font_card_name, anchor="mm")
                
            else:
                # Dimmed Wrong Answer Card (Smooth dark fade)
                draw.rounded_rectangle([(card_draw_x, cy), (card_draw_x + CARD_W, cy + CARD_H)], radius=18, fill=(12, 16, 26, 110), outline=(35, 45, 65, 80), width=1)
                
                # Dim Letter
                draw.rounded_rectangle([(card_draw_x + 20, cy + 22), (card_draw_x + 95, cy + CARD_H - 22)], radius=12, fill=(22, 28, 42, 140))
                draw.text((card_draw_x + 57, cy + CARD_H // 2), opt["letter"], fill=(100, 116, 139, 160), font=font_card_letter, anchor="mm")
                
                # Dim Flag
                canvas.paste(opt["flag"], (card_draw_x + 120, cy + (CARD_H - 60)//2), opt["flag"])
                draw = ImageDraw.Draw(canvas)
                
                # Dim Name
                draw.text((card_draw_x + 240, cy + CARD_H // 2), opt["name"], fill=(100, 116, 139, 140), font=font_card_name, anchor="lm")
                
        else:
            # ACTIVE GUESSING STATE (Scene 1 & 2)
            # Paste Soft Ambient Slate Shadow
            canvas.paste(backlight_normal, (card_draw_x - BLUR_PAD, cy - BLUR_PAD), backlight_normal)
            draw = ImageDraw.Draw(canvas)
            
            # Obsidian Frosted Glass Body
            draw.rounded_rectangle([(card_draw_x, cy), (card_draw_x + CARD_W, cy + CARD_H)], radius=20, fill=(16, 22, 38, 235), outline=(50, 65, 95, 180), width=2)
            
            # Bevel Top Highlight (1px frosted line)
            draw.line([(card_draw_x + 25, cy + 1), (card_draw_x + CARD_W - 25, cy + 1)], fill=(255, 255, 255, 30), width=1)
            
            # Letter Badge Box
            draw.rounded_rectangle([(card_draw_x + 20, cy + 20), (card_draw_x + 95, cy + CARD_H - 20)], radius=12, fill=(30, 41, 65, 240), outline=(70, 88, 125, 180), width=1)
            draw.text((card_draw_x + 57, cy + CARD_H // 2), opt["letter"], fill=(255, 255, 255, 255), font=font_card_letter, anchor="mm")
            
            # Flag
            canvas.paste(opt["flag"], (card_draw_x + 120, cy + (CARD_H - 60)//2), opt["flag"])
            draw = ImageDraw.Draw(canvas)
            
            # Country Name
            draw.text((card_draw_x + 240, cy + CARD_H // 2), opt["name"], fill=(241, 245, 249, 255), font=font_card_name, anchor="lm")
            
            # Subtle Tap Cue
            draw.text((card_draw_x + CARD_W - 55, cy + CARD_H // 2), "👉", font=font_badge, anchor="mm")

    # ------------------------------------------------------------------
    # ZONE 5: REFINED FOOTER CALL-TO-ACTION (Y: 1590 to 1780)
    # ------------------------------------------------------------------
    foot_w = 940
    foot_h = 150
    foot_x = (WIDTH - foot_w) // 2
    foot_y = 1600
    
    if not is_scene_3:
        # Scene 1 & 2: Clean Comment Driver
        draw.rounded_rectangle([(foot_x, foot_y), (foot_x + foot_w, foot_y + foot_h)], radius=22, fill=(14, 18, 30, 200), outline=(245, 158, 11, 140), width=2)
        draw.text((WIDTH//2, foot_y + 45), "💬 Drop your answer in the comments!", fill=(251, 191, 36, 255), font=font_bottom_main, anchor="mm")
        draw.text((WIDTH//2, foot_y + 105), "Can you guess it before the clock runs out?", fill=(203, 213, 225, 255), font=font_bottom_sub, anchor="mm")
        
    else:
        # Scene 3: WELCOMING DAILY SUBSCRIBE BANNER (No IQ 120 gatekeeping!)
        sub_pulse = (math.sin(cur_time * 7) + 1.0) * 0.5
        sub_glow_col = (220, 38, 38, int(80 + sub_pulse * 40))
        
        # Soft Red Ambient Backlight
        sub_backlight = make_backlight(foot_w, foot_h, BLUR_PAD, sub_glow_col, blur_r=18)
        canvas.paste(sub_backlight, (foot_x - BLUR_PAD, foot_y - BLUR_PAD), sub_backlight)
        draw = ImageDraw.Draw(canvas)
        
        # YouTube Red Card
        draw.rounded_rectangle([(foot_x, foot_y), (foot_x + foot_w, foot_y + foot_h)], radius=22, fill=(220, 38, 38, 245), outline=(254, 202, 202, 220), width=2)
        draw.text((WIDTH//2, foot_y + 45), "🔔 SUBSCRIBE FOR DAILY TRIVIA QUIZZES!", fill=(255, 255, 255, 255), font=font_bottom_main, anchor="mm")
        draw.text((WIDTH//2, foot_y + 105), "Test your brain every day • Can you get tomorrow's right?", fill=(254, 226, 226, 255), font=font_bottom_sub, anchor="mm")

    return canvas

# ----------------------------------------------------------------------
# 6. RENDER VIDEO WITH FFMPEG PIPE & EXTRACT SCREENSHOTS
# ----------------------------------------------------------------------
print("\n🎬 Rendering Video Frames directly to FFmpeg...")
visual_mp4 = os.path.join(output_dir, "raw_visuals.mp4")

ffmpeg_cmd = [
    "ffmpeg", "-y",
    "-f", "rawvideo",
    "-vcodec", "rawvideo",
    "-s", f"{WIDTH}x{HEIGHT}",
    "-pix_fmt", "rgb24",
    "-r", str(FPS),
    "-i", "-",
    "-c:v", "libx264",
    "-pix_fmt", "yuv420p",
    "-preset", "veryfast",
    "-crf", "18",
    visual_mp4
]

pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

screenshot_targets = {
    int(DUR_S1 * 0.7 * FPS): "01_question_options_screen.jpg",
    int((DUR_S1 + DUR_S2 * 0.5) * FPS): "02_countdown_tick_screen.jpg",
    int((DUR_S1 + DUR_S2 + 1.2) * FPS): "03_correct_answer_reveal.jpg",
    int((TOTAL_DURATION - 1.0) * FPS): "04_subscribe_callout.jpg"
}

for frame_idx in range(TOTAL_FRAMES):
    t_cur = frame_idx / FPS
    img = render_frame(t_cur, frame_idx)
    
    if frame_idx in screenshot_targets:
        fn = screenshot_targets[frame_idx]
        img.convert("RGB").save(os.path.join(preview_dir, fn), quality=95)
        print(f"  📸 Saved Preview Screenshot: {fn} (at {t_cur:.2f}s)")
        
    pipe.stdin.write(img.convert("RGB").tobytes())
    
    if frame_idx % 60 == 0:
        print(f"  Progress: frame {frame_idx}/{TOTAL_FRAMES} ({frame_idx/TOTAL_FRAMES*100:.1f}%)")

pipe.stdin.close()
pipe.wait()
print("✅ Video Stream Rendered!")

# ----------------------------------------------------------------------
# 7. ASSEMBLE FINAL SHORT (Visual + Mastered Audio)
# ----------------------------------------------------------------------
final_output_mp4 = os.path.join(output_dir, "studio_quiz_masterpiece_v2.mp4")
print("\n🎞️ Muxing Video & Mastered Audio...")

cmd_final = [
    "ffmpeg", "-y",
    "-i", visual_mp4,
    "-i", final_audio_fp,
    "-c:v", "copy",
    "-c:a", "aac",
    "-b:a", "192k",
    final_output_mp4
]
subprocess.run(cmd_final, capture_output=True, check=True)

print("="*60)
print("🎉 10/10 STUDIO-GRADE QUIZ SHORT V2 IS READY!")
print(f"📁 Video Path: {final_output_mp4}")
print(f"🖼️ Preview Frames: {preview_dir}")
print("="*60)
