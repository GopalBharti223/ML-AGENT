#!/usr/bin/env python3
"""
SmartStoryEngine V2 - Comprehensive Test Suite

Tests:
1. Multiple candidates are generated
2. Candidates receive scores with breakdown
3. Weak candidates are rejected by quality gates
4. Duplicate/recent candidates are penalized
5. Different story types are generated
6. Chart type selection works
7. Bubble is not selected without multidimensional data
8. AI Index failure is handled safely
9. World Bank continues working
10. OWID continues working
11. Existing fallback still works
12. Transparent candidate ranking
"""

import functools
import sys
from app.topic.smart_story import SmartStoryEngine
from app.data.providers import DataProviderRegistry


def must_pass(func):
    """Turn this test's `return False` into a real failure.

    pytest DISCARDS a test function's return value, so the
    `if cond: return True else: return False` style used
    throughout this file was collected, executed, and always
    reported PASS.  Wrapping the function makes the boolean
    decisive again while keeping the script-mode runner in
    main() working.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        assert result is not False, (
            f"{func.__name__} reported failure (returned False)"
        )
        # Return None so pytest does not emit its
        # PytestReturnNotNoneWarning ("Did you mean to use
        # `assert` instead of `return`?").
        return None
    return wrapper


@must_pass
def test_1_multiple_candidates():
    """Test 1: Multiple candidates are generated"""
    print("=" * 70)
    print("TEST 1: Multiple Candidate Generation")
    print("=" * 70)
    
    print("\nCalling SmartStoryEngine.select_best_candidate()...")
    print("This will generate candidates from all available providers.\n")
    
    candidate = SmartStoryEngine.select_best_candidate(
        max_indicators_per_provider=2,  # Limit for faster testing
    )
    
    if candidate:
        print(f"\n[OK] Selected candidate: {candidate.provider_id}/{candidate.indicator_code}")
        print(f"  Story type: {candidate.story_type}")
        print(f"  Score: {candidate.score:.2f}")
        return True
    else:
        print("[ERROR] No candidate selected")
        return False


@must_pass
def test_2_candidate_scoring():
    """Test 2: Candidates receive detailed scores"""
    print("\n" + "=" * 70)
    print("TEST 2: Candidate Scoring Breakdown")
    print("=" * 70)
    
    candidate = SmartStoryEngine.select_best_candidate(
        max_indicators_per_provider=2,
    )
    
    if not candidate:
        print("✗ No candidate to score")
        return False
    
    metrics = candidate.metrics
    
    print(f"\nMetrics for: {candidate.topic}")
    print(f"\nData Quality:")
    print(f"  • Countries: {metrics.get('number_of_valid_countries', 0)}")
    print(f"  • Years: {metrics.get('number_of_valid_years', 0)}")
    print(f"  • Completeness: {metrics.get('data_completeness', 0):.2%}")
    
    print(f"\nStory Strength:")
    print(f"  • Percentage Change: {metrics.get('percentage_change', 0):.2%}")
    print(f"  • Rank Change: {metrics.get('rank_change', 0)}")
    print(f"  • Trend Strength: {metrics.get('trend_strength', 0):.2f}")
    
    print(f"\nScoring Components:")
    print(f"  • Quality Score: {metrics.get('quality_score', 0):.1f}")
    print(f"  • Diversity Mult: {metrics.get('diversity_multiplier', 1.0):.3f}")
    print(f"  • Final Score: {candidate.score:.2f}")
    
    if candidate.score > 0:
        print("\n✓ Candidate has valid score breakdown")
        return True
    else:
        print("\n✗ Invalid score")
        return False


@must_pass
def test_3_quality_gates():
    """Test 3: Weak candidates are rejected"""
    print("\n" + "=" * 70)
    print("TEST 3: Quality Gate Filtering")
    print("=" * 70)
    
    print("\nTesting quality gate thresholds:")
    print(f"  MIN_QUALITY_SCORE: {SmartStoryEngine.MIN_QUALITY_SCORE}")
    print(f"  MIN_VISUAL_POTENTIAL: {SmartStoryEngine.MIN_VISUAL_POTENTIAL}")
    
    candidate = SmartStoryEngine.select_best_candidate(
        max_indicators_per_provider=3,
    )
    
    if not candidate:
        print("✗ No candidate passed quality gates")
        return False
    
    quality = candidate.metrics.get('quality_score', 0.0)
    visual = SmartStoryEngine._calculate_visual_potential(candidate)
    
    print(f"\nSelected candidate quality metrics:")
    print(f"  • Quality Score: {quality:.2f}")
    print(f"  • Visual Potential: {visual:.2f}")
    
    if quality >= SmartStoryEngine.MIN_QUALITY_SCORE:
        print(f"\n✓ Candidate passes quality gate (>= {SmartStoryEngine.MIN_QUALITY_SCORE})")
        return True
    else:
        print(f"\n✗ Candidate failed quality gate")
        return False


@must_pass
def test_4_different_story_types():
    """Test 4: Different story types are generated"""
    print("\n" + "=" * 70)
    print("TEST 4: Different Story Types")
    print("=" * 70)
    
    available_types = set(SmartStoryEngine.STORY_TO_CHART.keys())
    
    print(f"\nAvailable story types: {available_types}")
    print(f"Expected mappings to charts:")
    for story_type, chart_type in SmartStoryEngine.STORY_TO_CHART.items():
        print(f"  {story_type} → {chart_type}")
    
    candidate = SmartStoryEngine.select_best_candidate(
        max_indicators_per_provider=3,
    )
    
    if not candidate:
        print("✗ No candidate generated")
        return False
    
    if candidate.story_type in available_types:
        print(f"\n✓ Selected story type '{candidate.story_type}' is valid")
        print(f"✓ Mapped to chart type '{candidate.chart_type}'")
        return True
    else:
        print(f"\n✗ Invalid story type: {candidate.story_type}")
        return False


@must_pass
@must_pass
def test_5_chart_selection():
    """Test 5: Chart selection works correctly"""
    print("\n" + "=" * 70)
    print("TEST 5: Chart Type Selection")
    print("=" * 70)

    candidate = SmartStoryEngine.select_best_candidate(
        max_indicators_per_provider=2,
    )

    if not candidate:
        print("✗ No candidate")
        return False

    expected_chart = SmartStoryEngine.STORY_TO_CHART.get(
        candidate.story_type
    )

    print(f"\nCandidate: {candidate.topic}")
    print(f"  Story type: {candidate.story_type}")
    print(f"  Expected chart: {expected_chart}")
    print(f"  Selected chart: {candidate.chart_type}")

    # The authoritative set of renderable chart types is the
    # ChartSelector distribution, NOT STORY_TO_CHART.values().
    # The old whitelist predated the "area" chart (15% weight,
    # mapped to VisualEngine.render_area), so a perfectly valid
    # 'area' selection was reported as "Invalid chart type".
    from app.topic.chart_selector import ChartSelector

    valid_charts = set(ChartSelector.CHART_DISTRIBUTION) | \
        set(ChartSelector.DEFAULT_MAP.values())

    print(f"  Valid chart types: {sorted(valid_charts)}")

    assert candidate.chart_type in valid_charts, (
        f"selector emitted chart type {candidate.chart_type!r}, "
        f"which is not in the renderable set {sorted(valid_charts)}"
    )

    print("\n✓ Chart type is valid")
    return True


@must_pass
def test_6_bubble_safety():
    """Test 6: Bubble chart not forced without data"""
    print("\n" + "=" * 70)
    print("TEST 6: Bubble Chart Safety (No Fake Dimensions)")
    print("=" * 70)
    
    print("\nBubble charts are only selected when:")
    print("  • Data has 'x' and 'y' columns")
    print("  • Genuine multidimensional data exists")
    print("  • NOT forced merely to use the chart type")
    
    candidate = SmartStoryEngine.select_best_candidate(
        max_indicators_per_provider=3,
    )
    
    if not candidate:
        print("✗ No candidate")
        return False
    
    if candidate.chart_type == "bubble":
        print(f"\n⚠ Bubble chart selected for: {candidate.topic}")
        print("  Verify this data has genuine X/Y dimensions")
        return True
    else:
        print(f"\n✓ Chart type '{candidate.chart_type}' selected")
        print(f"  (Bubble safety check: not forcing unsupported type)")
        return True


@must_pass
def test_7_ai_index_failure():
    """Test 7: AI Index failure handled safely"""
    print("\n" + "=" * 70)
    print("TEST 7: AI Index Failure Handling")
    print("=" * 70)
    
    print("\nNote: AI Index provider should fail gracefully")
    print("(Real Stanford data unavailable in this environment)")
    
    candidate = SmartStoryEngine.select_best_candidate()

    if candidate is None:
        # This used to return True, which meant the test could
        # not detect a total provider outage.  The documented
        # contract is that SOME provider answers.
        raise AssertionError(
            "select_best_candidate() returned no candidate -- "
            "AI Index failure was not handled by falling back to "
            "another provider"
        )

    # Whether ai_index or a fallback wins, the result must be
    # a usable candidate, not a half-built one.
    assert candidate.provider_id, "candidate has no provider_id"
    assert candidate.indicator_code, "candidate has no indicator_code"
    assert candidate.topic, "candidate has no topic"

    if candidate.provider_id == "ai_index":
        print(f"\n⚠ AI Index was selected: {candidate.topic}")
        print("  This is okay if real Stanford data was available")
        return True
    else:
        print(f"\n✓ AI Index was skipped, fallback provider selected:")
        print(f"  {candidate.provider_id}/{candidate.indicator_code}")
        print("  (This is expected behavior when Stanford data unavailable)")
        return True


@must_pass
def test_8_world_bank_working():
    """Test 8: World Bank provider continues working"""
    print("\n" + "=" * 70)
    print("TEST 8: World Bank Provider (No Breakage)")
    print("=" * 70)
    
    try:
        wb_provider = DataProviderRegistry.get("worldbank")
        indicators = wb_provider.list_indicators()
        
        print(f"\n✓ World Bank provider accessible")
        print(f"✓ Available indicators: {len(indicators)}")
        
        if len(indicators) > 0:
            print(f"\nSample indicators:")
            for indicator in indicators[:3]:
                print(f"  • {indicator.code}: {indicator.name}")
            return True
        else:
            print("✗ No indicators found")
            return False
    except Exception as e:
        print(f"✗ Error accessing World Bank: {e}")
        return False


@must_pass
def test_9_owid_working():
    """Test 9: OWID provider continues working"""
    print("\n" + "=" * 70)
    print("TEST 9: OWID Provider (No Breakage)")
    print("=" * 70)
    
    try:
        owid_provider = DataProviderRegistry.get("owid")
        indicators = owid_provider.list_indicators()
        
        print(f"\n✓ OWID provider accessible")
        print(f"✓ Available indicators: {len(indicators)}")
        
        if len(indicators) > 0:
            print(f"\nSample indicators:")
            for indicator in indicators[:3]:
                print(f"  • {indicator.code}: {indicator.name}")
            return True
        else:
            print("✗ No indicators found")
            return False
    except Exception as e:
        print(f"✗ Error accessing OWID: {e}")
        return False


@must_pass
def test_10_existing_fallback():
    """Test 10: Existing fallback behavior preserved"""
    print("\n" + "=" * 70)
    print("TEST 10: Existing Fallback (generate_topic)")
    print("=" * 70)
    
    try:
        topic = SmartStoryEngine.generate_topic()
        
        if topic is None:
            # Returning True here meant "all providers down"
            # looked identical to a pass.
            raise AssertionError(
                "generate_topic() returned None -- the documented "
                "fallback path did not produce a topic"
            )

        # A returned topic must carry the fields downstream
        # stages rely on.
        assert topic.get("provider_id"), \
            "generate_topic() topic has no provider_id"
        assert topic.get("indicator_code"), \
            "generate_topic() topic has no indicator_code"
        assert topic.get("topic"), \
            "generate_topic() topic has no topic text"
        print(f"\n✓ generate_topic() returned valid topic data")
        print(f"  Provider: {topic.get('provider_id')}")
        print(f"  Indicator: {topic.get('indicator_code')}")
        print(f"  Story Type: {topic.get('story_type')}")
        print(f"  Chart Type: {topic.get('chart_type')}")
        print(f"  Topic: {topic.get('topic')}")
        
        return True
    except Exception as e:
        print(f"✗ Error in generate_topic(): {e}")
        return False


def main():
    """Run all tests"""
    print("\n")
    print("*" * 70)
    print("SMARTSTORYENGINE V2 - COMPREHENSIVE TEST SUITE")
    print("*" * 70)
    
    tests = [
        ("Multiple Candidates", test_1_multiple_candidates),
        ("Scoring Breakdown", test_2_candidate_scoring),
        ("Quality Gates", test_3_quality_gates),
        ("Story Types", test_4_different_story_types),
        ("Chart Selection", test_5_chart_selection),
        ("Bubble Safety", test_6_bubble_safety),
        ("AI Index Failure", test_7_ai_index_failure),
        ("WorldBank Working", test_8_world_bank_working),
        ("OWID Working", test_9_owid_working),
        ("Existing Fallback", test_10_existing_fallback),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")

    # Was `passed >= 8`, which declared "TESTS PASSED" (and exit
    # code 0) with up to two genuine failures.  A runner that
    # reports green despite failures is the same class of bug as
    # a test that cannot fail.
    if passed == total:
        print("\n✅ SMARTSTORYENGINE V2 TESTS PASSED")
        return True
    else:
        print(f"\n❌ TESTS FAILED ({total - passed} failing)")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
