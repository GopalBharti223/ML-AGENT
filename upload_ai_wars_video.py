"""Upload the rendered 85-second AI Wars video to YouTube as UNLISTED."""

import os
import sys
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import settings
settings.VIDEO_FORMAT = "landscape"
from app.youtube.uploader import upload_video

video_path = r"output\ai_wars\20261029_113826\final_video.mp4"
metadata_path = r"output\ai_wars\20261029_113826\youtube_metadata.json"
thumb_path = r"output\ai_wars\20261029_113826\thumbnails\preview_scene3_battle.jpg"

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

with open(r"output\ai_wars\20261029_113826\upload_result.json", "w", encoding="utf-8") as f:
    json.dump({"video_id": video_id, "video_url": f"https://youtu.be/{video_id}", "status": "unlisted"}, f, indent=2)
