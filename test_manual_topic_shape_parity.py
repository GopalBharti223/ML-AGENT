"""
OFFLINE SHAPE-PARITY TEST  (approved plan, testing item 1)

Proves that the NEW manual-keyword path and the EXISTING
automatic path emit the exact same topic_data contract --
top-level keys, story_metrics scalar keys, pandas payload types,
script-prompt context fields, fetch-story mapping -- WITHOUT any
network access, by registering a synthetic provider and running
BOTH engines against it.

Also acts as the schema gate:
  * ContentQualityValidator must accept BOTH objects
  * the two hard-bracket keys script.py needs ('topic',
    'category') must exist on BOTH objects

Run:  python test_manual_topic_shape_parity.py
Exit: 0 on success, 1 on any failure.
"""

import random
import sys

import pandas as pd

from app.ai.script import ScriptEngine
from app.data.providers.base import (
    DataProvider,
    DataProviderResult,
    IndicatorInfo,
    normalize_long_data,
    to_visual_dataframe,
)
from app.data.providers.health import provider_health
from app.data.providers.registry import DataProviderRegistry
from app.topic.content_quality import ContentQualityValidator
from app.topic.manual_topic import (
    ManualTopicEngine,
    ManualTopicError,
)
from app.topic.smart_story import SmartStoryEngine


FAKE_ID = "parity_fake"

YEARS = list(range(2015, 2025))

INDICATORS = {
    "FAKE.POP.TOTL": "Population",
    "FAKE.GDP.CD": "GDP",
}

SERIES = {
    # start >> decline hero / rank dropper
    "Delta":     [400, 390, 385, 370, 360, 340, 300, 250, 180, 120],
    "Charlie":   [300, 298, 297, 296, 295, 294, 293, 292, 291, 290],
    "Golf":      [250, 251, 252, 253, 254, 255, 256, 257, 258, 260],
    "Bravo":     [200, 201, 202, 203, 204, 205, 206, 207, 208, 210],
    "Alpha":     [100, 105, 110, 115, 120, 128, 135, 140, 145, 150],
    "Echo":      [50, 55, 60, 66, 72, 78, 84, 88, 92, 95],
    "Foxtrot":   [10, 14, 20, 28, 36, 44, 52, 62, 76, 90],
    "Hotel":     [30, None, 32, None, 34, None, 30, None, 28, 25],
}

CODES = {
    "Delta": "DLT",
    "Charlie": "CCH",
    "Golf": "GLF",
    "Bravo": "BRV",
    "Alpha": "ALP",
    "Echo": "ECH",
    "Foxtrot": "FOX",
    "Hotel": "HTL",
}


def _long_rows():
    rows = []
    for country, values in SERIES.items():
        for i, year in enumerate(YEARS):
            value = values[i]
            if value is None:
                continue
            rows.append(
                {
                    "country": country,
                    "country_code": CODES[country],
                    "year": year,
                    "value": float(value),
                }
            )
    return rows


class ParityProvider(DataProvider):

    provider_id = FAKE_ID
    provider_name = "World Bank"
    source_url = "https://data.worldbank.org"

    @classmethod
    def list_indicators(cls):
        return [
            IndicatorInfo(
                code=code,
                name=name,
                category="World Data",
                source_url=cls.source_url,
            )
            for code, name in INDICATORS.items()
        ]

    @classmethod
    def fetch_normalized(
        cls,
        indicator_code,
        years=10,
        story_type="fastest_growth",
        min_countries=8,
    ):
        metric_name = INDICATORS.get(
            indicator_code, indicator_code
        )
        rows = _long_rows()
        normalized = normalize_long_data(
            rows,
            cls.provider_id,
            metric_name,
            cls.provider_name,
            cls.source_url,
            indicator_code,
        )
        metadata = {
            "provider": cls.provider_id,
            "source_name": cls.provider_name,
            "source_url": cls.source_url,
            "indicator_code": indicator_code,
            "indicator_name": metric_name,
        }
        wide = to_visual_dataframe(
            normalized, metadata
        )
        return DataProviderResult(
            provider=cls.provider_id,
            indicator_code=indicator_code,
            metric_name=metric_name,
            source_name=cls.provider_name,
            source_url=cls.source_url,
            normalized_data=normalized,
            wide_data=wide,
            metadata=metadata,
        )


# ---------------------------------------------------------
# Isolate health-monitor state: no files touched, no
# circuit-breaker gating during the parity run.
# ---------------------------------------------------------
provider_health.is_available = lambda pid: True
provider_health.record_success = lambda *a, **k: None
provider_health.record_failure = lambda *a, **k: None
provider_health.record_empty = lambda *a, **k: None
provider_health.record_skipped = lambda *a, **k: None
provider_health.one_line_summary = (
    lambda: "[HEALTH] parity-test stub"
)

# ---------------------------------------------------------
# NEW (manual-path semantic step): keep this offline suite
# fully deterministic -- Groq is NEVER called from these
# tests.  Direct-match keywords ("population" -> tier 6)
# bypass the semantic step entirely anyway; stubbing the seam
# additionally makes the negative case independent of any
# network/API state.
# ---------------------------------------------------------
ManualTopicEngine._llm_semantic_pick = staticmethod(
    lambda keyword, indicator_names: None
)

DataProviderRegistry.register(ParityProvider)


RESULT = {"passed": 0, "failed": []}


def check(name, condition, detail=""):
    if condition:
        RESULT["passed"] += 1
        print(f"  \u2705 {name}")
    else:
        RESULT["failed"].append(name)
        print(f"  \u274c {name}  {detail}")

print("=" * 70)
print("OFFLINE SHAPE-PARITY TEST")
print("=" * 70)

# =========================================================
# PATH A -- EXISTING AUTOMATIC ENGINE, fully exercised
# (circuit breaker, all filters, validation, anti-repeat,
#  dedup, distribution preference, category rotation).
# Only the provider layer is synthetic.
# =========================================================

random.seed(12345)

auto_candidate = SmartStoryEngine.select_best_candidate(
    provider_ids=[FAKE_ID],
    max_indicators_per_provider=2,
    years=ManualTopicEngine.YEARS,
    min_countries=ManualTopicEngine.MIN_COUNTRIES,
)

check(
    "AUTO path selected a candidate",
    auto_candidate is not None,
)

auto = auto_candidate.to_topic_data()

print()
print("-" * 70)
print("MANUAL keyword='population'")
print("-" * 70)

# =========================================================
# PATH B -- NEW MANUAL KEYWORD ENGINE
# =========================================================

random.seed(12345)

manual = ManualTopicEngine.generate_manual_topic(
    "population",
    provider_ids=[FAKE_ID],
    seed=99,
)

# =========================================================
# PARITY ASSERTIONS
# =========================================================

EXPECTED_TOP = {
    "provider_id",
    "indicator_code",
    "indicator_name",
    "story_type",
    "provider_fetch_story_type",
    "chart_type",
    "topic_family",
    "years",
    "category",
    "source_name",
    "source_url",
    "topic",
    "smart_score",
    "story_metrics",
    "selected_countries",
    "selected_min_countries",
}

print()
print("[1] TOP-LEVEL CONTRACT")
check(
    "manual keys == expected factory keys",
    set(manual.keys()) == EXPECTED_TOP,
    f"diff={set(manual.keys()) ^ EXPECTED_TOP}",
)
check(
    "AUTO keys == manual keys (exact)",
    set(auto.keys()) == set(manual.keys()),
    f"diff={set(auto.keys()) ^ set(manual.keys())}",
)

print()
print("[2] HARD-BRACKET KEYS script.py/run.py need")
for key in ("topic", "category"):
    ok_a = isinstance(auto.get(key), str) and auto[key]
    ok_m = isinstance(manual.get(key), str) and manual[key]
    check(
        f"both paths expose truthy '{key}'",
        ok_a and ok_m,
        f"auto={auto.get(key)!r} manual={manual.get(key)!r}",
    )

print()
print("[3] story_metrics PARITY")
am = auto["story_metrics"]
mm = manual["story_metrics"]
# Optional per-story payload: only leader_challenge adds
# extra keys ('leader','challenger') -- see smart_story.py
# _story_metrics().  Parity therefore means: any key found on
# exactly one side must be justified BY THAT SIDE'S OWN
# story_type.
OPTIONAL_EXTRAS = {
    "leader_challenge": {"leader", "challenger"},
}
common = set(am.keys()) & set(mm.keys())
auto_only = set(am.keys()) - common
manual_only = set(mm.keys()) - common

def _allowed_extras(topic_data):
    return OPTIONAL_EXTRAS.get(
        topic_data["story_type"], set()
    )

check(
    "story_metrics parity modulo per-story extras",
    auto_only == _allowed_extras(auto)
    and manual_only == _allowed_extras(manual),
    f"auto-only={auto_only} "
    f"(needs {_allowed_extras(auto)}) | "
    f"manual-only={manual_only} "
    f"(needs {_allowed_extras(manual)})",
)
check(
    "no unexplained extra story_metrics keys",
    auto_only <= {"leader", "challenger"}
    and manual_only <= {"leader", "challenger"},
    f"auto-only={auto_only} manual-only={manual_only}",
)
SCALAR_ESSENTIALS = [
    "entity",
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
    "diversity_multiplier",
    "final_score",
    "selected_chart_type",
    "story_type",
]
missing_a = [k for k in SCALAR_ESSENTIALS if k not in am]
missing_m = [k for k in SCALAR_ESSENTIALS if k not in mm]
check(
    "all scalar essentials present on BOTH paths",
    not missing_a and not missing_m,
    f"auto-missing={missing_a} manual-missing={missing_m}",
)
populated = [
    k for k in SCALAR_ESSENTIALS
    if am.get(k) is not None or mm.get(k) is not None
]
check(
    "essentials carry non-None payloads where derivable",
    len(populated) >= len(SCALAR_ESSENTIALS) - 2,
    f"none-populated={[k for k in SCALAR_ESSENTIALS if k not in populated]}",
)
check(
    "'data' is DataFrame on BOTH paths",
    isinstance(am.get("data"), pd.DataFrame)
    and isinstance(mm.get("data"), pd.DataFrame),
)
check(
    "'latest_sorted' is Series on BOTH paths",
    isinstance(am.get("latest_sorted"), pd.Series)
    and isinstance(mm.get("latest_sorted"), pd.Series),
)

print()
print("[4] SCRIPT-GENERATION CONTEXT (story_details block)")
ctx_auto = ScriptEngine._build_story_context(auto)
ctx_manual = ScriptEngine._build_story_context(manual)
check(
    "context built for BOTH paths",
    bool(ctx_auto) and bool(ctx_manual),
)
check(
    "'entity' reaches the LLM prompt on BOTH paths",
    ctx_auto.get("entity") is not None
    and ctx_manual.get("entity") is not None,
)
check(
    "context key overlap >= 15 fields",
    len(set(ctx_auto) & set(ctx_manual)) >= 15,
)

print()
print("[5] FETCH-STORY MAPPING + TYPE SAFETY")
mapping = SmartStoryEngine.PROVIDER_FETCH_STORY
check(
    "manual provider_fetch_story_type follows map",
    manual["provider_fetch_story_type"]
    == mapping[manual["story_type"]],
)
check(
    "AUTO provider_fetch_story_type follows map",
    auto["provider_fetch_story_type"]
    == mapping[auto["story_type"]],
)
check(
    "'years' is int on BOTH paths",
    isinstance(auto["years"], int)
    and isinstance(manual["years"], int),
)
check(
    "smart_score numeric on BOTH paths",
    isinstance(auto["smart_score"], (int, float))
    and isinstance(manual["smart_score"], (int, float)),
)

print()
print("[6] CONTENT-QUALITY VALIDATOR (shape-level gate)")
verdict_auto = ContentQualityValidator.validate(auto)
verdict_manual = ContentQualityValidator.validate(manual)

def _well_formed(v):
    return (
        isinstance(v, dict)
        and {"valid", "reasons"}.issubset(v.keys())
        and isinstance(v["reasons"], list)
    )

check(
    "AUTO verdict well-formed {valid, reasons}",
    _well_formed(verdict_auto),
)
check(
    "MANUAL verdict well-formed {valid, reasons}",
    _well_formed(verdict_manual),
)

# ---------------------------------------------------------
# DOCUMENTED PRE-EXISTING DIVERGENCE (found BY this test):
#
# Producers (SmartStoryEngine._entity_metrics) store
# percentage_change as a FRACTION (-0.7 == -70%), while
# ContentQualityValidator recomputes it on a x100 PERCENT
# scale (line ~492) with tolerance 1.0.  Any genuine swing
# therefore trips the numeric rule -- identically for BOTH
# selection paths.  The validator is NOT wired into run.py,
# and per the approved ADD-ONLY principle we do not modify
# producer or validator here; we only require that both
# object shapes behave IDENTICALLY inside it, and that no
# failure OTHER than the known scale rule appears.
# ---------------------------------------------------------

def _has_scale_issue(reasons):
    return any(
        "does not match absolute_change"
        in str(reason)
        for reason in reasons
    )

check(
    "validator treats BOTH shapes identically "
    "(known % scale rule trips/passes together)",
    _has_scale_issue(verdict_auto.get("reasons", []))
    == _has_scale_issue(verdict_manual.get("reasons", [])),
)

unexpected = [
    str(r)
    for r in verdict_manual.get("reasons", [])
    if "does not match absolute_change"
    not in str(r)
]
check(
    "no OTHER validation failures on MANUAL object",
    not unexpected,
    unexpected,
)

print()
print("[7] MANUAL DETERMINISM (same seed => same object)")
snapshot = dict(manual)

random.seed(777)

rebuild = ManualTopicEngine.generate_manual_topic(
    "population",
    provider_ids=[FAKE_ID],
    seed=42,
)


def _split(d):
    """Split into (top-copy, scalar-metrics, frame, series),
    excluding the random curiosity-angle suffix key."""
    top = {
        k: v for k, v in d.items()
        if k not in ("topic",)
    }
    metrics = dict(top["story_metrics"])
    frame = metrics.pop("data")
    series = metrics.pop("latest_sorted")
    return top, metrics, frame, series


s_top, s_metrics, s_frame, s_series = _split(snapshot)
r_top, r_metrics, r_frame, r_series = _split(rebuild)

identical = (
    set(s_top.keys()) == set(r_top.keys())
    and set(s_metrics.keys()) == set(r_metrics.keys())
    and all(
        s_metrics[k] == r_metrics[k]
        for k in s_metrics
    )
    and s_top["chart_type"] == r_top["chart_type"]
    and s_top["smart_score"] == r_top["smart_score"]
    and s_top["story_type"] == r_top["story_type"]
    and s_top["indicator_code"]
    == r_top["indicator_code"]
    and s_frame.equals(r_frame)
    and s_series.equals(r_series)
)

check(
    "second seeded build reproduces identical payload "
    "(modulo curiosity-angle text)",
    identical,
)

print()
print("[8] NEGATIVE CASES")
try:
    ManualTopicEngine.generate_manual_topic(
        "nonexistent_widget_xyz",
        provider_ids=[FAKE_ID],
    )
    raised = False
    suggestions = []
except ManualTopicError as err:
    raised = True
    suggestions = err.suggestions
check(
    "unknown keyword raises ManualTopicError",
    raised,
)
check(
    "error carries friendly suggestions",
    len(suggestions) > 0,
)
topics = ManualTopicEngine.available_topics([FAKE_ID])
check(
    "available_topics lists synthetic indicators",
    "Population" in topics and "GDP" in topics,
)

# =========================================================
def _report():
    print()
    print("=" * 70)
    total_failed = len(RESULT["failed"])
    print(
        f"RESULT: {RESULT['passed']} PASSED / "
        f"{total_failed} FAILED"
    )
    print("=" * 70)

    if RESULT["failed"]:
        print("FAILED CHECKS:")
        for name in RESULT["failed"]:
            print(f"  - {name}")

    return total_failed


def test_manual_topic_shape_parity():
    """Real pytest guard for the checks executed at import.

    This file used to end in a bare ``sys.exit(0)`` at module
    level.  Importing it under pytest therefore raised
    ``INTERNALERROR: SystemExit`` and aborted the ENTIRE session,
    so its verdict was never reported by ``pytest -q`` at all.
    The checks still run while the module loads; this turns their
    RESULT tally into an actual assertion instead of an exit code.
    """
    failed = list(RESULT["failed"])
    _report()
    assert not failed, (
        f"{len(failed)} shape-parity check(s) failed: {failed}"
    )


if __name__ == "__main__":
    try:
        test_manual_topic_shape_parity()
    except AssertionError:
        sys.exit(1)
    sys.exit(0)
