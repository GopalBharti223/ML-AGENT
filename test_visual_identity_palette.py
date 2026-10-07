"""Visual identity regression tests (Part 1).

Pins the shared editorial identity every renderer draws from:

1. the CATEGORICAL palette contract (6-8 distinct, readable,
   gold-led) and its binding to MULTI_COLOR_PALETTE,
2. ``_get_categorical_color`` clamp semantics (slice order is
   pinned by test_pie_waffle.py),
3. the soft dark-navy title halo that replaced the heavy pure
   black ``withStroke`` outline,
4. atmosphere / line-depth helpers actually WIRED into the
   renderers -- they once existed as dead code that no renderer
   called, so the wiring itself is part of the contract.
"""
import os
import types

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

from app.visuals import design_system
from app.visuals.scene_engine import VisualEngine

SCENE_ENGINE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "app",
    "visuals",
    "scene_engine.py",
)


def _read_scene_source():
    with open(SCENE_ENGINE_PATH, encoding="utf-8") as handle:
        return handle.read()


def _rgb(hex_color):
    value = hex_color.lstrip("#")
    return tuple(
        int(value[index:index + 2], 16)
        for index in (0, 2, 4)
    )


# ----------------------------------------------------------
# Palette contract
# ----------------------------------------------------------

def test_categorical_palette_contract():
    palette = design_system.CATEGORICAL_PALETTE

    assert 6 <= len(palette) <= 8, palette
    assert len(set(palette)) == len(palette), (
        "palette colours must be distinct"
    )

    for color in palette:
        red, green, blue = _rgb(color)
        assert (red, green, blue) != (0, 0, 0)
        assert max(red, green, blue) >= 150, (
            f"{color} is too dark to read on the canvas"
        )


def test_hero_slot_is_brand_gold():
    """Slot 0 is the brand accent BY CONSTRUCTION, so the pie /
    waffle hero slice and the multi-colour bars can never drift
    apart."""

    assert (
        design_system.CATEGORICAL_PALETTE[0]
        == design_system.BRAND_GOLD
    )
    assert (
        VisualEngine.MULTI_COLOR_PALETTE[0]
        == design_system.BRAND_GOLD
    )


def test_multi_color_palette_is_the_shared_identity():
    assert (
        VisualEngine.MULTI_COLOR_PALETTE
        == design_system.CATEGORICAL_PALETTE
    )


# ----------------------------------------------------------
# Categorical colour selection (pie / waffle slice order)
# ----------------------------------------------------------

def test_categorical_color_follows_palette_with_clamp():
    palette = design_system.CATEGORICAL_PALETTE

    for index in range(len(palette)):
        assert (
            VisualEngine._get_categorical_color(index)
            == palette[index]
        )

    # Clamped, never wrapped.
    assert (
        VisualEngine._get_categorical_color(len(palette) + 3)
        == palette[-1]
    )
    assert VisualEngine._get_categorical_color(-2) == palette[0]


def test_categorical_color_empty_palette_falls_back_to_leader():
    saved = VisualEngine.MULTI_COLOR_PALETTE

    try:
        VisualEngine.MULTI_COLOR_PALETTE = []
        assert (
            VisualEngine._get_categorical_color(0)
            == VisualEngine.LEADER_COLOR
        )
    finally:
        VisualEngine.MULTI_COLOR_PALETTE = saved


# ----------------------------------------------------------
# Soft editorial halo instead of the heavy black outline
# ----------------------------------------------------------

def test_editorial_effects_are_soft_navy_not_black():
    effects = design_system.editorial_text_effects(linewidth=3.0)

    assert len(effects) == 1

    # matplotlib's withStroke stores its arguments on the
    # graphics-context dict it will apply at draw time.
    graphics_context = effects[0]._gc

    assert graphics_context["foreground"] == "#0B1220"
    assert graphics_context["foreground"] != "black"
    assert graphics_context["linewidth"] == 3.0
    # NO explicit alpha: withStroke would REPLACE the artist's
    # alpha with it and set_alpha(0) could no longer hide the
    # text (the live bug this test exists for).
    assert "alpha" not in graphics_context


def test_alpha_zero_fully_hides_stroked_text():
    """The exact bug found in live evidence: with an explicit
    stroke alpha the closing caption stayed visible at
    set_alpha(0) through the whole video."""

    fig = plt.figure(figsize=(4, 2), dpi=100)
    fig.patch.set_facecolor("#101A2C")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("#101A2C")
    ax.set_axis_off()

    text = ax.text(
        0.5, 0.5, "WHO DOMINATED?",
        ha="center", va="center",
        color="#E8C15A", fontsize=20, fontweight="bold",
    )
    text.set_path_effects(design_system.editorial_text_effects())
    text.set_alpha(0.0)

    fig.canvas.draw()
    buffer = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].astype(int)
    canvas = buffer[5, 5]
    changed = int(
        (np.abs(buffer - canvas).max(axis=2) > 40).sum()
    )
    plt.close(fig)

    assert changed == 0, (
        f"set_alpha(0) must hide the stroked text ({changed}px "
        "still drawn -- stroke alpha is overriding artist alpha)"
    )


def test_glow_stroke_is_preblended_and_carries_no_alpha():
    """The winner halo must NOT pass ``alpha=`` to withStroke --
    that replaces the artist alpha (the live caption bug).  Its
    20% opacity is baked into the colour over the canvas instead,
    so the halo is dim by construction."""

    effects = design_system._winner_effects("#D4AF37")
    graphics_context = effects[0]._gc

    assert "alpha" not in graphics_context

    highlight = np.array(
        mcolors.to_rgb(design_system.shade("#D4AF37", 0.45))
    )
    canvas = np.array(
        mcolors.to_rgb(design_system.CANVAS_COLOR)
    )
    expected = (
        highlight * design_system.GLOW_ALPHA
        + canvas * (1.0 - design_system.GLOW_ALPHA)
    )
    actual = np.array(
        mcolors.to_rgb(graphics_context["foreground"])
    )

    assert np.allclose(actual, expected, atol=1e-3), (
        f"glow must be pre-blended over the canvas: "
        f"{graphics_context['foreground']} != {expected}"
    )


def test_canvas_constant_matches_engine():
    assert design_system.CANVAS_COLOR == VisualEngine.BG_COLOR


def test_no_heavy_black_strokes_left_in_scene_engine():
    source = _read_scene_source()

    assert 'foreground="black"' not in source, (
        "title / label strokes must use the editorial halo"
    )
    assert "foreground='black'" not in source


# ----------------------------------------------------------
# Dead-code wiring: atmosphere + line depth
# ----------------------------------------------------------

def test_atmosphere_is_wired_into_create_figure():
    script = types.SimpleNamespace(
        title="Atmosphere probe",
        source_name="Test Source",
    )

    fig, ax = VisualEngine._create_figure(script, "")

    try:
        glows = [
            image for image in ax.images
            if image.zorder == 0
        ]

        assert len(glows) == 2, (
            "apply_atmosphere must run inside _create_figure "
            f"and add its two glow layers (found {len(glows)})"
        )
    finally:
        plt.close(fig)


def test_wiring_counts_in_source():
    source = _read_scene_source()

    assert (
        source.count("design_system.apply_atmosphere(") == 2
    ), "bar race + _create_figure must both call it"
    assert (
        source.count("design_system.apply_line_depth(") == 3
    ), "line / area / slope must all call it"


def test_line_depth_preserves_flat_colour_and_adds_halo():
    halo_line = plt.Line2D([], [])
    design_system.apply_line_depth(
        halo_line, ["#7D8CA3"], width=4.0, glow=True
    )

    assert halo_line.get_color() == "#7D8CA3"
    assert halo_line.get_linewidth() == 4.0
    assert halo_line.get_path_effects(), (
        "glow=True must attach the restrained halo"
    )

    plain_line = plt.Line2D([], [])
    design_system.apply_line_depth(
        plain_line, ["#7D8CA3"], width=3.5, glow=False
    )

    assert plain_line.get_color() == "#7D8CA3"
    assert plain_line.get_linewidth() == 3.5
    assert not plain_line.get_path_effects()