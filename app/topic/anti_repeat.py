"""
Anti-Repeat Validator for SmartStoryEngine

Prevents the story engine from repeatedly selecting the same topic,
indicator/story-type combination, year range, or full content
combination.

This module is standalone and designed to be reusable from
SmartStoryEngine later. It does NOT modify any existing class or
database method.
"""

from typing import Any, Dict, List, Optional

from app.database import db


class AntiRepeatValidator:
    """
    Validates story candidates against recent history to prevent
    repetitive content.

    Hard blocks:
      - Exact topic reuse
      - Same indicator + story type within 30 days
      - Same indicator + year range within 60 days
      - Same full combination within 90 days

    Soft penalty (NOT a hard block):
      - Topic-family repetition
    """

    # ---------------------------------------------------------
    # Default windows (aligned with existing database methods)
    # ---------------------------------------------------------

    STORY_TYPE_DAYS = 30
    YEAR_RANGE_DAYS = 60
    COMBINATION_DAYS = 90

    # Family repetition penalty (0.0 = no penalty, 1.0 = full block)
    FAMILY_PENALTY = 0.10

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    @classmethod
    def check(
        cls,
        *,
        topic: Optional[str] = None,
        indicator_code: Optional[str] = None,
        story_type: Optional[str] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        topic_family: Optional[str] = None,
        database=None,
    ) -> Dict[str, Any]:
        """
        Check a candidate against recent history.

        Parameters
        ----------
        topic : str, optional
            Candidate topic title.
        indicator_code : str, optional
            Indicator code (e.g., "NY.GDP.PCAP.CD").
        story_type : str, optional
            Story type (e.g., "fastest_growth").
        start_year : int, optional
            First year in the story window.
        end_year : int, optional
            Last year in the story window.
        topic_family : str, optional
            Topic family (e.g., "economy", "ai_investment").
        database : object, optional
            Database-like object with the same interface as
            app.database.db.  Defaults to the real db.

        Returns
        -------
        dict
            {
                "allowed": bool,
                "reasons": [str, ...],
                "hard_blocks": [str, ...],
                "family_penalty": float,
                "family_repeat": bool,
                "checks": {check_name: {"blocked": bool, "detail": str}}
            }
        """
        db_obj = database or db

        reasons: List[str] = []
        hard_blocks: List[str] = []
        checks: Dict[str, Dict[str, Any]] = {}

        # -----------------------------------------------------
        # 1. Exact topic reuse
        # -----------------------------------------------------

        topic_result = cls._check_topic(
            db_obj,
            topic,
        )
        checks["exact_topic"] = topic_result
        if topic_result["blocked"]:
            hard_blocks.append("exact_topic")
            reasons.append(
                topic_result["detail"] or "topic already used"
            )

        # -----------------------------------------------------
        # 2. Story-type reuse (hard block)
        # -----------------------------------------------------

        story_result = cls._check_story_type(
            db_obj,
            indicator_code,
            story_type,
        )
        checks["story_type_reuse"] = story_result
        if story_result["blocked"]:
            hard_blocks.append("story_type_reuse")
            reasons.append(
                story_result["detail"] or "story type recently used"
            )

        # -----------------------------------------------------
        # 3. Year-range reuse (hard block)
        # -----------------------------------------------------

        year_result = cls._check_year_range(
            db_obj,
            indicator_code,
            start_year,
            end_year,
        )
        checks["year_range_reuse"] = year_result
        if year_result["blocked"]:
            hard_blocks.append("year_range_reuse")
            reasons.append(
                year_result["detail"] or "year range recently used"
            )

        # -----------------------------------------------------
        # 4. Full combination reuse (hard block)
        # -----------------------------------------------------

        combo_result = cls._check_combination(
            db_obj,
            indicator_code,
            story_type,
            start_year,
            end_year,
        )
        checks["combination_reuse"] = combo_result
        if combo_result["blocked"]:
            hard_blocks.append("combination_reuse")
            reasons.append(
                combo_result["detail"] or "full combination recently used"
            )

        # -----------------------------------------------------
        # 5. Family repetition (soft penalty, NOT a hard block)
        # -----------------------------------------------------

        family_result = cls._check_family(
            db_obj,
            topic_family,
        )
        checks["family_repetition"] = family_result

        family_penalty = 0.0
        if family_result["repeat"]:
            family_penalty = cls.FAMILY_PENALTY

        return {
            "allowed": len(hard_blocks) == 0,
            "reasons": reasons,
            "hard_blocks": hard_blocks,
            "family_penalty": family_penalty,
            "family_repeat": family_result["repeat"],
            "checks": checks,
        }

    # ---------------------------------------------------------
    # Individual checks
    # ---------------------------------------------------------

    @classmethod
    def _check_topic(
        cls,
        db_obj,
        topic: Optional[str],
    ) -> Dict[str, Any]:
        """
        Exact topic reuse check.

        Uses db.is_topic_used(topic) when available.
        Falls back to scanning recent records if the method
        is not present (e.g., in tests with a fake db).
        """
        topic = str(topic or "").strip()
        if not topic:
            return {
                "blocked": False,
                "detail": "no topic provided to check",
            }

        # Preferred: use the database method
        if hasattr(db_obj, "is_topic_used"):
            try:
                used = bool(
                    db_obj.is_topic_used(topic)
                )
                if used:
                    return {
                        "blocked": True,
                        "detail": (
                            f"topic '{topic}' already used in history"
                        ),
                    }
                return {
                    "blocked": False,
                    "detail": f"topic '{topic}' is new",
                }
            except Exception as error:
                return {
                    "blocked": False,
                    "detail": (
                        f"topic check unavailable: {error}"
                    ),
                }

        # Fallback: scan recent records
        records = cls._get_records(db_obj)
        topic_lower = topic.lower()

        for record in records:
            if not isinstance(record, dict):
                continue

            old_topic = record.get("topic") or record.get("title")
            if not old_topic:
                continue

            if str(old_topic).strip().lower() == topic_lower:
                return {
                    "blocked": True,
                    "detail": (
                        f"topic '{topic}' already used in history"
                    ),
                }

        return {
            "blocked": False,
            "detail": f"topic '{topic}' is new",
        }

    @classmethod
    def _check_story_type(
        cls,
        db_obj,
        indicator_code: Optional[str],
        story_type: Optional[str],
    ) -> Dict[str, Any]:
        """
        Story-type reuse check (hard block).

        Uses db.is_story_type_used_recently(indicator, story, days=30)
        when available.
        """
        indicator_code = str(indicator_code or "").strip()
        story_type = str(story_type or "").strip()

        if not indicator_code or not story_type:
            return {
                "blocked": False,
                "detail": (
                    "indicator_code and story_type required "
                    "for story-type check"
                ),
            }

        if hasattr(db_obj, "is_story_type_used_recently"):
            try:
                used = bool(
                    db_obj.is_story_type_used_recently(
                        indicator_code,
                        story_type,
                        days=cls.STORY_TYPE_DAYS,
                    )
                )
                if used:
                    return {
                        "blocked": True,
                        "detail": (
                            f"indicator '{indicator_code}' + story "
                            f"'{story_type}' used within "
                            f"{cls.STORY_TYPE_DAYS} days"
                        ),
                    }
                return {
                    "blocked": False,
                    "detail": (
                        f"indicator '{indicator_code}' + story "
                        f"'{story_type}' not recently used"
                    ),
                }
            except Exception as error:
                return {
                    "blocked": False,
                    "detail": (
                        f"story-type check unavailable: {error}"
                    ),
                }

        # Fallback: scan recent records
        records = cls._get_records(db_obj)

        for record in records:
            if not isinstance(record, dict):
                continue

            if (
                str(record.get("indicator_code", "")) == indicator_code
                and str(record.get("story_type", "")) == story_type
            ):
                return {
                    "blocked": True,
                    "detail": (
                        f"indicator '{indicator_code}' + story "
                        f"'{story_type}' found in recent history"
                    ),
                }

        return {
            "blocked": False,
            "detail": (
                f"indicator '{indicator_code}' + story "
                f"'{story_type}' not recently used"
            ),
        }

    @classmethod
    def _check_year_range(
        cls,
        db_obj,
        indicator_code: Optional[str],
        start_year: Optional[int],
        end_year: Optional[int],
    ) -> Dict[str, Any]:
        """
        Year-range reuse check (hard block).

        Uses db.is_year_range_used_recently(
            indicator, start, end, days=60
        ) when available.
        """
        indicator_code = str(indicator_code or "").strip()

        try:
            start_year = int(start_year) if start_year is not None else None
            end_year = int(end_year) if end_year is not None else None
        except (TypeError, ValueError):
            return {
                "blocked": False,
                "detail": "invalid start/end year values",
            }

        if not indicator_code or start_year is None or end_year is None:
            return {
                "blocked": False,
                "detail": (
                    "indicator_code, start_year, and end_year "
                    "required for year-range check"
                ),
            }

        if hasattr(db_obj, "is_year_range_used_recently"):
            try:
                used = bool(
                    db_obj.is_year_range_used_recently(
                        indicator_code,
                        start_year,
                        end_year,
                        days=cls.YEAR_RANGE_DAYS,
                    )
                )
                if used:
                    return {
                        "blocked": True,
                        "detail": (
                            f"indicator '{indicator_code}' + years "
                            f"{start_year}-{end_year} used within "
                            f"{cls.YEAR_RANGE_DAYS} days"
                        ),
                    }
                return {
                    "blocked": False,
                    "detail": (
                        f"indicator '{indicator_code}' + years "
                        f"{start_year}-{end_year} not recently used"
                    ),
                }
            except Exception as error:
                return {
                    "blocked": False,
                    "detail": (
                        f"year-range check unavailable: {error}"
                    ),
                }

        # Fallback: scan recent records
        records = cls._get_records(db_obj)

        for record in records:
            if not isinstance(record, dict):
                continue

            if (
                str(record.get("indicator_code", "")) == indicator_code
                and record.get("start_year") == start_year
                and record.get("end_year") == end_year
            ):
                return {
                    "blocked": True,
                    "detail": (
                        f"indicator '{indicator_code}' + years "
                        f"{start_year}-{end_year} found in history"
                    ),
                }

        return {
            "blocked": False,
            "detail": (
                f"indicator '{indicator_code}' + years "
                f"{start_year}-{end_year} not recently used"
            ),
        }

    @classmethod
    def _check_combination(
        cls,
        db_obj,
        indicator_code: Optional[str],
        story_type: Optional[str],
        start_year: Optional[int],
        end_year: Optional[int],
    ) -> Dict[str, Any]:
        """
        Full combination reuse check (hard block).

        Uses db.is_content_combination_used(
            indicator, story, start, end, days=90
        ) when available.
        """
        indicator_code = str(indicator_code or "").strip()
        story_type = str(story_type or "").strip()

        try:
            start_year = int(start_year) if start_year is not None else None
            end_year = int(end_year) if end_year is not None else None
        except (TypeError, ValueError):
            return {
                "blocked": False,
                "detail": "invalid start/end year values",
            }

        if (
            not indicator_code
            or not story_type
            or start_year is None
            or end_year is None
        ):
            return {
                "blocked": False,
                "detail": (
                    "indicator_code, story_type, start_year, and "
                    "end_year required for combination check"
                ),
            }

        if hasattr(db_obj, "is_content_combination_used"):
            try:
                used = bool(
                    db_obj.is_content_combination_used(
                        indicator_code,
                        story_type,
                        start_year,
                        end_year,
                        days=cls.COMBINATION_DAYS,
                    )
                )
                if used:
                    return {
                        "blocked": True,
                        "detail": (
                            f"full combination "
                            f"({indicator_code}/{story_type}/"
                            f"{start_year}-{end_year}) used within "
                            f"{cls.COMBINATION_DAYS} days"
                        ),
                    }
                return {
                    "blocked": False,
                    "detail": (
                        f"full combination "
                        f"({indicator_code}/{story_type}/"
                        f"{start_year}-{end_year}) not recently used"
                    ),
                }
            except Exception as error:
                return {
                    "blocked": False,
                    "detail": (
                        f"combination check unavailable: {error}"
                    ),
                }

        # Fallback: scan recent records
        records = cls._get_records(db_obj)

        for record in records:
            if not isinstance(record, dict):
                continue

            if (
                str(record.get("indicator_code", "")) == indicator_code
                and str(record.get("story_type", "")) == story_type
                and record.get("start_year") == start_year
                and record.get("end_year") == end_year
            ):
                return {
                    "blocked": True,
                    "detail": (
                        f"full combination "
                        f"({indicator_code}/{story_type}/"
                        f"{start_year}-{end_year}) found in history"
                    ),
                }

        return {
            "blocked": False,
            "detail": (
                f"full combination "
                f"({indicator_code}/{story_type}/"
                f"{start_year}-{end_year}) not recently used"
            ),
        }

    @classmethod
    def _check_family(
        cls,
        db_obj,
        topic_family: Optional[str],
    ) -> Dict[str, Any]:
        """
        Family repetition check (soft penalty, NOT a hard block).

        Counts how many recent records share the same topic family.
        """
        topic_family = str(topic_family or "").strip().lower()

        if not topic_family or topic_family == "general":
            return {
                "repeat": False,
                "count": 0,
                "detail": "no specific family to check",
            }

        records = cls._get_records(db_obj)

        family_hits = 0

        for record in records:
            if not isinstance(record, dict):
                continue

            record_family = cls._record_family(record)
            if record_family == topic_family:
                family_hits += 1

        if family_hits > 0:
            return {
                "repeat": True,
                "count": family_hits,
                "detail": (
                    f"family '{topic_family}' appears "
                    f"{family_hits} time(s) in recent history"
                ),
            }

        return {
            "repeat": False,
            "count": 0,
            "detail": f"family '{topic_family}' not in recent history",
        }

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    @staticmethod
    def _get_records(db_obj) -> List[Dict]:
        """Get recent records from a database-like object."""
        if hasattr(db_obj, "get_recent_records"):
            try:
                records = db_obj.get_recent_records(limit=100)
                if records:
                    return records
            except Exception:
                pass

        if hasattr(db_obj, "get_recent_content"):
            try:
                records = db_obj.get_recent_content(limit=100)
                if records:
                    return records
            except Exception:
                pass

        return []

    @staticmethod
    def _record_family(record: Dict) -> str:
        """
        Determine the topic family of a history record.

        Uses the record's indicator_code / title / category to
        classify via topic_families.classify_topic_family().
        """
        from app.topic.topic_families import classify_topic_family

        return classify_topic_family(
            indicator_code=record.get("indicator_code", ""),
            indicator_name=record.get("title", ""),
            category=record.get("category", ""),
        )