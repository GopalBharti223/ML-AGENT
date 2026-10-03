#!/usr/bin/env python3
"""
Tests for AntiRepeatValidator

Verifies that story candidates are not repeatedly selected.

Tests:
1. Exact topic reuse is blocked.
2. Same indicator + story type within 30 days is blocked.
3. Same indicator + year range within 60 days is blocked.
4. Same full combination within 90 days is blocked.
5. Different indicator + same story type is allowed.
6. Same indicator + different story type is allowed.
7. Family repetition is not hard-blocked.
"""

import sys

from app.topic.anti_repeat import AntiRepeatValidator


class FakeDatabase:
    """
    A minimal in-memory fake that mimics only the database methods
    AntiRepeatValidator depends on.
    """

    def __init__(self, records=None):
        # records: list of dicts like get_recent_records() returns
        self._records = records or []
        self._used_topics = set()
        self._story_type_hits = set()
        self._year_range_hits = set()
        self._combination_hits = set()

        # Seed from records
        for record in self._records:
            topic = record.get("topic") or record.get("title")
            if topic:
                self._used_topics.add(str(topic).strip().lower())
            if record.get("indicator_code") and record.get("story_type"):
                self._story_type_hits.add(
                    (
                        str(record["indicator_code"]),
                        str(record["story_type"]),
                    )
                )
            if record.get("indicator_code") and record.get("start_year") and record.get("end_year"):
                self._year_range_hits.add(
                    (
                        str(record["indicator_code"]),
                        record["start_year"],
                        record["end_year"],
                    )
                )
            if (
                record.get("indicator_code")
                and record.get("story_type")
                and record.get("start_year")
                and record.get("end_year")
            ):
                self._combination_hits.add(
                    (
                        str(record["indicator_code"]),
                        str(record["story_type"]),
                        record["start_year"],
                        record["end_year"],
                    )
                )

    # -------------------------------------------------------
    # Database-like interface
    # -------------------------------------------------------

    def is_topic_used(self, topic):
        return str(topic).strip().lower() in self._used_topics

    def is_story_type_used_recently(self, indicator_code, story_type, days=30):
        return (
            (str(indicator_code), str(story_type))
            in self._story_type_hits
        )

    def is_year_range_used_recently(self, indicator_code, start_year, end_year, days=60):
        return (
            (str(indicator_code), start_year, end_year)
            in self._year_range_hits
        )

    def is_content_combination_used(self, indicator_code, story_type, start_year, end_year, days=90):
        return (
            (str(indicator_code), str(story_type), start_year, end_year)
            in self._combination_hits
        )

    def get_recent_records(self, limit=100):
        return self._records[:limit]

    def get_recent_content(self, limit=100):
        return self._records[:limit]


def test_1_exact_topic_reuse_blocked():
    print("=" * 70)
    print("TEST 1: Exact Topic Reuse Blocked")
    print("=" * 70)

    fake_db = FakeDatabase(
        records=[
            {
                "topic": "GDP Growth Leaders",
                "title": "GDP Growth Leaders",
                "indicator_code": "NY.GDP.PCAP.CD",
                "story_type": "fastest_growth",
                "start_year": 2016,
                "end_year": 2025,
            }
        ]
    )

    result = AntiRepeatValidator.check(
        topic="GDP Growth Leaders",
        database=fake_db,
    )

    assert result["allowed"] is False, (
        "Expected topic reuse to be blocked"
    )
    assert "exact_topic" in result["hard_blocks"], (
        f"Expected exact_topic in hard_blocks: {result['hard_blocks']}"
    )
    print(f"✓ Exact topic reuse correctly blocked")
    print(f"  Hard blocks: {result['hard_blocks']}")
    return True


def test_2_same_indicator_story_type_blocked():
    print("\n" + "=" * 70)
    print("TEST 2: Same Indicator + Story Type Blocked (30 days)")
    print("=" * 70)

    fake_db = FakeDatabase(
        records=[
            {
                "topic": "Internet Users Rise",
                "title": "Internet Users Rise",
                "indicator_code": "IT.NET.USER.ZS",
                "story_type": "fastest_growth",
                "start_year": 2016,
                "end_year": 2025,
            }
        ]
    )

    result = AntiRepeatValidator.check(
        topic="Different Topic Name",
        indicator_code="IT.NET.USER.ZS",
        story_type="fastest_growth",
        start_year=2015,
        end_year=2024,
        database=fake_db,
    )

    assert result["allowed"] is False, (
        "Expected indicator+story type reuse to be blocked"
    )
    assert "story_type_reuse" in result["hard_blocks"], (
        f"Expected story_type_reuse in hard_blocks: {result['hard_blocks']}"
    )
    print(f"✓ Same indicator + story type correctly blocked")
    print(f"  Hard blocks: {result['hard_blocks']}")
    return True


def test_3_same_year_range_blocked():
    print("\n" + "=" * 70)
    print("TEST 3: Same Indicator + Year Range Blocked (60 days)")
    print("=" * 70)

    fake_db = FakeDatabase(
        records=[
            {
                "topic": "GDP Growth",
                "title": "GDP Growth",
                "indicator_code": "NY.GDP.MKTP.CD",
                "story_type": "fastest_growth",
                "start_year": 2016,
                "end_year": 2025,
            }
        ]
    )

    # Same indicator + same year range but DIFFERENT story type
    result = AntiRepeatValidator.check(
        topic="A Completely New Title",
        indicator_code="NY.GDP.MKTP.CD",
        story_type="biggest_decline",
        start_year=2016,
        end_year=2025,
        database=fake_db,
    )

    assert result["allowed"] is False, (
        "Expected year-range reuse to be blocked"
    )
    assert "year_range_reuse" in result["hard_blocks"], (
        f"Expected year_range_reuse in hard_blocks: {result['hard_blocks']}"
    )
    print(f"✓ Same indicator + year range correctly blocked")
    print(f"  Hard blocks: {result['hard_blocks']}")
    return True


def test_4_same_full_combination_blocked():
    print("\n" + "=" * 70)
    print("TEST 4: Same Full Combination Blocked (90 days)")
    print("=" * 70)

    fake_db = FakeDatabase(
        records=[
            {
                "topic": "AI Policy: Ranking Drops",
                "title": "AI Policy: Ranking Drops",
                "indicator_code": "ai_policy",
                "story_type": "rank_decline",
                "start_year": 2019,
                "end_year": 2025,
            }
        ]
    )

    result = AntiRepeatValidator.check(
        topic="AI Policy: Yearly Changes",
        indicator_code="ai_policy",
        story_type="rank_decline",
        start_year=2019,
        end_year=2025,
        database=fake_db,
    )

    assert result["allowed"] is False, (
        "Expected full combination reuse to be blocked"
    )
    assert "combination_reuse" in result["hard_blocks"], (
        f"Expected combination_reuse in hard_blocks: {result['hard_blocks']}"
    )
    print(f"✓ Same full combination correctly blocked")
    print(f"  Hard blocks: {result['hard_blocks']}")
    return True


def test_5_different_indicator_same_story_allowed():
    print("\n" + "=" * 70)
    print("TEST 5: Different Indicator + Same Story Type Allowed")
    print("=" * 70)

    fake_db = FakeDatabase(
        records=[
            {
                "topic": "GDP Growth",
                "title": "GDP Growth",
                "indicator_code": "NY.GDP.MKTP.CD",
                "story_type": "fastest_growth",
                "start_year": 2016,
                "end_year": 2025,
            }
        ]
    )

    result = AntiRepeatValidator.check(
        topic="Internet Users Rise",
        indicator_code="IT.NET.USER.ZS",
        story_type="fastest_growth",
        start_year=2016,
        end_year=2025,
        database=fake_db,
    )

    assert result["allowed"] is True, (
        f"Expected different indicator + same story type to be allowed, "
        f"got: {result['reasons']}"
    )
    print(f"✓ Different indicator + same story type allowed")
    print(f"  Hard blocks: {result['hard_blocks']}")
    return True


def test_6_same_indicator_different_story_allowed():
    print("\n" + "=" * 70)
    print("TEST 6: Same Indicator + Different Story Type Allowed")
    print("=" * 70)

    fake_db = FakeDatabase(
        records=[
            {
                "topic": "Internet Users Rise",
                "title": "Internet Users Rise",
                "indicator_code": "IT.NET.USER.ZS",
                "story_type": "fastest_growth",
                "start_year": 2016,
                "end_year": 2025,
            }
        ]
    )

    # Use a DIFFERENT year range so only the story type differs.
    result = AntiRepeatValidator.check(
        topic="Internet Users Most Declined",
        indicator_code="IT.NET.USER.ZS",
        story_type="biggest_decline",
        start_year=2018,
        end_year=2024,
        database=fake_db,
    )

    assert result["allowed"] is True, (
        f"Expected same indicator + different story type to be allowed, "
        f"got: {result['reasons']}"
    )
    print(f"✓ Same indicator + different story type allowed")
    print(f"  Hard blocks: {result['hard_blocks']}")
    return True


def test_7_family_repetition_not_hard_blocked():
    print("\n" + "=" * 70)
    print("TEST 7: Family Repetition Not Hard-Blocked")
    print("=" * 70)

    fake_db = FakeDatabase(
        records=[
            {
                "topic": "GDP Growth Leaders",
                "title": "GDP Growth Leaders",
                "indicator_code": "NY.GDP.MKTP.CD",
                "story_type": "fastest_growth",
                "start_year": 2016,
                "end_year": 2025,
            }
        ]
    )

    # Same family ("economy") but different indicator, story, years
    result = AntiRepeatValidator.check(
        topic="GDP Per Capita Rising",
        indicator_code="NY.GDP.PCAP.CD",
        story_type="rank_climber",
        start_year=2015,
        end_year=2024,
        topic_family="economy",
        database=fake_db,
    )

    # Should NOT be hard-blocked by family repetition
    assert result["allowed"] is True, (
        f"Expected family repetition NOT to be a hard block, "
        f"got: {result['reasons']}"
    )
    # Both NY.GDP.MKTP.CD and NY.GDP.PCAP.CD classify as "economy",
    # so family repetition is correctly detected...
    assert result["family_repeat"] is True, (
        "Expected family repeat to be detected for economy-family "
        "records"
    )
    # ...but it is NOT a hard block.
    assert "family_repetition" not in result["hard_blocks"], (
        "Family repetition should NOT appear in hard_blocks"
    )
    print(f"✓ Family repetition detected but NOT hard-blocked")
    print(f"  family_repeat: {result['family_repeat']}")
    print(f"  family_penalty: {result['family_penalty']}")
    print(f"  allowed: {result['allowed']}")

    # Now check that family penalty is returned (not blocked)
    fake_db2 = FakeDatabase(
        records=[
            {
                "topic": "GDP Growth Leaders",
                "title": "GDP Growth Leaders",
                "indicator_code": "NY.GDP.MKTP.CD",
                "story_type": "fastest_growth",
                "start_year": 2016,
                "end_year": 2025,
            },
            {
                "topic": "GDP Per Capita Changes",
                "title": "GDP Per Capita Changes",
                "indicator_code": "NY.GDP.PCAP.CD",
                "story_type": "fastest_growth",
                "start_year": 2015,
                "end_year": 2024,
            },
        ]
    )

    result2 = AntiRepeatValidator.check(
        topic="New GDP Related Topic",
        indicator_code="NGDPDPC",  # IMF GDP per capita
        story_type="fastest_growth",
        start_year=2014,
        end_year=2023,
        topic_family="economy",
        database=fake_db2,
    )

    # Even with family repetition, it should be allowed (not hard-blocked)
    assert result2["allowed"] is True, (
        f"Family repetition should NOT hard-block: {result2['reasons']}"
    )
    print(f"✓ Family repetition is NOT a hard block (penalty only)")
    print(f"  family_penalty: {result2['family_penalty']}")
    print(f"  family_repeat: {result2['family_repeat']}")
    return True


def main():
    print("\n")
    print("*" * 70)
    print("ANTI-REPEAT VALIDATION TESTS")
    print("*" * 70)

    tests = [
        ("Exact Topic Reuse Blocked", test_1_exact_topic_reuse_blocked),
        ("Indicator+Story Type Blocked", test_2_same_indicator_story_type_blocked),
        ("Indicator+Year Range Blocked", test_3_same_year_range_blocked),
        ("Full Combination Blocked", test_4_same_full_combination_blocked),
        ("Different Indicator Allowed", test_5_different_indicator_same_story_allowed),
        ("Different Story Type Allowed", test_6_same_indicator_different_story_allowed),
        ("Family Not Hard-Blocked", test_7_family_repetition_not_hard_blocked),
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
        print("\n✅ ALL ANTI-REPEAT VALIDATION TESTS PASSED")
        return True
    else:
        print("\n❌ SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)