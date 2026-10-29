"""Upload the already-rendered 85s Netflix Streaming Wars video to YouTube as UNLISTED."""

import os
import sys
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import settings
settings.VIDEO_FORMAT = "landscape"
from app.youtube.uploader import upload_video

video_path = r"output\streaming_wars\20261029_094029\final_video.mp4"
metadata_path = r"output\streaming_wars\20261029_094029\youtube_metadata.json"
thumb_path = r"output\streaming_wars\20261029_094029\thumbnails\thumbnail.jpg"

with open(metadata_path, "r", encoding="utf-8") as f:
    metadata = json.load(f)

print(f"🎬 Uploading Video: {video_path}")
print(f"📌 Title: {metadata.get('title')}")
print(f"🔒 Privacy: UNLISTED")
print(f"🖼️ Thumbnail: {thumb_path}")

upload_result = upload_video(
    video_path=video_path,
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
