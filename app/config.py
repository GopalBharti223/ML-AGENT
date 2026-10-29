import json
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings


# ---------------------------------------------------------
# PROJECT ROOT
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


class Settings(BaseSettings):

    # -----------------------------------------------------
    # AI
    # -----------------------------------------------------

    GROQ_API_KEY: str = os.getenv(
        "GROQ_API_KEY",
        ""
    )

    GROQ_MODEL: str = os.getenv(
        "GROQ_MODEL",
        "openai/gpt-oss-120b"
    )

    # -----------------------------------------------------
    # APPLICATION
    # -----------------------------------------------------

    DEBUG_MODE: bool = (
        os.getenv(
            "DEBUG_MODE",
            "true"
        ).lower() == "true"
    )

    # -----------------------------------------------------
    # -----------------------------------------------------
    # VIDEO FORMAT & DIMENSIONS
    # -----------------------------------------------------
    VIDEO_FORMAT: str = os.getenv("VIDEO_FORMAT", "shorts").strip().lower()

    # -----------------------------------------------------
    # TOPIC SELECTION MODE ("viral_curated" vs "macro_open")
    # Default is "viral_curated" for maximum YouTube retention:
    # tech wars, gaming franchise sales, brand battles & net worth races.
    # -----------------------------------------------------
    TOPIC_SELECTION_MODE: str = os.getenv("TOPIC_SELECTION_MODE", "viral_curated").strip().lower()

    @property
    def is_landscape(self) -> bool:
        return self.VIDEO_FORMAT in ("landscape", "widescreen", "horizontal", "long")

    @property
    def canvas_width(self) -> int:
        return 1920 if self.is_landscape else 1080

    @property
    def canvas_height(self) -> int:
        return 1080 if self.is_landscape else 1920

    DAILY_UPLOADS: int = int(
        os.getenv(
            "DAILY_UPLOADS",
            "4"
        )
    )

    # LEGACY FALLBACK ONLY.  The rendered length is governed by
    # the per-video DURATION BAND (below): ScriptEngine computes
    # the target from the charted entity count, then the TTS
    # stage enforces the measured narration into that budget.
    # TARGET_DURATION is consulted only when an entity count is
    # unavailable, and even then it is clamped into the band.
    TARGET_DURATION: int = int(
        os.getenv(
            "TARGET_DURATION",
            "22"
        )
    )

    # Rendered-length band (seconds).  Every finished video must
    # land inside [DURATION_BAND_MIN, DURATION_BAND_MAX]:
    #   1-2 entities -> ~20s  (simple head-to-head)
    #   3 entities   -> ~24s
    #   4+ entities  -> ~28s  (ranked / multi-entity)
    DURATION_BAND_MIN: int = int(
        os.getenv("DURATION_BAND_MIN", "18")
    )

    DURATION_BAND_MAX: int = int(
        os.getenv("DURATION_BAND_MAX", "24")
    )

    # Hard cap for the TTS rate bump used to pull an over-long
    # narration back into the duration band (see tts.py).
    # INTELLIGIBILITY CEILING: measured on real renders, +15%
    # on top of the pacing profile's base (+5% steady / +14%
    # energetic) lands at 127-143 wpm -- clearly intelligible;
    # the published esports video shipped an effective +54%
    # (169 wpm) and viewers could not follow it.  Anything
    # beyond the ceiling is handled by SHORTENING the script
    # (LLM tighten pass / word budget), never by speed.
    TTS_MAX_RATE_BUMP_PCT: int = int(
        os.getenv("TTS_MAX_RATE_BUMP_PCT", "15")
    )

    # Total delivery-speed ceiling INCLUDING the pacing
    # profile's base rate.  The enforcement bump used to be
    # computed against the base rate, so an "energetic" scene
    # (+14% base) with a +45% bump shipped ~+59% overall --
    # far past anything intelligible.  The bump is now capped
    # so base + bump never exceeds this percentage.
    TTS_MAX_TOTAL_RATE_PCT: int = int(
        os.getenv("TTS_MAX_TOTAL_RATE_PCT", "25")
    )

    # Hard cap on enforcement re-synthesis attempts.  Each
    # pass re-synthesizes only the scenes still over their
    # own budget at a computed bump (<= TTS_MAX_RATE_BUMP_PCT).
    # When the ceiling is reached and the narration is STILL
    # over budget, the band guard escalates (shorten-then-
    # trim) instead of pushing speed further.
    TTS_ENFORCEMENT_MAX_PASSES: int = int(
        os.getenv("TTS_ENFORCEMENT_MAX_PASSES", "2")
    )

    QC_THRESHOLD: int = int(
        os.getenv(
            "QC_THRESHOLD",
            "90"
        )
    )

    UPLOAD_MODE: str = os.getenv(
        "UPLOAD_MODE",
        "draft"
    )

    # -----------------------------------------------------
    # DELAYED PUBLISH
    # Videos are uploaded UNLISTED first; publish_worker.py
    # flips them to PUBLIC after DELAYED_PUBLISH_DELAY_MINUTES
    # via a persistent SQLite queue (publish_queue table).
    # Zero extra cost: SQLite is local and the flip uses the
    # same free YouTube Data API quota.
    # -----------------------------------------------------

    DELAYED_PUBLISH_ENABLED: bool = (
        os.getenv(
            "DELAYED_PUBLISH_ENABLED",
            "true"
        ).lower() == "true"
    )

    DELAYED_PUBLISH_DELAY_MINUTES: int = int(
        os.getenv(
            "DELAYED_PUBLISH_DELAY_MINUTES",
            "15"
        )
    )

    # -----------------------------------------------------
    # MULTI-CHANNEL TOKEN MAP
    # Maps a channel identifier to the OAuth token file that
    # authenticates as that channel.  Format:
    #   "channel_a=youtube_token.json;channel_b=token_b.json"
    # The pipeline stores settings.CHANNEL_NAME (or "default")
    # in the publish_queue table; publish_worker.py looks the
    # token file up here before calling videos.update().
    # -----------------------------------------------------

    CHANNEL_TOKEN_MAP: str = os.getenv(
        "CHANNEL_TOKEN_MAP",
        "default=youtube_token.json"
    )

    # -----------------------------------------------------
    # TTS
    # -----------------------------------------------------

    TTS_VOICE: str = os.getenv(
        "TTS_VOICE",
        "en-US-GuyNeural"
    )

    # -----------------------------------------------------
    # CHANNEL BRANDING
    # Optional signature appended to every description.
    # -----------------------------------------------------

    CHANNEL_NAME: str = os.getenv(
        "CHANNEL_NAME",
        ""
    )

    CHANNEL_TAGLINE: str = os.getenv(
        "CHANNEL_TAGLINE",
        ""
    )

    # -----------------------------------------------------
    # ENGAGEMENT AUTOMATION
    # Post a question-form comment AS THE CHANNEL on each
    # uploaded Short (pinning stays a one-click manual step --
    # the official API cannot pin).
    # -----------------------------------------------------

    AUTO_PIN_COMMENT: bool = (
        os.getenv(
            "AUTO_PIN_COMMENT",
            "true"
        ).lower() == "true"
    )

    # -----------------------------------------------------
    # EXPERIMENTAL: auto-pin via YouTube's INTERNAL creator
    # endpoint (undocumented; the same call family Studio's
    # web app uses).  Off by default -- flip to true in .env
    # to let the pipeline attempt real pinning automatically.
    # -----------------------------------------------------

    AUTO_PIN_INTERNAL_API: bool = (
        os.getenv(
            "AUTO_PIN_INTERNAL_API",
            "false"
        ).lower() == "true"
    )

    AUTO_OPEN_PIN_BROWSER: bool = (
        os.getenv(
            "AUTO_OPEN_PIN_BROWSER",
            "false"
        ).lower() == "true"
    )

    # -----------------------------------------------------
    # AUDIENCE RELEVANCE (topic prioritization)
    #
    # Studio analytics audience geographies and the rivalry
    # pairs that reliably outperform.  Topics where at least
    # one side of the comparison is in AUDIENCE_COUNTRIES, or
    # where both sides form a RIVALRY_PAIR, are prioritized;
    # comparisons where NEITHER side is recognizable are
    # deprioritized/dropped.
    #
    # Comma-separated in .env, e.g.
    #   AUDIENCE_COUNTRIES=india,usa,china,indonesia
    # -----------------------------------------------------

    AUDIENCE_COUNTRIES: str = os.getenv(
        "AUDIENCE_COUNTRIES",
        "india,usa,china,indonesia,philippines,uk,pakistan"
    )

    RIVALRY_PAIRS: str = os.getenv(
        "RIVALRY_PAIRS",
        "usa|china,india|china,india|pakistan,usa|russia,"
        "china|japan,usa|india,uk|china,usa|uk"
    )

    # Toggle the audience-relevance gate on/off.
    AUDIENCE_RELEVANCE_ENABLED: bool = (
        os.getenv("AUDIENCE_RELEVANCE_ENABLED", "true").lower()
        == "true"
    )

    # Minimum candidates that must survive the gate before it is
    # allowed to narrow the pool (protects against collapsing the
    # rotation pool to a single topic).
    AUDIENCE_MIN_POOL: int = int(
        os.getenv("AUDIENCE_MIN_POOL", "4")
    )

    # When True, a candidate that is NOT recognizable at all is
    # removed whenever recognizable candidates exist.
    AUDIENCE_DROP_OBSCURE: bool = (
        os.getenv("AUDIENCE_DROP_OBSCURE", "true").lower() == "true"
    )

    # -----------------------------------------------------
    # CONTENT PILLARS (Strategic Channel Focus)
    #
    # Focus rotation on high-retention audience pillars:
    #   Pillar 1: Geopolitics & Global Power (economy, geography, demographics, energy)
    #   Pillar 2: Technology, Wealth & Market Disruption (AI, tech, brands)
    # Obscure/trivia categories (e.g. space_science, random ratios)
    # are deprioritized or gated out when STRATEGIC_PILLARS_ONLY is true.
    # -----------------------------------------------------
    STRATEGIC_PILLARS_ONLY: bool = (
        os.getenv("STRATEGIC_PILLARS_ONLY", "true").lower() == "true"
    )

    PILLAR_CATEGORIES: str = os.getenv(
        "PILLAR_CATEGORIES",
        "economy,countries_geography,population_demographics,energy,artificial_intelligence,technology_internet,companies_brands"
    )

    # -----------------------------------------------------
    # TITLE STAKES (question-with-stakes titles)
    #
    # Relative weights for the title-format rotation.  Stakes
    # formats (question / duel / twist: they imply a winner,
    # a loser, or a surprise) are heavily favored over the
    # descriptive number-led format, because analytics show
    # descriptive titles ("X's CPI jumped 13 points") under-
    # retain vs outcome titles ("Which country's inflation
    # is exploding fastest?").
    #
    # JSON in .env, e.g.
    #   TITLE_FORMAT_WEIGHTS={"question":5,"duel":3,"twist":2,"number_led":1}
    # -----------------------------------------------------

    TITLE_FORMAT_WEIGHTS: str = os.getenv(
        "TITLE_FORMAT_WEIGHTS",
        '{"question": 5, "duel": 3, "twist": 2, "number_led": 1}'
    )

    # -----------------------------------------------------
    # CHART DESIGN (mobile legibility)
    # -----------------------------------------------------

    # Max bars drawn per chart (mobile glanceability).
    CHART_MAX_BARS: int = int(os.getenv("CHART_MAX_BARS", "6"))

    # Bars used for the head-to-head "vs" format.
    CHART_BARS_VS: int = int(os.getenv("CHART_BARS_VS", "3"))

    # Dedicated ceiling for the animated bar-race renderer.
    # Bar race geometry is verified up to 6 entities.
    BAR_RACE_MAX_ENTITIES: int = int(os.getenv("BAR_RACE_MAX_ENTITIES", "6"))

    # Hard cap on entities/bars rendered in standard charts (line,
    # area, slope, bubble, top5_change). 6-8 cramped lines/areas fail on
    # mobile at a glance; 2-4 read instantly. Applied centrally through
    # VisualEngine._prepare_chart_data so standard renderers respect it.
    MAX_CHART_ENTITIES: int = int(os.getenv("MAX_CHART_ENTITIES", "4"))


    # Font sizes (pt) for the Shorts layout.
    FONT_COUNTRY: int = int(os.getenv("FONT_COUNTRY", "34"))
    FONT_VALUE: int = int(os.getenv("FONT_VALUE", "36"))
    FONT_TITLE: int = int(os.getenv("FONT_TITLE", "52"))
    FONT_YEAR: int = int(os.getenv("FONT_YEAR", "72"))

    # Rotate themed color palettes instead of one fixed gradient.
    PALETTE_ROTATION_ENABLED: bool = (
        os.getenv("PALETTE_ROTATION_ENABLED", "true").lower() == "true"
    )

    # Probability that a bar_race / top5_change video uses the
    # MULTI-COLOUR mode (one distinct colour per bar) instead of
    # the single rotated gradient ramp.  0.35 keeps both looks
    # alive across consecutive uploads without losing the
    # house gradient identity.
    MULTI_COLOR_PROBABILITY: float = float(
        os.getenv("MULTI_COLOR_PROBABILITY", "0.35")
    )

    # Themed color palettes, cycled per video so consecutive
    # uploads look visually distinct.  JSON in .env to override,
    # e.g.
    #   CHART_PALETTES={"economy": ["#F5C15C", "#C89B3C"], ...}
    # Keys are matched against topic keywords in the title
    # (economy / population / military / technology); unmatched
    # topics rotate through every palette in insertion order.
    CHART_PALETTES: str = os.getenv(
        "CHART_PALETTES",
        '{'
        '"economy": ["#F5C15C", "#C89B3C", "#8C6626", "#E8D5A3", "#A67C33", "#D9B26A", "#7A5526", "#B08D45"],'
        '"population": ["#5B9BD5", "#2E75B6", "#A9CCE3", "#1F4E79", "#7FB3D5", "#41729F", "#274472", "#6C9BCF"],'
        '"military": ["#E2725B", "#C0392B", "#E8A08A", "#7B241C", "#D98880", "#943126", "#B03A2E", "#E6B0AA"],'
        '"technology": ["#58D68D", "#28B463", "#A9DFBF", "#1D8348", "#7DCEA0", "#186A3B", "#45B39D", "#82E0AA"],'
        '"default": ["#D4AF37", "#C39A45", "#A67C33", "#E8C97A", "#8C6626", "#B08D45", "#62441F", "#9C7A3C"]'
        '}'
    )

    # Header-text toggles.  Generic subtitles ("AREA TREND OVER
    # TIME") and the opening "WATCH THE RANKINGS CHANGE" card
    # occupy prime visual space without showing a number, so both
    # default OFF.  The closing "WHO DOMINATED?" label stays on
    # (it is an outcome question, not context).
    SHOW_CHART_SUBTITLE: bool = (
        os.getenv("SHOW_CHART_SUBTITLE", "false").lower() == "true"
    )

    SHOW_OPENING_LABEL: bool = (
        os.getenv("SHOW_OPENING_LABEL", "false").lower() == "true"
    )

    SHOW_CLOSING_LABEL: bool = (
        os.getenv("SHOW_CLOSING_LABEL", "true").lower() == "true"
    )

    # =====================================================
    # PREMIUM UI v2  (theme / font / safe-zone system)
    #
    # Every value below is env-overridable so the look can be
    # tuned without touching code.  See app/visuals/theme.py
    # (ThemeEngine) and app/visuals/fonts.py (font loader).
    #
    # SIZING CONTRACT: the canvas is 1080x1920 at dpi=100, so
    # one PIXEL == 1/100 inch == 0.72 pt.  Font sizes are
    # declared here in POINTS (matplotlib's unit); the px
    # numbers in the comments are the delivered size.
    # =====================================================

    # Theme source.  "" = auto: keyword match on the topic,
    # else rotate through every theme with a persistent cursor
    # so two consecutive videos never share a theme.  Set to a
    # theme key (world/economy/population/military/technology/
    # health/sports/energy) to pin one look for every video.
    UI_THEME_OVERRIDE: str = os.getenv("UI_THEME_OVERRIDE", "")

    # Master switch for per-topic theming + cursor rotation.
    UI_THEME_ENABLED: bool = (
        os.getenv("UI_THEME_ENABLED", "true").lower() == "true"
    )

    # Background atmosphere strength, 0..1.  Scales the radial
    # accent glow and the vignette.  The glow itself sits at
    # UI_GLOW_ALPHA (the old 4-6% glow was effectively
    # invisible; 12-18% reads as cinematic without washing out
    # the chart).
    UI_GLOW_ALPHA: float = float(os.getenv("UI_GLOW_ALPHA", "0.15"))
    UI_VIGNETTE_ALPHA: float = float(
        os.getenv("UI_VIGNETTE_ALPHA", "0.22")
    )

    # ---- Shorts safe zones (fractions of the canvas) ----
    # YouTube overlays the right edge (like/comment/share rail),
    # the top (handle/caption) and the bottom (title, handle,
    # soundtrack).  Nothing important may be drawn inside them.
    SAFE_ZONE_TOP: float = float(os.getenv("SAFE_ZONE_TOP", "0.08"))
    SAFE_ZONE_BOTTOM: float = float(
        os.getenv("SAFE_ZONE_BOTTOM", "0.22")
    )
    SAFE_ZONE_RIGHT: float = float(os.getenv("SAFE_ZONE_RIGHT", "0.14"))
    # Left inset: keeps the rank badge / bar origin off the
    # screen edge so the chart never reads as clipped.
    SAFE_ZONE_LEFT: float = float(os.getenv("SAFE_ZONE_LEFT", "0.05"))

    # ---- Chart frame (bar race / top5) ----
    # Width as a fraction of the USABLE width (between the left
    # inset and the right safe zone).  0.86 gives the bars ~10%
    # more horizontal run than the old 0.80 while the worst-case
    # value label still lands left of the right safe edge
    # (measured: tip at 0.64 + widest value label <= 0.81 < 0.86).
    CHART_WIDTH_FRACTION: float = float(
        os.getenv("CHART_WIDTH_FRACTION", "0.94")
    )
    # Bar thickness as a fraction of the row pitch (0..1).
    # 0.72 gives bold, prominent, visually rich bars with balanced gaps.
    BAR_HEIGHT: float = float(os.getenv("BAR_HEIGHT", "0.72"))

    # ---- Legibility floor (1080-wide canvas, dpi=100) ----
    # 1 px == 0.72 pt at dpi=100, so px == pt / 0.72 == pt * 1.389.
    # Delivered minimums: title 70px, year 100px, entity 40px,
    # value 44px, axis/legend 32px.  NOTHING may render below
    # UI_MIN_FONT_PX; auto-fit stops there and ellipsises instead
    # of shrinking further.
    UI_MIN_FONT_PX: float = float(os.getenv("UI_MIN_FONT_PX", "30"))
    FONT_AXIS: int = int(os.getenv("FONT_AXIS", "23"))
    FONT_LEGEND: int = int(os.getenv("FONT_LEGEND", "26"))
    FONT_BADGE: int = int(os.getenv("FONT_BADGE", "30"))
    FONT_SOURCE: int = int(os.getenv("FONT_SOURCE", "22"))

    # Font family names registered from assets/fonts/ (OFL).
    # A missing file degrades to DejaVu Sans -- never a crash.
    UI_FONT_TITLE: str = os.getenv("UI_FONT_TITLE", "Montserrat")
    UI_FONT_TEXT: str = os.getenv("UI_FONT_TEXT", "Inter")

    # Max lines the title may occupy inside the top safe zone.
    UI_TITLE_MAX_LINES: int = int(os.getenv("UI_TITLE_MAX_LINES", "2"))

    # Optional thin progress bar drawn just above the bottom
    # safe zone; turns off cleanly if it ever risks clipping.
    UI_SHOW_PROGRESS_BAR: bool = (
        os.getenv("UI_SHOW_PROGRESS_BAR", "true").lower() == "true"
    )

    # Short-name map for long entity labels, JSON in .env:
    #   {"Democratic Republic of the Congo": "DR Congo"}
    # Applied BEFORE auto-fit, so a known long name never has to
    # shrink or ellipsise.
    UI_SHORT_NAME_MAP: str = os.getenv(
        "UI_SHORT_NAME_MAP",
        '{'
        '"Democratic Republic of the Congo": "DR Congo",'
        '"Congo, Dem. Rep.": "DR Congo",'
        '"Congo, Rep.": "Congo",'
        '"Central African Republic": "CAR",'
        '"Bosnia and Herzegovina": "Bosnia",'
        '"United Arab Emirates": "UAE",'
        '"United Kingdom": "UK",'
        '"United States of America": "USA",'
        '"Papua New Guinea": "PNG",'
        '"Saudi Arabia": "Saudi",'
        '"South Korea": "S. Korea",'
        '"North Korea": "N. Korea",'
        '"Korea, Rep.": "S. Korea",'
        '"Korea, Dem. People\'s Rep.": "N. Korea",'
        '"Russian Federation": "Russia",'
        '"Czech Republic": "Czechia",'
        '"Dominican Republic": "Dominican Rep.",'
        '"Trinidad and Tobago": "Trinidad",'
        '"Antigua and Barbuda": "Antigua",'
        '"Saint Vincent and the Grenadines": "St Vincent",'
        '"Solomon Islands": "Solomon Is.",'
        '"Equatorial Guinea": "Eq. Guinea",'
        '"Guinea-Bissau": "G.-Bissau",'
        '"West Bank and Gaza": "West Bank & Gaza",'
        '"Federated States of Micronesia": "Micronesia",'
        '"Saint Kitts and Nevis": "St. Kitts",'
        '"Sao Tome and Principe": "Sao Tome",'
        '"Venezuela, RB": "Venezuela",'
        '"Iran, Islamic Rep.": "Iran",'
        '"Egypt, Arab Rep.": "Egypt",'
        '"Syrian Arab Republic": "Syria",'
        '"Yemen, Rep.": "Yemen"'
        '}'
    )

    # -----------------------------------------------------
    # OPENING PAYOFF (retention)
    #
    # Seconds at the very start where the FINAL comparison is
    # already on screen (no buildup).  The year sweep then runs
    # as a replay and completes by OPENING_SWEEP_DONE of the
    # video, holding the final state for the remainder.
    #
    # Part 2: the hold is an intentional ~2.0s ANSWER CARD --
    # final result readable from frame 0, subtle entrance
    # micro-motion only (no flashy pop), then a clean replay.
    # -----------------------------------------------------

    OPENING_PAYOFF_SECONDS: float = float(
        os.getenv("OPENING_PAYOFF_SECONDS", "0.0")
    )

    # Fraction of the runtime by which the rewind -> forward year
    # sweep must be COMPLETE.  0.60 left 40% of the runtime as a
    # frozen final frame (a 48s render showed a static chart from
    # 0:29 to 0:49).  0.90 keeps the bars moving through ~90% of
    # the timeline and leaves only a brief final-state beat.
    OPENING_SWEEP_DONE: float = float(
        os.getenv("OPENING_SWEEP_DONE", "0.90")
    )

    # -----------------------------------------------------
    # HUMAN TOUCH LAYER (voice variety, intro line,
    # engagement comments, CTA)
    #
    # All wording/voices live here so they can be tuned
    # in .env without touching code.  JSON-in-env pattern
    # (same as TITLE_FORMAT_WEIGHTS / CHART_PALETTES).
    # -----------------------------------------------------

    # Voice PER CATEGORY -- now a POOL per category, not one
    # fixed narrator.
    #
    # PRIORITY 3: seven categories hard-mapped to
    # en-US-GuyNeural, so 47% of published videos (55% of the
    # most recent 20) used the same narrator.  Each value is
    # now a LIST the picker rotates through, choosing the
    # member that has gone longest unused.  Categories keep a
    # coherent sonic identity -- every voice listed for a
    # category suits that topic -- while consecutive uploads
    # stop sounding identical.
    #
    # A plain string is still accepted and behaves as a
    # one-voice pool, so older .env overrides keep working.
    #
    # Pool sizes are weighted by real category volume
    # (World Data alone is 28% of published videos), so the
    # resulting distribution evens out near 15-22% per voice.
    # JSON in .env, e.g.
    #   VOICE_CATEGORY_MAP={"defense": ["en-US-GuyNeural"]}
    VOICE_CATEGORY_MAP: str = os.getenv(
        "VOICE_CATEGORY_MAP",
        '{'
        # --- the 7 categories that used to funnel to Guy ---
        '"economy": ["en-US-GuyNeural", "en-US-JennyNeural"],'
        '"public_finance": ["en-US-GuyNeural", "en-US-AndrewNeural"],'
        '"countries_geography": ["en-US-GuyNeural", '
        '"en-US-AriaNeural", "en-GB-RyanNeural", '
        '"en-US-AndrewNeural", "en-US-JennyNeural"],'
        '"defense": ["en-US-GuyNeural", "en-GB-RyanNeural", '
        '"en-US-AriaNeural"],'
        '"governance": ["en-US-GuyNeural", "en-US-JennyNeural"],'
        '"sports": ["en-US-GuyNeural", "en-GB-RyanNeural", '
        '"en-US-AndrewNeural"],'
        '"football": ["en-US-GuyNeural", "en-GB-RyanNeural", '
        '"en-US-AndrewNeural"],'
        '"cars_automotive": ["en-US-GuyNeural", '
        '"en-US-AndrewNeural"],'
        # --- Jenny-led families, now able to cross over ---
        '"population_demographics": ["en-US-JennyNeural", '
        '"en-GB-RyanNeural"],'
        '"health": ["en-US-JennyNeural", "en-US-AndrewNeural"],'
        '"companies_brands": ["en-US-JennyNeural", '
        '"en-US-AriaNeural"],'
        '"general_interest": ["en-US-JennyNeural", '
        '"en-US-GuyNeural"],'
        '"education": ["en-US-JennyNeural", "en-US-AriaNeural"],'
        '"cities": ["en-US-JennyNeural", "en-US-AndrewNeural"],'
        # --- Ryan-led families ---
        '"environment_climate": ["en-GB-RyanNeural", '
        '"en-US-AriaNeural"],'
        '"energy": ["en-GB-RyanNeural", "en-US-AndrewNeural"],'
        '"space_science": ["en-GB-RyanNeural", '
        '"en-US-AriaNeural"],'
        # --- Aria-led families ---
        '"artificial_intelligence": ["en-US-AriaNeural", '
        '"en-US-GuyNeural", "en-US-JennyNeural", '
        '"en-US-AndrewNeural"],'
        '"technology_internet": ["en-US-AriaNeural", '
        '"en-US-JennyNeural"],'
        '"entertainment_pop_culture": ["en-US-AriaNeural", '
        '"en-GB-RyanNeural"],'
        '"gaming": ["en-US-AriaNeural", "en-US-AndrewNeural"]'
        '}'
    )

    # Fallback rotation pool for categories without a fixed voice
    # (and the source of voices for the hash rotation).
    # Andrew was added for Priority 3: with only four voices a
    # five-way split is impossible and one narrator must
    # dominate.  All are standard, widely-available Edge voices.
    VOICE_ROTATION_POOL: str = os.getenv(
        "VOICE_ROTATION_POOL",
        '["en-IN-NeerjaExpressiveNeural", "en-IN-PrabhatNeural", '
        '"en-US-GuyNeural", "en-US-JennyNeural", '
        '"en-US-AriaNeural", "en-GB-RyanNeural", '
        '"en-US-AndrewNeural"]'
    )

    # -----------------------------------------------------
    # CATEGORY STRING VARIANTS -> canonical
    # VOICE_CATEGORY_MAP key.
    #
    # Production emits the SAME parent category under many
    # spellings: provider title case ("AI Investment",
    # "Space / Science", "Formula 1"), snake case
    # ("artificial_intelligence", "space_science") and
    # the title-cased family form persisted to script.json
    # ("Population Demographics").
    #
    # Matching is NORMALIZED, never exact: lowercase,
    # separators (- _ / & . , | : + parens) become spaces,
    # whitespace collapses, then lookup is
    #   1. exact canonical key
    #   2. exact alias below
    #   3. plural-tolerant token match (so a subcategory
    #      suffix such as "AI Governance" still reaches the
    #      AI parent even without an explicit entry)
    #   4. stable-hash rotation (VOICE_ROTATION_POOL)
    # so a category can never silently miss its parent voice
    # because of case, spacing or a subcategory suffix.
    # -----------------------------------------------------
    VOICE_CATEGORY_ALIASES: str = os.getenv(
        "VOICE_CATEGORY_ALIASES",
        '{'
        # economy -> en-US-GuyNeural
        '"economics": "economy",'
        '"economic": "economy",'
        '"macro": "economy",'
        '"macroeconomics": "economy",'
        '"gdp": "economy",'
        '"gdp current us": "economy",'
        '"gdp per capita": "economy",'
        '"gdp per capita current us": "economy",'
        '"inflation": "economy",'
        '"inflation rate": "economy",'
        '"trade": "economy",'
        '"world economy": "economy",'
        '"markets": "economy",'
        '"finance": "economy",'
        '"finance markets": "economy",'
        '"monetary policy": "economy",'
        # public_finance -> en-US-GuyNeural
        '"public finance": "public_finance",'
        '"public debt": "public_finance",'
        '"government debt": "public_finance",'
        '"debt": "public_finance",'
        '"fiscal": "public_finance",'
        '"fiscal policy": "public_finance",'
        '"budget": "public_finance",'
        '"deficit": "public_finance",'
        '"taxation": "public_finance",'
        '"tax": "public_finance",'
        '"public spending": "public_finance",'
        '"government spending": "public_finance",'
        '"sovereign debt": "public_finance",'
        # countries_geography -> en-US-GuyNeural
        '"countries geography": "countries_geography",'
        '"countries": "countries_geography",'
        '"country": "countries_geography",'
        '"geography": "countries_geography",'
        '"world data": "countries_geography",'
        '"global data": "countries_geography",'
        '"geopolitics": "countries_geography",'
        '"international": "countries_geography",'
        '"world": "countries_geography",'
        '"global": "countries_geography",'
        # defense -> en-US-GuyNeural
        '"defense": "defense",'
        '"defence": "defense",'
        '"military": "defense",'
        '"military expenditure": "defense",'
        '"military spending": "defense",'
        '"armed forces": "defense",'
        '"army": "defense",'
        '"nato": "defense",'
        '"defense spending": "defense",'
        '"defence spending": "defense",'
        # governance -> en-US-GuyNeural
        '"governance": "governance",'
        '"government": "governance",'
        '"politics": "governance",'
        '"political": "governance",'
        '"policy": "governance",'
        '"public policy": "governance",'
        '"corruption": "governance",'
        '"corruption perceptions": "governance",'
        '"corruption perceptions index": "governance",'
        '"institutions": "governance",'
        '"rule of law": "governance",'
        '"democracy": "governance",'
        '"elections": "governance",'
        # sports -> en-US-GuyNeural
        '"sports": "sports",'
        '"sport": "sports",'
        '"formula 1": "sports",'
        '"formula one": "sports",'
        '"f1": "sports",'
        '"racing": "sports",'
        '"motorsport": "sports",'
        '"motorsports": "sports",'
        '"olympics": "sports",'
        '"olympic games": "sports",'
        '"athletics": "sports",'
        '"basketball": "sports",'
        '"tennis": "sports",'
        '"cricket": "sports",'
        '"nba": "sports",'
        '"golf": "sports",'
        '"cycling": "sports",'
        '"boxing": "sports",'
        '"ufc": "sports",'
        '"medal count": "sports",'
        # football -> en-US-GuyNeural
        '"football": "football",'
        '"soccer": "football",'
        '"football soccer": "football",'
        '"soccer football": "football",'
        '"fifa": "football",'
        '"world cup": "football",'
        '"uefa": "football",'
        '"champions league": "football",'
        '"premier league": "football",'
        '"la liga": "football",'
        '"serie a": "football",'
        '"bundesliga": "football",'
        '"football clubs": "football",'
        # cars_automotive -> en-US-GuyNeural
        '"cars automotive": "cars_automotive",'
        '"cars": "cars_automotive",'
        '"car": "cars_automotive",'
        '"automotive": "cars_automotive",'
        '"auto": "cars_automotive",'
        '"vehicles": "cars_automotive",'
        '"vehicle": "cars_automotive",'
        '"electric vehicles": "cars_automotive",'
        '"ev": "cars_automotive",'
        '"evs": "cars_automotive",'
        '"car sales": "cars_automotive",'
        '"automakers": "cars_automotive",'
        # population_demographics -> en-US-JennyNeural
        '"population": "population_demographics",'
        '"populations": "population_demographics",'
        '"population demographics": "population_demographics",'
        '"demographics": "population_demographics",'
        '"demographic": "population_demographics",'
        '"population growth": "population_demographics",'
        '"population change": "population_demographics",'
        '"birth rate": "population_demographics",'
        '"birth rates": "population_demographics",'
        '"fertility": "population_demographics",'
        '"fertility rate": "population_demographics",'
        '"migration": "population_demographics",'
        '"net migration": "population_demographics",'
        '"life expectancy": "population_demographics",'
        '"life expectancy at birth": "population_demographics",'
        '"median age": "population_demographics",'
        '"age structure": "population_demographics",'
        '"dependency ratio": "population_demographics",'
        # health -> en-US-JennyNeural
        '"health": "health",'
        '"healthcare": "health",'
        '"health care": "health",'
        '"public health": "health",'
        '"health expenditure": "health",'
        '"health spending": "health",'
        '"mortality": "health",'
        '"child mortality": "health",'
        '"infant mortality": "health",'
        '"under 5 mortality": "health",'
        '"disease": "health",'
        '"diseases": "health",'
        '"medicine": "health",'
        '"vaccination": "health",'
        '"wellbeing": "health",'
        '"wellness": "health",'
        '"hospitals": "health",'
        '"obesity": "health",'
        '"smoking": "health",'
        # education -> en-US-JennyNeural
        '"education": "education",'
        '"education spending": "education",'
        '"education expenditure": "education",'
        '"schooling": "education",'
        '"schools": "education",'
        '"school": "education",'
        '"literacy": "education",'
        '"literacy rate": "education",'
        '"students": "education",'
        '"universities": "education",'
        '"university": "education",'
        '"learning": "education",'
        '"pisa": "education",'
        '"enrollment": "education",'
        '"enrolment": "education",'
        '"teachers": "education",'
        '"dropout rate": "education",'
        # cities -> en-US-JennyNeural
        '"cities": "cities",'
        '"city": "cities",'
        '"urban": "cities",'
        '"urbanization": "cities",'
        '"urbanisation": "cities",'
        '"urban population": "cities",'
        '"megacities": "cities",'
        '"metro": "cities",'
        '"metropolitan": "cities",'
        '"slums": "cities",'
        '"housing": "cities",'
        # companies_brands -> en-US-JennyNeural
        '"companies brands": "companies_brands",'
        '"companies": "companies_brands",'
        '"company": "companies_brands",'
        '"brands": "companies_brands",'
        '"brand": "companies_brands",'
        '"corporate": "companies_brands",'
        '"corporation": "companies_brands",'
        '"corporations": "companies_brands",'
        '"business": "companies_brands",'
        '"businesses": "companies_brands",'
        '"startups": "companies_brands",'
        '"startup": "companies_brands",'
        '"firms": "companies_brands",'
        '"market cap": "companies_brands",'
        '"market capitalization": "companies_brands",'
        '"revenue": "companies_brands",'
        '"biggest companies": "companies_brands",'
        # general_interest -> en-US-JennyNeural
        '"general interest": "general_interest",'
        '"general": "general_interest",'
        '"general data": "general_interest",'
        '"general knowledge": "general_interest",'
        '"public interest": "general_interest",'
        '"misc": "general_interest",'
        '"miscellaneous": "general_interest",'
        '"other": "general_interest",'
        '"curiosity": "general_interest",'
        # space_science -> en-GB-RyanNeural
        '"space science": "space_science",'
        '"space": "space_science",'
        '"science": "space_science",'
        '"research": "space_science",'
        '"research publications": "space_science",'
        '"research publications by country": "space_science",'
        '"scientific output": "space_science",'
        '"science output": "space_science",'
        '"astronomy": "space_science",'
        '"astrophysics": "space_science",'
        '"cosmology": "space_science",'
        '"solar system": "space_science",'
        '"planets": "space_science",'
        '"planet": "space_science",'
        '"planetary": "space_science",'
        '"planetary science": "space_science",'
        '"space exploration": "space_science",'
        '"nasa": "space_science",'
        '"satellites": "space_science",'
        '"space missions": "space_science",'
        '"moon": "space_science",'
        '"mars": "space_science",'
        '"exoplanets": "space_science",'
        # environment_climate -> en-GB-RyanNeural
        '"environment climate": "environment_climate",'
        '"environment": "environment_climate",'
        '"climate": "environment_climate",'
        '"climate change": "environment_climate",'
        '"global warming": "environment_climate",'
        '"emissions": "environment_climate",'
        '"co2": "environment_climate",'
        '"co2 emissions": "environment_climate",'
        '"carbon emissions": "environment_climate",'
        '"greenhouse gas": "environment_climate",'
        '"greenhouse gases": "environment_climate",'
        '"biodiversity": "environment_climate",'
        '"nature": "environment_climate",'
        '"sustainability": "environment_climate",'
        '"extinction": "environment_climate",'
        '"red list": "environment_climate",'
        '"deforestation": "environment_climate",'
        '"natural disasters": "environment_climate",'
        '"flood deaths": "environment_climate",'
        '"air quality": "environment_climate",'
        # energy -> en-GB-RyanNeural
        '"energy": "energy",'
        '"energy use": "energy",'
        '"energy consumption": "energy",'
        '"energy transition": "energy",'
        '"electricity": "energy",'
        '"electricity access": "energy",'
        '"power": "energy",'
        '"renewables": "energy",'
        '"renewable energy": "energy",'
        '"solar": "energy",'
        '"solar power": "energy",'
        '"wind power": "energy",'
        '"oil": "energy",'
        '"gas": "energy",'
        '"natural gas": "energy",'
        '"coal": "energy",'
        '"fossil fuels": "energy",'
        '"nuclear": "energy",'
        '"hydropower": "energy",'
        # artificial_intelligence -> en-US-AriaNeural
        '"artificial intelligence": "artificial_intelligence",'
        '"ai": "artificial_intelligence",'
        '"machine learning": "artificial_intelligence",'
        '"deep learning": "artificial_intelligence",'
        '"ml": "artificial_intelligence",'
        '"llm": "artificial_intelligence",'
        '"llms": "artificial_intelligence",'
        '"large language models": "artificial_intelligence",'
        '"generative ai": "artificial_intelligence",'
        '"ai investment": "artificial_intelligence",'
        '"ai adoption": "artificial_intelligence",'
        '"ai research": "artificial_intelligence",'
        '"ai talent": "artificial_intelligence",'
        '"ai governance": "artificial_intelligence",'
        '"ai spending": "artificial_intelligence",'
        '"ai models": "artificial_intelligence",'
        '"ai patents": "artificial_intelligence",'
        '"ai startups": "artificial_intelligence",'
        '"ai policy": "artificial_intelligence",'
        '"automation": "artificial_intelligence",'
        '"robotics": "artificial_intelligence",'
        # technology_internet -> en-US-AriaNeural
        '"technology internet": "technology_internet",'
        '"technology": "technology_internet",'
        '"technologies": "technology_internet",'
        '"tech": "technology_internet",'
        '"internet": "technology_internet",'
        '"internet users": "technology_internet",'
        '"internet users of population": "technology_internet",'
        '"internet access": "technology_internet",'
        '"connectivity": "technology_internet",'
        '"digital": "technology_internet",'
        '"digitalization": "technology_internet",'
        '"digitalisation": "technology_internet",'
        '"telecom": "technology_internet",'
        '"telecommunications": "technology_internet",'
        '"broadband": "technology_internet",'
        '"mobile": "technology_internet",'
        '"mobile phones": "technology_internet",'
        '"mobile subscriptions": "technology_internet",'
        '"smartphones": "technology_internet",'
        '"smartphones consumer tech": "technology_internet",'
        '"consumer tech": "technology_internet",'
        '"computers": "technology_internet",'
        '"hardware": "technology_internet",'
        '"software": "technology_internet",'
        '"data centers": "technology_internet",'
        '"semiconductors": "technology_internet",'
        '"cybersecurity": "technology_internet",'
        # entertainment_pop_culture -> en-US-AriaNeural
        '"entertainment pop culture": "entertainment_pop_culture",'
        '"entertainment": "entertainment_pop_culture",'
        '"pop culture": "entertainment_pop_culture",'
        '"popculture": "entertainment_pop_culture",'
        '"anime": "entertainment_pop_culture",'
        '"manga": "entertainment_pop_culture",'
        '"movies": "entertainment_pop_culture",'
        '"movie": "entertainment_pop_culture",'
        '"film": "entertainment_pop_culture",'
        '"films": "entertainment_pop_culture",'
        '"box office": "entertainment_pop_culture",'
        '"tv": "entertainment_pop_culture",'
        '"television": "entertainment_pop_culture",'
        '"music": "entertainment_pop_culture",'
        '"streaming": "entertainment_pop_culture",'
        '"celebrities": "entertainment_pop_culture",'
        '"celebrity": "entertainment_pop_culture",'
        '"culture": "entertainment_pop_culture",'
        '"content": "entertainment_pop_culture",'
        '"netflix": "entertainment_pop_culture",'
        '"youtube": "entertainment_pop_culture",'
        # gaming -> en-US-AriaNeural
        '"gaming": "gaming",'
        '"games": "gaming",'
        '"game": "gaming",'
        '"video games": "gaming",'
        '"video game": "gaming",'
        '"videogames": "gaming",'
        '"esports": "gaming",'
        '"game rankings": "gaming",'
        '"game ratings": "gaming",'
        '"game sales": "gaming",'
        '"consoles": "gaming",'
        '"playstation": "gaming",'
        '"xbox": "gaming",'
        '"nintendo": "gaming",'
        '"steam": "gaming"'
        '}'
    )

    # Natural pause (ms) inserted BEFORE and AFTER the payoff
    # number/reveal phrase.  A small jitter is added so delivery
    # never sounds metronomic.  0 disables.
    #
    # EDGE TTS PAUSE CALIBRATION (measured): every punctuation
    # glyph Edge TTS renders — comma, period, ellipsis — produces
    # ~0.85-0.98s of dead air regardless of the intended pause
    # length.  There is no short-pause glyph.  The old defaults
    # (BEFORE=320ms / AFTER=280ms) were calibrated against a
    # measurement that reported commas at ~0.2-0.3s; re-measuring
    # on the current Edge TTS build shows commas actually render
    # ~0.86s, so even the "short" comma beat inserts ~0.86s of
    # dead air BEFORE the payoff number and another ~0.86s AFTER
    # it — ~1.7s of silence per scene, matching the published
    # military-spending video's stop-start narration.
    #
    # Fix: default both to 0 so no punctuation pauses are inserted
    # around payoff numbers.  Narration flow is preserved by the
    # pacing profile (rate/pitch/volume) and the inter-scene beat
    # is handled by the per-clip silence trims
    # (_trim_leading_silence / _trim_trailing_silence), not by
    # punctuation gaps.  Set non-zero via env var to restore the
    # old behavior (not recommended).
    PAYOFF_PAUSE_MS_BEFORE: int = int(
        os.getenv("PAYOFF_PAUSE_MS_BEFORE", "0")
    )
    PAYOFF_PAUSE_MS_AFTER: int = int(
        os.getenv("PAYOFF_PAUSE_MS_AFTER", "0")
    )

    # -----------------------------------------------------
    # INTERNAL-PAUSE COMPRESSION (dead-air fix, Issue 1)
    #
    # Edge TTS renders EVERY punctuation glyph -- comma,
    # period, semicolon -- as ~0.85-0.98s of silence, and
    # there is no short-pause glyph to ask for instead.  The
    # per-clip edge trims (_trim_leading_silence /
    # _trim_trailing_silence) only touch the FIRST and LAST
    # silence in a clip, so any scene with two sentences
    # shipped with those mid-clip pauses fully intact: the
    # freshly rendered military-spending video measured 0.84s
    # @1.21s and 0.94s @6.30s INSIDE scene 1 -- which the
    # viewer hears as broken, stop-start narration.
    #
    # _compress_internal_pauses() closes those MID-clip pauses
    # with silenceremove stop_periods=-1.  MEASURED on the real
    # rendered scene_1.mp3 (9.55s, two pauses, -40dB):
    #
    #   detect  keep    duration   gaps @0.25s   dead air
    #   0.15    0.05     8.16s        0          0.00s  <- chosen
    #   0.20    0.05     8.26s        2          0.51s
    #   0.30    0.05     8.46s        2          0.61s
    #   0.45    0.00     8.66s        2          0.91s
    #
    # The pause kept in the output is ~ (detect + keep), so
    # 150ms + 50ms leaves a natural ~0.20s sentence beat while
    # removing ~1.4s of dead air per paused scene.  Speech time
    # is unchanged (-0.02s across every recipe), i.e. only
    # silence is removed -- no words are clipped.
    # -----------------------------------------------------
    TTS_INTERNAL_PAUSE_TRIM: bool = (
        os.getenv("TTS_INTERNAL_PAUSE_TRIM", "true").lower() == "true"
    )
    TTS_INTERNAL_PAUSE_DETECT_MS: int = int(
        os.getenv("TTS_INTERNAL_PAUSE_DETECT_MS", "150")
    )
    TTS_INTERNAL_PAUSE_KEEP_MS: int = int(
        os.getenv("TTS_INTERNAL_PAUSE_KEEP_MS", "50")
    )

    # -----------------------------------------------------
    # END-OF-VIDEO TAIL (dead-air fix, Issue 1)
    #
    # The animation is rendered AUDIO_TAIL_HOLD_S longer than
    # the narration so the mux trims padding instead of speech.
    # That hold is dead air by construction and the assembler
    # fills it with tail_bridge_audio.mp3 -- a 100%-silent
    # segment.  It was a hard-coded 0.75s, which shipped a
    # measured 0.73s silent hole immediately before the outro
    # card.
    #
    # MEASURED on the real render 20260924_195250:
    #   narration 15.0605s, animation 15.3000s
    #   -> bridge = animation - narration = 0.2395s
    # The silent run the viewer actually hears is that bridge
    # PLUS the ~0.02s tail the narration trim deliberately
    # keeps: 0.24 + 0.02 = 0.26s, which is still ONE detectable
    # gap at the 0.25s floor.  0.20s brings the sum to ~0.21s --
    # below the floor and inaudible -- while still leaving ~10x
    # the slack needed to stop the mux ever truncating the final
    # syllable.
    #
    # TAIL_BRIDGE_WARN_S logs a warning if a future change ever
    # pushes the silent bridge back above that floor.
    # -----------------------------------------------------
    AUDIO_TAIL_HOLD_S: float = float(
        os.getenv("AUDIO_TAIL_HOLD", "0.20")
    )
    TAIL_BRIDGE_WARN_S: float = float(
        os.getenv("TAIL_BRIDGE_WARN_S", "0.30")
    )

    # Optional short spoken hook (5-8 words) before the data
    # reveal.  Rotated deterministically per video (stable hash
    # of topic+date, not random), so it varies but never repeats
    # back-to-back.  Empty list disables the hook entirely.
    INTRO_LINE_POOL: str = os.getenv(
        "INTRO_LINE_POOL",
        "[]"
    )

    # Fallback engagement questions used when the LLM comment
    # generator is unavailable.  Rotated with anti-repeat.
    ENGAGEMENT_COMMENT_FALLBACKS: str = os.getenv(
        "ENGAGEMENT_COMMENT_FALLBACKS",
        '['
        '"Which one surprised you more?",'
        '"Guess before you scroll -- did you get it right?",'
        '"Team leader or team upset -- defend your pick?",'
        '"Did your country make the top 3?",'
        '"Would you have guessed this order?"'
        ']'
    )

    # Outro CTA text (rendered on the closing card only,
    # never spoken, never before the payoff).
    OUTRO_CTA_TEXT: str = os.getenv(
        "OUTRO_CTA_TEXT",
        "Follow for more data stories"
    )

    # Static brand intro card BEFORE the animation.  Default OFF:
    # it delayed the payoff by 1.2s and directly conflicts with
    # the OPENING_PAYOFF_SECONDS fix.  Re-enable only if you
    # accept the retention cost.
    INTRO_CARD_ENABLED: bool = (
        os.getenv("INTRO_CARD_ENABLED", "false").lower() == "true"
    )

    # Brand outro card AFTER the animation. Default OFF:
    # showing an outro screen signals the video has ended, causing viewers
    # to swipe away early and tanking Average Percentage Viewed (APV).
    # Leaving it OFF enables seamless infinite looping on Shorts.
    OUTRO_CARD_ENABLED: bool = (
        os.getenv("OUTRO_CARD_ENABLED", "false").lower() == "true"
    )

    # Background Music (BGM) Engine: auto-ducks driving suspense / beat tracks
    # behind narration to eliminate dead-air and boost retention.
    BGM_ENABLED: bool = (
        os.getenv("BGM_ENABLED", "true").lower() == "true"
    )
    BGM_VOLUME: float = float(
        os.getenv("BGM_VOLUME", "0.12")
    )

    # Burn dynamic, high-contrast kinetic captions onto the video frame.
    # Essential for the 70%+ of mobile viewers watching muted or with low audio.
    BURN_CAPTIONS: bool = (
        os.getenv("BURN_CAPTIONS", "true").lower() == "true"
    )

    # -----------------------------------------------------
    # BRAND SFX ROTATION (PRIORITY 1)
    #
    # The intro ding and outro chime used to be ONE fixed cue
    # in every published video.  Both now rotate through a
    # small synthesized family (app/video/sfx.py) with
    # last-used tracking, so consecutive uploads never sound
    # identical.
    #
    # This optional map BIASES a category toward particular
    # variant indices so a topic family keeps a coherent
    # sonic identity while still rotating between uploads.
    # Unlisted categories rotate freely over the whole pool.
    # JSON in .env, e.g.
    #   SFX_CATEGORY_VARIANTS={"defense": [0, 2], "sports": [1, 3]}
    # -----------------------------------------------------

    SFX_CATEGORY_VARIANTS: str = os.getenv(
        "SFX_CATEGORY_VARIANTS",
        "",
    )

    # -----------------------------------------------------
    # PERFORMANCE FEEDBACK LOOP
    #
    # Read video_performance (populated by
    # app.youtube.analytics) to bias topic selection toward the
    # categories / country pairs that actually retain viewers.
    # -----------------------------------------------------

    PERFORMANCE_FEEDBACK_ENABLED: bool = (
        os.getenv("PERFORMANCE_FEEDBACK_ENABLED", "true").lower()
        == "true"
    )

    # Only videos at least this old are considered settled.
    PERFORMANCE_MIN_AGE_HOURS: int = int(
        os.getenv("PERFORMANCE_MIN_AGE_HOURS", "48")
    )

    # -----------------------------------------------------
    # AUDIENCE RELEVANCE & TARGETING
    # -----------------------------------------------------

    AUDIENCE_RELEVANCE_ENABLED: bool = (
        os.getenv("AUDIENCE_RELEVANCE_ENABLED", "true").lower() == "true"
    )

    AUDIENCE_COUNTRIES: str = os.getenv(
        "AUDIENCE_COUNTRIES",
        "India"
    )

    RIVALRY_PAIRS: str = os.getenv(
        "RIVALRY_PAIRS",
        "India|China,India|Pakistan,India|UK,India|United Kingdom,India|Germany,India|Japan,India|USA,India|United States,Tata|Reliance,Apple|Samsung,Tesla|BYD,Amazon|Walmart"
    )

    AUDIENCE_MIN_POOL: int = int(
        os.getenv("AUDIENCE_MIN_POOL", "4")
    )

    AUDIENCE_DROP_OBSCURE: bool = (
        os.getenv("AUDIENCE_DROP_OBSCURE", "true").lower() == "true"
    )

    STRATEGIC_PILLARS_ONLY: bool = (
        os.getenv("STRATEGIC_PILLARS_ONLY", "false").lower() == "true"
    )

    PILLAR_CATEGORIES: str = os.getenv(
        "PILLAR_CATEGORIES",
        "economy,technology_internet,countries_geography,companies_brands,energy,population_demographics"
    )

    # -----------------------------------------------------
    # PATHS
    # -----------------------------------------------------

    DB_PATH: str = os.getenv(
        "DB_PATH",
        str(BASE_DIR / "data" / "history.db")
    )

    OUTPUT_DIR: str = os.getenv(
        "OUTPUT_DIR",
        str(BASE_DIR / "output")
    )


settings = Settings()


def parse_json_setting(raw_value, default):
    """Parse a JSON-in-env setting (VOICE_CATEGORY_MAP,
    INTRO_LINE_POOL, ...).  Returns `default` when the value is
    blank or malformed so a bad .env edit can never crash the
    pipeline."""

    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError):
        return default

    if parsed is None or parsed == "" or parsed == []:
        return default

    return parsed