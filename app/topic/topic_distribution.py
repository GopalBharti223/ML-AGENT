"""
Topic Distribution Preference for SmartStoryEngine

Provides a deterministic, quality-preserving preference for
country stories with a soft target distribution:
- India: 30%
- USA: 15%
- China: 15%
- Russia: 8%
- Ukraine: 5%
- Israel: 5%
- Bangladesh: 2%
- Iran: 2%
- Other: 18%

This is a SOFT preference, NOT a hard requirement:
- Quality always wins
- Anti-repeat rules are never bypassed
- No randomness is introduced
- The preference uses existing database history
- A great global story beats a weak high-interest story
"""

import re
from typing import Dict, List, Set

from app.topic.topic_families import classify_topic_family


# =========================================================
# COUNTRY CATEGORIES
# =========================================================

# Map entity names to country categories.
# Comparison stories (e.g., "USA vs China") are handled by
# checking both the primary entity and leader/challenger.
COUNTRY_ALIASES = {
    "united states": "usa",
    "usa": "usa",
    "u.s.": "usa",
    "u.s.a.": "usa",
    "us": "usa",
    "india": "india",
    "china": "china",
    "russia": "russia",
    "ukraine": "ukraine",
    "israel": "israel",
    "iran": "iran",
    "bangladesh": "bangladesh",
}

# Soft target distribution (not hard quotas).
# Story quality always wins over distribution.
# These are LONG-RUN soft preferences, not per-video quotas.
TARGET_DISTRIBUTION = {
    "india": 0.30,
    "usa": 0.15,
    "china": 0.15,
    "russia": 0.08,
    "ukraine": 0.05,
    "israel": 0.05,
    "bangladesh": 0.02,
    "iran": 0.02,
    "other": 0.18,
}

# Per-country boost caps.
#
# India gets the strongest soft preference.
# USA and China get strong preference.
# Russia, Ukraine, Israel get moderate preference.
# Bangladesh and Iran get small preference.
# Other gets minimal preference.
#
# Quality always wins:
#   Weak India story 65 * 1.075 * 1.04 = ~72.7  <  Strong global 85
#   Strong India story 84 * 1.075 * 1.04 = ~93.9 >  Strong global 82
COUNTRY_MAX_BOOSTS = {
    "india": 0.08,
    "usa": 0.06,
    "china": 0.06,
    "russia": 0.05,
    "ukraine": 0.05,
    "israel": 0.05,
    "bangladesh": 0.03,
    "iran": 0.03,
    "other": 0.02,
}

# Backward-compatible sets
HIGH_INTEREST_COUNTRIES = set(COUNTRY_ALIASES.keys())

HOT_TOPIC_COUNTRIES = {
    "united states",
    "usa",
    "u.s.",
    "u.s.a.",
    "us",
    "india",
    "china",
}

# Backward-compatible target ratio (85% = all target countries)
TARGET_HIGH_INTEREST_RATIO = 0.85

# Tolerance band (kept for backward compatibility)
TOLERANCE = 0.10

# Maximum country boost applied to the strongest-preference
# country (India).  Kept small (8%) so quality always wins.
MAX_BOOST = 0.08

# Extra boost for hot topics (kept for backward compatibility)
HOT_TOPIC_EXTRA_BOOST = 0.03

# Boost scale: deficit * BOOST_SCALE = boost, capped at the
# per-country cap in COUNTRY_MAX_BOOSTS.
BOOST_SCALE = 0.25

# Small boost for "other" candidates when "other" is underrepresented.
OTHER_BOOST = 0.02

# =========================================================
# TOPIC-INTEREST SCORING
# =========================================================

# Soft topic-family interest multiplier applied to candidate
# scores.  High-curiosity families (economy, technology, AI,
# military, health, energy) get a small boost.  General topics
# get 1.0.
#
# Each family maps to real, currently-fetchable provider data:
#   economy      -> WB GDP/GDP/capita, IMF GDP/inflation/debt, OWID GDP/capita
#   health       -> WB life expectancy / mortality / health spend, OWID life expectancy
#   education    -> WB education expenditure
#   military     -> WB military expenditure
#   energy       -> OWID energy per capita
#   environment  -> OWID CO2 / CO2 per capita
#   technology   -> WB internet users, OWID internet users
#   urbanization -> WB urban population
#   electricity  -> WB electricity access
#   demographics -> WB population, OWID population
#   AI           -> Stanford AI Index investment/research/talent/policy
TOPIC_FAMILY_INTEREST = {
    "economy": 1.04,                    # GDP, growth, economy rankings
    "technology_connectivity": 1.04,    # Internet, digital adoption
    "ai_investment": 1.05,              # AI investment - high curiosity
    "ai_research": 1.04,                # AI research publications
    "ai_talent": 1.04,                  # AI talent migration
    "ai_governance": 1.03,              # AI policy / regulation
    "demographics": 1.02,               # Population changes
    "environment": 1.02,                # CO2, climate
    "health": 1.03,                     # Life expectancy, mortality, health spend
    "education": 1.02,                  # Education spending
    "military": 1.04,                   # Military / defense spending
    "energy": 1.03,                     # Energy use per person
    "urbanization": 1.01,               # Urban population
    "electricity": 1.02,                # Electricity access
    "general": 1.0,
}

# Families where a tiny / non-notable country story is likely
# to be boring (e.g., "tiny-country internet growth",
# "tiny-country CO2 changes", "tiny-country urbanization",
# "tiny-country electricity access").
#
# NOTE: health, education, military, energy, economy and
# technology are intentionally NOT in this set - they have
# natural high audience curiosity even for smaller countries.
BORING_FAMILIES = {
    "technology_connectivity",
    "environment",
    "demographics",
    "urbanization",
    "electricity",
}

# Penalty for boring small-country stories in boring-prone families.
# These topics may still be selected if genuinely exceptional,
# but they receive a lower topic-interest score.
BORING_SMALL_COUNTRY_PENALTY = 0.97

# Countries/entities that are inherently newsworthy - never
# considered "boring small countries".
NOTABLE_COUNTRIES = set(COUNTRY_ALIASES.keys()) | {
    "germany",
    "united kingdom",
    "uk",
    "france",
    "japan",
    "canada",
    "australia",
    "south korea",
    "brazil",
    "mexico",
    "indonesia",
    "turkey",
    "south africa",
    "vietnam",
    "saudi arabia",
    "italy",
    "spain",
    "netherlands",
    "switzerland",
    "sweden",
    "norway",
    "poland",
    "thailand",
    "singapore",
    "malaysia",
    "argentina",
    "egypt",
    "nigeria",
    "pakistan",
    "philippines",
    "taiwan",
    "hong kong",
    "europe",
}

# =========================================================
# MAJOR-COUNTRY COMPARISON BONUS
# =========================================================

# Countries where "X vs Y" comparisons have strong international
# curiosity potential (India vs China, India vs USA, USA vs China,
# India vs Russia, China vs Russia, India vs major economies,
# USA vs major economies, etc.).
MAJOR_COMPARISON_COUNTRIES = {
    "india",
    "usa",
    "china",
    "russia",
    "ukraine",
    "israel",
}

# Both sides are major countries (e.g., "India vs China",
# "USA vs China", "India vs USA").
MAJOR_COMPARISON_BOOST = 1.03

# One side is a major country (e.g., "USA vs Germany",
# "China vs Brazil").
MAJOR_COMPARISON_PARTIAL_BOOST = 1.015

# =========================================================
# CONCEPT-REPETITION PENALTIES
# =========================================================
#
# Soft penalties when the SAME entity + indicator CONCEPT
# appears in recent history under different wording
# (e.g., "Angola Population Trend" then "Population:
# Current Leader" where Angola is the subject) or appears
# multiple times in the current candidate pool.
#
# These are SOFT - only penalties, never hard blocks - so
# a genuinely exceptional story can still be selected
# even if it repeats a recently-covered concept.
CONCEPT_REPEAT_ONE_HIT = 0.93         # one recent hit for the concept
CONCEPT_REPEAT_MULTI_HITS = 0.85      # 2+ recent hits for the concept
CONCEPT_DUPLICATE_IN_POOL = 0.90      # same entity+indicator appears 2+ times in the pool

# =========================================================
# FAMILY-DIVERSITY PENALTIES
# =========================================================
#
# Softly demote candidates whose topic family has been
# over-represented in recent history.  This prevents the
# channel from repeatedly producing population/GDP stories
# when other supported categories exist.
#
# These are SOFT - quality still wins.  A genuinely
# exceptional population story can still be selected even
# if population was recently over-represented.
#
# Family share measured against recent_records (0..1):
#   share > 0.50  -> 0.93
#   share > 0.35  -> 0.96
#   otherwise     -> 1.0
FAMILY_SHARE_MILD_PENALTY = 0.96
FAMILY_SHARE_STRONG_PENALTY = 0.93
FAMILY_SHARE_MILD_THRESHOLD = 0.35
FAMILY_SHARE_STRONG_THRESHOLD = 0.50


class TopicDistributionPreference:
    """
    Deterministic soft preference for country stories.
    """

    # =====================================================
    # CLASSIFICATION
    # =====================================================

    @classmethod
    def country_category(cls, entity: str) -> str:
        """
        Map an entity name to a country category.
        Returns one of: india, usa, china, russia, ukraine,
        israel, iran, bangladesh, other.
        """
        entity = str(entity or "").strip().lower()
        return COUNTRY_ALIASES.get(entity, "other")

    @classmethod
    def is_high_interest(
        cls,
        entity: str
    ) -> bool:
        """
        Check if an entity is a target country (not 'other').
        """
        return cls.country_category(entity) != "other"

    @classmethod
    def is_hot_topic(
        cls,
        entity: str
    ) -> bool:
        """
        Check if an entity is a HOT TOPIC country
        (India, USA, China).
        """
        return cls.country_category(entity) in {
            "india",
            "usa",
            "china",
        }

    @classmethod
    def _entity_mentioned(
        cls,
        text: str,
        entity: str
    ) -> bool:
        """
        Check whether an entity name appears in text using
        word-boundary matching (e.g., "Angola" in
        "Angola Population Trend").
        """
        if not text or not entity:
            return False

        pattern = (
            r"\b"
            + re.escape(
                str(entity).strip().lower()
            )
            + r"\b"
        )

        return re.search(
            pattern,
            str(text).lower()
        ) is not None

    @classmethod
    def _candidate_concepts(
        cls,
        candidate
    ) -> Set[str]:
        """
        Build concept identifiers (entity + indicator) for a
        candidate.

        For comparison stories (leader_challenge), includes
        the challenger and leader entities too.

        Returns a set of lower-case "entity|indicator" strings.
        """
        metrics = getattr(
            candidate,
            "metrics",
            {}
        ) or {}

        entity = str(
            metrics.get("entity", "") or ""
        ).strip().lower()
        indicator = str(
            metrics.get("indicator_code", "") or ""
        ).strip().lower()
        leader = str(
            metrics.get("leader", "") or ""
        ).strip().lower()
        challenger = str(
            metrics.get("challenger", "") or ""
        ).strip().lower()

        concepts = set()

        if entity:
            concepts.add(
                f"{entity}|{indicator}"
            )
        if (
            leader
            and leader != entity
        ):
            concepts.add(
                f"{leader}|{indicator}"
            )
        if (
            challenger
            and challenger != entity
            and challenger != leader
        ):
            concepts.add(
                f"{challenger}|{indicator}"
            )

        return concepts

    @classmethod
    def concept_repeat_multiplier(
        cls,
        candidate,
        recent_records: List[Dict]
    ) -> float:
        """
        Soft penalty when the same entity+indicator CONCEPT
        appears in recent history under different topic wording
        (e.g., "Angola Population Trend" then "Population:
        Current Leader" where Angola is the subject).

        Returns a multiplier in [0.85, 1.0]:
        - 0.93 for one recent concept hit
        - 0.85 for two or more recent concept hits
        - 1.0 otherwise
        """
        if not recent_records:
            return 1.0

        concepts = cls._candidate_concepts(
            candidate
        )

        if not concepts:
            return 1.0

        hits = 0

        for record in recent_records:
            if not isinstance(
                record,
                dict
            ):
                continue

            record_indicator = str(
                record.get(
                    "indicator_code",
                    ""
                ) or ""
            ).strip().lower()

            if not record_indicator:
                continue

            text = " ".join(
                [
                    str(
                        record.get(
                            "topic",
                            ""
                        )
                    ),
                    str(
                        record.get(
                            "title",
                            ""
                        )
                    ),
                ]
            )

            for concept in concepts:
                entity, indicator = concept.split(
                    "|",
                    1
                )

                if (
                    indicator == record_indicator
                    and cls._entity_mentioned(
                        text,
                        entity
                    )
                ):
                    hits += 1
                    break

        if hits >= 2:
            return CONCEPT_REPEAT_MULTI_HITS

        if hits == 1:
            return CONCEPT_REPEAT_ONE_HIT

        return 1.0

    @classmethod
    def pool_duplicate_multiplier(
        cls,
        candidate,
        candidates: List
    ) -> float:
        """
        Soft penalty when the same concept (entity + indicator)
        appears multiple times in the current candidate pool
        under DIFFERENT story types (i.e., truly different
        wording of the same concept, like "Angola Population
        Trend" vs "Population: Current Leader" where Angola
        is the subject).

        Candidates with the SAME story type for the same
        concept (e.g., normal scoring duplicates) are NOT
        penalized — otherwise countries scored in multiple
        candidate slots would be unfairly handicapped.

        Returns a multiplier in [0.90, 1.0].
        """
        if not candidates:
            return 1.0

        concepts = cls._candidate_concepts(
            candidate
        )

        if not concepts:
            return 1.0

        candidate_story_type = str(
            getattr(
                candidate,
                "story_type",
                ""
            )
        ).strip().lower()

        duplicate_count = 0

        for other in candidates:
            if other is candidate:
                continue

            other_concepts = cls._candidate_concepts(
                other
            )

            if not (concepts & other_concepts):
                continue

            other_story_type = str(
                getattr(
                    other,
                    "story_type",
                    ""
                )
            ).strip().lower()

            # Only penalize when a DIFFERENT story type
            # covers the same concept (genuine re-wording).
            if other_story_type != candidate_story_type:
                duplicate_count += 1

        if duplicate_count >= 1:
            return CONCEPT_DUPLICATE_IN_POOL

        return 1.0

    @classmethod
    def candidate_country(
        cls,
        candidate
    ) -> str:
        """
        Determine the primary country category of a candidate.
        Uses the primary entity (main story subject).
        """
        metrics = getattr(
            candidate,
            "metrics",
            {}
        ) or {}

        entity = metrics.get(
            "entity",
            ""
        )

        return cls.country_category(entity)

    @classmethod
    def candidate_is_high_interest(
        cls,
        candidate
    ) -> bool:
        """
        Determine if a StoryCandidate is high-interest.

        Checks:
        1. metrics["entity"] - the primary entity
        2. metrics["leader"] - for leader_challenge stories
        3. metrics["challenger"] - for leader_challenge stories
        """
        metrics = getattr(
            candidate,
            "metrics",
            {}
        ) or {}

        # Primary entity
        entity = metrics.get(
            "entity",
            ""
        )
        if cls.is_high_interest(entity):
            return True

        # Leader / challenger (leader_challenge stories)
        leader = metrics.get(
            "leader",
            ""
        )
        if cls.is_high_interest(leader):
            return True

        challenger = metrics.get(
            "challenger",
            ""
        )
        if cls.is_high_interest(challenger):
            return True

        return False

    # =====================================================
    # HISTORY ANALYSIS
    # =====================================================

    @classmethod
    def _text_country_categories(
        cls,
        text: str
    ) -> Set[str]:
        """
        Find all country categories mentioned in text.
        Uses word-boundary matching to avoid false positives.
        """
        text = str(text or "").lower()
        categories = set()

        for alias, category in COUNTRY_ALIASES.items():
            pattern = (
                r"\b"
                + re.escape(alias)
                + r"\b"
            )
            if re.search(pattern, text):
                categories.add(category)

        return categories

    @classmethod
    def country_ratios(
        cls,
        recent_records: List[Dict]
    ) -> Dict[str, float]:
        """
        Calculate the current ratio of each country category
        in recent history.

        A record mentioning multiple countries (e.g., "USA vs China")
        counts toward each country's ratio.

        Returns a dict mapping category -> ratio in [0.0, 1.0].
        """
        counts = {
            cat: 0
            for cat in TARGET_DISTRIBUTION
        }
        total = 0

        for record in recent_records:
            if not isinstance(record, dict):
                continue

            text = " ".join(
                [
                    str(record.get("topic", "")),
                    str(record.get("title", "")),
                ]
            ).lower()

            if not text.strip():
                continue

            total += 1
            categories = cls._text_country_categories(text)

            if not categories:
                categories = {"other"}

            for cat in categories:
                counts[cat] += 1

        if total == 0:
            return {
                cat: 0.0
                for cat in TARGET_DISTRIBUTION
            }

        return {
            cat: count / total
            for cat, count in counts.items()
        }

    @classmethod
    def current_high_interest_ratio(
        cls,
        recent_records: List[Dict]
    ) -> float:
        """
        Calculate the current ratio of high-interest stories
        from recent history.

        Backward-compatible: returns the fraction of records
        mentioning at least one target country.
        """
        if not recent_records:
            return 0.0

        high_interest_count = 0
        total = 0

        for record in recent_records:
            if not isinstance(record, dict):
                continue

            text = " ".join(
                [
                    str(record.get("topic", "")),
                    str(record.get("title", "")),
                ]
            ).lower()

            if not text.strip():
                continue

            total += 1

            if cls._text_country_categories(text):
                high_interest_count += 1

        if total == 0:
            return 0.0

        return high_interest_count / total

    @classmethod
    def _text_contains_high_interest(
        cls,
        text: str
    ) -> bool:
        """
        Check if text contains any target country name.
        Backward-compatible helper.
        """
        return bool(
            cls._text_country_categories(text)
        )

    # =====================================================
    # COUNTRY MULTIPLIER
    # =====================================================

    @classmethod
    def distribution_multiplier(
        cls,
        entity: str,
        recent_records: List[Dict]
    ) -> float:
        """
        Calculate a deterministic multiplier for a candidate
        based on the current representation of its country
        category vs the target.

        Returns a multiplier in [1.0, 1.08].

        Logic:
        - If the candidate's country is underrepresented vs target:
            Boost by deficit * BOOST_SCALE, capped at the
            per-country cap in COUNTRY_MAX_BOOSTS.
        - If "other" is underrepresented:
            Small boost for "other" candidates.
        - Otherwise: no adjustment (1.0).
        """
        category = cls.country_category(entity)
        ratios = cls.country_ratios(recent_records)
        target = TARGET_DISTRIBUTION.get(
            category,
            TARGET_DISTRIBUTION["other"]
        )
        current = ratios.get(category, 0.0)

        # Underrepresented: boost proportional to deficit
        deficit = max(0.0, target - current)
        if deficit > 0:
            # Cap depends on the country's preference strength.
            cap = COUNTRY_MAX_BOOSTS.get(
                category,
                OTHER_BOOST
            )
            boost = min(
                cap,
                deficit * BOOST_SCALE
            )
            return 1.0 + boost

        return 1.0

    # =====================================================
    # TOPIC-INTEREST MULTIPLIER
    # =====================================================

    @classmethod
    def topic_interest_multiplier(
        cls,
        candidate
    ) -> float:
        """
        Soft topic-interest multiplier for a candidate.

        Returns a multiplier in [0.97, 1.05].

        - High-curiosity families (economy, technology, AI)
          get a small boost.
        - Boring small-country stories (tiny-country internet,
          CO2, life expectancy, urbanization) get a small penalty.

        This is a SOFT preference: a genuinely exceptional
        small-country story can still be selected.
        """
        family = str(
            getattr(
                candidate,
                "topic_family",
                "general"
            )
        ).strip().lower()

        metrics = getattr(
            candidate,
            "metrics",
            {}
        ) or {}

        entity = metrics.get(
            "entity",
            ""
        )
        entity_lower = str(
            entity or ""
        ).strip().lower()

        # Boring small-country penalty: for boring-prone families,
        # if the entity is not a notable country, apply a penalty.
        if (
            family in BORING_FAMILIES
            and entity_lower
            and entity_lower not in NOTABLE_COUNTRIES
        ):
            return BORING_SMALL_COUNTRY_PENALTY

        return TOPIC_FAMILY_INTEREST.get(
            family,
            1.0
        )

    # =====================================================
    # MAJOR-COUNTRY COMPARISON BONUS
    # =====================================================

    @classmethod
    def comparison_multiplier(
        cls,
        candidate
    ) -> float:
        """
        Small bonus for meaningful major-country comparisons
        (e.g., "India vs China", "USA vs China", "India vs USA").

        Only applies to leader_challenge stories which carry
        both leader and challenger metadata.

        Returns:
        - 1.03 when both sides are major countries
        - 1.015 when exactly one side is a major country
        - 1.0 otherwise
        """
        metrics = getattr(
            candidate,
            "metrics",
            {}
        ) or {}

        leader = metrics.get(
            "leader",
            ""
        )
        challenger = metrics.get(
            "challenger",
            ""
        )

        if not leader or not challenger:
            return 1.0

        leader_cat = cls.country_category(
            leader
        )
        challenger_cat = cls.country_category(
            challenger
        )

        leader_major = (
            leader_cat in MAJOR_COMPARISON_COUNTRIES
        )
        challenger_major = (
            challenger_cat in MAJOR_COMPARISON_COUNTRIES
        )

        if (
            leader_major
            and challenger_major
        ):
            return MAJOR_COMPARISON_BOOST

        if (
            leader_major
            or challenger_major
        ):
            return MAJOR_COMPARISON_PARTIAL_BOOST

        return 1.0

    # =====================================================
    # FAMILY-DIVERSITY MULTIPLIER
    # =====================================================

    @classmethod
    def family_diversity_multiplier(
        cls,
        candidate,
        recent_records: List[Dict]
    ) -> float:
        """
        Softly demote candidates whose topic family has been
        over-represented in recent history.

        The family is derived from the candidate's indicator code
        (via the shared topic-family classifier) and compared to
        the family distribution in recent_records.

        Returns a multiplier in [0.93, 1.0]:
        - 0.93 when the family share > 50% of recent history
        - 0.96 when the family share > 35% of recent history
        - 1.0 otherwise

        This is SOFT: a genuinely exceptional story within a
        frequently-used family can still be selected.
        """
        if not recent_records:
            return 1.0

        family = str(
            getattr(
                candidate,
                "topic_family",
                ""
            )
        ).strip().lower()

        if not family or family == "general":
            return 1.0

        total = 0
        family_count = 0

        for record in recent_records:
            if not isinstance(
                record,
                dict
            ):
                continue

            indicator_code = str(
                record.get(
                    "indicator_code",
                    ""
                )
            ).strip()

            if not indicator_code:
                continue

            total += 1

            record_family = classify_topic_family(
                indicator_code
            )

            if record_family == family:
                family_count += 1

        if total == 0:
            return 1.0

        share = family_count / total

        if share > FAMILY_SHARE_STRONG_THRESHOLD:
            return FAMILY_SHARE_STRONG_PENALTY

        if share > FAMILY_SHARE_MILD_THRESHOLD:
            return FAMILY_SHARE_MILD_PENALTY

        return 1.0

    # =====================================================
    # COMBINED MULTIPLIER
    # =====================================================

    @classmethod
    def combined_multiplier(
        cls,
        candidate,
        recent_records: List[Dict]
    ) -> float:
        """
        Combined soft-preference multiplier for a candidate.

        = country_multiplier * topic_interest_multiplier
          * comparison_multiplier * family_diversity_multiplier

        All components are soft bonuses/penalties.  Quality
        always wins:
          - Weak India candidate 65 * 1.075 * 1.04 = ~72.7
            still loses to a strong global candidate 85.
          - Strong India candidate 84 * 1.075 * 1.04 = ~93.9
            beats a strong global candidate 82
            when both are comparable.
        """
        metrics = getattr(
            candidate,
            "metrics",
            {}
        ) or {}

        entity = metrics.get(
            "entity",
            ""
        )

        country_mult = cls.distribution_multiplier(
            entity,
            recent_records
        )

        topic_mult = cls.topic_interest_multiplier(
            candidate
        )

        comparison_mult = cls.comparison_multiplier(
            candidate
        )

        concept_mult = cls.concept_repeat_multiplier(
            candidate,
            recent_records
        )

        family_mult = cls.family_diversity_multiplier(
            candidate,
            recent_records
        )

        return (
            country_mult
            * topic_mult
            * comparison_mult
            * concept_mult
            * family_mult
        )

    # =====================================================
    # APPLY PREFERENCE
    # =====================================================

    @classmethod
    def apply_preference(
        cls,
        candidates: List,
        recent_records: List[Dict]
    ) -> List:
        """
        Apply the distribution preference to a candidate list.

        Returns candidates sorted by adjusted score (descending).
        The original candidate objects are NOT modified.

        The adjustment combines:
        - Country distribution multiplier (soft, capped ~8%)
        - Topic-interest multiplier (soft, max ~5%)
        - Major-country comparison bonus (soft, max ~3%)

        All are small enough that quality always wins:
        a weak high-interest candidate (score 65) boosted to
        ~72 still loses to a strong global candidate (score 85).
        """
        if not candidates:
            return []

        scored = []

        for candidate in candidates:
            multiplier = cls.combined_multiplier(
                candidate,
                recent_records
            )

            # Soft penalty if the same concept (entity + indicator)
            # appears multiple times in the current candidate pool
            # under different story types / wording.
            pool_mult = cls.pool_duplicate_multiplier(
                candidate,
                candidates
            )

            multiplier = (
                multiplier * pool_mult
            )

            adjusted_score = (
                candidate.score * multiplier
            )

            scored.append(
                (
                    adjusted_score,
                    multiplier,
                    candidate,
                )
            )

        # Sort by adjusted score (descending)
        scored.sort(
            key=lambda item: item[0],
            reverse=True
        )

        return [
            candidate
            for _, _, candidate in scored
        ]

    @classmethod
    def get_multiplier_breakdown(
        cls,
        candidates: List,
        recent_records: List[Dict]
    ) -> Dict:
        """
        Return a breakdown of multipliers for transparency.
        """
        breakdown = {}

        for candidate in candidates:
            metrics = getattr(
                candidate,
                "metrics",
                {}
            ) or {}

            entity = metrics.get(
                "entity",
                ""
            )

            country_mult = cls.distribution_multiplier(
                entity,
                recent_records
            )
            topic_mult = cls.topic_interest_multiplier(
                candidate
            )
            comparison_mult = cls.comparison_multiplier(
                candidate
            )
            combined = (
                country_mult
                * topic_mult
                * comparison_mult
            )

            breakdown[
                candidate.topic
            ] = {
                "entity": entity,
                "country_category": cls.country_category(
                    entity
                ),
                "is_high_interest": cls.is_high_interest(
                    entity
                ),
                # New breakdown keys
                "country_multiplier": round(
                    country_mult,
                    4
                ),
                "topic_interest_multiplier": round(
                    topic_mult,
                    4
                ),
                "comparison_multiplier": round(
                    comparison_mult,
                    4
                ),
                "combined_multiplier": round(
                    combined,
                    4
                ),
                # Backward-compatible keys
                "multiplier": round(
                    combined,
                    4
                ),
                "original_score": round(
                    candidate.score,
                    2
                ),
                "adjusted_score": round(
                    candidate.score * combined,
                    2
                ),
            }

        return breakdown