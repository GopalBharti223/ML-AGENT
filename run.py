import os
import re as _re
import sys
import json
import inspect

from datetime import datetime, timedelta

# ---------------------------------------------------------
# UNICODE-SAFE OUTPUT
# Emoji console prints crash under cp1252 whenever output
# is redirected (scheduled tasks, log files, CI pipes).
# Force UTF-8 so the pipeline survives headless runs.
# ---------------------------------------------------------

for _stream in (sys.stdout, sys.stderr):

    if _stream and hasattr(_stream, "reconfigure"):

        try:

            _stream.reconfigure(
                encoding="utf-8",
                errors="replace",
            )

        except (ValueError, OSError):

            pass

from app.config import settings
from app.database import db
from app.time_labels import coerce_year_label

from app.data.providers import DataProviderRegistry
from app.topic.generator import TopicEngine
from app.topic.smart_story import SmartStoryEngine
from app.ai.script import ScriptEngine
from app.audio.tts import TTSEngine
from app.visuals.scene_engine import VisualEngine
from app.video.assembler import VideoAssembler

from app.youtube.metadata import MetadataEngine
from app.youtube.comments import (
    CommentEngine,
    generate_engagement_comment,
    post_comment_to_video,
)
from app.youtube.thumbnail import ThumbnailEngine
from app.youtube.uploader import (
    upload_video,
    upload_captions,
)
from app.captions import generate_srt

from app.qc.final_qc import FinalQC


# =========================================================
# YOUTUBE PUBLISHING MODE
# =========================================================

# ---------------------------------------------------------
# YOUTUBE PUBLISHING MODE
#
# Delayed-publish flow (default): videos go up as UNLISTED
# and are flipped to PUBLIC 15 minutes later by
# publish_worker.py (see README "Delayed publish flow").
# Override with YOUTUBE_PRIVACY_STATUS in .env if you ever
# need the old behavior.
# ---------------------------------------------------------

YOUTUBE_PRIVACY_STATUS = os.getenv(
    "YOUTUBE_PRIVACY_STATUS",
    "unlisted"
).lower()

if YOUTUBE_PRIVACY_STATUS not in [
    "private",
    "public",
    "unlisted"
]:
    raise ValueError(
        "Invalid YOUTUBE_PRIVACY_STATUS. "
        "Use: private, public, or unlisted."
    )


# =========================================================
# INTERACTIVE TOPIC MENU (opt-in only)
#
# Production schedules this script HEADLESS (see prod_run.*),
# so an unconditional input() would hang those runs forever.
# The menu therefore appears ONLY when stdin is a real TTY,
# or when RUN_MANUAL_TOPIC=<keyword> is set explicitly
# (allows scripted/forced manual runs). Empty env value or
# piped stdin => identical automatic behavior as always.
# =========================================================

# =========================================================
# TRENDING CANDIDATES (B2 — shown in the interactive menu)
#
# trend_scanner.py writes trend_candidates.json to the repo root
# (this folder) each morning.  When a human runs the pipeline
# interactively, the vetted trending topics are listed above the
# usual [1]/[2] menu so a trending keyword can be picked directly.
#
# Freshness gate: only candidates written within the last 24h
# are shown; stale files (and missing/corrupt files, and
# headless runs) behave exactly as before -- zero menu change.

# =========================================================


def _load_trending_candidates() -> list:

    """Load today's vetted trend candidates ([] when none/fresh)."""

    candidate_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "trend_candidates.json",
    )

    try:

        if not os.path.isfile(candidate_path):
            return []

        modified_at = datetime.fromtimestamp(
            os.path.getmtime(candidate_path)
        )

        if datetime.now() - modified_at > timedelta(hours=24):

            return []

        with open(
            candidate_path,
            "r",
            encoding="utf-8",
        ) as handle:

            payload = json.load(handle)

        candidates = payload.get("candidates", [])

        return candidates if isinstance(
            candidates,
            list,
        ) else []

    except (OSError, ValueError, TypeError):

        return []


def _print_trending_candidates(candidates: list) -> None:

    """Show the vetted trending picks above the topic menu."""

    if not candidates:

        return

    print(
        "\n🔥 TRENDING PICKS (vetted against the "
        "indicator catalog + provider health):"
    )

    for entry in candidates[:5]:

        print(
            f"   •  {entry.get('keyword', '?')}"
            f"\n      -> {entry.get('indicator_name', '?')}"
            f" ({entry.get('provider_name', '?')}."
            f" {entry.get('category', '')})"
        )

    print(
        "\n   Choose [1] then type one of these keywords "
        "to run a trending topic, or [2] for random."
    )


def prompt_topic_menu() -> str:
    """
    Topic menu with Curated Viral Battle as primary default.

    Returns:
        ""      -> choose option 1: Curated Viral Battle (automatic viral selection)
        keyword -> choose option 2: user-pinned custom keyword
    """

    print("\n" + "=" * 60)
    print("🎬 TOPIC SELECTION (Curated Viral Mode Active)")
    print("=" * 60)

    print(
        "  [1] Curated Viral Battle (DEFAULT) -> Maximum Retention & Clickability"
    )
    print(
        "      • AI Wars (ChatGPT vs Gemini vs Claude vs Groq)\n"
        "      • Programming Languages Race (Python vs JS vs Java vs C++ vs Rust)\n"
        "      • $3 Trillion Market Cap Clash (NVIDIA vs Apple vs Microsoft)\n"
        "      • Global EV Sales (Tesla vs BYD vs Xiaomi SU7)\n"
        "      • Browser Wars (Chrome vs IE vs Firefox vs Safari)\n"
        "      • Mobile OS Wars (Android vs iOS vs Symbian vs BlackBerry)\n"
        "      • YouTube Race (MrBeast vs T-Series) / Streaming Wars (Netflix vs Disney+)"
    )
    print(
        "  [2] Custom Keyword   -> type any keyword (e.g. gdp, birth rate, f1)"
    )
    print(
        "  [3] Open Macro Stats -> World Bank / IMF general economic data"
    )

    for _attempt in range(3):

        choice = input(
            "Select [1/2/3] (default 1 - Curated Viral): "
        ).strip().lower()

        if not choice or choice in ("1", "v", "viral", "default"):
            settings.TOPIC_SELECTION_MODE = "viral_curated"
            return ""

        if choice in ("2", "m", "custom", "keyword", "manual"):

            keyword = input(
                "Topic keyword: "
            ).strip()

            if keyword:
                return keyword

            print(
                "⚠️ Keyword was empty. Try again."
            )

            continue

        if choice in ("3", "macro", "open", "random"):
            settings.TOPIC_SELECTION_MODE = "macro_open"
            return ""

        if choice in ("q", "quit", "exit"):
            raise SystemExit(0)

        print(
            f"⚠️ Invalid choice '{choice}'. "
            "Enter 1, 2, or 3."
        )

    print(
        "\nℹ️ Defaulting to Curated Viral Battle selection."
    )
    settings.TOPIC_SELECTION_MODE = "viral_curated"
    return ""


# =========================================================
# ENTITY-IN-DATA VALIDATION (Issue 2 — named subject must be
# present in its own chart)
# =========================================================

class TopicDataMismatchError(Exception):
    """Raised when the topic/script names an entity that is not
    present in the fetched dataset.  The pipeline catches this
    and falls back (no video published) instead of rendering a
    video whose title claims something about an entity absent
    from its own chart."""


# Country-name tokens: letters, apostrophes and ampersands ONLY.
# A hyphen or space is deliberately excluded from the class, so a
# multi-word name splits into separate tokens that are each resolved
# through countries.name_forms.  Keeping the class free of escaped
# characters avoids the raw-string escaping traps that made an
# earlier revision of this guard silently match nothing.
_COUNTRY_TOKEN_RE = _re.compile(r"[A-Za-z][A-Za-z'&]*")


def _topic_named_entities(topic_data) -> list:
    """Ordered, de-duplicated entities the topic/script will NAME.

    Three sources, because a divergence between them is exactly how a
    video shipped whose title asked about India while the chart held
    Oman / Saudi Arabia / Lebanon / South Sudan:

      1. topic_data["selected_countries"] -- the country set the topic
         step handed to the Step-2 refetch;
      2. topic_data["story_metrics"] entity / leader / challenger --
         the Step-1 story metrics that
         ScriptEngine._build_story_context feeds straight into the
         script LLM.  This is the "earlier pipeline step" that names
         the subject even when the refetch's top-N frame no longer
         contains it (Step 1 scored India at #2 -> #3, then Step 2's
         ranking-based frame dropped India entirely);
      3. country-name tokens in the topic string AND the title,
         scanned SEPARATELY -- `topic or title` would never look at
         the title whenever the topic field is populated.

    Only widely-recognized country names are returned (see
    app.countries.name_forms), so the guard fires on a titled subject
    like "India" without tripping on incidental words.
    """

    from app.countries import name_forms

    forms = name_forms()

    entities = []

    def _add(value) -> None:
        text = str(value or "").strip()
        if not text:
            return
        if text not in entities:
            entities.append(text)

    # --- Source 1: the topic's own country set -------------------
    for entity in topic_data.get("selected_countries") or []:
        _add(entity)

    # --- Source 2: Step-1 story metrics (entity/leader/challenger)
    metrics = topic_data.get("story_metrics") or {}

    if isinstance(metrics, dict):
        for key in ("entity", "leader", "challenger"):
            _add(metrics.get(key))

    # --- Source 3: country tokens in topic AND title -------------
    for source in ("topic", "title"):
        text = str(topic_data.get(source) or "").strip()
        if not text:
            continue

        # "current US$" is World Bank currency notation, not a
        # United States mention.  Indicators like "Military
        # expenditure (current US$)" leak into topic strings, and
        # the token scan would otherwise inject a phantom 'US'
        # requirement that blocks every such topic.
        text = _re.sub(r"US\$", " ", text)

        for token in _COUNTRY_TOKEN_RE.findall(text):
            normalized = token.strip("'&").lower()
            if normalized not in forms:
                continue
            # "the world's biggest X" is a SCOPE phrase, not a
            # named subject -- a World aggregate bar is only
            # required when selected_countries / story_metrics
            # (sources 1-2) explicitly name it.
            if normalized == "world":
                continue
            _add(token)

    return entities


def _collect_script_highlight_entities(script) -> set:
    """Return the set of entity names that appear in at least one
    scene's highlight_countries across the whole script.

    This is the set the rendered chart is GUARANTEED to show,
    because render_bar_race explicitly reserves a bar for every
    highlight_country that has usable data.
    """

    entities = set()

    for scene in getattr(script, "scenes") or []:
        for country in (
            getattr(scene, "highlight_countries") or []
        ):
            if country:
                entities.add(country)

    return entities


def _entity_identity(entity):
    """Canonical identity for representation-safe entity comparison.

    The same country appears in three representations across the
    pipeline: ISO3 codes from selected_countries ("UKR"), plain
    names in script highlight_countries ("Ukraine") and World Bank
    label variants in the frame ("Ukraine, Rep.").  Both sides of
    every coverage comparison are reduced to the gazetteer's iso2
    code (app.countries.lookup) so a match is decided on canonical
    identity, never on string form.  Unrecognised tokens fall back
    to a casefolded exact form.
    """

    text = str(entity or "").strip()

    if not text:
        return None

    try:
        from app.countries import lookup

        meta = lookup(text)

        if meta and meta.get("iso2"):
            return meta["iso2"]

    except Exception:
        pass

    return text.casefold()


def _title_identities(text) -> set:
    """Canonical identities of country subjects named in a title.

    The renderer merges title subjects into every scene's focus
    (FOCUS-ENTITY BAR CAP), so a title that names a country gives it
    a guaranteed bar even when the LLM never listed it in
    highlight_countries.  Gate coverage counts titles exactly the
    same way the renderer draws them.
    """

    cleaned = _re.sub(r"US\$", " ", str(text or ""))
    found = set()

    try:
        from app.countries import name_forms

        forms = name_forms()
    except Exception:
        return found

    for token in _COUNTRY_TOKEN_RE.findall(cleaned):
        norm = token.strip("'&").lower()

        if norm in forms and norm != "world":
            identity = _entity_identity(norm)

            if identity:
                found.add(identity)

    return found


def _script_highlight_keys(script) -> dict:
    """identity -> original representation for every entity the
    script guarantees a bar for: scene highlight countries AND the
    country subjects named in the script/scene titles (the renderer
    merges title subjects into focus, so they are drawn too)."""

    keys = {}

    for country in _collect_script_highlight_entities(script):
        identity = _entity_identity(country)

        if identity is not None and identity not in keys:
            keys[identity] = country

    titles = [getattr(script, "title", "")]
    titles += [
        getattr(scene, "title", "")
        for scene in (getattr(script, "scenes") or [])
    ]

    for title in titles:
        for identity in _title_identities(title):
            if identity not in keys:
                keys[identity] = str(title)

    return keys


def _missing_named_entities(named_entities, script) -> list:
    """Named entities NOT canonically covered by the script's
    scene highlights (ISO3 vs full-name representations count as
    present -- see _entity_identity)."""

    keys = _script_highlight_keys(script)

    return [
        entity
        for entity in named_entities
        if _entity_identity(entity) not in keys
    ]


def _backfill_script_highlights(script, missing_entities, data):
    """Deterministically cover named entities the script missed.

    The script LLM frequently names only the story's protagonist
    (e.g. "Ukraine") while the topic's country set names six
    countries.  Rather than blocking an otherwise-correct video,
    each still-missing named entity is added to a scene's
    highlight_countries -- the renderer guarantees a bar for every
    highlight (FOCUS-ENTITY BAR CAP).

    Placement is cap-aware: title subjects and existing highlights
    already count against settings.MAX_CHART_ENTITIES per scene, so
    backfill never pushes an entity that draws today out of frame.
    An entity that fits nowhere stays missing and the gate blocks
    the video exactly as before -- the safety check itself is not
    weakened.

    Returns a list of (entity, frame_label, scene_index) notes for
    what was actually added; empty list means nothing changed.
    """

    notes = []

    scenes = list(getattr(script, "scenes") or [])

    if not scenes or not missing_entities:
        return notes

    # Frame labels the renderer will actually see.
    labels = []

    if data is not None and not getattr(data, "empty", True):
        try:
            from app.visuals.scene_engine import VisualEngine

            labels = VisualEngine._index_display_labels(data)
        except Exception:
            labels = []

    try:
        cap = int(getattr(settings, "MAX_CHART_ENTITIES", 4))
    except (TypeError, ValueError):
        cap = 4

    cap = max(2, cap)

    # Title subjects are merged into focus at render time too, so
    # count them against the cap before placing anything.

    # Focus identities already committed per scene.
    focus_ids = []

    for scene in scenes:
        committed = set()

        for country in getattr(scene, "highlight_countries") or []:
            identity = _entity_identity(country)

            if identity:
                committed.add(identity)

        committed |= _title_identities(getattr(scene, "title", ""))
        committed |= _title_identities(getattr(script, "title", ""))
        focus_ids.append(committed)

    for entity in missing_entities:
        identity = _entity_identity(entity)

        if identity is None:
            continue

        # Already covered by an earlier placement (alias forms
        # like "UK" / "United Kingdom" share one identity).
        if any(identity in committed for committed in focus_ids):
            continue

        # Prefer the exact frame label the renderer will draw.
        label = None

        if labels:
            try:
                from app.visuals.scene_engine import VisualEngine

                label = VisualEngine._match_label(entity, labels)
            except Exception:
                label = None

        if not label:
            try:
                from app.countries import lookup

                meta = lookup(entity)

                if meta and meta.get("display"):
                    label = meta["display"]

            except Exception:
                label = None

        if not label:
            label = str(entity)

        # Place in the scene with the most room left under the cap.
        placed_at = None

        for index in sorted(
            range(len(scenes)),
            key=lambda i: len(focus_ids[i]),
        ):

            if len(focus_ids[index]) < cap:
                placed_at = index
                break

        if placed_at is None:
            # No room anywhere -> stays missing -> gate blocks.
            continue

        scene = scenes[placed_at]
        current = list(getattr(scene, "highlight_countries") or [])
        current.append(label)
        scene.highlight_countries = current
        focus_ids[placed_at].add(identity)
        notes.append((entity, label, placed_at))

    return notes


def _ensure_data_matches_topic_entities(topic_data, data) -> None:
    """Hard guarantee: every entity the topic explicitly names must
    be present in the data frame that will actually be charted.

    Collects the named entities via _topic_named_entities (topic
    country set + Step-1 story metrics + topic/title country tokens)
    and resolves each against the frame with the renderer's own
    _match_label, so the validation simulates exactly what will be
    drawn.  If ANY named entity is absent, raises
    TopicDataMismatchError BEFORE script generation or rendering --
    the pipeline catches this and falls back rather than publishing a
    video whose title claims something about an entity that does not
    appear in its own chart.
    """

    from app.visuals.scene_engine import (
        VisualEngine,
    )

    if data is None or getattr(data, "empty", True):
        return

    labels = VisualEngine._index_display_labels(data)

    if not labels:
        return

    missing = [
        entity
        for entity in _topic_named_entities(topic_data)
        if VisualEngine._match_label(entity, labels) is None
    ]

    if missing:
        raise TopicDataMismatchError(
            f"Topic names entity(ies) [{', '.join(sorted(set(missing)))}] "
            f"that are NOT present in the fetched dataset "
            f"({len(labels)} labels: {', '.join(labels[:8])}{'...' if len(labels) > 8 else ''}). "
            f"The topic/title strings were: "
            f"topic={str(topic_data.get('topic') or '')[:80]!r}, "
            f"title={str(topic_data.get('title') or '')[:80]!r}"
        )


# =========================================================
# MAIN PIPELINE
# =========================================================

def _provider_accepts_countries(provider) -> bool:

    """
    True when the provider's fetch_normalized implements the
    optional `countries` parameter (worldbank, owid, imf).
    Non-country providers (F1, anime, vehicles, companies...)
    keep their unchanged signatures and simply ignore the hint.
    """

    return bool(
        getattr(
            provider,
            "supports_countries",
            lambda: False,
        )()
    )


def run_test_pipeline():

    try:

        # =====================================================
        # 0. DAILY UPLOAD LIMIT
        # =====================================================

        today_count = db.get_today_video_count()

        print(
            f"\n📊 Today's uploads: "
            f"{today_count}/{settings.DAILY_UPLOADS}"
        )

        if db.daily_limit_reached():

            print("\n" + "=" * 60)
            print("🛑 DAILY UPLOAD LIMIT REACHED")
            print("=" * 60)

            print(
                f"Today's limit: "
                f"{settings.DAILY_UPLOADS}"
            )

            print(
                "No new video will be generated "
                "or uploaded today."
            )

            return

        print(
            "\n🚀 Starting Automated Data Shorts Factory"
        )

        print("-" * 60)

        print(
            f"\n📢 YouTube publishing mode: "
            f"{YOUTUBE_PRIVACY_STATUS.upper()}"
        )

        # =====================================================
        # 1. TOPIC GENERATION
        # =====================================================

        print("\n" + "=" * 60)
        print("🧠 STEP 1 — TOPIC GENERATION")
        print("=" * 60)

        topic_data = None

        # -----------------------------------------------------
        # 1a. OPTIONAL MANUAL KEYWORD SELECTION
        #
        # An interactively chosen keyword resolves through
        # app.topic.manual_topic.ManualTopicEngine, which hands
        # back an object built by the SAME StoryCandidate.
        # to_topic_data() factory the automatic engine uses --
        # shape parity is proven by
        # test_manual_topic_shape_parity.py.
        #
        # Trigger conditions (both opt-in only):
        #   * RUN_MANUAL_TOPIC=<keyword>  env var (headless-capable)
        #   * interactive stdin TTY       -> menu prompt
        # Otherwise this whole block is skipped and behavior is
        # byte-for-byte what it was before.
        # -----------------------------------------------------

        # -----------------------------------------------------
        # CLI ARGUMENTS (--topic, --format)
        # -----------------------------------------------------
        cli_topic = None
        cli_format = None
        args = sys.argv[1:]
        for idx, arg in enumerate(args):
            if arg in ("--topic", "-t") and idx + 1 < len(args):
                cli_topic = args[idx + 1].strip()
            elif arg.startswith("--topic="):
                cli_topic = arg.split("=", 1)[1].strip()
            elif arg in ("--format", "-f") and idx + 1 < len(args):
                cli_format = args[idx + 1].strip().lower()
            elif arg.startswith("--format="):
                cli_format = arg.split("=", 1)[1].strip().lower()

        if cli_format:
            settings.VIDEO_FORMAT = cli_format
            print(f"\n🎬 Video format set via CLI: {settings.VIDEO_FORMAT.upper()} ({settings.canvas_width}x{settings.canvas_height})")

        manual_keyword = (
            cli_topic
            or os.getenv("RUN_MANUAL_TOPIC", "").strip()
        )

        if (
            not manual_keyword
            and sys.stdin.isatty()
        ):

            manual_keyword = prompt_topic_menu()

        if manual_keyword:

            print(
                f"\n🎯 Manual topic requested: "
                f"'{manual_keyword}'"
            )

            try:

                from app.topic.manual_topic import (
                    ManualTopicEngine,
                    ManualTopicError,
                )

                topic_data = (
                    ManualTopicEngine
                    .generate_manual_topic(
                        manual_keyword
                    )
                )

            except ManualTopicError as manual_error:

                print(
                    "\n⚠️ Manual topic unavailable; "
                    "falling back to automatic "
                    "selection."
                )

                print(
                    f"   Reason: {manual_error}"
                )

                suggestions = getattr(
                    manual_error,
                    "suggestions",
                    [],
                ) or []

                if suggestions:

                    print(
                        "   Available topics:"
                    )

                    for suggestion in suggestions[:12]:

                        print(
                            f"     - {suggestion}"
                        )

            except Exception as manual_error:

                print(
                    "\n⚠️ Manual selection failed "
                    "unexpectedly; falling back to "
                    "automatic selection."
                )

                print(
                    f"   Reason: {manual_error}"
                )

        # -----------------------------------------------------
        # 1b. AUTOMATIC SELECTION (unchanged behavior)
        # -----------------------------------------------------

        if topic_data is None:

            try:

                topic_data = (
                    SmartStoryEngine.generate_topic()
                )

            except Exception as smart_story_error:

                print(
                    "\nSmart Story Engine failed; "
                    "falling back to TopicEngine."
                )

                print(
                    f"Reason: {smart_story_error}"
                )

        if topic_data is None:

            topic_data = TopicEngine.generate_topic()

            topic_data.setdefault(
                "provider_id",
                "worldbank"
            )

            topic_data.setdefault(
                "chart_type",
                "bar_race"
            )

            topic_data.setdefault(
                "source_name",
                "World Bank"
            )

            topic_data.setdefault(
                "source_url",
                "https://data.worldbank.org"
            )

        force_chart_type = os.getenv("FORCE_CHART_TYPE", "").strip().lower()
        if force_chart_type:
            topic_data["chart_type"] = force_chart_type
            print(f"🎯 Forced chart type: '{force_chart_type}'")

        print("\n✅ Topic Generated:")

        print(
            f"   {topic_data['topic']}"
        )

        print(
            f"   Indicator: "
            f"{topic_data.get('indicator_code', 'N/A')}"
        )

        print(
            f"   Provider: "
            f"{topic_data.get('provider_id', 'worldbank')}"
        )

        print(
            f"   Story Type: "
            f"{topic_data.get('story_type', 'N/A')}"
        )

        print(
            f"   Timeframe: "
            f"{topic_data.get('years', 15)} years"
        )

        # =====================================================
        # 2. DATA COLLECTION
        # =====================================================

        indicator_code = topic_data.get(
            "indicator_code",
            "SP.POP.TOTL"
        )

        provider_id = topic_data.get(
            "provider_id",
            "worldbank"
        )

        provider_name = topic_data.get("source_name") or provider_id.upper()
        print("\n" + "=" * 60)
        print(f"📊 STEP 2 — {provider_name.upper()} DATA")
        print("=" * 60)

        try:

            years = int(
                topic_data.get(
                    "years",
                    15
                )
            )

        except (
            ValueError,
            TypeError
        ):

            years = 15

        print(
            f"\nFetching {years}-year time series..."
        )

        story_type = topic_data.get(
            "story_type",
            "fastest_growth"
        )

        provider_fetch_story_type = topic_data.get(
            "provider_fetch_story_type",
            story_type
        )

        provider = DataProviderRegistry.get(
            provider_id
        )

        # -----------------------------------------------------
        # CONSTRAINED STEP-2 REFETCH (Step1/Step2 consistency fix)
        #
        # Step 1 scored and quality-validated the winning
        # candidate on a SPECIFIC dataset: specific countries
        # (and for manual country requests, the countries the
        # user explicitly asked for) fetched with a specific
        # min_countries.  The refetch below is therefore
        # constrained to that same contract:
        #
        #   * selected_countries       -- Step 1's exact country
        #     set (required + context); Step 2 can no longer
        #     silently re-rank the whole world and produce a
        #     different narrative (current_leader video about a
        #     biggest_jump country set).
        #   * selected_min_countries   -- the min_countries value
        #     Step 1 actually used (6), instead of the provider
        #     default (8) that used to silently change the frame
        #     size (6 vs 8 countries).
        #
        # The story_type REMAPS still applies (the refetch ranks
        # the SAME countries for the requested story), but only
        # within the validated country set.  Providers that do
        # not implement the optional `countries` parameter
        # (non-country data sources) simply get the
        # min_countries fix.
        # -----------------------------------------------------

        selected_countries = topic_data.get(
            "selected_countries"
        ) or []

        selected_min_countries = topic_data.get(
            "selected_min_countries",
            6
        )

        # -----------------------------------------------------
        # NAMED-ENTITY GUARANTEE (Issue 2 fix)
        #
        # The topic's `selected_countries` is NOT guaranteed to
        # contain the entity the topic/script actually talks
        # about: the auto path derives it from the Step-1 scoring
        # frame's own codes (StoryCandidate._frame_country_codes),
        # which is a "top-N by story ranking" list -- India can
        # rank outside it while story_metrics still reports
        # entity="India", rank_change=-1.  The script then writes
        # its title/narration around India and the chart shows
        # somebody else.
        #
        # So merge every entity the topic/script NAMES into the
        # constrained fetch.  _topic_named_entities covers the
        # Step-1 story metrics (entity/leader/challenger) plus
        # country tokens in the topic and title, so a named
        # subject is REQUESTED rather than merely hoped for.  The
        # provider guarantees each requested country a slot that
        # has usable data (select_required_plus_context), and the
        # validation below still blocks the render if one is
        # missing anyway.
        # -----------------------------------------------------

        named_entities = _topic_named_entities(topic_data)

        fetch_countries = list(selected_countries)

        for entity in named_entities:
            if entity not in fetch_countries:
                fetch_countries.append(entity)

        if named_entities:
            added = [
                entity
                for entity in fetch_countries
                if entity not in selected_countries
            ]
            if added and _provider_accepts_countries(provider):
                print(
                    "   Named entities added to the country "
                    f"constraint: {', '.join(added)}"
                )

        fetch_kwargs = {
            "indicator_code": indicator_code,
            "years": years,
            "story_type": provider_fetch_story_type,
            "min_countries": selected_min_countries,
        }

        if (
            fetch_countries
            and _provider_accepts_countries(provider)
        ):

            fetch_kwargs["countries"] = fetch_countries

            print(
                f"   Country constraint: "
                f"{', '.join(fetch_countries)}"
            )

        provider_result = provider.fetch_normalized(
            **fetch_kwargs
        )

        data = provider_result.wide_data

        if hasattr(data, "index") and not data.empty:
            _norm_index = []
            for _item in data.index:
                if isinstance(_item, (tuple, list)) and len(_item) >= 2:
                    _norm_index.append(str(_item[-1]).strip())
                elif isinstance(_item, (tuple, list)) and len(_item) == 1:
                    _norm_index.append(str(_item[0]).strip())
                else:
                    _raw = str(_item).strip()
                    if _raw.startswith("(") and _raw.endswith(")"):
                        _m = _re.match(r"^\(\s*['\"]?([^'\",]+)['\"]?\s*,\s*['\"]?([^'\"]+)['\"]?\s*\)$", _raw)
                        if _m:
                            _raw = _m.group(2).strip()
                    _norm_index.append(_raw)
            data.index = _norm_index

        entity_label = "countries" if _provider_accepts_countries(provider) else "entities"

        if data.empty:

            print(
                f"❌ No {provider_name} data returned."
            )

            return

        indicator_name = topic_data.get(
            "indicator_name",
            provider_result.metric_name
        )

        source_name = topic_data.get(
            "source_name",
            provider_result.source_name
        )

        source_url = topic_data.get(
            "source_url",
            provider_result.source_url
        )

        topic_data["indicator_name"] = indicator_name
        topic_data["source_name"] = source_name
        topic_data["source_url"] = source_url

        print(
            f"✅ Data Collected: "
            f"{len(data)} {entity_label} fetched."
        )

        print(
            f"   Years available: "
            f"{data.columns[0]} → "
            f"{data.columns[-1]}"
        )

        # =====================================================
        # 3b. ENTITY-IN-DATA VALIDATION (Issue 2 — India absent
        #      from chart guard)
        #
        # Hard guarantee: if the topic/script explicitly NAMES an
        # entity (e.g. "India" in "India vs Saudi Arabia"), that
        # entity MUST be confirmed present in the data actually
        # being charted.  A topic can name India in its title and
        # script while the data query (selected_countries from an
        # earlier pipeline step, or a "top-N near X" query that
        # doesn't guarantee the named entity is included) silently
        # dropped it — this block catches that mismatch BEFORE any
        # video is assembled and falls back to regenerating the
        # topic instead of publishing a broken video.
        # =====================================================

        try:
            _ensure_data_matches_topic_entities(topic_data, data)

        except TopicDataMismatchError as exc:

            print()
            print("=" * 60)
            print("🛑 ENTITY-IN-DATA MISMATCH — VIDEO BLOCKED")
            print("=" * 60)
            print(f"   {exc}")
            print()
            print("   The topic names an entity that is not present in")
            print("   the fetched dataset.  Publishing would produce a")
            print("   video whose title/subject claims something about")
            print("   an entity that does not appear in its own chart.")
            print("   Falling back: no video will be generated this run.")
            print("   (Regenerate the topic with a country-inclusive")
            print("   query to resolve.)")
            print("=" * 60)

            return

        # =====================================================
        # 3. OUTPUT DIRECTORY
        #
        # IMPORTANT: Use a unique run identifier in the output
        # directory so each generated video has a unique path.
        #
        # The duplicate-upload guard (has_video_been_uploaded)
        # compares video_path to detect already-uploaded videos.
        # If every run reuses the same path
        # (output/test_run/final_video.mp4), the guard will
        # incorrectly block every new video because old records
        # with the same path exist.
        #
        # By using a unique run directory, each video gets a
        # unique path, so the guard correctly distinguishes
        # old uploaded videos from newly generated ones.
        # =====================================================

        from datetime import datetime as _datetime

        run_id = _datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        output_dir = os.path.join(
            settings.OUTPUT_DIR,
            "test_run",
            run_id
        )

        os.makedirs(
            output_dir,
            exist_ok=True
        )

        print(
            f"\n📁 Output directory: "
            f"{output_dir}"
        )

        # =====================================================
        # 4. SCRIPT GENERATION
        # =====================================================

        print("\n" + "=" * 60)
        print("📝 STEP 3 — SCRIPT GENERATION")
        print("=" * 60)

        script = ScriptEngine.generate_script(
            topic_data,
            data,
            indicator_name
        )

        script.source_name = source_name
        script.source_url = source_url
        script.indicator_code = topic_data.get("indicator_code", "")
        script.chart_type = topic_data.get(
            "chart_type",
            getattr(
                script,
                "chart_type",
                None
            )
            or "bar_race"
        )

        force_chart_type = os.getenv("FORCE_CHART_TYPE", "").strip().lower()
        if force_chart_type:
            script.chart_type = force_chart_type
            for scene in getattr(script, "scenes", []):
                scene.chart_type = force_chart_type

        print(
            f"\n📝 Script Generated: "
            f"{script.title}"
        )

        # -----------------------------------------------------
        # Save script
        # -----------------------------------------------------

        script_path = os.path.join(
            output_dir,
            "script.json"
        )

        with open(
            script_path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
                script.model_dump_json(
                    indent=2
                )
            )

        print(
            f"📄 Script saved to: "
            f"{script_path}"
        )

        # =====================================================
        # 4b. NAMED-ENTITY SCRIPT COVERAGE VALIDATION
        #     (Issue 2 — second gate)
        # =====================================================
        #
        # The step-3b gate (Entity-in-Data) verified that every
        # entity the topic NAMES is present in the fetched DATA.
        # This second gate verifies that every such entity is also
        # present in the RENDERED SCRIPT -- i.e. at least one
        # scene's highlight_countries includes it.  Without this
        # gate, the data fetch can include India (step 3b passes)
        # while the script generator writes a Saudi-Arabia-centric
        # story that never mentions India, producing a video whose
        # title talks about India but whose chart never shows it.
        #
        # A video is BLOCKED (no publish, no fallback video) when
        # a named entity is absent from ALL scenes' highlight
        # lists.  This is a hard guarantee, not a soft preference.
        #
        # Two representation-safety measures run before the block:
        #   1. both sides are compared on canonical identity
        #      (_entity_identity) so "UKR" == "Ukraine" ==
        #      "Ukraine, Rep." -- the same fix as the step-3b
        #      ENTITY-IN-DATA gate;
        #   2. entities the LLM genuinely failed to highlight are
        #      deterministically BACKFILLED into scene highlights
        #      inside the mobile bar cap, so the renderer reserves
        #      their bars.  What cannot be placed still blocks.
        # =====================================================

        _named_entities_topic = _topic_named_entities(topic_data)

        _missing_from_script = _missing_named_entities(
            _named_entities_topic,
            script,
        )

        if _missing_from_script:

            _backfill_notes = _backfill_script_highlights(
                script,
                _missing_from_script,
                data,
            )

            if _backfill_notes:

                print(
                    "\n   ↩️  Named entities backfilled into scene "
                    "highlights:"
                )

                for _ent, _label, _idx in _backfill_notes:
                    print(
                        f"        {_ent} -> \"{_label}\" "
                        f"(scene {_idx + 1})"
                    )

                # Persist the repaired artifact so script.json
                # matches what the renderer will receive.
                with open(
                    script_path,
                    "w",
                    encoding="utf-8",
                ) as _f:
                    _f.write(
                        script.model_dump_json(indent=2)
                    )

            _missing_from_script = _missing_named_entities(
                _named_entities_topic,
                script,
            )

        _named_script_entities = _collect_script_highlight_entities(script)

        if _missing_from_script:
            print()
            print("=" * 60)
            print("🛑 NAMED-ENTITY MISSING FROM SCRIPT — VIDEO BLOCKED")
            print("=" * 60)
            print(
                f"   Topic/script names: "
                f"{', '.join(_named_entities_topic)}"
            )
            _script_entities_str = (
                ", ".join(sorted(_named_script_entities))
                if _named_script_entities
                else "(none)"
            )
            print(
                f"   Entities in script: {_script_entities_str}"
            )
            print(
                f"   Missing from script: "
                f"{', '.join(_missing_from_script)}"
            )
            print()
            print("   The script generator produced a story that does")
            print("   not cover every entity the topic names, and the")
            print("   entity could not be backfilled into any scene")
            print("   without exceeding the mobile bar cap.  Publishing")
            print("   would produce a video whose title/subject claims")
            print("   something about an entity that does not appear in")
            print("   any scene's highlighted bars.  Falling back: no")
            print("   video will be generated this run.")
            print("   (Regenerate the topic or adjust the script prompt")
            print("   to include the named entity.)")
            print("=" * 60)

            return

        print(
            "   ✅ Named-entity script coverage check passed: "
            f"{', '.join(_named_entities_topic)}"
        )

        # =====================================================
        # 5. AUDIO / TTS
        # =====================================================

        print("\n" + "=" * 60)
        print("🎙️ STEP 4 — VOICEOVER")
        print("=" * 60)

        # -----------------------------------------------------
        # Voice selection (human-touch layer): the voice is
        # chosen PER CATEGORY (config: VOICE_CATEGORY_MAP, with
        # a stable-hash fallback through VOICE_ROTATION_POOL),
        # so economy always sounds like narrator A, population
        # like narrator B, etc.  `last_voice` from history still
        # guards against an immediate repeat for categories
        # without a mapping.
        # -----------------------------------------------------

        topic_category = str(
            topic_data.get("category") or ""
        ).strip()

        chosen_voice = TTSEngine.pick_voice(
            db.get_last_voice(),
            category=topic_category,
            # Priority 3: a category may map to a POOL of voices;
            # the recent history lets pick_voice() choose the one
            # that has gone longest unused instead of a fixed
            # narrator for every video of that category.
            last_voices=db.get_recent_voices(8),
        )

        print(f"🎙️ Voice for this video: {chosen_voice}")

        # Short spoken hook (5-8 words) before the data reveal,
        # rotated from the config INTRO_LINE_POOL per topic.
        # Empty pool -> None -> the hook is disabled entirely.
        intro_line = TTSEngine.pick_intro_line(
            topic_key=(
                f"{topic_category}|"
                f"{topic_data.get('indicator_code') or ''}|"
                f"{topic_data.get('story_type') or ''}"
            ),
            last_line=TTSEngine.load_last_intro_line(),
        )

        if intro_line:
            print(f"🎙️ Intro hook line: {intro_line}")

        audio_data = (
            TTSEngine.generate_narration(
                script,
                output_dir,
                voice=chosen_voice,
                intro_line=intro_line,
            )
        )

        # Persist the hook only after narration actually rendered,
        # so a failed run doesn't consume a pool entry.
        if intro_line:
            TTSEngine.save_last_intro_line(intro_line)

        print(
            f"✅ Voiceover generated: "
            f"{len(audio_data)} audio files."
        )

        # -----------------------------------------------------
        # REAL narration length (measured per scene by TTS).
        # This is the source of truth for the visual timeline:
        # the animation is sized to the actual audio so the
        # assembler never has to truncate narration or visuals.
        # -----------------------------------------------------

        real_audio_duration = max(
            (
                float(item.get("end_time") or 0.0)
                for item in audio_data
                if isinstance(item, dict)
            ),
            default=0.0,
        )

        if real_audio_duration > 0:

            print(
                f"⏱️ Measured narration length: "
                f"{real_audio_duration:.2f}s "
                f"(planned script: {script.total_duration}s)."
            )

            if real_audio_duration > 90:

                print(
                    "⚠️ Narration exceeds 90s — the final video "
                    "will run long for a Short. Consider "
                    "shortening the script for future runs "
                    "(improvement backlog); content is never "
                    "truncated to fit."
                )

        else:

            real_audio_duration = None

            print(
                "⚠️ Could not measure narration length from "
                "audio data; falling back to the planned "
                "script duration for rendering."
            )

        # =====================================================
        # 6. VISUAL GENERATION
        # =====================================================

        print("\n" + "=" * 60)
        print("🎨 STEP 5 — VISUAL GENERATION")
        print("=" * 60)

        visual_data = (
            VisualEngine.render_scenes(
                script,
                data,
                output_dir,
                audio_duration=real_audio_duration,
            )
        )

        print(
            f"✅ Visuals rendered: "
            f"{len(visual_data)} video(s)."
        )

        # =====================================================
        # 7. VIDEO ASSEMBLY
        # =====================================================

        print("\n" + "=" * 60)
        print("🎬 STEP 6 — VIDEO ASSEMBLY")
        print("=" * 60)

        # -----------------------------------------------------
        # Captions (timed to the REAL narration audio, shifted
        # by the branded intro length when cards are on; written
        # alongside the final video so they can be burned onto frames).
        # -----------------------------------------------------

        caption_offset = 0.0

        try:

            from app.video.branding import INTRO_DURATION_S

            intro_card_path = os.path.join(
                output_dir, "intro_card.mp4"
            )

            if os.path.exists(intro_card_path):
                caption_offset = float(INTRO_DURATION_S)

        except Exception:

            caption_offset = 0.0

        captions_path = generate_srt(
            audio_data,
            output_dir,
            time_offset=caption_offset,
        )

        final_video_path = (
            VideoAssembler.create_video(
                audio_data,
                visual_data,
                output_dir,
                sfx_category=topic_category,
                captions_path=captions_path,
            )
        )

        print(
            "\n✅ Final Video assembled:"
        )

        print(
            f"   {final_video_path}"
        )

        # =====================================================
        # 8. YOUTUBE METADATA
        # =====================================================

        print("\n" + "=" * 60)
        print("📝 STEP 7 — YOUTUBE METADATA")
        print("=" * 60)

        # Title-format rotation: avoid repeating the format
        # used by the last uploaded video (None on first run).
        last_title_format = db.get_last_title_format()

        metadata = (
            MetadataEngine.generate_metadata(
                script,
                data,
                story_type=topic_data.get(
                    "story_type"
                ),
                last_title_format=last_title_format,
            )
        )

        # -----------------------------------------------------
        # Ensure #Shorts exists
        # -----------------------------------------------------

        description = str(
            metadata.get(
                "description",
                ""
            )
        ).strip()

        if "#shorts" not in description.lower():

            if description:

                description += (
                    "\n\n#Shorts"
                )

            else:

                description = "#Shorts"

            metadata["description"] = description

        # -----------------------------------------------------
        # Save metadata
        # -----------------------------------------------------

        metadata_path = os.path.join(
            output_dir,
            "youtube_metadata.json"
        )

        with open(
            metadata_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                metadata,
                f,
                indent=2,
                ensure_ascii=False
            )

        print(
            "\n✅ YouTube metadata saved:"
        )

        print(
            f"   {metadata_path}"
        )

        # -----------------------------------------------------
        # Display metadata
        # -----------------------------------------------------

        print(
            "\n🎬 YouTube Title:"
        )

        print(
            f"   {metadata.get('title', '')}"
        )

        print(
            "\n📄 Description:"
        )

        print(
            f"   {metadata.get('description', '')}"
        )

        print(
            "\n#️⃣ Hashtags:"
        )

        print(
            f"   "
            f"{' '.join(metadata.get('hashtags', []))}"
        )

        print(
            "\n🔎 YouTube Tags:"
        )

        print(
            f"   "
            f"{', '.join(metadata.get('tags', []))}"
        )

        print(
            "\n📚 Category:"
        )

        print(
            f"   {metadata.get('category', '')}"
        )

        print(
            "\n🖼️ Thumbnail Text:"
        )

        print(
            f"   "
            f"{metadata.get('thumbnail_text', '')}"
        )

        # =====================================================
        # 9. THUMBNAIL FRAME GENERATION
        # =====================================================

        print("\n" + "=" * 60)
        print("🖼️ STEP 8 — THUMBNAIL GENERATION")
        print("=" * 60)

        thumbnail_candidates = (
            ThumbnailEngine.generate_candidates(
                final_video_path,
                output_dir,
                metadata.get("thumbnail_text")
            )
        )

        print(
            "\n✅ Thumbnail candidates generated:"
        )

        for thumbnail in thumbnail_candidates:

            print(
                f"   🖼️ {thumbnail}"
            )

        # =====================================================
        # 10. FINAL QC
        # =====================================================

        print("\n" + "=" * 60)
        print("🔎 STEP 9 — FINAL QUALITY CONTROL")
        print("=" * 60)

        qc_passed = FinalQC.run(
            video_path=final_video_path,
            metadata_path=metadata_path,
            script_path=script_path
        )

        # -----------------------------------------------------
        # STOP IF QC FAILS
        # -----------------------------------------------------

        if not qc_passed:

            print("\n" + "=" * 60)
            print("🚫 FINAL QC FAILED")
            print("=" * 60)

            print(
                "🚫 Pipeline stopped."
            )

            print(
                "🚫 Video will NOT be uploaded."
            )

            return

        print(
            "\n✅ FINAL QC PASSED."
        )

        # =====================================================
        # 11. YOUTUBE UPLOAD
        # =====================================================

        print("\n" + "=" * 60)
        print("📤 STEP 10 — YOUTUBE UPLOAD")
        print("=" * 60)

        print(
            "\n🚀 Starting YouTube upload..."
        )

        # -----------------------------------------------------
        # Select thumbnail
        # -----------------------------------------------------

        thumbnail_path = None

        if thumbnail_candidates:

            # Prefer a TITLED cover for the Shorts shelf;
            # fall back to the first raw frame.

            titled_candidates = [
                path
                for path in thumbnail_candidates
                if "_titled" in os.path.basename(path)
            ]

            thumbnail_path = (
                titled_candidates[0]
                if titled_candidates
                else thumbnail_candidates[0]
            )

            print(
                "\n🖼️ Selected thumbnail:"
            )

            print(
                f"   {thumbnail_path}"
            )

        # -----------------------------------------------------
        # Idempotency guard: prevent duplicate uploads
        #
        # If this exact video file has already been uploaded
        # (recorded in the database with upload_status='uploaded'),
        # skip the upload entirely.  This protects against
        # accidental duplicate uploads caused by pipeline
        # reruns, retries, or a crash between the upload and
        # the database save.
        # -----------------------------------------------------

        if db.has_video_been_uploaded(
            final_video_path,
            topic=topic_data.get("topic", "") if isinstance(topic_data, dict) else "",
            title=getattr(script, "title", ""),
        ):

            print(
                "\n🛑 SKIPPING UPLOAD: "
                "This video file has already been uploaded."
            )

            print(
                f"   {final_video_path}"
            )

            print(
                "No duplicate YouTube upload will be performed."
            )

            return

        if os.getenv("SKIP_UPLOAD", "").strip().lower() in ("true", "1", "yes"):
            print(
                "\n⏩ SKIP_UPLOAD enabled: Video generated successfully; upload deferred for visual QA."
            )
            print(f"   Final video: {final_video_path}")
            return

        # -----------------------------------------------------
        # Upload
        # -----------------------------------------------------

        print(
            "\n📢 Upload privacy mode:"
        )

        print(
            f"   {YOUTUBE_PRIVACY_STATUS.upper()}"
        )

        upload_result = upload_video(
            video_path=final_video_path,
            metadata=metadata,
            thumbnail_path=thumbnail_path,
            privacy_status=YOUTUBE_PRIVACY_STATUS
        )

        # -----------------------------------------------------
        # Upload captions (non-fatal; only when an SRT exists).
        # Uses the already-authorized youtube.force-ssl scope.
        # -----------------------------------------------------

        if upload_result.get("video_id") and captions_path:

            upload_captions(
                upload_result["video_id"],
                captions_path,
            )

        else:

            print(
                "ℹ️ No caption track uploaded for this video "
                "(no SRT available)."
            )

        # =====================================================
        # 12. SAVE SUCCESSFUL UPLOAD TO DATABASE
        # =====================================================

        # The assembler picked + persisted the brand SFX variants
        # while building the audio (PRIORITY 1); read the ledger
        # back so the durable record matches what actually
        # shipped.  Never fatal if the ledger is unreadable.
        _sfx_used = {}

        try:
            from app.video.sfx import load_last_sfx

            _sfx_used = load_last_sfx()
        except Exception:
            _sfx_used = {}

        try:

            db.save_record(
                topic=topic_data["topic"],
                category=topic_data.get(
                    "category",
                    "Economy"
                ),
                title=script.title,
                indicator_code=topic_data.get(
                    "indicator_code"
                ),
                story_type=topic_data.get(
                    "story_type"
                ),
                start_year=coerce_year_label(
                    data.columns[0]
                ),
                end_year=coerce_year_label(
                    data.columns[-1]
                ),
                video_path=str(
                    final_video_path
                ),
                youtube_id=upload_result.get(
                    "video_id"
                ),
                upload_status="uploaded",
                voice=chosen_voice,
                title_format=metadata.get(
                    "title_format"
                ),
                hook_style=getattr(
                    script,
                    "hook_style",
                    None
                ),
                ding_variant=_sfx_used.get(
                    "last_ding_variant"
                ),
                chime_variant=_sfx_used.get(
                    "last_chime_variant"
                ),
                # ROTATION OBSERVABILITY (additive).
                # Records which provider and which chart were
                # actually used, so long-term rotation can be
                # audited from the ledger instead of guessed.
                # Both are optional: .get() keeps this safe if
                # the story engine did not supply them.
                provider_id=topic_data.get(
                    "provider_id"
                ),
                chart_type=(
                    topic_data.get("chart_type")
                    or getattr(
                        script,
                        "chart_type",
                        None,
                    )
                )
            )

            print(
                "\n💾 Successful upload "
                "saved to database."
            )

            print(
                f"   YouTube ID: "
                f"{upload_result.get('video_id')}"
            )

            print(
                "   Status: uploaded"
            )

        except Exception as history_error:

            print(
                "\n⚠️ YouTube upload succeeded, "
                "but database save failed:"
            )

            print(
                f"   {history_error}"
            )

        # =====================================================
        # 12B. QUEUE DELAYED PUBLISH (unlisted -> public)
        #
        # The video was just uploaded UNLISTED.  Enqueue a row
        # in publish_queue so publish_worker.py (cron / GitHub
        # Actions) flips it to PUBLIC after
        # DELAYED_PUBLISH_DELAY_MINUTES.  No time.sleep() here:
        # the queue is persistent SQLite state, so the pipeline
        # never stalls and the worker can run on any schedule.
        # =====================================================

        if (
            YOUTUBE_PRIVACY_STATUS == "unlisted"
            and settings.DELAYED_PUBLISH_ENABLED
        ):

            try:

                channel_key = (
                    settings.CHANNEL_NAME or "default"
                )

                publish_at = (
                    datetime.now()
                    + timedelta(
                        minutes=settings.DELAYED_PUBLISH_DELAY_MINUTES
                    )
                )

                was_queued = db.enqueue_delayed_publish(
                    video_id=upload_result.get(
                        "video_id"
                    ),
                    channel=channel_key,
                    publish_at=publish_at
                )

                if was_queued:

                    print(
                        "\n⏳ Video queued for delayed publish:"
                    )

                else:

                    print(
                        "\nℹ️ Video was already queued "
                        "for delayed publish:"
                    )

                print(
                    f"   Video ID: "
                    f"{upload_result.get('video_id')}"
                )

                print(
                    f"   Channel: {channel_key}"
                )

                print(
                    f"   Goes public at: "
                    f"{publish_at.isoformat(timespec='seconds')}"
                )

            except Exception as queue_error:

                print(
                    "\n⚠️ Upload succeeded, but delayed-publish "
                    "queueing failed — the video will stay "
                    "UNLISTED. Enqueue it manually or re-run:"
                )

                print(
                    f"   {queue_error}"
                )

        # =====================================================
        # 13. UPLOAD RESULT
        # =====================================================

        print("\n" + "=" * 60)
        print("🎉 YOUTUBE UPLOAD COMPLETED")
        print("=" * 60)

        print(
            "\n🆔 Video ID:"
        )

        print(
            f"   {upload_result['video_id']}"
        )

        print(
            "\n🔗 YouTube URL:"
        )

        print(
            f"   {upload_result['url']}"
        )

        print(
            "\n🔒 Privacy:"
        )

        print(
            f"   {upload_result['privacy_status']}"
        )

        print(
            "\n📝 Title:"
        )

        print(
            f"   {upload_result['title']}"
        )

        # -----------------------------------------------------
        # Public / private status
        # -----------------------------------------------------

        if upload_result["privacy_status"] == "public":

            print(
                "\n🌎 VIDEO IS PUBLIC."
            )

            print(
                "✅ YouTube publishing completed."
            )

        elif upload_result["privacy_status"] == "unlisted":

            print(
                "\n🔗 VIDEO IS UNLISTED."
            )

            print(
                "⏳ publish_worker.py will flip it to "
                "PUBLIC automatically (see publish_queue)."
            )

        else:

            print(
                "\n🔒 VIDEO IS PRIVATE."
            )

        # =====================================================
        # 13B. AUTO ENGAGEMENT COMMENT (AI-generated)
        #
        # Immediately after a successful upload, ask the SAME
        # Groq client that wrote this video's title/script for
        # ONE punchy question tied to the video's topic and
        # numbers, then post it AS THE CHANNEL via
        # commentThreads.insert (the CHANNEL_BLUEPRINT
        # first-hour ritual).
        #
        # If the LLM step fails, fall back to the rotating
        # template engine so engagement survives a Groq
        # outage.  Every step is guarded: a comment failure
        # can NEVER fail the upload.  The official Data API
        # cannot PIN comments, so Studio pin guidance is
        # printed instead.
        # =====================================================

        if settings.AUTO_PIN_COMMENT:

            print(
                "\n💬 Engagement-comment step "
                "starting (AUTO_PIN_COMMENT="
                "true)..."
            )

            try:

                engagement_text = None

                # -----------------------------------------
                # Step 1: LLM-generated comment (preferred)
                # -----------------------------------------

                try:

                    engagement_text = (
                        generate_engagement_comment(
                            topic_data
                        )
                    )

                    print(
                        "\n🤖 AI engagement comment "
                        "generated:"
                    )

                    print(f"   {engagement_text}")

                except Exception as gen_error:

                    import traceback

                    print(
                        "\n⚠️ AI engagement comment "
                        "failed; using template "
                        "fallback:"
                    )

                    print(
                        f"   {type(gen_error).__name__}: "
                        f"{gen_error}"
                    )

                    traceback.print_exc()

                # -----------------------------------------
                # Step 2: post it (or template fallback)
                # -----------------------------------------

                if engagement_text:

                    comment_result = (
                        post_comment_to_video(
                            video_id=upload_result.get(
                                "video_id"
                            ),
                            comment_text=(
                                engagement_text
                            ),
                        )
                    )

                else:

                    comment_result = (
                        CommentEngine.post_question_comment(
                            video_id=upload_result.get(
                                "video_id"
                            ),
                            topic_data=topic_data,
                        )
                    )

                if not comment_result.get(
                    "posted"
                ):

                    print(
                        f"\n⚠️ Comment not posted: "
                        f"{comment_result.get('note')}"
                    )

            except Exception as comment_error:

                import traceback

                print(
                    "\n⚠️ Comment engine skipped "
                    "(upload unaffected):"
                )

                print(
                    f"   "
                    f"{type(comment_error).__name__}: "
                    f"{comment_error}"
                )

                traceback.print_exc()

        else:

            print(
                "\nℹ️ Auto question-comment disabled "
                "(AUTO_PIN_COMMENT=false)."
            )

        # =====================================================
        # 14. FINAL SUMMARY
        # =====================================================

        print("\n" + "=" * 60)
        print("🎉 COMPLETE PIPELINE FINISHED!")
        print("=" * 60)

        print(
            "\nThe pipeline generated:"
        )

        print("   ✅ Topic")
        print(
            "   ✅ "
            f"{topic_data.get('source_name') or 'Data'} data"
        )
        print("   ✅ Script")
        print("   ✅ Voiceover")
        print("   ✅ Visuals")
        print("   ✅ Final 1080x1920 video")
        print("   ✅ YouTube metadata")
        print("   ✅ Thumbnail candidates")
        print("   ✅ Final QC")
        print("   ✅ YouTube upload")
        print("   ✅ Database history")

        if upload_result.get(
            "thumbnail_uploaded"
        ) is False:

            print(
                "   ℹ️ Shorts cover/thumbnail "
                "handled separately"
            )

        print(
            "\n🎥 Uploaded video:"
        )

        print(
            f"   {upload_result['url']}"
        )

        print(
            "\n📊 Today's upload count:"
        )

        print(
            f"   "
            f"{db.get_today_video_count()}/"
            f"{settings.DAILY_UPLOADS}"
        )

        print(
            "\n🔒 Current privacy:"
        )

        print(
            f"   {upload_result['privacy_status']}"
        )

        if upload_result[
            "privacy_status"
        ] == "public":

            print(
                "\n🌎 The video is PUBLIC."
            )

        else:

            print(
                "\n🔒 The video is not public."
            )

    # =====================================================
    # GLOBAL ERROR HANDLING
    # =====================================================

    except Exception as e:

        print("\n" + "=" * 60)

        print(
            "❌ PIPELINE FAILED"
        )

        print("=" * 60)

        print(
            f"{type(e).__name__}: {e}"
        )

        raise


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    run_test_pipeline()
