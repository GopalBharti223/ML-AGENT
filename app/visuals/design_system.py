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
from matplotlib.patches import Ellipse


# =========================================================
# DEPTH / GLOW CONSTANTS
# =========================================================

# Winner glow: restrained.  A halo that reads as "premium
# emphasis", not as neon.
GLOW_ALPHA = 0.20


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
    """A soft outer halo, used ONLY for the emphasised entity."""

    from matplotlib import patheffects

    return [
        patheffects.withStroke(
            linewidth=7.0,
            foreground=shade(base, 0.45),
            alpha=GLOW_ALPHA,
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
    """Match the line treatment to the bar treatment."""

    if line is None:
        return

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

    Drawn in FIGURE coordinates at zorder 0 so they always sit
    behind the data, and never animated -- a moving background
    would compete with the chart for attention.
    """

    x0, y0, width, height = ax.get_position().bounds

    soft = shade(accent, 0.10)

    layers = (
        (0.74, 0.80, 0.62, 0.085),
        (0.28, 0.24, 0.52, 0.055),
    )

    for cx, cy, radius, alpha in layers:

        try:
            ax.add_patch(
                Ellipse(
                    (x0 + width * cx, y0 + height * cy),
                    width * radius,
                    height * radius,
                    transform=fig.transFigure,
                    facecolor=soft,
                    edgecolor="none",
                    alpha=alpha * float(strength),
                    zorder=0,
                )
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
# MOTION
# =========================================================

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


def apply_entrance_alpha(
    artists,
    frame,
    frames,
    spread=0.40,
    span=0.45,
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
    """

    if not artists or not frames:
        return

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

        try:
            artist.set_alpha(original * progress)
        except Exception:
            continue