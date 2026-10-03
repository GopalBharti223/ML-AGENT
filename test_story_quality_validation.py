#!/usr/bin/env python3
"""
Tests for StoryQualityValidator

Validates that generated story candidates are genuinely supported
by their underlying data.

Tests:
1. Valid candidate passes
2. Missing entity fails
3. Insufficient entities fails
4. Insufficient years fails
5. Low completeness fails
6. Wrong story direction fails
7. Near-zero base percentage change is rejected
8. Consistent signals pass
9. Clearly contradictory signals fail
10. Obviously misleading title fails
"""

import sys

import pandas as pd

from app.topic.story_quality import StoryQualityValidator


SAMPLE_COUNTRIES = [
    ("US", "United States"),
    ("CN", "China"),
    ("IN", "India"),
    ("GB", "United Kingdom"),
    ("DE", "Germany"),
    ("FR", "France"),
    ("JP", "Japan"),
    ("BR", "Brazil"),
]


def sample_metrics(**overrides):
    """Build a realistic metrics dict like SmartStoryEngine produces."""
    # Underlying wide-format data used for entity cross-check.
    sample_data = pd.DataFrame(
        index=pd.MultiIndex.from_tuples(
            SAMPLE_COUNTRIES,
            names=["country_code", "country"],
        ),
        columns=[2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
        data=100.0,
    )

    # latest_sorted is a Series indexed the same way.
    latest_sorted = pd.Series(
        [150.0, 140.0, 150.0, 120.0, 110.0, 100.0, 90.0, 80.0],
        index=pd.MultiIndex.from_tuples(
            SAMPLE_COUNTRIES,
            names=["country_code", "country"],
        ),
    )

    metrics = {
        "number_of_valid_countries": 8,
        "number_of_valid_years": 10,
        "data_completeness": 0.95,
        "entity": "India",
        "start_value": 100.0,
        "end_value": 150.0,
        "absolute_change": 50.0,
        "percentage_change": 0.50,
        "start_rank": 5.0,
        "end_rank": 3.0,
        "rank_change": 2.0,
        "trend_strength": 0.85,
        "leader_separation": 0.40,
        "story_type": "fastest_growth",
        "indicator_code": "NY.GDP.PCAP.CD",
        "indicator_name": "GDP Per Capita",
        "topic_family": "economy",
        "data": sample_data,
        "latest_sorted": latest_sorted,
    }
    metrics.update(overrides)
    return metrics


def valid_title():
    return "GDP Per Capita: Fastest Growth"


def test_1_valid_candidate_passes():
    print("=" * 70)
    print("TEST 1: Valid Candidate Passes")
    print("=" * 70)

    result = StoryQualityValidator.validate(
        sample_metrics(),
        title=valid_title(),
    )

    assert result["valid"] is True, (
        f"Expected valid, got reasons: {result['reasons']}"
    )
    print(f"✓ Valid candidate passed")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_2_missing_entity_fails():
    print("\n" + "=" * 70)
    print("TEST 2: Missing Entity Fails")
    print("=" * 70)

    result = StoryQualityValidator.validate(
        sample_metrics(entity="Phantom Land"),
        title=valid_title(),
    )

    assert result["valid"] is False, (
        "Expected invalid for missing entity"
    )
    assert "entity" in str(result["reasons"]).lower(), (
        f"Reasons should mention entity: {result['reasons']}"
    )
    print(f"✓ Missing entity correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_3_insufficient_entities_fails():
    print("\n" + "=" * 70)
    print("TEST 3: Insufficient Entities Fails")
    print("=" * 70)

    result = StoryQualityValidator.validate(
        sample_metrics(number_of_valid_countries=2),
        title=valid_title(),
    )

    assert result["valid"] is False, (
        "Expected invalid for insufficient entities"
    )
    assert any(
        "countries" in reason.lower()
        for reason in result["reasons"]
    ), f"Reasons should mention countries: {result['reasons']}"
    print(f"✓ Insufficient entities correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_4_insufficient_years_fails():
    print("\n" + "=" * 70)
    print("TEST 4: Insufficient Years Fails")
    print("=" * 70)

    result = StoryQualityValidator.validate(
        sample_metrics(number_of_valid_years=2),
        title=valid_title(),
    )

    assert result["valid"] is False, (
        "Expected invalid for insufficient years"
    )
    assert any(
        "years" in reason.lower()
        for reason in result["reasons"]
    ), f"Reasons should mention years: {result['reasons']}"
    print(f"✓ Insufficient years correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_5_low_completeness_fails():
    print("\n" + "=" * 70)
    print("TEST 5: Low Completeness Fails")
    print("=" * 70)

    result = StoryQualityValidator.validate(
        sample_metrics(data_completeness=0.25),
        title=valid_title(),
    )

    assert result["valid"] is False, (
        "Expected invalid for low completeness"
    )
    assert any(
        "completeness" in reason.lower()
        for reason in result["reasons"]
    ), f"Reasons should mention completeness: {result['reasons']}"
    print(f"✓ Low completeness correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_6_wrong_story_direction_fails():
    print("\n" + "=" * 70)
    print("TEST 6: Wrong Story Direction Fails")
    print("=" * 70)

    # fastest_growth but negative percent change
    result = StoryQualityValidator.validate(
        sample_metrics(
            story_type="fastest_growth",
            start_value=100.0,
            end_value=50.0,
            absolute_change=-50.0,
            percentage_change=-0.50,
            rank_change=-2.0,
        ),
        title="GDP Per Capita: Fastest Growth",
    )

    assert result["valid"] is False, (
        "Expected invalid for wrong story direction"
    )
    assert any(
        "growth" in reason.lower()
        or "percentage" in reason.lower()
        for reason in result["reasons"]
    ), f"Reasons should mention direction mismatch: {result['reasons']}"
    print(f"✓ Wrong story direction correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_7_near_zero_base_rejected():
    print("\n" + "=" * 70)
    print("TEST 7: Near-Zero Base Percentage Change Rejected")
    print("=" * 70)

    # Starting at ~0 and ending at ~0.0005 with a huge percent change
    result = StoryQualityValidator.validate(
        sample_metrics(
            story_type="fastest_growth",
            start_value=0.0000001,   # 1e-7, near zero
            end_value=0.0000005,     # 5e-7, still near zero
            absolute_change=0.0000004,
            percentage_change=4.0,   # 400% on near-zero base
            rank_change=5.0,
        ),
        title="GDP Per Capita: Fastest Growth",
    )

    assert result["valid"] is False, (
        "Expected invalid for near-zero base"
    )
    assert any(
        "near-zero" in reason.lower()
        or "zero base" in reason.lower()
        for reason in result["reasons"]
    ), f"Reasons should mention near-zero base: {result['reasons']}"
    print(f"✓ Near-zero base change correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_8_consistent_signals_pass():
    print("\n" + "=" * 70)
    print("TEST 8: Consistent Signals Pass")
    print("=" * 70)

    # All signals agree: positive growth, positive rank change,
    # high trend strength, high completeness.
    result = StoryQualityValidator.validate(
        sample_metrics(
            story_type="fastest_growth",
            start_value=100.0,
            end_value=150.0,
            absolute_change=50.0,
            percentage_change=0.50,
            start_rank=5.0,
            end_rank=3.0,
            rank_change=2.0,  # moved up in ranking
            trend_strength=0.85,
            data_completeness=0.95,
        ),
        title="GDP Per Capita: Fastest Growth",
    )

    assert result["valid"] is True, (
        f"Expected valid with consistent signals, got: {result['reasons']}"
    )
    print(f"✓ Consistent signals pass")
    return True


def test_9_contradictory_signals_fail():
    print("\n" + "=" * 70)
    print("TEST 9: Contradictory Signals Fail")
    print("=" * 70)

    # Positive percent change but negative rank change
    # (claims growth but the entity actually fell in ranking)
    result = StoryQualityValidator.validate(
        sample_metrics(
            story_type="fastest_growth",
            start_value=100.0,
            end_value=150.0,
            absolute_change=50.0,
            percentage_change=0.50,
            start_rank=3.0,
            end_rank=5.0,
            rank_change=-2.0,  # fell in ranking
            trend_strength=0.85,
        ),
        title="GDP Per Capita: Fastest Growth",
    )

    assert result["valid"] is False, (
        "Expected invalid for contradictory signals"
    )
    assert any(
        "contradiction" in reason.lower()
        for reason in result["reasons"]
    ), f"Reasons should mention signal contradiction: {result['reasons']}"
    print(f"✓ Contradictory signals correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def test_10_misleading_title_fails():
    print("\n" + "=" * 70)
    print("TEST 10: Misleading Title Fails")
    print("=" * 70)

    # Title says "Declines" but data shows growth
    result = StoryQualityValidator.validate(
        sample_metrics(
            story_type="fastest_growth",
            start_value=100.0,
            end_value=150.0,
            absolute_change=50.0,
            percentage_change=0.50,
            rank_change=2.0,
        ),
        title="GDP Per Capita: Fastest Declines",
    )

    assert result["valid"] is False, (
        "Expected invalid for misleading title"
    )
    assert any(
        "title" in reason.lower()
        for reason in result["reasons"]
    ), f"Reasons should mention title: {result['reasons']}"
    print(f"✓ Misleading title correctly rejected")
    print(f"  Reasons: {result['reasons']}")
    return True


def main():
    print("\n")
    print("*" * 70)
    print("STORY QUALITY VALIDATION TESTS")
    print("*" * 70)

    tests = [
        ("Valid Candidate Passes", test_1_valid_candidate_passes),
        ("Missing Entity Fails", test_2_missing_entity_fails),
        ("Insufficient Entities Fails", test_3_insufficient_entities_fails),
        ("Insufficient Years Fails", test_4_insufficient_years_fails),
        ("Low Completeness Fails", test_5_low_completeness_fails),
        ("Wrong Story Direction Fails", test_6_wrong_story_direction_fails),
        ("Near-Zero Base Rejected", test_7_near_zero_base_rejected),
        ("Consistent Signals Pass", test_8_consistent_signals_pass),
        ("Contradictory Signals Fail", test_9_contradictory_signals_fail),
        ("Misleading Title Fails", test_10_misleading_title_fails),
    ]

    results = []

    for name, test_func in tests:
        try:
            passed = test_func()
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
        print("\n✅ ALL STORY QUALITY VALIDATION TESTS PASSED")
        return True
    else:
        print("\n❌ SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)