"""Unit tests for Widescreen 16:9 Landscape Long-Format Engine and Duel Mode."""

import os
import pytest
import pandas as pd
from app.config import settings
from app.qc.final_qc import FinalQC
from app.youtube.metadata import MetadataEngine
from app.visuals.widescreen_duel import WidescreenDuelEngine, VIRAL_LORE_HEADLINES


def test_widescreen_settings_toggle():
    """Setting VIDEO_FORMAT toggles dimensions cleanly."""
    settings.VIDEO_FORMAT = "shorts"
    assert not settings.is_landscape
    assert settings.canvas_width == 1080
    assert settings.canvas_height == 1920

    settings.VIDEO_FORMAT = "landscape"
    assert settings.is_landscape
    assert settings.canvas_width == 1920
    assert settings.canvas_height == 1080

    # Reset
    settings.VIDEO_FORMAT = "shorts"


def test_viral_lore_headlines_exist():
    """Curated viral lore headlines are populated for top topics."""
    assert "youtube_subscribers_race" in VIRAL_LORE_HEADLINES
    assert "gta_sales" in VIRAL_LORE_HEADLINES
    assert "top_billionaires_net_worth" in VIRAL_LORE_HEADLINES
    assert len(VIRAL_LORE_HEADLINES["youtube_subscribers_race"]) >= 4


def test_metadata_engine_landscape_hashtags():
    """MetadataEngine omits #Shorts in landscape mode."""
    dummy_df = pd.DataFrame({2024: [10.0, 20.0]}, index=["Minecraft", "GTA"])

    settings.VIDEO_FORMAT = "landscape"
    tags = MetadataEngine._build_hashtags(None, dummy_df, 2024, ["#gaming", "#videogames"])
    assert "#Shorts" not in tags
    assert "#DataViz" in tags

    settings.VIDEO_FORMAT = "shorts"
    tags_shorts = MetadataEngine._build_hashtags(None, dummy_df, 2024, ["#gaming", "#videogames"])
    assert "#Shorts" in tags_shorts


def test_final_qc_landscape_resolution_pass(tmp_path):
    """FinalQC accepts 1920x1080 when in landscape mode."""
    settings.VIDEO_FORMAT = "landscape"
    dummy_video = tmp_path / "test_video.mp4"
    dummy_video.write_bytes(b"dummy")

    fake_probe = {
        "format": {"duration": "120.0"},
        "streams": [
            {"codec_type": "video", "width": 1920, "height": 1080},
            {"codec_type": "audio"}
        ]
    }
    orig_probe = FinalQC._probe_video
    FinalQC._probe_video = lambda path: fake_probe
    try:
        res = FinalQC.check_video(str(dummy_video))
        assert res["passed"] is True, f"Errors: {res.get('errors')}"
        assert res["width"] == 1920
        assert res["height"] == 1080
    finally:
        FinalQC._probe_video = orig_probe
        settings.VIDEO_FORMAT = "shorts"


def test_widescreen_duel_render_with_outro(tmp_path):
    """WidescreenDuelEngine renders MP4 with always-on HUD and outro card."""
    df = pd.DataFrame(
        {
            2011: [0.1, 0.2, 5.2],
            2018: [80.0, 78.0, 10.0],
            2024: [111.0, 278.0, 17.0],
            2026: [111.0, 305.0, 19.0],
        },
        index=["PewDiePie", "T-Series", "RayWilliamJohnson"]
    )
    out_file = str(tmp_path / "test_duel.mp4")
    res = WidescreenDuelEngine.render_landscape_animation(
        wide_data=df,
        output_file=out_file,
        title="Epic Subscriber War Test",
        duration_seconds=5.0,
        fps=15,
        indicator_code="youtube_subscribers_race"
    )
    assert os.path.exists(res)
    assert os.path.getsize(res) > 10000
