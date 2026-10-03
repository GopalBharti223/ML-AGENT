"""Jikan Provider - MyAnimeList anime rankings (entertainment_pop_culture).

Source: https://jikan.moe (unofficial MyAnimeList API)
License: Jikan public API (data derived from MyAnimeList).
Commercial use: REVIEW_REQUIRED (see provider catalog).

CRITICAL: Jikan "popularity" is a MyAnimeList listing metric,
NOT worldwide viewership. We never claim viewership.
"""
from typing import Dict, List

import pandas as pd
import requests

from app.data.providers.base import (
    DataProvider,
    DataProviderResult,
    IndicatorInfo,
)


class JikanProvider(DataProvider):

    provider_id = "jikan"
    provider_name = "Jikan (MyAnimeList)"
    source_url = "https://jikan.moe"
    base_url = "https://api.jikan.moe/v4"
    request_timeout = 30

    INDICATORS: Dict[str, Dict] = {
        "anime_popularity_ranking": {
            "name": "Anime Popularity Ranking",
            "category": "Anime",
            "metric_field": "popularity",
            "metric_name": "Popularity",
        },
        "anime_score_ranking": {
            "name": "Anime Score Ranking",
            "category": "Anime",
            "metric_field": "score",
            "metric_name": "Score",
        },
        "anime_members_ranking": {
            "name": "Anime Members Ranking",
            "category": "Anime",
            "metric_field": "members",
            "metric_name": "Members",
        },
        "anime_favorites_ranking": {
            "name": "Anime Favorites Ranking",
            "category": "Anime",
            "metric_field": "favorites",
            "metric_name": "Favorites",
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
    def _fetch_top_anime(cls, page: int = 1) -> List[Dict]:
        url = f"{cls.base_url}/top/anime"
        response = requests.get(
            url,
            params={"page": page, "limit": 25},
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
        anime_list = payload.get("data", []) or []
        rows = []
        for item in anime_list:
            title = str(item.get("title", "") or "").strip()
            if not title:
                continue
            try:
                rank = int(item.get("rank") or 0)
                score = float(item.get("score") or 0)
                popularity = int(item.get("popularity") or 0)
                members = int(item.get("members") or 0)
                favorites = int(item.get("favorites") or 0)
            except (ValueError, TypeError):
                continue
            aired = item.get("aired", {}) or {}
            prop = aired.get("prop", {}) or {}
            from_year = (prop.get("from", {}) or {}).get("year")
            try:
                year = int(from_year) if from_year else None
            except (ValueError, TypeError):
                year = None
            rows.append({
                "title": title, "rank": rank, "score": score,
                "popularity": popularity, "members": members,
                "favorites": favorites, "year": year,
            })
        return rows

    @classmethod
    def fetch_normalized(
        cls,
        indicator_code: str,
        years: int = 10,
        story_type: str = "fastest_growth",
        min_countries: int = 5,
    ) -> DataProviderResult:
        config = cls.INDICATORS.get(indicator_code)
        if not config:
            raise ValueError(f"Unknown indicator: {indicator_code}")

        all_rows = []
        try:
            for page in range(1, 6):
                page_rows = cls._fetch_top_anime(page=page)
                if not page_rows:
                    break
                all_rows.extend(page_rows)
        except Exception:
            return cls._empty_result(indicator_code, config)

        if not all_rows:
            return cls._empty_result(indicator_code, config)

        df = pd.DataFrame(all_rows)
        df = df.dropna(subset=["year"])
        df["year"] = df["year"].astype(int)
        max_year = int(df["year"].max())
        min_year = max_year - years + 1
        df = df[(df["year"] >= min_year) & (df["year"] <= max_year)]
        if df.empty:
            return cls._empty_result(indicator_code, config)

        metric_field = config["metric_field"]
        metric_name = config["metric_name"]
        wide = df.pivot_table(
            index="title", columns="year",
            values=metric_field, aggfunc="max",
        ).sort_index(axis=1)
        wide = wide.dropna(
            thresh=max(2, int(len(wide.columns) * 0.4))
        )
        if wide.empty or len(wide) < min_countries:
            return cls._empty_result(indicator_code, config)

        normalized_rows = []
        for title, row in wide.iterrows():
            for year, value in row.items():
                if pd.isna(value):
                    continue
                normalized_rows.append({
                    "country": title, "country_code": title,
                    "year": int(year), "metric": metric_name,
                    "value": float(value),
                    "provider": cls.provider_id,
                    "source_name": cls.provider_name,
                    "source_url": cls.source_url,
                    "indicator_code": indicator_code,
                })
        normalized = pd.DataFrame(normalized_rows)
        metadata = {
            "provider": cls.provider_id,
            "source_name": cls.provider_name,
            "source_url": cls.source_url,
            "indicator_code": indicator_code,
            "indicator_name": config["name"],
            "category": config["category"],
        }
        wide.attrs.update(metadata)
        wide.attrs["normalized_data"] = normalized
        return DataProviderResult(
            provider=cls.provider_id,
            indicator_code=indicator_code,
            metric_name=config["name"],
            source_name=cls.provider_name,
            source_url=cls.source_url,
            normalized_data=normalized,
            wide_data=wide,
            metadata=metadata,
        )

    @classmethod
    def _empty_result(cls, indicator_code: str, config: Dict) -> DataProviderResult:
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