"""OpenAlex Provider — research publications by country (year series).

Source: https://openalex.org (free public domain scholarly database)
License: CC0 (public domain).
Commercial use: ALLOWED (see provider catalog).

The "publications" indicator fetches a country × year count of
scholarly works so the existing SmartStoryEngine can produce
stories like:

  "Which country produced the most research publications?"
  "Who grew fastest in scientific output?"
  "Which country is rising fastest in research?"

OpenAlex is a real, openly licensed database of ~250M scholarly
works.  We query its /works endpoint with a per-year/per-country
facet.  Only real counts returned by OpenAlex are used.
"""
from typing import Dict, List

import pandas as pd
import requests

from app.data.providers.base import (
    DataProvider,
    DataProviderResult,
    IndicatorInfo,
)


class OpenAlexProvider(DataProvider):

    provider_id = "openalex"
    provider_name = "OpenAlex"
    source_url = "https://openalex.org"
    base_url = "https://api.openalex.org"
    request_timeout = 60

    # A short, clear topic filter.  "Space science / astronomy"
    # matches the space_science category. Keep human-readable.
    TOPIC_SEARCH = (
        "space OR astronomy OR astrophysics OR "
        "spacecraft OR satellite OR cosmology"
    )

    INDICATORS: Dict[str, Dict] = {
        "research_publications_by_country": {
            "name": "Research Publications by Country",
            "category": "Space / Science",
        },
    }

    @classmethod
    def list_indicators(cls) -> List[IndicatorInfo]:
        return [
            IndicatorInfo(
                code=code,
                name=config["name"],
                category=config["category"],
                source_url=cls.source_url,
            )
            for code, config in cls.INDICATORS.items()
        ]

    @classmethod
    def _year_publication_counts(
        cls,
        year: int
    ) -> Dict[str, int]:
        """Query OpenAlex /works facet for a single year.

        Returns {country_code: count} using only the real facet
        data returned by OpenAlex.  Unknown countries are skipped.
        """
        url = f"{cls.base_url}/works"
        params = {
            "filter": (
                f"from_publication_date:{year}-01-01,"
                f"to_publication_date:{year}-12-31,"
                f"default.search:{cls.TOPIC_SEARCH}"
            ),
            "group_by": "authorships.countries.id",
            "per-page": 50,
            "mailto": "myshorts-datafactory@example.org",
        }

        response = requests.get(
            url,
            params=params,
            timeout=cls.request_timeout,
            headers={
                "User-Agent": (
                    "MyShorts-DataFactory/1.0 "
                    "(mailto:myshorts-datafactory@example.org)"
                )
            },
        )

        response.raise_for_status()

        payload = response.json()

        counts = {}

        for group in payload.get("group_by", []) or []:
            country_key = str(
                (group or {}).get("key", "")
            ).strip()

            # OpenAlex country keys come back as ISO 3166-1 alpha-2
            # (e.g., "US", "IN", "CN").  Skip aggregates / nulls.
            if not country_key or country_key == "null":
                continue

            doc_count = int(
                (group or {}).get("count", 0) or 0
            )

            if doc_count > 0:
                counts[country_key] = doc_count

        return counts

    @classmethod
    def fetch_normalized(
        cls,
        indicator_code: str,
        years: int = 10,
        story_type: str = "fastest_growth",
        min_countries: int = 8
    ) -> DataProviderResult:
        config = cls.INDICATORS.get(indicator_code)

        if not config:
            raise ValueError(
                f"Unknown indicator: {indicator_code}"
            )

        years = max(5, min(years, 15))

        end_year = 2024  # last full year with complete data
        start_year = end_year - years + 1

        # country_code -> {year: count}
        rows_by_country: Dict[str, Dict[int, int]] = {}

        for year in range(start_year, end_year + 1):
            try:
                counts = cls._year_publication_counts(year)
            except Exception:
                # API down / rate-limited: skip that year,
                # never fabricate.
                continue

            for code, count in counts.items():
                rows_by_country.setdefault(code, {})[year] = count

        if not rows_by_country:
            return cls._empty_result(indicator_code, config)

        # Build wide DataFrame with ISO code as index; add a
        # readable name column from ISO alpha-2 mapping.
        index = sorted(rows_by_country)
        years_list = list(range(start_year, end_year + 1))

        data = {}
        for code in index:
            data[code] = [
                rows_by_country[code].get(y, None)
                for y in years_list
            ]

        wide = pd.DataFrame(
            data,
            index=years_list,
        ).T

        wide.columns = [int(c) for c in wide.columns]
        wide = wide.sort_index(axis=1)

        # Convert ISO alpha-2 to readable names where known.
        wide["country_name"] = wide.index.map(
            _ISO2_TO_NAME.get
        )

        # Drop rows without a readable country name.
        wide = wide.dropna(subset=["country_name"])

        # Requirement: at least `min_countries` with data in >half
        # the years.
        wide = wide.dropna(
            thresh=max(3, int(len(wide.columns) * 0.5))
        )

        wide = wide.drop(columns=["country_name"])

        if wide.empty or len(wide) < min_countries:
            return cls._empty_result(indicator_code, config)

        metric_name = config["name"]

        # Normalized rows (long format)
        normalized_rows = []
        for code, row in wide.iterrows():
            for year, value in row.items():
                if pd.isna(value):
                    continue
                normalized_rows.append(
                    {
                        "country": _ISO2_TO_NAME.get(code, code),
                        "country_code": code,
                        "year": int(year),
                        "metric": metric_name,
                        "value": float(value),
                        "provider": cls.provider_id,
                        "source_name": cls.provider_name,
                        "source_url": cls.source_url,
                        "indicator_code": indicator_code,
                    }
                )

        normalized = pd.DataFrame(normalized_rows)

        metadata = {
            "provider": cls.provider_id,
            "source_name": cls.provider_name,
            "source_url": cls.source_url,
            "indicator_code": indicator_code,
            "indicator_name": metric_name,
            "category": config["category"],
        }

        wide.attrs.update(metadata)
        wide.attrs["normalized_data"] = normalized

        return DataProviderResult(
            provider=cls.provider_id,
            indicator_code=indicator_code,
            metric_name=metric_name,
            source_name=cls.provider_name,
            source_url=cls.source_url,
            normalized_data=normalized,
            wide_data=wide,
            metadata=metadata,
        )

    @classmethod
    def _empty_result(
        cls,
        indicator_code: str,
        config: Dict
    ) -> DataProviderResult:
        empty_df = pd.DataFrame()
        metadata = {
            "provider": cls.provider_id,
            "source_name": cls.provider_name,
            "source_url": cls.source_url,
            "indicator_code": indicator_code,
            "indicator_name": config["name"],
            "category": config["category"],
        }
        return DataProviderResult(
            provider=cls.provider_id,
            indicator_code=indicator_code,
            metric_name=config["name"],
            source_name=cls.provider_name,
            source_url=cls.source_url,
            normalized_data=empty_df,
            wide_data=empty_df,
            metadata=metadata,
        )


# Small ISO alpha-2 -> readable name map for the top countries
# OpenAlex will return.  Full mapping not needed; unknown codes
# are dropped (real data only).
_ISO2_TO_NAME = {
    "US": "United States",
    "GB": "United Kingdom",
    "DE": "Germany",
    "FR": "France",
    "IT": "Italy",
    "ES": "Spain",
    "NL": "Netherlands",
    "CH": "Switzerland",
    "SE": "Sweden",
    "NO": "Norway",
    "DK": "Denmark",
    "FI": "Finland",
    "PL": "Poland",
    "RU": "Russia",
    "UA": "Ukraine",
    "IN": "India",
    "CN": "China",
    "JP": "Japan",
    "KR": "South Korea",
    "CA": "Canada",
    "AU": "Australia",
    "BR": "Brazil",
    "MX": "Mexico",
    "AR": "Argentina",
    "CL": "Chile",
    "TR": "Turkey",
    "IL": "Israel",
    "SA": "Saudi Arabia",
    "AE": "United Arab Emirates",
    "ZA": "South Africa",
    "NG": "Nigeria",
    "EG": "Egypt",
    "ID": "Indonesia",
    "TH": "Thailand",
    "SG": "Singapore",
    "MY": "Malaysia",
    "PH": "Philippines",
    "IR": "Iran",
    "PK": "Pakistan",
    "BD": "Bangladesh",
    "AT": "Austria",
    "BE": "Belgium",
    "IE": "Ireland",
    "PT": "Portugal",
    "GR": "Greece",
    "CZ": "Czechia",
    "HU": "Hungary",
    "RO": "Romania",
    "NZ": "New Zealand",
}