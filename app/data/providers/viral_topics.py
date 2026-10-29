"""Viral Topics Provider — Gaming, Billionaires, Brand Wars, and Pop Culture.

Supplies verified historical and snapshot data for high-retention viral topics:
  - Grand Theft Auto Copies Sold by Game
  - Best-Selling Video Games of All Time (Minecraft vs GTA vs Roblox)
  - World Richest Billionaires Net Worth (Elon Musk, Jeff Bezos, Ambani, Adani)
  - Global Electric Vehicle Sales (Tesla vs BYD)
  - Global Smartphone Market Shipments (Apple vs Samsung vs Xiaomi)
  - Most Popular Social Media Platforms
  - Highest-Grossing Movies of All Time
"""

from typing import Dict, List, Optional
import pandas as pd

from app.data.providers.base import (
    DataProvider,
    DataProviderResult,
    IndicatorInfo,
)
from app.data.static.viral_datasets import VIRAL_INDICATORS


class ViralTopicsProvider(DataProvider):

    provider_id = "viral_topics"
    provider_name = "Viral Culture & Wealth Archives"
    source_url = "https://data.lr-atlas.com"
    entity_comparison = True

    @classmethod
    def supports_countries(cls) -> bool:
        """Allows entity filtering when caller requests specific items."""
        return True

    @classmethod
    def list_indicators(cls) -> List[IndicatorInfo]:
        return [
            IndicatorInfo(
                code=code,
                name=info["name"],
                category=info["category"],
                source_url=info["source_url"],
            )
            for code, info in VIRAL_INDICATORS.items()
        ]

    @classmethod
    def search_indicators(cls, query: str) -> List[IndicatorInfo]:
        q = str(query or "").strip().lower()
        if not q:
            return cls.list_indicators()

        matches = []
        for info in cls.list_indicators():
            if (
                q in info.name.lower()
                or q in info.code.lower()
                or q in info.category.lower()
            ):
                matches.append(info)
        return matches

    @classmethod
    def fetch_normalized(
        cls,
        indicator_code: str,
        years: int = 10,
        story_type: str = "fastest_growth",
        min_countries: int = 4,
        countries: Optional[List[str]] = None,
    ) -> DataProviderResult:
        config = VIRAL_INDICATORS.get(indicator_code)
        if not config:
            raise ValueError(
                f"Unknown viral indicator code: {indicator_code}. "
                f"Available: {', '.join(sorted(VIRAL_INDICATORS.keys()))}"
            )

        raw_data = config["data"]
        raw_years = config["years"]
        metric_name = config["metric_name"]

        # Filter entities if explicit hints provided
        selected_entities = list(raw_data.keys())
        if countries:
            hint_matched = []
            for hint in countries:
                h = str(hint).lower().strip()
                for entity in selected_entities:
                    if h in entity.lower() or entity.lower() in h:
                        if entity not in hint_matched:
                            hint_matched.append(entity)
            if len(hint_matched) >= 2:
                selected_entities = hint_matched

        # Construct wide DataFrame: index=entity, columns=years
        wide_dict = {}
        for entity in selected_entities:
            wide_dict[entity] = raw_data[entity]

        wide_df = pd.DataFrame(wide_dict, index=raw_years).T
        wide_df.index.name = "entity"

        # Construct normalized DataFrame: country, country_code, year, metric, value
        norm_rows = []
        for entity in wide_df.index:
            for yr in wide_df.columns:
                val = float(wide_df.loc[entity, yr])
                norm_rows.append(
                    {
                        "country": entity,
                        "country_code": entity[:3].upper() if len(entity) >= 3 else entity,
                        "year": int(yr),
                        "metric": metric_name,
                        "value": val,
                        "provider": cls.provider_id,
                        "source_name": config["source_name"],
                        "source_url": config["source_url"],
                        "indicator_code": indicator_code,
                    }
                )

        norm_df = pd.DataFrame(norm_rows)

        metadata = {
            "indicator_code": indicator_code,
            "metric_name": metric_name,
            "category": config["category"],
            "unit": config.get("unit", ""),
            "is_time_series": config.get("is_time_series", True),
            "source_name": config["source_name"],
            "source_url": config["source_url"],
        }

        return DataProviderResult(
            provider=cls.provider_id,
            indicator_code=indicator_code,
            metric_name=metric_name,
            source_name=config["source_name"],
            source_url=config["source_url"],
            normalized_data=norm_df,
            wide_data=wide_df,
            metadata=metadata,
        )
