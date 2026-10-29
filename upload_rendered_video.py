"""Upload already-rendered 1920x1080 landscape video as unlisted."""

import os
import sys
import json

# Force UTF-8 stream
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import settings
settings.VIDEO_FORMAT = "landscape"
from app.youtube.uploader import upload_video
from app.database import db

dir_path = "output/test_run/20261029_001410"
video_path = os.path.join(dir_path, "final_video.mp4")
metadata_path = os.path.join(dir_path, "youtube_metadata.json")
script_path = os.path.join(dir_path, "script.json")

with open(metadata_path, "r", encoding="utf-8") as f:
    metadata = json.load(f)

with open(script_path, "r", encoding="utf-8") as f:
    script_data = json.load(f)

thumb_dir = os.path.join(dir_path, "thumbnails")
thumb_path = os.path.join(thumb_dir, "thumbnail_13_74s_titled_bottom.jpg")
if not os.path.exists(thumb_path) and os.path.exists(thumb_dir):
    candidates = [os.path.join(thumb_dir, f) for f in os.listdir(thumb_dir) if f.endswith(".jpg")]
    thumb_path = candidates[0] if candidates else None

print(f"🎬 Ready to upload: {video_path}")
print(f"📌 Title: {metadata.get('title')}")
print(f"🔒 Privacy: UNLISTED")
print("Authenticating with YouTube API...")

upload_result = upload_video(
    video_path=video_path,
    metadata=metadata,
    thumbnail_path=thumb_path,
    privacy_status="unlisted"
)

video_id = upload_result.get("video_id")
print("\n" + "=" * 60)
print(f"🎉 UPLOAD SUCCESSFUL!")
print(f"🔗 Video URL: https://youtu.be/{video_id}")
print(f"🔒 Privacy Status: UNLISTED")
print("=" * 60)

try:
    db.save_video_record(
        date=script_data.get("generated_at", ""),
        topic=metadata.get("title", ""),
        category=metadata.get("category", "Education"),
        title=metadata.get("title", ""),
        video_path=video_path,
        youtube_id=video_id,
        qc_score=100,
        upload_status="uploaded",
        indicator_code="youtube_subscribers_race",
        story_type="rank_climber",
        start_year=2018,
        end_year=2025,
        voice="en-US-AriaNeural",
        title_format="question",
        hook_style="stakes",
        chart_type="widescreen_duel",
    )
    print("✅ Recorded in database.")
except Exception as exc:
    print(f"Database note: {exc}")
