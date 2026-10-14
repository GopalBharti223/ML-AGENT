import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.patches as mpatches
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
import os
import random

from app.time_labels import coerce_year_label
from app.config import settings
from app.visuals import design_system


class VisualEngine:


    # =========================================================
    # COLORS
    # =========================================================

    # -----------------------------------------------------
    # PREMIUM PALETTE
    #
    # Navy-tinted deep canvas, ivory typography and a
    # champagne-gold accent system. Constant names are
    # kept for compatibility; only the values changed.
    #
    # BACKGROUND TONE (Part 3): was #0D1117 -- a near-pure
    # neutral black with a barely-there blue cast (RGB
    # 13/17/23, channels within 10 of each other), which read
    # as flat "GitHub dark" charcoal and left the gold accents
    # floating on a void.  Now #101A2C: still deep enough to
    # stay OLED-friendly and to keep ivory text (#F5F2EA) at a
    # ~17:1 contrast ratio, but LIFTED (+3/+9/+21) with the
    # blue channel clearly dominant, so the canvas reads as a
    # navy-tinted night blue that the champagne gold / azure
    # bar palettes sit on rather than glare against.
    # BG_GRADIENT_TOP is kept numerically EQUAL to BG_COLOR so
    # the vignette starts exactly on the canvas colour.
    # -----------------------------------------------------

    BG_COLOR = "#101A2C"

    TEXT_COLOR = "#F5F2EA"
    SECONDARY_TEXT = "#9AA4B2"

    ELECTRIC_BLUE = "#D4AF37"
    BLUE_VIOLET = "#C39A45"
    VIOLET = "#A67C33"
    PURPLE = "#8C6626"
    MAGENTA_PURPLE = "#E8C97A"

    LEADER_COLOR = "#F0D48A"

    # Step 6 emphasis
    OVERTAKE_COLOR = "#FFF3D6"

    # =========================================================
    # ENHANCED VISUAL COLORS
    # =========================================================

    # Background gradient (top ΓåÆ bottom).  TOP mirrors
    # BG_COLOR; BOTTOM keeps the original +8/+10/+16 step on
    # the new navy base so the vignette is exactly as subtle
    # as before, only tinted navy.
    BG_GRADIENT_TOP = "#101A2C"
    BG_GRADIENT_BOTTOM = "#18243C"

    # Subtle grid lines
    GRID_COLOR = "#222A36"

    # Leader bar glow
    LEADER_GLOW = "#D4AF37"

    # Year transition flash
    FLASH_COLOR = "#F5F2EA"


    # =========================================================
    # VIDEO
    # =========================================================

    FPS = 30

    # =========================================================
    # AUDIO-SYNCED TIMING
    #
    # When run.py passes the REAL measured narration length to
    # render_scenes(), _duration_override carries (audio +
    # AUDIO_TAIL_HOLD) and every renderer sizes its timeline
    # from _effective_duration() instead of the planned
    # script.total_duration.  The tail hold makes the video run
    # slightly LONGER than the audio so the assembler trims
    # padding -- never narration -- at the mux.
    # =========================================================

    # DEAD-AIR FIX (Issue 1, published-video review): this was a
    # hard-coded 0.75s.  The hold exists only so the mux trims
    # padding rather than the final syllable, and narration is
    # already aggressively edge-trimmed
    # (_trim_leading_silence / _trim_trailing_silence), so 0.75s
    # was pure slack: the assembler has to fill the whole hold
    # with tail_bridge_audio.mp3, which is 100% silence -- measured
    # 0.73s of dead air sitting immediately before the outro card.
    # Now sourced from settings (AUDIO_TAIL_HOLD_S, default 0.20s).
    # MEASURED: at 0.25s the real render 20260924_195250 produced
    # an exact 0.2395s bridge, and 0.24 + the narration's 0.02s
    # kept tail = 0.26s -- still one detectable gap at the 0.25s
    # floor.  At 0.20s the silent run is ~0.21s: below the floor,
    # inaudible, and still ample slack for the mux.
    AUDIO_TAIL_HOLD = float(
        getattr(settings, "AUDIO_TAIL_HOLD_S", 0.20)
    )

    _duration_override: float = 0.0

    @staticmethod
    def _effective_duration(script):

        override = getattr(
            VisualEngine,
            "_duration_override",
            0.0,
        )

        if override and override > 0:
            return override

        planned = getattr(
            script,
            "total_duration",
            0,
        ) or 0

        return planned if planned > 0 else 25

    # =========================================================
    # BAR
    # =========================================================

    BAR_HEIGHT = 0.48

    # Never draw a bar narrower than this fraction of the current
    # axis maximum.  Prevents an entity with a genuinely tiny value
    # (relative to the leader) from rendering as an invisible
    # zero-width sliver.
    MIN_VISIBLE_BAR_FRACTION = 0.015

    # =========================================================
    # LABEL COLLISION
    # =========================================================

    MIN_LABEL_GAP = 0.72

    # Hard floor on the row gap the label solver may degrade to.
    # It is deliberately > 0: two labels sharing one row is the
    # exact defect _solve_label_positions exists to prevent, so
    # the solver must never be allowed to bottom out at zero.
    MIN_ROW_SEPARATION = 0.02

    # Largest font bump the bar-race animation applies to a label
    # for leader / overtake emphasis.  The label-fit guard fits
    # labels at base + this so the per-frame emphasis bump can
    # never re-introduce a left-edge overflow.
    LABEL_FONT_BUMP = 2

    # =========================================================
    # SHARE-OF-TOTAL CHARTS (PIE / WAFFLE)  -- Part 1 and Part 2
    #
    # A pie or waffle is only HONEST when the numbers are parts
    # of one whole.  Both renderers therefore refuse to invent a
    # total: they read the shares from the data and, when the
    # parts do not add up to 100%, the waffle shows the shortfall
    # as a grey "Rest of World" block rather than silently
    # rescaling the parts to fill the grid.
    # =========================================================

    # Entity window a part-of-whole chart may cover.  Fewer than
    # 3 slices is not a distribution; more than 6 is unreadable
    # in a 10x10 grid / on a phone.
    SHARE_MIN_ENTITIES = 3
    SHARE_MAX_ENTITIES = 6

    # 10 x 10 grid == 100 boxes, so ONE BOX is exactly ONE
    # PERCENTAGE POINT.  That identity is what makes the waffle
    # an integer-exact picture of the shares.
    WAFFLE_GRID = 10
    WAFFLE_BOXES = WAFFLE_GRID * WAFFLE_GRID

    # Grey styling for the boxes a <100% total leaves unfilled.
    REST_OF_WORLD_COLOR = "#39424F"
    REST_OF_WORLD_LABEL = "Rest of World"

    # Tolerance for "the parts add up to a whole" (percent
    # points).  Real percentage indicators carry rounding noise.
    SHARE_TOTAL_TOLERANCE = 2.0

    # ---------------------------------------------------------
    # MULTI-COLOUR BAR MODE  -- Part 4
    #
    # bar_race / top5_change historically painted every bar with
    # one rotated gradient ramp, so consecutive videos looked
    # alike.  This mode gives each bar its OWN colour from a
    # curated, mutually distinguishable 8-colour set, and is
    # chosen PROBABILISTICALLY per video so both looks appear
    # across uploads.
    # ---------------------------------------------------------

    MULTI_COLOR_CHART_TYPES = {"bar_race", "top5_change"}

    MULTI_COLOR_PROBABILITY = float(
        getattr(settings, "MULTI_COLOR_PROBABILITY", 0.35)
    )

    # Restrained brand-derived set: champagne gold leads and muted
    # slate / sage / terracotta companions follow, so the
    # alternate bar look belongs to the SAME channel as the
    # single-ramp version (no neon rainbow mode).  Kept distinct
    # from LEADER_COLOR / OVERTAKE_COLOR (which still override
    # for emphasis).
    MULTI_COLOR_PALETTE = list(design_system.CATEGORICAL_PALETTE)

    _MULTI_COLOR_MODE: bool = False

    # =========================================================
    # STEP 4 ΓÇö SHORTS LAYOUT
    # =========================================================

    CHART_LEFT = 0.37
    CHART_BOTTOM = 0.20
    CHART_WIDTH = 0.57
    CHART_HEIGHT = 0.53

    TITLE_Y = 0.935
    # Mobile legibility: label/number sizes come from config
    # (FONT_TITLE / FONT_YEAR / FONT_COUNTRY / FONT_VALUE env
    # overrides) so small text is readable on a phone screen.
    TITLE_SIZE = settings.FONT_TITLE

    YEAR_X = 0.84
    YEAR_Y = 0.805
    YEAR_SIZE = settings.FONT_YEAR

    SOURCE_Y = 0.075
    SOURCE_SIZE = 18

    COUNTRY_FONT_SIZE = settings.FONT_COUNTRY
    VALUE_FONT_SIZE = settings.FONT_VALUE

    # =========================================================
    # STEP 5 ΓÇö PACING
    # =========================================================

    TRANSITION_RATIO = 0.78

    # =========================================================
    # STEP 6 ΓÇö RANKING EMPHASIS
    # =========================================================

    SIGNIFICANT_RANK_CHANGE = 1

    OVERTAKE_EMPHASIS = 0.65

    # =========================================================
    # STEP 7 ΓÇö OPENING / CLOSING
    # =========================================================

    OPENING_SECONDS = 0.75
    CLOSING_SECONDS = 0.45

    # =========================================================
    # VALUE FORMATTER
    # =========================================================

    @staticmethod
    def _bar_width(value, max_val):
        """Bar width for one entity: the raw value (true zeros stay
        at zero), with a small visible floor so a genuinely tiny
        positive value can never render as an invisible zero-width
        sliver."""
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0
        if value <= 0:
            return 0.0
        try:
            floor = (
                float(max_val or 0.0)
                * VisualEngine.MIN_VISIBLE_BAR_FRACTION
            )
        except (TypeError, ValueError):
            floor = 0.0
        return max(value, floor)

    @staticmethod
    def _bar_width_signed(value, max_abs):
        """Signed variant for symmetric (positive/negative) charts:
        keeps tiny gains and tiny declines visible without ever
        inflating a true-zero value or flipping a bar's sign."""
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0
        if value == 0:
            return 0.0
        try:
            floor = (
                float(max_abs or 0.0)
                * VisualEngine.MIN_VISIBLE_BAR_FRACTION
            )
        except (TypeError, ValueError):
            floor = 0.0
        if value > 0:
            return max(value, floor)
        return min(value, -floor)

    @staticmethod
    def _format_value(value, indicator_name=""):

        if pd.isna(value):
            return ""

        value = float(value)

        indicator = str(
            indicator_name
        ).lower()

        if (
            "%" in indicator
            or "percent" in indicator
        ):
            return f"{value:.1f}%"

        if (
            "perceptions index" in indicator
            or "index score" in indicator
        ):
            # Survey-based index scores (0-100): NEVER compacted
            # with K/B/M suffixes -- display as a plain integer.
            return f"{value:.0f}"

        if "life expectancy" in indicator:
            return f"{value:.1f}"

        if "population" in indicator:

            if abs(value) >= 1_000_000_000:
                return (
                    f"{value / 1_000_000_000:.1f}B"
                )

            if abs(value) >= 1_000_000:
                return (
                    f"{value / 1_000_000:.1f}M"
                )

            if abs(value) >= 1_000:
                return (
                    f"{value / 1_000:.1f}K"
                )

            return f"{value:,.0f}"

        if (
            "gdp" in indicator
            or "current us$" in indicator
        ):

            # Sign OUTSIDE the currency symbol: "-$1.4T", never
            # "$-1.4T" (f"${negative:.1f}" put the minus after the
            # dollar sign -- measured on a top5 decline render).
            sign = "-" if value < 0 else ""
            magnitude = abs(value)

            if magnitude >= 1_000_000_000_000:
                return (
                    f"{sign}${magnitude / 1_000_000_000_000:.1f}T"
                )

            if magnitude >= 1_000_000_000:
                return (
                    f"{sign}${magnitude / 1_000_000_000:.1f}B"
                )

            if magnitude >= 1_000_000:
                return (
                    f"{sign}${magnitude / 1_000_000:.1f}M"
                )

            return f"{sign}${magnitude:,.0f}"

        if (
            "co2" in indicator
            or "emission" in indicator
        ):

            if abs(value) >= 1_000_000:
                return (
                    f"{value / 1_000_000:.1f}M"
                )

            if abs(value) >= 1_000:
                return (
                    f"{value / 1_000:.1f}K"
                )

            return f"{value:,.0f}"

        if abs(value) >= 1_000_000_000:
            return (
                f"{value / 1_000_000_000:.1f}B"
            )

        if abs(value) >= 1_000_000:
            return (
                f"{value / 1_000_000:.1f}M"
            )

        if abs(value) >= 1_000:
            return (
                f"{value / 1_000:.1f}K"
            )

        if abs(value) < 100:
            return f"{value:.1f}"

        return f"{value:,.0f}"

    # =========================================================
    # EASING
    # =========================================================

    @staticmethod
    def ease_in_out(t):

        t = max(
            0.0,
            min(
                1.0,
                float(t)
            )
        )

        return (
            t * t * (3.0 - 2.0 * t)
        )

    # =========================================================
    # STEP 5 ΓÇö PACED TRANSITION
    # =========================================================

    @staticmethod
    def get_transition_progress(
        year_progress
    ):

        year_progress = max(
            0.0,
            min(
                1.0,
                float(year_progress)
            )
        )

        transition_ratio = (
            VisualEngine.TRANSITION_RATIO
        )

        hold_total = (
            1.0
            - transition_ratio
        )

        hold_before = (
            hold_total * 0.35
        )

        transition_end = (
            hold_before
            + transition_ratio
        )

        if year_progress <= hold_before:
            return 0.0

        if year_progress >= transition_end:
            return 1.0

        movement_progress = (
            year_progress
            - hold_before
        ) / transition_ratio

        return VisualEngine.ease_in_out(
            movement_progress
        )

    # =========================================================
    # LABEL COLLISION SOLVER
    # =========================================================

    @staticmethod
    def _solve_label_positions(
        raw_positions,
        min_gap,
        min_y,
        max_y
    ):

        """Push N labels apart so that every one owns a distinct row.

        Bars ride the raw interpolated rank and are allowed to
        cross; LABELS are what the viewer actually reads, so they
        are de-collided here.  Three invariants are guaranteed:

          1. every label lands inside [min_y, max_y];
          2. no two labels share a row (gap >= the effective gap);
          3. the original vertical ordering is preserved.

        DEFECT FIXED -- "two countries, one name": the previous
        version walked down the stack enforcing ``min_gap`` and
        then clamped every label with ``min(y, max_y)``.  That
        clamp silently DISCARDED the gap the loop had just
        enforced: any transition that compressed the stack past
        the bottom of the axis parked two or more labels on the
        IDENTICAL row (measured: gaps of 0.06 against a required
        0.72 for a 4-bar full reversal).  The "bottom correction"
        that followed could therefore never fire -- it was dead
        code guarded by a condition the clamp made unreachable.

        The ladder is now laid out WITHOUT the destructive clamp,
        and is built so it fits by construction rather than by
        correction.  Each label is placed at

            max(its own raw row, one gap below the previous)
            capped at (bottom of window - gap for every row below)

        The cap is what makes the fit provable: because
        (count - 1) * effective_gap <= span, the very first label
        is guaranteed room for the whole ladder, and every later
        label is guaranteed room for the rows still to come.  No
        corrective shift is ever needed -- which is what makes the
        row guarantee exact.  (The obvious alternative, shifting
        the finished ladder to fit the window, cannot work: a
        shift that fits max_y can push the top label out through
        min_y, and the reverse correction undoes the first.)

        If the caller demands a gap larger than the window can
        hold, the gap degrades -- but never below
        MIN_ROW_SEPARATION, so distinct rows are still guaranteed.
        """

        if not raw_positions:
            return []

        count = len(raw_positions)

        span = float(max_y) - float(min_y)

        low = float(min_y)
        high = float(max_y)

        # N labels need N - 1 gaps between them inside the span.
        if count > 1 and span > 0:

            usable_gap = span / (count - 1)

        else:

            usable_gap = float(min_gap)

        effective_gap = max(
            min(float(min_gap), usable_gap),
            min(VisualEngine.MIN_ROW_SEPARATION, usable_gap),
        )

        # Sorted by desired row; each raw clamped into the window.
        indexed = sorted(
            enumerate(raw_positions),
            key=lambda item: float(item[1]),
        )

        solved = {}

        previous = None

        for position, (index, raw_y) in enumerate(
            indexed
        ):

            # Rows still to place BELOW this one.
            room_left = (count - 1 - position) * effective_gap

            own_row = max(
                min(float(raw_y), high),
                low,
            )

            if previous is None:
                candidate = own_row
            else:
                candidate = max(
                    own_row,
                    previous + effective_gap,
                )

            # Keep enough room below for the remaining labels.
            solved[index] = min(
                candidate,
                high - room_left,
            )

            previous = solved[index]

        return [
            solved[index]
            for index in range(count)
        ]

    # =========================================================
    # LABEL FIT GUARD
    # =========================================================

    # OffsetImage zoom used for flag icons (keep in sync with
    # the zoom passed to OffsetImage in _get_flag_image).
    FLAG_ZOOM = 0.32

    @staticmethod
    def _constrain_labels_in_frame(
        fig,
        ax,
        texts,
        left_margin_px: float = 0.0,
        right_margin_px: float = 0.0,
        font_bump: float = 0.0,
        min_font_pt: float = 12.0,
        max_shift_frac: float = 0.12,
    ) -> list:
        """Keep every text's box inside the FIGURE on the
        requested side(s); return the base font sizes.

        This is the ONE safe-boundary implementation.  It backs
        bar_race's flag-aware left-edge fit, slope's two-sided
        fit, and (via _max_label_anchor_data_x) the moving
        labels of line / area -- deliberately three chart types,
        one algorithm.

        Order of operations, cheapest visual cost first:
          1. shift/narrow the axes inward, capped at
             max_shift_frac of the figure width, split between the
             sides in proportion to how much each one overflows;
          2. shrink ONLY the labels that still overflow, one point
             at a time, never below min_font_pt.

        `font_bump` pre-sizes every label at the LARGEST size the
        caller will later apply, so per-frame emphasis can never
        re-introduce an overflow.

        Returns a list of base font sizes parallel to `texts`.
        """

        if not texts:
            return []

        try:
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
        except Exception:
            return [
                float(text.get_fontsize())
                for text in texts
            ]

        fig_w_px = (
            float(fig.get_figwidth())
            * float(fig.dpi)
        )

        right_limit = fig_w_px - float(right_margin_px)

        sizes = [
            max(
                min_font_pt,
                float(text.get_fontsize())
                + float(font_bump),
            )
            for text in texts
        ]

        def _apply(applied_sizes):

            for text, size in zip(texts, applied_sizes):
                text.set_fontsize(size)

            try:
                fig.canvas.draw()
            except Exception:
                pass

        def _edges(index):

            try:
                box = texts[index].get_window_extent(
                    renderer=renderer
                )
                return float(box.x0), float(box.x1)
            except Exception:
                return None

        def _overflow(index):

            edges = _edges(index)

            if edges is None:
                return 0.0, 0.0

            x0, x1 = edges

            return (
                max(0.0, float(left_margin_px) - x0),
                max(0.0, x1 - right_limit),
            )

        _apply(sizes)

        need_left = 0.0
        need_right = 0.0

        for index in range(len(texts)):

            left, right = _overflow(index)

            need_left = max(need_left, left)
            need_right = max(need_right, right)

        total_need = need_left + need_right

        if total_need > 0:

            shift_px = min(
                total_need,
                max_shift_frac * fig_w_px,
            )

            share_left = need_left / total_need
            share_right = need_right / total_need

            dx_left = (
                share_left * shift_px / fig_w_px
            )
            dx_right = (
                share_right * shift_px / fig_w_px
            )

            box = ax.get_position()

            ax.set_position(
                [
                    box.x0 + dx_left,
                    box.y0,
                    max(
                        0.05,
                        box.width - dx_left - dx_right,
                    ),
                    box.height,
                ]
            )

            _apply(sizes)

        # Shrink ONLY what still overflows after the axes shift.
        for index in range(len(texts)):

            for _ in range(60):

                if sizes[index] <= min_font_pt:
                    break

                left, right = _overflow(index)

                if left <= 0 and right <= 0:
                    break

                sizes[index] = max(
                    min_font_pt,
                    sizes[index] - 1.0,
                )

                _apply(sizes)

        return [
            max(min_font_pt, size)
            for size in sizes
        ]

    @staticmethod
    def _fit_labels_in_frame(
        fig,
        ax,
        texts,
        extra_left_px: float = 48.0,
        font_bump: float = 0.0,
        min_font_pt: float = 12.0,
    ) -> list:
        """bar_race's flag-aware LEFT-edge fit.

        Thin wrapper over _constrain_labels_in_frame (the single
        safe-boundary implementation) that reserves the room a
        flag icon needs to the left of its label.  Behaviour is
        unchanged from the original flag-aware guard.
        """
        # Room the flag icon needs to the LEFT of a label:
        # icon width (styled flag * zoom) plus the 6pt offset
        # gap used by _attach_country_flag, with margin.
        flag_reserve_px = (
            float(VisualEngine._FLAG_SIZE[0])
            * VisualEngine.FLAG_ZOOM
            + extra_left_px
        )

        fit_sizes = VisualEngine._constrain_labels_in_frame(
            fig,
            ax,
            texts,
            left_margin_px=flag_reserve_px,
            right_margin_px=0.0,
            font_bump=font_bump,
            min_font_pt=min_font_pt,
        )

        # Hand back the BASE sizes: what the caller must use as
        # the base of its own `base + emphasis` arithmetic.
        base_sizes = [
            max(min_font_pt, size - float(font_bump))
            for size in fit_sizes
        ]

        for text, size in zip(texts, base_sizes):
            text.set_fontsize(size)

        try:
            fig.canvas.draw()
        except Exception:
            pass

        return base_sizes

    @staticmethod
    def _reserve_value_headroom(
        fig,
        ax,
        value_texts,
        max_val: float,
        right_margin_px: float = 28.0,
        max_expand_frac: float = 0.30,
    ) -> float:
        """Part 2 DEFECT B guard: keep bar-race/top5 numeric labels inside.

        Entity-label fit (Part 1) protects the LEFT edge; nothing
        protected the RIGHT: the largest value text sits at
        ``bar_width(max) + gap`` so e.g. ``36.7M`` ran ~41px past a
        1080px canvas.  This measures the REAL rendered width of
        every value text at its CURRENT string, widens the x-limit
        only as much as needed (bounded by max_expand_frac so the
        chart never collapses), and returns the (possibly new)
        max_val.  Returns the input unchanged when nothing
        overflows, so normal charts are pixel-identical.
        """

        if not value_texts:
            return max_val

        try:
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
        except Exception:
            return max_val

        try:
            fig_w_px = (
                float(fig.get_figwidth()) * float(fig.dpi)
            )
        except Exception:
            return max_val

        right_limit = fig_w_px - float(right_margin_px)
        worst = 0.0

        for text in value_texts:
            try:
                box = text.get_window_extent(renderer=renderer)
                worst = max(worst, float(box.x1) - right_limit)
            except Exception:
                continue

        if worst <= 0:
            return max_val

        try:
            base = float(max_val)
        except (TypeError, ValueError):
            return max_val

        if base <= 0:
            return max_val

        # Convert the pixel overflow back into data units via the
        # current transform, then grow the limit just past it.
        try:
            px_per_data = (
                ax.transData.transform((base, 0.0))[0]
                - ax.transData.transform((0.0, 0.0))[0]
            ) / base
        except Exception:
            return max_val

        if px_per_data <= 0:
            return max_val

        need_data = worst / px_per_data * 1.05
        cap = base * (1.0 + float(max_expand_frac))
        grown = min(base + need_data, cap)

        try:
            lo, _hi = ax.get_xlim()
            ax.set_xlim(lo, grown)
        except Exception:
            return max_val

        return grown

    @staticmethod
    def _max_label_anchor_data_x(
        fig,
        ax,
        texts,
        right_margin_px: float = 24.0,
    ) -> float:
        """Largest DATA-x a left-anchored moving label may sit at
        without its text running past the figure's right edge.

        line and area park the country name on the moving leading
        edge of the series, so as the sweep advances the anchor
        reaches the right side of the axes and a long name runs
        off-canvas (measured before the fix: "Democratic Republic
        of the Congo" ended at x1 = 1478px on a 1080px frame).

        These labels hold a CONSTANT string at a CONSTANT font
        size, so their pixel width is fixed: measure it once,
        convert the pixel budget back into data coordinates, and
        clamp the anchor in the render loop.  Short labels never
        reach the clamp, so their appearance is unchanged.
        """

        if not texts:
            return float("inf")

        try:
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
        except Exception:
            return float("inf")

        fig_w_px = (
            float(fig.get_figwidth())
            * float(fig.dpi)
        )

        widest = 0.0

        for text in texts:

            try:
                box = text.get_window_extent(
                    renderer=renderer
                )
                widest = max(
                    widest,
                    float(box.x1) - float(box.x0),
                )
            except Exception:
                continue

        if widest <= 0:
            return float("inf")

        budget_px = fig_w_px - float(right_margin_px) - widest

        if budget_px <= 0:
            # Even a zero-width anchor would overflow: fall back
            # to the axes' own right edge so behaviour degrades
            # to "as good as possible" rather than nonsense.
            budget_px = 0.0

        try:
            x_data, _ = ax.transData.inverted().transform(
                (budget_px, 0.0)
            )
            return float(x_data)
        except Exception:
            return float("inf")

    @staticmethod
    def _is_year_axis(labels) -> bool:
        """True when every x label is a whole year (1900..2100).

        Used to decide whether the x-axis may be pinned to
        INTEGER year ticks.  The default matplotlib locator picked
        half-year steps on year ranges, so the axis printed
        "2019.0  2019.5  2020.0 ...".  Any axis that is not made
        of whole years (generic numeric x values, non-year data)
        returns False and keeps the default locator untouched.
        """

        values = list(labels)

        if len(values) < 2:
            return False

        try:
            numbers = [float(value) for value in values]
        except (TypeError, ValueError):
            return False

        for value in numbers:

            if not np.isfinite(value):
                return False

            if abs(value - round(value)) > 1e-9:
                return False

            if not (1900 <= value <= 2100):
                return False

        return True

    # =========================================================
    # PREMIUM GRADIENT SYSTEM (CSS-style linear gradients)
    # =========================================================

    _GRADIENT_CACHE = {}

    @staticmethod
    def _hex_to_rgb01(hex_color):

        h = str(hex_color).lstrip("#")

        return np.array(
            [
                int(h[0:2], 16),
                int(h[2:4], 16),
                int(h[4:6], 16),
            ],
            dtype=float
        ) / 255.0

    @staticmethod
    def _shade(hex_color, amount):

        """
        Lighten (amount > 0) or darken (amount < 0)
        a hex color.
        """

        rgb = VisualEngine._hex_to_rgb01(hex_color)

        if amount >= 0:
            rgb = rgb + (1.0 - rgb) * amount
        else:
            rgb = rgb * (1.0 + amount)

        rgb = np.clip(rgb, 0.0, 1.0)

        return "#{:02X}{:02X}{:02X}".format(
            int(round(rgb[0] * 255)),
            int(round(rgb[1] * 255)),
            int(round(rgb[2] * 255)),
        )

    @staticmethod
    def _bar_gradient(base_hex):

        """
        Build a horizontal linear gradient for a bar:

            deep shade at the base
            ΓåÆ luminous shade at the tip

        like a premium CSS linear-gradient fill.
        Results are cached per color.
        """

        cached = (
            VisualEngine._GRADIENT_CACHE.get(
                base_hex
            )
        )

        if cached is not None:
            return cached

        start = VisualEngine._hex_to_rgb01(
            VisualEngine._shade(base_hex, -0.38)
        )

        end = VisualEngine._hex_to_rgb01(
            VisualEngine._shade(base_hex, 0.22)
        )

        t = np.linspace(
            0.0,
            1.0,
            256
        ).reshape(1, -1, 1)

        gradient = (
            (1.0 - t) * start.reshape(1, 1, 3)
            + t * end.reshape(1, 1, 3)
        )

        VisualEngine._GRADIENT_CACHE[base_hex] = gradient

        return gradient

    # =========================================================
    # COLOR SYSTEM
    # =========================================================

    # ---------------------------------------------------------
    # THEMED PALETTE ROTATION (config-driven)
    #
    # One fixed metallic ramp made every video look the same.
    # Palettes are defined in app.config settings.CHART_PALETTES
    # (env-overridable JSON).  select_palette() picks the active
    # palette ONCE PER VIDEO: a themed palette when the title /
    # topic matches (economy / population / military / technology
    # keywords), otherwise a cursor rotation through all palettes
    # so consecutive uploads look visually distinct.
    # ---------------------------------------------------------

    _PALETTES: dict = {}
    _PALETTES_LOADED: bool = False
    _PALETTE_CURSOR: int = 0
    _ACTIVE_PALETTE: list = []
    _ACTIVE_PALETTE_NAME: str = ""

    # Palette key -> topic keyword stems matched against the
    # video title/topic/category (lowercase, substring match).
    _PALETTE_TOPIC_KEYWORDS: dict = {
        "economy": (
            "econom", "gdp", "inflation", "cpi", "richest",
            "poorest", "billionaire", "debt", "income", "revenue",
            "net worth", "money", "trade", "export", "import",
            "gold", "budget", "salary", "wage", "company",
            "companies", "brand", "bank",
        ),
        "population": (
            "population", "people", "urban", "migration",
            "birth", "fertility", "life expectancy", "cities",
            "city", "megacity",
        ),
        "military": (
            "militar", "army", "war", "soldier", "nuclear",
            "defense", "defence", "weapon", "tank", "fighter",
            "navy", "air force", "missile", "drone",
        ),
        "technology": (
            "technolog", "internet", " ai ", "ai-", "tech",
            "coding", "program", "software", "robot", "youtube",
            "instagram", "tiktok", "gaming", "gamer", "esports",
            "smartphone", "app",
        ),
    }

    @classmethod
    def _load_palettes(cls):
        """Parse settings.CHART_PALETTES once (JSON dict of lists)."""

        if cls._PALETTES_LOADED:
            return

        cls._PALETTES_LOADED = True

        import json

        try:
            parsed = json.loads(settings.CHART_PALETTES)
            if isinstance(parsed, dict):
                cls._PALETTES = {
                    str(key).strip().lower(): [
                        str(color) for color in values
                    ]
                    for key, values in parsed.items()
                    if isinstance(values, (list, tuple)) and values
                }
        except (ValueError, TypeError, AttributeError):
            cls._PALETTES = {}

        if not cls._PALETTES:
            # Fallback: the historical fixed metallic ramp.
            cls._PALETTES = {
                "default": [
                    "#E3BC6B", "#C89B45", "#AD7F35", "#93682C",
                    "#7A5526", "#62441F", "#4C351A", "#3B2915",
                ],
            }

    @classmethod
    def select_palette(cls, script=None):
        """Choose the active bar palette for ONE video.

        1. Themed palette when title/topic/category matches a
           palette keyword group.
        2. Otherwise rotate the cursor through every palette so
           consecutive videos differ.

        Returns the active palette list (also stored on
        _ACTIVE_PALETTE for _get_bar_color).
        """

        cls._load_palettes()

        fallback = (
            cls._PALETTES.get("default")
            or next(iter(cls._PALETTES.values()))
        )

        if not getattr(settings, "PALETTE_ROTATION_ENABLED", True):
            cls._ACTIVE_PALETTE = fallback
            cls._ACTIVE_PALETTE_NAME = "default"
            return fallback

        haystack = ""

        if script is not None:
            for attr in ("title", "topic", "category", "topic_family"):
                value = getattr(script, attr, "")
                haystack += " " + str(value or "").lower()

        # Themed match first.
        for key, keywords in cls._PALETTE_TOPIC_KEYWORDS.items():
            palette = cls._PALETTES.get(key)
            if not palette:
                continue
            if any(k in haystack for k in keywords):
                cls._ACTIVE_PALETTE = palette
                cls._ACTIVE_PALETTE_NAME = key
                return palette

        # Cursor rotation (skip the "default" entry so themed
        # colors actually cycle).
        names = [
            name for name in cls._PALETTES if name != "default"
        ] or list(cls._PALETTES)

        name = names[cls._PALETTE_CURSOR % len(names)]
        cls._PALETTE_CURSOR += 1

        cls._ACTIVE_PALETTE = cls._PALETTES[name]
        cls._ACTIVE_PALETTE_NAME = name

        return cls._ACTIVE_PALETTE

    @staticmethod
    def _select_bar_coloring(chart_type):
        """Choose the per-bar colouring MODE for ONE video.

        Called once per render_scenes() run for EVERY chart
        type, so the flag is always explicitly set (never left
        over from a previous video):

          * only bar_race / top5_change are eligible at all;
          * among those, the multi-colour look is chosen
            PROBABILISTICALLY (settings.MULTI_COLOR_PROBABILITY,
            default 0.35) so the two looks genuinely mix across
            consecutive uploads instead of one of them
            disappearing.

        Returns True when the multi-colour mode is active.
        """

        eligible = (
            str(chart_type).strip().lower()
            in VisualEngine.MULTI_COLOR_CHART_TYPES
        )

        if not eligible:
            VisualEngine._MULTI_COLOR_MODE = False
            return False

        try:
            probability = float(
                VisualEngine.MULTI_COLOR_PROBABILITY
            )
        except (TypeError, ValueError):
            probability = 0.35

        probability = max(0.0, min(1.0, probability))

        VisualEngine._MULTI_COLOR_MODE = bool(
            random.random() < probability
        )

        return VisualEngine._MULTI_COLOR_MODE

    @staticmethod
    def _get_bar_color(
        rank,
        is_current_leader=False,
        is_overtake=False
    ):

        if is_overtake:
            return VisualEngine.OVERTAKE_COLOR

        if is_current_leader:
            return VisualEngine.LEADER_COLOR

        # -----------------------------------------------------
        # MULTI-COLOUR MODE (Part 4): one distinct colour per
        # bar, from the curated palette, instead of the single
        # rotated gradient ramp.  Leader / overtake emphasis
        # above still wins, so the story beats stay readable.
        # -----------------------------------------------------

        if VisualEngine._MULTI_COLOR_MODE:

            palette = VisualEngine.MULTI_COLOR_PALETTE

            if palette:

                rank = max(
                    0,
                    min(
                        int(rank),
                        len(palette) - 1
                    )
                )

                return palette[rank]

        # Active themed palette for THIS video (rotated once per
        # render by select_palette; falls back to a lazy pick when
        # a renderer was called directly).
        palette = (
            VisualEngine._ACTIVE_PALETTE
            or VisualEngine.select_palette()
        )

        rank = max(
            0,
            min(
                int(rank),
                len(palette) - 1
            )
        )

        return palette[rank]

    # =========================================================
    # STEP 6 ΓÇö FIND OVERTAKES
    # =========================================================

    @staticmethod
    def _find_overtakes(
        current_ranks,
        next_ranks,
        countries
    ):

        overtakes = set()

        for country in countries:

            current_rank = float(
                current_ranks[country]
            )

            next_rank = float(
                next_ranks[country]
            )

            if (
                current_rank
                - next_rank
                >= VisualEngine.SIGNIFICANT_RANK_CHANGE
            ):

                overtakes.add(
                    country
                )

        return overtakes

    # =========================================================
    # INDEX NORMALIZATION
    # =========================================================

    @staticmethod
    def _normalize_index(data):

        """
        Safely convert the DataFrame index into normal
        string labels.

        MultiIndex rows arrive from the providers as
        (code/identifier, human-readable name) pairs:

            ("4", "PC")
            ("USA", "United States")
            ("IND", "India")

        becomes:

            "PC"
            "United States"
            "India"

        The LAST level is always the human-readable display name --
        the first level is the internal code, and using it as the
        chart label put raw RAWG platform ids (4, 187, 21, ...) on
        gaming charts instead of "PC", "PlayStation 5", etc.
        """

        if isinstance(
            data.index,
            pd.MultiIndex
        ):

            normalized = []

            for item in data.index:

                if len(item) == 0:
                    normalized.append("")
                    continue

                # The LAST level holds the human-readable
                # display name; the first level is the internal
                # code/identifier.
                label = item[-1] if len(item) >= 2 else item[0]

                if (
                    label is None
                    or pd.isna(label)
                ):
                    label = ""

                label = str(
                    label
                ).strip()

                normalized.append(
                    label
                )

            data.index = pd.Index(
                normalized,
                dtype="object"
            )

        else:

            data.index = pd.Index(
                [
                    ""
                    if (
                        value is None
                        or pd.isna(value)
                    )
                    else str(value).strip()
                    for value in data.index
                ],
                dtype="object"
            )

        # Remove empty labels.
        valid_mask = [
            bool(
                str(value).strip()
            )
            for value in data.index
        ]

        data = data.loc[
            valid_mask
        ]

        # Remove duplicate country names.
        # Keep the first occurrence.
        if data.index.duplicated().any():

            data = data[
                ~data.index.duplicated(
                    keep="first"
                )
            ]

        return data

    # =========================================================
    # BAR RACE RENDER
    # =========================================================


    # ---------------------------------------------------------
    # CHECKPOINT-YEAR SUBSAMPLING (Issue 5)
    #
    # YEAR_WINDOW_POOL now reaches 15-year spans.  Sweeping every
    # intermediate year of a 12-15 column window would compress
    # each transition far below the pacing the 18-30s band was
    # tuned for (the exact path back to Issue 1's rushed
    # narration).  Windows wider than 10 columns are therefore
    # animated through evenly spaced CHECKPOINT years -- start,
    # three midpoints, end -- always including the first /
    # middle / last years the script engine narrates.  Windows
    # of 10 or fewer columns keep the verified behaviour.
    # ---------------------------------------------------------

    @staticmethod
    def checkpoint_years(years):

        count = len(years)

        if count <= 10:
            return list(years)

        picks = sorted(
            {0, count // 4, count // 2, 3 * count // 4, count - 1}
        )

        return [years[i] for i in picks]


    @staticmethod
    def render_bar_race(
        script,
        data: pd.DataFrame,
        output_dir: str
    ):

        if data.empty:

            raise ValueError(
                "No data provided for visual rendering."
            )

        os.makedirs(
            output_dir,
            exist_ok=True
        )

        print(
            "≡ƒÄ¿ Rendering Step 6 + Step 7 "
            "premium Shorts animation..."
        )

        # =====================================================
        # CLEAN DATA
        # =====================================================

        data = data.copy()

        # -----------------------------------------------------
        # FIX:
        # World Bank can return a MultiIndex.
        #
        # DO NOT use:
        #
        # data.index.astype(str)
        #
        # because pandas raises:
        #
        # TypeError: Setting a MultiIndex dtype to anything
        # other than object is not supported
        # -----------------------------------------------------

        data = VisualEngine._normalize_index(
            data
        )

        # -----------------------------------------------------
        # Column labels -> numeric years.  Handles plain years,
        # the World Bank "YR" form, AND season labels like
        # "2024-25" / "2024/25" / "2025-26 (in progress)" via the
        # shared coerce_year_label helper (season labels resolve
        # to their starting year).  Columns with no plausible
        # year are skipped; duplicate years (e.g. "2024" plus
        # "2024-25") keep only the first occurrence.
        # -----------------------------------------------------

        valid_original_columns = []
        seen_years = set()

        for column in data.columns:

            year = coerce_year_label(column)

            if year is None or year in seen_years:
                continue

            seen_years.add(year)

            valid_original_columns.append(
                (
                    column,
                    year,
                )
            )

        # If no valid year columns remain,
        # fail clearly instead of producing a
        # confusing matplotlib error.

        if not valid_original_columns:

            raise ValueError(
                "No valid year columns found "
                "for visual rendering."
            )

        data = data[
            [
                original
                for original, _
                in valid_original_columns
            ]
        ]

        data.columns = [
            year
            for _, year
            in valid_original_columns
        ]

        data = data.reindex(
            sorted(
                data.columns
            ),
            axis=1
        )

        data = data.dropna(
            how="all"
        )

        data = data.dropna(
            axis=0,
            how="all"
        )

        if data.empty:

            raise ValueError(
                "No usable data after cleaning."
            )

        years = list(
            data.columns
        )

        # CHECKPOINT SUBSAMPLING (Issue 5): wide windows animate
        # through evenly spaced checkpoint years (see
        # checkpoint_years) so pacing never compresses; <=10
        # columns are untouched.
        years = VisualEngine.checkpoint_years(years)

        # =====================================================
        # MOBILE BAR CAP
        # =====================================================

        # Mobile legibility: 6-8 bars have cramped labels that
        # fail on a phone at a glance.  The budget comes from
        # compute_bar_cap (CHART_MAX_BARS, vs-title override,
        # MAX_CHART_ENTITIES ceiling) and the selection from
        # cap_display_index -- BOTH shared with
        # app/qc/entity_guard.py so the pre-render validation
        # simulates exactly what this renderer draws.
        #
        # FOCUS-AWARE (Issue 2 fix): entities the script names
        # (scene highlight_countries / title) are guaranteed a
        # bar even when their peak value ranks below the value
        # leaders -- the published India video dropped its own
        # subject here.
        #
        # `countries` is the pre-cap label list: the index was
        # already normalised to display names at line ~1085, and
        # its LENGTH is what decides whether the cap runs at all.
        # (A missing assignment here raised UnboundLocalError,
        # which aborted every bar-race render.)
        countries = (
            VisualEngine._index_display_labels(data)
        )

        MAX_BARS = (
            VisualEngine.compute_bar_cap(script)
        )

        focus_entities = (
            VisualEngine._resolve_focus_entities(
                script,
                data,
            )
        )

        if len(countries) > MAX_BARS:

            kept_raw = (
                VisualEngine.cap_display_index(
                    data,
                    MAX_BARS,
                    focus=focus_entities,
                )
            )

            data = data.loc[
                kept_raw
            ]

        countries = (
            VisualEngine
            ._index_display_labels(data)
        )

        print(
            "≡ƒôè Chart bars (focus-guaranteed): "
            f"{', '.join(countries)}"
        )

        if focus_entities:

            missing_focus = [
                label
                for label in focus_entities
                if label not in countries
            ]

            if missing_focus:

                raise ValueError(
                    "Focus entities missing from the "
                    f"rendered bars: {missing_focus} "
                    f"(rendered: {countries})."
                )

        data = data.ffill(
            axis=1
        ).bfill(
            axis=1
        )

        # Make sure all values are numeric.
        # Invalid values become NaN.

        for column in data.columns:

            data[column] = pd.to_numeric(
                data[column],
                errors="coerce"
            )

        data = data.dropna(
            how="all"
        )

        if data.empty:

            raise ValueError(
                "No numeric World Bank data "
                "available after cleaning."
            )

        countries = data.index.tolist()

        # =====================================================
        # FLAGS ΓÇö fetch every country's flag up-front so the
        # per-label attachment below never triggers a mid-render
        # network burst (which flagcdn rate-limits, silently
        # dropping all flags after the first).
        # =====================================================

        VisualEngine.prefetch_flags(countries)

        # =====================================================
        # RANKINGS
        # =====================================================

        ranks_df = data.rank(
            method="first",
            ascending=False,
            axis=0
        )

        # =====================================================
        # FIGURE
        # =====================================================

        plt.rcParams[
            "figure.facecolor"
        ] = VisualEngine.BG_COLOR

        plt.rcParams[
            "axes.facecolor"
        ] = VisualEngine.BG_COLOR

        plt.rcParams[
            "text.color"
        ] = VisualEngine.TEXT_COLOR

        plt.rcParams[
            "font.family"
        ] = "DejaVu Sans"

        fig = plt.figure(
            figsize=(10.8, 19.2),
            dpi=100
        )

        # =====================================================
        # CHART
        # =====================================================

        ax = fig.add_axes(
            [
                VisualEngine.CHART_LEFT,
                VisualEngine.CHART_BOTTOM,
                VisualEngine.CHART_WIDTH,
                VisualEngine.CHART_HEIGHT
            ]
        )

        ax.set_facecolor(
            VisualEngine.BG_COLOR
        )

        for spine in ax.spines.values():
            spine.set_visible(False)

        ax.set_xticks([])
        ax.set_yticks([])

        # Restrained depth behind the data (same treatment as
        # _create_figure): soft figure-space glows at zorder 0,
        # tinted by the active topic ramp.
        design_system.apply_atmosphere(
            ax,
            fig,
            (
                VisualEngine._ACTIVE_PALETTE
                or [design_system.BRAND_GOLD]
            )[0],
        )

        # =====================================================
        # VIDEO TIMING (computed early: needed by the
        # background pulse below) -- audio-synced when the real
        # narration length was provided to render_scenes().
        # =====================================================

        video_duration = (
            VisualEngine._effective_duration(
                script
            )
        )

        total_frames = int(
            video_duration
            * VisualEngine.FPS
        )

        # =====================================================
        # ENHANCED BACKGROUND: gradient + vignette
        # =====================================================

        VisualEngine._draw_background(
            fig,
            ax,
            pulse_frame=0,
            total_frames=total_frames
        )

        # =====================================================
        # GRID LINES (animated fade-in)
        # =====================================================

        ax.grid(
            True,
            axis="x",
            color=VisualEngine.GRID_COLOR,
            alpha=0.35,
            linewidth=1.0
        )

        max_val = float(
            data.max().max()
        )


        if max_val <= 0:
            max_val = 1

        max_val *= 1.18

        ax.set_xlim(
            0,
            max_val
        )

        # -----------------------------------------------------
        # VERTICAL SPACING (entity-count aware)
        #
        # Bars sit on integer rank slots, so a slot's pixel
        # height is axes_height / ylim_span.  With the span
        # fixed to exactly N units, a 3-entity chart inflated
        # every slot (bars AND gaps) by 33% vs the 4-entity
        # look -- sparse, oversized bars.  Normalize the slot
        # size to the 4-entity reference and center the
        # content: the extra span is split evenly as
        # top/bottom padding.
        # -----------------------------------------------------

        n_bars = len(countries)

        reference_span = 4 if n_bars >= 3 else 3

        extra_span = max(0.0, reference_span - n_bars)

        ax.set_ylim(
            -0.5 - extra_span / 2.0,
            n_bars - 0.5 + extra_span / 2.0,
        )

        ax.invert_yaxis()

        # =====================================================
        # INITIAL RANKS
        # =====================================================

        first_year = years[0]

        initial_ranks = ranks_df[
            first_year
        ]

        # =====================================================
        # BARS
        # =====================================================

        bars = []

        for country in countries:

            rank = (
                int(
                    initial_ranks[country]
                )
                - 1
            )

            value = float(
                data.loc[
                    country,
                    first_year
                ]
            )

            color = (
                VisualEngine
                ._get_bar_color(
                    rank,
                    is_current_leader=(
                        rank == 0
                    )
                )
            )

            # Premium CSS-style gradient bar
            bar = ax.imshow(
                VisualEngine._bar_gradient(
                    color
                ),
                extent=[
                    0,
                    VisualEngine._bar_width(value, max_val),
                    rank
                    - VisualEngine.BAR_HEIGHT / 2,
                    rank
                    + VisualEngine.BAR_HEIGHT / 2,
                ],
                origin="lower",
                aspect="auto",
                interpolation="bilinear",
                zorder=2
            )

            bars.append(
                bar
            )

        # =====================================================
        # TEXT
        # =====================================================

        value_texts = []
        name_texts = []

        for country in countries:

            rank = (
                int(
                    initial_ranks[country]
                )
                - 1
            )

            value_text = ax.text(
                0,
                rank,
                "",
                va="center",
                ha="left",
                color=VisualEngine.TEXT_COLOR,
                fontsize=VisualEngine.VALUE_FONT_SIZE,
                fontweight="bold",
                clip_on=False
            )

            value_text.set_path_effects(
                design_system.editorial_text_effects(linewidth=2.0)
            )

            value_texts.append(
                value_text
            )

            name_text = ax.text(
                -max_val * 0.055,
                rank,
                country,
                va="center",
                ha="right",
                color=VisualEngine.TEXT_COLOR,
                fontsize=VisualEngine.COUNTRY_FONT_SIZE,
                fontweight="bold",
                clip_on=False
            )

            name_text.set_path_effects(
                design_system.editorial_text_effects(linewidth=2.0)
            )

            name_texts.append(
                name_text
            )

        # ---------------------------------------------
        # LABEL FIT GUARD: long names ("Turks and Caicos
        # Islands") previously extended past the left frame
        # edge -- clipping the text and pushing the flag
        # icon entirely off-canvas.  Measure the rendered
        # labels and shift the axes right by the overflow
        # BEFORE attaching flags (the flag anchors off the
        # post-shift extents).
        #
        # The guard RETURNS the fitted font sizes: update()
        # re-applies a font size on every frame, so the fitted
        # sizes are the only thing keeping a long label on
        # screen.  They are fitted at base + LABEL_FONT_BUMP so
        # the per-frame leader/overtake emphasis is safe too.
        # ---------------------------------------------

        label_base_fonts = None

        try:
            label_base_fonts = (
                VisualEngine._fit_labels_in_frame(
                    fig,
                    ax,
                    name_texts,
                    font_bump=(
                        VisualEngine
                        .LABEL_FONT_BUMP
                    ),
                )
            )
        except Exception as fit_error:
            print(
                f"ΓÜá∩╕Å Label fit guard skipped "
                f"({type(fit_error).__name__}: "
                f"{fit_error})."
            )

        if (
            not label_base_fonts
            or len(label_base_fonts)
            != len(name_texts)
        ):
            label_base_fonts = [
                float(VisualEngine.COUNTRY_FONT_SIZE)
                for _ in name_texts
            ]

        # ---------------------------------------------
        # PART 2 DEFECT B -- VALUE-LABEL HEADROOM (right edge).
        #
        # The value texts are EMPTY at setup time, so measure with
        # the FINAL formatted strings (largest = worst case),
        # positioned at the final bar tip; the guard widens the
        # x-limit only when the real glyphs would overflow.  Runs
        # AFTER the Part 1 left-edge fit so both sides are safe
        # simultaneously.
        # ---------------------------------------------
        try:
            _indicator = getattr(
                script, "indicator_name", script.title
            )
            _final_year = years[-1]
            for _vt, _country in zip(value_texts, countries):
                try:
                    _val = float(
                        data.loc[_country, _final_year]
                    )
                    _vt.set_text(
                        VisualEngine._format_value(
                            _val,
                            _indicator,
                        )
                    )
                    _vt.set_x(
                        VisualEngine._bar_width(
                            _val,
                            max_val,
                        )
                        + max_val * 0.012
                    )
                except Exception:
                    continue
            max_val = VisualEngine._reserve_value_headroom(
                fig,
                ax,
                value_texts,
                max_val,
                right_margin_px=(
                    design_system.VALUE_SAFE_MARGIN_PX
                ),
            )
            for _vt in value_texts:
                try:
                    _vt.set_text("")
                    _vt.set_x(0)
                except Exception:
                    continue
            try:
                fig.canvas.draw()
            except Exception:
                pass
        except Exception:
            pass

        # ---------------------------------------------
        # COUNTRY FLAG ICONS (beside each label)
        # Per-country try: one bad flag must not strip
        # the flags off every other bar.
        # ---------------------------------------------

        flag_boxes = []
        try:
            fig.canvas.draw()
        except Exception:
            pass

        for i, country in enumerate(countries):
            try:
                flag_boxes.append(
                    VisualEngine._attach_country_flag(
                        ax, fig, country, name_texts[i]
                    )
                )
            except Exception:
                flag_boxes.append(None)

        # ---------------------------------------------
        # FLAG ANCHOR CACHE
        #
        # The flags were positioned against the fitted BASE
        # font size.  The animation bumps a label's font for
        # leader / overtake emphasis, and a right-anchored
        # label grows LEFTWARDS -- so the enlarged text slid
        # over its own flag.  Pre-measure the left edge at all
        # three sizes the loop uses so the icon tracks the
        # label exactly, at zero per-frame cost.
        # ---------------------------------------------

        flag_anchors = (
            VisualEngine._flag_anchor_data_x(
                ax,
                fig,
                name_texts,
                flag_boxes,
                label_base_fonts,
            )
        )

        # =====================================================
        # STEP 7 ΓÇö TITLE
        # =====================================================

        title_text = fig.text(
            0.5,
            VisualEngine.TITLE_Y,
            script.title.upper(),
            ha="center",
            va="top",
            color=VisualEngine.TEXT_COLOR,
            fontsize=VisualEngine.TITLE_SIZE,
            fontweight="bold",
            wrap=True
        )

        title_text.set_path_effects(
            design_system.editorial_text_effects(linewidth=2.5)
        )

        # =====================================================
        # YEAR
        # =====================================================

        year_text = fig.text(
            VisualEngine.YEAR_X,
            VisualEngine.YEAR_Y,
            "",
            ha="center",
            va="center",
            color=VisualEngine.ELECTRIC_BLUE,
            fontsize=VisualEngine.YEAR_SIZE,
            fontweight="bold"
        )

        year_text.set_path_effects(
            design_system.editorial_text_effects(linewidth=3.0)
        )

        # =====================================================
        # STEP 7 ΓÇö OPENING LABEL
        # =====================================================

        opening_text = fig.text(
            0.5,
            0.855,
            # "WATCH THE RANKINGS CHANGE" is context, not payoff --
            # it burns the first second on zero information.
            # Config-gated (SHOW_OPENING_LABEL, default OFF).
            (
                "WATCH THE RANKINGS CHANGE"
                if getattr(
                    settings, "SHOW_OPENING_LABEL", False
                )
                else ""
            ),
            ha="center",
            va="center",
            color=VisualEngine.MAGENTA_PURPLE,
            fontsize=22,
            fontweight="bold",
            alpha=0.0
        )

        opening_text.set_path_effects(
            design_system.editorial_text_effects(linewidth=2.0)
        )

        # =====================================================
        # STEP 7 ΓÇö CLOSING LABEL
        # =====================================================

        closing_text = fig.text(
            0.5,
            0.135,
            "WHO DOMINATED?",
            ha="center",
            va="center",
            color=VisualEngine.ELECTRIC_BLUE,
            fontsize=25,
            fontweight="bold",
            alpha=0.0
        )

        closing_text.set_path_effects(
            design_system.editorial_text_effects(linewidth=2.0)
        )

        # =====================================================
        # SOURCE
        # =====================================================

        source_text = fig.text(
            0.5,
            VisualEngine.SOURCE_Y,
            f"Source: {script.source_name}",
            ha="center",
            va="center",
            color=VisualEngine.SECONDARY_TEXT,
            fontsize=VisualEngine.SOURCE_SIZE,
            style="italic"
        )

        # =====================================================
        # VIDEO TIMING -- audio-synced when the real narration
        # length was provided to render_scenes().
        # =====================================================

        video_duration = (
            VisualEngine._effective_duration(
                script
            )
        )

        total_frames = int(
            video_duration
            * VisualEngine.FPS
        )

        year_count = len(years)

        if year_count <= 1:

            frames_per_transition = (
                total_frames
            )

        else:

            frames_per_transition = (
                total_frames
                / (
                    year_count - 1
                )
            )

        opening_frames = int(
            VisualEngine.OPENING_SECONDS
            * VisualEngine.FPS
        )

        closing_frames = int(
            VisualEngine.CLOSING_SECONDS
            * VisualEngine.FPS
        )

        # -----------------------------------------------------
        # OPENING PAYOFF (retention)
        #
        # The FINAL comparison is on screen from frame 0 -- no
        # intro card, no buildup, no context before the payoff
        # (settings.OPENING_PAYOFF_SECONDS, default 2.0s).  The
        # history then replays as a rewind -> forward sweep that
        # completes by settings.OPENING_SWEEP_DONE of the runtime,
        # and the final state holds for the remainder.
        # -----------------------------------------------------

        payoff_seconds = float(
            getattr(
                settings,
                "OPENING_PAYOFF_SECONDS",
                0.0,
            )
            or 0.0
        )

        payoff_frames = 0

        if (
            payoff_seconds > 0
            and year_count > 1
        ):
            payoff_frames = min(
                int(
                    payoff_seconds
                    * VisualEngine.FPS
                ),
                total_frames // 2,
            )

        if payoff_frames:

            sweep_done = min(
                1.0,
                max(
                    0.1,
                    float(
                        getattr(
                            settings,
                            "OPENING_SWEEP_DONE",
                            1.0,
                        )
                        or 1.0
                    ),
                )
            )

            sweep_span = max(
                1,
                int(
                    total_frames
                    * sweep_done
                )
                - payoff_frames,
            )

            # +1 rewind transition (final year -> first year) on
            # top of the normal (year_count - 1) forward ones.
            frames_per_transition = max(
                1.0,
                sweep_span
                / (year_count - 1 + 1),
            )

        # =====================================================
        # UPDATE
        # =====================================================

        def update(frame):

            # =================================================
            # STEP 7 ΓÇö OPENING
            # =================================================

            opening_alpha = 0.0

            if (
                opening_frames > 0
                and frame < opening_frames
            ):

                progress = (
                    frame
                    / opening_frames
                )

                opening_alpha = min(
                    1.0,
                    progress * 2.0
                )

            opening_text.set_alpha(
                opening_alpha
            )

            # =================================================
            # DETERMINE YEAR
            # =================================================

            # -------------------------------------------------
            # OPENING PAYOFF: the first payoff_frames show the
            # FINAL comparison (no buildup), then the history
            # replays as a rewind -> forward sweep (the extra +1
            # transition was accounted for in
            # frames_per_transition above).  With payoff disabled
            # this reduces exactly to the historical mapping.
            # -------------------------------------------------

            if (
                payoff_frames
                and frame < payoff_frames
                and year_count > 1
            ):

                year_idx = year_count - 1
                next_idx = year_count - 1
                year_progress = 1.0

                # ENTRANCE, not a freeze.  The final ranking is
                # still correct and visible from frame 0 (the
                # retention intent is preserved), but the bars
                # now FADE IN with a stagger instead of sitting
                # motionless for the answer hold.  Measured before:
                # only 0.0005% of pixels changed at 0.5s.
                design_system.apply_entrance_alpha(
                    list(bars) + list(flag_boxes),
                    frame,
                    payoff_frames,
                )

            elif year_count <= 1:

                year_idx = 0
                next_idx = 0
                year_progress = 0.0

            else:

                effective_frame = (
                    frame - payoff_frames
                    if frame >= payoff_frames
                    else frame
                )

                raw_transition = (
                    effective_frame
                    / frames_per_transition
                )

                transition_index = int(
                    raw_transition
                )

                transition_fraction = (
                    raw_transition
                    - transition_index
                )

                if (
                    payoff_frames
                    and transition_index == 0
                ):

                    # Rewind transition: final state -> first year.
                    year_idx = year_count - 1
                    next_idx = 0
                    year_progress = (
                        transition_fraction
                    )

                else:

                    if payoff_frames:
                        # Forward transitions start at index 1
                        # (index 0 was the rewind).
                        year_idx = transition_index - 1
                    else:
                        year_idx = transition_index

                    year_idx = max(
                        0,
                        min(
                            year_idx,
                            year_count - 1
                        )
                    )

                    next_idx = min(
                        year_idx + 1,
                        year_count - 1
                    )

                    if (
                        year_idx
                        >= year_count - 1
                    ):

                        year_idx = (
                            year_count - 1
                        )

                        next_idx = (
                            year_count - 1
                        )

                        year_progress = 1.0

                    else:

                        year_progress = (
                            transition_fraction
                        )

            # =================================================
            # PACED MOVEMENT
            # =================================================

            transition_progress = (
                VisualEngine
                .get_transition_progress(
                    year_progress
                )
            )

            current_year = years[
                year_idx
            ]

            next_year = years[
                next_idx
            ]

            # =================================================
            # YEAR LABEL
            # =================================================

            if (
                year_progress >= 0.50
                and next_idx != year_idx
            ):

                display_year = next_year

            else:

                display_year = current_year

            year_text.set_text(
                str(display_year)
            )

            # =================================================
            # DATA
            # =================================================

            current_values = data[
                current_year
            ]

            next_values = data[
                next_year
            ]

            current_ranks = ranks_df[
                current_year
            ]

            next_ranks = ranks_df[
                next_year
            ]

            # =================================================
            # OVERTAKES
            # =================================================

            overtakes = (
                VisualEngine
                ._find_overtakes(
                    current_ranks,
                    next_ranks,
                    countries
                )
            )

            # =================================================
            # LEADERS
            # =================================================

            current_leader = (
                current_values.idxmax()
            )

            next_leader = (
                next_values.idxmax()
            )

            # =================================================
            # BAR POSITIONS
            # =================================================

            raw_bar_positions = []

            for country in countries:

                current_position = (
                    float(
                        current_ranks[
                            country
                        ]
                    )
                    - 1
                )

                next_position = (
                    float(
                        next_ranks[
                            country
                        ]
                    )
                    - 1
                )

                y_position = (
                    current_position
                    + (
                        next_position
                        - current_position
                    )
                    * transition_progress
                )

                raw_bar_positions.append(
                    y_position
                )

            # =================================================
            # LABEL POSITIONS
            # =================================================

            label_positions = (
                VisualEngine
                ._solve_label_positions(
                    raw_bar_positions,
                    VisualEngine.MIN_LABEL_GAP,
                    0,
                    len(countries) - 1
                )
            )

            # =================================================
            # UPDATE BARS
            # =================================================

            for i, country in enumerate(
                countries
            ):

                # ---------------------------------------------
                # VALUE
                # ---------------------------------------------

                current_value = float(
                    current_values[
                        country
                    ]
                )

                next_value = float(
                    next_values[
                        country
                    ]
                )

                value = (
                    current_value
                    + (
                        next_value
                        - current_value
                    )
                    * transition_progress
                )

                # ---------------------------------------------
                # POSITION
                # ---------------------------------------------

                bar_y = (
                    raw_bar_positions[i]
                )

                bars[i].set_extent(
                    [
                        0,
                        VisualEngine._bar_width(value, max_val),
                        bar_y
                        - VisualEngine.BAR_HEIGHT / 2,
                        bar_y
                        + VisualEngine.BAR_HEIGHT / 2,
                    ]
                )

                # ---------------------------------------------
                # RANK
                # ---------------------------------------------

                current_rank = (
                    float(
                        current_ranks[
                            country
                        ]
                    )
                    - 1
                )

                next_rank = (
                    float(
                        next_ranks[
                            country
                        ]
                    )
                    - 1
                )

                interpolated_rank = (
                    current_rank
                    + (
                        next_rank
                        - current_rank
                    )
                    * transition_progress
                )

                nearest_rank = int(
                    round(
                        interpolated_rank
                    )
                )

                nearest_rank = max(
                    0,
                    min(
                        nearest_rank,
                        len(countries) - 1
                    )
                )

                # ---------------------------------------------
                # OVERTAKE EMPHASIS
                # ---------------------------------------------

                is_overtake = (
                    country in overtakes
                    and (
                        0.25
                        <= transition_progress
                        <= 0.85
                    )
                )

                # ---------------------------------------------
                # LEADER
                # ---------------------------------------------

                is_leader = (
                    (
                        country
                        == current_leader
                    )
                    and transition_progress < 0.5
                ) or (
                    (
                        country
                        == next_leader
                    )
                    and transition_progress >= 0.5
                )

                # ---------------------------------------------
                # BAR COLOR
                # ---------------------------------------------

                bars[i].set_data(
                    VisualEngine
                    ._bar_gradient(
                        VisualEngine
                        ._get_bar_color(
                            nearest_rank,
                            is_current_leader=(
                                is_leader
                            ),
                            is_overtake=(
                                is_overtake
                            )
                        )
                    )
                )

                # ---------------------------------------------
                # VALUE TEXT
                # ---------------------------------------------

                indicator_name = getattr(
                    script,
                    "indicator_name",
                    script.title
                )

                value_texts[i].set_text(
                    VisualEngine
                    ._format_value(
                        value,
                        indicator_name
                    )
                )

                value_texts[i].set_x(
                    VisualEngine._bar_width(value, max_val)
                    + max_val * 0.012
                )

                value_texts[i].set_y(
                    bar_y
                )

                # ---------------------------------------------
                # COUNTRY LABEL
                # ---------------------------------------------

                name_texts[i].set_y(
                    label_positions[i]
                )

                if flag_boxes[i] is not None:
                    # Use the pre-measured left edge for the
                    # font size about to be applied, so an
                    # enlarged label never slides over its
                    # own flag icon.
                    anchor_x = flag_boxes[i].xy[0]

                    row = (
                        flag_anchors[i]
                        if i < len(flag_anchors)
                        else None
                    )

                    if row:
                        bump = (
                            2 if is_overtake
                            else (1 if is_leader else 0)
                        )
                        if (
                            bump < len(row)
                            and row[bump] is not None
                        ):
                            anchor_x = row[bump]

                    flag_boxes[i].xy = (
                        anchor_x,
                        label_positions[i]
                    )

                # ---------------------------------------------
                # STEP 6 ΓÇö TEXT EMPHASIS
                #
                # NOTE: every branch adds its emphasis to
                # label_base_fonts[i] -- the size the fit
                # guard measured and guaranteed fits -- and
                # NEVER to COUNTRY_FONT_SIZE.  Restoring the
                # unfitted size here each frame is what pushed
                # long labels (and their flags) off the left
                # edge for the whole video.
                # ---------------------------------------------

                base_font = label_base_fonts[i]

                if is_overtake:

                    name_texts[i].set_fontsize(
                        base_font + 2
                    )

                    name_texts[i].set_color(
                        VisualEngine
                        .OVERTAKE_COLOR
                    )

                    value_texts[i].set_color(
                        VisualEngine
                        .OVERTAKE_COLOR
                    )

                elif is_leader:

                    name_texts[i].set_fontsize(
                        base_font + 1
                    )

                    name_texts[i].set_color(
                        VisualEngine
                        .TEXT_COLOR
                    )

                    value_texts[i].set_color(
                        VisualEngine
                        .TEXT_COLOR
                    )

                else:

                    name_texts[i].set_fontsize(
                        base_font
                    )

                    name_texts[i].set_color(
                        VisualEngine
                        .TEXT_COLOR
                    )

                    value_texts[i].set_color(
                        VisualEngine
                        .TEXT_COLOR
                    )

            # =================================================
            # STEP 7 ΓÇö CLOSING
            # =================================================

            closing_start = (
                total_frames
                - closing_frames
            )

            closing_alpha = 0.0

            if (
                closing_frames > 0
                and frame >= closing_start
            ):

                progress = (
                    frame
                    - closing_start
                ) / closing_frames

                closing_alpha = min(
                    1.0,
                    progress * 2.0
                )

            closing_text.set_alpha(
                closing_alpha
            )

            # =================================================
            # RETURN ARTISTS
            # =================================================

            return (
                bars
                + value_texts
                + name_texts
                + [
                    year_text,
                    opening_text,
                    closing_text
                ]
            )

        # =====================================================
        # ANIMATION
        # =====================================================

        ani = animation.FuncAnimation(
            fig,
            update,
            frames=total_frames,
            interval=1000 / VisualEngine.FPS,
            blit=False
        )

        # =====================================================
        # EXPORT
        # =====================================================

        output_path = os.path.join(
            output_dir,
            "full_race.mp4"
        )

        writer = animation.FFMpegWriter(
            fps=VisualEngine.FPS,
            bitrate=12000
        )

        ani.save(
            output_path,
            writer=writer
        )

        plt.close(fig)

        print(
            f"Γ£à Step 6 + Step 7 video saved: "
            f"{output_path}"
        )


        return [
            {
                "scene_number": 1,
                "image_path": output_path
            }
        ]

    # =========================================================
    # SHARED CHART DATA
    # =========================================================

    # =========================================================
    # FOCUS-ENTITY BAR CAP
    #
    # PUBLISHED-VIDEO DEFECT (Issue 2, "India missing from its
    # own chart"): the mobile bar cap kept the top-N entities
    # by PEAK VALUE, so the story's named subject -- whose peak
    # may rank below the value leaders -- was silently dropped
    # from the rendered chart while the title and every scene
    # narration kept talking about it.  The India military-
    # spending video shipped bars for Oman / Saudi Arabia /
    # Lebanon / South Sudan while the title claimed "Why Did
    # India Slip From #2 to #3?" and India appeared in ZERO
    # frames.
    #
    # The cap is now FOCUS-AWARE: entities the script itself
    # names (scene highlight_countries) are guaranteed a bar;
    # the remaining slots go to the highest-value entities.
    # The same helpers are reused by app/qc/entity_guard.py so
    # the pre-render validation simulates EXACTLY what the
    # renderer will draw.
    # =========================================================

    @staticmethod
    def compute_bar_cap(script) -> int:
        """Mobile bar budget for one video (2..MAX_CHART_ENTITIES).

        settings.CHART_MAX_BARS (default 4) is the per-chart
        target; "vs"-titled head-to-head videos are further
        capped to settings.CHART_BARS_VS (default 3) because the
        matchup IS the video.  Shared by the renderer and the
        entity guard so both agree on the displayed count.
        """

        try:
            max_bars = int(
                getattr(settings, "CHART_MAX_BARS", 4)
            )
        except (TypeError, ValueError):
            max_bars = 4

        try:
            hard_cap = int(
                getattr(settings, "MAX_CHART_ENTITIES", 4)
            )
        except (TypeError, ValueError):
            hard_cap = 4

        max_bars = max(
            2,
            min(
                max_bars,
                max(2, hard_cap),
            ),
        )

        title_text = str(
            getattr(script, "title", "") or ""
        ).lower()

        if " vs " in title_text or " vs. " in title_text:

            try:
                vs_cap = int(
                    getattr(settings, "CHART_BARS_VS", 3)
                )
            except (TypeError, ValueError):
                vs_cap = 3

            max_bars = min(
                max_bars,
                max(2, vs_cap),
            )

        return max_bars

    @staticmethod
    def _index_display_labels(data) -> list:
        """Human-readable labels of the frame index.

        MultiIndex rows arrive as (code, display-name) pairs --
        the LAST level is the display name (see
        _normalize_index).  Plain indexes are used verbatim.
        """

        labels = []

        try:

            if isinstance(
                data.index,
                pd.MultiIndex,
            ):

                for entry in data.index:

                    labels.append(
                        str(entry[-1])
                    )

                return labels

        except Exception:

            pass

        for entry in data.index:

            labels.append(str(entry))

        return labels

    @staticmethod
    def _match_label(
        entity: str,
        labels: list,
    ):
        """Resolve one named entity onto a frame label.

        Matching order (same tolerance the rest of the
        pipeline uses via app.countries):
          1. canonical country identity -- app.countries.lookup()
             maps both the entity name and each frame label to
             ISO-3166 display names, so "India" matches a row
             keyed "India" regardless of provider naming;
          2. case-insensitive exact match;
          3. containment (shorter inside longer) -- covers
             suffixed provider labels like "Somalia, Fed. Rep."
        Returns the matched frame label, or None.
        """

        from app.countries import lookup as country_lookup

        wanted = str(entity or "").strip()

        if not wanted:
            return None

        wanted_meta = country_lookup(wanted)

        wanted_lower = wanted.casefold()

        best_containment = None

        for label in labels:

            label_lower = str(label).casefold()

            if not label_lower:
                continue

            if wanted_meta:

                label_meta = country_lookup(label)

                if (
                    label_meta
                    and label_meta["iso2"]
                    == wanted_meta["iso2"]
                ):
                    return label

            if label_lower == wanted_lower:
                return label

            if (
                wanted_lower in label_lower
                or label_lower in wanted_lower
            ):

                if best_containment is None:
                    best_containment = label

        return best_containment

    @staticmethod
    def _resolve_focus_entities(
        script,
        data,
    ) -> list:
        """Entities the SCRIPT names, resolved onto the frame.

        Sources, in order: every scene's highlight_countries
        (the LLM's structured per-scene subject list -- the
        exact field the published video filled with "India")
        plus the country names the TITLE mentions.  Returned
        as the matched frame labels, order-preserving and
        deduplicated.
        """

        import re as _re

        labels = (
            VisualEngine._index_display_labels(data)
        )

        requested = []

        for scene in (
            getattr(script, "scenes", None) or []
        ):

            for entity in (
                getattr(scene, "highlight_countries", None)
                or []
            ):

                entity = str(entity or "").strip()

                if entity and entity not in requested:
                    requested.append(entity)

        title = str(
            getattr(script, "title", "") or ""
        )

        if title:

            from app.countries import name_forms

            forms = name_forms()

            for token in _re.findall(
                r"[A-Za-z][A-Za-z'&.\- ]{1,}",
                title,
            ):

                token = token.strip(" '.,-")

                if not token:
                    continue

                normalized = _re.sub(
                    r"[^a-zA-Z0-9]+",
                    " ",
                    token,
                ).strip().lower()

                if normalized in forms:

                    if token not in requested:
                        requested.append(token)

        matched = []

        for entity in requested:

            label = VisualEngine._match_label(
                entity,
                labels,
            )

            if label and label not in matched:
                matched.append(label)

        return matched

    @staticmethod
    def cap_display_index(
        data,
        max_items: int,
        focus=None,
    ) -> list:
        """Value-ranked top-N bar selection WITH focus guarantees.

        Entities in `focus` (frame labels) always keep a bar;
        the remaining slots go to the highest-peak entities.
        This is the single cap decision the bar renderer draws
        and the entity guard simulates, so a validated video
        can never ship without its named subject on screen.
        """

        labels = (
            VisualEngine._index_display_labels(data)
        )

        focus_labels = [
            label
            for label in (focus or [])
            if label in labels
        ]

        if len(labels) <= max_items:
            return list(data.index)

        kept = list(focus_labels)

        if max_items - len(kept) > 0:

            ranked = (
                data.max(axis=1)
                .sort_values(
                    ascending=False
                )
            )

            for entry in ranked.index:

                if len(kept) >= max_items:
                    break

                is_multi = isinstance(
                    data.index,
                    pd.MultiIndex,
                )

                display = str(
                    entry[-1] if is_multi else entry
                )

                if display in kept:
                    continue

                kept.append(display)

        # Map the kept DISPLAY labels back onto the RAW index
        # entries so data.loc[] works for MultiIndex frames.
        is_multi = isinstance(
            data.index,
            pd.MultiIndex,
        )

        kept_raw = []

        for entry in data.index:

            display = str(
                entry[-1] if is_multi else entry
            )

            if display in kept:
                kept_raw.append(entry)

        return kept_raw

    @staticmethod
    def _prepare_chart_data(
        data: pd.DataFrame,
        max_items=8,
        respect_cap: bool = True,
        focus=None,
        fill: bool = True,
    ):
        """Normalize one wide frame for rendering.

        respect_cap=False lets a renderer opt out of the mobile
        entity ceiling temporarily -- top5_change needs the FULL
        frame to compute year-over-year changes before picking the
        biggest movers; truncating first would select by peak value
        instead, which silently changes what the chart is about.

        `focus` (frame labels) names entities that MUST survive
        the mobile cap -- the story's named subjects (see the
        FOCUS-ENTITY BAR CAP notes above).

        fill=False keeps interior/edge NaNs intact for renderers
        whose comparison edges must be REAL observations -- slope
        never fabricates a start/end value via ffill/bfill.
        """
        if data.empty:
            raise ValueError(
                "No data provided for visual rendering."
            )

        data = VisualEngine._normalize_index(
            data.copy()
        )

        # Season-label safe coercion (see coerce_year_label):
        # plain years, "YR" forms and season labels all resolve;
        # duplicates keep the first occurrence.

        valid_columns = []
        seen_years = set()

        for column in data.columns:

            year = coerce_year_label(column)

            if year is None or year in seen_years:
                continue

            seen_years.add(year)

            valid_columns.append(
                (
                    column,
                    year
                )
            )

        if not valid_columns:
            raise ValueError(
                "No valid year columns found "
                "for visual rendering."
            )

        data = data[
            [
                column
                for column, _
                in valid_columns
            ]
        ]

        data.columns = [
            year
            for _, year
            in valid_columns
        ]

        data = data.reindex(
            sorted(
                data.columns
            ),
            axis=1
        )

        for column in data.columns:
            data[column] = pd.to_numeric(
                data[column],
                errors="coerce"
            )

        data = data.dropna(
            how="all"
        )

        if data.empty:
            raise ValueError(
                "No numeric data available "
                "after cleaning."
            )

        if fill:
            data = data.ffill(
                axis=1
            ).bfill(
                axis=1
            )

        # Mobile bar cap: no chart may render more than
        # settings.MAX_CHART_ENTITIES bars (default 4) regardless
        # of what the renderer requested.  6-8 cramped bars fail
        # on mobile at a glance; 2-4 read instantly.
        if respect_cap:
            try:
                cap = int(
                    getattr(settings, "MAX_CHART_ENTITIES", 4)
                )
            except (TypeError, ValueError):
                cap = 4
            cap = max(2, cap)
            max_items = (
                min(max_items, cap) if max_items else cap
            )

        if len(data.index) > max_items:

            # FOCUS-AWARE CAP: named entities keep a bar even
            # when their peak value ranks below the value
            # leaders (Issue 2 -- India dropped from its own
            # chart).  The kept labels are mapped back onto the
            # raw index so MultiIndex frames survive the .loc.
            kept_raw = (
                VisualEngine.cap_display_index(
                    data,
                    max_items,
                    focus=focus,
                )
            )

            data = data.loc[
                kept_raw
            ]

        return data

    # =========================================================
    # SHARED FIGURE
    # =========================================================

    @staticmethod
    def _set_chart_style():

        plt.rcParams[
            "figure.facecolor"
        ] = VisualEngine.BG_COLOR

        plt.rcParams[
            "axes.facecolor"
        ] = VisualEngine.BG_COLOR

        plt.rcParams[
            "text.color"
        ] = VisualEngine.TEXT_COLOR

        plt.rcParams[
            "font.family"
        ] = "DejaVu Sans"

    # =========================================================
    # BACKGROUND GRADIENT + VIGNETTE
    # =========================================================

    @staticmethod
    def _draw_background(
        fig,
        ax,
        pulse_frame=0,
        total_frames=1
    ):
        """
        Draw a vertical gradient background and a
        subtle vignette overlay on the figure.

        The gradient goes from BG_GRADIENT_TOP (top)
        to BG_GRADIENT_BOTTOM (bottom).

        A slow pulse effect shifts the gradient colors
        by a small amount based on the frame number,
        creating a living background.

        The vignette darkens the edges to draw the
        viewer's eye toward the center of the chart.
        """

        # -------------------------------------------------
        # Static premium gradient (no pulsing)
        # -------------------------------------------------

        pulse = 0.0

        # Interpolate between top and bottom colors
        # with a subtle pulse offset

        top_rgb = np.array(
            [
                int(
                    VisualEngine.BG_GRADIENT_TOP[1:3],
                    16
                ),
                int(
                    VisualEngine.BG_GRADIENT_TOP[3:5],
                    16
                ),
                int(
                    VisualEngine.BG_GRADIENT_TOP[5:7],
                    16
                ),
            ],
            dtype=float
        )

        bottom_rgb = np.array(
            [
                int(
                    VisualEngine.BG_GRADIENT_BOTTOM[1:3],
                    16
                ),
                int(
                    VisualEngine.BG_GRADIENT_BOTTOM[3:5],
                    16
                ),
                int(
                    VisualEngine.BG_GRADIENT_BOTTOM[5:7],
                    16
                ),
            ],
            dtype=float
        )

        # Apply pulse offset
        top_rgb = np.clip(
            top_rgb + pulse * 8,
            0,
            255
        )
        bottom_rgb = np.clip(
            bottom_rgb + pulse * 8,
            0,
            255
        )

        # -------------------------------------------------
        # GRADIENT IMAGE
        # -------------------------------------------------

        height = 200

        gradient = np.zeros(
            (
                height,
                1,
                3
            )
        )

        for row in range(height):

            ratio = row / max(
                1,
                height - 1
            )

            gradient[row, 0] = (
                top_rgb
                * (
                    1
                    - ratio
                )
                + bottom_rgb
                * ratio
            )

        gradient = (
            gradient
            / 255.0
        )

        fig.figimage(
            gradient,
            xo=0,
            yo=0,
            alpha=1.0,
            zorder=0
        )

        # -------------------------------------------------
        # Clean finish: no vignette overlay ΓÇö the smooth
        # gradient alone keeps the frame premium.
        # -------------------------------------------------

    # =========================================================
    # LEADER BAR GLOW
    # =========================================================

    @staticmethod
    def _draw_glow(
        ax,
        bar_y,
        bar_width,
        bar_height,
        glow_alpha=0.25
    ):
        """
        Draw a soft glow rectangle behind a bar.

        The glow is a wider, semi-transparent version
        of the leader bar color.
        """

        glow_width = bar_width * 1.15

        glow = ax.add_patch(
            mpatches.Rectangle(
                (
                    0,
                    bar_y
                    - bar_height / 2
                ),
                glow_width,
                bar_height,
                facecolor=VisualEngine.LEADER_GLOW,
                alpha=glow_alpha,
                zorder=0
            )
        )

        return glow

    @staticmethod
    def _create_figure(
        script,
        subtitle=""
    ):


        VisualEngine._set_chart_style()

        fig = plt.figure(
            figsize=(10.8, 19.2),
            dpi=100
        )

        ax = fig.add_axes(
            [
                0.13,
                0.20,
                0.78,
                0.58
            ]
        )

        ax.set_facecolor(
            VisualEngine.BG_COLOR
        )

        for spine in ax.spines.values():
            spine.set_visible(False)

        # Restrained depth behind the data: two soft glows in
        # figure space at zorder 0, tinted by the active topic
        # ramp (gold as the fallback).  Drawn once, never
        # animated -- a moving background would compete with the
        # chart for attention.
        design_system.apply_atmosphere(
            ax,
            fig,
            (
                VisualEngine._ACTIVE_PALETTE
                or [design_system.BRAND_GOLD]
            )[0],
        )

        title = fig.text(
            0.5,
            VisualEngine.TITLE_Y,
            script.title.upper(),
            ha="center",
            va="top",
            color=VisualEngine.TEXT_COLOR,
            fontsize=VisualEngine.TITLE_SIZE,
            fontweight="bold",
            wrap=True
        )

        title.set_path_effects(
            design_system.editorial_text_effects(linewidth=2.5)
        )

        # Generic subtitles ("AREA TREND OVER TIME") occupy prime
        # visual space without showing a number -- config-gated
        # (SHOW_CHART_SUBTITLE, default OFF).
        if subtitle and getattr(
            settings, "SHOW_CHART_SUBTITLE", False
        ):
            fig.text(
                0.5,
                0.845,
                subtitle.upper(),
                ha="center",
                va="center",
                color=VisualEngine.MAGENTA_PURPLE,
                fontsize=23,
                fontweight="bold"
            )

        fig.text(
            0.5,
            VisualEngine.SOURCE_Y,
            f"Source: {script.source_name}",
            ha="center",
            va="center",
            color=VisualEngine.SECONDARY_TEXT,
            fontsize=VisualEngine.SOURCE_SIZE,
            style="italic"
        )

        return fig, ax

    @staticmethod
    def _save_animation(
        fig,
        update,
        total_frames,
        output_dir,
        filename
    ):

        os.makedirs(
            output_dir,
            exist_ok=True
        )

        ani = animation.FuncAnimation(
            fig,
            update,
            frames=total_frames,
            interval=1000 / VisualEngine.FPS,
            blit=False
        )

        output_path = os.path.join(
            output_dir,
            filename
        )

        writer = animation.FFMpegWriter(
            fps=VisualEngine.FPS,
            bitrate=12000
        )

        ani.save(
            output_path,
            writer=writer
        )

        plt.close(fig)

        return [
            {
                "scene_number": 1,
                "image_path": output_path
            }
        ]

    @staticmethod
    def _duration_frames(script):

        # Audio-synced when the real narration length was
        # provided to render_scenes(); planned duration otherwise.

        duration = (
            VisualEngine._effective_duration(
                script
            )
        )

        return max(
            1,
            int(
                duration
                * VisualEngine.FPS
            )
        )


    @staticmethod
    def _indicator_name(script):

        return getattr(
            script,
            "indicator_name",
            getattr(
                script,
                "title",
                ""
            )
        )

    # =========================================================
    # COUNTRY FLAG ICONS
    # =========================================================

    _FLAG_ARRAY_CACHE = {}

    # Download tuning: flagcdn.com rate-limits rapid successive
    # requests, which used to silently drop every flag after the
    # first one. Retry with a small delay and a browser User-Agent
    # so every bar gets its flag, not just the top one.

    _FLAG_DOWNLOAD_RETRIES = 3
    _FLAG_DOWNLOAD_TIMEOUT = 10  # seconds per attempt
    _FLAG_RETRY_DELAY = 1.5      # seconds between attempts

    # -----------------------------------------------------
    # PREMIUM FLAG STYLING
    #
    # Every flag is rendered at the EXACT same pixel size on
    # every bar regardless of country or source aspect ratio,
    # gets a rounded-corner mask, and a thin warm-gold ring so
    # it blends into the dark/gold theme instead of reading as
    # a pasted-on hard-edged rectangle.
    # -----------------------------------------------------

    _FLAG_SIZE = (80, 60)       # uniform width x height in px
    _FLAG_CORNER_RADIUS = 12    # rounded-mask radius in px
    _FLAG_BORDER_WIDTH = 2      # ring thickness in px
    _FLAG_BORDER_COLOR = (
        232, 197, 106, 210
    )                           # warm gold, alpha ~82%

    # Styled RGBA arrays keyed by ISO2 code (built once per run).
    _FLAG_STYLED_CACHE = {}

    @staticmethod
    def _download_flag(code, local_path):
        """Download one flag PNG with retries; return True on success."""

        import time
        import urllib.request
        import urllib.error

        url = (
            "https://flagcdn.com/w80/"
            f"{code}.png"
        )

        for attempt in range(
            VisualEngine._FLAG_DOWNLOAD_RETRIES
        ):

            try:

                request = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (compatible; "
                            "BarRaceRenderer/1.0)"
                        )
                    },
                )

                with urllib.request.urlopen(
                    request,
                    timeout=VisualEngine._FLAG_DOWNLOAD_TIMEOUT
                ) as response:

                    payload = response.read()

                # Validate before writing: a partial / error page
                # should not poison the local cache.

                if len(payload) < 100:
                    raise ValueError(
                        "Flag payload too small."
                    )

                with open(local_path, "wb") as fh:
                    fh.write(payload)

                return True

            except Exception:

                if (
                    attempt
                    < VisualEngine._FLAG_DOWNLOAD_RETRIES - 1
                ):
                    time.sleep(
                        VisualEngine._FLAG_RETRY_DELAY
                    )

        return False

    @staticmethod
    def _flag_cache_dir():
        """Project-root-anchored flag disk cache.

        The old CWD-relative "assets/flags" path silently missed
        whenever the pipeline ran from another working directory,
        forcing a re-download of every flag each run.
        """

        project_root = os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        )

        flag_dir = os.path.join(
            project_root, "assets", "flags"
        )

        os.makedirs(flag_dir, exist_ok=True)

        return flag_dir

    @staticmethod
    def prefetch_flags(country_names):
        """Download every needed flag up-front, sequentially.

        Called once per render so the per-label attachment later
        always hits the local cache. A short pause between requests
        keeps flagcdn.com happy.
        """

        import time

        try:
            from app.countries import iso2_code
        except Exception:
            return

        flag_dir = VisualEngine._flag_cache_dir()

        codes = []

        for name in country_names:

            code = iso2_code(name)

            if (
                code is not None
                and code not in codes
            ):
                codes.append(code)

        for index, code in enumerate(codes):

            local_path = os.path.join(
                flag_dir, f"{code}.png"
            )

            if os.path.exists(local_path):
                continue

            if index > 0:
                time.sleep(0.4)

            VisualEngine._download_flag(
                code, local_path
            )

        # Production-run visibility: proves the flag
        # pipeline executed during real renders.
        print(
            f"≡ƒÜ⌐ Flags ready: {len(codes)} "
            f"unique code(s) cached in {flag_dir}"
        )

    @staticmethod
    def _load_raw_flag_array(code):
        """Decode the raw flag PNG for an ISO2 code, or None.

        Memory cache -> local disk cache -> CDN download.
        Download failures are NOT cached permanently: a later
        render retries, so a transient network blip never strips
        a country of its flag for good.
        """

        cached = VisualEngine._FLAG_ARRAY_CACHE.get(code)

        if cached is not None:
            return cached

        array = None

        try:

            from PIL import Image

            flag_dir = (
                VisualEngine._flag_cache_dir()
            )

            local_path = os.path.join(
                flag_dir, f"{code}.png"
            )

            if not os.path.exists(local_path):

                VisualEngine._download_flag(
                    code, local_path
                )

            if os.path.exists(local_path):

                array = np.asarray(
                    Image.open(
                        local_path
                    ).convert("RGBA")
                )

        except Exception:
            array = None

        if array is not None:
            VisualEngine._FLAG_ARRAY_CACHE[code] = array

        return array

    @staticmethod
    def _style_flag_array(code):
        """Uniform premium-styled RGBA flag for `code`, or None.

        Center-crops the source to ONE fixed aspect ratio and
        resizes to _FLAG_SIZE so every country renders at the
        exact same size on every bar, then applies a rounded-
        corner mask plus a thin warm-gold ring so icons blend
        into the dark/gold theme instead of reading as pasted-on
        hard-edged rectangles.  Cached per code; never raises --
        falls back to the unstyled array.
        """

        if code in VisualEngine._FLAG_STYLED_CACHE:
            return VisualEngine._FLAG_STYLED_CACHE[code]

        base = VisualEngine._load_raw_flag_array(code)

        if base is None:
            return None

        styled = None

        try:

            from PIL import Image, ImageDraw

            image = Image.fromarray(base).convert(
                "RGBA"
            )

            target_w, target_h = (
                VisualEngine._FLAG_SIZE
            )
            target_ratio = target_w / target_h

            # Center-crop to the uniform aspect: zero
            # distortion, identical output dimensions for
            # every country.
            src_w, src_h = image.size
            src_ratio = src_w / max(1, src_h)

            if src_ratio > target_ratio:

                crop_w = int(src_h * target_ratio)
                x0 = (src_w - crop_w) // 2
                image = image.crop(
                    (x0, 0, x0 + crop_w, src_h)
                )

            elif src_ratio < target_ratio:

                crop_h = int(src_w / target_ratio)
                y0 = (src_h - crop_h) // 2
                image = image.crop(
                    (0, y0, src_w, y0 + crop_h)
                )

            image = image.resize(
                (target_w, target_h),
                Image.LANCZOS,
            )

            # Rounded-corner alpha mask.
            mask = Image.new(
                "L", (target_w, target_h), 0
            )

            ImageDraw.Draw(mask).rounded_rectangle(
                (
                    0, 0,
                    target_w - 1, target_h - 1,
                ),
                radius=(
                    VisualEngine._FLAG_CORNER_RADIUS
                ),
                fill=255,
            )

            image.putalpha(mask)

            # Thin warm-gold ring inside the rounded edge.
            half = (
                VisualEngine._FLAG_BORDER_WIDTH // 2
            )

            ring = Image.new(
                "RGBA",
                (target_w, target_h),
                (0, 0, 0, 0),
            )

            ImageDraw.Draw(ring).rounded_rectangle(
                (
                    half, half,
                    target_w - 1 - half,
                    target_h - 1 - half,
                ),
                radius=(
                    VisualEngine._FLAG_CORNER_RADIUS
                ),
                outline=(
                    VisualEngine._FLAG_BORDER_COLOR
                ),
                width=(
                    VisualEngine._FLAG_BORDER_WIDTH
                ),
            )

            image = Image.alpha_composite(image, ring)

            styled = np.asarray(image)

        except Exception:
            styled = None

        if styled is None:
            # A plain flag still beats no flag at all.
            styled = base

        VisualEngine._FLAG_STYLED_CACHE[code] = styled

        return styled

    @staticmethod
    def _get_flag_image(country_name):
        """Return a fresh OffsetImage of the country flag, or None.

        Only the decoded RGBA array is cached; a new OffsetImage is built
        for every call so each chart axes owns its own artist (reusing an
        OffsetImage across figures raises "Can not reset the Axes").

        Accepts full names AND alpha-2/alpha-3 codes ("Germany",
        "DEU", "de") thanks to the extended countries lookup.
        """

        try:
            from app.countries import iso2_code
        except Exception:
            return None

        code = iso2_code(country_name)

        if code is None:
            return None

        styled = VisualEngine._style_flag_array(code)

        if styled is None:
            return None

        return OffsetImage(styled, zoom=0.32)

    @staticmethod
    def _flag_anchor_data_x(
        ax,
        fig,
        name_texts,
        flag_boxes,
        base_fonts,
    ):
        """Pre-measure each label's LEFT edge, in data coordinates,
        at every font size the animation will ever apply.

        Labels are RIGHT-anchored at a fixed data offset, so when
        the animation bumps a label's font for leader / overtake
        emphasis the text grows LEFTWARDS.  The flag icon is
        positioned exactly once by _attach_country_flag, so
        without this the enlarged label slid straight over its
        own flag.

        The loop only ever uses base, base + 1 and base + 2, so
        those three anchors are measured once up front and the
        per-frame cost is a list index.  Returns a list parallel
        to `name_texts`; each entry is [base, +1, +2] or None
        when that label has no flag.
        """

        anchors = []

        for index, text in enumerate(
            name_texts
        ):

            if (
                index >= len(flag_boxes)
                or flag_boxes[index] is None
            ):
                anchors.append(None)
                continue

            try:
                renderer = (
                    fig.canvas.get_renderer()
                )
            except Exception:
                anchors.append(None)
                continue

            base_pt = float(
                base_fonts[index]
            )

            row = []

            for bump in range(
                VisualEngine
                .LABEL_FONT_BUMP + 1
            ):

                try:
                    text.set_fontsize(
                        base_pt + bump
                    )
                    fig.canvas.draw()
                    extent = (
                        text.get_window_extent(
                            renderer=renderer
                        )
                    )
                    x_data, _ = (
                        ax.transData
                        .inverted()
                        .transform(
                            (extent.x0, extent.y0)
                        )
                    )
                    row.append(float(x_data))
                except Exception:
                    row.append(None)

            # Restore the fitted base size.
            try:
                text.set_fontsize(base_pt)
            except Exception:
                pass

            anchors.append(row)

        try:
            fig.canvas.draw()
        except Exception:
            pass

        return anchors

    @staticmethod
    def _attach_country_flag(ax, fig, country_name, label_text):
        """Place a small flag icon just left of a country's text label.

        Returns the AnnotationBbox artist, or None when no flag is known.
        """

        flag = VisualEngine._get_flag_image(country_name)

        if flag is None:

            print(
                f"≡ƒÜ⌐ No flag for '{country_name}' "
                "-- text-only label."
            )

            return None

        try:
            renderer = fig.canvas.get_renderer()
            extent = label_text.get_window_extent(
                renderer=renderer
            )
        except Exception as exc:

            print(
                f"≡ƒÜ⌐ Flag skipped for "
                f"'{country_name}': label extent "
                f"unavailable ({exc})."
            )

            return None

        inv = ax.transData.inverted()
        x_anchor, y_anchor = inv.transform(
            (extent.x0, extent.y0)
        )

        flag.image.axes = ax
        box = AnnotationBbox(
            flag,
            (x_anchor, y_anchor),
            xybox=(-6, 0),
            xycoords="data",
            boxcoords="offset points",
            box_alignment=(1.0, 0.5),
            frameon=False,
            pad=0,
            zorder=6,
            # Labels sit left of the bars, i.e. OUTSIDE the axes
            # x-limits; without this the annotation is skipped.
            annotation_clip=False,
        )
        ax.add_artist(box)

        # Production-run visibility: one line per attached flag.
        print(f"≡ƒÜ⌐ Flag attached: {country_name}")

        return box

    # =========================================================
    # LINE CHART
    # =========================================================

    @staticmethod
    def render_line(
        script,
        data: pd.DataFrame,
        output_dir: str
    ):

        print(
            "Rendering line chart Shorts animation..."
        )

        data = VisualEngine._prepare_chart_data(
            data,
            max_items=5,
            focus=VisualEngine._resolve_focus_entities(
                script,
                data,
            ),
        )

        years = list(
            data.columns
        )

        total_frames = VisualEngine._duration_frames(
            script
        )

        fig, ax = VisualEngine._create_figure(
            script,
            "Trend over time"
        )

        y_min = float(
            data.min().min()
        )
        y_max = float(
            data.max().max()
        )

        if y_min == y_max:
            y_max = y_min + 1

        padding = (
            y_max
            - y_min
        ) * 0.12

        ax.set_xlim(
            min(years),
            max(years)
        )
        ax.set_ylim(
            y_min - padding,
            y_max + padding
        )
        ax.tick_params(
            colors=VisualEngine.SECONDARY_TEXT,
            labelsize=14
        )
        ax.grid(
            True,
            color="#27313D",
            alpha=0.55,
            linewidth=1
        )

        # INTEGER YEAR TICKS (render audit): the default locator
        # chose half-year steps on this range, printing
        # "2019.0  2019.5  2020.0 ...".  When the x-axis really IS
        # years, pin the locator to integers so the axis reads
        # "2019  2020  2021  2022".  Non-year x-axes keep the
        # default locator (see _is_year_axis).
        if VisualEngine._is_year_axis(years):
            ax.xaxis.set_major_locator(
                MaxNLocator(integer=True)
            )

        # Shared LR Atlas categorical system (gold-led, muted
        # companions) instead of a renderer-local hard-coded set.
        palette = list(design_system.CATEGORICAL_PALETTE)

        lines = []
        markers = []
        labels = []
        value_labels = []

        for index, country in enumerate(data.index):
            color = palette[
                index % len(palette)
            ]
            line, = ax.plot(
                [],
                [],
                color=color,
                linewidth=4,
                solid_capstyle="round"
            )
            # Bar-matched line treatment: round joins plus the
            # restrained winner halo on the hero series.  A
            # single-entry colour list keeps the flat categorical
            # hue EXACT (bar_face returns it untouched).
            design_system.apply_line_depth(
                line,
                [color],
                width=4,
                glow=(index == 0),
            )
            marker, = ax.plot(
                [],
                [],
                "o",
                color=color,
                markersize=10
            )
            label = ax.text(
                years[0],
                data.loc[country, years[0]],
                country,
                color=VisualEngine.TEXT_COLOR,
                fontsize=17,
                fontweight="bold",
                ha="left",
                va="center"
            )
            value_label = ax.text(
                years[0],
                data.loc[country, years[0]],
                "",
                color=color,
                fontsize=18,
                fontweight="bold",
                ha="left",
                va="bottom"
            )
            labels.append(label)
            value_labels.append(value_label)
            lines.append(line)
            markers.append(marker)

        # FRAME-SAFETY (long labels): the widest name decides how
        # far right an anchor may travel before its text would
        # leave the frame.  Measured once; short labels never hit
        # the clamp so their appearance is unchanged.
        #
        # The VALUE label shares this anchor (set_position below)
        # but is still empty at setup, so measuring names alone
        # under-reserved the right edge: "$500.0B" ran 34px past a
        # 1080px frame while "Ireland" fit.  Probe every real
        # formatted value for this indicator, park the widest
        # string in one value label, and measure names + probe.
        _anchor_indicator = VisualEngine._indicator_name(script)

        if value_labels:
            try:
                fig.canvas.draw()
                _probe_renderer = fig.canvas.get_renderer()
                _probe_label = value_labels[0]

                # Match the font the render loop will apply AFTER
                # this point (VALUE_FONT_SIZE * value_size_ratio =
                # 28.08pt): measuring at the 18pt creation font
                # under-measured every candidate by ~35%.
                _stack = design_system.label_stack(
                    padding if padding > 0 else 1.0
                )
                _probe_label.set_fontsize(
                    VisualEngine.VALUE_FONT_SIZE
                    * _stack["value_size_ratio"]
                )

                _widest_str = ""
                _widest_w = -1.0

                for _entity in data.index:
                    for _yr in years:
                        _candidate = VisualEngine._format_value(
                            float(data.loc[_entity, _yr]),
                            _anchor_indicator,
                        )
                        if not _candidate:
                            continue
                        _probe_label.set_text(_candidate)
                        try:
                            _w = _probe_label.get_window_extent(
                                renderer=_probe_renderer
                            ).width
                        except Exception:
                            continue
                        if _w > _widest_w:
                            _widest_w = _w
                            _widest_str = _candidate

                _probe_label.set_text(_widest_str)
                max_label_x = VisualEngine._max_label_anchor_data_x(
                    fig,
                    ax,
                    labels + [_probe_label],
                )
            except Exception:
                max_label_x = VisualEngine._max_label_anchor_data_x(
                    fig,
                    ax,
                    labels,
                )
            finally:
                for _vl in value_labels:
                    _vl.set_text("")
        else:
            max_label_x = VisualEngine._max_label_anchor_data_x(
                fig,
                ax,
                labels,
            )

        # LABEL HIERARCHY offsets: keep the value clear of the
        # entity name instead of stacking both on one anchor.
        label_stack = design_system.label_stack(
            padding if padding > 0 else 1.0
        )

        for value_label in value_labels:
            try:
                value_label.set_fontsize(
                    VisualEngine.VALUE_FONT_SIZE
                    * label_stack["value_size_ratio"]
                )
            except Exception:
                continue

        # ---------------------------------------------
        # END-LABEL DECLUTTER (render audit): the moving
        # name/value pair is anchored to each line's endpoint, and
        # near the right edge converging series ("Bosnia and
        # Herzegovina" vs "Turks and Caicos Islands") printed their
        # names and values on top of each other.  Measure the real
        # pixel height of one name/value block once and turn it
        # into a minimum vertical GAP in data units; the render
        # loop then pushes overlapping blocks apart along y while
        # the markers and lines stay on the true data.
        #
        # Block geometry: name is va="center" at entity_dy, value
        # is va="bottom" at value_dy (above the name), so two
        # blocks need  (value_dy - entity_dy) + value height
        # + half name height + padding  between their centres.
        # ---------------------------------------------
        _px_to_y = 0.0

        try:

            fig.canvas.draw()
            _renderer = fig.canvas.get_renderer()

            _axes_h_px = (
                ax.get_position().height
                * fig.get_figheight()
                * fig.dpi
            )
            _y_span = (y_max + padding) - (y_min - padding)
            _px_to_y = (
                _y_span / _axes_h_px if _axes_h_px > 0 else 0.0
            )

            _name_h = (
                labels[0].get_window_extent(
                    renderer=_renderer
                ).height
                * _px_to_y
            )

            # Value labels are still EMPTY at setup time, so their
            # extent would measure ~0 and the gap would come out
            # too small to separate the blocks.  Measure with a
            # representative value, then restore the empty text.
            value_labels[0].set_text("000.0")
            _value_h = (
                value_labels[0].get_window_extent(
                    renderer=_renderer
                ).height
                * _px_to_y
            )
            value_labels[0].set_text("")

            _min_label_gap = (
                (label_stack["value_dy"] - label_stack["entity_dy"])
                + _value_h
                + _name_h * 0.5
                + 10.0 * _px_to_y
            )

        except Exception:

            # Conservative fallback: ~1.8x the value offset.
            _name_h = 0.0
            _value_h = 0.0
            _min_label_gap = (
                (label_stack["value_dy"] - label_stack["entity_dy"])
                * 1.8
            )

        # ---------------------------------------------
        # COUNTRY FLAG ICONS beside each line's leading
        # marker.  Anchored to the marker's DATA coords
        # (refreshed every frame below) with a fixed
        # points-based offset so spacing stays constant.
        # ---------------------------------------------

        VisualEngine.prefetch_flags(
            list(data.index)
        )

        flag_boxes = []

        for country in data.index:

            try:

                flag = (
                    VisualEngine._get_flag_image(
                        country
                    )
                )

                if flag is None:
                    flag_boxes.append(None)
                    continue

                flag.image.axes = ax

                box = AnnotationBbox(
                    flag,
                    (
                        years[0],
                        float(
                            data.loc[
                                country, years[0]
                            ]
                        ),
                    ),
                    xybox=(-16, 0),
                    xycoords="data",
                    boxcoords="offset points",
                    box_alignment=(1.0, 0.5),
                    frameon=False,
                    pad=0,
                    zorder=6,
                    annotation_clip=False,
                )

                ax.add_artist(box)

                box.set_visible(False)

                flag_boxes.append(box)

            except Exception:

                flag_boxes.append(None)

        year_text = fig.text(
            0.5,
            0.135,
            "",
            ha="center",
            va="center",
            color=VisualEngine.ELECTRIC_BLUE,
            fontsize=44,
            fontweight="bold"
        )

        indicator = VisualEngine._indicator_name(
            script
        )

        # OPENING PAYOFF: hold the FINAL line state for the first
        # settings.OPENING_PAYOFF_SECONDS, then replay the history.
        payoff_frames = 0

        payoff_seconds = float(
            getattr(
                settings,
                "OPENING_PAYOFF_SECONDS",
                0.0,
            )
            or 0.0
        )

        if (
            payoff_seconds > 0
            and len(years) > 1
        ):
            payoff_frames = min(
                int(
                    payoff_seconds
                    * VisualEngine.FPS
                ),
                total_frames // 2,
            )

        def update(frame):
            if (
                payoff_frames
                and frame < payoff_frames
            ):
                # ENTRANCE, not a freeze: the series are already at
                # their final (payoff) values, but they now draw
                # themselves in with a stagger instead of holding a
                # dead frame.  Measured before: 0.0000% of pixels
                # changed at 0.5s.
                design_system.apply_entrance_alpha(
                    list(lines)
                    + list(markers)
                    + list(labels),
                    frame,
                    payoff_frames,
                )
                progress = 1.0
            elif payoff_frames:
                # YEAR-COUNTER SYNC FIX (render audit): frames run
                # 0..total_frames-1, so dividing by (total_frames -
                # payoff_frames) never reached progress 1.0 on the
                # final frame -- int(span) landed one year short and
                # the last frame still displayed 2021 while the data
                # ran through 2022.  The denominator must be the
                # number of REMAINING frame steps (total_frames - 1
                # - payoff_frames) so the final frame is exactly
                # progress 1.0 -> final data year.
                progress = VisualEngine.ease_in_out(
                    (frame - payoff_frames)
                    / max(
                        1,
                        total_frames - 1 - payoff_frames,
                    )
                )
            else:
                progress = VisualEngine.ease_in_out(
                    frame
                    / max(
                        1,
                        total_frames - 1
                    )
                )

            span = (
                len(years)
                - 1
            ) * progress
            year_index = min(
                int(span),
                len(years) - 1
            )
            partial = span - int(span)

            visible_years = years[
                :year_index + 1
            ]

            if (
                year_index < len(years) - 1
                and visible_years
            ):
                display_years = visible_years + [
                    years[year_index]
                    + (
                        years[year_index + 1]
                        - years[year_index]
                    )
                    * partial
                ]
            else:
                display_years = visible_years

            # Endpoint anchor per series for the END-LABEL
            # DECLUTTER pass below: the true x/y of the moving line
            # end (markers, flags and values always use these).
            endpoints = {}

            for item_index, country in enumerate(data.index):
                values = list(
                    data.loc[
                        country,
                        visible_years
                    ]
                )

                if (
                    year_index < len(years) - 1
                    and values
                ):
                    current_value = data.loc[
                        country,
                        years[year_index]
                    ]
                    next_value = data.loc[
                        country,
                        years[year_index + 1]
                    ]
                    values = values + [
                        current_value
                        + (
                            next_value
                            - current_value
                        )
                        * partial
                    ]

                lines[item_index].set_data(
                    display_years,
                    values
                )

                flag_box = (
                    flag_boxes[item_index]
                )

                if values:
                    x = display_years[-1]
                    y = values[-1]

                    markers[item_index].set_data(
                        [x],
                        [y]
                    )

                    endpoints[item_index] = (x, y)

                    if flag_box is not None:
                        flag_box.xy = (x, y)
                        flag_box.set_visible(True)

                elif flag_box is not None:
                    flag_box.set_visible(False)

            # --------------------------------------------------
            # END-LABEL DECLUTTER pass: push overlapping name/value
            # blocks apart along Y so two converging endpoints can
            # never print on top of each other ("Bosnia and
            # Herzegovina" over "Turks and Caicos Islands" at the
            # right edge).  Only the TEXT stack moves; markers,
            # lines and the printed values stay on the true data.
            # --------------------------------------------------
            if endpoints:

                ordered_ends = sorted(
                    endpoints.items(),
                    key=lambda entry: entry[1][1],
                )

                placed = {}
                previous = None

                for item_index, (_x, true_y) in ordered_ends:

                    stacked_y = true_y

                    if (
                        previous is not None
                        and stacked_y < previous + _min_label_gap
                    ):
                        stacked_y = previous + _min_label_gap

                    placed[item_index] = stacked_y
                    previous = stacked_y

                # Keep the whole stack inside the axes: if the
                # topmost block was pushed past the upper limit,
                # shift the stack back down (relative separation is
                # preserved); clamp the bottom the same way.
                # NOTE: get_ylim() is (bottom, top).
                y_low, y_high = ax.get_ylim()

                top_item = max(
                    placed,
                    key=lambda item: placed[item],
                )
                top_room = (
                    y_high
                    - label_stack["value_dy"]
                    - _value_h
                    - 4.0 * _px_to_y
                )

                excess = placed[top_item] - top_room

                if excess > 0:
                    for item in placed:
                        placed[item] -= excess

                bottom_item = min(
                    placed,
                    key=lambda item: placed[item],
                )
                bottom_room = (
                    y_low
                    + 4.0 * _px_to_y
                    + _name_h * 0.5
                    - label_stack["entity_dy"]
                )

                deficit = bottom_room - placed[bottom_item]

                if deficit > 0:
                    for item in placed:
                        placed[item] += deficit

                for item_index, (x, true_y) in endpoints.items():

                    stacked_y = placed.get(item_index, true_y)

                    # FRAME-SAFETY: the name rides the moving
                    # leading edge, so it would run past the
                    # right edge of the frame at the end of the
                    # sweep.  Clamp the anchor; short labels never
                    # reach the limit and look unchanged.
                    label_x = min(
                        x + 0.15,
                        max_label_x,
                    )

                    # LABEL HIERARCHY: the value used to share
                    # this exact anchor with the entity name, so
                    # "60.0" rendered ON TOP of "Central African
                    # Republic" (visible in real frames).  Lift
                    # the value clear of the name -- the NAME is
                    # the story, the number is support.
                    labels[item_index].set_position(
                        (
                            label_x,
                            stacked_y
                            + label_stack["entity_dy"],
                        )
                    )
                    value_labels[item_index].set_position(
                        (
                            label_x,
                            stacked_y
                            + label_stack["value_dy"],
                        )
                    )
                    value_labels[item_index].set_text(
                        VisualEngine._format_value(
                            true_y,
                            indicator
                        )
                    )

            year_text.set_text(
                str(
                    years[year_index]
                )
            )

            return (
                lines
                + markers
                + labels
                + value_labels
                + [
                    year_text
                ]
                + [
                    box
                    for box in flag_boxes
                    if box is not None
                ]
            )

        return VisualEngine._save_animation(
            fig,
            update,
            total_frames,
            output_dir,
            "line_chart.mp4"
        )

    # =========================================================
    # AREA CHART
    # =========================================================

    @staticmethod
    def render_area(
        script,
        data: pd.DataFrame,
        output_dir: str
    ):

        print(
            "Rendering area chart Shorts animation..."
        )

        data = VisualEngine._prepare_chart_data(
            data,
            max_items=5,
            focus=VisualEngine._resolve_focus_entities(
                script,
                data,
            ),
        )

        years = list(
            data.columns
        )

        total_frames = VisualEngine._duration_frames(
            script
        )

        fig, ax = VisualEngine._create_figure(
            script,
            "Area trend over time"
        )

        # -------------------------------------------------
        # GENUINE AREA CHART
        #
        # A real time-series area chart: one translucent
        # filled region per entity under its own trend line,
        # swept left to right across a REAL, visible year
        # axis.  (The bar-race version this replaced hid the
        # x-axis and drew horizontal bars instead.)
        #
        # fill_between() is used deliberately rather than
        # stackplot(): these are independent per-country
        # indicators, so stacking would imply a total that
        # does not exist.  Regions are alpha-blended and
        # depth-sorted so the largest series sits at the
        # back and smaller ones stay readable on top.
        # -------------------------------------------------

        entities = list(
            data.index
        )

        # Themed / rotated per-video palette, chosen once by
        # render_scenes(); resolved lazily when this
        # renderer is called directly.
        palette = (
            VisualEngine._ACTIVE_PALETTE
            or VisualEngine.select_palette(script)
        )

        if not palette:
            palette = ["#D4AF37"]

        # Depth sort: biggest series drawn first (lowest
        # zorder) so the smaller ones stay visible.
        order = sorted(
            entities,
            key=lambda name: float(
                data.loc[name].max()
            ),
            reverse=True
        )

        # Numeric x positions.  Season-style columns
        # ("2024-25") coerce to their starting year; a frame
        # with no parsable year falls back to even spacing.
        year_positions = []

        for column in years:
            parsed = coerce_year_label(
                column
            )
            year_positions.append(
                parsed
                if parsed is not None
                else 0
            )

        if len(set(
            year_positions
        )) != len(year_positions):
            year_positions = list(
                range(len(years))
            )

        min_x = min(
            year_positions
        )
        max_x = max(
            year_positions
        )
        x_span = max_x - min_x

        if x_span <= 0:
            x_span = 1.0

        # Regions are filled down to the axis floor.
        baseline = min(
            0.0,
            float(data.min().min())
        )
        top = float(
            data.max().max()
        )

        if top <= baseline:
            top = baseline + 1.0

        # Extra room on the right for the leading-edge
        # name / value labels.
        ax.set_xlim(
            min_x - x_span * 0.03,
            max_x + x_span * 0.30
        )
        ax.set_ylim(
            baseline,
            top + (top - baseline) * 0.14
        )

        # A REAL time axis: year ticks stay visible.
        tick_stride = max(
            1,
            len(years) // 6
        )
        tick_indexes = list(
            range(0, len(years), tick_stride)
        )

        ax.set_xticks([
            year_positions[i]
            for i in tick_indexes
        ])
        ax.set_xticklabels([
            str(years[i])
            for i in tick_indexes
        ])
        ax.tick_params(
            colors=VisualEngine.SECONDARY_TEXT,
            labelsize=15
        )
        ax.grid(
            True,
            color="#27313D",
            alpha=0.5,
            linewidth=1
        )

        VisualEngine.prefetch_flags(
            entities
        )

        lines = []
        fills = []
        labels = []
        value_labels = []
        flag_boxes = []

        indicator = VisualEngine._indicator_name(
            script
        )

        for depth, entity in enumerate(order):

            color = palette[
                depth % len(palette)
            ]

            line, = ax.plot(
                [],
                [],
                color=color,
                linewidth=3.5,
                solid_capstyle="round",
                zorder=10 + depth
            )
            # Bar-matched line treatment; depth 0 is the biggest
            # series (the hero), so only it carries the halo.
            design_system.apply_line_depth(
                line,
                [color],
                width=3.5,
                glow=(depth == 0),
            )
            lines.append(line)

            fills.append(
                ax.fill_between(
                    [min_x, min_x],
                    [baseline, baseline],
                    baseline,
                    color=color,
                    alpha=0.30,
                    linewidth=0,
                    zorder=depth
                )
            )

            labels.append(
                ax.text(
                    min_x,
                    baseline,
                    entity,
                    color=VisualEngine.TEXT_COLOR,
                    fontsize=17,
                    fontweight="bold",
                    ha="left",
                    va="center"
                )
            )

            value_labels.append(
                ax.text(
                    min_x,
                    baseline,
                    "",
                    color=color,
                    fontsize=18,
                    fontweight="bold",
                    ha="left",
                    va="bottom"
                )
            )

            # Flag rides the leading edge of the region.
            flag_box = None

            try:
                flag = (
                    VisualEngine._get_flag_image(
                        entity
                    )
                )

                if flag is not None:

                    flag.image.axes = ax

                    flag_box = AnnotationBbox(
                        flag,
                        (min_x, baseline),
                        xybox=(-16, 0),
                        xycoords="data",
                        boxcoords="offset points",
                        box_alignment=(1.0, 0.5),
                        frameon=False,
                        pad=0,
                        zorder=20,
                        annotation_clip=False
                    )

                    ax.add_artist(flag_box)
                    flag_box.set_visible(False)

            except Exception:
                flag_box = None

            flag_boxes.append(flag_box)

        # FRAME-SAFETY (long labels): see render_line.  Clamp the
        # moving leading-edge anchor so the name can never leave
        # the frame.
        #
        # Same value-label caveat as render_line: the value shares
        # this anchor but is still empty here, so probe the widest
        # real formatted value first or "$500.0B" overruns the
        # right edge while short names fit.
        if value_labels:
            try:
                fig.canvas.draw()
                _probe_renderer = fig.canvas.get_renderer()
                _probe_label = value_labels[0]

                # Match the font the render loop will apply AFTER
                # this point (VALUE_FONT_SIZE * value_size_ratio):
                # measuring at the 18pt creation font under-measured
                # every candidate by ~35%.
                try:
                    _span = float(
                        data.to_numpy().max() - data.to_numpy().min()
                    )
                except Exception:
                    _span = 1.0
                _stack = design_system.label_stack(_span)
                _probe_label.set_fontsize(
                    VisualEngine.VALUE_FONT_SIZE
                    * _stack["value_size_ratio"]
                )

                _widest_str = ""
                _widest_w = -1.0

                for _entity in data.index:
                    for _yr in years:
                        _candidate = VisualEngine._format_value(
                            float(data.loc[_entity, _yr]),
                            indicator,
                        )
                        if not _candidate:
                            continue
                        _probe_label.set_text(_candidate)
                        try:
                            _w = _probe_label.get_window_extent(
                                renderer=_probe_renderer
                            ).width
                        except Exception:
                            continue
                        if _w > _widest_w:
                            _widest_w = _w
                            _widest_str = _candidate

                _probe_label.set_text(_widest_str)
                max_label_x = VisualEngine._max_label_anchor_data_x(
                    fig,
                    ax,
                    labels + [_probe_label],
                )
            except Exception:
                max_label_x = VisualEngine._max_label_anchor_data_x(
                    fig,
                    ax,
                    labels,
                )
            finally:
                for _vl in value_labels:
                    _vl.set_text("")
        else:
            max_label_x = VisualEngine._max_label_anchor_data_x(
                fig,
                ax,
                labels,
            )

        # LABEL HIERARCHY offsets: keep the value clear of the
        # entity name instead of stacking both on one anchor.
        try:
            _area_span = float(
                data.to_numpy().max() - data.to_numpy().min()
            )
        except Exception:
            _area_span = 1.0

        label_stack = design_system.label_stack(_area_span)

        for value_label in value_labels:
            try:
                value_label.set_fontsize(
                    VisualEngine.VALUE_FONT_SIZE
                    * label_stack["value_size_ratio"]
                )
            except Exception:
                continue

        year_text = fig.text(
            0.5,
            0.135,
            "",
            ha="center",
            va="center",
            color=VisualEngine.ELECTRIC_BLUE,
            fontsize=44,
            fontweight="bold"
        )

        # OPENING PAYOFF: hold the FINAL area state for the
        # first settings.OPENING_PAYOFF_SECONDS, then replay
        # the history (shared with the other renderers).
        payoff_frames = 0

        payoff_seconds = float(
            getattr(
                settings,
                "OPENING_PAYOFF_SECONDS",
                0.0,
            ) or 0.0
        )

        if (
            payoff_seconds > 0
            and len(years) > 1
        ):
            payoff_frames = min(
                int(
                    payoff_seconds
                    * VisualEngine.FPS
                ),
                total_frames // 2
            )

        def update(frame):
            if (
                payoff_frames
                and frame < payoff_frames
            ):
                # ENTRANCE, not a freeze: the regions are already at
                # their final (payoff) values, but they now build
                # themselves in with a stagger instead of holding a
                # dead frame.  Measured before: 0.0000% of pixels
                # changed at 0.5s.
                design_system.apply_entrance_alpha(
                    list(lines)
                    + list(fills)
                    + list(labels),
                    frame,
                    payoff_frames,
                )
                progress = 1.0
            elif payoff_frames:
                # YEAR-COUNTER SYNC FIX (same as render_line): the
                # final frame must land on progress 1.0 or the year
                # counter stops one data year short of the dataset.
                progress = VisualEngine.ease_in_out(
                    (frame - payoff_frames)
                    / max(
                        1,
                        total_frames - 1 - payoff_frames
                    )
                )
            else:
                progress = VisualEngine.ease_in_out(
                    frame
                    / max(
                        1,
                        total_frames - 1
                    )
                )

            span = (
                len(year_positions) - 1
            ) * progress

            year_index = min(
                int(span),
                len(year_positions) - 1
            )
            partial = span - int(span)

            visible_columns = years[
                :year_index + 1
            ]

            draw_x = year_positions[
                :year_index + 1
            ]

            # Carry an interpolated leading edge one step
            # ahead of the last settled year.
            if year_index < len(years) - 1:
                draw_x = draw_x + [
                    year_positions[year_index]
                    + (
                        year_positions[year_index + 1]
                        - year_positions[year_index]
                    ) * partial
                ]

            # A lone point draws neither a line nor an area,
            # so collapse degenerate frames onto a
            # zero-width segment instead of building a
            # self-intersecting polygon.
            if len(draw_x) < 2:
                draw_x = [
                    draw_x[0],
                    draw_x[0]
                ]

            for slot, entity in enumerate(order):

                draw_y = []

                for value in data.loc[
                    entity,
                    visible_columns
                ].tolist():
                    draw_y.append(
                        0.0
                        if pd.isna(value)
                        else float(value)
                    )

                if year_index < len(years) - 1:

                    current = data.loc[
                        entity,
                        years[year_index]
                    ]
                    following = data.loc[
                        entity,
                        years[year_index + 1]
                    ]

                    if not (
                        pd.isna(current)
                        or pd.isna(following)
                    ):
                        draw_y.append(
                            float(current)
                            + (
                                float(following)
                                - float(current)
                            ) * partial
                        )

                if len(draw_y) < len(draw_x):
                    tail = (
                        draw_y[-1]
                        if draw_y
                        else baseline
                    )
                    draw_y = draw_y + [
                        tail
                    ] * (
                        len(draw_x) - len(draw_y)
                    )

                lines[slot].set_data(
                    draw_x,
                    draw_y
                )

                # Rebuild the filled region under the line.
                vertices = np.column_stack(
                    [draw_x, draw_y]
                )
                floor = np.array([
                    [draw_x[-1], baseline],
                    [draw_x[0], baseline]
                ])

                fills[slot].set_verts(
                    [np.vstack([
                        vertices,
                        floor
                    ])]
                )

                leading_x = (
                    draw_x[-1]
                    + x_span * 0.012
                )
                leading_y = draw_y[-1]

                # FRAME-SAFETY: same clamp as the line chart --
                # the name rides the moving leading edge and must
                # never run past the right edge of the frame.
                label_x = min(
                    leading_x,
                    max_label_x,
                )

                labels[slot].set_position(
                    (label_x, leading_y + label_stack["entity_dy"])
                )
                value_labels[slot].set_position(
                    (
                        label_x,
                        leading_y + label_stack["value_dy"],
                    )
                )
                value_labels[slot].set_text(
                    VisualEngine._format_value(
                        leading_y,
                        indicator
                    )
                )

                box = flag_boxes[slot]

                if box is not None:
                    if len(draw_x) >= 2:
                        box.xy = (
                            draw_x[-1],
                            leading_y
                        )
                        box.set_visible(True)
                    else:
                        box.set_visible(False)

            year_text.set_text(
                str(years[year_index])
            )

            return (
                lines
                + fills
                + labels
                + value_labels
                + [year_text]
                + [
                    box
                    for box in flag_boxes
                    if box is not None
                ]
            )

        return VisualEngine._save_animation(
            fig,
            update,
            total_frames,
            output_dir,
            "area_chart.mp4"
        )

    # =========================================================
    # SLOPE CHART
    # =========================================================

    @staticmethod
    def render_slope(
        script,
        data: pd.DataFrame,
        output_dir: str
    ):

        print(
            "Rendering slope chart Shorts animation..."
        )

        data = VisualEngine._prepare_chart_data(
            data,
            max_items=8,
            focus=VisualEngine._resolve_focus_entities(
                script,
                data,
            ),
            # SLOPE ENDPOINT HONESTY: never forward/back-fill the
            # comparison window -- a fabricated start or end value
            # would be a fabricated comparison.
            fill=False,
        )

        # Years with NO observations at all are not part of the
        # comparison window; drop them before fixing the edges so
        # an all-NaN trailing year cannot silently become "now".
        data = data.dropna(
            axis=1,
            how="all"
        )

        years = list(
            data.columns
        )

        if len(years) < 2:
            raise ValueError(
                "Slope chart needs at least two years with "
                "observed values to compare."
            )

        start_year = years[0]
        end_year = years[-1]

        # TRUE ENDPOINTS: the raw first/last COLUMN values, real
        # observations only.  Ranks used to drive the y-coords
        # here, which made every line flat -- identical rank rows
        # start to end regardless of how the metric moved.  y is
        # now the metric itself; entities missing either edge are
        # EXCLUDED (with a printed note), never silently filled.
        endpoints = {}
        skipped = []

        for country in data.index:

            v_start = data.loc[country, start_year]
            v_end = data.loc[country, end_year]

            if pd.isna(v_start) or pd.isna(v_end):
                skipped.append(country)
                continue

            endpoints[country] = (
                float(v_start),
                float(v_end),
            )

        if skipped:
            print(
                "  slope: excluded (missing "
                f"{start_year} and/or {end_year} value): "
                + ", ".join(skipped)
            )

        if not endpoints:
            raise ValueError(
                "Slope chart needs at least one entity with "
                f"values in both {start_year} and {end_year}."
            )

        data = data.loc[
            [
                country
                for country in data.index
                if country in endpoints
            ]
        ]

        indicator = VisualEngine._indicator_name(
            script
        )

        # VALUE-BASED Y: each line's slope IS the metric change.
        all_values = [
            value
            for pair in endpoints.values()
            for value in pair
        ]

        y_low = min(all_values)
        y_high = max(all_values)

        if y_low == y_high:
            pad = (
                abs(y_low) * 0.10
                if y_low
                else 1.0
            )
        else:
            pad = (y_high - y_low) * 0.12

        y_lo = y_low - pad
        y_hi = y_high + pad

        total_frames = VisualEngine._duration_frames(
            script
        )

        fig, ax = VisualEngine._create_figure(
            script,
            "Then vs now"
        )

        ax.set_xlim(
            -0.25,
            1.25
        )
        ax.set_ylim(
            y_lo,
            y_hi
        )
        ax.set_xticks(
            [
                0,
                1
            ]
        )
        ax.set_xticklabels(
            [
                str(start_year),
                str(end_year)
            ],
            color=VisualEngine.TEXT_COLOR,
            fontsize=26,
            fontweight="bold"
        )
        ax.set_yticks([])

        ax.vlines(
            [
                0,
                1
            ],
            y_lo,
            y_hi,
            color="#27313D",
            linewidth=2
        )

        # ---------------------------------------------
        # LABEL ROWS (value-scale de-collision): with value-based
        # y, near-equal values park name labels on top of each
        # other (rank rows could never collide).  Solve each side's
        # rows in VALUE units.  The gap is TWO label-block heights
        # because a value label flips above/below its row (va
        # top/bottom keeps its own line from running through the
        # number), so worst-case neighbours need block+block.
        # ---------------------------------------------

        axes_px = (
            ax.get_position().height
            * fig.get_figheight()
            * fig.dpi
        )

        value_pt = (
            VisualEngine.VALUE_FONT_SIZE
            * design_system.label_stack(
                pad if pad > 0 else 1.0
            )["value_size_ratio"]
        )

        block_px = (
            max(
                16.0,
                float(value_pt),
            )
            * fig.dpi
            / 72.0
            * 1.2
        )

        row_gap = (
            2.0
            * block_px
            / max(1.0, axes_px)
            * (y_hi - y_lo)
        )

        left_rows = (
            VisualEngine._solve_label_positions(
                [
                    endpoints[country][0]
                    for country in data.index
                ],
                row_gap,
                y_lo,
                y_hi,
            )
        )

        right_rows = (
            VisualEngine._solve_label_positions(
                [
                    endpoints[country][1]
                    for country in data.index
                ],
                row_gap,
                y_lo,
                y_hi,
            )
        )

        lines = []
        left_labels = []
        right_labels = []
        left_value_labels = []
        right_value_labels = []

        for index, country in enumerate(data.index):
            color = VisualEngine._get_bar_color(
                index
            )
            v_start, v_end = endpoints[country]
            rising = v_end >= v_start
            line, = ax.plot(
                [0, 0],
                [
                    v_start,
                    v_start
                ],
                color=color,
                linewidth=4,
                solid_capstyle="round",
                marker="o",
                markersize=9
            )
            # Bar-matched line treatment; index 0 is the lead
            # series, so only it carries the halo.
            design_system.apply_line_depth(
                line,
                [color],
                width=4,
                glow=(index == 0),
            )
            # NAME sits outside the axes at its solved row; the
            # VALUE chip sits just inside, on the same row, and
            # flips to the side AWAY from its own slope so the
            # line never runs through its own number.  The LINE
            # stays at the raw data y -- only the label rows are
            # de-collided.
            left_label = ax.text(
                -0.04,
                left_rows[index],
                country,
                ha="right",
                va="center",
                color=VisualEngine.TEXT_COLOR,
                fontsize=16,
                fontweight="bold"
            )
            right_label = ax.text(
                1.04,
                right_rows[index],
                country,
                ha="left",
                va="center",
                color=VisualEngine.TEXT_COLOR,
                fontsize=16,
                fontweight="bold",
                alpha=0.0
            )
            left_value_label = ax.text(
                0.02,
                left_rows[index],
                VisualEngine._format_value(
                    v_start,
                    indicator,
                ),
                ha="left",
                va="top" if rising else "bottom",
                color=color,
                fontsize=value_pt,
                fontweight="bold"
            )
            right_value_label = ax.text(
                0.98,
                right_rows[index],
                VisualEngine._format_value(
                    v_end,
                    indicator,
                ),
                ha="right",
                va="bottom" if rising else "top",
                color=color,
                fontsize=value_pt,
                fontweight="bold",
                alpha=0.0
            )
            lines.append(line)
            left_labels.append(left_label)
            right_labels.append(right_label)
            left_value_labels.append(left_value_label)
            right_value_labels.append(right_value_label)

        # ---------------------------------------------
        # FRAME-SAFETY (long labels): slope puts the name
        # OUTSIDE the two slope endpoints, so a long name runs
        # off whichever edge it is on.  Measured before the fix:
        # "Democratic Republic of the Congo" started at
        # x0 = -170px, i.e. 170px off the left of a 1080px
        # frame.
        #
        # These labels never move (update() only fades alpha), so
        # a one-time fit persists for the whole video.  Both
        # sides are constrained because the left and right
        # labels overflow independently.
        # ---------------------------------------------

        VisualEngine._constrain_labels_in_frame(
            fig,
            ax,
            left_labels,
            left_margin_px=24.0,
            right_margin_px=0.0,
            min_font_pt=11.0,
        )

        VisualEngine._constrain_labels_in_frame(
            fig,
            ax,
            right_labels,
            left_margin_px=0.0,
            right_margin_px=24.0,
            min_font_pt=11.0,
        )

        # ---------------------------------------------
        # COUNTRY FLAG ICONS beside each end-of-slope
        # name label.  Positions never move here (only
        # alpha animates), so one-time attachment is
        # enough; boxes fade in step with labels below.
        # ---------------------------------------------

        VisualEngine.prefetch_flags(
            list(data.index)
        )

        try:
            fig.canvas.draw()
        except Exception:
            pass

        slope_flag_boxes = []

        for slope_i, slope_country in enumerate(
            data.index
        ):

            try:

                slope_flag_boxes.append(
                    VisualEngine._attach_country_flag(
                        ax,
                        fig,
                        slope_country,
                        right_labels[slope_i],
                    )
                )

            except Exception:

                slope_flag_boxes.append(None)

        for slope_box in slope_flag_boxes:
            if slope_box is not None:
                slope_box.set_alpha(0.0)

        def update(frame):
            progress = VisualEngine.ease_in_out(
                frame
                / max(
                    1,
                    total_frames - 1
                )
            )

            for index, country in enumerate(data.index):
                y0, y1 = endpoints[country]
                lines[index].set_data(
                    [
                        0,
                        progress
                    ],
                    [
                        y0,
                        y0 + (
                            y1 - y0
                        ) * progress
                    ]
                )
                # The arrival side (name + value + flag) fades in
                # as the line reaches it; the departure side is
                # already on screen at frame 0.
                right_labels[index].set_alpha(
                    progress
                )
                right_value_labels[index].set_alpha(
                    progress
                )
                if (
                    slope_flag_boxes[index]
                    is not None
                ):
                    slope_flag_boxes[
                        index
                    ].set_alpha(progress)

            return (
                lines
                + left_labels
                + right_labels
                + left_value_labels
                + right_value_labels
                + [
                    box
                    for box in slope_flag_boxes
                    if box is not None
                ]
            )

        return VisualEngine._save_animation(
            fig,
            update,
            total_frames,
            output_dir,
            "slope_chart.mp4"
        )

    # =========================================================
    # BUBBLE CHART
    # =========================================================

    @staticmethod
    def render_bubble(
        script,
        data: pd.DataFrame,
        output_dir: str
    ):

        print(
            "Rendering bubble chart Shorts animation..."
        )

        raw_data = VisualEngine._normalize_index(
            data.copy()
        )
        raw_columns = {
            str(column).strip().lower(): column
            for column in raw_data.columns
        }

        if (
            "x" in raw_columns
            and "y" in raw_columns
        ):
            return VisualEngine._render_xy_bubble(
                script,
                raw_data,
                raw_columns["x"],
                raw_columns["y"],
                raw_columns.get("size"),
                output_dir
            )

        data = VisualEngine._prepare_chart_data(
            data,
            max_items=8,
            focus=VisualEngine._resolve_focus_entities(
                script,
                data,
            ),
        )

        years = list(
            data.columns
        )

        total_frames = VisualEngine._duration_frames(
            script
        )

        fig, ax = VisualEngine._create_figure(
            script,
            "Relationship view"
        )

        indicator = VisualEngine._indicator_name(
            script
        )

        if True:
            latest_year = years[-1]
            values = data[latest_year]

            ax.set_axis_off()
            sorted_values = values.sort_values(
                ascending=True
            )

            # --------------------------------------------------
            # FRAME-SAFETY (fallback ranking): y-tick labels are
            # NEVER drawn with axison=False (pixel-diff verified:
            # hiding them changed 0 pixels), and their geometry
            # ran off the left edge anyway -- measured x0 =
            # -322px for "Democratic Republic of the Congo", so
            # the bars rendered ANONYMOUS and the flags anchored
            # to invisible text.  Draw the names as real axes
            # texts right-anchored in the left gutter (the
            # render_bar_race pattern) and run them through the
            # flag-aware fit guard so long names shrink/shift
            # instead of leaving the frame.
            # --------------------------------------------------
            bar_lo = min(
                0.0,
                float(sorted_values.min()),
            )
            bar_hi = max(
                0.0,
                float(sorted_values.max()),
            )
            if bar_hi - bar_lo <= 0:
                bar_hi = bar_lo + 1.0

            span = bar_hi - bar_lo

            bars = ax.barh(
                range(
                    len(sorted_values)
                ),
                sorted_values.values,
                color=VisualEngine.ELECTRIC_BLUE,
                alpha=0.0
            )

            ax.set_xlim(
                bar_lo - span * 0.18,
                bar_hi + span * 0.18,
            )

            name_anchor_x = bar_lo - span * 0.055

            ax.set_yticks([])
            ax.set_xticks([])
            ax.set_title(
                "Single metric available",
                color=VisualEngine.MAGENTA_PURPLE,
                fontsize=22,
                fontweight="bold"
            )
            fig.text(
                0.5,
                0.135,
                "Bubble relationships need explicit x and y metrics",
                ha="center",
                va="center",
                color=VisualEngine.SECONDARY_TEXT,
                fontsize=18
            )

            name_labels = [
                ax.text(
                    name_anchor_x,
                    position,
                    str(name),
                    va="center",
                    ha="right",
                    color=VisualEngine.TEXT_COLOR,
                    fontsize=VisualEngine.COUNTRY_FONT_SIZE,
                    fontweight="bold",
                    clip_on=False,
                )
                for position, name in enumerate(sorted_values.index)
            ]

            VisualEngine._fit_labels_in_frame(
                fig,
                ax,
                name_labels,
            )

            # -----------------------------------------
            # COUNTRY FLAG ICONS beside each ranked-bar
            # label -- this fallback view IS a ranking,
            # so every bar gets its country's flag.
            # -----------------------------------------

            VisualEngine.prefetch_flags(
                sorted_values.index.tolist()
            )

            try:
                fig.canvas.draw()
            except Exception:
                pass

            for flag_i, flag_country in enumerate(
                sorted_values.index
            ):

                if flag_i >= len(name_labels):
                    break

                try:

                    VisualEngine._attach_country_flag(
                        ax,
                        fig,
                        str(flag_country),
                        name_labels[flag_i],
                    )

                except Exception:
                    continue

            def update_single(frame):
                progress = VisualEngine.ease_in_out(
                    frame
                    / max(
                        1,
                        total_frames - 1
                    )
                )
                for bar in bars:
                    bar.set_alpha(progress)
                return list(bars) + name_labels

            return VisualEngine._save_animation(
                fig,
                update_single,
                total_frames,
                output_dir,
                "bubble_chart.mp4"
            )

        first_year = years[0]
        latest_year = years[-1]
        x_values = data[first_year]
        y_values = data[latest_year]
        size_values = (
            y_values
            - x_values
        ).abs()

        if float(size_values.max()) == 0:
            size_values = y_values.abs()

        max_size = float(
            size_values.max()
        )
        if max_size <= 0:
            max_size = 1.0

        ax.set_xlabel(
            str(first_year),
            color=VisualEngine.SECONDARY_TEXT,
            fontsize=17
        )
        ax.set_ylabel(
            str(latest_year),
            color=VisualEngine.SECONDARY_TEXT,
            fontsize=17
        )
        ax.tick_params(
            colors=VisualEngine.SECONDARY_TEXT,
            labelsize=13
        )
        ax.grid(
            True,
            color="#27313D",
            alpha=0.55
        )

        x_padding = (
            float(x_values.max())
            - float(x_values.min())
        ) * 0.12 or 1
        y_padding = (
            float(y_values.max())
            - float(y_values.min())
        ) * 0.12 or 1

        ax.set_xlim(
            float(x_values.min()) - x_padding,
            float(x_values.max()) + x_padding
        )
        ax.set_ylim(
            float(y_values.min()) - y_padding,
            float(y_values.max()) + y_padding
        )

        scatter = ax.scatter(
            x_values,
            y_values,
            s=[
                80
                for _ in data.index
            ],
            c=[
                VisualEngine._get_bar_color(index)
                for index, _
                in enumerate(data.index)
            ],
            alpha=0.78,
            edgecolors=VisualEngine.TEXT_COLOR,
            linewidths=1.5
        )

        labels = []

        for country in data.index:
            label = ax.text(
                x_values[country],
                y_values[country],
                country,
                color=VisualEngine.TEXT_COLOR,
                fontsize=14,
                fontweight="bold",
                ha="left",
                va="bottom",
                alpha=0.0
            )
            labels.append(label)

        # ---------------------------------------------
        # FRAME-SAFETY (long labels): a bubble label is
        # anchored at its bubble with ha="left", so a long
        # name on a bubble near the right edge runs off the
        # frame.  Measured before this guard: "Central African
        # Republic" ended at x1 = 1166px on a 1080px frame.
        #
        # Positions are static here (update() only fades alpha),
        # so a one-time fit persists for the whole video.
        # ---------------------------------------------

        VisualEngine._constrain_labels_in_frame(
            fig,
            ax,
            labels,
            left_margin_px=0.0,
            right_margin_px=24.0,
            min_font_pt=9.0,
        )

        # ---------------------------------------------
        # COUNTRY FLAG ICONS beside each bubble label.
        # Label positions are static here; flags simply
        # fade in alongside their text.
        # ---------------------------------------------

        VisualEngine.prefetch_flags(
            list(data.index)
        )

        try:
            fig.canvas.draw()
        except Exception:
            pass

        bubble_flag_boxes = []

        for bubble_i, bubble_country in enumerate(
            data.index
        ):

            try:

                box = (
                    VisualEngine._attach_country_flag(
                        ax,
                        fig,
                        bubble_country,
                        labels[bubble_i],
                    )
                )

                if box is not None:
                    box.set_alpha(0.0)

                bubble_flag_boxes.append(box)

            except Exception:

                bubble_flag_boxes.append(None)

        fig.text(
            0.5,
            0.135,
            f"{first_year} vs {latest_year} | "
            f"bubble size = change in {indicator}",
            ha="center",
            va="center",
            color=VisualEngine.SECONDARY_TEXT,
            fontsize=18
        )

        def update(frame):
            progress = VisualEngine.ease_in_out(
                frame
                / max(
                    1,
                    total_frames - 1
                )
            )
            sizes = [
                160
                + (
                    float(size_values[country])
                    / max_size
                ) * 1250
                * progress
                for country in data.index
            ]
            scatter.set_sizes(
                sizes
            )
            scatter.set_alpha(
                0.35
                + 0.45 * progress
            )
            bubble_fade = max(
                0.0,
                (progress - 0.35) / 0.65
            )
            for label in labels:
                label.set_alpha(bubble_fade)
            for box in bubble_flag_boxes:
                if box is not None:
                    box.set_alpha(bubble_fade)
            return [
                scatter
            ] + labels + [
                box
                for box in bubble_flag_boxes
                if box is not None
            ]

        return VisualEngine._save_animation(
            fig,
            update,
            total_frames,
            output_dir,
            "bubble_chart.mp4"
        )

    @staticmethod
    def _render_xy_bubble(
        script,
        data: pd.DataFrame,
        x_column,
        y_column,
        size_column,
        output_dir: str
    ):

        data[x_column] = pd.to_numeric(
            data[x_column],
            errors="coerce"
        )
        data[y_column] = pd.to_numeric(
            data[y_column],
            errors="coerce"
        )

        if size_column is not None:
            data[size_column] = pd.to_numeric(
                data[size_column],
                errors="coerce"
            )

        required = [
            x_column,
            y_column
        ]
        data = data.dropna(
            subset=required
        )

        if data.empty:
            raise ValueError(
                "No usable x/y data available "
                "for bubble chart."
            )

        if len(data.index) > 8:
            data = data.head(8)

        total_frames = VisualEngine._duration_frames(
            script
        )

        fig, ax = VisualEngine._create_figure(
            script,
            "Relationship view"
        )

        x_values = data[x_column]
        y_values = data[y_column]

        if size_column is not None:
            size_values = data[size_column].abs()
        else:
            size_values = pd.Series(
                [
                    1.0
                    for _ in data.index
                ],
                index=data.index
            )

        max_size = float(
            size_values.max()
        )
        if max_size <= 0:
            max_size = 1.0

        ax.set_xlabel(
            str(x_column),
            color=VisualEngine.SECONDARY_TEXT,
            fontsize=17
        )
        ax.set_ylabel(
            str(y_column),
            color=VisualEngine.SECONDARY_TEXT,
            fontsize=17
        )
        ax.tick_params(
            colors=VisualEngine.SECONDARY_TEXT,
            labelsize=13
        )
        ax.grid(
            True,
            color="#27313D",
            alpha=0.55
        )

        x_padding = (
            float(x_values.max())
            - float(x_values.min())
        ) * 0.12 or 1
        y_padding = (
            float(y_values.max())
            - float(y_values.min())
        ) * 0.12 or 1

        ax.set_xlim(
            float(x_values.min()) - x_padding,
            float(x_values.max()) + x_padding
        )
        ax.set_ylim(
            float(y_values.min()) - y_padding,
            float(y_values.max()) + y_padding
        )

        scatter = ax.scatter(
            x_values,
            y_values,
            s=[
                80
                for _ in data.index
            ],
            c=[
                VisualEngine._get_bar_color(index)
                for index, _
                in enumerate(data.index)
            ],
            alpha=0.78,
            edgecolors=VisualEngine.TEXT_COLOR,
            linewidths=1.5
        )

        labels = []

        for country in data.index:
            labels.append(
                ax.text(
                    x_values[country],
                    y_values[country],
                    country,
                    color=VisualEngine.TEXT_COLOR,
                    fontsize=14,
                    fontweight="bold",
                    ha="left",
                    va="bottom",
                    alpha=0.0
                )
            )

        # ---------------------------------------------
        # FRAME-SAFETY (long labels): this is the path an
        # x/y dataset actually takes.  The name is anchored at
        # its bubble with ha="left", so a long name on a bubble
        # near the right edge runs off the frame.  Measured
        # before this guard: "Central African Republic" ended
        # at x1 = 1166px on a 1080px frame.
        #
        # Positions are static (update() only fades alpha), so
        # a one-time fit persists for the whole video.
        # ---------------------------------------------

        VisualEngine._constrain_labels_in_frame(
            fig,
            ax,
            labels,
            left_margin_px=0.0,
            right_margin_px=24.0,
            min_font_pt=9.0,
        )

        # ---------------------------------------------
        # COUNTRY FLAG ICONS beside each bubble label
        # (static positions; fade in with the text).
        # ---------------------------------------------

        VisualEngine.prefetch_flags(
            list(data.index)
        )

        try:
            fig.canvas.draw()
        except Exception:
            pass

        xy_flag_boxes = []

        for xy_i, xy_country in enumerate(
            data.index
        ):

            try:

                box = (
                    VisualEngine._attach_country_flag(
                        ax,
                        fig,
                        xy_country,
                        labels[xy_i],
                    )
                )

                if box is not None:
                    box.set_alpha(0.0)

                xy_flag_boxes.append(box)

            except Exception:

                xy_flag_boxes.append(None)

        def update(frame):
            progress = VisualEngine.ease_in_out(
                frame
                / max(
                    1,
                    total_frames - 1
                )
            )
            sizes = [
                160
                + (
                    float(size_values[country])
                    / max_size
                ) * 1250
                * progress
                for country in data.index
            ]
            scatter.set_sizes(
                sizes
            )
            xy_fade = max(
                0.0,
                (progress - 0.35) / 0.65
            )
            for label in labels:
                label.set_alpha(xy_fade)
            for box in xy_flag_boxes:
                if box is not None:
                    box.set_alpha(xy_fade)
            return [
                scatter
            ] + labels + [
                box
                for box in xy_flag_boxes
                if box is not None
            ]

        return VisualEngine._save_animation(
            fig,
            update,
            total_frames,
            output_dir,
            "bubble_chart.mp4"
        )

    # =========================================================
    # TOP 5 CHANGE
    # =========================================================

    @staticmethod
    def render_top5_change(
        script,
        data: pd.DataFrame,
        output_dir: str
    ):

        print(
            "Rendering top 5 change Shorts animation..."
        )

        # Full frame first: movers are picked by CHANGE, not by
        # peak value, so the mobile cap must not truncate here
        # (respect_cap=False).  The cap is applied right below
        # when the top movers are selected.
        data = VisualEngine._prepare_chart_data(
            data,
            max_items=30,
            respect_cap=False
        )

        years = list(
            data.columns
        )
        start_year = years[0]
        end_year = years[-1]

        changes = (
            data[end_year]
            - data[start_year]
        ).dropna()

        if changes.empty:
            raise ValueError(
                "No change values available "
                "for top5_change."
            )

        # Mobile cap applies to the RENDERED movers too: default
        # settings.MAX_CHART_ENTITIES (4) instead of the old
        # hardcoded 5 (settings-tunable).
        try:
            top_cap = int(
                getattr(settings, "MAX_CHART_ENTITIES", 4)
            )
        except (TypeError, ValueError):
            top_cap = 4
        top_cap = max(2, top_cap)

        top_changes = changes.reindex(
            changes.abs()
            .sort_values(
                ascending=False
            )
            .head(top_cap)
            .index
        )

        total_frames = VisualEngine._duration_frames(
            script
        )

        # FLAGS ΓÇö fetch up-front (see render_bar_race note).
        VisualEngine.prefetch_flags(
            top_changes.index.tolist()
        )

        fig, ax = VisualEngine._create_figure(
            script,
            f"Biggest moves: {start_year} to {end_year}"
        )

        ordered = top_changes.sort_values()
        max_abs = float(
            ordered.abs().max()
        )
        if max_abs <= 0:
            max_abs = 1

        ax.set_xlim(
            -max_abs * 1.25,
            max_abs * 1.25
        )
        ax.set_ylim(
            -0.5,
            len(ordered) - 0.5
        )
        ax.axvline(
            0,
            color="#27313D",
            linewidth=2
        )
        ax.set_xticks([])
        ax.set_yticks([])

        bars = ax.barh(
            range(
                len(ordered)
            ),
            [
                0
                for _ in ordered
            ],
            color=[
                VisualEngine.ELECTRIC_BLUE
                if value >= 0
                else "#B56A5A"
                for value in ordered.values
            ],
            height=0.62
        )

        country_labels = []
        value_labels = []
        indicator = VisualEngine._indicator_name(
            script
        )

        for index, (country, value) in enumerate(
            ordered.items()
        ):
            country_label = ax.text(
                -max_abs * 1.20,
                index,
                country,
                ha="left",
                va="center",
                color=VisualEngine.TEXT_COLOR,
                fontsize=21,
                fontweight="bold"
            )
            value_label = ax.text(
                0,
                index,
                "",
                ha="left",
                va="center",
                color=VisualEngine.TEXT_COLOR,
                fontsize=22,
                fontweight="bold"
            )
            country_labels.append(country_label)
            value_labels.append(value_label)

        # --------------------------------------------------
        # VALUE/LABEL GUTTER (render audit): "-12.9" used to sit
        # just LEFT of its (negative) bar tip -- i.e. inside the
        # country-name column -- so on a long name the value
        # printed straight through it ("-2.0" over "Turks and
        # Caicos Islands").  The negative value now sits just
        # RIGHT of the zero axis, in the clear space on its own
        # row; positive values keep their position beyond the bar
        # tip (unchanged).  This guard reserves that column: any
        # name long enough to reach the value column is shrunk
        # (never ellipsised) so label and value can never share
        # pixels, for ANY label length.
        # --------------------------------------------------
        try:

            fig.canvas.draw()
            _renderer = fig.canvas.get_renderer()

            _value_col_px = float(
                ax.transData.transform(
                    (max_abs * 0.04, 0.0)
                )[0]
            )
            _budget_px = _value_col_px - 24.0

            for _label in country_labels:

                for _ in range(20):

                    _box = _label.get_window_extent(
                        renderer=_renderer
                    )

                    if (
                        float(_box.x1) <= _budget_px
                        or _label.get_fontsize() <= 14.0
                        or _budget_px <= 0.0
                    ):
                        break

                    _label.set_fontsize(
                        max(
                            14.0,
                            _label.get_fontsize() - 1.0,
                        )
                    )

        except Exception:
            pass

        # ---------------------------------------------
        # COUNTRY FLAG ICONS (beside each label)
        # Per-country try: one bad flag must not strip
        # the flags off every other bar.
        # ---------------------------------------------

        flag_boxes = []
        try:
            fig.canvas.draw()
        except Exception:
            pass

        for i, country in enumerate(ordered.index):
            try:
                flag_boxes.append(
                    VisualEngine._attach_country_flag(
                        ax, fig, country, country_labels[i]
                    )
                )
            except Exception:
                flag_boxes.append(None)

        # PART 2 DEFECT B -- VALUE HEADROOM (right edge).  Same
        # guard as bar_race: park the FINAL positive-tip strings
        # at their final anchors, widen xlim only if the real
        # glyphs overflow, then clear (update() rewrites all).
        try:
            for _idx, (_country, _value) in enumerate(
                ordered.items()
            ):
                try:
                    _av = float(_value)
                    _sign = "+" if _av > 0 else ""
                    value_labels[_idx].set_text(
                        f"{_sign}"
                        f"{VisualEngine._format_value(_av, indicator)}"
                    )
                    if _av >= 0:
                        _lx = (
                            VisualEngine._bar_width_signed(
                                _av, max_abs
                            )
                            + max_abs * 0.04
                        )
                    else:
                        _lx = max_abs * 0.04
                    value_labels[_idx].set_x(_lx)
                except Exception:
                    continue
            try:
                fig.canvas.draw()
            except Exception:
                pass
            _lo, _hi = ax.get_xlim()
            _span = abs(_hi - _lo) or 1.0
            # Reuse the bar-race guard via a proxy max_val: the
            # axes are symmetric (-1.25..1.25 of max_abs), so grow
            # both limits proportionally to the measured need.
            try:
                _renderer = fig.canvas.get_renderer()
                _fig_w = (
                    float(fig.get_figwidth()) * float(fig.dpi)
                )
                _limit = _fig_w - float(
                    design_system.VALUE_SAFE_MARGIN_PX
                )
                _worst = 0.0
                for _t in value_labels:
                    try:
                        _box = _t.get_window_extent(
                            renderer=_renderer
                        )
                        _worst = max(
                            _worst, float(_box.x1) - _limit
                        )
                    except Exception:
                        continue
                if _worst > 0:
                    try:
                        _px0 = ax.transData.transform(
                            (_lo, 0.0)
                        )[0]
                        _px1 = ax.transData.transform(
                            (_hi, 0.0)
                        )[0]
                        _ppd = abs(_px1 - _px0) / _span
                    except Exception:
                        _ppd = 0.0
                    if _ppd > 0:
                        _grow = (
                            _worst / _ppd * 1.05 / _span
                        )
                        _grow = min(_grow, 0.30)
                        ax.set_xlim(
                            _lo * (1.0 + _grow),
                            _hi * (1.0 + _grow),
                        )
                        max_abs = max_abs * (1.0 + _grow)
            except Exception:
                pass
            for _vt in value_labels:
                try:
                    _vt.set_text("")
                except Exception:
                    continue
            try:
                fig.canvas.draw()
            except Exception:
                pass
        except Exception:
            pass

        # OPENING PAYOFF: the FINAL differences are on screen from
        # frame 0 (settings.OPENING_PAYOFF_SECONDS), then the bars
        # replay their growth.  A 30s buildup before the payoff was
        # the single biggest swipe-away driver on this format.
        payoff_frames = 0

        payoff_seconds = float(
            getattr(
                settings,
                "OPENING_PAYOFF_SECONDS",
                0.0,
            )
            or 0.0
        )

        if payoff_seconds > 0:
            payoff_frames = min(
                int(
                    payoff_seconds
                    * VisualEngine.FPS
                ),
                total_frames // 2,
            )

        def update(frame):
            if (
                payoff_frames
                and frame < payoff_frames
            ):
                # ENTRANCE (not a freeze).  The retention intent --
                # the answer is on screen immediately -- is kept,
                # but the bars now ASSEMBLE into their final state
                # instead of sitting motionless.  Measured before
                # this change: 0.0002% of pixels changed across
                # the entire opening, and top5_change was 100%
                # static across the whole video.
                entrance_phase = True
                progress = 1.0
            elif payoff_frames:
                entrance_phase = False
                progress = VisualEngine.ease_in_out(
                    (frame - payoff_frames)
                    / max(
                        1,
                        total_frames - 1 - payoff_frames,
                    )
                )
            else:
                entrance_phase = False
                progress = VisualEngine.ease_in_out(
                    frame
                    / max(
                        1,
                        total_frames - 1
                    )
                )

            for index, (country, value) in enumerate(
                ordered.items()
            ):
                # Staggered so the winner lands first and the
                # field trails in behind it.
                #
                # OPENING-FLOOR FIX (render audit): grow used to
                # start at 0 with a wide stagger, so rows past the
                # winner were still empty ~1s in -- the first 0.5s
                # read as dead space.  Growth now starts at
                # ENTRANCE_FLOOR of final width with a tighter
                # stagger, so every bar is on screen from frame 0
                # and settles quickly (matching the alpha entrance
                # used by bar_race / line).
                grow = (
                    design_system.ENTRANCE_FLOOR
                    + (
                        1.0 - design_system.ENTRANCE_FLOOR
                    )
                    * design_system.entrance(
                        frame,
                        payoff_frames,
                        delay=design_system.stagger(
                            index,
                            len(ordered),
                            spread=0.24,
                        ),
                        span=0.34,
                    )
                    if entrance_phase
                    else 1.0
                )

                animated_value = (
                    float(value)
                    * progress
                    * grow
                )
                bars[index].set_width(
                    VisualEngine._bar_width_signed(
                        animated_value,
                        max_abs,
                    )
                )
                bars[index].set_x(
                    min(
                        0,
                        VisualEngine._bar_width_signed(
                            animated_value,
                            max_abs,
                        ),
                    )
                )
                # VALUE/LABEL GUTTER (see the setup guard above):
                # positive values stay just beyond their bar tip;
                # negative values sit just RIGHT of the zero axis
                # instead of just left of the tip, which is where
                # they collided with the country name.  The row's
                # name column is now guaranteed clear of its value
                # for any label length.
                if animated_value >= 0:
                    label_x = (
                        VisualEngine._bar_width_signed(
                            animated_value,
                            max_abs,
                        )
                        + max_abs * 0.04
                    )
                else:
                    label_x = max_abs * 0.04

                value_labels[index].set_x(
                    label_x
                )
                value_labels[index].set_ha("left")
                sign = "+" if animated_value > 0 else ""
                value_labels[index].set_text(
                    f"{sign}"
                    f"{VisualEngine._format_value(animated_value, indicator)}"
                )

            return (
                list(bars)
                + country_labels
                + value_labels
            )

        return VisualEngine._save_animation(
            fig,
            update,
            total_frames,
            output_dir,
            "top5_change_chart.mp4"
        )

    # =========================================================
    # SHARE-OF-TOTAL HELPERS  -- Part 1 and Part 2
    # =========================================================

    @staticmethod
    def _share_values(data):
        """Latest-year values, one per entity, biggest first.

        Both part-of-whole renderers read the SAME slice of the
        frame: the latest year, non-negative, sorted descending
        so the largest share is drawn first.  Rows that are not
        finite numbers are dropped rather than coerced to zero
        (a zero-width slice would read as a real 0% share).
        """

        if data is None or data.empty or len(data.columns) == 0:
            return [], []

        latest = data.columns[-1]

        labels = []
        values = []

        for label, raw in zip(data.index, data[latest]):

            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue

            if not np.isfinite(value) or value < 0:
                continue

            labels.append(str(label))
            values.append(value)

        order = sorted(
            range(len(values)),
            key=lambda position: values[position],
            reverse=True,
        )

        return (
            [labels[position] for position in order],
            [values[position] for position in order],
        )

    @staticmethod
    def is_share_of_total(data) -> bool:
        """True only when the frame really is a part of one whole.

        The numbers must be non-negative percentages that ADD UP
        TO A WHOLE (100, within SHARE_TOTAL_TOLERANCE) and the
        entity count must fall inside SHARE_MIN_ENTITIES ..
        SHARE_MAX_ENTITIES.

        This is the render-time guard that stops an absolute
        series (GDP in dollars, population counts) from being
        forced into a pie or a 100-box grid, where the renderer
        would have to invent a total -- "Guyana is 37% of world
        GDP" -- to fill the shapes.

        ChartSelector._share_of_total_data() encodes the same
        rule at selection time (without importing this heavy
        module); the two are cross-checked by test_pie_waffle.py
        so they cannot silently drift apart.
        """

        if data is None or data.empty:
            return False

        _, values = VisualEngine._share_values(data)

        if not (
            VisualEngine.SHARE_MIN_ENTITIES
            <= len(values)
            <= VisualEngine.SHARE_MAX_ENTITIES
        ):
            return False

        total = float(sum(values))

        if total <= 0:
            return False

        return (
            abs(total - 100.0)
            <= VisualEngine.SHARE_TOTAL_TOLERANCE
        )

    @staticmethod
    def _get_categorical_color(index):
        """Colour for a CATEGORICAL part-of-whole chart.

        The rotated house ramp is a single-hue METAL.  On a pie or
        a waffle that is unreadable: rendered proof with the gold
        ramp gave China / USA / India / Russia / Japan five
        near-identical golds, so the grid showed position but no
        identity.  A legend-keyed chart needs hues that can be
        told apart, so pie / waffle draw from the curated
        categorical palette instead of the ramp.
        """

        palette = VisualEngine.MULTI_COLOR_PALETTE

        if not palette:
            return VisualEngine.LEADER_COLOR

        position = max(
            0,
            min(int(index), len(palette) - 1),
        )

        return palette[position]

    @staticmethod
    def largest_remainder(shares, total_boxes):
        """Largest Remainder (Hamilton) apportionment.

        Turns fractional box counts into INTEGERS that sum to
        EXACTLY ``total_boxes`` -- never 99, never 101.

        Flooring every share always loses boxes; the leftover
        boxes are handed out one at a time to the shares with
        the largest DISCARDED FRACTION.  That is the standard
        method that guarantees both exactness and fair rounding,
        which naive ``round()`` does not (rounding each share
        independently can sum to 98 or 102).

        Returns a list of ints parallel to ``shares``.
        """

        if not shares:
            return []

        total_boxes = int(total_boxes)

        if total_boxes <= 0:
            return [0 for _ in shares]

        population = float(sum(shares))

        if population <= 0:
            # Degenerate: nothing measurable.  Hand the whole
            # grid to the first entry so the total is still
            # exact rather than arbitrary.
            return [
                total_boxes if position == 0 else 0
                for position in range(len(shares))
            ]

        ideal = [
            float(share) / population * total_boxes
            for share in shares
        ]

        counts = [int(np.floor(value)) for value in ideal]

        leftover = total_boxes - sum(counts)

        ranked = sorted(
            range(len(shares)),
            key=lambda position: (
                ideal[position] - counts[position],
                -position,
            ),
            reverse=True,
        )

        if leftover > 0:

            for position in ranked[:leftover]:
                counts[position] += 1

        elif leftover < 0:

            # Only float noise can overshoot, and never by more
            # than a box or two.
            for position in reversed(ranked)[: -leftover]:

                if counts[position] > 0:
                    counts[position] -= 1

        return counts

    # =========================================================
    # PIE / DONUT CHART  -- Part 1
    # =========================================================

    @staticmethod
    def render_pie(
        script,
        data: pd.DataFrame,
        output_dir: str
    ):

        print(
            "Rendering share-of-total pie (donut) "
            "Shorts animation..."
        )

        data = VisualEngine._prepare_chart_data(
            data,
            max_items=VisualEngine.SHARE_MAX_ENTITIES,
            # A part-of-whole chart that silently DROPS a part is
            # a lie: the remaining wedges get rescaled to a whole
            # that never existed.  Renderers therefore opt out of
            # the global MAX_CHART_ENTITIES mobile cap and rely on
            # the 3-6 entity window (SHARE_MIN/MAX_ENTITIES) that
            # the selector already enforces.  Same reasoning as
            # top5_change's respect_cap=False.
            respect_cap=False,
            focus=VisualEngine._resolve_focus_entities(
                script,
                data,
            ),
        )

        labels, values = VisualEngine._share_values(data)

        if len(values) < 2:
            raise ValueError(
                "Pie chart needs at least two entities with "
                "numeric values."
            )

        total = float(sum(values))

        shares = [
            value / total * 100.0
            for value in values
        ]

        latest_year = str(data.columns[-1])

        total_frames = VisualEngine._duration_frames(script)

        fig, ax = VisualEngine._create_figure(
            script,
            "Share of total"
        )

        # Square-ish donut box on the LEFT; the legend owns the
        # right-hand column, so a long name can never collide
        # with a wedge or with another name.
        ax.set_position([0.10, 0.28, 0.40, 0.44])
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_xlim(-1.22, 1.22)
        ax.set_ylim(-1.22, 1.22)

        # -----------------------------------------------------
        # DONUT: one Wedge per entity, laid out clockwise from
        # 12 o'clock so the biggest share is the first thing the
        # eye meets and the sweep matches reading order.
        # -----------------------------------------------------

        wedges = []
        spans = []
        angle = 90.0

        for index, share in enumerate(shares):

            extent = share / 100.0 * 360.0

            wedge = mpatches.Wedge(
                (0.0, 0.0),
                1.0,
                angle - extent,
                angle,
                width=0.40,
                facecolor=VisualEngine._get_categorical_color(
                    index
                ),
                edgecolor=VisualEngine.BG_COLOR,
                linewidth=2.0,
            )

            ax.add_patch(wedge)

            wedges.append(wedge)
            spans.append(extent)

            angle -= extent

        # -----------------------------------------------------
        # NO in-ring percentage labels.
        #
        # They were removed after rendered proof showed them
        # colliding with the centre emphasis ("17.0%" printed
        # straight through "44.0%" for a 4-slice donut).  Every
        # share is already printed, colour-keyed, in the legend
        # column -- so the ring labels were pure duplication
        # carrying a real overlap risk.
        # -----------------------------------------------------

        # -----------------------------------------------------
        # CENTRE: the leader and its share -- the one number a
        # part-of-whole chart is really about.  Sized to FIT the
        # hole (inner radius 0.6 of a 1.0 donut) so it can never
        # touch the ring.
        # -----------------------------------------------------

        centre_value = ax.text(
            0.0,
            0.10,
            f"{shares[0]:.1f}%",
            ha="center",
            va="center",
            color=VisualEngine.TEXT_COLOR,
            fontsize=30,
            fontweight="bold",
            alpha=0.0,
        )

        centre_name = ax.text(
            0.0,
            -0.22,
            labels[0][:14],
            ha="center",
            va="center",
            color=VisualEngine.LEADER_COLOR,
            fontsize=16,
            fontweight="bold",
            alpha=0.0,
        )

        # -----------------------------------------------------
        # LEGEND (right column): swatch, name, share.  Lists
        # EVERY entity, so a thin slice is never anonymous.
        # -----------------------------------------------------

        fig.text(
            0.585,
            0.70,
            latest_year,
            ha="left",
            va="center",
            color=VisualEngine.MAGENTA_PURPLE,
            fontsize=40,
            fontweight="bold",
        )

        legend_artists = []

        legend_y = 0.625
        legend_step = 0.052

        for index, (label, share) in enumerate(
            zip(labels, shares)
        ):

            row_y = legend_y - index * legend_step

            swatch = mpatches.Rectangle(
                (0.585, row_y - 0.011),
                0.022,
                0.022,
                transform=fig.transFigure,
                facecolor=VisualEngine._get_categorical_color(
                    index
                ),
                edgecolor="none",
                alpha=0.0,
            )

            fig.add_artist(swatch)
            legend_artists.append(swatch)

            legend_artists.append(
                fig.text(
                    0.620,
                    row_y,
                    label[:22],
                    ha="left",
                    va="center",
                    color=VisualEngine.TEXT_COLOR,
                    fontsize=17,
                    fontweight="bold",
                    alpha=0.0,
                )
            )

            legend_artists.append(
                fig.text(
                    0.955,
                    row_y,
                    f"{share:.1f}%",
                    ha="right",
                    va="center",
                    color=VisualEngine.LEADER_COLOR,
                    fontsize=17,
                    fontweight="bold",
                    alpha=0.0,
                )
            )

        def update(frame):

            progress = VisualEngine.ease_in_out(
                frame / max(1, total_frames - 1)
            )

            cumulative = 0.0

            for index, share in enumerate(shares):

                fraction = share / 100.0

                if fraction <= 0:

                    wedges[index].set_theta2(
                        wedges[index].theta1
                    )
                    continue

                # Each wedge owns a slice of the timeline sized
                # by its own share, so the sweep advances evenly
                # and finishes exactly at 12 o'clock.
                local = (progress - cumulative) / fraction

                local = max(0.0, min(1.0, local))

                wedges[index].set_theta2(
                    wedges[index].theta1
                    + spans[index] * local
                )

                cumulative += fraction

            centre_value.set_alpha(progress)
            centre_name.set_alpha(progress)

            # The legend trails the sweep slightly so the wedges
            # are read first.
            legend_alpha = max(
                0.0,
                (progress - 0.15) / 0.85,
            )

            for artist in legend_artists:
                artist.set_alpha(legend_alpha)

            return (
                wedges
                + [centre_value, centre_name]
                + legend_artists
            )

        return VisualEngine._save_animation(
            fig,
            update,
            total_frames,
            output_dir,
            "pie_chart.mp4"
        )

    # =========================================================
    # WAFFLE / ICON-GRID CHART  -- Part 2
    # =========================================================

    @staticmethod
    def render_waffle(
        script,
        data: pd.DataFrame,
        output_dir: str
    ):

        print(
            "Rendering share-of-total waffle (10x10 icon grid) "
            "Shorts animation..."
        )

        data = VisualEngine._prepare_chart_data(
            data,
            max_items=VisualEngine.SHARE_MAX_ENTITIES,
            # See render_pie: dropping a part of a whole would make
            # the remaining boxes a false 100%.
            respect_cap=False,
            focus=VisualEngine._resolve_focus_entities(
                script,
                data,
            ),
        )

        labels, values = VisualEngine._share_values(data)

        if len(values) < 2:
            raise ValueError(
                "Waffle chart needs at least two entities with "
                "numeric values."
            )

        total = float(sum(values))

        shares = [
            value / total * 100.0
            for value in values
        ]

        # -----------------------------------------------------
        # EXACT BOX-COUNT MATH
        #
        # ONE BOX == ONE PERCENTAGE POINT, so the number of
        # boxes a share gets must be an INTEGER and the whole
        # grid must add to EXACTLY 100 -- never 99 or 101.
        #
        # The named entities are apportioned the boxes their
        # shares of ONE WHOLE earn (round(total)); whatever is
        # left over is the grey "Rest of World" block, so a
        # total of 96% shows 4 grey boxes rather than silently
        # rescaling the parts to fill the grid.
        # -----------------------------------------------------

        entity_boxes = int(round(total))

        entity_boxes = max(
            0,
            min(VisualEngine.WAFFLE_BOXES, entity_boxes),
        )

        counts = VisualEngine.largest_remainder(
            values,
            entity_boxes,
        )

        rest_boxes = VisualEngine.WAFFLE_BOXES - sum(counts)

        if rest_boxes < 0:

            # Defensive only: apportionment is exact by
            # construction, but never ship a grid that
            # overflows 100 boxes.
            overflow = -rest_boxes

            for position in range(len(counts)):

                if overflow <= 0:
                    break

                take = min(counts[position], overflow)

                counts[position] -= take
                overflow -= take

            rest_boxes = 0

        print(
            "  waffle boxes: "
            + ", ".join(
                f"{label}={count}"
                for label, count in zip(labels, counts)
            )
            + (
                f", {VisualEngine.REST_OF_WORLD_LABEL}"
                f"={rest_boxes}"
                if rest_boxes
                else ""
            )
            + f"  (total = {sum(counts) + rest_boxes})"
        )

        # Fill order: entity boxes in descending-share order,
        # then the grey remainder.  The grid therefore fills
        # biggest-share-first, which is the order the legend
        # reads in.
        fill_colors = []

        for index, count in enumerate(counts):
            fill_colors.extend(
                [
                    VisualEngine._get_categorical_color(index)
                ] * count
            )

        fill_colors.extend(
            [VisualEngine.REST_OF_WORLD_COLOR] * rest_boxes
        )

        latest_year = str(data.columns[-1])

        total_frames = VisualEngine._duration_frames(script)

        fig, ax = VisualEngine._create_figure(
            script,
            "Share of total"
        )

        ax.set_position([0.14, 0.22, 0.40, 0.46])
        ax.set_aspect("equal")
        ax.axis("off")

        # Cells occupy 0.07 .. 9.93 on both axes; the limits must
        # CONTAIN that with a margin.  Measured before the fix:
        # xlim/ylim stopped at 9.3, so the last column and the
        # top row of the grid were sliced off by the axes clip
        # (a 10x10 grid rendered as 9x10).
        ax.set_xlim(-0.1, 10.1)
        ax.set_ylim(-0.1, 10.1)

        # -----------------------------------------------------
        # 100 SQUARES.  Each starts EMPTY (canvas colour) and
        # lights up in its owner's colour as the sweep reaches
        # it, so the grid visibly fills to exactly 100 boxes.
        # -----------------------------------------------------

        grid = VisualEngine.WAFFLE_GRID

        cells = []

        for position in range(VisualEngine.WAFFLE_BOXES):

            column = position % grid
            row = position // grid

            cell = mpatches.Rectangle(
                (column + 0.07, (grid - 1 - row) + 0.07),
                0.86,
                0.86,
                facecolor=VisualEngine.BG_COLOR,
                edgecolor=VisualEngine.GRID_COLOR,
                linewidth=1.4,
            )

            ax.add_patch(cell)
            cells.append(cell)

        # -----------------------------------------------------
        # LEGEND (right column).  Box counts are printed next to
        # the shares because a waffle is read in BOXES -- and
        # every row's count is an integer that sums to 100.
        # -----------------------------------------------------

        fig.text(
            0.585,
            0.70,
            latest_year,
            ha="left",
            va="center",
            color=VisualEngine.MAGENTA_PURPLE,
            fontsize=40,
            fontweight="bold",
        )

        legend_artists = []

        rows = [
            (
                label,
                VisualEngine._get_categorical_color(index),
                counts[index],
                shares[index],
            )
            for index, label in enumerate(labels)
        ]

        if rest_boxes > 0:
            rows.append(
                (
                    VisualEngine.REST_OF_WORLD_LABEL,
                    VisualEngine.REST_OF_WORLD_COLOR,
                    rest_boxes,
                    float(rest_boxes),
                )
            )

        legend_y = 0.625
        legend_step = 0.050

        for index, (name, color, count, share) in enumerate(rows):

            row_y = legend_y - index * legend_step

            swatch = mpatches.Rectangle(
                (0.585, row_y - 0.011),
                0.022,
                0.022,
                transform=fig.transFigure,
                facecolor=color,
                edgecolor="none",
                alpha=0.0,
            )

            fig.add_artist(swatch)
            legend_artists.append(swatch)

            legend_artists.append(
                fig.text(
                    0.620,
                    row_y,
                    name[:18],
                    ha="left",
                    va="center",
                    color=VisualEngine.TEXT_COLOR,
                    fontsize=16,
                    fontweight="bold",
                    alpha=0.0,
                )
            )

            legend_artists.append(
                fig.text(
                    0.955,
                    row_y,
                    f"{count} ┬╖ {share:.1f}%",
                    ha="right",
                    va="center",
                    color=VisualEngine.LEADER_COLOR,
                    fontsize=16,
                    fontweight="bold",
                    alpha=0.0,
                )
            )

        # Live box counter: makes the one-box-one-point
        # identity explicit while the grid fills.
        counter = fig.text(
            0.585,
            0.24,
            "0 / 100 boxes",
            ha="left",
            va="center",
            color=VisualEngine.SECONDARY_TEXT,
            fontsize=17,
            fontweight="bold",
            alpha=0.0,
        )

        legend_artists.append(counter)

        def update(frame):

            progress = VisualEngine.ease_in_out(
                frame / max(1, total_frames - 1)
            )

            filled = int(
                progress * VisualEngine.WAFFLE_BOXES
            )

            for position, cell in enumerate(cells):

                if position < filled:

                    cell.set_facecolor(
                        fill_colors[position]
                    )
                    cell.set_edgecolor(
                        VisualEngine.BG_COLOR
                    )

                else:

                    cell.set_facecolor(
                        VisualEngine.BG_COLOR
                    )
                    cell.set_edgecolor(
                        VisualEngine.GRID_COLOR
                    )

            legend_alpha = max(
                0.0,
                (progress - 0.25) / 0.75,
            )

            for artist in legend_artists:

                if artist is counter:
                    artist.set_alpha(1.0)
                else:
                    artist.set_alpha(legend_alpha)

            counter.set_text(f"{filled} / 100 boxes")

            return cells + legend_artists

        return VisualEngine._save_animation(
            fig,
            update,
            total_frames,
            output_dir,
            "waffle_chart.mp4"
        )

    # =========================================================
    # DISPATCHER
    # =========================================================

    @staticmethod
    def _get_chart_type(script):

        chart_type = getattr(
            script,
            "chart_type",
            None
        )

        if not chart_type:
            scenes = getattr(
                script,
                "scenes",
                []
            )
            if scenes:
                chart_type = getattr(
                    scenes[0],
                    "chart_type",
                    None
                )

        chart_type = (
            chart_type
            or "bar_race"
        )

        return str(
            chart_type
        ).strip().lower()

    @staticmethod
    def render_scenes(
        script,
        data: pd.DataFrame,
        output_dir: str,
        audio_duration: float = None
    ):

        # One palette per video: a themed palette when the
        # title/topic matches a keyword group (economy -> gold,
        # population -> blue, ...), otherwise the cursor rotates so
        # consecutive videos look visually distinct.
        VisualEngine.select_palette(script)

        chart_type = VisualEngine._get_chart_type(
            script
        )

        # Per-bar colouring MODE for this video (Part 4): the
        # single rotated gradient, or one distinct colour per
        # bar.  Chosen once here so the whole video is
        # consistent, and set for EVERY chart type so the flag
        # never leaks across videos.
        VisualEngine._select_bar_coloring(chart_type)

        renderers = {
            "bar_race": VisualEngine.render_bar_race,
            "line": VisualEngine.render_line,
            "area": VisualEngine.render_area,
            "slope": VisualEngine.render_slope,
            "bubble": VisualEngine.render_bubble,
            "top5_change": VisualEngine.render_top5_change,
            "pie": VisualEngine.render_pie,
            "waffle": VisualEngine.render_waffle,
        }

        if chart_type not in renderers:
            raise ValueError(
                "Unsupported chart_type: "
                f"{chart_type}. "
                "Use one of: "
                f"{', '.join(sorted(renderers))}."
            )

        # -----------------------------------------------------
        # AUDIO-SYNCED RENDER DURATION
        #
        # The narration is generated BEFORE the visuals, so the
        # REAL measured audio length is available here.  Sizing
        # the animation to the actual audio (instead of the
        # planned script.total_duration) removes the historical
        # mismatch that the assembler used to "fix" by hard-
        # truncating the longer stream (cutting narration or
        # animation).
        #
        # A small tail hold is added so the rendered video is
        # always slightly LONGER than the audio; the assembler
        # then trims only the tail padding -- never narration.
        # -----------------------------------------------------

        restored_override = (
            VisualEngine._duration_override
        )

        if audio_duration and audio_duration > 0:

            VisualEngine._duration_override = (
                float(audio_duration)
                + VisualEngine.AUDIO_TAIL_HOLD
            )

            print(
                "ΓÅ▒∩╕Å Rendering visuals synced to REAL audio: "
                f"{audio_duration:.2f}s audio "
                f"-> {VisualEngine._duration_override:.2f}s "
                "animation "
                f"(planned was {script.total_duration}s)."
            )

        try:

            return renderers[chart_type](
                script,
                data,
                output_dir
            )

        finally:

            VisualEngine._duration_override = (
                restored_override
            )
