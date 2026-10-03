"""Performance feedback loop for topic selection.

WHY THIS EXISTS
---------------
`app/youtube/analytics.py` already COLLECTS per-video performance into
the `video_performance` table (views, avg_view_duration_s,
avg_view_percentage), but NOTHING ever read it -- topic selection ran
on a static rule set forever.  This module closes the loop.

It aggregates settled performance (videos older than
settings.PERFORMANCE_MIN_AGE_HOURS) by topic family / indicator and by
the audience-geography entities implied by the title, then exposes a
small bounded multiplier that `SmartStoryEngine` applies before
category rotation.

Design constraints:
  * NO-OP when there is no data (fresh install / analytics not yet
    collected) -- the static audience-relevance rules still decide.
  * Bounded (PERF_MIN_MULT .. PERF_MAX_MULT) so a handful of lucky
    videos cannot hijack the channel.
  * Deterministic: same history in -> same multipliers out.

Collect with:  python -m app.youtube.analytics --collect
"""

import re
from typing import Dict, List, Optional, Tuple

from app.config import settings

from app.topic.audience_relevance import (
    RECOGNIZABLE_ENTITIES,
    _normalize,
)
from app.topic.topic_families import classify_topic_family


# Bounds on the feedback multiplier.
PERF_MIN_MULT = 0.90
PERF_MAX_MULT = 1.15

# Minimum settled videos before the loop is trusted at all.
PERF_MIN_SAMPLES = 3


def _retention_score(row: Dict) -> Optional[float]:
    """0..1 retention proxy for one performance row (None if unusable)."""
    pct = row.get("avg_view_percentage")
    seconds = row.get("avg_view_duration_s")

    try:
        if pct is not None:
            return max(0.0, min(1.0, float(pct) / 100.0))
    except (TypeError, ValueError):
        pass

    try:
        if seconds is not None:
            return max(0.0, min(1.0, float(seconds) / 25.0))
    except (TypeError, ValueError):
        pass

    return None


def _title_entities(title: str) -> List[str]:
    """Recognizable entities mentioned in a published title."""
    text = str(title or "").lower()
    found = []
    for entity in RECOGNIZABLE_ENTITIES:
        if re.search(r"\b" + re.escape(entity) + r"\b", text):
            found.append(_normalize(entity))
    # longest-first so "united states" beats "us"
    found.sort(key=len, reverse=True)
    return list(dict.fromkeys(found))


class PerformanceBias:
    """Aggregated retention signal keyed by family / indicator / entity."""

    def __init__(self):
        self.samples = 0
        self.family_mult: Dict[str, float] = {}
        self.indicator_mult: Dict[str, float] = {}
        self.entity_mult: Dict[str, float] = {}
        self.summary: List[Tuple[str, float, int]] = []

    # -----------------------------------------------------
    # BUILD
    # -----------------------------------------------------

    @classmethod
    def load(
        cls,
        records: Optional[List[Dict]] = None
    ) -> "PerformanceBias":
        """Build the bias from settled performance rows.

        `records` may be passed in (tests); otherwise it is read from
        the database.  Returns an EMPTY bias when disabled or when
        there is not enough data.
        """
        bias = cls()

        if not getattr(settings, "PERFORMANCE_FEEDBACK_ENABLED", True):
            return bias

        if records is None:
            records = cls._read_records()

        usable = []

        for row in records or []:
            if not isinstance(row, dict):
                continue
            score = _retention_score(row)
            if score is None:
                continue
            usable.append((row, score))

        if len(usable) < PERF_MIN_SAMPLES:
            return bias

        bias.samples = len(usable)

        overall = sum(score for _, score in usable) / len(usable)

        family_scores: Dict[str, List[float]] = {}
        indicator_scores: Dict[str, List[float]] = {}
        entity_scores: Dict[str, List[float]] = {}

        for row, score in usable:
            indicator = str(row.get("indicator_code") or "").strip()
            if indicator:
                indicator_scores.setdefault(indicator, []).append(score)

                family = classify_topic_family(indicator)
                if family and family != "general":
                    family_scores.setdefault(family, []).append(score)

            for entity in _title_entities(row.get("title")):
                entity_scores.setdefault(entity, []).append(score)

        bias.family_mult = cls._lift(family_scores, overall)
        bias.indicator_mult = cls._lift(indicator_scores, overall)
        bias.entity_mult = cls._lift(entity_scores, overall)

        bias.summary = sorted(
            (
                (family, mult, len(family_scores[family]))
                for family, mult in bias.family_mult.items()
            ),
            key=lambda item: -item[1],
        )

        return bias

    @staticmethod
    def _lift(
        grouped: Dict[str, List[float]],
        overall: float,
    ) -> Dict[str, float]:
        """Grouped-mean vs overall-mean -> bounded multiplier."""
        result: Dict[str, float] = {}

        if overall <= 0:
            return result

        for key, scores in grouped.items():
            if not scores:
                continue
            mean = sum(scores) / len(scores)
            result[key] = max(
                PERF_MIN_MULT,
                min(PERF_MAX_MULT, mean / overall),
            )

        return result

    @staticmethod
    def _read_records() -> List[Dict]:
        """Read settled performance rows (never raises)."""
        try:
            from app.database import Database

            db = Database()
            return db.get_settled_performance(
                min_age_hours=int(
                    getattr(
                        settings,
                        "PERFORMANCE_MIN_AGE_HOURS",
                        48,
                    )
                )
            )
        except Exception:
            return []

    # -----------------------------------------------------
    # APPLY
    # -----------------------------------------------------

    def multiplier(self, candidate) -> float:
        """Bounded multiplier for one candidate (1.0 when no signal)."""
        if self.samples < PERF_MIN_SAMPLES:
            return 1.0

        parts: List[float] = []

        family = str(
            getattr(candidate, "topic_family", "") or ""
        ).strip().lower()
        if family in self.family_mult:
            parts.append(self.family_mult[family])

        indicator = str(
            getattr(candidate, "indicator_code", "") or ""
        ).strip()
        if indicator in self.indicator_mult:
            parts.append(self.indicator_mult[indicator])

        metrics = getattr(candidate, "metrics", None) or {}
        for key in ("entity", "leader", "challenger"):
            entity = _normalize(str(metrics.get(key) or ""))
            if entity in self.entity_mult:
                parts.append(self.entity_mult[entity])

        if not parts:
            return 1.0

        # Damped combination so stacked signals cannot run away.
        combined = 1.0
        for part in parts:
            combined *= part

        return max(
            PERF_MIN_MULT,
            min(PERF_MAX_MULT, combined ** (1.0 / len(parts))),
        )

    def describe(self) -> str:
        """One-line human summary for run logs."""
        if self.samples < PERF_MIN_SAMPLES:
            return (
                "[PERF] No settled performance signal yet "
                f"({self.samples} samples) -- static rules only."
            )

        top = ", ".join(
            f"{name}={mult:.2f} (n={count})"
            for name, mult, count in self.summary[:5]
        )
        return (
            f"[PERF] Feedback active from {self.samples} settled "
            f"videos. Top families: {top}"
        )


__all__ = [
    "PerformanceBias",
    "PERF_MIN_MULT",
    "PERF_MAX_MULT",
    "PERF_MIN_SAMPLES",
    "_retention_score",
    "_title_entities",
]