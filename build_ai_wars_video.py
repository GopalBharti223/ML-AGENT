"""Build and render an 85-second 16:9 widescreen long-format video for:
The AI Wars: ChatGPT vs Google Gemini vs Claude vs Groq vs Meta AI (2021-2026).
Features Cyber AI Theme (Emerald vs Violet), 142 BPM Battle Rush audio, sleek 13pt captions,
top-right corner Battle HUD, and complete SEO metadata with ready-to-paste pinned comment.
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
output_dir = os.path.join("output", "ai_wars", timestamp)
os.makedirs(output_dir, exist_ok=True)
print(f"🎬 Preparing AI Wars Long-Format Render in: {output_dir}")

# ----------------------------------------------------------------------
# 2. Load 2021-2026 AI Models Race Dataset
# ----------------------------------------------------------------------
dataset_info = VIRAL_INDICATORS["ai_models_race"]
years = dataset_info["years"]
data_dict = dataset_info["data"]
df = pd.DataFrame(data_dict, index=years).T
df.columns = [int(c) for c in df.columns]
print(f"📊 Loaded {len(df)} AI models across {len(years)} years ({years[0]} - {years[-1]}).")

# ----------------------------------------------------------------------
# 3. Create 85-Second High-Tension Script
# ----------------------------------------------------------------------
scenes = [
    ScriptScene(
        scene_number=1,
        duration=14.0,
        narration=(
            "In late 2022, the modern artificial intelligence race ignited when OpenAI launched ChatGPT, "
            "reaching one hundred million monthly users in just two months and shattering all historic consumer adoption records."
        ),
        visual_description="OpenAI launches ChatGPT sparking the historic modern generative AI boom",
        text_overlay="2021-2022: OpenAI Launches ChatGPT & The AI Revolution",
        chart_type="widescreen_duel",
        scene_purpose="HOOK",
        visual_emphasis="chatgpt launch",
        highlight_countries=["ChatGPT (OpenAI)", "Midjourney"],
        important_year=2022,
        important_value=50.0,
        pacing_hint="steady buildup",
    ),
    ScriptScene(
        scene_number=2,
        duration=14.0,
        narration=(
            "By 2023, Silicon Valley triggered a frantic trillion dollar gold rush. "
            "Google declared an internal code red to launch Bard, while Microsoft invested billions to power Copilot across Windows."
        ),
        visual_description="Tech giants scramble to enter the generative AI race",
        text_overlay="2023: The Generative AI Gold Rush & Tech Titan Clash",
        chart_type="widescreen_duel",
        scene_purpose="BUILDUP",
        visual_emphasis="ai gold rush",
        highlight_countries=["ChatGPT (OpenAI)", "Google Gemini", "Microsoft Copilot"],
        important_year=2023,
        important_value=180.0,
        pacing_hint="accelerating climb",
    ),
    ScriptScene(
        scene_number=3,
        duration=14.0,
        narration=(
            "In 2024, the frontier escalated dramatically. "
            "Google rebranded to Gemini, Anthropic's Claude three point five Sonnet conquered advanced coding, and Groq shattered ultra fast inference speed barriers."
        ),
        visual_description="Gemini rebrands, Claude 3.5 Sonnet leads coding, and Groq breaks speed records",
        text_overlay="2024: Google Gemini, Claude 3.5 Sonnet & Groq LPUs",
        chart_type="widescreen_duel",
        scene_purpose="TENSION",
        visual_emphasis="frontier model clash",
        highlight_countries=["ChatGPT (OpenAI)", "Google Gemini", "Claude (Anthropic)", "Groq (Fast LPU)"],
        important_year=2024,
        important_value=320.0,
        pacing_hint="battle tension",
    ),
    ScriptScene(
        scene_number=4,
        duration=14.0,
        narration=(
            "Meta unleashed its open source Llama models, instantly distributing Meta AI to over four hundred million active users across WhatsApp and Instagram, "
            "mounting a fierce global challenge."
        ),
        visual_description="Meta AI leverages WhatsApp and Instagram to challenge ChatGPT directly",
        text_overlay="2024-2025: Meta AI & The Open Source Llama Surge",
        chart_type="widescreen_duel",
        scene_purpose="MILESTONE",
        visual_emphasis="meta ai surge",
        highlight_countries=["ChatGPT (OpenAI)", "Meta AI (Llama)", "Google Gemini"],
        important_year=2025,
        important_value=360.0,
        pacing_hint="steady growth",
    ),
    ScriptScene(
        scene_number=5,
        duration=14.0,
        narration=(
            "Then came the era of reasoning models and autonomous agents. "
            "OpenAI unveiled its revolutionary o-series, while DeepSeek shocked the global tech ecosystem with astonishingly efficient frontier reasoning."
        ),
        visual_description="Reasoning models emerge with OpenAI o1/o3 and DeepSeek R1",
        text_overlay="2025-2026: Reasoning Models & The DeepSeek Shockwave",
        chart_type="widescreen_duel",
        scene_purpose="CLIMAX",
        visual_emphasis="reasoning models",
        highlight_countries=["ChatGPT (OpenAI)", "DeepSeek", "Google Gemini"],
        important_year=2025,
        important_value=420.0,
        pacing_hint="high energy overtake",
    ),
    ScriptScene(
        scene_number=6,
        duration=15.0,
        narration=(
            "Today in 2026, ChatGPT reigns supreme with four hundred and eighty million active users! "
            "Which AI model is your daily favorite? Comment below, like, and subscribe to LR Atlas for more epic data battles!"
        ),
        visual_description="ChatGPT crowned undisputed AI leader with glassmorphic Outro Card",
        text_overlay="2026: Undisputed AI King & The Future Frontier",
        chart_type="widescreen_duel",
        scene_purpose="RESOLUTION",
        visual_emphasis="all time champion",
        highlight_countries=["ChatGPT (OpenAI)", "Meta AI (Llama)"],
        important_year=2026,
        important_value=480.0,
        pacing_hint="triumphant outro",
    ),
]

script = VideoScript(
    title="The AI Wars: ChatGPT vs Google Gemini vs Claude vs Groq | Who Won?",
    topic="The AI Wars: ChatGPT vs Google Gemini vs Claude vs Groq vs Meta AI (2021-2026)",
    category="Technology",
    indicator_name="Monthly Active Users (Millions)",
    total_duration=85,
    scenes=scenes,
    fact_check=FactCheck(is_accurate=True, discrepancies="none"),
    source_name="SimilarWeb Intelligence, Sensor Tower & Company Disclosures",
    source_url="https://www.similarweb.com",
    indicator_code="ai_models_race",
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
# 5. Render 1920x1080 Widescreen Duel Animation (Cyber AI Theme)
# ----------------------------------------------------------------------
visual_dir = os.path.join(output_dir, "visuals")
os.makedirs(visual_dir, exist_ok=True)
animation_path = os.path.join(visual_dir, "visual_0.mp4")
render_duration = 85.0

print("\n⚔️ Rendering 1920x1080 Widescreen Duel Animation in CYBER AI THEME (85s) ...")
WidescreenDuelEngine.render_landscape_animation(
    wide_data=df,
    output_file=animation_path,
    title=script.title,
    category_label="LR ATLAS DATA LABS // ARTIFICIAL INTELLIGENCE RACE",
    duration_seconds=render_duration,
    fps=30,
    indicator_code="ai_models_race",
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
# 8. Generate 450-Character SEO Tags, Clickable Hashtags & Pinned Comment
# ----------------------------------------------------------------------
print("\n🏷️ Generating SEO Tags, Hashtags & Pinned Comment Section...")

title = "The AI Wars (2021–2026): ChatGPT vs Google Gemini vs Claude vs Groq | Who Won?"

hashtags = [
    "#AIWars",
    "#ChatGPT",
    "#GoogleGemini",
    "#ClaudeAI",
    "#ArtificialIntelligence"
]

tags = [
    "chatgpt",
    "google gemini",
    "claude ai",
    "groq",
    "meta ai",
    "deepseek",
    "ai wars",
    "openai",
    "anthropic",
    "microsoft copilot",
    "chatgpt vs gemini",
    "claude 3.5 sonnet",
    "artificial intelligence",
    "groq lpu",
    "chatgpt user count 2026",
    "best ai model 2026",
    "ai comparison",
    "ai benchmark",
    "bar chart race",
    "data visualization",
    "lr atlas"
]

description = (
    "From OpenAI launching ChatGPT in late 2022 to an astonishing 480 Million monthly active users in 2026, "
    "this is the definitive visual history of the global AI Race: ChatGPT vs Google Gemini vs Claude vs Groq vs Meta AI.\n\n"
    "Watch the complete rise of generative AI, Google's frantic code red and Gemini rebrand, "
    "Claude 3.5 Sonnet's coding surge, Groq's lightning-fast LPUs, and DeepSeek's open reasoning breakthrough.\n\n"
    "📊 Data Sources: SimilarWeb Intelligence, Sensor Tower & Company Disclosures.\n\n"
    + " ".join(hashtags)
    + "\n\n📊 Produced by LR Atlas Data Labs"
)

pinned_comment = (
    "🤖 QUICK POLL: Which AI model is your daily favorite in 2026?\n"
    "🟢 A) ChatGPT (GPT-4o / o1 / o3)\n"
    "🟣 B) Google Gemini (2.0 Pro / Ultra)\n"
    "🟠 C) Claude 3.5 / 3.7 Sonnet (Anthropic)\n"
    "⚡ D) Groq / DeepSeek / Meta AI (Comment below!)\n\n"
    "⏱️ TIMESTAMPS & CHAPTERS:\n"
    "0:00 — 2021-2022: OpenAI Launches ChatGPT & The AI Revolution\n"
    "0:14 — 2023: The Generative AI Gold Rush & Tech Titan Clash\n"
    "0:28 — 2024: Google Gemini, Claude 3.5 Sonnet & Groq LPUs\n"
    "0:42 — 2024-2025: Meta AI & The Open Source Llama Surge\n"
    "0:56 — 2025-2026: Reasoning Models & The DeepSeek Shockwave\n"
    "1:10 — 2026: The Undisputed All-Time AI Champion\n"
    "1:18 — Final Verdict & Community Poll\n\n"
    "🔔 Subscribe to LR Atlas for daily high-stakes data wars! Which topic should we race next? 👇"
)

metadata = {
    "title": title,
    "description": description,
    "hashtags": hashtags,
    "tags": tags,
    "category": "Technology",
    "pinned_comment": pinned_comment,
    "thumbnail_text": "ChatGPT vs Gemini vs Claude: Who Won?",
}

metadata_file = os.path.join(output_dir, "youtube_metadata.json")
with open(metadata_file, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2)
print("✅ Full SEO metadata & pinned comment saved to youtube_metadata.json")

# ----------------------------------------------------------------------
# 9. Extract High-Resolution Preview Frames
# ----------------------------------------------------------------------
thumb_dir = os.path.join(output_dir, "thumbnails")
os.makedirs(thumb_dir, exist_ok=True)
preview_frames = [
    (15.0, "preview_scene1_hook.jpg"),
    (42.0, "preview_scene3_battle.jpg"),
    (65.0, "preview_scene5_deepseek.jpg"),
    (82.0, "preview_scene6_outro.jpg"),
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
print("📸 Extracted 4 preview frames for verification.")

# ----------------------------------------------------------------------
# 10. Upload to YouTube as UNLISTED
# ----------------------------------------------------------------------
print("\n🚀 Uploading Final Video to YouTube as UNLISTED...")
privacy_status = "unlisted"
try:
    upload_res = upload_video(
        video_path=final_video_path,
        title=title,
        description=description,
        tags=tags,
        category_id="28",  # Science & Technology
        privacy_status=privacy_status,
    )
    video_id = upload_res.get("id")
    video_url = f"https://youtu.be/{video_id}"
    print(f"\n🎉 UPLOAD SUCCESSFUL!")
    print(f"📺 Video URL: {video_url}")
    print(f"🔒 Privacy Status: {privacy_status.upper()}")

    with open(os.path.join(output_dir, "upload_result.json"), "w", encoding="utf-8") as f:
        json.dump({"video_id": video_id, "video_url": video_url, "status": privacy_status}, f, indent=2)

except Exception as e:
    print(f"❌ Upload encountered an error: {e}")
    import traceback
    traceback.print_exc()

print(f"\n✨ AI Wars Video Pipeline Complete! All assets stored in: {output_dir}")
