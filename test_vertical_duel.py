"""Unit test and visual verification for VerticalDuelEngine (1080x1920 Shorts)."""

import os
import pytest
import pandas as pd
from app.visuals.vertical_duel import VerticalDuelEngine
from app.data.static.viral_datasets import VIRAL_INDICATORS

import sys
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def test_vertical_duel_render():
    """Verify VerticalDuelEngine renders a valid 1080x1920 MP4 animation."""
    ds = VIRAL_INDICATORS["ai_models_race"]
    years = ds["years"]
    df = pd.DataFrame(ds["data"], index=years).T
    df.columns = [int(c) for c in df.columns]

    out_file = os.path.join("output", "_test_vertical", "ai_shorts_test.mp4")
    os.makedirs(os.path.dirname(out_file), exist_ok=True)

    result_path = VerticalDuelEngine.render_portrait_animation(
        wide_data=df,
        output_file=out_file,
        title="ChatGPT vs Google Gemini: Who Wins?",
        duration_seconds=5.0,  # fast 5s test
        fps=30,
        indicator_code="ai_models_race"
    )

    assert os.path.exists(result_path)
    assert os.path.getsize(result_path) > 50000  # at least 50KB

    # Extract preview frame at 3.0s
    frame_path = os.path.join("output", "_test_vertical", "shorts_preview_3s.jpg")
    cmd = [
        "ffmpeg", "-y",
        "-ss", "3.0",
        "-i", result_path,
        "-vframes", "1",
        "-q:v", "2",
        frame_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert os.path.exists(frame_path)

if __name__ == "__main__":
    test_vertical_duel_render()
    print("[SUCCESS] VerticalDuelEngine test passed successfully!")

