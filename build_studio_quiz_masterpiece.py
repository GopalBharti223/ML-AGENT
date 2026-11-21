"""Studio-Grade 10/10 Interactive Quiz / Trivia Shorts Engine.
Concept: "Global Geography IQ Challenge: Guess the Country!"
Engineered for maximum retention, emotional engagement, and subscriber conversion.
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

output_dir = os.path.join("output", "studio_quiz_masterpiece")
os.makedirs(output_dir, exist_ok=True)
preview_dir = os.path.join(output_dir, "preview_frames")
os.makedirs(preview_dir, exist_ok=True)
audio_dir = os.path.join(output_dir, "audio")
os.makedirs(audio_dir, exist_ok=True)

print("="*60)
print("🚀 INITIALIZING 10/10 STUDIO-GRADE QUIZ ENGINE")
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
        "text": "Time is up! The correct answer is B, Japan! Over eighty percent got this wrong. Subscribe if your IQ is over one hundred and twenty!",
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

# Convert MP3 to WAV & Measure Exact Durations
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
print(f"  Scene 3 (Reveal & Subscribe CTA): {DUR_S1 + DUR_S2:.2f}s -> {TOTAL_DURATION:.2f}s")
print(f"  Total Video Duration: {TOTAL_DURATION:.2f}s ({TOTAL_FRAMES} frames at 30fps)")

# ----------------------------------------------------------------------
# 2. MASTER AUDIO MIX (Narration + Clock Ticks + SFX + Ducked Music)
# ----------------------------------------------------------------------
print("\n🎵 Synthesizing Clock Ticks and Mastering Audio...")

# Generate clean clock tick sound
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

# Build FFmpeg complex audio filter
# s1 starts at 0.0
# s2 starts at DUR_S1
# s3 starts at DUR_S1 + DUR_S2
# 5 clock ticks during Scene 2 at DUR_S1 + 0.3s, 1.2s, 2.1s, 3.0s, 3.9s
# SFX impact at DUR_S1 + DUR_S2
# SFX victory chime at DUR_S1 + DUR_S2 + 0.4s
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
# 3. HIGH-END GRAPHIC ASSETS & FONTS (Segoe UI Bold)
# ----------------------------------------------------------------------
def get_font(size, bold=True):
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    try: return ImageFont.truetype(name, size)
    except: return ImageFont.load_default()

font_badge = get_font(28, bold=True)
font_title = get_font(46, bold=True)
font_q_label = get_font(26, bold=True)
font_question = get_font(38, bold=True)
font_hint = get_font(26, bold=True)
font_timer = get_font(100, bold=True)
font_card_letter = get_font(38, bold=True)
font_card_name = get_font(40, bold=True)
font_card_status = get_font(32, bold=True)
font_bottom_main = get_font(36, bold=True)
font_bottom_sub = get_font(24, bold=True)

# Load and prepare rounded flags
def load_round_flag(code, size=(96, 64)):
    p1 = os.path.join("assets", "flags_hires", f"{code}.png")
    p2 = os.path.join("assets", "flags", f"{code}.png")
    path = p1 if os.path.exists(p1) else p2
    im = Image.open(path).convert("RGBA")
    im = im.resize(size, Image.Resampling.LANCZOS)
    
    # Mask rounded rectangle
    mask = Image.new("L", size, 0)
    draw_m = ImageDraw.Draw(mask)
    draw_m.rounded_rectangle([(0,0), size], radius=12, fill=255)
    im.putalpha(mask)
    
    # Subtle border around flag
    border = Image.new("RGBA", size, (0,0,0,0))
    draw_b = ImageDraw.Draw(border)
    draw_b.rounded_rectangle([(0,0), (size[0]-1, size[1]-1)], radius=12, outline=(255,255,255,140), width=2)
    return Image.alpha_composite(im, border)

flag_id = load_round_flag("id")
flag_jp = load_round_flag("jp")
flag_kr = load_round_flag("kr")
flag_nz = load_round_flag("nz")

# Big Japan Flag for Reveal (240x160)
flag_jp_big = load_round_flag("jp", size=(240, 160))

options_data = [
    {"letter": "A", "code": "id", "name": "INDONESIA", "flag": flag_id, "correct": False},
    {"letter": "B", "code": "jp", "name": "JAPAN", "flag": flag_jp, "correct": True},
    {"letter": "C", "code": "kr", "name": "SOUTH KOREA", "flag": flag_kr, "correct": False},
    {"letter": "D", "code": "nz", "name": "NEW ZEALAND", "flag": flag_nz, "correct": False},
]

# Pre-generate 45 Floating Background Particles (deterministic seed)
np.random.seed(42)
PARTICLES = []
for _ in range(45):
    PARTICLES.append({
        "x": np.random.randint(40, WIDTH - 40),
        "base_y": np.random.randint(0, HEIGHT),
        "speed": np.random.uniform(30, 80),
        "radius": np.random.randint(2, 6),
        "alpha": np.random.randint(40, 140),
        "color": (251, 191, 36) if np.random.rand() > 0.5 else (6, 182, 212)
    })

# ----------------------------------------------------------------------
# 4. STUDIO CANVAS GENERATION FUNCTION
# ----------------------------------------------------------------------
def create_studio_base():
    # Deep luxury gradient: Top navy-indigo to dark abyss
    base = Image.new("RGBA", (WIDTH, HEIGHT), (11, 15, 26, 255))
    draw = ImageDraw.Draw(base)
    
    # Subtle vertical gradient
    for y in range(0, HEIGHT, 4):
        ratio = y / HEIGHT
        r = int(14 * (1 - ratio) + 7 * ratio)
        g = int(18 * (1 - ratio) + 9 * ratio)
        b = int(32 * (1 - ratio) + 16 * ratio)
        draw.rectangle([(0, y), (WIDTH, y+4)], fill=(r, g, b, 255))
        
    # Ambient Top Spotlights (Neon Cyan Left, Deep Gold Right)
    glow_top = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
    g_draw = ImageDraw.Draw(glow_top)
    
    # Top-Left Cyan Glow
    for r_i in range(350, 0, -10):
        a = int(30 * (1 - r_i/350))
        g_draw.ellipse([(100 - r_i, 150 - r_i), (100 + r_i, 150 + r_i)], fill=(6, 182, 212, a))
        
    # Top-Right Gold Glow
    for r_i in range(350, 0, -10):
        a = int(35 * (1 - r_i/350))
        g_draw.ellipse([(WIDTH - 100 - r_i, 150 - r_i), (WIDTH - 100 + r_i, 150 + r_i)], fill=(245, 158, 11, a))
        
    # Subtle luxury studio grid
    grid_img = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
    grid_draw = ImageDraw.Draw(grid_img)
    for gx in range(60, WIDTH, 80):
        grid_draw.line([(gx, 0), (gx, HEIGHT)], fill=(255, 255, 255, 6), width=1)
    for gy in range(60, HEIGHT, 80):
        grid_draw.line([(0, gy), (WIDTH, gy)], fill=(255, 255, 255, 6), width=1)
        
    res = Image.alpha_composite(base, glow_top)
    res = Image.alpha_composite(res, grid_img)
    return res

STUDIO_BG = create_studio_base()

# ----------------------------------------------------------------------
# 5. RENDER FRAME PIPELINE
# ----------------------------------------------------------------------
def render_frame(cur_time, frame_num):
    canvas = STUDIO_BG.copy()
    draw = ImageDraw.Draw(canvas)
    
    # 0. Floating Ambient Particles
    for p in PARTICLES:
        y_pos = (p["base_y"] - cur_time * p["speed"]) % HEIGHT
        x_wobble = p["x"] + int(math.sin(cur_time * 2 + p["radius"]) * 10)
        draw.ellipse([
            (x_wobble - p["radius"], y_pos - p["radius"]),
            (x_wobble + p["radius"], y_pos + p["radius"])
        ], fill=(*p["color"], p["alpha"]))
        
    # ------------------------------------------------------------------
    # ZONE 1: TOP HEADER BADGE (Y: 90 to 220)
    # ------------------------------------------------------------------
    hw, hh = 960, 130
    hx = (WIDTH - hw) // 2
    hy = 90
    
    # Glow around header
    glow_rect = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
    g_draw = ImageDraw.Draw(glow_rect)
    g_draw.rounded_rectangle([(hx-4, hy-4), (hx+hw+4, hy+hh+4)], radius=26, fill=(245, 158, 11, 45))
    canvas = Image.alpha_composite(canvas, glow_rect)
    draw = ImageDraw.Draw(canvas)
    
    draw.rounded_rectangle([(hx, hy), (hx+hw, hy+hh)], radius=24, fill=(18, 22, 38, 245), outline=(245, 158, 11, 230), width=3)
    draw.text((WIDTH//2, hy + 35), "⚡ GLOBAL GEOGRAPHY IQ CHALLENGE ⚡", fill=(251, 191, 36, 255), font=font_badge, anchor="mm")
    draw.text((WIDTH//2, hy + 85), "GUESS THE COUNTRY IN 5 SECONDS!", fill=(255, 255, 255, 255), font=font_title, anchor="mm")
    
    # ------------------------------------------------------------------
    # ZONE 2: QUESTION & CLUES GLASS CARD (Y: 250 to 570)
    # ------------------------------------------------------------------
    qw, qh = 960, 310
    qx = (WIDTH - qw) // 2
    qy = 250
    
    # Question Card Background (Frosted Glass Navy)
    draw.rounded_rectangle([(qx, qy), (qx+qw, qy+qh)], radius=28, fill=(16, 22, 40, 245), outline=(6, 182, 212, 210), width=3)
    
    # Question Tag Pill
    draw.rounded_rectangle([(qx + 40, qy + 25), (qx + 240, qy + 65)], radius=12, fill=(6, 182, 212, 40), outline=(6, 182, 212, 180), width=2)
    draw.text((qx + 140, qy + 45), "❓ QUESTION #1", fill=(103, 232, 249, 255), font=font_q_label, anchor="mm")
    
    # Question Text (2 Lines with drop shadow)
    q_line1 = "Which country has over 6,800 islands"
    q_line2 = "and the world's fastest bullet trains?"
    
    # Shadow
    draw.text((WIDTH//2 + 2, qy + 115 + 2), q_line1, fill=(0, 0, 0, 180), font=font_question, anchor="mm")
    draw.text((WIDTH//2, qy + 115), q_line1, fill=(255, 255, 255, 255), font=font_question, anchor="mm")
    
    draw.text((WIDTH//2 + 2, qy + 175 + 2), q_line2, fill=(0, 0, 0, 180), font=font_question, anchor="mm")
    draw.text((WIDTH//2, qy + 175), q_line2, fill=(255, 255, 255, 255), font=font_question, anchor="mm")
    
    # Sub-clue Hint Pill (Bottom of question card)
    draw.rounded_rectangle([(qx + 40, qy + 235), (qx + qw - 40, qy + 285)], radius=14, fill=(245, 158, 11, 25), outline=(245, 158, 11, 140), width=2)
    draw.text((WIDTH//2, qy + 260), "💡 HINT: Famous for Mount Fuji & Cherry Blossoms", fill=(253, 230, 138, 255), font=font_hint, anchor="mm")

    # ------------------------------------------------------------------
    # ZONE 3: COUNTDOWN TIMER / REVEAL STATUS (Y: 590 to 920)
    # ------------------------------------------------------------------
    timer_cx, timer_cy = WIDTH // 2, 755
    timer_r = 120
    
    is_scene_1 = cur_time < DUR_S1
    is_scene_2 = (cur_time >= DUR_S1) and (cur_time < DUR_S1 + DUR_S2)
    is_scene_3 = cur_time >= (DUR_S1 + DUR_S2)
    
    if is_scene_1:
        # Scene 1: Pulsing preview ring
        pulse = (math.sin(cur_time * 6) + 1.0) * 0.5  # 0 to 1
        ring_r = int(timer_r + pulse * 8)
        draw.ellipse([(timer_cx - ring_r, timer_cy - ring_r), (timer_cx + ring_r, timer_cy + ring_r)], fill=(18, 24, 44, 230), outline=(6, 182, 212, 140), width=6)
        draw.text((timer_cx, timer_cy - 18), "CHOOSE AN", fill=(147, 197, 253, 255), font=font_badge, anchor="mm")
        draw.text((timer_cx, timer_cy + 22), "OPTION BELOW", fill=(255, 255, 255, 255), font=font_badge, anchor="mm")
        
    elif is_scene_2:
        # Scene 2: Live High-Voltage 5-Second Countdown
        t_elapsed = cur_time - DUR_S1
        t_prog = min(1.0, max(0.0, t_elapsed / DUR_S2))
        seconds_left = max(1, math.ceil(5.0 * (1.0 - t_prog)))
        
        # Color transition: Neon Gold -> Neon Red when 2 seconds left
        timer_col = (239, 68, 68) if seconds_left <= 2 else (245, 158, 11)
        
        # Outer Glowing Track
        draw.ellipse([(timer_cx - timer_r, timer_cy - timer_r), (timer_cx + timer_r, timer_cy + timer_r)], fill=(15, 20, 36, 245), outline=(40, 52, 78, 200), width=10)
        
        # Sweeping Progress Arc (starts at top -90 deg and sweeps clockwise)
        sweep_end = -90 + int(360 * (1.0 - t_prog))
        draw.arc([(timer_cx - timer_r, timer_cy - timer_r), (timer_cx + timer_r, timer_cy + timer_r)], start=-90, end=sweep_end, fill=timer_col, width=14)
        
        # Digital Number with scale pulse on every second
        sec_fraction = (t_elapsed * 5.0 / DUR_S2) % 1.0
        pop_scale = 1.0 + (1.0 - sec_fraction) * 0.12 if sec_fraction < 0.25 else 1.0
        
        # Number shadow
        draw.text((timer_cx + 3, timer_cy + 3), str(seconds_left), fill=(0, 0, 0, 200), font=font_timer, anchor="mm")
        draw.text((timer_cx, timer_cy), str(seconds_left), fill=(255, 255, 255, 255) if seconds_left > 2 else (239, 68, 68, 255), font=font_timer, anchor="mm")
        
    else:
        # Scene 3: ANSWER REVEAL HALO
        t_rev = cur_time - (DUR_S1 + DUR_S2)
        # Pulsing victory aura
        halo_r = int(timer_r + 15 + math.sin(t_rev * 8) * 10)
        draw.ellipse([(timer_cx - halo_r, timer_cy - halo_r), (timer_cx + halo_r, timer_cy + halo_r)], fill=(16, 185, 129, 35), outline=(16, 185, 129, 200), width=6)
        
        # Paste Big Japan Flag
        bw, bh = flag_jp_big.size
        bx = timer_cx - bw // 2
        by = timer_cy - bh // 2
        canvas.paste(flag_jp_big, (bx, by), flag_jp_big)
        draw = ImageDraw.Draw(canvas)
        
        # "CORRECT!" Pill above the flag
        draw.rounded_rectangle([(timer_cx - 130, by - 40), (timer_cx + 130, by - 6)], radius=12, fill=(16, 185, 129, 240), outline=(255, 255, 255, 220), width=2)
        draw.text((timer_cx, by - 23), "✓ CORRECT ANSWER", fill=(255, 255, 255, 255), font=font_card_status, anchor="mm")

    # ------------------------------------------------------------------
    # ZONE 4: 4 MULTIPLE-CHOICE CARDS (Y: 940 to 1560)
    # ------------------------------------------------------------------
    card_w = 940
    card_h = 125
    card_x = (WIDTH - card_w) // 2
    start_y = 940
    gap_y = 145
    
    for i, opt in enumerate(options_data):
        cy = start_y + i * gap_y
        
        # Slide-in animation for Scene 1
        slide_start = 0.4 + i * 0.35
        if cur_time < slide_start:
            card_draw_x = card_x - int(500 * (1.0 - cur_time / slide_start))
            card_alpha = min(255, int(255 * (cur_time / slide_start)))
        else:
            card_draw_x = card_x
            card_alpha = 255
            
        if card_alpha <= 10:
            continue
            
        if is_scene_3:
            # REVEAL STATE
            if opt["correct"]:
                # Radiant Neon Emerald Green Glow
                glow_c = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
                gc_draw = ImageDraw.Draw(glow_c)
                gc_draw.rounded_rectangle([(card_draw_x - 6, cy - 6), (card_draw_x + card_w + 6, cy + card_h + 6)], radius=24, fill=(16, 185, 129, 80))
                canvas = Image.alpha_composite(canvas, glow_c)
                draw = ImageDraw.Draw(canvas)
                
                # Card Body
                draw.rounded_rectangle([(card_draw_x, cy), (card_draw_x + card_w, cy + card_h)], radius=22, fill=(5, 150, 105, 245), outline=(52, 211, 153, 255), width=4)
                
                # Letter Box [ B ] (Gold accent)
                draw.rounded_rectangle([(card_draw_x + 20, cy + 20), (card_draw_x + 105, cy + card_h - 20)], radius=14, fill=(245, 158, 11, 240), outline=(255, 255, 255, 220), width=2)
                draw.text((card_draw_x + 62, cy + card_h // 2), opt["letter"], fill=(255, 255, 255, 255), font=font_card_letter, anchor="mm")
                
                # Flag
                canvas.paste(opt["flag"], (card_draw_x + 130, cy + (card_h - 64)//2), opt["flag"])
                draw = ImageDraw.Draw(canvas)
                
                # Country Name
                draw.text((card_draw_x + 250, cy + card_h // 2), opt["name"], fill=(255, 255, 255, 255), font=font_card_name, anchor="lm")
                
                # Right Checkmark Badge
                draw.rounded_rectangle([(card_draw_x + card_w - 200, cy + 28), (card_draw_x + card_w - 25, cy + card_h - 28)], radius=14, fill=(255, 255, 255, 240))
                draw.text((card_draw_x + card_w - 112, cy + card_h // 2), "✓ 100%", fill=(5, 150, 105, 255), font=font_card_status, anchor="mm")
                
            else:
                # Dimmed Wrong Answer Card
                draw.rounded_rectangle([(card_draw_x, cy), (card_draw_x + card_w, cy + card_h)], radius=20, fill=(18, 22, 34, 130), outline=(239, 68, 68, 80), width=2)
                
                # Dim Letter Box
                draw.rounded_rectangle([(card_draw_x + 20, cy + 22), (card_draw_x + 100, cy + card_h - 22)], radius=12, fill=(35, 42, 60, 160))
                draw.text((card_draw_x + 60, cy + card_h // 2), opt["letter"], fill=(156, 163, 175, 180), font=font_card_letter, anchor="mm")
                
                # Dim Flag
                canvas.paste(opt["flag"], (card_draw_x + 130, cy + (card_h - 64)//2), opt["flag"])
                draw = ImageDraw.Draw(canvas)
                
                # Dim Name
                draw.text((card_draw_x + 250, cy + card_h // 2), opt["name"], fill=(156, 163, 175, 160), font=font_card_name, anchor="lm")
                
                # Red 'X'
                draw.text((card_draw_x + card_w - 80, cy + card_h // 2), "✕", fill=(239, 68, 68, 200), font=font_card_name, anchor="mm")
                
        else:
            # ACTIVE GUESSING STATE (Scene 1 & Scene 2)
            # Glassmorphic Dark Card
            draw.rounded_rectangle([(card_draw_x, cy), (card_draw_x + card_w, cy + card_h)], radius=20, fill=(20, 26, 46, 240), outline=(60, 78, 115, 200), width=2)
            
            # Letter Badge Box
            colors = [(59, 130, 246), (147, 51, 234), (245, 158, 11), (236, 72, 153)]
            box_col = colors[i % len(colors)]
            draw.rounded_rectangle([(card_draw_x + 20, cy + 22), (card_draw_x + 105, cy + card_h - 22)], radius=14, fill=box_col)
            draw.text((card_draw_x + 62, cy + card_h // 2), opt["letter"], fill=(255, 255, 255, 255), font=font_card_letter, anchor="mm")
            
            # Country Flag
            canvas.paste(opt["flag"], (card_draw_x + 130, cy + (card_h - 64)//2), opt["flag"])
            draw = ImageDraw.Draw(canvas)
            
            # Country Name
            draw.text((card_draw_x + 250, cy + card_h // 2), opt["name"], fill=(245, 245, 255, 255), font=font_card_name, anchor="lm")
            
            # Subtle Tap Indicator
            draw.text((card_draw_x + card_w - 80, cy + card_h // 2), "👉", font=font_hint, anchor="mm")

    # ------------------------------------------------------------------
    # ZONE 5: INTERACTIVE FOOTER / CALL-TO-ACTION (Y: 1590 to 1800)
    # ------------------------------------------------------------------
    foot_w = 960
    foot_h = 170
    foot_x = (WIDTH - foot_w) // 2
    foot_y = 1600
    
    if not is_scene_3:
        # Scene 1 & 2: Interactive Comment Driver
        pulse_c = int(math.sin(cur_time * 5) * 20)
        draw.rounded_rectangle([(foot_x, foot_y), (foot_x + foot_w, foot_y + foot_h)], radius=24, fill=(18, 24, 42, 240), outline=(245, 158, 11, 180), width=2)
        draw.text((WIDTH//2, foot_y + 45), "💬 COMMENT YOUR GUESS BELOW NOW!", fill=(251, 191, 36, 255), font=font_bottom_main, anchor="mm")
        draw.text((WIDTH//2, foot_y + 110), "🔥 85% of people fail this geography challenge", fill=(209, 213, 219, 255), font=font_bottom_sub, anchor="mm")
        
    else:
        # Scene 3: HIGH-CONVERSION PULSING SUBSCRIBE BANNER
        sub_pulse = (math.sin(cur_time * 8) + 1.0) * 0.5  # 0 to 1
        sub_border = (239, 68, 68, 255) if sub_pulse > 0.5 else (255, 215, 0, 255)
        
        # Glowing shadow
        sub_glow = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
        sg_draw = ImageDraw.Draw(sub_glow)
        sg_draw.rounded_rectangle([(foot_x - 6, foot_y - 6), (foot_x + foot_w + 6, foot_y + foot_h + 6)], radius=28, fill=(239, 68, 68, 65))
        canvas = Image.alpha_composite(canvas, sub_glow)
        draw = ImageDraw.Draw(canvas)
        
        # Red/Gold conversion card
        draw.rounded_rectangle([(foot_x, foot_y), (foot_x + foot_w, foot_y + foot_h)], radius=24, fill=(220, 38, 38, 245), outline=sub_border, width=4)
        draw.text((WIDTH//2, foot_y + 50), "🔔 SUBSCRIBE IF YOU GOT IT RIGHT!", fill=(255, 255, 255, 255), font=font_bottom_main, anchor="mm")
        draw.text((WIDTH//2, foot_y + 115), "Daily Geography & IQ Trivia • Challenge Your Brain Daily", fill=(254, 226, 226, 255), font=font_bottom_sub, anchor="mm")
        
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
    
    # Save preview screenshot if target frame
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
final_output_mp4 = os.path.join(output_dir, "studio_quiz_final.mp4")
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
print("🎉 10/10 STUDIO-GRADE QUIZ SHORT IS READY!")
print(f"📁 Video Path: {final_output_mp4}")
print(f"🖼️ Preview Frames: {preview_dir}")
print("="*60)
