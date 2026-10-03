#!/usr/bin/env python3
"""
Content Quality Validation Tests

Tests the ContentQualityValidator which validates that a selected
story can safely become video content.

Tests:
1. Valid story passes
2. Missing title fails
3. Missing provider fails
4. Invalid year range fails
5. Empty data fails
6. Non-numeric value fails
7. Wrong story direction fails
8. Unsupported numerical claim fails
9. Misleading title fails
10. Empty script fails
11. Placeholder script fails
12. Valid script passes
13. Script with contradictory claim fails
14. Source metadata missing is detected
"""

import sys
import math

from app.topic.content_quality import ContentQualityValidator


def _make_valid_story_data():
    """Create a valid story data dict for testing."""
    return {
        "provider_id": "ai_index",
        "indicator_code": "ai_investment",
        "indicator_name": "AI Investment",
        "story_type": "fastest_growth",
        "chart_type": "top5_change",
        "topic_family": "ai_investment",
        "years": 5,
        "category": "AI",
        "source_name": "Stanford AI Index",
        "source_url": "https://hai.stanford.edu/ai-index",
        "topic": "AI Investment: Fastest Growth",
        "smart_score": 91.67,
        "story_metrics": {
            "entity": "United States",
            "start_year": 2021,
            "end_year": 2025,
            "start_value": 100.0,
            "end_value": 150.0,
            "absolute_change": 50.0,
            "percentage_change": 50.0,
            "start_rank": 3.0,
            "end_rank": 1.0,
            "rank_change": 2.0,
            "number_of_valid_countries": 6,
            "number_of_valid_years": 5,
            "data_completeness": 0.95,
            "leader_separation": 0.15,
            "trend_strength": 0.85,
            "story_type": "fastest_growth",
        },
    }


def test_valid_story_passes():
    """TEST 1: Valid story passes."""
    print("\n" + "=" * 70)
    print("TEST 1: Valid story passes")
    print("=" * 70)

    story_data = _make_valid_story_data()
    result = ContentQualityValidator.validate(story_data)

    assert result["valid"] is True, (
        f"Valid story should pass, but failed: {result['reasons']}"
    )
    assert result["score"] == 100.0, (
        f"Valid story should score 100, got {result['score']}"
    )

    print(f"✓ Valid story passed validation")
    print(f"  Score: {result['score']}")
    print(f"  Checks: {len(result['checks'])}")
    return True


def test_missing_title_fails():
    """TEST 2: Missing title fails."""
    print("\n" + "=" * 70)
    print("TEST 2: Missing title fails")
    print("=" * 70)

    story_data = _make_valid_story_data()
    story_data["topic"] = ""

    result = ContentQualityValidator.validate(story_data)

    assert result["valid"] is False, (
        "Missing title should fail validation"
    )
    assert any(
        "title" in r.lower() or "topic" in r.lower()
        for r in result["reasons"]
    ), f"Should mention title/topic: {result['reasons']}"

    print(f"✓ Missing title correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_missing_provider_fails():
    """TEST 3: Missing provider fails."""
    print("\n" + "=" * 70)
    print("TEST 3: Missing provider fails")
    print("=" * 70)

    story_data = _make_valid_story_data()
    story_data["provider_id"] = ""

    result = ContentQualityValidator.validate(story_data)

    assert result["valid"] is False, (
        "Missing provider should fail validation"
    )
    assert any(
        "provider" in r.lower()
        for r in result["reasons"]
    ), f"Should mention provider: {result['reasons']}"

    print(f"✓ Missing provider correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_invalid_year_range_fails():
    """TEST 4: Invalid year range fails."""
    print("\n" + "=" * 70)
    print("TEST 4: Invalid year range fails")
    print("=" * 70)

    story_data = _make_valid_story_data()
    story_data["story_metrics"]["start_year"] = 2025
    story_data["story_metrics"]["end_year"] = 2021

    result = ContentQualityValidator.validate(story_data)

    assert result["valid"] is False, (
        "Invalid year range should fail validation"
    )
    assert any(
        "start_year" in r.lower() or "end_year" in r.lower()
        for r in result["reasons"]
    ), f"Should mention year range: {result['reasons']}"

    print(f"✓ Invalid year range correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_empty_data_fails():
    """TEST 5: Empty data fails."""
    print("\n" + "=" * 70)
    print("TEST 5: Empty data fails")
    print("=" * 70)

    story_data = _make_valid_story_data()
    story_data["story_metrics"]["entity"] = ""
    story_data["story_metrics"]["start_value"] = None
    story_data["story_metrics"]["end_value"] = None

    result = ContentQualityValidator.validate(story_data)

    assert result["valid"] is False, (
        "Empty data should fail validation"
    )
    assert any(
        "entity" in r.lower() or "start_value" in r.lower()
        for r in result["reasons"]
    ), f"Should mention missing data: {result['reasons']}"

    print(f"✓ Empty data correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_non_numeric_value_fails():
    """TEST 6: Non-numeric value fails."""
    print("\n" + "=" * 70)
    print("TEST 6: Non-numeric value fails")
    print("=" * 70)

    story_data = _make_valid_story_data()
    story_data["story_metrics"]["start_value"] = "not_a_number"

    result = ContentQualityValidator.validate(story_data)

    assert result["valid"] is False, (
        "Non-numeric value should fail validation"
    )
    assert any(
        "start_value" in r.lower()
        for r in result["reasons"]
    ), f"Should mention start_value: {result['reasons']}"

    print(f"✓ Non-numeric value correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_wrong_story_direction_fails():
    """TEST 7: Wrong story direction fails."""
    print("\n" + "=" * 70)
    print("TEST 7: Wrong story direction fails")
    print("=" * 70)

    story_data = _make_valid_story_data()
    # fastest_growth but percentage_change is negative
    story_data["story_metrics"]["percentage_change"] = -10.0
    story_data["story_metrics"]["absolute_change"] = -10.0
    story_data["story_metrics"]["start_value"] = 100.0
    story_data["story_metrics"]["end_value"] = 90.0

    result = ContentQualityValidator.validate(story_data)

    assert result["valid"] is False, (
        "Wrong story direction should fail validation"
    )
    assert any(
        "fastest_growth" in r.lower() or "non-positive" in r.lower()
        for r in result["reasons"]
    ), f"Should mention story direction: {result['reasons']}"

    print(f"✓ Wrong story direction correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_unsupported_numerical_claim_fails():
    """TEST 8: Unsupported numerical claim fails."""
    print("\n" + "=" * 70)
    print("TEST 8: Unsupported numerical claim fails")
    print("=" * 70)

    story_data = _make_valid_story_data()
    # Make absolute_change inconsistent with start/end values
    story_data["story_metrics"]["start_value"] = 100.0
    story_data["story_metrics"]["end_value"] = 150.0
    story_data["story_metrics"]["absolute_change"] = 999.0  # Wrong!

    result = ContentQualityValidator.validate(story_data)

    assert result["valid"] is False, (
        "Inconsistent numerical claim should fail validation"
    )
    assert any(
        "absolute_change" in r.lower()
        for r in result["reasons"]
    ), f"Should mention absolute_change: {result['reasons']}"

    print(f"✓ Unsupported numerical claim correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_misleading_title_fails():
    """TEST 9: Misleading title fails."""
    print("\n" + "=" * 70)
    print("TEST 9: Misleading title fails")
    print("=" * 70)

    story_data = _make_valid_story_data()
    # Title says "Fastest Growth" but data is declining
    story_data["topic"] = "AI Investment: Fastest Growth"
    story_data["story_metrics"]["percentage_change"] = -5.0
    story_data["story_metrics"]["absolute_change"] = -5.0
    story_data["story_metrics"]["start_value"] = 100.0
    story_data["story_metrics"]["end_value"] = 95.0

    result = ContentQualityValidator.validate(story_data)

    assert result["valid"] is False, (
        "Misleading title should fail validation"
    )
    assert any(
        "fastest growth" in r.lower()
        for r in result["reasons"]
    ), f"Should mention misleading title: {result['reasons']}"

    print(f"✓ Misleading title correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_empty_script_fails():
    """TEST 10: Empty script fails."""
    print("\n" + "=" * 70)
    print("TEST 10: Empty script fails")
    print("=" * 70)

    story_data = _make_valid_story_data()
    result = ContentQualityValidator.validate(
        story_data,
        script=""
    )

    assert result["valid"] is False, (
        "Empty script should fail validation"
    )
    assert any(
        "script" in r.lower()
        for r in result["reasons"]
    ), f"Should mention script: {result['reasons']}"

    print(f"✓ Empty script correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_placeholder_script_fails():
    """TEST 11: Placeholder script fails."""
    print("\n" + "=" * 70)
    print("TEST 11: Placeholder script fails")
    print("=" * 70)

    story_data = _make_valid_story_data()
    result = ContentQualityValidator.validate(
        story_data,
        script="This is a [INSERT VALUE] placeholder script with enough words to pass the minimum word count check."
    )

    assert result["valid"] is False, (
        "Placeholder script should fail validation"
    )
    assert any(
        "placeholder" in r.lower()
        for r in result["reasons"]
    ), f"Should mention placeholder: {result['reasons']}"

    print(f"✓ Placeholder script correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_valid_script_passes():
    """TEST 12: Valid script passes."""
    print("\n" + "=" * 70)
    print("TEST 12: Valid script passes")
    print("=" * 70)

    story_data = _make_valid_story_data()
    valid_script = (
        "AI Investment in the United States has grown significantly "
        "from 2021 to 2025. The data shows a strong upward trend "
        "with the country leading in AI funding. This represents "
        "a major shift in the global AI landscape over the past "
        "five years, with investment increasing substantially."
    )

    result = ContentQualityValidator.validate(
        story_data,
        script=valid_script
    )

    assert result["valid"] is True, (
        f"Valid script should pass, but failed: {result['reasons']}"
    )

    print(f"✓ Valid script passed validation")
    print(f"  Score: {result['score']}")
    return True


def test_script_with_contradictory_claim_fails():
    """TEST 13: Script with contradictory claim fails."""
    print("\n" + "=" * 70)
    print("TEST 13: Script with contradictory claim fails")
    print("=" * 70)

    story_data = _make_valid_story_data()
    # Script contains debug text
    result = ContentQualityValidator.validate(
        story_data,
        script="DEBUG: This is a debug script with enough words to pass the minimum word count check here."
    )

    assert result["valid"] is False, (
        "Script with debug text should fail validation"
    )
    assert any(
        "debug" in r.lower()
        for r in result["reasons"]
    ), f"Should mention debug text: {result['reasons']}"

    print(f"✓ Script with contradictory claim correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_source_metadata_missing_detected():
    """TEST 14: Source metadata missing is detected."""
    print("\n" + "=" * 70)
    print("TEST 14: Source metadata missing is detected")
    print("=" * 70)

    story_data = _make_valid_story_data()
    story_data["source_name"] = ""
    story_data["source_url"] = ""

    result = ContentQualityValidator.validate(story_data)

    assert result["valid"] is False, (
        "Missing source metadata should fail validation"
    )
    assert any(
        "source" in r.lower()
        for r in result["reasons"]
    ), f"Should mention source: {result['reasons']}"

    print(f"✓ Missing source metadata correctly detected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_fabricated_source_detected():
    """TEST 15: Fabricated source name is detected."""
    print("\n" + "=" * 70)
    print("TEST 15: Fabricated source detected")
    print("=" * 70)

    story_data = _make_valid_story_data()
    story_data["source_name"] = "Fake Data Source"
    story_data["source_url"] = "https://example.com"

    result = ContentQualityValidator.validate(story_data)

    assert result["valid"] is False, (
        "Fabricated source should fail validation"
    )
    assert any(
        "fabricated" in r.lower()
        for r in result["reasons"]
    ), f"Should mention fabricated source: {result['reasons']}"

    print(f"✓ Fabricated source correctly detected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_nan_value_fails():
    """TEST 16: NaN value fails."""
    print("\n" + "=" * 70)
    print("TEST 16: NaN value fails")
    print("=" * 70)

    story_data = _make_valid_story_data()
    story_data["story_metrics"]["start_value"] = float("nan")

    result = ContentQualityValidator.validate(story_data)

    assert result["valid"] is False, (
        "NaN value should fail validation"
    )
    assert any(
        "start_value" in r.lower()
        for r in result["reasons"]
    ), f"Should mention start_value: {result['reasons']}"

    print(f"✓ NaN value correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_infinity_value_fails():
    """TEST 17: Infinity value fails."""
    print("\n" + "=" * 70)
    print("TEST 17: Infinity value fails")
    print("=" * 70)

    story_data = _make_valid_story_data()
    story_data["story_metrics"]["end_value"] = float("inf")

    result = ContentQualityValidator.validate(story_data)

    assert result["valid"] is False, (
        "Infinity value should fail validation"
    )
    assert any(
        "end_value" in r.lower()
        for r in result["reasons"]
    ), f"Should mention end_value: {result['reasons']}"

    print(f"✓ Infinity value correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_deterministic_behavior():
    """TEST 18: Deterministic behavior."""
    print("\n" + "=" * 70)
    print("TEST 18: Deterministic behavior")
    print("=" * 70)

    story_data = _make_valid_story_data()

    result1 = ContentQualityValidator.validate(story_data)
    result2 = ContentQualityValidator.validate(story_data)

    assert result1 == result2, (
        "Same input should produce same output"
    )

    print(f"✓ Deterministic behavior verified")
    print(f"  Result 1 valid: {result1['valid']}")
    print(f"  Result 2 valid: {result2['valid']}")
    return True


def test_story_candidate_object():
    """TEST 19: Validator works with StoryCandidate objects."""
    print("\n" + "=" * 70)
    print("TEST 19: StoryCandidate object support")
    print("=" * 70)

    from app.topic.smart_story import StoryCandidate

    metrics = _make_valid_story_data()["story_metrics"]
    candidate = StoryCandidate(
        provider_id="ai_index",
        indicator_code="ai_investment",
        indicator_name="AI Investment",
        story_type="fastest_growth",
        chart_type="top5_change",
        topic_family="ai_investment",
        years=5,
        category="AI",
        source_name="Stanford AI Index",
        source_url="https://hai.stanford.edu/ai-index",
        topic="AI Investment: Fastest Growth",
        score=91.67,
        metrics=metrics,
    )

    result = ContentQualityValidator.validate(candidate)

    assert result["valid"] is True, (
        f"Valid StoryCandidate should pass: {result['reasons']}"
    )

    print(f"✓ StoryCandidate object validated successfully")
    print(f"  Score: {result['score']}")
    return True


def main():
    print("\n")
    print("=" * 70)
    print("CONTENT QUALITY VALIDATION TESTS")
    print("=" * 70)

    all_tests = [
        ("VALID_STORY_PASSES", test_valid_story_passes),
        ("MISSING_TITLE_FAILS", test_missing_title_fails),
        ("MISSING_PROVIDER_FAILS", test_missing_provider_fails),
        ("INVALID_YEAR_RANGE_FAILS", test_invalid_year_range_fails),
        ("EMPTY_DATA_FAILS", test_empty_data_fails),
        ("NON_NUMERIC_VALUE_FAILS", test_non_numeric_value_fails),
        ("WRONG_STORY_DIRECTION_FAILS", test_wrong_story_direction_fails),
        ("UNSUPPORTED_NUMERICAL_CLAIM_FAILS", test_unsupported_numerical_claim_fails),
        ("MISLEADING_TITLE_FAILS", test_misleading_title_fails),
        ("EMPTY_SCRIPT_FAILS", test_empty_script_fails),
        ("PLACEHOLDER_SCRIPT_FAILS", test_placeholder_script_fails),
        ("VALID_SCRIPT_PASSES", test_valid_script_passes),
        ("SCRIPT_CONTRADICTORY_FAILS", test_script_with_contradictory_claim_fails),
        ("SOURCE_METADATA_MISSING", test_source_metadata_missing_detected),
        ("FABRICATED_SOURCE_DETECTED", test_fabricated_source_detected),
        ("NAN_VALUE_FAILS", test_nan_value_fails),
        ("INFINITY_VALUE_FAILS", test_infinity_value_fails),
        ("DETERMINISTIC_BEHAVIOR", test_deterministic_behavior),
        ("STORY_CANDIDATE_OBJECT", test_story_candidate_object),
    ]

    results = []

    for name, func in all_tests:
        try:
            passed = func()
            results.append((name, passed))
        except Exception as error:
            print(f"\n✗ EXCEPTION: {error}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed_count = sum(1 for _, passed in results if passed)
    total = len(results)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed_count}/{total} tests passed")

    if passed_count == total:
        print("\n✅ ALL CONTENT QUALITY VALIDATION TESTS PASSED")
        return True
    else:
        print("\n❌ SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
