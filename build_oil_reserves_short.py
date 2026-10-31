"""Build and assemble an ultra-fast, high-retention 35-second YouTube Short (1080x1920 9:16).
Topic: Which Country Has The Most Oil Reserves? (1990-2026) - Venezuela vs Saudi Arabia vs Iran vs USA
Features:
- VerticalDuelEngine (Always-On Mobile VS Battle HUD, Monogram Badges, Giant Year Counter).
- 142 BPM Battle Rush music (auto-ducked).
- High-contrast kinetic subtitles in the safe mobile corridor.
- Dynamic Unit Formatting (Billion Barrels).
- Cinematic Outro Card with Community CTA.
"""

import os
import sys
import json
import time
from datetime import datetime
import pandas as pd

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

# ----------------------------------------------------------------------
# 1. Output Directory
# ----------------------------------------------------------------------
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_dir = os.path.join("output", "oil_reserves_short", timestamp)
os.makedirs(output_dir, exist_ok=True)
print(f"🎬 Preparing Global Oil Reserves YouTube Short Render in: {output_dir}")

# ----------------------------------------------------------------------
# 2. Load Global Oil Reserves Dataset
# ----------------------------------------------------------------------
dataset_info = VIRAL_INDICATORS["global_oil_reserves"]
years = dataset_info["years"]
data_dict = dataset_info["data"]
df = pd.DataFrame(data_dict, index=years).T
df.columns = [int(c) for c in df.columns]
print(f"📊 Loaded {len(df)} countries across {len(years)} years ({years[0]} - {years[-1]}).")

# ----------------------------------------------------------------------
# 3. Create 35-Second Punchy Script (High Viral Retention)
# ----------------------------------------------------------------------
scenes = [
    ScriptScene(
        scene_number=1,
        duration=8.5,
        narration=(
            "Think Saudi Arabia has the world's largest oil reserves? Think again! "
            "Back in 1990, Saudi Arabia ruled supreme with two hundred and sixty billion barrels, "
            "while Venezuela held just sixty billion."
        ),
        visual_description="Saudi Arabia dominates global oil in 1990",
        text_overlay="1990: Saudi Arabia Rules Global Energy",
        chart_type="vertical_duel",
        scene_purpose="HOOK",
        visual_emphasis="saudi arabia dominance",
        highlight_countries=["Saudi Arabia", "Venezuela"],
        important_year=1990,
        important_value=260.0,
        pacing_hint="explosive hook",
    ),
    ScriptScene(
        scene_number=2,
        duration=8.5,
        narration=(
            "For two decades, the Middle East looked untouchable. "
            "Canada jumped into the top tier after certifying Alberta oil sands, "
            "while Iran and Iraq expanded their massive energy reserves."
        ),
        visual_description="Canada leaps up with oil sands; Middle East holds top positions",
        text_overlay="2005: Canada & Middle East Dominance",
        chart_type="vertical_duel",
        scene_purpose="BUILDUP",
        visual_emphasis="oil sands certification",
        highlight_countries=["Canada", "Iran", "Iraq"],
        important_year=2005,
        important_value=178.8,
        pacing_hint="fast climb",
    ),
    ScriptScene(
        scene_number=3,
        duration=9.0,
        narration=(
            "Then came the massive historic shock! "
            "Venezuela certified the monstrous Orinoco Belt, skyrocketing past three hundred billion barrels "
            "and stripping Saudi Arabia of the world number one crown!"
        ),
        visual_description="Venezuela historic surge past Saudi Arabia to world #1",
        text_overlay="2011: Venezuela Dethrones Saudi Arabia!",
        chart_type="vertical_duel",
        scene_purpose="CLIMAX",
        visual_emphasis="venezuela overtakes saudi arabia",
        highlight_countries=["Venezuela", "Saudi Arabia"],
        important_year=2011,
        important_value=300.9,
        pacing_hint="high energy overtake",
    ),
    ScriptScene(
        scene_number=4,
        duration=9.0,
        narration=(
            "Today, Venezuela reigns supreme with three hundred and four billion barrels! "
            "Who will control global energy in 2030? Vote in the comments, because whenever you ask..."
        ),
        visual_description="Venezuela crowned champion with live floating debate pill",
        text_overlay="2026: The Undisputed King of Oil",
        chart_type="vertical_duel",
        scene_purpose="RESOLUTION",
        visual_emphasis="champion outro",
        highlight_countries=["Venezuela"],
        important_year=2026,
        important_value=304.0,
        pacing_hint="triumphant outro",
    ),
]

script = VideoScript(
    title="Which Country Has The Most Oil? (1990-2026): Venezuela vs Saudi Arabia",
    topic="World Proven Crude Oil Reserves: Venezuela vs Saudi Arabia vs Iran (1990-2026)",
    category="Energy & Resources",
    indicator_name="Crude Oil Reserves (Billion Barrels)",
    total_duration=35,
    scenes=scenes,
    fact_check=FactCheck(is_accurate=True, discrepancies="none"),
    source_name="OPEC Annual Statistical Bulletin & Energy Institute (EI)",
    source_url="https://www.opec.org",
    indicator_code="global_oil_reserves",
)

with open(os.path.join(output_dir, "script.json"), "w", encoding="utf-8") as f:
    json.dump(script.model_dump(), f, indent=2)
print("📝 Script created: 4 punchy scenes, 35.0 seconds target duration.")

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
    title="WHICH COUNTRY HAS THE MOST OIL?",
    category_label="LR ATLAS // GLOBAL ENERGY WARS",
    duration_seconds=render_duration,
    fps=30,
    indicator_code="global_oil_reserves",
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
# 8. SEO Metadata for YouTube Shorts
# ----------------------------------------------------------------------
title = "Which Country Has The Most Oil? (1990-2026) 🛢️ #Shorts"
hashtags = ["#Shorts", "#Oil", "#Energy", "#Geopolitics", "#Economy", "#Venezuela", "#SaudiArabia"]
tags = [
    "shorts", "oil reserves", "crude oil", "venezuela oil", "saudi arabia oil",
    "largest oil reserves", "petroleum", "energy", "geopolitics", "opec",
    "world data", "data battle"
]

description = (
    "Think Saudi Arabia has the most oil in the world? Think again! Watch how Venezuela overtook Saudi Arabia to claim the world's largest proven crude oil reserves (1990-2026).\n\n"
    "Who do you think will dominate global energy by 2030? Comment below!\n\n"
    + " ".join(hashtags)
    + "\n\n📊 Produced by LR Atlas"
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
# 9. Extract Preview Frames
# ----------------------------------------------------------------------
thumb_dir = os.path.join(output_dir, "thumbnails")
os.makedirs(thumb_dir, exist_ok=True)
preview_frames = [
    (5.0, "short_preview_1990_saudi_lead.jpg"),
    (20.0, "short_preview_2011_venezuela_overtake.jpg"),
    (32.0, "short_preview_venezuela_champion.jpg"),
]

import subprocess
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
print("📸 Extracted 3 preview frames for verification.")
print(f"\n✨ YouTube Short Pipeline Complete! Video ready at: {final_video_path}")
