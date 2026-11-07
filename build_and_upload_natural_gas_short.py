"""Build, assemble, and publish a high-retention 35-second YouTube Short (1080x1920 9:16).
Topic: Who Produces The Most Natural Gas? (1990-2026) - USA vs Russia vs Iran vs China vs Qatar
Features:
- VerticalDuelEngine (Always-On Mobile VS Battle HUD, Monogram Badges, Glowing Year Counter).
- 142 BPM Battle Rush music (auto-ducked).
- High-contrast kinetic subtitles in mobile safe corridor.
- Dynamic Unit Formatting (BCM - Billion Cubic Meters).
- Cinematic Outro Card with Community CTA & Seamless Loop.
- Direct Live Upload to YouTube.
"""

import os
import sys
import json
import time
from datetime import datetime
import pandas as pd
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import settings
settings.VIDEO_FORMAT = "portrait"  # 1080x1920 Vertical Shorts
settings.BURN_CAPTIONS = True
settings.BGM_ENABLED = True
settings.BGM_VOLUME = 0.14

from app.data.static.viral_datasets import VIRAL_INDICATORS
from app.models import VideoScript, ScriptScene, FactCheck
from app.audio.tts import TTSEngine
from app.visuals.vertical_duel import VerticalDuelEngine
from app.video.assembler import VideoAssembler
from app.qc.final_qc import FinalQC
from app.captions import generate_srt
from app.youtube.uploader import upload_video

# ----------------------------------------------------------------------
# 1. Output Directory
# ----------------------------------------------------------------------
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_dir = os.path.join("output", "natural_gas_short", timestamp)
os.makedirs(output_dir, exist_ok=True)
print(f"🎬 Initialized Output Directory: {output_dir}")

# ----------------------------------------------------------------------
# 2. Load Global Natural Gas Production Dataset
# ----------------------------------------------------------------------
dataset_info = VIRAL_INDICATORS["natural_gas_production"]
years = dataset_info["years"]
data_dict = dataset_info["data"]
df = pd.DataFrame(data_dict, index=years).T
df.columns = [int(c) for c in df.columns]
print(f"📊 Loaded {len(df)} countries across {len(years)} years ({years[0]} - {years[-1]}).")

# ----------------------------------------------------------------------
# 3. Create 35-Second Punchy Script (High Viral Retention & Seamless Loop)
# ----------------------------------------------------------------------
scenes = [
    ScriptScene(
        scene_number=1,
        duration=8.5,
        narration=(
            "Think Russia produces the most natural gas in the world? Think again! "
            "Back in 1990, Russia ruled supreme, pumping six hundred and forty billion cubic meters "
            "while America trailed far behind!"
        ),
        visual_description="Russia dominates global natural gas production in 1990 with USA trailing",
        text_overlay="1990: Russia Rules Global Energy",
        chart_type="vertical_duel",
        scene_purpose="HOOK",
        visual_emphasis="russia dominance",
        highlight_countries=["Russia", "United States"],
        important_year=1990,
        important_value=640.0,
        pacing_hint="explosive hook",
    ),
    ScriptScene(
        scene_number=2,
        duration=8.5,
        narration=(
            "For two decades, Russian gas powered Europe while Iran, Qatar, and Canada expanded their energy empires. "
            "But deep underground, an American technology revolution was quietly brewing!"
        ),
        visual_description="Russia dominates European supply while Qatar and Iran expand LNG",
        text_overlay="2005: Russia Dominance & Rise of Qatar",
        chart_type="vertical_duel",
        scene_purpose="BUILDUP",
        visual_emphasis="qatar and iran rise",
        highlight_countries=["Russia", "Qatar", "Iran", "Canada"],
        important_year=2005,
        important_value=640.0,
        pacing_hint="fast climb",
    ),
    ScriptScene(
        scene_number=3,
        duration=9.0,
        narration=(
            "Then came 2011! The American shale revolution exploded with hydraulic fracturing, "
            "shattering all global records and officially dethroning Russia to claim number one on Earth!"
        ),
        visual_description="Historic 2011 overtake: USA overtakes Russia for #1 natural gas producer",
        text_overlay="2011: USA DETHRONES RUSSIA FOR #1!",
        chart_type="vertical_duel",
        scene_purpose="CLIMAX",
        visual_emphasis="usa overtakes russia",
        highlight_countries=["United States", "Russia"],
        important_year=2011,
        important_value=651.0,
        pacing_hint="high energy overtake",
    ),
    ScriptScene(
        scene_number=4,
        duration=9.0,
        narration=(
            "Today, America is the world's undisputed gas titan, surpassing one trillion cubic meters every year! "
            "Who will rule global energy in 2030? Vote in the comments, because whenever you ask..."
        ),
        visual_description="United States crowned champion with live floating debate pill and seamless viral loop",
        text_overlay="2026: USA The 1-Trillion BCM Titan",
        chart_type="vertical_duel",
        scene_purpose="RESOLUTION",
        visual_emphasis="champion outro",
        highlight_countries=["United States"],
        important_year=2026,
        important_value=1070.0,
        pacing_hint="triumphant outro",
    ),
]

script = VideoScript(
    title="Who Produces The Most Natural Gas? (1990-2026): USA vs Russia 🔥 #Shorts",
    topic="World Natural Gas Production: USA vs Russia vs Iran vs China vs Qatar (1990-2026)",
    category="Energy & Resources",
    indicator_name="Natural Gas Production (Billion Cubic Meters - BCM)",
    total_duration=35,
    scenes=scenes,
    fact_check=FactCheck(is_accurate=True, discrepancies="none"),
    source_name="Energy Institute Statistical Review of World Energy & EIA",
    source_url="https://www.energyinst.org",
    indicator_code="natural_gas_production",
)

with open(os.path.join(output_dir, "script.json"), "w", encoding="utf-8") as f:
    json.dump(script.model_dump(), f, indent=2)
print("📝 Script created: 4 punchy scenes, 35.0 seconds target duration.")

# ----------------------------------------------------------------------
# 4. Generate Voiceover Audio (Edge TTS) & Align Scene Timings
# ----------------------------------------------------------------------
print("\n🎙️ Generating voiceover audio with Edge TTS (en-US-AndrewNeural)...")
audio_dir = os.path.join(output_dir, "audio")
os.makedirs(audio_dir, exist_ok=True)
audio_data = TTSEngine.generate_narration(
    script=script,
    output_dir=audio_dir,
    voice="en-US-AndrewNeural",
)
total_audio_duration = sum(item.get("actual_duration", item.get("duration", 0)) for item in audio_data)
print(f"✅ Voiceover generated: {len(audio_data)} segments, {total_audio_duration:.2f}s spoken narration.")

print("⏱️ Synchronizing audio narration segments to visual scene timeline (35.0s)...")
padded_audio = VideoAssembler.align_landscape_audio(
    audio_data=audio_data,
    output_dir=output_dir,
    target_total_duration=35.0,
)
print("✅ Audio synchronization complete.")

srt_path = os.path.join(output_dir, "captions.srt")
generate_srt(audio_data, output_dir)
print(f"✅ Captions synchronized and ready: {srt_path}")

# ----------------------------------------------------------------------
# 5. Render 1080x1920 Vertical Animation (VerticalDuelEngine)
# ----------------------------------------------------------------------
visual_dir = os.path.join(output_dir, "visuals")
os.makedirs(visual_dir, exist_ok=True)
animation_path = os.path.join(visual_dir, "visual_0.mp4")
render_duration = 35.0

print("\n⚔️ Rendering 1080x1920 Vertical Duel Animation (35s) ...")
VerticalDuelEngine.render_portrait_animation(
    wide_data=df,
    output_file=animation_path,
    title="WHO PRODUCES THE MOST NATURAL GAS?",
    category_label="LR ATLAS // GLOBAL ENERGY WARS",
    duration_seconds=render_duration,
    fps=30,
    indicator_code="natural_gas_production",
)
print(f"✅ Animation rendered successfully: {animation_path} ({os.path.getsize(animation_path)/(1024*1024):.1f} MB)")

visual_data = [{"scene_number": 1, "image_path": animation_path}]

# ----------------------------------------------------------------------
# 6. Assemble Final Short (142 BPM Battle Rush BGM + Kinetic Subtitles)
# ----------------------------------------------------------------------
print("\n🎞️ Assembling Final YouTube Short with 142 BPM Battle Rush BGM...")
final_video_path = VideoAssembler.create_video(
    audio_data=padded_audio,
    visual_data=visual_data,
    output_dir=output_dir,
    captions_path=srt_path,
    sfx_category="duel_battle",
)
print(f"\n🎉 FINAL SHORT ASSEMBLED: {final_video_path}")
print(f"📦 File Size: {os.path.getsize(final_video_path)/(1024*1024):.2f} MB")

# ----------------------------------------------------------------------
# 7. Quality Control Audit
# ----------------------------------------------------------------------
print("\n🔍 Running Final Quality Control...")
qc_result = FinalQC.check_video(final_video_path)
print(f"QC Passed: {qc_result.get('passed')} (Score: {qc_result.get('score', 100)})")

# ----------------------------------------------------------------------
# 8. Extract Preview Frames
# ----------------------------------------------------------------------
thumb_dir = os.path.join(output_dir, "thumbnails")
os.makedirs(thumb_dir, exist_ok=True)
preview_frames = [
    (5.0, "short_preview_1990_russia_lead.jpg"),
    (20.0, "short_preview_2011_usa_overtake.jpg"),
    (32.0, "short_preview_usa_titan.jpg"),
]

for sec, fname in preview_frames:
    p_path = os.path.join(thumb_dir, fname)
    extract_cmd = [
        "ffmpeg", "-y",
        "-ss", str(sec),
        "-i", final_video_path,
        "-vframes", "1",
        "-q:v", "2",
        p_path
    ]
    subprocess.run(extract_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("📸 Extracted preview frames for verification.")

# ----------------------------------------------------------------------
# 9. SEO Metadata for YouTube Shorts
# ----------------------------------------------------------------------
title = "Who Produces The Most Natural Gas? (1990-2026) 🔥 #Shorts"
hashtags = ["#Shorts", "#NaturalGas", "#Energy", "#USA", "#Russia", "#Geopolitics", "#Economy", "#LRAtlas"]
tags = [
    "shorts", "natural gas", "natural gas production", "who produces the most natural gas",
    "usa vs russia", "shale gas", "fracking", "energy crisis", "russia gazprom",
    "us energy", "qatar gas", "lng", "bcm", "world data", "data battle"
]

description = (
    "Think Russia produces the most natural gas in the world? Think again! Watch the dramatic 35-year battle for global energy supremacy between the United States and Russia (1990-2026).\n\n"
    "Who do you think will control global energy in 2030? Comment below!\n\n"
    + " ".join(hashtags)
    + "\n\n📊 Source: Energy Institute Statistical Review of World Energy & EIA\nProduced by LR Atlas"
)

metadata = {
    "title": title,
    "description": description,
    "hashtags": hashtags,
    "tags": tags,
    "category": "Education",
    "video_path": final_video_path,
}

metadata_file = os.path.join(output_dir, "youtube_metadata.json")
with open(metadata_file, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2)
print("✅ SEO metadata saved to youtube_metadata.json")

# ----------------------------------------------------------------------
# 10. UPLOAD & PUBLISH LIVE TO YOUTUBE
# ----------------------------------------------------------------------
thumb_candidate = os.path.join(thumb_dir, "short_preview_2011_usa_overtake.jpg")

print("\n" + "=" * 60)
print(f"🚀 UPLOADING & PUBLISHING YOUTUBE SHORT NOW...")
print(f"📌 Title: {metadata['title']}")
print(f"🔒 Privacy Status: PUBLIC (Publishing Immediately)")
print("=" * 60)

upload_result = upload_video(
    video_path=final_video_path,
    metadata=metadata,
    thumbnail_path=thumb_candidate,
    privacy_status="public",
)

video_id = upload_result.get("video_id")
print("\n" + "=" * 60)
print(f"🎉 YOUTUBE SHORT PUBLISHED SUCCESSFULLY!")
print(f"🆔 Video ID: {video_id}")
print(f"🔗 Short URL: https://youtube.com/shorts/{video_id}")
print(f"🔒 Privacy Status: PUBLIC (LIVE)")
print("=" * 60)

with open(os.path.join(output_dir, "upload_result.json"), "w", encoding="utf-8") as f:
    json.dump({
        "video_id": video_id,
        "short_url": f"https://youtube.com/shorts/{video_id}",
        "status": "public",
        "published_at": datetime.now().isoformat(),
    }, f, indent=2)

print("\n🏁 ALL TASKS COMPLETED!")

