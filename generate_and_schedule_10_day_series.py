"""
Master Generation & Scheduling Engine for LR Atlas 10-Day Series.
Renders all 20 multi-category high-curiosity quiz shorts (2 per day for 10 days)
and schedules them via the YouTube Data API v3.

Schedule:
- Everyday @ 1:00 PM IST (07:30 UTC)
- Everyday @ 7:30 PM IST (14:00 UTC)
- From Tuesday Nov 24, 2026 to Thursday Dec 03, 2026.
"""

import os
import sys
import json
import math
import wave
import subprocess
import asyncio
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import edge_tts
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from quiz_database import get_10_day_series

WIDTH = 1080
HEIGHT = 1920
FPS = 30
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUTPUT_BASE = os.path.abspath(r"output\10_day_series")
MANIFEST_PATH = os.path.join(OUTPUT_BASE, "manifest.json")
os.makedirs(OUTPUT_BASE, exist_ok=True)

def load_manifest():
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_manifest(manifest):
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

def get_flag_path(code):
    p1 = os.path.abspath(f"assets/flags_hires/{code}.png")
    p2 = os.path.abspath(f"assets/flags/{code}.png")
    path = p1 if os.path.exists(p1) else p2
    return "file:///" + path.replace("\\", "/")

def build_html_frame(quiz, timer_sec=6, timer_urgent=False, is_reveal=False):
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
    width: 1080px; height: 1920px; background: #08070d; font-family: 'Space Grotesk', sans-serif;
    color: white; display: flex; flex-direction: column; align-items: center;
    padding: 85px 70px 75px 70px; overflow: hidden; position: relative;
  }}
  .light-beam {{
    position: absolute; top: 15%; left: 50%; transform: translate(-50%, -20%);
    width: 950px; height: 950px;
    background: radial-gradient(circle, rgba(139, 92, 246, 0.28) 0%, rgba(99, 102, 241, 0.12) 40%, rgba(8, 7, 13, 0) 70%);
    pointer-events: none; z-index: 1;
  }}
  .content {{
    position: relative; z-index: 2; width: 100%; display: flex; flex-direction: column;
    align-items: center; height: 100%;
  }}
  .channel-name {{
    position: absolute; top: 25px; right: 25px; font-size: 22px; font-weight: 700;
    color: rgba(148, 163, 184, 0.7); letter-spacing: 1.5px; z-index: 10;
  }}
  .category-pill {{
    background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.12);
    backdrop-filter: blur(16px); color: #94a3b8; padding: 10px 34px; border-radius: 999px;
    font-size: 22px; font-weight: 700; letter-spacing: 2px; margin-bottom: 35px;
  }}
  .question-box {{ text-align: center; max-width: 960px; margin-bottom: 35px; }}
  .question-title {{
    font-family: 'Playfair Display', serif; font-size: 56px; font-weight: 700;
    line-height: 1.32; color: #ffffff; letter-spacing: -0.5px;
    text-shadow: 0 4px 25px rgba(0, 0, 0, 0.85);
  }}
  .question-clue {{ margin-top: 18px; font-size: 26px; color: #94a3b8; font-weight: 600; }}
  .timer-circle-wrapper {{
    position: relative; width: 165px; height: 165px; margin-bottom: 95px;
  }}
  .timer-circle-glow {{
    position: absolute; inset: -26px; border-radius: 50%; filter: blur(34px);
    opacity: 0.75; background: {timer_glow};
  }}
  .timer-circle {{
    position: relative; z-index: 2; width: 165px; height: 165px; border-radius: 50%;
    background: rgba(13, 16, 27, 0.92); backdrop-filter: blur(20px);
    border: 4px solid {timer_border}; display: flex; align-items: center; justify-content: center;
    box-shadow: 0 14px 40px rgba(0, 0, 0, 0.8);
  }}
  .timer-num {{ font-size: 72px; font-weight: 700; color: {timer_col}; letter-spacing: -1px; }}
  .options-container {{
    width: 100%; display: flex; flex-direction: column; gap: 40px; margin-top: 10px;
  }}
  .card-wrapper {{ position: relative; width: 100%; height: 142px; }}
  .card-glow {{
    position: absolute; inset: -10px; border-radius: 38px; filter: blur(36px);
    opacity: 0.65; z-index: 1;
  }}
  .option-card {{
    position: relative; z-index: 2; width: 100%; height: 100%; border-radius: 28px;
    display: flex; align-items: center; padding: 0 34px; background: rgba(13, 16, 27, 0.88);
    backdrop-filter: blur(24px); box-shadow: 0 16px 36px rgba(0,0,0,0.85);
  }}
  .letter-pill {{
    width: 72px; height: 72px; border-radius: 20px; display: flex; align-items: center;
    justify-content: center; font-size: 34px; font-weight: 700; margin-right: 28px;
    color: white; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
  }}
  .flag-thumb {{
    width: 96px; height: 64px; border-radius: 12px; object-fit: cover; margin-right: 28px;
    border: 1.5px solid rgba(255, 255, 255, 0.22); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.6);
  }}
  .country-title {{ font-size: 42px; font-weight: 700; letter-spacing: 1px; }}
  .footer-bar {{
    margin-top: 55px; width: 100%; padding: 26px 36px; border-radius: 999px;
    background: rgba(245, 158, 11, 0.08); border: 1.5px solid rgba(245, 158, 11, 0.35);
    backdrop-filter: blur(20px); text-align: center;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5), 0 0 30px rgba(245, 158, 11, 0.15);
  }}
  .footer-reveal {{
    background: rgba(251, 191, 36, 0.15); border: 2px solid rgba(251, 191, 36, 0.7);
    box-shadow: 0 0 50px rgba(245, 158, 11, 0.35);
  }}
  .footer-text {{ font-size: 26px; font-weight: 700; color: #fbbf24; letter-spacing: 0.5px; }}
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

def render_quiz_video(quiz):
    q_dir = os.path.join(OUTPUT_BASE, quiz["id"])
    f_dir = os.path.join(q_dir, "frames")
    a_dir = os.path.join(q_dir, "audio")
    os.makedirs(f_dir, exist_ok=True)
    os.makedirs(a_dir, exist_ok=True)
    final_mp4 = os.path.join(q_dir, f"{quiz['id']}.mp4")

    if os.path.exists(final_mp4) and os.path.getsize(final_mp4) > 1000000:
        print(f"  ⚡ Already rendered: {final_mp4}")
        return final_mp4

    print(f"\n🎬 RENDERING: Day {quiz['day']} ({quiz['slot']}) - {quiz['id']}")
    print(f"🎙️ Voice: {quiz['voice']} | Topic: {quiz['category']}")

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
    render_frame_img(build_html_frame(quiz, timer_sec=6, timer_urgent=False), f_q, temp_html)

    for sec in [6, 5, 4, 3, 2, 1]:
        urg = sec <= 2
        render_frame_img(build_html_frame(quiz, timer_sec=sec, timer_urgent=urg), os.path.join(f_dir, f"countdown_{sec}.png"), temp_html)

    f_rev = os.path.join(f_dir, "reveal.png")
    render_frame_img(build_html_frame(quiz, timer_sec=0, timer_urgent=True, is_reveal=True), f_rev, temp_html)
    print("  ✓ Chrome frames rendered")

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

    # Clean intermediate segments
    for sf in seg_files:
        try: os.remove(sf)
        except: pass
    try: os.remove(raw_v)
    except: pass

    print(f"  ✓ Video complete: {final_mp4}")
    return final_mp4

def upload_and_schedule(quiz, mp4_path, youtube):
    print(f"\n🚀 UPLOADING & SCHEDULING: {quiz['youtube_title']}")
    print(f"⏰ Schedule Target: {quiz['schedule_label']} ({quiz['schedule_time']})")

    body = {
        "snippet": {
            "title": quiz["youtube_title"],
            "description": (
                f"{quiz['question']}\n\n"
                f"💡 Clue: {quiz['clue']}\n\n"
                "Drop your guess in the comments before time runs out! 👇\n\n"
                "Subscribe to LR Atlas for daily brain & trivia quizzes! 🔔\n\n"
                + " ".join(f"#{t.replace(' ', '')}" for t in quiz["tags"])
            ),
            "tags": quiz["tags"],
            "categoryId": "27",
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": quiz["schedule_time"],
            "selfDeclaredMadeForKids": False,
            "madeForKids": False,
        },
    }

    media = MediaFileUpload(mp4_path, mimetype="video/mp4", resumable=True)
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        st, resp = req.next_chunk()
        if st:
            print(f"  Uploading... {int(st.progress() * 100)}%")

    vid_id = resp["id"]
    vid_url = f"https://youtube.com/shorts/{vid_id}"
    print(f"  🎉 SUCCESS! Video Scheduled: {vid_url} for {quiz['schedule_label']}")
    return vid_id, vid_url

def main():
    series = get_10_day_series()
    manifest = load_manifest()

    print("="*70)
    print("🌍 LR ATLAS: 10-DAY 20-VIDEO MASTER PIPELINE")
    print(f"📊 Total Series Videos: {len(series)}")
    print("="*70)

    # Authenticate YouTube
    youtube = None
    try:
        creds = Credentials.from_authorized_user_file("youtube_token.json")
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open("youtube_token.json", "w") as f:
                f.write(creds.to_json())
        youtube = build("youtube", "v3", credentials=creds)
    except Exception as e:
        print(f"⚠️ Warning: Could not authenticate YouTube: {e}")

    quota_exceeded = False

    for idx, quiz in enumerate(series):
        qid = quiz["id"]
        entry = manifest.get(qid, {
            "id": qid,
            "day": quiz["day"],
            "slot": quiz["slot"],
            "title": quiz["youtube_title"],
            "schedule_label": quiz["schedule_label"],
            "schedule_time": quiz["schedule_time"],
            "video_path": None,
            "rendered": False,
            "uploaded": False,
            "video_id": None,
            "url": None
        })

        # Step 1: Render Video
        if not entry.get("rendered") or not (entry.get("video_path") and os.path.exists(entry["video_path"])):
            try:
                mp4 = render_quiz_video(quiz)
                entry["video_path"] = mp4
                entry["rendered"] = True
                manifest[qid] = entry
                save_manifest(manifest)
            except Exception as e:
                print(f"❌ Failed to render {qid}: {e}")
                continue
        else:
            print(f"[{idx+1}/{len(series)}] {qid} already rendered.")

        # Step 2: Upload Video
        if not entry.get("uploaded"):
            if quota_exceeded:
                print(f"  ⏸️ Skipping upload for {qid} (daily API quota reached). Will upload in next quota window.")
                continue

            if youtube is None:
                print(f"  ⏸️ Skipping upload for {qid} (YouTube client unavailable).")
                continue

            try:
                vid_id, vid_url = upload_and_schedule(quiz, entry["video_path"], youtube)
                entry["uploaded"] = True
                entry["video_id"] = vid_id
                entry["url"] = vid_url
                manifest[qid] = entry
                save_manifest(manifest)
            except HttpError as err:
                err_str = str(err)
                if "quotaExceeded" in err_str or "uploadLimitExceeded" in err_str:
                    print("\n" + "!"*70)
                    print("⚠️ YOUTUBE API DAILY UPLOAD QUOTA REACHED (10,000 units)")
                    print("All remaining videos are fully rendered and safely queued.")
                    print("!"*70)
                    quota_exceeded = True
                else:
                    print(f"❌ Upload error on {qid}: {err}")
            except Exception as e:
                print(f"❌ Upload exception on {qid}: {e}")

    print("\n" + "="*70)
    print("📈 LR ATLAS: 10-DAY PIPELINE SUMMARY")
    print("="*70)
    rendered_count = sum(1 for e in manifest.values() if e.get("rendered"))
    uploaded_count = sum(1 for e in manifest.values() if e.get("uploaded"))
    print(f"✨ Total Rendered: {rendered_count}/{len(series)}")
    print(f"🚀 Total Scheduled / Uploaded: {uploaded_count}/{len(series)}")
    for q in series:
        qid = q["id"]
        info = manifest.get(qid, {})
        status = "✅ SCHEDULED" if info.get("uploaded") else ("🎬 RENDERED (QUEUED)" if info.get("rendered") else "⏳ PENDING")
        url = info.get("url", "N/A")
        print(f"Day {q['day']} | {q['schedule_label']} | {status} | {url}")
    print("="*70)

if __name__ == "__main__":
    main()
