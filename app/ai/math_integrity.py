"""Deterministic mathematical integrity and claim validation for scripts.

Validates numerical claims in generated scripts against the actual validated
provider DataFrame (wide_data), ensuring that:
1. Direction of change (increase vs decrease) matches ground truth.
2. Magnitudes of absolute and percentage changes match ground truth within rounding tolerances.
3. Zero baselines are not divided by zero or reported as percentages.
4. "Percentage points" is classified as absolute delta, not relative %.
5. Absolute point changes on rate/percentage indicators are not confused with relative %.
6. Internal consistency (stated start and end values match stated difference).
7. Multi-entity compound sentences attribute claims using clause boundaries.
8. Unverifiable or ambiguous claims fail closed rather than assuming false attribution.
9. Non-change numbers (years, durations, ranks, counts, denominators) are preserved.
10. Controlled surgical repair/retry is performed on mathematical errors without blind regex.
"""

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.time_labels import coerce_year_label


class MathIntegrityError(Exception):
    """Raised when script math cannot be validated or safely repaired."""
    pass


@dataclass
class EntityGroundTruth:
    entity: str
    has_sufficient_data: bool
    start_year: Optional[int]
    end_year: Optional[int]
    start_val: Optional[float]
    end_val: Optional[float]
    abs_change: Optional[float]
    pct_change: Optional[float]
    is_zero_baseline: bool
    direction: str  # "increase", "decrease", "flat", "unknown"
    observations: int


@dataclass
class NumericalClaim:
    raw_text: str
    entity: Optional[str]
    claimed_val: float
    is_percent: bool
    is_points: bool
    direction: str  # "increase", "decrease", "any", "unknown"
    claimed_start: Optional[float] = None
    claimed_end: Optional[float] = None
    sentence: str = ""
    scene_number: Optional[int] = None
    is_ambiguous: bool = False
    scale_multiplier: float = 1.0
    scale_word: str = ""
    start_scale_multiplier: float = 1.0
    start_scale_word: str = ""
    end_scale_multiplier: float = 1.0
    end_scale_word: str = ""
    claim_type: str = "delta"  # "delta", "destination", "range"


@dataclass
class MathValidationReport:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    claims: List[NumericalClaim] = field(default_factory=list)
    failing_scenes: List[int] = field(default_factory=list)


class MathIntegrityEngine:
    """Deterministic math calculation and claim validation."""

    # Words signaling increase (verbs, participles, nouns)
    INCREASE_WORDS = {
        "increased", "increases", "increase", "increasing",
        "rose", "rises", "rise", "rising",
        "climbed", "climbs", "climb", "climbing",
        "surged", "surges", "surge", "surging",
        "jumped", "jumps", "jump", "jumping",
        "grew", "grows", "grow", "growing", "growth",
        "added", "adds", "add", "adding",
        "soared", "soars", "soar", "soaring",
        "skyrocketed", "skyrockets", "skyrocketing",
        "expanded", "expands", "expand", "expanding", "expansion",
        "gained", "gains", "gain", "gaining",
        "spike", "spikes", "spiked", "spiking",
        "up",
    }

    # Words signaling decrease (verbs, participles, nouns)
    DECREASE_WORDS = {
        "decreased", "decreases", "decrease", "decreasing",
        "fell", "falls", "fall", "falling",
        "dropped", "drops", "drop", "dropping",
        "declined", "declines", "decline", "declining",
        "shed", "sheds", "shedding",
        "lost", "loses", "lose", "losing", "loss",
        "plummeted", "plummeting", "plummets",
        "shrank", "shrinks", "shrink", "shrinking",
        "collapsed", "collapsing",
        "cut", "cuts", "cutting",
        "shaved", "shaves", "shaving",
        "dip", "dips", "dipped", "dipping",
        "slip", "slips", "slipped", "slipping", "slid",
        "down",
    }

    # Words signaling difference/change without fixed direction
    NEUTRAL_CHANGE_WORDS = {
        "difference", "gap", "margin", "spread", "changed", "shifted", "moved"
    }

    CLAUSE_SPLIT_PATTERN = re.compile(
        r';\s*'
        r'|,\s+(?:while|whereas|but|and)?\s*'
        r'|,\s*(?:while|whereas|but|and)\s*'
        r'|\s+\b(?:while|whereas|but)\b\s*'
        r'|(?<=[)%\d])\s+\band\b\s+'
        r'|(?<=points)\s+\band\b\s+'
        r'|(?<=point)\s+\band\b\s+'
        r'|(?<=percent)\s+\band\b\s+'
        r'|(?<=billion)\s+\band\b\s+'
        r'|(?<=billions)\s+\band\b\s+'
        r'|(?<=million)\s+\band\b\s+'
        r'|(?<=millions)\s+\band\b\s+',
        re.IGNORECASE,
    )

    @staticmethod
    def _resolve_entity_for_claim(
        clause: str,
        clause_entities: List[Tuple[int, int, str]],
        clause_single_entity: Optional[str],
        is_clause_ambiguous: bool,
        match_start: int,
        is_active_verb: bool = False,
    ) -> Tuple[Optional[str], bool]:
        """Resolve entity and ambiguity flag for a pattern match within a clause.

        If clause has a single entity, attribute to it.
        If clause has multiple entities and is_active_verb is True:
            Attribute to the entity directly preceding the verb (unless compound subject).
        Otherwise, fall back to nearest entity marked ambiguous.
        """
        matched_entity = clause_single_entity
        ambiguous = is_clause_ambiguous

        if matched_entity is None:
            if not clause_entities:
                return None, True

            if is_active_verb:
                preceding = [e for e in clause_entities if e[1] <= match_start]
                if preceding:
                    last_pre = preceding[-1]
                    intervening = clause[last_pre[1]:match_start]
                    # Allowed between subject entity and active verb: whitespace, quotes, and optional adverbs
                    if re.match(
                        r"^[\s\"')’]*(?:sharply|rapidly|steadily|significantly|dramatically|further|also|then|now|later)?[\s\"')’]*$",
                        intervening,
                        re.IGNORECASE,
                    ):
                        text_before_ent = clause[:last_pre[0]].rstrip()
                        if len(preceding) >= 2 and re.search(r"\b(?:and|or)\s*$", text_before_ent, re.IGNORECASE):
                            second_last = preceding[-2]
                            between_ents = clause[second_last[1]:last_pre[0]].strip()
                            if re.match(r"^(?:and|or)$", between_ents, re.IGNORECASE):
                                # Compound subject: e.g. "India and China jumped" -> ambiguous
                                return last_pre[2], True
                        # Direct unambiguous subject of this active verb!
                        return last_pre[2], False

            nearest = min(clause_entities, key=lambda e: abs(e[0] - match_start))
            matched_entity = nearest[2]
            ambiguous = True

        return matched_entity, ambiguous

    MAGNITUDE_MULTIPLIERS = {
        "thousand": 1e3,
        "thousands": 1e3,
        "k": 1e3,
        "million": 1e6,
        "millions": 1e6,
        "m": 1e6,
        "billion": 1e9,
        "billions": 1e9,
        "b": 1e9,
        "trillion": 1e12,
        "trillions": 1e12,
        "t": 1e12,
    }

    @staticmethod
    def compute_ground_truth(
        data: pd.DataFrame,
        topic_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, EntityGroundTruth]:
        """Compute ground-truth start/end endpoints and changes from wide DataFrame.

        Sorts years chronologically, handles missing/NaN observations,
        negative changes, and zero baselines explicitly.
        """
        if data is None or data.empty:
            return {}

        valid_year_cols: List[Tuple[int, Any]] = []
        for col in data.columns:
            y = coerce_year_label(col)
            if y is not None:
                valid_year_cols.append((y, col))

        valid_year_cols.sort(key=lambda item: item[0])

        if not valid_year_cols:
            return {}

        ground_truth: Dict[str, EntityGroundTruth] = {}

        for row_idx, entity_idx in enumerate(data.index):
            entity_name, _ = MathIntegrityEngine._normalize_entity_name(entity_idx)
            obs: List[Tuple[int, float]] = []

            for yr, col in valid_year_cols:
                col_loc = data.columns.get_loc(col)
                val = data.iat[row_idx, col_loc]
                if pd.notna(val):
                    try:
                        fval = float(val)
                        if not math.isnan(fval) and not math.isinf(fval):
                            obs.append((yr, fval))
                    except (ValueError, TypeError):
                        continue

            if len(obs) == 0:
                ground_truth[entity_name] = EntityGroundTruth(
                    entity=entity_name,
                    has_sufficient_data=False,
                    start_year=None,
                    end_year=None,
                    start_val=None,
                    end_val=None,
                    abs_change=None,
                    pct_change=None,
                    is_zero_baseline=False,
                    direction="unknown",
                    observations=0,
                )
            elif len(obs) == 1:
                yr, val = obs[0]
                ground_truth[entity_name] = EntityGroundTruth(
                    entity=entity_name,
                    has_sufficient_data=True,
                    start_year=yr,
                    end_year=yr,
                    start_val=val,
                    end_val=val,
                    abs_change=0.0,
                    pct_change=0.0,
                    is_zero_baseline=abs(val) < 1e-9,
                    direction="flat",
                    observations=1,
                )
            else:
                s_yr, s_val = obs[0]
                e_yr, e_val = obs[-1]
                abs_change = e_val - s_val
                is_zero_baseline = abs(s_val) < 1e-9

                if is_zero_baseline:
                    pct_change = None
                else:
                    pct_change = (abs_change / abs(s_val)) * 100.0

                if abs_change > 1e-6:
                    direction = "increase"
                elif abs_change < -1e-6:
                    direction = "decrease"
                else:
                    direction = "flat"

                ground_truth[entity_name] = EntityGroundTruth(
                    entity=entity_name,
                    has_sufficient_data=True,
                    start_year=s_yr,
                    end_year=e_yr,
                    start_val=s_val,
                    end_val=e_val,
                    abs_change=abs_change,
                    pct_change=pct_change,
                    is_zero_baseline=is_zero_baseline,
                    direction=direction,
                    observations=len(obs),
                )

        return ground_truth

    @staticmethod
    def is_rate_or_percentage_indicator(
        indicator_name: str = "",
        indicator_code: str = "",
        topic: str = "",
    ) -> bool:
        """Detect whether indicator is a rate, index, or percentage."""
        text = f"{indicator_name} {indicator_code} {topic}".lower()
        keywords = [
            "%", "percent", "rate", "ratio", "per 1,000", "per 1000",
            "per thousand", "per capita", "mortality", "index", "share"
        ]
        return any(kw in text for kw in keywords)

    @staticmethod
    def _normalize_entity_name(entity_idx: Any) -> Tuple[str, Optional[str]]:
        """Extract canonical display name and code from string, tuple, or list index."""
        if isinstance(entity_idx, (tuple, list)):
            if len(entity_idx) >= 2:
                code = str(entity_idx[0]).strip() if entity_idx[0] is not None else None
                name = str(entity_idx[-1]).strip() if entity_idx[-1] is not None else ""
                return name or (code or ""), code
            elif len(entity_idx) == 1:
                return str(entity_idx[0]).strip(), None
        raw_str = str(entity_idx).strip()
        if raw_str.startswith("(") and raw_str.endswith(")"):
            m = re.match(r"^\(\s*['\"]?([^'\",]+)['\"]?\s*,\s*['\"]?([^'\"]+)['\"]?\s*\)$", raw_str)
            if m:
                code, name = m.group(1).strip(), m.group(2).strip()
                return name or code, code
        return raw_str, None

    @staticmethod
    def _is_year(token: str) -> bool:
        """Check if numeric token is likely a calendar year."""
        try:
            val = int(str(token).replace(",", ""))
            return 1900 <= val <= 2100
        except ValueError:
            return False

    @staticmethod
    def _parse_magnitude(mag_str: Optional[str]) -> Tuple[float, str]:
        """Convert magnitude string into (multiplier, normalized_word)."""
        if not mag_str:
            return 1.0, ""
        clean = mag_str.strip().lower()
        if clean in MathIntegrityEngine.MAGNITUDE_MULTIPLIERS:
            return MathIntegrityEngine.MAGNITUDE_MULTIPLIERS[clean], clean
        return 1.0, ""

    @staticmethod
    def _parse_unit(unit_str: str) -> Tuple[bool, bool]:
        """Classify unit into (is_points, is_percent).

        Crucial statistical rule:
        "percentage points" is an ABSOLUTE difference (is_points=True, is_percent=False).
        It must never be confused with relative percentage (is_percent=True).
        """
        unit = (unit_str or "").lower().strip()
        is_points = "point" in unit
        is_percent = ("%" in unit or "percent" in unit) and not is_points
        return is_points, is_percent

    @staticmethod
    def build_entity_aliases(known_entities: List[str]) -> List[Tuple[str, str]]:
        """Map canonical entity names and their standard aliases/short forms.

        Handles corporate suffixes (Inc., Corporation, Ltd.) and country abbreviations
        (United States -> US, UK -> United Kingdom, etc.) so natural voiceover phrasing
        can be accurately attributed to ground truth entities without losing strictness.
        """
        alias_pairs: List[Tuple[str, str]] = []
        corp_suffix = re.compile(
            r"^(?:The\s+)?(.*?)(?:,?\s+(?:Inc\.?|Corporation|Corp\.?|Co\.?|Company|Ltd\.?|LLC|Plc|Platforms\s+Inc\.?|Chase\s+&\s+Co\.?|Holdings?|Group|SA|AG|NV|SE))(?:\s+Inc\.?|\s+Corp\.?)?$",
            re.IGNORECASE,
        )
        for ent in known_entities:
            alias_pairs.append((ent, ent))
            m = corp_suffix.match(ent)
            if m:
                base = m.group(1).strip()
                if base and base != ent:
                    alias_pairs.append((base, ent))
                    if ".com" in base.lower():
                        alias_pairs.append((re.sub(r"\.com", "", base, flags=re.I).strip(), ent))

            if ent == "Alphabet Inc.":
                alias_pairs.append(("Google", ent))
                alias_pairs.append(("Alphabet", ent))
            elif ent == "Meta Platforms Inc.":
                alias_pairs.append(("Facebook", ent))
                alias_pairs.append(("Meta", ent))
            elif ent == "JPMorgan Chase & Co.":
                alias_pairs.append(("JPMorgan", ent))
                alias_pairs.append(("JP Morgan", ent))
            elif ent == "The Coca-Cola Company":
                alias_pairs.append(("Coca-Cola", ent))
                alias_pairs.append(("Coke", ent))
            elif ent == "The Walt Disney Company":
                alias_pairs.append(("Disney", ent))
            elif ent == "India":
                for a in ("Delhi", "New Delhi"):
                    alias_pairs.append((a, ent))
            elif ent == "China":
                alias_pairs.append(("Beijing", ent))
            elif ent == "United States":
                for a in ("US", "USA", "U.S.", "U.S.A.", "Washington"):
                    alias_pairs.append((a, ent))
            elif ent == "United Kingdom":
                for a in ("UK", "U.K.", "Britain", "London"):
                    alias_pairs.append((a, ent))
            elif ent == "Korea, Rep.":
                for a in ("South Korea", "Korea"):
                    alias_pairs.append((a, ent))
            elif ent in ("Russian Federation", "Russia"):
                alias_pairs.append(("Russia", ent))
                alias_pairs.append(("Moscow", ent))
            elif ent == "Venezuela, RB":
                alias_pairs.append(("Venezuela", ent))
            elif ent == "United Arab Emirates":
                alias_pairs.append(("UAE", ent))
            elif ent == "Saudi Arabia":
                alias_pairs.append(("Riyadh", ent))
            elif ent == "Lebanon":
                alias_pairs.append(("Beirut", ent))

        # Sort descending by alias length so longer matches take precedence
        alias_pairs.sort(key=lambda x: len(x[0]), reverse=True)
        return alias_pairs

    @staticmethod
    def extract_claims(
        text: str,
        known_entities: List[str],
        scene_number: Optional[int] = None,
    ) -> List[NumericalClaim]:
        """Extract numerical change claims using clause-aware entity attribution.

        Preserves valid calendar years, durations, ranks, counts, and denominators.
        Fails closed on ambiguous entity attribution.
        """
        claims: List[NumericalClaim] = []
        if not text:
            return claims

        alias_pairs = MathIntegrityEngine.build_entity_aliases(known_entities)

        # Identify unique canonical entities across the entire scene/narration text
        scene_entities: List[str] = []
        for alias, canonical in alias_pairs:
            if re.search(r"\b" + re.escape(alias) + r"\b", text, re.IGNORECASE):
                if canonical not in scene_entities:
                    scene_entities.append(canonical)

        sentences = re.split(r"(?<=[.!?])\s+", text)

        for sent in sentences:
            sent_clean = sent.strip()
            if not sent_clean:
                continue

            # Identify all entities in this sentence via alias resolution
            sentence_entities = []
            for alias, canonical in alias_pairs:
                if re.search(r"\b" + re.escape(alias) + r"\b", sent_clean, re.IGNORECASE):
                    if canonical not in sentence_entities:
                        sentence_entities.append(canonical)

            # Split sentence into clauses
            raw_clauses = MathIntegrityEngine.CLAUSE_SPLIT_PATTERN.split(sent_clean)
            clauses = [c.strip() for c in raw_clauses if c.strip()]

            # 1. Endpoint claims: "from X to Y" (sentence level)
            endpoint_match = re.search(
                r"\bfrom\s+(?:\$|€|£)?\s*([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(trillions?|billions?|millions?|thousands?|[kmbtKMBT])?\s+to\s+(?:\$|€|£)?\s*([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(trillions?|billions?|millions?|thousands?|[kmbtKMBT])?\b",
                sent_clean,
                re.IGNORECASE,
            )
            claimed_start = None
            claimed_end = None
            start_scale_mult = 1.0
            start_scale_word = ""
            end_scale_mult = 1.0
            end_scale_word = ""
            endpoint_span = None
            if endpoint_match:
                endpoint_span = endpoint_match.span()
                tok_a_num = endpoint_match.group(1).replace(",", "")
                tok_a_mag = endpoint_match.group(2)
                tok_b_num = endpoint_match.group(3).replace(",", "")
                tok_b_mag = endpoint_match.group(4)
                if not tok_a_mag and tok_b_mag:
                    # Scale word inheritance from second endpoint: e.g. "from 1.0 to 2.3 billion"
                    tok_a_mag = tok_b_mag

                mult_a, word_a = MathIntegrityEngine._parse_magnitude(tok_a_mag)
                mult_b, word_b = MathIntegrityEngine._parse_magnitude(tok_b_mag)

                is_year_a = MathIntegrityEngine._is_year(tok_a_num) and mult_a == 1.0
                is_year_b = MathIntegrityEngine._is_year(tok_b_num) and mult_b == 1.0

                if not (is_year_a and is_year_b):
                    try:
                        val_a = float(tok_a_num)
                        val_b = float(tok_b_num)
                        claimed_start = val_a
                        claimed_end = val_b
                        start_scale_mult = mult_a
                        start_scale_word = word_a
                        end_scale_mult = mult_b
                        end_scale_word = word_b
                    except ValueError:
                        pass

            for clause_idx, clause in enumerate(clauses):
                clause_entities = []
                for alias, canonical in alias_pairs:
                    pattern = r"\b" + re.escape(alias) + r"\b"
                    for m in re.finditer(pattern, clause, re.IGNORECASE):
                        clause_entities.append((m.start(), m.end(), canonical))
                clause_entities.sort(key=lambda x: x[0])

                # Determine clause entity context:
                # If clause has exactly 1 entity, attribution is clear.
                # If clause has 0 entities but sentence has only 1 entity overall, inherit it.
                # If sentence has 0 entities but scene has only 1 entity overall, inherit it.
                # If multiple entities exist in clause/sentence/scene, mark ambiguous.
                clause_single_entity: Optional[str] = None
                is_clause_ambiguous = False

                unique_clause_ents = list(dict.fromkeys(e[2] for e in clause_entities))
                if len(unique_clause_ents) == 1:
                    clause_single_entity = unique_clause_ents[0]
                elif len(unique_clause_ents) == 0:
                    if len(sentence_entities) == 1:
                        clause_single_entity = sentence_entities[0]
                    elif len(scene_entities) == 1:
                        clause_single_entity = scene_entities[0]
                    else:
                        is_clause_ambiguous = True
                else:
                    # Multiple entities in this clause
                    is_clause_ambiguous = True

                # Regex patterns for change claims within this clause:

                # Pattern A: Verb first: e.g. "rose by 4.4 points", "jumped 12%", "dropped by 5", "rose by 1.2 billion"
                verb_pattern = re.compile(
                    r"\b([a-zA-Z]+)\b\s+(?:by\s+)?(?:\$|€|£)?\s*([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(trillions?|billions?|millions?|thousands?|[kmbtKMBT])?\s*(%|percentage points?|points?|percent|percentage)?(?=\s|[.,;!?]|$)",
                    re.IGNORECASE,
                )

                for match in verb_pattern.finditer(clause):
                    trigger_word = match.group(1).lower()
                    number_str = match.group(2).replace(",", "")
                    mag_str = match.group(3)
                    unit_str = match.group(4) or ""

                    scale_mult, scale_word = MathIntegrityEngine._parse_magnitude(mag_str)

                    if MathIntegrityEngine._is_year(number_str) and not unit_str and scale_mult == 1.0:
                        continue

                    direction = None
                    if trigger_word in MathIntegrityEngine.INCREASE_WORDS:
                        direction = "increase"
                    elif trigger_word in MathIntegrityEngine.DECREASE_WORDS:
                        direction = "decrease"
                    elif trigger_word in MathIntegrityEngine.NEUTRAL_CHANGE_WORDS:
                        direction = "any"

                    if direction is not None:
                        try:
                            c_val = float(number_str)
                        except ValueError:
                            continue

                        # Filter out denominators like "per 1,000"
                        if "per" in clause.lower() and c_val in (100.0, 1000.0, 100000.0, 1000000.0) and not unit_str and scale_mult == 1.0:
                            continue

                        is_points, is_percent = MathIntegrityEngine._parse_unit(unit_str)
                        if is_points or is_percent:
                            scale_mult = 1.0
                            scale_word = ""

                        # Entity resolution
                        matched_entity, ambiguous = MathIntegrityEngine._resolve_entity_for_claim(
                            clause,
                            clause_entities,
                            clause_single_entity,
                            is_clause_ambiguous,
                            match.start(),
                            is_active_verb=True,
                        )

                        claims.append(
                            NumericalClaim(
                                raw_text=match.group(0),
                                entity=matched_entity,
                                claimed_val=c_val,
                                is_percent=is_percent,
                                is_points=is_points,
                                direction=direction,
                                claimed_start=claimed_start,
                                claimed_end=claimed_end,
                                sentence=sent_clean,
                                scene_number=scene_number,
                                is_ambiguous=ambiguous or (matched_entity is None),
                                scale_multiplier=scale_mult,
                                scale_word=scale_word,
                                start_scale_multiplier=start_scale_mult,
                                start_scale_word=start_scale_word,
                                end_scale_multiplier=end_scale_mult,
                                end_scale_word=end_scale_word,
                                claim_type="delta",
                            )
                        )

                # Pattern B: Noun phrase: e.g. "an increase of 4.4 points", "a drop of 15%", "a surge of 1.2 billion"
                noun_pattern = re.compile(
                    r"\b(?:a|an)\s+([a-zA-Z]+)\s+of\s+(?:\$|€|£)?\s*([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(trillions?|billions?|millions?|thousands?|[kmbtKMBT])?\s*(%|percentage points?|points?|percent|percentage)?(?=\s|[.,;!?]|$)",
                    re.IGNORECASE,
                )

                for match in noun_pattern.finditer(clause):
                    noun_word = match.group(1).lower()
                    number_str = match.group(2).replace(",", "")
                    mag_str = match.group(3)
                    unit_str = match.group(4) or ""

                    scale_mult, scale_word = MathIntegrityEngine._parse_magnitude(mag_str)

                    direction = None
                    if noun_word in MathIntegrityEngine.INCREASE_WORDS:
                        direction = "increase"
                    elif noun_word in MathIntegrityEngine.DECREASE_WORDS:
                        direction = "decrease"
                    elif noun_word in MathIntegrityEngine.NEUTRAL_CHANGE_WORDS:
                        direction = "any"

                    if direction is not None:
                        try:
                            c_val = float(number_str)
                        except ValueError:
                            continue

                        is_points, is_percent = MathIntegrityEngine._parse_unit(unit_str)
                        if is_points or is_percent:
                            scale_mult = 1.0
                            scale_word = ""

                        # Entity resolution
                        matched_entity, ambiguous = MathIntegrityEngine._resolve_entity_for_claim(
                            clause,
                            clause_entities,
                            clause_single_entity,
                            is_clause_ambiguous,
                            match.start(),
                            is_active_verb=False,
                        )

                        if not any(
                            c.scene_number == scene_number
                            and c.sentence == sent_clean
                            and abs(c.claimed_val - c_val) < 1e-6
                            and abs(c.scale_multiplier - scale_mult) < 1e-6
                            for c in claims
                        ):
                            claims.append(
                                NumericalClaim(
                                    raw_text=match.group(0),
                                    entity=matched_entity,
                                    claimed_val=c_val,
                                    is_percent=is_percent,
                                    is_points=is_points,
                                    direction=direction,
                                    claimed_start=claimed_start,
                                    claimed_end=claimed_end,
                                    sentence=sent_clean,
                                    scene_number=scene_number,
                                    is_ambiguous=ambiguous or (matched_entity is None),
                                    scale_multiplier=scale_mult,
                                    scale_word=scale_word,
                                    start_scale_multiplier=start_scale_mult,
                                    start_scale_word=start_scale_word,
                                    end_scale_multiplier=end_scale_mult,
                                    end_scale_word=end_scale_word,
                                    claim_type="delta",
                                )
                            )

                # Pattern C: Passive voice / Number-first phrasing:
                # e.g. "10% was lost by Cyprus", "4.4 points were added", "1.2 billion was added by India"
                passive_pattern = re.compile(
                    r"\b(?:\$|€|£)?\s*([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(trillions?|billions?|millions?|thousands?|[kmbtKMBT])?\s*(%|percentage points?|points?|percent|percentage)?\s+(?:was|were)\s+([a-zA-Z]+)\b",
                    re.IGNORECASE,
                )

                for match in passive_pattern.finditer(clause):
                    number_str = match.group(1).replace(",", "")
                    mag_str = match.group(2)
                    unit_str = match.group(3) or ""
                    verb_word = match.group(4).lower()

                    scale_mult, scale_word = MathIntegrityEngine._parse_magnitude(mag_str)

                    direction = "unknown"
                    if verb_word in MathIntegrityEngine.INCREASE_WORDS:
                        direction = "increase"
                    elif verb_word in MathIntegrityEngine.DECREASE_WORDS:
                        direction = "decrease"
                    elif verb_word in MathIntegrityEngine.NEUTRAL_CHANGE_WORDS:
                        direction = "any"

                    try:
                        c_val = float(number_str)
                    except ValueError:
                        continue

                    is_points, is_percent = MathIntegrityEngine._parse_unit(unit_str)
                    if is_points or is_percent:
                        scale_mult = 1.0
                        scale_word = ""

                    # Entity resolution
                    matched_entity, ambiguous = MathIntegrityEngine._resolve_entity_for_claim(
                        clause,
                        clause_entities,
                        clause_single_entity,
                        is_clause_ambiguous or (direction == "unknown"),
                        match.start(),
                        is_active_verb=False,
                    )

                    if not any(
                        c.scene_number == scene_number
                        and c.sentence == sent_clean
                        and abs(c.claimed_val - c_val) < 1e-6
                        and abs(c.scale_multiplier - scale_mult) < 1e-6
                        for c in claims
                    ):
                        claims.append(
                            NumericalClaim(
                                raw_text=match.group(0),
                                entity=matched_entity,
                                claimed_val=c_val,
                                is_percent=is_percent,
                                is_points=is_points,
                                direction=direction,
                                claimed_start=claimed_start,
                                claimed_end=claimed_end,
                                sentence=sent_clean,
                                scene_number=scene_number,
                                is_ambiguous=ambiguous or (matched_entity is None),
                                scale_multiplier=scale_mult,
                                scale_word=scale_word,
                                start_scale_multiplier=start_scale_mult,
                                start_scale_word=start_scale_word,
                                end_scale_multiplier=end_scale_mult,
                                end_scale_word=end_scale_word,
                                claim_type="delta",
                            )
                        )

                # Pattern D: Destination-level claims:
                # e.g. "India increased to 2.3 billion", "fell to 800 million", "climbed to 2.3 million"
                dest_pattern = re.compile(
                    r"\b([a-zA-Z]+)\b\s+(?:(?:sharply|rapidly|steadily|significantly|dramatically|further)\s+)?to\s+(?:\$|€|£)?\s*([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(trillions?|billions?|millions?|thousands?|[kmbtKMBT])?\s*(%|percentage points?|points?|percent|percentage)?(?=\s|[.,;!?]|$)",
                    re.IGNORECASE,
                )

                for match in dest_pattern.finditer(clause):
                    # Guard against overlapping with "from X to Y" ranges
                    if endpoint_span is not None:
                        clause_start_in_sent = sent_clean.find(clause)
                        if clause_start_in_sent >= 0:
                            m_start_in_sent = clause_start_in_sent + match.start()
                            m_end_in_sent = m_start_in_sent + len(match.group(0))
                            if not (m_end_in_sent <= endpoint_span[0] or m_start_in_sent >= endpoint_span[1]):
                                continue

                    trigger_word = match.group(1).lower()
                    number_str = match.group(2).replace(",", "")
                    mag_str = match.group(3)
                    unit_str = match.group(4) or ""

                    scale_mult, scale_word = MathIntegrityEngine._parse_magnitude(mag_str)

                    if MathIntegrityEngine._is_year(number_str) and not unit_str and scale_mult == 1.0:
                        continue

                    direction = None
                    if trigger_word in MathIntegrityEngine.INCREASE_WORDS:
                        direction = "increase"
                    elif trigger_word in MathIntegrityEngine.DECREASE_WORDS:
                        direction = "decrease"

                    if direction is not None:
                        try:
                            c_val = float(number_str)
                        except ValueError:
                            continue

                        is_points, is_percent = MathIntegrityEngine._parse_unit(unit_str)
                        if is_points or is_percent:
                            scale_mult = 1.0
                            scale_word = ""

                        # Entity resolution
                        matched_entity, ambiguous = MathIntegrityEngine._resolve_entity_for_claim(
                            clause,
                            clause_entities,
                            clause_single_entity,
                            is_clause_ambiguous,
                            match.start(),
                            is_active_verb=True,
                        )

                        if not any(
                            c.scene_number == scene_number
                            and c.sentence == sent_clean
                            and c.claim_type == "destination"
                            and abs(c.claimed_val - c_val) < 1e-6
                            and abs(c.scale_multiplier - scale_mult) < 1e-6
                            for c in claims
                        ):
                            claims.append(
                                NumericalClaim(
                                    raw_text=match.group(0),
                                    entity=matched_entity,
                                    claimed_val=c_val,
                                    is_percent=is_percent,
                                    is_points=is_points,
                                    direction=direction,
                                    claimed_start=None,
                                    claimed_end=c_val,
                                    sentence=sent_clean,
                                    scene_number=scene_number,
                                    is_ambiguous=ambiguous or (matched_entity is None),
                                    scale_multiplier=scale_mult,
                                    scale_word=scale_word,
                                    start_scale_multiplier=1.0,
                                    start_scale_word="",
                                    end_scale_multiplier=scale_mult,
                                    end_scale_word=scale_word,
                                    claim_type="destination",
                                )
                            )

            # Standalone range claim: "India climbed from 1.0 billion to 2.3 billion."
            # Only created if no delta claims and no destination claims were extracted from this sentence
            sentence_claims = [c for c in claims if c.sentence == sent_clean]
            if claimed_start is not None and claimed_end is not None and not sentence_claims:
                range_direction = "any"
                words_in_sent = set(re.findall(r"\b[a-zA-Z]+\b", sent_clean.lower()))
                if any(w in MathIntegrityEngine.INCREASE_WORDS for w in words_in_sent):
                    range_direction = "increase"
                elif any(w in MathIntegrityEngine.DECREASE_WORDS for w in words_in_sent):
                    range_direction = "decrease"

                matched_entity = None
                ambiguous = False
                if len(sentence_entities) == 1:
                    matched_entity = sentence_entities[0]
                elif len(sentence_entities) == 0:
                    if len(scene_entities) == 1:
                        matched_entity = scene_entities[0]
                    else:
                        ambiguous = True
                else:
                    ambiguous = True

                start_raw = claimed_start * start_scale_mult
                end_raw = claimed_end * end_scale_mult
                diff_raw = abs(end_raw - start_raw)
                range_val = diff_raw / end_scale_mult if end_scale_mult > 0 else diff_raw

                claims.append(
                    NumericalClaim(
                        raw_text=endpoint_match.group(0),
                        entity=matched_entity,
                        claimed_val=range_val,
                        is_percent=False,
                        is_points=False,
                        direction=range_direction,
                        claimed_start=claimed_start,
                        claimed_end=claimed_end,
                        sentence=sent_clean,
                        scene_number=scene_number,
                        is_ambiguous=ambiguous or (matched_entity is None),
                        scale_multiplier=end_scale_mult,
                        scale_word=end_scale_word,
                        start_scale_multiplier=start_scale_mult,
                        start_scale_word=start_scale_word,
                        end_scale_multiplier=end_scale_mult,
                        end_scale_word=end_scale_word,
                        claim_type="range",
                    )
                )

        return claims

    @staticmethod
    def _matches_ground_truth_val(
        claimed_val: float,
        scale_multiplier: float,
        expected_val: float,
    ) -> Tuple[bool, float]:
        """Check if claimed_val (with optional scale_multiplier) matches expected_val.

        Returns (is_match, best_discrepancy).
        Handles raw units vs pre-scaled data, 1-dec/2-dec roundings, and relative tolerance.
        """
        candidates = [(claimed_val, 1.0)]
        if scale_multiplier > 1.0:
            candidates.append((claimed_val * scale_multiplier, scale_multiplier))

        is_match = False
        best_discrepancy = float("inf")

        for cand_val, cand_mult in candidates:
            cand_1dec = (
                abs(cand_val - round(cand_val, 1)) < 1e-4
                and abs(cand_val - expected_val) <= (0.05 * cand_mult) + 1e-4
            )
            cand_2dec = (
                abs(cand_val - round(cand_val, 2)) < 1e-4
                and abs(cand_val - expected_val) <= (0.005 * cand_mult) + 1e-4
            )
            cand_standard_rounding = (
                cand_1dec
                or cand_2dec
                or abs(cand_val - round(expected_val, 1)) < 1e-4
                or abs(cand_val - round(expected_val, 2)) < 1e-4
            )
            if cand_mult > 1.0:
                scaled_exp = expected_val / cand_mult
                if (
                    abs(claimed_val - round(scaled_exp, 1)) < 1e-4
                    or abs(claimed_val - round(scaled_exp, 2)) < 1e-4
                ):
                    cand_standard_rounding = True

            abs_tol = max(0.05 * cand_mult, 0.03 * abs(expected_val))
            diff = abs(cand_val - expected_val)
            if diff < best_discrepancy:
                best_discrepancy = diff

            if cand_standard_rounding or (diff - abs_tol) <= 1e-4:
                is_match = True
                break

        return is_match, best_discrepancy

    @staticmethod
    def validate_claims(
        claims: List[NumericalClaim],
        ground_truth: Dict[str, EntityGroundTruth],
        default_entity: Optional[str] = None,
        is_rate_indicator: bool = False,
    ) -> MathValidationReport:
        """Validate extracted numerical claims against ground truth.

        Checks:
        1. Ambiguous claims fail closed (marked unverified).
        2. Direction of change (increase vs decrease).
        3. Magnitude tolerance: dynamically tight for small numbers (< 1.0),
           checking standard 1-dec/2-dec roundings.
        4. Zero baseline safety (percentage change from 0 is rejected).
        5. "Percentage points" validated as absolute points, not %.
        6. Rate/percentage confusion (stating % for an absolute point difference).
        7. Destination-level claims checked against truth.end_val.
        8. Stated endpoints checked against ground truth start/end values.
        9. Internal consistency (endpoints diff vs stated delta in compatible units).
        """
        errors: List[str] = []
        warnings: List[str] = []
        failing_scenes: List[int] = []

        for claim in claims:
            # Ambiguity guard: If attribution is ambiguous, fail closed
            if claim.is_ambiguous or not claim.entity:
                err = (
                    f"Scene {claim.scene_number}: Ambiguous numerical claim '{claim.raw_text}' "
                    f"cannot be safely attributed to a single entity or direction."
                )
                errors.append(err)
                if claim.scene_number and claim.scene_number not in failing_scenes:
                    failing_scenes.append(claim.scene_number)
                continue

            entity = claim.entity
            if entity not in ground_truth:
                err = f"Scene {claim.scene_number}: Claim '{claim.raw_text}' refers to entity '{entity}' not present in dataset."
                errors.append(err)
                if claim.scene_number and claim.scene_number not in failing_scenes:
                    failing_scenes.append(claim.scene_number)
                continue

            truth = ground_truth[entity]

            if not truth.has_sufficient_data:
                err = f"Scene {claim.scene_number}: '{entity}' has insufficient data observations in provider dataset."
                errors.append(err)
                if claim.scene_number and claim.scene_number not in failing_scenes:
                    failing_scenes.append(claim.scene_number)
                continue

            # 1. Direction Validation
            if claim.direction == "increase" and truth.direction == "decrease":
                err = (
                    f"Scene {claim.scene_number}: Direction mismatch for {entity}. "
                    f"Claimed increase ('{claim.raw_text}'), but data decreased from "
                    f"{truth.start_val:.2f} ({truth.start_year}) to {truth.end_val:.2f} ({truth.end_year}) "
                    f"({truth.abs_change:+.2f})."
                )
                errors.append(err)
                if claim.scene_number and claim.scene_number not in failing_scenes:
                    failing_scenes.append(claim.scene_number)
                continue

            if claim.direction == "decrease" and truth.direction == "increase":
                err = (
                    f"Scene {claim.scene_number}: Direction mismatch for {entity}. "
                    f"Claimed decrease ('{claim.raw_text}'), but data increased from "
                    f"{truth.start_val:.2f} ({truth.start_year}) to {truth.end_val:.2f} ({truth.end_year}) "
                    f"({truth.abs_change:+.2f})."
                )
                errors.append(err)
                if claim.scene_number and claim.scene_number not in failing_scenes:
                    failing_scenes.append(claim.scene_number)
                continue

            if claim.direction in ("increase", "decrease") and truth.direction == "flat":
                err = (
                    f"Scene {claim.scene_number}: Direction mismatch for {entity}. "
                    f"Claimed {claim.direction} ('{claim.raw_text}'), but data remained flat "
                    f"at {truth.start_val:.2f} ({truth.abs_change:+.2f})."
                )
                errors.append(err)
                if claim.scene_number and claim.scene_number not in failing_scenes:
                    failing_scenes.append(claim.scene_number)
                continue

            # 2. Zero Baseline Check
            if truth.is_zero_baseline and claim.is_percent:
                err = (
                    f"Scene {claim.scene_number}: Zero baseline error for {entity}. "
                    f"Started at 0 in {truth.start_year}; relative percentage change is mathematically undefined."
                )
                errors.append(err)
                if claim.scene_number and claim.scene_number not in failing_scenes:
                    failing_scenes.append(claim.scene_number)
                continue

            # 3. Destination-Level Claim Validation
            if claim.claim_type == "destination":
                if truth.end_val is None:
                    err = f"Scene {claim.scene_number}: Ground truth endpoint missing for {entity}."
                    errors.append(err)
                    if claim.scene_number and claim.scene_number not in failing_scenes:
                        failing_scenes.append(claim.scene_number)
                    continue

                is_valid_dest, dest_disc = MathIntegrityEngine._matches_ground_truth_val(
                    claimed_val=claim.claimed_val,
                    scale_multiplier=claim.scale_multiplier,
                    expected_val=truth.end_val,
                )
                if not is_valid_dest:
                    dest_unit = f" {claim.scale_word}" if claim.scale_word else ""
                    err = (
                        f"Scene {claim.scene_number}: Destination discrepancy for {entity}. "
                        f"Claimed destination level of {claim.claimed_val}{dest_unit}, "
                        f"but actual end value was {truth.end_val:.2f} ({truth.end_year}). "
                        f"Discrepancy: {dest_disc:.2f}."
                    )
                    errors.append(err)
                    if claim.scene_number and claim.scene_number not in failing_scenes:
                        failing_scenes.append(claim.scene_number)
                continue

            # 4. Magnitude Validation (for Delta and Range claims)
            claimed_magnitude = abs(claim.claimed_val)

            if claim.is_percent:
                if truth.pct_change is None:
                    err = f"Scene {claim.scene_number}: {entity} has undefined percentage change."
                    errors.append(err)
                    if claim.scene_number and claim.scene_number not in failing_scenes:
                        failing_scenes.append(claim.scene_number)
                    continue

                expected_pct = abs(truth.pct_change)
                pct_tol = max(1.0, 0.05 * expected_pct)

                # Check for rate confusion: did LLM say 'X%' when it was X points?
                expected_abs = abs(truth.abs_change)
                if (
                    is_rate_indicator
                    and abs(claimed_magnitude - expected_abs) <= 0.25
                    and abs(claimed_magnitude - expected_pct) > pct_tol
                ):
                    err = (
                        f"Scene {claim.scene_number}: Percentage confusion for {entity}. "
                        f"Stated '{claim.claimed_val}%', but the absolute change was {truth.abs_change:+.2f} points, "
                        f"and relative percentage change was {truth.pct_change:+.1f}%. "
                        f"For rate/percentage indicators, report absolute difference as 'points' or 'percentage points', not '%'."
                    )
                    errors.append(err)
                    if claim.scene_number and claim.scene_number not in failing_scenes:
                        failing_scenes.append(claim.scene_number)
                    continue

                if abs(claimed_magnitude - expected_pct) > pct_tol:
                    err = (
                        f"Scene {claim.scene_number}: Percentage discrepancy for {entity}. "
                        f"Claimed {claim.claimed_val}%, but actual relative change is {truth.pct_change:+.1f}% "
                        f"({truth.start_val:.2f} -> {truth.end_val:.2f}). Discrepancy: {abs(claimed_magnitude - expected_pct):.1f}%."
                    )
                    errors.append(err)
                    if claim.scene_number and claim.scene_number not in failing_scenes:
                        failing_scenes.append(claim.scene_number)
                    continue

            else:
                # Absolute difference / points / percentage points claim
                expected_abs = abs(truth.abs_change)
                is_valid_magnitude, best_discrepancy = MathIntegrityEngine._matches_ground_truth_val(
                    claimed_val=claimed_magnitude,
                    scale_multiplier=claim.scale_multiplier,
                    expected_val=expected_abs,
                )

                if not is_valid_magnitude:
                    err = (
                        f"Scene {claim.scene_number}: Numerical discrepancy for {entity}. "
                        f"Claimed change of {claim.claimed_val}{(' ' + claim.scale_word) if claim.scale_word else ''}, "
                        f"but actual change is {truth.abs_change:+.2f} "
                        f"({truth.start_val:.2f} in {truth.start_year} -> {truth.end_val:.2f} in {truth.end_year}). "
                        f"Discrepancy: {best_discrepancy:.2f}."
                    )
                    errors.append(err)
                    if claim.scene_number and claim.scene_number not in failing_scenes:
                        failing_scenes.append(claim.scene_number)

            # 5. Endpoint Ground Truth Validation
            # Stated start endpoint must match ground-truth start
            if claim.claimed_start is not None:
                if truth.start_val is None:
                    err = f"Scene {claim.scene_number}: Ground truth start endpoint missing for {entity}."
                    errors.append(err)
                    if claim.scene_number and claim.scene_number not in failing_scenes:
                        failing_scenes.append(claim.scene_number)
                else:
                    is_valid_start, start_disc = MathIntegrityEngine._matches_ground_truth_val(
                        claimed_val=claim.claimed_start,
                        scale_multiplier=claim.start_scale_multiplier,
                        expected_val=truth.start_val,
                    )
                    if not is_valid_start:
                        start_unit = f" {claim.start_scale_word}" if claim.start_scale_word else ""
                        err = (
                            f"Scene {claim.scene_number}: Endpoint start discrepancy for {entity}. "
                            f"Claimed start value of {claim.claimed_start}{start_unit}, "
                            f"but actual start value was {truth.start_val:.2f} ({truth.start_year}). "
                            f"Discrepancy: {start_disc:.2f}."
                        )
                        errors.append(err)
                        if claim.scene_number and claim.scene_number not in failing_scenes:
                            failing_scenes.append(claim.scene_number)

            # Stated end endpoint must match ground-truth end
            if claim.claimed_end is not None:
                if truth.end_val is None:
                    err = f"Scene {claim.scene_number}: Ground truth end endpoint missing for {entity}."
                    errors.append(err)
                    if claim.scene_number and claim.scene_number not in failing_scenes:
                        failing_scenes.append(claim.scene_number)
                else:
                    is_valid_end, end_disc = MathIntegrityEngine._matches_ground_truth_val(
                        claimed_val=claim.claimed_end,
                        scale_multiplier=claim.end_scale_multiplier,
                        expected_val=truth.end_val,
                    )
                    if not is_valid_end:
                        end_unit = f" {claim.end_scale_word}" if claim.end_scale_word else ""
                        err = (
                            f"Scene {claim.scene_number}: Endpoint end discrepancy for {entity}. "
                            f"Claimed end value of {claim.claimed_end}{end_unit}, "
                            f"but actual end value was {truth.end_val:.2f} ({truth.end_year}). "
                            f"Discrepancy: {end_disc:.2f}."
                        )
                        errors.append(err)
                        if claim.scene_number and claim.scene_number not in failing_scenes:
                            failing_scenes.append(claim.scene_number)

            # 6. Internal Consistency & Direction Check for Stated Endpoints
            if claim.claimed_start is not None and claim.claimed_end is not None:
                start_raw = claim.claimed_start * claim.start_scale_multiplier
                end_raw = claim.claimed_end * claim.end_scale_multiplier
                internal_delta_raw = abs(end_raw - start_raw)

                # Check direction of movement between endpoints
                if claim.direction == "increase" and end_raw < start_raw - 1e-6:
                    err = (
                        f"Scene {claim.scene_number}: Endpoint direction conflict for {entity}. "
                        f"Claimed increase, but stated endpoints move downward from {claim.claimed_start}{(' ' + claim.start_scale_word) if claim.start_scale_word else ''} to "
                        f"{claim.claimed_end}{(' ' + claim.end_scale_word) if claim.end_scale_word else ''}."
                    )
                    errors.append(err)
                    if claim.scene_number and claim.scene_number not in failing_scenes:
                        failing_scenes.append(claim.scene_number)
                elif claim.direction == "decrease" and end_raw > start_raw + 1e-6:
                    err = (
                        f"Scene {claim.scene_number}: Endpoint direction conflict for {entity}. "
                        f"Claimed decrease, but stated endpoints move upward from {claim.claimed_start}{(' ' + claim.start_scale_word) if claim.start_scale_word else ''} to "
                        f"{claim.claimed_end}{(' ' + claim.end_scale_word) if claim.end_scale_word else ''}."
                    )
                    errors.append(err)
                    if claim.scene_number and claim.scene_number not in failing_scenes:
                        failing_scenes.append(claim.scene_number)

                if not claim.is_percent:
                    candidates_delta_raw = [claimed_magnitude * claim.scale_multiplier]
                    if claim.scale_multiplier == 1.0 and claim.end_scale_multiplier > 1.0:
                        candidates_delta_raw.append(claimed_magnitude * claim.end_scale_multiplier)
                    elif claim.scale_multiplier > 1.0 and claim.end_scale_multiplier == 1.0:
                        candidates_delta_raw.append(claimed_magnitude)

                    min_discrepancy_raw = min(abs(cd - internal_delta_raw) for cd in candidates_delta_raw)
                    effective_scale = max(claim.scale_multiplier, claim.end_scale_multiplier, claim.start_scale_multiplier)
                    tol = max(0.05 * effective_scale, 0.05 * internal_delta_raw)
                    if min_discrepancy_raw > tol:
                        err = (
                            f"Scene {claim.scene_number}: Internal arithmetic conflict for {entity}. "
                            f"Stated values from {claim.claimed_start}{(' ' + claim.start_scale_word) if claim.start_scale_word else ''} to "
                            f"{claim.claimed_end}{(' ' + claim.end_scale_word) if claim.end_scale_word else ''} yield a difference of "
                            f"{abs(claim.claimed_end - claim.claimed_start):.2f}{(' ' + claim.end_scale_word) if claim.end_scale_word else ''}, "
                            f"but narration claimed change of {claim.claimed_val}{(' ' + claim.scale_word) if claim.scale_word else ''}."
                        )
                        errors.append(err)
                        if claim.scene_number and claim.scene_number not in failing_scenes:
                            failing_scenes.append(claim.scene_number)
                        continue

        return MathValidationReport(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            claims=claims,
            failing_scenes=failing_scenes,
        )

    @staticmethod
    def validate_script(
        script: Any,
        data: pd.DataFrame,
        topic_data: Optional[Dict[str, Any]] = None,
    ) -> MathValidationReport:
        """Validate entire script model scenes against DataFrame ground truth."""
        ground_truth = MathIntegrityEngine.compute_ground_truth(data, topic_data)
        known_entities = list(ground_truth.keys())

        default_entity = None
        if topic_data:
            story_metrics = topic_data.get("story_metrics")
            if isinstance(story_metrics, dict):
                default_entity = story_metrics.get("entity")

        if not default_entity and known_entities:
            default_entity = known_entities[0]

        is_rate = False
        if topic_data:
            is_rate = MathIntegrityEngine.is_rate_or_percentage_indicator(
                indicator_name=str(topic_data.get("indicator_name", "")),
                indicator_code=str(topic_data.get("indicator_code", "")),
                topic=str(topic_data.get("topic", "")),
            )

        all_claims: List[NumericalClaim] = []
        scenes = getattr(script, "scenes", [])

        for idx, scene in enumerate(scenes, start=1):
            narration = getattr(scene, "narration", "")
            claims = MathIntegrityEngine.extract_claims(
                text=narration,
                known_entities=known_entities,
                scene_number=idx,
            )
            all_claims.extend(claims)

        return MathIntegrityEngine.validate_claims(
            claims=all_claims,
            ground_truth=ground_truth,
            default_entity=default_entity,
            is_rate_indicator=is_rate,
        )

    @staticmethod
    def repair_script_math(
        script: Any,
        data: pd.DataFrame,
        topic_data: Optional[Dict[str, Any]] = None,
        max_retries: int = 1,
    ) -> bool:
        """Controlled surgical LLM repair of scenes that failed math validation.

        Does NOT use blind regex string replacement. Prompts the LLM with
        exact ground truth endpoints and required change deltas.
        Returns True if script is mathematically valid (either initially or after repair).
        Returns False if validation still fails after all attempts.
        """
        ground_truth = MathIntegrityEngine.compute_ground_truth(data, topic_data)
        if not ground_truth:
            return True

        for attempt in range(max_retries + 1):
            report = MathIntegrityEngine.validate_script(script, data, topic_data)
            if report.is_valid:
                return True

            if attempt >= max_retries:
                print(
                    f"🛑 Math integrity validation failed after {max_retries} surgical repair passes:\n"
                    + "\n".join(f"   - {err}" for err in report.errors)
                )
                return False

            print(
                f"🔧 Attempting surgical math repair pass {attempt + 1}/{max_retries} "
                f"for scenes {report.failing_scenes}..."
            )

            from app.groq_client import GroqLLM

            scenes = getattr(script, "scenes", [])
            for scene_num in report.failing_scenes:
                if not (1 <= scene_num <= len(scenes)):
                    continue

                scene = scenes[scene_num - 1]
                narration = getattr(scene, "narration", "")

                scene_errors = [e for e in report.errors if f"Scene {scene_num}:" in e]
                if not scene_errors:
                    continue

                facts = []
                for ent, gt in ground_truth.items():
                    if gt.has_sufficient_data:
                        pct_str = f"{gt.pct_change:+.1f}%" if gt.pct_change is not None else "N/A (zero baseline)"
                        facts.append(
                            f"- {ent}: {gt.start_year}={gt.start_val:.2f} -> {gt.end_year}={gt.end_val:.2f} "
                            f"(diff={gt.abs_change:+.2f}, relative={pct_str})"
                        )

                facts_block = "\n".join(facts[:8])

                repair_prompt = (
                    f"You are repairing ONE scene in a YouTube Shorts script that contains a mathematical error.\n\n"
                    f"Current scene {scene_num} narration:\n"
                    f'"{narration}"\n\n'
                    f"Mathematical errors detected:\n"
                    f"{chr(10).join(scene_errors)}\n\n"
                    f"Verified Ground Truth Data:\n"
                    f"{facts_block}\n\n"
                    f"REQUIREMENTS:\n"
                    f"1. Rewrite ONLY scene {scene_num}'s narration so all numbers and deltas exactly match ground truth.\n"
                    f"   State each entity's metrics in distinct simple sentences (e.g. 'Saudi Arabia leads at 6.48%. Lebanon rose to 2.51%.') to guarantee clear attribution.\n"
                    f"2. Keep the exact same narrative role, punchy tone, and dramatic pacing.\n"
                    f"3. Max 25 words. Plain text only in JSON.\n\n"
                    f'Reply ONLY with JSON: {{"narration": "..."}}'
                )

                try:
                    payload = GroqLLM.generate_structured(
                        repair_prompt,
                        temperature=0.3,
                        max_tokens=2048,
                        system=(
                            "You are a data-veracity editor ensuring numerical accuracy. "
                            "You must return ONLY a valid JSON object matching the requested schema."
                        ),
                    )
                    repaired = (
                        str(payload.get("narration", "")).strip()
                        if isinstance(payload, dict)
                        else ""
                    )
                    if repaired:
                        scene.narration = repaired
                        print(f"   ✓ Scene {scene_num} narration mathematically updated: '{repaired}'")
                except Exception as exc:
                    print(f"   ⚠️ Surgical repair failed for Scene {scene_num}: {exc}")

        return False
