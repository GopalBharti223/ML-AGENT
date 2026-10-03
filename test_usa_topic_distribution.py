#!/usr/bin/env python3
"""
Phase 12 - USA Topic Distribution Tests

Verifies the deterministic, quality-preserving preference for
high-interest country stories (USA, Ukraine, Israel, Iran, India, China)
targeting approximately 40% of generated stories.

Tests:
1. USA candidate is correctly identified as high-interest
2. Non-USA candidate is correctly identified as global/non-USA
3. USA preference can select a strong USA comparison when appropriate
4. A weak USA story does NOT beat a substantially better global story
5. Recent USA story blocked by AntiRepeat remains blocked
6. No USA data available → global story can still be selected
7. USA preference is deterministic
8. Approximately 40% high-interest preference is maintained
9. Existing AI Index stories continue working
10. Existing story-quality/content-quality validators continue working
"""

import sys

import pandas as pd

from app.topic.topic_distribution import (
    HIGH_INTEREST_COUNTRIES,
    HOT_TOPIC_EXTRA_BOOST,
    MAX_BOOST,
    TARGET_HIGH_INTEREST_RATIO,
    TOLERANCE,
    TopicDistributionPreference,
)
from app.topic.smart_story import StoryCandidate
from app.topic.story_quality import StoryQualityValidator
from app.topic.content_quality import ContentQualityValidator


# =========================================================
# CANDIDATE BUILDERS
# =========================================================

def make_candidate(
    entity="United States",
    score=70.0,
    story_type="fastest_growth",
    indicator_code="NY.GDP.PCAP.CD",
    indicator_name="GDP Per Capita",
    topic=None,
    leader=None,
    challenger=None,
):
    """Build a StoryCandidate for testing."""
    metrics = {
        "entity": entity,
        "start_year": 2016,
        "end_year": 2025,
        "start_value": 100.0,
        "end_value": 150.0,
        "absolute_change": 50.0,
        "percentage_change": 50.0,
        "start_rank": 5.0,
        "end_rank": 3.0,
        "rank_change": 2.0,
        "number_of_valid_countries": 8,
        "number_of_valid_years": 10,
        "data_completeness": 0.95,
        "leader_separation": 0.40,
        "trend_strength": 0.85,
        "story_type": story_type,
        "indicator_code": indicator_code,
        "indicator_name": indicator_name,
        "topic_family": "economy",
    }

    if leader:
        metrics["leader"] = leader
    if challenger:
        metrics["challenger"] = challenger

    if topic is None:
        topic = f"{indicator_name}: Fastest Growth"

    return StoryCandidate(
        provider_id="worldbank",
        indicator_code=indicator_code,
        indicator_name=indicator_name,
        story_type=story_type,
        chart_type="top5_change",
        topic_family="economy",
        years=10,
        category="World Data",
        source_name="World Bank",
        source_url="https://data.worldbank.org",
        topic=topic,
        score=score,
        metrics=metrics,
    )


def make_history(records=None):
    """Build a list of history records."""
    return records or []


# =========================================================
# TEST 1: USA candidate identified as high-interest
# =========================================================

def test_1_usa_identified():
    print("=" * 70)
    print("TEST 1: USA candidate is correctly identified")
    print("=" * 70)

    candidate = make_candidate(
        entity="United States",
        score=70.0,
    )

    assert TopicDistributionPreference.is_high_interest(
        "United States"
    ) is True, "United States should be high-interest"
    assert TopicDistributionPreference.is_high_interest(
        "USA"
    ) is True, "USA should be high-interest"
    assert TopicDistributionPreference.is_high_interest(
        "us"
    ) is True, "us should be high-interest"
    assert TopicDistributionPreference.candidate_is_high_interest(
        candidate
    ) is True, "USA candidate should be high-interest"

    # Also test other high-interest countries
    for country in ["Israel", "Iran", "India", "China", "Russia"]:
        assert TopicDistributionPreference.is_high_interest(
            country
        ) is True, f"{country} should be high-interest"

    print(f"✓ USA and other high-interest countries correctly identified")
    print(f"  High-interest set: {sorted(HIGH_INTEREST_COUNTRIES)}")
    return True


# =========================================================
# TEST 2: Non-USA candidate identified as global
# =========================================================

def test_2_non_usa_identified():
    print("\n" + "=" * 70)
    print("TEST 2: Non-USA candidate is correctly identified as global")
    print("=" * 70)

    candidate = make_candidate(
        entity="Brazil",
        score=70.0,
    )

    assert TopicDistributionPreference.is_high_interest(
        "Brazil"
    ) is False, "Brazil should NOT be high-interest"
    assert TopicDistributionPreference.is_high_interest(
        "Germany"
    ) is False, "Germany should NOT be high-interest"
    assert TopicDistributionPreference.is_high_interest(
        "France"
    ) is False, "France should NOT be high-interest"
    assert TopicDistributionPreference.is_high_interest(
        "Japan"
    ) is False, "Japan should NOT be high-interest"
    assert TopicDistributionPreference.candidate_is_high_interest(
        candidate
    ) is False, "Brazil candidate should NOT be high-interest"

    print(f"✓ Non-USA candidates correctly identified as global")
    return True


# =========================================================
# TEST 3: USA preference can select a strong USA comparison
# =========================================================

def test_3_usa_preference_selects_strong_usa():
    print("\n" + "=" * 70)
    print("TEST 3: USA preference can select a strong USA comparison")
    print("=" * 70)

    # History with NO high-interest stories -> below target
    history = make_history([
        {"topic": "Brazil GDP Growth", "title": "Brazil GDP Growth"},
        {"topic": "Germany Life Expectancy", "title": "Germany Life Expectancy"},
        {"topic": "France Energy Use", "title": "France Energy Use"},
    ])

    # Verify the ratio is 0.0 (no high-interest in history)
    ratio = TopicDistributionPreference.current_high_interest_ratio(
        history
    )
    assert ratio == 0.0, (
        f"Expected ratio 0.0, got {ratio}"
    )

    # Strong USA candidate (score 80)
    usa_candidate = make_candidate(
        entity="United States",
        score=80.0,
        topic="GDP Per Capita: United States Fastest Growth",
    )

    # Moderate global candidate (score 75)
    global_candidate = make_candidate(
        entity="Brazil",
        score=75.0,
        topic="GDP Per Capita: Brazil Fastest Growth",
    )

    candidates = [global_candidate, usa_candidate]

    # Apply preference
    result = TopicDistributionPreference.apply_preference(
        candidates,
        history
    )

    # USA candidate should be first (boosted by 5%)
    assert result[0].metrics["entity"] == "United States", (
        f"Expected USA candidate first, got {result[0].metrics['entity']}"
    )

    # Verify the multiplier
    # USA is underrepresented (target 15%, current 0%):
    # deficit 0.15 * BOOST_SCALE 0.25 = 0.0375, capped at COUNTRY_MAX_BOOSTS["usa"] 0.06
    multiplier = TopicDistributionPreference.distribution_multiplier(
        "United States",
        history
    )
    expected = 1.0 + min(0.06, 0.15 * 0.25)
    assert multiplier == expected, (
        f"Expected multiplier {expected}, got {multiplier}"
    )

    print(f"✓ Strong USA candidate selected when below target")
    print(f"  USA score: {usa_candidate.score} → {usa_candidate.score * multiplier:.2f}")
    print(f"  Global score: {global_candidate.score}")
    return True


# =========================================================
# TEST 4: Weak USA does NOT beat strong global
# =========================================================

def test_4_weak_usa_does_not_beat_strong_global():
    print("\n" + "=" * 70)
    print("TEST 4: Weak USA story does NOT beat a substantially better global story")
    print("=" * 70)

    # History with NO high-interest stories -> below target
    history = make_history([
        {"topic": "Brazil GDP Growth", "title": "Brazil GDP Growth"},
        {"topic": "Germany Life Expectancy", "title": "Germany Life Expectancy"},
    ])

    # Weak USA candidate (score 60)
    weak_usa = make_candidate(
        entity="United States",
        score=60.0,
        topic="GDP Per Capita: United States Fastest Growth",
    )

    # Strong global candidate (score 75)
    strong_global = make_candidate(
        entity="Brazil",
        score=75.0,
        topic="GDP Per Capita: Brazil Fastest Growth",
    )

    candidates = [weak_usa, strong_global]

    # Apply preference
    result = TopicDistributionPreference.apply_preference(
        candidates,
        history
    )

    # Strong global should still win (75 > 60 * 1.05 = 63)
    assert result[0].metrics["entity"] == "Brazil", (
        f"Expected strong global candidate first, got {result[0].metrics['entity']}"
    )

    # Verify the math: 60 * 1.0375 = 62.25 < 75
    boosted_usa = 60.0 * (1.0 + min(0.06, 0.15 * 0.25))
    assert boosted_usa < 75.0, (
        f"Boosted USA score {boosted_usa} should be less than global score 75"
    )

    print(f"✓ Weak USA story correctly loses to strong global story")
    print(f"  Weak USA: 60 * 1.0375 = {boosted_usa:.2f}")
    print(f"  Strong global: 75")
    return True


# =========================================================
# TEST 5: AntiRepeat still blocks recent USA stories
# =========================================================

def test_5_antirepeat_blocks_recent_usa():
    print("\n" + "=" * 70)
    print("TEST 5: Recent USA story blocked by AntiRepeat remains blocked")
    print("=" * 70)

    from app.topic.anti_repeat import AntiRepeatValidator

    class FakeDb:
        def __init__(self):
            self._topics = {"GDP Per Capita: United States Fastest Growth"}
            self._story_hits = {("NY.GDP.PCAP.CD", "fastest_growth")}
            self._year_hits = {("NY.GDP.PCAP.CD", 2016, 2025)}
            self._combo_hits = {("NY.GDP.PCAP.CD", "fastest_growth", 2016, 2025)}

        def is_topic_used(self, topic):
            return topic in self._topics

        def is_story_type_used_recently(self, indicator_code, story_type, days=30):
            return (indicator_code, story_type) in self._story_hits

        def is_year_range_used_recently(self, indicator_code, start_year, end_year, days=60):
            return (indicator_code, start_year, end_year) in self._year_hits

        def is_content_combination_used(self, indicator_code, story_type, start_year, end_year, days=90):
            return (indicator_code, story_type, start_year, end_year) in self._combo_hits

        def get_recent_records(self, limit=100):
            return []

        def get_recent_content(self, limit=100):
            return []

    fake_db = FakeDb()

    # USA candidate that was recently used
    result = AntiRepeatValidator.check(
        topic="GDP Per Capita: United States Fastest Growth",
        indicator_code="NY.GDP.PCAP.CD",
        story_type="fastest_growth",
        start_year=2016,
        end_year=2025,
        database=fake_db,
    )

    assert result["allowed"] is False, (
        "Recent USA story should be blocked by AntiRepeat"
    )
    assert "exact_topic" in result["hard_blocks"], (
        f"Expected exact_topic in hard_blocks: {result['hard_blocks']}"
    )

    print(f"✓ Recent USA story correctly blocked by AntiRepeat")
    print(f"  Hard blocks: {result['hard_blocks']}")
    return True


# =========================================================
# TEST 6: No USA data → global story still selected
# =========================================================

def test_6_no_usa_data_global_selected():
    print("\n" + "=" * 70)
    print("TEST 6: No USA data available → global story can still be selected")
    print("=" * 70)

    # History with NO high-interest stories
    history = make_history([
        {"topic": "Brazil GDP Growth", "title": "Brazil GDP Growth"},
        {"topic": "Germany Life Expectancy", "title": "Germany Life Expectancy"},
    ])

    # Only global candidates available
    global_candidate = make_candidate(
        entity="Brazil",
        score=70.0,
        topic="GDP Per Capita: Brazil Fastest Growth",
    )

    candidates = [global_candidate]

    result = TopicDistributionPreference.apply_preference(
        candidates,
        history
    )

    assert len(result) == 1, "Should still return the global candidate"
    assert result[0].metrics["entity"] == "Brazil", (
        "Global candidate should still be selected"
    )

    print(f"✓ Global story selected when no USA data available")
    return True


# =========================================================
# TEST 7: USA preference is deterministic
# =========================================================

def test_7_deterministic():
    print("\n" + "=" * 70)
    print("TEST 7: USA preference is deterministic")
    print("=" * 70)

    history = make_history([
        {"topic": "Brazil GDP Growth", "title": "Brazil GDP Growth"},
        {"topic": "Germany Life Expectancy", "title": "Germany Life Expectancy"},
    ])

    usa_candidate = make_candidate(
        entity="United States",
        score=80.0,
    )
    global_candidate = make_candidate(
        entity="Brazil",
        score=75.0,
    )

    candidates = [global_candidate, usa_candidate]

    result1 = TopicDistributionPreference.apply_preference(
        candidates,
        history
    )
    result2 = TopicDistributionPreference.apply_preference(
        candidates,
        history
    )

    assert result1[0].metrics["entity"] == result2[0].metrics["entity"], (
        "Selection should be deterministic"
    )
    assert result1[0].score == result2[0].score, (
        "Scores should be deterministic"
    )

    print(f"✓ USA preference is deterministic")
    print(f"  Result 1: {result1[0].metrics['entity']}")
    print(f"  Result 2: {result2[0].metrics['entity']}")
    return True


# =========================================================
# TEST 8: ~40% high-interest preference maintained
# =========================================================

def test_8_ratio_maintained():
    print("\n" + "=" * 70)
    print("TEST 8: Approximately 40% high-interest preference maintained")
    print("=" * 70)

    # Simulate 10 selection cycles with a mix of candidates
    # History starts empty (ratio 0.0 -> below target)
    history = []

    high_interest_selected = 0
    total_selected = 0

    for cycle in range(10):
        # Build a candidate pool with both high-interest and global candidates
        candidates = []

        # High-interest candidates - scores vary by cycle
        for entity in ["United States", "China", "India"]:
            candidates.append(
                make_candidate(
                    entity=entity,
                    score=60.0 + (cycle % 3) * 5.0,
                    topic=f"{entity} GDP Growth",
                )
            )

        # Global candidates - scores vary independently
        for entity in ["Brazil", "Germany", "France", "Japan"]:
            candidates.append(
                make_candidate(
                    entity=entity,
                    score=55.0 + ((cycle + 1) % 4) * 5.0,
                    topic=f"{entity} GDP Growth",
                )
            )

        # Apply preference
        result = TopicDistributionPreference.apply_preference(
            candidates,
            history
        )

        # Select the best
        selected = result[0]
        total_selected += 1

        if TopicDistributionPreference.candidate_is_high_interest(
            selected
        ):
            high_interest_selected += 1

        # Add to history
        history.append(
            {
                "topic": selected.topic,
                "title": selected.topic,
            }
        )

    ratio = high_interest_selected / total_selected

    print(f"  High-interest selected: {high_interest_selected}/{total_selected}")
    print(f"  Ratio: {ratio:.2f}")

    # The ratio should be meaningfully above 0 (preference works)
    assert high_interest_selected > 0, (
        "High-interest preference should select at least one high-interest story"
    )

    # The ratio should be in a reasonable range (not 0%, not 100%)
    assert 0.20 <= ratio <= 0.80, (
        f"Ratio {ratio:.2f} should be in a reasonable range"
    )

    print(f"✓ High-interest preference maintained over repeated cycles")
    return True


# =========================================================
# TEST 9: AI Index stories continue working
# =========================================================

def test_9_ai_index_stories_work():
    print("\n" + "=" * 70)
    print("TEST 9: Existing AI Index stories continue working")
    print("=" * 70)

    # AI Index candidates should work with the preference system
    ai_candidate = make_candidate(
        entity="United States",
        score=85.0,
        indicator_code="ai_investment",
        indicator_name="AI Investment",
        topic="AI Investment: United States Fastest Growth",
    )

    # Verify the preference system handles AI Index entities
    assert TopicDistributionPreference.is_high_interest(
        "United States"
    ) is True, "USA should be high-interest in AI Index stories"

    # Verify story quality validator still works
    quality_result = StoryQualityValidator.validate(
        ai_candidate.metrics,
        story_type=ai_candidate.story_type,
        title=ai_candidate.topic,
        indicator_name=ai_candidate.indicator_name,
    )
    assert quality_result["valid"] is True, (
        f"AI Index candidate should pass story quality: {quality_result['reasons']}"
    )

    # Verify content quality validator still works
    content_result = ContentQualityValidator.validate(
        ai_candidate.to_topic_data()
    )
    assert content_result["valid"] is True, (
        f"AI Index candidate should pass content quality: {content_result['reasons']}"
    )

    print(f"✓ AI Index stories continue working with preference system")
    return True


# =========================================================
# TEST 10: Existing validators continue working
# =========================================================

def test_10_validators_continue_working():
    print("\n" + "=" * 70)
    print("TEST 10: Existing story-quality/content-quality validators continue working")
    print("=" * 70)

    # Valid candidate
    valid_candidate = make_candidate(
        entity="United States",
        score=80.0,
    )

    quality_result = StoryQualityValidator.validate(
        valid_candidate.metrics,
        story_type=valid_candidate.story_type,
        title=valid_candidate.topic,
        indicator_name=valid_candidate.indicator_name,
    )
    assert quality_result["valid"] is True, (
        f"Valid candidate should pass story quality: {quality_result['reasons']}"
    )

    content_result = ContentQualityValidator.validate(
        valid_candidate.to_topic_data()
    )
    assert content_result["valid"] is True, (
        f"Valid candidate should pass content quality: {content_result['reasons']}"
    )

    # Invalid candidate (wrong story direction)
    invalid_metrics = dict(valid_candidate.metrics)
    invalid_metrics["percentage_change"] = -50.0
    invalid_metrics["absolute_change"] = -50.0
    invalid_metrics["start_value"] = 150.0
    invalid_metrics["end_value"] = 100.0

    invalid_result = StoryQualityValidator.validate(
        invalid_metrics,
        story_type="fastest_growth",
        title="GDP Per Capita: Fastest Growth",
        indicator_name="GDP Per Capita",
    )
    assert invalid_result["valid"] is False, (
        "Invalid candidate should fail story quality"
    )

    print(f"✓ Existing validators continue working correctly")
    print(f"  Valid candidate: PASS")
    print(f"  Invalid candidate: REJECTED")
    return True


# =========================================================
# MAIN
# =========================================================

def main():
    print("\n")
    print("*" * 70)
    print("PHASE 12 - USA TOPIC DISTRIBUTION TESTS")
    print("*" * 70)

    tests = [
        ("USA identified", test_1_usa_identified),
        ("Non-USA identified", test_2_non_usa_identified),
        ("USA preference selects strong USA", test_3_usa_preference_selects_strong_usa),
        ("Weak USA loses to strong global", test_4_weak_usa_does_not_beat_strong_global),
        ("AntiRepeat blocks recent USA", test_5_antirepeat_blocks_recent_usa),
        ("No USA data → global selected", test_6_no_usa_data_global_selected),
        ("Deterministic", test_7_deterministic),
        ("~40% ratio maintained", test_8_ratio_maintained),
        ("AI Index stories work", test_9_ai_index_stories_work),
        ("Validators continue working", test_10_validators_continue_working),
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
        print("\n✅ ALL USA TOPIC DISTRIBUTION TESTS PASSED")
        return True
    else:
        print("\n❌ SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)