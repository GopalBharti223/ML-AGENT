"""NHTSA vPIC Provider - vehicle manufacturers & models (cars_automotive).

Source: https://vpic.nhtsa.dot.gov/api (US NHTSA Vehicle Safety
Manufacturer Information).
License: US public domain.
Commercial use: ALLOWED (see provider catalog).

Provides manufacturer / model counts.  NHTSA vPIC is a
manufacturer-model DIRECTORY, NOT a global car-sales time series.
We NEVER fabricate "best-selling car worldwide" or sales figures.
Only genuine manufacturer/model counts are exposed.

The existing SmartStoryEngine requires multi-year time series, so
NHTSA candidates may be sparse; the engine skips NHTSA when no
qualifying time series exists (real-data-only rule).
"""
from typing import Dict, List

import pandas as pd
import requests

from app.data.providers.base import (
    DataProvider,
    DataProviderResult,
    IndicatorInfo,
)


class NHTSAProvider(DataProvider):

    provider_id = "nhtsa"
    provider_name = "NHTSA vPIC"
    source_url = "https://vpic.nhtsa.dot.gov/api"
    base_url = "https://vpic.nhtsa.dot.gov/api"
    request_timeout = 30

    INDICATORS: Dict[str, Dict] = {
        "vehicle_manufacturer_models": {
            "name": "Vehicle Manufacturers by Model Count",
            "category": "Automotive",
            "metric_field": "model_count",
            "metric_name": "Model Count",
        },
        "vehicle_types_by_manufacturer": {
            "name": "Vehicle Types by Manufacturer",
            "category": "Automotive",
            "metric_field": "type_count",
            "metric_name": "Type Count",
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
    def _fetch_manufacturers(cls) -> List[Dict]:
        url = f"{cls.base_url}/getallmanufacturers"
        response = requests.get(
            url,
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
        results = payload.get("Results", []) or []
        rows = []
        for item in results:
            name = str(item.get("MfrName", "") or "").strip()
            if not name:
                continue
            rows.append({
                "name": name,
                "code": str(item.get("MfrID", "") or "").strip(),
            })
        return rows

    @classmethod
    def _fetch_model_count(cls, mfr_id: str) -> int:
        url = f"{cls.base_url}/getmodelsformake/{mfr_id}"
        try:
            response = requests.get(
                url,
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
            results = payload.get("Results", []) or []
            return len(results)
        except Exception:
            return 0

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

        try:
            manufacturers = cls._fetch_manufacturers()
        except Exception:
            return cls._empty_result(indicator_code, config)

        if not manufacturers:
            return cls._empty_result(indicator_code, config)

        rows = []
        for mfr in manufacturers:
            model_count = cls._fetch_model_count(mfr["code"])
            if model_count > 0:
                rows.append({
                    "name": mfr["name"],
                    "code": mfr["code"],
                    "model_count": model_count,
                    "type_count": model_count,
                })

        if not rows:
            return cls._empty_result(indicator_code, config)

        df = pd.DataFrame(rows)
        current_year = 2025
        df["year"] = current_year

        metric_field = config["metric_field"]
        metric_name = config["metric_name"]

        wide = df.pivot_table(
            index="name", columns="year",
            values=metric_field, aggfunc="max",
        ).sort_index(axis=1)

        if wide.empty or len(wide) < min_countries:
            return cls._empty_result(indicator_code, config)

        normalized_rows = []
        for name, row in wide.iterrows():
            for year, value in row.items():
                if pd.isna(value):
                    continue
                normalized_rows.append({
                    "country": name, "country_code": name,
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