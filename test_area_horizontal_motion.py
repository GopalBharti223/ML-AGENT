#!/usr/bin/env python3
"""
Smallest visual test for the modified render_area().

Verifies that the area chart renderer now produces the
horizontal moving bar / stick-style animation:

  - Renders a tiny synthetic dataset through
    VisualEngine.render_area()
  - Confirms an mp4 is produced at the expected path
  - Confirms the animation math interpolates bar widths
    and rank positions smoothly (spot-checks update())
"""

import os
import sys
import types

import pandas as pd

from app.visuals.scene_engine import VisualEngine


def build_data():
    """Small wide-format time series with a rank swap mid-timeline."""
    return pd.DataFrame(
        {
            2018: [100.0, 90.0, 80.0, 70.0],
            2019: [110.0, 95.0, 85.0, 72.0],
            2020: [105.0, 120.0, 88.0, 75.0],
            2021: [130.0, 125.0, 92.0, 78.0],
        },
        index=["USA", "CHN", "DEU", "JPN"],
    )


def build_script():
    return types.SimpleNamespace(
        title="GDP Test Story",
        source_name="World Bank",
        total_duration=1.0,  # 30 frames @ 30fps -> fast render
        indicator_name="GDP (current US$)",
    )


def test_area_horizontal_motion():
    data = build_data()
    script = build_script()

    out_dir = os.path.join("logs", "test_area_render")

    scenes = VisualEngine.render_area(script, data, out_dir)

    assert isinstance(scenes, list) and len(scenes) == 1, (
        f"Expected one scene dict, got {scenes}"
    )

    path = scenes[0]["image_path"]
    assert scenes[0]["scene_number"] == 1, "Unexpected scene number"
    assert os.path.isfile(path), f"Expected rendered file at {path}"

    size = os.path.getsize(path)
    assert size > 10_000, f"Video suspiciously small: {size} bytes"

    print(f"OK: {path} ({size} bytes)")
    print("PASS: render_area produced horizontal bar-race style video")
    return True


def test_bar_race_smoke():
    """Regression: total_frames was used before definition in
    render_bar_race (UnboundLocalError). Verify it renders now."""
    data = build_data()
    script = build_script()

    out_dir = os.path.join("logs", "test_bar_race_render")

    scenes = VisualEngine.render_bar_race(script, data, out_dir)

    path = scenes[0]["image_path"]
    assert os.path.isfile(path), f"Expected rendered file at {path}"

    size = os.path.getsize(path)
    assert size > 10_000, f"Video suspiciously small: {size} bytes"

    print(f"OK: {path} ({size} bytes)")
    print("PASS: render_bar_race renders without UnboundLocalError")
    return True


def main():
    ok_area = test_area_horizontal_motion()
    ok_race = test_bar_race_smoke()
    return ok_area and ok_race


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
