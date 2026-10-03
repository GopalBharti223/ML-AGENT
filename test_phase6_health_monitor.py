#!/usr/bin/env python3
"""
Phase 6 Integration Test - Provider Health Monitor + Circuit Breaker

Verifies:
1. Unknown providers default to available / UNKNOWN status
2. A single failure -> DEGRADED but still available
3. failure_threshold consecutive failures -> DOWN + breaker opens
4. Half-open probe: fail re-opens with DOUBLED cooldown;
   success closes the breaker (HEALTHY, backoff reset)
5. State persists across instances (JSON round-trip)
6. Corrupt state file is ignored safely
7. report() / snapshot() / one_line_summary() shapes
8. SmartStoryEngine wiring: failures recorded during fetching,
   provider skipped by the breaker on the NEXT run (no re-fetch)

No network required: providers are faked at the registry level.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(
    0,
    os.path.dirname(os.path.abspath(__file__))
)

# ---------------------------------------------------------------
# UNICODE-SAFE OUTPUT (repo convention)
# ---------------------------------------------------------------

for _stream in (sys.stdout, sys.stderr):

    if _stream and hasattr(_stream, "reconfigure"):

        try:

            _stream.reconfigure(
                encoding="utf-8",
                errors="replace",
            )

        except (ValueError, OSError):

            pass

import pandas as pd

from app.data.providers.base import DataProviderResult, IndicatorInfo
from app.data.providers.health import (
    ProviderHealthMonitor,
    STATUS_DEGRADED,
    STATUS_DOWN,
    STATUS_HALF_OPEN,
    STATUS_HEALTHY,
    STATUS_UNKNOWN,
)

import app.topic.smart_story as smart_story_module

from app.topic.smart_story import SmartStoryEngine


# ---------------------------------------------------------------
# Local fakes (kept isolated; no production files touched)
# ---------------------------------------------------------------

def _fake_indicators(count):

    return [
        IndicatorInfo(
            code=f"FAKE.{i}",
            name=f"Fake indicator {i}",
            category="test",
        )
        for i in range(count)
    ]


class FailingProvider:
    """Simulates an upstream API outage: every fetch raises."""

    provider_id = "fakeprov"
    provider_name = "Fake Always-Failing Provider"

    @classmethod
    def list_indicators(cls):
        return _fake_indicators(4)

    @classmethod
    def fetch_normalized(cls, **kwargs):
        raise RuntimeError("simulated upstream outage")


class PatchedRegistry:
    """Serves FailingProvider for 'fakeprov'; passes others through."""

    @classmethod
    def get(cls, provider_id):
        if provider_id == "fakeprov":
            return FailingProvider
        raise ValueError(f"unknown provider: {provider_id}")


def make_monitor(tmp_dir, persist=True, **overrides):
    """Fresh monitor isolated from production state files."""

    defaults = dict(
        state_path=str(Path(tmp_dir) / "health.json"),
        alerts_path=str(Path(tmp_dir) / "alerts.log"),
        degraded_after=1,
        failure_threshold=3,
        cooldown_seconds=300.0,
        max_cooldown_seconds=3600.0,
        persist=persist,
    )

    defaults.update(overrides)

    return ProviderHealthMonitor(**defaults)


# ---------------------------------------------------------------
# UNIT TESTS -- monitor behavior
# ---------------------------------------------------------------

def test_unknown_provider_defaults():
    """Never-seen providers are available and UNKNOWN."""

    print("=" * 70)
    print("TEST 1: Unknown provider defaults")
    print("=" * 70)

    tmp = tempfile.mkdtemp()

    monitor = make_monitor(tmp)

    assert monitor.is_available("never_seen") is True
    assert monitor.status("never_seen") == STATUS_UNKNOWN

    snap = monitor.snapshot()
    assert snap == {}, f"snapshot should be empty: {snap}"

    print("ok - unknown provider is available with UNKNOWN status")
    return True


def test_degraded_but_available():
    """One failure -> DEGRADED, breaker still closed."""

    print("\n" + "=" * 70)
    print("TEST 2: Single failure degrades without opening")
    print("=" * 70)

    tmp = tempfile.mkdtemp()

    monitor = make_monitor(tmp)

    monitor.record_failure("p", "X.1", "boom")

    assert monitor.status("p") == STATUS_DEGRADED
    assert monitor.is_available("p") is True

    state = monitor.snapshot()["p"]
    assert state["total_failures"] == 1
    assert state["consecutive_failures"] == 1
    assert state["last_error"] == "boom"
    assert state["last_error_indicator"] == "X.1"

    # A success fully restores HEALTHY.
    monitor.record_success("p", "X.1")

    assert monitor.status("p") == STATUS_HEALTHY

    state = monitor.snapshot()["p"]
    assert state["consecutive_failures"] == 0
    assert state["total_successes"] == 1

    print("ok - DEGRADED after 1 failure, HEALTHY after success")
    return True


def test_circuit_opens_after_threshold():
    """failure_threshold consecutive failures -> DOWN + skip."""

    print("\n" + "=" * 70)
    print("TEST 3: Circuit opens at threshold")
    print("=" * 70)

    tmp = tempfile.mkdtemp()

    monitor = make_monitor(tmp, failure_threshold=3)

    for i in range(3):
        monitor.record_failure("dead", f"X.{i}", f"error {i}")

        if i < 2:
            assert monitor.status("dead") == STATUS_DEGRADED
            assert monitor.is_available("dead") is True

    assert monitor.status("dead") == STATUS_DOWN
    assert monitor.is_available("dead") is False

    state = monitor.snapshot()["dead"]
    assert state["consecutive_failures"] == 3
    assert state["available"] is False
    assert state["cooldown_remaining_seconds"] > 0

    # Empty results must NOT escalate anything.
    before = monitor.snapshot()["dead"]["total_failures"]
    monitor.record_empty("dead", "X.9")

    state = monitor.snapshot()["dead"]
    assert state["empty_results"] == 1
    assert state["total_failures"] == before
    assert state["status"] == STATUS_DOWN

    print("ok - DOWN after threshold; empty results never trip it")
    return True


def test_half_open_probe_cycle():
    """Cooldown elapsed -> one probe; fail reopens (2x), success closes."""

    print("\n" + "=" * 70)
    print("TEST 4: Half-open probe cycle with backoff")
    print("=" * 70)

    tmp = tempfile.mkdtemp()

    monitor = make_monitor(
        tmp,
        failure_threshold=3,
        cooldown_seconds=1000.0,
        max_cooldown_seconds=10000.0,
    )

    for i in range(3):
        monitor.record_failure("flaky", f"X.{i}", "outage")

    base_cooldown = monitor._state["flaky"]["cooldown_seconds"]
    assert base_cooldown == 1000.0

    assert monitor.is_available("flaky") is False

    # Simulate cooldown elapsing (white-box, deterministic).
    monitor._state["flaky"]["next_probe_ts"] = time.time() - 1

    assert monitor.is_available("flaky") is True
    assert monitor.status("flaky") == STATUS_HALF_OPEN

    # Probe FAILS -> reopen with doubled cooldown.
    monitor.record_failure("flaky", "probe", "still broken")

    state = monitor._state["flaky"]
    assert state["status"] == STATUS_DOWN
    assert state["cooldown_seconds"] == 2000.0
    assert monitor.is_available("flaky") is False

    # Cooldown elapses again -> probe SUCCEEDS -> closes.
    monitor._state["flaky"]["next_probe_ts"] = time.time() - 1

    assert monitor.is_available("flaky") is True

    monitor.record_success("flaky", "probe")

    state = monitor._state["flaky"]
    assert state["status"] == STATUS_HEALTHY
    assert state["consecutive_failures"] == 0
    assert state["cooldown_seconds"] == 1000.0
    assert monitor.is_available("flaky") is True

    print("ok - probe fail doubles cooldown; probe success recovers")
    return True

def test_persistence_roundtrip():
    """DOWN state survives process restart via JSON state file."""

    print("\n" + "=" * 70)
    print("TEST 5: Persistence round-trip")
    print("=" * 70)

    tmp = tempfile.mkdtemp()

    first = make_monitor(tmp, failure_threshold=3)

    for i in range(3):
        first.record_failure("alpha", f"A.{i}", "net down")

    first.record_success("beta", "B.1")

    assert first.is_available("alpha") is False

    # New instance = simulated process restart.
    second = make_monitor(tmp, failure_threshold=3)

    assert second.status("alpha") == STATUS_DOWN
    assert second.is_available("alpha") is False

    state = second.snapshot()["alpha"]
    assert state["total_failures"] == 3
    assert state["last_error"] == "net down"

    assert second.status("beta") == STATUS_HEALTHY
    assert second.is_available("alpha") is False
    assert second.is_available("beta") is True

    print("ok - breaker state restored across instances")
    return True


def test_corrupt_state_file_ignored():
    """Garbage state file must not crash or poison monitoring."""

    print("\n" + "=" * 70)
    print("TEST 6: Corrupt state file handled safely")
    print("=" * 70)

    tmp = tempfile.mkdtemp()

    state_file = Path(tmp) / "health.json"

    state_file.write_text(
        "{ this is not valid json !!",
        encoding="utf-8",
    )

    monitor = make_monitor(tmp)

    assert monitor.snapshot() == {}

    # Monitor stays fully functional afterwards.
    monitor.record_success("fresh", "F.1")

    assert monitor.status("fresh") == STATUS_HEALTHY

    print("ok - corrupt state discarded; monitoring continues")
    return True


def test_report_and_alerts():
    """report()/one_line_summary() render; alerts hit the log."""

    print("\n" + "=" * 70)
    print("TEST 7: Reports and alert log")
    print("=" * 70)

    tmp = tempfile.mkdtemp()

    monitor = make_monitor(tmp, failure_threshold=3)

    for i in range(4):
        monitor.record_failure("ai_index", f"AI.{i}", "stanford unreachable")

    # Degrade then recover -> exercises the RECOVERED alert path.
    monitor.record_failure("worldbank", "W.1", "hiccup")
    monitor.record_success("worldbank", "W.1")

    report = monitor.report()

    assert "PROVIDER HEALTH REPORT" in report
    assert "ai_index" in report
    assert "down" in report
    assert "worldbank" in report
    assert "healthy" in report
    assert "stanford unreachable" in report

    summary = monitor.one_line_summary()
    assert "worldbank=healthy" in summary
    assert "ai_index=DOWN!!" in summary

    alerts_file = Path(tmp) / "alerts.log"

    assert alerts_file.exists(), "alert log should exist"

    alerts = alerts_file.read_text(encoding="utf-8")

    assert "DOWN       [ai_index]" in alerts
    assert "RECOVERED  [worldbank]" in alerts

    snap = monitor.snapshot()
    assert snap["ai_index"]["available"] is False
    assert snap["worldbank"]["available"] is True

    print("ok - table, summary line and alert log all populated")
    return True

# ---------------------------------------------------------------
# INTEGRATION TEST -- SmartStoryEngine wiring
# ---------------------------------------------------------------

def test_smart_story_engine_integration():
    """
    Full wiring check with NO network:

    Run 1: every fetch raises -> failures recorded, breaker
           opens once threshold crossed.
    Run 2: provider skipped BEFORE any fetch (fallback logged,
           failure count unchanged).
    """

    print("\n" + "=" * 70)
    print("TEST 8: SmartStoryEngine integration")
    print("=" * 70)

    tmp = tempfile.TemporaryDirectory()

    monitor = make_monitor(
        tmp.name,
        persist=False,
        failure_threshold=3,
    )

    original_registry = smart_story_module.DataProviderRegistry
    original_health = smart_story_module.provider_health

    smart_story_module.DataProviderRegistry = PatchedRegistry
    smart_story_module.provider_health = monitor

    try:
        # ---------------- RUN 1: outage is recorded -------------
        candidate = SmartStoryEngine.select_best_candidate(
            provider_ids=["fakeprov"],
            max_indicators_per_provider=4,
        )

        assert candidate is None, "no data -> no candidate"

        state = monitor.snapshot().get("fakeprov")

        assert state is not None, "engine must report failures"

        assert state["total_failures"] == 4
        assert state["consecutive_failures"] == 4
        assert state["status"] == STATUS_DOWN
        assert "simulated upstream outage" in state["last_error"]
        assert monitor.is_available("fakeprov") is False

        # ------- RUN 2: open circuit short-circuits fetches -----
        candidate2 = SmartStoryEngine.select_best_candidate(
            provider_ids=["fakeprov"],
            max_indicators_per_provider=4,
        )

        assert candidate2 is None

        state = monitor.snapshot()["fakeprov"]

        # No NEW fetch attempts happened.
        assert state["total_failures"] == 4
        assert state["skipped_by_breaker"] == 1

        # Unknown providers stay available (no false positives).
        assert monitor.is_available("worldbank") is True
        assert monitor.status("worldbank") == STATUS_UNKNOWN

    finally:
        smart_story_module.DataProviderRegistry = original_registry
        smart_story_module.provider_health = original_health

    print("ok - engine records failures; breaker skips next run")
    return True


# ---------------------------------------------------------------
# RUNNER (repo convention: standalone script + exit code)
# ---------------------------------------------------------------

def main():

    print("\n")
    print("*" * 70)
    print("PHASE 6 INTEGRATION TESTS -- PROVIDER HEALTH MONITOR")
    print("*" * 70)

    all_tests = [
        ("UNKNOWN_DEFAULTS", test_unknown_provider_defaults),
        ("DEGRADED_BUT_AVAILABLE", test_degraded_but_available),
        ("CIRCUIT_OPENS", test_circuit_opens_after_threshold),
        ("HALF_OPEN_PROBE", test_half_open_probe_cycle),
        ("PERSISTENCE", test_persistence_roundtrip),
        ("CORRUPT_STATE_SAFE", test_corrupt_state_file_ignored),
        ("REPORTS_AND_ALERTS", test_report_and_alerts),
        ("ENGINE_INTEGRATION", test_smart_story_engine_integration),
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
        print("\n✅ ALL PHASE 6 HEALTH MONITOR TESTS PASSED")
        return True

    print("\n❌ SOME TESTS FAILED")
    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)



