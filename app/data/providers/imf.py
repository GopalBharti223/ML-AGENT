from datetime import date
from typing import Dict, List

import pandas as pd
import requests

from app.data.providers.base import (
    DataProvider,
    DataProviderResult,
    IndicatorInfo,
    match_country_request,
    normalize_long_data,
    select_required_plus_context,
    to_visual_dataframe,
)


class IMFProvider(DataProvider):

    provider_id = "imf"
    provider_name = "International Monetary Fund"
    base_url = "https://www.imf.org/external/datamapper/api/v2"
    source_url = "https://www.imf.org/external/datamapper"
    request_timeout = 45

    INDICATORS: Dict[str, Dict] = {
        "NGDPD": {
            "name": "GDP, current prices",
            "category": "Economy",
            "dataset": "WEO",
        },
        "NGDP_RPCH": {
            "name": "Real GDP growth",
            "category": "Economy",
            "dataset": "WEO",
        },
        "NGDPDPC": {
            "name": "GDP per capita, current prices",
            "category": "Economy",
            "dataset": "WEO",
        },
        "PCPIPCH": {
            "name": "Inflation rate, average consumer prices",
            "category": "Inflation",
            "dataset": "WEO",
        },
        "GGXWDG_NGDP": {
            "name": "General government gross debt",
            "category": "Public Finance",
            "dataset": "WEO",
        },
    }

    @classmethod
    def list_indicators(cls) -> List[IndicatorInfo]:

        return [
            IndicatorInfo(
                code=code,
                name=config["name"],
                category=config.get(
                    "category",
                    ""
                ),
                source_url=f"{cls.source_url}/{code}"
            )
            for code, config
            in cls.INDICATORS.items()
        ]

    @classmethod
    def _request_json(
        cls,
        path: str,
        params=None
    ) -> Dict:

        url = (
            f"{cls.base_url}/"
            f"{path.lstrip('/')}"
        )

        response = requests.get(
            url,
            params=params,
            timeout=cls.request_timeout,
            headers={
                "User-Agent":
                    "MetricForge-IMFProvider/1.0"
            }
        )

        if response.status_code == 403:
            raise RuntimeError(
                "IMF DataMapper API returned HTTP 403 "
                "from this environment. The provider uses "
                "the official public IMF DataMapper API, "
                "but this request was blocked upstream."
            )

        response.raise_for_status()

        return response.json()

    @classmethod
    def _load_indicator_metadata(cls) -> Dict:

        try:
            payload = cls._request_json(
                "indicators"
            )
        except Exception:
            return {}

        return payload.get(
            "indicators",
            {}
        )

    @classmethod
    def _load_country_metadata(cls) -> Dict:

        try:
            payload = cls._request_json(
                "countries"
            )
        except Exception:
            return {}

        countries = payload.get(
            "countries",
            payload
        )

        if not isinstance(
            countries,
            dict
        ):
            return {}

        result = {}

        for code, item in countries.items():
            if isinstance(
                item,
                dict
            ):
                label = (
                    item.get("label")
                    or item.get("name")
                    or code
                )
            else:
                label = str(item)

            result[
                str(code)
            ] = str(label).strip()

        return result

    @classmethod
    def _periods(
        cls,
        years: int,
        end_year=None
    ) -> List[int]:

        years = max(
            3,
            min(
                int(years),
                40
            )
        )

        if end_year is None:
            end_year = date.today().year

        end_year = int(
            end_year
        )

        start_year = (
            end_year
            - years
            + 1
        )

        return list(
            range(
                start_year,
                end_year + 1
            )
        )

    @classmethod
    def _fetch_series(
        cls,
        indicator_code: str,
        periods: List[int]
    ) -> Dict:

        params = {
            "periods": ",".join(
                str(period)
                for period in periods
            )
        }

        return cls._request_json(
            indicator_code,
            params=params
        )

    @classmethod
    def _story_score(
        cls,
        row,
        story_type: str
    ):

        values = row.dropna()

        if len(values) < 2:
            return None

        first_value = float(
            values.iloc[0]
        )
        last_value = float(
            values.iloc[-1]
        )

        if story_type in (
            "fastest_growth",
            "fastest_decline"
        ):
            if abs(first_value) < 1e-9:
                return None

            return (
                last_value - first_value
            ) / abs(first_value)

        return last_value - first_value

    @classmethod
    def _rank_visual_data(
        cls,
        wide_data: pd.DataFrame,
        story_type: str,
        min_countries: int,
        countries=None
    ) -> pd.DataFrame:

        if wide_data.empty:
            return wide_data

        min_required_years = max(
            3,
            int(
                len(wide_data.columns)
                * 0.60
            )
        )

        wide_data = wide_data.dropna(
            thresh=min_required_years
        )

        if wide_data.empty:
            return wide_data

        scored = []

        for index, row in wide_data.iterrows():
            score = cls._story_score(
                row,
                story_type
            )

            if score is None:
                continue

            scored.append(
                (
                    index,
                    score
                )
            )

        if not scored:
            return pd.DataFrame()

        ascending = story_type in (
            "most_declined",
            "fastest_decline"
        )

        scored = sorted(
            scored,
            key=lambda item: item[1],
            reverse=not ascending
        )

        scored_keys = [
            index
            for index, _
            in scored
        ]

        # -----------------------------------------------------
        # OPTIONAL COUNTRY CONSTRAINT ("required + context")
        # Requested countries with usable data are guaranteed a
        # slot; the rest is filled up to min_countries from the
        # story ranking. Missing/unrecognized countries are
        # logged and skipped -- never a hard failure.
        # -----------------------------------------------------

        if countries:

            required_keys, unmatched_tokens = (
                match_country_request(
                    countries,
                    scored_keys
                )
            )

            for token in unmatched_tokens:

                print(
                    f"  [IMF] Requested country "
                    f"'{token}' not found in this "
                    "dataset; ignoring it."
                )

            selected_indexes, missing_required = (
                select_required_plus_context(
                    scored_keys,
                    required_keys,
                    min_countries
                )
            )

            for key in missing_required:

                print(
                    f"  [IMF] Requested country "
                    f"'{key[1]}' has no usable data; "
                    "skipping it."
                )

            if required_keys:

                print(
                    "  [IMF] Country constraint: "
                    "required "
                    f"[{', '.join(str(key[0]) for key in required_keys)}] "
                    "+ context fill."
                )

        else:

            selected_indexes = scored_keys[
                :min_countries
            ]

        return wide_data.loc[
            selected_indexes
        ].copy()

    @classmethod
    def fetch_normalized(
        cls,
        indicator_code: str,
        years: int = 15,
        story_type: str = "fastest_growth",
        min_countries: int = 8,
        countries=None
    ) -> DataProviderResult:

        indicator_code = str(
            indicator_code
        ).strip()

        if indicator_code not in cls.INDICATORS:
            raise ValueError(
                "Unsupported IMF indicator: "
                f"{indicator_code}. "
                "Use one of: "
                f"{', '.join(sorted(cls.INDICATORS))}."
            )

        indicator_metadata = (
            cls._load_indicator_metadata()
        )

        official_info = indicator_metadata.get(
            indicator_code,
            {}
        )

        config = cls.INDICATORS[
            indicator_code
        ]

        metric_name = (
            official_info.get("label")
            or config["name"]
        )

        projection_year = official_info.get(
            "projection-year"
        )

        periods = cls._periods(
            years,
            end_year=projection_year
        )

        print(
            "Fetching IMF dataset: "
            f"{metric_name}..."
        )

        payload = cls._fetch_series(
            indicator_code,
            periods
        )

        values = (
            payload.get("values", {})
            .get(indicator_code, {})
        )

        if not values:
            raise ValueError(
                "IMF DataMapper returned no values "
                f"for {indicator_code}."
            )

        country_labels = cls._load_country_metadata()

        rows = []

        for country_code, series in values.items():
            if not isinstance(
                series,
                dict
            ):
                continue

            country_code = str(
                country_code
            ).strip()

            country_name = country_labels.get(
                country_code,
                country_code
            )

            for year, value in series.items():
                if value is None:
                    continue

                try:
                    year = int(year)
                    value = float(value)
                except (
                    ValueError,
                    TypeError
                ):
                    continue

                rows.append(
                    {
                        "country": country_name,
                        "country_code": country_code,
                        "year": year,
                        "metric": metric_name,
                        "value": value,
                        "provider": cls.provider_id,
                        "source_name": cls.provider_name,
                        "source_url": cls.source_url,
                        "indicator_code": indicator_code,
                    }
                )

        normalized = normalize_long_data(
            rows=rows,
            provider=cls.provider_id,
            metric_name=metric_name,
            source_name=cls.provider_name,
            source_url=cls.source_url,
            indicator_code=indicator_code
        )

        if normalized.empty:
            raise ValueError(
                "No usable IMF country/year values "
                "after normalization."
            )

        result_metadata = {
            "provider": cls.provider_id,
            "source_name": cls.provider_name,
            "source_url": cls.source_url,
            "indicator_code": indicator_code,
            "indicator_name": metric_name,
            "imf_dataset": (
                official_info.get("dataset")
                or config.get("dataset")
            ),
            "imf_unit": official_info.get("unit"),
            "imf_source": official_info.get("source"),
            "imf_projection_year": projection_year,
        }

        wide_data = to_visual_dataframe(
            normalized,
            result_metadata
        )

        wide_data = cls._rank_visual_data(
            wide_data,
            story_type,
            min_countries,
            countries=countries
        )

        wide_data.attrs.update(
            result_metadata
        )
        wide_data.attrs[
            "normalized_data"
        ] = normalized
        wide_data.attrs[
            "story_type"
        ] = story_type

        if len(wide_data) < min_countries:
            raise ValueError(
                "IMF dataset did not have enough usable "
                "countries after filtering."
            )

        print(
            "IMF data accepted: "
            f"{len(wide_data)} countries, "
            f"{wide_data.columns[0]} to "
            f"{wide_data.columns[-1]}."
        )

        return DataProviderResult(
            provider=cls.provider_id,
            indicator_code=indicator_code,
            metric_name=metric_name,
            source_name=cls.provider_name,
            source_url=cls.source_url,
            normalized_data=normalized,
            wide_data=wide_data,
            metadata=result_metadata
        )
