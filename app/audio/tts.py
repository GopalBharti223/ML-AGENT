
import asyncio
import edge_tts
import json
import os
import subprocess
from pathlib import Path

from app.config import settings, parse_json_setting


class TTSEngine:

    VOICE = os.getenv("TTS_VOICE", "en-US-GuyNeural")

    # -----------------------------------------------------
    # Voice rotation (P3): a different natural Edge TTS
    # voice per video so consecutive uploads don't all
    # sound identical.  All entries are standard,
    # widely-available Edge neural voices.  The last-used
    # voice is tracked in the history DB and pick_voice()
    # never repeats it while alternatives remain.
    # -----------------------------------------------------
    VOICE_ROTATION = [
        "en-US-GuyNeural",
        "en-US-JennyNeural",
        "en-US-AriaNeural",
        "en-GB-RyanNeural",
    ]

    # -----------------------------------------------------
    # HUMAN-TOUCH VOICE LAYER
    #
    # Voice is chosen PER CATEGORY (config: VOICE_CATEGORY_MAP)
    # so the channel sounds intentional: economy videos always
    # use the same narrator, population always another, etc.
    # Categories without a mapping rotate deterministically
    # through the pool by stable hash of the category name --
    # same category, same voice, every time (no random
    # glitching between uploads), different categories sound
    # different.
    # -----------------------------------------------------

    @classmethod
    def _rotation_pool(cls) -> list:
        pool = parse_json_setting(
            getattr(settings, "VOICE_ROTATION_POOL", ""),
            cls.VOICE_ROTATION,
        )
        if not isinstance(pool, list) or not pool:
            return list(cls.VOICE_ROTATION)
        return [str(v) for v in pool if str(v).strip()]

    # -----------------------------------------------------
    # CATEGORY NORMALIZATION
    #
    # Production hands this method parent categories under a
    # dozen spellings: "AI Investment" / "AI Governance" (the
    # subcategory title from the topic engine), "Space /
    # Science" (provider title case), "World Data" (catalog
    # default) and "artificial_intelligence" (snake).  Both
    # sides are normalized (case, separators, whitespace) and
    # matching falls back to a plural-tolerant token run, so a
    # subcategory can no longer silently miss its parent's
    # voice and drop into the hash rotation.
    # -----------------------------------------------------

    _CATEGORY_SEPARATOR_RE = None

    @classmethod
    def normalize_category(cls, category) -> str:
        """Lowercase + collapse separators/whitespace.

        "AI Investment"          -> "ai investment"
        "Space / Science"        -> "space science"
        "Population_Demographics"-> "population demographics"
        """

        import re

        if cls._CATEGORY_SEPARATOR_RE is None:
            cls._CATEGORY_SEPARATOR_RE = re.compile(
                r"[^a-z0-9]+"
            )

        text = str(category or "").strip().lower()

        if not text:
            return ""

        return cls._CATEGORY_SEPARATOR_RE.sub(
            " ", text
        ).strip()

    @staticmethod
    def _category_tokens(normalized: str) -> list:
        """Tokens with a crude singular form (plural-tolerant)."""

        tokens = str(normalized or "").split()

        return [
            token[:-1]
            if len(token) > 3 and token.endswith("s")
            else token
            for token in tokens
        ]

    @classmethod
    def _category_mapping(cls) -> tuple:
        """(VOICE_CATEGORY_MAP, VOICE_CATEGORY_ALIASES) tables."""

        mapping = parse_json_setting(
            getattr(settings, "VOICE_CATEGORY_MAP", ""),
            {},
        )

        aliases = parse_json_setting(
            getattr(settings, "VOICE_CATEGORY_ALIASES", ""),
            {},
        )

        if not isinstance(mapping, dict):
            mapping = {}

        if not isinstance(aliases, dict):
            aliases = {}

        return mapping, aliases

    @classmethod
    def _match_normalized(cls, view: str, cat_tokens: list):
        """Match one normalized alias/key against the category.

        Returns "exact" or "contains" (whole-word token run), so
        "ai governance" reaches the AI parent via the alias "ai"
        while an unrelated word never matches by letter overlap.
        """

        view_tokens = cls._category_tokens(view)

        if not view_tokens:
            return None

        if view_tokens == cat_tokens:
            return "exact"

        smaller, larger = (
            (view_tokens, cat_tokens)
            if len(view_tokens) <= len(cat_tokens)
            else (cat_tokens, view_tokens)
        )

        span = len(smaller)

        for index in range(0, len(larger) - span + 1):
            if larger[index:index + span] == smaller:
                return "contains"

        return None

    @classmethod
    def resolve_category(cls, category) -> dict:
        """Resolve a raw category string to its parent mapping.

        Returns {"raw", "normalized", "key", "voice", "voices",
        "matched"}.  `key`/`voice`/`voices` are None/[] when
        nothing matched, in which case the caller's stable-hash
        rotation applies.
        """

        raw = str(category or "").strip()

        normalized = cls.normalize_category(raw)

        resolved = {
            "raw": raw,
            "normalized": normalized,
            "key": None,
            "voice": None,
            "voices": [],
            "matched": None,
        }

        if not normalized:
            return resolved

        mapping, aliases = cls._category_mapping()

        cat_tokens = cls._category_tokens(normalized)

        # Canonical keys first (authoritative spellings), then
        # the explicit alias table.
        candidates = [
            (cls.normalize_category(key), key, "key")
            for key in mapping
        ]

        candidates += [
            (cls.normalize_category(alias), key, "alias")
            for alias, key in aliases.items()
        ]

        best_exact = None
        best_contained = None

        for view, key, source in candidates:

            if not view:
                continue

            voice = cls._voice_value(
                mapping.get(key)
            )

            if not voice:
                # A partial VOICE_CATEGORY_MAP override (or an
                # alias pointing at a key that table dropped)
                # must not swallow the match -- keep scanning.
                continue

            hit = cls._match_normalized(view, cat_tokens)

            if hit == "exact" and best_exact is None:
                best_exact = (key, source, voice)

            elif hit == "contains" and best_contained is None:
                best_contained = (key, source, voice)

        chosen = best_exact or best_contained

        if chosen is None:
            return resolved

        key, source, voices = chosen

        resolved["key"] = key
        # "voice" stays the PRIMARY voice so every existing
        # caller keeps working; "voices" is the full rotation
        # pool for this category (PRIORITY 3).
        resolved["voices"] = list(voices)
        resolved["voice"] = voices[0]
        resolved["matched"] = (
            f"{source}:{cls.normalize_category(key)}"
        )

        return resolved

    @staticmethod
    def _voice_value(raw):
        """
        Normalize a VOICE_CATEGORY_MAP value into a list.

        Accepts BOTH shapes so existing config keeps working:
          "economy": "en-US-GuyNeural"          -> ["en-US-GuyNeural"]
          "defense": ["en-US-GuyNeural", "..."] -> ["en-US-GuyNeural", "..."]
        """
        if isinstance(raw, (list, tuple)):
            voices = [
                str(v).strip()
                for v in raw
                if str(v or "").strip()
            ]
        elif raw is not None and str(raw).strip():
            voices = [str(raw).strip()]
        else:
            voices = []

        # Deduplicate, preserving order.
        seen = set()
        unique = []
        for v in voices:
            if v not in seen:
                seen.add(v)
                unique.append(v)

        return unique

    @classmethod
    def _category_voice_pool(cls, category) -> list:
        """
        The full voice POOL configured for this category
        (PRIORITY 3), or [] when the category is unmapped.

        A pool longer than 1 is what removes the single-voice
        funnel: seven categories used to hard-map to
        en-US-GuyNeural, so 47% of published videos (55% of
        the most recent 20) sounded identical.
        """
        resolved = cls.resolve_category(category)

        return list(resolved.get("voices") or [])

    @classmethod
    def _category_voice(cls, category) -> str:
        """Deterministic per-category PRIMARY voice.

        1. Category resolution (normalized canonical key, then
           alias table, then plural-tolerant token match) wins.
        2. Otherwise stable-hash the category into the pool
           (identical for every video of that category).
        3. No category at all -> "" (caller falls back to the
           last-voice-avoiding rotation).
        """

        pool = cls._rotation_pool()

        if not pool:
            return cls.VOICE

        resolved = cls.resolve_category(category)

        if not resolved["normalized"]:
            return ""

        if resolved["voice"]:
            return resolved["voice"]

        # Stable hash: deterministic across processes/runs
        # (hash() is randomized per process -- never use it).
        import hashlib

        digest = int(
            hashlib.md5(
                resolved["normalized"].encode("utf-8")
            ).hexdigest(),
            16,
        )
        return pool[digest % len(pool)]

    # -----------------------------------------------------
    # INTRO HOOK ANTI-REPEAT STATE
    #
    # The previous video's hook line, persisted to disk so
    # pick_intro_line(last_line=...) can guarantee two
    # consecutive uploads never share the same opening
    # line (same pattern as comments.py's
    # posted_comments.json ledger).
    # -----------------------------------------------------
    INTRO_STATE_PATH = str(
        Path(__file__).resolve().parents[2]
        / "data"
        / "last_intro_line.json"
    )

    @classmethod
    def load_last_intro_line(cls) -> str:
        """Return the previous video's hook line ('' when none)."""
        try:
            with open(
                cls.INTRO_STATE_PATH,
                "r",
                encoding="utf-8",
            ) as handle:
                state = json.load(handle)
            return str(state.get("last_line") or "")
        except (OSError, ValueError):
            return ""

    @classmethod
    def save_last_intro_line(cls, line: str) -> None:
        """Persist this video's hook line for the next upload."""
        try:
            os.makedirs(
                os.path.dirname(cls.INTRO_STATE_PATH),
                exist_ok=True,
            )
            with open(
                cls.INTRO_STATE_PATH,
                "w",
                encoding="utf-8",
            ) as handle:
                json.dump(
                    {"last_line": str(line or "")},
                    handle,
                    indent=2,
                )
        except OSError:
            pass

    @classmethod
    def pick_intro_line(
        cls,
        topic_key: str = "",
        last_line: str = None,
    ) -> str:
        """One short human hook line before the data reveal.

        Chosen deterministically per video (stable hash of
        topic_key) so it varies across videos but never
        wobbles between reruns of the same video.  When the
        pick equals `last_line` (the previous video's hook,
        passed by the caller from history) it advances to the
        next pool entry so consecutive uploads never repeat.
        Empty pool -> None (hook disabled).
        """
        import hashlib

        pool = parse_json_setting(
            getattr(settings, "INTRO_LINE_POOL", ""),
            [],
        )
        if not isinstance(pool, list):
            return None
        pool = [str(x).strip() for x in pool if str(x).strip()]
        if not pool:
            return None

        key = str(topic_key or "").strip().lower()
        if key:
            digest = int(
                hashlib.md5(key.encode("utf-8")).hexdigest(), 16
            )
            index = digest % len(pool)
        else:
            index = 0

        line = pool[index]
        if (
            len(pool) > 1
            and last_line
            and line == str(last_line).strip()
        ):
            line = pool[(index + 1) % len(pool)]

        return line

    # -----------------------------------------------------
    # LAST-HOOK LEDGER (so consecutive uploads never repeat
    # the same hook back-to-back, even across separate
    # process runs).  Same tolerant JSON-file pattern as the
    # comment ledger in app.youtube.comments.
    # -----------------------------------------------------

    @classmethod
    def last_intro_hook(cls) -> Optional[str]:
        """Previous video's intro hook (None when unavailable)."""
        import json
        import os

        try:
            path = cls._hook_ledger_path()
            with open(path, "r", encoding="utf-8") as handle:
                value = json.load(handle)
            line = str((value or {}).get("last_hook") or "").strip()
            return line or None
        except Exception:
            return None

    @classmethod
    def remember_intro_hook(cls, line: str) -> None:
        """Persist this video's hook for the next run's guard."""
        import json
        import os

        try:
            path = cls._hook_ledger_path()
            os.makedirs(
                os.path.dirname(path), exist_ok=True
            )
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(
                    {"last_hook": str(line or "").strip()},
                    handle,
                )
        except Exception:
            # A ledger failure must never break a publish.
            pass

    @staticmethod
    def _hook_ledger_path() -> str:
        """data/last_intro_hook.json (next to history.db)."""
        import os

        try:
            base = os.path.dirname(
                str(settings.DB_PATH or "")
            )
            if base:
                return os.path.join(base, "last_intro_hook.json")
        except Exception:
            pass
        return os.path.join(
            "data", "last_intro_hook.json"
        )

    @classmethod
    def pick_voice(
        cls,
        last_voice: str = None,
        category: str = None,
        last_voices=None,
    ) -> str:
        """
        Choose the voice for this video.

        With a `category`, the mapping is deterministic
        (economy -> same narrator every time).  Without one,
        rotate randomly while avoiding an immediate repeat of
        `last_voice` (the previous video's voice from history).

        PRIORITY 3 -- category VOICE POOL rotation: a category
        may now map to SEVERAL voices.  When it does, the pick
        is the pool member that has gone longest without being
        used, judged against `last_voices` (the recent voice
        history, newest first, from the DB).  That gives three
        properties at once:
          * never repeats the immediately previous video,
          * cycles the whole pool, so a busy category cannot
            pile onto one narrator,
          * stays deterministic (no random glitching between
            uploads) for a given history.
        """
        pool = cls._rotation_pool()

        if not pool:
            return cls.VOICE

        category_pool = cls._category_voice_pool(category)

        if category_pool:

            if len(category_pool) == 1:
                return category_pool[0]

            # Rank by most recent use; unseen voices first.
            recent = [
                str(v).strip()
                for v in (last_voices or [])
                if str(v or "").strip()
            ]

            # Index of each voice's MOST RECENT use.  `recent`
            # is newest-first, so the FIRST occurrence wins --
            # a plain dict comprehension would keep the last
            # one and hand a frequently-used voice its OLDEST
            # position, which inverts the whole ranking.
            position = {}

            for index, voice in enumerate(recent):
                if voice not in position:
                    position[voice] = index

            # DESCENDING: index 0 is the MOST recent use, and an
            # unseen voice gets the sentinel high value, so
            # sorting descending puts the longest-unused member
            # first.  (Ascending returns the most recently used
            # voice and pins the category to one narrator.)
            return sorted(
                category_pool,
                key=lambda v: position.get(v, 10 ** 6),
                reverse=True,
            )[0]

        last = str(last_voice or "").strip()

        candidates = [
            v for v in pool
            if v != last
        ] or pool

        import random

        return random.choice(candidates)


    # Viral Shorts Pacing: Confident, crisp delivery that stops viewers
    # from swiping away. Never drop below +5% speed (sluggish delivery kills retention).
    PACING_PROFILES = {
        "energetic": {
            "rate": "+16%",
            "pitch": "+3Hz",
            "volume": "+2%",
        },
        "intense": {
            "rate": "+13%",
            "pitch": "+2Hz",
            "volume": "+4%",
        },
        "steady": {
            "rate": "+10%",
            "pitch": "+1Hz",
            "volume": "+1%",
        },
        "calm": {
            "rate": "+6%",
            "pitch": "+0Hz",
            "volume": "+0%",
        },
    }

    @staticmethod
    def _profile_for(pacing_hint) -> dict:
        """Map a scene's pacing_hint to a voice profile."""

        hint = str(pacing_hint or "").lower()

        if any(
            word in hint
            for word in ("fast", "quick", "rapid", "urgent")
        ):
            return TTSEngine.PACING_PROFILES[
                "energetic"
            ]

        if any(
            word in hint
            for word in (
                "dramatic",
                "tight",
                "finish",
                "reveal",
                "surprise",
                "climax",
            )
        ):
            return TTSEngine.PACING_PROFILES[
                "intense"
            ]

        if any(
            word in hint
            for word in ("slow", "calm")
        ):
            return TTSEngine.PACING_PROFILES[
                "calm"
            ]

        return TTSEngine.PACING_PROFILES["steady"]

    # -----------------------------------------------------
    # PAYOFF PACING (human-touch layer)
    #
    # Edge TTS does not accept raw SSML through Communicate,
    # so emphasis is delivered with punctuation: natural
    # spoken pauses around the payoff number via ellipses,
    # which Edge renders as real silence.  Jitter is added
    # so consecutive numbers never get identical gaps.
    # -----------------------------------------------------

    @staticmethod
    def _apply_payoff_pauses(text: str) -> str:
        """Wrap the first number in a scene's narration with
        short natural pauses (config: PAYOFF_PAUSE_MS_*)."""
        import random
        import re

        if not text:
            return text

        before = max(0, int(getattr(settings, "PAYOFF_PAUSE_MS_BEFORE", 0) or 0))
        after = max(0, int(getattr(settings, "PAYOFF_PAUSE_MS_AFTER", 0) or 0))
        if before == 0 and after == 0:
            return text

        match = re.search(r"\d[\d.%]*", text)
        if not match:
            return text

        # -------------------------------------------------
        # Edge TTS pause calibration (measured, Issue 1 fix):
        # every punctuation glyph Edge TTS renders -- comma,
        # period, ellipsis -- produces ~0.85-0.98s of dead air
        # regardless of intended length; there is no short-pause
        # glyph.  The old comment claimed commas rendered
        # ~0.2-0.3s but re-measurement shows commas actually
        # render ~0.86s, so even the "short" comma inserts
        # ~0.86s of silence.  With both BEFORE and AFTER non-zero,
        # each payoff number carries ~1.7s of dead air -- matching
        # the stop-start narration measured on the published
        # military-spending video.  Defaults are now 0 (see
        # config), so this is disabled unless env vars override.
        # When non-zero, the mapping below is kept for backward
        # compatibility but all three glyphs render approximately
        # equally long.
        #
        # DEAD-AIR RULES (still applied when non-zero):
        #   * the pause span is extended across glued
        #     prefix symbols (# $ EUR GBP ...) -- the beat
        #     goes before/after the whole token;
        #   * a glyph adjacent to EXISTING punctuation
        #     (whitespace-inspected: ". : ; ! ? , -- ...")
        #     is dropped -- natural punctuation already
        #     renders its own pause;
        #   * a glyph at the very start/end of the text is
        #     dropped (nothing to separate).
        # -------------------------------------------------

        def _pause_glyph(ms: int) -> str:
            if ms < 400:
                return ","
            if ms < 700:
                return "."
            return "..."

        _GLUED_PREFIX = "#$€£₹¥№§"
        # Whitespace-significant punctuation that already
        # produces its own Edge TTS pause when adjacent.
        _PAUSE_PUNCT = ".,!?;:…—–‑-)"

        start, end = match.span()

        # Extend the span left across glued symbols so the
        # pause wraps "#2" as a unit instead of splitting
        # it into "# , 2 .".
        while start > 0 and text[start - 1] in _GLUED_PREFIX:
            start -= 1

        # Nearest significant characters OUTSIDE the span,
        # skipping the spaces that surround it.
        prev_ch = ""
        scan = start - 1
        while scan >= 0 and text[scan].isspace():
            scan -= 1
        if scan >= 0:
            prev_ch = text[scan]

        next_ch = ""
        scan = end
        while scan < len(text) and text[scan].isspace():
            scan += 1
        if scan < len(text):
            next_ch = text[scan]

        parts = [text[:start].rstrip()]

        if (
            before > 0
            and prev_ch
            and prev_ch not in _PAUSE_PUNCT
        ):
            parts.append(_pause_glyph(before))

        parts.append(text[start:end].rstrip())

        if (
            after > 0
            and next_ch
            and next_ch not in _PAUSE_PUNCT
        ):
            parts.append(_pause_glyph(after))

        parts.append(text[end:].lstrip())

        return " ".join(
            part for part in parts if part
        )

    @staticmethod
    def _normalize_spoken_pauses(text: str) -> str:
        """Replace glyphs Edge TTS renders as LONG dead air.

        Measured on real renders: an em/en dash renders a
        ~0.85s hole and any ellipsis run renders ~0.85-0.95s.
        Both are replaced with a comma in the SPOKEN text only
        -- the displayed narration keeps its typography.  Note:
        Edge TTS renders commas at ~0.86s as well (not ~0.2-0.3s
        as once assumed), so this normalization does not shorten
        the pause -- it only prevents the dash/ellipsis from
        rendering as an even longer or inconsistent gap, and keeps
        the spoken text free of typographic clutter.  Decimal
        points are untouched (only dash characters and runs
        of 2+ dots are rewritten).
        """

        import re

        if not text:
            return text

        normalized = re.sub(r"[—–]", ", ", text)

        normalized = re.sub(
            r"\.{2,}|…",
            ", ",
            normalized,
        )

        return normalized


    @staticmethod
    async def _generate_audio(
        text: str,
        output_path: str,
        voice: str = None,
        profile: dict = None
    ):
        """Generate one MP3 using Edge TTS."""

        selected_voice = (
            voice
            or TTSEngine.VOICE
        )

        speech_settings = (
            profile
            or TTSEngine.PACING_PROFILES["steady"]
        )

        last_error = None
        for attempt in range(1, 4):
            try:
                communicate = edge_tts.Communicate(
                    TTSEngine._apply_payoff_pauses(
                        TTSEngine._normalize_spoken_pauses(text)
                    ),
                    selected_voice,
                    rate=speech_settings["rate"],
                    pitch=speech_settings["pitch"],
                    volume=speech_settings["volume"]
                )
                await communicate.save(output_path)
                if os.path.exists(output_path) and os.path.getsize(output_path) > 500:
                    last_error = None
                    break
            except Exception as e:
                last_error = e
                if attempt < 3:
                    await asyncio.sleep(1.2 * attempt)

        if last_error:
            raise last_error

        # -------------------------------------------------
        # EDGE TRIMS (trailing + leading)
        #
        # Trailing: Edge TTS leaves ~0.6-0.9s of trailing
        # silence on every clip.  Across 4-5 scenes that is
        # 3-4s of dead air that inflates the measured
        # narration length (and therefore the whole video).
        # Trim the tail to at most ~0.25s so scenes keep a
        # natural inter-scene beat without carrying filler
        # silence.
        #
        # Leading (published-video review, Issue 1): Edge TTS
        # also opens every clip with ~0.18s of silence which
        # was never trimmed.  Stacked on the previous scene's
        # 0.25s kept tail, every scene boundary carried
        # ~0.4s of dead air.  The head is trimmed to ~0.08s
        # so the seam lands at a natural ~0.33s sentence
        # gap.  Both trims are non-fatal: a failed trim
        # keeps the original clip.
        # -------------------------------------------------

        TTSEngine._trim_clip_edges(
            output_path
        )

    @staticmethod
    def _trim_clip_edges(audio_path) -> None:

        TTSEngine._trim_trailing_silence(audio_path)

        TTSEngine._trim_leading_silence(audio_path)

        # MID-CLIP pauses (dead-air fix, Issue 1).  The two edge
        # trims above only reach the FIRST and LAST silence in the
        # clip, so Edge TTS's ~0.85s sentence pauses in the middle
        # of a multi-sentence scene shipped untouched: the fresh
        # military-spending render measured 0.84s @1.21s and 0.94s
        # @6.30s INSIDE scene 1 (2 of the 4 gaps still present in
        # the final video).  Runs LAST so it can only ever see
        # interior pauses -- the inter-scene seam is already sized
        # by the edge trims above.  Non-fatal.
        TTSEngine._compress_internal_pauses(audio_path)

    @staticmethod
    def _trim_leading_silence(
        audio_path,
        keep_seconds: float = 0.08,
    ) -> None:
        """Trim leading silence from an MP3 to <= ~keep_seconds.

        silenceremove with start_periods=1 drops everything
        before the first sound above the threshold, keeping
        `keep_seconds` of it as a tiny natural attack.  A
        0.08s head plus the previous scene's 0.25s kept tail
        gives a ~0.33s sentence beat at concat seams instead
        of the ~0.4s+ dead air that shipped.  Non-fatal.
        """

        import subprocess

        source = str(audio_path)

        trimmed = source + ".leadtrim.mp3"

        command = [
            "ffmpeg", "-y",
            "-i", source,
            "-af",
            (
                "silenceremove=start_periods=1:"
                "start_threshold=-45dB:"
                f"start_duration={keep_seconds}"
            ),
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            trimmed,
        ]

        try:

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if (
                result.returncode == 0
                and os.path.exists(trimmed)
                and os.path.getsize(trimmed) > 0
            ):
                os.replace(trimmed, source)

            else:
                try:
                    os.remove(trimmed)
                except OSError:
                    pass

        except Exception:

            try:
                os.remove(trimmed)
            except OSError:
                pass


    @staticmethod
    def _trim_trailing_silence(audio_path) -> None:
        """Trim trailing silence from an MP3 to <= ~0.05s.

        ISSUE 1 fix (published-video review): the old start_duration=0.25
        kept ~0.25s of trailing silence on EVERY scene clip.  Stacked
        across scene boundaries that was ~0.33s per seam, and on the LAST
        scene it became the audible 1.0-1.9s dead-air hole at the end of
        the published video.  Lowered start_duration to 0.02 so silenceremove
        removes the vast majority of trailing silence; a tiny 0.02s residue
        is inaudible and avoids cutting into the final syllable's release.
        """

        import subprocess

        source = str(audio_path)

        trimmed = source + ".trim.mp3"

        command = [
            "ffmpeg", "-y",
            "-i", source,
            "-af",
            (
                "areverse,"
                "silenceremove=start_periods=1:"
                "start_threshold=-45dB:"
                "start_duration=0.02,"
                "areverse"
            ),
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            trimmed,
        ]

        try:

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if (
                result.returncode == 0
                and os.path.exists(trimmed)
                and os.path.getsize(trimmed) > 0
            ):
                os.replace(trimmed, source)

            else:
                try:
                    os.remove(trimmed)
                except OSError:
                    pass

        except Exception:
            try:
                os.remove(trimmed)
            except OSError:
                pass

    @staticmethod
    def _compress_internal_pauses(
        audio_path,
        detect_seconds: float = None,
        keep_seconds: float = None,
    ) -> None:
        """Compress MID-clip sentence pauses to ~(detect + keep).

        Edge TTS turns every punctuation glyph into ~0.85-0.98s of
        silence and offers no short-pause glyph.  The two edge trims
        next door only reach the leading/trailing silence, so a
        two-sentence scene kept both mid-clip pauses: the fresh
        military-spending render measured 0.84s @1.21s and 0.94s
        @6.30s INSIDE scene_1.mp3 -- the broken, stop-start narration
        the review reported.

        silenceremove with stop_periods=-1 removes EVERY silence
        longer than `detect_seconds` and leaves `keep_seconds` behind,
        so the residual pause is ~ (detect + keep).  MEASURED on the
        real rendered scene_1.mp3 (9.55s, two pauses, -40dB):

          detect  keep   output   gaps @0.25s   speech delta
          0.15    0.05   8.16s       0           -0.02s
          0.20    0.05   8.26s       2           -0.02s
          0.30    0.05   8.46s       2           -0.02s

        0.15/0.05 is the default: zero gaps at the 0.25s detection
        floor while keeping a natural ~0.20s sentence beat, and the
        speech delta proves ONLY silence is removed (no clipped
        words).  Config-driven via TTS_INTERNAL_PAUSE_DETECT_MS /
        _KEEP_MS, switchable off with TTS_INTERNAL_PAUSE_TRIM.

        NOTE: if PAYOFF_PAUSE_MS_BEFORE/AFTER are ever set non-zero
        again (they default to 0 precisely because those punctuation
        pauses were the dead air), that deliberate payoff beat is
        compressed to the same ~0.20s -- raise the detect/keep
        thresholds or disable the trim if a longer beat is wanted.

        Non-fatal: any failure keeps the original clip.
        """

        import subprocess

        leftover = str(audio_path) + ".pausetrim.mp3"

        try:

            if not getattr(
                settings, "TTS_INTERNAL_PAUSE_TRIM", True
            ):
                return

            if detect_seconds is None:

                detect_seconds = (
                    int(
                        getattr(
                            settings,
                            "TTS_INTERNAL_PAUSE_DETECT_MS",
                            150,
                        )
                        or 0
                    )
                    / 1000.0
                )

            if keep_seconds is None:

                keep_seconds = (
                    int(
                        getattr(
                            settings,
                            "TTS_INTERNAL_PAUSE_KEEP_MS",
                            50,
                        )
                        or 0
                    )
                    / 1000.0
                )

            # Guard rails: below 0.10s the filter starts eating the
            # natural release of plosives; above 0.60s it no longer
            # reaches the ~0.85s Edge punctuation pause at all.
            detect_seconds = max(
                0.10, min(0.60, float(detect_seconds))
            )

            keep_seconds = max(
                0.0, min(detect_seconds, float(keep_seconds))
            )

            command = [
                "ffmpeg", "-y",
                "-i", str(audio_path),
                "-af",
                (
                    "silenceremove=stop_periods=-1:"
                    f"stop_duration={detect_seconds}:"
                    # -40dB rather than the -45dB the edge trims use:
                    # the filter must remove exactly what a -40dB
                    # dead-air check reports, otherwise residual
                    # "silence" between -45 and -40dB survives and
                    # still reads as a gap in the audit.
                    "stop_threshold=-40dB:"
                    f"stop_silence={keep_seconds}"
                ),
                "-c:a", "libmp3lame",
                "-b:a", "128k",
                leftover,
            ]

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if (
                result.returncode == 0
                and os.path.exists(leftover)
                and os.path.getsize(leftover) > 0
            ):
                os.replace(leftover, str(audio_path))

            else:
                try:
                    os.remove(leftover)
                except OSError:
                    pass

        except Exception:

            try:
                os.remove(leftover)
            except OSError:
                pass

    @staticmethod
    def _llm_shorten_over_budget(
        script,
        audio_data: list,
        planned_total: float,
        voice: str = None,
    ) -> bool:
        """CUT WORDS, never push speed (intelligibility, Issue 1).

        Once the rate-bump ceiling is spent, the next lever is a
        SHORTER script: the LLM tighten pass rewrites the
        narration with the same facts in fewer words, and the
        affected scenes are re-synthesized at their ORIGINAL base
        rate (no bump at all).  Returns True when at least one
        scene was re-synthesized and got shorter.

        Sharing the LLM path with script generation means the
        rewrite preserves every fact/year/number (see
        ScriptEngine._tighten_narration).
        """

        try:

            from app.ai.script import ScriptEngine

        except Exception as exc:

            print(
                "  ✂️ Word-shortening unavailable "
                f"({type(exc).__name__}: {exc})."
            )

            return False

        before = {
            int(item["scene_number"]): str(
                item.get("narration") or ""
            )
            for item in audio_data
        }

        if not before:
            return False

        try:

            changed = ScriptEngine._tighten_narration(
                script,
                int(round(planned_total)),
            )

        except Exception as exc:

            print(
                "  ✂️ Word-shortening failed "
                f"({type(exc).__name__}: {exc})."
            )

            return False

        if not changed:

            print(
                "  ✂️ Word-shortening returned no change; "
                "escalating."
            )

            return False

        shortened = []

        for item in audio_data:

            number = int(item["scene_number"])

            new_text = ""

            for scene in script.scenes:

                if int(scene.scene_number) == number:

                    new_text = str(scene.narration or "").strip()

                    break

            old_text = before.get(number, "")

            if not new_text or new_text == old_text:

                continue

            item["narration"] = new_text

            hook = str(item.get("hook_prefix") or "").strip()

            item["spoken_text"] = (
                f"{hook} {new_text}".strip()
                if hook
                else new_text
            )

            # Re-synthesize at the ORIGINAL base pacing profile
            # -- the bump is deliberately NOT re-applied, so the
            # delivery sounds the same as every on-budget scene.
            asyncio.run(
                TTSEngine._generate_audio(
                    item["spoken_text"],
                    item["audio_path"],
                    voice or TTSEngine.VOICE,
                    item["pacing_profile"],
                )
            )

            TTSEngine._trim_clip_edges(item["audio_path"])

            item["actual_duration"] = (
                TTSEngine._get_audio_duration(item["audio_path"])
            )

            shortened.append(number)

            print(
                f"  ✂️ Scene {number} rewritten shorter "
                f"({len(old_text.split())} -> "
                f"{len(new_text.split())} words) and "
                f"re-spoken at base rate; now "
                f"{item['actual_duration']:.2f}s."
            )

        return bool(shortened)

    @staticmethod
    def _shorten_then_trim(
        script,
        audio_data: list,
        planned_total: float,
        voice: str = None,
    ) -> float:
        """Escalation when the speed ceiling is spent.

        Speed is OFF the table (intelligibility).  Instead:
          0. rewrite the narration with FEWER WORDS via the LLM
             tighten pass and re-speak it at the base rate
             (preferred: keeps every scene and every fact);
          1. drop whole scenes, shortest narration first
             (scene 1 = the hook is never dropped), then
             re-time the surviving scenes across the
             planned total;
          2. if still over, time-compress the LAST scene
             with ffmpeg atempo (pitch-preserving, capped
             at 1.12x -- speech stays intelligible).

        Returns the measured narration total afterwards.
        """

        def _measured() -> float:

            return sum(
                item["actual_duration"]
                for item in audio_data
            )

        measured_total = _measured()

        print(
            "✂️ Speed ceiling reached and narration "
            f"still {measured_total:.2f}s vs "
            f"{planned_total:.2f}s plan - trying "
            "WORD-SHORTENING first (speed stays fixed)."
        )

        # --------------------------------------------------
        # STEP 0 -- fewer words at the same speed.
        # --------------------------------------------------

        if TTSEngine._llm_shorten_over_budget(
            script,
            audio_data,
            planned_total,
            voice=voice,
        ):

            measured_total = _measured()

            print(
                "  ✂️ After word-shortening: "
                f"{measured_total:.2f}s (planned "
                f"{planned_total:.2f}s)."
            )

        if measured_total <= planned_total + 1.0:

            return measured_total

        # --------------------------------------------------
        # STEP 1 -- still too long: drop whole scenes.
        # --------------------------------------------------

        droppable = sorted(
            (
                item
                for item in audio_data
                if int(item["scene_number"]) > 1
            ),
            key=lambda item: (
                len(str(item.get("narration") or ""))
            ),
        )

        for item in droppable:

            if measured_total <= planned_total + 1.0:
                break

            if len(audio_data) <= 1:
                break

            audio_data.remove(item)

            try:
                os.remove(item["audio_path"])
            except OSError:
                pass

            measured_total = _measured()

            print(
                f"  ✂️ Dropped scene "
                f"{item['scene_number']} "
                f"({item['actual_duration']:.2f}s); "
                f"narration now "
                f"{measured_total:.2f}s."
            )

        # Re-time the surviving scenes so the visual
        # timeline keeps its planned length.

        kept_durations = []

        for item in audio_data:

            scene = next(
                (
                    s for s in script.scenes
                    if int(s.scene_number)
                    == int(item["scene_number"])
                ),
                None,
            )

            kept_durations.append(
                (
                    scene,
                    item,
                    float(scene.duration)
                    if scene is not None
                    else 0.0,
                )
            )

        kept_total = sum(
            duration
            for _, _, duration in kept_durations
        )

        if kept_total > 0:

            scale = planned_total / kept_total

            for scene, item, duration in kept_durations:

                if scene is None:
                    continue

                scene.duration = round(
                    duration * scale,
                    2,
                )

                item["script_duration"] = float(
                    scene.duration
                )

        measured_total = _measured()

        # Absolute last resort: time-compress the overhang
        # with atempo (preserves pitch; a rate bump instead
        # resynthesizes the whole delivery faster).  Capped
        # at 1.12x so speech stays intelligible; beyond the
        # cap the narration simply runs past the plan
        # rather than sounding rushed.

        overhang = measured_total - planned_total - 1.0

        if (
            overhang > 0.5
            and audio_data
            and planned_total > 0
        ):

            last = audio_data[-1]

            target_length = max(
                0.5,
                last["actual_duration"] - overhang,
            )

            factor = min(
                1.12,
                max(
                    1.0,
                    last["actual_duration"]
                    / target_length,
                ),
            )

            if factor > 1.005:

                compressed = (
                    last["audio_path"] + ".ts.mp3"
                )

                result = subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-i", last["audio_path"],
                        "-af",
                        f"atempo={factor:.4f}",
                        "-c:a", "libmp3lame",
                        "-b:a", "128k",
                        compressed,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                if (
                    result.returncode == 0
                    and os.path.exists(compressed)
                ):

                    os.replace(
                        compressed,
                        last["audio_path"],
                    )

                    last["actual_duration"] = (
                        TTSEngine
                        ._get_audio_duration(
                            last["audio_path"]
                        )
                    )

                    measured_total = _measured()

                    print(
                        f"  ✂️ Last scene time-compressed "
                        f"x{factor:.3f} (pitch preserved); "
                        f"narration now "
                        f"{measured_total:.2f}s."
                    )

        print(
            f"⏱️ Narration after shorten-then-trim: "
            f"{measured_total:.2f}s (planned "
            f"{planned_total:.2f}s)."
        )

        return measured_total

    @staticmethod
    def _add_rate_pct(rate: str, bump_pct: int) -> str:
        """Add a percentage bump to an Edge TTS rate string.

        "+5%" + 12 -> "+17%"; unparseable input -> "+12%".
        The result is clamped so the TOTAL delivery speed
        (base profile rate + enforcement bump) never exceeds
        settings.TTS_MAX_TOTAL_RATE_PCT -- the intelligibility
        guarantee.  The old code stacked an unbounded bump on
        top of the base profile (+14% energetic + 45% bump =
        ~+59% shipped, measured 169 wpm on the published
        esports video -- unintelligible).
        """

        import re

        match = re.search(
            r"([+-]?\d+)%",
            str(rate or ""),
        )

        base = (
            int(match.group(1))
            if match
            else 0
        )

        total = base + int(bump_pct)

        # Intelligibility ceiling on the TOTAL speed (base
        # profile rate + bump), not the bump alone.

        try:
            from app.config import settings as _settings

            total_ceiling = int(
                getattr(
                    _settings,
                    "TTS_MAX_TOTAL_RATE_PCT",
                    25,
                )
                or 25
            )

        except Exception:

            total_ceiling = 25

        total = max(-20, min(total_ceiling, total))

        sign = "+" if total >= 0 else ""

        return f"{sign}{total}%"

    @staticmethod
    def _get_audio_duration(
        audio_path: str
    ) -> float:
        """
        Get the REAL duration of an audio file
        using ffprobe.

        This is important because the duration written
        in the AI script is not necessarily the actual
        TTS duration.
        """

        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Could not determine audio duration:\n"
                f"{result.stderr}"
            )

        try:
            return float(
                result.stdout.strip()
            )
        except ValueError:
            raise RuntimeError(
                f"Invalid audio duration returned "
                f"for: {audio_path}"
            )

    @staticmethod
    def generate_narration(
        script,
        output_dir: str,
        voice: str = None,
        intro_line: str = None,
    ):
        """
        Generate one MP3 per scene.

        IMPORTANT:
        The returned duration is the REAL duration
        of the generated MP3, not the duration requested
        by the AI script.

        `voice` lets the caller rotate voices across videos
        (see TTSEngine.pick_voice); None falls back to the
        default VOICE, preserving the old behavior.

        `intro_line` (human-touch layer) is a short spoken
        hook prepended to the FIRST scene only, before the
        data reveal.  None/empty leaves scene 1 untouched.
        """

        os.makedirs(
            output_dir,
            exist_ok=True
        )

        audio_data = []

        print(
            "🎙️ Generating voiceover via Edge TTS..."
        )

        for scene in script.scenes:

            narration = scene.narration

            # The scene-1 spoken-hook prefix is kept so a later
            # re-synthesis (LLM shorten / enforcement) can rebuild
            # the exact same spoken text instead of guessing it.
            hook_prefix = ""

            # HUMAN-TOUCH: short hook line ahead of the first
            # scene's narration (config: INTRO_LINE_POOL).
            if (
                intro_line
                and scene.scene_number == getattr(
                    script.scenes[0], "scene_number", 1
                )
                and intro_line.strip()
                and intro_line.strip() not in narration
            ):
                hook_prefix = intro_line.strip()

                narration = (
                    hook_prefix + " " + narration
                )
                print(
                    f"  [HOOK] Scene {scene.scene_number}: "
                    f"\"{intro_line.strip()}\""
                )

            audio_path = os.path.join(
                output_dir,
                f"scene_{scene.scene_number}.mp3"
            )

            # ---------------------------------------------
            # Generate audio
            # ---------------------------------------------

            pacing_profile = TTSEngine._profile_for(
                getattr(scene, "pacing_hint", "")
            )

            asyncio.run(
                TTSEngine._generate_audio(
                    narration,
                    audio_path,
                    voice or TTSEngine.VOICE,
                    pacing_profile
                )
            )

            # ---------------------------------------------
            # Verify file exists
            # ---------------------------------------------

            if not os.path.exists(
                audio_path
            ):
                raise RuntimeError(
                    f"TTS failed to create: "
                    f"{audio_path}"
                )

            # ---------------------------------------------
            # Measure REAL duration
            # ---------------------------------------------

            actual_duration = (
                TTSEngine
                ._get_audio_duration(
                    audio_path
                )
            )

            requested_duration = float(
                scene.duration
            )

            difference = (
                actual_duration
                - requested_duration
            )

            print(
                f"  -> Scene "
                f"{scene.scene_number}: "
                f"{actual_duration:.2f}s "
                f"(script: "
                f"{requested_duration:.2f}s, "
                f"difference: "
                f"{difference:+.2f}s)"
            )

            # ---------------------------------------------
            # Store timing information
            # ---------------------------------------------

            audio_data.append(
                {
                    "scene_number": scene.scene_number,
                    "audio_path": audio_path,
                    "text_overlay": scene.text_overlay,
                    "visual_description": scene.visual_description,
                    "narration": scene.narration,

                    # Exact text that was synthesized (hook
                    # already prepended for scene 1) -- needed
                    # by the duration-enforcement re-synthesis.
                    "spoken_text": narration,

                    # The spoken-hook prefix alone (scene 1 only;
                    # "" elsewhere).  A later LLM word-shortening
                    # rewrite must rebuild spoken_text as
                    # hook_prefix + shortened narration, so the
                    # hook is never lost or duplicated.
                    "hook_prefix": hook_prefix,

                    # Pacing profile used for this scene.
                    "pacing_profile": pacing_profile,

                    # Requested by AI
                    "script_duration": requested_duration,

                    # REAL TTS duration
                    "actual_duration": actual_duration
                }
            )

        # ---------------------------------------------
        # DURATION ENFORCEMENT (band guard)
        #
        # The measured narration length is the visual
        # timeline's source of truth, so an over-long
        # narration stretches the whole video past the
        # duration band (an "18s" script once rendered at
        # 49s because the TTS ran 47s).  When the measured
        # total exceeds the planned duration, re-synthesize
        # the over-budget scenes with a computed rate bump.
        #
        # INTELLIGIBILITY (published-video review, Issue 1):
        # the old single pass hit +45% ADDED on top of the
        # pacing profile's own base rate -- measured 169 wpm
        # shipped (natural 110) -- and a viewer could not
        # follow it.  Now:
        #   * the bump is capped by TTS_MAX_RATE_BUMP_PCT
        #     (15) AND by TTS_MAX_TOTAL_RATE_PCT (25) on the
        #     combined base+bump speed (see _add_rate_pct);
        #   * up to TTS_ENFORCEMENT_MAX_PASSES passes run
        #     (the old single pass left the esports video at
        #     31.1s of narration vs a 24s plan);
        #   * when the ceiling is reached and the narration
        #     is STILL over budget, escalation is SHORTEN-
        #     THEN-TRIM below, never more speed.
        # ---------------------------------------------

        planned_total = float(
            getattr(script, "total_duration", 0) or 0
        )

        max_passes = max(
            1,
            int(
                getattr(
                    settings,
                    "TTS_ENFORCEMENT_MAX_PASSES",
                    2,
                )
                or 2
            ),
        )

        def _measured():
            return sum(
                item["actual_duration"]
                for item in audio_data
            )

        measured_total = _measured()

        if planned_total > 0:

            for pass_number in range(1, max_passes + 1):

                if measured_total <= planned_total + 1.0:
                    break

                needed_pct = int(
                    round(
                        (
                            measured_total / planned_total
                            - 1.0
                        )
                        * 100
                    )
                )

                max_bump = max(
                    5,
                    int(
                        getattr(
                            settings,
                            "TTS_MAX_RATE_BUMP_PCT",
                            15,
                        )
                        or 15
                    ),
                )

                bump = max(3, min(max_bump, needed_pct))

                print(
                    f"⏱️ Narration {measured_total:.2f}s exceeds the "
                    f"{planned_total:.2f}s plan - re-synthesizing "
                    f"over-budget scenes at +{bump}% rate "
                    f"(pass {pass_number}/{max_passes}, "
                    f"speed ceiling honored)."
                )

                for item in audio_data:

                    scene = next(
                        (
                            s for s in script.scenes
                            if int(s.scene_number)
                            == int(item["scene_number"])
                        ),
                        None,
                    )

                    if scene is None:
                        continue

                    # Only scenes over their own budget are
                    # sped up; on-budget scenes keep their
                    # natural pace.
                    if item["actual_duration"] <= (
                        float(scene.duration) + 0.35
                    ):
                        continue

                    faster_profile = dict(
                        item["pacing_profile"]
                    )

                    faster_profile["rate"] = (
                        TTSEngine._add_rate_pct(
                            item["pacing_profile"]["rate"],
                            bump,
                        )
                    )

                    asyncio.run(
                        TTSEngine._generate_audio(
                            item["spoken_text"],
                            item["audio_path"],
                            voice or TTSEngine.VOICE,
                            faster_profile,
                        )
                    )

                    item["actual_duration"] = (
                        TTSEngine._get_audio_duration(
                            item["audio_path"]
                        )
                    )

                measured_total = _measured()

                print(
                    f"⏱️ Narration after enforcement pass "
                    f"{pass_number}: {measured_total:.2f}s "
                    f"(planned {planned_total:.2f}s)."
                )

            # ---------------------------------------------
            # SHORTEN-THEN-TRIM ESCALATION (see above)
            # ---------------------------------------------

            if measured_total > planned_total + 1.0:

                measured_total = (
                    TTSEngine._shorten_then_trim(
                        script,
                        audio_data,
                        planned_total,
                    )
                )

        # ---------------------------------------------
        # Total duration
        # ---------------------------------------------

        total_audio_duration = sum(
            item["actual_duration"]
            for item in audio_data
        )

        requested_total_duration = sum(
            item["script_duration"]
            for item in audio_data
        )

        print(
            "\n🎙️ Audio timing report:"
        )

        print(
            f"  Script duration: "
            f"{requested_total_duration:.2f}s"
        )

        print(
            f"  Actual TTS duration: "
            f"{total_audio_duration:.2f}s"
        )

        print(
            f"  Difference: "
            f"{total_audio_duration - requested_total_duration:+.2f}s"
        )

        # ---------------------------------------------
        # Add timeline information
        # ---------------------------------------------

        current_time = 0.0

        for item in audio_data:

            item["start_time"] = (
                current_time
            )

            current_time += (
                item["actual_duration"]
            )

            item["end_time"] = (
                current_time
            )

        print(
            f"  Final narration length: "
            f"{current_time:.2f}s"
        )

        return audio_data
