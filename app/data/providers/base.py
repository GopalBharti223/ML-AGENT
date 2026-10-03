from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from inspect import signature
from typing import Dict, List, Optional

import pandas as pd


@dataclass(frozen=True)
class IndicatorInfo:

    code: str
    name: str
    category: str = ""
    source_url: str = ""


@dataclass(frozen=True)
class ProviderMetadata:
    """
    Rich metadata about a data provider.

    Used by the topic engine to decide whether a category is
    eligible:
      provider exists -> enabled -> real data available
      -> passes validation -> category becomes eligible.

    commercial_use values:
      - "ALLOWED"         : clearly permitted (e.g., public-domain
                            government data, CC0).
      - "REVIEW_REQUIRED" : free API exists but commercial use of
                            the dataset is unclear or needs a special
                            tier.  Do NOT silently treat as unlimited.
      - "PROHIBITED"      : source clearly forbids commercial use.
    """
    provider_id: str
    provider_name: str
    category: str
    supported_topics: List[str] = field(default_factory=list)
    supported_indicators: List[str] = field(default_factory=list)
    countries_or_regions: str = "Global"
    historical_coverage: str = "Varies by source"
    latest_data_date: str = "Unknown"
    license: str = "Unknown"
    commercial_use: str = "REVIEW_REQUIRED"
    attribution_required: bool = False
    rate_limit: str = "Varies"
    requires_api_key: bool = False
    enabled: bool = True
    source_url: str = ""


@dataclass
class DataProviderResult:

    provider: str
    indicator_code: str
    metric_name: str
    source_name: str
    source_url: str
    normalized_data: pd.DataFrame
    wide_data: pd.DataFrame
    metadata: Dict


class DataProvider(ABC):

    provider_id: str
    provider_name: str

    @classmethod
    def supports_countries(cls) -> bool:

        """
        True when this provider's fetch_normalized implements the
        optional `countries` parameter (worldbank, owid, imf).
        Non-country providers (F1, anime, vehicles, companies...)
        keep their unchanged signatures and simply ignore the
        hint -- callers use this to avoid passing an unsupported
        keyword.
        """

        try:

            return (
                "countries"
                in signature(
                    cls.fetch_normalized
                ).parameters
            )

        except (TypeError, ValueError):

            return False

    @classmethod
    def is_configured(cls) -> bool:
        """
        True when this provider can attempt real fetches.

        Key-gated providers (football_data, rawg) override this
        to report whether their API key is present, so automatic
        rotation can skip them cleanly instead of burning the
        fetch budget on guaranteed failures.  The default is
        always-configured (all keyless providers).
        """

        return True

    @classmethod
    @abstractmethod
    def list_indicators(cls) -> List[IndicatorInfo]:
        raise NotImplementedError

    @classmethod
    def search_indicators(
        cls,
        query: str
    ) -> List[IndicatorInfo]:

        query = str(
            query or ""
        ).strip().lower()

        indicators = cls.list_indicators()

        if not query:
            return indicators

        return [
            indicator
            for indicator in indicators
            if (
                query in indicator.code.lower()
                or query in indicator.name.lower()
                or query in indicator.category.lower()
            )
        ]

    @classmethod
    @abstractmethod
    def fetch_normalized(
        cls,
        indicator_code: str,
        years: int = 15,
        story_type: str = "fastest_growth",
        min_countries: int = 8,
        countries: Optional[List[str]] = None
    ) -> DataProviderResult:
        """
        Fetch a normalized dataset for one indicator.

        `countries` (OPTIONAL, non-breaking default None) is a
        hint of specific countries a user explicitly asked for
        (names, aliases, ISO2 or ISO3 codes).  When given, the
        provider MUST guarantee every requested country that has
        usable data is present in the returned frame, then fill
        the remaining slots up to `min_countries` with the
        highest-ranked remaining countries ("required + context").
        Countries without usable data are dropped with a logged
        warning -- never a hard failure.  Providers with no
        concept of countries may ignore the hint entirely.
        """
        raise NotImplementedError

    @classmethod
    def fetch_data(
        cls,
        indicator_code: str,
        years: int = 15,
        story_type: str = "fastest_growth",
        min_countries: int = 8,
        countries: Optional[List[str]] = None
    ) -> pd.DataFrame:

        fetch_kwargs = {
            "indicator_code": indicator_code,
            "years": years,
            "story_type": story_type,
            "min_countries": min_countries,
        }

        # Only forward the country hint to providers whose
        # fetch_normalized actually implements it (worldbank,
        # owid, imf); non-country providers keep their unchanged
        # signature and never see the keyword.
        if countries and cls.supports_countries():

            fetch_kwargs["countries"] = countries

        result = cls.fetch_normalized(
            **fetch_kwargs
        )

        return result.wide_data


def normalize_long_data(
    rows: List[Dict],
    provider: str,
    metric_name: str,
    source_name: str,
    source_url: str,
    indicator_code: str
) -> pd.DataFrame:

    normalized = pd.DataFrame(
        rows,
        columns=[
            "country",
            "country_code",
            "year",
            "metric",
            "value",
            "provider",
            "source_name",
            "source_url",
            "indicator_code",
        ]
    )

    if normalized.empty:
        return normalized

    normalized["country"] = (
        normalized["country"]
        .astype(str)
        .str.strip()
    )

    normalized["country_code"] = (
        normalized["country_code"]
        .astype(str)
        .str.strip()
    )

    normalized["year"] = pd.to_numeric(
        normalized["year"],
        errors="coerce"
    )

    normalized["value"] = pd.to_numeric(
        normalized["value"],
        errors="coerce"
    )

    normalized = normalized.dropna(
        subset=[
            "country",
            "country_code",
            "year",
            "value"
        ]
    )

    normalized["year"] = (
        normalized["year"]
        .astype(int)
    )

    normalized["metric"] = metric_name
    normalized["provider"] = provider
    normalized["source_name"] = source_name
    normalized["source_url"] = source_url
    normalized["indicator_code"] = indicator_code

    normalized = normalized.drop_duplicates(
        subset=[
            "country_code",
            "year",
            "metric"
        ],
        keep="first"
    )

    return normalized


def to_visual_dataframe(
    normalized: pd.DataFrame,
    result_metadata: Optional[Dict] = None
) -> pd.DataFrame:

    if normalized.empty:
        return pd.DataFrame()

    pivot = normalized.pivot(
        index=[
            "country_code",
            "country"
        ],
        columns="year",
        values="value"
    )

    pivot = pivot.sort_index(
        axis=1
    )

    metadata = dict(
        result_metadata or {}
    )

    pivot.attrs.update(
        metadata
    )

    pivot.attrs[
        "normalized_data"
    ] = normalized

    return pivot


# =========================================================
# COUNTRY-HINT RESOLUTION (shared by worldbank / owid / imf)
#
# Supports the optional `countries` fetch parameter: free-form
# tokens a user explicitly requested ("India", "usa",
# "United Kingdom", "IND", "GBR", ...) resolved against the
# (code, name) pairs of a real dataset frame.
# =========================================================

def normalize_country_token(token) -> str:
    """Collapse a token to lowercase alphanumerics for matching."""
    return "".join(
        character
        for character in str(token or "").lower()
        if character.isalnum()
    )


def match_country_request(
    requested_tokens,
    code_name_pairs
):
    """
    Resolve free-form country tokens against the (code, name)
    pairs of a dataset frame.

    Matching precedence per token:
      1. exact normalized code or name match
      2. app.countries.lookup() alias/ISO2/ISO3 match, mapped to
         frame pairs whose NAME resolves to the same ISO2 country
         (so "UK" finds World Bank's "United Kingdom"/GBR and
         "South Korea" finds "Korea, Rep."/KOR)

    Returns (matched_pairs, unmatched_tokens):
      matched_pairs    -- (code, name) pairs from
                          code_name_pairs, in requested-token
                          order, deduplicated
      unmatched_tokens -- tokens that resolved to NOTHING in the
                          frame (caller logs and ignores them;
                          never a hard failure)
    """

    from app.countries import lookup as country_lookup

    pairs = [
        (str(code).strip(), str(name).strip())
        for code, name in code_name_pairs
    ]

    by_exact: Dict[str, list] = {}
    by_iso2: Dict[str, list] = {}

    for pair in pairs:
        code, name = pair

        by_exact.setdefault(
            normalize_country_token(code),
            []
        ).append(pair)

        by_exact.setdefault(
            normalize_country_token(name),
            []
        ).append(pair)

        entry = country_lookup(name)

        if entry:
            by_iso2.setdefault(
                entry["iso2"].upper(),
                []
            ).append(pair)

    matched = []
    matched_seen = set()
    unmatched = []

    for token in requested_tokens:

        token = str(token or "").strip()

        if not token:
            continue

        hits = list(
            by_exact.get(
                normalize_country_token(token),
                []
            )
        )

        if not hits:

            entry = country_lookup(token)

            if entry:
                hits = list(
                    by_iso2.get(
                        entry["iso2"].upper(),
                        []
                    )
                )

        if not hits:
            unmatched.append(token)
            continue

        for pair in hits:
            if pair not in matched_seen:
                matched_seen.add(pair)
                matched.append(pair)

    return matched, unmatched


def select_required_plus_context(
    ranked_keys,
    required_keys,
    min_countries
):
    """
    Dataset-row selection for a country-constrained fetch.

    Every required key PRESENT in ranked_keys is guaranteed a
    slot; remaining slots (up to min_countries) are filled with
    the highest-ranked remaining keys, so a 2-country request
    still produces a visually populated frame.  Required keys
    that are absent from ranked_keys (no usable data) are
    reported for a logged, graceful skip -- never a hard fail.

    Returns (selected_keys, missing_required) where
    selected_keys keeps ranked order (best story value first).
    """

    ranked = list(ranked_keys)

    required_list = []
    required_seen = set()

    for key in required_keys:
        if key in required_seen:
            continue
        required_seen.add(key)
        required_list.append(key)

    present = set(ranked)

    required_present = [
        key for key in required_list
        if key in present
    ]

    missing_required = [
        key for key in required_list
        if key not in present
    ]

    remaining = max(
        0,
        int(min_countries) - len(required_present)
    )

    required_pending = set(required_present)

    selected = []

    for key in ranked:

        if key in required_pending:
            selected.append(key)
            required_pending.discard(key)

        elif remaining > 0:
            selected.append(key)
            remaining -= 1

    return selected, missing_required
