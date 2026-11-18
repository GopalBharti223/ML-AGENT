"""Build, Render and Upload the 85-Second 16:9 Widescreen Duel Video.
Topic: The YouTube Throne: PewDiePie vs T-Series vs MrBeast (2011-2026).
Widescreen 1920x1080 Landscape, Dual Scoreboard, Battle Rush BGM, Auto-Upload.
"""

import os
import sys
import subprocess
from build_long_format_video import *
from app.youtube.uploader import upload_video

# 1. Run upload pipeline
print("\n" + "=" * 60)
print("🚀 LAUNCHING YOUTUBE UPLOAD FOR WIDESCREEN LONG-FORMAT VIDEO...")
print("=" * 60)

with open(os.path.join(output_dir, "youtube_metadata.json"), "r", encoding="utf-8") as f:
    yt_meta = json.load(f)

# Choose best thumbnail
chosen_thumb = None
if os.path.exists(thumb_dir):
    thumbs = [os.path.join(thumb_dir, f) for f in os.listdir(thumb_dir) if f.endswith((".jpg", ".png"))]
    if thumbs:
        chosen_thumb = thumbs[0]
        print(f"🖼️ Selected Widescreen Thumbnail: {chosen_thumb}")

upload_result = upload_video(
    video_path=final_video_path,
    metadata=yt_meta,
    thumbnail_path=chosen_thumb,
    privacy_status="public",
)

vid = upload_result.get("video_id")
print("\n" + "=" * 60)
print(f"🎉 85-SECOND WIDESCREEN LONG VIDEO IS LIVE!")
print(f"🆔 Video ID: {vid}")
print(f"🔗 Video URL: https://youtu.be/{vid}")
print("=" * 60)
