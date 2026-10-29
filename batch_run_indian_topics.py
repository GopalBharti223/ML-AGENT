"""
Batch Video Generator and YouTube Uploader for Indian-focused Data Shorts
Runs the full pipeline end-to-end for multiple chart types in PRIVATE mode.
"""
import os
import sys
import json
import time
import subprocess
from pathlib import Path

# Force UTF-8 output
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TASKS = [
    {
        "chart_type": "bar_race",
        "topic": "India vs China GDP",
        "description": "Bar Race: India vs China GDP Comparison"
    },
    {
        "chart_type": "line",
        "topic": "India vs UK economy",
        "description": "Line Chart: India vs UK Economic Overtake"
    },
    {
        "chart_type": "top5_change",
        "topic": "India population",
        "description": "Top 5 Change: India Population Standing"
    },
    {
        "chart_type": "area",
        "topic": "India renewable energy",
        "description": "Area Chart: India Energy Transition"
    },
    {
        "chart_type": "slope",
        "topic": "India vs China military",
        "description": "Slope Chart: India vs China Military Expenditure"
    }
]

def get_latest_upload_info():
    """Find the latest youtube_metadata.json in output/"""
    output_dir = Path("output")
    if not output_dir.exists():
        return None
    meta_files = list(output_dir.glob("**/youtube_metadata.json"))
    if not meta_files:
        return None
    meta_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    try:
        with open(meta_files[0], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def main():
    print("=" * 70)
    print("🚀 BATCH VIDEO GENERATION & UPLOAD (PRIVATE MODE)")
    print(f"Total Graph Types to Generate: {len(TASKS)}")
    print("=" * 70)

    results = []
    python_exe = sys.executable

    for idx, task in enumerate(TASKS, 1):
        chart_type = task["chart_type"]
        topic = task["topic"]
        desc = task["description"]

        print("\n" + "#" * 70)
        print(f"[{idx}/{len(TASKS)}] Generating: {desc}")
        print(f"Graph Type: {chart_type.upper()} | Topic: '{topic}'")
        print("#" * 70 + "\n")

        env = os.environ.copy()
        env["RUN_MANUAL_TOPIC"] = topic
        env["FORCE_CHART_TYPE"] = chart_type
        env["YOUTUBE_PRIVACY_STATUS"] = "private"
        env["PYTHONIOENCODING"] = "utf-8"

        start_time = time.time()
        process = subprocess.Popen(
            [python_exe, "run.py"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1
        )

        video_id = None
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            if "Video ID:" in line:
                parts = line.strip().split("Video ID:")
                if len(parts) > 1:
                    video_id = parts[1].strip()
            elif "https://www.youtube.com/watch?v=" in line:
                parts = line.strip().split("https://www.youtube.com/watch?v=")
                if len(parts) > 1:
                    video_id = parts[1].strip().split()[0]

        process.wait()
        elapsed = time.time() - start_time

        # Check metadata file if video_id not caught in stdout
        if not video_id:
            info = get_latest_upload_info()
            if info:
                video_id = info.get("video_id")

        success = (process.returncode == 0) and (video_id is not None)
        status_str = "SUCCESS" if success else ("FAILED (Exit code %d)" % process.returncode)

        results.append({
            "index": idx,
            "chart_type": chart_type,
            "topic": topic,
            "description": desc,
            "status": status_str,
            "video_id": video_id,
            "youtube_url": f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
            "elapsed_seconds": round(elapsed, 1)
        })

        print("\n" + "-" * 70)
        if video_id:
            print(f"✅ Video Uploaded (PRIVATE): https://www.youtube.com/watch?v={video_id}")
        else:
            print(f"⚠️ Task finished with status: {status_str}")
        print(f"Elapsed Time: {elapsed:.1f}s")
        print("-" * 70)

        # Brief cooldown between YouTube uploads
        if idx < len(TASKS):
            print("⏳ Cooldown 5 seconds before next task...")
            time.sleep(5)

    print("\n" + "=" * 70)
    print("📊 BATCH GENERATION SUMMARY")
    print("=" * 70)
    for r in results:
        v_url = r['youtube_url'] or 'N/A'
        print(f"• [{r['chart_type'].upper()}] {r['topic']} -> {r['status']}")
        if r['youtube_url']:
            print(f"  Link (Private): {r['youtube_url']} ({r['elapsed_seconds']}s)")
    print("=" * 70)

if __name__ == "__main__":
    main()
