import random
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from app.data.providers import DataProviderRegistry
from app.data.providers.health import provider_health
from app.database import db
from app.topic.anti_repeat import AntiRepeatValidator
from app.topic.category_rotation import CategoryRotationSelector
from app.topic.chart_selector import ChartSelector
from app.topic.story_quality import StoryQualityValidator
from app.topic.story_scoring import StoryScorer
from app.topic.story_diversity import StoryDiversityScorer
from app.topic.topic_distribution import TopicDistributionPreference
from app.topic.topic_families import (
    classify_topic_family,
    family_to_category,
)
from app.topic import audience_relevance
from app.topic.performance_bias import PerformanceBias
from app.config import settings


# Metric keys written by the audience-relevance gate's annotate().
# They are selection-time state, consumed by
# CategoryRotationSelector from the CANDIDATE (never from the
# published topic_data), so StoryCandidate.to_topic_data() strips
# them.  Keeping this as a named constant means a future gate that
# adds a fourth key is a one-line change here rather than another
# auto/manual shape divergence.
_AUDIENCE_METRIC_KEYS = frozenset({
    "audience_band",
    "audience_score",
    "audience_reasons",
})


@dataclass
class StoryCandidate:

    provider_id: str
    indicator_code: str
    indicator_name: str
    story_type: str
    chart_type: str
    topic_family: str
    years: int
    category: str
    source_name: str
    source_url: str
    topic: str
    score: float
    metrics: Dict

    # min_countries actually used by the Step-1 fetch that
    # produced this candidate's dataset (defaults to
    # SmartStoryEngine.MIN_COUNTRIES).  Carried through
    # to_topic_data() so run.py's Step-2 refetch reuses the
    # SAME frame size instead of a provider default (8).
    min_countries: int = 6

    # Optional explicit country hint (canonical display names)
    # the user asked for -- set only by the manual path.  When
    # present, to_topic_data() emits THIS as selected_countries
    # (so Step 2 reproduces exactly what the user requested)
    # instead of inferring the codes from the scored frame.
    selected_countries: Optional[List[str]] = None

    def _frame_country_codes(self) -> List[str]:

        """
        Country codes of the exact frame this candidate was
        scored on (metrics['data']), order-preserving and
        deduplicated.  Empty when the frame is missing or is
        not country-indexed (entity-keyed providers such as
        jikan use plain title indexes).
        """

        data = None

        if isinstance(self.metrics, dict):
            data = self.metrics.get("data")

        if data is None:
            return []

        try:

            if data.empty:
                return []

            level = data.index.get_level_values(
                "country_code"
            )

        except Exception:

            return []

        codes = []

        for code in level:

            code = str(code).strip()

            if code and code not in codes:
                codes.append(code)

        return codes

    def to_topic_data(self) -> Dict:

        # -----------------------------------------------------
        # story_metrics IS A COPY, and audience_* is stripped.
        #
        # Two reasons, both about keeping the auto and manual
        # handoff shapes identical (test_manual_topic_shape_parity):
        #
        # 1. The audience-relevance gate is SELECTION-time
        #    machinery.  `SmartStoryEngine.select_best_candidate()`
        #    calls audience_relevance.annotate(), which stamps
        #    audience_band / audience_score / audience_reasons
        #    into this candidate's metrics.  The manual keyword
        #    path never runs the gate (by design -- the user
        #    already named the topic, so relevance filtering is
        #    meaningless), so those three keys existed on the auto
        #    path only.  They are deliberately stripped here so
        #    the returned payload is identical on both paths; the
        #    candidate keeps its own copies, which is what
        #    CategoryRotationSelector actually reads.
        #
        # 2. This dict used to BE `self.metrics` by reference.  Any
        #    later mutation of topic_data["story_metrics"] would
        #    have silently written through into the live candidate.
        #    Copying removes that aliasing hazard entirely.
        # -----------------------------------------------------

        metrics = {
            key: value
            for key, value in (self.metrics or {}).items()
            if key not in _AUDIENCE_METRIC_KEYS
        }

        return {
            "provider_id": self.provider_id,
            "indicator_code": self.indicator_code,
            "indicator_name": self.indicator_name,
            "story_type": self.story_type,
            "provider_fetch_story_type":
                SmartStoryEngine.PROVIDER_FETCH_STORY.get(
                    self.story_type,
                    "fastest_growth"
                ),
            "chart_type": self.chart_type,
            "topic_family": self.topic_family,
            "years": self.years,
            "category": self.category,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "topic": self.topic,
            "smart_score": round(
                float(self.score),
                2
            ),
            "story_metrics": metrics,
            "selected_countries":
                self.selected_countries
                or self._frame_country_codes(),
            "selected_min_countries":
                int(self.min_countries),
        }


class SmartStoryEngine:

    STORY_TO_CHART = {
        "fastest_growth": "top5_change",
        "biggest_decline": "top5_change",
        "rank_climber": "slope",
        "rank_decline": "slope",
        "current_leader": "bar_race",
        "leader_challenge": "bar_race",
        "trend_over_time": "line",
    }

    PROVIDER_FETCH_STORY = {
        "fastest_growth": "fastest_growth",
        "biggest_decline": "most_declined",
        "rank_climber": "biggest_jump",
        "rank_decline": "most_declined",
        "current_leader": "biggest_jump",
        "leader_challenge": "biggest_jump",
        "trend_over_time": "fastest_growth",
    }

    # V2 Configuration
    DEFAULT_YEARS = 10
    MIN_COUNTRIES = 6
    MAX_INDICATORS_PER_PROVIDER = 5  # Increased from 3 for more candidate diversity
    # V2 Configuration
    DEFAULT_YEARS = 10
    MIN_COUNTRIES = 6
    MAX_INDICATORS_PER_PROVIDER = 5  # Increased from 3 for more candidate diversity

    # ---------------------------------------------------------
    # YEAR-WINDOW ROTATION (investigation: 3rd solar_system
    # dominance report)
    #
    # Root cause: every provider derived its fetch window
    # DETERMINISTICALLY (worldbank/owid: DEFAULT_YEARS=10 ending at
    # the latest data year; openalex/sec_edgar: end=2024;
    # jolpica_f1: end=2025; rawg: end=today.year-1).  Because
    # AntiRepeatValidator hard-blocks (indicator, start_year,
    # end_year) for YEAR_RANGE_DAYS=60 days, each
    # (indicator, fixed window) pair is usable only ONCE per 60
    # days REGARDLESS of story type.  With ~55 real indicators the
    # whole catalog offered only ~55 usable slots per 60 days while
    # the channel publishes 5-18 videos/day (300-1000 per 60 days).
    # Anti-repeat therefore exhausted nearly the entire time-series
    # catalog every run (log evidence: dozens of
    # "Skip worldbank/.../...: year_range_reuse" lines), the
    # surviving pool collapsed to 2-3 categories, and the
    # least-exhausted source won by default -- first population,
    # then solar_system.
    #
    # Fix: vary the fetch window PER INDICATOR so each indicator
    # exposes len(YEAR_WINDOW_POOL) distinct (indicator, window)
    # slots instead of one.  The year-range anti-repeat check keeps
    # its full protective meaning -- it still hard-blocks an exact
    # reused window -- but one blocked window no longer blocks the
    # indicator itself.
    #
    # An explicit years= argument (tests, manual paths) disables the
    # rotation and keeps the historical behavior byte-for-byte.
    # ---------------------------------------------------------
    YEAR_WINDOW_ROTATION = True
    YEAR_WINDOW_POOL = (4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15)

    # High-voltage, high-curiosity indicators prioritized for YouTube Shorts retention.
    # Deprioritizes dry/academic indicators (e.g. fertilizer use, pupil-teacher ratios,
    # extinction indices) in favor of high-stakes macroeconomic, defense, and tech shifts.
    HIGH_VOLTAGE_INDICATORS = frozenset({
        # Macroeconomic & Wealth Races
        "NY.GDP.MKTP.CD",       # GDP (Current US$)
        "NY.GDP.PCAP.CD",       # GDP Per Capita (Current US$)
        "NGDPD",                # IMF GDP in Billions USD
        "NGDP_RPCH",            # IMF Real GDP Growth %
        "NGDPDPC",              # IMF GDP Per Capita
        "PCPIPCH",              # IMF Inflation
        "gdp_per_capita",       # OWID GDP Per Capita
        "DT.DOD.DECT.CD",       # External Debt Stocks
        # Geopolitical & Military Might
        "MS.MIL.XPND.GD.ZS",    # Military Spending (% of GDP)
        # Digital Revolution & Connectivity
        "IT.NET.USER.ZS",       # Internet Users (% of Population)
        "internet_users",       # OWID Internet Users
        # Energy & Demographic Surge
        "EG.ELC.ACCS.ZS",       # Access to Electricity (%)
        "energy_per_capita",    # OWID Energy Per Capita
        "SP.POP.TOTL",          # Total Population
        "population",           # OWID Population
        # Corporate & Global Sports Dominance
        "corporate_revenues",
        "constructor_standings",
        "driver_standings",
    })
    
    # Quality gates for candidate filtering
    MIN_QUALITY_SCORE = 5.0  # Reject candidates with very low quality
    MIN_VISUAL_POTENTIAL = 10.0  # Minimum visual interest

    # Anti-repeat diversity floor: strict anti-repeat + dedup must
    # NEVER collapse the candidate pool to a single provider/category.
    # Real production failure: 125 quality-validated candidates
    # collapsed to exactly 1 solar_system snapshot, so random/auto
    # topic mode only ever produced solar-system videos.  The rotation
    # stage needs a real choice to spread topics across every
    # indicator.
    MIN_ANTI_REPEAT_POOL = 6

    # When topping the pool back up, a (indicator, story_type) that
    # was published within this many most-recent picks counts as an
    # immediate repeat and is de-prioritized for re-admission.
    ANTI_REPEAT_PICK_RECENCY = 10

    # Dedup combo window: only (provider, indicator, story_type)
    # combos within this many most-recent picks are hard-removed.
    # The previous behavior scanned the ~last 100 records with no
    # date/pick cutoff, permanently blocking months-old combos and --
    # combined with the 30/60/90-day anti-repeat windows -- squeezing
    # the rotation pool down to a single never-used provider.
    DEDUP_RECENCY_WINDOW = 10
    
    # Scoring weights (V2 enhancements)
    QUALITY_WEIGHT = 0.45  # Data quality and story strength
    VISUAL_WEIGHT = 0.30   # Visual interest for YouTube Shorts
    DIVERSITY_WEIGHT = 0.25  # Topic diversity penalty

    # Random selection settings
    #
    # Without randomness, the engine always picks the #1 ranked
    # candidate.  Population data is so complete and visually
    # dramatic that it wins every time, starving the channel of
    # topic variety.  These settings introduce a controlled
    # random component into the final selection.
    #
    # SELECTION_POOL_SIZE: Randomly select from the top N
    #   candidates instead of always taking rank #1.
    # MIN_SELECTION_WEIGHT: Floor on each candidate's selection
    #   probability so lower-ranked candidates in the pool get a
    #   fair chance (higher scores still win more often).
    SELECTION_POOL_SIZE = 5
    MIN_SELECTION_WEIGHT = 0.30

    @classmethod
    def _pick_fetch_years(cls) -> int:
        """Pick the fetch window for ONE indicator (year-window rotation).

        Returns DEFAULT_YEARS when rotation is disabled so behavior
        stays identical to the pre-fix engine.
        """
        if not cls.YEAR_WINDOW_ROTATION or not cls.YEAR_WINDOW_POOL:
            return cls.DEFAULT_YEARS

        return random.choice(list(cls.YEAR_WINDOW_POOL))

    @classmethod
    def generate_topic(
        cls
    ) -> Optional[Dict]:

        candidate = cls.select_best_candidate()

        if candidate is None:
            return None

        return candidate.to_topic_data()

    @classmethod
    def select_best_candidate(
        cls,
        provider_ids: Optional[List[str]] = None,
        max_indicators_per_provider: int = None,
        years: int = None,
        min_countries: int = None
    ) -> Optional[StoryCandidate]:
        """
        SmartStoryEngine V2: Generate multiple candidates from all providers,
        score them transparently, filter weak candidates, and select the best.
        
        Process:
        1. Discover indicators from all providers
        2. Fetch data and generate candidates for each story type
        3. Score candidates with quality, visual, and diversity components
        4. Filter out weak and duplicate candidates
        5. Return the highest-scoring valid candidate
        """

        provider_ids = provider_ids or [
            "worldbank",
            "owid",
            "imf",
            "ai_index",
            "jolpica_f1",
            "openalex",
            "jikan",
            "nhtsa",
            "sec_edgar",
            "solar_system",
            # Key-gated sources added to automatic rotation
            # (investigation A2: they were registered and
            # manual-reachable but never picked randomly).
            # Both skip cleanly via is_configured() when no
            # API key is set.
            "football_data",
            "rawg",
            # NOTE: wikipedia is intentionally NOT in automatic
            # rotation -- it is manual-keyword-only by design
            # (it needs keyword-resolved entity titles as its
            # fetch hint and self-skips without one).
        ]

        max_indicators_per_provider = (
            max_indicators_per_provider
            or cls.MAX_INDICATORS_PER_PROVIDER
        )

        # None means "caller did not pin a window" -> the
        # per-indicator YEAR-WINDOW ROTATION below applies.  An
        # explicit years= argument (tests, manual paths) keeps the
        # historical fixed-window behavior.
        caller_years = years

        years = years or cls.DEFAULT_YEARS
        min_countries = (
            min_countries
            or cls.MIN_COUNTRIES
        )

        candidates = []
        recent_records = cls._recent_records()

        print("\n" + "=" * 70)
        print("Smart Story Engine V2: Multi-Candidate Evaluation")
        print("=" * 70)

        for provider_id in provider_ids:
            try:
                provider = DataProviderRegistry.get(
                    provider_id
                )
            except Exception as error:
                print(
                    f"Skip provider {provider_id}: {error}"
                )
                continue

            #
            # PHASE 6: circuit-breaker gate.  A provider whose
            # upstream source keeps failing is skipped entirely
            # so the run spends its fetch budget on live sources
            # instead of hammering a dead API.
            #
            if not provider_health.is_available(provider_id):

                provider_health.record_skipped(
                    provider_id
                )

                print(
                    f"\n[{provider_id.upper()}] SKIPPED: "
                    f"health monitor reports source DOWN "
                    f"(circuit open)."
                )

                continue

            # Key-gated providers (football_data, rawg): skip
            # cleanly when the API key is not configured instead
            # of burning the fetch budget on guaranteed failures
            # (which would also open the circuit breaker for a
            # configuration problem rather than an outage).
            try:
                provider_configured = provider.is_configured()
            except Exception:
                provider_configured = True

            if not provider_configured:

                print(
                    f"\n[{provider_id.upper()}] SKIPPED: "
                    "API key not configured (set the key in "
                    ".env to enable this source)."
                )

                continue

            all_indicators = provider.list_indicators()

            # HIGH-VOLTAGE INDICATOR CURATION:
            # Prioritizes high-stakes macroeconomic (GDP), defense (military spend),
            # connectivity (internet), energy, and corporate topics over dry/academic indicators.
            high_voltage = [
                ind for ind in all_indicators
                if ind.code in cls.HIGH_VOLTAGE_INDICATORS
            ]
            standard = [
                ind for ind in all_indicators
                if ind.code not in cls.HIGH_VOLTAGE_INDICATORS
            ]

            if high_voltage:
                # Rotate within both pools to preserve diversity while keeping high-voltage first
                hv_offset = random.randrange(len(high_voltage))
                hv_rotated = high_voltage[hv_offset:] + high_voltage[:hv_offset]
                std_offset = random.randrange(len(standard)) if standard else 0
                std_rotated = standard[std_offset:] + standard[:std_offset] if standard else []
                ordered_indicators = hv_rotated + std_rotated
            else:
                offset = random.randrange(len(all_indicators)) if all_indicators else 0
                ordered_indicators = (
                    all_indicators[offset:] + all_indicators[:offset]
                    if all_indicators else []
                )

            if len(ordered_indicators) > max_indicators_per_provider:
                indicators = ordered_indicators[:max_indicators_per_provider]
            else:
                indicators = ordered_indicators

            print(
                f"\n[{provider_id.upper()}] "
                f"Evaluating {len(indicators)} indicators..."
            )

            for indicator in indicators:
                # Fetch with "fastest_growth" to get base data
                # (all story types will be generated from this)
                provider_story = cls.PROVIDER_FETCH_STORY[
                    "fastest_growth"
                ]

                # YEAR-WINDOW ROTATION: vary the dataset window per
                # indicator so the (indicator, year-range) anti-repeat
                # space multiplies.  See YEAR_WINDOW_POOL above for the
                # full root-cause write-up.  When the caller pinned a
                # window explicitly, respect it unchanged.
                if caller_years is not None:
                    fetch_years = years
                else:
                    fetch_years = cls._pick_fetch_years()
                    if fetch_years != cls.DEFAULT_YEARS:
                        print(
                            f"  [WINDOW] {indicator.code}: "
                            f"{fetch_years}-year window "
                            f"(rotated from default "
                            f"{cls.DEFAULT_YEARS})"
                        )

                # AUDIENCE TARGETING: when audience relevance is active
                # and provider supports countries, pass audience countries
                # hint so target geography (e.g. India) is guaranteed in the
                # dataset alongside top global competitors.
                fetch_kwargs = {
                    "indicator_code": indicator.code,
                    "years": fetch_years,
                    "story_type": provider_story,
                    "min_countries": min_countries,
                }
                if getattr(settings, "AUDIENCE_RELEVANCE_ENABLED", True):
                    raw_audience = getattr(settings, "AUDIENCE_COUNTRIES", "")
                    if raw_audience and getattr(provider, "supports_countries", lambda: False)():
                        audience_hint = [c.strip() for c in raw_audience.split(",") if c.strip()]
                        if audience_hint:
                            fetch_kwargs["countries"] = audience_hint

                try:
                    result = provider.fetch_normalized(**fetch_kwargs)
                except Exception as error:

                    provider_health.record_failure(
                        provider_id=provider_id,
                        indicator_code=indicator.code,
                        error=str(error),
                    )

                    print(
                        f"  [X] {indicator.code}: {error}"
                    )

                    err_str = str(error).lower()
                    if not provider_health.is_available(provider_id) or "429" in err_str or "rate limit" in err_str:
                        print(
                            f"  [!] {provider_id.upper()} circuit tripped / rate limited; "
                            "skipping remaining indicators for this provider."
                        )
                        break

                    continue

                if (
                    result.wide_data is None
                    or result.wide_data.empty
                ):
                    provider_health.record_empty(
                        provider_id=provider_id,
                        indicator_code=indicator.code,
                    )
                    continue

                provider_health.record_success(
                    provider_id=provider_id,
                    indicator_code=indicator.code,
                )

                # Generate candidates for ALL story types.  Snapshot
                # providers (solar_system) self-restrict to ranking /
                # head-to-head story types via SUPPORTED_STORY_TYPES.
                generated = cls.generate_candidates(
                    provider_id=provider_id,
                    indicator_code=indicator.code,
                    indicator_name=result.metric_name,
                    category=indicator.category,
                    source_name=result.source_name,
                    source_url=result.source_url,
                    data=result.wide_data,
                    years=years,
                    min_countries=min_countries,
                    snapshot_only=bool(
                        getattr(provider, "snapshot_only", False)
                    ),
                    allowed_story_types=getattr(
                        provider, "SUPPORTED_STORY_TYPES", None
                    ),
                )

                candidates.extend(generated)
                print(
                    f"  [+] {indicator.code}: "
                    f"{len(generated)} candidates generated"
                )

        #
        # PHASE 6: one-line operator visibility into which
        # sources helped this run and which are struggling.
        #
        print(
            "\n[HEALTH] " + provider_health.one_line_summary()
        )

        if not candidates:
            print(
                "\n[ERROR] SmartStoryEngine V2: "
                "No valid candidates found"
            )
            return None

        print(
            f"\n[POOL] Candidate Pool: {len(candidates)} candidates before filtering"
        )

        # V2: Apply quality gates and filtering
        filtered = cls._filter_candidates(
            candidates
        )

        if not filtered:
            print(
                "\n[ERROR] No candidates passed quality gates"
            )
            return None

        print(
            f"[OK] After quality filtering: {len(filtered)} candidates"
        )

        # V2: Apply story quality validation
        quality_validated = cls._validate_story_quality(
            filtered
        )

        if not quality_validated:
            print(
                "\n[ERROR] No candidates passed "
                "story quality validation"
            )
            return None

        print(
            f"[OK] After story quality validation: "
            f"{len(quality_validated)} candidates"
        )

        # V2: Apply anti-repeat validation
        anti_repeat_validated = cls._apply_anti_repeat(
            quality_validated
        )

        if not anti_repeat_validated:
            #
            # CRITICAL FIX: Population dominance avoidance.
            #
            # Originally this fell back to [quality_validated[0]],
            # which is the single highest-quality candidate.
            # Because population data is extremely complete and
            # visually dramatic, it is almost always that #1
            # candidate.  When anti-repeat blocked every candidate,
            # the engine hard-picked population, completely
            # bypassing _select_candidate_with_randomness() and
            # starving the channel of topic variety.
            #
            # Now we fall back to the FULL quality-validated list,
            # so _select_candidate_with_randomness() still provides
            # topic diversity even when anti-repeat rules reject
            # every candidate.
            #
            # Anti-repeat rules are important, but when they block
            # everything, re-selecting quality-validated diversity
            # is better than deterministic population every time.
            #
            print(
                "\n[WARN] Anti-repeat rules exhausted all "
                "unique candidates; "
                "using full quality-validated pool "
                "for topic diversity."
            )
            anti_repeat_validated = list(
                quality_validated
            )

        print(
            f"[OK] After anti-repeat validation: "
            f"{len(anti_repeat_validated)} candidates"
        )

        # V2: Apply duplicate/repetition protection
        final = cls._deduplicate_candidates(
            anti_repeat_validated,
            recent_records
        )

        if not final:
            #
            # CRITICAL FIX: Population dominance avoidance.
            #
            # Same issue as anti-repeat: original fallback was
            # [quality_validated[0]] (best quality = population).
            # Use the full quality-validated pool so topic
            # diversity is preserved.
            #
            print(
                "\n[WARN] All candidates removed by "
                "duplicate protection. "
                "Using full quality-validated pool "
                "for topic diversity."
            )
            final = list(quality_validated)  # Fallback preserves diversity

        print(
            f"[OK] After deduplication: {len(final)} candidates"
        )

        # V2: Apply topic distribution preference
        #
        # This is a SOFT preference for high-interest country
        # stories (USA, Ukraine, Israel, Iran, India, China).
        # It applies a small deterministic multiplier (max 5%)
        # based on the current high-interest ratio in history.
        # Quality always wins: a high-interest candidate with
        # score 60 (boosted to 63) still loses to a global
        # candidate with score 70.
        final = TopicDistributionPreference.apply_preference(
            final,
            recent_records
        )

        print(
            f"[OK] After topic distribution preference: "
            f"{len(final)} candidates"
        )

        # =================================================
        # AUDIENCE RELEVANCE GATE
        #
        # Retention fix.  The published channel's worst videos are
        # comparisons where NEITHER side is recognizable
        # ("Syria vs Namibia", "Uzbekistan CPI" -> 5-40 views) and
        # its best are head-to-heads the audience knows
        # (USA vs China, India vs China).
        #
        # Previously nothing acted on that: the soft distribution
        # multiplier only reordered the list, and the rotator then
        # picked `rng.choice(pool)`, so an obscure-country topic had
        # exactly the same odds as a USA-vs-China one.  Here the
        # pool is restricted to the top-scoring relevance bands
        # BEFORE category rotation, so auto-selection can only pick
        # from audience-relevant / recognizable candidates.
        #
        # The gate widens itself (A -> A+B -> A+B+C) whenever the
        # survivor count would fall below AUDIENCE_MIN_POOL, so the
        # rotation pool never collapses to a single topic.
        # =================================================

        if final:

            audience_relevance.annotate(final, logger=print)

            gated = audience_relevance.filter_pool(
                final,
                logger=print
            )

            if gated:
                final = gated

            print(
                f"[OK] After audience relevance gate: "
                f"{len(final)} candidates"
            )

        # =================================================
        # PERFORMANCE FEEDBACK LOOP
        #
        # video_performance (written by app.youtube.analytics) is
        # now READ: settled videos bias the scores toward the
        # families / indicators / entities that actually retain
        # viewers.  No-op until analytics has been collected.
        # =================================================

        final = cls._apply_performance_bias(final)

        print(
            f"[OK] After performance feedback: "
            f"{len(final)} candidates"
        )

        final = cls._apply_trending_boost(final)

        print(
            f"[OK] After trend candidate boost: "
            f"{len(final)} candidates"
        )

        # Category rotation + random topic selection.
        #
        # The PREVIOUS behavior was "highest score wins": build a
        # score-ranked list, then always pick the #1 candidate
        # (or score-weighted random among the top few).  Because
        # population data is extremely complete and visually
        # dramatic, it ranked #1 almost every run, so the channel
        # only ever made population videos.
        #
        # The NEW behavior:
        #   1. Group valid candidates by TOP-LEVEL CATEGORY.
        #   2. Select a category using recent-category avoidance
        #      (least-recent categories preferred, random within
        #      that band).
        #   3. Within the selected category, randomly select ONE
        #      valid candidate (NOT score-weighted).
        #   4. Apply a random curiosity/story angle.
        #
        # Quality score is a GATE (minimum threshold) that already
        # filtered out weak candidates upstream. It is no longer
        # used to pick the winner.
        best = CategoryRotationSelector.select(
            final,
            recent_records=recent_records,
        )

        if best is None:
            print(
                "\n[ERROR] Category rotation "
                "returned no candidate"
            )
            return None

        print(
            "\n[SELECTED] Smart Story Engine selected: "
            f"{best.topic} "
            f"({best.provider_id}/"
            f"{best.indicator_code}/"
            f"{best.story_type}) "
            f"score={best.score:.2f}"
        )

        return best

    @classmethod
    def _select_candidate_with_randomness(
        cls,
        candidates: List[StoryCandidate]
    ) -> Optional[StoryCandidate]:
        """
        Select the winning candidate with controlled randomness
        AND topic diversity.

        Instead of always returning the #1 ranked candidate, this
        builds a diverse pool from the top candidates:

        1. Take the #1 ranked candidate (best quality).
        2. Add the best candidate from each distinct indicator
           (so population can't dominate the pool).
        3. Randomly select from this diverse pool using
           score-weighted distribution.

        This ensures:
        - Quality is preserved (top candidate always in pool).
        - Topic variety (different indicators get a fair chance).
        - Population can't monopolize the selection.
        """
        if not candidates:
            return None

        # Build a diverse pool: best candidate from each indicator
        best_by_indicator = {}
        for candidate in candidates:
            key = (
                candidate.provider_id,
                candidate.indicator_code,
            )
            if key not in best_by_indicator:
                best_by_indicator[key] = candidate

        # Start with the #1 ranked candidate (best overall quality)
        pool = [candidates[0]]

        # Add the best candidate from each distinct indicator
        for candidate in best_by_indicator.values():
            if candidate not in pool:
                pool.append(candidate)

        # Limit pool size
        pool = pool[:cls.SELECTION_POOL_SIZE]

        max_score = max(
            float(c.score)
            for c in pool
        )

        weights = []
        for candidate in pool:
            if max_score > 0:
                normalized = (
                    float(candidate.score)
                    / max_score
                )
            else:
                normalized = 1.0

            # Ensure every candidate in the pool has a fair chance
            weight = max(
                cls.MIN_SELECTION_WEIGHT,
                normalized
            )
            weights.append(weight)

        return random.choices(
            pool,
            weights=weights,
            k=1
        )[0]

    # ========== V2 Quality & Filtering Methods ==========

    @classmethod
    def _filter_candidates(
        cls,
        candidates: List[StoryCandidate],
        min_valid_entities: int = None
    ) -> List[StoryCandidate]:
        """
        Apply quality gates to reject weak candidates.
        
        Rejects candidates with:
        - Very low quality scores
        - Insufficient data
        - Weak visual potential

        `min_valid_entities` optionally overrides the historical
        3-entity minimum for deliberate entity-comparison datasets
        (e.g. a 2-entity "Tesla vs BYD" head-to-head).  None keeps
        the previous behavior byte-for-byte.
        """
        required_countries = (
            3
            if min_valid_entities is None
            else max(2, int(min_valid_entities))
        )

        filtered = []
        
        for candidate in candidates:
            # Gate 1: Minimum quality score
            if candidate.score < cls.MIN_QUALITY_SCORE:
                continue
            
            # Gate 2: Minimum visual potential
            visual_potential = cls._calculate_visual_potential(
                candidate
            )
            if visual_potential < cls.MIN_VISUAL_POTENTIAL:
                continue
            
            # Gate 3: Data sufficiency
            metrics = candidate.metrics
            valid_countries = metrics.get(
                "number_of_valid_countries", 0
            )
            valid_years = metrics.get(
                "number_of_valid_years", 0
            )
            completeness = metrics.get(
                "data_completeness", 0.0
            )
            
            if (
                valid_countries < required_countries
                or valid_years < 3
                or completeness < 0.40
            ):
                continue
            
            filtered.append(candidate)
        
        # Sort by score
        filtered.sort(
            key=lambda x: x.score,
            reverse=True
        )
        
        return filtered

    @classmethod
    def _validate_story_quality(
        cls,
        candidates: List[StoryCandidate]
    ) -> List[StoryCandidate]:
        """
        Apply StoryQualityValidator as an additional validation layer.

        Rejects candidates whose story claims are not clearly
        supported by the underlying data.
        """
        validated = []

        for candidate in candidates:
            result = StoryQualityValidator.validate(
                candidate.metrics,
                story_type=candidate.story_type,
                title=candidate.topic,
                indicator_name=candidate.indicator_name,
            )

            if result["valid"]:
                validated.append(candidate)
            else:
                print(
                    f"  [QUALITY] Rejected "
                    f"{candidate.provider_id}/"
                    f"{candidate.indicator_code}/"
                    f"{candidate.story_type}: "
                    f"{result['reasons']}"
                )

        return validated

    @classmethod
    def _apply_anti_repeat(
        cls,
        candidates: List[StoryCandidate],
        database=None
    ) -> List[StoryCandidate]:
        """
        Apply AntiRepeatValidator as an additional validation layer.

        Rejects candidates that hard-block against recent history.
        Family repetition is NOT a hard block.

        DIVERSITY FLOOR: hard blocks must never collapse the pool to
        a single provider/category.  Real production failure: 125
        quality-validated candidates collapsed to exactly 1
        solar_system snapshot, so random topic mode only ever emitted
        solar-system videos.  When strict filtering would leave fewer
        than MIN_ANTI_REPEAT_POOL candidates, the pool is topped back
        up from the quality-validated list in a safe order:
            1. candidates whose exact topic was never used;
            2. candidates whose top-level CATEGORY is not yet covered
               by the surviving pool (so the floor cannot re-admit
               six candidates that all belong to one category);
            3. candidates whose (indicator, story_type) was not used
               in the last ANTI_REPEAT_PICK_RECENCY picks.
        The category rotation stage (recency + hard cap + entity
        anti-repeat) provides the actual variety; this floor only
        guarantees it gets a choice.
        """
        allowed = []
        rejected = []

        for candidate in candidates:
            metrics = candidate.metrics

            result = AntiRepeatValidator.check(
                topic=candidate.topic,
                indicator_code=candidate.indicator_code,
                story_type=candidate.story_type,
                start_year=metrics.get("start_year"),
                end_year=metrics.get("end_year"),
                topic_family=candidate.topic_family,
                database=database,
            )

            if result["allowed"]:
                allowed.append(candidate)
            else:
                rejected.append(
                    (candidate, list(result["hard_blocks"] or []))
                )
                for block in result["hard_blocks"]:
                    print(
                        f"  [ANTI-REPEAT] Skip "
                        f"{candidate.provider_id}/"
                        f"{candidate.indicator_code}/"
                        f"{candidate.story_type}: {block}"
                    )

        # Nothing to relax when all candidates passed or the strict
        # pool already meets the floor.
        #
        # FIX (3rd solar_system report): the previous
        # `len(candidates) <= MIN_ANTI_REPEAT_POOL` guard SKIPPED
        # topping up exactly when the pre-filter pool was tiny -- the
        # scenario where the floor matters most.  A 5-candidate pool
        # that anti-repeat reduced to 2 stayed at 2 even though the
        # rejected candidates were available.  Always top up while
        # there is headroom and rejected candidates to re-admit.
        if not rejected or len(allowed) >= cls.MIN_ANTI_REPEAT_POOL:
            return allowed

        # The most recently published (indicator, story_type) pairs;
        # re-admission de-prioritizes combos that would immediately
        # repeat a just-published video.
        recent_pairs = set()

        for record in cls._recent_records()[: cls.ANTI_REPEAT_PICK_RECENCY]:
            if not isinstance(record, dict):
                continue
            code = str(record.get("indicator_code") or "")
            story = str(record.get("story_type") or "")
            if code and story:
                recent_pairs.add((code, story))

        # Top-level categories already covered by the surviving pool;
        # re-admission prefers candidates that ADD a missing category
        # so the floor cannot rebuild a single-category pool.
        covered_categories = {
            family_to_category(
                str(
                    getattr(candidate, "topic_family", "") or ""
                ).strip().lower()
            )
            for candidate in allowed
        }

        def _readmit_key(item):
            candidate, blocks = item
            exact_blocked = "exact_topic" in blocks
            pair_recent = (
                (candidate.indicator_code, candidate.story_type)
                in recent_pairs
            )
            candidate_category = family_to_category(
                str(
                    getattr(candidate, "topic_family", "") or ""
                ).strip().lower()
            )
            # Ascending sort: safest re-admissions come first --
            # 1. no exact-topic repeat (never re-issue a published
            #    title, even for category coverage);
            # 2. candidate ADDS a category missing from the pool;
            # 3. (indicator, story_type) not immediately recent.
            return (
                1 if exact_blocked else 0,
                0 if candidate_category in covered_categories else 1,
                1 if pair_recent else 0,
            )

        rejected.sort(key=_readmit_key)

        re_added = 0

        for candidate, blocks in rejected:
            if len(allowed) >= cls.MIN_ANTI_REPEAT_POOL:
                break
            allowed.append(candidate)
            re_added += 1
            print(
                f"  [ANTI-REPEAT] Re-admitted for pool diversity "
                f"{candidate.provider_id}/"
                f"{candidate.indicator_code}/"
                f"{candidate.story_type} "
                f"(blocks: {', '.join(blocks)})"
            )

        if re_added:
            print(
                "\n[WARN] Anti-repeat left fewer than "
                f"{cls.MIN_ANTI_REPEAT_POOL} candidates; "
                f"re-admitted {re_added} quality-validated "
                "candidates to keep the rotation pool diverse "
                "(exact-topic duplicates still blocked)."
            )

        return allowed

    @classmethod
    def _calculate_visual_potential(
        cls,
        candidate: StoryCandidate
    ) -> float:
        """
        Calculate visual interest score for YouTube Shorts.
        
        Scores based on:
        - Magnitude of change
        - Ranking movement
        - Clear winner/loser
        - Trend consistency
        
        Range: 0-100
        """
        metrics = candidate.metrics
        
        # Components
        magnitude = abs(
            metrics.get("percentage_change", 0.0) or 0.0
        )
        
        rank_movement = abs(
            metrics.get("rank_change", 0.0) or 0.0
        )
        
        leader_separation = metrics.get(
            "leader_separation", 1.0
        )
        
        trend_strength = metrics.get(
            "trend_strength", 0.0
        ) or 0.0
        
        # Calculate components
        magnitude_score = min(
            100.0,
            magnitude * 50.0
        )
        
        rank_score = min(
            100.0,
            rank_movement * 20.0
        )
        
        leader_score = min(
            100.0,
            max(
                0.0,
                (1.0 - leader_separation) * 100.0
            )
        )
        
        trend_score = trend_strength * 100.0

        # A snapshot ranking story has NO temporal movement
        # (magnitude / rank / trend are all zero by construction).
        # Its visual interest is the RANKING spread itself -- how
        # dominant the #1 entity is over the rest -- so score that
        # directly instead of letting the all-zero temporal signals
        # starve the candidate.
        if metrics.get("snapshot_ranking"):
            return min(100.0, max(0.0, leader_score))
        
        # Weighted combination
        visual_potential = (
            magnitude_score * 0.35
            + rank_score * 0.25
            + leader_score * 0.20
            + trend_score * 0.20
        )
        
        return min(100.0, max(0.0, visual_potential))

    @classmethod
    def _deduplicate_candidates(
        cls,
        candidates: List[StoryCandidate],
        recent_records: List[Dict]
    ) -> List[StoryCandidate]:
        """
        Remove candidates that are duplicates or recent repeats.
        
        Criteria for rejection:
        - Same provider + indicator + story_type
        - Same topic family within recent window
        - Similar generated topic text
        """
        if not candidates:
            return []
        
        filtered = []
        removed = []
        recent_combinations = set()

        # FIX: only the most recent picks may hard-remove a candidate.
        # The previous behavior scanned ~the last 100 records with no
        # date/pick cutoff, permanently blocking months-old combos and
        # collapsing the rotation pool down to a single survivor.
        recent_records = (recent_records or [])[
            : cls.DEDUP_RECENCY_WINDOW
        ]

        # Extract recent combinations from history
        for record in recent_records:
            if not isinstance(record, dict):
                continue
            
            provider = str(
                record.get("provider_id", "")
            )
            indicator = str(
                record.get("indicator_code", "")
            )
            story_type = str(
                record.get("story_type", "")
            )
            topic_family = str(
                record.get("topic_family", "")
            )
            
            # Store combinations for checking
            if all([provider, indicator, story_type]):
                recent_combinations.add(
                    (provider, indicator, story_type)
                )
            
            # Also check family (prevent excessive family repeats)
            if topic_family and topic_family != "general":
                recent_combinations.add(
                    f"family:{topic_family}"
                )
        
        # Check each candidate
        for candidate in candidates:
            combo = (
                candidate.provider_id,
                candidate.indicator_code,
                candidate.story_type
            )
            
            # Skip if exact combination was recent
            if combo in recent_combinations:
                print(
                    f"  [DUP] Duplicate: "
                    f"{candidate.provider_id}/"
                    f"{candidate.indicator_code}/"
                    f"{candidate.story_type} (recent)"
                )
                removed.append(candidate)
                continue
            
            # Apply topic family penalty if recent
            family_key = f"family:{candidate.topic_family}"
            if (
                family_key in recent_combinations
                and candidate.topic_family != "general"
            ):
                print(
                    f"  [~] Family repeat: "
                    f"{candidate.topic_family} "
                    f"(score penalty applied)"
                )
            
            filtered.append(candidate)
        
        # Sort again by score after filtering
        filtered.sort(
            key=lambda x: x.score,
            reverse=True
        )

        # DIVERSITY FLOOR, STAGE 2 (3rd solar_system report,
        # investigation A6-4).
        #
        # `_apply_anti_repeat` tops the pool back up to
        # MIN_ANTI_REPEAT_POOL *before* this stage, but this dedup
        # stage then hard-removes exactly those re-admitted
        # candidates again (their (provider, indicator, story_type)
        # combo is in the last DEDUP_RECENCY_WINDOW published
        # records).  The pool could therefore fall back below the
        # floor, and because CategoryRotationSelector derives its
        # eligible-category set from THIS list, a candidate could
        # survive anti-repeat yet never become selectable -- the
        # logged symptom was a diversity-floor re-admission
        # (worldbank/EG.ELC.ACCS.ZS, sec_edgar/...) whose category
        # never appeared in "Eligible categories".
        #
        # Mirror the anti-repeat floor here so the two stages agree:
        # when strict dedup starves the pool, re-admit removed
        # candidates in a safe order (prefer ones whose category the
        # pool does not cover yet), never letting the pool drop
        # below MIN_ANTI_REPEAT_POOL.
        if removed and len(filtered) < cls.MIN_ANTI_REPEAT_POOL:

            def _category_of(candidate) -> str:
                return family_to_category(
                    str(
                        getattr(candidate, "topic_family", "") or ""
                    ).strip().lower()
                )

            covered = {_category_of(candidate) for candidate in filtered}

            removed.sort(
                key=lambda candidate: (
                    0 if _category_of(candidate) not in covered else 1
                )
            )

            re_added = 0

            for candidate in removed:
                if len(filtered) >= cls.MIN_ANTI_REPEAT_POOL:
                    break
                filtered.append(candidate)
                re_added += 1
                print(
                    f"  [DEDUP] Re-admitted for pool diversity "
                    f"{candidate.provider_id}/"
                    f"{candidate.indicator_code}/"
                    f"{candidate.story_type}"
                )

            if re_added:
                print(
                    "\n[WARN] Deduplication left fewer than "
                    f"{cls.MIN_ANTI_REPEAT_POOL} candidates; "
                    f"re-admitted {re_added} quality-validated "
                    "candidates so the rotation pool (and therefore "
                    "the eligible-category set) stays diverse."
                )
        
        return filtered

    @classmethod
    def _apply_performance_bias(
        cls,
        candidates: List[StoryCandidate]
    ) -> List[StoryCandidate]:
        """Re-weight candidates by measured audience retention.

        Closes the feedback loop: `app.youtube.analytics` writes
        per-video performance into `video_performance`, and this
        reads it back so the families / indicators / entities that
        actually hold viewers win more often over time.

        Safe by construction:
          * no settled data  -> returns the list UNCHANGED
          * multiplier bounds -> 0.90 .. 1.15, so one lucky video
            cannot hijack topic selection
        """
        if not candidates:
            return candidates

        try:
            bias = PerformanceBias.load()
        except Exception as error:
            print(
                f"[PERF] Feedback unavailable ({error}); "
                "using static scoring."
            )
            return candidates

        print(bias.describe())

        if bias.samples < 1:
            return candidates

        adjusted = []

        for candidate in candidates:

            multiplier = bias.multiplier(candidate)

            if multiplier != 1.0:
                candidate.score = candidate.score * multiplier
                metrics = getattr(candidate, "metrics", None)
                if isinstance(metrics, dict):
                    metrics["performance_multiplier"] = multiplier

            adjusted.append(candidate)

        # Keep a deterministic order so the rotator sees the
        # strongest-first list (relevance weighting happens inside
        # CategoryRotationSelector).
        adjusted.sort(
            key=lambda item: item.score,
            reverse=True
        )

        return adjusted

    @classmethod
    def _apply_trending_boost(
        cls,
        candidates: List[StoryCandidate]
    ) -> List[StoryCandidate]:
        """Boost candidates matching fresh, vetted trending topics.

        Only active when trend_candidates.json is fresh (< 24h old)
        and carries verified search volume (google_trends or multi-source score >= 3).
        Never treats RSS response count as search volume.
        """
        import os
        import json
        from datetime import datetime, timedelta

        trend_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "trend_candidates.json"
        )
        if not os.path.isfile(trend_path):
            return candidates

        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(trend_path))
            if datetime.now() - mtime > timedelta(hours=24):
                return candidates

            with open(trend_path, "r", encoding="utf-8") as f:
                payload = json.load(f)

            trend_list = payload.get("candidates", [])
            if not isinstance(trend_list, list):
                return candidates

            trusted = []
            for tc in trend_list:
                score = tc.get("score", 0)
                kw = tc.get("keyword", "")
                p_id = tc.get("provider_id", "")
                ind_code = tc.get("indicator_code", "")
                if score >= 3 and p_id and ind_code:
                    trusted.append((p_id, ind_code, kw, score))

            if not trusted:
                return candidates

            boosted_count = 0
            for cand in candidates:
                for p_id, ind_code, kw, t_score in trusted:
                    if cand.provider_id == p_id and cand.indicator_code == ind_code:
                        boost = min(30.0, 15.0 + t_score * 3.0)
                        cand.score += boost
                        if isinstance(cand.metrics, dict):
                            cand.metrics["trending_boost"] = boost
                            cand.metrics["trending_keyword"] = kw
                        boosted_count += 1
                        print(
                            f"  [TREND BOOST] +{boost:.1f} pts to "
                            f"{cand.provider_id}/{cand.indicator_code} "
                            f"(keyword '{kw}', score={cand.score:.1f})"
                        )

            if boosted_count > 0:
                print(
                    f"[TRENDS] Applied search-volume trend boost to {boosted_count} candidates."
                )
                candidates.sort(key=lambda item: item.score, reverse=True)
        except Exception as e:
            print(f"  [TRENDS] Trend boost skipped: {e}")

        return candidates

    @classmethod
    def _show_candidate_ranking(
        cls,
        candidates: List[StoryCandidate]
    ) -> None:
        """
        Display top candidates with transparent scoring breakdown.
        """
        if not candidates:
            return
        
        print("\n[RANKING] Top Candidates (with scoring breakdown):\n")
        
        for idx, candidate in enumerate(candidates[:5], 1):
            metrics = candidate.metrics
            
            quality_score = metrics.get(
                "quality_score", 0.0
            )
            
            visual_potential = cls._calculate_visual_potential(
                candidate
            )
            
            diversity_mult = metrics.get(
                "diversity_multiplier", 1.0
            )
            
            print(
                f"{idx}. {candidate.topic}\n"
                f"   Provider: {candidate.provider_id}/"
                f"{candidate.indicator_code}\n"
                f"   Story Type: {candidate.story_type} "
                f"→ {candidate.chart_type}\n"
                f"   Scores:\n"
                f"     • Quality: {quality_score:.1f}\n"
                f"     • Visual Potential: {visual_potential:.1f}\n"
                f"     • Diversity Mult: {diversity_mult:.3f}\n"
                f"     • Final Score: {candidate.score:.2f}\n"
            )

    @classmethod
    def generate_candidates(
        cls,
        provider_id: str,
        indicator_code: str,
        indicator_name: str,
        category: str,
        source_name: str,
        source_url: str,
        data: pd.DataFrame,
        years: int,
        min_countries: Optional[int] = None,
        min_valid_entities: Optional[int] = None,
        snapshot_only: bool = False,
        allowed_story_types: Optional[set] = None
    ) -> List[StoryCandidate]:

        effective_min_countries = (
            min_countries
            or cls.MIN_COUNTRIES
        )

        # ---------------------------------------------------------
        # Snapshot datasets (Solar System provider) carry a single
        # point in time -- no year-over-year change.  Two things
        # follow from snapshot_only=True:
        #   1. Only the RANKING / HEAD-TO-HEAD story types that a
        #      snapshot can honestly support are generated (the
        #      provider declares them in SUPPORTED_STORY_TYPES).
        #      Time-series story types (fastest_growth, biggest_
        #      decline, rank_climber, rank_decline, trend_over_time)
        #      are NEVER generated for a snapshot -- this is the
        #      code-level enforcement of the ranking-only rule, not
        #      just a docstring.
        #   2. A deliberate 2-entity head-to-head ("Earth vs Mars")
        #      is a valid dataset (quality gates accept >= 2).
        # ---------------------------------------------------------
        if snapshot_only:
            allowed = (
                set(allowed_story_types or {})
                or set(cls.STORY_TO_CHART)
            )
            story_types_for_frame = [
                story_type
                for story_type in cls.STORY_TO_CHART
                if story_type in allowed
            ]
            min_rows = 2 if min_valid_entities == 2 else 3
        else:
            story_types_for_frame = list(cls.STORY_TO_CHART)
            min_rows = 3

        prepared = cls._prepare_data(
            data,
            min_rows=min_rows
        )

        if prepared.empty:
            return []

        metrics = cls._analyze_data(
            prepared,
            min_rows=min_rows
        )

        if not metrics:
            return []

        candidates = []
        topic_family = classify_topic_family(
            indicator_code=indicator_code,
            indicator_name=indicator_name,
            category=category
        )
        recent_records = cls._recent_records()

        for story_type in story_types_for_frame:
            story_metrics = cls._story_metrics(
                story_type,
                metrics
            )

            if story_metrics is None:
                continue

            story_metrics[
                "indicator_code"
            ] = indicator_code
            story_metrics[
                "indicator_name"
            ] = indicator_name
            story_metrics[
                "topic_family"
            ] = topic_family
            story_metrics[
                "data"
            ] = metrics["data"]
            story_metrics[
                "latest_sorted"
            ] = metrics["latest_sorted"]

            # Mark snapshot candidates so downstream gates
            # (visual potential, filtering) score the RANKING
            # spread instead of temporal movement.
            if snapshot_only:
                story_metrics["snapshot_ranking"] = True

            score_details = StoryScorer.score(
                story_type,
                story_metrics,
                recent_records,
                min_valid_entities=min_valid_entities,
                allow_snapshot_rankings=snapshot_only
            )
            score = score_details[
                "final_score"
            ]

            if score <= 0:
                continue

            story_metrics.update(
                score_details
            )

            chart_type = ChartSelector.select_chart(
                story_type,
                story_metrics,
                data
            )

            # Prevent static planetary constants from being selected as historical time-series races
            if (snapshot_only or provider_id == "solar_system") and chart_type in (
                "bar_race", "area", "line", "slope", "top5_change"
            ):
                continue

            story_metrics[
                "selected_chart_type"
            ] = chart_type

            topic = cls._build_topic(
                indicator_name,
                story_type,
                story_metrics
            )

            candidates.append(
                StoryCandidate(
                    provider_id=provider_id,
                    indicator_code=indicator_code,
                    indicator_name=indicator_name,
                    story_type=story_type,
                    chart_type=chart_type,
                    topic_family=topic_family,
                    years=years,
                    category=(
                        category
                        or family_to_category(
                            topic_family
                        ).replace("_", " ").title()
                    ),
                    source_name=source_name,
                    source_url=source_url,
                    topic=topic,
                    score=score,
                    metrics=story_metrics,
                    min_countries=effective_min_countries,
                )
            )

        return candidates

    @staticmethod
    def _prepare_data(
        data: pd.DataFrame,
        min_rows: int = 3
    ) -> pd.DataFrame:

        if data is None or data.empty:
            return pd.DataFrame()

        min_rows = max(2, int(min_rows))

        prepared = data.copy()

        valid_columns = []

        for column in prepared.columns:
            try:
                year = int(
                    str(column).replace(
                        "YR",
                        ""
                    )
                )
            except (
                ValueError,
                TypeError
            ):
                continue

            valid_columns.append(
                (
                    column,
                    year
                )
            )

        if len(valid_columns) < 3:
            return pd.DataFrame()

        prepared = prepared[
            [
                column
                for column, _
                in valid_columns
            ]
        ]

        prepared.columns = [
            year
            for _, year
            in valid_columns
        ]

        prepared = prepared.reindex(
            sorted(
                prepared.columns
            ),
            axis=1
        )

        for column in prepared.columns:
            prepared[column] = pd.to_numeric(
                prepared[column],
                errors="coerce"
            )

        min_required = max(
            3,
            int(
                len(prepared.columns)
                * 0.60
            )
        )

        prepared = prepared.dropna(
            thresh=min_required
        )

        prepared = prepared.ffill(
            axis=1
        ).bfill(
            axis=1
        )

        if len(prepared) < min_rows:
            return pd.DataFrame()

        return prepared

    @classmethod
    def _analyze_data(
        cls,
        data: pd.DataFrame,
        min_rows: int = 3
    ) -> Optional[Dict]:

        years = list(
            data.columns
        )

        start_year = years[0]
        end_year = years[-1]

        start = data[start_year]
        end = data[end_year]

        valid_mask = (
            start.notna()
            & end.notna()
        )

        data = data.loc[
            valid_mask
        ]

        min_rows = max(2, int(min_rows))
        if len(data) < min_rows:
            return None

        start = data[start_year]
        end = data[end_year]

        absolute_change = end - start

        percent_change = pd.Series(
            index=data.index,
            dtype=float
        )

        safe_denominator = (
            start.notna()
            & (start.abs() > 1e-9)
        )

        percent_change.loc[
            safe_denominator
        ] = (
            absolute_change.loc[
                safe_denominator
            ]
            / start.loc[
                safe_denominator
            ].abs()
        )

        start_rank = start.rank(
            method="first",
            ascending=False
        )

        end_rank = end.rank(
            method="first",
            ascending=False
        )

        rank_change = start_rank - end_rank

        completeness = float(
            data.notna().sum().sum()
        ) / float(
            data.shape[0]
            * data.shape[1]
        )

        latest_sorted = end.dropna().sort_values(
            ascending=False
        )

        if len(latest_sorted) >= 2:
            leader_gap = float(
                latest_sorted.iloc[0]
                - latest_sorted.iloc[1]
            )
            leader_base = max(
                abs(float(latest_sorted.iloc[0])),
                1e-9
            )
            leader_separation = (
                leader_gap
                / leader_base
            )
        else:
            leader_separation = 1.0

        trends = {}

        x = pd.Series(
            range(
                len(years)
            ),
            dtype=float
        )

        for index, row in data.iterrows():
            values = row.astype(float)

            if values.nunique() < 2:
                trends[index] = 0.0
                continue

            correlation = x.corr(
                pd.Series(
                    values.values,
                    dtype=float
                )
            )

            if pd.isna(correlation):
                correlation = 0.0

            trends[index] = abs(
                float(correlation)
            )

        trend_strength = pd.Series(
            trends
        )

        return {
            "data": data,
            "start_year": start_year,
            "end_year": end_year,
            "start": start,
            "end": end,
            "absolute_change": absolute_change,
            "percent_change": percent_change,
            "start_rank": start_rank,
            "end_rank": end_rank,
            "rank_change": rank_change,
            "valid_countries": int(len(data)),
            "valid_years": int(len(years)),
            "data_completeness": completeness,
            "leader_separation": float(
                leader_separation
            ),
            "trend_strength": trend_strength,
            "latest_sorted": latest_sorted,
        }

    @classmethod
    def _story_metrics(
        cls,
        story_type: str,
        metrics: Dict
    ) -> Optional[Dict]:

        if story_type == "fastest_growth":
            series = metrics[
                "percent_change"
            ].dropna()

            series = series[
                series > 0
            ]

            if series.empty:
                return None

            entity = series.idxmax()
            return cls._entity_metrics(
                entity,
                metrics,
                story_type
            )

        if story_type == "biggest_decline":
            series = metrics[
                "absolute_change"
            ].dropna()

            series = series[
                series < 0
            ]

            if series.empty:
                return None

            entity = series.idxmin()
            return cls._entity_metrics(
                entity,
                metrics,
                story_type
            )

        if story_type == "rank_climber":
            series = metrics[
                "rank_change"
            ].dropna()

            series = series[
                series > 0
            ]

            if series.empty:
                return None

            entity = series.idxmax()
            return cls._entity_metrics(
                entity,
                metrics,
                story_type
            )

        if story_type == "rank_decline":
            series = metrics[
                "rank_change"
            ].dropna()

            series = series[
                series < 0
            ]

            if series.empty:
                return None

            entity = series.idxmin()
            return cls._entity_metrics(
                entity,
                metrics,
                story_type
            )

        if story_type == "current_leader":
            latest = metrics[
                "latest_sorted"
            ]

            if latest.empty:
                return None

            entity = latest.index[0]
            return cls._entity_metrics(
                entity,
                metrics,
                story_type
            )

        if story_type == "leader_challenge":
            latest = metrics[
                "latest_sorted"
            ]

            if len(latest) < 2:
                return None

            leader = latest.index[0]
            challenger = latest.index[1]

            result = cls._entity_metrics(
                challenger,
                metrics,
                story_type
            )

            result[
                "leader"
            ] = cls._label(
                leader
            )
            result[
                "challenger"
            ] = cls._label(
                challenger
            )

            return result

        if story_type == "trend_over_time":
            series = metrics[
                "trend_strength"
            ].dropna()

            if series.empty:
                return None

            entity = series.idxmax()
            return cls._entity_metrics(
                entity,
                metrics,
                story_type
            )

        return None

    @classmethod
    def _entity_metrics(
        cls,
        entity,
        metrics: Dict,
        story_type: str
    ) -> Dict:

        return {
            "entity": cls._label(entity),
            "start_year": int(
                metrics["start_year"]
            ),
            "end_year": int(
                metrics["end_year"]
            ),
            "start_value": cls._safe_float(
                metrics["start"].loc[
                    entity
                ]
            ),
            "end_value": cls._safe_float(
                metrics["end"].loc[
                    entity
                ]
            ),
            "absolute_change": cls._safe_float(
                metrics[
                    "absolute_change"
                ].loc[
                    entity
                ]
            ),
            "percentage_change": cls._safe_float(
                metrics[
                    "percent_change"
                ].loc[
                    entity
                ]
            ),
            "start_rank": cls._safe_float(
                metrics[
                    "start_rank"
                ].loc[
                    entity
                ]
            ),
            "end_rank": cls._safe_float(
                metrics[
                    "end_rank"
                ].loc[
                    entity
                ]
            ),
            "rank_change": cls._safe_float(
                metrics[
                    "rank_change"
                ].loc[
                    entity
                ]
            ),
            "number_of_valid_countries": metrics[
                "valid_countries"
            ],
            "number_of_valid_years": metrics[
                "valid_years"
            ],
            "meaningful_observations": int(
                metrics[
                    "data"
                ].notna().sum().sum()
            ),
            "data_completeness": cls._safe_float(
                metrics[
                    "data_completeness"
                ]
            ),
            "leader_separation": cls._safe_float(
                metrics[
                    "leader_separation"
                ]
            ),
            "trend_strength": cls._safe_float(
                metrics[
                    "trend_strength"
                ].loc[
                    entity
                ]
            ),
            "story_type": story_type,
        }

    @classmethod
    def score_story(
        cls,
        story_type: str,
        metrics: Dict
    ) -> float:

        return StoryScorer.score(
            story_type,
            metrics,
            cls._recent_records()
        )[
            "final_score"
        ]

    @staticmethod
    def _recent_records():

        try:
            return db.get_recent_records(
                limit=100
            )
        except Exception:
            return []

    @staticmethod
    def _uniqueness_multiplier(
        indicator_code,
        story_type
    ) -> float:

        if not indicator_code:
            return 1.0

        try:
            records = db.get_recent_records(
                limit=100
            )
        except Exception:
            return 1.0

        for record in records:
            if not isinstance(
                record,
                dict
            ):
                continue

            if (
                str(
                    record.get(
                        "indicator_code",
                        ""
                    )
                ) == str(indicator_code)
                and str(
                    record.get(
                        "story_type",
                        ""
                    )
                ) == str(story_type)
            ):
                return 0.55

        return 1.0

    @staticmethod
    def _build_topic(
        indicator_name: str,
        story_type: str,
        metrics: Dict
    ) -> str:

        entity = metrics.get(
            "entity",
            "Countries"
        )

        templates = {
            "fastest_growth":
                f"{indicator_name}: Fastest Growth",
            "biggest_decline":
                f"{indicator_name}: Biggest Declines",
            "rank_climber":
                f"{indicator_name}: Rank Climbers",
            "rank_decline":
                f"{indicator_name}: Ranking Drops",
            "current_leader":
                f"{indicator_name}: Current Leader",
            "leader_challenge":
                f"{indicator_name}: Leader Challenge",
            "trend_over_time":
                f"{entity} {indicator_name} Trend",
        }

        return templates.get(
            story_type,
            f"{indicator_name}: Data Story"
        )

    @staticmethod
    def _safe_float(value):

        if pd.isna(value):
            return None

        return float(value)

    @staticmethod
    def _label(index_value) -> str:

        if isinstance(
            index_value,
            tuple
        ):
            if len(index_value) >= 2:
                return str(
                    index_value[1]
                )
            if index_value:
                return str(
                    index_value[0]
                )

        return str(index_value)
