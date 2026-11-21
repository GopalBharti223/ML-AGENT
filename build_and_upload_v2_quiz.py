"""
Production-Ready V2 Quiz Engine & Daily Auto-Uploader for LR Atlas.
Supports:
- Enlarged 165px circular countdown clock with glowing shadow
- Shifted options downwards with balanced vertical spacing
- 6-second timer with urgent crimson shift on 2s/1s
- Luxury champagne-gold glass bottom bar
- Scheduling via YouTube API (e.g. 9:00 PM IST)
"""

import os
import sys
import math
import wave
import subprocess
import asyncio
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import edge_tts
from quiz_database import get_quiz_by_id

WIDTH = 1080
HEIGHT = 1920
FPS = 30
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# CLI Arguments: quiz_id and optional schedule ISO timestamp
quiz_id = sys.argv[1] if len(sys.argv) > 1 else "quiz_02_ai_chips"
schedule_time = sys.argv[2] if len(sys.argv) > 2 else None

quiz = get_quiz_by_id(quiz_id)

output_dir = os.path.join("output", f"quiz_v2_{quiz['id']}")
frames_dir = os.path.join(output_dir, "frames")
audio_dir = os.path.join(output_dir, "audio")
os.makedirs(frames_dir, exist_ok=True)
os.makedirs(audio_dir, exist_ok=True)

print("="*60)
print(f"🎬 BUILDING V2 QUIZ SHORT: {quiz['id']} ({quiz['category']})")
if schedule_time:
    print(f"⏰ Schedule Target: {schedule_time} (9:00 PM IST)")
print("="*60)

# ----------------------------------------------------------------------
# 1. GENERATE TIGHT, FAST-PACED NARRATION (~15.5s TOTAL)
# ----------------------------------------------------------------------
VOICE = "en-US-BrianNeural"
VOICE_RATE = "+0%"

async def generate_narration():
    scenes = [
        ("scene_1", quiz["narration_hook"]),
        ("scene_2", quiz["narration_countdown"]),
        ("scene_3", quiz["narration_reveal"])
    ]
    durations = []
    for sid, text in scenes:
        mp3 = os.path.join(audio_dir, f"{sid}.mp3")
        wav = os.path.join(audio_dir, f"{sid}.wav")
        comm = edge_tts.Communicate(text, VOICE, rate=VOICE_RATE)
        await comm.save(mp3)
        subprocess.run(["ffmpeg", "-y", "-i", mp3, "-ar", "44100", "-ac", "2", wav], capture_output=True, check=True)
        dur = float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", wav
        ]).decode().strip())
        durations.append(dur)
        print(f"  🎙️ {sid}: {dur:.2f}s")
    return durations

durations = asyncio.run(generate_narration())
DUR_S1 = durations[0]
DUR_S2 = max(6.0, durations[1])  # Exact 6.0s for the 6-second countdown
DUR_S3 = durations[2]
TOTAL_DURATION = DUR_S1 + DUR_S2 + DUR_S3
TOTAL_FRAMES = int(TOTAL_DURATION * FPS)

print(f"\n⏱️ Optimized Video Timeline:")
print(f"  Hook & Question: 0.00s -> {DUR_S1:.2f}s")
print(f"  6-Second Ticking Timer: {DUR_S1:.2f}s -> {DUR_S1 + DUR_S2:.2f}s")
print(f"  Reveal & Subscribe: {DUR_S1 + DUR_S2:.2f}s -> {TOTAL_DURATION:.2f}s")
print(f"  Total Duration: {TOTAL_DURATION:.2f}s (High-retention pace!)")

# ----------------------------------------------------------------------
# 2. HTML GENERATOR WITH 165px CLOCK & LOWERED OPTIONS
# ----------------------------------------------------------------------
def get_flag_path(code):
    p1 = os.path.abspath(f"assets/flags_hires/{code}.png")
    p2 = os.path.abspath(f"assets/flags/{code}.png")
    path = p1 if os.path.exists(p1) else p2
    return "file:///" + path.replace("\\", "/")

def build_html_frame(timer_sec=6, timer_urgent=False, is_reveal=False):
    timer_col = "#ef4444" if timer_urgent else "#38bdf8"
    timer_glow = "rgba(239, 68, 68, 0.75)" if timer_urgent else "rgba(56, 189, 248, 0.55)"
    timer_border = "rgba(239, 68, 68, 0.85)" if timer_urgent else "rgba(56, 189, 248, 0.65)"

    themes = [
        {"glow": "#00d2ff", "border": "rgba(56, 189, 248, 0.7)", "text": "#7dd3fc", "badge": "linear-gradient(135deg, #0ea5e9, #0284c7)"},
        {"glow": "#6366f1", "border": "rgba(129, 140, 248, 0.7)", "text": "#c4b5fd", "badge": "linear-gradient(135deg, #6366f1, #4f46e5)"},
        {"glow": "#10b981", "border": "rgba(52, 211, 153, 0.7)", "text": "#6ee7b7", "badge": "linear-gradient(135deg, #10b981, #059669)"},
        {"glow": "#f59e0b", "border": "rgba(251, 191, 36, 0.7)", "text": "#fcd34d", "badge": "linear-gradient(135deg, #f59e0b, #d97706)"},
    ]

    cards_html = ""
    for i, opt in enumerate(quiz["options"]):
        th = themes[i % len(themes)]
        flag_url = get_flag_path(opt["code"])
        
        if is_reveal:
            if opt["correct"]:
                cards_html += f"""
                <div class='card-wrapper'>
                  <div class='card-glow' style='background:#10b981;opacity:0.92;filter:blur(42px);'></div>
                  <div class='option-card' style='border:3px solid rgba(52,211,153,0.95);background:rgba(6,44,30,0.92);box-shadow:0 0 50px rgba(16,185,129,0.55);'>
                    <div class='letter-pill' style='background:linear-gradient(135deg,#10b981,#059669);'>✓</div>
                    <img class='flag-thumb' src='{flag_url}'>
                    <div class='country-title' style='color:#34d399;font-size:45px;'>{opt["name"]}</div>
                  </div>
                </div>"""
            else:
                cards_html += f"""
                <div class='card-wrapper'>
                  <div class='card-glow' style='background:#1e293b;opacity:0.15;'></div>
                  <div class='option-card' style='border:2px solid rgba(51,65,85,0.3);opacity:0.35;'>
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
        footer_html = """
        <div class='footer-bar footer-reveal'>
          <div class='footer-text' style='color:#ffffff;font-size:30px;'>🔔 SUBSCRIBE FOR DAILY TRIVIA QUIZZES!</div>
        </div>"""
    else:
        footer_html = """
        <div class='footer-bar'>
          <div class='footer-text'>💬 Comment your guess before time runs out</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset='utf-8'>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;0,800;1,600&family=Space+Grotesk:wght@500;600;700&display=swap');
  
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  
  body {{
    width: 1080px;
    height: 1920px;
    background: #08070d;
    font-family: 'Space Grotesk', sans-serif;
    color: white;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 85px 70px 75px 70px;
    overflow: hidden;
    position: relative;
  }}
  
  .light-beam {{
    position: absolute;
    top: 15%;
    left: 50%;
    transform: translate(-50%, -20%);
    width: 950px;
    height: 950px;
    background: radial-gradient(circle, rgba(139, 92, 246, 0.28) 0%, rgba(99, 102, 241, 0.12) 40%, rgba(8, 7, 13, 0) 70%);
    pointer-events: none;
    z-index: 1;
  }}
  
  .content {{
    position: relative;
    z-index: 2;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    height: 100%;
  }}
  
  .channel-name {{
    position: absolute;
    top: 25px;
    right: 25px;
    font-size: 22px;
    font-weight: 700;
    color: rgba(148, 163, 184, 0.7);
    letter-spacing: 1.5px;
    z-index: 10;
  }}
  
  .category-pill {{
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.12);
    backdrop-filter: blur(16px);
    color: #94a3b8;
    padding: 10px 34px;
    border-radius: 999px;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 2px;
    margin-bottom: 35px;
  }}
  
  .question-box {{
    text-align: center;
    max-width: 960px;
    margin-bottom: 35px;
  }}
  
  .question-title {{
    font-family: 'Playfair Display', serif;
    font-size: 56px;
    font-weight: 700;
    line-height: 1.32;
    color: #ffffff;
    letter-spacing: -0.5px;
    text-shadow: 0 4px 25px rgba(0, 0, 0, 0.85);
  }}
  
  .question-clue {{
    margin-top: 18px;
    font-size: 26px;
    color: #94a3b8;
    font-weight: 600;
  }}
  
  /* ENLARGED 165px CIRCULAR CLOCK */
  .timer-circle-wrapper {{
    position: relative;
    width: 165px;
    height: 165px;
    margin-bottom: 95px; /* Deep spacing to lower options */
  }}
  
  .timer-circle-glow {{
    position: absolute;
    inset: -26px;
    border-radius: 50%;
    filter: blur(34px);
    opacity: 0.75;
    background: {timer_glow};
  }}
  
  .timer-circle {{
    position: relative;
    z-index: 2;
    width: 165px;
    height: 165px;
    border-radius: 50%;
    background: rgba(13, 16, 27, 0.92);
    backdrop-filter: blur(20px);
    border: 4px solid {timer_border};
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 14px 40px rgba(0, 0, 0, 0.8);
  }}
  
  .timer-num {{
    font-size: 72px;
    font-weight: 700;
    color: {timer_col};
    letter-spacing: -1px;
  }}
  
  /* 4 OPTION CARDS - EXPANDED & SHIFTED DOWN */
  .options-container {{
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 40px;
    margin-top: 10px;
  }}
  
  .card-wrapper {{
    position: relative;
    width: 100%;
    height: 142px;
  }}
  
  .card-glow {{
    position: absolute;
    inset: -10px;
    border-radius: 38px;
    filter: blur(36px);
    opacity: 0.65;
    z-index: 1;
  }}
  
  .option-card {{
    position: relative;
    z-index: 2;
    width: 100%;
    height: 100%;
    border-radius: 28px;
    display: flex;
    align-items: center;
    padding: 0 34px;
    background: rgba(13, 16, 27, 0.88);
    backdrop-filter: blur(24px);
    box-shadow: 0 16px 36px rgba(0,0,0,0.85);
  }}
  
  .letter-pill {{
    width: 72px;
    height: 72px;
    border-radius: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 34px;
    font-weight: 700;
    margin-right: 28px;
    color: white;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
  }}
  
  .flag-thumb {{
    width: 96px;
    height: 64px;
    border-radius: 12px;
    object-fit: cover;
    margin-right: 28px;
    border: 1.5px solid rgba(255, 255, 255, 0.22);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.6);
  }}
  
  .country-title {{
    font-size: 42px;
    font-weight: 700;
    letter-spacing: 1px;
  }}
  
  /* REFINED LUXURY BOTTOM BAR (NO HARSH RED!) */
  .footer-bar {{
    margin-top: 55px;
    width: 100%;
    padding: 26px 36px;
    border-radius: 999px;
    background: rgba(245, 158, 11, 0.08);
    border: 1.5px solid rgba(245, 158, 11, 0.35);
    backdrop-filter: blur(20px);
    text-align: center;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5), 0 0 30px rgba(245, 158, 11, 0.15);
  }}
  
  .footer-reveal {{
    background: rgba(251, 191, 36, 0.15);
    border: 2px solid rgba(251, 191, 36, 0.7);
    box-shadow: 0 0 50px rgba(245, 158, 11, 0.35);
  }}
  
  .footer-text {{
    font-size: 26px;
    font-weight: 700;
    color: #fbbf24;
    letter-spacing: 0.5px;
  }}
</style>
</head>
<body>
  <div class='light-beam'></div>
  <div class='channel-name'>LR ATLAS</div>
  
  <div class='content'>
    <div class='category-pill'>{quiz["category"]}</div>
    
    <div class='question-box'>
      <div class='question-title'>{quiz["question"]}</div>
      <div class='question-clue'>{quiz["clue"]}</div>
    </div>
    
    <div class='timer-circle-wrapper'>
      <div class='timer-circle-glow'></div>
      <div class='timer-circle'>
        <span class='timer-num'>{timer_sec}</span>
      </div>
    </div>
    
    <div class='options-container'>
      {cards_html}
    </div>
    
    {footer_html}
  </div>
</body>
</html>"""

# ----------------------------------------------------------------------
# 3. RENDER KEYFRAMES VIA CHROME HEADLESS
# ----------------------------------------------------------------------
def render_frame_img(html_str, filename):
    html_fp = os.path.join(output_dir, "_temp.html")
    with open(html_fp, "w", encoding="utf-8") as f:
        f.write(html_str)
    out_fp = os.path.join(frames_dir, filename)
    cmd = [
        CHROME, "--headless=new",
        f"--screenshot={os.path.abspath(out_fp)}",
        "--window-size=1080,1920",
        "--hide-scrollbars",
        "--allow-file-access-from-files",
        "file:///" + os.path.abspath(html_fp).replace("\\", "/")
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out_fp

print("\n📸 Rendering Keyframes via Chrome Engine...")
f_question = render_frame_img(build_html_frame(timer_sec=6, timer_urgent=False), "question.png")
print("  ✓ Question Frame (Hook)")

for sec in [6, 5, 4, 3, 2, 1]:
    is_urgent = sec <= 2
    f_tick = render_frame_img(build_html_frame(timer_sec=sec, timer_urgent=is_urgent), f"countdown_{sec}.png")
    print(f"  ✓ Countdown {sec}s {'(🚨 URGENT CRIMSON)' if is_urgent else ''}")

f_reveal = render_frame_img(build_html_frame(timer_sec=0, timer_urgent=True, is_reveal=True), "reveal.png")
print("  ✓ Answer Reveal Frame")

# ----------------------------------------------------------------------
# 4. ASSEMBLE TIGHT 15.5-SECOND VIDEO
# ----------------------------------------------------------------------
print("\n🎬 Assembling Video Segments...")
sec_dur = DUR_S2 / 6.0

segments = [
    (f_question, DUR_S1),
    (os.path.join(frames_dir, "countdown_6.png"), sec_dur),
    (os.path.join(frames_dir, "countdown_5.png"), sec_dur),
    (os.path.join(frames_dir, "countdown_4.png"), sec_dur),
    (os.path.join(frames_dir, "countdown_3.png"), sec_dur),
    (os.path.join(frames_dir, "countdown_2.png"), sec_dur),
    (os.path.join(frames_dir, "countdown_1.png"), sec_dur),
    (f_reveal, DUR_S3),
]

seg_files = []
for i, (img_path, dur) in enumerate(segments):
    seg_mp4 = os.path.join(output_dir, f"seg_{i}.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", img_path,
        "-c:v", "libx264", "-t", f"{dur:.3f}",
        "-pix_fmt", "yuv420p", "-vf", f"scale={WIDTH}:{HEIGHT}",
        "-r", str(FPS), "-preset", "veryfast", "-crf", "18",
        seg_mp4
    ], capture_output=True, check=True)
    seg_files.append(seg_mp4)

concat_txt = os.path.join(output_dir, "concat.txt")
with open(concat_txt, "w") as f:
    for seg in seg_files:
        f.write(f"file '{os.path.abspath(seg).replace(os.sep, '/')}'\n")

raw_video = os.path.join(output_dir, "raw_video.mp4")
subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", concat_txt, "-c:v", "libx264", "-pix_fmt", "yuv420p",
    "-preset", "veryfast", "-crf", "18", raw_video
], capture_output=True, check=True)
print("  ✓ Video stream concatenated.")

# ----------------------------------------------------------------------
# 5. MASTER AUDIO WITH 6 CLOCK TICKS & SFX
# ----------------------------------------------------------------------
print("\n🎵 Mastering Audio with 6 Clock Ticks & SFX...")

sample_rate = 44100
t = np.linspace(0, 0.08, int(sample_rate * 0.08), False)
tick_wave = np.sin(2 * np.pi * 1400 * t) * np.exp(-t * 60)
tick_wave = (tick_wave / np.max(np.abs(tick_wave)) * 30000).astype(np.int16)
tick_fp = os.path.join(audio_dir, "clock_tick.wav")
with wave.open(tick_fp, 'w') as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(sample_rate)
    f.writeframes(tick_wave.tobytes())

wav_s1 = os.path.join(audio_dir, "scene_1.wav")
wav_s2 = os.path.join(audio_dir, "scene_2.wav")
wav_s3 = os.path.join(audio_dir, "scene_3.wav")

sfx_impact = "assets/sfx/shorts_impact.wav"
sfx_cash = "assets/sfx/shorts_cash_bell.wav"
sfx_whoosh = "assets/sfx/shorts_whoosh.wav"
bg_music = "assets/audio/music/tension_riser.wav"

mastered_audio = os.path.join(output_dir, "mastered_audio.wav")

filter_parts = [
    f"[0:a]adelay=0|0,apad=whole_dur={TOTAL_DURATION}[nar1]",
    f"[1:a]adelay={int(DUR_S1*1000)}|{int(DUR_S1*1000)},apad=whole_dur={TOTAL_DURATION}[nar2]",
    f"[2:a]adelay={int((DUR_S1+DUR_S2)*1000)}|{int((DUR_S1+DUR_S2)*1000)},apad=whole_dur={TOTAL_DURATION}[nar3]",
    f"[3:a]volume=0.6,adelay=150|150,apad=whole_dur={TOTAL_DURATION}[sfx_w]",
    f"[4:a]volume=0.85,adelay={int((DUR_S1+DUR_S2)*1000)}|{int((DUR_S1+DUR_S2)*1000)},apad=whole_dur={TOTAL_DURATION}[sfx_imp]",
    f"[5:a]volume=0.95,adelay={int((DUR_S1+DUR_S2+0.3)*1000)}|{int((DUR_S1+DUR_S2+0.3)*1000)},apad=whole_dur={TOTAL_DURATION}[sfx_c]",
]

for i in range(6):
    delay_ms = int((DUR_S1 + i * sec_dur + 0.25) * 1000)
    vol = 0.9 + i * 0.08
    filter_parts.append(f"[6:a]volume={vol:.2f},adelay={delay_ms}|{delay_ms},apad=whole_dur={TOTAL_DURATION}[tk{i}]")

filter_parts.append(f"[7:a]volume=0.12,atrim=0:{TOTAL_DURATION},afade=t=out:st={TOTAL_DURATION-1.5}:d=1.5[bgm]")

tick_labels = "".join(f"[tk{i}]" for i in range(6))
filter_parts.append(
    f"[nar1][nar2][nar3][sfx_w][sfx_imp][sfx_c]{tick_labels}[bgm]"
    f"amix=inputs=13:duration=longest:dropout_transition=2,"
    f"atrim=0:{TOTAL_DURATION},loudnorm=I=-14:LRA=7:tp=-1.5[outa]"
)

cmd_audio = [
    "ffmpeg", "-y",
    "-i", wav_s1, "-i", wav_s2, "-i", wav_s3,
    "-i", sfx_whoosh, "-i", sfx_impact, "-i", sfx_cash,
    "-i", tick_fp, "-i", bg_music,
    "-filter_complex", ";".join(filter_parts),
    "-map", "[outa]",
    mastered_audio
]
subprocess.run(cmd_audio, capture_output=True, check=True)

final_mp4 = os.path.join(output_dir, f"{quiz['id']}_master_v2.mp4")
subprocess.run([
    "ffmpeg", "-y",
    "-i", raw_video, "-i", mastered_audio,
    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
    final_mp4
], capture_output=True, check=True)

actual_dur = subprocess.check_output([
    "ffprobe", "-v", "error", "-show_entries", "format=duration",
    "-of", "default=noprint_wrappers=1:nokey=1", final_mp4
]).decode().strip()

print(f"\n✅ MASTER SHORT READY: {final_mp4} ({float(actual_dur):.2f}s)")

# ----------------------------------------------------------------------
# 6. UPLOAD / SCHEDULE TO YOUTUBE
# ----------------------------------------------------------------------
print("\n🚀 Uploading to YouTube Channel (LR Atlas)...")

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

creds = Credentials.from_authorized_user_file("youtube_token.json")
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
    with open("youtube_token.json", "w") as f:
        f.write(creds.to_json())

youtube = build("youtube", "v3", credentials=creds)

privacy = "private" if schedule_time else "public"
status_dict = {
    "privacyStatus": privacy,
    "selfDeclaredMadeForKids": False,
    "madeForKids": False,
}
if schedule_time:
    status_dict["publishAt"] = schedule_time

body = {
    "snippet": {
        "title": quiz["youtube_title"],
        "description": (
            f"{quiz['question']}\n\n"
            f"💡 Clue: {quiz['clue']}\n\n"
            "Drop your guess in the comments before the clock hits zero! 👇\n\n"
            "Subscribe to LR Atlas for daily brain & trivia quizzes! 🔔\n\n"
            + " ".join(f"#{t.replace(' ', '')}" for t in quiz["tags"])
        ),
        "tags": quiz["tags"],
        "categoryId": "27",
    },
    "status": status_dict,
}

media = MediaFileUpload(final_mp4, mimetype="video/mp4", resumable=True)
request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

response = None
while response is None:
    status, response = request.next_chunk()
    if status:
        print(f"  Uploading: {int(status.progress() * 100)}%")

video_id = response["id"]
video_url = f"https://youtube.com/shorts/{video_id}"
print(f"\n🎉 UPLOADED & SCHEDULED SUCCESSFULLY!")
print(f"📺 Video ID: {video_id}")
print(f"🔗 URL: {video_url}")
if schedule_time:
    print(f"⏰ Scheduled To Go Public At: 9:00 PM IST ({schedule_time})")

# Post comment
try:
    comment_body = {
        "snippet": {
            "videoId": video_id,
            "topLevelComment": {
                "snippet": {
                    "textOriginal": "Did you guess it before the clock turned red? Let us know your score below! 👇🧠"
                }
            }
        }
    }
    comment_res = youtube.commentThreads().insert(part="snippet", body=comment_body).execute()
    print("  💬 Pinned engagement comment posted successfully!")
except Exception as e:
    print(f"  Note on comment: {e}")

print("="*60)
print(f"🚀 SCHEDULED VIDEO READY: {video_url}")
print("="*60)
