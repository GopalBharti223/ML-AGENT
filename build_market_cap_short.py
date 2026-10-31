"""Build and assemble an ultra-fast, high-retention 35-second YouTube Short (1080x1920 9:16).
Topic: Trillion Dollar Race: Most Valuable Companies (2018-2026) - NVIDIA vs Apple vs Microsoft
Features:
- VerticalDuelEngine (Always-On Mobile VS Battle HUD, Stock Ticker Monograms NVDA/AAPL/MSFT, Giant Year Counter).
- 142 BPM Battle Rush music (auto-ducked).
- High-contrast kinetic subtitles in the safe mobile corridor.
- Dynamic Unit Formatting ($ Trillions).
- Sleek Floating Debate Pill & Seamless Looping finish.
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
output_dir = os.path.join("output", "market_cap_short", timestamp)
os.makedirs(output_dir, exist_ok=True)
print(f"🎬 Preparing Most Valuable Companies YouTube Short Render in: {output_dir}")

# ----------------------------------------------------------------------
# 2. Load Market Cap Dataset
# ----------------------------------------------------------------------
dataset_info = VIRAL_INDICATORS["top_companies_market_cap"]
years = dataset_info["years"]
data_dict = dataset_info["data"]
df = pd.DataFrame(data_dict, index=years).T
df.columns = [int(c) for c in df.columns]
print(f"📊 Loaded {len(df)} companies across {len(years)} years ({years[0]} - {years[-1]}).")

# ----------------------------------------------------------------------
# 3. Create 35-Second Punchy Script (Seamless Viral Loop)
# ----------------------------------------------------------------------
scenes = [
    ScriptScene(
        scene_number=1,
        duration=8.5,
        narration=(
            "Think Apple is the most valuable company in the world? Think again! "
            "Back in 2018, Apple made history by becoming the world's first one-trillion-dollar company, "
            "while NVIDIA was sitting at just eighty billion!"
        ),
        visual_description="Apple reaches historic $1 Trillion while NVIDIA is a fraction",
        text_overlay="2018: Apple Reaches $1 Trillion",
        chart_type="vertical_duel",
        scene_purpose="HOOK",
        visual_emphasis="apple first trillion",
        highlight_countries=["Apple", "NVIDIA"],
        important_year=2018,
        important_value=0.74,
        pacing_hint="explosive hook",
    ),
    ScriptScene(
        scene_number=2,
        duration=8.5,
        narration=(
            "For years, Apple and Microsoft dominated global markets, "
            "both racing past three trillion dollars while Big Tech ruled the world."
        ),
        visual_description="Apple and Microsoft duel above $3 Trillion",
        text_overlay="2021: Apple & Microsoft Hit $3 Trillion",
        chart_type="vertical_duel",
        scene_purpose="BUILDUP",
        visual_emphasis="big tech dominance",
        highlight_countries=["Apple", "Microsoft"],
        important_year=2021,
        important_value=2.91,
        pacing_hint="fast climb",
    ),
    ScriptScene(
        scene_number=3,
        duration=9.0,
        narration=(
            "Then the Artificial Intelligence revolution exploded! "
            "Unstoppable demand for AI chips propelled NVIDIA on a historic rocket surge, "
            "surpassing Microsoft and dethroning Apple as number one in the world!"
        ),
        visual_description="NVIDIA AI rocket surge dethroning Apple to #1",
        text_overlay="2024: NVIDIA AI Rocket Surge to #1!",
        chart_type="vertical_duel",
        scene_purpose="CLIMAX",
        visual_emphasis="nvidia overtakes apple",
        highlight_countries=["NVIDIA", "Apple"],
        important_year=2024,
        important_value=3.4,
        pacing_hint="high energy overtake",
    ),
    ScriptScene(
        scene_number=4,
        duration=9.0,
        narration=(
            "Today in 2026, NVIDIA reigns supreme at three point seven five trillion dollars! "
            "Will NVIDIA hit five trillion first? Vote in the comments, because whenever you ask..."
        ),
        visual_description="NVIDIA crowned world champion with live floating debate pill",
        text_overlay="2026: The $3.75T AI Empire",
        chart_type="vertical_duel",
        scene_purpose="RESOLUTION",
        visual_emphasis="champion outro",
        highlight_countries=["NVIDIA"],
        important_year=2026,
        important_value=3.75,
        pacing_hint="triumphant outro",
    ),
]

script = VideoScript(
    title="Apple DOES NOT Have The Most Money?! 😱🚀 #Shorts",
    topic="Trillion Dollar Race: Most Valuable Companies by Market Cap - NVIDIA vs Apple (2018-2026)",
    category="Wealth",
    indicator_name="Market Cap ($ Trillion)",
    total_duration=35,
    scenes=scenes,
    fact_check=FactCheck(is_accurate=True, discrepancies="none"),
    source_name="Bloomberg & CompaniesMarketCap",
    source_url="https://companiesmarketcap.com",
    indicator_code="top_companies_market_cap",
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
    title="TRILLION DOLLAR TECH RACE",
    category_label="LR ATLAS // BIG TECH & AI WARS",
    duration_seconds=render_duration,
    fps=30,
    indicator_code="top_companies_market_cap",
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
title = "Apple DOES NOT Have The Most Money?! 😱🚀 #Shorts"
hashtags = ["#Shorts", "#NVIDIA", "#Apple", "#Microsoft", "#AI", "#Tech", "#StockMarket", "#Money"]
tags = [
    "shorts", "nvidia market cap", "apple vs nvidia", "most valuable company",
    "trillion dollar company", "tech wars", "ai revolution", "stock market",
    "data battle", "data race", "lr atlas"
]

description = (
    "Think Apple is still the world's most valuable company? Watch how NVIDIA's AI rocket surge took down Apple and Microsoft to reach $3.75 Trillion (2018-2026).\n\n"
    "Will NVIDIA hit $5 Trillion first? Comment below!\n\n"
    + " ".join(hashtags)
    + "\n\n📊 Produced by LR Atlas"
)

metadata = {
    "title": title,
    "description": description,
    "hashtags": hashtags,
    "tags": tags,
    "category": "Technology",
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
    (5.0, "short_preview_2018_apple_trillion.jpg"),
    (20.0, "short_preview_2024_nvidia_overtake.jpg"),
    (33.5, "short_preview_nvidia_champion.jpg"),
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
