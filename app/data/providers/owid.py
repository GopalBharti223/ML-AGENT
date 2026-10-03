"""
OWID provider — Our World in Data grapher datasets.

CONTENT POLICY (Governance indicators):

The Corruption Perceptions Index entry is a PERCEPTION measure:
a composite of expert and business surveys curated by
Transparency International, NOT an objective measurement of
corruption.  We NEVER claim a country "is the most corrupt" or
"has the cleanest government" -- content must reference the
INDEX SCORE ("highest/lowest Corruption Perceptions Index
score", "as measured by Transparency International") and stay
strictly descriptive (rank + score + year).  The matching
framing constraint in app/ai/script.py enforces this in every
generated title and script.

CONTENT POLICY (Natural-disaster deaths -- EM-DAT):

Deaths from natural disasters are RECORDED deaths from the
EM-DAT international disaster database (via OWID).  Recording
quality improves dramatically in recent decades; older decades
are significantly underreported.  We NEVER frame any country as
"the most disaster-prone" and NEVER compare death counts across
decades as if equally recorded -- wording stays "recorded
deaths", "as catalogued by EM-DAT", with time comparisons
scoped to recent decades.  Blank cells mean NO RECORD (dropped,
never coerced to zero).  Matching FRAMING_CONSTRAINTS entries
in app/ai/script.py enforce this in every generated script.

CONTENT POLICY (Biodiversity -- IUCN Red List Index):

The Red List Index measures the DIRECTION of national
extinction risk over time (0-1; falling = species moving
toward extinction faster).  It is NOT a species count: we
NEVER claim a country "has the most endangered species" or
cite any "number of species" from this dataset.  Framing stays
on risk trends ("extinction risk rising fastest", "reversing
species decline").  Matching FRAMING_CONSTRAINTS entry in
app/ai/script.py enforces this in every generated script.
"""
from io import StringIO
from typing import Dict, List, Optional

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


class OWIDProvider(DataProvider):

    provider_id = "owid"
    provider_name = "Our World in Data"
    base_url = "https://ourworldindata.org/grapher"
    request_timeout = 45

    INDICATORS: Dict[str, Dict] = {
        "population": {
            "name": "Population",
            "category": "Population",
            "slug": "population",
        },
        "life_expectancy": {
            "name": "Life Expectancy",
            "category": "Health",
            "slug": "life-expectancy",
        },
        "co2_emissions": {
            "name": "Annual CO2 Emissions",
            "category": "Climate",
            "slug": "annual-co2-emissions-per-country",
        },
        "co2_per_capita": {
            "name": "CO2 Emissions Per Capita",
            "category": "Climate",
            "slug": "co-emissions-per-capita",
        },
        "energy_per_capita": {
            "name": "Energy Use Per Person",
            "category": "Energy",
            "slug": "per-capita-energy-use",
        },
        "gdp_per_capita": {
            "name": "GDP Per Capita",
            "category": "Economy",
            "slug": "gdp-per-capita-worldbank",
        },
        "internet_users": {
            "name": "Share of Population Using the Internet",
            "category": "Technology",
            "slug": "share-of-individuals-using-the-internet",
        },
        # Transparency International's CPI, mirrored by OWID.
        # PERCEPTION index (survey-based) -- see the content
        # policy in this module's docstring; scores are 0-100.
        "corruption_perceptions_index": {
            "name": "Corruption Perceptions Index Score",
            "category": "Governance",
            "slug": "corruption-perception-index",
        },
        # -----------------------------------------------------
        # Natural-disaster deaths (EM-DAT, mirrored by OWID).
        # Multi-column CSV: each indicator selects ONE column
        # ("column" key).  Blank cells are coerced to NaN and
        # dropped -- a blank means NO RECORD, never zero.
        # See the content policy in this module's docstring and
        # the matching FRAMING_CONSTRAINTS entry in script.py.
        # -----------------------------------------------------
        "deaths_floods": {
            "name": "Recorded Deaths from Floods",
            "category": "Environment",
            "slug": "number-of-deaths-from-natural-disasters",
            "column": "Floods",
        },
        "deaths_all_disasters": {
            "name": "Recorded Deaths from All Natural Disasters",
            "category": "Environment",
            "slug": "number-of-deaths-from-natural-disasters",
            "column": "All disasters",
        },
        # -----------------------------------------------------
        # IUCN Red List Index (via OWID): measures the DIRECTION
        # of national extinction risk over time (0-1; falling =
        # species moving toward extinction faster).  NOT a species
        # count -- never claim "most endangered species".  See the
        # FRAMING_CONSTRAINTS entry in script.py.
        # -----------------------------------------------------
        "red_list_index": {
            "name": "Red List Index (Extinction Risk Trend)",
            "category": "Environment",
            "slug": "red-list-index",
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
                source_url=cls._chart_url(
                    config["slug"]
                )
            )
            for code, config
            in cls.INDICATORS.items()
        ]

    @classmethod
    def _chart_url(
        cls,
        slug: str
    ) -> str:

        return f"{cls.base_url}/{slug}"

    @classmethod
    def _csv_url(
        cls,
        slug: str
    ) -> str:

        return (
            f"{cls._chart_url(slug)}.csv"
            "?v=1&csvType=full&useColumnShortNames=false"
        )

    @classmethod
    def _metadata_url(
        cls,
        slug: str
    ) -> str:

        return (
            f"{cls._chart_url(slug)}.metadata.json"
            "?v=1&csvType=full&useColumnShortNames=false"
        )

    @classmethod
    def _request_text(
        cls,
        url: str
    ) -> str:

        response = requests.get(
            url,
            timeout=cls.request_timeout,
            headers={
                "User-Agent":
                    "MetricForge-OWIDProvider/1.0"
            }
        )

        response.raise_for_status()

        return response.text

    @classmethod
    def _request_json(
        cls,
        url: str
    ) -> Dict:

        response = requests.get(
            url,
            timeout=cls.request_timeout,
            headers={
                "User-Agent":
                    "MetricForge-OWIDProvider/1.0"
            }
        )

        response.raise_for_status()

        return response.json()

    @classmethod
    def _load_csv(
        cls,
        slug: str
    ) -> pd.DataFrame:

        csv_text = cls._request_text(
            cls._csv_url(slug)
        )

        return pd.read_csv(
            StringIO(csv_text)
        )

    @classmethod
    def _load_metadata(
        cls,
        slug: str
    ) -> Dict:

        try:
            return cls._request_json(
                cls._metadata_url(slug)
            )
        except requests.RequestException:
            return {}

    @classmethod
    def _data_column(
        cls,
        df: pd.DataFrame,
        preferred: Optional[str] = None
    ) -> str:

        structural_columns = {
            "Entity",
            "Code",
            "Year",
            "Day",
        }

        if (
            preferred
            and preferred in df.columns
        ):
            return preferred

        data_columns = [
            column
            for column in df.columns
            if column not in structural_columns
        ]

        if not data_columns:
            raise ValueError(
                "OWID dataset has no metric column."
            )

        return data_columns[0]

    @classmethod
    def _filter_country_rows(
        cls,
        df: pd.DataFrame
    ) -> pd.DataFrame:

        if "Code" not in df.columns:
            return pd.DataFrame()

        codes = (
            df["Code"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        mask = (
            codes.str.len().eq(3)
            & ~codes.str.startswith(
                "OWID_"
            )
        )

        return df.loc[
            mask
        ].copy()

    @classmethod
    def _select_years(
        cls,
        df: pd.DataFrame,
        years: int
    ) -> pd.DataFrame:

        if "Year" not in df.columns:
            return pd.DataFrame()

        df["Year"] = pd.to_numeric(
            df["Year"],
            errors="coerce"
        )

        df = df.dropna(
            subset=[
                "Year"
            ]
        )

        if df.empty:
            return df

        latest_year = int(
            df["Year"].max()
        )

        start_year = (
            latest_year
            - int(years)
            + 1
        )

        return df[
            (
                df["Year"] >= start_year
            )
            & (
                df["Year"] <= latest_year
            )
        ].copy()

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

        available_years = list(
            wide_data.columns
        )

        min_required_years = max(
            3,
            int(
                len(available_years)
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
                    f"  [OWID] Requested country "
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
                    f"  [OWID] Requested country "
                    f"'{key[1]}' has no usable data; "
                    "skipping it."
                )

            if required_keys:

                print(
                    "  [OWID] Country constraint: "
                    "required "
                    f"[{', '.join(str(key[0]) for key in required_keys)}] "
                    "+ context fill."
                )

        else:

            selected_indexes = scored_keys[
                :min_countries
            ]

        selected = wide_data.loc[
            selected_indexes
        ].copy()

        return selected

    @classmethod
    def fetch_normalized(
        cls,
        indicator_code: str,
        years: int = 15,
        story_type: str = "fastest_growth",
        min_countries: int = 8,
        countries=None
    ) -> DataProviderResult:

        if indicator_code not in cls.INDICATORS:
            raise ValueError(
                "Unsupported OWID indicator: "
                f"{indicator_code}. "
                "Use one of: "
                f"{', '.join(sorted(cls.INDICATORS))}."
            )

        config = cls.INDICATORS[
            indicator_code
        ]

        years = max(
            3,
            min(
                int(years),
                40
            )
        )

        slug = config[
            "slug"
        ]

        print(
            "Fetching OWID dataset: "
            f"{config['name']}..."
        )

        raw = cls._load_csv(
            slug
        )

        raw = cls._filter_country_rows(
            raw
        )

        raw = cls._select_years(
            raw,
            years
        )

        metric_column = cls._data_column(
            raw,
            config.get(
                "column"
            )
        )

        raw[metric_column] = pd.to_numeric(
            raw[metric_column],
            errors="coerce"
        )

        raw = raw.dropna(
            subset=[
                "Entity",
                "Code",
                "Year",
                metric_column
            ]
        )

        if raw.empty:
            raise ValueError(
                "OWID dataset returned no usable "
                "country/year values."
            )

        metadata = cls._load_metadata(
            slug
        )

        source_url = cls._chart_url(
            slug
        )

        rows = []

        for _, item in raw.iterrows():
            rows.append(
                {
                    "country": item["Entity"],
                    "country_code": item["Code"],
                    "year": int(item["Year"]),
                    "metric": config["name"],
                    "value": float(item[metric_column]),
                    "provider": cls.provider_id,
                    "source_name": cls.provider_name,
                    "source_url": source_url,
                    "indicator_code": indicator_code,
                }
            )

        normalized = normalize_long_data(
            rows=rows,
            provider=cls.provider_id,
            metric_name=config["name"],
            source_name=cls.provider_name,
            source_url=source_url,
            indicator_code=indicator_code
        )

        result_metadata = {
            "provider": cls.provider_id,
            "source_name": cls.provider_name,
            "source_url": source_url,
            "indicator_code": indicator_code,
            "indicator_name": config["name"],
            "owid_slug": slug,
            "owid_metric_column": metric_column,
            "owid_metadata": metadata,
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
                "OWID dataset did not have enough "
                "usable countries after filtering."
            )

        print(
            "OWID data accepted: "
            f"{len(wide_data)} countries, "
            f"{wide_data.columns[0]} to "
            f"{wide_data.columns[-1]}."
        )

        return DataProviderResult(
            provider=cls.provider_id,
            indicator_code=indicator_code,
            metric_name=config["name"],
            source_name=cls.provider_name,
            source_url=source_url,
            normalized_data=normalized,
            wide_data=wide_data,
            metadata=result_metadata
        )
