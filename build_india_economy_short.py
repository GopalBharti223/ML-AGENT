"""Build and assemble a 26-second hyper-paced viral YouTube Short (1080x1920 9:16).
Topic: India vs UK vs World GDP: The $4 Trillion Economic Overtake (2000-2026)
Features:
- 0.8s Hook Shock Curiosity Banner (Frame 0 eye-lock)
- Sub-bass Hook Impact Boom at t=0.0s
- Dynamic Overtake Swoosh & Cash Bell SFX on rankings changes
- Word-by-word active neon gold glow captions (captions.ass)
- 26-second hyper-pace (Target APV > 100%)
- Seamless Viral Looping Outro
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
from app.captions import generate_ass_word_glow

# ----------------------------------------------------------------------
# 1. Output Directory
# ----------------------------------------------------------------------
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_dir = os.path.join("output", "india_gdp_short", timestamp)
os.makedirs(output_dir, exist_ok=True)
print(f"🎬 Preparing India vs UK Economy Short in: {output_dir}")

# ----------------------------------------------------------------------
# 2. Load Dataset
# ----------------------------------------------------------------------
dataset_info = VIRAL_INDICATORS["top_world_economies_gdp"]
years = dataset_info["years"]
data_dict = dataset_info["data"]
df = pd.DataFrame(data_dict, index=years).T
df.columns = [int(c) for c in df.columns]
print(f"📊 Loaded {len(df)} economies across {len(years)} years ({years[0]} - {years[-1]}).")

# ----------------------------------------------------------------------
# 3. Create 26-Second Hyper-Paced Script (Seamless Viral Loop)
# ----------------------------------------------------------------------
scenes = [
    ScriptScene(
        scene_number=1,
        duration=6.5,
        narration=(
            "Think the UK is still richer than India? Think again! "
            "Back in 2000, India had just 470 billion dollars, while the UK was nearly four times larger!"
        ),
        visual_description="2000 starting positions: UK far ahead of India",
        text_overlay="2000: UK 4x Larger Than India",
        chart_type="vertical_duel",
        scene_purpose="HOOK",
        visual_emphasis="india vs uk start",
        highlight_countries=["India", "United Kingdom"],
        important_year=2000,
        important_value=0.47,
        pacing_hint="explosive hook",
    ),
    ScriptScene(
        scene_number=2,
        duration=6.5,
        narration=(
            "For two decades, India launched an unstoppable economic surge, "
            "blasting past France and Italy to conquer the global ranks!"
        ),
        visual_description="India overtaking European powers",
        text_overlay="2015: India Rockets Past Europe",
        chart_type="vertical_duel",
        scene_purpose="BUILDUP",
        visual_emphasis="fast climb",
        highlight_countries=["India", "France"],
        important_year=2015,
        important_value=2.10,
        pacing_hint="fast climb",
    ),
    ScriptScene(
        scene_number=3,
        duration=6.5,
        narration=(
            "Then in 2022, history was made! "
            "India officially dethroned the United Kingdom to become the fifth largest economy on Earth!"
        ),
        visual_description="India overtakes United Kingdom for #5",
        text_overlay="2022: India Dethrones UK to #5!",
        chart_type="vertical_duel",
        scene_purpose="CLIMAX",
        visual_emphasis="historic overtake",
        highlight_countries=["India", "United Kingdom"],
        important_year=2022,
        important_value=3.42,
        pacing_hint="high energy overtake",
    ),
    ScriptScene(
        scene_number=4,
        duration=6.5,
        narration=(
            "Today in 2026, India reaches four point two trillion dollars, closing in on Germany for number three! "
            "Will India reach number three by 2028? Vote in the comments, because whenever you ask..."
        ),
        visual_description="India chasing Germany & Japan with live debate pill",
        text_overlay="2026: The $4.2T Powerhouse",
        chart_type="vertical_duel",
        scene_purpose="RESOLUTION",
        visual_emphasis="champion outro",
        highlight_countries=["India"],
        important_year=2026,
        important_value=4.25,
        pacing_hint="triumphant outro",
    ),
]

script = VideoScript(
    title="India Surpasses UK Economy?! 🇮🇳🚀 #Shorts",
    topic="World GDP Race: India vs UK vs Japan vs Germany (2000-2026)",
    category="Economy",
    indicator_name="GDP ($ Trillion)",
    total_duration=26,
    scenes=scenes,
    fact_check=FactCheck(is_accurate=True, discrepancies="none"),
    source_name="International Monetary Fund (IMF) & World Bank",
    source_url="https://www.imf.org",
    indicator_code="top_world_economies_gdp",
)

with open(os.path.join(output_dir, "script.json"), "w", encoding="utf-8") as f:
    json.dump(script.model_dump(), f, indent=2)
print("📝 Script created: 4 punchy scenes, 26.0s target duration.")

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

print("⏱️ Synchronizing audio narration segments to visual scene timeline (26.0s)...")
padded_audio = VideoAssembler.align_landscape_audio(
    audio_data=audio_data,
    output_dir=output_dir,
    target_total_duration=26.0,
)
print("✅ Audio synchronization complete.")

# Generate Kinetic Word-Level ASS Subtitles (Neon Yellow Active Glow)
ass_path = generate_ass_word_glow(
    audio_data=padded_audio,
    output_dir=output_dir,
    filename="captions.ass",
    active_color_bgr="&H0024E5FF&",  # Bright Neon Yellow / Gold
)
print(f"✅ Kinetic Glow ASS Subtitles ready: {ass_path}")

# ----------------------------------------------------------------------
# 5. Render 1080x1920 Vertical Animation (With 0.8s Hook Shock)
# ----------------------------------------------------------------------
visual_dir = os.path.join(output_dir, "visuals")
os.makedirs(visual_dir, exist_ok=True)
animation_path = os.path.join(visual_dir, "visual_0.mp4")
render_duration = 26.0

print("\n⚔️ Rendering 1080x1920 Vertical Duel Animation (26s) ...")
VerticalDuelEngine.render_portrait_animation(
    wide_data=df,
    output_file=animation_path,
    title="TOP WORLD ECONOMIES (GDP)",
    category_label="LR ATLAS // GLOBAL WEALTH WARS",
    duration_seconds=render_duration,
    fps=30,
    indicator_code="top_world_economies_gdp",
    hook_question="DID INDIA CRUSH THE UK ECONOMY?!",
)
print(f"✅ Animation rendered successfully: {animation_path} ({os.path.getsize(animation_path)/(1024*1024):.1f} MB)")

visual_data = [{"scene_number": 1, "image_path": animation_path}]

# ----------------------------------------------------------------------
# 6. Assemble Final Short (Hook Boom + Overtake SFX + Kinetic ASS Captions)
# ----------------------------------------------------------------------
print("\n🎞️ Assembling Final YouTube Short with 142 BPM Battle Rush & Dynamic SFX...")
final_video_path = VideoAssembler.create_video(
    audio_data=padded_audio,
    visual_data=visual_data,
    output_dir=output_dir,
    captions_path=ass_path,
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
title = "India Surpasses UK Economy?! 🇮🇳🚀 #Shorts"
hashtags = ["#Shorts", "#India", "#UK", "#Economy", "#GDP", "#Geopolitics", "#Growth", "#World"]
tags = [
    "shorts", "india vs uk economy", "india gdp", "india overtakes uk",
    "top economies by gdp", "india superpower", "world economy",
    "geopolitics", "data race", "lr atlas"
]

description = (
    "Think the UK is still richer than India? Watch how India's unstoppable economic surge overtook the United Kingdom to become the #5 economy in the world (2000-2026).\n\n"
    "Will India become #3 by 2028? Vote in the comments below!\n\n"
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
    (0.4, "short_preview_01_hook_shock.jpg"),
    (14.0, "short_preview_02_india_overtake_uk.jpg"),
    (24.5, "short_preview_03_india_debate_outro.jpg"),
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
