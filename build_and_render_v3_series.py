"""
V3 Interactive Quiz Series Video Generator.
Renders 10 diverse high-curiosity video shorts with:
- Dynamic category color themes (Cyber Cyan, Fiery Orange, Cosmic Violet, Neon Magenta, Emerald Mint, Imperial Gold)
- Depleting circular SVG countdown ring
- Difficulty / IQ challenge badge
- Did You Know fact card on answer reveal
- Super-engaging "COMMENT YES OR NO" call-to-action
"""

import os
import sys
import json
import wave
import subprocess
import asyncio
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import edge_tts
from quiz_database import get_v3_interactive_series

WIDTH = 1080
HEIGHT = 1920
FPS = 30
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUTPUT_BASE = os.path.abspath(r"output\v3_interactive_series")
os.makedirs(OUTPUT_BASE, exist_ok=True)

CATEGORY_THEMES = {
    "SPORTS & SPEED": {
        "beam": "radial-gradient(circle, rgba(249, 115, 22, 0.35) 0%, rgba(234, 88, 12, 0.14) 40%, rgba(8, 7, 13, 0) 70%)",
        "accent": "#f97316",
        "pill_bg": "rgba(249, 115, 22, 0.12)",
        "pill_border": "rgba(249, 115, 22, 0.45)",
        "pill_text": "#fb923c",
        "glow": "rgba(249, 115, 22, 0.65)"
    },
    "TECH & AI": {
        "beam": "radial-gradient(circle, rgba(6, 182, 212, 0.35) 0%, rgba(14, 165, 233, 0.14) 40%, rgba(8, 7, 13, 0) 70%)",
        "accent": "#06b6d4",
        "pill_bg": "rgba(6, 182, 212, 0.12)",
        "pill_border": "rgba(6, 182, 212, 0.45)",
        "pill_text": "#22d3ee",
        "glow": "rgba(6, 182, 212, 0.65)"
    },
    "SPACE & COSMIC": {
        "beam": "radial-gradient(circle, rgba(168, 85, 247, 0.35) 0%, rgba(124, 58, 237, 0.14) 40%, rgba(8, 7, 13, 0) 70%)",
        "accent": "#a855f7",
        "pill_bg": "rgba(168, 85, 247, 0.12)",
        "pill_border": "rgba(168, 85, 247, 0.45)",
        "pill_text": "#c084fc",
        "glow": "rgba(168, 85, 247, 0.65)"
    },
    "MOVIES & POP CULTURE": {
        "beam": "radial-gradient(circle, rgba(236, 72, 153, 0.35) 0%, rgba(219, 39, 119, 0.14) 40%, rgba(8, 7, 13, 0) 70%)",
        "accent": "#ec4899",
        "pill_bg": "rgba(236, 72, 153, 0.12)",
        "pill_border": "rgba(236, 72, 153, 0.45)",
        "pill_text": "#f472b6",
        "glow": "rgba(236, 72, 153, 0.65)"
    },
    "NATURE & WILDLIFE": {
        "beam": "radial-gradient(circle, rgba(16, 185, 129, 0.35) 0%, rgba(5, 150, 105, 0.14) 40%, rgba(8, 7, 13, 0) 70%)",
        "accent": "#10b981",
        "pill_bg": "rgba(16, 185, 129, 0.12)",
        "pill_border": "rgba(16, 185, 129, 0.45)",
        "pill_text": "#34d399",
        "glow": "rgba(16, 185, 129, 0.65)"
    },
    "SCIENCE & GENIUS": {
        "beam": "radial-gradient(circle, rgba(99, 102, 241, 0.35) 0%, rgba(79, 70, 229, 0.14) 40%, rgba(8, 7, 13, 0) 70%)",
        "accent": "#818cf8",
        "pill_bg": "rgba(99, 102, 241, 0.12)",
        "pill_border": "rgba(99, 102, 241, 0.45)",
        "pill_text": "#a5b4fc",
        "glow": "rgba(99, 102, 241, 0.65)"
    },
    "TRAVEL & MEGASTRUCTURES": {
        "beam": "radial-gradient(circle, rgba(245, 158, 11, 0.35) 0%, rgba(217, 119, 6, 0.14) 40%, rgba(8, 7, 13, 0) 70%)",
        "accent": "#f59e0b",
        "pill_bg": "rgba(245, 158, 11, 0.12)",
        "pill_border": "rgba(245, 158, 11, 0.45)",
        "pill_text": "#fbbf24",
        "glow": "rgba(245, 158, 11, 0.65)"
    }
}

def get_flag_path(code):
    p1 = os.path.abspath(f"assets/flags_hires/{code}.png")
    p2 = os.path.abspath(f"assets/flags/{code}.png")
    path = p1 if os.path.exists(p1) else p2
    return "file:///" + path.replace("\\", "/")

def build_v3_frame(quiz, timer_sec=6, is_reveal=False):
    theme = CATEGORY_THEMES.get(quiz["category"], CATEGORY_THEMES["MOVIES & POP CULTURE"])
    
    circumference = 452.4
    if is_reveal or timer_sec == 0:
        dash_offset = circumference
    else:
        dash_offset = circumference * (1 - (timer_sec / 6.0))
        
    is_urgent = timer_sec <= 2
    ring_color = "#ef4444" if is_urgent else theme["accent"]
    ring_glow = "rgba(239, 68, 68, 0.85)" if is_urgent else theme["glow"]
    
    cards_html = ""
    card_themes = [
        {"glow": "#00d2ff", "border": "rgba(56, 189, 248, 0.7)", "text": "#7dd3fc", "badge": "linear-gradient(135deg, #0ea5e9, #0284c7)"},
        {"glow": "#6366f1", "border": "rgba(129, 140, 248, 0.7)", "text": "#c4b5fd", "badge": "linear-gradient(135deg, #6366f1, #4f46e5)"},
        {"glow": "#10b981", "border": "rgba(52, 211, 153, 0.7)", "text": "#6ee7b7", "badge": "linear-gradient(135deg, #10b981, #059669)"},
        {"glow": "#f59e0b", "border": "rgba(251, 191, 36, 0.7)", "text": "#fcd34d", "badge": "linear-gradient(135deg, #f59e0b, #d97706)"},
    ]

    for i, opt in enumerate(quiz["options"]):
        th = card_themes[i % len(card_themes)]
        flag_url = get_flag_path(opt["code"])
        
        if is_reveal:
            if opt["correct"]:
                cards_html += f"""
                <div class='card-wrapper'>
                  <div class='card-glow' style='background:#10b981;opacity:0.95;filter:blur(44px);'></div>
                  <div class='option-card' style='border:3.5px solid rgba(52,211,153,0.95);background:rgba(6,44,30,0.94);box-shadow:0 0 55px rgba(16,185,129,0.6);'>
                    <div class='letter-pill' style='background:linear-gradient(135deg,#10b981,#059669);font-size:38px;'>✓</div>
                    <img class='flag-thumb' src='{flag_url}'>
                    <div class='country-title' style='color:#34d399;font-size:45px;'>{opt["name"]}</div>
                  </div>
                </div>"""
            else:
                cards_html += f"""
                <div class='card-wrapper'>
                  <div class='card-glow' style='background:#1e293b;opacity:0.1;'></div>
                  <div class='option-card' style='border:2px solid rgba(51,65,85,0.25);opacity:0.32;'>
                    <div class='letter-pill' style='background:#334155;color:#94a3b8;'>{opt["letter"]}</div>
                    <img class='flag-thumb' src='{flag_url}'>
                    <div class='country-title' style='color:#64748b;'>{opt["name"]}</div>
                  </div>
                </div>"""
        else:
            cards_html += f"""
            <div class='card-wrapper'>
              <div class='card-glow' style='background:{th["glow"]};'></div>
              <div class='option-card' style='border:2px solid {th["border"]};'>
                <div class='letter-pill' style='background:{th["badge"]};'>{opt["letter"]}</div>
                <img class='flag-thumb' src='{flag_url}'>
                <div class='country-title' style='color:{th["text"]};'>{opt["name"]}</div>
              </div>
            </div>"""

    if is_reveal:
        fact_card = f"""
        <div class='fact-box'>
          <div class='fact-badge'>💡 DID YOU KNOW?</div>
          <div class='fact-text'>{quiz["fact"]}</div>
        </div>"""
        footer_html = """
        <div class='footer-bar footer-reveal'>
          <div class='footer-text' style='color:#ffffff;font-size:30px;'>🎯 DID YOU GET IT RIGHT? COMMENT YES OR NO! 👇</div>
        </div>"""
    else:
        fact_card = ""
        footer_html = """
        <div class='footer-bar'>
          <div class='footer-text'>💬 Comment your guess before the timer hits 0!</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset='utf-8'>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;0,800;1,600&family=Space+Grotesk:wght@500;600;700&display=swap');
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    width: 1080px; height: 1920px; background: #08070d; font-family: 'Space Grotesk', sans-serif;
    color: white; display: flex; flex-direction: column; align-items: center;
    padding: 80px 70px 70px 70px; overflow: hidden; position: relative;
  }}
  .light-beam {{
    position: absolute; top: 12%; left: 50%; transform: translate(-50%, -20%);
    width: 1000px; height: 1000px;
    background: {theme["beam"]};
    pointer-events: none; z-index: 1;
  }}
  .channel-name {{
    position: absolute; top: 25px; right: 28px; font-size: 22px; font-weight: 700;
    color: rgba(255, 255, 255, 0.45); letter-spacing: 2px; z-index: 10;
  }}
  .content {{
    position: relative; z-index: 2; width: 100%; display: flex; flex-direction: column;
    align-items: center; height: 100%;
  }}
  .badges-row {{
    display: flex; align-items: center; gap: 16px; margin-bottom: 30px;
  }}
  .category-pill {{
    background: {theme["pill_bg"]}; border: 1.5px solid {theme["pill_border"]};
    backdrop-filter: blur(16px); color: {theme["pill_text"]}; padding: 10px 28px; border-radius: 999px;
    font-size: 20px; font-weight: 700; letter-spacing: 1.8px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
  }}
  .difficulty-pill {{
    background: rgba(239, 68, 68, 0.15); border: 1.5px solid rgba(239, 68, 68, 0.45);
    backdrop-filter: blur(16px); color: #f87171; padding: 10px 24px; border-radius: 999px;
    font-size: 20px; font-weight: 700; letter-spacing: 1.5px;
    box-shadow: 0 4px 20px rgba(239, 68, 68, 0.2);
  }}
  .question-box {{ text-align: center; max-width: 960px; margin-bottom: 30px; }}
  .question-title {{
    font-family: 'Playfair Display', serif; font-size: 54px; font-weight: 700;
    line-height: 1.32; color: #ffffff; letter-spacing: -0.5px;
    text-shadow: 0 4px 25px rgba(0, 0, 0, 0.85);
  }}
  .clue-badge-box {{
    margin-top: 16px; display: inline-flex; align-items: center; gap: 12px;
    background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(148, 163, 184, 0.25);
    padding: 8px 24px; border-radius: 999px;
  }}
  .clue-label {{ font-size: 20px; font-weight: 700; color: #fbbf24; letter-spacing: 1px; }}
  .clue-text {{ font-size: 23px; color: #cbd5e1; font-weight: 600; }}
  
  .timer-svg-container {{
    position: relative; width: 175px; height: 175px; margin-bottom: 75px;
    display: flex; align-items: center; justify-content: center;
  }}
  .timer-svg-glow {{
    position: absolute; inset: -20px; border-radius: 50%;
    background: {ring_glow}; filter: blur(36px); opacity: 0.65; z-index: 1;
  }}
  .timer-svg-circle {{
    position: absolute; inset: 0; width: 175px; height: 175px; z-index: 2;
    transform: rotate(-90deg);
  }}
  .timer-inner-card {{
    position: relative; z-index: 3; width: 140px; height: 140px; border-radius: 50%;
    background: rgba(13, 16, 27, 0.94); backdrop-filter: blur(24px);
    display: flex; align-items: center; justify-content: center;
    box-shadow: inset 0 2px 10px rgba(255, 255, 255, 0.1), 0 12px 30px rgba(0,0,0,0.8);
  }}
  .timer-num {{ font-size: 72px; font-weight: 800; color: {ring_color}; letter-spacing: -1px; }}
  
  .options-container {{
    width: 100%; display: flex; flex-direction: column; gap: 34px;
  }}
  .card-wrapper {{ position: relative; width: 100%; height: 136px; }}
  .card-glow {{
    position: absolute; inset: -10px; border-radius: 36px; filter: blur(36px);
    opacity: 0.65; z-index: 1;
  }}
  .option-card {{
    position: relative; z-index: 2; width: 100%; height: 100%; border-radius: 28px;
    display: flex; align-items: center; padding: 0 34px; background: rgba(13, 16, 27, 0.88);
    backdrop-filter: blur(24px); box-shadow: 0 16px 36px rgba(0,0,0,0.85);
  }}
  .letter-pill {{
    width: 68px; height: 68px; border-radius: 20px; display: flex; align-items: center;
    justify-content: center; font-size: 32px; font-weight: 700; margin-right: 28px;
    color: white; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
  }}
  .flag-thumb {{
    width: 92px; height: 62px; border-radius: 12px; object-fit: cover; margin-right: 28px;
    border: 1.5px solid rgba(255, 255, 255, 0.22); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.6);
  }}
  .country-title {{ font-size: 40px; font-weight: 700; letter-spacing: 1px; }}

  .fact-box {{
    margin-top: 25px; width: 100%; padding: 20px 30px; border-radius: 22px;
    background: rgba(16, 185, 129, 0.12); border: 1.5px solid rgba(52, 211, 153, 0.5);
    backdrop-filter: blur(20px); display: flex; flex-direction: column; gap: 8px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
  }}
  .fact-badge {{ font-size: 20px; font-weight: 700; color: #34d399; letter-spacing: 1.5px; }}
  .fact-text {{ font-size: 24px; color: #e2e8f0; font-weight: 600; line-height: 1.3; }}

  .footer-bar {{
    margin-top: 35px; width: 100%; padding: 24px 32px; border-radius: 999px;
    background: rgba(245, 158, 11, 0.08); border: 1.5px solid rgba(245, 158, 11, 0.35);
    backdrop-filter: blur(20px); text-align: center;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5), 0 0 30px rgba(245, 158, 11, 0.15);
  }}
  .footer-reveal {{
    background: rgba(245, 158, 11, 0.18); border: 2px solid rgba(251, 191, 36, 0.85);
    box-shadow: 0 0 50px rgba(245, 158, 11, 0.4);
  }}
  .footer-text {{ font-size: 26px; font-weight: 700; color: #fbbf24; letter-spacing: 0.5px; }}
</style>
</head>
<body>
  <div class='light-beam'></div>
  <div class='channel-name'>LR ATLAS</div>
  <div class='content'>
    <div class='badges-row'>
      <div class='category-pill'>{quiz["category"]}</div>
      <div class='difficulty-pill'>🧠 {quiz["difficulty"]}</div>
    </div>
    <div class='question-box'>
      <div class='question-title'>{quiz["question"]}</div>
      <div class='clue-badge-box'>
        <span class='clue-label'>💡 CLUE:</span>
        <span class='clue-text'>{quiz["clue"]}</span>
      </div>
    </div>
    
    <div class='timer-svg-container'>
      <div class='timer-svg-glow'></div>
      <svg class='timer-svg-circle' viewBox='0 0 175 175'>
        <!-- Background track -->
        <circle cx='87.5' cy='87.5' r='72' stroke='rgba(255,255,255,0.1)' stroke-width='8' fill='none'/>
        <!-- Depleting countdown arc -->
        <circle cx='87.5' cy='87.5' r='72' stroke='{ring_color}' stroke-width='8' fill='none'
                stroke-dasharray='452.4' stroke-dashoffset='{dash_offset}' stroke-linecap='round'/>
      </svg>
      <div class='timer-inner-card'>
        <span class='timer-num'>{timer_sec}</span>
      </div>
    </div>

    <div class='options-container'>
      {cards_html}
    </div>
    {fact_card}
    {footer_html}
  </div>
</body>
</html>"""

def render_frame_img(html_str, out_fp, temp_html_fp):
    with open(temp_html_fp, "w", encoding="utf-8") as f:
        f.write(html_str)
    cmd = [
        CHROME, "--headless=new",
        f"--screenshot={os.path.abspath(out_fp)}",
        "--window-size=1080,1920",
        "--hide-scrollbars",
        "--allow-file-access-from-files",
        "file:///" + os.path.abspath(temp_html_fp).replace("\\", "/")
    ]
    subprocess.run(cmd, capture_output=True, check=True)

def render_single_v3_drop(quiz):
    q_dir = os.path.join(OUTPUT_BASE, quiz["id"])
    f_dir = os.path.join(q_dir, "frames")
    a_dir = os.path.join(q_dir, "audio")
    os.makedirs(f_dir, exist_ok=True)
    os.makedirs(a_dir, exist_ok=True)
    final_mp4 = os.path.join(q_dir, f"{quiz['id']}.mp4")

    if os.path.exists(final_mp4) and os.path.getsize(final_mp4) > 1000000:
        print(f"  ⚡ Already rendered: {final_mp4}")
        return final_mp4

    print(f"\n🎬 RENDERING V3 INTERACTIVE: {quiz['id']} ({quiz['category']})")
    print(f"🎙️ Voice: {quiz['voice']} | Difficulty: {quiz['difficulty']}")

    # 1. Edge-TTS Narration
    scenes = [
        ("scene_1", quiz["narration_hook"]),
        ("scene_2", quiz["narration_countdown"]),
        ("scene_3", quiz["narration_reveal"])
    ]
    durations = []
    for sid, text in scenes:
        mp3 = os.path.join(a_dir, f"{sid}.mp3")
        wav = os.path.join(a_dir, f"{sid}.wav")
        asyncio.run(edge_tts.Communicate(text, quiz["voice"], rate="+0%").save(mp3))
        subprocess.run(["ffmpeg", "-y", "-i", mp3, "-ar", "44100", "-ac", "2", wav], capture_output=True, check=True)
        dur = float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", wav
        ]).decode().strip())
        durations.append(dur)

    dur_s1 = durations[0]
    dur_s2 = max(6.0, durations[1])
    dur_s3 = durations[2]
    total_dur = dur_s1 + dur_s2 + dur_s3
    print(f"  ✓ Voice generated ({total_dur:.2f}s)")

    # 2. Chrome Keyframe Renders
    temp_html = os.path.join(q_dir, "_temp.html")
    f_q = os.path.join(f_dir, "question.png")
    render_frame_img(build_v3_frame(quiz, timer_sec=6, is_reveal=False), f_q, temp_html)

    for sec in [6, 5, 4, 3, 2, 1]:
        render_frame_img(build_v3_frame(quiz, timer_sec=sec, is_reveal=False), os.path.join(f_dir, f"countdown_{sec}.png"), temp_html)

    f_rev = os.path.join(f_dir, "reveal.png")
    render_frame_img(build_v3_frame(quiz, timer_sec=0, is_reveal=True), f_rev, temp_html)
    print("  ✓ Chrome dynamic frames rendered")

    # 3. Assemble Segments
    sec_dur = dur_s2 / 6.0
    segs = [
        (f_q, dur_s1),
        (os.path.join(f_dir, "countdown_6.png"), sec_dur),
        (os.path.join(f_dir, "countdown_5.png"), sec_dur),
        (os.path.join(f_dir, "countdown_4.png"), sec_dur),
        (os.path.join(f_dir, "countdown_3.png"), sec_dur),
        (os.path.join(f_dir, "countdown_2.png"), sec_dur),
        (os.path.join(f_dir, "countdown_1.png"), sec_dur),
        (f_rev, dur_s3),
    ]
    seg_files = []
    for i, (img, dur) in enumerate(segs):
        s_mp4 = os.path.join(q_dir, f"seg_{i}.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", img,
            "-c:v", "libx264", "-t", f"{dur:.3f}",
            "-pix_fmt", "yuv420p", "-vf", f"scale={WIDTH}:{HEIGHT}",
            "-r", str(FPS), "-preset", "veryfast", "-crf", "18",
            s_mp4
        ], capture_output=True, check=True)
        seg_files.append(s_mp4)

    concat_txt = os.path.join(q_dir, "concat.txt")
    with open(concat_txt, "w") as f:
        for sf in seg_files:
            f.write(f"file '{os.path.abspath(sf).replace(os.sep, '/')}'\n")

    raw_v = os.path.join(q_dir, "raw_video.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_txt, "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "veryfast", "-crf", "18", raw_v
    ], capture_output=True, check=True)

    # 4. Master Audio & SFX
    tick_fp = os.path.join(a_dir, "tick.wav")
    sample_rate = 44100
    t = np.linspace(0, 0.08, int(sample_rate * 0.08), False)
    tick_wave = np.sin(2 * np.pi * 1400 * t) * np.exp(-t * 60)
    tick_wave = (tick_wave / np.max(np.abs(tick_wave)) * 30000).astype(np.int16)
    with wave.open(tick_fp, 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(tick_wave.tobytes())

    wav_s1 = os.path.join(a_dir, "scene_1.wav")
    wav_s2 = os.path.join(a_dir, "scene_2.wav")
    wav_s3 = os.path.join(a_dir, "scene_3.wav")
    sfx_impact = "assets/sfx/shorts_impact.wav"
    sfx_cash = "assets/sfx/shorts_cash_bell.wav"
    sfx_whoosh = "assets/sfx/shorts_whoosh.wav"
    bg_music = "assets/audio/music/tension_riser.wav"

    m_audio = os.path.join(q_dir, "mastered_audio.wav")
    filter_parts = [
        f"[0:a]adelay=0|0,apad=whole_dur={total_dur}[nar1]",
        f"[1:a]adelay={int(dur_s1*1000)}|{int(dur_s1*1000)},apad=whole_dur={total_dur}[nar2]",
        f"[2:a]adelay={int((dur_s1+dur_s2)*1000)}|{int((dur_s1+dur_s2)*1000)},apad=whole_dur={total_dur}[nar3]",
        f"[3:a]volume=0.6,adelay=150|150,apad=whole_dur={total_dur}[sfx_w]",
        f"[4:a]volume=0.85,adelay={int((dur_s1+dur_s2)*1000)}|{int((dur_s1+dur_s2)*1000)},apad=whole_dur={total_dur}[sfx_imp]",
        f"[5:a]volume=0.95,adelay={int((dur_s1+dur_s2+0.3)*1000)}|{int((dur_s1+dur_s2+0.3)*1000)},apad=whole_dur={total_dur}[sfx_c]",
    ]
    for k in range(6):
        d_ms = int((dur_s1 + k * sec_dur + 0.25) * 1000)
        vol = 0.9 + k * 0.08
        filter_parts.append(f"[6:a]volume={vol:.2f},adelay={d_ms}|{d_ms},apad=whole_dur={total_dur}[tk{k}]")

    filter_parts.append(f"[7:a]volume=0.12,atrim=0:{total_dur},afade=t=out:st={total_dur-1.5}:d=1.5[bgm]")
    t_labels = "".join(f"[tk{k}]" for k in range(6))
    filter_parts.append(
        f"[nar1][nar2][nar3][sfx_w][sfx_imp][sfx_c]{t_labels}[bgm]"
        f"amix=inputs=13:duration=longest:dropout_transition=2,"
        f"atrim=0:{total_dur},loudnorm=I=-14:LRA=7:tp=-1.5[outa]"
    )

    subprocess.run([
        "ffmpeg", "-y",
        "-i", wav_s1, "-i", wav_s2, "-i", wav_s3,
        "-i", sfx_whoosh, "-i", sfx_impact, "-i", sfx_cash,
        "-i", tick_fp, "-i", bg_music,
        "-filter_complex", ";".join(filter_parts),
        "-map", "[outa]", m_audio
    ], capture_output=True, check=True)

    # 5. Final Mux
    subprocess.run([
        "ffmpeg", "-y", "-i", raw_v, "-i", m_audio,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        final_mp4
    ], capture_output=True, check=True)

    for sf in seg_files:
        try: os.remove(sf)
        except: pass
    try: os.remove(raw_v)
    except: pass

    print(f"  ✓ V3 Video Ready: {final_mp4}")
    return final_mp4

def main():
    series = get_v3_interactive_series()
    manifest_fp = os.path.join(OUTPUT_BASE, "manifest_v3.json")
    manifest = {}
    if os.path.exists(manifest_fp):
        with open(manifest_fp, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    print("=" * 70)
    print("🚀 LR ATLAS: V3 INTERACTIVE VIDEO SERIES RENDERER")
    print(f"📊 Total New Drops: {len(series)}")
    print("=" * 70)

    for idx, quiz in enumerate(series):
        qid = quiz["id"]
        print(f"[{idx+1}/{len(series)}] Processing {qid}...")
        mp4_path = render_single_v3_drop(quiz)
        manifest[qid] = {
            "id": qid,
            "day": quiz["day"],
            "slot": quiz["slot"],
            "category": quiz["category"],
            "title": quiz["youtube_title"],
            "schedule_label": quiz["schedule_label"],
            "schedule_time": quiz["schedule_time"],
            "video_path": mp4_path,
            "rendered": True,
            "uploaded": False
        }
        with open(manifest_fp, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("🏆 ALL 10 V3 INTERACTIVE DROPS SUCCESSFULLY PRE-RENDERED!")
    print("=" * 70)

if __name__ == "__main__":
    main()
