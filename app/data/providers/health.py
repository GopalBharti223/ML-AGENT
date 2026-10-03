# =========================================================
# PROVIDER HEALTH MONITOR — Phase 6 (Monitoring & Reporting)
# =========================================================
#
# Runtime availability tracking + circuit breaker for every
# DataProvider registered in DataProviderRegistry, so one dead
# upstream API cannot silently burn fetch attempts on every
# pipeline run.
#
# Requirements mapped from PHASE_4A_COMPLETION.md "Next Steps":
#
#   1. Add provider health checks
#        -> record_success / record_failure
#   2. Monitor data source availability
#        -> status() / is_available() / report()
#   3. Alert if source becomes unavailable
#        -> ALERT lines on console AND appended to
#           logs/provider_health.log
#   4. Log provider fallback behavior
#        -> record_skipped() counters persisted with state
#
# FAILURE MODEL
# -------------
# - A fetch that RAISES counts as a failure.  Providers are
#   built to return clean-but-empty results instead of fake
#   data, so an exception means a genuine outage (network down,
#   HTTP 5xx, rate limiting, auth failure...).
# - A clean-but-empty result is tracked separately as an
#   "empty" event.  Missing data is NOT an outage and never
#   trips the breaker.
# - Consecutive failures escalate:
#       UNKNOWN -> DEGRADED (>= degraded_after)
#               -> DOWN     (>= failure_threshold)
#   While DOWN, is_available() returns False and the engine
#   skips the provider until the cooldown elapses.  ONE
#   half-open probe is then allowed; if it fails, the breaker
#   re-opens with a DOUBLED cooldown (exponential backoff,
#   capped at max_cooldown_seconds).  Any success restores
#   HEALTHY and resets the backoff.
#
# PERSISTENCE
# -----------
# State is mirrored to JSON (default: data/provider_health.json)
# so breaker decisions survive process restarts between
# scheduled runs.  A missing or corrupt file is ignored --
# monitoring must NEVER take the pipeline down.
#
# Thread safety: a single lock guards all mutations.  The
# pipeline is effectively single-threaded, but overlapping
# scheduled tasks must not corrupt shared state.
# =========================================================

import json
import os
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional


# ---------------------------------------------------------
# STATUS CONSTANTS
# ---------------------------------------------------------

STATUS_HEALTHY = "healthy"

STATUS_DEGRADED = "degraded"

STATUS_DOWN = "down"

STATUS_HALF_OPEN = "half_open"

STATUS_UNKNOWN = "unknown"


def _project_root() -> Path:
    """
    Repository root, derived from this file's location:

        <root>/app/data/providers/health.py
    """

    return Path(__file__).resolve().parents[3]


class ProviderHealthMonitor:

    DEFAULT_STATE_PATH = str(
        _project_root() / "data" / "provider_health.json"
    )

    DEFAULT_ALERTS_PATH = str(
        _project_root() / "logs" / "provider_health.log"
    )

    def __init__(
        self,
        state_path: Optional[str] = None,
        alerts_path: Optional[str] = None,
        degraded_after: int = 1,
        failure_threshold: int = 3,
        cooldown_seconds: float = 300.0,
        max_cooldown_seconds: float = 3600.0,
        persist: bool = True,
        clock: Callable[[], float] = time.time,
    ):

        self.state_path = (
            state_path
            or os.getenv(
                "PROVIDER_HEALTH_STATE_PATH",
                self.DEFAULT_STATE_PATH,
            )
        )

        self.alerts_path = (
            alerts_path
            or os.getenv(
                "PROVIDER_HEALTH_ALERTS_PATH",
                self.DEFAULT_ALERTS_PATH,
            )
        )

        self.degraded_after = max(1, int(degraded_after))

        # DOWN threshold must be strictly beyond DEGRADED.
        self.failure_threshold = max(
            self.degraded_after + 1,
            int(failure_threshold),
        )

        self.cooldown_seconds = float(cooldown_seconds)

        self.max_cooldown_seconds = float(max_cooldown_seconds)

        self.persist = bool(persist)

        # Injectable clock keeps half-open/backoff tests
        # deterministic without sleeping.
        self.clock = clock

        self._lock = threading.Lock()

        # provider_id -> entry dict (see _new_entry)
        self._state: Dict[str, Dict] = {}

        if self.persist and self.state_path:

            self._load_state()

    # -----------------------------------------------------
    # INTERNALS
    # -----------------------------------------------------

    def _new_entry(self) -> Dict:
        """Fresh per-provider tracking record."""

        return {
            "status": STATUS_UNKNOWN,
            "consecutive_failures": 0,
            "total_successes": 0,
            "total_failures": 0,
            "empty_results": 0,
            "skipped_by_breaker": 0,
            "last_error": "",
            "last_error_indicator": "",
            "last_success_indicator": "",
            "last_success_ts": None,
            "last_failure_ts": None,
            "cooldown_seconds": self.cooldown_seconds,
            "next_probe_ts": 0.0,
            "half_open": False,
        }

    def _entry(self, provider_id: str) -> Dict:
        """Get-or-create a provider entry. Lock must be held."""

        entry = self._state.get(provider_id)

        if entry is None:

            entry = self._new_entry()

            self._state[provider_id] = entry

        return entry


    # -----------------------------------------------------
    # PUBLIC API -- RECORDING OUTCOMES
    # -----------------------------------------------------

    def record_success(
        self,
        provider_id: str,
        indicator_code: str = ""
    ) -> None:
        """
        Record a successful fetch.

        Restores HEALTHY from ANY state (including a half-open
        probe) and resets consecutive-failure / backoff counters.
        A recovery alert fires when the provider was not healthy.
        """

        with self._lock:

            entry = self._entry(provider_id)

            was_status = entry["status"]

            entry["consecutive_failures"] = 0

            entry["total_successes"] += 1

            entry["last_success_ts"] = self.clock()

            if indicator_code:
                entry["last_success_indicator"] = str(indicator_code)

            entry["half_open"] = False

            entry["next_probe_ts"] = 0.0

            entry["cooldown_seconds"] = self.cooldown_seconds

            entry["status"] = STATUS_HEALTHY

            if was_status in (
                STATUS_DEGRADED,
                STATUS_DOWN,
                STATUS_HALF_OPEN,
            ):

                self._alert(
                    f"RECOVERED  [{provider_id}] source back to "
                    f"HEALTHY (was {was_status.upper()})"
                )

            self._save_state_locked()

    def record_failure(
        self,
        provider_id: str,
        indicator_code: str = "",
        error: str = ""
    ) -> None:
        """
        Record a failed fetch (an exception escaping the provider).

        Escalation:
          below failure_threshold -> DEGRADED (provider still
          attempted on future runs)
          at/above threshold      -> DOWN, breaker opens, probe
          allowed only after cooldown.  A failed half-open probe
          re-opens with DOUBLED cooldown (capped).
        """

        with self._lock:

            entry = self._entry(provider_id)

            was_status = entry["status"]

            now = self.clock()

            entry["consecutive_failures"] += 1

            entry["total_failures"] += 1

            entry["last_failure_ts"] = now

            entry["last_error"] = str(error or "")[:500]

            entry["last_error_indicator"] = str(indicator_code or "")

            # Still under threshold: degrade but keep trying.
            if entry["consecutive_failures"] < self.failure_threshold:

                entry["status"] = STATUS_DEGRADED

                if was_status == STATUS_UNKNOWN:

                    self._alert(
                        f"DEGRADED   [{provider_id}] "
                        f"{entry['consecutive_failures']} consecutive "
                        f"failure(s): {entry['last_error'][:120]}"
                    )

                self._save_state_locked()

                return

            alert_message = ""

            if (
                was_status == STATUS_HALF_OPEN
                or entry["half_open"]
            ):

                entry["cooldown_seconds"] = min(
                    entry["cooldown_seconds"] * 2,
                    self.max_cooldown_seconds,
                )

                alert_message = (
                    f"STILL DOWN [{provider_id}] half-open probe "
                    f"FAILED; breaker re-opened for "
                    f"{entry['cooldown_seconds']:.0f}s | "
                    f"{entry['last_error'][:150]}"
                )

            elif was_status != STATUS_DOWN:

                entry["cooldown_seconds"] = self.cooldown_seconds

                alert_message = (
                    f"DOWN       [{provider_id}] circuit OPENED after "
                    f"{entry['consecutive_failures']} consecutive "
                    f"failures; retry in "
                    f"{entry['cooldown_seconds']:.0f}s | "
                    f"{entry['last_error'][:150]}"
                )

            entry["status"] = STATUS_DOWN

            entry["half_open"] = False

            entry["next_probe_ts"] = (
                now + entry["cooldown_seconds"]
            )

            if alert_message:

                self._alert(alert_message)

            self._save_state_locked()

    def record_empty(
        self,
        provider_id: str,
        indicator_code: str = ""
    ) -> None:
        """
        Record a clean-but-empty result.

        Providers return empty data when an indicator simply has
        no rows.  That is NOT an outage, so it never escalates
        status -- it is only counted for visibility.
        """

        with self._lock:

            entry = self._entry(provider_id)

            entry["empty_results"] += 1

            self._save_state_locked()

    def record_skipped(self, provider_id: str) -> None:
        """
        Log that the engine skipped this provider because its
        circuit was open.  This is the fallback-behavior audit
        trail required by Phase 6.
        """

        with self._lock:

            entry = self._entry(provider_id)

            entry["skipped_by_breaker"] += 1

            self._alert(
                f"FALLBACK   [{provider_id}] SKIPPED by open circuit "
                f"(skip #{entry['skipped_by_breaker']}); engine "
                f"continues with other providers"
            )

            self._save_state_locked()

    # -----------------------------------------------------
    # PUBLIC API -- AVAILABILITY (CIRCUIT BREAKER)
    # -----------------------------------------------------

    def is_available(self, provider_id: str) -> bool:
        """
        Circuit-breaker gate.

        True  -> safe to attempt a fetch.
        False -> provider is DOWN and cooling off; caller should
                 skip it and let other providers win.

        When a DOWN provider's cooldown has elapsed, exactly one
        HALF_OPEN probe is permitted (this call flips the state).
        The probe's success/failure decides whether the breaker
        closes again or re-opens with doubled backoff.
        """

        with self._lock:

            entry = self._state.get(provider_id)

            if entry is None:

                return True

            if entry["status"] != STATUS_DOWN:

                return True

            now = self.clock()

            if now >= entry["next_probe_ts"]:

                entry["status"] = STATUS_HALF_OPEN

                entry["half_open"] = True

                self._alert(
                    f"PROBE      [{provider_id}] cooldown elapsed -- "
                    f"allowing one half-open probe"
                )

                self._save_state_locked()

                return True

            return False

    # -----------------------------------------------------
    # PUBLIC API -- INSPECTION & REPORTING
    # -----------------------------------------------------

    def status(self, provider_id: str) -> str:
        """Current status string for one provider."""

        with self._lock:

            entry = self._state.get(provider_id)

            if entry is None:

                return STATUS_UNKNOWN

            return entry["status"]

    def snapshot(self) -> Dict[str, Dict]:
        """
        JSON-safe deep copy of all tracked state, plus computed
        convenience fields ('available', cooldown remaining).
        """

        with self._lock:

            now = self.clock()

            snapshot: Dict[str, Dict] = {}

            for pid, entry in self._state.items():

                item = dict(entry)

                item["available"] = (
                    item["status"] != STATUS_DOWN
                )

                if item["status"] == STATUS_DOWN:

                    remaining = max(
                        0.0,
                        entry["next_probe_ts"] - now,
                    )

                    item["cooldown_remaining_seconds"] = round(
                        remaining,
                        1,
                    )

                snapshot[pid] = item

            return snapshot

    def report(self) -> str:
        """Human-readable multi-line health table for operators."""

        with self._lock:

            stamp = time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(),
            )

            lines = [
                "=" * 78,
                f"PROVIDER HEALTH REPORT -- {stamp}",
                "=" * 78,
                f"{'provider':<14} {'status':<10} "
                f"{'ok':>4} {'fail':>5} {'consec':>6} "
                f"{'empty':>5} {'skips':>5}  last_error",
                "-" * 78,
            ]

            for pid in sorted(self._state):

                entry = self._state[pid]

                last_error = str(
                    entry.get("last_error", "")
                ).replace("\n", " ")

                if len(last_error) > 44:
                    last_error = last_error[:41] + "..."

                lines.append(
                    f"{pid:<14} {entry['status']:<10} "
                    f"{entry['total_successes']:>4} "
                    f"{entry['total_failures']:>5} "
                    f"{entry['consecutive_failures']:>6} "
                    f"{entry['empty_results']:>5} "
                    f"{entry['skipped_by_breaker']:>5}  "
                    f"{last_error}"
                )

            if not self._state:

                lines.append(
                    "(no provider activity recorded yet)"
                )

            down_count = sum(
                1
                for e in self._state.values()
                if e["status"] == STATUS_DOWN
            )

            lines.append("-" * 78)

            lines.append(
                f"{len(self._state)} tracked | {down_count} DOWN | "
                f"state: {self.state_path}"
            )

            lines.append("=" * 78)

            return "\n".join(lines)

    def one_line_summary(self) -> str:
        """Compact per-run footer, e.g. 'wb=healthy | ai=down'."""

        with self._lock:

            parts = []

            for pid in sorted(self._state):

                entry = self._state[pid]

                label = entry["status"]

                if label == STATUS_DOWN:
                    label = "DOWN!!"

                parts.append(f"{pid}={label}")

            if not parts:

                return (
                    "no provider activity recorded yet"
                )

            return " | ".join(parts)

    # -----------------------------------------------------
    # PUBLIC API -- OPERATIONS / TESTS
    # -----------------------------------------------------

    def reset_provider(self, provider_id: str) -> None:
        """Forget all history for one provider."""

        with self._lock:

            self._state.pop(provider_id, None)

            self._save_state_locked()

    def reset_all(self) -> None:
        """Forget all tracked state (fresh monitoring)."""

        with self._lock:

            self._state.clear()

            self._save_state_locked()

    # -----------------------------------------------------
    # INTERNALS -- ALERTING & PERSISTENCE
    # -----------------------------------------------------

    def _alert(self, message: str) -> None:
        """
        Emit an operations alert: console + alert log file.

        Called with self._lock held.  All IO errors are
        swallowed -- alerting must never crash the pipeline.
        """

        stamp = time.strftime("%Y-%m-%d %H:%M:%S")

        line = f"[{stamp}] {message}"

        try:

            print(f"[ALERT] {line}")

        except Exception:

            pass

        if not self.alerts_path:

            return

        try:

            log_file = Path(self.alerts_path)

            log_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with log_file.open(
                "a",
                encoding="utf-8"
            ) as handle:

                handle.write(line + "\n")

        except OSError:

            pass

    def _save_state_locked(self) -> None:
        """
        Mirror state to JSON atomically (tmp file + replace).
        Lock must be held.  Failures are ignored on purpose.
        """

        if not self.persist or not self.state_path:

            return

        payload = {
            "version": 1,
            "saved_at": time.strftime(
                "%Y-%m-%dT%H:%M:%S",
                time.localtime(),
            ),
            "providers": self._state,
        }

        try:

            target = Path(self.state_path)

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            tmp = target.with_suffix(
                target.suffix + ".tmp"
            )

            with tmp.open(
                "w",
                encoding="utf-8"
            ) as handle:

                json.dump(
                    payload,
                    handle,
                    indent=2,
                    default=str,
                )

            os.replace(tmp, target)

        except (OSError, TypeError, ValueError):

            pass

    def _load_state(self) -> None:
        """
        Restore state from disk at startup.

        A missing file is normal (first run).  A CORRUPT file is
        discarded silently -- monitoring starts fresh rather than
        blocking the pipeline.
        """

        if not self.state_path:

            return

        try:

            target = Path(self.state_path)

            if not target.exists():

                return

            with target.open(
                "r",
                encoding="utf-8"
            ) as handle:

                payload = json.load(handle)

            providers = payload.get("providers")

            if not isinstance(providers, dict):

                return

            merged: Dict[str, Dict] = {}

            for pid, raw in providers.items():

                if not isinstance(raw, dict):

                    continue

                entry = self._new_entry()

                entry.update(
                    {
                        key: raw[key]
                        for key in entry
                        if key in raw
                    }
                )

                merged[str(pid)] = entry

            self._state = merged

        except (OSError, ValueError):

            # OSError: unreadable file
            # ValueError: malformed JSON
            self._state = {}


# ---------------------------------------------------------
# MODULE-LEVEL SINGLETON
#
# Shared by SmartStoryEngine (and any future callers):
#
#     from app.data.providers.health import provider_health
#
# Tests construct isolated instances instead of touching this.
# ---------------------------------------------------------

provider_health = ProviderHealthMonitor()





