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
import matplotlib.colors as mcolors
import numpy as np
from matplotlib.colors import LinearSegmentedColormap


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