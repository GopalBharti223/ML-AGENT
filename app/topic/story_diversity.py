"""
Story Diversity Scorer for SmartStoryEngine

Provides a soft diversity adjustment to the candidate selection process,
preferring different story types, topic families, and providers when
high-quality alternatives are available.

This is NOT a hard block - quality always wins. The diversity scorer
provides a multiplier that slightly prefers diverse candidates
when they are close in quality to repeated ones.

The purpose is:
  High-quality stories + meaningful diversity + deterministic selection

NOT:
  Maximum diversity at the expense of quality
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from app.topic.topic_families import classify_topic_family


class StoryDiversityScorer:
    """
    Lightweight diversity scorer that provides soft adjustments
    to candidate selection without hard-blocking.

    Dimensions:
    1. Story type recency
    2. Topic family recency
    3. Provider recency
    4. Indicator recency
    """

    # Diversity penalty strength (0.0 = no penalty, 1.0 = strong penalty)
    # Values close to 0 mean minimal adjustment; close to 1 mean strong preference
    STORY_TYPE_PENALTY = 0.05   # 5% penalty for recently used story type
    FAMILY_PENALTY = 0.03       # 3% penalty for recently used family
    PROVIDER_PENALTY = 0.02     # 2% penalty for recently used provider
    INDICATOR_PENALTY = 0.01    # 1% penalty for recently used indicator

    # Window for "recent" (same as anti-repeat 90-day combination window)
    RECENCY_WINDOW_DAYS = 90

    def __init__(self, recent_records: List[Dict] = None):
        self.recent_records = recent_records or []
        self._penalty_cache: Dict[str, float] = {}

    def score_candidate(
        self,
        candidate: "StoryCandidate",
        all_candidates: List["StoryCandidate"] = None
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate diversity adjustment for a candidate.

        Returns:
            (adjusted_score, breakdown) where breakdown contains
            per-dimension penalty factors.
        """
        breakdown = {
            "story_type_penalty": 1.0,
            "family_penalty": 1.0,
            "provider_penalty": 1.0,
            "indicator_penalty": 1.0,
            "diversity_score": 1.0,
        }

        if not self.recent_records:
            return candidate.score, breakdown

        # 1. Story type recency penalty
        story_type_penalty = self._calculate_story_type_penalty(
            candidate.story_type
        )
        breakdown["story_type_penalty"] = story_type_penalty

        # 2. Topic family recency penalty
        family_penalty = self._calculate_family_penalty(candidate.topic_family)
        breakdown["family_penalty"] = family_penalty

        # 3. Provider recency penalty
        provider_penalty = self._calculate_provider_penalty(candidate.provider_id)
        breakdown["provider_penalty"] = provider_penalty

        # 4. Indicator recency penalty
        indicator_penalty = self._calculate_indicator_penalty(
            candidate.indicator_code
        )
        breakdown["indicator_penalty"] = indicator_penalty

        # Combined diversity score (product of all penalties, closer to 1 = less penalty)
        combined_penalty = (
            story_type_penalty
            * family_penalty
            * provider_penalty
            * indicator_penalty
        )
        breakdown["diversity_score"] = combined_penalty

        # Apply adjustment: quality_score * diversity_multiplier
        # The candidate's score already includes quality + diversity from StoryScorer
        # This is an additional adjustment on top
        adjusted_score = candidate.score * combined_penalty

        return adjusted_score, breakdown

    def _calculate_story_type_penalty(self, story_type: str) -> float:
        """Penalty for recently used story type (0.95 = 5% penalty)."""
        penalty = 1.0
        for record in self.recent_records:
            if not isinstance(record, dict):
                continue
            record_story = str(record.get("story_type", ""))
            if record_story == story_type:
                # Check if within recency window
                record_date = self._parse_date(record.get("date"))
                if record_date:
                    days_ago = (datetime.now() - record_date).days
                    if days_ago <= self.RECENCY_WINDOW_DAYS:
                        penalty = 1.0 - self.STORY_TYPE_PENALTY
                        penalty = max(penalty, 0.5)  # Minimum 50% of original
                        penalty = min(penalty, 1.0)  # Maximum 100%
                        penalty = min(penalty, penalty)  # Keep the strongest (lowest) penalty
                        penalty = min(penalty, 1.0 - self.STORY_TYPE_PENALTY)
                        penalty = max(penalty, 1.0 - self.STORY_TYPE_PENALTY)
                else:
                    # No date available, apply mild penalty
                    penalty = 1.0 - self.STORY_TYPE_PENALTY
                    penalty = max(penalty, 0.5)
                    penalty = min(penalty, 1.0)
                penalty = min(penalty, 1.0 - self.STORY_TYPE_PENALTY)
                penalty = max(penalty, 1.0 - self.STORY_TYPE_PENALTY)
                penalty = min(penalty, 1.0)
                penalty = max(penalty, 1.0 - self.STORY_TYPE_PENALTY)
                break  # Use first match (strongest penalty)
        return penalty

    def _calculate_family_penalty(self, topic_family: str) -> float:
        """Penalty for recently used topic family."""
        penalty = 1.0
        for record in self.recent_records:
            if not isinstance(record, dict):
                continue
            record_family = str(record.get("topic_family", ""))
            if record_family == topic_family and record_family != "general":
                record_date = self._parse_date(record.get("date"))
                if record_date:
                    days_ago = (datetime.now() - record_date).days
                    if days_ago <= self.RECENCY_WINDOW_DAYS:
                        penalty = 1.0 - self.FAMILY_PENALTY
                        penalty = max(penalty, 0.5)
                        penalty = min(penalty, 1.0)
                        penalty = min(penalty, 1.0 - self.FAMILY_PENALTY)
                        penalty = max(penalty, 1.0 - self.FAMILY_PENALTY)
                        break
                else:
                    penalty = 1.0 - self.FAMILY_PENALTY
                    penalty = max(penalty, 0.5)
                    penalty = min(penalty, 1.0)
                    penalty = min(penalty, 1.0 - self.FAMILY_PENALTY)
                    break
        return penalty

    def _calculate_provider_penalty(self, provider_id: str) -> float:
        """Penalty for recently used provider."""
        penalty = 1.0
        for record in self.recent_records:
            if not isinstance(record, dict):
                continue
            record_provider = str(record.get("provider_id", ""))
            if record_provider == provider_id:
                record_date = self._parse_date(record.get("date"))
                if record_date:
                    days_ago = (datetime.now() - record_date).days
                    if days_ago <= self.RECENCY_WINDOW_DAYS:
                        penalty = 1.0 - self.PROVIDER_PENALTY
                        penalty = max(penalty, 0.5)
                        penalty = min(penalty, 1.0)
                        penalty = min(penalty, 1.0 - self.PROVIDER_PENALTY)
                        penalty = max(penalty, 1.0 - self.PROVIDER_PENALTY)
                        break
                else:
                    penalty = 1.0 - self.PROVIDER_PENALTY
                    penalty = max(penalty, 0.5)
                    penalty = min(penalty, 1.0)
                    penalty = min(penalty, 1.0 - self.PROVIDER_PENALTY)
                    break
        return penalty

    def _calculate_indicator_penalty(self, indicator_code: str) -> float:
        """Penalty for recently used indicator code."""
        penalty = 1.0
        for record in self.recent_records:
            if not isinstance(record, dict):
                continue
            record_indicator = str(record.get("indicator_code", ""))
            if record_indicator == indicator_code:
                record_date = self._parse_date(record.get("date"))
                if record_date:
                    days_ago = (datetime.now() - record_date).days
                    if days_ago <= self.RECENCY_WINDOW_DAYS:
                        penalty = 1.0 - self.INDICATOR_PENALTY
                        penalty = max(penalty, 0.5)
                        penalty = min(penalty, 1.0)
                        penalty = min(penalty, 1.0 - self.INDICATOR_PENALTY)
                        penalty = max(penalty, 1.0 - self.INDICATOR_PENALTY)
                        break
                else:
                    penalty = 1.0 - self.INDICATOR_PENALTY
                    penalty = max(penalty, 0.5)
                    penalty = min(penalty, 1.0)
                    penalty = min(penalty, 1.0 - self.INDICATOR_PENALTY)
                    break
        return penalty

    @staticmethod
    def _parse_date(value) -> Optional[datetime]:
        """Parse a date string from record."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None

    @classmethod
    def apply_diversity_adjustment(
        cls,
        candidates: List["StoryCandidate"],
        recent_records: List[Dict] = None
    ) -> List["StoryCandidate"]:
        """
        Apply diversity scoring to a candidate pool and return
        candidates with adjusted scores.

        This is called after anti-repeat validation and before
        final deduplication/ranking.
        """
        scorer = cls(recent_records=recent_records)

        scored = []
        for candidate in candidates:
            adjusted_score, breakdown = scorer.score_candidate(candidate)
            # Store the adjusted score on the candidate
            candidate.diversity_adjustment = breakdown
            scored.append((adjusted_score, candidate))

        # Sort by adjusted score (descending)
        scored.sort(key=lambda x: x[0], reverse=True)

        # Return candidates in adjusted score order
        return [candidate for _, candidate in scored]