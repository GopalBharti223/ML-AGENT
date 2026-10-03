
import json
import random
import re
from typing import Dict

from app.config import settings
from app.groq_client import GroqLLM
from app.countries import (
    country_hashtag,
    display_name,
    is_widely_recognized,
)
from app.time_labels import coerce_year_label

import pandas as pd

# Words too generic to make good topic hashtags.
_TOPIC_STOP = {
    "the", "of", "and", "for", "per", "in", "to", "a", "by", "on",
    "at", "with", "from", "over", "their", "its", "an",
}


class MetadataEngine:

    # =====================================================
    # GENERATE YOUTUBE METADATA
    # =====================================================

    # -----------------------------------------------------
    # Country-aware helpers
    # -----------------------------------------------------

    @staticmethod
    def _winning_country(data: pd.DataFrame, latest_year):
        """Return a widely-recognized display name for the #1 entity."""

        column = data[latest_year].dropna()
        if column.empty:
            return None

        winner = str(column.idxmax())
        if is_widely_recognized(winner):
            return display_name(winner)
        return None

    @staticmethod
    def _apply_winner_title(
        title: str,
        winner: str,
        script,
        latest_year
    ) -> str | None:

        title_lower = title.lower()
        if any(
            token in title_lower
            for token in winner.lower().split()
        ):
            return None

        subject = str(
            getattr(script, "indicator_name", "") or ""
        ).strip()
        if not subject:
            subject = str(
                getattr(script, "title", "") or ""
            ).strip()
        subject = re.sub(
            r"\s+", " ", subject
        ).strip(" -")

        if not subject:
            return None

        candidate = (
            f"{winner} Tops {subject} in {latest_year}?"
        )

        if len(candidate) > 100:
            tokens = subject.split()
            candidate = (
                f"{winner} Tops "
                f"{' '.join(tokens[:3])} in {latest_year}?"
            )

        if 0 < len(candidate) <= 100:
            return candidate
        return None

    # -----------------------------------------------------
    # Human-sounding engagement helpers
    # -----------------------------------------------------

    @staticmethod
    def _entities_are_countries(data: pd.DataFrame) -> bool:
        """True when most chart entities are real countries."""

        sample = [
            str(value)
            for value in list(data.index)[:10]
        ]

        if not sample:
            return False

        recognized = sum(
            1
            for value in sample
            if is_widely_recognized(value)
        )

        return (
            recognized / len(sample)
        ) >= 0.6

    @staticmethod
    def _pick_comment_prompt(script, data) -> str:
        """
        Rotate comment bait so uploads never repeat
        the same engagement line.
        """

        if MetadataEngine._entities_are_countries(data):

            return random.choice(
                [
                    "Which country surprised you most? Drop it below.",
                    "Did your country climb or fall? Argue below.",
                ]
            )

        # Drivers, anime studios, cars, papers - anything.
        return random.choice(
            [
                "Did you see that ending coming?",
                "Hot take? The comments are open.",
                "Rate this twist 1-10 below.",
            ]
        )

    @staticmethod
    def _append_comment_prompt(
        description: str,
        script=None,
        data=None
    ) -> str:

        if data is not None:

            line = MetadataEngine._pick_comment_prompt(
                script,
                data
            )

        else:

            line = "Did you see that ending coming?"

        if line.lower() in description.lower():
            return description
        return description.rstrip() + "\n\n" + line

    # Phrases that instantly mark a description as
    # machine-written. Scrubbed even if the LLM
    # sneaks them past the prompt rules.
    _AI_TELL_PATTERNS = [
        (
            r"like,\s*comment(,\s*and|\s+and)?\s*subscribe[^.!?\n]*[!.?]?",
            "",
        ),
        (
            r"\bsubscribe for more[^.!?\n]*[!.?]?",
            "",
        ),
        (
            r"\bthis shorts?\b\s+(video\s+)?"
            r"(visualizes|visualises|reveals|shows|explores|breaks down)",
            "watch",
        ),
    ]

    @staticmethod
    def _scrub_ai_tells(text: str) -> str:
        """Remove templated AI phrasing from titles/descriptions."""

        cleaned = str(text)

        for pattern, replacement in (
            MetadataEngine._AI_TELL_PATTERNS
        ):

            cleaned = re.sub(
                pattern,
                replacement,
                cleaned,
                flags=re.IGNORECASE,
            )

        cleaned = re.sub(
            r"[ \t]{2,}",
            " ",
            cleaned,
        )

        cleaned = re.sub(
            r"\n{3,}",
            "\n\n",
            cleaned,
        )

        return cleaned.strip()

    @staticmethod
    def _derive_topic_tags(script) -> list:
        """Fallback topic hashtags derived from the indicator/category."""

        candidates = []

        for attr in ("indicator_name", "category", "topic"):
            value = str(
                getattr(script, attr, "") or ""
            ).strip()
            tokens = [
                token
                for token in re.split(
                    r"[^A-Za-z0-9]+", value
                )
                if len(token) >= 2
                and token.lower() not in _TOPIC_STOP
            ]
            if not tokens:
                continue
            tag = "#" + "".join(
                tok[:1].upper() + tok[1:]
                for tok in tokens[:3]
            )
            if tag not in candidates:
                candidates.append(tag)
            if len(candidates) >= 2:
                break

        if not candidates:
            candidates.append("#DataTrends")
        return candidates

    @staticmethod
    def _hashtag_from_name(name) -> str | None:
        """Turn an entity display name into #CamelCaseHashtag.

        MALFORMED-TAG FIX (published-video review, Issue 3):
        several providers return a MultiIndex wide frame --
        the entity shows up here as the stringified tuple
        '("Esports", "Esports")', which tokenized into
        [Esports, Esports] and produced #EsportsEsports
        (3 of the last 205 videos shipped such tags:
        #EsportsEsports, #NetflixNetflix, #UnknownUnknown).
        Tuples are unwrapped to their FIRST non-empty
        element before tokenizing.
        """

        value = name

        # MultiIndex row keys arrive as tuples
        # (country_code, country); flatten to a plain string.

        if isinstance(value, (tuple, list)):
            value = next(
                (
                    str(part)
                    for part in value
                    if str(part or "").strip()
                ),
                "",
            )

        tokens = [
            token
            for token in re.split(
                r"[^A-Za-z0-9]+",
                str(value),
            )
            if len(token) >= 2
            and token.lower() not in _TOPIC_STOP
        ]

        if not tokens:
            return None

        # Defense in depth: a repeated consecutive token
        # (any source) collapses to one occurrence.

        deduped = []

        for token in tokens:
            if not deduped or deduped[-1].lower() != token.lower():
                deduped.append(token)

        tokens = deduped

        if not tokens:
            return None

        return "#" + "".join(
            tok[:1].upper() + tok[1:]
            for tok in tokens[:3]
        )

    @staticmethod
    def _entity_hashtags(
        data: pd.DataFrame,
        latest_year,
        avoid
    ) -> list:
        """Top non-country entities as hashtags.

        F1 drivers, teams, anime, games, companies...  Country
        entities are handled by the geography slice and are
        excluded through `avoid` (lowercased hashtags)."""

        ranked = (
            data[latest_year]
            .dropna()
            .sort_values(ascending=False)
        )

        result = []

        for entity in ranked.index:

            tag = MetadataEngine._hashtag_from_name(
                str(entity)
            )

            if tag is None:
                continue

            if tag.lower() in avoid:
                continue

            if tag not in result:
                result.append(tag)

            if len(result) >= 2:
                break

        return result

    @staticmethod
    def _build_hashtags(
        script,
        data: pd.DataFrame,
        latest_year,
        ai_hashtags
    ) -> list:
        """Return a topic-dense hashtag mix.

        Priority: topical hashtags first (LLM + derived),
        then top non-country entities, then ONE geography
        tag, then the mandatory #Shorts.  Generic filler
        (#DataViz, provider names) is dropped so the set
        feels as specific as the search-tags field.
        """

        reserved = {"#shorts", "#dataviz"}

        # 1) Geography: top recognizable countries (for
        #    country stories) - also used as an avoid set.
        geography = []
        ranked = (
            data[latest_year]
            .dropna()
            .sort_values(ascending=False)
        )
        for country_name in ranked.index:
            tag = country_hashtag(str(country_name))
            if tag is None:
                continue
            if tag not in geography:
                geography.append(tag)
            if len(geography) >= 2:
                break

        geography_set = {
            tag.lower()
            for tag in geography
        }

        # 2) Topic hashtags (PRIMARY) - LLM hashtags first,
        #    then derived topic tags, up to 5.
        topic = []
        for hashtag in ai_hashtags:
            hashtag = str(hashtag).strip()
            if hashtag and not hashtag.startswith("#"):
                hashtag = "#" + hashtag
            low = hashtag.lower()
            if low in reserved or low in geography_set:
                continue
            if hashtag not in topic:
                topic.append(hashtag)
            if len(topic) >= 5:
                break

        if len(topic) < 4:
            for tag in MetadataEngine._derive_topic_tags(
                script
            ):
                low = tag.lower()
                if low in reserved or low in geography_set:
                    continue
                if tag not in topic:
                    topic.append(tag)
                if len(topic) >= 5:
                    break

        # The LLM sometimes returns only 1-2 topic tags (or
        # country-adjacent ones).  Derived topic tags ALWAYS
        # top the pool up so the topical slice stays dense.
        for tag in MetadataEngine._derive_topic_tags(
            script
        ):
            low = tag.lower()
            if low in reserved or low in geography_set:
                continue
            if tag not in topic:
                topic.append(tag)
            if len(topic) >= 5:
                break

        # 3) Non-country entity hashtags (F1 drivers, teams,
        #    games, actors...).
        avoid = (
            geography_set
            | reserved
            | {tag.lower() for tag in topic}
        )
        entity_tags = MetadataEngine._entity_hashtags(
            data,
            latest_year,
            avoid,
        )

        # 4) Compose: topic-heavy, geography light.  At most
        #    ONE entity tag and ONE geography tag so the
        #    topical slice dominates the final set (and the
        #    first hashtags YouTube displays above the title
        #    are topical, not filler).
        result = (
            topic[:5]
            + entity_tags[:1]
            + geography[:1]
        )

        seen = set()
        ordered = []

        for tag in result:

            low = tag.lower()

            if low in seen:

                continue

            seen.add(low)

            ordered.append(tag)

        # #Shorts is mandatory and must never be pushed out by
        # a full topic slice (YouTube requires it in the video
        # description for Shorts classification).  Prepend so it
        # can NEVER be evicted by the content slice.

        final = ["#Shorts"]

        seen_lc = {"#shorts"}

        for tag in ordered:

            low = tag.lower()

            if low in seen_lc:

                continue

            if low in reserved:

                continue

            seen_lc.add(low)

            final.append(tag)

        return final[:7]

    # -----------------------------------------------------
    # Title format rotation + truthfulness validation
    # -----------------------------------------------------

    TITLE_FORMATS = {
        "question": (
            "Question-with-stakes - open with Who/What/Which/Why "
            "and frame a contest the viewer must watch to resolve. "
            "Imply a winner/loser or a shocking gap; never merely "
            "describe the chart."
        ),
        "number_led": (
            "Number-led stakes - open with the sharpest verified "
            "stat, but frame it as a challenge or upset, not a "
            "report line ('X just did what Y said was impossible')."
        ),
        "duel": (
            "Duel - pit two specific entities against each other "
            "with clear stakes for the loser ('vs' framing)."
        ),
        "twist": (
            "Twist - promise a surprise no one expects, implying "
            "the obvious answer is wrong; withhold the outcome."
        ),
    }

    # Default weights favoring stakes formats over the descriptive
    # number-led format.  Overridable via settings.title weights.
    _TITLE_FORMAT_WEIGHTS_DEFAULT = {
        "question": 5,
        "duel": 3,
        "twist": 2,
        "number_led": 1,
    }

    # Title wording that asserts a leader / #1 position.
    _LEADER_CLAIM_RE = re.compile(
        r"\b(leads?|dominates?|tops?|rules?|reigns?|"
        r"#1|number one|number\s*1|takes? the crown|"
        r"stole the crown|winning|wins?|won the)\b",
        re.IGNORECASE,
    )

    # Common entity aliases: canonical lowercase name ->
    # aliases that may appear in titles.  Checked only when
    # the canonical name itself did not match, and always
    # with word boundaries so a short alias like "us" cannot
    # match inside "status" or "industry".
    _ENTITY_ALIASES = {
        "united states": (
            "usa", "us", "america", "u.s.",
        ),
        "united states of america": (
            "usa", "us", "america",
        ),
        "united kingdom": (
            "uk", "britain", "england", "great britain",
        ),
        "russian federation": ("russia",),
        "russia": ("russian federation",),
        "korea, rep.": ("south korea", "korea"),
        "south korea": ("korea",),
        "egypt, arab rep.": ("egypt",),
        "iran, islamic rep.": ("iran",),
        "hong kong sar, china": ("hong kong",),
        "czechia": ("czech republic",),
        "czech republic": ("czechia",),
        "turkiye": ("turkey",),
        "turkey": ("turkiye",),
        "viet nam": ("vietnam",),
        "vietnam": ("viet nam",),
    }

    # Strong verbs for growth/change stories.
    # The LLM tends to overuse "surge" — this list gives it a varied
    # vocabulary to draw from, and the rotation tracker below biases
    # away from verbs used in recent videos.
    _STRONG_VERBS = [
        "surge", "rocket", "skyrocket", "soar", "spike",
        "jump", "leap", "climb", "boom", "explode",
        "double", "triple", "vault", "accelerate", "explode",
        "shoot up", "burst", "ignite", "snowball", "balloon",
    ]

    # Recently-used strong verbs (module-level so it persists across
    # calls within the same process / test run).
    _recent_strong_verbs: List[str] = []

    # Verbs considered "overused" — if the LLM uses one of these,
    # we replace it with a less-common synonym.
    _OVERUSED_VERBS = {"surge", "surges", "surged", "surging"}

    # Replacement map: overused verb -> list of alternatives
    _VERB_ALTERNATIVES = {
        "surge": ["jump", "leap", "climb", "spike", "soar", "rocket",
                   "vault", "boom", "snowball", "balloon", "swell"],
        "surges": ["jumps", "leaps", "climbs", "spikes", "soars", "rockets",
                    "vaults", "booms", "snowballs", "balloons", "swells"],
        "surged": ["jumped", "leaped", "climbed", "spiked", "soared", "rocketed",
                    "vaulted", "boomed", "snowballed", "ballooned", "swelled"],
        "surging": ["jumping", "leaping", "climbing", "spiking", "soaring",
                     "rocketing", "vaulting", "booming", "snowballing",
                     "ballooning", "swelling"],
    }

    @staticmethod
    def _replace_overused_verbs(title: str) -> str:
        """Replace overused strong verbs with less-common synonyms.

        Defense-in-depth: the prompt asks for vocabulary variety but the
        LLM ignores it.  We enforce it here by replacing overused verbs
        with alternatives, preferring verbs not used in recent videos.
        """
        import random

        # Keep original words for output; use lowercased only for matching
        words = title.split()

        for i, word in enumerate(words):
            # Strip punctuation for matching (lowercased)
            clean = word.strip(".,!?;:-'\"").lower()
            if clean in MetadataEngine._OVERUSED_VERBS:
                alternatives = MetadataEngine._VERB_ALTERNATIVES.get(clean, [])
                if not alternatives:
                    continue

                # Prefer verbs not used recently
                recent = set(MetadataEngine._recent_strong_verbs)
                fresh = [v for v in alternatives if v not in recent]
                if not fresh:
                    fresh = alternatives

                replacement = random.choice(fresh)
                MetadataEngine._recent_strong_verbs.append(replacement)
                # Keep last 10 verbs in history
                if len(MetadataEngine._recent_strong_verbs) > 10:
                    MetadataEngine._recent_strong_verbs = (
                        MetadataEngine._recent_strong_verbs[-10:]
                    )

                # Preserve original capitalization
                if word[0].isupper():
                    replacement = replacement.capitalize()
                # Preserve trailing punctuation
                trailing = ""
                while word and word[-1] in ".,!?;:'\"":
                    trailing = word[-1] + trailing
                    word = word[:-1]

                words[i] = replacement + trailing
                break  # Only replace one verb per title

        return " ".join(words)

    @staticmethod
    def _ensure_entity_or_number(
        title: str, data, latest_year, script
    ) -> str:
        """Ensure the title contains either a concrete number or a named entity.

        If the title is generic (no number, no entity from the data),
        inject the winning entity name.
        """
        import re

        # Check for a concrete number (digits)
        has_number = bool(re.search(r'\d', title))

        # Check for a named entity from the data
        has_entity = False
        if not data.empty:
            for idx in data.index[:15]:
                name = str(idx).strip()
                if len(name) > 2 and name.lower() in title.lower():
                    has_entity = True
                    break

        if has_number or has_entity:
            return title

        # Title is generic — inject the most relevant entity.
        # Priority: (1) entity mentioned in topic/title context,
        #           (2) winning entity from data.
        entity = MetadataEngine._find_topic_entity(data, script)
        if not entity:
            entity = MetadataEngine._winning_country(data, latest_year)
        if entity:
            return f"{entity}: {title}"

        return title

    @staticmethod
    def _find_topic_entity(data, script) -> Optional[str]:
        """Find the entity that is the subject of the topic.

        Checks the topic title and indicator name for mentions of entities
        in the data. Returns the first matching entity name, or None.
        """
        if data.empty:
            return None

        # Collect candidate text from topic context
        context_parts = [
            str(getattr(script, "topic", "") or ""),
            str(getattr(script, "indicator_name", "") or ""),
            str(getattr(script, "title", "") or ""),
        ]
        context_lower = " ".join(context_parts).lower()

        if not context_lower.strip():
            return None

        # Find entities from data that appear in the topic context
        for idx in data.index:
            name = str(idx).strip()
            if len(name) > 2 and name.lower() in context_lower:
                # Return the display name if widely recognized
                from app.countries import display_name, is_widely_recognized
                if is_widely_recognized(name):
                    return display_name(name)
                return name

        return None

    @classmethod
    def _title_format_weights(cls) -> Dict[str, float]:
        """Title-format weights from config (JSON), with safe fallback.

        Stakes formats (question/duel/twist) are weighted above the
        descriptive number-led format; see TITLE_FORMAT_WEIGHTS in
        app.config.
        """

        weights: Dict[str, float] = dict(
            MetadataEngine._TITLE_FORMAT_WEIGHTS_DEFAULT
        )

        raw = getattr(settings, "TITLE_FORMAT_WEIGHTS", "") or ""

        try:

            parsed = json.loads(raw)

            if isinstance(parsed, dict):

                for key, value in parsed.items():

                    if key in weights and float(value) >= 0:
                        weights[key] = float(value)

        except (ValueError, TypeError):

            pass  # malformed env JSON -> defaults

        return weights

    @classmethod
    def _pick_title_format(
        cls,
        last_format=None
    ) -> str:
        """Pick a title format different from the last used.

        Weighted toward stakes formats (question/duel/twist) per
        TITLE_FORMAT_WEIGHTS; the descriptive number-led format
        still appears, just rarely.
        """

        options = list(
            MetadataEngine.TITLE_FORMATS.keys()
        )

        if (
            last_format in options
            and len(options) > 1
        ):

            options = [
                fmt
                for fmt in options
                if fmt != last_format
            ]

        weights = MetadataEngine._title_format_weights()

        picked = random.choices(
            options,
            weights=[
                max(0.0, weights.get(fmt, 1.0))
                for fmt in options
            ],
            k=1,
        )[0]

        return picked

    @classmethod
    def _pick_strong_verb(cls) -> str:
        """Pick a strong verb for growth/change stories, biasing away
        from verbs used in recent videos."""

        recent = getattr(cls, "_recent_strong_verbs", []) or []
        # Bias away from the last 5 used verbs.
        avoid = set(recent[-5:])

        options = [
            v for v in cls._STRONG_VERBS
            if v not in avoid
        ]
        if not options:
            options = list(cls._STRONG_VERBS)

        verb = random.choice(options)

        # Update history.
        history = list(recent)
        history.append(verb)
        cls._recent_strong_verbs = history[-10:]

        return verb

    @staticmethod
    def _title_entity(
        title: str,
        data: pd.DataFrame
    ) -> str | None:
        """Return the data entity mentioned in the title."""

        lowered_title = title.lower()

        best = None

        try:

            for _year in data.columns:

                column = data[_year].dropna()

                for entity in column.index:

                    token = str(entity).strip().lower()

                    if (
                        len(token) < 3
                        or token not in lowered_title
                    ):
                        continue

                    if (
                        best is None
                        or len(token) > len(best[1])
                    ):
                        best = (str(entity), token)

        except Exception:

            pass

        # Alias pass: titles often abbreviate ("USA", "UK")
        # while data indexes use canonical names ("United
        # States").  Match aliases with word boundaries.
        if best is None:

            try:

                for _year in data.columns:

                    column = data[_year].dropna()

                    for entity in column.index:

                        token = (
                            str(entity).strip().lower()
                        )

                        for alias in (
                            MetadataEngine
                            ._ENTITY_ALIASES
                            .get(token, ())
                        ):

                            if len(alias) < 2:

                                continue

                            if re.search(
                                r"\b"
                                + re.escape(alias)
                                + r"\b",
                                lowered_title,
                            ):

                                if (
                                    best is None
                                    or len(alias)
                                    > len(best[1])
                                ):

                                    best = (
                                        str(entity),
                                        alias,
                                    )

            except Exception:

                pass

        return best[0] if best else None

    @staticmethod
    def _validate_title_claims(
        title: str,
        script,
        data: pd.DataFrame,
        latest_key,
        story_type=None
    ):
        """Correct a title that overclaims a leader position.

        Returns (title, changed).

        - Entity named in the title is NOT actually rank #1
          in the latest year -> truthful rank reframe.
        - Decline story + leader framing -> regenerated
          truthful framing (rank reframe) when an entity is
          known; otherwise logged (prompt now carries the
          story type to prevent it at generation time).
        """

        entity = MetadataEngine._title_entity(
            title,
            data,
        )

        subject = str(
            getattr(script, "indicator_name", "") or ""
        ).strip()

        latest_year = coerce_year_label(latest_key)

        if latest_year is None:
            latest_year = str(latest_key)

        decline_family = {
            "rank_decline", "decline", "falling",
            "collapse", "drop", "dropout",
        }

        if not MetadataEngine._LEADER_CLAIM_RE.search(
            title
        ):
            return title, False

        # ---- decline story: refuse leader framing ----
        if (
            story_type
            and str(story_type).lower() in decline_family
        ):

            print(
                "⚠️ Title uses leader/dominance framing for a "
                f"decline story ('{title}'; story_type="
                f"{story_type}). "
            )

            if entity:

                column = data[latest_key].dropna()

                if not column.empty and entity in column.index:

                    rank = (
                        column
                        .sort_values(ascending=False)
                        .index
                        .get_loc(entity)
                        + 1
                    )

                    reframe = (
                        f"{entity} Slipped to #{rank} in "
                        f"{subject} ({latest_year})"
                    )

                    print(
                        f"  -> truthful reframe: '{reframe}'"
                    )

                    return reframe, True

        # ---- entity named + leader claim: verify its rank ----
        if entity:

            column = data[latest_key].dropna()

            if column.empty:
                return title, False

            if entity not in column.index:
                return title, False

            rank = (
                column
                .sort_values(ascending=False)
                .index
                .get_loc(entity)
                + 1
            )

            if rank == 1:
                return title, False

            reframe = (
                f"{entity} Reaches #{rank} in "
                f"{subject} ({latest_year})"
            )

            print(
                "⚠️ Title claims a leader position the data "
                f"does not support ('{title}'; {entity} is "
                f"rank #{rank}, not #1). Truthful reframe -> "
                f"'{reframe}'"
            )

            return reframe, True

        # No entity matched: we cannot compute a rank, so the
        # overclaim cannot be auto-corrected.  Make it LOUD so
        # repeated occurrences are visible in run logs.
        print(
            "⚠️ Title claims a leader position but no data "
            f"entity could be matched in '{title}'; cannot "
            "auto-verify. (Generation prompt carries the story "
            "type to prevent this at the source.)"
        )

        return title, False

    @staticmethod
    def generate_metadata(
        script,
        data: pd.DataFrame,
        story_type: str = None,
        last_title_format: str = None,
        story_metrics: dict = None,
    ) -> dict:

        if data is None or data.empty:
            raise ValueError(
                "Cannot generate metadata without data."
            )

        # -------------------------------------------------
        # Prepare verified data summary
        #
        # Season-label safe: the prompt/title years are coerced
        # ("2025-26 (in progress)" -> 2025) so raw labels never
        # leak into LLM prompts or titles; data access keeps the
        # original column keys.
        # -------------------------------------------------

        latest_key = data.columns[-1]
        first_key = data.columns[0]

        latest_year = coerce_year_label(latest_key)
        if latest_year is None:
            latest_year = str(latest_key)

        first_year = coerce_year_label(first_key)
        if first_year is None:
            first_year = str(first_key)

        latest_data = (
            data[latest_key]
            .sort_values(ascending=False)
            .head(15)
            .to_dict()
        )

        first_data = (
            data[first_key]
            .sort_values(ascending=False)
            .head(15)
            .to_dict()
        )

        # -------------------------------------------------
        # Prepare COMPACT script information
        #
        # IMPORTANT:
        # Do not send full narration + visual descriptions
        # for every scene. They can make the Groq request
        # exceed the provider TPM limit.
        # -------------------------------------------------

        scenes_text = []

        MAX_SCENES = 12
        MAX_NARRATION_CHARS = 500
        MAX_OVERLAY_CHARS = 150

        for scene in script.scenes[:MAX_SCENES]:

            narration = str(
                getattr(scene, "narration", "")
            ).strip()

            text_overlay = str(
                getattr(scene, "text_overlay", "")
            ).strip()

            # Keep enough narration to understand the scene,
            # but prevent a huge prompt.
            if len(narration) > MAX_NARRATION_CHARS:
                narration = (
                    narration[:MAX_NARRATION_CHARS]
                    + "..."
                )

            if len(text_overlay) > MAX_OVERLAY_CHARS:
                text_overlay = (
                    text_overlay[:MAX_OVERLAY_CHARS]
                    + "..."
                )

            scenes_text.append(
                f"Scene {scene.scene_number}: "
                f"Narration: {narration} | "
                f"Overlay: {text_overlay}"
            )

        scenes_text = "\n".join(scenes_text)

        if len(script.scenes) > MAX_SCENES:
            scenes_text += (
                f"\n[{len(script.scenes) - MAX_SCENES} "
                f"additional scenes omitted for token safety]"
            )

        # -------------------------------------------------
        # Compact country/entity list
        # -------------------------------------------------

        entities = [
            str(value)
            for value in list(data.index)[:30]
        ]

        # -------------------------------------------------
        # Today's required title format (rotated via the
        # history DB so consecutive uploads never share one)
        # -------------------------------------------------

        format_used = MetadataEngine._pick_title_format(
            last_title_format
        )

        format_desc = MetadataEngine.TITLE_FORMATS.get(
            format_used,
            "",
        )

        story_type_label = str(
            story_type or "unknown"
        ).strip()

        # -------------------------------------------------
        # AI PROMPT
        # -------------------------------------------------

        prompt = f"""
You are the YouTube metadata manager for a
data-driven YouTube Shorts channel.

Create metadata ONLY from the verified information below.

Do NOT invent statistics, countries, years, sources,
or claims that are not supported by the data.

VIDEO INFORMATION

Topic:
{script.topic}

Title:
{script.title}

Category:
{script.category}

Source:
{script.source_name}

Source URL:
{script.source_url}

Story type:
{story_type_label}

Data period:
{first_year} to {latest_year}

Countries/entities:
{entities}

Latest year values:
{latest_data}

First year values:
{first_data}

SCRIPT CONTEXT

{scenes_text}

TASK

Generate:

1. YouTube title
2. YouTube description
3. Hashtags
4. YouTube search tags
5. YouTube category
6. Short thumbnail text

TITLE STYLE

Sound like a person, not a report.  Format rotation is
handled for you: today's REQUIRED format is below.  Use
EXACTLY that format for the title; the other formats are
reserved for other videos so consecutive uploads never
repeat a template.

STAKES RULE (mandatory):

The title must imply a WINNER/LOSER, an UPSET, a shocking
gap, or a comparison outcome the viewer can only resolve
by watching.  NEVER describe what the chart shows.

- Bad (descriptive): "X's CPI jumped 13 points"
- Good (stakes): "Which country's inflation is
  exploding fastest?"
- Bad: "Population trends in 2025"
- Good: "China or India: who peaks first?"

Every title must imply an outcome or a contest.

REQUIRED TITLE FORMAT FOR THIS RUN:

{format_used}: {format_desc}

FORMAT MENU (for reference - do NOT switch away from the
required format):

1. Question-with-stakes - "Who ...?", "What ...?",
   "Which ...?", "Why ...?" - framed as a contest.
   Example: "Which economy collapses first by 2030?"

2. Number-led stakes - open with the shocking stat as an
   upset, not a report line.
   Example: "Angola just did what economists called
   impossible"

3. Duel - pit two entities against each other.
   Example: "Norris vs Verstappen: who blinks first?"

4. Twist - promise the surprise; the obvious answer is
   wrong.
   Example: "The CO2 leader nobody talks about"

VOCABULARY VARIETY (rotate strong verbs across videos):

For growth/change stories, use ONE of these verbs per title —
NEVER repeat the same verb in consecutive videos.  This list
ensures "surge" is not the default for every rising-trend story:

- rockets, jumps, climbs, doubles, leaps, soars, spikes,
- vaults, explodes, balloons, booms, skyrockets, swells,
- snowballs, multiplies, accelerates, bulldozes, sprints

For decline/fall stories: drops, slides, tumbles, plunges,
slumps, dips, shrinks, erodes, retreats, freefalls.


STORY FRAMING (match the title to the video's real story):

The video's story type is: {story_type_label}.

- Decline stories (rank_decline, fall, collapse): NEVER
  use "leads / dominates / tops" framing.  Say what
  actually fell: "Girona dropped 40 points", "Ricciardo
  went from 1 win to zero".
- Growth stories (fastest_growth, biggest_jump, climb):
  rising framing is fine, but only for entities the data
  shows rising.
- Leader/current-leader stories: name the leader ONLY when
  it really is #1 in the data.  If an entity is rank 2 or
  worse, say its real rank ("Reaches #31") - never "leads".

Other title rules:

- Maximum 70 characters preferred.
- Interesting but accurate - zero misleading clickbait.
- A "leads / dominates / tops / #1" claim MUST match the
  entity's actual rank in the data.
- Suitable for YouTube Shorts.
- Do not simply repeat the internal topic title.
- Never use "Whom"; prefer "Who".

DESCRIPTION

- Maximum approximately 500 characters.
- FIRST LINE must be the single most surprising
  verified fact, with its concrete number.
  No preamble like "This Short...".
- Mention the time period when useful.
- Name the actual data source briefly.
- End with ONE short casual invitation to comment.
  Sound like a friend, not a marketing email.
- Do not repeat the entire narration.

FORBIDDEN PHRASES (instant bot red flags):

- "Like, comment, and subscribe"
- "Subscribe for more"
- "This Short visualizes / reveals / shows"
- "Welcome back"
- "In this video"
- "data-driven insights"

If you feel the urge to write any of those,
delete the sentence and say it plainly instead.

HASHTAGS

- Generate 6-10 relevant hashtags.
- The majority must be specific to THIS video's actual
  topic/entities (e.g. #InternetPenetration, #Ricciardo,
  #LaLiga), not generic filler like #Data or #WorldData.
- Always include #Shorts.

TAGS

- Generate 8-15 relevant search keywords.
- Only use keywords relevant to this video.

CATEGORY

Use:
Education

unless the actual content clearly belongs elsewhere.

THUMBNAIL TEXT

- Maximum 4 words.
- Short and curiosity-driven.
- Must not make a false claim.

RETURN ONLY VALID JSON.

{{
    "title": "string - your strongest option",
    "title_options": [
        "the title above repeated here",
        "variant 2 using a different format",
        "variant 3 using a different format"
    ],
    "description": "string",
    "hashtags": [
        "#Shorts"
    ],
    "tags": [
        "keyword 1"
    ],
    "category": "Education",
    "thumbnail_text": "string"
}}
"""

        # -------------------------------------------------
        # GENERATE
        # -------------------------------------------------

        raw_metadata = GroqLLM.generate_structured(
            prompt
        )

        # -------------------------------------------------
        # VALIDATE RESPONSE
        # -------------------------------------------------

        required_fields = [
            "title",
            "description",
            "hashtags",
            "tags",
            "category",
            "thumbnail_text"
        ]

        for field in required_fields:

            if field not in raw_metadata:

                raise ValueError(
                    f"Metadata missing field: {field}"
                )

        # -------------------------------------------------
        # Clean title
        # -------------------------------------------------

        title = str(
            raw_metadata["title"]
        ).strip()

        if not title:

            raise ValueError(
                "Generated title is empty."
            )

        # -------------------------------------------------
        # POST-GEN VERB REPLACEMENT (Issue 1 fix):
        # If the LLM used an overused strong verb, replace it
        # with a less-common synonym from the approved list.
        # This is defense-in-depth: the prompt asks for variety
        # but the LLM ignores it.  We enforce it here.
        # -------------------------------------------------
        title = MetadataEngine._replace_overused_verbs(title)

        # -------------------------------------------------
        # POST-GEN ENTITY/NUMBER CHECK (Issue 2 fix):
        # If the title has neither a concrete number nor a
        # named entity from the data, inject the winner.
        # -------------------------------------------------
        title = MetadataEngine._ensure_entity_or_number(
            title, data, latest_year, script
        )

        # -------------------------------------------------
        # Prefer naming the winning country when it is
        # widely recognizable, e.g. "USA Tops X in 2025?"
        # -------------------------------------------------

        winner = MetadataEngine._winning_country(
            data, latest_year
        )
        if winner:
            applied = MetadataEngine._apply_winner_title(
                title, winner, script, latest_year
            )
            if applied:
                title = applied

        if len(title) > 100:

            title = title[:97] + "..."

        title = MetadataEngine._scrub_ai_tells(
            title
        )

        # -------------------------------------------------
        # TRUTHFULNESS VALIDATION
        #
        # 1. A "leads/dominates/tops/#1" claim must match the
        #    entity's actual rank in the data.  If the entity
        #    named in the title is NOT rank #1, reframe to the
        #    real rank ("Reaches #31" not "leads").
        # 2. Decline stories must not use leader framing.
        # -------------------------------------------------

        title, _title_changed = (
            MetadataEngine._validate_title_claims(
                title,
                script,
                data,
                latest_key,
                story_type=story_type,
            )
        )

        # -------------------------------------------------
        # Description
        # -------------------------------------------------

        description = str(
            raw_metadata["description"]
        ).strip()

        description = MetadataEngine._append_comment_prompt(
            description,
            script,
            data
        )

        description = MetadataEngine._scrub_ai_tells(
            description
        )

        # -------------------------------------------------
        # Channel signature (branding consistency)
        # -------------------------------------------------

        if settings.CHANNEL_NAME:

            signature = (
                f"\n\n📊 {settings.CHANNEL_NAME}"
            )

            if settings.CHANNEL_TAGLINE:
                signature += (
                    f" — {settings.CHANNEL_TAGLINE}"
                )

            if settings.CHANNEL_NAME not in description:
                description += signature

        # -------------------------------------------------
        # Hashtags
        # -------------------------------------------------

        hashtags = MetadataEngine._build_hashtags(
            script, data, latest_year, raw_metadata["hashtags"]
        )

        # -------------------------------------------------
        # Tags
        # -------------------------------------------------

        tags = []

        for tag in raw_metadata["tags"]:

            tag = str(
                tag
            ).strip()

            if tag and tag not in tags:
                tags.append(tag)

        tags = tags[:15]

        # -------------------------------------------------
        # Category
        # -------------------------------------------------

        category = str(
            raw_metadata["category"]
        ).strip()

        if not category:
            category = "Education"

        # -------------------------------------------------
        # Thumbnail text
        # -------------------------------------------------

        thumbnail_text = str(
            raw_metadata["thumbnail_text"]
        ).strip()

        if not thumbnail_text:
            thumbnail_text = script.title

        # -------------------------------------------------
        # Title options for A/B testing
        # (YouTube Test & Compare friendly)
        # -------------------------------------------------

        title_options = []

        for option in (
            raw_metadata.get("title_options") or []
        ):

            option = MetadataEngine._scrub_ai_tells(
                str(option)
            )

            if option and option not in title_options:
                title_options.append(option)

        if title not in title_options:
            title_options.insert(0, title)

        title_options = title_options[:5]

        # -------------------------------------------------
        # Final result
        # -------------------------------------------------

        metadata = {
            "title": title,
            "title_format": format_used,
            "title_options": title_options,
            "description": description,
            "hashtags": hashtags,
            "tags": tags,
            "category": category,
            "thumbnail_text": thumbnail_text
        }

        # -------------------------------------------------
        # PRINT RESULT
        # -------------------------------------------------

        print("\n" + "=" * 60)
        print("📝 YOUTUBE METADATA")
        print("=" * 60)

        print(
            f"\n🎬 Title:\n{metadata['title']}"
        )

        print(
            f"\n📄 Description:\n"
            f"{metadata['description']}"
        )

        print(
            f"\n#️⃣ Hashtags:\n"
            f"{' '.join(metadata['hashtags'])}"
        )

        print(
            f"\n🔎 Tags:\n"
            f"{', '.join(metadata['tags'])}"
        )

        print(
            f"\n📚 Category:\n"
            f"{metadata['category']}"
        )

        print(
            f"\n🖼️ Thumbnail Text:\n"
            f"{metadata['thumbnail_text']}"
        )

        print("\n" + "=" * 60)

        return metadata
