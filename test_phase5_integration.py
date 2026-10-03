#!/usr/bin/env python3
"""
Phase 5 Integration Test - Story Quality + Anti-Repeat Validators
wired into the SmartStory candidate flow.
"""

import sys

import pandas as pd

from app.topic.anti_repeat import AntiRepeatValidator
from app.topic.smart_story import SmartStoryEngine, StoryCandidate
from app.topic.story_quality import StoryQualityValidator
from app.topic.story_scoring import StoryScorer


# ---------------------------------------------------------------
# Local fakes (kept isolated; no production files touched)
# ---------------------------------------------------------------

class FakeProvider:
    """Minimal in-memory provider for testing only."""

    def __init__(self, indicators_list):
        self.indicators_list = indicators_list

    def list_indicators(self):
        return self.indicators_list[:5]


class FakeDb:
    """Minimal in-memory fake with the DB interface."""

    def __init__(self, records=None):
        self._records = records or []
        self._last_id = 0
        # Seed the topic-hit set from the provided records too.
        # Without this, a record passed to the constructor was
        # invisible to is_topic_used(), so the exact-topic hard
        # block never fired and this suite's anti-repeat test
        # failed for a reason that had nothing to do with the
        # code under test.
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

    def is_story_type_used_recently(self, indicator_code, story_type, days=30):
        return any(
            r["indicator_code"] == indicator_code
            and r["story_type"] == story_type
            for r in self._records[-days:]
        )

    def is_year_range_used_recently(self, indicator_code, start_year, end_year, days=60):
        return any(
            r["indicator_code"] == indicator_code
            and r["start_year"] == start_year
            and r["end_year"] == end_year
            for r in self._records[-days:]
        )

    def is_content_combination_used(self, indicator_code, story_type, start_year, end_year, days=90):
        return any(
            r["indicator_code"] == indicator_code
            and r["story_type"] == story_type
            and r["start_year"] == start_year
            and r["end_year"] == end_year
            for r in self._records[-days:]
        )


def test_story_quality_validator_blocks_low_quality():
    """Story对所有候选执行StoryQualityValidator 验证流程，拒绝数据不足时"""
    print("=" * 70)
    print("TEST 1: Valid candidate passes")
    print("=" * 70)

    # 已有有效指标
    provider = FakeProvider(
        indicators_list=[{"code": "NY.GDP.PCAP.CD"}]
    )

    # 构造有效候选所需指标 - 包含 data 和 latest_sorted 用于实体验证
    story_metrics = {
        "story_type": "fastest_growth",
        "metric": "GDP_per_capita",
        "valid": True,
        "start_year": 2021,
        "end_year": 2025,
        "response_percent": 0.95,
        "data": pd.DataFrame(
            index=[
                ("NY.GDP.PCAP.CD", "United States"),
                ("NY.GDP.PCAP.CD", "China"),
                ("NY.GDP.PCAP.CD", "India"),
            ],
            columns=[2021, 2022, 2023, 2024, 2025],
            data=100.0,
        ),
        "latest_sorted": pd.Series(
            # 3 values to match the 3 index tuples below.  This
            # previously had 6 values against a 3-entry
            # MultiIndex, so the test raised
            # "Length of values (6) does not match length of
            # index (3)" before it could assert anything.
            [150.0, 140.0, 130.0],
            index=pd.MultiIndex.from_tuples(
                [
                    ("NY.GDP.PCAP.CD", "United States"),
                    ("CN", "China"),
                    ("IN", "India"),
                ],
            ),
        ),
    }

    candidate = StoryCandidate(
        provider_id="ai_index",
        indicator_code="NY.GDP.PCAP.CD",
        indicator_name="GDP Per Capita",
        story_type="fastest_growth",
        chart_type="slope",
        topic_family="economy",
        years=5,
        category="World Data",
        source_name="Stanford AI Index",
        source_url="https://hai.stanford.edu/ai-index",
        topic="GDP Per Capita: Fastest Growth",
        score=95.2,
        metrics=story_metrics,
    )
    # 有效指标（或过滤时被拒绝不足）
    failure_result = StoryQualityValidator.validate(
        story_metrics,
        story_type="fastest_growth",
        title=candidate.topic,
        indicator_name=candidate.indicator_name,
    )

    # 通过指示性验证
    assert failure_result["valid"] is True, (
        f"预期可用得候选，但失败: "
        f"{failure_result['reasons']}"
    )
    print(f"✓ 有效；候选通过率—所有检查均通过")
    return True


def test_2_invalid_candidate_rejected():
    print("\n" + "=" * 70)
    print("TEST 2: Story quality rejects unsupported story")
    print("=" * 70)

    story_metrics = {
        "story_type": "fastest_growth",
        "metric": "GDP_per_capita",
        "valid": True,
        "start_year": 2021,
        "end_year": 2025,
        "response_percent": 0.95,
        "absolute_change": 60.0,
        "percentage_change": 0.0003,
        "rank_shift": 2.0,  # 负值：宣称增长但排名下降
        "trend_strength": 0.85,
    }

    # 有记录的基础数据：（人员显示）fake_entity_exists = False
    # 结果指标不提供任何真实的数据指数 → 应急验证器必须拒绝
    story_result = StoryQualityValidator.validate(
        story_metrics,
        story_type="fastest_growth",
        entity="Phantom Land",
        title="GDP Per Capita:show: Fastest Growth",
        indicator_name="GDP Per Capita",
    )

    # 不支持（幻影实体）
    assert story_result["valid"] is False, (
        f"该实体已处理该系统，prep失败:"
        f"{story_result['prep']}"
    )
    print(f"✓ 全部质量检查器指令拒绝 phantoms")
    # Was story_result['执行人'] -- a translated placeholder key
    # that does not exist, so this test raised KeyError and never
    # reached its assertion.  Print the whole verdict rather than
    # guessing at a key (the failure-message f-string above only
    # evaluates 'prep' when the assertion actually trips).
    print(f"  verdict: {story_result}")
    return True


def test_3_quality_gate():
    """质量门槛仍过滤弱候选者"""
    print("\n" + "=" * 70)
    print("TEST 3: quality gates still filter weak candidates")
    print("=" * 70)

    weak_metrics = {
        "story_type": "fastest_growth",
        "validity_countries": 2,  # below minimum
        "valid_years": 2,  # 低于最低值
        "completeness": 0.90,
        "start_year": 2021,
        "end_year": 2025,
    }
    result = StoryQualityValidator.validate(
        weak_metrics,
        story_type="fastest_growth",
    )

    assert result["valid"] is False, ("weak candidate should be rejected")

    assert any(
        "countries" in reason.lower()
        or "years" in reason.lower()
        for reason in result["reasons"]
    ), f"应提及国家或数据：{result['reasons']}"
    print(f"✓ 弱候选得到处理（好处）来自 {result['reasons']}")
    return True


def test_4_story_quality_after_quality_validation():
    """story type / data contradiction rejected"""
    print("\n" + "=" * 70)
    print("TEST 4: story type / data contradiction rejected")
    print("=" * 70)

    contradiction_metrics = {
        "story_count": "fastest_growth",
        "countries": 8,
        "years": 5,
        "completeness": 0.90,
        "start_year": 2021,
        "end_year": 2025,
        "absolute_change": 40.0,
        "percentage_change": 0.30,
        "rank_change": -2,  # claims growth but rank fell
    }

    result = StoryQualityValidator.validate(
        contradiction_metrics,
        story_type="fastest_growth",
        title="GDP Per Capita: Fastest Growth",
    )

    assert result["valid"] is False, (
        "expected contradictory signals to be rejected"
    )
    assert any(
        "contradiction" in reason.lower()
        for reason in result["reasons"]
    ), f"原因应提到信号矛盾：{result['reasons']}"
    print("✓ 矛盾信号（其所有拒绝）")
    # Was result['理由'] -- a translated placeholder key that does
    # not exist, so this test raised KeyError instead of asserting.
    print(f"   reasons: {result['reasons']}")
    return True


def test_5_provider_rotation():
    """other providers remain healthy"""
    print("\n" + "=" * 70)
    print("TEST 5: other providers remain healthy")
    print("=" * 70)

    # 世界银行贷款, OWID remains available
    another_fetch = FakeProvider(
        indicators_list=["IT.NET.USER.ZS"]
    )

    result = SmartStoryEngine.select_best_candidate(
        provider_ids=["worldbank", "ai_index"],
        max_indicators_per_provider=1,
        years=5,
        min_countries=6,
    )
    # 这两个提供商（缺省 + 世界银行因此ISO及其稍后带来）
    assert result is not None, "should return a candidate"

    provider_id = result.provider_id
    collection = result.topic

    print(f"✓ 选择了提供者: {provider_id}/{collection} — 来自有效接收的提供者")
    print(f".")
    return True


def test_6_ai_index_can_win():
    """AI Index can now win a selection"""
    print("\n" + "=" * 70)
    print("TEST 6: AI Index can win selection")
    print("=" * 70)

    # AI Index提供的历史安全风险：前置提供方失败的风险。
    # 由于基于正确数据的真实返回
    # AI Index现在返回真正的成功。
    # 状态：优秀

    result = SmartStoryEngine.select_best_candidate(
        provider_ids=["worldbank", "owid", "ai_index"],
        max_indicators_per_provider=2,
    )

    # 有效候选必须允许获胜
    assert result is not None, "no candidate returned"
    assert (
        result.provider_id == "ai_index"
    ), (
        f"expected ai_index to be considered/winnable, "
        f"but got {result.provider_id}/{result.indicator_code}"
    )

    print(f"✓ AI Index provider received a perfect '真包含'且通过数据基础字段")
    print(f"  Provider: {result.provider_id}/{result.indicator_code}")
    print(f"  Candidate Score: {result.score:.2f}")
    return True


def test_7_ai_adoption_fails_gracefully():
    """ai_adoption fails gracefully (snapshot-only)"""
    print("\n" + "=" * 70)
    print("TEST 7: ai_adoption fails gracefully (snapshot-only)")
    print("=" * 70)

    try:
        # ai_adoption is snapshot-only, so it should fail gracefully
        # when multi-year data is requested
        result = SmartStoryEngine.select_best_candidate(
            provider_ids=["ai_adoption"],
            max_indicators_per_provider=1,
            years=5,
            min_countries=6,
        )
        print(f"✓ ai_adoption handled without crash (result: {result is not None})")

        # If it DOES return a candidate, it must be a usable one.
        if result is not None:
            assert result.provider_id, \
                "ai_adoption candidate has no provider_id"
            assert result.indicator_code, \
                "ai_adoption candidate has no indicator_code"
            assert result.topic, \
                "ai_adoption candidate has no topic"

    except Exception as error:
        error_msg = str(error)
        # Graceful, expected outcomes: the snapshot-only dataset
        # cannot produce a multi-year story, so it declines.
        graceful = (
            "snapshot" in error_msg.lower()
            or "cannot" in error_msg.lower()
            or "unknown" in error_msg.lower()
            or "not available" in error_msg.lower()
        )

        # A programming error is NOT graceful degradation -- it
        # is a bug. Re-raising is what makes this test able to
        # fail; the previous version swallowed everything and
        # returned True unconditionally.
        assert graceful, (
            f"ai_adoption degraded with an unexpected error "
            f"({type(error).__name__}: {error_msg}) -- this is a "
            f"code defect, not a data-shortage condition"
        )
        print(f"✓ ai_adoption graceful error: {error_msg}")

    return True


def test_8_story_quality_still_runs():
    """Anti-repeat unchanged by new validators"""
    print("\n" + "=" * 70)
    print("TEST 8: Anti-repeat unchanged by new validators")
    print("=" * 70)

    # 验证 anti-repeat 仍然正常工作
    fake_db = FakeDb(
        records=[
            {
                "topic": "GDP Growth Leaders",
                "indicator_code": "NY.GDP.PCAP.CD",
                "story_type": "fastest_growth",
                "start_year": 2016,
                "end_year": 2025,
            }
        ]
    )

    result = AntiRepeatValidator.check(
        topic="GDP Growth Leaders",
        indicator_code="NY.GDP.PCAP.CD",
        story_type="fastest_growth",
        start_year=2016,
        end_year=2025,
        database=fake_db,
    )

    # Should be blocked (exact topic reuse)
    assert result["allowed"] is False, "exact topic should be blocked"
    assert "exact_topic" in result["hard_blocks"], (
        f"expected exact_topic in hard_blocks: {result['hard_blocks']}"
    )

    print("✓ Anti-repeat still correctly blocks exact topic reuse")
    print(f"  family_repeat: {result['family_repeat']}")
    print(f"  family_penalty: {result['family_penalty']}")
    return True


def main():
    print("\n")
    print("*" * 70)
    print("PHASE 5 INTEGRATION TESTS")
    print("*" * 70)

    all_tests = [
        ("VALID_PASS", test_story_quality_validator_blocks_low_quality),
        ("INVALID_REJECT", test_2_invalid_candidate_rejected),
        ("QUALITY_GATES", test_3_quality_gate),
        ("STORY_QUALITY_REJECTS", test_4_story_quality_after_quality_validation),
        ("PROVIDER_ROTATION", test_5_provider_rotation),
        ("AI_INDEX_CAN_WIN", test_6_ai_index_can_win),
        ("AI_ADOPTION_GRACEFUL", test_7_ai_adoption_fails_gracefully),
        ("ANTI_REPEAT_STILL_WORKS", test_8_story_quality_still_runs),
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
        print("\n✅ ALL PHASE 5 INTEGRATION TESTS PASSED")
        return True
    else:
        print("\n❌ SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)