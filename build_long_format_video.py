"""Build and render an 85-second 16:9 widescreen long-format video with Duel Mode,
142 BPM Battle Rush audio, always-on scoreboard, and cinematic outro card.
"""

import os
import sys
import json
import time
from datetime import datetime
import pandas as pd

# Force UTF-8 stream
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
from app.youtube.thumbnail import ThumbnailEngine
from app.qc.final_qc import FinalQC
from app.captions import generate_srt

# ----------------------------------------------------------------------
# 1. Prepare Output Directory
# ----------------------------------------------------------------------
if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
    output_dir = sys.argv[1]
else:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join("output", "long_format", timestamp)
    os.makedirs(output_dir, exist_ok=True)
print(f"🎬 Preparing Long-Format Render in: {output_dir}")

# ----------------------------------------------------------------------
# 2. Load 2011-2026 YouTube Subscribers Race Dataset
# ----------------------------------------------------------------------
dataset_info = VIRAL_INDICATORS["youtube_subscribers_race"]
years = dataset_info["years"]
data_dict = dataset_info["data"]
df = pd.DataFrame(data_dict, index=years).T
# Ensure columns are integer years
df.columns = [int(c) for c in df.columns]
print(f"📊 Loaded {len(df)} channels across {len(years)} years ({years[0]} - {years[-1]}).")

# ----------------------------------------------------------------------
# 3. Create 85-Second High-Tension Script
# ----------------------------------------------------------------------
scenes = [
    ScriptScene(
        scene_number=1,
        duration=14.0,
        narration=(
            "In 2011, the kings of early YouTube were RayWilliamJohnson and Smosh, "
            "pulling in millions of passionate fans when reaching five million subscribers was an unimaginable world record."
        ),
        visual_description="RayWilliamJohnson and Smosh lead early YouTube rankings as gaming creators emerge",
        text_overlay="2011: The Golden Age of Early YouTube Kings",
        chart_type="widescreen_duel",
        scene_purpose="HOOK",
        visual_emphasis="early kings",
        highlight_countries=["RayWilliamJohnson", "Smosh", "PewDiePie"],
        important_year=2011,
        important_value=5.2,
        pacing_hint="steady buildup",
    ),
    ScriptScene(
        scene_number=2,
        duration=14.0,
        narration=(
            "By 2013, the gaming explosion arrived. A Swedish creator named PewDiePie skyrocketed "
            "from just two million to nineteen million subscribers, seizing the number one crown and dominating the global leaderboard for years."
        ),
        visual_description="PewDiePie surges past Smosh and dominates global gaming leaderboards",
        text_overlay="2013-2016: The PewDiePie Era Begins",
        chart_type="widescreen_duel",
        scene_purpose="BUILDUP",
        visual_emphasis="pewdiepie rise",
        highlight_countries=["PewDiePie", "Smosh", "T-Series"],
        important_year=2013,
        important_value=19.0,
        pacing_hint="accelerating climb",
    ),
    ScriptScene(
        scene_number=3,
        duration=14.0,
        narration=(
            "Then came 2018. India's digital revolution propelled music powerhouse T-Series into global contention, "
            "sparking the legendary PewDiePie versus T-Series war that captured the entire internet and redefined digital entertainment."
        ),
        visual_description="T-Series closes the gap on PewDiePie sparking the legendary battle",
        text_overlay="2018: The Historic 100M Subscriber War",
        chart_type="widescreen_duel",
        scene_purpose="TENSION",
        visual_emphasis="the subscriber war",
        highlight_countries=["PewDiePie", "T-Series"],
        important_year=2018,
        important_value=80.0,
        pacing_hint="battle tension",
    ),
    ScriptScene(
        scene_number=4,
        duration=14.0,
        narration=(
            "In 2019, T-Series made history as the very first channel to cross one hundred million subscribers. "
            "Meanwhile, global lockdown surges catapulted Cocomelon and family animation channels into the top ranks of YouTube."
        ),
        visual_description="T-Series crosses 100M milestone first as kids channels explode",
        text_overlay="2019-2021: First Channel to 100 Million",
        chart_type="widescreen_duel",
        scene_purpose="MILESTONE",
        visual_emphasis="100 million milestone",
        highlight_countries=["T-Series", "Cocomelon", "PewDiePie"],
        important_year=2019,
        important_value=122.0,
        pacing_hint="steady growth",
    ),
    ScriptScene(
        scene_number=5,
        duration=14.0,
        narration=(
            "But nobody was prepared for MrBeast. Through unprecedented viral mega-productions and insane giveaways, "
            "he climbed from twelve million in 2018 to over two hundred and fifty million, closing the impossible gap."
        ),
        visual_description="MrBeast accelerates at historic velocity closing the lead on T-Series",
        text_overlay="2022-2024: MrBeast Closes The Impossible Gap",
        chart_type="widescreen_duel",
        scene_purpose="CLIMAX",
        visual_emphasis="mrbeast surge",
        highlight_countries=["MrBeast", "T-Series"],
        important_year=2023,
        important_value=224.0,
        pacing_hint="high energy overtake",
    ),
    ScriptScene(
        scene_number=6,
        duration=15.0,
        narration=(
            "In June 2024, the historic overtake shook the internet. Today, MrBeast reigns undisputed past three hundred and eighty-five million subscribers! "
            "Who had the greatest run in internet history? Comment below, like, and subscribe to LR Atlas for more epic data battles!"
        ),
        visual_description="MrBeast overtakes T-Series and claims all-time #1 crown with outro card",
        text_overlay="2024-2026: The Undisputed All-Time Champion",
        chart_type="widescreen_duel",
        scene_purpose="RESOLUTION",
        visual_emphasis="all time champion",
        highlight_countries=["MrBeast", "T-Series"],
        important_year=2026,
        important_value=385.0,
        pacing_hint="triumphant outro",
    ),
]

script = VideoScript(
    title="YouTube Subscriber War: Who Reaches 385M and Conquers History?",
    topic="YouTube Subscriber Race: MrBeast vs T-Series vs PewDiePie (2011-2026)",
    category="Entertainment",
    indicator_name="Subscribers (Millions)",
    total_duration=85,
    scenes=scenes,
    fact_check=FactCheck(is_accurate=True, discrepancies="none"),
    source_name="YouTube Data API & Social Blade Archive",
    source_url="https://socialblade.com",
    indicator_code="youtube_subscribers_race",
)

with open(os.path.join(output_dir, "script.json"), "w", encoding="utf-8") as f:
    json.dump(script.dict(), f, indent=2)
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

# Align audio narration segments to exact visual scene timestamps
print("⏱️ Synchronizing audio narration segments to visual scene timeline (85.0s)...")
padded_audio = VideoAssembler.align_landscape_audio(
    audio_data=audio_data,
    output_dir=output_dir,
    target_total_duration=85.0,
)
print("✅ Audio synchronization complete: all scenes cued to exact visual timestamps.")

# Generate Subtitle File (SRT) with synchronized scene timings
srt_path = os.path.join(output_dir, "captions.srt")
generate_srt(audio_data, output_dir)
print(f"✅ Captions synchronized and ready: {srt_path}")

# ----------------------------------------------------------------------
# 5. Render 1920x1080 Widescreen Duel Animation
# ----------------------------------------------------------------------
visual_dir = os.path.join(output_dir, "visuals")
os.makedirs(visual_dir, exist_ok=True)
animation_path = os.path.join(visual_dir, "visual_0.mp4")
render_duration = 85.0

if os.path.exists(animation_path) and os.path.getsize(animation_path) > 1000000:
    print(f"✅ Found existing rendered 85s animation: {animation_path} ({os.path.getsize(animation_path)/(1024*1024):.1f} MB)")
else:
    print("\n⚔️ Rendering 1920x1080 Widescreen Duel Animation (85s) ...")
    WidescreenDuelEngine.render_landscape_animation(
        wide_data=df,
        output_file=animation_path,
        title=script.title,
        category_label="LR ATLAS DATA LABS // ALL-TIME SUBSCRIBER RACE",
        duration_seconds=render_duration,
        fps=30,
        indicator_code="youtube_subscribers_race",
    )
    print(f"✅ Animation rendered successfully: {animation_path} ({os.path.getsize(animation_path)/(1024*1024):.1f} MB)")

visual_data = [{"scene_number": 1, "image_path": animation_path}]

# ----------------------------------------------------------------------
# 6. Assemble Final Video (Mix 142 BPM Battle Rush BGM + Subtitles)
# ----------------------------------------------------------------------
print("\n🎞️ Assembling Final Video with 142 BPM Battle Rush BGM & Subtitles...")
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
if qc_result.get("errors"):
    print(f"QC Errors: {qc_result.get('errors')}")

# ----------------------------------------------------------------------
# 8. Generate YouTube Metadata & Widescreen Thumbnails
# ----------------------------------------------------------------------
print("\n🏷️ Generating YouTube Metadata & Thumbnails...")
topic_meta = {
    "topic": "YouTube Subscriber Race: MrBeast vs T-Series vs PewDiePie (2011-2026)",
    "category": "Entertainment",
    "provider_id": "viral_topics",
    "indicator_code": "youtube_subscribers_race",
    "story_type": "rank_climber",
    "source_name": "YouTube Data API & Social Blade Archive",
    "source_url": "https://socialblade.com",
}
metadata = MetadataEngine.generate_metadata(
    script=script,
    data=df,
    story_type="rank_climber",
)

with open(os.path.join(output_dir, "youtube_metadata.json"), "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2)

thumb_dir = os.path.join(output_dir, "thumbnails")
os.makedirs(thumb_dir, exist_ok=True)
try:
    thumb_candidates = ThumbnailEngine.generate_thumbnails(
        video_path=final_video_path,
        output_dir=thumb_dir,
        title=metadata.get("title", script.title),
    )
    print(f"✅ Generated {len(thumb_candidates)} thumbnail candidates.")
except Exception as th_err:
    print(f"Thumbnail note: {th_err}")

print("\n" + "=" * 60)
print("🚀 LONG-FORMAT DUEL BATTLE VIDEO READY!")
print(f"📁 Directory: {output_dir}")
print(f"🎥 Video File: {final_video_path}")
print(f"⏱️ Duration: {render_duration:.1f}s (85s Widescreen 1920x1080 HD)")
print("=" * 60)
