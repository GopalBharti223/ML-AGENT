"""Create and upload a 20-second Xbox vs PlayStation gaming short to YouTube."""

import os
import sys
import subprocess
import json
import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from app.config import settings
settings.VIDEO_FORMAT = "portrait"

from app.youtube.uploader import upload_video

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
base_dir = os.path.join("output", "gaming_vs_console_20s")
subfolders = [f for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f))]
if not subfolders:
    print("No output subfolder found in", base_dir)
    sys.exit(1)
latest = sorted(subfolders)[-1]
output_dir = os.path.join(base_dir, latest)
print(f"Using output folder: {output_dir}")

# ---------------------------------------------------------------------------
# 1. Convert static PNG to a 20s video
# ---------------------------------------------------------------------------
image_path = os.path.join(output_dir, "gaming_short.png")
if not os.path.exists(image_path):
    print(f"Image not found at {image_path}")
    sys.exit(1)

video_path = os.path.join(output_dir, "final_video.mp4")

ffmpeg_cmd = [
    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
    "-loop", "1", "-i", image_path,
    "-c:v", "libx264", "-t", "20",
    "-pix_fmt", "yuv420p",
    "-vf", "scale=1080:1920",
    video_path
]
print("Generating video with ffmpeg...")
subprocess.run(ffmpeg_cmd, check=True)
print(f"Video created: {video_path}")

# ---------------------------------------------------------------------------
# 2. Add background music (optional)
# ---------------------------------------------------------------------------
music_src = os.path.join("assets", "audio", "battle_rush.wav")
final_video_path = video_path

if os.path.exists(music_src):
    mixed_path = os.path.join(output_dir, "final_video_with_audio.mp4")
    mix_cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", video_path, "-i", music_src,
        "-filter_complex", "[1:a]volume=0.12[a1]",
        "-map", "0:v", "-map", "[a1]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        mixed_path
    ]
    print("Adding background music...")
    subprocess.run(mix_cmd, check=True)
    final_video_path = mixed_path
    print(f"Video with audio saved: {final_video_path}")
else:
    print("No background music found - uploading silent video.")

# ---------------------------------------------------------------------------
# 3. Load metadata
# ---------------------------------------------------------------------------
metadata_path = os.path.join(output_dir, "youtube_metadata.json")
if not os.path.exists(metadata_path):
    metadata_path = os.path.join("D:\\ML_AGENT", "gaming_short_metadata.json")
    if not os.path.exists(metadata_path):
        print("Metadata JSON not found.")
        sys.exit(1)

with open(metadata_path, "r", encoding="utf-8") as f:
    metadata = json.load(f)
print("Loaded metadata.")

# ---------------------------------------------------------------------------
# 4. Upload to YouTube as PRIVATE
# ---------------------------------------------------------------------------
print("=" * 60)
print(f"Ready to upload: {final_video_path}")
print(f"Title: {metadata.get('title')}")
print("Privacy: private")
print("=" * 60)

upload_result = upload_video(
    video_path=final_video_path,
    metadata=metadata,
    thumbnail_path=None,
    privacy_status="private",
)

video_id = upload_result.get("video_id")
print("\n" + "=" * 60)
print("YOUTUBE SHORT UPLOADED SUCCESSFULLY!")
print(f"Video ID: {video_id}")
print(f"Short URL: https://youtube.com/shorts/{video_id}")
print("=" * 60)

result_path = os.path.join(output_dir, "upload_result.json")
with open(result_path, "w", encoding="utf-8") as f:
    json.dump({
        "video_id": video_id,
        "short_url": f"https://youtube.com/shorts/{video_id}",
        "status": "private"
    }, f, indent=2)
print(f"Upload result saved to {result_path}")
