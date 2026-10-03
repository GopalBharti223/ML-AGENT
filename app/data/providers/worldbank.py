from typing import List

import pandas as pd

from app.data.providers.base import (
    DataProvider,
    DataProviderResult,
    IndicatorInfo,
)
from app.data.worldbank import WorldBankData


class WorldBankProvider(DataProvider):

    provider_id = "worldbank"
    provider_name = "World Bank"
    source_url = "https://data.worldbank.org"

    # ---------------------------------------------------------
    # Per-indicator display categories (Section C category split).
    #
    # The previous single shared "World Data" bucket collapsed
    # genuinely different source topics (education, population,
    # health, energy, ...) under one label in the DB/history,
    # making category-level rotation look more repetitive than
    # it actually is.  Rotation itself classifies via
    # topic_family (indicator-code classifier) and is NOT
    # affected by this change -- this fixes the recorded and
    # displayed category.  Values follow the same Title Case
    # convention the other providers already use (owid:
    # "Population", "Health", "Energy", "Economy", ...).
    # ---------------------------------------------------------

    _INDICATOR_CATEGORIES = {
        "IT.NET.USER.ZS": "Technology",
        "SP.DYN.LE00.IN": "Health",
        "NY.GDP.MKTP.CD": "Economy",
        "NY.GDP.PCAP.CD": "Economy",
        "SP.POP.TOTL": "Population",
        "SP.URB.TOTL.IN.ZS": "Population",
        "SE.XPD.TOTL.GD.ZS": "Education",
        "MS.MIL.XPND.GD.ZS": "Defense",
        "EG.ELC.ACCS.ZS": "Energy",
        "SH.DYN.MORT": "Health",
        "SH.XPD.CHEX.GD.ZS": "Health",
        "DT.DOD.DECT.CD": "Debt",
    }

    @classmethod
    def list_indicators(cls) -> List[IndicatorInfo]:

        return [
            IndicatorInfo(
                code=code,
                name=name,
                category=cls._INDICATOR_CATEGORIES.get(
                    code,
                    "Economy"
                ),
                source_url=cls.source_url
            )
            for code, name
            in WorldBankData.INDICATORS.items()
        ]

    @classmethod
    def fetch_normalized(
        cls,
        indicator_code: str,
        years: int = 15,
        story_type: str = "fastest_growth",
        min_countries: int = 8,
        countries=None
    ) -> DataProviderResult:

        wide_data = WorldBankData.fetch_data(
            indicator_code=indicator_code,
            years=years,
            story_type=story_type,
            min_countries=min_countries,
            countries=countries
        )

        metric_name = WorldBankData.INDICATORS.get(
            indicator_code,
            indicator_code
        )

        normalized_rows = []

        if not wide_data.empty:
            for index, row in wide_data.iterrows():
                country_code = index[0]
                country = index[1]

                for year, value in row.items():
                    if pd.isna(value):
                        continue

                    normalized_rows.append(
                        {
                            "country": country,
                            "country_code": country_code,
                            "year": int(year),
                            "metric": metric_name,
                            "value": float(value),
                            "provider": cls.provider_id,
                            "source_name": cls.provider_name,
                            "source_url": cls.source_url,
                            "indicator_code": indicator_code,
                        }
                    )

        normalized_data = pd.DataFrame(
            normalized_rows
        )

        metadata = {
            "provider": cls.provider_id,
            "source_name": cls.provider_name,
            "source_url": cls.source_url,
            "indicator_code": indicator_code,
            "indicator_name": metric_name,
        }

        wide_data.attrs.update(
            metadata
        )

        wide_data.attrs[
            "normalized_data"
        ] = normalized_data

        return DataProviderResult(
            provider=cls.provider_id,
            indicator_code=indicator_code,
            metric_name=metric_name,
            source_name=cls.provider_name,
            source_url=cls.source_url,
            normalized_data=normalized_data,
            wide_data=wide_data,
            metadata=metadata
        )
