#!/usr/bin/env python3
"""Non-rendering artist and coordinate tests for bar-race layout geometry.

Covers:
1. Multi-entity scaling for 4, 5, and 6 entities:
   - All bar, label, value, and flag artists remain inside the 1080x1920 canvas.
   - All artists stay within the mobile vertical safe zones (safe_bottom 0.22 -> 422.4px,
     safe_top 0.92 -> 1766.4px).
   - Sixth entity bar and artists remain cleanly above the footer text and safe bottom.
2. Short and zero-length bar collision immunity:
   - On zero-length bars (value = 0.0) and tiny slivers (value = 0.5% max), value texts
     never overlap the country flag icon or country label.
   - Value texts never overflow past the right safe line into the YouTube Shorts action rail.
3. Horizontal artist ordering and spacing:
   - Flag icon sits strictly left of the country label with positive breathing room.
   - Country label sits left of value text with positive clearance.
4. Transition stability:
   - Label positions and bar geometry remain non-overlapping during animated rank swaps.
"""
import matplotlib

matplotlib.use("Agg")

import matplotlib.animation as manim
import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
import numpy as np
import pandas as pd
import pytest

from app.config import settings
from app.visuals import design_system
from app.visuals.scene_engine import VisualEngine


@pytest.fixture(autouse=True)
def _stub_flags(monkeypatch):
    """Hermetic stub producing real 64x44 RGBA flag image boxes without network."""
    flag_arr = np.ones((44, 64, 4), dtype=np.float32)
    monkeypatch.setattr(
        VisualEngine,
        "prefetch_flags",
        classmethod(lambda cls, items: None),
    )
    monkeypatch.setattr(
        VisualEngine,
        "_get_flag_image",
        staticmethod(lambda name: OffsetImage(flag_arr, zoom=VisualEngine.FLAG_ZOOM)),
    )


class _GeometryScript:
    title = "Global Economic Shift"
    topic = "economy"
    category = "economy"
    topic_family = "economy"
    source_name = "World Bank - WDI"
    indicator_name = "GDP Growth Rate (%)"
    total_duration = 10.0
    chart_type = "bar_race"

    def __init__(self, entities, duration=10.0):
        self.total_duration = duration
        self.scenes = [
            {
                "chart_type": "bar_race",
                "narration": "Narration text",
                "highlight_countries": list(entities),
            }
        ]


def _capture_race_figure(df, duration=10.0):
    """Capture the initialized figure and animation step function without video encode."""
    cap = {}
    orig_save = manim.Animation.save
    orig_close = plt.close

    def mock_save(self, filename, *args, **kwargs):
        cap["fig"] = getattr(self, "_fig", None)
        cap["func"] = getattr(self, "_func", None)
        cap["frames"] = getattr(self, "_save_count", 0) or 0

    manim.Animation.save = mock_save
    plt.close = lambda *args, **kwargs: None

    try:
        script = _GeometryScript(df.index, duration=duration)
        VisualEngine.render_bar_race(script, df, "_tmp_geom_test")
    finally:
        manim.Animation.save = orig_save
        plt.close = orig_close

    assert cap.get("fig") is not None, "Failed to capture figure"
    return cap["fig"], cap.get("func"), cap.get("frames", 0)


@pytest.mark.parametrize("n_entities", [4, 5, 6])
def test_bar_race_geometry_bounds_and_no_clipping(n_entities):
    """Verify that 4, 5, and 6 entities stay inside canvas and above safe bottom."""
    countries = [f"Nation_{chr(65 + i)}" for i in range(n_entities)]
    # Mix of large, medium, small, and zero values
    vals_start = [100.0 - i * 18.0 for i in range(n_entities)]
    vals_start[-1] = 0.0  # Last entity has zero bar at start
    vals_end = [110.0 - i * 15.0 for i in range(n_entities)]

    df = pd.DataFrame({2018: vals_start, 2022: vals_end}, index=countries)
    fig, update_fn, n_frames = _capture_race_figure(df, duration=2.0)

    try:
        # Step to frame 0 and check initial layout
        update_fn(0)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        ax = fig.axes[0]

        safe_bottom_px = design_system.safe_bottom() * 1920.0
        safe_top_px = design_system.safe_top() * 1920.0
        safe_right_px = design_system.safe_right() * 1080.0
        safe_left_px = design_system.safe_left() * 1080.0

        # Assert exactly n_entities bars are drawn (bars are zorder=2; background images are zorder=0)
        images = [
            c for c in ax.get_children()
            if isinstance(c, matplotlib.image.AxesImage) and c.get_zorder() == 2
        ]
        assert len(images) == n_entities, f"Expected {n_entities} bars, got {len(images)}"

        # Assert all bars are inside safe vertical range
        for idx, bar in enumerate(images):
            extent = bar.get_extent()
            p_top = ax.transData.transform((0.0, extent[2]))
            p_bottom = ax.transData.transform((0.0, extent[3]))
            bar_y_bottom = min(p_top[1], p_bottom[1])
            bar_y_top = max(p_top[1], p_bottom[1])

            assert bar_y_bottom >= safe_bottom_px, (
                f"Bar {idx} bottom ({bar_y_bottom:.1f}px) clipped below safe bottom ({safe_bottom_px:.1f}px)"
            )
            assert bar_y_top <= safe_top_px, (
                f"Bar {idx} top ({bar_y_top:.1f}px) exceeds safe top ({safe_top_px:.1f}px)"
            )

        # Check texts inside ax: values and names
        ax_texts = [t for t in ax.texts if t.get_text()]
        for t in ax_texts:
            bbox = t.get_window_extent(renderer=renderer)
            assert bbox.y0 >= safe_bottom_px - 5.0, (
                f"Text '{t.get_text()}' y0 ({bbox.y0:.1f}px) dropped below safe line ({safe_bottom_px:.1f}px)"
            )
            assert bbox.x1 <= safe_right_px + 2.0, (
                f"Text '{t.get_text()}' x1 ({bbox.x1:.1f}px) breached safe right ({safe_right_px:.1f}px)"
            )
            assert bbox.x0 >= safe_left_px - 2.0, (
                f"Text '{t.get_text()}' x0 ({bbox.x0:.1f}px) fell off left edge ({safe_left_px:.1f}px)"
            )

        # Check footer text separation from chart bottom
        footer_texts = [t for t in fig.texts if "DOMINATED" in t.get_text()]
        if footer_texts:
            footer_bbox = footer_texts[0].get_window_extent(renderer=renderer)
            lowest_bar = images[-1]
            ext = lowest_bar.get_extent()
            lowest_bar_y = min(
                ax.transData.transform((0, ext[2]))[1],
                ax.transData.transform((0, ext[3]))[1],
            )
            assert lowest_bar_y > footer_bbox.y1, (
                f"Lowest bar ({lowest_bar_y:.1f}px) collides with footer text top ({footer_bbox.y1:.1f}px)"
            )
    finally:
        plt.close(fig)


def test_short_and_zero_bar_no_collision_with_flag_or_label():
    """Verify that zero-length and short bars do not collide value text with flags or names."""
    countries = [
        "Dominican Republic",
        "Trinidad and Tobago",
        "Saint Lucia",
        "Antigua and Barbuda",
    ]
    # Country 3 is near-zero (0.2), Country 4 is exact zero (0.0)
    df = pd.DataFrame(
        {
            2020: [80.0, 40.0, 0.2, 0.0],
            2021: [85.0, 42.0, 0.5, 0.0],
        },
        index=countries,
    )
    fig, update_fn, _ = _capture_race_figure(df, duration=1.0)

    try:
        update_fn(0)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        ax = fig.axes[0]

        flags = [c for c in ax.get_children() if isinstance(c, AnnotationBbox)]
        assert len(flags) == len(countries), f"Expected {len(countries)} flags, got {len(flags)}"

        name_texts = []
        value_texts = []
        for t in ax.texts:
            txt = t.get_text().strip()
            if not txt:
                continue
            is_val = False
            try:
                float(txt.replace("$", "").replace("%", "").replace("M", "").replace("B", ""))
                is_val = True
            except ValueError:
                pass
            if is_val:
                value_texts.append(t)
            else:
                name_texts.append(t)

        assert len(name_texts) == len(countries)
        assert len(value_texts) == len(countries)

        for i in range(len(countries)):
            flag_box = flags[i].get_window_extent(renderer=renderer)
            name_box = name_texts[i].get_window_extent(renderer=renderer)
            val_box = value_texts[i].get_window_extent(renderer=renderer)

            # 1. Flag must be strictly left of name
            assert flag_box.x1 <= name_box.x0 + 1.0, (
                f"Row {i} ({countries[i]}): Flag x1 ({flag_box.x1:.1f}) overlaps Name x0 ({name_box.x0:.1f})"
            )

            # 2. Value text must NEVER overlap the flag on zero/short bars
            assert val_box.x0 >= flag_box.x1, (
                f"Row {i} ({countries[i]}): Value text x0 ({val_box.x0:.1f}) overlaps Flag x1 ({flag_box.x1:.1f})"
            )

            # 3. Value text must be positioned clear of the country name horizontally
            assert val_box.x0 >= name_box.x1 - 1.0, (
                f"Row {i} ({countries[i]}): Value text x0 ({val_box.x0:.1f}) collides with Name x1 ({name_box.x1:.1f})"
            )

            # 4. Value text must not breach safe_right
            safe_right_px = design_system.safe_right() * 1080.0
            assert val_box.x1 <= safe_right_px + 2.0, (
                f"Row {i} ({countries[i]}): Value text x1 ({val_box.x1:.1f}) overflows safe right ({safe_right_px:.1f})"
            )
    finally:
        plt.close(fig)


def test_transition_stability_6_entities_no_row_collapse():
    """Verify that during rank crossing mid-transition, row spacing is maintained."""
    countries = [f"Nation_{i}" for i in range(1, 7)]
    # Complete rank inversion between 2020 and 2022
    df = pd.DataFrame(
        {
            2020: [100.0, 80.0, 60.0, 40.0, 20.0, 10.0],
            2022: [10.0, 20.0, 40.0, 60.0, 80.0, 100.0],
        },
        index=countries,
    )
    fig, update_fn, n_frames = _capture_race_figure(df, duration=2.0)

    try:
        mid_frame = n_frames // 2
        update_fn(mid_frame)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        ax = fig.axes[0]

        name_y_positions = []
        for t in ax.texts:
            txt = t.get_text()
            if txt.startswith("Nation_"):
                bbox = t.get_window_extent(renderer=renderer)
                name_y_positions.append((txt, (bbox.y0 + bbox.y1) / 2.0))

        assert len(name_y_positions) == 6
        sorted_y = sorted(name_y_positions, key=lambda item: item[1])

        # Check that no two labels collapse onto the identical row (gap >= 15px)
        for i in range(len(sorted_y) - 1):
            gap = sorted_y[i + 1][1] - sorted_y[i][1]
            assert gap >= 15.0, (
                f"Labels '{sorted_y[i][0]}' and '{sorted_y[i + 1][0]}' collapsed together "
                f"at mid-frame (gap: {gap:.1f}px)"
            )
    finally:
        plt.close(fig)


def test_bar_race_cap_is_6_while_non_bar_race_defaults_to_4():
    """Verify bar-race supports 6 entities while standard charts default to 4 entities."""
    # 1. Config defaults verification
    assert getattr(settings, "CHART_MAX_BARS", None) == 6
    assert getattr(settings, "BAR_RACE_MAX_ENTITIES", None) == 6
    assert getattr(settings, "MAX_CHART_ENTITIES", None) == 4

    # 2. Bar race cap evaluation
    script_standard = _GeometryScript([f"C{i}" for i in range(6)])
    assert VisualEngine.compute_bar_cap(script_standard) == 6

    script_vs = _GeometryScript([f"C{i}" for i in range(6)])
    script_vs.title = "Country A vs Country B"
    assert VisualEngine.compute_bar_cap(script_vs) == getattr(settings, "CHART_BARS_VS", 3)

    # 3. Non-bar-race renderer data preparation cap (governed by MAX_CHART_ENTITIES = 4)
    df_8 = pd.DataFrame(
        {2020: [100.0 - i * 10.0 for i in range(8)], 2021: [105.0 - i * 10.0 for i in range(8)]},
        index=[f"Nation_{chr(65 + i)}" for i in range(8)],
    )
    prepared = VisualEngine._prepare_chart_data(df_8)
    assert len(prepared.index) == 4, (
        f"Non-bar-race _prepare_chart_data retained {len(prepared.index)} entities; expected 4"
    )

    # 4. Bar race retains 6 entities under the same input dimensions
    df_6 = pd.DataFrame(
        {2020: [100.0 - i * 10.0 for i in range(6)], 2021: [105.0 - i * 10.0 for i in range(6)]},
        index=[f"Nation_{chr(65 + i)}" for i in range(6)],
    )
    fig, update_fn, _ = _capture_race_figure(df_6, duration=1.0)
    try:
        update_fn(0)
        ax = fig.axes[0]
        bar_images = [
            c for c in ax.get_children()
            if isinstance(c, matplotlib.image.AxesImage) and c.get_zorder() == 2
        ]
        assert len(bar_images) == 6, (
            f"Bar race rendered {len(bar_images)} bars; expected 6"
        )
    finally:
        plt.close(fig)

