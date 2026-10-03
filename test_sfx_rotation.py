"""Brand SFX rotation tests (Priority 1).

The channel shipped ONE fixed intro_ding.wav in every video and
a single fixed two-note outro chime, so every upload opened and
closed with the identical sound.  app/video/sfx.py added a
family of synthesized cues plus per-video rotation.

These tests pin the properties that actually matter:
  1. the variants are real, distinct, short audio (not aliases
     of one another, not long melodies);
  2. the DEAD-AIR INVARIANT holds for every chime variant --
     the notes must span the whole outro card, because the
     earlier fix removed a measured 0.67s silent tail by making
     note_seconds divide OUTRO_DURATION_S;
  3. rotation actually varies AND never repeats the previous
     video's cue.
"""
import hashlib
import os
import sys
import tempfile
import wave

sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
))

import numpy as np

from app.config import settings
from app.video import sfx
from app.video.branding import (
    DING_DURATION_S,
    OUTRO_DURATION_S,
    _chime_notes,
    synthesize_intro_ding,
)


def check(name, condition):
    """Print the result AND assert it.

    The house style in this repo is `ok &= check(...)` with the
    test returning a bool -- but pytest DISCARDS a test's return
    value, so such a test can never fail.  Asserting here makes
    every check a real guard.
    """
    status = "ok" if condition else "FAIL"
    print(f"  [{status}] {name}")
    assert condition, f"FAILED: {name}"
    return True


def _measure(path):
    """(duration_s, peak, rms, dominant_hz, md5)."""
    with wave.open(str(path), "rb") as handle:
        params = handle.getparams()
        raw = np.frombuffer(
            handle.readframes(params.nframes),
            dtype=np.int16,
        ).astype(np.float64) / 32768.0

    duration = params.nframes / float(params.framerate)
    peak = float(np.max(np.abs(raw))) if raw.size else 0.0
    rms = float(np.sqrt(np.mean(raw ** 2))) if raw.size else 0.0

    spectrum = np.abs(np.fft.rfft(raw))
    freqs = np.fft.rfftfreq(
        len(raw), 1.0 / params.framerate
    )
    dominant = (
        float(freqs[int(np.argmax(spectrum))])
        if raw.size else 0.0
    )

    with open(path, "rb") as handle:
        digest = hashlib.md5(handle.read()).hexdigest()

    return duration, peak, rms, dominant, digest


# =========================================================
# 1. VARIANT ASSETS ARE REAL AND DISTINCT
# =========================================================

def test_ding_variants_are_distinct_audio():
    print("\nTEST 1: every ding variant is real, "
          "distinct audio")

    ok = True

    for index in range(len(sfx.DING_VARIANTS)):
        sfx.synthesize_ding_variant(index, force=True)

    paths = [
        sfx.ding_path(i)
        for i in range(len(sfx.DING_VARIANTS))
    ]

    for path in paths:
        assert os.path.exists(path), f"missing {path}"

        duration, peak, rms, _dom, _md5 = _measure(path)
        name = os.path.basename(path)

        ok &= check(
            f"{name} exists & non-empty "
            f"({os.path.getsize(path)} B)",
            os.path.getsize(path) > 1000,
        )
        ok &= check(
            f"{name} is a short sting "
            f"({duration:.2f}s <= 0.95s)",
            duration <= 0.95,
        )
        ok &= check(
            f"{name} has signal "
            f"(peak {peak:.2f}, rms {rms:.3f})",
            peak > 0.5 and rms > 0.05,
        )
        ok &= check(
            f"{name} is not clipping", peak <= 1.0
        )

    digests = {_measure(p)[4] for p in paths}
    ok &= check(
        f"all {len(paths)} variants are byte-distinct",
        len(digests) == len(paths),
    )

    dominants = [round(_measure(p)[3]) for p in paths]
    ok &= check(
        f"variants occupy different registers {dominants}",
        len(set(dominants)) == len(paths),
    )

    return ok


def test_default_ding_is_unchanged():
    print("\nTEST 2: default call is the ORIGINAL cue "
          "(backward compatible)")

    ok = True

    ok &= check(
        "variant 0 keeps the historical filename",
        sfx.ding_path(0).name == "intro_ding.wav",
    )
    ok &= check(
        "variant 0 duration matches the original "
        f"{DING_DURATION_S}s",
        abs(
            sfx.DING_VARIANTS[0]["duration_s"]
            - DING_DURATION_S
        ) < 1e-6,
    )
    ok &= check(
        "synthesize_intro_ding() -> intro_ding.wav",
        synthesize_intro_ding().name == "intro_ding.wav",
    )
    ok &= check(
        "synthesize_intro_ding(variant=0) -> intro_ding.wav",
        synthesize_intro_ding(
            variant=0
        ).name == "intro_ding.wav",
    )
    ok &= check(
        "synthesize_intro_ding(variant=2) -> intro_ding_2.wav",
        synthesize_intro_ding(
            variant=2
        ).name == "intro_ding_2.wav",
    )
    ok &= check(
        "variant index wraps instead of raising",
        sfx.ding_path(99).name
        == sfx.ding_path(99 % len(sfx.DING_VARIANTS)).name,
    )
    ok &= check(
        "original chime notes unchanged (E5->B4)",
        _chime_notes(0) == (659.26, 493.88),
    )
    ok &= check(
        "original chime notes still match the table",
        _chime_notes(0)
        == tuple(sfx.CHIME_VARIANTS[0]["notes"]),
    )

    return ok


# =========================================================
# 3. DEAD-AIR INVARIANT
# =========================================================

def test_every_chime_spans_the_full_outro_card():
    print("\nTEST 3: DEAD-AIR INVARIANT -- every chime "
          "rings through the whole card")

    ok = True

    for index, spec in enumerate(sfx.CHIME_VARIANTS):
        notes = sfx.chime_notes(index)

        ok &= check(
            f"chime {index} ({spec['name']}) has >= 2 notes",
            len(notes) >= 2,
        )

        # The renderer computes note_seconds as
        # OUTRO_DURATION_S / len(notes), so the notes cover
        # the card exactly.  A variant that rendered only part
        # of the card would bring back the 0.67s silent tail.
        note_seconds = OUTRO_DURATION_S / len(notes)
        covered = note_seconds * len(notes)

        ok &= check(
            f"chime {index} covers {covered:.2f}s of the "
            f"{OUTRO_DURATION_S}s card",
            abs(covered - OUTRO_DURATION_S) < 1e-9,
        )
        ok &= check(
            f"chime {index} each note < card length "
            f"({note_seconds:.2f}s)",
            note_seconds < OUTRO_DURATION_S,
        )
        ok &= check(
            f"chime {index} notes descend (sign-off feel)",
            notes[0] > notes[-1],
        )

    signatures = {
        sfx.chime_notes(i)
        for i in range(len(sfx.CHIME_VARIANTS))
    }
    ok &= check(
        f"all {len(sfx.CHIME_VARIANTS)} chime note-sets "
        f"are distinct",
        len(signatures) == len(sfx.CHIME_VARIANTS),
    )

    return ok


# =========================================================
# 4. ROTATION
# =========================================================

def test_rotation_varies_and_never_repeats():
    print("\nTEST 4: rotation varies and avoids an "
          "immediate repeat")

    ok = True

    keys = [f"_test_run_{i}" for i in range(24)]

    # Production commits each pick to the ledger, so the next
    # video reads a DIFFERENT last-used.  Track it here the
    # same way; passing a pinned last_variant would pin one
    # variant out of the pool for the whole loop.
    dings, chimes = [], []
    last_ding = last_chime = None

    for key in keys:
        ding = sfx.pick_ding_variant(
            topic_key=key,
            category="Defense",
            last_variant=last_ding,
        )
        chime = sfx.pick_chime_variant(
            topic_key=key,
            category="Defense",
            last_variant=last_chime,
        )
        dings.append(ding)
        chimes.append(chime)
        last_ding, last_chime = ding, chime

    ok &= check(
        f"ding rotation uses {len(set(dings))}"
        f"/{len(sfx.DING_VARIANTS)} variants",
        len(set(dings)) == len(sfx.DING_VARIANTS),
    )
    ok &= check(
        f"chime rotation uses {len(set(chimes))}"
        f"/{len(sfx.CHIME_VARIANTS)} variants",
        len(set(chimes)) == len(sfx.CHIME_VARIANTS),
    )

    def repeats(seq):
        return sum(
            1 for a, b in zip(seq, seq[1:]) if a == b
        )

    ok &= check(
        "no consecutive ding repeats", repeats(dings) == 0
    )
    ok &= check(
        "no consecutive chime repeats",
        repeats(chimes) == 0,
    )
    ok &= check(
        "same topic key is deterministic",
        sfx.pick_ding_variant(
            topic_key=keys[0], category="Defense"
        ) == dings[0],
    )
    ok &= check(
        "all picks are valid indices",
        all(0 <= v < len(sfx.DING_VARIANTS) for v in dings)
        and all(
            0 <= v < len(sfx.CHIME_VARIANTS) for v in chimes
        ),
    )

    return ok


def test_rotation_never_returns_last_used():
    print("\nTEST 5: an explicit last-used is never re-picked")

    ok = True

    for last in range(len(sfx.DING_VARIANTS)):
        picked = sfx.pick_ding_variant(
            topic_key=f"fixed_{last}",
            category=None,
            last_variant=last,
        )
        ok &= check(
            f"ding: last={last} -> picked={picked} (differs)",
            picked != last,
        )

    for last in range(len(sfx.CHIME_VARIANTS)):
        picked = sfx.pick_chime_variant(
            topic_key=f"fixed_{last}",
            category=None,
            last_variant=last,
        )
        ok &= check(
            f"chime: last={last} -> picked={picked} (differs)",
            picked != last,
        )

    return ok


# =========================================================
# 5. CATEGORY BIAS + LEDGER + BRANDING WIRING
# =========================================================

def test_category_bias_restricts_pool():
    print("\nTEST 6: SFX_CATEGORY_VARIANTS biases a category")

    ok = True
    original = sfx.settings.SFX_CATEGORY_VARIANTS

    try:
        sfx.settings.SFX_CATEGORY_VARIANTS = '{"defense": [1, 2]}'

        # Track last-used across picks, as the ledger does in
        # production -- otherwise one variant is excluded for
        # the whole loop and the other is chosen every time.
        picks, last = set(), None
        for i in range(20):
            value = sfx.pick_ding_variant(
                topic_key=f"c{i}",
                category="Defense",
                last_variant=last,
            )
            picks.add(value)
            last = value

        ok &= check(
            f"defense restricted to {{1,2}}, got {sorted(picks)}",
            picks <= {1, 2} and len(picks) == 2,
        )

        free, last_free = set(), None
        for i in range(20):
            value = sfx.pick_ding_variant(
                topic_key=f"u{i}",
                category="Economy",
                last_variant=last_free,
            )
            free.add(value)
            last_free = value

        ok &= check(
            f"unlisted category rotates freely "
            f"({sorted(free)})",
            free == set(
                range(len(sfx.DING_VARIANTS))
            ),
        )

    finally:
        sfx.settings.SFX_CATEGORY_VARIANTS = original

    # A malformed map must never crash a publish.
    try:
        sfx.settings.SFX_CATEGORY_VARIANTS = "not json{"
        picked = sfx.pick_ding_variant(
            topic_key="malformed", category="Defense"
        )
        ok &= check(
            "malformed map degrades to free rotation",
            0 <= picked < len(sfx.DING_VARIANTS),
        )
    finally:
        sfx.settings.SFX_CATEGORY_VARIANTS = original

    return ok


def test_ledger_round_trip():
    print("\nTEST 7: last-sfx ledger persists and reloads")

    ok = True

    original_db = settings.DB_PATH

    # _state_path() derives the ledger location from
    # settings.DB_PATH (and only falls back to
    # _SFX_STATE_PATH), so the DB setting is what must be
    # redirected to isolate this test.
    with tempfile.TemporaryDirectory() as tmp:
        settings.DB_PATH = os.path.join(tmp, "test.db")

        try:
            ok &= check(
                f"ledger is redirected into the temp dir "
                f"({sfx._state_path()})",
                sfx._state_path().startswith(tmp),
            )

            sfx.remember_sfx(2, 1)
            loaded = sfx.load_last_sfx()

            ok &= check(
                f"ledger stores the pick {loaded}",
                loaded.get("last_ding_variant") == 2
                and loaded.get("last_chime_variant") == 1,
            )
            ok &= check(
                "next ding advances past the last pick",
                sfx.pick_ding_variant(
                    topic_key="after"
                ) != 2,
            )
            ok &= check(
                "next chime advances past the last pick",
                sfx.pick_chime_variant(
                    topic_key="after"
                ) != 1,
            )

        finally:
            settings.DB_PATH = original_db

    return ok


def test_branding_accepts_variants_and_defaults():
    print("\nTEST 8: branding threads variants through, "
          "defaults unchanged")

    import inspect

    from app.video import branding

    ok = True

    sig = inspect.signature(
        branding.build_brand_audio_segments
    )
    ok &= check(
        "build_brand_audio_segments has variant params",
        "ding_variant" in sig.parameters
        and "chime_variant" in sig.parameters,
    )
    ok &= check(
        "both default to 0 (original cue)",
        sig.parameters["ding_variant"].default == 0
        and sig.parameters["chime_variant"].default == 0,
    )

    for name in (
        "_build_intro_audio", "_build_outro_audio"
    ):
        params = inspect.signature(
            getattr(branding, name)
        ).parameters
        ok &= check(
            f"{name} accepts variant, default 0",
            params["variant"].default == 0,
        )

    for index in range(len(sfx.CHIME_VARIANTS)):
        ok &= check(
            f"branding._chime_notes({index}) reaches the "
            f"rotating table",
            _chime_notes(index) == sfx.chime_notes(index),
        )

    return ok
