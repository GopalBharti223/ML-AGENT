"""Football-Data.org Provider — league standings (football).

Source: https://www.football-data.org (v4 REST API)
License: free tier for non-commercial use (10 req/min, ~12
competitions, limited historical seasons).  Commercial use of the
data requires a paid tier -- see provider catalog
(REVIEW_REQUIRED).  Requires FOOTBALL_DATA_API_KEY (free, instant
signup); without a key the provider raises RuntimeError and the
engines skip it gracefully (established convention).

Provides per-season final standings as an entity x season pivot
so the existing SmartStoryEngine can produce trend/leader stories:

  "Which team has collected the most points?"
  "Which club is climbing fastest?"

Only real points returned by the API are used.  Wages, transfer
values, attendance are NEVER fabricated.

NOTE: seasons are identified by their STARTING year (int), so the
frame carries plain numeric year columns -- the season-label
rendering fix (app/time_labels.py) is defense in depth, not a
dependency for this provider.
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


class FootballDataOrgProvider(DataProvider):

    provider_id = "football_data"
    provider_name = "Football-Data.org"
    source_url = "https://www.football-data.org"
    base_url = "https://api.football-data.org/v4"
    request_timeout = 30
    max_retries = 3
    retry_delay = 1.0

    COMPETITIONS: Dict[str, Dict] = {
        "PL": "Premier League",
        "PD": "La Liga",
        "SA": "Serie A",
        "BL": "Bundesliga",
        "FL1": "Ligue 1",
    }

    INDICATORS: Dict[str, Dict] = {
        "premier_league_standings": {
            "name": "Premier League Standings Points",
            "category": "Football",
            "competition": "PL",
        },
        "la_liga_standings": {
            "name": "La Liga Standings Points",
            "category": "Football",
            "competition": "PD",
        },
        "serie_a_standings": {
            "name": "Serie A Standings Points",
            "category": "Football",
            "competition": "SA",
        },
        "bundesliga_standings": {
            "name": "Bundesliga Standings Points",
            "category": "Football",
            "competition": "BL",
        },
        "ligue1_standings": {
            "name": "Ligue 1 Standings Points",
            "category": "Football",
            "competition": "FL1",
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
            os.getenv("FOOTBALL_DATA_API_KEY", "") or ""
        ).strip()

    @classmethod
    def is_configured(cls) -> bool:
        """
        Automatic rotation consults this (via the engine's
        configured-skip) so a missing free key cleanly removes
        football_data from the candidate scan instead of burning
        the fetch budget on guaranteed RuntimeError failures.
        """
        return bool(cls._api_key())

    @classmethod
    def _request_json(
        cls,
        url: str,
        params: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """GET JSON with retries.

        Returns None for 400/403/404 (season out of scope for the
        tier, unknown competition) so missing seasons are skipped
        gracefully.  Other failures raise RuntimeError after the
        retries are exhausted.
        """
        api_key = cls._api_key()

        if not api_key:
            raise RuntimeError(
                "FOOTBALL_DATA_API_KEY is not configured; "
                "get a free key at "
                "https://www.football-data.org/client/register"
            )

        headers = {"X-Auth-Token": api_key}

        last_error: Optional[Exception] = None

        for attempt in range(cls.max_retries):

            if attempt:
                time.sleep(cls.retry_delay * attempt)

            try:
                response = requests.get(
                    url,
                    params=params,
                    timeout=cls.request_timeout,
                    headers=headers,
                )
            except requests.RequestException as error:
                last_error = error
                continue

            if response.status_code in (
                400, 403, 404, 429,
            ):
                # 429: free tier is 10 req/min -- back off and
                # retry once more inside the loop; if it persists
                # we surface the error to the caller's except.
                if response.status_code == 429:
                    last_error = RuntimeError(
                        "HTTP 429 (rate limited)"
                    )
                    time.sleep(
                        cls.retry_delay * (attempt + 2)
                    )
                    continue
                return None

            response.raise_for_status()

            return response.json()

        raise RuntimeError(
            f"Football-Data.org request failed after "
            f"{cls.max_retries} attempts: {last_error}"
        )

    @classmethod
    def list_seasons_window(cls, years: int):
        end_year = date.today().year - 1
        start_year = end_year - max(1, int(years)) + 1
        return start_year, end_year

    @classmethod
    def _season_standings(
        cls,
        competition: str,
        season: int,
        requested_teams,
    ) -> List[Dict]:
        """One season's TOTAL standings as row dicts.

        Returns [] when the tier does not cover the season.
        `requested_teams` (the countries hint) narrows the table
        to the named teams when provided.
        """
        url = (
            f"{cls.base_url}/competitions/"
            f"{competition}/standings"
        )

        payload = cls._request_json(
            url,
            params={"season": season},
        )

        if not payload:
            return []

        standings = (
            payload.get("standings", []) or []
        )

        table = []

        for standing in standings:
            if (
                str(
                    standing.get("type", "")
                ).upper() != "TOTAL"
            ):
                continue
            table = standing.get("table", []) or []
            break

        rows = []

        for entry in table:
            team = entry.get("team", {}) or {}
            name = str(team.get("name", "") or "").strip()
            if not name:
                continue
            try:
                points = float(
                    entry.get("points", 0) or 0
                )
            except (TypeError, ValueError):
                continue
            rows.append(
                {
                    "name": name,
                    "code": str(
                        team.get("tla", "")
                        or team.get("id", "")
                        or name
                    ),
                    "points": points,
                }
            )

        if requested_teams:

            def _norm(value):
                return "".join(
                    character
                    for character
                    in str(value or "").lower()
                    if character.isalnum()
                )

            wanted = [
                _norm(team)
                for team in requested_teams
            ]

            rows = [
                row
                for row in rows
                if any(
                    token
                    and (
                        token in _norm(row["name"])
                        or _norm(row["name"]) in token
                    )
                    for token in wanted
                )
            ]

        return rows

    @classmethod
    def fetch_normalized(
        cls,
        indicator_code: str,
        years: int = 10,
        story_type: str = "fastest_growth",
        min_countries: int = 6,
        countries=None,
    ) -> DataProviderResult:
        """Final standings points per season for one league."""
        config = cls.INDICATORS.get(indicator_code)

        if not config:
            raise ValueError(
                f"Unknown indicator: {indicator_code}"
            )

        if not cls._api_key():
            raise RuntimeError(
                "FOOTBALL_DATA_API_KEY is not configured; "
                "the provider is skipped gracefully."
            )

        requested_teams = [
            str(team).strip()
            for team in (countries or [])
            if str(team or "").strip()
        ]

        competition = config["competition"]

        start_year, end_year = cls.list_seasons_window(
            years
        )

        rows = []
        available_years = []

        # Newest season first; the free tier may cover only a few
        # historical seasons -- missing seasons return [] and are
        # skipped gracefully (real data only).
        for season in range(
            end_year, start_year - 1, -1
        ):
            season_rows = cls._season_standings(
                competition,
                season,
                requested_teams,
            )
            if not season_rows:
                continue
            available_years.append(season)
            for row in season_rows:
                rows.append(
                    {
                        **row,
                        "year": season,
                    }
                )

        if not rows:
            return cls._empty_result(
                indicator_code, config
            )

        df = pd.DataFrame(rows)

        wide = df.pivot_table(
            index=["code", "name"],
            columns="year",
            values="points",
            aggfunc="max",
        )

        wide = wide.sort_index(axis=1)

        # Minimum coverage requirement (other providers'
        # convention): teams need data in a majority of the
        # seasons that actually returned data.
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

        metric_name = config["name"]

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
            "seasons": available_years,
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
            metric_name=config["name"],
            source_name=cls.provider_name,
            source_url=cls.source_url,
            normalized_data=empty_df,
            wide_data=empty_df,
            metadata=metadata,
        )

