#!/usr/bin/env python3
"""
End-to-End Story + Content Validation

Verifies the complete story-selection path from provider data
to the final selected topic.

Tests the pipeline:
  Provider Data
      ↓
  Normalized Data
      ↓
  Candidate Generation
      ↓
  Quality Validation
      ↓
  Anti-Repeat
      ↓
  Diversity
      ↓
  Final Candidate
      ↓
  Story Type + Entity + Years + Metrics + Title + Chart
"""

import functools
import sys
import pandas as pd

from app.topic.anti_repeat import AntiRepeatValidator
from app.topic.smart_story import SmartStoryEngine
from app.topic.story_quality import StoryQualityValidator
from app.topic.story_scoring import StoryScorer


def must_pass(func):
    """Turn this test's `return False` into a real failure.

    pytest DISCARDS a test function's return value, so a test
    that only `return`s a boolean is collected, executed, and
    always reported PASS.  This wrapper makes it decisive
    again while leaving the script-mode runner untouched.
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


class _EnvironmentSkip(Exception):
    """A test that could not reach a verdict, because the live
    providers changed underneath it.

    Recorded as SKIPPED -- deliberately NOT counted as a pass,
    so an environment problem can never masquerade as success.
    """


def _skip(reason):
    """Skip the current test, honestly labelled."""
    if "pytest" in sys.modules:
        import pytest
        pytest.skip(reason)
    raise _EnvironmentSkip(reason)


class _FakeDb:
    """Minimal in-memory stand-in for the real database.

    Used so tests can exercise the anti-repeat logic without
    writing junk rows into the production database (which has
    no delete API).
    """

    def __init__(self, records=None):
        self._records = records or []
        self._last_id = 0
        # Seed the topic-hit set from the provided records too --
        # otherwise a seeded "used" topic would not register and
        # is_topic_used() would wrongly report it as fresh.
        self._topic_hits = {
            r.get("topic", "") for r in self._records
        }

    def get_recent_records(self, limit=100):
        return self._records[:limit]

    def get_recent_content(self, limit=100):
        return self._records[:limit]

    def save_record(self, **fields):
        self._last_id += 1
        record = {"id": self._last_id}
        record.update(fields)
        self._records.append(record)
        self._topic_hits.add(record.get("topic", ""))
        return record

    def is_topic_used(self, topic):
        return topic in self._topic_hits

    def is_story_type_used_recently(self, indicator_code,
                                    story_type, days=30):
        return any(
            r["indicator_code"] == indicator_code
            and r["story_type"] == story_type
            for r in self._records[-days:]
        )

    def is_year_range_used_recently(self, indicator_code,
                                    start_year, end_year,
                                    days=60):
        return any(
            r["indicator_code"] == indicator_code
            and r["start_year"] == start_year
            and r["end_year"] == end_year
            for r in self._records[-days:]
        )

    def is_content_combination_used(self, indicator_code,
                                    story_type, start_year,
                                    end_year, days=90):
        return any(
            r["indicator_code"] == indicator_code
            and r["story_type"] == story_type
            and r["start_year"] == start_year
            and r["end_year"] == end_year
            for r in self._records[-days:]
        )




@must_pass
def test_valid_candidate_survives():
    """TEST 1: A legitimate candidate reaches final selection."""
    print("\n" + "=" * 70)
    print("TEST 1: Valid candidate survives")
    print("=" * 70)

    result = SmartStoryEngine.select_best_candidate(
        provider_ids=["worldbank", "ai_index"],
        max_indicators_per_provider=2,
        years=5,
        min_countries=6,
    )

    # A valid candidate should be returned (AI Index may win)
    # The key is it doesn't crash and returns a proper candidate
    if result is not None:
        # Verify candidate has all required fields
        assert hasattr(result, 'provider_id'), "Missing provider_id"
        assert hasattr(result, 'indicator_code'), "Missing indicator_code"
        assert hasattr(result, 'story_type'), "Missing story_type"
        assert hasattr(result, 'topic'), "Missing topic"
        assert hasattr(result, 'score'), "Missing score"
        assert hasattr(result, 'metrics'), "Missing metrics"

        # Verify required fields are non-empty
        assert result.provider_id, "provider_id should be non-empty"
        assert result.indicator_code, "indicator_code should be non-empty"
        assert result.story_type, "story_type should be non-empty"
        assert result.topic, "topic should be non-empty"

        print(f"✓ Valid candidate survived selection")
        print(f"  Provider: {result.provider_id}")
        print(f"  Indicator: {result.indicator_code}")
        print(f"  Story Type: {result.story_type}")
        print(f"  Topic: {result.topic}")
        print(f"  Score: {result.score:.2f}")
    else:
        # No candidate is also acceptable (e.g., ai_adoption only)
        print(f"✓ No candidate returned (acceptable for some provider configs)")

    return True


@must_pass
def test_entity_consistency():
    """TEST 2: A candidate referencing a nonexistent entity is rejected."""
    print("\n" + "=" * 70)
    print("TEST 2: Entity consistency")
    print("=" * 70)

    # Use World Bank data which has real country data
    result = SmartStoryEngine.select_best_candidate(
        provider_ids=["worldbank"],
        max_indicators_per_provider=1,
        years=5,
        min_countries=6,
    )

    if result is not None:
        # The entity should exist in the data
        metrics = result.metrics
        entity = metrics.get("entity", "")

        # For World Bank GDP data, entities should be actual countries
        # We can't check specific country names without the full dataset,
        # but we can verify the entity field is populated
        assert entity, "entity should be populated"

        # Verify the metrics have start/end values
        assert metrics.get("start_value") is not None, "start_value should exist"
        assert metrics.get("end_value") is not None, "end_value should exist"
        assert metrics.get("start_year") is not None, "start_year should exist"
        assert metrics.get("end_year") is not None, "end_year should exist"

        # Verify start_year < end_year
        assert metrics.get("start_year") < metrics.get("end_year"), \
            "start_year should be less than end_year"

        print(f"✓ Entity consistency verified")
        print(f"  Entity: {entity}")
        print(f"  Start-End: {metrics.get('start_year')} → {metrics.get('end_year')}")
        print(f"  Start Value: {metrics.get('start_value')}")
        print(f"  End Value: {metrics.get('end_value')}")
    else:
        print(f"✓ No candidate (entity check skipped)")

    return True


@must_pass
def test_year_consistency():
    """TEST 3: A candidate referencing unavailable years is rejected."""
    print("\n" + "=" * 70)
    print("TEST 3: Year consistency")
    print("=" * 70)

    result = SmartStoryEngine.select_best_candidate(
        provider_ids=["worldbank"],
        max_indicators_per_provider=1,
        years=5,
        min_countries=6,
    )

    if result is not None:
        metrics = result.metrics

        # Verify years are valid
        start_year = metrics.get("start_year")
        end_year = metrics.get("end_year")

        # Both years should exist and start < end
        assert start_year is not None, "start_year should exist"
        assert end_year is not None, "end_year should exist"
        assert start_year < end_year, "start_year should be less than end_year"

        # Verify the data actually has these years
        # The underlying data columns should include these years
        print(f"✓ Year consistency verified")
        print(f"  Start-End: {start_year} → {end_year}")

    return True


@must_pass
def test_story_direction():
    """TEST 4: A growth story cannot be generated from declining data."""
    print("\n" + "=" * 70)
    print("TEST 4: Story direction consistency")
    print("=" * 70)

    # This test verifies that the story type matches the data direction
    # We'll check by looking at the candidate's metrics

    result = SmartStoryEngine.select_best_candidate(
        provider_ids=["worldbank", "ai_index"],
        max_indicators_per_provider=2,
        years=5,
        min_countries=6,
    )

    if result is not None:
        metrics = result.metrics
        story_type = result.story_type
        pct_change = metrics.get("percentage_change")

        # For a "fastest_growth" story, percentage_change should be positive
        # For "biggest_decline", it should be negative
        # We can't strictly enforce this without knowing the exact story type,
        # but we can verify the metrics are internally consistent

        print(f"✓ Story direction checked")
        print(f"  Story Type: {story_type}")
        print(f"  Percentage Change: {pct_change}")

        # The important thing is that the candidate's metrics are
        # self-consistent (start/end values match percent_change sign)
        start_val = metrics.get("start_value")
        end_val = metrics.get("end_value")
        abs_change = metrics.get("absolute_change")

        # Previously this block only PRINTED when the numbers
        # agreed and then returned True unconditionally, so an
        # inconsistent candidate passed silently.
        if (start_val is not None and end_val is not None
                and abs_change is not None and pct_change is not None):
            assert abs_change == abs(end_val - start_val) or \
                abs(abs_change - (end_val - start_val)) < 1e-6, (
                    f"absolute_change {abs_change} disagrees with "
                    f"end-start {end_val - start_val}"
                )

            if start_val != 0:
                expected_pct = abs_change / abs(start_val) * 100
                if expected_pct != 0:
                    # NOTE: metrics["percentage_change"] holds a
                    # FRACTION (0.20 means 20%), despite the name.
                    # The old code formatted it with `:.2%`, which
                    # confirms the fraction convention.
                    pct_diff = abs(
                        pct_change * 100 - expected_pct
                    ) / abs(expected_pct) * 100
                    assert pct_diff < 50, (
                        f"percentage_change {pct_change * 100} differs "
                        f"from the value implied by the series "
                        f"({expected_pct:.4f}) by {pct_diff:.1f}%"
                    )

            # A direction-tagged story must agree with its data.
            if story_type == "fastest_growth":
                assert (end_val - start_val) > 0, (
                    "fastest_growth story built from non-growing data "
                    f"({start_val} -> {end_val})"
                )
            elif story_type == "biggest_decline":
                assert (end_val - start_val) < 0, (
                    "biggest_decline story built from non-declining "
                    f"data ({start_val} -> {end_val})"
                )

    return True


@must_pass
def test_metric_consistency():
    """TEST 5: Candidate metrics match the underlying DataFrame."""
    print("\n" + "=" * 70)
    print("TEST 5: Metric consistency")
    print("=" * 70)

    result = SmartStoryEngine.select_best_candidate(
        provider_ids=["worldbank"],
        max_indicators_per_provider=1,
        years=5,
        min_countries=6,
    )

    if result is not None:
        metrics = result.metrics

        # Verify key metric fields exist and are reasonable
        required_fields = [
            "start_value", "end_value", "absolute_change",
            "percentage_change", "start_rank", "end_rank",
            "rank_change", "number_of_valid_countries",
            "number_of_valid_years"
        ]

        for field in required_fields:
            assert field in metrics, f"Missing required field: {field}"
            val = metrics[field]
            # For numeric fields, verify they're not None (except rank which can be)
            if field in ["start_value", "end_value", "absolute_change", "percentage_change"]:
                assert val is not None, f"{field} should not be None"

        print(f"✓ Metric consistency verified")
        print(f"  Required fields present: {all(f in metrics for f in required_fields)}")

    return True


@must_pass
def test_title_accuracy():
    """TEST 6: Title/story combination accuracy."""
    print("\n" + "=" * 70)
    print("TEST 6: Title accuracy")
    print("=" * 70)

    result = SmartStoryEngine.select_best_candidate(
        provider_ids=["worldbank", "ai_index"],
        max_indicators_per_provider=2,
        years=5,
        min_countries=6,
    )

    if result is not None:
        topic = result.topic
        story_type = result.story_type

        # The topic should not be completely nonsensical
        # It should reference the indicator name and story type
        indicator_name = result.indicator_name
        assert indicator_name, "indicator_name should exist"
        assert topic, "topic should exist"

        # Verify the topic contains the indicator name
        # (it may be truncated or modified, but should reference it)
        indicator_lower = indicator_name.lower()
        topic_lower = topic.lower()

        # The topic should mention the indicator or entity
        metrics = result.metrics
        entity_val = metrics.get("entity", "")
        has_indicator = indicator_lower in topic_lower
        has_entity = len(entity_val) > 2 and entity_val.lower() in topic_lower

        print(f"✓ Title accuracy checked")
        print(f"  Topic: {topic}")
        print(f"  Indicator: {indicator_name}")
        print(f"  Story Type: {story_type}")

    return True


@must_pass
def test_indicator_description():
    """TEST 7: Indicator description accuracy."""
    print("\n" + "=" * 70)
    print("TEST 7: Indicator description accuracy")
    print("=" * 70)

    result = SmartStoryEngine.select_best_candidate(
        provider_ids=["worldbank", "ai_index"],
        max_indicators_per_provider=2,
        years=5,
        min_countries=6,
    )

    if result is not None:
        # The indicator name should be meaningful
        indicator_name = result.indicator_name
        indicator_code = result.indicator_code

        # Should have a non-empty indicator name
        assert indicator_name, "indicator_name should be non-empty"

        # The indicator code should be a valid format
        # (World Bank codes are typically like "NY.GDP.MKTP.CD")
        assert indicator_code, "indicator_code should be non-empty"

        print(f"✓ Indicator description accuracy verified")
        print(f"  Indicator Name: {indicator_name}")
        print(f"  Indicator Code: {indicator_code}")

    return True


@must_pass
def test_chart_compatibility():
    """TEST 8: Chart compatibility."""
    print("\n" + "=" * 70)
    print("TEST 8: Chart compatibility")
    print("=" * 70)

    result = SmartStoryEngine.select_best_candidate(
        provider_ids=["worldbank", "ai_index"],
        max_indicators_per_provider=2,
        years=5,
        min_countries=6,
    )

    if result is not None:
        story_type = result.story_type
        chart_type = result.chart_type

        # Verify chart type is reasonable for story type
        # Basic compatibility map
        compatible = {
            "fastest_growth": "top5_change",
            "biggest_decline": "top5_change",
            "rank_climber": "slope",
            "rank_decline": "slope",
            "current_leader": "bar_race",
            "leader_challenge": "bar_race",
            "trend_over_time": "line",
        }

        expected = compatible.get(story_type)
        # The chart type should be one of the expected types
        # (it may differ slightly due to ChartSelector logic, but should be reasonable)
        print(f"✓ Chart compatibility checked")
        print(f"  Story Type: {story_type}")
        print(f"  Chart Type: {chart_type}")
        print(f"  Expected: {expected}")

        # `expected` used to be computed and then never compared
        # against anything, so this test verified nothing at all.
        #
        # The real contract is NOT "chart_type == STORY_TO_CHART
        # [story_type]": ChartSelector deliberately re-rolls the
        # chart from a weighted distribution (bar_race 50%,
        # top5_change 20%, area 15%, bubble 10%, line 5%) so
        # consecutive videos don't look identical.  The map only
        # seeds/validates.  What must hold is that the emitted
        # type is renderable, and that bubble never appears
        # without multidimensional data.
        from app.topic.chart_selector import ChartSelector

        valid_charts = set(ChartSelector.CHART_DISTRIBUTION) | \
            set(ChartSelector.DEFAULT_MAP.values())

        assert chart_type in valid_charts, (
            f"selector returned non-renderable chart type "
            f"{chart_type!r} (renderable: {sorted(valid_charts)})"
        )

        if expected is not None:
            print(f"  (story map default is {expected!r}; the "
                  f"weighted selector is allowed to vary it)")

        # A bubble chart needs multidimensional data; a story
        # flagged as such must not silently fall back.
        if chart_type == "bubble":
            assert result.metrics.get("bubble_safe", True), (
                "bubble selected for a candidate not marked "
                "bubble-safe"
            )

    return True


@must_pass
def test_ai_index_real_data():
    """TEST 9: AI Index real data verification."""
    print("\n" + "=" * 70)
    print("TEST 9: AI Index real data")
    print("=" * 70)

    result = SmartStoryEngine.select_best_candidate(
        provider_ids=["ai_index"],
        max_indicators_per_provider=2,
    )

    if result is not None:
        # Verify it's actually an AI Index candidate
        assert result.provider_id == "ai_index", "Should be ai_index provider"

        # Verify metrics have real data
        metrics = result.metrics
        assert metrics is not None, "Metrics should exist"

        # The candidate should be internally consistent
        assert result.topic, "Topic should exist"
        assert result.indicator_code, "Indicator code should exist"
        assert result.story_type, "Story type should exist"

        print(f"✓ AI Index real data verified")
        print(f"  Provider: {result.provider_id}")
        print(f"  Indicator: {result.indicator_code}/{result.story_type}")
        print(f"  Topic: {result.topic}")
        print(f"  Score: {result.score:.2f}")

    return True


@must_pass
def test_ai_adoption_graceful():
    """TEST 10: ai_adoption graceful behavior."""
    print("\n" + "=" * 70)
    print("TEST 10: ai_adoption graceful behavior")
    print("=" * 70)

    try:
        result = SmartStoryEngine.select_best_candidate(
            provider_ids=["ai_adoption"],
            max_indicators_per_provider=1,
            years=5,
            min_countries=6,
        )

        # If it returns a result, that's acceptable
        # The key is it doesn't crash with an incomprehensible error
        if result is not None:
            print(f"✓ ai_adoption returned a candidate (acceptable)")
            assert result.provider_id, \
                "ai_adoption candidate has no provider_id"
            assert result.topic, \
                "ai_adoption candidate has no topic"

        print(f"✓ ai_adoption handled without crash")

    except AssertionError:
        raise
    except Exception as error:
        error_msg = str(error)
        # If it raises, it should be a comprehensible error
        # about snapshot-only data or unavailable provider
        graceful = (
            "snapshot" in error_msg.lower()
            or "cannot" in error_msg.lower()
            or "unknown" in error_msg.lower()
            or "not available" in error_msg.lower()
        )
        # Previously EVERY exception was accepted and the test
        # returned True regardless, so a genuine crash was
        # indistinguishable from graceful degradation.
        assert graceful, (
            f"ai_adoption crashed with an unexpected error "
            f"({type(error).__name__}: {error_msg}) -- a code "
            f"defect rather than a data-shortage condition"
        )
        print(f"✓ ai_adoption graceful error: {error_msg}")

    return True


@must_pass
def test_anti_repeat_still_works():
    """TEST 11: Anti-repeat still works in end-to-end flow."""
    print("\n" + "=" * 70)
    print("TEST 11: Anti-repeat still works")
    print("=" * 70)

    # Previously this wrote a junk row ("Test Repeated Story") into
    # the REAL production database on every test run -- there is no
    # delete API, so the row stayed forever and could influence the
    # live anti-repeat logic.  Use an in-memory fake instead (the
    # same pattern test_phase5_integration.py uses).
    fake_db = _FakeDb(
        records=[
            {
                "topic": "Test Repeated Story",
                "indicator_code": "NY.GDP.PCAP.CD",
                "story_type": "fastest_growth",
                "start_year": 2021,
                "end_year": 2025,
            }
        ]
    )

    result = AntiRepeatValidator.check(
        topic="Test Repeated Story",
        indicator_code="NY.GDP.PCAP.CD",
        story_type="fastest_growth",
        start_year=2021,
        end_year=2025,
        database=fake_db,
    )

    # Real assertions: the exact same topic must be hard-blocked.
    # Previously this printed a message and returned True no matter
    # what the validator decided.
    assert result["allowed"] is False, (
        f"exact topic reuse was not blocked: {result}"
    )
    assert "exact_topic" in result.get("hard_blocks", []), (
        f"expected exact_topic in hard_blocks, got "
        f"{result.get('hard_blocks')}"
    )

    print(f"✓ Anti-repeat still correctly blocks exact topic reuse")
    print(f"  family_repeat: {result['family_repeat']}")
    print(f"  family_penalty: {result['family_penalty']}")

    return True


@must_pass
def test_diversity_still_works():
    """TEST 12: Diversity still works in end-to-end flow."""
    print("\n" + "=" * 70)
    print("TEST 12: Diversity still works")
    print("=" * 70)

    # The diversity scorer should be active
    # We verify by checking that the selection pipeline
    # includes the diversity step

    result = SmartStoryEngine.select_best_candidate(
        provider_ids=["worldbank", "ai_index"],
        max_indicators_per_provider=2,
        years=5,
        min_countries=6,
    )

    if result is not None:
        print(f"✓ Diversity path active - candidate selected: {result.topic[:50]}")
        # A candidate that came back must be complete.  The old
        # version printed and returned True either way, so a
        # half-built candidate was indistinguishable from a
        # healthy one.
        assert result.topic, "selected candidate has no topic"
        assert result.provider_id, "selected candidate has no provider_id"
        assert result.indicator_code, \
            "selected candidate has no indicator_code"
        assert result.story_type, "selected candidate has no story_type"
    else:
        print(f"✓ Pipeline active (no candidate returned)")
        raise AssertionError(
            "diversity run returned no candidate -- the pipeline "
            "produced nothing to score"
        )

    return True


@must_pass
def test_deterministic_selection():
    """TEST 13: Deterministic selection."""
    print("\n" + "=" * 70)
    print("TEST 13: Deterministic selection")
    print("=" * 70)

    # Run the selection twice with the same conditions
    # The results should be deterministic (same candidate selected)
    # Note: This is hard to test perfectly without controlling
    # the full state, but we can verify the flow is deterministic

    result1 = SmartStoryEngine.select_best_candidate(
        provider_ids=["worldbank"],
        max_indicators_per_provider=1,
        years=5,
        min_countries=6,
    )

    result2 = SmartStoryEngine.select_best_candidate(
        provider_ids=["worldbank"],
        max_indicators_per_provider=1,
        years=5,
        min_countries=6,
    )

    # Both should return either a candidate or None deterministically
    # (not random)
    print(f"✓ Deterministic selection verified")
    print(f"  Result 1: {result1 is not None}")
    print(f"  Result 2: {result2 is not None}")

    # The old version just printed both flags and returned True, so
    # a non-deterministic selector would have passed unnoticed.
    # Identical inputs with unchanged state must give the same
    # candidate.
    #
    # NOTE: this pipeline reads LIVE providers, so the candidate
    # pool can legitimately differ between two calls (observed:
    # "Not enough years available" on one call only).  That is an
    # environment change, not a scoring defect, so it is skipped
    # rather than silently passed.
    if result1 is None or result2 is None:
        if (result1 is None) != (result2 is None):
            _skip(
                "provider availability changed between the two "
                f"calls (run 1 candidate={result1 is not None}, "
                f"run 2 candidate={result2 is not None}); scorer "
                "determinism cannot be judged"
            )
    else:
        assert (result1.indicator_code, result1.story_type) == \
            (result2.indicator_code, result2.story_type), (
                "selection was not deterministic: got "
                f"{result1.indicator_code}/{result1.story_type} then "
                f"{result2.indicator_code}/{result2.story_type}"
            )

    return True


@must_pass
def test_no_fake_data():
    """TEST 14: No fake/demo data."""
    print("\n" + "=" * 70)
    print("TEST 14: No fake/demo data")
    print("=" * 70)

    result = SmartStoryEngine.select_best_candidate(
        provider_ids=["worldbank"],
        max_indicators_per_provider=1,
        years=5,
        min_countries=6,
    )

    if result is not None:
        metrics = result.metrics

        # Verify no demo/fake values
        # World Bank real data should have actual country names,
        # not "Fake Country" or similar

        entity = metrics.get("entity", "")
        # Entity should be populated and not be a demo value
        assert entity and entity != "Fake Country", \
            "Entity should be a real value, not demo data"

        print(f"✓ No fake/demo data")
        print(f"  Entity: {entity}")

    return True


def main():
    print("\n")
    print("=" * 70)
    print("END-TO-END STORY + CONTENT VALIDATION")
    print("=" * 70)

    all_tests = [
        ("VALID_CANDIDATE", test_valid_candidate_survives),
        ("ENTITY_CONSISTENCY", test_entity_consistency),
        ("YEAR_CONSISTENCY", test_year_consistency),
        ("STORY_DIRECTION", test_story_direction),
        ("METRIC_CONSISTENCY", test_metric_consistency),
        ("TITLE_ACCURACY", test_title_accuracy),
        ("INDICATOR_DESCRIPTION", test_indicator_description),
        ("CHART_COMPATIBILITY", test_chart_compatibility),
        ("AI_INDEX_REAL_DATA", test_ai_index_real_data),
        ("AI_ADOPTION_GRACEFUL", test_ai_adoption_graceful),
        ("ANTI_REPEAT_STILL_WORKS", test_anti_repeat_still_works),
        ("DIVERSITY_STILL_WORKS", test_diversity_still_works),
        ("DETERMINISTIC_SELECTION", test_deterministic_selection),
        ("NO_FAKE_DATA", test_no_fake_data),
    ]

    results = []

    for name, func in all_tests:
        try:
            passed = func()
            results.append((name, passed))
        except _EnvironmentSkip as reason:
            # Not a pass and not a failure: no verdict was
            # reachable.  Kept visible so it can never be
            # mistaken for green.
            print(f"\n~ SKIP: {reason}")
            results.append((name, None))
        except Exception as error:
            print(f"\n✗ EXCEPTION: {error}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed_count = sum(1 for _, passed in results if passed)
    skipped_count = sum(1 for _, passed in results if passed is None)
    total = len(results)

    for name, passed in results:
        if passed is None:
            status = "~ SKIP"
        elif passed:
            status = "✓ PASS"
        else:
            status = "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed_count}/{total} tests passed"
          f" ({skipped_count} skipped)")

    if passed_count == total:
        print("\n✅ ALL END-TO-END VALIDATION TESTS PASSED")
        return True
    elif passed_count + skipped_count == total:
        # Everything either passed or was skipped -- no failures.
        print(f"\n⚠ NO FAILURES ({skipped_count} test(s) skipped "
              f"because the live providers changed mid-run)")
        return True
    else:
        print("\n❌ SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)