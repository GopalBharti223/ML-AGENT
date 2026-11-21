"""
FINAL QUIZ SHORT: Build + Render + Master Audio + Upload to YouTube.
Design: CodeHelp ONE luxury glassmorphism with distinct neon glowing shadows.
Timeline: Scene1(7.58s question) + Scene2(4.82s countdown) + Scene3(9.05s reveal) = 21.45s
"""
import os, sys, subprocess, json, math, wave
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

WIDTH, HEIGHT, FPS = 1080, 1920, 30
output_dir = "output/quiz_final"
frames_dir = os.path.join(output_dir, "frames")
audio_dir = os.path.join(output_dir, "audio")
os.makedirs(frames_dir, exist_ok=True)

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# Scene durations (measured from TTS)
DUR_S1 = 7.58
DUR_S2 = 4.82
DUR_S3 = 9.05
TOTAL = DUR_S1 + DUR_S2 + DUR_S3
TOTAL_FRAMES = int(TOTAL * FPS)

print(f"Total: {TOTAL:.2f}s = {TOTAL_FRAMES} frames")

# =====================================================================
# 1. HTML TEMPLATE (The approved CodeHelp ONE style)
# =====================================================================
def build_html(timer_seconds=7, timer_urgent=False, is_reveal=False):
    urgent_cls = "urgent" if timer_urgent else ""
    timer_color = "#ef4444" if timer_urgent else "#38bdf8"
    timer_glow = "rgba(239, 68, 68, 0.6)" if timer_urgent else "rgba(56, 189, 248, 0.4)"
    timer_border = "rgba(239, 68, 68, 0.7)" if timer_urgent else "rgba(56, 189, 248, 0.5)"

    # Build option cards HTML
    if is_reveal:
        cards_html = """
      <div class='card-wrapper'>
        <div class='card-glow' style='background:#334155;opacity:0.2;'></div>
        <div class='option-card' style='border:2px solid rgba(50,60,80,0.3);opacity:0.4;'>
          <div class='letter-pill letter-a'>A</div>
          <img class='flag-thumb' src='file:///D:/ML_AGENT/assets/flags_hires/id.png'>
          <div class='country-title' style='color:#64748b;'>INDONESIA</div>
        </div>
      </div>
      <div class='card-wrapper'>
        <div class='card-glow' style='background:#10b981;opacity:0.85;'></div>
        <div class='option-card' style='border:3px solid rgba(52,211,153,0.9);background:rgba(6,44,30,0.9);'>
          <div class='letter-pill' style='background:linear-gradient(135deg,#10b981,#059669);'>B</div>
          <img class='flag-thumb' src='file:///D:/ML_AGENT/assets/flags_hires/jp.png'>
          <div class='country-title' style='color:#34d399;font-size:46px;'>JAPAN ✓</div>
        </div>
      </div>
      <div class='card-wrapper'>
        <div class='card-glow' style='background:#334155;opacity:0.2;'></div>
        <div class='option-card' style='border:2px solid rgba(50,60,80,0.3);opacity:0.4;'>
          <div class='letter-pill letter-c'>C</div>
          <img class='flag-thumb' src='file:///D:/ML_AGENT/assets/flags/kr.png'>
          <div class='country-title' style='color:#64748b;'>SOUTH KOREA</div>
        </div>
      </div>
      <div class='card-wrapper'>
        <div class='card-glow' style='background:#334155;opacity:0.2;'></div>
        <div class='option-card' style='border:2px solid rgba(50,60,80,0.3);opacity:0.4;'>
          <div class='letter-pill letter-d'>D</div>
          <img class='flag-thumb' src='file:///D:/ML_AGENT/assets/flags/nz.png'>
          <div class='country-title' style='color:#64748b;'>NEW ZEALAND</div>
        </div>
      </div>"""
    else:
        cards_html = """
      <div class='card-wrapper'>
        <div class='card-glow glow-a'></div>
        <div class='option-card card-a'>
          <div class='letter-pill letter-a'>A</div>
          <img class='flag-thumb' src='file:///D:/ML_AGENT/assets/flags_hires/id.png'>
          <div class='country-title ct-a'>INDONESIA</div>
        </div>
      </div>
      <div class='card-wrapper'>
        <div class='card-glow glow-b'></div>
        <div class='option-card card-b'>
          <div class='letter-pill letter-b'>B</div>
          <img class='flag-thumb' src='file:///D:/ML_AGENT/assets/flags_hires/jp.png'>
          <div class='country-title ct-b'>JAPAN</div>
        </div>
      </div>
      <div class='card-wrapper'>
        <div class='card-glow glow-c'></div>
        <div class='option-card card-c'>
          <div class='letter-pill letter-c'>C</div>
          <img class='flag-thumb' src='file:///D:/ML_AGENT/assets/flags/kr.png'>
          <div class='country-title ct-c'>SOUTH KOREA</div>
        </div>
      </div>
      <div class='card-wrapper'>
        <div class='card-glow glow-d'></div>
        <div class='option-card card-d'>
          <div class='letter-pill letter-d'>D</div>
          <img class='flag-thumb' src='file:///D:/ML_AGENT/assets/flags/nz.png'>
          <div class='country-title ct-d'>NEW ZEALAND</div>
        </div>
      </div>"""

    footer_html = """
    <div class='footer-bar footer-sub'>
      <div class='footer-text' style='color:#fecaca;'>🔔 SUBSCRIBE FOR DAILY TRIVIA QUIZZES!</div>
    </div>""" if is_reveal else """
    <div class='footer-bar'>
      <div class='footer-text'>💬 Comment your guess before time runs out</div>
    </div>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset='utf-8'>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700;800&family=DM+Sans:wght@500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    width: 1080px;
    height: 1920px;
    background: #08070d;
    font-family: 'DM Sans', sans-serif;
    color: white;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 85px 70px 70px 70px;
    overflow: hidden;
    position: relative;
  }}

  .light-beam {{
    position: absolute;
    top: 16%;
    left: 50%;
    transform: translate(-50%, -20%);
    width: 900px;
    height: 900px;
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

  /* Channel Branding */
  .channel-name {{
    position: absolute;
    top: 30px;
    right: 30px;
    font-family: 'Space Grotesk', sans-serif;
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
    padding: 10px 32px;
    border-radius: 999px;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 2px;
    margin-bottom: 40px;
  }}

  .question-box {{
    text-align: center;
    max-width: 940px;
    margin-bottom: 40px;
  }}

  .question-title {{
    font-family: 'Playfair Display', serif;
    font-size: 56px;
    font-weight: 700;
    line-height: 1.32;
    color: #ffffff;
    letter-spacing: -0.5px;
    text-shadow: 0 4px 25px rgba(0, 0, 0, 0.8);
  }}

  .question-clue {{
    margin-top: 20px;
    font-size: 26px;
    color: #94a3b8;
    font-weight: 600;
  }}

  /* COUNTDOWN CIRCLE with Glowing Shadow */
  .timer-circle-wrapper {{
    position: relative;
    width: 110px;
    height: 110px;
    margin-bottom: 60px;
  }}

  .timer-circle-glow {{
    position: absolute;
    inset: -18px;
    border-radius: 50%;
    filter: blur(28px);
    opacity: 0.7;
    background: {timer_glow};
  }}

  .timer-circle {{
    position: relative;
    z-index: 2;
    width: 110px;
    height: 110px;
    border-radius: 50%;
    background: rgba(13, 16, 27, 0.9);
    backdrop-filter: blur(20px);
    border: 3px solid {timer_border};
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.7);
  }}

  .timer-num {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 48px;
    font-weight: 700;
    color: {timer_color};
  }}

  .options-container {{
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 36px;
  }}

  .card-wrapper {{
    position: relative;
    width: 100%;
    height: 136px;
  }}

  .card-glow {{
    position: absolute;
    inset: -10px;
    border-radius: 38px;
    filter: blur(35px);
    opacity: 0.65;
    z-index: 1;
  }}

  .glow-a {{ background: #00d2ff; }}
  .glow-b {{ background: #6366f1; }}
  .glow-c {{ background: #10b981; }}
  .glow-d {{ background: #f59e0b; }}

  .option-card {{
    position: relative;
    z-index: 2;
    width: 100%;
    height: 100%;
    border-radius: 28px;
    display: flex;
    align-items: center;
    padding: 0 32px;
    background: rgba(13, 16, 27, 0.88);
    backdrop-filter: blur(24px);
    box-shadow: 0 15px 35px rgba(0,0,0,0.8);
  }}

  .card-a {{ border: 2px solid rgba(56, 189, 248, 0.65); }}
  .card-b {{ border: 2px solid rgba(129, 140, 248, 0.7); }}
  .card-c {{ border: 2px solid rgba(52, 211, 153, 0.65); }}
  .card-d {{ border: 2px solid rgba(251, 191, 36, 0.7); }}

  .letter-pill {{
    width: 68px;
    height: 68px;
    border-radius: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 32px;
    font-weight: 700;
    margin-right: 28px;
    color: white;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
  }}

  .letter-a {{ background: linear-gradient(135deg, #0ea5e9, #0284c7); }}
  .letter-b {{ background: linear-gradient(135deg, #6366f1, #4f46e5); }}
  .letter-c {{ background: linear-gradient(135deg, #10b981, #059669); }}
  .letter-d {{ background: linear-gradient(135deg, #f59e0b, #d97706); }}

  .flag-thumb {{
    width: 92px;
    height: 62px;
    border-radius: 12px;
    object-fit: cover;
    margin-right: 28px;
    border: 1.5px solid rgba(255, 255, 255, 0.2);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.6);
  }}

  /* Each option: distinct text color + Space Grotesk font */
  .country-title {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 42px;
    font-weight: 700;
    letter-spacing: 1px;
  }}
  .ct-a {{ color: #7dd3fc; }}
  .ct-b {{ color: #c4b5fd; }}
  .ct-c {{ color: #6ee7b7; }}
  .ct-d {{ color: #fcd34d; }}

  .footer-bar {{
    margin-top: auto;
    width: 100%;
    padding: 24px 32px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.12);
    backdrop-filter: blur(20px);
    text-align: center;
  }}

  .footer-sub {{
    background: rgba(220, 38, 38, 0.65);
    border-color: rgba(254, 202, 202, 0.4);
    box-shadow: 0 0 40px rgba(220, 38, 38, 0.4);
  }}

  .footer-text {{
    font-size: 26px;
    font-weight: 700;
    color: #94a3b8;
    letter-spacing: 0.5px;
  }}
</style>
</head>
<body>
  <div class='light-beam'></div>
  <div class='channel-name'>LR ATLAS</div>

  <div class='content'>
    <div class='category-pill'>GEOGRAPHY QUIZ</div>

    <div class='question-box'>
      <div class='question-title'>Which country has over 6,800 islands and the world&rsquo;s fastest bullet trains?</div>
      <div class='question-clue'>Home to Mount Fuji and famous for cherry blossoms</div>
    </div>

    <div class='timer-circle-wrapper'>
      <div class='timer-circle-glow'></div>
      <div class='timer-circle'>
        <span class='timer-num'>{timer_seconds}</span>
      </div>
    </div>

    <div class='options-container'>
      {cards_html}
    </div>

    {footer_html}
  </div>
</body>
</html>"""


# =====================================================================
# 2. RENDER KEY FRAMES VIA CHROME HEADLESS
# =====================================================================
def screenshot(html_str, out_png):
    html_path = os.path.join(output_dir, "_temp_frame.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_str)
    abs_html = os.path.abspath(html_path)
    abs_out = os.path.abspath(out_png)
    cmd = [
        CHROME, "--headless=new",
        f"--screenshot={abs_out}",
        "--window-size=1080,1920",
        "--hide-scrollbars",
        "--allow-file-access-from-files",
        "file:///" + abs_html.replace("\\", "/")
    ]
    subprocess.run(cmd, capture_output=True, check=True)

print("\n📸 Rendering key frames via Chrome...")

# Scene 1 frame (question + options visible, timer at 5)
frame_question = os.path.join(frames_dir, "question.png")
screenshot(build_html(timer_seconds=5, timer_urgent=False), frame_question)
print("  ✓ Question frame")

# Countdown frames: 5, 4, 3 (normal), then 2, 1 (urgent red)
for sec in [5, 4, 3, 2, 1]:
    urgent = sec <= 2
    fp = os.path.join(frames_dir, f"countdown_{sec}.png")
    screenshot(build_html(timer_seconds=sec, timer_urgent=urgent), fp)
    print(f"  ✓ Countdown {sec}s {'(URGENT!)' if urgent else ''}")

# Reveal frame
frame_reveal = os.path.join(frames_dir, "reveal.png")
screenshot(build_html(timer_seconds=0, timer_urgent=True, is_reveal=True), frame_reveal)
print("  ✓ Reveal frame")

# =====================================================================
# 3. BUILD VIDEO FROM KEYFRAMES
# =====================================================================
print("\n🎬 Assembling video from keyframes...")

# Timeline:
# Scene 1: 0.0s → 7.58s = question frame (held)
# Scene 2: 7.58s → 12.40s = countdown frames cycling each ~1s
#   7.58 → 8.54  = 5s frame
#   8.54 → 9.50  = 4s frame
#   9.50 → 10.46 = 3s frame (still calm)
#   10.46 → 11.43 = 2s frame (URGENT)
#   11.43 → 12.40 = 1s frame (URGENT)
# Scene 3: 12.40s → 21.45s = reveal frame (held)

sec_dur = DUR_S2 / 5.0  # each countdown second

concat_file = os.path.join(output_dir, "concat.txt")
segments = [
    (frame_question, DUR_S1),
    (os.path.join(frames_dir, "countdown_5.png"), sec_dur),
    (os.path.join(frames_dir, "countdown_4.png"), sec_dur),
    (os.path.join(frames_dir, "countdown_3.png"), sec_dur),
    (os.path.join(frames_dir, "countdown_2.png"), sec_dur),
    (os.path.join(frames_dir, "countdown_1.png"), sec_dur),
    (frame_reveal, DUR_S3),
]

# Build video segments and concat
seg_files = []
for i, (img_path, dur) in enumerate(segments):
    seg_mp4 = os.path.join(output_dir, f"seg_{i}.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", img_path,
        "-c:v", "libx264",
        "-t", f"{dur:.3f}",
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={WIDTH}:{HEIGHT}",
        "-r", str(FPS),
        "-preset", "veryfast",
        "-crf", "18",
        seg_mp4
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    seg_files.append(seg_mp4)
    print(f"  ✓ Segment {i}: {os.path.basename(img_path)} ({dur:.2f}s)")

with open(concat_file, "w") as f:
    for seg in seg_files:
        f.write(f"file '{os.path.abspath(seg).replace(os.sep, '/')}'\n")

raw_video = os.path.join(output_dir, "raw_video.mp4")
subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", concat_file,
    "-c:v", "libx264", "-pix_fmt", "yuv420p",
    "-preset", "veryfast", "-crf", "18",
    raw_video
], capture_output=True, check=True)
print(f"  ✓ Raw video assembled: {raw_video}")

# =====================================================================
# 4. MASTER AUDIO (Narration + Clock Ticks + SFX + Music)
# =====================================================================
print("\n🎵 Mastering audio...")

# Generate clock tick
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

wav_s1 = os.path.join(audio_dir, "scene_1.wav")
wav_s2 = os.path.join(audio_dir, "scene_2.wav")
wav_s3 = os.path.join(audio_dir, "scene_3.wav")

sfx_impact = "assets/sfx/shorts_impact.wav"
sfx_cash = "assets/sfx/shorts_cash_bell.wav"
sfx_whoosh = "assets/sfx/shorts_whoosh.wav"
bg_music = "assets/audio/music/tension_riser.wav"

mastered_audio = os.path.join(output_dir, "mastered_audio.wav")

filter_parts = [
    f"[0:a]adelay=0|0,apad=whole_dur={TOTAL}[nar1]",
    f"[1:a]adelay={int(DUR_S1*1000)}|{int(DUR_S1*1000)},apad=whole_dur={TOTAL}[nar2]",
    f"[2:a]adelay={int((DUR_S1+DUR_S2)*1000)}|{int((DUR_S1+DUR_S2)*1000)},apad=whole_dur={TOTAL}[nar3]",
    f"[3:a]volume=0.6,adelay=200|200,apad=whole_dur={TOTAL}[sfx_w]",
    f"[4:a]volume=0.8,adelay={int((DUR_S1+DUR_S2)*1000)}|{int((DUR_S1+DUR_S2)*1000)},apad=whole_dur={TOTAL}[sfx_imp]",
    f"[5:a]volume=0.9,adelay={int((DUR_S1+DUR_S2+0.4)*1000)}|{int((DUR_S1+DUR_S2+0.4)*1000)},apad=whole_dur={TOTAL}[sfx_c]",
]

# 5 clock ticks during Scene 2
for i in range(5):
    delay_ms = int((DUR_S1 + i * sec_dur + 0.3) * 1000)
    vol = 0.9 + i * 0.08
    filter_parts.append(f"[6:a]volume={vol:.2f},adelay={delay_ms}|{delay_ms},apad=whole_dur={TOTAL}[tk{i}]")

filter_parts.append(f"[7:a]volume=0.12,atrim=0:{TOTAL},afade=t=out:st={TOTAL-1.5}:d=1.5[bgm]")

tick_labels = "".join(f"[tk{i}]" for i in range(5))
filter_parts.append(
    f"[nar1][nar2][nar3][sfx_w][sfx_imp][sfx_c]{tick_labels}[bgm]"
    f"amix=inputs=12:duration=longest:dropout_transition=2,"
    f"atrim=0:{TOTAL},loudnorm=I=-14:LRA=7:tp=-1.5[outa]"
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
print(f"  ✓ Mastered audio: {mastered_audio}")

# =====================================================================
# 5. MUX VIDEO + AUDIO → FINAL MP4
# =====================================================================
final_mp4 = os.path.join(output_dir, "quiz_geography_japan_final.mp4")
subprocess.run([
    "ffmpeg", "-y",
    "-i", raw_video, "-i", mastered_audio,
    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
    final_mp4
], capture_output=True, check=True)

dur_check = subprocess.check_output([
    "ffprobe", "-v", "error", "-show_entries", "format=duration",
    "-of", "default=noprint_wrappers=1:nokey=1", final_mp4
]).decode().strip()
print(f"\n✅ Final video ready: {final_mp4} ({dur_check}s)")

# =====================================================================
# 6. UPLOAD TO YOUTUBE
# =====================================================================
print("\n🚀 Uploading to YouTube...")

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

body = {
    "snippet": {
        "title": "Can You Guess This Country in 5 Seconds? 🌍🧠 #Shorts #Quiz #Geography",
        "description": (
            "Can you guess this country from just 3 clues? 🏝️🚄🌸\n\n"
            "Drop your answer in the comments BEFORE watching the reveal!\n\n"
            "Subscribe for daily geography trivia quizzes! 🔔\n\n"
            "#Shorts #GeographyQuiz #GuessThat #Trivia #WorldQuiz #BrainTeaser "
            "#IQTest #Japan #DailyQuiz #LRAtlas"
        ),
        "tags": [
            "shorts", "quiz", "geography", "guess the country",
            "trivia", "world quiz", "brain teaser", "IQ test",
            "japan", "daily quiz", "LR Atlas", "geography challenge"
        ],
        "categoryId": "27",  # Education
    },
    "status": {
        "privacyStatus": "public",
        "selfDeclaredMadeForKids": False,
        "madeForKids": False,
    },
}

media = MediaFileUpload(final_mp4, mimetype="video/mp4", resumable=True)
request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

response = None
while response is None:
    status, response = request.next_chunk()
    if status:
        print(f"  Uploading... {int(status.progress() * 100)}%")

video_id = response["id"]
print(f"\n🎉 UPLOADED SUCCESSFULLY!")
print(f"📺 Video ID: {video_id}")
print(f"🔗 URL: https://youtube.com/shorts/{video_id}")
print(f"🎬 Title: {body['snippet']['title']}")
