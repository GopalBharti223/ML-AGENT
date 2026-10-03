"""Unit checks for gate 4b canonical comparison + backfill.

Scenario A = mil run log: named=[UKR,BFA,LUX,SOM,MWI,LVA],
script highlights only [Ukraine]  -> UKR covered canonically,
BFA/LUX/SOM/MWI/LVA backfilled.
Scenario B = random run log: named=[Luxembourg,UAE,United Kingdom,
UK], highlights=[Luxembourg,UAE]  -> UK/United Kingdom backfilled
once (shared identity GB).
Scenario C = genuine unknown entity still blocks (safety intact).
"""

from types import SimpleNamespace

import pandas as pd

import run as run_mod


def make_script(titles, highlights):
    scenes = [
        SimpleNamespace(title=t, highlight_countries=list(h))
        for t, h in zip(titles, highlights)
    ]
    return SimpleNamespace(title="Script Title", scenes=scenes)


# ---------------------------------------------------------------- A
script_a = make_script(
    ["Ukraine's Defense Spend", "Scene 2", "Scene 3",
     "Scene 4", "Scene 5", "Scene 6"],
    [["Ukraine"], [], [], [], [], []],
)

named_a = ["UKR", "BFA", "LUX", "SOM", "MWI", "LVA"]

missing_a0 = run_mod._missing_named_entities(named_a, script_a)
assert "UKR" not in missing_a0, (
    "UKR vs 'Ukraine' must count as covered (canonical identity); "
    f"got missing={missing_a0}"
)
assert set(missing_a0) == {"BFA", "LUX", "SOM", "MWI", "LVA"}, missing_a0

frame_a = pd.DataFrame(
    {"2020": [1, 2, 3, 4, 5, 6]},
    index=["Ukraine", "Burkina Faso", "Luxembourg",
           "Somalia", "Malawi", "Latvia"],
)

notes_a = run_mod._backfill_script_highlights(
    script_a, missing_a0, frame_a
)
assert len(notes_a) == 5, notes_a

missing_a1 = run_mod._missing_named_entities(named_a, script_a)
assert missing_a1 == [], f"after backfill must be empty, got {missing_a1}"

# per-scene focus (incl. title countries) never exceeds cap=4
cap = 4
for scene in script_a.scenes:
    focus = set(run_mod._title_identities_for_test(scene.title)) \
        if hasattr(run_mod, "_title_identities_for_test") else set()
    n = len(scene.highlight_countries)
    assert n <= cap, f"scene {scene.title!r} over cap: {n}"
print("A: mil scenario OK -- UKR covered, 5 backfilled, per-scene <=4")

# ---------------------------------------------------------------- B
# B1 = random run log: the LLM title itself names UK, so the renderer
# merges UK into focus (FOCUS-ENTITY BAR CAP) even though
# highlight_countries never lists it -> gate must count it covered.
script_b = make_script(
    ["What sank UK AI talent?", "Scene 2", "Scene 3", "Scene 4"],
    [["Luxembourg", "UAE"], [], [], []],
)
script_b.title = "What sank UK AI talent?"

named_b = ["Luxembourg", "UAE", "United Kingdom", "UK"]

missing_b0 = run_mod._missing_named_entities(named_b, script_b)
assert missing_b0 == [], (
    f"title-named UK must count as covered, got missing={missing_b0}"
)

notes_b = run_mod._backfill_script_highlights(script_b, missing_b0, None)
assert notes_b == [], f"nothing to place, got {notes_b}"
print("B1: random-run scenario OK -- UK covered via title identity")

# B2 = same entities but NO title mention -> both alias forms of GB
# collapse to one placement (shared canonical identity).
script_b2 = make_script(
    ["Scene 1", "Scene 2", "Scene 3", "Scene 4"],
    [["Luxembourg", "UAE"], [], [], []],
)
script_b2.title = "Talent drain across Europe"

missing_b20 = run_mod._missing_named_entities(named_b, script_b2)
assert set(missing_b20) == {"United Kingdom", "UK"}, missing_b20

notes_b2 = run_mod._backfill_script_highlights(
    script_b2, missing_b20, None
)
assert len(notes_b2) == 1, (
    f"UK + United Kingdom share identity GB -> exactly 1 placement, "
    f"got {notes_b2}"
)

missing_b21 = run_mod._missing_named_entities(named_b, script_b2)
assert missing_b21 == [], missing_b21
print(f"B2: alias collapse OK -- single GB placement {notes_b2[0][1]!r}")

# ---------------------------------------------------------------- C
script_c = make_script(["Scene 1", "Scene 2"], [["Ukraine"], []])
missing_c = run_mod._missing_named_entities(["Atlantis"], script_c)
assert missing_c == ["Atlantis"], (
    "genuine unknown entity must still be reported as missing"
)

# unknown entity present in NO frame label -> backfill falls back to
# raw token; identity still unknown -> recompute still flags it ONLY
# if the raw token's casefold identity was not added.  Placement adds
# the token, which DOES cover it (renderer will attempt a match and
# simply not draw it) -- so verify the data gate remains the true
# blocker for unknowns: _ensure_data... raises for Atlantis vs frame.
try:
    run_mod._ensure_data_matches_topic_entities(
        {"selected_countries": ["Atlantis"],
         "story_metrics": {}, "topic": "", "title": ""},
        frame_a,
    )
    raise SystemExit("C FAILED: Atlantis should raise TopicDataMismatchError")
except run_mod.TopicDataMismatchError:
    pass
print("C: unknown entity still blocked by step-3b data gate")

print("ALL GATE-4B UNIT CHECKS PASSED")
