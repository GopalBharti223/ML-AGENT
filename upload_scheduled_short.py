"""Upload the rendered NVIDIA vs Apple Trillion Dollar Short as SCHEDULED for tomorrow 6:30 PM IST."""

import os
import sys
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import settings
settings.VIDEO_FORMAT = "portrait"
from app.youtube.uploader import upload_video

# Output directory for latest market cap short
video_path = r"output\market_cap_short\20261031_222025\final_video.mp4"
metadata_path = r"output\market_cap_short\20261031_222025\youtube_metadata.json"
thumb_path = r"output\market_cap_short\20261031_222025\thumbnails\short_preview_2024_nvidia_overtake.jpg"

# Tomorrow Nov 1, 2026 at 6:30 PM IST = 13:00 UTC
# RFC 3339 format required by YouTube Data API v3
publish_at_iso = "2026-11-01T13:00:00Z"

with open(metadata_path, "r", encoding="utf-8") as f:
    metadata = json.load(f)

print(f"🎬 Uploading YouTube Short: {video_path}")
print(f"📌 Title: {metadata.get('title')}")
print(f"⏰ Schedule Time: 01 November 2026 at 6:30 PM IST ({publish_at_iso})")
print(f"🔒 Status: SCHEDULED (Private until release)")

upload_result = upload_video(
    video_path=video_path,
    metadata=metadata,
    thumbnail_path=thumb_path,
    privacy_status="private",
    publish_at=publish_at_iso,
)

video_id = upload_result.get("video_id")
print("\n" + "=" * 60)
print(f"🎉 YOUTUBE SHORT SCHEDULED SUCCESSFULLY!")
print(f"🆔 Video ID: {video_id}")
print(f"🔗 Short URL: https://youtube.com/shorts/{video_id}")
print(f"⏰ Going LIVE at: 01 Nov 2026, 6:30 PM IST")
print("=" * 60)

with open(r"output\market_cap_short\20261031_222025\upload_result.json", "w", encoding="utf-8") as f:
    json.dump({
        "video_id": video_id,
        "short_url": f"https://youtube.com/shorts/{video_id}",
        "status": "scheduled",
        "publish_at": publish_at_iso,
        "scheduled_ist": "01 Nov 2026, 6:30 PM IST"
    }, f, indent=2)
