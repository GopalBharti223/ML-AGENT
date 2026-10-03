from datetime import datetime, timedelta
from typing import Dict, Iterable

from app.topic.topic_families import classify_topic_family


class StoryScorer:

    MIN_COUNTRIES = 3
    MIN_YEARS = 3
    MIN_COMPLETENESS = 0.60
    MIN_MOVEMENT_SCORE = 0.01

    @classmethod
    def score(
        cls,
        story_type: str,
        metrics: Dict,
        recent_records: Iterable[Dict] = None,
        min_valid_entities: int = None,
        allow_snapshot_rankings: bool = False
    ) -> Dict:

        quality = cls.quality_score(
            story_type,
            metrics,
            min_valid_entities=min_valid_entities,
            allow_snapshot_rankings=allow_snapshot_rankings
        )

        diversity = cls.diversity_multiplier(
            metrics,
            recent_records or []
        )

        final_score = round(
            quality["quality_score"]
            * diversity["diversity_multiplier"],
            2
        )

        explanation = {}
        explanation.update(quality)
        explanation.update(diversity)
        explanation["final_score"] = final_score

        return explanation

    @classmethod
    def quality_score(
        cls,
        story_type: str,
        metrics: Dict,
        min_valid_entities: int = None,
        allow_snapshot_rankings: bool = False
    ) -> Dict:

        valid_countries = int(
            metrics.get(
                "number_of_valid_countries",
                0
            )
            or 0
        )
        valid_years = int(
            metrics.get(
                "number_of_valid_years",
                0
            )
            or 0
        )
        completeness = float(
            metrics.get(
                "data_completeness",
                0.0
            )
            or 0.0
        )

        # Optional override for entity-comparison datasets: a
        # deliberate 2-entity head-to-head ("Tesla vs BYD") is
        # valid when the caller says so.  Default (None) keeps
        # the historical 3-entity minimum everywhere.
        required_countries = (
            cls.MIN_COUNTRIES
            if min_valid_entities is None
            else max(2, int(min_valid_entities))
        )

        if (
            valid_countries < required_countries
            or valid_years < cls.MIN_YEARS
            or completeness < cls.MIN_COMPLETENESS
        ):
            return {
                "quality_score": 0.0,
                "quality_rejected": True,
                "rejection_reason": "insufficient usable data",
            }

        percent_change = abs(
            metrics.get(
                "percentage_change"
            )
            or 0.0
        )
        absolute_change = abs(
            metrics.get(
                "absolute_change"
            )
            or 0.0
        )
        scale = max(
            abs(
                metrics.get(
                    "start_value"
                )
                or 0.0
            ),
            abs(
                metrics.get(
                    "end_value"
                )
                or 0.0
            ),
            1.0
        )
        absolute_signal = min(
            1.0,
            absolute_change / scale
        )
        percent_signal = min(
            1.0,
            percent_change
        )
        rank_signal = min(
            1.0,
            abs(
                metrics.get(
                    "rank_change"
                )
                or 0.0
            ) / 5.0
        )
        trend_signal = min(
            1.0,
            metrics.get(
                "trend_strength",
                0.0
            )
            or 0.0
        )
        separation = metrics.get(
            "leader_separation",
            1.0
        )

        if story_type == "leader_challenge":
            separation_signal = max(
                0.0,
                1.0 - min(
                    1.0,
                    separation * 4.0
                )
            )
        else:
            separation_signal = min(
                1.0,
                separation * 4.0
            )

        country_signal = min(
            1.0,
            valid_countries / 8.0
        )
        year_signal = min(
            1.0,
            valid_years / 10.0
        )

        # ---------------------------------------------------------
        # Snapshot-dataset ranking stories (current_leader /
        # leader_challenge): the dataset has NO year-over-year
        # movement, so the "movement" gate would always reject.
        # For a snapshot the meaningful signal IS the leader
        # separation (the spread between #1 and #2), which is what
        # the ranking story is actually about.  Time-series story
        # types are never allowed on this path (the engine skips
        # them entirely for snapshot providers), so including
        # separation here cannot leak a fabricated temporal claim.
        # ---------------------------------------------------------
        if (
            allow_snapshot_rankings
            and story_type in ("current_leader", "leader_challenge")
        ):
            movement_signals = (
                percent_signal,
                absolute_signal,
                rank_signal,
                trend_signal,
                separation_signal,
            )
        else:
            movement_signals = (
                percent_signal,
                absolute_signal,
                rank_signal,
                trend_signal,
            )

        if (
            max(movement_signals)
            < cls.MIN_MOVEMENT_SCORE
        ):
            return {
                "quality_score": 0.0,
                "quality_rejected": True,
                "rejection_reason": "no meaningful movement",
            }

        base_score = (
            completeness * 18
            + country_signal * 10
            + year_signal * 10
        )

        if story_type in (
            "fastest_growth",
            "biggest_decline",
        ):
            story_score = (
                percent_signal * 28
                + absolute_signal * 18
                + trend_signal * 10
                + separation_signal * 6
            )
        elif story_type in (
            "rank_climber",
            "rank_decline",
        ):
            story_score = (
                rank_signal * 36
                + percent_signal * 10
                + absolute_signal * 8
                + trend_signal * 8
            )
        elif story_type == "current_leader":
            story_score = (
                separation_signal * 30
                + trend_signal * 18
                + absolute_signal * 8
                + percent_signal * 6
            )
        elif story_type == "leader_challenge":
            story_score = (
                separation_signal * 34
                + trend_signal * 14
                + rank_signal * 8
                + percent_signal * 6
            )
        else:
            story_score = (
                trend_signal * 36
                + percent_signal * 12
                + absolute_signal * 8
                + year_signal * 6
            )

        return {
            "quality_score": round(
                base_score + story_score,
                2
            ),
            "quality_rejected": False,
            "magnitude_signal": round(
                percent_signal,
                4
            ),
            "absolute_signal": round(
                absolute_signal,
                4
            ),
            "rank_signal": round(
                rank_signal,
                4
            ),
            "trend_signal": round(
                trend_signal,
                4
            ),
            "visual_separation_signal": round(
                separation_signal,
                4
            ),
        }

    @classmethod
    def diversity_multiplier(
        cls,
        metrics: Dict,
        recent_records: Iterable[Dict]
    ) -> Dict:

        indicator = str(
            metrics.get(
                "indicator_code",
                ""
            )
        )
        story_type = str(
            metrics.get(
                "story_type",
                ""
            )
        )
        family = str(
            metrics.get(
                "topic_family",
                "general"
            )
        )

        exact_indicator_hits = 0
        exact_story_hits = 0
        family_hits = 0

        cutoff = datetime.now() - timedelta(
            days=90
        )

        for record in recent_records:
            if not isinstance(
                record,
                dict
            ):
                continue

            record_date = cls._parse_date(
                record.get(
                    "date"
                )
            )

            if (
                record_date is not None
                and record_date < cutoff
            ):
                continue

            record_indicator = str(
                record.get(
                    "indicator_code",
                    ""
                )
            )
            record_story = str(
                record.get(
                    "story_type",
                    ""
                )
            )
            record_family = classify_topic_family(
                indicator_code=record.get(
                    "indicator_code",
                    ""
                ),
                indicator_name=record.get(
                    "title",
                    ""
                ),
                category=record.get(
                    "category",
                    ""
                )
            )

            if record_indicator == indicator:
                exact_indicator_hits += 1

                if record_story == story_type:
                    exact_story_hits += 1

            if (
                family
                and family != "general"
                and family == record_family
            ):
                family_hits += 1

        penalty = (
            min(
                0.24,
                exact_indicator_hits * 0.12
            )
            + min(
                0.22,
                exact_story_hits * 0.22
            )
            + min(
                0.18,
                family_hits * 0.06
            )
        )

        multiplier = max(
            0.45,
            1.0 - penalty
        )

        return {
            "diversity_multiplier": round(
                multiplier,
                4
            ),
            "diversity_penalty": round(
                penalty,
                4
            ),
            "recent_indicator_hits": exact_indicator_hits,
            "recent_story_hits": exact_story_hits,
            "recent_family_hits": family_hits,
        }

    @staticmethod
    def _parse_date(value):

        if not value:
            return None

        try:
            return datetime.fromisoformat(
                str(value)
            )
        except ValueError:
            return None
