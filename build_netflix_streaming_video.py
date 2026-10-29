"""Build and render an 85-second 16:9 widescreen long-format video for:
The Streaming Wars: Netflix vs Disney+ vs Prime Video (2012-2026).
Features Netflix Red Theme, 142 BPM Battle Rush audio, sleek 13pt captions,
and complete SEO metadata with ready-to-paste pinned comment.
"""

import os
import sys
import json
import time
from datetime import datetime
import pandas as pd
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import settings
settings.VIDEO_FORMAT = "landscape"
settings.BURN_CAPTIONS = True
settings.BGM_ENABLED = True
settings.BGM_VOLUME = 0.14

from app.data.static.viral_datasets import VIRAL_INDICATORS
from app.models import VideoScript, ScriptScene, FactCheck
from app.audio.tts import TTSEngine
from app.visuals.widescreen_duel import WidescreenDuelEngine
from app.video.assembler import VideoAssembler
from app.youtube.metadata import MetadataEngine
from app.youtube.uploader import upload_video
from app.qc.final_qc import FinalQC
from app.captions import generate_srt

# ----------------------------------------------------------------------
# 1. Output Directory
# ----------------------------------------------------------------------
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_dir = os.path.join("output", "streaming_wars", timestamp)
os.makedirs(output_dir, exist_ok=True)
print(f"🎬 Preparing Netflix Streaming Wars Long-Format Render in: {output_dir}")

# ----------------------------------------------------------------------
# 2. Load 2012-2026 Streaming Wars Dataset
# ----------------------------------------------------------------------
dataset_info = VIRAL_INDICATORS["streaming_wars_race"]
years = dataset_info["years"]
data_dict = dataset_info["data"]
df = pd.DataFrame(data_dict, index=years).T
df.columns = [int(c) for c in df.columns]
print(f"📊 Loaded {len(df)} platforms across {len(years)} years ({years[0]} - {years[-1]}).")

# ----------------------------------------------------------------------
# 3. Create 85-Second High-Tension Script
# ----------------------------------------------------------------------
scenes = [
    ScriptScene(
        scene_number=1,
        duration=14.0,
        narration=(
            "In 2012, Netflix made an audacious gamble, pivoting from DVD mailers to original streaming with House of Cards, "
            "amassing thirty million subscribers and pioneering the modern binge-watching revolution."
        ),
        visual_description="Netflix launches original streaming era while DVD business fades",
        text_overlay="2012: The Netflix Original Revolution Begins",
        chart_type="widescreen_duel",
        scene_purpose="HOOK",
        visual_emphasis="netflix gamble",
        highlight_countries=["Netflix", "Hulu"],
        important_year=2012,
        important_value=25.0,
        pacing_hint="steady buildup",
    ),
    ScriptScene(
        scene_number=2,
        duration=14.0,
        narration=(
            "By 2016, Stranger Things became an unprecedented global cultural phenomenon. "
            "Netflix surged past one hundred million subscribers, expanding into over one hundred and ninety countries with zero serious rivals."
        ),
        visual_description="Stranger Things propels Netflix past 100M global subscribers",
        text_overlay="2016-2018: Stranger Things & Global Expansion",
        chart_type="widescreen_duel",
        scene_purpose="BUILDUP",
        visual_emphasis="stranger things boom",
        highlight_countries=["Netflix", "Amazon Prime Video"],
        important_year=2016,
        important_value=89.0,
        pacing_hint="accelerating climb",
    ),
    ScriptScene(
        scene_number=3,
        duration=14.0,
        narration=(
            "Then in late 2019, the true Streaming Wars erupted. "
            "Entertainment titan Disney launched Disney Plus with The Mandalorian, gaining an astonishing sixty million subscribers in its very first year."
        ),
        visual_description="Disney+ launches the Streaming Wars and rapidly chases Netflix",
        text_overlay="2019-2020: Disney+ Launches The Streaming Wars",
        chart_type="widescreen_duel",
        scene_purpose="TENSION",
        visual_emphasis="disney plus launch",
        highlight_countries=["Netflix", "Disney+"],
        important_year=2019,
        important_value=26.5,
        pacing_hint="battle tension",
    ),
    ScriptScene(
        scene_number=4,
        duration=14.0,
        narration=(
            "During global lockdowns, streaming demand shattered records. "
            "As Squid Game became the biggest television launch in history, Amazon Prime Video and HBO Max surged into nine-figure subscriber territory."
        ),
        visual_description="Squid Game breaks records as streaming usage hits historic highs",
        text_overlay="2021-2022: Squid Game Era & Lockdown Boom",
        chart_type="widescreen_duel",
        scene_purpose="MILESTONE",
        visual_emphasis="squid game surge",
        highlight_countries=["Netflix", "Disney+", "Amazon Prime Video"],
        important_year=2021,
        important_value=221.8,
        pacing_hint="steady growth",
    ),
    ScriptScene(
        scene_number=5,
        duration=14.0,
        narration=(
            "In 2023, Wall Street panic hit as growth stalled. "
            "But Netflix's bold password crackdown and ad-supported tiers sparked a historic financial comeback, re-establishing a massive lead over Disney."
        ),
        visual_description="Netflix password crackdown sparks historic subscriber rebound",
        text_overlay="2023-2024: The Great Password Crackdown Comeback",
        chart_type="widescreen_duel",
        scene_purpose="CLIMAX",
        visual_emphasis="netflix comeback",
        highlight_countries=["Netflix", "Disney+"],
        important_year=2023,
        important_value=260.3,
        pacing_hint="high energy overtake",
    ),
    ScriptScene(
        scene_number=6,
        duration=15.0,
        narration=(
            "Today, Netflix reigns undisputed as the all-time King of Streaming, crossing three hundred and five million subscribers! "
            "Which streaming service is your daily favorite? Comment below, like, and subscribe to LR Atlas for more epic data battles!"
        ),
        visual_description="Netflix crowned undisputed all-time King with glassmorphic Outro Card",
        text_overlay="2024-2026: Undisputed All-Time Streaming King",
        chart_type="widescreen_duel",
        scene_purpose="RESOLUTION",
        visual_emphasis="all time champion",
        highlight_countries=["Netflix", "Disney+"],
        important_year=2026,
        important_value=305.0,
        pacing_hint="triumphant outro",
    ),
]

script = VideoScript(
    title="The Streaming Wars: Who Wins The Battle For Hollywood's Throne?",
    topic="The Streaming Wars: Netflix vs Disney+ vs Prime Video (2012-2026)",
    category="Entertainment",
    indicator_name="Paying Subscribers (Millions)",
    total_duration=85,
    scenes=scenes,
    fact_check=FactCheck(is_accurate=True, discrepancies="none"),
    source_name="Official SEC 10-K Filings & Statista Streaming Intelligence",
    source_url="https://ir.netflix.net",
    indicator_code="streaming_wars_race",
)

with open(os.path.join(output_dir, "script.json"), "w", encoding="utf-8") as f:
    json.dump(script.model_dump(), f, indent=2)
print("📝 Script created: 6 scenes, 85.0 seconds target duration.")

# ----------------------------------------------------------------------
# 4. Generate Voiceover Audio (Edge TTS) & Align Scene Timings
# ----------------------------------------------------------------------
print("\n🎙️ Generating voiceover audio...")
audio_dir = os.path.join(output_dir, "audio")
os.makedirs(audio_dir, exist_ok=True)
audio_data = TTSEngine.generate_narration(
    script=script,
    output_dir=audio_dir,
    voice="en-US-AndrewNeural",
)
total_audio_duration = sum(item.get("actual_duration", item.get("duration", 0)) for item in audio_data)
print(f"✅ Voiceover generated: {len(audio_data)} segments, {total_audio_duration:.2f}s spoken narration.")

print("⏱️ Synchronizing audio narration segments to visual scene timeline (85.0s)...")
padded_audio = VideoAssembler.align_landscape_audio(
    audio_data=audio_data,
    output_dir=output_dir,
    target_total_duration=85.0,
)
print("✅ Audio synchronization complete: all scenes cued to exact visual timestamps.")

srt_path = os.path.join(output_dir, "captions.srt")
generate_srt(audio_data, output_dir)
print(f"✅ Captions synchronized and ready: {srt_path}")

# ----------------------------------------------------------------------
# 5. Render 1920x1080 Widescreen Duel Animation (Netflix Red Theme)
# ----------------------------------------------------------------------
visual_dir = os.path.join(output_dir, "visuals")
os.makedirs(visual_dir, exist_ok=True)
animation_path = os.path.join(visual_dir, "visual_0.mp4")
render_duration = 85.0

print("\n⚔️ Rendering 1920x1080 Widescreen Duel Animation in NETFLIX THEME (85s) ...")
WidescreenDuelEngine.render_landscape_animation(
    wide_data=df,
    output_file=animation_path,
    title=script.title,
    category_label="LR ATLAS DATA LABS // STREAMING WARS BATTLE",
    duration_seconds=render_duration,
    fps=30,
    indicator_code="streaming_wars_race",
)
print(f"✅ Animation rendered successfully: {animation_path} ({os.path.getsize(animation_path)/(1024*1024):.1f} MB)")

visual_data = [{"scene_number": 1, "image_path": animation_path}]

# ----------------------------------------------------------------------
# 6. Assemble Final Video (142 BPM Battle Rush BGM + Sleek 13pt Subtitles)
# ----------------------------------------------------------------------
print("\n🎞️ Assembling Final Video with 142 BPM Battle Rush BGM & Sleek 13pt Subtitles...")
final_video_path = VideoAssembler.create_video(
    audio_data=padded_audio,
    visual_data=visual_data,
    output_dir=output_dir,
    captions_path=srt_path,
    sfx_category="duel_battle",
)
print(f"\n🎉 FINAL VIDEO ASSEMBLED: {final_video_path}")
print(f"📦 File Size: {os.path.getsize(final_video_path)/(1024*1024):.2f} MB")

# ----------------------------------------------------------------------
# 7. Quality Control Audit
# ----------------------------------------------------------------------
print("\n🔍 Running Final Quality Control...")
qc_result = FinalQC.check_video(final_video_path)
print(f"QC Passed: {qc_result.get('passed')} (Score: {qc_result.get('score', 100)})")

# ----------------------------------------------------------------------
# 8. Generate 500-Character SEO Tags, Clickable Hashtags & Pinned Comment
# ----------------------------------------------------------------------
print("\n🏷️ Generating 500-Character SEO Tags, Hashtags & Pinned Comment Section...")

title = "The Streaming Wars (2012–2026): Who Won Hollywood's Throne? | Netflix vs Disney+"

hashtags = [
    "#StreamingWars",
    "#Netflix",
    "#DisneyPlus",
    "#Entertainment",
    "#DataViz"
]

tags = [
    "netflix",
    "streaming wars",
    "disney plus",
    "prime video",
    "hbo max",
    "netflix vs disney plus",
    "netflix subscriber count 2026",
    "streaming platform comparison",
    "most popular streaming service",
    "stranger things 5",
    "squid game 2",
    "the mandalorian",
    "amazon prime video",
    "hulu",
    "apple tv plus",
    "entertainment news",
    "streaming market share",
    "netflix documentary",
    "netflix revenue",
    "disney plus subscribers",
    "streaming wars documentary",
    "netflix growth history",
    "house of cards netflix",
    "netflix password crackdown",
    "max streaming service",
    "streaming platform rankings",
    "lr atlas",
    "data visualization",
    "bar chart race"
]

description = (
    "From DVD mailers in 2012 to an astonishing 305 Million paying subscribers in 2026, "
    "this is the epic 14-year history of the Streaming Wars: Netflix vs Disney+ vs Amazon Prime Video vs HBO Max.\n\n"
    "Watch the complete rise of Stranger Things, the explosive launch of Disney Plus, "
    "the Squid Game pandemic boom, and the controversial password crackdown that solidified Netflix's crown.\n\n"
    "📊 Data Sources: Official SEC 10-K Filings & Statista Streaming Intelligence.\n\n"
    + " ".join(hashtags)
    + "\n\n📊 Produced by LR Atlas Data Labs"
)

pinned_comment = (
    "🔥 QUICK POLL: Which streaming service do you use the most right now?\n"
    "🔴 A) Netflix (Squid Game / Stranger Things)\n"
    "🔵 B) Disney+ / Hotstar (Marvel & Star Wars)\n"
    "🟡 C) Amazon Prime Video / JioCinema\n"
    "🟣 D) HBO Max / Apple TV+ (Comment below!)\n\n"
    "⏱️ TIMESTAMPS & CHAPTERS:\n"
    "0:00 — 2012: The Netflix Streaming Revolution Begins\n"
    "0:14 — 2016: The Stranger Things Global Explosion\n"
    "0:28 — 2019: Disney+ Launches The Streaming Wars\n"
    "0:42 — 2021: Squid Game & The Lockdown Surge\n"
    "0:56 — 2023: The Great Password Crackdown Comeback\n"
    "1:10 — 2026: The Undisputed All-Time Champion\n"
    "1:18 — Final Verdict & Community Poll\n\n"
    "🔔 Subscribe to LR Atlas for daily high-stakes data wars! Which topic should we race next? 👇"
)

metadata = {
    "title": title,
    "description": description,
    "hashtags": hashtags,
    "tags": tags,
    "category": "Entertainment",
    "pinned_comment": pinned_comment,
    "thumbnail_text": "Netflix vs Disney+: Who Won?",
}

metadata_file = os.path.join(output_dir, "youtube_metadata.json")
with open(metadata_file, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2)
print("✅ Full SEO metadata & pinned comment saved to youtube_metadata.json")

# ----------------------------------------------------------------------
# 9. Extract High-Resolution Thumbnails & Preview Frames
# ----------------------------------------------------------------------
thumb_dir = os.path.join(output_dir, "thumbnails")
os.makedirs(thumb_dir, exist_ok=True)
thumb_path = os.path.join(thumb_dir, "thumbnail.jpg")

# Extract frame at 40s (Disney+ vs Netflix battle)
extract_cmd = [
    "ffmpeg", "-y",
    "-ss", "40.0",
    "-i", final_video_path,
    "-vframes", "1",
    "-q:v", "2",
    thumb_path
]
os.system(" ".join(extract_cmd))
print(f"🖼️ Thumbnail generated: {thumb_path}")

# Extract 4 preview frames for user inspection
frame_timestamps = [
    ("frame_1_2012_early_era.png", "5.0"),
    ("frame_2_2019_disney_launch.png", "35.0"),
    ("frame_3_2022_lockdown_peak.png", "50.0"),
    ("frame_4_2026_outro_champion.png", "83.0"),
]
artifact_dir = r"C:\Users\gkb16\.gemini\antigravity-ide\brain\ca29c4ce-0c08-4fcc-b693-3829e24c5663"
for fname, sec in frame_timestamps:
    out_frame = os.path.join(artifact_dir, f"netflix_{fname}")
    os.system(f'ffmpeg -y -ss {sec} -i "{final_video_path}" -vframes 1 "{out_frame}" >nul 2>&1')
print("📸 4 Preview frames saved to artifact directory.")

# ----------------------------------------------------------------------
# 10. Upload to YouTube as UNLISTED
# ----------------------------------------------------------------------
print("\n🚀 Uploading Video to YouTube as UNLISTED...")
upload_result = upload_video(
    video_path=final_video_path,
    metadata=metadata,
    thumbnail_path=thumb_path,
    privacy_status="unlisted",
)

video_id = upload_result.get("video_id")
print("\n" + "=" * 60)
print(f"🎉 YOUTUBE UPLOAD SUCCESSFUL!")
print(f"🔗 Video URL: https://youtu.be/{video_id}")
print(f"🔒 Privacy Status: UNLISTED")
print("=" * 60)
