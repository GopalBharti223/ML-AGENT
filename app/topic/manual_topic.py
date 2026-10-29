"""
Manual topic-selection engine.

Lets a human pin the data story by keyword (e.g. "birth rate",
"gdp", "population") instead of letting the automatic
SmartStoryEngine choose the topic.

DESIGN CONTRACT (approved plan):

- ADD-ONLY: this module never modifies any existing
  automatic-selection code path.

- Same-shape handoff: the manual path produces its result through
  the SAME factory the automatic path uses
  (SmartStoryEngine.StoryCandidate.to_topic_data()), so script,
  visual, QC, upload and database steps receive an
  identically-shaped topic_data dict on both paths.

- Deliberately SKIPPED here (they exist to fight *automatic*
  topic starvation and could silently swap away the requested
  topic):
      * AntiRepeatValidator hard blocks vs history
      * duplicate/repeat pruning vs recent records
      * TopicDistributionPreference country steering
      * CategoryRotationSelector random category roulette

- Deliberately KEPT (data-truthfulness gates, independent of how
  the indicator was chosen):
      * SmartStoryEngine.generate_candidates   (all 7 stories)
      * SmartStoryEngine._filter_candidates    (quality gates)
      * StoryQualityValidator.validate         (claims vs numbers)

- Winner selection is DETERMINISTIC (highest score, first wins
  ties) instead of random, because the user explicitly asked for
  this indicator.

SEMANTIC LAYER (this file only; automatic path untouched):

- resolve_keyword() remains the fast, deterministic
  direct-text matcher it always was and is the FIRST step --
  exact matches like "population", "gdp", "birth rate" never
  reach the network.

- When direct matching is weak or empty, ONE cheap Groq call
  maps the user's raw phrasing ("highest death ratio",
  "how many people are online") onto the single closest REAL
  indicator name taken from the full healthy-provider catalog,
  exactly as if a better keyword had been typed.  Resolution
  then continues through this SAME pipeline unchanged.

- The Groq seam (_llm_semantic_pick) is a single injectable
  function so offline tests can stub it deterministically.
  Any transport/parse failure degrades gracefully to today's
  pre-semantic behavior (weak direct match kept, otherwise the
  friendly-suggestions ManualTopicError -> automatic path).

- Random selection stays byte-for-byte the domain of
  SmartStoryEngine.select_best_candidate(); nothing here
  touches it.
"""

import random
import re
from typing import Dict, List, Optional, Tuple, Type

from app.data.providers.base import (
    DataProvider,
    IndicatorInfo,
    match_country_request,
)
from app.data.providers.registry import DataProviderRegistry
from app.topic.category_rotation import CategoryRotationSelector
from app.topic.smart_story import (
    SmartStoryEngine,
    StoryCandidate,
)
from app.topic.story_quality import StoryQualityValidator

# ---------------------------------------------------------
# Circuit-breaker awareness for the SEMANTIC catalog only.
# The direct matching tiers are deliberately left exactly as
# they always were (no health gating anywhere on that path);
# the LLM catalog simply refuses to advertise indicators from
# providers whose breaker is currently open.
#
# Guarded import: monitoring must never break resolution.
# ---------------------------------------------------------

try:

    from app.data.providers.health import (
        provider_health,
    )

except Exception:

    provider_health = None


class ManualTopicError(ValueError):
    """
    Raised when a keyword cannot be resolved to any usable
    indicator.  Carries friendly suggestion strings so callers
    can tell the user what IS available.
    """

    def __init__(self, message: str, suggestions=None):

        super().__init__(message)

        self.suggestions = suggestions or []


class ManualTopicEngine:

    # Provider evaluation order mirrors select_best_candidate's
    # default list so priorities hold identically on both paths.
    DEFAULT_PROVIDER_ORDER = [
        "viral_topics",
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
        "football_data",
        "rawg",
        "wikipedia",
    ]

    # Reuse auto-path constants so the dataset window fed into
    # candidate generation matches what run.py step 2 refetches.
    YEARS = SmartStoryEngine.DEFAULT_YEARS
    MIN_COUNTRIES = SmartStoryEngine.MIN_COUNTRIES
    BASE_FETCH_STORY = (
        SmartStoryEngine.PROVIDER_FETCH_STORY[
            "fastest_growth"
        ]
    )

    # -----------------------------------------------------
    # SEMANTIC FALLBACK TUNING (manual path only)
    #
    # SEMANTIC_CONFIDENT_TIER:
    #   Direct matches whose winning tier reaches this value
    #   put the keyword INSIDE the indicator name itself
    #   (6 exact, 5 prefix, 4 whole word, 3 substring) and are
    #   considered confident -- they NEVER trigger an LLM call
    #   and keep today's behavior byte-for-byte.
    #   Tier 2 (keyword inside the category label) and tier 1
    #   (inside the raw indicator code) are accidental-looking
    #   evidence, so the semantic step is consulted; its answer
    #   is prepended while the weak matches stay as backup.
    # -----------------------------------------------------

    SEMANTIC_CONFIDENT_TIER = 3

    # Cheap + fast: temperature 0, small token budget -- the
    # model only has to copy one name back out of a known list.

    SEMANTIC_TEMPERATURE = 0.0

    SEMANTIC_MAX_TOKENS = 512

    # Answer strings that mean "no real data topic fits".

    SEMANTIC_NONE_WORDS = {
        "NONE",
        "NOTHING",
        "N/A",
        "NA",
        "NO MATCH",
        "NO MATCHES",
        "UNKNOWN",
        "",
    }

    # -----------------------------------------------------
    # COUNTRY HINT PARSING (manual path only)
    #
    # _detect_country_tokens() is the OFFLINE trigger and
    # fallback; the LLM seam (when consulted) is the PRIMARY
    # parser because it understands context and demonyms.
    # Single-token detection only accepts KNOWN NAME FORMS --
    # never lookup()'s bare ISO-code fallback -- so English
    # words colliding with ISO 3166 codes ("are" -> ARE/UAE,
    # "and" -> AND/Andorra, "can" -> CAN/Canada) can never
    # produce a false hit.  "us"/"in"/"no" are additionally
    # stopworded: standalone they are overwhelmingly English
    # words, and the LLM path handles them when they really
    # mean the USA.
    # -----------------------------------------------------

    _COUNTRY_TOKEN_STOPWORDS = {"in", "no", "us"}


    # =========================================================
    # KEYWORD RESOLUTION
    #
    # Scores every indicator of every eligible provider against
    # the free-text keyword, best tier wins deterministically.
    # =========================================================

    @classmethod
    def resolve_keyword(
        cls,
        keyword: str,
        provider_ids: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[Tuple[str, IndicatorInfo]]:
        """
        Resolve free text into concrete (provider_id, indicator)
        matches, best-first.

        Matching tiers (higher wins):
          6 = exact indicator-name equality (case-insensitive)
          5 = name starts with the keyword
          4 = keyword appears as a whole word inside the name
          3 = plain substring inside the name
          2 = keyword inside the category label
          1 = keyword inside the raw indicator code

        Ties break by provider order (channel-curated sources
        first), then by shorter indicator name.
        """

        normalized = str(keyword or "").strip().lower()

        if not normalized:
            return []

        ordered_ids = cls._ordered_provider_ids(
            provider_ids
        )

        scored = []

        for provider_order, provider_id in enumerate(ordered_ids):

            try:

                provider = (
                    DataProviderRegistry.get(
                        provider_id
                    )
                )

            except Exception:

                continue

            indicators = cls._safe_list_indicators(
                provider
            )

            for indicator in indicators:

                tier = cls._match_tier(
                    normalized,
                    indicator,
                )

                if tier <= 0:
                    continue

                scored.append(
                    (
                        tier,
                        -provider_order,
                        -len(str(indicator.name)),
                        provider_id,
                        indicator,
                    )
                )

        scored.sort(
            key=lambda item: (
                item[0],
                item[1],
                item[2],
            ),
            reverse=True,
        )

        results = []

        seen_keys = set()

        for (
            _tier,
            neg_order,
            _neg_len,
            provider_id,
            indicator,
        ) in scored:

            key = (provider_id, indicator.code)

            if key in seen_keys:
                continue

            seen_keys.add(key)

            results.append((provider_id, indicator))

            if len(results) >= limit:
                break

        return results

    @staticmethod
    def _ordered_provider_ids(
        provider_ids: Optional[List[str]]
    ) -> List[str]:

        if provider_ids:
            return list(provider_ids)

        registered = set(
            DataProviderRegistry.list_providers()
        )

        return [
            provider_id
            for provider_id in ManualTopicEngine.DEFAULT_PROVIDER_ORDER
            if provider_id in registered
        ]

    @staticmethod
    def _safe_list_indicators(
        provider: Type[DataProvider]
    ) -> List[IndicatorInfo]:

        try:

            return list(provider.list_indicators())

        except Exception:

            return []


    @staticmethod
    def _match_tier(
        keyword: str,
        indicator: IndicatorInfo,
    ) -> int:

        name = str(indicator.name or "").strip().lower()
        code = str(indicator.code or "").strip().lower()
        category = str(
            indicator.category or ""
        ).strip().lower()

        if not name and not code:
            return 0

        if name == keyword:
            return 6

        if name.startswith(keyword):
            return 5

        words = {
            word.strip(",.:;()[]|-")
            for word in name.split()
        }

        if keyword in words:
            return 4

        if keyword in name:
            return 3

        tokens = [t.strip(",.:;()[]|-") for t in keyword.split() if len(t.strip(",.:;()[]|-")) >= 2]
        if len(tokens) > 1 and all(t in name for t in tokens):
            return 3

        # Plural/stem tolerance (e.g. 'smartphones' vs 'smartphone', 'consoles' vs 'console')
        stem = keyword[:-1] if keyword.endswith("s") and len(keyword) > 3 else keyword
        if stem in name or stem in code:
            return 3

        if any(len(w) >= 4 and w in keyword for w in words):
            return 3

        if category and keyword in category:
            return 2

        if keyword in code:
            return 1

        return 0

    # =========================================================
    # SEMANTIC RESOLUTION (manual path only)
    #
    # One cheap Groq call maps free-text user intent onto the
    # single closest REAL indicator name from the full healthy
    # provider catalog.  Never consulted when a direct tier
    # already matched the keyword into an indicator NAME.
    # =========================================================

    @classmethod
    def _catalog_entries(
        cls,
        provider_ids: Optional[List[str]] = None,
    ) -> List[Tuple[int, str, IndicatorInfo]]:
        """
        Every listable indicator from every ordered provider
        that is currently reachable, as
        (provider_order, provider_id, indicator).

        Mirrors resolve_keyword()'s provider ordering exactly;
        providers whose circuit breaker is OPEN are skipped so
        the LLM can only pick something actually fetchable.
        """

        entries = []

        for provider_order, provider_id in enumerate(
            cls._ordered_provider_ids(provider_ids)
        ):

            try:

                provider = DataProviderRegistry.get(
                    provider_id
                )

            except Exception:

                continue

            if provider_health is not None:

                try:

                    if not provider_health.is_available(
                        provider_id
                    ):

                        continue

                except Exception:

                    pass  # monitoring must never break matching

            for indicator in cls._safe_list_indicators(
                provider
            ):

                entries.append(
                    (
                        provider_order,
                        provider_id,
                        indicator,
                    )
                )

        return entries

    @classmethod
    def _detect_country_tokens(
        cls,
        keyword: str,
    ) -> List[str]:
        """
        Offline, zero-network recognition of country mentions
        inside the raw keyword.  Greedy longest-first n-gram
        matching against the app.countries catalog.

        Used as (a) the trigger that lets a CONFIDENT direct
        indicator match still spend its one LLM call on country
        parsing ("India vs USA military" hits the Military
        indicator on tier 4 and would otherwise never reach the
        LLM), and (b) the fallback hint when the LLM is
        unavailable.  Returns canonical display names.
        """

        from app.countries import (
            lookup as country_lookup,
            name_forms,
        )

        known_names = name_forms()

        tokens = re.findall(
            r"[A-Za-z][A-Za-z.']*" ,
            str(keyword or ""),
        )

        total = len(tokens)

        found: List[str] = []
        consumed = set()

        for size in (3, 2, 1):

            start = 0

            while start + size <= total:

                window = range(
                    start,
                    start + size,
                )

                if any(
                    position in consumed
                    for position in window
                ):
                    start += 1
                    continue

                gram = " ".join(
                    tokens[start:start + size]
                ).strip()

                entry = None

                if size >= 2:

                    entry = country_lookup(gram)

                else:

                    word = gram.lower()

                    if (
                        word
                        in cls._COUNTRY_TOKEN_STOPWORDS
                    ):

                        if word == "us":

                            _iso_entry = (
                                country_lookup(word)
                            )

                            if _iso_entry:

                                print(
                                    "  [COUNTRY-DETECT] "
                                    f"'{word}' is also the "
                                    "ISO2 code for "
                                    f"{_iso_entry['display']} "
                                    "but was skipped as an "
                                    "English stopword; the "
                                    "semantic step resolves "
                                    "it when reachable."
                                )

                        start += 1
                        continue

                    name_key = re.sub(
                        r"[^a-z0-9]+",
                        " ",
                        word,
                    ).strip()

                    if name_key in known_names:

                        entry = country_lookup(gram)

                if entry:

                    display = entry["display"]

                    if display not in found:
                        found.append(display)

                    for position in window:
                        consumed.add(position)

                    start += size
                    continue

                start += 1

        return found

    @staticmethod
    def _normalize_label(label: str) -> str:
        """
        Case/whitespace normalization shared by prompt labels
        and any LLM answer before membership is decided.
        """

        return " ".join(
            str(label or "").split()
        ).lower()

    @staticmethod
    def _llm_semantic_pick(
        keyword: str,
        indicator_names: List[str],
    ) -> Optional[Dict]:
        """
        The ONLY network seam of the semantic step.

        ONE cheap Groq call does BOTH jobs:
          1. copies back the single closest indicator name from
             `indicator_names` (or NONE) -- exactly as before -- and
          2. extracts the specific COUNTRIES the user asked for
             ("India vs USA military" -> ["India", "USA"]).

        Returns a dict:
            {"indicator": <label str, or None for clean NONE answers>,
             "countries": <raw token list, or None when the transport
                           payload carried no country field at all
                           (legacy stub contract)>}

        The caller (_semantic_matches) owns ALL validation against
        the catalog / country metadata, so offline tests can stub
        this seam with either the NEW dict contract or the LEGACY
        plain-string contract; both are accepted there.

        Transport failures PROPAGATE; _semantic_matches() owns
        the graceful-degradation policy.
        """

        from app.groq_client import GroqLLM

        numbered = "\n".join(
            f"{index}. {name}"
            for index, name in enumerate(
                indicator_names,
                start=1,
            )
        )

        prompt = (
            "User wants a data story about: "
            f"\"{keyword}\"\n"
            "\n"
            "Pick the SINGLE closest indicator from "
            "this list.\n"
            "\n"
            "ALSO: if the keyword names specific "
            "countries, list them under "
            "\"countries\". Only the countries the "
            "USER explicitly asked about (e.g. "
            "\"India vs USA military\" -> India and "
            "USA), never every country in the data. "
            "If the keyword names no specific "
            "country, use an empty list.\n"
            "\n"
            'Reply with JSON only:\n'
            '{"indicator": "<copy the indicator text '
            'EXACTLY>", "countries": ["<country name>", '
            '...]}\n'
            "or {\"indicator\": \"NONE\", "
            "\"countries\": []} if nothing on the "
            "list reasonably matches.\n"
            "\n"
            "Indicators:\n"
            f"{numbered}"
        )

        payload = GroqLLM.generate_structured(
            prompt,
            temperature=(
                ManualTopicEngine.SEMANTIC_TEMPERATURE
            ),
            max_tokens=(
                ManualTopicEngine.SEMANTIC_MAX_TOKENS
            ),
            system=(
                "You are a strict topic matcher for a "
                "data-provider catalog. Reply ONLY with "
                "the JSON object requested."
            ),
        )

        picked = ""

        raw_countries = None

        if isinstance(payload, dict):

            picked = str(
                payload.get("indicator", "")
            )

            if isinstance(
                payload.get("countries"),
                list
            ):

                raw_countries = [
                    str(item)
                    for item in payload["countries"]
                ]

        picked = (
            picked.strip()
            .strip("\"'`")
            .strip()
        )

        # Tolerate index answers even though the prompt asks
        # for exact text: costs nothing, adds robustness.

        if picked.isdigit():

            index = int(picked)

            if 1 <= index <= len(indicator_names):

                return {
                    "indicator":
                        indicator_names[index - 1],
                    "countries": raw_countries,
                }

            return {
                "indicator": None,
                "countries": raw_countries,
            }

        if (
            picked.upper()
            in ManualTopicEngine.SEMANTIC_NONE_WORDS
        ):
            return {
                "indicator": None,
                "countries": raw_countries,
            }

        if not picked:
            return {
                "indicator": None,
                "countries": raw_countries,
            }

        return {
            "indicator": picked,
            "countries": raw_countries,
        }

    @staticmethod
    def _validate_country_hint(
        raw_countries,
    ) -> Optional[List[str]]:
        """
        Normalize raw LLM country tokens via app.countries.lookup()
        (handles "usa", "United States", "IN", ISO3 codes, aliases).

        Returns:
          None            -- the seam provided NO country answer at
                             all (legacy stub / payload without the
                             key / transport failure): caller falls
                             back to offline detection
          []              -- the seam SAW the keyword and found no
                             countries: trusted, no fallback
          [display, ...]  -- canonical display names, deduplicated,
                             input order preserved

        Unrecognized tokens are logged and ignored -- never an
        error (ambiguous/junk input must not break resolution).
        """

        if raw_countries is None:
            return None

        from app.countries import (
            lookup as country_lookup,
        )

        validated: List[str] = []

        for token in raw_countries:

            token = str(token or "").strip()

            if not token:
                continue

            entry = country_lookup(token)

            if entry:

                if entry["display"] not in validated:
                    validated.append(entry["display"])

            else:

                print(
                    "  [SEMANTIC] Country token "
                    f"'{token}' not recognized; "
                    "ignoring it."
                )

        return validated

    # -----------------------------------------------------
    # ENTITY-COMPARISON ROUTE (manual path only)
    #
    # "Tesla vs BYD", "Messi vs Ronaldo": the keyword names
    # specific non-country entities.  Indicator matching can only
    # pick an INDICATOR, so a fixed-list provider (SEC's 18
    # companies) silently compared such requests against whichever
    # entities it happens to carry.  This route detects comparison
    # keywords, probes whether any existing provider dataset
    # genuinely covers ALL named entities, and otherwise routes to
    # the Wikipedia pageviews provider, which can compare ANY
    # notable named entity (search-interest framing).  A failed
    # route falls through to the previous behavior unchanged.
    # -----------------------------------------------------

    _ENTITY_VS_RE = re.compile(
        r"^\s*(?P<left>.{1,60}?)\s+"
        r"(?:vs\.?|versus)\s+"
        r"(?P<right>.{1,60}?)\s*$",
        re.IGNORECASE,
    )

    # Indicator-flavored words: a side containing one of these is
    # an indicator phrase, not an entity ("gdp of India vs China"
    # stays on the country/indicator path).
    _ENTITY_METRIC_WORDS = {
        "gdp", "population", "inflation", "debt", "co2",
        "energy", "internet", "revenue", "income", "assets",
        "spending", "expenditure", "mortality", "expectancy",
        "users", "urban", "electricity", "health", "education",
        "military", "points", "wins", "standings", "publications",
        "pageviews", "members", "favorites", "score", "adoption",
        "talent", "investment", "policy", "life", "per", "capita",
    }

    _ENTITY_COVERAGE_CACHE: Dict[
        Tuple[str, Tuple[str, ...]],
        bool,
    ] = {}

    @classmethod
    def _detect_entity_comparison(
        cls,
        keyword: str,
    ) -> List[str]:
        """Detect an 'X vs Y' comparison keyword.

        Returns the two raw side names, or [] when the keyword is
        not a comparison or either side looks like an indicator
        phrase rather than a named entity.
        """
        match = cls._ENTITY_VS_RE.match(
            str(keyword or "").strip()
        )

        if not match:
            return []

        names = []

        for part in (
            match.group("left"),
            match.group("right"),
        ):

            name = re.sub(
                r"\s+",
                " ",
                str(part or ""),
            ).strip(" ,.:;!?()[]'\"")

            words = name.split()

            if not words:
                return []

            lowered = [word.lower() for word in words]

            if any(
                word in cls._ENTITY_METRIC_WORDS
                for word in lowered
            ):
                return []

            if any("vs" == word or "versus" == word for word in lowered):
                return []

            names.append(name)

        if len(names) != 2:
            return []

        return names

    # =========================================================
    # SINGLE-ENTITY SUPERLATIVE QUERIES (manual path only)
    #
    # Broadens entity-comparison detection beyond "X vs Y" to
    # single-entity superlative questions scoped to a country
    # or region: "richest person in India", "tallest building
    # in Dubai", "most popular actor in Brazil".
    #
    # - Wealth queries ("richest person", "billionaire"...) have
    #   NO free, ToS-compliant data source (Forbes real-time data
    #   requires scraping which violates their ToS). These are
    #   detected and HONESTLY DECLINED with a clear log message,
    #   then fall through to the existing fallback/suggestions.
    #
    # - Other superlatives (fame, popularity, physical size, age)
    #   route through the EXISTING Wikipedia pageviews pipeline
    #   (search-interest framing) when the LLM can propose real
    #   verifiable entities.
    # =========================================================
    _SUPERLATIVE_ALTERNATION = (
        r"(?:most\s+\w+(?:\s+\w+)?|"  # "most popular", "most well known"
        r"richest|wealthiest|poorest|wealthy|"
        r"tallest|shortest|biggest|smallest|largest|"
        r"oldest|youngest|newest|fastest|slowest|"
        r"longest|highest|lowest|best|worst|top)"
    )

    # Scope-last form: "richest person in India",
    # "tallest building in Dubai", "most popular actor
    # in Brazil".  Spoken prefixes ("who is the richest
    # person in India") are stripped.
    _SUPERLATIVE_QUERY_RE = re.compile(
        r"^\s*"
        r"(?:who\s+is\s+(?:the\s+)?|what\s+is\s+(?:the\s+)?|"
        r"name\s+the\s+|the\s+)?"
        r"(?P<superlative>" + _SUPERLATIVE_ALTERNATION + r")\s+"
        r"(?P<noun>.+?)\s+"
        r"(?:in|within|from)\s+"
        r"(?P<scope>.+?)\s*$",
        re.IGNORECASE,
    )

    # Scope-first form: "India's richest person",
    # "India richest person", "Dubai's tallest building".
    _SUPERLATIVE_SCOPE_FIRST_RE = re.compile(
        r"^\s*(?P<scope>.+?)\s*(?:['’]s?|['’])?\s+"
        r"(?:the\s+)?"
        r"(?P<superlative>" + _SUPERLATIVE_ALTERNATION + r")\s+"
        r"(?P<noun>.+?)\s*$",
        re.IGNORECASE,
    )

    # Superlative words that indicate wealth / net-worth queries.
    # These have NO free reliable data source and must decline.
    _WEALTH_SUPERLATIVE_WORDS = {
        "richest", "wealthiest", "wealthy", "poorest",
        "billionaire", "millionaire", "net worth",
        "net-worth", "net worths", "richest person",
        "wealthiest person", "richest people",
        "wealthiest people",
    }

    # Nouns that turn a wealth superlative into a COUNTRY
    # question ("richest country in Europe") -- answerable from
    # GDP/GNI country data, so no wealth decline may fire.
    _COUNTRY_NOUN_WORDS = {
        "country", "countries", "economy", "economies",
        "nation", "nations", "state", "states",
    }

    @classmethod
    def _detect_superlative_query(
        cls,
        keyword: str,
    ) -> Optional[Tuple[str, str, str]]:
        """Detect a single-entity superlative question.

        Handles BOTH word orders:
          scope-last:  "richest person in India",
                       "who is the tallest building in Dubai"
          scope-first: "India's richest person",
                       "India richest person"

        Returns (superlative_word, noun_phrase, scope_phrase) or
        None when the keyword is not a superlative question.

        Example: "richest person in India" ->
            ("richest", "person", "India")
        "India's richest person" ->
            ("richest", "person", "India")
        """
        text = str(keyword or "").strip()

        if not text:
            return None

        match = cls._SUPERLATIVE_QUERY_RE.match(text)

        if not match:

            match = cls._SUPERLATIVE_SCOPE_FIRST_RE.match(
                text
            )

            if not match:
                return None

        superlative = match.group("superlative").strip()
        noun = match.group("noun").strip()
        scope = match.group("scope").strip()

        # Guard: reject queries that are actually indicator phrases
        # (e.g., "gdp of india" has no superlative, but "biggest gdp
        # in india" is a country-indicator query, not an entity query).
        # Token membership -- NOT substring -- so "person" does not
        # trip the "per" (per-capita) entry.
        lowered_noun = noun.lower()
        noun_tokens = {
            token.strip(".,!?;:'\"()")
            for token in lowered_noun.split()
        }
        if any(
            token in cls._ENTITY_METRIC_WORDS
            for token in noun_tokens
        ):
            return None

        # Guard: degenerate scopes ("the fastest car" parses with
        # scope "the") are not scoped superlative questions.
        scope_tokens = scope.lower().split()
        if (
            scope_tokens
            and scope_tokens[0] in ("the", "a", "an")
            and len(scope_tokens) == 1
        ):
            return None

        return (superlative, noun, scope)

    @classmethod
    def _is_wealth_superlative(
        cls,
        superlative_word: str,
    ) -> bool:
        """Check whether a superlative word indicates wealth."""
        lowered = superlative_word.lower()
        return any(
            w in lowered
            for w in cls._WEALTH_SUPERLATIVE_WORDS
        )

    @classmethod
    def _detect_wealth_superlative_query(
        cls,
        keyword: str,
    ) -> Optional[Tuple[str, str, str]]:
        """Detect a wealth/net-worth superlative query.

        Returns (superlative, noun, scope) when the keyword asks
        for a PERSON/COMPANY wealth ranking ("richest person in
        India", "India's richest person").  Country-shaped nouns
        ("richest country in Europe") return None -- those are
        answerable from GDP/GNI country data and must stay on the
        country path.
        """
        detected = cls._detect_superlative_query(keyword)

        if not detected:
            return None

        sup_word, noun, scope = detected

        lowered_noun = noun.lower()

        if any(
            word in lowered_noun
            for word in cls._COUNTRY_NOUN_WORDS
        ):
            return None

        if cls._is_wealth_superlative(sup_word) or any(
            word in lowered_noun
            for word in cls._WEALTH_SUPERLATIVE_WORDS
        ):
            return (sup_word, noun, scope)

        return None

    @classmethod
    def _llm_entity_titles(
        cls,
        keyword: str,
        entity_names: List[str],
    ) -> Optional[List[Dict[str, str]]]:
        """
        The ONLY network seam of the entity-comparison step.

        ONE cheap Groq call turns the raw keyword into real
        comparable entities plus their canonical English Wikipedia
        article titles.  Returns [{"name", "title"}, ...] or None
        on any failure (offline tests stub this seam; the caller
        then falls back to the keyword-derived names).
        """
        from app.groq_client import GroqLLM

        named = ", ".join(entity_names)

        prompt = (
            'User wants a data story comparing: "'
            f"{keyword}\"\n"
            "\n"
            "Propose 2-4 real-world entities to compare. The "
            f"named ones ({named}) MUST be included unless they "
            "are fictional or not notable enough for a Wikipedia "
            "article.\n"
            "Prefer direct head-to-head rivals of the same kind "
            "(companies, people, products, teams, works). Do NOT "
            "propose countries unless the user explicitly asked "
            "for countries.\n"
            "For each entity give its canonical English Wikipedia "
            "article title (exact title, no URL, no disambiguation "
            "parentheses unless part of the title).\n"
            "\n"
            "Reply with JSON only:\n"
            '{"entities": [{"name": "<display name>", '
            '"wikipedia_title": "<exact article title>"}, ...]}\n'
            "If no sensible real-entity comparison exists, reply "
            '{"entities": []}'
        )

        payload = GroqLLM.generate_structured(
            prompt,
            temperature=0.0,
            max_tokens=512,
            system=(
                "You map comparison requests to real entities and "
                "their Wikipedia article titles. Reply ONLY with "
                "the JSON object requested."
            ),
        )

        entities = (
            payload.get("entities")
            if isinstance(payload, dict)
            else None
        )

        if not isinstance(entities, list):
            return None

        proposals = []

        for item in entities:

            if not isinstance(item, dict):
                continue

            name = str(item.get("name", "")).strip()
            title = str(
                item.get("wikipedia_title", "")
            ).strip()

            if name and title:
                proposals.append(
                    {"name": name, "title": title}
                )

        return proposals or None

    @staticmethod
    def _llm_superlative_entities(
        keyword: str,
        superlative: str,
        noun: str,
        scope: str,
    ) -> Optional[List[Dict[str, str]]]:
        """LLM seam for single-entity superlative queries.

        Proposes 2-4 real-world entities matching the superlative
        + scope (e.g., "most popular actor in India" -> top Indian
        actors), with their canonical Wikipedia article titles.
        Returns None on any failure so the caller can degrade.

        Mirrors _llm_entity_titles: ONE cheap Groq call, same JSON
        contract, temperature 0.
        """
        from app.groq_client import GroqLLM

        prompt = (
            f'User wants a data story about: "{keyword}"\n'
            "\n"
            f"Superlative: '{superlative}'  Noun: '{noun}'  "
            f"Scope: '{scope}'\n"
            "\n"
            "Propose 2-4 real-world entities that are the best "
            "candidates for this superlative query. "
            "Focus on notable, verifiable entities within the "
            f"scope ({scope}) that have Wikipedia articles.\n"
            "Do NOT propose countries if the query is about a "
            "sub-national scope; only do so if the user asked "
            "about countries.\n"
            "For each entity give its canonical English Wikipedia "
            "article title (exact title, no URL, no disambiguation "
            "parentheses unless part of the title).\n"
            "\n"
            'Reply with JSON only:\n'
            '{"entities": [{"name": "<display name>", '
            '"wikipedia_title": "<exact article title>"}, ...]}\n'
            "If no sensible real entities exist for this query, "
            'reply {"entities": []}\n'
        )

        payload = GroqLLM.generate_structured(
            prompt,
            temperature=0.0,
            max_tokens=512,
            system=(
                "You map superlative queries to real entities and "
                "their Wikipedia article titles. Reply ONLY with "
                "the JSON object requested."
            ),
        )

        entities = (
            payload.get("entities")
            if isinstance(payload, dict)
            else None
        )

        if not isinstance(entities, list):
            return None

        proposals = []

        for item in entities:
            if not isinstance(item, dict):
                continue

            name = str(item.get("name", "")).strip()
            title = str(
                item.get("wikipedia_title", "")
            ).strip()

            if name and title:
                proposals.append(
                    {"name": name, "title": title}
                )

        return proposals or None

    @staticmethod
    def _normalized_entity_token(value: str) -> str:
        """Collapse a name to lowercase alphanumerics for probing."""
        return "".join(
            character
            for character in str(value or "").lower()
            if character.isalnum()
        )

    @classmethod
    def _probe_provider_entities(
        cls,
        provider_id: str,
        entity_names: List[str],
    ) -> bool:
        """Cheaply probe whether one provider's dataset covers ALL
        the named entities (so its real data can serve the request).

        sec_edgar checks its static company list (no network);
        jolpica_f1 / jikan / nhtsa do ONE or TWO cheap API calls;
        country-shaped providers return False (the country path
        already owns those keywords).
        """

        def contains(haystacks, needle: str) -> bool:
            token = cls._normalized_entity_token(needle)
            if not token:
                return False
            for hay in haystacks:
                hay_token = cls._normalized_entity_token(hay)
                if not hay_token:
                    continue
                if token in hay_token or hay_token in token:
                    return True
            return False

        if provider_id == "sec_edgar":
            from app.data.providers.sec_edgar import (
                SECEdgarProvider,
            )

            known = (
                list(SECEdgarProvider.COMPANIES.keys())
                + list(SECEdgarProvider.COMPANIES.values())
            )
            return all(
                contains(known, name)
                for name in entity_names
            )

        if provider_id == "jolpica_f1":
            from datetime import date as _date
            from app.data.providers.jolpica_f1 import (
                JolpicaF1Provider,
            )

            season = str(_date.today().year - 1)
            known = []
            for endpoint in (
                "driverstandings",
                "constructorstandings",
            ):
                try:
                    rows = JolpicaF1Provider._fetch_standings(
                        endpoint,
                        season,
                    )
                except Exception:
                    continue
                known.extend(
                    row.get("name", "") for row in rows
                )
            if not known:
                return False
            return all(
                contains(known, name)
                for name in entity_names
            )

        if provider_id == "jikan":
            from app.data.providers.jikan import JikanProvider

            known = []
            for page in (1, 2):
                try:
                    rows = JikanProvider._fetch_top_anime(
                        page=page
                    )
                except Exception:
                    continue
                known.extend(
                    row.get("title", "") for row in rows
                )
            if not known:
                return False
            return all(
                contains(known, name)
                for name in entity_names
            )

        if provider_id == "nhtsa":
            from app.data.providers.nhtsa import NHTSAProvider

            try:
                rows = NHTSAProvider._fetch_manufacturers()
            except Exception:
                return False
            known = [
                row.get("name", "") for row in rows
            ]
            return all(
                contains(known, name)
                for name in entity_names
            )

        if provider_id == "solar_system":
            # Static NASA dataset -- no network needed.  Any planet
            # name (with or without metric-suffix noise from the
            # entity detector, e.g. "Mars: Gravity Comparison") is
            # covered when the substring matches a body.
            from app.data.providers.solar_system import (
                SolarSystemProvider,
            )

            try:
                known = [
                    body["name"]
                    for body in SolarSystemProvider._load_bodies()
                ]
            except Exception:
                return False
            if not known:
                return False
            return all(
                contains(known, name)
                for name in entity_names
            )

        return False

    @classmethod
    def _provider_entity_coverage(
        cls,
        provider_id: str,
        entity_names: List[str],
    ) -> bool:
        """Cached wrapper around _probe_provider_entities."""
        cache_key = (
            provider_id,
            tuple(
                sorted(
                    name.lower() for name in entity_names
                )
            ),
        )

        if cache_key in cls._ENTITY_COVERAGE_CACHE:
            return cls._ENTITY_COVERAGE_CACHE[cache_key]

        try:
            covered = cls._probe_provider_entities(
                provider_id,
                entity_names,
            )
        except Exception as error:
            print(
                f"  [ENTITY] Coverage probe for "
                f"'{provider_id}' failed: {error}"
            )
            covered = False

        cls._ENTITY_COVERAGE_CACHE[cache_key] = covered

        return covered

    @classmethod
    def _wikipedia_entity_match(
        cls,
        keyword: str,
        entity_names: List[str],
    ):
        """Tier-2 entity-comparison route via Wikipedia pageviews.

        1. The LLM proposes real comparable entities + their
           Wikipedia article titles (fallback: keyword-derived
           names when the seam is unavailable).
        2. Each title is verified against the pageview API; a
           title without data is retried with opensearch
           alternates; entities with no usable data are dropped.
        3. The route only proceeds when >= 2 entities verify.

        Returns (path_label, [(wikipedia, indicator)], titles) or
        None to fall through to the previous behavior unchanged.
        """
        from app.countries import lookup as country_lookup
        from app.data.providers.wikipedia import (
            WikipediaPageviewsProvider,
        )

        proposals = None

        try:
            proposals = cls._llm_entity_titles(
                keyword,
                entity_names,
            )
        except Exception as error:
            print(
                "  [ENTITY] LLM entity proposal failed "
                f"({type(error).__name__}: {error}); using "
                "keyword-derived names."
            )

        if not proposals:
            proposals = [
                {"name": name, "title": name}
                for name in entity_names
            ]

        # All-country comparisons belong to the existing country
        # path ("gdp of India vs China" -> India vs China GDP).
        if all(
            country_lookup(proposal["name"])
            for proposal in proposals
        ):
            print(
                "  [ENTITY] All proposed entities are "
                "countries; keeping the country path."
            )
            return None

        try:
            verified, failed = (
                WikipediaPageviewsProvider.probe_entities(
                    proposals
                )
            )
        except Exception as error:
            print(
                "  [ENTITY] Wikipedia verification failed: "
                f"{error}"
            )
            return None

        if failed:
            print(
                "  [ENTITY] No pageview data for: "
                f"{', '.join(failed)} (dropped)"
            )

        if len(verified) < 2:
            print(
                f"  [ENTITY] Only {len(verified)} verifiable "
                "entities; not enough for a comparison."
            )
            return None

        provider = DataProviderRegistry.get("wikipedia")

        indicators = cls._safe_list_indicators(provider)

        if not indicators:
            return None

        entity_display = ", ".join(verified.keys())

        label = (
            "Entity comparison via Wikipedia pageviews "
            "(search interest, NOT sales/revenue): "
            f"{entity_display}"
        )

        return (
            label,
            [(provider.provider_id, indicators[0])],
            list(verified.values()),
        )

    @classmethod
    def _wikipedia_superlative_match(
        cls,
        keyword: str,
        superlative: str,
        noun: str,
        scope: str,
    ):
        """Tier-2 single-entity superlative route via Wikipedia.

        Reuses the existing _wikipedia_entity_match verification/
        routing logic, but the LLM proposal step uses a
        superlative-specific prompt (propose top N entities
        matching the superlative + scope, rather than "include
        these named entities").

        Returns (path_label, [(wikipedia, indicator)], titles) or
        None to fall through to the previous behavior — identical
        contract to _wikipedia_entity_match.
        """
        from app.countries import lookup as country_lookup
        from app.data.providers.wikipedia import (
            WikipediaPageviewsProvider,
        )

        proposals = None

        try:
            proposals = cls._llm_superlative_entities(
                keyword,
                superlative,
                noun,
                scope,
            )
        except Exception as error:
            print(
                "  [SUPERLATIVE] LLM entity proposal failed "
                f"({type(error).__name__}: {error})."
            )
            return None

        if not proposals:
            print(
                "  [SUPERLATIVE] LLM proposed no real entities; "
                "falling back to indicator matching."
            )
            return None

        # If ALL proposed entities are countries, this is really a
        # country-data query — keep the country path.
        if all(
            country_lookup(proposal["name"])
            for proposal in proposals
        ):
            print(
                "  [SUPERLATIVE] All proposed entities are "
                "countries; keeping the country path."
            )
            return None

        try:
            verified, failed = (
                WikipediaPageviewsProvider.probe_entities(
                    proposals
                )
            )
        except Exception as error:
            print(
                "  [SUPERLATIVE] Wikipedia verification failed: "
                f"{error}"
            )
            return None

        if failed:
            print(
                "  [SUPERLATIVE] No pageview data for: "
                f"{', '.join(failed)} (dropped, real data only)"
            )

        if len(verified) < 2:
            print(
                f"  [SUPERLATIVE] Only {len(verified)} verifiable "
                "entities; not enough for a comparison."
            )
            return None

        provider = DataProviderRegistry.get("wikipedia")

        indicators = cls._safe_list_indicators(provider)

        if not indicators:
            return None

        entity_display = ", ".join(verified.keys())

        label = (
            "Superlative query via Wikipedia pageviews "
            "(public search interest — NOT verified "
            f"{noun} rankings): {entity_display}"
        )

        return (
            label,
            [(provider.provider_id, indicators[0])],
            list(verified.values()),
        )

    @classmethod
    def _semantic_matches(
        cls,
        keyword: str,
        provider_ids: Optional[List[str]] = None,
    ) -> Tuple[
        Optional[str],
        List[Tuple[str, IndicatorInfo]],
        Optional[List[str]],
    ]:
        """
        Build the healthy-provider catalog, make ONE LLM call,
        then map the returned name back to concrete
        (provider_id, indicator) pairs using the SAME tie-breaks
        as resolve_keyword (provider order first).  Duplicate
        indicator names across providers stay allowed --
        channel-curated ordering decides who wins.

        This method NEVER raises: any seam failure degrades to
        (None, []) so today's pre-semantic behavior survives an
        outage of the matcher itself.

        Returns (picked_display_name_or_None, matches,
        country_hint) where country_hint is:
          None     -> seam gave no country answer (caller falls
                      back to offline detection)
          []       -> seam saw the keyword and found no countries
          [str,..] -> validated canonical display names
        """

        entries = cls._catalog_entries(
            provider_ids=provider_ids,
        )

        display_names = []

        sources: Dict[
            str,
            List[Tuple[int, str, IndicatorInfo]],
        ] = {}

        for (
            provider_order,
            provider_id,
            indicator,
        ) in entries:

            label = str(indicator.name).strip()

            key = cls._normalize_label(label)

            if not key:
                continue

            bucket = sources.get(key)

            if bucket is None:

                sources[key] = [
                    (
                        provider_order,
                        provider_id,
                        indicator,
                    )
                ]

                display_names.append(label)

            else:

                bucket.append(
                    (
                        provider_order,
                        provider_id,
                        indicator,
                    )
                )

        if not display_names:
            return (None, [], None)

        try:

            seam_result = cls._llm_semantic_pick(
                str(keyword or "").strip(),
                display_names,
            )

        except Exception as error:

            print(
                f"  [SEMANTIC] LLM lookup failed "
                f"({type(error).__name__}: {error}); "
                "continuing without it."
            )

            return (None, [], None)

        # -----------------------------------------------------
        # Accept BOTH seam contracts: the new dict
        # {"indicator", "countries"} and the LEGACY plain string
        # (offline stubs written before country parsing existed).
        # -----------------------------------------------------

        picked = None

        raw_countries = None

        if isinstance(seam_result, dict):

            picked = seam_result.get("indicator")

            if isinstance(
                seam_result.get("countries"),
                list
            ):

                raw_countries = list(
                    seam_result["countries"]
                )

        elif isinstance(seam_result, str):

            picked = seam_result

        validated_countries = (
            cls._validate_country_hint(
                raw_countries
            )
        )

        if picked is None:
            return (
                None,
                [],
                validated_countries,
            )

        key = cls._normalize_label(picked)

        bucket = sources.get(key)

        if not bucket:

            print(
                f"  [SEMANTIC] Answer '{picked}' is not "
                "in the provided catalog; ignoring it."
            )

            return (None, [], validated_countries)

        results = []

        seen_keys = set()

        for (
            _provider_order,
            provider_id,
            indicator,
        ) in sorted(bucket, key=lambda item: item[0]):

            pair_key = (provider_id, indicator.code)

            if pair_key in seen_keys:
                continue

            seen_keys.add(pair_key)

            results.append((provider_id, indicator))

        canonical_label = next(
            label
            for label in display_names
            if cls._normalize_label(label) == key
        )

        return (
            canonical_label,
            results,
            validated_countries,
        )

    @classmethod
    def resolve_topic_path(
        cls,
        keyword: str,
        provider_ids: Optional[List[str]] = None,
    ) -> Tuple[
        str,
        List[Tuple[str, IndicatorInfo]],
        List[str],
    ]:
        """
        Full manual-path resolution policy (the ONLY new
        caller-facing step on this path).

        1. FAST PATH: resolve_keyword()'s direct tiers.  When the
           winning match places the keyword inside the indicator
           name (tier >= SEMANTIC_CONFIDENT_TIER) AND the keyword
           mentions no countries, no LLM call happens at all --
           keywords that matched directly before this change
           behave exactly as they always did.
        2. COUNTRY DETECTION (offline, free): recognize country
           names/aliases in the raw keyword.  Detection never
           fires on bare ISO-code fallbacks, so English words
           colliding with ISO codes can not false-trigger.
        3. SEMANTIC STEP: weak/absent textual evidence OR a
           detected country hint triggers ONE Groq call over the
           full healthy catalog; the call returns BOTH the
           indicator pick AND the parsed countries.  The LLM is
           the primary country parser (context/demonyms); its
           validated answer wins over offline detection, and
           offline detection is the fallback when the seam fails.
        4. ENTITY / SUPERLATIVE ROUTES: keywords naming specific
           non-country entities ("Tesla vs BYD") or single-entity
           superlatives ("tallest building in Dubai", "India's
           biggest tech company") resolve through the Wikipedia
           pageviews pipeline with honest search-interest
           framing.  Wealth superlatives about people/companies
           ("richest person in India") are declined BEFORE any
           LLM call -- no free, ToS-compliant wealth data source
           exists -- and surface as suggestions, never as
           fabricated numbers.
        5. FALLBACKS: a seam failure, a junk answer, or an honest
           NONE degrade gracefully -- first to whatever weak
           direct matches existed, otherwise to the automatic
           path via generate_manual_topic()'s unchanged
           ManualTopicError contract.

        Returns (path_label, matches, country_hint) where
        country_hint is a (possibly empty) list of canonical
        display names the user explicitly requested, and
        path_label starts with one of:
              "Direct match ..."            (no/failed LLM)
              "Semantic match via LLM..."
              "No match — falling back to automatic"
              "No match — wealth ranking declined ..."
        """

        normalized = str(keyword or "").strip().lower()

        matches = cls.resolve_keyword(
            keyword,
            provider_ids=provider_ids,
        )

        top_tier = 0

        if matches and normalized:

            top_tier = cls._match_tier(
                normalized,
                matches[0][1],
            )

        # Offline country detection (cheap, no network).

        detected_countries = (
            cls._detect_country_tokens(
                normalized
            )
        )

        # FAST PATH: confident direct match and nothing
        # country-shaped in the keyword -> unchanged behavior,
        # zero LLM cost.

        if (
            top_tier >= cls.SEMANTIC_CONFIDENT_TIER
            and not detected_countries
        ):

            return ("Direct match", matches, [])

        # -----------------------------------------------------
        # WEALTH SUPERLATIVE FAST DECLINE (manual path only)
        #
        # "Richest person in India" / "India's richest person":
        # NO free, ToS-compliant wealth-ranking data source
        # exists (Forbes' real-time list is scrape-only, which
        # violates their ToS; Wikidata's net-worth property is
        # sparse and unmaintained).  Declining HERE -- before
        # the semantic LLM call -- prevents the query from
        # being silently converted into a country-stat story
        # and keeps the honest explanation attached to the
        # suggestions the caller prints.
        # -----------------------------------------------------

        wealth_superlative = (
            cls._detect_wealth_superlative_query(keyword)
        )

        if wealth_superlative:

            sup_word, sup_noun, sup_scope = wealth_superlative

            try:
                vt_provider = DataProviderRegistry.get("viral_topics")
                for ind in vt_provider.list_indicators():
                    if ind.code == "top_billionaires_net_worth":
                        print(
                            "  [SUPERLATIVE] Wealth/net-worth ranking "
                            f"('{sup_word} {sup_noun}') for '{sup_scope}' "
                            "-> matched verified Forbes Billionaires Archives."
                        )
                        return (
                            "Wealth ranking via Forbes Billionaires Archives",
                            [("viral_topics", ind)],
                            [],
                        )
            except Exception:
                pass

            print(
                "  [SUPERLATIVE] Wealth/net-worth ranking "
                f"('{sup_word} {sup_noun}') requested for "
                f"'{sup_scope}' but no free, ToS-compliant "
                "data source exists (Forbes real-time data "
                "requires scraping their site). Declining "
                "honestly -- no numbers will be fabricated."
            )

            return (
                "No match — wealth ranking declined "
                "(no free ToS-compliant data source)",
                [],
                [],
            )

        semantic_label = None

        semantic_matches = []

        llm_countries = None

        if normalized and (
            top_tier < cls.SEMANTIC_CONFIDENT_TIER
            or detected_countries
        ):

            (
                semantic_label,
                semantic_matches,
                llm_countries,
            ) = cls._semantic_matches(
                keyword,
                provider_ids=provider_ids,
            )

        # Country hint precedence: a validated LLM answer (even
        # an explicit EMPTY one) wins because the LLM saw the
        # full keyword context; only an ABSENT answer (legacy
        # stub / transport failure) falls back to detection.

        if llm_countries is None:

            country_hint = list(detected_countries)

        else:

            country_hint = list(llm_countries)

        # -----------------------------------------------------
        # ENTITY-COMPARISON ROUTE (manual path only)
        #
        # A keyword naming specific non-country entities can never
        # be satisfied by indicator matching alone.  When no
        # existing provider dataset genuinely covers ALL the named
        # entities (cheap cached probes; SEC's static list, F1
        # standings, top anime, manufacturer directory), route to
        # the Wikipedia pageviews provider, which can compare ANY
        # notable named entity with honest search-interest
        # framing.  A failed route falls through unchanged.
        # -----------------------------------------------------

        entity_names = cls._detect_entity_comparison(keyword)

        if entity_names:

            from app.countries import (
                lookup as _country_lookup,
            )

            if not all(
                _country_lookup(name)
                for name in entity_names
            ):

                candidate_pairs = list(matches) + list(
                    semantic_matches
                )

                covering = [
                    provider_id
                    for provider_id, _indicator
                    in candidate_pairs
                    if cls._provider_entity_coverage(
                        provider_id,
                        entity_names,
                    )
                ]

                if covering:

                    print(
                        "  [ENTITY] "
                        f"{', '.join(entity_names)} fully "
                        f"covered by {covering[0]}; using its "
                        "real dataset."
                    )

                else:

                    entity_route = (
                        cls._wikipedia_entity_match(
                            keyword,
                            entity_names,
                        )
                    )

                    if entity_route is not None:
                        return entity_route

        # -----------------------------------------------------
        # SUPERLATIVE-QUERY ROUTE (manual path only)
        #
        # Broadens entity detection beyond "X vs Y" to single-
        # entity superlative questions scoped to a country/region:
        # "tallest building in Dubai", "most popular actor in
        # Brazil", "India's biggest tech company".
        #
        # - Wealth superlatives never reach this block: person/
        #   company nouns are declined EARLY (before the semantic
        #   LLM call, see the fast-decline block above) and
        #   country nouns stay on the country path.
        # - Other superlatives (fame, popularity, physical size,
        #   age) route through the Wikipedia pageviews pipeline
        #   (search-interest framing) when the LLM can propose
        #   real, verified entities.  A failed route falls
        #   through to the previous behavior unchanged.
        # -----------------------------------------------------
        superlative = cls._detect_superlative_query(keyword)

        if superlative and not cls._is_wealth_superlative(
            superlative[0]
        ):

            sup_word, sup_noun, sup_scope = superlative

            # Route to the Wikipedia dynamic-entity pipeline.
            superlative_route = cls._wikipedia_superlative_match(
                keyword,
                sup_word,
                sup_noun,
                sup_scope,
            )

            if superlative_route is not None:
                return superlative_route

        countries_suffix = (
            f" [countries: {', '.join(country_hint)}]"
            if country_hint
            else ""
        )

        confident_direct = (
            top_tier >= cls.SEMANTIC_CONFIDENT_TIER
        )

        if confident_direct:

            # Confident direct match + country hint: the direct
            # match keeps PRIORITY; the semantic picks from the
            # same LLM call become ordered backups.

            merged = list(matches)

            existing = {
                (pid, indicator.code)
                for pid, indicator in merged
            }

            for pid, indicator in semantic_matches:

                pair_key = (pid, indicator.code)

                if pair_key in existing:
                    continue

                existing.add(pair_key)

                merged.append((pid, indicator))

            if country_hint:

                if semantic_matches:

                    label = (
                        "Direct match (country "
                        "hint parsed via LLM"
                        f"{countries_suffix})"
                    )

                else:

                    label = (
                        "Direct match (country "
                        "hint from offline "
                        f"detection{countries_suffix})"
                    )

            else:

                label = "Direct match"

            return (label, merged, country_hint)

        if semantic_matches:

            merged = list(semantic_matches)

            existing = {
                (pid, indicator.code)
                for pid, indicator in merged
            }

            for pid, indicator in matches:

                pair_key = (pid, indicator.code)

                if pair_key in existing:
                    continue

                existing.add(pair_key)

                merged.append((pid, indicator))

            detail = (
                f": '{semantic_label}'"
                if semantic_label else ""
            )

            return (
                f"Semantic match via LLM{detail}"
                f"{countries_suffix}",
                merged,
                country_hint,
            )

        if matches:

            return (
                "Direct match (weak text tier; "
                "semantic step found nothing)"
                f"{countries_suffix}",
                matches,
                country_hint,
            )

        return (
            "No match — falling back to automatic"
            f"{countries_suffix}",
            [],
            country_hint,
        )

    # =========================================================
    # MANUAL TOPIC CONSTRUCTION
    # =========================================================

    @classmethod
    def generate_manual_topic(
        cls,
        keyword: str,
        provider_ids: Optional[List[str]] = None,
        seed: Optional[int] = None,
    ) -> dict:
        """
        Full manual-path entry point.

        Resolves the keyword, fetches the winning indicator ONCE
        (same recipe as select_best_candidate), builds every
        story-type candidate through the SAME scoring machinery
        as the automatic path, applies unchanged quality gates,
        then deterministically picks the strongest valid
        candidate.

        Returns the exact dict shape produced by
        SmartStoryEngine.generate_topic().

        Raises ManualTopicError (with suggestions) when nothing
        usable matches the keyword.
        """

        # Resolution policy: direct text tiers first; when the
        # keyword is weak OR names specific countries, one cheap
        # LLM semantic call decides the indicator and parses the
        # countries in the SAME call.  The label makes transparent
        # which path decided.  When empty, raise exactly as before
        # -- run.py prints suggestions and falls back to automatic.
        path_label, matches, country_hint = (
            cls.resolve_topic_path(
                keyword,
                provider_ids=provider_ids,
            )
        )

        print(f"\n[MATCH] {path_label}")

        if country_hint:

            print(
                "  [Target] Specific countries/entities "
                "requested: "
                f"{', '.join(country_hint)}"
            )

        if not matches:

            raise ManualTopicError(
                "No supported indicator found "
                f"for '{str(keyword).strip()}'.",
                suggestions=(
                    cls.available_topics(
                        provider_ids=provider_ids
                    )
                ),
            )

        last_error = ""

        for provider_id, indicator in matches:

            try:

                candidate = cls._build_best_candidate(
                    provider_id,
                    indicator,
                    seed=seed,
                    countries=country_hint,
                )

            except Exception as error:

                print(
                    f"  [WARN] {provider_id}/"
                    f"{indicator.code} candidate build "
                    f"failed: {type(error).__name__}: "
                    f"{error}"
                )

                last_error = str(error)

                continue

            if candidate is None:
                continue

            # ENTITY PRESENCE CHECK: if the keyword names a specific
            # entity that the LLM used for routing (e.g. "Samsung"),
            # verify that entity is actually in the fetched data.
            # SEC EDGAR's static company list may not include the
            # requested company — without this check the system would
            # silently generate a video about a DIFFERENT company
            # (Tesla/Adobe/Alphabet) that happens to be the chart
            # winner.  When the entity is missing, skip this match
            # and fall through to the next provider (or decline).
            # Skip this check for Wikipedia (it can resolve any entity
            # dynamically and the keyword may be a comparison like
            # "Tesla vs BYD" that doesn't match a single data row).
            if provider_id != "wikipedia":
                entity_mismatch = cls._check_entity_in_data(
                    keyword,
                    candidate,
                    country_hint=country_hint,
                )
            else:
                entity_mismatch = None
            if entity_mismatch:
                print(
                    f"  [ENTITY] Keyword entity '{entity_mismatch}' "
                    f"not found in {provider_id} data — skipping "
                    f"(would misroute to a different entity)"
                )
                last_error = (
                    f"Entity '{entity_mismatch}' not in "
                    f"{provider_id} dataset"
                )
                continue

            topic_data = candidate.to_topic_data()

            print(
                "\n[SELECTED] Manual keyword "
                f"'{str(keyword).strip()}' -> "
                f"{topic_data['topic']} "
                f"({topic_data['provider_id']}/"
                f"{topic_data['indicator_code']}/"
                f"{topic_data['story_type']}) "
                f"score="
                f"{float(topic_data['smart_score']):.2f}"
            )

            return topic_data

        # WIKIPEDIA FALLBACK: if all provider matches failed (e.g. SEC
        # EDGAR declined because the entity isn't in its static list),
        # try the Wikipedia dynamic-entity resolver as a last resort.
        # This handles single-entity keywords like "Samsung" that the
        # entity-comparison detector (which needs "vs") never catches.
        #
        # The fallback returns a ROUTE tuple -- (path_label, matches,
        # titles) -- the SAME shape _wikipedia_entity_match() returns,
        # NOT a topic dict.  The candidate is then built through
        # _build_best_candidate() so the returned topic_data carries
        # the exact full to_topic_data() schema (category, chart_type,
        # years, provider_fetch_story_type, story_metrics, ...).
        # HISTORY: an earlier version returned a hand-built partial
        # dict here (9 keys, no 'category'), which crashed
        # ScriptEngine with KeyError: 'category' and silently broke
        # every downstream consumer of the shape contract.
        wiki_route = cls._try_wikipedia_fallback(keyword)

        if wiki_route is not None:

            route_label, route_matches, route_titles = wiki_route

            print(f"\n[WIKIPEDIA FALLBACK] {route_label}")

            for route_pid, route_indicator in route_matches:

                try:

                    candidate = cls._build_best_candidate(
                        route_pid,
                        route_indicator,
                        seed=seed,
                        countries=route_titles,
                    )

                except Exception as error:

                    print(
                        "  [WARN] Wikipedia fallback "
                        f"{route_pid}/"
                        f"{route_indicator.code} failed: "
                        f"{type(error).__name__}: {error}"
                    )

                    last_error = str(error)

                    continue

                if candidate is None:
                    continue

                topic_data = candidate.to_topic_data()

                print(
                    "\n[SELECTED] Manual keyword "
                    f"'{str(keyword).strip()}' -> "
                    f"{topic_data['topic']} "
                    f"({topic_data['provider_id']}/"
                    f"{topic_data['indicator_code']}/"
                    f"{topic_data['story_type']}) "
                    f"score="
                    f"{float(topic_data['smart_score']):.2f}"
                )

                return topic_data

        hints = (
            f" Last provider error: {last_error}"
            if last_error else ""
        )

        raise ManualTopicError(
            f"Keyword '{str(keyword).strip()}' resolved "
            f"({len(matches)} match(es)) but no candidate "
            f"passed the shared quality gates.{hints}",
            suggestions=(
                cls.available_topics(
                    provider_ids=provider_ids
                )
            ),
        )


    @classmethod
    def _check_entity_in_data(
        cls,
        keyword: str,
        candidate,
        country_hint: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Check if the keyword's entity is present in the candidate data.

        Returns the entity name if it IS missing (triggering a skip),
        or None if the entity is present (or no specific entity).

        The check must only fire when the keyword NAMES a specific
        non-country entity (e.g. "Samsung" routed to SEC EDGAR).
        It must NOT fire for:
          - country keywords / country comparisons ("India vs USA
            Military", "military spending brazil india") -- those are
            validated by the country-matching path;
          - free-form questions;
          - single generic indicator words ("military", "gdp").
        False positives here silently kill legitimate requests, so
        the check errs on the side of SKIPPING when the keyword does
        not clearly name one proper-noun entity.
        """
        from app.countries import is_widely_recognized

        kw = str(keyword or "").strip()

        if not kw or len(kw) < 2:
            return None

        # LLM/country detection found countries in the keyword --
        # country requests are validated by the dataset country-matching
        # path, not by this entity heuristic.
        if country_hint:
            return None

        # "X vs Y" comparisons (countries or companies) are resolved
        # by the entity-comparison route, not this check.
        _kw_flat = re.sub(r"\s+", " ", kw.lower())

        if " vs " in f" {_kw_flat} " or " versus " in f" {_kw_flat} ":
            return None

        # Free-form multi-word questions cannot be post-hoc reduced to
        # a single entity string ("who still rules streaming?").
        if len(kw.split()) > 8:
            return None

        # Collect proper-noun candidates from the keyword.
        names = set()

        for token in re.split(r"[\\s,;:?!'\"]+", kw):

            if not token:
                continue

            if not re.match(r"[A-Z][A-Za-z0-9'&-]{1,}", token):
                continue

            # Skip country names (e.g. "US", "USA", "India") -- those
            # are handled by the country-matching path.
            if is_widely_recognized(token):
                continue

            names.add(token)

        if not names:
            return None

        # Drop tokens that are really the INDICATOR/topic words of the
        # matched dataset ("Military" in "India vs USA Military" is the
        # indicator name, not an entity to check).
        indicator_text = (
            f"{getattr(candidate, 'indicator_name', '')} "
            f"{getattr(candidate, 'topic', '')}"
        ).lower()

        indicator_tokens = {
            part
            for part in re.findall(
                r"[a-z0-9']+", indicator_text
            )
        }

        names = {
            name
            for name in names
            if name.lower() not in indicator_tokens
        }

        if not names:
            return None

        data = None

        if (
            hasattr(candidate, "metrics")
            and isinstance(candidate.metrics, dict)
        ):
            data = candidate.metrics.get("data")

        if data is None or (
            hasattr(data, "empty") and data.empty
        ):
            return None

        # Any one namespace token matching a data entity means the
        # keyword's subject IS represented in the dataset.
        for idx in data.index:

            name_in_data = str(idx).strip()

            if not name_in_data:
                continue

            for name in names:

                if (
                    name.lower() in name_in_data.lower()
                    or name_in_data.lower() in name.lower()
                ):
                    return None  # Entity found

        # Entity NOT found -- signal the mismatch so the caller skips
        # this match (would misroute to a different entity's chart).
        return kw

    @classmethod
    def _try_wikipedia_fallback(
        cls,
        keyword: str,
    ) -> Optional[Tuple[str, list, List[str]]]:
        """Last-resort Wikipedia dynamic-entity ROUTE finder.

        Handles keywords naming notable non-country entities (e.g.
        "Samsung", or a free-form question like "Netflix: who still
        rules streaming searches?") that no provider's static dataset
        covers.  The LLM proposes comparable entities and each
        proposal is verified against the Wikipedia pageview API.

        Returns the SAME route tuple _wikipedia_entity_match()
        returns -- (path_label, [(wikipedia, indicator)], titles) --
        so the caller builds the candidate through the normal
        _build_best_candidate() pipeline and gets a FULL-schema
        to_topic_data() dict back.  Returns None to decline
        unchanged (the caller then raises ManualTopicError).

        HISTORY: an earlier version returned a hand-built partial
        topic dict here.  It carried only 9 keys and was missing
        category / chart_type / years / provider_fetch_story_type /
        indicator_name / topic_family / story_metrics /
        selected_min_countries, which violated the module's
        same-shape handoff contract and crashed ScriptEngine with
        KeyError: 'category'.  Do NOT rebuild a topic dict here --
        always route through _build_best_candidate().
        """
        from app.countries import is_widely_recognized

        kw = str(keyword or "").strip()

        if not kw or len(kw) < 2:
            return None

        # Generic single words and country names belong to the
        # indicator/country paths, not the entity route.
        _GENERIC = {
            'gdp', 'population', 'energy', 'health', 'education',
            'internet', 'debt', 'revenue', 'income', 'assets',
            'growth', 'decline', 'rank', 'top', 'best', 'worst',
        }

        if kw.lower() in _GENERIC or is_widely_recognized(kw):
            return None

        # Ask the LLM for comparable entities + Wikipedia titles.
        # The LLM seam is nondeterministic; retry once before giving
        # up so free-form keywords ("who still rules streaming?")
        # don't randomly lose the route on a single flake.
        proposals = None
        last_error = ""

        for _attempt in range(2):

            try:
                proposals = cls._llm_entity_titles(keyword, [kw])
            except Exception as error:
                last_error = str(error)
                proposals = None

            if proposals:
                break

            print(
                "  [ENTITY] LLM entity proposal retry "
                f"(attempt {_attempt + 1})"
                f"{' — ' + last_error if last_error else ''}"
            )

        if not proposals:
            return None

        # All-country comparisons belong to the existing country
        # path ("gdp of India vs China" -> India vs China GDP).
        from app.countries import lookup as country_lookup

        if all(
            country_lookup(
                str(p.get("name", ""))
                if isinstance(p, dict)
                else str(p)
            )
            for p in proposals
        ):
            return None

        # Verify each proposed title against the pageview API;
        # entities with no usable data are dropped.
        try:
            from app.data.providers.wikipedia import (
                WikipediaPageviewsProvider,
            )

            verified, failed = (
                WikipediaPageviewsProvider.probe_entities(
                    proposals
                )
            )
        except Exception:
            return None

        if failed:
            print(
                "  [ENTITY] No pageview data for: "
                f"{', '.join(failed)} (dropped)"
            )

        if len(verified) < 2:
            return None

        provider = DataProviderRegistry.get("wikipedia")

        indicators = cls._safe_list_indicators(provider)

        if not indicators:
            return None

        entity_display = ", ".join(verified.keys())

        label = (
            "Wikipedia entity fallback (search interest, "
            "NOT sales/revenue): "
            f"{entity_display}"
        )

        return (
            label,
            [(provider.provider_id, indicators[0])],
            list(verified.values()),
        )

    @staticmethod
    def _prefer_requested_country(
        validated_candidates,
        countries: Optional[List[str]],
    ):
        """
        Manual-path story preference: among already quality-
        validated, score-sorted candidates, return the highest
        scoring candidate whose story FOCUS is one of the
        countries the user explicitly requested.

        Focus = the story's entity/leader/challenger name(s),
        matched by ISO2 so display-name aliases agree
        ("USA" == "United States" == "US").

        Graceful fallback: when NO validated story centres on a
        requested country (e.g. India's military-spend % is flat
        and no hero story passes the gates), the previous best
        candidate is returned unchanged -- the request never
        lowers quality.
        """

        if not countries:
            if validated_candidates:
                return validated_candidates[0]
            return None

        from app.countries import (
            lookup as country_lookup,
        )

        requested_iso2 = set()

        for country in countries:

            entry = country_lookup(country)

            if entry:
                requested_iso2.add(
                    entry["iso2"].upper()
                )

        if not requested_iso2:

            if validated_candidates:
                return validated_candidates[0]
            return None

        for candidate in validated_candidates:

            focus = []

            metrics = getattr(
                candidate,
                "metrics",
                None,
            )

            if isinstance(metrics, dict):

                for key in (
                    "entity",
                    "leader",
                    "challenger",
                ):

                    value = metrics.get(key)

                    if value:
                        focus.append(
                            str(value)
                        )

            for entity in focus:

                entry = country_lookup(entity)

                if (
                    entry
                    and entry["iso2"].upper()
                    in requested_iso2
                ):
                    return candidate

        return validated_candidates[0]

    @classmethod
    def _build_best_candidate(
        cls,
        provider_id: str,
        indicator: IndicatorInfo,
        seed: Optional[int] = None,
        countries: Optional[List[str]] = None,
    ) -> Optional[StoryCandidate]:
        """
        Fetch once, generate every story type, apply quality
        gates + story validation, return the highest-scoring
        valid candidate.

        `countries` is the optional country hint parsed from the
        manual keyword (canonical display names).  When present
        the Step-1 fetch is constrained to those countries
        ("required + context") -- via the SAME optional
        `countries` parameter the provider layer exposes -- so
        Step 1 and Step 2 operate on the user's requested
        dataset.

        Mirrors the automatic pipeline stage-for-stage UNTIL the
        point where history/category/randomness layers would
        normally apply -- intentionally omitted for manual
        selections (see module docstring).
        """

        provider = DataProviderRegistry.get(
            provider_id
        )

        print(
            f"\n[MANUAL] {provider_id.upper()} fetching "
            f"{indicator.code} ({indicator.name}) ..."
        )

        # Same fetch recipe the automatic path uses for its base
        # dataset: one "fastest_growth" fetch, then every story
        # type is derived analytically from that single frame.
        # `countries` narrows the fetch when the user named
        # specific countries -- only for providers whose
        # fetch_normalized implements the optional parameter.
        fetch_kwargs = {
            "indicator_code": indicator.code,
            "years": cls.YEARS,
            "story_type": cls.BASE_FETCH_STORY,
            "min_countries": cls.MIN_COUNTRIES,
        }

        if (
            countries
            and getattr(
                provider,
                "supports_countries",
                lambda: False,
            )()
        ):

            fetch_kwargs["countries"] = countries

        elif countries:

            print(
                f"  [MANUAL] Provider "
                f"'{provider.provider_id}' does not "
                "support country filtering; "
                "ignoring the country request."
            )

        result = provider.fetch_normalized(
            **fetch_kwargs
        )

        # Entity-comparison datasets (Wikipedia pageviews route)
        # legitimately carry only 2 rows for a head-to-head; the
        # entity gates accept 2 instead of the historical 3 for
        # THIS path only (fetch already guarantees >= 2).
        min_valid_entities = None

        if (
            getattr(provider, "entity_comparison", False)
            and countries
        ):
            min_valid_entities = 2

        wide_data = result.wide_data

        if wide_data is None or wide_data.empty:

            print(
                f"  [X] {indicator.code}: no "
                "visual-grade data returned."
            )

            return None

        candidates = SmartStoryEngine.generate_candidates(
            provider_id=provider_id,
            indicator_code=indicator.code,
            indicator_name=result.metric_name,
            category=(
                indicator.category or ""
            ),
            source_name=result.source_name,
            source_url=result.source_url,
            data=wide_data,
            years=cls.YEARS,
            min_valid_entities=min_valid_entities,
            snapshot_only=bool(
                getattr(provider, "snapshot_only", False)
            ),
            allowed_story_types=getattr(
                provider, "SUPPORTED_STORY_TYPES", None
            ),
        )

        if not candidates:

            print(
                f"  [X] {indicator.code}: zero "
                "derivable story candidates."
            )

            return None

        gated = SmartStoryEngine._filter_candidates(
            candidates,
            min_valid_entities=min_valid_entities,
        )

        if not gated:

            print(
                f"  [X] {indicator.code}: all "
                "candidates failed quality gates."
            )

            return None

        validated = []

        for candidate in gated:

            verdict = StoryQualityValidator.validate(
                candidate.metrics,
                story_type=candidate.story_type,
                title=candidate.topic,
                indicator_name=(
                    candidate.indicator_name
                ),
                min_countries=min_valid_entities,
            )

            if verdict.get("valid"):
                validated.append(candidate)

            else:

                print(
                    f"  [QUALITY] Rejected "
                    f"{candidate.story_type}: "
                    f"{verdict.get('reasons')}"
                )

        if not validated:

            print(
                f"  [X] {indicator.code}: all "
                "candidates failed story-quality "
                "validation."
            )

            return None

        validated.sort(
            key=lambda item: item.score,
            reverse=True,
        )

        winner = cls._prefer_requested_country(
            validated,
            countries,
        )

        if winner is None:
            return None

        # Channel curiosity-angle naming, applied exactly like the
        # automatic finisher does, so downstream consumers see the
        # same topic-string convention on both paths.
        rng = (
            random.Random(seed)
            if seed is not None
            else random.Random()
        )

        winner.topic = (
            CategoryRotationSelector
            ._apply_story_angle(winner, rng)
        )

        if countries:

            # Anchor Step-2's refetch to the countries the user
            # explicitly asked for ("required + context") rather
            # than whatever Step 1 happened to rank top.  The
            # provider already dropped any requested country with
            # no usable data (logged warning); the hint keeps the
            # remaining request verbatim so Step 2 reproduces the
            # SAME dataset -- this is the key link that makes the
            # Part A plumbing deliver Issue 1.
            winner.selected_countries = list(
                countries
            )

        return winner

    # =========================================================
    # USER-FACING DISCOVERY
    # =========================================================

    @classmethod
    def available_topics(
        cls,
        provider_ids: Optional[List[str]] = None,
        limit: int = 14,
    ) -> List[str]:
        """
        Human-readable list of resolvable indicator names, used
        for error messages and interactive menus.
        """

        ordered_ids = cls._ordered_provider_ids(
            provider_ids
        )

        names = []

        for provider_id in ordered_ids:

            try:

                provider = (
                    DataProviderRegistry.get(
                        provider_id
                    )
                )

            except Exception:

                continue

            for indicator in cls._safe_list_indicators(
                provider
            ):

                label = str(indicator.name).strip()

                if label and label not in names:
                    names.append(label)

        return names[:limit]

