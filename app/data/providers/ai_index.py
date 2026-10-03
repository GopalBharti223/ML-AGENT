from io import BytesIO
from typing import Dict, List, Optional

import pandas as pd
import requests

from app.data.providers.base import (
    DataProvider,
    DataProviderResult,
    IndicatorInfo,
    normalize_long_data,
    to_visual_dataframe,
)


class AIIndexProvider(DataProvider):
    """
    Stanford AI Index Data Provider

    Provides access to AI-focused indicators from Stanford's AI Index,
    including AI investment, research, talent, and policy metrics.

    Official Data Source: https://hai.stanford.edu/ai-index
    Public Data Folder: https://drive.google.com/drive/folders/1zJTOg0iR0j5SijCwFutwWvDt143lW277

    Data is downloaded from Stanford's official public Google Drive folder
    containing the 2026 AI Index report figure data as CSV files.

    PRODUCTION BEHAVIOR:
    - Only returns real Stanford AI Index data from official sources
    - If real data is unavailable, raises a RuntimeError
    - Does NOT return fake/demo data labeled as Stanford data
    - SmartStoryEngine catches the exception and skips to other providers
    """

    provider_id = "ai_index"
    provider_name = "Stanford AI Index"
    source_url = "https://hai.stanford.edu/ai-index"
    public_data_url = "https://drive.google.com/drive/folders/1zJTOg0iR0j5SijCwFutwWvDt143lW277"
    request_timeout = 45

    # Country/entity code mapping.
    # Only include mappings where the code is genuinely known.
    # For aggregate entities without a standard code (e.g., "Rest of the world"),
    # the entity name itself is preserved as the code.
    COUNTRY_CODES: Dict[str, str] = {
        # Major entities used in AI Index figures
        "United States": "US",
        "China": "CN",
        "India": "IN",
        "Europe": "EU",
        "United Kingdom": "GB",
        "Germany": "DE",
        "France": "FR",
        "Japan": "JP",
        "South Korea": "KR",
        "Canada": "CA",
        "Australia": "AU",
        "Israel": "IL",
        "Singapore": "SG",
        "Sweden": "SE",
        "Switzerland": "CH",
        "Netherlands": "NL",
        "Spain": "ES",
        "Italy": "IT",
        "United Arab Emirates": "AE",
        "Saudi Arabia": "SA",
        "Ireland": "IE",
        "Norway": "NO",
        "Belgium": "BE",
        "Austria": "AT",
        "Finland": "FI",
        "Denmark": "DK",
        "Poland": "PL",
        "Czech Republic": "CZ",
        "New Zealand": "NZ",
        "Portugal": "PT",
        "Hong Kong": "HK",
        "Chile": "CL",
        "Costa Rica": "CR",
        "Croatia": "HR",
        "Cyprus": "CY",
        "Estonia": "EE",
        "Greece": "GR",
        "Hungary": "HU",
        "Iceland": "IS",
        "Indonesia": "ID",
        "Latvia": "LV",
        "Lithuania": "LT",
        "Luxembourg": "LU",
        "Mexico": "MX",
        "Romania": "RO",
        "Slovakia": "SK",
        "Slovenia": "SI",
        "South Africa": "ZA",
        "Turkey": "TR",
        "Uruguay": "UY",
        "Brazil": "BR",
        "Argentina": "AR",
        "Bulgaria": "BG",
    }

    # Core AI-related indicators based on Stanford AI Index publications.
    # Each indicator maps to an official per-figure CSV in the public data folder.
    INDICATORS: Dict[str, Dict] = {
        "ai_investment": {
            "name": "AI Investment",
            "category": "AI Investment",
            "description": "Private AI investment in billions USD",
            "file_id": "15nqxRFDA4bTCiToicLsCjVyDY28FAnv9",
            "file_name": "fig_4.2.11.csv",
        },
        "ai_research": {
            "name": "AI Research Publications",
            "category": "AI Research",
            "description": "AI publications share of computer science publications",
            "file_id": "1AK_x2Mx0Ro42MO_K9fVgoJAJSWaoK-Ip",
            "file_name": "fig_1.6.6.csv",
        },
        "ai_talent": {
            "name": "AI Talent",
            "category": "AI Talent",
            "description": "Net AI talent migration per 10K LinkedIn members",
            "file_id": "15b44uDmYo0ZXFg07dnyEXs-HYyQzq4Ug",
            "file_name": "fig_4.4.24.csv",
        },
        "ai_adoption": {
            "name": "AI Adoption",
            "category": "AI Adoption",
            "description": "AI diffusion rate (% of population), H2 2025 snapshot",
            "file_id": "1cu5qIeu61KtYahkO9-1nW1rwageEv6r-",
            "file_name": "fig_4.3.10.csv",
        },
        "ai_policy": {
            "name": "AI Policy",
            "category": "AI Governance",
            "description": "Number of AI-related bills/regulations",
            "file_id": "1TcKYNdgvxDqMDJVUYyAHtG0o5mRTKuez",
            "file_name": "fig_8.2.1.csv",
        },
    }

    # Indicators that only provide snapshot data (single point in time)
    SNAPSHOT_ONLY_INDICATORS = {
        "ai_adoption",
    }

    @classmethod
    def list_indicators(cls) -> List[IndicatorInfo]:
        """
        List all available AI Index indicators.
        """
        return [
            IndicatorInfo(
                code=code,
                name=config["name"],
                category=config.get("category", ""),
                source_url=f"{cls.public_data_url}?resourcekey={config.get('file_name', '')}"
            )
            for code, config in cls.INDICATORS.items()
        ]

    # ========== Internal helpers ==========

    @classmethod
    def _download_csv(cls, file_id: str) -> pd.DataFrame:
        """
        Download and parse a CSV file from the official Stanford AI Index
        public Google Drive folder.

        Handles UTF-8 and latin-1/cp1252 encoding fallback.
        """
        url = (
            "https://drive.google.com/uc"
            f"?export=download&id={file_id}"
        )

        try:
            response = requests.get(
                url,
                timeout=cls.request_timeout,
                headers={
                    "User-Agent":
                        "MetricForge-AIIndexProvider/1.0"
                }
            )
        except Exception as error:
            raise RuntimeError(
                f"Cannot access Stanford AI Index data source: {error}. "
                f"Official source: {cls.public_data_url}"
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"Stanford AI Index download failed with HTTP "
                f"{response.status_code}. "
                f"Official source: {cls.public_data_url}"
            )

        raw_bytes = response.content

        if not raw_bytes:
            raise RuntimeError(
                "Stanford AI Index download returned an empty file."
            )

        # Try UTF-8 first, then fall back to latin-1/cp1252
        last_error = None
        for encoding in ("utf-8", "latin-1", "cp1252"):
            try:
                return pd.read_csv(
                    BytesIO(raw_bytes),
                    encoding=encoding
                )
            except UnicodeDecodeError as error:
                last_error = error
                continue
            except Exception as error:
                last_error = error
                continue

        raise RuntimeError(
            "Stanford AI Index CSV could not be parsed "
            f"with any supported encoding: {last_error}"
        )

    @classmethod
    def _country_code(cls, entity: str) -> str:
        """
        Map a country/entity name to its ISO code when genuinely known.
        For unknown or aggregate entities, preserves the entity name.
        """
        name = str(entity).strip()

        code = cls.COUNTRY_CODES.get(name)
        if code:
            return code

        # Some entity names may have annotation suffixes (e.g., "Australia*")
        base_name = name.rstrip("*")
        code = cls.COUNTRY_CODES.get(base_name)
        if code:
            return code

        return name

    @classmethod
    def _parse_year_value_label(
        cls,
        df: pd.DataFrame,
        value_column: str,
        label_column: str,
        year_column: str = "Year"
    ) -> pd.DataFrame:
        """
        Parse a long-format CSV with columns: [Year, value, Label/country].
        Returns a standardized DataFrame with country, country_code, year, value.
        """
        rows = []

        for _, item in df.iterrows():
            entity = str(item.get(label_column, "")).strip()
            year_raw = item.get(year_column)

            try:
                year = int(float(year_raw))
            except (TypeError, ValueError):
                continue

            try:
                value = float(item[value_column])
            except (TypeError, ValueError):
                continue

            if pd.isna(value):
                continue

            rows.append(
                {
                    "country": entity,
                    "country_code": cls._country_code(entity),
                    "year": year,
                    "value": value,
                }
            )

        return pd.DataFrame(rows)

    @classmethod
    def _parse_talent_csv(
        cls,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Parse the AI talent migration CSV (fig_4.4.24.csv).
        Columns: [year, country, netflow_per_10K]
        Year values are like '1/1/21' meaning Jan 1 of 2021.
        """
        rows = []

        for _, item in df.iterrows():
            entity = str(item.get("country", "")).strip()
            year_raw = item.get("year")

            # Parse year from '1/1/21' style dates
            year = None
            if isinstance(year_raw, str):
                # Format like '1/1/21' -> extract last component as 2-digit year
                parts = year_raw.strip().split("/")
                if len(parts) >= 2:
                    try:
                        yy = int(parts[-1])
                        year = 2000 + yy if yy < 100 else yy
                    except (TypeError, ValueError):
                        year = None
            elif isinstance(year_raw, (int, float)):
                try:
                    year = int(year_raw)
                except (TypeError, ValueError):
                    year = None

            if year is None:
                continue

            try:
                value = float(item.get("netflow_per_10K"))
            except (TypeError, ValueError):
                continue

            if pd.isna(value):
                continue

            entity = entity.rstrip("*")

            rows.append(
                {
                    "country": entity,
                    "country_code": cls._country_code(entity),
                    "year": year,
                    "value": value,
                }
            )

        return pd.DataFrame(rows)

    @classmethod
    def _parse_wide_country_csv(
        cls,
        df: pd.DataFrame,
        country_column: str = "Country"
    ) -> pd.DataFrame:
        """
        Parse a wide-format CSV where columns are years.
        Columns: [Country, '2019', '2020', ..., '2025'].
        """
        rows = []

        for _, item in df.iterrows():
            entity = str(item.get(country_column, "")).strip()

            if not entity:
                continue

            for column in df.columns:
                if column == country_column:
                    continue

                try:
                    year = int(str(column).strip())
                except (TypeError, ValueError):
                    continue

                try:
                    value = float(item[column])
                except (TypeError, ValueError):
                    continue

                if pd.isna(value):
                    continue

                rows.append(
                    {
                        "country": entity,
                        "country_code": cls._country_code(entity),
                        "year": year,
                        "value": value,
                    }
                )

        return pd.DataFrame(rows)

    @classmethod
    def _select_recent_years(
        cls,
        normalized: pd.DataFrame,
        years: int
    ) -> pd.DataFrame:
        """
        Keep only the most recent N years in the normalized data.
        """
        if normalized.empty or "year" not in normalized.columns:
            return normalized

        latest_year = int(
            normalized["year"].max()
        )

        start_year = latest_year - int(years) + 1

        return normalized[
            normalized["year"] >= start_year
        ].copy()

    # ========== Public methods ==========

    @classmethod
    def fetch_normalized(
        cls,
        indicator_code: str,
        years: int = 15,
        story_type: str = "fastest_growth",
        min_countries: int = 8
    ) -> DataProviderResult:
        """
        Fetch and normalize Stanford AI Index data.

        Downloads the official per-figure CSV from Stanford's public
        Google Drive folder and normalizes it to the standard long/wide
        format used by the visualisation system.

        If the official data cannot be downloaded, parsed, or normalized,
        raises a RuntimeError (never returns fake/empty data as success).
        """
        if indicator_code not in cls.INDICATORS:
            raise ValueError(
                f"Unknown AI Index indicator: {indicator_code}. "
                f"Use one of: {', '.join(sorted(cls.INDICATORS.keys()))}"
            )

        config = cls.INDICATORS[indicator_code]
        metric_name = config["name"]

        # Snapshot-only indicators cannot produce multi-year stories
        if indicator_code in cls.SNAPSHOT_ONLY_INDICATORS:
            raise RuntimeError(
                f"Stanford AI Index indicator '{indicator_code}' "
                f"({metric_name}) is a single-year snapshot dataset "
                f"({config['file_name']}) and cannot be used for "
                "multi-year time-series stories. "
                f"Official source: {cls.public_data_url}"
            )

        print(
            f"Fetching Stanford AI Index: {indicator_code} "
            f"({config['file_name']})..."
        )

        # Download the official CSV
        df = cls._download_csv(config["file_id"])

        if df.empty:
            raise RuntimeError(
                f"Stanford AI Index CSV for '{indicator_code}' "
                "was empty after download."
            )

        # Parse based on indicator-specific column structure
        if indicator_code == "ai_investment":
            # Columns: Year, Total investment (in billions of US dollars), Label
            value_column = (
                "Total investment (in billions of US dollars)"
                if "Total investment (in billions of US dollars)" in df.columns
                else df.columns[1]
            )
            normalized = cls._parse_year_value_label(
                df,
                value_column=value_column,
                label_column="Label"
            )
        elif indicator_code == "ai_research":
            # Columns: Year, AI publications in CS (% of total), Label
            value_column = (
                "AI publications in CS (% of total)"
                if "AI publications in CS (% of total)" in df.columns
                else df.columns[1]
            )
            normalized = cls._parse_year_value_label(
                df,
                value_column=value_column,
                label_column="Label"
            )
        elif indicator_code == "ai_talent":
            # Columns: year, country, netflow_per_10K
            normalized = cls._parse_talent_csv(df)
        elif indicator_code == "ai_policy":
            # Columns: Country, 2019, 2020, ..., 2025 (wide format)
            normalized = cls._parse_wide_country_csv(df)
        else:
            raise RuntimeError(
                f"No parser implemented for Stanford AI Index "
                f"indicator '{indicator_code}'."
            )

        if normalized.empty:
            raise RuntimeError(
                f"Stanford AI Index CSV for '{indicator_code}' "
                "contained no usable country/year rows after parsing."
            )

        # Apply the requested year window
        normalized = cls._select_recent_years(
            normalized,
            years
        )

        if normalized.empty:
            raise RuntimeError(
                f"Stanford AI Index data for '{indicator_code}' "
                f"had no rows within the requested {years}-year window."
            )

        # Sort year range for reporting
        available_years = sorted(
            normalized["year"].unique()
        )

        # Build rows for normalize_long_data
        rows = []

        for _, item in normalized.iterrows():
            rows.append(
                {
                    "country": item["country"],
                    "country_code": item["country_code"],
                    "year": int(item["year"]),
                    "metric": metric_name,
                    "value": float(item["value"]),
                    "provider": cls.provider_id,
                    "source_name": cls.provider_name,
                    "source_url": cls.source_url,
                    "indicator_code": indicator_code,
                }
            )

        normalized_data = normalize_long_data(
            rows=rows,
            provider=cls.provider_id,
            metric_name=metric_name,
            source_name=cls.provider_name,
            source_url=cls.source_url,
            indicator_code=indicator_code
        )

        if normalized_data.empty:
            raise RuntimeError(
                f"Stanford AI Index normalized data for "
                f"'{indicator_code}' was empty."
            )

        # Build result metadata
        result_metadata = {
            "provider": cls.provider_id,
            "source_name": cls.provider_name,
            "source_url": cls.source_url,
            "public_data_url": cls.public_data_url,
            "indicator_code": indicator_code,
            "indicator_name": metric_name,
            "indicator_description": config["description"],
            "official_file": config["file_name"],
            "official_file_id": config["file_id"],
            "years": available_years,
            "entity_count": int(
                normalized_data["country_code"].nunique()
            ),
        }

        # Build visual (wide) DataFrame
        wide_data = to_visual_dataframe(
            normalized_data,
            result_metadata
        )

        wide_data.attrs.update(
            result_metadata
        )
        wide_data.attrs[
            "normalized_data"
        ] = normalized_data
        wide_data.attrs[
            "story_type"
        ] = story_type

        if wide_data.empty:
            raise RuntimeError(
                f"Stanford AI Index wide data for '{indicator_code}' "
                "was empty after pivoting."
            )

        # Coverage check:
        # Datasets with few entities (e.g., 3 for investment) are valid.
        # Only fail if we got zero rows of usable data.
        entity_count = len(wide_data)
        if entity_count == 0:
            raise RuntimeError(
                f"Stanford AI Index data for '{indicator_code}' "
                "had no usable entities."
            )

        print(
            f"Stanford AI Index data accepted: "
            f"{entity_count} entities, "
            f"{available_years[0]} to {available_years[-1]} "
            f"({len(available_years)} years)."
        )

        return DataProviderResult(
            provider=cls.provider_id,
            indicator_code=indicator_code,
            metric_name=metric_name,
            source_name=cls.provider_name,
            source_url=cls.source_url,
            normalized_data=normalized_data,
            wide_data=wide_data,
            metadata=result_metadata
        )