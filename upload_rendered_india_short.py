"""Quick script to authenticate and upload the already rendered 20s India vs UK GDP Short."""

import os
import sys
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from app.config import settings
settings.VIDEO_FORMAT = "portrait"

from app.youtube.uploader import upload_video

output_dir = r"output\india_gdp_v2_20s\20261106_135611"
video_path = os.path.join(output_dir, "final_video.mp4")
metadata_path = os.path.join(output_dir, "youtube_metadata.json")
thumb_path = os.path.join(output_dir, "thumbnails", "short_thumbnail.jpg")

if not os.path.exists(video_path):
    print(f"❌ Video not found at {video_path}")
    sys.exit(1)

with open(metadata_path, "r", encoding="utf-8") as f:
    metadata = json.load(f)

print("=" * 60)
print(f"🎬 Ready to upload: {video_path}")
print(f"📌 Title: {metadata.get('title')}")
print(f"🔒 Privacy Status: PRIVATE")
print("=" * 60)

upload_result = upload_video(
    video_path=video_path,
    metadata=metadata,
    thumbnail_path=thumb_path if os.path.exists(thumb_path) else None,
    privacy_status="private",
)

video_id = upload_result.get("video_id")
print("\n" + "=" * 60)
print(f"🎉 YOUTUBE SHORT UPLOADED SUCCESSFULLY AS PRIVATE!")
print(f"🆔 Video ID: {video_id}")
print(f"🔗 Short URL: https://youtube.com/shorts/{video_id}")
print("=" * 60)

with open(os.path.join(output_dir, "upload_result.json"), "w", encoding="utf-8") as f:
    json.dump({
        "video_id": video_id,
        "short_url": f"https://youtube.com/shorts/{video_id}",
        "status": "private"
    }, f, indent=2)

