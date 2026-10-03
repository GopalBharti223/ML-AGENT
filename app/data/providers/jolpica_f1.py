"""Jolpica F1 Provider — Formula 1 standings & results.

Source: https://api.jolpi.ca/ergast/f1 (successor to the Ergast F1 API)
License: open public API.
Commercial use: ALLOWED (see provider catalog).

Provides season-by-season driver & constructor championship
standings as a country/entity × year pivot so the existing
SmartStoryEngine can generate trend/leader/rank stories:

  "Which driver led the most seasons?"
  "Who accumulated the most points 2016-2025?"
  "Which constructor dominated the championship?"
  "Who climbed most in the standings?"

Only real points/wins/podiums returned by the API are used.
Salary, sponsorship, popularity, revenue are NEVER fabricated.
"""
from typing import Dict, List

import pandas as pd
import requests

from app.data.providers.base import (
    DataProvider,
    DataProviderResult,
    IndicatorInfo,
)


class JolpicaF1Provider(DataProvider):

    provider_id = "jolpica_f1"
    provider_name = "Jolpica F1"
    source_url = "https://api.jolpi.ca/ergast/f1"
    base_url = "https://api.jolpi.ca/ergast/f1"
    request_timeout = 30

    INDICATORS: Dict[str, Dict] = {
        "driver_standings": {
            "name": "F1 Driver Championship Points",
            "category": "Formula 1",
            "endpoint": "driverstandings",
            "value_field": "points",
        },
        "constructor_standings": {
            "name": "F1 Constructor Championship Points",
            "category": "Formula 1",
            "endpoint": "constructorstandings",
            "value_field": "points",
        },
        # Race wins ride along in every driver-standings payload,
        # so this indicator costs ZERO extra API calls: the same
        # standings fetch pivots on the "wins" field instead of
        # "points".  This is the catalog's promised third
        # indicator (previously claimed but not implemented).
        "race_wins": {
            "name": "F1 Driver Race Wins per Season",
            "category": "Formula 1",
            "endpoint": "driverstandings",
            "value_field": "wins",
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
    # FETCH STANDINGS FOR A SEASON
    # =====================================================

    @classmethod
    def _fetch_standings(
        cls,
        endpoint: str,
        season: str
    ) -> List[Dict]:
        """Fetch driver/constructor standings for one season.

        Returns a list of {name, code, points, wins} rows.
        """
        url = (
            f"{cls.base_url}/{season}/{endpoint}.json"
        )

        response = requests.get(
            url,
            timeout=cls.request_timeout,
            headers={"User-Agent": "MyShorts-DataFactory/1.0"},
        )

        response.raise_for_status()

        payload = response.json()

        standings_lists = (
            payload
            .get("MRData", {})
            .get("StandingsTable", {})
            .get("StandingsLists", [])
        )

        if not standings_lists:
            return []

        standings = standings_lists[0].get(
            "DriverStandings"
            if endpoint == "driverstandings"
            else "ConstructorStandings",
            [],
        )

        rows = []

        for item in standings:
            name = None
            code = None

            if endpoint == "driverstandings":
                driver = item.get("Driver", {})
                name = (
                    driver.get("givenName", "")
                    + " "
                    + driver.get("familyName", "")
                ).strip()
                code = driver.get("code") or driver.get("driverId", "")
            else:
                constructor = item.get("Constructor", {})
                name = constructor.get("name", "")
                code = constructor.get("constructorId", "")

            if not name:
                continue

            try:
                points = float(
                    item.get("points", 0) or 0
                )
                wins = int(
                    item.get("wins", 0) or 0
                )
            except (ValueError, TypeError):
                continue

            rows.append(
                {
                    "name": name,
                    "code": code,
                    "points": points,
                    "wins": wins,
                }
            )

        return rows

    # =====================================================
    # FETCH NORMALIZED
    # =====================================================

    @classmethod
    def fetch_normalized(
        cls,
        indicator_code: str,
        years: int = 15,
        story_type: str = "fastest_growth",
        min_countries: int = 3
    ) -> DataProviderResult:
        """Fetch points per season for drivers/constructors.

        years controls how many recent seasons to include
        (e.g., 10 -> 2016-2025).  Only real championship points
        from the API are used.
        """
        config = cls.INDICATORS.get(indicator_code)

        if not config:
            raise ValueError(
                f"Unknown indicator: {indicator_code}"
            )

        # Fall back to using the last N completed seasons.
        current_year = 2026
        end_year = current_year - 1  # most recent completed season
        start_year = end_year - min(years, 20) + 1

        all_rows = []

        for season in range(start_year, end_year + 1):
            try:
                season_rows = cls._fetch_standings(
                    config["endpoint"],
                    str(season),
                )
            except Exception:
                # Season may not exist yet or network error;
                # skip that season gracefully (real data only).
                continue

            for row in season_rows:
                all_rows.append(
                    {
                        **row,
                        "year": season,
                    }
                )

        if not all_rows:
            return cls._empty_result(indicator_code, config)

        df = pd.DataFrame(all_rows)

        # Keep entity name; pivot on the indicator's value field
        # (championship points for standings, wins for race_wins).
        wide = df.pivot(
            index=["code", "name"],
            columns="year",
            values=config.get("value_field", "points"),
        )

        wide = wide.sort_index(axis=1)

        # Minimum entity/season requirement (like other providers)
        wide = wide.dropna(
            thresh=max(3, int(len(wide.columns) * 0.5))
        )

        if wide.empty or len(wide) < min_countries:
            return cls._empty_result(indicator_code, config)

        metric_name = config["name"]

        # Build long-form normalized rows (compatible with base helper)
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