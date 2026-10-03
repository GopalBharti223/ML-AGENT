"""RAWG Provider — video game popularity by platform per year (gaming).

Source: https://rawg.io/apidocs (RAWG Video Games Database)
License: free tier (20k requests/month) with attribution and a
required backlink; commercial use is free for hobby/small projects
under RAWG's threshold, otherwise paid -- see provider catalog
(REVIEW_REQUIRED, same precedent as the jikan provider).  Requires
RAWG_API_KEY (free, instant signup); without a key the provider
raises RuntimeError and the engines skip it gracefully.

DESIGN (revised after live verification):

RAWG's games-list API exposes only SNAPSHOT per-game fields
(`added`, `rating`, `released`) -- there is no per-game multi-year
time series.  A naive "top games by release year" pivot puts each
game in exactly one release-year column, so no entity spans the
>=3 years the story engine requires (verified: 75 games -> 0 rows
with >=2 non-null years -> empty).

So the indicators are built as real, multi-year ENTITY x YEAR
series at the PLATFORM level, using only genuine RAWG values:

  - `games_popular_ranking`: each platform per year = the sum of
    community "added" counts of that platform's top-15 added games
    released that year (real attention-on-that-year's-games).
  - `games_rating_ranking`: each platform per year = the mean
    Metacritic-style `rating` of that platform's top-rated games
    released that year.

Framing stays honest: these are community-attention / rating
averages, never sales or player counts (never fabricated).
"""
import os
import time
from datetime import date
from typing import Dict, List, Optional

import pandas as pd
import requests

from app.data.providers.base import (
    DataProvider,
    DataProviderResult,
    IndicatorInfo,
)


class RAWGProvider(DataProvider):

    provider_id = "rawg"
    provider_name = "RAWG"
    source_url = "https://rawg.io"
    base_url = "https://api.rawg.io/api/games"
    request_timeout = 30
    max_retries = 3
    retry_delay = 1.0
    page_size = 15

    # Stable RAWG platform ids (well-known, long-lived).
    PLATFORMS: Dict[str, str] = {
        "4": "PC",
        "187": "PlayStation 5",
        "186": "Xbox Series S/X",
        "7": "Nintendo Switch",
        "3": "iOS",
        "21": "Android",
    }

    INDICATORS: Dict[str, Dict] = {
        "games_popular_ranking": {
            "name": "Most Added Games by Platform per Year",
            "category": "Gaming",
            "ordering": "-added",
            "value_field": "added",
            "metric_name": "Community Added Count",
            "agg": "sum",
        },
        "games_rating_ranking": {
            "name": "Highest Rated Games by Platform per Year",
            "category": "Gaming",
            "ordering": "-rating",
            "value_field": "rating",
            "metric_name": "Average Rating",
            "agg": "mean",
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

    # =====================================================
    # HTTP
    # =====================================================

    @staticmethod
    def _api_key() -> str:
        return str(
            os.getenv("RAWG_API_KEY", "") or ""
        ).strip()

    @classmethod
    def is_configured(cls) -> bool:
        """
        Automatic rotation consults this (via the engine's
        configured-skip) so a missing free key cleanly removes
        rawg from the candidate scan instead of burning the
        fetch budget on guaranteed RuntimeError failures.
        """
        return bool(cls._api_key())

    @classmethod
    def _request_json(
        cls,
        url: str,
        params: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """GET JSON with retries; None on 4xx (no data / tier)."""
        api_key = cls._api_key()

        if not api_key:
            raise RuntimeError(
                "RAWG_API_KEY is not configured; get a free "
                "key at https://rawg.io/apidocs"
            )

        merged = dict(params or {})
        merged["key"] = api_key

        last_error: Optional[Exception] = None

        for attempt in range(cls.max_retries):

            if attempt:
                time.sleep(cls.retry_delay * attempt)

            try:
                response = requests.get(
                    url,
                    params=merged,
                    timeout=cls.request_timeout,
                    headers={
                        "User-Agent": (
                            "MyShorts-DataFactory/1.0 "
                            "(mailto:myshorts-datafactory"
                            "@example.org)"
                        )
                    },
                )
            except requests.RequestException as error:
                last_error = error
                continue

            if response.status_code in (
                400, 401, 403, 404,
            ):
                return None

            if response.status_code == 429:
                last_error = RuntimeError(
                    "HTTP 429 (rate limited)"
                )
                time.sleep(
                    cls.retry_delay * (attempt + 2)
                )
                continue

            response.raise_for_status()

            time.sleep(0.2)

            return response.json()

        raise RuntimeError(
            f"RAWG request failed after "
            f"{cls.max_retries} attempts: {last_error}"
        )

    # =====================================================
    # PLATFORM x YEAR AGGREGATION
    # =====================================================

    @classmethod
    def _platform_year_value(
        cls,
        config: Dict,
        platform_id: str,
        year: int,
    ) -> Optional[float]:
        """One real value for (platform, year).

        Queries that year's releases on the platform ordered by
        the indicator's field, then aggregates the top games:
          - "sum"  -> sum of community 'added' counts (popularity)
          - "mean" -> mean rating
        Returns None when the API returns nothing usable for that
        cell (kept sparse so a missing year never blocks the rest).
        """
        payload = cls._request_json(
            cls.base_url,
            params={
                "platforms": platform_id,
                "dates": f"{year}-01-01,{year}-12-31",
                "ordering": config["ordering"],
                "page_size": cls.page_size,
            },
        )

        if not payload:
            return None

        results = payload.get("results", []) or []

        values = []

        for item in results:
            raw = item.get(config["value_field"])
            try:
                value = float(raw or 0)
            except (TypeError, ValueError):
                continue
            if value > 0:
                values.append(value)

        if not values:
            return None

        if config.get("agg") == "mean":
            return round(
                sum(values) / len(values), 2
            )

        # default: sum of community 'added' counts
        return round(float(sum(values)), 2)

    # === CONTINUED: FETCH NORMALIZED ===

    @classmethod
    def fetch_normalized(
        cls,
        indicator_code: str,
        years: int = 10,
        story_type: str = "fastest_growth",
        min_countries: int = 6,
        countries=None,
    ) -> DataProviderResult:
        """Popular / highest-rated games by platform per year.

        ENTITIES are the 6 tracked platforms; COLUMNS are years;
        values are real RAWG aggregates over that platform-year's
        top games (see module docstring).  This is the multi-year
        ENTITY x YEAR series the story engine can actually consume.
        """
        config = cls.INDICATORS.get(indicator_code)

        if not config:
            raise ValueError(
                f"Unknown indicator: {indicator_code}"
            )

        if not cls._api_key():
            raise RuntimeError(
                "RAWG_API_KEY is not configured; the "
                "provider is skipped gracefully."
            )

        end_year = date.today().year - 1
        start_year = end_year - max(1, int(years)) + 1

        rows = []

        for platform_id, platform_name in cls.PLATFORMS.items():

            for year in range(
                start_year, end_year + 1
            ):

                value = cls._platform_year_value(
                    config,
                    platform_id,
                    year,
                )

                if value is None:
                    continue

                rows.append(
                    {
                        "country": platform_name,
                        "country_code": platform_id,
                        "year": year,
                        "value": value,
                    }
                )

        if not rows:
            return cls._empty_result(
                indicator_code, config
            )

        df = pd.DataFrame(rows)

        wide = df.pivot_table(
            index=["country_code", "country"],
            columns="year",
            values="value",
            aggfunc="max",
        )

        wide = wide.sort_index(axis=1)

        # Platforms present in a majority of the window survive.
        wide = wide.dropna(
            thresh=max(
                2,
                int(len(wide.columns) * 0.5),
            )
        )

        if (
            wide.empty
            or len(wide) < min_countries
            or len(wide.columns) < 3
        ):
            return cls._empty_result(
                indicator_code, config
            )

        metric_name = config["metric_name"]

        normalized_rows = []

        for (code, name), row in wide.iterrows():
            for year, value in row.items():
                if pd.isna(value):
                    continue
                normalized_rows.append(
                    {
                        "country": name,
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
            "indicator_name": config["name"],
            "category": config["category"],
            "attribution": (
                "Data provided by RAWG (rawg.io) -- "
                "attribution required"
            ),
            "metric_meaning": (
                "community-added sum / average rating of that "
                "platform-year's top games; NOT sales or player "
                "counts"
            ),
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
        config: Dict,
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
            metric_name=config["metric_name"],
            source_name=cls.provider_name,
            source_url=cls.source_url,
            normalized_data=empty_df,
            wide_data=empty_df,
            metadata=metadata,
        )
