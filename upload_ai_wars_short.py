"""Upload the rendered 35-second AI Wars Short to YouTube as UNLISTED."""

import os
import sys
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import settings
settings.VIDEO_FORMAT = "portrait"
from app.youtube.uploader import upload_video

video_path = r"output\ai_wars_short\20261029_163158\final_video.mp4"
metadata_path = r"output\ai_wars_short\20261029_163158\youtube_metadata.json"
thumb_path = r"output\ai_wars_short\20261029_163158\thumbnails\short_preview_mid_battle.jpg"

with open(metadata_path, "r", encoding="utf-8") as f:
    metadata = json.load(f)

print(f"🎬 Uploading YouTube Short: {video_path}")
print(f"📌 Title: {metadata.get('title')}")
print(f"🔒 Privacy: UNLISTED")

upload_result = upload_video(
    video_path=video_path,
    metadata=metadata,
    thumbnail_path=thumb_path,
    privacy_status="unlisted",
)

video_id = upload_result.get("video_id")
print("\n" + "=" * 60)
print(f"🎉 YOUTUBE SHORT UPLOAD SUCCESSFUL!")
print(f"🔗 Short URL: https://youtube.com/shorts/{video_id}")
print(f"🔒 Privacy Status: UNLISTED")
print("=" * 60)

with open(r"output\ai_wars_short\20261029_163158\upload_result.json", "w", encoding="utf-8") as f:
    json.dump({"video_id": video_id, "short_url": f"https://youtube.com/shorts/{video_id}", "status": "unlisted"}, f, indent=2)
