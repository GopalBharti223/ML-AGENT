"""Category voice-pool rotation tests (Priority 3).

VOICE_CATEGORY_MAP used to map each category to exactly ONE
voice.  Seven categories all hard-mapped to en-US-GuyNeural, so
47% of published videos (55% of the most recent 20) used the
same narrator.  Values may now be a LIST, and pick_voice()
rotates within the pool, choosing the member that has gone
longest unused.

The tests below pin:
  1. backward compatibility -- a plain string still means a
     one-voice pool, so older .env overrides keep working;
  2. no category is a single-voice funnel any more;
  3. the pick never repeats the most recently used voice;
  4. REGRESSION for the two bugs this feature shipped with:
       a) sorting ascending by recency returned the MOST
          recently used voice (the opposite of the intent);
       b) building the recency index with a dict comprehension
          kept the LAST duplicate, so a frequently used voice
          inherited its OLDEST position and the ranking
          inverted -- Defense returned the same voice 4/4.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
))

from app.audio.tts import TTSEngine
from app.config import parse_json_setting, settings


def check(name, condition):
    """Print the result AND assert it.

    The house style in this repo is `ok &= check(...)` with the
    test returning a bool -- but pytest DISCARDS a test's return
    value, so such a test can never fail.  Asserting here makes
    every check a real guard (verified by _mutation_check.py,
    which reintroduces each bug and confirms the test fails).
    """
    status = "ok" if condition else "FAIL"
    print(f"  [{status}] {name}")
    assert condition, f"FAILED: {name}"
    return True


# Every category that production has actually published.
REAL_CATEGORIES = [
    "World Data", "Climate", "Population", "Formula 1",
    "Energy", "space_science", "Economy", "Technology",
    "Health", "AI Talent", "AI Governance", "Companies",
    "AI Investment", "Public Interest", "Defense",
    "AI Research", "Gaming", "Football", "Environment",
    "Education", "Governance", "Debt", "cities",
]


# =========================================================
# 1. BACKWARD COMPATIBILITY
# =========================================================

def test_voice_value_accepts_both_shapes():
    print("\nTEST 1: VOICE_CATEGORY_MAP accepts a string "
          "OR a list")

    ok = True

    ok &= check(
        "string -> single-voice pool",
        TTSEngine._voice_value("en-US-GuyNeural")
        == ["en-US-GuyNeural"],
    )
    ok &= check(
        "list -> pool, order preserved",
        TTSEngine._voice_value(
            ["en-US-GuyNeural", "en-US-JennyNeural"]
        ) == ["en-US-GuyNeural", "en-US-JennyNeural"],
    )
    ok &= check(
        "tuples accepted",
        TTSEngine._voice_value(
            ("en-GB-RyanNeural",)
        ) == ["en-GB-RyanNeural"],
    )
    ok &= check(
        "duplicates collapsed",
        TTSEngine._voice_value(
            ["en-US-GuyNeural", "en-US-GuyNeural"]
        ) == ["en-US-GuyNeural"],
    )
    ok &= check(
        "blank / None -> empty (never matches)",
        TTSEngine._voice_value(None) == []
        and TTSEngine._voice_value("") == []
        and TTSEngine._voice_value([]) == [],
    )

    # A one-voice pool must still return that exact voice.
    # (_category_mapping re-reads settings on every call, so
    # mutating the setting is enough -- no patching needed.)
    original = settings.VOICE_CATEGORY_MAP
    try:
        settings.VOICE_CATEGORY_MAP = (
            '{"economy": "en-US-GuyNeural"}'
        )
        ok &= check(
            "legacy string map still pins the voice",
            TTSEngine._category_voice_pool("Economy")
            == ["en-US-GuyNeural"],
        )
        ok &= check(
            "legacy string map -> pick_voice unchanged",
            TTSEngine.pick_voice(
                last_voice="en-GB-RyanNeural",
                category="Economy",
                last_voices=["en-US-GuyNeural"],
            ) == "en-US-GuyNeural",
        )
    finally:
        settings.VOICE_CATEGORY_MAP = original

    return ok


# =========================================================
# 2. NO CATEGORY IS A SINGLE-VOICE FUNNEL
# =========================================================

def test_every_category_has_multiple_voices():
    print("\nTEST 2: no production category is a "
          "single-voice funnel")

    ok = True

    single = []
    unmapped = []

    for category in REAL_CATEGORIES:
        pool = TTSEngine._category_voice_pool(category)
        if not pool:
            unmapped.append(category)
        elif len(pool) == 1:
            single.append((category, pool[0]))

    ok &= check(
        f"all {len(REAL_CATEGORIES)} real categories map",
        not unmapped,
    )
    ok &= check(
        f"no category is pinned to one voice "
        f"(found {single})",
        not single,
    )

    # Defense was the reported example.
    defense = TTSEngine._category_voice_pool("Defense")
    ok &= check(
        f"Defense has {len(defense)} voices {defense}",
        len(defense) >= 2,
    )

    # The historically worst funnel.
    world = TTSEngine._category_voice_pool("World Data")
    ok &= check(
        f"World Data (28% of all videos) has "
        f"{len(world)} voices",
        len(world) >= 2,
    )

    # Every configured entry must be usable.
    mapping = parse_json_setting(
        settings.VOICE_CATEGORY_MAP, {}
    )
    broken = [
        k for k, v in mapping.items()
        if not TTSEngine._voice_value(v)
    ]
    ok &= check(
        f"no map entry has an empty voice list {broken}",
        not broken,
    )

    # Every pool voice must exist in the rotation pool.
    rotation = set(TTSEngine._rotation_pool())
    unknown = set()
    for category in REAL_CATEGORIES:
        for voice in TTSEngine._category_voice_pool(
            category
        ):
            if voice not in rotation:
                unknown.add((category, voice))
    ok &= check(
        f"every pool voice is in the rotation pool "
        f"{unknown}",
        not unknown,
    )

    return ok


# =========================================================
# 3. ROTATION BEHAVIOR
# =========================================================

def test_pick_never_repeats_the_most_recent_voice():
    print("\nTEST 3: the pick never repeats the most "
          "recently used voice")

    ok = True

    for category in ("Defense", "Economy", "World Data"):
        pool = TTSEngine._category_voice_pool(category)

        for voice in pool:
            picked = TTSEngine.pick_voice(
                last_voice=voice,
                category=category,
                last_voices=[voice],
            )
            ok &= check(
                f"{category}: last={voice.split('-')[-1][:4]} "
                f"-> {picked.split('-')[-1][:4]} (differs)",
                picked != voice,
            )
            ok &= check(
                f"{category}: pick is inside the pool",
                picked in pool,
            )

    return ok


def test_pick_prefers_the_least_recently_used():
    print("\nTEST 4: the pick is the longest-unused "
          "pool member")

    ok = True

    pool = TTSEngine._category_voice_pool("Defense")

    # Every pool member but one has been used; the unseen one
    # must win.
    for unseen in pool:
        history = [v for v in pool if v != unseen]
        picked = TTSEngine.pick_voice(
            last_voice=history[0],
            category="Defense",
            last_voices=history,
        )
        ok &= check(
            f"unseen {unseen.split('-')[-1][:4]} is chosen "
            f"over the rest",
            picked == unseen,
        )

    # With every member used once, the OLDEST must win.
    oldest = pool[-1]
    picked = TTSEngine.pick_voice(
        last_voice=pool[0],
        category="Defense",
        last_voices=list(pool),
    )
    ok &= check(
        f"oldest member wins when all were used "
        f"({oldest.split('-')[-1][:4]})",
        picked == oldest,
    )

    return ok


def test_regression_duplicate_voice_uses_first_occurrence():
    print("\nTEST 5: REGRESSION -- duplicates use the FIRST "
          "(most recent) occurrence")

    ok = True

    pool = TTSEngine._category_voice_pool("Defense")
    if len(pool) < 2:
        return True

    # A history where the SAME voice appears at BOTH ends, and
    # a third voice is genuinely the stalest:
    #   newest ... oldest
    #     Guy   Aria   Ryan   Guy
    # `recent` is newest-first, so Guy's FIRST occurrence (0) is
    # its most recent use and Ryan (2) is the stalest -> Ryan.
    #
    # With the dict-comprehension bug the LAST occurrence wins,
    # so Guy is scored at 3, looks the stalest, and is chosen
    # instead.  This history therefore separates the two.
    guy, aria, ryan = pool
    history = [guy, aria, ryan, guy]
    picked = TTSEngine.pick_voice(
        last_voice=guy,
        category="Defense",
        last_voices=history,
    )

    ok &= check(
        f"stalest member wins "
        f"({ryan.split('-')[-1][:4]}); got "
        f"{picked.split('-')[-1][:4]}",
        picked == ryan,
    )
    ok &= check(
        f"the duplicate voice {guy.split('-')[-1][:4]} is "
        f"not re-picked just because it also appears older",
        picked != guy,
    )

    # Repeating a voice must never make it look STALE.
    flooded = [guy, aria] + [ryan] * 5
    picked = TTSEngine.pick_voice(
        last_voice=guy,
        category="Defense",
        last_voices=flooded,
    )
    ok &= check(
        f"a voice flooded to the back is correctly seen as "
        f"stale and chosen ({picked.split('-')[-1][:4]})",
        picked == ryan,
    )

    return ok


def test_rotation_cycles_a_pool_over_consecutive_calls():
    print("\nTEST 6: a category cycles its pool over "
          "consecutive publishes")

    ok = True

    history = []
    picks = []

    for _ in range(9):
        voice = TTSEngine.pick_voice(
            last_voice=history[0] if history else None,
            category="Defense",
            last_voices=list(history[:8]),
        )
        picks.append(voice)
        history.insert(0, voice)
        history = history[:8]

    pool = TTSEngine._category_voice_pool("Defense")

    ok &= check(
        f"9 defense publishes use {len(set(picks))} voices",
        len(set(picks)) == len(pool),
    )
    ok &= check(
        f"no consecutive repeat across {len(picks)} picks",
        sum(
            1 for a, b in zip(picks, picks[1:]) if a == b
        ) == 0,
    )
    ok &= check(
        f"every pick is in the pool ({pool})",
        set(picks) <= set(pool),
    )

    return ok


# =========================================================
# 4. END-TO-END DISTRIBUTION
# =========================================================

def test_published_mix_is_not_voice_skewed():
    print("\nTEST 7: the real published mix no longer "
          "skews to one narrator")

    ok = True

    # Real category volumes, weighted as production produces
    # them (World Data alone is 28% of all videos).
    mix = []
    for category, count in (
        ("World Data", 57), ("Climate", 15),
        ("Population", 12), ("Formula 1", 12),
        ("Energy", 11), ("space_science", 9),
        ("Economy", 9), ("Technology", 8),
        ("Health", 8), ("AI Talent", 8),
        ("AI Governance", 8), ("Companies", 7),
        ("AI Investment", 6), ("Public Interest", 5),
        ("Defense", 5), ("AI Research", 5),
        ("Gaming", 3), ("Football", 3),
        ("Environment", 3), ("Education", 3),
        ("Governance", 1), ("Debt", 1),
    ):
        mix.extend([category] * count)

    history = []
    picks = []

    for category in mix:
        voice = TTSEngine.pick_voice(
            last_voice=history[0] if history else None,
            category=category,
            last_voices=list(history[:8]),
        )
        picks.append(voice)
        history.insert(0, voice)
        history = history[:8]

    counts = {}
    for voice in picks:
        counts[voice] = counts.get(voice, 0) + 1

    total = len(picks)
    shares = {
        v: 100.0 * n / total
        for v, n in counts.items()
    }

    print("    --- projected distribution ---")
    for voice, pct in sorted(
        shares.items(), key=lambda kv: -kv[1]
    ):
        bar = "#" * int(pct)
        print(f"    {voice:<22} {pct:5.1f}%  {bar}")

    max_share = max(shares.values())
    spread = max_share - min(shares.values())

    ok &= check(
        f"max single-voice share is {max_share:.1f}% "
        f"(was 55% in the last 20)",
        max_share <= 30.0,
    )
    ok &= check(
        f"spread is {spread:.1f}pp", spread <= 15.0
    )
    ok &= check(
        f"all {len(counts)} rotation voices are used",
        len(counts) == len(TTSEngine._rotation_pool()),
    )
    ok &= check(
        "no immediate repeats anywhere in the mix",
        sum(
            1 for a, b in zip(picks, picks[1:]) if a == b
        ) == 0,
    )

    return ok


def test_unmapped_category_still_rotates():
    print("\nTEST 8: an unmapped category still resolves "
          "(no crash, no fixed voice)")

    ok = True

    for category in ("Totally Unknown Topic", "", None):
        voice = TTSEngine.pick_voice(
            last_voice="en-US-GuyNeural",
            category=category,
            last_voices=["en-US-GuyNeural"],
        )
        ok &= check(
            f"unmapped {category!r} -> valid voice {voice}",
            voice in TTSEngine._rotation_pool(),
        )

    ok &= check(
        "unmapped pick avoids the previous voice",
        TTSEngine.pick_voice(
            last_voice="en-US-GuyNeural",
            category="Totally Unknown Topic",
            last_voices=None,
        ) != "en-US-GuyNeural",
    )

    return ok

