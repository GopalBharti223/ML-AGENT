import random

import pandas as pd

from app.config import settings
from app.groq_client import GroqLLM
from app.models import VideoScript
from app.time_labels import coerce_year_label


class ScriptEngine:

    # -----------------------------------------------------
    # CREATIVE ROTATION
    #
    # Same skeleton every video = viewers pattern-match
    # after two Shorts and swipe away. We rotate hook and
    # ending styles per run so uploads never feel templated.
    # -----------------------------------------------------

    HOOK_STYLES = {
        "blunt_question": {
            "brief": (
                "Open with a short punchy question the viewer "
                "needs answered. Max 8 words. AVOID opening "
                "with \"Who's\" / \"Who is\" - that skeleton is "
                "overused; pick a differently-shaped question."
            ),
            "openers": [
                '"Who actually {did / leads} {entity}?" - name '
                "the real actor",
                '"What if {entity} {surprising result}?"',
                '"Why did {entity} just {big shift}?"',
                '"Which {category} actually {surprise}?"',
                '"How did {entity} just {big shift}?" - make '
                "the viewer need the answer",
                '"{entity} or {entity2} - which one really '
                '{leads / wins}?"',
                '"What made {entity} {surprising result}?"',
            ],
        },
        "bold_claim": {
            "brief": (
                "Open with a confident claim the data backs "
                "up, then make the viewer wait for the proof."
            ),
            "openers": [
                '"{entity} just {extreme change} - watch this."',
                '"Nobody expected {surprising result}."',
                '"It is official: {claim the data proves}."',
            ],
        },
        "stakes": {
            "brief": (
                "Open with what is about to change or be lost - "
                "a crown stolen, a record broken. Data only."
            ),
            "openers": [
                '"{entity}\'s {N}-year reign is ending."',
                '"The {crown / record / top spot} just changed '
                "hands.\"",
                '"After {N} years on top, {entity} is slipping '
                "- fast.\"",
            ],
        },
        "time_machine": {
            "brief": (
                "Jump straight to a past year, then tease how "
                "different everything looks now. AVOID "
                "\"Flashback to {YEAR}...\" and the "
                "\"{YEAR}? {fact}, {fact}.\" pattern - both are "
                "overused; use a different time-jump transition."
            ),
            "openers": [
                '"Back in {YEAR}, {surprising fact}."',
                '"Rewind to {YEAR}: {surprising fact}."',
                '"{entity} in {YEAR}: {fact}. Look where they '
                "are now.\"",
                '"Remember {YEAR}? {surprising fact}."',
                '"It is {YEAR}. {surprising fact}. Now watch '
                "what happens next.\"",
                '"{N} years ago, {entity} {past fact}. Today? '
                "{present fact}.\"",
                '"Travel back to {YEAR}: {surprising fact}. '
                "Fast forward to now.\"",
            ],
        },
        "contrarian": {
            "brief": (
                "Open with what everyone assumes, then hint the "
                "data flips it. ONLY if the data truly flips it. "
                "AVOID 'Everyone thinks X...' and 'Forget what "
                "you have heard' - prefer fresh skeletons."
            ),
            "openers": [
                (
                    "You probably think {X} is the story - "
                    "here's the real shift the numbers show."
                ),
                (
                    "Wait - before you assume {X}, the data "
                    "says {surprising result}"
                ),
                (
                    "{X}? Check the year first. {reframed take} "
                    "is what the data actually proves."
                ),
                (
                    "The popular take on {X} is wrong - the data "
                    "tells a different story entirely."
                ),
                (
                    "Everyone repeat this {X} talking point. "
                    "The numbers have moved on without them."
                ),
            ],
        },
    }

    ENDING_STYLES = {
        "number_punch":
            "End on the raw number swing, delivered with "
            "attitude. No moral of the story.",
        "cliffhanger":
            "End on an unanswered follow-up question that "
            "begs people to argue in the comments.",
        "verdict":
            "End on a one-line verdict about who really won.",
        "full_circle":
            "End by contrasting the final value with the "
            "first-year value in one breath.",
        "debate_starter":
            "End by inviting disagreement - ask if the data "
            "got it right.",
        "seamless_loop":
            "End on a fast unfinished bridge line that flows seamlessly "
            "right back into the video's opening hook, creating an infinite retention loop.",
    }

    # ---------------------------------------------------------
    # Per-indicator honesty framing constraints (Tier-2c).
    #
    # Some datasets structurally CANNOT support absolute claims.
    # For those, the exact constraint text here is injected
    # verbatim into the title/script prompt (a single LLM call
    # produces both).  Keyed by indicator code so the manual and
    # automatic topic paths are covered identically.
    # ---------------------------------------------------------

    FRAMING_CONSTRAINTS = {

        # World Bank external debt (International Debt
        # Statistics): only nations that REPORT debt to the WB
        # appear in the data; high-income non-reporters (US,
        # Japan, Germany, UK, France...) are absent, so "the
        # world's most indebted country" would be a false claim.
        "DT.DOD.DECT.CD":
            "COVERAGE LIMIT: this dataset contains ONLY nations "
            "that report external debt to the World Bank - "
            "mostly emerging and developing economies. The US, "
            "Japan, Germany, the UK and France are ABSENT from "
            "the data. NEVER call any country 'the world's most "
            "indebted' or claim the ranking covers the whole "
            "world. ALWAYS scope every ranking claim - narration "
            "AND title - with wording like 'among reporting "
            "nations', 'among emerging economies' or 'of the "
            "nations that report external debt to the World "
            "Bank'. A title that makes NO ranking claim (e.g. a "
            "single country's growth story) may omit the scoping "
            "phrase, but any superlative ranking in a title must "
            "carry it.",

        # Transparency International's Corruption Perceptions
        # Index (via OWID): survey-based PERCEPTION measure.
        "corruption_perceptions_index":
            "PERCEPTION INDEX: these values are Transparency "
            "International's Corruption Perceptions Index scores "
            "(0-100) - a survey-based perception measure, NOT an "
            "objective measurement of corruption. ALWAYS name it "
            "'Corruption Perceptions Index score' and credit "
            "Transparency International ('CPI score' is an "
            "acceptable shorthand after the first mention). "
            "NEVER write that a "
            "country 'is the most corrupt' or 'is the cleanest' "
            "- write that it 'has the lowest/highest CPI score'. "
            "Stay strictly descriptive: ranks, scores and years "
            "only. NO commentary about specific governments, no "
            "accusations, no editorializing.",

        # EM-DAT natural-disaster deaths (via OWID): RECORDED
        # deaths.  Older decades are significantly underreported,
        # so cross-era comparisons are NOT apples-to-apples.
        "deaths_floods":
            "RECORDED DEATHS (EM-DAT): these are deaths RECORDED "
            "in the EM-DAT international disaster database, as "
            "mirrored by Our World in Data. Recording is FAR "
            "better in recent decades - older decades have major "
            "underreporting. NEVER call a country 'the most "
            "disaster-prone' or compare decades as if equally "
            "recorded. ALWAYS say 'recorded deaths' or 'as "
            "catalogued by EM-DAT', and scope time comparisons "
            "to recent decades. A blank/zero year means nothing "
            "was RECORDED - not that nobody died.",

        "deaths_all_disasters":
            "RECORDED DEATHS (EM-DAT): these are deaths RECORDED "
            "in the EM-DAT international disaster database (all "
            "natural-disaster types combined: droughts, "
            "earthquakes, floods, landslides, storms, wildfires, "
            "extreme temperatures), as mirrored by Our World in "
            "Data. Recording is FAR better in recent decades - "
            "older decades have major underreporting. NEVER call "
            "a country 'the most disaster-prone' or compare "
            "decades as if equally recorded. ALWAYS say "
            "'recorded deaths' or 'as catalogued by EM-DAT', and "
            "scope time comparisons to recent decades. A "
            "blank/zero year means nothing was RECORDED - not "
            "that nobody died.",

        # IUCN Red List Index (via OWID): DIRECTION of national
        # extinction risk, NOT a species count.
        "red_list_index":
            "RED LIST INDEX (IUCN): this measures the DIRECTION "
            "of national extinction risk over time - an index "
            "from 0 to 1 where 1.0 means no species are moving "
            "toward extinction and FALLING values mean extinction "
            "risk is worsening. It is NOT a species count or "
            "population number. NEVER claim a country 'has the "
            "most endangered species' or cite any 'number of "
            "species' - that data does not exist here. Frame ONLY "
            "as a risk trend: 'extinction risk rising fastest', "
            "'the few countries reversing species decline', "
            "'falling/rising Red List Index value'.",

        # USGS earthquakes: magnitude-threshold counts with
        # region-biased detection coverage; offshore quakes are
        # attributed to the nearest coastline country.
        "earthquake_count_m6":
            "MAGNITUDE-6+ EARTHQUAKES (USGS): counts include ONLY "
            "earthquakes of magnitude 6.0 and above, because "
            "smaller quakes are detected unevenly across regions "
            "(dense seismic networks in Japan/US vs sparse ocean "
            "monitoring) - so raw counts are NOT a fair 'most "
            "earthquake-prone country' measure. Offshore quakes "
            "are attributed to the nearest coastline country "
            "(some to 'International waters'), so a count can "
            "include quakes that struck no populated land. "
            "ALWAYS scope claims: 'magnitude-6+ earthquakes "
            "recorded by USGS', never 'the world's most "
            "earthquake-prone country'.",

        "earthquake_max_magnitude":
            "EARTHQUAKE MAGNITUDES (USGS): these are the strongest "
            "magnitude-6+ earthquakes RECORDED by USGS per "
            "country-year. Instrumental recording only reaches "
            "back reliably a few decades, and detection coverage "
            "is uneven across regions. Offshore quakes are "
            "attributed to the nearest coastline country (some to "
            "'International waters'). ALWAYS say 'recorded by "
            "USGS' and scope any 'strongest ever' claim to the "
            "instrumental record - never 'the strongest in "
            "history' without that caveat.",

        # Wikipedia pageviews entity comparisons (Netflix, Tesla, etc.):
        # search-popularity metric, NOT sales/revenue/subscribers.
        "search_interest":
            "SEARCH INTEREST (Wikipedia pageviews): these numbers "
            "are monthly Wikipedia article pageviews - a rough "
            "proxy for public curiosity, NOT sales, revenue, "
            "subscribers or viewership. A high pageview count "
            "can reflect controversy, breaking-news spikes, or "
            "seasonal interest as often as genuine popularity. "
            "NEVER claim a company is bigger than, beats, "
            "outsells or earns more than on the basis of these "
            "numbers, and NEVER compare them to financial "
            "metrics. ALWAYS frame as Wikipedia search interest "
            "or pageviews, and note that spikes can be "
            "news-driven rather than popularity-driven.",
    }

    @staticmethod
    def _pick_rotation(styles: dict) -> tuple:
        """Randomly pick one entry from a style catalog.

        Tracks recently used names (class-level _rotation_history)
        so the same style is not picked in consecutive runs -- this
        is what actually makes the skeletons vary in practice.
        """

        available = list(styles.keys())

        recent = (
            getattr(ScriptEngine, "_rotation_history", [])
            or []
        )

        # Bias away from the most recently picked styles.
        candidates = [
            name for name in available
            if name not in recent[:2]
        ]
        if not candidates:
            candidates = available

        name = random.choice(candidates)

        # Update history (module-level so it persists across calls
        # within the same process / test run).
        history = getattr(
            ScriptEngine, "_rotation_history", []
        )
        history.append(name)
        ScriptEngine._rotation_history = history[-8:]

        return name, styles[name]

    @staticmethod
    def _format_style_brief(
        style_name,
        style_value
    ) -> str:
        """Expand a style entry into a prompt block.

        Style entries may be plain strings (coming styles) or
        dicts with a `brief` and an `openers` skeleton list
        (hook styles).  The skeleton list forces the model to
        VARY the opening sentence instead of recycling a single
        template ("Who's [verb]-ing...", "YEAR? fact, fact.",
        "Everyone assumes... Wrong") across every video.
        """

        if isinstance(style_value, str):

            return style_value

        if isinstance(style_value, dict):

            brief = str(
                style_value.get("brief", "") or ""
            ).strip()

            openers = style_value.get("openers") or []

            # Per-run rotation: offer only a random subset of the
            # skeletons so the model cannot lock onto ONE favorite
            # (e.g. always "Travel back to {YEAR}") when the full
            # list is visible every single run.
            if len(openers) > 3:

                openers = random.sample(openers, 3)

            lines = [brief]

            if openers:

                lines.append(
                    "Opening skeletons for THIS run - pick ONE and "
                    "vary the wording; never recycle the same "
                    "opener in consecutive videos:"
                )

                for opener in openers:

                    lines.append(f"- {opener}")

            return "\n".join(lines)

        return str(style_value)

    @staticmethod
    def _get_ranking_snapshot(
        data: pd.DataFrame,
        year: int,
        limit: int = 5
    ) -> list:

        if year not in data.columns:
            return []

        ranking = (
            data[year]
            .dropna()
            .sort_values(
                ascending=False
            )
            .head(limit)
        )

        result = []

        for rank, (
            country,
            value
        ) in enumerate(
            ranking.items(),
            start=1
        ):

            result.append(
                {
                    "rank": rank,
                    "country": str(country),
                    "value": float(value)
                }
            )

        return result

    @staticmethod
    def _build_data_context(
        data: pd.DataFrame
    ) -> dict:

        years = list(
            data.columns
        )

        first_key = years[0]
        middle_key = years[
            len(years) // 2
        ]
        last_key = years[-1]

        def _display_year(key):
            """Season-label safe prompt label.

            Column labels are coerced to numeric years
            ("2024-25" -> 2024) so season labels never leak
            raw into the LLM prompt; unparseable labels fall
            back to their string form.
            """
            coerced = coerce_year_label(key)
            return (
                coerced
                if coerced is not None
                else str(key)
            )

        context = {
            "first_year": {
                "year": _display_year(first_key),
                "ranking": (
                    ScriptEngine
                    ._get_ranking_snapshot(
                        data,
                        first_key
                    )
                )
            },

            "middle_year": {
                "year": _display_year(middle_key),
                "ranking": (
                    ScriptEngine
                    ._get_ranking_snapshot(
                        data,
                        middle_key
                    )
                )
            },

            "last_year": {
                "year": _display_year(last_key),
                "ranking": (
                    ScriptEngine
                    ._get_ranking_snapshot(
                        data,
                        last_key
                    )
                )
            }
        }

        # Ground-truth mathematical endpoints & deltas (Phase 1 math integrity)
        from app.ai.math_integrity import MathIntegrityEngine
        ground_truth = MathIntegrityEngine.compute_ground_truth(data)
        verified_changes = {}
        for ent, gt in ground_truth.items():
            if gt.has_sufficient_data:
                pct_str = (
                    f"{gt.pct_change:+.1f}%"
                    if gt.pct_change is not None
                    else "N/A (zero baseline)"
                )
                verified_changes[ent] = {
                    "start": round(gt.start_val, 2),
                    "end": round(gt.end_val, 2),
                    "absolute_change": round(gt.abs_change, 2),
                    "percentage_change": pct_str,
                    "direction": gt.direction,
                }

        context["verified_changes"] = verified_changes
        return context

    @staticmethod
    def _build_story_context(
        topic_data: dict
    ) -> dict:

        metrics = topic_data.get(
            "story_metrics",
            {}
        )

        allowed_keys = [
            "entity",
            "leader",
            "challenger",
            "start_year",
            "end_year",
            "start_value",
            "end_value",
            "absolute_change",
            "percentage_change",
            "start_rank",
            "end_rank",
            "rank_change",
            "number_of_valid_countries",
            "number_of_valid_years",
            "meaningful_observations",
            "data_completeness",
            "leader_separation",
            "trend_strength",
            "quality_score",
            "diversity_penalty",
            "topic_family",
            "selected_chart_type",
        ]

        return {
            key: metrics.get(key)
            for key in allowed_keys
            if key in metrics
        }

    @staticmethod
    def _normalize_important_value(value):
        """Reduce a scene's important_value to ONE number or None.

        The schema requires a single float, but the LLM sometimes
        emits a dict of country->value pairs, a list, or prose on
        multi-country topics.  This collapses ANY shape to the
        single numeric value that best fits the field's downstream
        use (scene visual emphasis):

          - dict      -> the MAX numeric value among its values
                         (the winner / highlighted figure)
          - list/tuple -> the MAX numeric element
          - str       -> the first embedded number ("Bhutan 6783"->6783)
          - int/float -> passed through as float
          - everything else / no parseable number -> None

        Returns a float (or None).  Logs a warning when it had to
        collapse a non-scalar shape so bad generations stay visible.
        """

        # Real numbers pass straight through (as float).
        if isinstance(value, bool):
            result = None

        elif isinstance(value, (int, float)):
            result = float(value)

        # dict of country->value pairs -> max numeric value.
        elif isinstance(value, dict):

            numbers = [
                ScriptEngine._to_float(v)
                for v in value.values()
            ]

            numbers = [
                n for n in numbers
                if n is not None
            ]

            result = (
                max(numbers)
                if numbers else None
            )

            if result is not None:
                print(
                    "⚠️ important_value was a dict "
                    f"({value}); collapsed to MAX "
                    f"value {result}."
                )

        # list/tuple -> max numeric element.
        elif isinstance(value, (list, tuple)):
            numbers = [
                ScriptEngine._to_float(v)
                for v in value
            ]

            numbers = [
                n for n in numbers
                if n is not None
            ]

            result = (
                max(numbers)
                if numbers else None
            )

            if result is not None:
                print(
                    "⚠️ important_value was a list "
                    f"({value}); collapsed to MAX "
                    f"value {result}."
                )

        # str -> first embedded number.
        elif isinstance(value, str):
            result = ScriptEngine._first_number(value)

        else:
            result = None

        return result

    # -----------------------------------------------------
    # INDICATOR-SPECIFIC TITLE POLISH (Tier-2d)
    #
    # Some indicators (CPI especially) have a rendering contract
    # that the title MUST name the index explicitly (e.g. "CPI")
    # or "Corruption Perceptions Index").  The LLM is instructed
    # to do this, but as a safety net we post-process here so a
    # one-off bad title never reaches the viewer.
    # -----------------------------------------------------

    @staticmethod
    def _polish_title_for_indicator(
        title: str,
        indicator_name: str,
    ) -> str:
        """Ensure indicator-required keywords are present in title."""
        t = title or ""
        low = t.lower()

        # Corruption Perceptions Index: title must carry "CPI" or
        # "corruption perceptions index" so viewers know this is a
        # perception SCORE, not an objective corruption measurement.
        # Match BOTH the indicator code (underscored) and the friendly
        # name (spaced) since callers may pass either.
        ind_low = indicator_name.lower()
        is_cpi = (
            "corruption_perceptions_index" in ind_low
            or "corruption perceptions index" in ind_low
        )
        if is_cpi:
            if "cpi" not in low and "corruption perceptions index" not in low:
                # Insert the CPI name without rewriting the whole title.
                if t and not t.endswith("?"):
                    return f"{t} (CPI)"
                return f"CPI: {t}"

        return t

    # -----------------------------------------------------
    # HONEST-FRAMING ENFORCEMENT (Tier-2c hard backstop)
    #
    # The FRAMING_CONSTRAINTS text is injected into the LLM
    # prompt, but the LLM can (and live-verification showed it
    # DOES) omit the honest framing from the narration.  For the
    # honesty-labeled indicators the framing is a hard content
    # contract, so this backstop deterministically appends the
    # required disclosure sentence to the closing scene whenever
    # the corpus (title + all narrations) lacks it.
    # -----------------------------------------------------

    FRAMING_BACKSTOP = {
        # EM-DAT recorded deaths: recorded-vs-real + era
        # comparability disclosure.
        "deaths_floods": (
            "All figures are recorded deaths catalogued by "
            "EM-DAT - older decades are underreported, so "
            "cross-era comparisons are not exact."
        ),
        "deaths_all_disasters": (
            "All figures are recorded deaths catalogued by "
            "EM-DAT - older decades are underreported, so "
            "cross-era comparisons are not exact."
        ),
        # Red List Index: direction of risk, NOT species counts.
        "red_list_index": (
            "This is the Red List Index - it tracks the "
            "direction of extinction risk over time, not the "
            "number of endangered species."
        ),
        # USGS earthquakes: magnitude threshold + offshore
        # attribution disclosure.
        "earthquake_count_m6": (
            "Counts include only magnitude-6+ earthquakes "
            "recorded by USGS; offshore quakes are attributed "
            "to the nearest coastline country."
        ),
        "earthquake_max_magnitude": (
            "Magnitudes are USGS-recorded events; offshore "
            "quakes are attributed to the nearest coastline "
            "country."
        ),
        # Wikipedia pageviews entity comparisons (Netflix, Tesla,
        # streaming services): search-popularity metric, NOT
        # sales/revenue/subscribers.
        "search_interest": (
            "These are Wikipedia article pageviews - a proxy "
            "for search interest, not sales or revenue. "
            "Spikes can be news-driven, not popularity-driven."
        ),
    }

    @staticmethod
    def _enforce_honest_framing(
        script,
        indicator_name: str,
    ) -> bool:
        """
        Deterministically guarantee the honest-framing disclosure
        for honesty-labeled indicators.  Returns True when the
        backstop appended a disclosure sentence.

        Matched on BOTH the indicator code (underscored) and the
        friendly name (spaced), mirroring the Tier-2d matcher.
        """
        ind_low = str(indicator_name or "").lower()

        suffix = None

        for key, sentence in (
            ScriptEngine.FRAMING_BACKSTOP.items()
        ):
            if (
                key in ind_low
                or key.replace("_", " ") in ind_low
            ):
                suffix = sentence
                break

        if suffix is None:
            return False

        corpus_parts = [str(script.title or "")]

        for scene in script.scenes:
            corpus_parts.append(
                str(getattr(scene, "narration", "") or "")
            )

        corpus = " ".join(
            part.lower() for part in corpus_parts
        )

        # Already framed?  Check a stable keyword from the
        # disclosure sentence rather than the whole sentence.
        anchor = {
            "deaths_floods": "em-dat",
            "deaths_all_disasters": "em-dat",
            "red_list_index": "direction of extinction risk",
            "earthquake_count_m6": "magnitude-6+",
            "earthquake_max_magnitude": "usgs",
        }
        # Re-derive the key that matched to pick the right anchor.
        matched_key = None
        for key in ScriptEngine.FRAMING_BACKSTOP:
            if (
                key in ind_low
                or key.replace("_", " ") in ind_low
            ):
                matched_key = key
                break

        anchor_text = anchor.get(matched_key, "")

        if anchor_text and anchor_text in corpus:
            return False

        # Append the disclosure to the LAST scene so the video
        # ends with the honesty note (viewer hears it last).
        last_scene = script.scenes[-1]

        current = str(
            getattr(last_scene, "narration", "") or ""
        ).rstrip()

        if current and current.endswith((".", "!", "?")):
            last_scene.narration = f"{current} {suffix}"
        else:
            last_scene.narration = f"{current} {suffix}".lstrip()

        print(
            "🛡️ Honest-framing backstop appended "
            f"({matched_key})."
        )

        return True

    @staticmethod
    def _to_float(value):
        """Best-effort float coercion; None when not a number."""

        if isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            return ScriptEngine._first_number(value)

        return None

    @staticmethod
    def _first_number(value):
        """First number embedded in a string, else None."""

        import re as _re

        match = _re.search(
            r"-?\d+(?:\.\d+)?",
            str(value).replace(",", ""),
        )

        return (
            float(match.group())
            if match else None
        )

    @staticmethod
    def _is_sensitive_topic(topic_data: dict, indicator_name: str) -> bool:
        """Detect if topic involves tragedy, mortality, disease, disaster, poverty, or crisis."""
        text = " ".join([
            str(topic_data.get("topic", "")),
            str(topic_data.get("indicator_code", "")),
            str(topic_data.get("category", "")),
            str(indicator_name or "")
        ]).lower()

        sensitive_keywords = [
            "death", "mortality", "disaster", "flood", "earthquake",
            "casualt", "disease", "poverty", "famine", "hunger",
            "extinct", "suicide", "crime", "homicide", "kill",
            "crisis", "malnutrition", "epidemic", "pandemic",
            "conflict", "war", "refugee", "displace"
        ]
        return any(kw in text for kw in sensitive_keywords)

    @staticmethod
    def _sanitize_sensitive_script(script, is_sensitive: bool) -> None:
        """Strip tone-deaf sports and gaming metaphors from serious topic scripts."""
        if not is_sensitive or not getattr(script, "scenes", None):
            return

        import re
        forbidden_replacements = [
            (r"\bwinner\b", "highest-ranked"),
            (r"\bwinners\b", "most affected"),
            (r"\bwon the race\b", "recorded the highest rate"),
            (r"\bwon\b", "surpassed"),
            (r"\bchampion\b", "top country"),
            (r"\btook the crown\b", "rose to the top"),
            (r"\btake the crown\b", "rise to the top"),
            (r"\bcrushed\b", "exceeded"),
            (r"\bloser\b", "lowest-ranked"),
            (r"\blosers\b", "least affected"),
            (r"\bthe race\b", "the trend"),
        ]

        for scene in script.scenes:
            narration = getattr(scene, "narration", "")
            if not narration:
                continue
            text = str(narration)
            for pattern, repl in forbidden_replacements:
                text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
            scene.narration = text

    @staticmethod
    def generate_script(
        topic_data: dict,
        data: pd.DataFrame,
        indicator_name: str
    ) -> VideoScript:

        # Ensure data.index is normalized to canonical names (e.g. 'India' rather than ('IND', 'India'))
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
                        import re as _re_inline
                        _m = _re_inline.match(r"^\(\s*['\"]?([^'\",]+)['\"]?\s*,\s*['\"]?([^'\"]+)['\"]?\s*\)$", _raw)
                        if _m:
                            _raw = _m.group(2).strip()
                    _norm_index.append(_raw)
            if _norm_index != list(data.index):
                data = data.copy()
                data.index = _norm_index

        chart_type = topic_data.get(
            "chart_type",
            "bar_race"
        )

        source_name = topic_data.get(
            "source_name",
            "World Bank"
        )

        source_url = topic_data.get(
            "source_url",
            "https://data.worldbank.org"
        )

        data_context = (
            ScriptEngine
            ._build_data_context(data)
        )

        story_context = (
            ScriptEngine
            ._build_story_context(
                topic_data
            )
        )

        # -------------------------------------------------
        # Honest-framing constraints (Tier-2c): when the
        # indicator has a known coverage limit, inject it
        # verbatim so the LLM cannot make absolute claims
        # the data cannot support (title AND narration).
        # -------------------------------------------------

        framing_section = ""

        constraint = ScriptEngine.FRAMING_CONSTRAINTS.get(
            str(topic_data.get("indicator_code", ""))
        )

        if constraint:

            framing_section = (
                "TOPIC FRAMING CONSTRAINTS (MUST FOLLOW - "
                "these override creative style):\n\n"
                f"{constraint}\n\n"
            )

        is_sensitive = ScriptEngine._is_sensitive_topic(
            topic_data,
            indicator_name
        )

        if is_sensitive:
            framing_section += (
                "TONAL SAFETY INSTRUCTION (CRITICAL - SERIOUS REAL-WORLD TOPIC):\n"
                "This topic touches mortality, natural disaster, disease, human suffering, or crisis.\n"
                "- NEVER use competitive sports, race, or arcade gaming terminology (\"winner\", \"won\", "
                "\"loser\", \"champion\", \"crown\", \"crushed\", \"beat out\", \"reign\", \"dominated\").\n"
                "- Adopt a serious, investigative, and respectful tone. Treat the data with human dignity.\n"
                "- Focus on the severity, human scale, and real-world causes of the shift.\n\n"
            )

        # -------------------------------------------------
        # Rotate today's creative brief so two runs never
        # produce the same-shaped video.
        # -------------------------------------------------

        hook_name, hook_style = (
            ScriptEngine._pick_rotation(
                ScriptEngine.HOOK_STYLES
            )
        )

        hook_brief = (
            ScriptEngine._format_style_brief(
                hook_name,
                hook_style,
            )
        )

        ending_name, ending_brief = (
            ScriptEngine._pick_rotation(
                ScriptEngine.ENDING_STYLES
            )
        )

        if is_sensitive and ending_name == "verdict":
            ending_brief = (
                "End on a sobering one-line takeaway on what this trajectory means for "
                "the affected populations and regional stability. Do NOT declare a 'winner'."
            )

        print(
            f"🎨 Style rotation: "
            f"hook={hook_name}, "
            f"ending={ending_name}"
            f"{' [SERIOUS/TONAL SAFETY ACTIVE]' if is_sensitive else ''}"
        )

        # -----------------------------------------------------
        # TARGET DURATION BAND (18-30s, entity-count aware)
        #
        # A single fixed TARGET_DURATION never matched the render:
        # the measured TTS narration became the timeline and blew
        # straight past it (a "18s" script rendered at 49s).  The
        # target is now a per-video band:
        #   1-2 entities -> ~20s (18-22s), simple head-to-head
        #   3 entities   -> ~24s (22-26s)
        #   4+ entities  -> ~28s (26-30s), ranked/multi-entity
        # The fixed TARGET_DURATION env value is only a fallback
        # when the entity count is unknown, clamped into the band.
        # -----------------------------------------------------

        try:
            entity_count = len(
                set(
                    str(name) for name in data.index
                )
            ) if hasattr(data, "index") else 0

        except Exception:
            entity_count = 0

        target_duration = (
            ScriptEngine
            ._duration_band_for_entities(
                entity_count
            )
        )

        if getattr(settings, "is_landscape", False):
            max_words = max(50, int((target_duration - 5.0) * 2.1))
            format_intro = f"Write an epic, high-stakes {target_duration}-second cinematic YouTube widescreen video script"
        else:
            max_words = max(25, int((target_duration - 3.0) * 2.5))
            format_intro = f"Write a {target_duration}-second YouTube Shorts script"

        prompt = f"""
{format_intro} that
sounds like a sharp, fast-talking friend who cannot
believe what the data just showed them.

NOT a documentary narrator. Not Wikipedia. A human.

TOPIC:
{topic_data.get('topic', 'Data comparison')}

INDICATOR:
{indicator_name}

CHART TYPE:
{chart_type}

PROVIDER:
{topic_data.get('provider_id', 'worldbank')}

SOURCE:
{source_name}
{source_url}

STORY TYPE:
{topic_data.get('story_type', 'fastest_growth')}

SELECTED STORY DETAILS:
{story_context}

TODAY'S CREATIVE BRIEF (rotates every run):

HOOK STYLE -> {hook_name}
{hook_brief}

ENDING STYLE -> {ending_name}
{ending_brief}

DATA:

{data_context}

IMPORTANT FACT RULES:

1. Never invent countries.
2. Never invent rankings.
3. Never invent numbers.
4. Only mention rankings supported by the data.
5. If describing a rise/fall, it must be visible
   from the supplied historical data.
6. Do not claim a country became #1 unless
   the data supports it.
7. Any numerical claim must match the supplied
   DATA or SELECTED STORY DETAILS exactly.
8. "important_value" must ALWAYS be a single
   plain number (a float or int) -- NEVER an
   object/dictionary of country-value pairs,
   NEVER a list, NEVER a string with words.
   Even when a scene discusses MULTIPLE
   countries, important_value reports the ONE
   number this scene is highlighting (usually
   the winner's / leader's value, or the exact
   value the narration calls out for that
   scene). If no single number fits, use null.

{framing_section}VOICE - HOW IT MUST SOUND:

- Contractions ALWAYS: it's, they're, didn't, wasn't.
- Talk TO the viewer at least once ("you", "your").
- Vary rhythm: mix a 3-word punch with a longer line.
- Sound excited or skeptical where the data is wild.
- Write numbers as digits (204, 395.5) so TTS
  reads them cleanly.
- NEVER use these dead giveaways:
  "Today we", "In this video", "let's dive",
  "buckle up", "delve", "This Short visualizes",
  "data-driven insights", "game-changer",
  textbook phrasing like "sat fourth with".

Compare:

BAD:  "In 2016 Max Verstappen sat fourth with 204 points."
GOOD: "2016? Verstappen was stuck in fourth. Just 204 points."

SCRIPT REQUIREMENTS:

- Exactly 4 or 5 scenes.
- Total duration = {target_duration} seconds.
- AT MOST {max_words} narration words TOTAL.  This script must
  be SPOKEN in {target_duration} seconds: a spoken number
  ("204", "395.5") costs ~3 words, so every numeric token
  counts TRIPLE against the budget.  Fewer, denser lines win.
- Scene 1 IS the hook ({hook_name}) - no warm-up.
- HOOK MUST SCROLL-STOP: scene 1's narration needs at
  least one concrete NUMBER from the data OR one specific
  named entity (a country, company, driver, team...).
  NEVER open with an abstract, entity-less question like
  "Who's leading X right now?" - pure abstraction gives a
  viewer no reason to stop.
- Anchor the hook in the story's actual direction (rise,
  fall, overtake) using the STORY TYPE above.
- Never start a script with the same opening words as the
  examples (do not literally copy a skeleton).  In
  particular, avoid repeating "Everyone thinks X..." -
  vary the wording each run.
- SEAMLESS VIRAL LOOP: End the script on a high-energy cliffhanger or bridge sentence that connects seamlessly into the opening hook of Scene 1. Do NOT say goodbye, do NOT say subscribe, and do NOT wrap up with generic broadcast conclusions.
- HIGH-STAKES STORYTELLING: Treat the data as a high-stakes competition or historic geopolitical battle. Make the gap between #1 and competitors feel thrilling and emotionally charged.
- Short punchy sentences.
- CAUSAL DEPTH (The 'Why'): At least one middle scene (Scene 2 or 3) MUST give a concrete causal reason WHY the numbers shifted (e.g. policy reform, economic crash, war, technology boom, infrastructure investment). Do NOT just list number after number; explain what caused the shift so viewers stay invested.
- Prefer a curiosity-gap title (Who/What/Which/Why)
  so viewers stay to find the answer - but vary the
  wording, never recycle earlier title patterns.
- Only use a statement title when no question fits.
- Keep the title faithful to the selected story.
- Each scene must have:
  narration
  visual_description
  text_overlay
- Each scene should also include structured visual
  planning fields when useful:
  scene_purpose, visual_emphasis,
  highlight_countries, important_year,
  important_value, pacing_hint
- pacing_hint options: fast reveal / steady /
  quick rise / tight finish / dramatic.

important_value FORMAT (critical):

"important_value" must be JUST a number -- a single
positional numeric value for the scene:

CORRECT:
  "important_value": 6783

CORRECT (multi-country scene, reporting the one
highlighted winner's value):
  "important_value": 55943

INCORRECT (never do this - an object of
country->value pairs):
  "important_value": {{"Bhutan": 6783,
  "Falkland Islands": 55943}}

INCORRECT (never a list):
  "important_value": [6783, 55943]

INCORRECT (never a string with words):
  "important_value": "Bhutan 6783"

VISUAL DESCRIPTION:

Describe what the selected animated chart should
be doing during the scene.
Tie each visual description to the selected story.
Use scene purposes like HOOK, RANKING, OVERTAKE,
HIGHLIGHT, ENDING when they fit.
Do not describe visual elements unsupported by
the selected chart type.

TEXT OVERLAY:

Keep it SHORT.
Prefer 1-5 words.
It must fit on a vertical 1080x1920 Shorts screen.

Return ONLY JSON:

{{
    "title": "short engaging title",
    "topic": "{topic_data.get('topic', 'Data comparison')}",
    "category": "{topic_data.get('category', 'General')}",
    "indicator_name": "{indicator_name}",
    "chart_type": "{chart_type}",
    "total_duration": {target_duration},
    "scenes": [
        {{
            "scene_number": 1,
            "duration": 5.0,
            "narration": "string",
            "visual_description": "string",
            "text_overlay": "string",
            "chart_type": "{chart_type}",
            "scene_purpose": "HOOK",
            "visual_emphasis": "central question",
            "highlight_countries": [],
            "important_year": null,
            "important_value": null,
            "pacing_hint": "fast reveal"
        }}
    ],
    "fact_check": {{
        "is_accurate": true,
        "discrepancies": "none"
    }},
    "source_name": "{source_name}",
    "source_url": "{source_url}"
}}
"""

        # -----------------------------------------------------
        # GENERATE
        # -----------------------------------------------------

        raw_script = (
            GroqLLM.generate_structured(
                prompt,
                temperature=0.85
            )
        )

        # -----------------------------------------------------
        # DEFENSIVE SCHEMA NORMALIZATION (safety net)
        #
        # The model occasionally violates the schema by
        # stuffing prose OR country-value objects into the
        # numeric important_value field (e.g.
        #   {"Bhutan": 6783, "Falkland Islands": 55943})
        # which hard-fails pydantic and would kill the whole
        # run.  Normalize it to ONE number BEFORE the model is
        # constructed. This runs ahead of VideoScript(...) and
        # AHEAD of the fact-check step, so it never disturbs
        # the existing self fact-check flow below.
        # -----------------------------------------------------

        for _scene in raw_script.get(
            "scenes", []
        ):

            # important_value: collapse dict/list/string/all
            # forms to a single float.
            _important = _scene.get(
                "important_value"
            )

            _scene["important_value"] = (
                ScriptEngine
                ._normalize_important_value(
                    _important
                )
            )

            # important_year: keep a plain int or repair a
            # malformed string.
            _year = _scene.get(
                "important_year"
            )

            if isinstance(_year, str):

                import re as _re

                _match = _re.search(
                    r"-?\d+",
                    str(_year).replace(",", ""),
                )

                _scene["important_year"] = (
                    int(_match.group())
                    if _match else None
                )

        # -----------------------------------------------------
        # HOOK_STYLE CAPTURE (retention feedback loop)
        #
        # The style chosen at prompt-build time (hook_name,
        # script.py ~511) is stored on the script model so it
        # flows into script.json AND into video_history via
        # run.py's save_record, giving the analytics collector
        # a per-video style axis to correlate performance
        # against.  Historical rows are NOT backfilled.
        # -----------------------------------------------------

        raw_script["hook_style"] = hook_name

        script = VideoScript(
            **raw_script
        )

        # INDICATOR-SPECIFIC TITLE POLISH (Tier-2d).
        script.title = ScriptEngine._polish_title_for_indicator(
            script.title or "",
            indicator_name,
        )

        # -----------------------------------------------------------
        # HONEST-FRAMING BACKSTOP (Tier-3b)
        # Deterministically guarantee the disclosure sentence is
        # present in the LAST scene's narration for honesty-labeled
        # indicators (EM-DAT deaths, Red List Index, USGS quakes).
        # Injected AFTER title polish so the word-count report below
        # stays accurate.  Matched on the indicator CODE (the keys of
        # FRAMING_BACKSTOP are codes like 'deaths_floods'), NOT the
        # friendly name, because the friendly name never contains the
        # underscored code as a substring.
        # -----------------------------------------------------------
        ScriptEngine._enforce_honest_framing(
            script,
            topic_data.get(
                "indicator_code",
                "",
            ),
        )

        # -----------------------------------------------------------
        # TONAL SAFETY SANITIZATION (Serious / Sensitive Topics)
        # Strips tone-deaf sports and arcade terminology from tragedies.
        # -----------------------------------------------------------
        ScriptEngine._sanitize_sensitive_script(
            script,
            is_sensitive
        )



        # -----------------------------------------------------
        # FORCE TOTAL DURATION
        # (target_duration was resolved from settings above)
        # -----------------------------------------------------

        total_scene_duration = sum(
            scene.duration
            for scene in script.scenes
        )

        if total_scene_duration <= 0:

            raise ValueError(
                "Generated scene durations "
                "are invalid."
            )

        # Scale scene durations so that they add
        # up EXACTLY to the target duration.
        scale = (
            target_duration
            / total_scene_duration
        )

        for scene in script.scenes:

            scene.duration = round(
                scene.duration * scale,
                2
            )

        # Fix rounding difference.
        difference = round(
            target_duration
            - sum(
                scene.duration
                for scene in script.scenes
            ),
            2
        )

        script.scenes[-1].duration += (
            difference
        )

        script.total_duration = (
            target_duration
        )

        # -----------------------------------------------------
        # WORD COUNT
        # -----------------------------------------------------

        narration = " ".join(
            scene.narration
            for scene in script.scenes
        )

        word_count = len(
            narration.split()
        )

        print(
            f"📝 Script word count: "
            f"{word_count} "
            f"(budget for {target_duration}s: "
            f"~{max_words})."
        )

        word_min = max(20, int(max_words * 0.6))

        word_max = int(max_words * 1.1)

        if not word_min <= word_count <= word_max:

            print(
                "⚠️ Narration word count "
                f"({word_count}) is outside the "
                f"{target_duration}s band "
                f"[{word_min}-{word_max}]."
            )

        # -----------------------------------------------------
        # SPOKEN-DURATION GATE (+ ONE tighten rewrite)
        #
        # The prompt carries a word budget, but numbers expand
        # when spoken and the model overshoots.  Estimate the
        # real spoken length; when it would stretch the render
        # past the band, do ONE surgical rewrite.  The TTS stage
        # enforces the final measured length regardless.
        # -----------------------------------------------------

        estimated_seconds = sum(
            ScriptEngine._estimate_spoken_seconds(
                scene.narration
            )
            for scene in script.scenes
        )

        print(
            f"⏱️ Estimated spoken length: "
            f"{estimated_seconds:.1f}s "
            f"(band target {target_duration}s)."
        )

        if estimated_seconds > (
            target_duration * 1.15
        ):

            print(
                "✂️ Narration is too long for the "
                f"{target_duration}s band - requesting "
                "one tighten rewrite."
            )

            if ScriptEngine._tighten_narration(
                script,
                target_duration,
            ):

                re_estimate = sum(
                    ScriptEngine
                    ._estimate_spoken_seconds(
                        scene.narration
                    )
                    for scene in script.scenes
                )

                print(
                    "✂️ Tighten pass done: estimated "
                    f"{estimated_seconds:.1f}s -> "
                    f"{re_estimate:.1f}s."
                )

        # -----------------------------------------------------
        # BASIC FACT-CHECK FLAG
        # -----------------------------------------------------

        if not script.fact_check.is_accurate:

            print(
                "⚠️ AI marked script "
                "as potentially inaccurate:"
            )

            print(
                script.fact_check.discrepancies
            )

        # -----------------------------------------------------
        # HOOK CONCRETENESS GUARD
        #
        # If scene 1 is an abstract, scroll-stopping question
        # with no number and no named entity, try ONE surgical
        # rewrite of just the hook.  Failure keeps the original.
        # (see _hook_is_concrete / _refine_abstract_hook below)
        # -----------------------------------------------------

        if not ScriptEngine._hook_is_concrete(
            script,
            data,
        ):

            print(
                "⚠️ Hook is abstract (no number, no named "
                "entity) - requesting one surgical rewrite."
            )

            rewritten = (
                ScriptEngine._refine_abstract_hook(
                    script,
                    data,
                    target_duration,
                )
            )

            if rewritten:

                script.scenes[0].narration = rewritten

                print(
                    "✏️ Hook rewritten with concrete "
                    f"detail: {rewritten}"
                )

        # -----------------------------------------------------
        # DETERMINISTIC MATH INTEGRITY VALIDATION & REPAIR (Phase 1)
        #
        # Validate numerical change claims against the validated
        # DataFrame. If discrepancies are found, perform surgical
        # repair passes with ground-truth numbers rather than
        # blind string replacement.
        # -----------------------------------------------------
        from app.ai.math_integrity import MathIntegrityEngine, MathIntegrityError

        is_valid = MathIntegrityEngine.repair_script_math(
            script,
            data,
            topic_data,
            max_retries=2,
        )
        if not is_valid:
            raise MathIntegrityError(
                "Script failed mathematical integrity validation and could not be safely repaired."
            )

        return script

    # (Tier-2d title polish defined once above at line ~593;
    #  this duplicate was removed to avoid confusion.)

    # -----------------------------------------------------
    # DURATION BAND (18-30s) + SPOKEN-LENGTH HELPERS
    #
    # The rendered length is governed by a per-video band, not
    # a fixed number: the measured TTS narration is the visual
    # timeline's source of truth, so the narration itself must
    # fit the budget or the whole video runs long.
    # -----------------------------------------------------

    @staticmethod
    def _duration_band_for_entities(entity_count) -> int:
        """Target seconds for this video, inside [18, 30].

        1-2 entities -> ~20s (simple head-to-head)
        3 entities   -> ~24s
        4+ entities  -> ~28s (ranked / multi-entity)

        settings.TARGET_DURATION is only a fallback when the
        entity count is unknown, clamped into the band.
        """

        if getattr(settings, "is_landscape", False):
            return int(getattr(settings, "LANDSCAPE_TARGET_DURATION", 85))

        band_min = max(
            1,
            int(getattr(settings, "DURATION_BAND_MIN", 18)),
        )
        band_max = max(
            band_min,
            int(getattr(settings, "DURATION_BAND_MAX", 30)),
        )

        def _clamp(value) -> int:
            return max(
                band_min,
                min(band_max, int(value)),
            )

        try:
            count = int(entity_count)
        except (TypeError, ValueError):
            count = 0

        if count <= 0:
            # Entity count unavailable: fall back to the legacy
            # fixed value, clamped into the band.
            try:
                fallback = int(settings.TARGET_DURATION)
            except (TypeError, ValueError):
                fallback = (band_min + band_max) // 2
            return _clamp(fallback)

        if count <= 2:
            target = 20
        elif count == 3:
            target = 24
        else:
            target = 28

        return _clamp(target)

    @staticmethod
    def _estimate_spoken_seconds(text) -> float:
        """Rough spoken length of one narration line (seconds).

        Calibrated against measured Edge-TTS renders: ~2.5 written
        words per spoken second at the pipeline's pacing; every
        numeric token ("204", "395.5", "#2") expands to ~3 spoken
        words; ~0.8s of punctuation/pause overhead per line.
        """

        import re

        if not text:
            return 0.0

        spoken_words = 0.0

        for token in str(text).split():
            spoken_words += (
                3.0
                if re.search(r"\d", token)
                else 1.0
            )

        return spoken_words / 2.5 + 0.8

    @staticmethod
    def _tighten_narration(
        script,
        target_duration: int,
    ) -> bool:
        """ONE LLM rewrite pass that shortens every scene's
        narration so the spoken estimate fits the duration band.

        Returns True when the script was modified.  Any failure
        keeps the original narration -- the TTS rate-enforcement
        pass still bounds the measured audio afterwards.
        """

        import json

        max_words = max(
            25,
            int((target_duration - 3.0) * 2.5),
        )

        scenes_payload = [
            {
                "scene_number": int(
                    scene.scene_number
                ),
                "narration": str(scene.narration),
            }
            for scene in script.scenes
        ]

        prompt = f"""Shorten the narration of a {target_duration}-second YouTube Shorts script so it can be SPOKEN in {target_duration} seconds.

Hard rules:
- Keep every fact, country, year and number EXACTLY as given. Never invent or drop data.
- Keep the hook punchy (scene 1) and the ending loop-ready.
- Total across all scenes: AT MOST {max_words} words (a numeric token costs ~3 spoken words).
- Same voice: contractions, no filler, no new rhetorical devices.

Scenes (JSON):
{json.dumps(scenes_payload, ensure_ascii=False)}

Return ONLY JSON:
{{
    "scenes": [
        {{
            "scene_number": 1,
            "narration": "shortened line"
        }}
    ]
}}
"""

        try:

            raw = GroqLLM.generate_structured(
                prompt,
                temperature=0.3,
            )

            payload = (
                raw
                if isinstance(raw, dict)
                else json.loads(str(raw))
            )

            by_number = {}

            for item in payload.get("scenes", []):
                try:
                    by_number[
                        int(item.get("scene_number"))
                    ] = str(
                        item.get("narration") or ""
                    ).strip()
                except (TypeError, ValueError):
                    continue

        except Exception as exc:

            print(
                "⚠️ Narration tighten pass failed "
                f"({type(exc).__name__}: {exc}); keeping "
                "original narration."
            )

            return False

        changed = False

        for scene in script.scenes:

            new_text = by_number.get(
                int(scene.scene_number),
                "",
            )

            if (
                new_text
                and new_text
                != str(scene.narration).strip()
            ):
                scene.narration = new_text
                changed = True

        return changed

    # -----------------------------------------------------
    # HOOK CONCRETENESS GUARD
    #
    # An abstract scene-1 ("Who's topping X now?") gives a
    # viewer no reason to stop scrolling.  If scene 1 has
    # neither a concrete number nor a named entity from the
    # data, do ONE surgical LLM rewrite of just the hook.
    # Any failure degrades gracefully (original hook kept).
    # -----------------------------------------------------

    @staticmethod
    def _hook_is_concrete(
        script,
        data
    ) -> bool:
        """True when scene 1 contains a digit or a data entity."""

        import re as _re

        hook = str(
            getattr(
                script.scenes[0],
                "narration",
                "",
            )
            or ""
        )

        if _re.search(r"\d", hook):
            return True

        lowered = hook.lower()

        try:

            for _year in data.columns:

                for _entity in data[_year].dropna().index:

                    token = str(_entity).strip().lower()

                    if (
                        len(token) >= 3
                        and token in lowered
                    ):

                        return True

        except Exception:

            pass

        return False

    @staticmethod
    def _refine_abstract_hook(
        script,
        data,
        target_duration: int
    ) -> str | None:
        """One-shot LLM rewrite of an abstract hook.

        Returns the new narration, or None on any failure
        (caller keeps the original hook).
        """

        try:

            from app.groq_client import GroqLLM

            hook = str(
                getattr(
                    script.scenes[0],
                    "narration",
                    "",
                )
                or ""
            )

            entities = [
                str(value)
                for value in list(data.index)[:12]
            ]

            prompt = (
                "You are rewriting ONE scene of a YouTube "
                "Shorts data script.\n\n"
                f"Current scene 1 narration (too abstract):\n"
                f'"{hook}"\n\n'
                f"The dataset covers these entities: "
                f"{', '.join(entities)}.\n\n"
                "Rewrite ONLY the hook line so it grabs a "
                "scrolling viewer: it MUST lead with a "
                "concrete number from the data or a specific "
                "named entity (or both). Keep the same fact "
                "and tone. One punchy sentence, max 20 words, "
                "numbers as digits.\n\n"
                'Reply with JSON only: {"narration": "..."}'
            )

            payload = GroqLLM.generate_structured(
                prompt,
                temperature=0.7,
                max_tokens=1024,
                system=(
                    "You write punchy YouTube Shorts hook "
                    "lines that lead with concrete data detail. "
                    "You must return ONLY a valid JSON object matching the requested schema."
                ),
            )

            narration = (
                str(payload.get("narration", "")).strip()
                if isinstance(payload, dict)
                else ""
            )

            if not narration:
                return None

            words = narration.split()

            if len(words) > 22:

                narration = " ".join(words[:22])

            return narration

        except Exception as exc:

            print(
                f"⚠️ Hook refinement failed "
                f"({type(exc).__name__}: {exc}); "
                "keeping the original hook."
            )

            return None
