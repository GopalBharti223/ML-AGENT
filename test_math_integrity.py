"""Focused unit tests for Phase 1 deterministic math integrity in scripts.

Tests cover:
1. Ground truth computation: sorted years, missing values, zero baseline, negative changes.
2. Claim extraction: isolates change claims while ignoring valid years, durations, ranks, and denominators.
3. Numerical validation:
   - Valid vs invalid increases/decreases
   - The verified defect (4.9 claimed vs 4.4 actual)
   - Zero baseline protection
   - Rate/percentage indicator confusion (% vs points)
   - Rounding tolerance
   - TopicEngine fallback (no story_metrics)
"""

import pandas as pd
import pytest

from app.ai.math_integrity import (
    EntityGroundTruth,
    MathIntegrityEngine,
    MathIntegrityError,
    MathValidationReport,
    NumericalClaim,
)


# =====================================================================
# 1. GROUND TRUTH COMPUTATION TESTS
# =====================================================================


def test_ground_truth_sorted_years():
    """Ensure year columns in any order are sorted chronologically."""
    df = pd.DataFrame(
        {
            2024: [17.6],
            2010: [13.2],
            2015: [15.0],
        },
        index=["Lebanon"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    assert "Lebanon" in gt
    leb = gt["Lebanon"]
    assert leb.start_year == 2010
    assert leb.end_year == 2024
    assert leb.start_val == 13.2
    assert leb.end_val == 17.6
    assert round(leb.abs_change, 2) == 4.4
    assert round(leb.pct_change, 2) == round(((17.6 - 13.2) / 13.2) * 100, 2)
    assert leb.direction == "increase"
    assert leb.is_zero_baseline is False


def test_ground_truth_missing_and_nan_values():
    """Ensure missing and NaN values at endpoints or intermediate years are handled."""
    df = pd.DataFrame(
        {
            "2010": [None, 100.0],
            "2015": [12.0, None],
            "2020": [18.0, 80.0],
            "2024": [None, None],
        },
        index=["CountryA", "CountryB"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    # CountryA has data only in 2015 and 2020
    assert gt["CountryA"].start_year == 2015
    assert gt["CountryA"].end_year == 2020
    assert gt["CountryA"].abs_change == 6.0
    assert gt["CountryA"].direction == "increase"

    # CountryB has data in 2010 and 2020
    assert gt["CountryB"].start_year == 2010
    assert gt["CountryB"].end_year == 2020
    assert gt["CountryB"].abs_change == -20.0
    assert gt["CountryB"].direction == "decrease"


def test_ground_truth_zero_baseline():
    """Ensure baseline of 0 disables relative percentage change."""
    df = pd.DataFrame(
        {
            2010: [0.0],
            2020: [25.0],
        },
        index=["SolarCountry"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    sc = gt["SolarCountry"]
    assert sc.is_zero_baseline is True
    assert sc.abs_change == 25.0
    assert sc.pct_change is None  # Undefined percentage from 0
    assert sc.direction == "increase"


def test_ground_truth_negative_change_decrease():
    """Ensure decreasing indicator produces negative abs_change and decrease direction."""
    df = pd.DataFrame(
        {
            2015: [50.0],
            2020: [35.0],
        },
        index=["DecliningCountry"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    dc = gt["DecliningCountry"]
    assert dc.abs_change == -15.0
    assert dc.pct_change == -30.0
    assert dc.direction == "decrease"


def test_ground_truth_insufficient_data():
    """Ensure entity with 0 or 1 observation is safely flagged."""
    df = pd.DataFrame(
        {
            2015: [None, 42.0],
            2020: [None, None],
        },
        index=["NoData", "OneYearOnly"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    assert gt["NoData"].has_sufficient_data is False
    assert gt["OneYearOnly"].has_sufficient_data is True
    assert gt["OneYearOnly"].abs_change == 0.0


# =====================================================================
# 2. CLAIM EXTRACTION & NUMBER PRESERVATION TESTS
# =====================================================================


def test_extract_claims_isolates_change_verbs_and_nouns():
    """Verify change claims are extracted with correct direction and numbers."""
    text = (
        "Lebanon's child mortality rose by 4.4 points, while Cyprus saw a drop of 15%."
    )
    claims = MathIntegrityEngine.extract_claims(text, known_entities=["Lebanon", "Cyprus"])

    assert len(claims) == 2

    c1 = claims[0]
    assert c1.entity == "Lebanon"
    assert c1.claimed_val == 4.4
    assert c1.is_points is True
    assert c1.is_percent is False
    assert c1.direction == "increase"

    c2 = claims[1]
    assert c2.entity == "Cyprus"
    assert c2.claimed_val == 15.0
    assert c2.is_percent is True
    assert c2.direction == "decrease"


def test_extract_claims_preserves_valid_years_ranks_durations():
    """Verify that calendar years, durations, ranks, and denominators are NOT extracted as change claims."""
    text = (
        "In 2024, the top 5 countries dominated global production. "
        "Over 10 years, mortality remained below 15 per 1,000 live births. "
        "Rank #1 shifted between two nations."
    )
    claims = MathIntegrityEngine.extract_claims(text, known_entities=["India", "China"])

    # None of 2024, 5, 10, 1000, 1 should be treated as change claims
    assert len(claims) == 0


def test_extract_claims_captures_endpoints():
    """Verify 'from X to Y' is captured for internal arithmetic checking."""
    text = "Lebanon rose from 13.2 to 17.6, climbing by 4.4 points."
    claims = MathIntegrityEngine.extract_claims(text, known_entities=["Lebanon"])

    assert len(claims) == 1
    assert claims[0].claimed_val == 4.4
    assert claims[0].claimed_start == 13.2
    assert claims[0].claimed_end == 17.6


# =====================================================================
# 3. NUMERICAL VALIDATION & ERROR DETECTION TESTS
# =====================================================================


def test_production_defect_caught_and_flagged():
    """Replicate the exact production defect: 4.9 claimed vs 4.4 actual (from 13.2 to 17.6)."""
    df = pd.DataFrame(
        {
            2010: [13.2],
            2024: [17.6],
        },
        index=["Lebanon"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    # Defect text from production run 20261021_235451:
    failing_text = "Lebanon's child mortality rose by 4.9 points, climbing from 13.2 to 17.6 per thousand."
    claims = MathIntegrityEngine.extract_claims(failing_text, known_entities=["Lebanon"], scene_number=2)

    report = MathIntegrityEngine.validate_claims(claims, gt, default_entity="Lebanon")

    assert report.is_valid is False
    assert len(report.errors) >= 1
    # Check that discrepancy between 4.9 and 4.4 was flagged
    assert any("Numerical discrepancy" in err or "Internal arithmetic conflict" in err for err in report.errors)


def test_valid_numerical_change_passes():
    """Corrected version of the defect passes validation."""
    df = pd.DataFrame(
        {
            2010: [13.2],
            2024: [17.6],
        },
        index=["Lebanon"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    correct_text = "Lebanon's child mortality rose by 4.4 points, climbing from 13.2 to 17.6 per thousand."
    claims = MathIntegrityEngine.extract_claims(correct_text, known_entities=["Lebanon"], scene_number=2)

    report = MathIntegrityEngine.validate_claims(claims, gt, default_entity="Lebanon")

    assert report.is_valid is True
    assert len(report.errors) == 0


def test_direction_mismatch_detected():
    """Entity decreased, but script claims increase."""
    df = pd.DataFrame(
        {
            2015: [50.0],
            2020: [35.0],
        },
        index=["CountryX"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    bad_text = "CountryX surged by 15 points."
    claims = MathIntegrityEngine.extract_claims(bad_text, known_entities=["CountryX"], scene_number=1)

    report = MathIntegrityEngine.validate_claims(claims, gt, default_entity="CountryX")

    assert report.is_valid is False
    assert any("Direction mismatch" in err for err in report.errors)


def test_zero_baseline_percentage_rejected():
    """Script claims percentage increase from a 0 baseline."""
    df = pd.DataFrame(
        {
            2010: [0.0],
            2020: [10.0],
        },
        index=["SolarGen"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    bad_text = "SolarGen surged by 100%."
    claims = MathIntegrityEngine.extract_claims(bad_text, known_entities=["SolarGen"], scene_number=1)

    report = MathIntegrityEngine.validate_claims(claims, gt, default_entity="SolarGen")

    assert report.is_valid is False
    assert any("Zero baseline error" in err for err in report.errors)


def test_percentage_confusion_on_rate_indicator_flagged():
    """Script reports 4% when the change was 4 points (and relative was 40%)."""
    df = pd.DataFrame(
        {
            2010: [10.0],
            2020: [14.0],
        },
        index=["InfantMortality"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    # Indicator is a rate/percentage
    confused_text = "InfantMortality rose by 4%."
    claims = MathIntegrityEngine.extract_claims(confused_text, known_entities=["InfantMortality"], scene_number=1)

    report = MathIntegrityEngine.validate_claims(
        claims, gt, default_entity="InfantMortality", is_rate_indicator=True
    )

    assert report.is_valid is False
    assert any("Percentage confusion" in err for err in report.errors)


def test_rounding_tolerance_allows_small_floating_point_rounding():
    """True delta is 4.412, claim of 4.4 passes within tolerance."""
    df = pd.DataFrame(
        {
            2010: [10.0],
            2020: [14.412],
        },
        index=["TestCountry"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    text = "TestCountry increased by 4.4 points."
    claims = MathIntegrityEngine.extract_claims(text, known_entities=["TestCountry"], scene_number=1)

    report = MathIntegrityEngine.validate_claims(claims, gt, default_entity="TestCountry")

    assert report.is_valid is True
    assert len(report.errors) == 0


def test_topic_engine_fallback_without_story_metrics():
    """Ensure calculation and validation work identically when story_metrics is absent."""
    df = pd.DataFrame(
        {
            2010: [20.0, 50.0],
            2020: [40.0, 30.0],
        },
        index=["India", "Japan"],
    )
    topic_data = {
        "topic": "Internet Users Rise",
        "indicator_code": "IT.NET.USER.ZS",
        # story_metrics is absent in TopicEngine fallback
    }

    gt = MathIntegrityEngine.compute_ground_truth(df, topic_data)

    assert "India" in gt
    assert "Japan" in gt
    assert gt["India"].abs_change == 20.0
    assert gt["India"].pct_change == 100.0
    assert gt["Japan"].abs_change == -20.0
    assert gt["Japan"].pct_change == -40.0


# =====================================================================
# 4. PHASE 1.1 REGRESSION TESTS
# =====================================================================


def test_script_generation_raises_math_integrity_error_on_unrepaired_math(monkeypatch):
    """Ensure ScriptEngine.generate_script raises MathIntegrityError if repair fails."""
    from app.ai.script import ScriptEngine

    df = pd.DataFrame(
        {
            2010: [13.2],
            2024: [17.6],
        },
        index=["Lebanon"],
    )
    topic_data = {
        "topic": "Lebanon Mortality",
        "indicator_code": "SH.DYN.MORT",
        "story_type": "fastest_growth",
        "selected_countries": ["Lebanon"],
    }

    from app.groq_client import GroqLLM

    raw_dummy = {
        "title": "Lebanon Spike",
        "topic": "Lebanon Mortality",
        "category": "Health",
        "indicator_name": "Mortality Rate",
        "chart_type": "bar_race",
        "total_duration": 20,
        "scenes": [
            {
                "scene_number": 1,
                "duration": 5.0,
                "narration": "Lebanon surged by 50 points.",
                "visual_description": "Intro",
                "text_overlay": "Lebanon",
                "highlight_countries": ["Lebanon"],
            },
            {
                "scene_number": 2,
                "duration": 5.0,
                "narration": "A sharp rise.",
                "visual_description": "Bars moving",
                "text_overlay": "Rising",
                "highlight_countries": ["Lebanon"],
            },
            {
                "scene_number": 3,
                "duration": 5.0,
                "narration": "Higher still.",
                "visual_description": "Climbing",
                "text_overlay": "High",
                "highlight_countries": ["Lebanon"],
            },
            {
                "scene_number": 4,
                "duration": 5.0,
                "narration": "Final peak.",
                "visual_description": "Outro",
                "text_overlay": "Peak",
                "highlight_countries": ["Lebanon"],
            },
        ],
        "fact_check": {
            "is_accurate": True,
            "discrepancies": "none",
        },
        "source_name": "World Bank",
        "source_url": "https://data.worldbank.org",
    }

    monkeypatch.setattr(GroqLLM, "generate_structured", lambda *a, **kw: raw_dummy)
    monkeypatch.setattr(MathIntegrityEngine, "repair_script_math", lambda *a, **kw: False)

    with pytest.raises(MathIntegrityError) as exc_info:
        ScriptEngine.generate_script(topic_data, df, "Mortality Rate")

    assert "mathematical integrity validation" in str(exc_info.value)


def test_percentage_points_not_interpreted_as_relative_percent():
    """Verify '4.4 percentage points' is treated as absolute delta, not 4.4% relative change."""
    df = pd.DataFrame(
        {
            2010: [13.2],
            2024: [17.6],
        },
        index=["Lebanon"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)
    # Ground truth: abs_change = 4.4 points, pct_change = +33.3%

    # 1. Stating "4.4 percentage points"
    points_text = "Lebanon experienced an increase of 4.4 percentage points."
    claims_pts = MathIntegrityEngine.extract_claims(points_text, known_entities=["Lebanon"], scene_number=1)
    assert len(claims_pts) == 1
    c_pts = claims_pts[0]
    assert c_pts.claimed_val == 4.4
    assert c_pts.is_points is True
    assert c_pts.is_percent is False
    assert c_pts.direction == "increase"

    # Validating points claim against ground truth (4.4 points matches 4.4 abs change)
    report_pts = MathIntegrityEngine.validate_claims(claims_pts, gt, default_entity="Lebanon")
    assert report_pts.is_valid is True
    assert len(report_pts.errors) == 0

    # 2. Stating "4.4%" (confused relative percent)
    pct_text = "Lebanon experienced an increase of 4.4%."
    claims_pct = MathIntegrityEngine.extract_claims(pct_text, known_entities=["Lebanon"], scene_number=1)
    assert len(claims_pct) == 1
    c_pct = claims_pct[0]
    assert c_pct.claimed_val == 4.4
    assert c_pct.is_points is False
    assert c_pct.is_percent is True

    # Validating percent claim against ground truth (4.4% does NOT match +33.3% relative change)
    report_pct = MathIntegrityEngine.validate_claims(claims_pct, gt, default_entity="Lebanon")
    assert report_pct.is_valid is False
    assert any("discrepancy" in err.lower() or "confusion" in err.lower() for err in report_pct.errors)


def test_compound_sentence_multi_entity_clause_attribution():
    """Verify clause-aware attribution for:
    'A rise of 4.4 points lifted Lebanon, while a drop of 10% hit Cyprus.'
    """
    df = pd.DataFrame(
        {
            2010: [13.2, 100.0],
            2024: [17.6, 90.0],
        },
        index=["Lebanon", "Cyprus"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    compound_text = "A rise of 4.4 points lifted Lebanon, while a drop of 10% hit Cyprus."
    claims = MathIntegrityEngine.extract_claims(compound_text, known_entities=["Lebanon", "Cyprus"], scene_number=1)

    assert len(claims) == 2

    # Claim 1: Lebanon, +4.4 points
    c1 = claims[0]
    assert c1.entity == "Lebanon"
    assert c1.claimed_val == 4.4
    assert c1.is_points is True
    assert c1.is_percent is False
    assert c1.direction == "increase"
    assert c1.is_ambiguous is False

    # Claim 2: Cyprus, -10%
    c2 = claims[1]
    assert c2.entity == "Cyprus"
    assert c2.claimed_val == 10.0
    assert c2.is_points is False
    assert c2.is_percent is True
    assert c2.direction == "decrease"
    assert c2.is_ambiguous is False

    # Validation should pass cleanly for both entities
    report = MathIntegrityEngine.validate_claims(claims, gt)
    assert report.is_valid is True
    assert len(report.errors) == 0


def test_entity_after_number_attribution():
    """Verify claims where the entity appears after the number are safely attributed."""
    df = pd.DataFrame(
        {
            2010: [13.2],
            2024: [17.6],
        },
        index=["Lebanon"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    text = "A rise of 4.4 points was recorded for Lebanon."
    claims = MathIntegrityEngine.extract_claims(text, known_entities=["Lebanon"], scene_number=1)

    assert len(claims) == 1
    assert claims[0].entity == "Lebanon"
    assert claims[0].claimed_val == 4.4
    assert claims[0].direction == "increase"
    assert claims[0].is_ambiguous is False

    report = MathIntegrityEngine.validate_claims(claims, gt)
    assert report.is_valid is True


def test_ambiguous_claim_fails_closed():
    """Verify that ambiguous multi-entity claims fail closed rather than guessing."""
    df = pd.DataFrame(
        {
            2010: [13.2, 100.0],
            2024: [17.6, 90.0],
        },
        index=["Lebanon", "Cyprus"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    # Both entities in one clause with no clear attribution
    ambiguous_text = "Between Lebanon and Cyprus, a surge of 4.4 points was observed."
    claims = MathIntegrityEngine.extract_claims(ambiguous_text, known_entities=["Lebanon", "Cyprus"], scene_number=1)

    assert len(claims) == 1
    assert claims[0].is_ambiguous is True

    # Fails closed in validation
    report = MathIntegrityEngine.validate_claims(claims, gt)
    assert report.is_valid is False
    assert any("Ambiguous numerical claim" in err for err in report.errors)


def test_small_delta_tight_tolerance():
    """Verify tightened tolerance on small delta (0.25):
    - Admits valid 1-dec (0.3, 0.2) and 2-dec (0.25) rounding
    - Rejects materially incorrect values (0.10, 0.40, 0.50)
    """
    df = pd.DataFrame(
        {
            2010: [1.00],
            2020: [1.25],
        },
        index=["CountryA"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)
    # Expected abs_change = 0.25

    # 1. Valid roundings
    for valid_val in [0.25, 0.3, 0.2]:
        text = f"CountryA increased by {valid_val} points."
        claims = MathIntegrityEngine.extract_claims(text, known_entities=["CountryA"], scene_number=1)
        report = MathIntegrityEngine.validate_claims(claims, gt, default_entity="CountryA")
        assert report.is_valid is True, f"Valid rounding {valid_val} was unexpectedly rejected: {report.errors}"

    # 2. Materially incorrect values
    for invalid_val in [0.10, 0.40, 0.50]:
        text = f"CountryA increased by {invalid_val} points."
        claims = MathIntegrityEngine.extract_claims(text, known_entities=["CountryA"], scene_number=1)
        report = MathIntegrityEngine.validate_claims(claims, gt, default_entity="CountryA")
        assert report.is_valid is False, f"Material error {invalid_val} was unexpectedly accepted!"
        assert any("Numerical discrepancy" in err for err in report.errors)


def test_passive_and_number_first_phrasing():
    """Verify passive and number-first phrasing:
    - Safely identified entity and direction passes
    - Unknown direction or unresolvable entity fails closed
    """
    df = pd.DataFrame(
        {
            2010: [100.0],
            2020: [90.0],
        },
        index=["Cyprus"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    # 1. Safely identified passive decrease
    text_ok = "10% was lost by Cyprus."
    claims_ok = MathIntegrityEngine.extract_claims(text_ok, known_entities=["Cyprus"], scene_number=1)
    assert len(claims_ok) == 1
    assert claims_ok[0].entity == "Cyprus"
    assert claims_ok[0].claimed_val == 10.0
    assert claims_ok[0].direction == "decrease"
    assert claims_ok[0].is_ambiguous is False

    report_ok = MathIntegrityEngine.validate_claims(claims_ok, gt, default_entity="Cyprus")
    assert report_ok.is_valid is True

    # 2. Unknown direction must fail closed
    text_unknown_dir = "10% was registered by Cyprus."
    claims_unknown = MathIntegrityEngine.extract_claims(text_unknown_dir, known_entities=["Cyprus"], scene_number=1)
    assert len(claims_unknown) == 1
    assert claims_unknown[0].is_ambiguous is True

    report_unknown = MathIntegrityEngine.validate_claims(claims_unknown, gt, default_entity="Cyprus")
    assert report_unknown.is_valid is False
    assert any("Ambiguous numerical claim" in err for err in report_unknown.errors)

    # 3. Unidentifiable entity must fail closed
    text_no_entity = "10% was lost across the region."
    claims_no_entity = MathIntegrityEngine.extract_claims(text_no_entity, known_entities=["Cyprus", "Lebanon"], scene_number=1)
    assert len(claims_no_entity) == 1
    assert claims_no_entity[0].is_ambiguous is True

    report_no_entity = MathIntegrityEngine.validate_claims(claims_no_entity, gt)
    assert report_no_entity.is_valid is False
    assert any("Ambiguous numerical claim" in err for err in report_no_entity.errors)


# =====================================================================
# 5. PHASE 1.2 REGRESSION TESTS: MAGNITUDE, SI SCALING & COMMAS
# =====================================================================


def test_magnitude_words_extraction_and_scaling():
    """Verify magnitude words (thousand, million, billion, trillion) and abbreviations are extracted with correct scale."""
    sample_text = (
        "India added 1.2 billion people, while Brazil grew by 500 million. "
        "Japan dropped by 300 thousand, and Global GDP rose by 2.5 trillion."
    )
    claims = MathIntegrityEngine.extract_claims(
        sample_text,
        known_entities=["India", "Brazil", "Japan", "Global GDP"],
        scene_number=1,
    )
    assert len(claims) == 4

    # 1. India: 1.2 billion
    c_ind = next(c for c in claims if c.entity == "India")
    assert c_ind.claimed_val == 1.2
    assert c_ind.scale_multiplier == 1e9
    assert c_ind.scale_word == "billion"
    assert c_ind.direction == "increase"

    # 2. Brazil: 500 million
    c_br = next(c for c in claims if c.entity == "Brazil")
    assert c_br.claimed_val == 500.0
    assert c_br.scale_multiplier == 1e6
    assert c_br.scale_word == "million"
    assert c_br.direction == "increase"

    # 3. Japan: 300 thousand
    c_jp = next(c for c in claims if c.entity == "Japan")
    assert c_jp.claimed_val == 300.0
    assert c_jp.scale_multiplier == 1e3
    assert c_jp.scale_word == "thousand"
    assert c_jp.direction == "decrease"

    # 4. Global GDP: 2.5 trillion
    c_gdp = next(c for c in claims if c.entity == "Global GDP")
    assert c_gdp.claimed_val == 2.5
    assert c_gdp.scale_multiplier == 1e12
    assert c_gdp.scale_word == "trillion"
    assert c_gdp.direction == "increase"


def test_abbreviated_magnitude_suffixes():
    """Verify abbreviated suffixes (k, m, b, t) are parsed cleanly."""
    text = "India rose by 1.2B, while Kenya jumped 500k and US added 2.5T."
    claims = MathIntegrityEngine.extract_claims(text, known_entities=["India", "Kenya", "US"], scene_number=1)
    assert len(claims) == 3

    c_b = next(c for c in claims if c.entity == "India")
    assert c_b.claimed_val == 1.2
    assert c_b.scale_multiplier == 1e9

    c_k = next(c for c in claims if c.entity == "Kenya")
    assert c_k.claimed_val == 500.0
    assert c_k.scale_multiplier == 1e3

    c_t = next(c for c in claims if c.entity == "US")
    assert c_t.claimed_val == 2.5
    assert c_t.scale_multiplier == 1e12


def test_scaled_values_vs_raw_units_validation():
    """Avoid false validation failures when prose expresses scaled value (1.2 billion) but data uses raw units (1,200,000,000)."""
    df = pd.DataFrame(
        {
            2010: [1_000_000_000.0],
            2020: [2_200_000_000.0],
        },
        index=["India"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)
    # Ground truth: abs_change = 1,200,000,000.0

    prose = "India rose by 1.2 billion people."
    claims = MathIntegrityEngine.extract_claims(prose, known_entities=["India"], scene_number=1)
    assert len(claims) == 1
    assert claims[0].claimed_val == 1.2
    assert claims[0].scale_multiplier == 1e9

    report = MathIntegrityEngine.validate_claims(claims, gt, default_entity="India")
    assert report.is_valid is True, f"Validation failed unexpectedly: {report.errors}"


def test_comma_and_decimal_formatted_numbers():
    """Verify comma-separated and currency-prefixed numbers are parsed and validated."""
    df = pd.DataFrame(
        {
            2010: [5_000_000.0],
            2020: [6_250_000.0],
        },
        index=["CompanyA"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    # 1. Comma-formatted raw number
    comma_text = "CompanyA increased by 1,250,000 units."
    claims_comma = MathIntegrityEngine.extract_claims(comma_text, known_entities=["CompanyA"], scene_number=1)
    assert len(claims_comma) == 1
    assert claims_comma[0].claimed_val == 1250000.0
    assert claims_comma[0].scale_multiplier == 1.0

    report_comma = MathIntegrityEngine.validate_claims(claims_comma, gt, default_entity="CompanyA")
    assert report_comma.is_valid is True

    # 2. Decimal-scaled with currency: $1.25 million
    curr_text = "CompanyA added $1.25 million."
    claims_curr = MathIntegrityEngine.extract_claims(curr_text, known_entities=["CompanyA"], scene_number=1)
    assert len(claims_curr) == 1
    assert claims_curr[0].claimed_val == 1.25
    assert claims_curr[0].scale_multiplier == 1e6

    report_curr = MathIntegrityEngine.validate_claims(claims_curr, gt, default_entity="CompanyA")
    assert report_curr.is_valid is True


def test_incorrect_magnitude_rejected():
    """Verify incorrect magnitude words (e.g. million instead of billion) are rejected as numerical discrepancies."""
    df = pd.DataFrame(
        {
            2010: [1_000_000_000.0],
            2020: [2_200_000_000.0],
        },
        index=["India"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)
    # Ground truth: abs_change = 1.2 billion (1,200,000,000)

    # Narration incorrectly claims "1.2 million" instead of 1.2 billion
    bad_text = "India rose by 1.2 million people."
    claims = MathIntegrityEngine.extract_claims(bad_text, known_entities=["India"], scene_number=1)
    assert len(claims) == 1

    report = MathIntegrityEngine.validate_claims(claims, gt, default_entity="India")
    assert report.is_valid is False
    assert any("Numerical discrepancy" in err for err in report.errors)


def test_scaled_endpoints_internal_consistency():
    """Verify internal consistency check handles scaled endpoints."""
    df = pd.DataFrame(
        {
            2010: [1_000_000_000.0],
            2020: [2_300_000_000.0],
        },
        index=["India"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    # 1. Consistent endpoints: from 1.0 billion to 2.3 billion, adding 1.3 billion
    valid_text = "India climbed from 1.0 billion to 2.3 billion, adding 1.3 billion."
    claims_valid = MathIntegrityEngine.extract_claims(valid_text, known_entities=["India"], scene_number=1)
    report_valid = MathIntegrityEngine.validate_claims(claims_valid, gt, default_entity="India")
    assert report_valid.is_valid is True

    # 2. Inconsistent endpoints: from 1.0 billion to 2.3 billion (delta 1.3), but narration claimed change of 2.0 billion
    # Ground truth matches the claimed 2.0 billion so magnitude check passes, isolating the internal arithmetic conflict
    df_2b = pd.DataFrame(
        {
            2010: [1_000_000_000.0],
            2020: [3_000_000_000.0],
        },
        index=["India"],
    )
    gt_2b = MathIntegrityEngine.compute_ground_truth(df_2b)
    inconsistent_text = "India climbed from 1.0 billion to 2.3 billion, adding 2.0 billion."
    claims_bad = MathIntegrityEngine.extract_claims(inconsistent_text, known_entities=["India"], scene_number=1)
    report_bad = MathIntegrityEngine.validate_claims(claims_bad, gt_2b, default_entity="India")
    assert report_bad.is_valid is False
    assert any("Internal arithmetic conflict" in err for err in report_bad.errors)


# =====================================================================
# 10. PHASE 1.4 REGRESSION TESTS: ENDPOINT SCALING & DESTINATION CLAIMS
# =====================================================================


def test_endpoint_scaling_correct_and_incorrect():
    """Verify endpoint scaling behavior (Issue A):
    1. India rose from 1.0 billion to 2.3 billion, adding 1.3 billion -> PASS
    2. India rose from 1.0 billion to 2.3 million, adding 1.3 billion -> FAIL
    3. India rose from 1.0 billion to 2.3 billion, adding 1.3 million -> FAIL
    """
    df = pd.DataFrame(
        {
            2010: [1_000_000_000.0],
            2020: [2_300_000_000.0],
        },
        index=["India"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    # 1. Both endpoints and delta correctly scaled -> PASS
    text_pass = "India rose from 1.0 billion to 2.3 billion, adding 1.3 billion."
    claims_pass = MathIntegrityEngine.extract_claims(text_pass, known_entities=["India"], scene_number=1)
    report_pass = MathIntegrityEngine.validate_claims(claims_pass, gt, default_entity="India")
    assert report_pass.is_valid is True
    assert len(report_pass.errors) == 0

    # 2. Second endpoint incorrectly scaled (million instead of billion) -> FAIL
    text_bad_end = "India rose from 1.0 billion to 2.3 million, adding 1.3 billion."
    claims_bad_end = MathIntegrityEngine.extract_claims(text_bad_end, known_entities=["India"], scene_number=1)
    report_bad_end = MathIntegrityEngine.validate_claims(claims_bad_end, gt, default_entity="India")
    assert report_bad_end.is_valid is False
    assert any("Endpoint end discrepancy" in err for err in report_bad_end.errors)
    assert any("Internal arithmetic conflict" in err for err in report_bad_end.errors)

    # 3. Delta incorrectly scaled (million instead of billion) -> FAIL
    text_bad_delta = "India rose from 1.0 billion to 2.3 billion, adding 1.3 million."
    claims_bad_delta = MathIntegrityEngine.extract_claims(text_bad_delta, known_entities=["India"], scene_number=1)
    report_bad_delta = MathIntegrityEngine.validate_claims(claims_bad_delta, gt, default_entity="India")
    assert report_bad_delta.is_valid is False
    assert any("Numerical discrepancy" in err for err in report_bad_delta.errors)
    assert any("Internal arithmetic conflict" in err for err in report_bad_delta.errors)


def test_valid_delta_cannot_hide_incorrect_endpoints():
    """Verify that a valid delta cannot hide incorrect endpoint values (Issue A.5)."""
    df = pd.DataFrame(
        {
            2010: [1_000_000_000.0],
            2020: [2_300_000_000.0],
        },
        index=["India"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)
    # Correct delta is +1.3 billion, but true endpoints are 1.0B -> 2.3B.
    # Stated endpoints: 5.0B -> 6.3B (delta is 1.3B, perfectly matching ground truth delta and internal arithmetic).
    deceptive_text = "India rose from 5.0 billion to 6.3 billion, adding 1.3 billion."
    claims = MathIntegrityEngine.extract_claims(deceptive_text, known_entities=["India"], scene_number=1)
    report = MathIntegrityEngine.validate_claims(claims, gt, default_entity="India")

    assert report.is_valid is False
    assert any("Endpoint start discrepancy" in err for err in report.errors)
    assert any("Endpoint end discrepancy" in err for err in report.errors)


def test_scale_word_inheritance_on_first_endpoint():
    """Verify scale word on second endpoint is inherited by first endpoint (e.g. from 1.0 to 2.3 billion)."""
    df = pd.DataFrame(
        {
            2010: [1_000_000_000.0],
            2020: [2_300_000_000.0],
        },
        index=["India"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    text = "India rose from 1.0 to 2.3 billion, adding 1.3 billion."
    claims = MathIntegrityEngine.extract_claims(text, known_entities=["India"], scene_number=1)
    assert len(claims) == 1
    c = claims[0]
    assert c.claimed_start == 1.0
    assert c.start_scale_multiplier == 1e9
    assert c.start_scale_word == "billion"
    assert c.claimed_end == 2.3
    assert c.end_scale_multiplier == 1e9
    assert c.end_scale_word == "billion"

    report = MathIntegrityEngine.validate_claims(claims, gt, default_entity="India")
    assert report.is_valid is True
    assert len(report.errors) == 0


def test_standalone_range_claims():
    """Verify standalone 'from X to Y' claims without an explicit 'adding Z' clause."""
    df = pd.DataFrame(
        {
            2010: [1_000_000_000.0],
            2020: [2_300_000_000.0],
        },
        index=["India"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    # Valid standalone range
    text_valid = "India climbed from 1.0 billion to 2.3 billion."
    claims_valid = MathIntegrityEngine.extract_claims(text_valid, known_entities=["India"], scene_number=1)
    assert len(claims_valid) == 1
    assert claims_valid[0].claim_type == "range"
    assert claims_valid[0].direction == "increase"
    report_valid = MathIntegrityEngine.validate_claims(claims_valid, gt, default_entity="India")
    assert report_valid.is_valid is True

    # Standalone range with incorrect end scale
    text_invalid = "India climbed from 1.0 billion to 2.3 million."
    claims_invalid = MathIntegrityEngine.extract_claims(text_invalid, known_entities=["India"], scene_number=1)
    assert len(claims_invalid) == 1
    report_invalid = MathIntegrityEngine.validate_claims(claims_invalid, gt, default_entity="India")
    assert report_invalid.is_valid is False
    assert any("Endpoint end discrepancy" in err for err in report_invalid.errors)


def test_destination_level_claims_upward():
    """Verify destination claims for upward trends: correct vs incorrect levels (Issue B)."""
    df = pd.DataFrame(
        {
            2010: [1_000_000_000.0],
            2020: [2_300_000_000.0],
        },
        index=["India"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    # Correct destination level -> PASS
    pass_text = "India increased to 2.3 billion."
    claims_pass = MathIntegrityEngine.extract_claims(pass_text, known_entities=["India"], scene_number=1)
    assert len(claims_pass) == 1
    assert claims_pass[0].claim_type == "destination"
    assert claims_pass[0].claimed_val == 2.3
    assert claims_pass[0].scale_multiplier == 1e9
    report_pass = MathIntegrityEngine.validate_claims(claims_pass, gt, default_entity="India")
    assert report_pass.is_valid is True

    # Incorrect scale (million instead of billion) -> FAIL
    fail_scale_text = "India increased to 2.3 million."
    claims_fail_scale = MathIntegrityEngine.extract_claims(fail_scale_text, known_entities=["India"], scene_number=1)
    assert len(claims_fail_scale) == 1
    report_fail_scale = MathIntegrityEngine.validate_claims(claims_fail_scale, gt, default_entity="India")
    assert report_fail_scale.is_valid is False
    assert any("Destination discrepancy" in err for err in report_fail_scale.errors)

    # Incorrect value (3.5 billion instead of 2.3 billion) -> FAIL
    fail_val_text = "India increased to 3.5 billion."
    claims_fail_val = MathIntegrityEngine.extract_claims(fail_val_text, known_entities=["India"], scene_number=1)
    report_fail_val = MathIntegrityEngine.validate_claims(claims_fail_val, gt, default_entity="India")
    assert report_fail_val.is_valid is False
    assert any("Destination discrepancy" in err for err in report_fail_val.errors)


def test_destination_level_claims_downward():
    """Verify destination claims for downward trends: correct vs incorrect levels (Issue B)."""
    df = pd.DataFrame(
        {
            2010: [1_000_000_000.0],
            2020: [800_000_000.0],
        },
        index=["India"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    # Correct downward destination level -> PASS
    pass_text = "India fell to 800 million."
    claims_pass = MathIntegrityEngine.extract_claims(pass_text, known_entities=["India"], scene_number=1)
    assert len(claims_pass) == 1
    assert claims_pass[0].claim_type == "destination"
    assert claims_pass[0].direction == "decrease"
    report_pass = MathIntegrityEngine.validate_claims(claims_pass, gt, default_entity="India")
    assert report_pass.is_valid is True

    # Incorrect downward destination scale (thousand instead of million) -> FAIL
    fail_scale_text = "India fell to 800 thousand."
    claims_fail_scale = MathIntegrityEngine.extract_claims(fail_scale_text, known_entities=["India"], scene_number=1)
    report_fail_scale = MathIntegrityEngine.validate_claims(claims_fail_scale, gt, default_entity="India")
    assert report_fail_scale.is_valid is False
    assert any("Destination discrepancy" in err for err in report_fail_scale.errors)

    # Incorrect downward destination value (500 million instead of 800 million) -> FAIL
    fail_val_text = "India fell to 500 million."
    claims_fail_val = MathIntegrityEngine.extract_claims(fail_val_text, known_entities=["India"], scene_number=1)
    report_fail_val = MathIntegrityEngine.validate_claims(claims_fail_val, gt, default_entity="India")
    assert report_fail_val.is_valid is False
    assert any("Destination discrepancy" in err for err in report_fail_val.errors)


def test_destination_claim_direction_mismatch():
    """Verify destination claim with wrong direction verb is rejected."""
    df = pd.DataFrame(
        {
            2010: [1_000_000_000.0],
            2020: [2_300_000_000.0],
        },
        index=["India"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    # Data increased to 2.3 billion, but narration claims 'fell to 2.3 billion'
    wrong_dir_text = "India fell to 2.3 billion."
    claims = MathIntegrityEngine.extract_claims(wrong_dir_text, known_entities=["India"], scene_number=1)
    report = MathIntegrityEngine.validate_claims(claims, gt, default_entity="India")
    assert report.is_valid is False
    assert any("Direction mismatch" in err for err in report.errors)


def test_destination_compared_against_endpoint_not_delta():
    """Verify destination claim validates against end_val, NOT abs_change."""
    df = pd.DataFrame(
        {
            2010: [1_000_000_000.0],
            2020: [2_300_000_000.0],
        },
        index=["India"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)
    # abs_change is 1.3 billion, end_val is 2.3 billion.
    # Claiming 'increased to 1.3 billion' confuses delta with destination -> FAIL
    confused_text = "India increased to 1.3 billion."
    claims = MathIntegrityEngine.extract_claims(confused_text, known_entities=["India"], scene_number=1)
    report = MathIntegrityEngine.validate_claims(claims, gt, default_entity="India")
    assert report.is_valid is False
    assert any("Destination discrepancy" in err for err in report.errors)


def test_combined_destination_and_delta_in_single_sentence():
    """Verify sentence containing both destination level and delta claim."""
    df = pd.DataFrame(
        {
            2010: [1_000_000_000.0],
            2020: [2_300_000_000.0],
        },
        index=["India"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    # 1. Both destination and delta correct -> PASS
    both_correct = "India increased to 2.3 billion, adding 1.3 billion."
    claims_both = MathIntegrityEngine.extract_claims(both_correct, known_entities=["India"], scene_number=1)
    assert len(claims_both) == 2
    report_both = MathIntegrityEngine.validate_claims(claims_both, gt, default_entity="India")
    assert report_both.is_valid is True

    # 2. Destination incorrect scale, delta correct -> FAIL
    bad_dest = "India increased to 2.3 million, adding 1.3 billion."
    claims_bad_dest = MathIntegrityEngine.extract_claims(bad_dest, known_entities=["India"], scene_number=1)
    report_bad_dest = MathIntegrityEngine.validate_claims(claims_bad_dest, gt, default_entity="India")
    assert report_bad_dest.is_valid is False
    assert any("Destination discrepancy" in err for err in report_bad_dest.errors)

    # 3. Destination correct, delta incorrect scale -> FAIL
    bad_delta = "India increased to 2.3 billion, adding 1.3 million."
    claims_bad_delta = MathIntegrityEngine.extract_claims(bad_delta, known_entities=["India"], scene_number=1)
    report_bad_delta = MathIntegrityEngine.validate_claims(claims_bad_delta, gt, default_entity="India")
    assert report_bad_delta.is_valid is False
    assert any("Numerical discrepancy" in err for err in report_bad_delta.errors)


def test_non_destination_phrases_not_misidentified():
    """Verify that general 'to X' phrases, calendar years, and non-change verbs are not treated as destination claims."""
    # Calendar year
    text_year = "India grew from 2010 to 2024."
    claims_year = MathIntegrityEngine.extract_claims(text_year, known_entities=["India"])
    assert len(claims_year) == 0

    # Non-change verb
    text_non_change = "India moved to 5 locations."
    claims_non_change = MathIntegrityEngine.extract_claims(text_non_change, known_entities=["India"])
    assert len(claims_non_change) == 0

    # Comparison preposition
    text_comp = "India had high growth compared to 2.3 billion."
    claims_comp = MathIntegrityEngine.extract_claims(text_comp, known_entities=["India"])
    assert len(claims_comp) == 0


def test_rate_indicator_points_and_percentage_destination():
    """Verify destination claims for rate indicators supporting points and percent."""
    df = pd.DataFrame(
        {
            2010: [13.2],
            2020: [17.6],
        },
        index=["Lebanon"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    # Correct percent destination
    text_pct = "Lebanon rose to 17.6%."
    claims_pct = MathIntegrityEngine.extract_claims(text_pct, known_entities=["Lebanon"], scene_number=1)
    report_pct = MathIntegrityEngine.validate_claims(claims_pct, gt, default_entity="Lebanon")
    assert report_pct.is_valid is True

    # Incorrect percent destination
    text_bad_pct = "Lebanon rose to 25.0%."
    claims_bad_pct = MathIntegrityEngine.extract_claims(text_bad_pct, known_entities=["Lebanon"], scene_number=1)
    report_bad_pct = MathIntegrityEngine.validate_claims(claims_bad_pct, gt, default_entity="Lebanon")
    assert report_bad_pct.is_valid is False
    assert any("Destination discrepancy" in err for err in report_bad_pct.errors)

    # Correct points destination
    text_pts = "Lebanon rose to 17.6 points."
    claims_pts = MathIntegrityEngine.extract_claims(text_pts, known_entities=["Lebanon"], scene_number=1)
    report_pts = MathIntegrityEngine.validate_claims(claims_pts, gt, default_entity="Lebanon")
    assert report_pts.is_valid is True


def test_multi_entity_sentence_with_conjunction_attribution():
    """Verify production fix:
    'Saudi Arabia leads at 6.48% (#1) and Lebanon jumps to 2.51%, overtaking India’s 2.30%.'
    Attributed unambiguously to Lebanon without false positive ambiguity flag.
    """
    df = pd.DataFrame(
        {
            2016: [6.48, 1.50, 2.55],
            2025: [6.48, 2.51, 2.30],
        },
        index=["Saudi Arabia", "Lebanon", "India"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    text = "Saudi Arabia leads at 6.48% (#1) and Lebanon jumps to 2.51%, overtaking India’s 2.30%."
    claims = MathIntegrityEngine.extract_claims(
        text,
        known_entities=["Saudi Arabia", "Lebanon", "India"],
        scene_number=3,
    )

    assert len(claims) == 1
    assert claims[0].entity == "Lebanon"
    assert claims[0].claimed_val == 2.51
    assert claims[0].direction == "increase"
    assert claims[0].is_ambiguous is False

    report = MathIntegrityEngine.validate_claims(claims, gt)
    assert report.is_valid is True
    assert len(report.errors) == 0


def test_compound_subject_vs_independent_clause_attribution():
    """Verify compound subject ('India and China') remains ambiguous,
    while independent clauses joined by conjunction ('Delhi slipped... and Beijing jumped...') are cleanly attributed.
    """
    df = pd.DataFrame(
        {
            2016: [2.55, 1.50],
            2025: [2.30, 1.80],
        },
        index=["India", "China"],
    )
    gt = MathIntegrityEngine.compute_ground_truth(df)

    # 1. Compound subject fails closed as ambiguous
    compound_text = "India and China jumped by 5%."
    claims_compound = MathIntegrityEngine.extract_claims(
        compound_text,
        known_entities=["India", "China"],
        scene_number=1,
    )
    assert len(claims_compound) == 1
    assert claims_compound[0].is_ambiguous is True

    # 2. Independent clauses with metric before conjunction are cleanly attributed
    clause_text = "Delhi slipped to 2.30% and Beijing jumped to 1.80%."
    claims_clauses = MathIntegrityEngine.extract_claims(
        clause_text,
        known_entities=["India", "China"],
        scene_number=1,
    )
    assert len(claims_clauses) == 2
    c_ind = next(c for c in claims_clauses if c.entity == "India")
    c_chn = next(c for c in claims_clauses if c.entity == "China")
    assert c_ind.claimed_val == 2.30
    assert c_ind.is_ambiguous is False
    assert c_chn.claimed_val == 1.80
    assert c_chn.is_ambiguous is False

    report = MathIntegrityEngine.validate_claims(claims_clauses, gt)
    assert report.is_valid is True
    assert len(report.errors) == 0


def test_tuple_index_dataframe_ground_truth_and_claim_validation():
    """Verify DataFrames with tuple indices (e.g. ('IND', 'India') from World Bank)
    are cleanly normalized into human-readable canonical names in ground truth and claims.
    """
    tuple_index = [
        ("UKR", "Ukraine"),
        ("LUX", "Luxembourg"),
        ("BFA", "Burkina Faso"),
        ("DNK", "Denmark"),
        ("CHN", "China"),
        ("IND", "India"),
    ]
    df = pd.DataFrame(
        [
            [10.0, 39.56],
            [0.50, 0.85],
            [1.00, 3.30],
            [2.00, 3.25],
            [1.50, 1.72],
            [2.55, 2.30],
        ],
        index=tuple_index,
        columns=[2016, 2025],
    )

    gt = MathIntegrityEngine.compute_ground_truth(df)

    # Ensure canonical country names are keys, not stringified tuples
    assert "India" in gt
    assert "China" in gt
    assert "Ukraine" in gt
    assert "('IND', 'India')" not in gt

    assert gt["India"].start_val == 2.55
    assert gt["India"].end_val == 2.30
    assert gt["India"].direction == "decrease"

    text = "India fell to 2.30% while Ukraine reached 39.56%."
    claims = MathIntegrityEngine.extract_claims(text, known_entities=list(gt.keys()), scene_number=1)
    assert len(claims) >= 1

    c_ind = next(c for c in claims if c.entity == "India")
    assert c_ind.claimed_val == 2.30
    assert c_ind.direction == "decrease"
    assert c_ind.is_ambiguous is False

    report = MathIntegrityEngine.validate_claims(claims, gt)
    assert report.is_valid is True
    assert len(report.errors) == 0



