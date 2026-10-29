"""
Category Rotation & Random Topic Selection

Replaces the previous "highest score wins" behavior with a
pure category-rotation + random-selection system:

1. Validate & filter candidates (quality = a GATE, not the
   winner criterion) - this remains in SmartStoryEngine.
2. Group the remaining (valid, non-recent) candidates by
   TOP-LEVEL CATEGORY.
3. Select a category using recent-category avoidance:
   - Categories used recently (within RECENT_CATEGORY_WINDOW)
     are deprioritized.
   - When multiple eligible categories exist, the least-recent
     categories are preferred but selection is RANDOM among
     them (no fixed order).
   - If the pool is small, relax the window gracefully.
4. Within the selected category, randomly select ONE valid
   candidate (equal chance - NOT score-weighted).
5. Apply a random curiosity/story angle to the topic text.

Quality score is NEVER used to choose the winner. It is only
used as a minimum validation threshold (done upstream).

Real-data rule: a category must have at least one real
candidate in the pool to be eligible. Categories with no
provider data are never fabricated.
"""
import random
from typing import Dict, List, Optional

from app.config import settings
from app.topic.topic_families import (
    UNSUPPORTED_CATEGORIES,
    family_to_category,
)


class CategoryRotationSelector:
    """Select a candidate using category rotation + randomness."""

    # Recent-category memory: a category used within this many
    # previous selections is temporarily deprioritized.
    RECENT_CATEGORY_WINDOW = 5

    # Number of least-recent categories to randomly choose from.
    # 0 = always pick the single least-recent category.
    RANDOM_CATEGORY_CHOICES = 3

    # Minimum number of candidates a category must have in the
    # pool to be considered "eligible".
    MIN_CANDIDATES_PER_CATEGORY = 1

    # Anti-repeat depletion leaves some categories with a single
    # surviving topic.  When ANY category still has at least this
    # many candidates, thin (single-candidate) categories are
    # excluded from selection so the rotator does not
    # deterministically re-pick the same lone survivor.
    PREFERRED_POOL_SIZE = 2

    # HARD CAP: maximum times a category can appear in the last
    # HARD_CAP_WINDOW picks.  This prevents the recency-only scoring
    # from letting a single category dominate (real production bug:
    # space_science appeared 4/6 consecutive times).  Set to 0 to
    # disable.
    HARD_CAP_MAX_IN_WINDOW = 2
    HARD_CAP_WINDOW = 8

    # Module-level recent category history for production use.
    # Reset on demand via reset() for tests.
    _recent_categories: List[str] = []

    # Module-level recent entity history (prevents same entity from
    # appearing in consecutive videos even across different categories).
    _recent_entities: List[str] = []
    MAX_ENTITY_HISTORY = 10
    ENTITY_REPEAT_WINDOW = 5  # Don't repeat entity within this many picks

    # =====================================================
    # RECENT CATEGORY MEMORY
    # =====================================================

    @classmethod
    def reset(cls) -> None:
        """Reset the in-memory recent-category history (tests)."""
        cls._recent_categories = []

    @classmethod
    def recent_categories(cls) -> List[str]:
        """Return the current recent category history (copy)."""
        return list(cls._recent_categories)

    @classmethod
    def _derive_recent_categories(
        cls,
        recent_records: List[Dict]
    ) -> List[str]:
        """
        Derive recent top-level categories from DB history.

        Each record may carry topic_family (production saves it)
        or indicator_code (older records).  We derive the family
        via the shared classifier when only the code is present.

        Contract (FIX, investigation A6-1): records arrive
        NEWEST-FIRST (Database.get_recent_records uses
        "ORDER BY id DESC").  Scoring in
        _score_category_recency assumes CHRONOLOGICAL order
        (oldest -> newest, recent[-1] == the actual last pick),
        so the derived list is reversed and WINDOWED to the most
        recent RECENT_CATEGORY_WINDOW picks.  Keeping the window
        strictly smaller than the number of eligible categories
        guarantees a non-empty "not recent" band (score 0) with
        genuine random choice inside it, instead of every
        category carrying a small deterministic recency score.
        """
        from app.topic.topic_families import classify_topic_family

        derived = []

        for record in recent_records or []:
            if not isinstance(record, dict):
                continue

            topic_family = str(
                record.get("topic_family", "") or ""
            ).strip().lower()

            if not topic_family:
                indicator_code = str(
                    record.get("indicator_code", "") or ""
                ).strip()
                if indicator_code:
                    topic_family = classify_topic_family(
                        indicator_code
                    )

            if not topic_family:
                continue

            category = family_to_category(topic_family)
            derived.append(category)

        # newest-first input -> chronological output, then keep
        # only the most recent window entries.
        derived.reverse()

        return derived[-cls.RECENT_CATEGORY_WINDOW:]

    # =====================================================
    # CATEGORY SELECTION
    # =====================================================

    @classmethod
    def _group_by_category(
        cls,
        candidates: List
    ) -> Dict[str, List]:
        """
        Group validated candidates by top-level category.
        Skips unsupported categories (never fabricated).
        """
        groups: Dict[str, List] = {}

        for candidate in candidates:
            family = str(
                getattr(candidate, "topic_family", "")
                or ""
            ).strip().lower()

            category = family_to_category(family)

            if category in UNSUPPORTED_CATEGORIES:
                continue

            groups.setdefault(category, []).append(candidate)

        return groups

    @classmethod
    def _score_category_recency(
        cls,
        category: str,
        recent: List[str]
    ) -> int:
        """
        Recency score: lower is better.

        category not in recent              -> 0 (preferred)
        category is the LAST selected       -> very high penalty
        category older in recent window     -> medium penalty
        """
        if category not in recent:
            return 0

        # The immediately-previous category gets a strong penalty
        # so it is excluded whenever other categories exist.
        if recent and recent[-1] == category:
            return 10_000

        # Older recent entries get a small, bounded penalty so a
        # category outside the recent window returns to 0 (eligible).
        position = recent.index(category)
        return len(recent) - position

    @classmethod
    def _select_category(
        cls,
        categories: List[str],
        recent: List[str],
        rng: random.Random,
        logger: Optional[callable] = None
    ) -> Optional[str]:
        """
        Pick the best category using recency avoidance + randomness.

        - Sort categories by recency score (ascending).
        - Take the least-recent cats (top RANDOM_CATEGORY_CHOICES).
        - Randomly pick one of those.
        """
        if not categories:
            return None

        scored = sorted(
            (
                (cls._score_category_recency(cat, recent), cat)
                for cat in categories
            ),
            key=lambda item: (item[0], item[1]),
        )

        best_score = scored[0][0]

        # Every category that ties with the best (least-recent)
        # is a candidate.  This gives ALL eligible categories a
        # genuine random chance, not just the first few that
        # happen to sort first.  (The previous band of 3
        # starved otherwise-eligible categories.)
        candidates_band = [
            cat
            for score, cat in scored
            if score == best_score
        ]

        if len(candidates_band) < 1:
            candidates_band = [scored[0][1]]

        selected = rng.choice(candidates_band)

        if logger:
            logger(
                f"[CATEGORY ROTATION]\n"
                f"Recent categories: {recent}\n"
                f"Eligible categories: {categories}\n"
                f"Selected category: {selected}"
            )

        return selected

    @classmethod
    def _apply_story_angle(
        cls,
        candidate,
        rng: random.Random
    ) -> str:
        """
        Apply a random curiosity/story angle to the candidate topic.

        The angle makes the topic feel like a question/story
        rather than a dry dataset label.  The underlying metrics
        and data stay untouched - only the topic title text is
        reframed.
        """
        topic = str(
            getattr(candidate, "topic", "")
            or ""
        ).strip()

        entity = str(
            (candidate.metrics or {}).get("entity", "")
            or ""
        ).strip()

        indicator = str(
            getattr(candidate, "indicator_name", "")
            or getattr(candidate, "indicator_code", "")
            or ""
        ).strip()

        angles = [
            f"Who Leads in {indicator}?",
            f"Which Country Dominates {indicator}?",
            f"{entity if entity else 'Nations'} in {indicator}: Who Is Rising?",
            f"The {indicator} Story: Big Numbers Behind the Trend",
            f"Country vs Country: {indicator} Compared",
            f"Where Is {indicator} Growing Fastest?",
            f"What Changed Most in {indicator}?",
            f"The Surprising Truth About {indicator}",
        ]

        # Attribute the original indicator name for clarity
        return f"{topic} | (angle: {rng.choice(angles)})"

    # =====================================================
    # HARD CAP ENFORCEMENT
    # =====================================================

    @classmethod
    def _enforce_hard_cap(
        cls,
        category: str,
        eligible_categories: List[str],
        recent: List[str],
        rng: random.Random,
        groups: Dict[str, List],
    ) -> str:
        """Enforce hard cap: no category more than HARD_CAP_MAX_IN_WINDOW
        times in the last HARD_CAP_WINDOW picks.

        If the selected category has hit the cap, try the next-best
        alternative from the eligible categories.  If ALL categories
        have hit the cap (small pool), relax the constraint and return
        the original.
        """
        if cls.HARD_CAP_MAX_IN_WINDOW <= 0:
            return category

        # FIX (3rd solar_system report): `recent` is now the MERGED
        # DB-derived + in-session history passed down from select().
        # The previous implementation read ONLY
        # cls._recent_categories, which is empty in every fresh
        # production process (run.py generates one video per
        # process), so the cap was blind to cross-run repetition --
        # e.g. space_science appearing 5x in the last 8 published
        # videos was invisible to it and it kept winning.
        recent_history = list(recent or [])[-cls.HARD_CAP_WINDOW:]
        count = recent_history.count(category)

        if count < cls.HARD_CAP_MAX_IN_WINDOW:
            return category  # Not capped

        # Category hit the cap — find an alternative
        # Sort eligible categories by recency score (ascending) so we
        # pick the least-recent alternative
        scored = []
        for cat in eligible_categories:
            cat_count = recent_history.count(cat)
            if cat_count < cls.HARD_CAP_MAX_IN_WINDOW:
                # Score: prefer categories with fewer recent picks
                scored.append((cat_count, cat))

        if scored:
            scored.sort(key=lambda x: (x[0], x[1]))
            best_count = scored[0][0]
            # Randomly pick among the best alternatives
            alternatives = [cat for cnt, cat in scored if cnt == best_count]
            return rng.choice(alternatives)

        # All categories hit the cap (very small pool) — relax
        return category

    @classmethod
    def _filter_recent_entities(cls, pool: List) -> List:
        """Filter out candidates whose entity was used recently.

        Prevents the same entity (company, country, topic) from
        appearing in consecutive videos even when categories differ.
        """
        if not pool or cls.ENTITY_REPEAT_WINDOW <= 0:
            return pool

        recent = set(cls._recent_entities[-cls.ENTITY_REPEAT_WINDOW:])
        if not recent:
            return pool

        # Try to find candidates whose entity is NOT in recent history
        fresh = []
        for candidate in pool:
            entity = cls._extract_entity(candidate)
            if entity and entity in recent:
                continue  # Skip — entity was used recently
            fresh.append(candidate)

        # If all candidates are "fresh", return original pool
        # (better to pick something than nothing)
        return fresh if fresh else pool

    @staticmethod
    def _extract_entity(candidate) -> Optional[str]:
        """Extract the primary entity name from a candidate."""
        # Try metrics entity
        metrics = getattr(candidate, "metrics", {}) or {}
        if isinstance(metrics, dict):
            entity = metrics.get("entity")
            if entity:
                return str(entity).strip().lower()

        # Try candidate topic/indicator
        topic = str(getattr(candidate, "topic", "") or "").strip()
        if topic:
            # Extract first word(s) as entity hint
            return topic.split()[0].lower() if topic else None

        return None

    @classmethod
    def _track_selected_entity(cls, candidate) -> None:
        """Record the entity of the selected candidate for anti-repeat."""
        entity = cls._extract_entity(candidate)
        if entity:
            cls._recent_entities.append(entity)
            # Trim to max history
            if len(cls._recent_entities) > cls.MAX_ENTITY_HISTORY:
                cls._recent_entities = cls._recent_entities[-cls.MAX_ENTITY_HISTORY:]

    # =====================================================
    # MAIN SELECTION ENTRY POINT
    # =====================================================

    @classmethod
    def select(
        cls,
        candidates: List,
        recent_records: Optional[List[Dict]] = None,
        seed: Optional[int] = None,
        logger=None,
    ):
        """
        Main selection: category rotation + random candidate.

        Args:
            candidates: quality/anti-repeat/deduplicated list.
            recent_records: recent DB history (used to derive
                recent categories).
            seed: optional random seed (tests).
            logger: optional callable to receive log output.

        Returns:
            The selected candidate object, or None if no
            candidate is available.
        """
        if not candidates:
            return None

        rng = random.Random(seed) if seed is not None else random.Random()
        logger = logger or print

        # Rebuild recent categories from DB history + in-memory.
        #
        # FIX (investigation A6-1): the DB-derived list used to be
        # passed in FULL (~100 entries).  With only ~6 eligible
        # categories every category appeared in that list, every
        # recency score became a small non-zero value, and the
        # category with the OLDEST last occurrence deterministically
        # won the tie-band -- 15/15 live runs picked the same
        # category.  Only the most recent picks may influence
        # scoring: a sliding window smaller than the number of
        # eligible categories guarantees a non-empty "not recent"
        # band (score 0) with genuine random choice inside it.
        recent_from_records = cls._derive_recent_categories(
            recent_records
        )

        recent = list(
            recent_from_records[-cls.RECENT_CATEGORY_WINDOW:]
        )

        # FIX (investigation A6-2): the previous merge dropped
        # every in-memory pick (`if cat not in recent` -- the DB
        # history already contained them), so the true last pick
        # never sat at recent[-1] and the 10,000
        # "immediately-previous" penalty never fired.  Append
        # in-session picks UNCONDITIONALLY, then re-trim to the
        # window so the actual most-recent selection is the last
        # entry.
        for cat in cls._recent_categories:
            recent.append(cat)

        recent = recent[-cls.RECENT_CATEGORY_WINDOW:]

        # Full merged history for the HARD CAP and for operator
        # logging.  The recency SCORING window is re-trimmed below
        # (dynamic window), but the cap must see the real last-8
        # picks across runs -- otherwise a category that dominated
        # the published channel (e.g. space_science) is invisible
        # to the cap in every fresh process.
        recent_full = list(recent)[-cls.HARD_CAP_WINDOW:]

        # Group valid candidates by category
        groups = cls._group_by_category(candidates)

        eligible_categories = sorted(
            cat
            for cat, items in groups.items()
            if len(items) >= cls.MIN_CANDIDATES_PER_CATEGORY
        )

        if not eligible_categories:
            return None

        # -------------------------------------------------
        # STRATEGIC PILLAR FILTERING
        # Focus rotation on high-retention audience pillars
        # (Geopolitics & Power, Tech & Disruption) while falling
        # back gracefully if no pillar category has candidates.
        # -------------------------------------------------
        if getattr(settings, "STRATEGIC_PILLARS_ONLY", False):
            pillar_list = [
                c.strip().lower()
                for c in getattr(settings, "PILLAR_CATEGORIES", "").split(",")
                if c.strip()
            ]
            if pillar_list:
                pillar_eligible = [
                    cat for cat in eligible_categories
                    if cat in pillar_list
                ]
                if pillar_eligible:
                    if logger:
                        logger(
                            f"[STRATEGIC PILLARS] Focused {len(eligible_categories)} categories "
                            f"to {len(pillar_eligible)} pillar categories: {pillar_eligible}"
                        )
                    eligible_categories = pillar_eligible

        # FIX (investigation A6-1, part 2): the window must leave
        # GENUINE GAPS.  With W eligible categories a static window
        # of 5 leaves exactly one score-0 category when W == 6 --
        # the "random" band collapses to a single deterministic
        # option.  Re-trim the window to (eligible - 2) so at least
        # TWO categories always sit at score 0 and the choice among
        # them is genuinely random, while the true last pick always
        # survives the trim (it is recent[-1]) so the immediate-
        # repeat penalty keeps working.
        dynamic_window = max(
            1,
            min(
                cls.RECENT_CATEGORY_WINDOW,
                len(eligible_categories) - 2,
            ),
        )

        recent = recent[-dynamic_window:]

        # Operator clarity (3rd solar_system report): the log used
        # to print ONLY the post-trim scoring window, which with a
        # small eligible set shows a single entry (e.g.
        # "Recent categories: ['gaming']") and looks like broken
        # history tracking.  Print the full merged window too.
        if logger:
            logger(
                f"[CATEGORY ROTATION] Recent history "
                f"(full window, DB + in-session, last "
                f"{len(recent_full)} picks): {recent_full}"
            )

        # FIX (investigation A6-3): when anti-repeat filtering
        # leaves a category with a single surviving candidate,
        # picking that category back-to-back deterministically
        # re-issues the same story.  Thin (single-candidate)
        # categories stay eligible -- otherwise they are permanently
        # starved (space_science/gaming in the live pool) -- but the
        # immediately-last-picked one is excluded to prevent the
        # deterministic re-issue.  _select_category still rotates +
        # randomizes within the eligible set.
        preferred_categories = [
            cat
            for cat in eligible_categories
            if len(groups[cat]) >= cls.PREFERRED_POOL_SIZE
        ]

        if preferred_categories:
            # Include thin (single-candidate) categories UNLESS they
            # are the immediately-last-selected one.  The previous
            # rule excluded ALL thin categories whenever any category
            # had >=2 candidates, which permanently starved real
            # single-survivor categories (space_science, gaming in the
            # live pool) -- random mode ended up alternating between
            # the same pair of fat categories and never made other
            # indicators.  Recency already gives the immediate-prev
            # category a 10,000 penalty, so the only determinism to
            # guard here is re-picking the same lone topic
            # back-to-back.
            last_recent = (
                recent[-1]
                if recent
                else None
            )

            selection_categories = []
            seen = set()

            for cat in eligible_categories:

                if cat in seen:
                    continue

                thin = (
                    len(groups[cat])
                    < cls.PREFERRED_POOL_SIZE
                )

                if thin and cat == last_recent:
                    continue

                seen.add(cat)
                selection_categories.append(cat)

            excluded = sorted(
                set(eligible_categories)
                - set(selection_categories)
            )

            if logger and excluded:

                logger(
                    "[CATEGORY ROTATION] Excluded (last-picked "
                    "lone survivor, avoid immediate re-issue): "
                    f"{excluded}"
                )

        else:

            selection_categories = eligible_categories

        # Select category (rotation + randomness)
        category = cls._select_category(
            selection_categories,
            recent,
            rng,
            logger=logger
        )

        if not category:
            return None

        # HARD CAP: if this category has been picked too many times
        # recently, pick the next-best alternative.  This prevents
        # the recency-only scoring from letting a single category
        # dominate (real production bug: space_science 4/6 times).
        # `recent_full` carries the merged DB + in-session history
        # so the cap also works across process restarts.
        category = cls._enforce_hard_cap(
            category, selection_categories, recent_full, rng, groups
        )

        pool = groups[category]

        # Remove already-seen recent topic/concepts:
        # we keep anti-repeat upstream; here we only avoid
        # exact duplicates within this run.
        logger(
            f"[TOPIC RANDOM SELECTION]\n"
            f"Eligible topics in {category}: {len(pool)}\n"
        )

        # =================================================
        # RELEVANCE-WEIGHTED PICK (retention fix).
        #
        # This used to be a flat `rng.choice(pool)`, which gave an
        # obscure-country candidate (band C) exactly the same odds as
        # an audience-geography / rivalry candidate (band A) inside
        # the same category -- the direct cause of "Syria vs Namibia"
        # style videos on a channel whose best performers are
        # USA-vs-China / India-vs-China head-to-heads.
        #
        # ORDER MATTERS: the band must be computed on the FULL
        # category pool, BEFORE the entity anti-repeat filter.  Doing
        # it after lets the entity filter strip every band-A
        # candidate (all of them "recent") and silently degrade the
        # best band to C, which reintroduced obscure picks.
        #
        # Steps:
        #   1. best band present in the category wins;
        #   2. entity anti-repeat is applied WITHIN that band;
        #   3. if the entity filter empties the band, fall back to
        #      the band pool (and finally to the full pool).
        #
        # Randomness is preserved, so the channel does not become
        # deterministic.
        # =================================================

        try:
            bands = [
                str(
                    (getattr(candidate, "metrics", None) or {})
                    .get("audience_band", "")
                )
                for candidate in pool
            ]
        except Exception:
            bands = []

        selection_pool = pool

        if any(bands):

            best_band = min(band for band in bands if band)

            band_pool = [
                candidate
                for candidate, band in zip(pool, bands)
                if band == best_band
            ]

            if band_pool:
                selection_pool = band_pool

                # Entity anti-repeat only WITHIN the best band.
                filtered_band = cls._filter_recent_entities(
                    list(band_pool)
                )

                if filtered_band:
                    selection_pool = filtered_band

            logger(
                "  [RELEVANCE] Best band in this category: "
                f"{best_band} "
                f"({len(selection_pool)}/{len(pool)} candidates)"
            )

        else:

            # No relevance signal (tests / manual paths): keep the
            # historical behaviour exactly.
            selection_pool = cls._filter_recent_entities(list(pool))

            if not selection_pool:
                selection_pool = pool

        # Transparent weighted selection using existing quality metrics, audience relevance,
        # and data completeness rather than uniform random choice.
        weights = []
        for cand in selection_pool:
            base_score = max(1.0, float(getattr(cand, "score", 1.0) or 1.0))
            cand_metrics = getattr(cand, "metrics", {}) or {}
            aud_score = float(cand_metrics.get("audience_score", 50.0) or 50.0)
            completeness = float(cand_metrics.get("data_completeness", 0.8) or 0.8)
            w = base_score * (aud_score / 50.0) * (0.5 + 0.5 * completeness)
            weights.append(max(0.1, w))

        selected = rng.choices(selection_pool, weights=weights, k=1)[0]
        sel_idx = selection_pool.index(selected)
        sel_pct = (weights[sel_idx] / sum(weights)) * 100.0

        if logger:
            logger(
                f"  Selected via transparent quality/audience weighting: \"{selected.topic}\" "
                f"(provider={selected.provider_id}, indicator={selected.indicator_code}, "
                f"score={selected.score:.1f}, selection_prob={sel_pct:.1f}%)"
            )

        # Track the selected entity
        cls._track_selected_entity(selected)

        # Apply a random curiosity/story angle to the topic text
        # (does not touch underlying metrics/data).
        selected.topic = cls._apply_story_angle(
            selected,
            rng
        )

        # Store in recent category memory.
        #
        # IMPORTANT: trim to RECENT_CATEGORY_WINDOW (not 2x).
        # With a window of 5, a category becomes eligible again
        # after 5 other selections.  Keeping 2x (10) with a pool
        # of exactly 10 categories would make ALL of them
        # "recent", locking the rotator into a fixed cycle.
        current_recent = cls.recent_categories()
        current_recent.append(category)
        if len(current_recent) > cls.RECENT_CATEGORY_WINDOW:
            current_recent = (
                current_recent[-(cls.RECENT_CATEGORY_WINDOW):]
            )
        cls._recent_categories = current_recent

        return selected
