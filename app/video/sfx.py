"""Rotating synthesized sound-effect cues (intro ding / outro chime).

PRIORITY 1 -- sound effects had ZERO variation: one fixed
intro_ding.wav was reused in every published video and the
outro was the same two fixed synthesized notes every time.

This module generates a small FAMILY of brand cues with the
same pure-numpy approach the original single ding used (no
external assets), and picks one per video so consecutive
uploads never sound identical.

Design mirrors TTSEngine.pick_intro_line():
  * a category map (config: SFX_CATEGORY_VARIANTS) biases a
    category toward particular variants, so defense never
    randomly sounds like sports;
  * a stable hash of the topic key spreads the rest;
  * last-used tracking (data/last_sfx.json, the same ledger
    pattern as last_intro_hook.json) advances the pick so two
    consecutive videos never reuse the same cue.

Every generator is idempotent: a variant is only re-synthesized
when its file is missing or force=True.
"""

import json
import os
import wave
from pathlib import Path

import numpy as np

from app.config import parse_json_setting, settings


ASSETS_SFX_DIR = (
    Path(__file__).resolve().parents[2] / "assets" / "sfx"
)

DING_SAMPLE_RATE = 44100
CHIME_SAMPLE_RATE = 24000

# ---------------------------------------------------------
# DING VARIANTS
#
# index 0 is the ORIGINAL cue, kept under its historical
# filename so enabling rotation never changes the sound a
# viewer already knows.  The rest differ in register, glide
# direction and decay so they read as distinct brand stings
# rather than pitch-shifts of one another.
# ---------------------------------------------------------

DING_VARIANTS = (
    {
        "name": "classic",
        "start_hz": 880.0,
        "end_hz": 523.0,
        "decay": 3.2,
        "duration_s": 0.75,
    },
    {
        "name": "high",
        "start_hz": 1174.7,
        "end_hz": 880.0,
        "decay": 2.6,
        "duration_s": 0.62,
    },
    {
        "name": "low",
        "start_hz": 659.3,
        "end_hz": 440.0,
        "decay": 3.8,
        "duration_s": 0.88,
    },
    {
        "name": "bright",
        "start_hz": 987.8,
        "end_hz": 1244.5,
        "decay": 4.4,
        "duration_s": 0.55,
    },
)

# ---------------------------------------------------------
# CHIME VARIANTS
#
# Each entry is a note sequence.  DEAD-AIR CONSTRAINT: the
# renderer divides OUTRO_DURATION_S by len(notes), so every
# variant -- including the 3-note one -- rings through the
# WHOLE outro card.  Never add a variant whose notes finish
# early or the measured 0.67s silent tail returns.
# ---------------------------------------------------------

CHIME_VARIANTS = (
    {
        "name": "e5_b4",
        "notes": (659.26, 493.88),
    },
    {
        "name": "c5_g4",
        "notes": (523.25, 392.00),
    },
    {
        "name": "g5_d5_b4",
        "notes": (783.99, 587.33, 493.88),
    },
)

# ---------------------------------------------------------
# ROTATION STATE  (mirrors TTSEngine's intro-hook ledger)
# ---------------------------------------------------------

_SFX_STATE_PATH = str(
    Path(__file__).resolve().parents[2]
    / "data"
    / "last_sfx.json"
)


def _state_path() -> str:

    try:
        base = os.path.dirname(
            str(settings.DB_PATH or "")
        )
        if base:
            return os.path.join(base, "last_sfx.json")
    except Exception:
        pass

    return _SFX_STATE_PATH


def load_last_sfx() -> dict:

    try:
        with open(
            _state_path(), "r", encoding="utf-8"
        ) as handle:
            value = json.load(handle)
        if isinstance(value, dict):
            return value
    except Exception:
        pass

    return {}


def remember_sfx(ding_variant, chime_variant) -> None:

    try:
        path = _state_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "last_ding_variant": int(ding_variant),
                    "last_chime_variant": int(chime_variant),
                },
                handle,
            )
    except Exception:
        # A ledger failure must never break a publish.
        pass


def _last_used(kind: str, total: int):

    value = load_last_sfx().get(
        f"last_{kind}_variant"
    )

    try:
        index = int(value)
    except (TypeError, ValueError):
        return None

    if 0 <= index < total:
        return index

    return None


# ---------------------------------------------------------
# CATEGORY BIAS
# ---------------------------------------------------------

def _category_variants(category) -> list:

    mapping = parse_json_setting(
        getattr(settings, "SFX_CATEGORY_VARIANTS", ""),
        {},
    )

    if not isinstance(mapping, dict):
        return list(range(len(DING_VARIANTS)))

    text = str(category or "").strip().lower()

    if not text:
        return list(range(len(DING_VARIANTS)))

    for key, value in mapping.items():
        if str(key).strip().lower() != text:
            continue
        if isinstance(value, (list, tuple)) and value:
            return [
                int(v)
                for v in value
                if str(v).isdigit()
                and 0 <= int(v) < len(DING_VARIANTS)
            ] or list(range(len(DING_VARIANTS)))

    return list(range(len(DING_VARIANTS)))


def _pick(topic_key, category, last_variant, total) -> int:

    allowed = [
        v for v in _category_variants(category)
        if 0 <= v < total
    ] or list(range(total))

    import hashlib

    key = str(topic_key or "").strip().lower()

    if key:
        digest = int(
            hashlib.md5(
                key.encode("utf-8")
            ).hexdigest(),
            16,
        )
    else:
        digest = 0

    index = allowed[digest % len(allowed)]

    # Never repeat the previous video's cue.
    if index == last_variant and len(allowed) > 1:
        position = allowed.index(index)
        index = allowed[(position + 1) % len(allowed)]

    return index


def pick_ding_variant(
    topic_key: str = "",
    category: str = None,
    last_variant: int = None,
) -> int:

    """Intro-ding variant index for this video."""

    if last_variant is None:
        last_variant = _last_used(
            "ding", len(DING_VARIANTS)
        )

    return _pick(
        topic_key,
        category,
        last_variant,
        len(DING_VARIANTS),
    )


def pick_chime_variant(
    topic_key: str = "",
    category: str = None,
    last_variant: int = None,
) -> int:

    """Outro-chime variant index for this video."""

    if last_variant is None:
        last_variant = _last_used(
            "chime", len(CHIME_VARIANTS)
        )

    return _pick(
        topic_key,
        category,
        last_variant,
        len(CHIME_VARIANTS),
    )


# ---------------------------------------------------------
# SYNTHESIS
# ---------------------------------------------------------

def ding_path(variant: int) -> Path:

    index = int(variant) % len(DING_VARIANTS)

    if index == 0:
        # Historical filename, kept so existing installs and
        # any already-rendered assets keep working.
        return ASSETS_SFX_DIR / "intro_ding.wav"

    return ASSETS_SFX_DIR / f"intro_ding_{index}.wav"


def synthesize_ding_variant(
    variant: int,
    force: bool = False,
) -> Path | None:

    """
    Write one intro-ding variant to assets/sfx/.

    Idempotent: skips when the file already exists unless
    force=True.  Returns the path, or None on failure (the
    caller degrades to an unbranded video).
    """

    try:

        spec = DING_VARIANTS[int(variant) % len(DING_VARIANTS)]
        target = ding_path(variant)

        if not force and target.exists():
            return target

        ASSETS_SFX_DIR.mkdir(
            parents=True, exist_ok=True
        )

        sample_rate = DING_SAMPLE_RATE
        duration = float(spec["duration_s"])
        n_samples = int(sample_rate * duration)

        t = np.linspace(
            0.0, duration, n_samples, endpoint=False
        )

        start_hz = float(spec["start_hz"])
        end_hz = float(spec["end_hz"])

        # Exponential glide start -> end (rises when end > start).
        freq = start_hz * (
            end_hz / start_hz
        ) ** (t / duration)

        phase = 2.0 * np.pi * np.cumsum(freq) / sample_rate
        tone = np.sin(phase)

        envelope = np.exp(
            -float(spec["decay"]) * t / duration
        )

        samples = tone * envelope

        # 5ms linear fade-in (avoid a click at t=0).
        fade_in = int(sample_rate * 0.005)
        samples[:fade_in] *= np.linspace(
            0.0, 1.0, fade_in, endpoint=False
        )

        pcm = (samples * 32767.0).astype(np.int16)

        with wave.open(str(target), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(pcm.tobytes())

        return target

    except Exception as error:

        print(
            f"⚠️ Ding variant {variant} synthesis failed "
            f"({type(error).__name__}: {error})."
        )

        return None


def synthesize_all_dings(force: bool = False) -> list:

    """Generate every ding variant; returns the paths built."""

    built = []

    for index in range(len(DING_VARIANTS)):
        path = synthesize_ding_variant(index, force)
        if path:
            built.append(path)

    return built


def chime_notes(variant: int) -> tuple:

    spec = CHIME_VARIANTS[int(variant) % len(CHIME_VARIANTS)]

    return tuple(spec["notes"])


def describe_ding(variant: int) -> str:

    index = int(variant) % len(DING_VARIANTS)
    spec = DING_VARIANTS[index]

    return (
        f"{index} ({spec['name']}, "
        f"{spec['start_hz']:.0f}->{spec['end_hz']:.0f} Hz)"
    )


def describe_chime(variant: int) -> str:

    index = int(variant) % len(CHIME_VARIANTS)
    spec = CHIME_VARIANTS[index]

    notes = "/".join(
        f"{n:.0f}" for n in spec["notes"]
    )

    return f"{index} ({spec['name']}, {notes} Hz)"
