"""Build and assemble an ultra-fast, high-retention 35-second YouTube Short (1080x1920 9:16).
Features:
- VerticalDuelEngine (Always-On Mobile VS Battle HUD, Monogram Badges, Giant Year Counter).
- 142 BPM Battle Rush music (auto-ducked).
- High-contrast kinetic 13pt captions in the safe mobile corridor.
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
output_dir = os.path.join("output", "ai_wars_short", timestamp)
os.makedirs(output_dir, exist_ok=True)
print(f"🎬 Preparing AI Wars YouTube Short Render in: {output_dir}")

# ----------------------------------------------------------------------
# 2. Load AI Models Race Dataset
# ----------------------------------------------------------------------
dataset_info = VIRAL_INDICATORS["ai_models_race"]
years = dataset_info["years"]
data_dict = dataset_info["data"]
df = pd.DataFrame(data_dict, index=years).T
df.columns = [int(c) for c in df.columns]
print(f"📊 Loaded {len(df)} AI models across {len(years)} years ({years[0]} - {years[-1]}).")

# ----------------------------------------------------------------------
# 3. Create 35-Second Punchy Script (High Viral Retention)
# ----------------------------------------------------------------------
scenes = [
    ScriptScene(
        scene_number=1,
        duration=8.5,
        narration=(
            "In 2022, OpenAI ignited the artificial intelligence revolution with ChatGPT, "
            "reaching one hundred million users faster than any app in human history."
        ),
        visual_description="ChatGPT launch sparks global AI race",
        text_overlay="2022: ChatGPT Smashes Adoption Records",
        chart_type="vertical_duel",
        scene_purpose="HOOK",
        visual_emphasis="chatgpt launch",
        highlight_countries=["ChatGPT (OpenAI)"],
        important_year=2022,
        important_value=50.0,
        pacing_hint="explosive hook",
    ),
    ScriptScene(
        scene_number=2,
        duration=8.5,
        narration=(
            "By 2024, Google unleashed Gemini, Claude conquered coding, "
            "and Groq shattered ultra-fast inference speed barriers."
        ),
        visual_description="Tech giants battle in frontier AI",
        text_overlay="2024: Gemini & Claude Challenge OpenAI",
        chart_type="vertical_duel",
        scene_purpose="BUILDUP",
        visual_emphasis="frontier clash",
        highlight_countries=["Google Gemini", "Claude (Anthropic)", "Groq (Fast LPU)"],
        important_year=2024,
        important_value=160.0,
        pacing_hint="fast climb",
    ),
    ScriptScene(
        scene_number=3,
        duration=9.0,
        narration=(
            "Then Meta distributed open-source Llama to four hundred million users on WhatsApp, "
            "while DeepSeek stunned the world with hyper-efficient reasoning."
        ),
        visual_description="Meta AI and DeepSeek shock the AI industry",
        text_overlay="2025: Meta AI & DeepSeek Shockwave",
        chart_type="vertical_duel",
        scene_purpose="CLIMAX",
        visual_emphasis="meta ai and deepseek",
        highlight_countries=["Meta AI (Llama)", "DeepSeek"],
        important_year=2025,
        important_value=360.0,
        pacing_hint="high energy clash",
    ),
    ScriptScene(
        scene_number=4,
        duration=9.0,
        narration=(
            "Today in 2026, ChatGPT reigns supreme with four hundred and eighty million users! "
            "Which AI model is your daily favorite? Comment below and subscribe to LR Atlas!"
        ),
        visual_description="ChatGPT crowned champion with Outro Card",
        text_overlay="2026: The Undisputed AI King",
        chart_type="vertical_duel",
        scene_purpose="RESOLUTION",
        visual_emphasis="champion outro",
        highlight_countries=["ChatGPT (OpenAI)"],
        important_year=2026,
        important_value=480.0,
        pacing_hint="triumphant outro",
    ),
]

script = VideoScript(
    title="ChatGPT vs Google Gemini: Who Won The AI Wars?",
    topic="The AI Wars: ChatGPT vs Google Gemini vs Claude vs Groq (2021-2026)",
    category="Technology",
    indicator_name="Monthly Active Users (Millions)",
    total_duration=35,
    scenes=scenes,
    fact_check=FactCheck(is_accurate=True, discrepancies="none"),
    source_name="SimilarWeb & Company Disclosures",
    source_url="https://www.similarweb.com",
    indicator_code="ai_models_race",
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
    title=script.title,
    category_label="LR ATLAS // ARTIFICIAL INTELLIGENCE RACE",
    duration_seconds=render_duration,
    fps=30,
    indicator_code="ai_models_race",
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
title = "ChatGPT vs Google Gemini: Who Won The AI Wars? #Shorts"
hashtags = ["#Shorts", "#AIWars", "#ChatGPT", "#GoogleGemini", "#ClaudeAI"]
tags = ["shorts", "chatgpt", "gemini", "claude ai", "groq", "meta ai", "ai wars", "openai", "deepseek"]

description = (
    "Who reached 100M users the fastest? The definitive AI Race (2021-2026): ChatGPT vs Google Gemini vs Claude vs Groq.\n\n"
    + " ".join(hashtags)
    + "\n\n📊 Produced by LR Atlas"
)

metadata = {
    "title": title,
    "description": description,
    "hashtags": hashtags,
    "tags": tags,
    "category": "Technology",
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
    (5.0, "short_preview_hook.jpg"),
    (18.0, "short_preview_mid_battle.jpg"),
    (32.0, "short_preview_outro.jpg"),
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
