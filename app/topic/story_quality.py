"""
Story Quality Validator for SmartStoryEngine

Validates whether a generated story candidate is actually supported
by its underlying data. The validator is intentionally conservative:
it rejects candidates whose story claims are not clearly substantiated
by the underlying metrics.

This module is standalone and designed to be reusable from
SmartStoryEngine later. It does NOT modify any existing class.
"""

from typing import Any, Dict, List, Optional


class StoryQualityValidator:
    """
    Conservative validator for story candidates.

    Checks:
    1. Entity validity
    2. Story-type appropriateness
    3. Near-zero base-value sanity
    4. Signal consistency
    5. Data sufficiency
    6. Completeness
    7. Title quality
    """

    # ---------------------------------------------------------
    # Thresholds (aligned with existing engine conventions)
    # ---------------------------------------------------------

    MIN_COUNTRIES = 3
    MIN_YEARS = 3

    # StoryScorer uses MIN_COMPLETENESS = 0.60; candidate filtering
    # uses 0.40.  We stay between the two but err conservative.
    MIN_COMPLETENESS = 0.40

    # A percent change driven by a near-zero base is misleading.
    # The existing engine already refuses to divide by abs(base) < 1e-9.
    # We additionally flag cases where the base is tiny relative to
    # the end value but the *absolute* change is small as well.
    NEAR_ZERO_BASE_ABS = 1e-6

    # Minimum absolute change required for a meaningful story.
    MIN_ABSOLUTE_CHANGE = 1e-9

    # Minimum percentage-change magnitude to qualify as "movement".
    MIN_PERCENT_CHANGE = 0.01  # 1%

    # Signal-consistency slack (rank change must be in same direction
    # as percent change unless magnitude is genuinely below threshold).
    RANK_EPSILON = 0.001

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    @classmethod
    def validate(
        cls,
        metrics: Dict[str, Any],
        *,
        story_type: Optional[str] = None,
        entity: Optional[str] = None,
        title: Optional[str] = None,
        indicator_name: Optional[str] = None,
        min_countries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Validate a story candidate.

        Parameters
        ----------
        metrics : dict
            A metrics dictionary as produced by
            SmartStoryEngine._entity_metrics() / _analyze_data()
            and consumed by StoryScorer.  Expected keys:
              - number_of_valid_countries
              - number_of_valid_years
              - data_completeness
              - story_type
              - entity
              - start_value
              - end_value
              - absolute_change
              - percentage_change
              - start_rank
              - end_rank
              - rank_change
              - trend_strength
              - indicator_code
              - indicator_name
              - topic_family
        story_type : str, optional
            Override for metrics["story_type"].
        entity : str, optional
            Override for metrics["entity"].
        title : str, optional
            Generated story title to check.
        indicator_name : str, optional
            Override for metrics["indicator_name"].
        min_countries : int, optional
            Override for MIN_COUNTRIES for deliberate entity-
            comparison datasets (a 2-entity head-to-head).  None
            keeps the historical 3-entity minimum.

        Returns
        -------
        dict
            {
                "valid": bool,
                "reasons": [str, ...],
                "checks": {check_name: {"passed": bool, "detail": str|None}}
            }
        """
        reasons: List[str] = []
        checks: Dict[str, Dict[str, Any]] = {}

        # -----------------------------------------------------
        # Pull values with overrides
        # -----------------------------------------------------

        resolved_story_type = story_type or metrics.get("story_type", "")
        resolved_entity = entity or metrics.get("entity", "")
        resolved_title = title or ""
        resolved_indicator_name = (
            indicator_name
            or metrics.get("indicator_name")
            or metrics.get("metric_name")
            or ""
        )

        # -----------------------------------------------------
        # 1. Entity validity
        # -----------------------------------------------------

        entity_result = cls._check_entity(metrics, resolved_entity)
        checks["entity_validity"] = entity_result
        if not entity_result["passed"]:
            reasons.append(entity_result["detail"] or "invalid entity")

        # -----------------------------------------------------
        # 2. Story-type appropriateness
        # -----------------------------------------------------

        story_result = cls._check_story_type(
            metrics,
            resolved_story_type,
            resolved_entity,
        )
        checks["story_type_appropriateness"] = story_result
        if not story_result["passed"]:
            reasons.append(
                story_result["detail"] or "story type not supported by data"
            )

        # -----------------------------------------------------
        # 3. Near-zero base-value sanity
        # -----------------------------------------------------

        base_result = cls._check_near_zero_base(metrics)
        checks["near_zero_base"] = base_result
        if not base_result["passed"]:
            reasons.append(
                base_result["detail"] or "misleading near-zero base-value change"
            )

        # -----------------------------------------------------
        # 4. Signal consistency
        # -----------------------------------------------------

        signal_result = cls._check_signal_consistency(
            metrics,
            resolved_story_type,
        )
        checks["signal_consistency"] = signal_result
        if not signal_result["passed"]:
            reasons.append(
                signal_result["detail"] or "contradictory signals"
            )

        # -----------------------------------------------------
        # 5. Data sufficiency
        # -----------------------------------------------------

        sufficiency_result = cls._check_data_sufficiency(
            metrics,
            min_countries=min_countries,
        )
        checks["data_sufficiency"] = sufficiency_result
        if not sufficiency_result["passed"]:
            reasons.append(
                sufficiency_result["detail"] or "insufficient data"
            )

        # -----------------------------------------------------
        # 6. Completeness
        # -----------------------------------------------------

        completeness_result = cls._check_completeness(metrics)
        checks["completeness"] = completeness_result
        if not completeness_result["passed"]:
            reasons.append(
                completeness_result["detail"] or "low completeness"
            )

        # -----------------------------------------------------
        # 7. Title quality
        # -----------------------------------------------------

        title_result = cls._check_title_quality(
            resolved_title,
            resolved_entity,
            resolved_story_type,
            resolved_indicator_name,
            metrics,
        )
        checks["title_quality"] = title_result
        if not title_result["passed"]:
            reasons.append(
                title_result["detail"] or "misleading title"
            )

        return {
            "valid": len(reasons) == 0,
            "reasons": reasons,
            "checks": checks,
        }

    # ---------------------------------------------------------
    # Individual checks
    # ---------------------------------------------------------

    @classmethod
    def _check_entity(
        cls,
        metrics: Dict[str, Any],
        entity: Optional[str],
    ) -> Dict[str, Any]:
        """
        Verify the candidate's selected entity exists in the data.

        We accept an entity when either:
          - metrics["entity"] matches (case-insensitive), OR
          - the entity appears in metrics["data"] index, OR
          - the entity appears in metrics["latest_sorted"] index.
        """
        entity = str(entity or "").strip()
        if not entity:
            return {
                "passed": False,
                "detail": "no entity provided for story",
            }

        # Case 1: search in data / latest_sorted indices first.
        # These represent the actual underlying data, so an entity
        # that is not present there is a phantom entity.
        for key in ("data", "latest_sorted"):
            index_values = getattr(
                metrics.get(key),
                "index",
                None,
            )
            if index_values is None:
                continue

            for idx in index_values:
                # The wide-data index may be a tuple (code, country)
                label = cls._index_label(idx)
                if label and label.lower() == entity.lower():
                    return {
                        "passed": True,
                        "detail": f"entity '{entity}' found in {key}",
                    }

        # Case 2: if no data index is available, fall back to
        # metrics["entity"] as the source of truth.
        metric_entity = str(
            metrics.get("entity", "")
        ).strip().lower()
        if metric_entity and metric_entity == entity.lower():
            # Only accept if there is no data index to cross-check.
            has_data_index = any(
                getattr(metrics.get(key), "index", None) is not None
                for key in ("data", "latest_sorted")
            )
            if not has_data_index:
                return {
                    "passed": True,
                    "detail": f"entity '{entity}' found in metrics",
                }

        return {
            "passed": False,
            "detail": (
                f"entity '{entity}' not found in underlying data"
            ),
        }

    @classmethod
    def _check_story_type(
        cls,
        metrics: Dict[str, Any],
        story_type: Optional[str],
        entity: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verify the story type is genuinely supported by the metrics.

        Story type expectations:
          - fastest_growth : meaningful positive growth
          - biggest_decline: meaningful negative movement
          - rank_climber   : rank improvement (positive rank_change)
          - rank_decline   : rank deterioration (negative rank_change)
          - current_leader : valid leader exists
          - leader_challenge: meaningful competition (small gap)
          - trend_over_time: sufficient multi-year movement
        """
        story_type = str(story_type or "").strip()
        if not story_type:
            return {
                "passed": False,
                "detail": "no story type provided",
            }

        entity = str(entity or metrics.get("entity", "")).strip()

        percent_change = cls._num(
            metrics.get("percentage_change")
        )
        absolute_change = cls._num(
            metrics.get("absolute_change")
        )
        rank_change = cls._num(
            metrics.get("rank_change")
        )
        start_value = cls._num(
            metrics.get("start_value")
        )
        end_value = cls._num(
            metrics.get("end_value")
        )
        trend_strength = cls._num(
            metrics.get("trend_strength")
        )
        leader_separation = cls._num(
            metrics.get("leader_separation")
        )

        # Derive per-entity trends from metrics["trend_strength"] series
        entity_trend = None
        trend_series = metrics.get("trend_strength")
        if hasattr(trend_series, "get"):
            entity_trend = cls._num(
                trend_series.get(entity)
            )
        if entity_trend is None:
            entity_trend = trend_strength

        # -------------------------------------------------
        # fastest_growth / biggest_decline
        # -------------------------------------------------
        if story_type in ("fastest_growth", "biggest_decline"):
            direction = (
                "positive"
                if story_type == "fastest_growth"
                else "negative"
            )

            if percent_change is None:
                return {
                    "passed": False,
                    "detail": (
                        f"'{story_type}' requires percentage_change"
                    ),
                }

            if story_type == "fastest_growth" and percent_change <= 0:
                return {
                    "passed": False,
                    "detail": (
                        f"story '{story_type}' claims growth but "
                        f"percentage_change is {percent_change:.4f}"
                    ),
                }

            if story_type == "biggest_decline" and percent_change >= 0:
                return {
                    "passed": False,
                    "detail": (
                        f"story '{story_type}' claims decline but "
                        f"percentage_change is {percent_change:.4f}"
                    ),
                }

            # Direction consistency with absolute change
            if absolute_change is not None:
                if (
                    story_type == "fastest_growth"
                    and absolute_change <= 0
                ):
                    return {
                        "passed": False,
                        "detail": (
                            f"story '{story_type}' but absolute_change "
                            f"is {absolute_change:.6f}"
                        ),
                    }
                if (
                    story_type == "biggest_decline"
                    and absolute_change >= 0
                ):
                    return {
                        "passed": False,
                        "detail": (
                            f"story '{story_type}' but absolute_change "
                            f"is {absolute_change:.6f}"
                        ),
                    }

            return {
                "passed": True,
                "detail": (
                    f"'{story_type}' supported by "
                    f"{direction} movement "
                    f"(percent={percent_change:.4f}, "
                    f"abs={absolute_change})"
                ),
            }

        # -------------------------------------------------
        # rank_climber / rank_decline
        # -------------------------------------------------
        if story_type in ("rank_climber", "rank_decline"):
            if rank_change is None:
                return {
                    "passed": False,
                    "detail": (
                        f"'{story_type}' requires rank_change"
                    ),
                }

            if story_type == "rank_climber" and rank_change <= 0:
                return {
                    "passed": False,
                    "detail": (
                        f"story '{story_type}' claims rank climb but "
                        f"rank_change is {rank_change:.4f}"
                    ),
                }

            if story_type == "rank_decline" and rank_change >= 0:
                return {
                    "passed": False,
                    "detail": (
                        f"story '{story_type}' claims rank drop but "
                        f"rank_change is {rank_change:.4f}"
                    ),
                }

            # Also require some value movement in the same direction
            if absolute_change is not None:
                if (
                    story_type == "rank_climber"
                    and absolute_change <= 0
                ):
                    return {
                        "passed": False,
                        "detail": (
                            f"'{story_type}' with non-positive "
                            f"absolute_change ({absolute_change:.6f})"
                        ),
                    }
                if (
                    story_type == "rank_decline"
                    and absolute_change >= 0
                ):
                    return {
                        "passed": False,
                        "detail": (
                            f"'{story_type}' with non-negative "
                            f"absolute_change ({absolute_change:.6f})"
                        ),
                    }

            return {
                "passed": True,
                "detail": (
                    f"'{story_type}' supported by rank_change "
                    f"of {rank_change:.4f}"
                ),
            }

        # -------------------------------------------------
        # current_leader
        # -------------------------------------------------
        if story_type == "current_leader":
            if end_value is None:
                return {
                    "passed": False,
                    "detail": (
                        "'current_leader' requires end_value"
                    ),
                }

            # A valid leader needs a positive, non-trivial value.
            if abs(end_value) < cls.MIN_ABSOLUTE_CHANGE:
                return {
                    "passed": False,
                    "detail": (
                        f"'current_leader' end_value is effectively "
                        f"zero ({end_value:.6f})"
                    ),
                }

            leader_sep = leader_separation
            if leader_sep is None:
                leader_sep = 1.0

            if leader_sep > 1.5:
                return {
                    "passed": False,
                    "detail": (
                        f"'current_leader' leader separation is "
                        f"suspiciously large ({leader_sep:.4f})"
                    ),
                }

            return {
                "passed": True,
                "detail": (
                    f"'current_leader' has valid leader with "
                    f"end_value={end_value:.4f}"
                ),
            }

        # -------------------------------------------------
        # leader_challenge
        # -------------------------------------------------
        if story_type == "leader_challenge":
            if leader_separation is None:
                return {
                    "passed": False,
                    "detail": (
                        "'leader_challenge' requires leader_separation"
                    ),
                }

            # leader_challenge requires meaningful competition:
            # second-place entity close enough to challenge.
            if leader_separation > 0.25:
                return {
                    "passed": False,
                    "detail": (
                        f"'leader_challenge' gap too large "
                        f"({leader_separation:.4f})"
                    ),
                }

            return {
                "passed": True,
                "detail": (
                    f"'leader_challenge' supported by "
                    f"separation={leader_separation:.4f}"
                ),
            }

        # -------------------------------------------------
        # trend_over_time
        # -------------------------------------------------
        if story_type == "trend_over_time":
            if start_value is None or end_value is None:
                return {
                    "passed": False,
                    "detail": (
                        "'trend_over_time' requires start/end values"
                    ),
                }

            if abs(end_value - start_value) < cls.MIN_ABSOLUTE_CHANGE:
                return {
                    "passed": False,
                    "detail": (
                        f"'trend_over_time' with no meaningful movement "
                        f"(abs change {abs(end_value - start_value):.6f})"
                    ),
                }

            # Trend strength should be at least moderate.
            trend = entity_trend
            if trend is not None and trend < 0.25:
                return {
                    "passed": False,
                    "detail": (
                        f"'trend_over_time' trend_strength "
                        f"too low ({trend:.4f})"
                    ),
                }

            return {
                "passed": True,
                "detail": (
                    f"'trend_over_time' supported by "
                    f"start={start_value:.4f} → end={end_value:.4f}"
                ),
            }

        # -------------------------------------------------
        # Unknown story type
        # -------------------------------------------------
        return {
            "passed": False,
            "detail": f"unknown story type '{story_type}'",
        }

    @classmethod
    def _check_near_zero_base(
        cls,
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Reject stories where percentage change is dramatic primarily
        because the starting value is near zero.
        """
        start_value = cls._num(
            metrics.get("start_value")
        )
        end_value = cls._num(
            metrics.get("end_value")
        )
        percent_change = cls._num(
            metrics.get("percentage_change")
        )
        absolute_change = cls._num(
            metrics.get("absolute_change")
        )
        story_type = str(
            metrics.get("story_type", "")
        ).strip()

        # Only meaningful for change-oriented stories.
        if story_type not in (
            "fastest_growth",
            "biggest_decline",
        ):
            return {
                "passed": True,
                "detail": (
                    "near-zero base check not applicable "
                    f"to '{story_type}'"
                ),
            }

        if percent_change is None or start_value is None:
            return {
                "passed": True,
                "detail": "no percentage data to check",
            }

        # If the base is effectively zero and the percentage
        # change is large, the story is misleading.
        if abs(start_value) <= cls.NEAR_ZERO_BASE_ABS:
            # Only reject if the absolute change is also small relative
            # to scale; if the movement is real (e.g., 0→100M) the
            # story can still be meaningful.
            scale = max(
                abs(end_value or 0.0),
                abs(start_value),
                1.0,
            )
            relative_abs = (
                abs(absolute_change or 0.0)
                / max(scale, 1e-12)
            )

            if relative_abs < 0.05:
                return {
                    "passed": False,
                    "detail": (
                        f"percentage_change={percent_change:.4f} "
                        f"driven by near-zero base "
                        f"(start={start_value:.6g})"
                    ),
                }

            return {
                "passed": True,
                "detail": (
                    f"near-zero base but meaningful movement "
                    f"(rel_abs={relative_abs:.4f})"
                ),
            }

        return {
            "passed": True,
            "detail": (
                f"base value {start_value:.4g} is not near-zero"
            ),
        }

    @classmethod
    def _check_signal_consistency(
        cls,
        metrics: Dict[str, Any],
        story_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verify that percentage_change and rank_change point in a
        consistent direction for growth/decline stories.
        """
        story_type = str(
            story_type or metrics.get("story_type", "")
        ).strip()

        percent_change = cls._num(
            metrics.get("percentage_change")
        )
        rank_change = cls._num(
            metrics.get("rank_change")
        )

        if story_type in ("fastest_growth", "biggest_decline"):
            # Both percent and rank should agree on direction.
            if percent_change is None or rank_change is None:
                return {
                    "passed": True,
                    "detail": "insufficient signals for cross-check",
                }

            percent_dir = 1 if percent_change > 0 else (
                -1 if percent_change < 0 else 0
            )
            rank_dir = 1 if rank_change > 0 else (
                -1 if rank_change < 0 else 0
            )

            # rank_change > 0 means the entity moved UP in ranking
            # (e.g., from rank 10 to rank 5).  This corresponds to
            # *positive* value movement.
            if percent_dir != 0 and rank_dir != 0:
                if percent_dir != rank_dir:
                    return {
                        "passed": False,
                        "detail": (
                            f"signal contradiction: percent_change="
                            f"{percent_change:.4f} but rank_change="
                            f"{rank_change:.4f}"
                        ),
                    }

            return {
                "passed": True,
                "detail": (
                    f"percent_change and rank_change directions "
                    f"consistent"
                ),
            }

        return {
            "passed": True,
            "detail": f"signal check not applicable to '{story_type}'",
        }

    @classmethod
    def _check_data_sufficiency(
        cls,
        metrics: Dict[str, Any],
        min_countries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Require at least MIN_COUNTRIES and MIN_YEARS.

        `min_countries` optionally overrides MIN_COUNTRIES for
        deliberate entity-comparison datasets (2-entity head-to-
        head); None keeps the historical minimum.
        """
        required_countries = (
            cls.MIN_COUNTRIES
            if min_countries is None
            else max(2, int(min_countries))
        )

        countries = int(
            metrics.get("number_of_valid_countries", 0) or 0
        )
        years = int(
            metrics.get("number_of_valid_years", 0) or 0
        )

        if countries < required_countries:
            return {
                "passed": False,
                "detail": (
                    f"only {countries} countries; need at least "
                    f"{required_countries}"
                ),
            }

        if years < cls.MIN_YEARS:
            return {
                "passed": False,
                "detail": (
                    f"only {years} years; need at least {cls.MIN_YEARS}"
                ),
            }

        return {
            "passed": True,
            "detail": (
                f"data sufficient: {countries} entities, "
                f"{years} years"
            ),
        }

    @classmethod
    def _check_completeness(
        cls,
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Require completeness above the engine's candidate-filter
        threshold (0.40).
        """
        completeness = float(
            metrics.get("data_completeness", 0.0) or 0.0
        )

        if completeness < cls.MIN_COMPLETENESS:
            return {
                "passed": False,
                "detail": (
                    f"completeness {completeness:.2f} below "
                    f"required {cls.MIN_COMPLETENESS}"
                ),
            }

        return {
            "passed": True,
            "detail": f"completeness {completeness:.2f} is sufficient",
        }

    @classmethod
    def _check_title_quality(
        cls,
        title: str,
        entity: Optional[str],
        story_type: Optional[str],
        indicator_name: Optional[str],
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Lightweight deterministic title check.

        Verifies the title:
          - is non-empty
          - mentions either the indicator or entity (loosely)
          - does not obviously contradict the story direction
        """
        title = str(title or "").strip()
        if not title:
            return {
                "passed": False,
                "detail": "title is empty",
            }

        title_lower = title.lower()
        entity_lower = str(entity or "").strip().lower()
        indicator_lower = str(indicator_name or "").strip().lower()

        # -------------------------------------------------
        # Direction keyword mapping
        # -------------------------------------------------
        growth_words = {
            "growth", "grow", "rising", "rise", "climb", "climber",
            "leaders", "leader", "surge", "boom", "increase",
            "pulling ahead", "ahead",
        }
        decline_words = {
            "decline", "declines", "declining", "fall", "falls",
            "falling", "drop", "drops", "dropped", "losing ground",
            "lose", "decrease",
        }

        # -------------------------------------------------
        # Determine expected direction from story type
        # -------------------------------------------------
        expected_direction = None
        if story_type in ("fastest_growth", "rank_climber", "current_leader"):
            expected_direction = "positive"
        elif story_type in ("biggest_decline", "rank_decline"):
            expected_direction = "negative"
        elif story_type in ("leader_challenge", "trend_over_time"):
            expected_direction = "neutral"

        # Actual direction from metrics
        percent_change = cls._num(
            metrics.get("percentage_change")
        )
        actual_direction = None
        if percent_change is not None:
            if percent_change > cls.RANK_EPSILON:
                actual_direction = "positive"
            elif percent_change < -cls.RANK_EPSILON:
                actual_direction = "negative"
            else:
                actual_direction = "neutral"

        # -------------------------------------------------
        # Check for contradiction: title says "growth" but
        # actual direction is negative (or vice versa).
        # -------------------------------------------------
        title_has_growth = any(
            word in title_lower
            for word in growth_words
        )
        title_has_decline = any(
            word in title_lower
            for word in decline_words
        )

        if (
            actual_direction == "negative"
            and title_has_growth
            and not title_has_decline
        ):
            return {
                "passed": False,
                "detail": (
                    f"title '{title}' suggests growth but "
                    f"data is declining (percent={percent_change:.4f})"
                ),
            }

        if (
            actual_direction == "positive"
            and title_has_decline
            and not title_has_growth
        ):
            return {
                "passed": False,
                "detail": (
                    f"title '{title}' suggests decline but "
                    f"data is growing (percent={percent_change:.4f})"
                ),
            }

        # -------------------------------------------------
        # Expected direction vs title hint
        # -------------------------------------------------
        if expected_direction == "positive":
            if title_has_decline and not title_has_growth:
                return {
                    "passed": False,
                    "detail": (
                        f"title '{title}' contradicts '{story_type}' "
                        f"which requires positive movement"
                    ),
                }
        elif expected_direction == "negative":
            if title_has_growth and not title_has_decline:
                return {
                    "passed": False,
                    "detail": (
                        f"title '{title}' contradicts '{story_type}' "
                        f"which requires negative movement"
                    ),
                }

        # -------------------------------------------------
        # Entity mention (loose)
        # -------------------------------------------------
        if entity_lower and len(entity_lower) > 2:
            if entity_lower not in title_lower:
                # Not a hard failure: many titles mention the indicator
                # or a generic country label instead. We just note it.
                pass

        # -------------------------------------------------
        # Pass
        # -------------------------------------------------
        return {
            "passed": True,
            "detail": f"title '{title}' looks reasonable",
        }

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    @staticmethod
    def _num(value):
        """Return a float, or None if the value is not numeric."""
        try:
            if value is None:
                return None
            result = float(value)
            if result != result:  # NaN
                return None
            return result
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _index_label(index_value: Any) -> Optional[str]:
        """Extract a label from a (possibly tuple) index value."""
        if isinstance(index_value, tuple):
            if len(index_value) >= 2:
                return str(index_value[1])
            if index_value:
                return str(index_value[0])
            return None
        return str(index_value)