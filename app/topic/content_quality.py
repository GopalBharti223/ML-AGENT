"""
Content Quality Validator for SmartStoryEngine

Validates that a selected story can safely become video content.
Checks story identity, time validity, data validity, story direction,
numerical claims, title accuracy, script content, and source integrity.

This is a deterministic, dependency-free validation layer.
It does NOT use LLMs to judge content.

The validator is inserted between the best story selection and
content generation in the SmartStoryEngine flow.
"""

import math
from typing import Dict, List, Optional, Any


class ContentQualityValidator:
    """
    Deterministic content quality validator.

    Validates a story candidate's data and metadata before it
    proceeds to script generation and video rendering.

    Checks:
    1. Story identity (title, provider, indicator, story_type, source)
    2. Time validity (start_year, end_year)
    3. Data validity (entities, numerical values)
    4. Story direction consistency
    5. Numerical claim validation
    6. Title validation
    7. Script validation (if script provided)
    8. Source integrity
    """

    # Story type → expected direction of percentage_change
    # positive = growth, negative = decline, zero = no change
    STORY_DIRECTION = {
        "fastest_growth": "positive",
        "biggest_decline": "negative",
        "rank_climber": "positive",  # rank_change > 0 means climbing
        "rank_decline": "negative",   # rank_change < 0 means declining
        "current_leader": "any",      # leader has highest value
        "leader_challenge": "any",   # challenger is close to leader
        "trend_over_time": "any",    # any meaningful trend
    }

    # Placeholder patterns that indicate unresolved templates
    PLACEHOLDER_PATTERNS = [
        "[INSERT",
        "[VALUE]",
        "[ENTITY]",
        "[YEAR]",
        "[NUMBER]",
        "[PERCENT]",
        "{insert",
        "{value}",
        "{entity}",
        "{year}",
        "{number}",
        "{percent}",
        "TODO",
        "FIXME",
        "PLACEHOLDER",
        "XXX",
    ]

    # Debug text patterns
    DEBUG_PATTERNS = [
        "DEBUG:",
        "DEBUG ",
        "print(",
        "Traceback",
        "Exception:",
        "Error:",
    ]

    @classmethod
    def validate(
        cls,
        story_data: Dict,
        script: Optional[str] = None,
    ) -> Dict:
        """
        Validate a story candidate for content quality.

        Args:
            story_data: Dict from StoryCandidate.to_topic_data() or
                        a StoryCandidate object
            script: Optional script text to validate

        Returns:
            {
                "valid": bool,
                "score": float,
                "reasons": [],
                "checks": {},
            }
        """
        checks = {}
        reasons = []

        # Handle both StoryCandidate objects and dicts
        if hasattr(story_data, "to_topic_data"):
            data = story_data.to_topic_data()
        elif isinstance(story_data, dict):
            data = story_data
        else:
            return {
                "valid": False,
                "score": 0.0,
                "reasons": ["story_data must be a dict or StoryCandidate"],
                "checks": {},
            }

        # Extract metrics
        metrics = data.get("story_metrics", {})
        if not metrics:
            metrics = data.get("metrics", {})

        # =====================================================
        # CHECK 1: Story Identity
        # =====================================================
        identity_checks = cls._check_story_identity(data)
        checks["story_identity"] = identity_checks
        if not identity_checks["valid"]:
            reasons.extend(identity_checks["reasons"])

        # =====================================================
        # CHECK 2: Time Validity
        # =====================================================
        time_checks = cls._check_time_validity(metrics)
        checks["time_validity"] = time_checks
        if not time_checks["valid"]:
            reasons.extend(time_checks["reasons"])

        # =====================================================
        # CHECK 3: Data Validity
        # =====================================================
        data_checks = cls._check_data_validity(metrics)
        checks["data_validity"] = data_checks
        if not data_checks["valid"]:
            reasons.extend(data_checks["reasons"])

        # =====================================================
        # CHECK 4: Story Direction
        # =====================================================
        direction_checks = cls._check_story_direction(
            data.get("story_type", ""),
            metrics
        )
        checks["story_direction"] = direction_checks
        if not direction_checks["valid"]:
            reasons.extend(direction_checks["reasons"])

        # =====================================================
        # CHECK 5: Numerical Claim Validation
        # =====================================================
        numerical_checks = cls._check_numerical_claims(metrics)
        checks["numerical_claims"] = numerical_checks
        if not numerical_checks["valid"]:
            reasons.extend(numerical_checks["reasons"])

        # =====================================================
        # CHECK 6: Title Validation
        # =====================================================
        title_checks = cls._check_title(
            data.get("topic", ""),
            data.get("story_type", ""),
            metrics
        )
        checks["title_validation"] = title_checks
        if not title_checks["valid"]:
            reasons.extend(title_checks["reasons"])

        # =====================================================
        # CHECK 7: Script Validation (if provided)
        # =====================================================
        if script is not None:
            script_checks = cls._check_script(script)
            checks["script_validation"] = script_checks
            if not script_checks["valid"]:
                reasons.extend(script_checks["reasons"])

        # =====================================================
        # CHECK 8: Source Integrity
        # =====================================================
        source_checks = cls._check_source_integrity(data)
        checks["source_integrity"] = source_checks
        if not source_checks["valid"]:
            reasons.extend(source_checks["reasons"])

        # =====================================================
        # Calculate overall score
        # =====================================================
        total_checks = len(checks)
        passed_checks = sum(
            1 for c in checks.values() if c.get("valid", False)
        )
        score = round(
            (passed_checks / total_checks) * 100.0,
            2
        ) if total_checks > 0 else 0.0

        return {
            "valid": len(reasons) == 0,
            "score": score,
            "reasons": reasons,
            "checks": checks,
        }

    # =========================================================
    # CHECK 1: Story Identity
    # =========================================================

    @classmethod
    def _check_story_identity(cls, data: Dict) -> Dict:
        """Verify title, provider, indicator, story_type, and source exist."""
        reasons = []

        title = data.get("topic", "")
        if not title or not str(title).strip():
            reasons.append("Title/topic is missing or empty")

        provider = data.get("provider_id", "")
        if not provider or not str(provider).strip():
            reasons.append("Provider ID is missing or empty")

        indicator = data.get("indicator_code", "")
        if not indicator or not str(indicator).strip():
            reasons.append("Indicator code is missing or empty")

        indicator_name = data.get("indicator_name", "")
        if not indicator_name or not str(indicator_name).strip():
            reasons.append("Indicator name is missing or empty")

        story_type = data.get("story_type", "")
        if not story_type or not str(story_type).strip():
            reasons.append("Story type is missing or empty")

        return {
            "valid": len(reasons) == 0,
            "reasons": reasons,
        }

    # =========================================================
    # CHECK 2: Time Validity
    # =========================================================

    @classmethod
    def _check_time_validity(cls, metrics: Dict) -> Dict:
        """Verify start_year and end_year are valid."""
        reasons = []

        start_year = metrics.get("start_year")
        end_year = metrics.get("end_year")

        if start_year is None:
            reasons.append("start_year is missing")
        if end_year is None:
            reasons.append("end_year is missing")

        if start_year is not None and end_year is not None:
            try:
                start = int(start_year)
                end = int(end_year)
            except (ValueError, TypeError):
                reasons.append(
                    f"start_year/end_year are not valid integers: "
                    f"{start_year}/{end_year}"
                )
            else:
                if start >= end:
                    reasons.append(
                        f"start_year ({start}) must be less than "
                        f"end_year ({end})"
                    )

                # Check for future years (beyond 2026)
                # Allow up to 2026 since we're in 2026
                if end > 2026:
                    reasons.append(
                        f"end_year ({end}) is in the future "
                        f"(beyond 2026)"
                    )

                # Check for unreasonably old years
                if start < 1900:
                    reasons.append(
                        f"start_year ({start}) is unreasonably old"
                    )

        return {
            "valid": len(reasons) == 0,
            "reasons": reasons,
        }

    # =========================================================
    # CHECK 3: Data Validity
    # =========================================================

    @classmethod
    def _check_data_validity(cls, metrics: Dict) -> Dict:
        """Verify entities and numerical values are valid."""
        reasons = []

        # Check entity exists
        entity = metrics.get("entity", "")
        if not entity or not str(entity).strip():
            reasons.append("Entity is missing or empty")

        # Check numerical values are actually numeric and finite
        numeric_fields = [
            "start_value",
            "end_value",
            "absolute_change",
            "percentage_change",
        ]

        for field in numeric_fields:
            value = metrics.get(field)
            if value is None:
                reasons.append(f"{field} is None")
            elif not cls._is_valid_number(value):
                reasons.append(
                    f"{field} is not a valid finite number: {value}"
                )

        # Check rank values
        rank_fields = ["start_rank", "end_rank", "rank_change"]
        for field in rank_fields:
            value = metrics.get(field)
            if value is not None and not cls._is_valid_number(value):
                reasons.append(
                    f"{field} is not a valid number: {value}"
                )

        # Check valid countries/years
        valid_countries = metrics.get("number_of_valid_countries", 0)
        valid_years = metrics.get("number_of_valid_years", 0)

        if valid_countries is not None:
            try:
                if int(valid_countries) < 1:
                    reasons.append(
                        f"number_of_valid_countries is too low: "
                        f"{valid_countries}"
                    )
            except (ValueError, TypeError):
                reasons.append(
                    f"number_of_valid_countries is not numeric: "
                    f"{valid_countries}"
                )

        if valid_years is not None:
            try:
                if int(valid_years) < 1:
                    reasons.append(
                        f"number_of_valid_years is too low: "
                        f"{valid_years}"
                    )
            except (ValueError, TypeError):
                reasons.append(
                    f"number_of_valid_years is not numeric: "
                    f"{valid_years}"
                )

        return {
            "valid": len(reasons) == 0,
            "reasons": reasons,
        }

    # =========================================================
    # CHECK 4: Story Direction
    # =========================================================

    @classmethod
    def _check_story_direction(
        cls,
        story_type: str,
        metrics: Dict
    ) -> Dict:
        """Verify story type agrees with data direction."""
        reasons = []

        if not story_type:
            return {
                "valid": True,
                "reasons": [],
            }

        expected_direction = cls.STORY_DIRECTION.get(
            story_type,
            "any"
        )

        if expected_direction == "any":
            return {
                "valid": True,
                "reasons": [],
            }

        pct_change = metrics.get("percentage_change")
        rank_change = metrics.get("rank_change")

        if expected_direction == "positive":
            # fastest_growth, rank_climber
            if story_type == "fastest_growth":
                if pct_change is not None:
                    if pct_change <= 0:
                        reasons.append(
                            f"fastest_growth story but "
                            f"percentage_change is "
                            f"non-positive ({pct_change})"
                        )
            elif story_type == "rank_climber":
                if rank_change is not None:
                    if rank_change <= 0:
                        reasons.append(
                            f"rank_climber story but "
                            f"rank_change is "
                            f"non-positive ({rank_change})"
                        )

        elif expected_direction == "negative":
            # biggest_decline, rank_decline
            if story_type == "biggest_decline":
                if pct_change is not None:
                    if pct_change >= 0:
                        reasons.append(
                            f"biggest_decline story but "
                            f"percentage_change is "
                            f"non-negative ({pct_change})"
                        )
            elif story_type == "rank_decline":
                if rank_change is not None:
                    if rank_change >= 0:
                        reasons.append(
                            f"rank_decline story but "
                            f"rank_change is "
                            f"non-negative ({rank_change})"
                        )

        return {
            "valid": len(reasons) == 0,
            "reasons": reasons,
        }

    # =========================================================
    # CHECK 5: Numerical Claim Validation
    # =========================================================

    @classmethod
    def _check_numerical_claims(cls, metrics: Dict) -> Dict:
        """Verify numerical claims are derivable from data."""
        reasons = []

        start_value = metrics.get("start_value")
        end_value = metrics.get("end_value")
        absolute_change = metrics.get("absolute_change")
        percentage_change = metrics.get("percentage_change")

        # Verify absolute_change = end_value - start_value
        if (
            start_value is not None
            and end_value is not None
            and absolute_change is not None
            and cls._is_valid_number(start_value)
            and cls._is_valid_number(end_value)
            and cls._is_valid_number(absolute_change)
        ):
            expected_abs = end_value - start_value
            if abs(absolute_change - expected_abs) > 0.01:
                reasons.append(
                    f"absolute_change ({absolute_change}) does not "
                    f"match end_value - start_value "
                    f"({expected_abs:.4f})"
                )

        # Verify percentage_change is consistent with absolute_change
        if (
            start_value is not None
            and absolute_change is not None
            and percentage_change is not None
            and cls._is_valid_number(start_value)
            and cls._is_valid_number(absolute_change)
            and cls._is_valid_number(percentage_change)
            and abs(start_value) > 1e-9
        ):
            expected_pct = (
                absolute_change / abs(start_value) * 100
            )
            if abs(percentage_change - expected_pct) > 1.0:
                reasons.append(
                    f"percentage_change ({percentage_change}) does not "
                    f"match absolute_change/start_value*100 "
                    f"({expected_pct:.4f})"
                )

        return {
            "valid": len(reasons) == 0,
            "reasons": reasons,
        }

    # =========================================================
    # CHECK 6: Title Validation
    # =========================================================

    @classmethod
    def _check_title(
        cls,
        title: str,
        story_type: str,
        metrics: Dict
    ) -> Dict:
        """Verify title is not misleading."""
        reasons = []

        if not title or not str(title).strip():
            reasons.append("Title is empty")
            return {
                "valid": False,
                "reasons": reasons,
            }

        title_lower = str(title).lower()

        # Check for misleading growth/decline claims
        pct_change = metrics.get("percentage_change")

        if "fastest growth" in title_lower or "fastest growing" in title_lower:
            if pct_change is not None and pct_change <= 0:
                reasons.append(
                    f"Title claims 'fastest growth' but "
                    f"percentage_change is non-positive "
                    f"({pct_change})"
                )

        if "biggest decline" in title_lower or "biggest drop" in title_lower:
            if pct_change is not None and pct_change >= 0:
                reasons.append(
                    f"Title claims 'biggest decline' but "
                    f"percentage_change is non-negative "
                    f"({pct_change})"
                )

        if "ranking drops" in title_lower or "rank decline" in title_lower:
            rank_change = metrics.get("rank_change")
            if rank_change is not None and rank_change >= 0:
                reasons.append(
                    f"Title claims 'ranking drops' but "
                    f"rank_change is non-negative "
                    f"({rank_change})"
                )

        if "rank climber" in title_lower or "rank rise" in title_lower:
            rank_change = metrics.get("rank_change")
            if rank_change is not None and rank_change <= 0:
                reasons.append(
                    f"Title claims 'rank climber' but "
                    f"rank_change is non-positive "
                    f"({rank_change})"
                )

        return {
            "valid": len(reasons) == 0,
            "reasons": reasons,
        }

    # =========================================================
    # CHECK 7: Script Validation
    # =========================================================

    @classmethod
    def _check_script(cls, script: str) -> Dict:
        """Validate script content for placeholders and contradictions."""
        reasons = []

        if not script or not str(script).strip():
            reasons.append("Script is empty or None")
            return {
                "valid": False,
                "reasons": reasons,
            }

        script_str = str(script)

        # Check for placeholder text
        for pattern in cls.PLACEHOLDER_PATTERNS:
            if pattern.lower() in script_str.lower():
                reasons.append(
                    f"Script contains placeholder text: '{pattern}'"
                )

        # Check for debug text
        for pattern in cls.DEBUG_PATTERNS:
            if pattern.lower() in script_str.lower():
                reasons.append(
                    f"Script contains debug text: '{pattern}'"
                )

        # Check minimum word count
        word_count = len(script_str.split())
        if word_count < 15:
            reasons.append(
                f"Script is too short: {word_count} words "
                f"(minimum 15)"
            )

        return {
            "valid": len(reasons) == 0,
            "reasons": reasons,
        }

    # =========================================================
    # CHECK 8: Source Integrity
    # =========================================================

    @classmethod
    def _check_source_integrity(cls, data: Dict) -> Dict:
        """Verify source information is present and not fabricated."""
        reasons = []

        source_name = data.get("source_name", "")
        if not source_name or not str(source_name).strip():
            reasons.append("Source name is missing")

        source_url = data.get("source_url", "")
        if not source_url or not str(source_url).strip():
            reasons.append("Source URL is missing")

        # Check for fabricated source names
        fabricated_sources = [
            "demo",
            "fake",
            "test",
            "placeholder",
            "example",
            "sample",
        ]

        source_lower = str(source_name).lower()
        for fake in fabricated_sources:
            if fake in source_lower:
                reasons.append(
                    f"Source name appears fabricated: "
                    f"'{source_name}'"
                )

        return {
            "valid": len(reasons) == 0,
            "reasons": reasons,
        }

    # =========================================================
    # Utility
    # =========================================================

    @staticmethod
    def _is_valid_number(value: Any) -> bool:
        """Check if a value is a valid finite number."""
        if value is None:
            return False
        try:
            num = float(value)
        except (ValueError, TypeError):
            return False
        if math.isnan(num) or math.isinf(num):
            return False
        return True
