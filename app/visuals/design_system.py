"""PREMIUM VISUAL DESIGN SYSTEM.

One place for the visual language shared by all eight renderers:
depth, atmosphere, ramps, glow and motion timing.  Renderers call
these helpers instead of each inventing its own effects, so a
look change lands everywhere at once and stays consistent.

Design rules encoded here:

* the chart is the hero -- effects never reduce legibility;
* depth comes from light, not clutter: a thin top highlight, a
  soft ambient shadow and a very restrained glow;
* nothing is fully opaque-glass; tints stay subtle;
* motion is purposeful (entrance, build, rank change, payoff)
  and always eased -- no bounce, no shake, no idle jitter.
"""
import json

import matplotlib.colors as mcolors
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from app.config import settings
from app.visuals import fonts as _fonts


# ---- font / sizing convenience shims (single source: fonts.py) -----
min_pt = _fonts.min_pt
px_to_pt = _fonts.px_to_pt
pt_to_px = _fonts.pt_to_px
title_family = _fonts.title_family
text_family = _fonts.text_family
title_weight = _fonts.title_weight
label_weight = _fonts.label_weight


# =========================================================
# LR ATLAS EDITORIAL CATEGORICAL SYSTEM
#
# ONE restrained identity across every renderer: champagne gold
# leads, and the supporting hues are muted, desaturated
# companions -- slate-blue, sage, terracotta, slate -- that feel
# related and editorial on the navy canvas.  No neon, no rainbow
# wheel: a legend-keyed chart must stay legible without looking
# like a different brand from the single-ramp bars.
# =========================================================

# Primary brand accent; index 0 is the hero slot.
BRAND_GOLD = "#D4AF37"

# Restrained secondary accents: muted companions of the gold,
# dark enough to sit on the navy canvas without glowing.
# Slot 0 IS the brand gold (bound by construction, so the hero
# slot can never drift from the brand accent).
CATEGORICAL_PALETTE = [
    BRAND_GOLD,  # champagne gold (hero)
    "#7D8CA3",  # muted slate blue
    "#6E9887",  # muted sage
    "#B56A5A",  # muted terracotta
    "#A67C52",  # muted bronze
    "#8FA3BF",  # pale slate
    "#7FA08F",  # pale sage
    "#C08A78",  # pale terracotta
]


def editorial_text_effects(linewidth=2.5):
    """Soft dark-navy halo for titles and key labels.

    The heavy pure-black ``withStroke`` outline reads as gaming /
    thumbnail art.  A thinner halo in the canvas tone keeps the
    ivory text readable over bright bars while disappearing into
    the design instead of framing every glyph.

    NEVER pass ``alpha=`` to ``withStroke``: matplotlib then
    REPLACES the artist's alpha with the stroke's, so animated
    text can no longer be hidden with ``set_alpha(0)`` (caught
    live: the bar-race closing caption stayed visible through the
    entire video because of it).  Softness comes from the colour
    and the thin width alone.
    """

    from matplotlib import patheffects

    return [
        patheffects.withStroke(
            linewidth=linewidth,
            foreground="#0B1220",
        )
    ]


# =========================================================
# DEPTH / GLOW CONSTANTS
# =========================================================

# Winner glow: restrained.  A halo that reads as "premium
# emphasis", not as neon.
GLOW_ALPHA = 0.20

# Canvas tone -- must equal VisualEngine.BG_COLOR (pinned by
# test_visual_identity_palette).  The glow's 20% alpha is
# PRE-BLENDED over this tone instead of passed to withStroke as
# alpha= (see editorial_text_effects: an explicit stroke alpha
# replaces the artist alpha and breaks every fade/hide).
CANVAS_COLOR = "#101A2C"


# =========================================================
# RAMPS
# =========================================================

def ramp(colors, name="ramp"):
    """LinearSegmentedColormap from a list of hex colours.

    Renderers build gradients from the ACTIVE topic palette, so a
    topic change re-tints every gradient automatically instead of
    hard-coding gold everywhere.
    """

    colors = [c for c in colors if c]

    if len(colors) < 2:
        colors = ["#F5C15C", "#C89B3C"]

    return LinearSegmentedColormap.from_list(name, colors, N=256)


def shade(hex_color, amount):
    """Lighten (amount>0) or darken (amount<0) a hex colour.

    amount is a fraction: 0.18 lightens by 18% toward white.
    Used for the top highlight and the ambient shadow so both stay
    in the same hue family as the base colour.
    """

    try:
        rgb = np.array(mcolors.to_rgb(hex_color))
    except (ValueError, TypeError):
        return hex_color

    if amount >= 0:
        rgb = rgb + (1.0 - rgb) * amount
    else:
        rgb = rgb * (1.0 + amount)

    return mcolors.to_hex(np.clip(rgb, 0.0, 1.0))


def bar_face(colors, index, count):
    """Pick a ramp position for one entity.

    index 0 is the winner, so it gets the brightest end of the
    ramp and the tail falls away -- that is the whole visual
    hierarchy of a ranked chart, expressed as a colour ramp.
    """

    if not colors:
        return "#F5C15C"

    if count <= 1:
        return colors[0]

    t = 0.10 + 0.80 * (index / max(1, count - 1))

    if t <= 1.0:
        return ramp(colors)(t)

    return colors[-1]


def _winner_effects(base):
    """A soft outer halo, used ONLY for the emphasised entity.

    The GLOW_ALPHA opacity is baked into the stroke colour by
    pre-blending over the canvas (never passed as ``alpha=`` --
    that would replace the artist's alpha and break set_alpha
    fades/hides).  On the canvas the result is pixel-equivalent
    to drawing the highlight at 20% alpha.
    """

    from matplotlib import patheffects

    highlight = np.array(mcolors.to_rgb(shade(base, 0.45)))
    canvas = np.array(mcolors.to_rgb(CANVAS_COLOR))
    blended = mcolors.to_hex(
        highlight * GLOW_ALPHA + canvas * (1.0 - GLOW_ALPHA)
    )

    return [
        patheffects.withStroke(
            linewidth=7.0,
            foreground=blended,
        )
    ]


def apply_depth(artist, colors, index, count, glow=False):
    """Give one bar a dimensional, premium fill.

    Layers, cheap to cheap:
      1. a vertical gradient built from the topic ramp,
      2. a thin bright top edge = the surface catching light,
      3. an optional restrained halo for the winner.
    """

    if artist is None:
        return

    base = bar_face(colors, index, count)

    try:
        artist.set_facecolor(
            ramp([shade(base, -0.28), base, shade(base, 0.20)])
        )
    except Exception:
        try:
            artist.set_facecolor(base)
        except Exception:
            pass

    try:
        artist.set_edgecolor(shade(base, 0.34))
        artist.set_linewidth(1.0)
    except Exception:
        pass

    if glow:
        try:
            artist.set_path_effects(_winner_effects(base))
        except Exception:
            pass


def apply_line_depth(line, colors, index=0, width=5.0, glow=False):
    """Match the line treatment to the bar treatment.

    A single-entry colour list means "this line's EXACT colour"
    and is used verbatim: the ramp builder falls back to the
    default gold pair for lists shorter than two, which would
    silently repaint every line gold.  Longer lists keep the
    ramp-position behaviour of the bars.
    """

    if line is None:
        return

    colors = [color for color in (colors or []) if color]

    if not colors:
        base = "#F5C15C"
    elif len(colors) == 1:
        base = colors[0]
    else:
        base = bar_face(colors, index, 3)

    try:
        line.set_color(base)
        line.set_linewidth(width)
        line.set_solid_capstyle("round")
        line.set_solid_joinstyle("round")
    except Exception:
        pass

    if glow:
        try:
            line.set_path_effects(_winner_effects(base))
        except Exception:
            pass


# =========================================================
# ATMOSPHERE
# =========================================================

def apply_atmosphere(ax, fig, accent, strength=1.0):
    """Add restrained depth to the canvas behind the chart.

    Two cheap layers, both far below the chart in contrast:
      1. a wide, very soft radial glow in the accent colour,
      2. a smaller matching glow low on the opposite side.

    The glow is a smooth radial ALPHA FALLOFF (peak at the
    centre, easing to zero at the buffer edge), not a flat-filled
    ellipse: a flat fill showed its own boundary -- and, when it
    reached an axes edge, a clipped hard edge -- which read as a
    gray blob rather than atmosphere.

    Drawn in FIGURE coordinates at zorder 0 so they always sit
    behind the data, and never animated -- a moving background
    would compete with the chart for attention.
    """

    x0, y0, width, height = ax.get_position().bounds

    soft = shade(accent, 0.10)
    red, green, blue = mcolors.to_rgb(soft)

    # Radial window: 1.0 at the centre, 0.0 at the buffer edge.
    grid = 96
    step = 1.0 / (grid - 1)
    yy, xx = np.mgrid[0:grid, 0:grid]
    distance = np.sqrt(
        ((xx * step) - 0.5) ** 2
        + ((yy * step) - 0.5) ** 2
    ) * 2.0
    falloff = np.clip(1.0 - distance, 0.0, 1.0) ** 2

    # (cx, cy, radius, peak alpha).  Centres are kept at least
    # radius/2 + 0.02 from every axes edge so the glow always
    # fades to zero BEFORE any clip boundary.
    layers = (
        (0.74, 0.76, 0.44, 0.060),
        (0.28, 0.30, 0.52, 0.040),
    )

    for cx, cy, radius, alpha in layers:

        rgba = np.empty((grid, grid, 4), dtype=float)
        rgba[..., 0] = red
        rgba[..., 1] = green
        rgba[..., 2] = blue
        rgba[..., 3] = falloff * alpha * float(strength)

        half_x = width * radius / 2.0
        half_y = height * radius / 2.0

        try:
            ax.imshow(
                rgba,
                extent=[
                    x0 + width * cx - half_x,
                    y0 + height * cy - half_y,
                    x0 + width * cx + half_x,
                    y0 + height * cy + half_y,
                ],
                transform=fig.transFigure,
                aspect="auto",
                interpolation="bilinear",
                zorder=0,
            )
        except Exception:
            pass

    return accent


# =========================================================
# LAYOUT
# =========================================================

def label_stack(data_range, ratio=0.055, size_ratio=0.78):
    """Separate the value label from the entity label.

    The two labels used to share ONE anchor, so a value like
    "60.0" rendered directly on top of the country name -- visible
    in real line/area frames.  Lift the value clear of the name
    and make it visually secondary, which is also the correct
    hierarchy: the NAME is the story, the number is support.
    """

    try:
        span = abs(float(data_range))
    except (TypeError, ValueError):
        span = 1.0

    if span <= 0:
        span = 1.0

    return {
        "entity_dy": 0.0,
        "value_dy": span * float(ratio),
        "value_size_ratio": float(size_ratio),
    }


# =========================================================
# THEME ENGINE  (Premium UI v2)
#
# One background family PER TOPIC instead of a single fixed
# canvas for every video.  The theme owns the background
# gradient, the accent pair, the glow colour and the 8-colour
# bar ramp, so all eight renderers share one brand per topic.
#
# The registry lives in app/visuals/theme.py; resolution and
# cursor rotation are re-exported here so visual code only
# ever imports design_system.
# =========================================================

from app.visuals import theme as _theme_mod


build_theme = _theme_mod.build_theme
resolve_theme = _theme_mod.resolve_theme
theme_keys = _theme_mod.theme_keys
default_theme_key = _theme_mod.default_theme_key
reset_theme_cursor = _theme_mod.reset_cursor
next_theme_key = _theme_mod.next_theme_key


def theme_for(topic=""):
    """Theme KEY for one topic (override > keyword > rotation)."""
    override = str(getattr(settings, "UI_THEME_OVERRIDE", "") or "").strip()

    if override and override in _theme_mod._THEME_REGISTRY:
        return override

    if not getattr(settings, "UI_THEME_ENABLED", True):
        return _theme_mod.default_theme_key()

    return next_theme_key(topic or "")


def active_theme(topic=""):
    """Full theme DICT for one topic.  Never returns None."""
    key = theme_for(topic)
    theme = build_theme(key)
    if theme is None:
        theme = build_theme(_theme_mod.default_theme_key())
    if theme is None:
        theme = {
            "bg_top": CANVAS_COLOR,
            "bg_bottom": shade(CANVAS_COLOR, 0.08),
            "accent": BRAND_GOLD,
            "accent2": shade(BRAND_GOLD, 0.24),
            "glow": BRAND_GOLD,
            "text_primary": "#F8F6F0",
            "text_secondary": "#A8B3C7",
            "ramp": list(CATEGORICAL_PALETTE),
        }
    return theme


# =========================================================
# CINEMATIC BACKGROUND
#
# Three stacked layers, all STATIC (a moving background
# competes with the chart for attention):
#   1. vertical gradient  bg_top -> bg_bottom,
#   2. radial accent glow -- 12-18% peak alpha (the old
#      4-6% glow was effectively invisible),
#   3. a very light vignette that lifts the centre.
# =========================================================

def gradient_image(top, bottom, size=256):
    """RGBA image of a vertical gradient from `top` to `bottom`."""
    top_rgb = np.array(mcolors.to_rgb(top), dtype=float)
    bottom_rgb = np.array(mcolors.to_rgb(bottom), dtype=float)

    # Row 0 is the TOP of the screen (imshow origin="upper").
    ramp = np.linspace(0.0, 1.0, size, dtype=float)[:, None, None]
    image = (
        top_rgb[None, :, :] * (1.0 - ramp)
        + bottom_rgb[None, :, :] * ramp
    )

    rgba = np.ones((size, 1, 4), dtype=float)
    rgba[..., :3] = image
    rgba[..., 3] = 1.0
    return rgba


def _radial_falloff(grid=128, exponent=2.0):
    """Smooth 1.0-at-centre -> 0.0-at-edge window (no hard rim)."""
    step = 1.0 / (grid - 1)
    yy, xx = np.mgrid[0:grid, 0:grid]
    distance = np.sqrt(
        ((xx * step) - 0.5) ** 2 + ((yy * step) - 0.5) ** 2
    ) * 2.0
    return np.clip(1.0 - distance, 0.0, 1.0) ** exponent


def glow_alpha():
    """Peak alpha for the background accent glow (0.12..0.60)."""
    try:
        value = float(getattr(settings, "UI_GLOW_ALPHA", 0.15))
    except (TypeError, ValueError):
        value = 0.15
    # Floor raised to 0.12: anything in the old 4-6% band reads as
    # "no background at all" on a phone.
    return min(0.60, max(0.12, value))


def vignette_alpha():
    """Edge-darkening strength for the vignette (0..0.60)."""
    try:
        value = float(getattr(settings, "UI_VIGNETTE_ALPHA", 0.22))
    except (TypeError, ValueError):
        value = 0.22
    return min(0.60, max(0.0, value))


def paint_background(fig, theme, strength=1.0):
    """Paint the full-canvas themed background behind the chart.

    Layers go on a dedicated full-figure axes at zorder -10 so they
    can never cover data, and never animate.  Safe to call once per
    figure: every step is individually guarded, so a failure degrades
    to a flat ``bg_top`` canvas instead of raising.

    Returns the accent colour so callers can chain off it.
    """
    if not theme:
        theme = active_theme()

    top = theme.get("bg_top") or CANVAS_COLOR
    bottom = theme.get("bg_bottom") or shade(top, 0.10)
    glow = theme.get("glow") or theme.get("accent") or BRAND_GOLD

    try:
        scale = max(0.0, min(1.0, float(strength)))
    except (TypeError, ValueError):
        scale = 1.0

    try:
        base = fig.add_axes([0.0, 0.0, 1.0, 1.0], zorder=-10)
        base.set_axis_off()
        base.set_facecolor("none")
        base.patch.set_alpha(0.0)
    except Exception:
        try:
            fig.patch.set_facecolor(top)
        except Exception:
            pass
        return glow

    # 1. vertical gradient -----------------------------------
    try:
        base.imshow(
            gradient_image(top, bottom),
            origin="upper",
            extent=[0.0, 1.0, 0.0, 1.0],
            aspect="auto",
            interpolation="bilinear",
            zorder=0,
        )
    except Exception:
        try:
            fig.patch.set_facecolor(top)
        except Exception:
            pass

    # 2. radial accent glows ---------------------------------
    # Placed high (where the eye lands first on a vertical Short)
    # with a cooler counter-glow low down, so the frame reads as
    # lit rather than flat-filled.
    strength_total = glow_alpha() * scale
    red, green, blue = mcolors.to_rgb(shade(glow, 0.06))
    falloff = _radial_falloff()

    layers = (
        (0.62, 0.76, 0.74, 0.44, 1.00),
        (0.20, 0.22, 0.62, 0.34, 0.55),
    )

    for cx, cy, half_w, half_h, weight in layers:
        rgba = np.empty(falloff.shape + (4,), dtype=float)
        rgba[..., 0] = red
        rgba[..., 1] = green
        rgba[..., 2] = blue
        rgba[..., 3] = falloff * strength_total * weight

        try:
            base.imshow(
                rgba,
                origin="upper",
                extent=[cx - half_w, cx + half_w,
                        cy - half_h, cy + half_h],
                aspect="auto",
                interpolation="bilinear",
                zorder=1,
            )
        except Exception:
            continue

    # 3. light vignette --------------------------------------
    edge = vignette_alpha() * scale
    if edge > 0.0:
        dark = np.array(mcolors.to_rgb(top), dtype=float) * 0.35
        corner = np.clip(1.0 - falloff, 0.0, 1.0) ** 1.5

        rgba = np.empty(falloff.shape + (4,), dtype=float)
        rgba[..., 0] = dark[0]
        rgba[..., 1] = dark[1]
        rgba[..., 2] = dark[2]
        rgba[..., 3] = corner * edge

        try:
            base.imshow(
                rgba,
                origin="upper",
                extent=[0.0, 1.0, 0.0, 1.0],
                aspect="auto",
                interpolation="bilinear",
                zorder=2,
            )
        except Exception:
            pass

    return glow


# =========================================================
# SAFE ZONES
#
# YouTube Shorts overlays its own chrome on top of the video:
# the like/comment/share rail down the RIGHT edge, the handle
# and caption strip at the TOP, and the title/handle/soundtrack
# block at the BOTTOM.  Text or numbers drawn into those bands
# are simply unreadable, so every renderer must lay out inside
# the rectangle these helpers return.
#
# Values are FRACTIONS of the 1080x1920 canvas.
# =========================================================

def _clamp_frac(value, fallback, low=0.0, high=0.45):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return min(high, max(low, number))


def safe_zone():
    """Shorts UI overlay insets, as canvas fractions."""
    return {
        "top": _clamp_frac(
            getattr(settings, "SAFE_ZONE_TOP", 0.08), 0.08, 0.0, 0.30
        ),
        "bottom": _clamp_frac(
            getattr(settings, "SAFE_ZONE_BOTTOM", 0.22), 0.22, 0.0, 0.40
        ),
        "right": _clamp_frac(
            getattr(settings, "SAFE_ZONE_RIGHT", 0.14), 0.14, 0.0, 0.40
        ),
        "left": _clamp_frac(
            getattr(settings, "SAFE_ZONE_LEFT", 0.05), 0.05, 0.0, 0.25
        ),
    }


def safe_left():
    return safe_zone()["left"]


def safe_right():
    """Figure-x of the right usable edge (1 - right inset)."""
    return 1.0 - safe_zone()["right"]


def safe_top():
    """Figure-y of the top usable edge (1 - top inset)."""
    return 1.0 - safe_zone()["top"]


def safe_bottom():
    """Figure-y of the bottom usable edge."""
    return safe_zone()["bottom"]


def usable_width():
    """Horizontal span available to content, as a fraction."""
    return max(0.20, safe_right() - safe_left())


def chart_frame(vertical_span=None):
    """(left, bottom, width, height) for the bar-race / top5 axes.

    Replaces the old CHART_LEFT 0.37 / CHART_WIDTH 0.57 frame that
    left a wide dead column on the left and ran under the Shorts
    rail on the right.  The new frame starts just inside the left
    inset and spans CHART_WIDTH_FRACTION of the usable width, and
    vertically fills the band between the safe zones so the empty
    gap above and below the chart is gone.
    """
    left = safe_left()
    width = usable_width() * _clamp_frac(
        getattr(settings, "CHART_WIDTH_FRACTION", 0.80), 0.80, 0.30, 1.0
    )

    top = safe_top()
    bottom = safe_bottom()
    available = top - bottom

    if vertical_span:
        available *= _clamp_frac(vertical_span, 1.0, 0.20, 1.0)

    # Nudge up slightly: a chart optically centred in the usable
    # band reads low, because the bottom third is overlaid chrome.
    bottom += available * 0.04
    height = max(0.12, available * 0.92)

    return left, bottom, width, height


def title_zone():
    """(left, bottom, width, height) of the title band at the top."""
    zone = safe_zone()
    left = zone["left"]
    width = usable_width()
    top = 1.0 - zone["top"]
    height = max(0.05, top - 0.72)
    return left, 0.72, width, height


def progress_bar_y():
    """Figure-y of the optional progress bar, above the bottom inset."""
    return min(0.985, safe_bottom() + 0.012)


def progress_bar_span():
    """(left, width) of the progress bar track."""
    left = safe_left()
    return left, usable_width()


# =========================================================
# TEXT FITTING  -- "zero clipping, zero overlap"
#
# Four ordered strategies per label:
#   1. short-name map  (curated abbreviation table),
#   2. auto-fit        (shrink toward the legibility floor),
#   3. two-line wrap   (only if auto-fit alone still overflows),
#   4. ellipsis        (never shrink below fonts.min_pt()).
# =========================================================

# Curated short names for long country / entity labels that blow
# up bar-race rows on a phone.  Match is case-insensitive on the
# normalized key.  Extend / override via UI_SHORT_NAME_MAP (JSON).
_DEFAULT_SHORT_NAMES = {
    "democratic republic of the congo": "DR Congo",
    "democratic republic of congo": "DR Congo",
    "central african republic": "CAR",
    "bosnia and herzegovina": "Bosnia",
    "united states of america": "United States",
    "united states": "United States",
    "united kingdom of great britain": "United Kingdom",
    "united kingdom": "United Kingdom",
    "russian federation": "Russia",
    "republic of china": "China",
    "people's republic of china": "China",
    "kingdom of saudi arabia": "Saudi Arabia",
    "saudi arabia": "Saudi Arabia",
    "united arab emirates": "UAE",
    "south korea": "South Korea",
    "korea, republic of": "South Korea",
    "republic of korea": "South Korea",
    "north korea": "North Korea",
    "united republic of tanzania": "Tanzania",
    "papua new guinea": "PNG",
    "czech republic": "Czechia",
    "czechia": "Czechia",
    "trinidad and tobago": "Trinidad",
    "antigua and barbuda": "Antigua",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "dr congo": "DR Congo",
}

_SHORT_NAME_CACHE = {"loaded": False, "map": None}


def _normalize_key(name):
    return " ".join(str(name).strip().lower().split())


def _short_name_map():
    """Merge the built-in short names with the .env override."""
    if _SHORT_NAME_CACHE["loaded"]:
        return _SHORT_NAME_CACHE["map"]

    merged = dict(_DEFAULT_SHORT_NAMES)
    raw = getattr(settings, "UI_SHORT_NAME_MAP", "") or ""
    if raw:
        try:
            extra = json.loads(raw)
            if isinstance(extra, dict):
                for key, value in extra.items():
                    merged[_normalize_key(key)] = str(value)
        except Exception:
            pass

    _SHORT_NAME_CACHE["map"] = merged
    _SHORT_NAME_CACHE["loaded"] = True
    return merged


def short_name(name):
    """Curated short form of `name`, or `name` unchanged."""
    mapping = _short_name_map()
    key = _normalize_key(name)
    if key in mapping:
        return mapping[key]
    return str(name)


_MEASURE_FIG = {"fig": None}


def _measure_renderer():
    """One shared hidden figure renderer for text measuring."""
    try:
        import matplotlib
        fig = _MEASURE_FIG["fig"]
        if fig is None:
            fig = matplotlib.figure.Figure(figsize=(1, 1), dpi=100)
            _MEASURE_FIG["fig"] = fig
        return fig.canvas.get_renderer()
    except Exception:
        return None


def _text_width_px(text, fontsize_pt, family=None, weight="normal"):
    """Approximate rendered width of `text` in canvas pixels."""
    if family is None:
        family = text_family()

    try:
        renderer = _measure_renderer()
        if renderer is not None:
            from matplotlib.textpath import TextPath
            from matplotlib.font_manager import FontProperties

            properties = FontProperties(
                family=family, size=fontsize_pt, weight=weight
            )
            path = TextPath((0, 0), str(text), prop=properties)
            return path.get_extents().width * 100.0 / 72.0
    except Exception:
        pass

    # Heuristic fallback (~0.55 em average advance) -> px.
    return len(str(text)) * fontsize_pt * 0.55 * 100.0 / 72.0


# Public alias: renderers measure label budgets with the same
# helper the fitting tools use (pie/waffle legend columns, value
# budgets, etc.) so no renderer re-invents a width estimator.
text_width_px = _text_width_px


def fit_fontsize(text, max_width_px, start_px, family=None, weight="normal"):
    """Largest point size <= start_px that fits `text` in max_width_px.

    Never returns below the legibility floor (fonts.min_pt()).
    """
    floor_pt = min_pt()
    start_pt = px_to_pt(start_px)

    text = str(text)
    if not text or max_width_px <= 0:
        return max(start_pt, floor_pt)

    try:
        size = float(start_pt)
        while size > floor_pt and _text_width_px(
            text, size, family, weight
        ) > max_width_px:
            size -= 0.5
    except Exception:
        size = max(start_pt, floor_pt)

    return max(floor_pt, size)


def ellipsize(text, max_width_px, fontsize_pt, family=None, weight="normal"):
    """Truncate `text` with an ellipsis so it fits max_width_px.

    Only used when a label will not fit at the floor, so a long name
    degrades to "Democratic Republic o..." instead of being drawn
    sub-floor or off the edge.
    """
    text = str(text)
    try:
        if _text_width_px(
            text, fontsize_pt, family, weight
        ) <= max_width_px:
            return text
    except Exception:
        return text

    ellipsis = "..."
    trimmed = text
    while trimmed and _text_width_px(
        trimmed + ellipsis, fontsize_pt, family, weight
    ) > max_width_px:
        trimmed = trimmed[:-1]
    trimmed = trimmed.rstrip()
    return (trimmed + ellipsis) if trimmed else ellipsis


def _wrap_two_lines(text, max_width_px, size_pt, family, weight):
    """Best balanced 2-line split of `text`, or None if none fits."""
    words = str(text).split()
    if len(words) < 2:
        return None

    best = None
    best_cost = None
    for split in range(1, len(words)):
        head = " ".join(words[:split])
        tail = " ".join(words[split:])
        try:
            head_w = _text_width_px(head, size_pt, family, weight)
            tail_w = _text_width_px(tail, size_pt, family, weight)
        except Exception:
            return None
        if head_w <= max_width_px and tail_w <= max_width_px:
            cost = abs(head_w - tail_w)
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best = [head, tail]
    return best


def fit_label(text, max_width_px, base_px, family=None, weight="bold",
              max_lines=2):
    """Fit one label to max_width_px honouring every rule at once.

    Order: short-name -> auto-fit -> (optional 2-line wrap) -> ellipsis.
    Returns ``(short, lines, fontsize_pt)``; fontsize >= legibility
    floor, so callers draw it directly with no further size checks.
    """
    if family is None:
        family = text_family()

    short = short_name(text)
    size_pt = fit_fontsize(short, max_width_px, base_px, family, weight)

    try:
        if _text_width_px(short, size_pt, family, weight) <= max_width_px:
            return short, [short], size_pt
    except Exception:
        return short, [short], size_pt

    if max_lines >= 2:
        best = _wrap_two_lines(short, max_width_px, size_pt, family, weight)
        if best is not None:
            return short, best, size_pt

    return short, [
        ellipsize(short, max_width_px, size_pt, family, weight)
    ], size_pt


def _greedy_wrap(text, max_width_px, size_pt, family, weight):
    """Greedy word wrap of `text` at `size_pt` into fitting lines."""
    words = str(text).split()
    if not words:
        return [""]

    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = current + " " + word
        try:
            fits = _text_width_px(
                candidate, size_pt, family, weight
            ) <= max_width_px
        except Exception:
            fits = True
        if fits:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def wrap_title(text, max_width_px, start_px, family=None, max_lines=None):
    """Fit a title to at most `max_lines` lines, never below the floor.

    Returns ``(lines, fontsize_pt)``.
    """
    if family is None:
        family = title_family()

    if max_lines is None:
        max_lines = int(getattr(settings, "UI_TITLE_MAX_LINES", 2) or 2)
    max_lines = max(1, int(max_lines))

    text = " ".join(str(text).split())
    floor_pt = min_pt()
    size_pt = px_to_pt(start_px)

    while True:
        lines = _greedy_wrap(text, max_width_px, size_pt, family, "bold")
        if len(lines) <= max_lines or size_pt <= floor_pt + 0.01:
            return lines[:max_lines], max(floor_pt, size_pt)
        size_pt -= 1.0


def draw_glass_card(fig, rect, accent=None, radius=0.02, alpha=None,
                    border=True):
    """Soft glass card behind the title (rounded, translucent, 1px
    accent border).  `rect` = (left, bottom, width, height) in figure
    fractions.  Returns the card axes or None -- never raises.
    """
    if accent is None:
        accent = BRAND_GOLD

    if alpha is None:
        try:
            alpha = float(getattr(settings, "UI_TITLE_CARD_ALPHA", 0.10))
        except (TypeError, ValueError):
            alpha = 0.10

    left, bottom, width, height = rect
    try:
        ax = fig.add_axes([left, bottom, width, height], zorder=-5)
        ax.set_axis_off()
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.patch.set_alpha(0.0)

        from matplotlib.patches import FancyBboxPatch

        card = FancyBboxPatch(
            (0.008, 0.06),
            0.984,
            0.88,
            boxstyle=f"round,pad=0,rounding_size={radius}",
            linewidth=1.0 if border else 0,
            edgecolor=accent if border else "none",
            facecolor="#FFFFFF",
            transform=ax.transAxes,
            zorder=0,
        )
        card.set_alpha(alpha)
        ax.add_patch(card)
        return ax
    except Exception:
        return None


# =========================================================
# MOTION  -- Part 2 shared language
#
# Every renderer speaks the same timing dialect (normalized
# 0.0 -> 1.0 progress, smoothstep ease-in/out, staggered
# reveal, short payoff/final beat), while each chart keeps its
# OWN movement (bars race, lines sweep, waffles fill).
# No bounce / shake / jitter / elastic overshoot anywhere.
# =========================================================

# Shared answer-hold / payoff window (seconds).  Renderers read
# the env-tunable settings value; this constant is the fallback
# and the single number tests pin.
ANSWER_HOLD_SECONDS = 2.0

# Opening-entrance stagger windows: tighter than the legacy
# 0.55/1.0 defaults so content is readable from frame 0 and
# settled quickly -- editorial reveal, not loading animation.
ENTRANCE_SPREAD = 0.24
ENTRANCE_SPAN = 0.34

# Closing beat: how far before the end the final state must be
# fully settled (fraction of total frames).  The tail after it
# is a short intentional beat, never a long dead hold.
FINAL_SETTLE_FRAC = 0.94

# Right-edge safety (px) for numeric value labels at 1080x1920.
VALUE_SAFE_MARGIN_PX = 28.0


def ease_out(t):
    """Decelerating ease: quick start, calm landing.

    Entrances arrive and settle instead of snapping, which is what
    separates a premium reveal from a cheap pop.
    """

    t = max(0.0, min(1.0, float(t)))

    return 1.0 - (1.0 - t) ** 3


def ease_in_out(t):
    t = max(0.0, min(1.0, float(t)))

    return t * t * (3.0 - 2.0 * t)


def normalized_progress(frame, total_frames, start_frac=0.0, end_frac=1.0):
    """Map a frame index onto eased 0.0 -> 1.0 over [start,end].

    Deterministic, monotonic, bounded; immune to total_frames
    changes.  Division-by-zero safe (degenerate window -> 1.0).
    """

    try:
        total = max(1, int(total_frames) - 1)
        frame = float(frame)
    except (TypeError, ValueError):
        return 0.0

    start = max(0.0, min(1.0, float(start_frac)))
    end = max(0.0, min(1.0, float(end_frac)))

    if end <= start:
        return 1.0 if frame >= start * total else 0.0

    raw = (frame / total - start) / (end - start)

    return ease_in_out(raw)


def answer_hold_frames(total_frames, fps=30, seconds=None):
    """Frame count of the opening answer hold (~2.0s).

    Clamped to [0, total_frames // 2] so short videos keep a
    proportional hold and never lose their replay.
    """

    try:
        total = max(1, int(total_frames))
        rate = float(fps) if float(fps) > 0 else 30.0
        secs = (
            float(seconds)
            if seconds is not None
            else ANSWER_HOLD_SECONDS
        )
    except (TypeError, ValueError):
        return 0

    if secs <= 0:
        return 0

    return min(int(secs * rate), total // 2)


def entrance(frame, frames, delay=0.0, span=1.0):
    """Staggered entrance progress in [0, 1].

    Each element gets its own `delay` fraction of the window, so
    a chart assembles in a readable order (winner first, then the
    field) instead of everything appearing at once.

    This is what gives the opening a real visual event even while
    the data already sits at its final payoff state -- the
    previous behaviour held a frozen final frame for
    OPENING_PAYOFF_SECONDS, which measured 0.0002%-0.0005% of
    changed pixels across that window.
    """

    if frames <= 1:
        return 1.0

    position = (float(frame) - float(delay) * frames) / max(
        1e-6, float(span) * frames
    )

    return ease_out(position)


def stagger(index, count, spread=0.55):
    """Delay fraction for element `index` of `count`.

    The winner (index 0) starts first; later ranks trail off, so
    the eye is guided to the leader.
    """

    if count <= 1:
        return 0.0

    return float(spread) * (index / max(1, count - 1))


# OPENING-FLOOR FIX (render audit, bar_race / line / top5_change):
# the entrance used to fade/grow every element from EXACTLY zero,
# so the first ~0.5s of a Short was mostly empty canvas -- the
# story had not started yet.  Every entrance now starts at this
# fraction of its final size/opacity and settles to full, which
# fills the opening with content that is already readable while
# still animating in (settled, not rushed).
#
# Part 2: 0.45 was still visibly dim on the answer hold -- the
# final state must be READABLE at frame 0, with only subtle
# presence/micro-motion.  0.72 keeps full legibility while the
# stagger still gives the opening a real visual event.
ENTRANCE_FLOOR = 0.72


def apply_entrance_alpha(
    artists,
    frame,
    frames,
    spread=0.24,
    span=0.34,
    floor=None,
):
    """Staggered fade-in for a renderer's artists.

    Renderer-agnostic and deliberately non-destructive: it only
    scales `alpha`, never geometry, so it can be dropped into the
    opening-payoff branch of ANY renderer without changing what
    the chart means or where anything sits.

    Each artist's ORIGINAL alpha is captured on first use and used
    as the ceiling.  Without that, an area fill created with
    alpha=0.30 would be forced to 1.0 by the entrance and turn
    into an opaque slab -- a visual regression, not an entrance.

    Rationale: the opening payoff deliberately froze the final
    state so the answer is visible immediately (good for
    retention) -- but frozen measured 0.0000%-0.0008% changed
    pixels across 2.5s, which reads on a phone as a dead frame.
    Fading in while the data is already final keeps the retention
    behaviour and restores a real opening visual event.

    OPENING-FLOOR: the fade used to start at alpha 0, so even with
    the stagger the first ~0.5s was largely empty canvas.  The
    fade now starts at `floor` (ENTRANCE_FLOOR by default) of the
    artist's original opacity and settles to full, and the
    stagger/spread window is tighter, so content is readable from
    the very first frames without a flashy pop.
    """

    if not artists or not frames:
        return

    if floor is None:
        floor = ENTRANCE_FLOOR

    try:
        floor = min(1.0, max(0.0, float(floor)))
    except (TypeError, ValueError):
        floor = ENTRANCE_FLOOR

    count = len(artists)

    for index, artist in enumerate(artists):

        if artist is None:
            continue

        # Capture the artist's intended opacity once.
        original = getattr(artist, "_entrance_base_alpha", None)

        if original is None:

            try:
                current = artist.get_alpha()
                original = 1.0 if current is None else float(current)
            except Exception:
                original = 1.0

            try:
                artist._entrance_base_alpha = original
            except Exception:
                pass

        progress = entrance(
            frame,
            frames,
            delay=stagger(index, count, spread),
            span=span,
        )

        # Floor + settle: visible from the first frame, full by the
        # end of the entrance window (progress == 1 -> `original`).
        eased = floor + (1.0 - floor) * progress

        try:
            artist.set_alpha(original * eased)
        except Exception:
            continue