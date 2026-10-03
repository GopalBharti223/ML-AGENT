import time
import requests
import pandas as pd
import numpy as np
from typing import Optional

from app.data.providers.base import (
    match_country_request,
    select_required_plus_context,
)


class WorldBankData:

    BASE_URL = "https://api.worldbank.org/v2"

    # =========================================================
    # WORLD BANK INDICATORS
    # =========================================================

    INDICATORS = {

        "IT.NET.USER.ZS":
            "Internet Users (% of Population)",

        "SP.DYN.LE00.IN":
            "Life Expectancy at Birth",

        "NY.GDP.MKTP.CD":
            "GDP (Current US$)",

        "NY.GDP.PCAP.CD":
            "GDP Per Capita (Current US$)",

        "SP.POP.TOTL":
            "Population",

        "SP.URB.TOTL.IN.ZS":
            "Urban Population (%)",

        "SE.XPD.TOTL.GD.ZS":
            "Government Education Expenditure (% of GDP)",

        "MS.MIL.XPND.GD.ZS":
            "Military Expenditure (% of GDP)",

        "EG.ELC.ACCS.ZS":
            "Access to Electricity (%)",

        "SH.DYN.MORT":
            "Under-5 Mortality Rate",

        "SH.XPD.CHEX.GD.ZS":
            "Current Health Expenditure (% of GDP)",

        # External debt stocks (International Debt Statistics).
        # COVERAGE HONESTY: only nations that REPORT external debt
        # to the World Bank appear here -- mostly emerging and
        # developing economies.  High-income non-reporters (US,
        # Japan, Germany, UK, France...) are absent, so generated
        # content must scope claims to "among reporting nations"
        # (see the matching framing constraint in app/ai/script.py).
        "DT.DOD.DECT.CD":
            "External Debt Stocks (Current US$)",
    }

    # =========================================================
    # REQUEST SETTINGS
    # =========================================================

    REQUEST_TIMEOUT = 60

    MAX_RETRIES = 3

    RETRY_DELAY = 2

    # =========================================================
    # COUNTRY CACHE
    # =========================================================

    _countries_cache = None

    # =========================================================
    # BASIC REQUEST
    # =========================================================

    @classmethod
    def _request(
        cls,
        url,
        params=None,
        timeout=None
    ):

        if timeout is None:
            timeout = cls.REQUEST_TIMEOUT

        last_error = None

        for attempt in range(
            1,
            cls.MAX_RETRIES + 1
        ):

            try:

                print(
                    f"🌐 World Bank request "
                    f"attempt {attempt}/"
                    f"{cls.MAX_RETRIES}"
                )

                response = requests.get(
                    url,
                    params=params,
                    timeout=timeout,
                    headers={
                        "User-Agent":
                            "MyShorts-DataFactory/1.0"
                    }
                )

                response.raise_for_status()

                payload = response.json()

                return payload

            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError
            ) as e:

                last_error = e

                print(
                    f"⚠️ World Bank connection "
                    f"problem: {e}"
                )

                if attempt < cls.MAX_RETRIES:

                    print(
                        f"⏳ Retrying in "
                        f"{cls.RETRY_DELAY} seconds..."
                    )

                    time.sleep(
                        cls.RETRY_DELAY
                    )

            except (
                requests.exceptions.RequestException,
                ValueError
            ) as e:

                last_error = e

                print(
                    f"⚠️ World Bank API error: "
                    f"{e}"
                )

                if attempt < cls.MAX_RETRIES:

                    time.sleep(
                        cls.RETRY_DELAY
                    )

            except Exception as e:

                last_error = e

                print(
                    f"⚠️ Unexpected World Bank "
                    f"error: {e}"
                )

                if attempt < cls.MAX_RETRIES:

                    time.sleep(
                        cls.RETRY_DELAY
                    )

        print(
            f"❌ World Bank request failed "
            f"after {cls.MAX_RETRIES} attempts."
        )

        if last_error:

            print(
                f"   Last error: {last_error}"
            )

        return None

    # =========================================================
    # GET ACTUAL COUNTRIES
    # =========================================================

    @classmethod
    def get_real_countries(cls):

        """
        Returns only actual countries.

        World Bank also returns:
        - regions
        - income groups
        - lending groups
        - World Bank aggregates

        Those are removed here.
        """

        if cls._countries_cache is not None:

            return cls._countries_cache

        url = (
            f"{cls.BASE_URL}/country"
        )

        params = {
            "format": "json",
            "per_page": 400
        }

        payload = cls._request(
            url,
            params
        )

        if not payload or len(payload) < 2:

            print(
                "❌ Could not load World Bank "
                "country metadata."
            )

            return {}

        countries = {}

        for item in payload[1]:

            country_id = item.get(
                "id"
            )

            country_name = item.get(
                "name"
            )

            region = item.get(
                "region",
                {}
            )

            region_id = region.get(
                "id"
            )

            if not country_id:
                continue

            if not country_name:
                continue

            # World Bank aggregate regions
            # normally have region.id == "NA".
            if region_id == "NA":
                continue

            countries[country_id] = country_name

        print(
            f"🌍 World Bank real countries "
            f"available: {len(countries)}"
        )

        cls._countries_cache = countries

        return countries

    # =========================================================
    # FETCH RAW DATA - NORMAL METHOD
    # =========================================================

    @classmethod
    def _fetch_raw_data(
        cls,
        indicator_code: str,
        start_year: int,
        end_year: int
    ):

        url = (
            f"{cls.BASE_URL}/country/all/indicator/"
            f"{indicator_code}"
        )

        params = {
            "format": "json",
            "date": f"{start_year}:{end_year}",
            "per_page": 20000
        }

        print(
            "📡 Requesting World Bank "
            "all-country dataset..."
        )

        payload = cls._request(
            url,
            params,
            timeout=cls.REQUEST_TIMEOUT
        )

        if not payload or len(payload) < 2:

            return []

        return payload[1]

    # =========================================================
    # FALLBACK COUNTRY-BY-COUNTRY FETCH
    # =========================================================

    @classmethod
    def _fetch_country_data(
        cls,
        indicator_code: str,
        country_code: str,
        start_year: int,
        end_year: int
    ):

        url = (
            f"{cls.BASE_URL}/country/"
            f"{country_code}/indicator/"
            f"{indicator_code}"
        )

        params = {
            "format": "json",
            "date": f"{start_year}:{end_year}",
            "per_page": 100
        }

        payload = cls._request(
            url,
            params,
            timeout=30
        )

        if not payload or len(payload) < 2:

            return []

        return payload[1]

    # =========================================================
    # FALLBACK FETCH ALL COUNTRIES
    # =========================================================

    @classmethod
    def _fetch_with_fallback(
        cls,
        indicator_code: str,
        start_year: int,
        end_year: int,
        real_countries: dict
    ):

        # -----------------------------------------------------
        # FIRST ATTEMPT
        # -----------------------------------------------------

        raw_data = cls._fetch_raw_data(
            indicator_code,
            start_year,
            end_year
        )

        if raw_data:

            print(
                f"✅ Bulk World Bank request "
                f"returned {len(raw_data)} records."
            )

            return raw_data

        # -----------------------------------------------------
        # FALLBACK
        # -----------------------------------------------------

        print(
            "\n⚠️ Bulk World Bank request failed."
        )

        print(
            "🔄 Switching to country-by-country "
            "fallback mode..."
        )

        raw_data = []

        country_items = list(
            real_countries.items()
        )

        total_countries = len(
            country_items
        )

        for position, (
            country_code,
            country_name
        ) in enumerate(
            country_items,
            start=1
        ):

            print(
                f"   🌍 [{position}/"
                f"{total_countries}] "
                f"{country_name}"
            )

            country_records = (
                cls._fetch_country_data(
                    indicator_code,
                    country_code,
                    start_year,
                    end_year
                )
            )

            if country_records:

                raw_data.extend(
                    country_records
                )

            # -------------------------------------------------
            # Safety pause
            #
            # Prevent sending requests too aggressively.
            # -------------------------------------------------

            time.sleep(0.05)

        print(
            f"📦 Fallback collected "
            f"{len(raw_data)} records."
        )

        return raw_data

    # =========================================================
    # CLEAN DATA
    # =========================================================

    @classmethod
    def _build_dataframe(
        cls,
        raw_data,
        real_countries
    ):

        rows = []

        for item in raw_data:

            country_id = item.get(
                "countryiso3code"
            )

            country_name = item.get(
                "country",
                {}
            ).get(
                "value"
            )

            year = item.get(
                "date"
            )

            value = item.get(
                "value"
            )

            if not country_id:
                continue

            if country_id not in real_countries:
                continue

            if not year:
                continue

            if value is None:
                continue

            try:

                year = int(
                    year
                )

                value = float(
                    value
                )

            except (
                ValueError,
                TypeError
            ):

                continue

            rows.append(
                {
                    "country":
                        country_name,

                    "country_code":
                        country_id,

                    "year":
                        year,

                    "value":
                        value
                }
            )

        if not rows:

            return pd.DataFrame()

        df = pd.DataFrame(
            rows
        )

        # -----------------------------------------------------
        # Remove duplicates
        # -----------------------------------------------------

        df = df.drop_duplicates(
            subset=[
                "country_code",
                "year"
            ]
        )

        # -----------------------------------------------------
        # Pivot
        # -----------------------------------------------------

        pivot = df.pivot(
            index=[
                "country_code",
                "country"
            ],
            columns="year",
            values="value"
        )

        pivot = pivot.sort_index(
            axis=1
        )

        return pivot

    # =========================================================
    # STORY CALCULATION
    # =========================================================

    @classmethod
    def _calculate_story_value(
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

        if story_type == "biggest_jump":

            return (
                last_value
                - first_value
            )

        if story_type == "fastest_growth":

            if abs(first_value) < 1e-9:

                return None

            return (
                (last_value - first_value)
                / abs(first_value)
            )

        if story_type == "most_declined":

            return (
                last_value
                - first_value
            )

        if story_type == "fastest_decline":

            if abs(first_value) < 1e-9:

                return None

            return (
                (last_value - first_value)
                / abs(first_value)
            )

        return (
            last_value
            - first_value
        )

    # =========================================================
    # STORY RANKING
    # =========================================================

    @classmethod
    def _rank_countries(
        cls,
        df,
        story_type
    ):

        ranking = []

        for index, row in df.iterrows():

            score = (
                cls._calculate_story_value(
                    row,
                    story_type
                )
            )

            if score is None:
                continue

            country_code = index[0]

            country_name = index[1]

            ranking.append(
                {
                    "country_code":
                        country_code,

                    "country":
                        country_name,

                    "story_value":
                        score
                }
            )

        if not ranking:

            return []

        ranking_df = pd.DataFrame(
            ranking
        )

        if story_type in (
            "biggest_jump",
            "fastest_growth"
        ):

            ranking_df = (
                ranking_df.sort_values(
                    "story_value",
                    ascending=False
                )
            )

        elif story_type in (
            "most_declined",
            "fastest_decline"
        ):

            ranking_df = (
                ranking_df.sort_values(
                    "story_value",
                    ascending=True
                )
            )

        else:

            ranking_df = (
                ranking_df.sort_values(
                    "story_value",
                    ascending=False
                )
            )

        return ranking_df.to_dict(
            "records"
        )

    # =========================================================
    # VISUAL QUALITY
    # =========================================================

    @classmethod
    def _visual_quality(
        cls,
        selected_df,
        story_type
    ):

        if selected_df.empty:

            return {
                "score": 0,
                "spread": 0,
                "similar_bars": 100,
                "average_gap": 0
            }

        values = []

        for index, row in (
            selected_df.iterrows()
        ):

            story_value = (
                cls._calculate_story_value(
                    row,
                    story_type
                )
            )

            if story_value is not None:

                values.append(
                    float(story_value)
                )

        if len(values) < 2:

            return {
                "score": 0,
                "spread": 0,
                "similar_bars": 100,
                "average_gap": 0
            }

        values = np.array(
            values,
            dtype=float
        )

        min_value = np.min(
            values
        )

        max_value = np.max(
            values
        )

        mean_abs = np.mean(
            np.abs(values)
        )

        if mean_abs <= 1e-12:

            spread = 0

        else:

            spread = (
                max_value
                - min_value
            ) / mean_abs

        value_range = (
            max_value
            - min_value
        )

        if value_range <= 1e-12:

            normalized = np.zeros_like(
                values
            )

        else:

            normalized = (
                values
                - min_value
            ) / value_range

        sorted_values = np.sort(
            normalized
        )

        gaps = np.diff(
            sorted_values
        )

        if len(gaps) == 0:

            average_gap = 0

        else:

            average_gap = float(
                np.mean(gaps)
            )

        similar_count = 0

        for gap in gaps:

            if gap < 0.10:

                similar_count += 1

        if len(gaps) > 0:

            similar_percent = (
                similar_count
                / len(gaps)
                * 100
            )

        else:

            similar_percent = 100

        spread_score = min(
            50,
            spread * 50
        )

        gap_score = min(
            30,
            average_gap * 100
        )

        diversity_score = max(
            0,
            20
            - (
                similar_percent
                * 0.20
            )
        )

        score = (
            spread_score
            + gap_score
            + diversity_score
        )

        score = int(
            max(
                0,
                min(
                    100,
                    score
                )
            )
        )

        return {
            "score":
                score,

            "spread":
                round(
                    float(spread),
                    2
                ),

            "similar_bars":
                round(
                    float(
                        similar_percent
                    )
                ),

            "average_gap":
                round(
                    float(
                        average_gap
                    ),
                    2
                )
        }

    # =========================================================
    # MAIN FETCH METHOD
    # =========================================================

    @classmethod
    def fetch_data(
        cls,
        indicator_code: str,
        years: int = 15,
        story_type: str = "fastest_growth",
        min_countries: int = 8,
        countries=None
    ):

        indicator_name = cls.INDICATORS.get(
        indicator_code,
        indicator_code
        )

        print(
             f"Fetching {years}-year time series for "
             f"{indicator_name}..."
        )

        # -----------------------------------------------------
        # Validate years
        # -----------------------------------------------------

        try:

            years = int(
                years
            )

        except (
            ValueError,
            TypeError
        ):

            years = 15

        years = max(
            5,
            min(
                years,
                30
            )
        )

        # -----------------------------------------------------
        # Validate story
        # -----------------------------------------------------

        valid_story_types = {
            "fastest_growth",
            "fastest_decline",
            "biggest_jump",
            "most_declined"
        }

        if story_type not in valid_story_types:

            print(
                f"⚠️ Unknown story type: "
                f"{story_type}"
            )

            story_type = (
                "fastest_growth"
            )

        # -----------------------------------------------------
        # Get actual countries
        # -----------------------------------------------------

        real_countries = (
            cls.get_real_countries()
        )

        if not real_countries:

            return pd.DataFrame()

        # -----------------------------------------------------
        # Determine years
        # -----------------------------------------------------

        end_year = 2025

        start_year = (
            end_year
            - years
            + 1
        )

        # -----------------------------------------------------
        # Fetch data with fallback
        # -----------------------------------------------------

        raw_data = (
            cls._fetch_with_fallback(
                indicator_code,
                start_year,
                end_year,
                real_countries
            )
        )

        if not raw_data:

            print(
                "❌ No World Bank "
                "records returned."
            )

            return pd.DataFrame()

        # -----------------------------------------------------
        # Build clean dataframe
        # -----------------------------------------------------

        df = cls._build_dataframe(
            raw_data,
            real_countries
        )

        if df.empty:

            print(
                "❌ No valid country "
                "data after filtering."
            )

            return pd.DataFrame()

        # -----------------------------------------------------
        # Keep requested years
        # -----------------------------------------------------

        available_years = [
            year
            for year in df.columns
            if (
                start_year
                <= year
                <= end_year
            )
        ]

        available_years = sorted(
            available_years
        )

        if len(
            available_years
        ) < 5:

            print(
                "❌ Not enough years "
                "available."
            )

            return pd.DataFrame()

        df = df[
            available_years
        ]

        # -----------------------------------------------------
        # Require enough observations
        # -----------------------------------------------------

        min_required_years = max(
            5,
            int(
                len(
                    available_years
                )
                * 0.60
            )
        )

        df = df.dropna(
            thresh=min_required_years
        )

        if df.empty:

            print(
                "❌ No countries have "
                "enough data."
            )

            return pd.DataFrame()

        # -----------------------------------------------------
        # Rank countries
        # -----------------------------------------------------

        ranking = (
            cls._rank_countries(
                df,
                story_type
            )
        )

        if not ranking:

            print(
                "❌ Could not calculate "
                "story ranking."
            )

            return pd.DataFrame()

        # -----------------------------------------------------
        # OPTIONAL COUNTRY CONSTRAINT ("required + context")
        #
        # `countries` carries countries a user explicitly asked
        # for ("India", "usa", "United Kingdom", ISO2/ISO3...).
        # Every requested country WITH usable data is guaranteed
        # a slot; remaining slots up to min_countries are filled
        # with the next-highest-ranked countries via the SAME
        # story ranking, so a 2-country request still yields a
        # visually populated frame.  Requested countries count
        # toward the min_countries gate (never relaxed below).
        # -----------------------------------------------------

        requested_codes = None

        if countries:

            matched_pairs, unmatched_tokens = (
                match_country_request(
                    countries,
                    real_countries.items()
                )
            )

            for token in unmatched_tokens:

                print(
                    f"⚠️ Requested country "
                    f"'{token}' not recognized "
                    "for this dataset; ignoring it."
                )

            if matched_pairs:

                requested_codes = [
                    code
                    for code, _name
                    in matched_pairs
                ]

            else:

                print(
                    "⚠️ None of the requested "
                    "countries matched; "
                    "fetching unrestricted."
                )

        if requested_codes:

            ranked_codes = [
                item["country_code"]
                for item in ranking
            ]

            selected_codes, missing_required = (
                select_required_plus_context(
                    ranked_codes,
                    requested_codes,
                    min_countries
                )
            )

            for code in missing_required:

                print(
                    f"⚠️ Requested country "
                    f"'{real_countries.get(code, code)}' "
                    "has no usable data for this "
                    "indicator; skipping it."
                )

            print(
                "🎯 Country constraint: required "
                f"[{', '.join(requested_codes)}] + "
                "context fill."
            )

        else:

            selected_codes = [
                item["country_code"]
                for item in ranking[
                    :max(
                        min_countries * 3,
                        24
                    )
                ]
            ]

        candidate = df[
            df.index.get_level_values(
                "country_code"
            ).isin(
                selected_codes
            )
        ].copy()

        # -----------------------------------------------------
        # Candidate ranking
        # -----------------------------------------------------

        candidate_ranking = (
            cls._rank_countries(
                candidate,
                story_type
            )
        )

        if not candidate_ranking:

            return pd.DataFrame()

        if requested_codes:

            # The constrained selection is already exactly
            # sized (required + context); ranking only fixes
            # the visual order.

            final_codes = [
                item["country_code"]
                for item in candidate_ranking
            ]

        else:

            final_codes = [
                item["country_code"]
                for item in candidate_ranking[
                    :min_countries
                ]
            ]

        selected = candidate[
            candidate.index.get_level_values(
                "country_code"
            ).isin(
                final_codes
            )
        ].copy()

        # -----------------------------------------------------
        # Sort according to story ranking
        # -----------------------------------------------------

        order = {
            item["country_code"]:
                position

            for position, item
            in enumerate(
                candidate_ranking
            )
        }

        selected = selected.assign(
            _story_order=[
                order.get(
                    code,
                    999
                )
                for code in
                selected.index.get_level_values(
                    "country_code"
                )
            ]
        )

        selected = (
            selected.sort_values(
                "_story_order"
            )
        )

        selected = (
            selected.drop(
                columns="_story_order"
            )
        )

        # -----------------------------------------------------
        # Ensure enough countries
        # -----------------------------------------------------

        if len(selected) < min_countries:

            print(
                f"❌ Only "
                f"{len(selected)} "
                f"usable countries found."
            )

            return pd.DataFrame()

        # -----------------------------------------------------
        # Visual quality
        # -----------------------------------------------------

        quality = (
            cls._visual_quality(
                selected,
                story_type
            )
        )

        print(
            "\n📊 STORY DATA QUALITY"
        )

        print(
            f"Story type: "
            f"{story_type}"
        )

        print(
            f"Score: "
            f"{quality['score']}/100"
        )

        print(
            f"Story spread: "
            f"{quality['spread']}"
        )

        print(
            f"Similar bars: "
            f"{quality['similar_bars']}%"
        )

        print(
            f"Average gap: "
            f"{quality['average_gap']}"
        )

        # -----------------------------------------------------
        # Reject extremely poor datasets
        # -----------------------------------------------------

        if quality["score"] < 20:

            print(
                "\n⚠️ DATASET REJECTED"
            )

            print(
                "Reason: "
                "The selected countries do "
                "not produce enough "
                "visual separation."
            )

            print(
                "The actual World Bank "
                "data will NOT be modified."
            )

            return pd.DataFrame()

        print(
            "\n✅ World Bank data accepted."
        )

        print(
            f"Countries: "
            f"{len(selected)}"
        )

        print(
            f"Years: "
            f"{selected.columns[0]} "
            f"→ "
            f"{selected.columns[-1]}"
        )

        print(
            f"Visual score: "
            f"{quality['score']}/100"
        )

        # -----------------------------------------------------
        # Metadata
        # -----------------------------------------------------

        selected.attrs[
            "story_type"
        ] = story_type

        selected.attrs[
            "indicator_code"
        ] = indicator_code

        selected.attrs[
            "quality_score"
        ] = quality["score"]

        selected.attrs[
            "story_quality"
        ] = quality

        return selected