"""
USGS earthquake provider -- country-year earthquake statistics.

Fetches the USGS FDSN event API (earthquake.usgs.gov/fdsnws/event/,
keyless, GeoJSON) and aggregates individual EVENTS into the standard
country-year wide_data shape the pipeline expects.

CONTENT POLICY (honesty framing, see FRAMING_CONSTRAINTS in app/ai/
script.py and the tier notes there):

- ONLY magnitude 6.0+ events are counted.  Smaller quakes are
  detected unevenly across regions (dense networks in Japan/US vs
  sparse ocean-floor monitoring), so raw low-magnitude counts are
  NOT a fair cross-country comparison.  The M6+ threshold trades
  quantity for comparability.
- Country attribution comes from the USGS "place" string when it
  names a country (comma-trailing token); otherwise the event's
  epicenter is matched against a compact coastal-gazetteer of
  seismic regions and attributed to the NEAREST coastline country.
  Genuinely mid-ocean / unattributable events are bucketed honestly
  under "International waters" -- never force-fit to a country.
- Counts are "M6+ earthquakes recorded by USGS in the instrumental
  era" -- never "the most earthquake-prone country" as an absolute
  claim.
"""

import re

import time

from datetime import datetime, timezone

from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

from app.countries import (
    display_name as _country_display,
    lookup as _country_lookup,
)

from app.data.providers.base import (
    DataProvider,
    DataProviderResult,
    IndicatorInfo,
    match_country_request,
    normalize_long_data,
    select_required_plus_context,
    to_visual_dataframe,
)


class USGSEarthquakeProvider(DataProvider):

    provider_id = "usgs"
    provider_name = "U.S. Geological Survey"

    request_timeout = 90

    # Cross-country comparability floor (see module docstring).
    MIN_MAGNITUDE = 6.0

    # GeoJSON page size + paging safety cap (M6+ for 15 years is
    # ~8k events; the cap only guards a pathological request).
    PAGE_SIZE = 20000
    MAX_PAGES = 5

    # Attribution radius for the coastal gazetteer: an epicenter
    # farther than this from every anchor is "International waters".
    GAZETTEER_MAX_KM = 650

    INDICATORS: Dict[str, Dict] = {
        "earthquake_count_m6": {
            "name": "Magnitude-6+ Earthquakes Recorded by USGS",
            "category": "Environment",
            "aggregate": "count",
        },
        "earthquake_max_magnitude": {
            "name": "Strongest Magnitude-6+ Earthquake (USGS)",
            "category": "Environment",
            "aggregate": "max",
        },
    }

    @classmethod
    def list_indicators(cls) -> List[IndicatorInfo]:

        return [
            IndicatorInfo(
                code=code,
                name=config["name"],
                category=config.get("category", ""),
                source_url=(
                    "https://earthquake.usgs.gov/fdsnws/event/1/"
                ),
            )
            for code, config
            in cls.INDICATORS.items()
        ]

    # ---------------------------------------------------------
    # HTTP layer
    # ---------------------------------------------------------

    @classmethod
    def _query_url(
        cls,
        start_year: int,
        end_year: int,
        offset: int,
    ) -> str:

        return (
            "https://earthquake.usgs.gov/fdsnws/event/1/query"
            f"?format=geojson&starttime={start_year}-01-01"
            f"&endtime={end_year + 1}-01-01"
            f"&minmagnitude={cls.MIN_MAGNITUDE}"
            f"&orderby=time-asc&limit={cls.PAGE_SIZE}"
            f"&offset={offset}"
        )

    @classmethod
    def _fetch_events(
        cls,
        years: int,
    ) -> List[dict]:

        end_year = datetime.now(
            timezone.utc
        ).year

        start_year = end_year - max(3, int(years)) + 1

        events: List[dict] = []

        seen_ids = set()

        for page in range(1, cls.MAX_PAGES + 1):

            # FDSN `offset` is a 1-based RECORD offset, not a page
            # number: page 2 with limit=20000 must start at record
            # 20001.  (Passing offset=2 would re-fetch page 1.)
            offset = 1 + (page - 1) * cls.PAGE_SIZE

            url = cls._query_url(
                start_year,
                end_year,
                offset=offset,
            )

            features: List[dict] = []

            # Defensive retry: transient network/DNS failures get
            # 3 attempts with linear backoff, matching the
            # provider layer's graceful-degradation pattern.
            for attempt in range(1, 4):

                try:

                    response = requests.get(
                        url,
                        timeout=cls.request_timeout,
                        headers={
                            "User-Agent":
                                "MetricForge-USGSEarthquakeProvider/1.0"
                        },
                    )

                    response.raise_for_status()

                    features = (
                        response.json().get("features", [])
                    )

                    break

                except (
                    requests.RequestException,
                    ValueError,
                ) as error:

                    if attempt == 3:

                        raise

                    print(
                        f"  [USGS] Request attempt "
                        f"{attempt} failed "
                        f"({type(error).__name__}); retrying..."
                    )

                    time.sleep(2 * attempt)

            for feature in features:

                event_id = feature.get("id")

                if event_id in seen_ids:
                    continue

                seen_ids.add(event_id)

                events.append(feature)

            if len(features) < cls.PAGE_SIZE:
                break

        return events

    # ---------------------------------------------------------
    # ATTRIBUTION LAYER -- part 1: place-string parsing
    #
    # USGS "place" strings come in several shapes:
    #   "24 km WNW of Port-Vila, Vanuatu"      -> trailing country
    #   "2024 Hyuganada Sea, Japan Earthquake" -> legacy title with
    #                                             an " Earthquake" suffix
    #   "central Alaska" / "Hawaii"            -> US sub-region, no
    #                                             country token
    #   "Kuril Islands"                        -> region only
    # ---------------------------------------------------------

    # Trailing comma segment: last ", <token>" in the string.
    _PLACE_TAIL_RE = re.compile(r",\s*([^,]+?)\s*$")

    # Legacy USGS titles end with " Earthquake"/" Earthquakes".
    _TITLE_SUFFIX_RE = re.compile(
        r"\s+Earthquakes?\s*$",
        re.IGNORECASE,
    )

    # Unambiguous sub-national regions of one country.  USGS uses
    # state/region names for US events (and a few territories), so
    # the trailing token is rarely "United States" directly.
    _SUBREGION_TO_ISO2 = {
        "alaska": "US", "hawaii": "US", "california": "US",
        "nevada": "US", "oregon": "US", "washington": "US",
        "idaho": "US", "montana": "US", "wyoming": "US",
        "utah": "US", "arizona": "US", "new mexico": "US",
        "texas": "US", "oklahoma": "US", "arkansas": "US",
        "missouri": "US", "tennessee": "US", "kentucky": "US",
        "virginia": "US", "west virginia": "US", "maine": "US",
        "kodiak island region": "US",
        "andreanof islands aleutians": "US",
        "rat islands aleutians": "US",
        "fox islands aleutians": "US",
        "andreanof islands": "US", "rat islands": "US",
        "fox islands": "US", "aleutian islands": "US",
        "puerto rico": "PR", "virgin islands": "US",
        "guam": "GU", "american samoa": "AS",
        "northern mariana islands": "MP",
        "svalbard": "NO", "jan mayen": "NO",
        "greenland": "GL", "faroe islands": "DK",
        "new caledonia": "NC", "french polynesia": "PF",
        "santa cruz islands": "SB", "new britain region": "PG",
        "new ireland region": "PG",
        "bougainville region": "PG",
        "mindanao": "PH", "luzon": "PH",
        "sumatra": "ID", "java": "ID",
        "molucca sea": "ID", "banda sea": "ID",
        "hokkaido": "JP", "ryukyu islands": "JP",
        "bonin islands": "JP", "volcano islands": "JP",
        "taiwan region": "TW", "crete": "GR",
        "dodecanese islands": "GR", "dodecanese": "GR",
        "sulawesi": "ID", "kalimantan": "ID",
        "kamchatka": "RU", "kuril islands": "RU",
        "sakhalin": "RU", "chukotka": "RU",
        "hindu kush region": "AF", "xizang": "CN",
        "qinghai": "CN", "sichuan": "CN", "yunnan": "CN",
        "xinjiang": "CN", "gansu": "CN",
        "south of fiji islands": "FJ", "fiji region": "FJ",
        "kermadec islands": "NZ",
        "north island of new zealand": "NZ",
        "south island of new zealand": "NZ",
        "macquarie island": "AU", "heard island": "AU",
        "vanuatu region": "VU", "tonga region": "TO",
        "samoa islands": "WS", "nicobar islands": "IN",
        "andaman islands": "IN", "assam": "IN",
        "azores islands": "PT", "azores": "PT",
        "canary islands": "ES", "balearic islands": "ES",
        "sicily": "IT", "sardinia": "IT",
        "tyrrhenian sea": "IT", "santa cruz": "SB",
    }

    @classmethod
    def _country_from_place(
        cls,
        place,
    ) -> Optional[str]:

        text = str(place or "").strip()

        if not text:
            return None

        text = cls._TITLE_SUFFIX_RE.sub(
            "",
            text,
        )

        candidates = []

        tail_match = cls._PLACE_TAIL_RE.search(
            text
        )

        if tail_match:
            candidates.append(
                tail_match.group(1)
            )

        # Whole-string regions ("Kuril Islands",
        # "central Alaska", "Hawaii").
        candidates.append(text)

        for token in candidates:

            token = token.strip()

            if not token:
                continue

            sub_iso2 = cls._SUBREGION_TO_ISO2.get(
                token.lower()
            )

            if sub_iso2:
                return sub_iso2

            entry = _country_lookup(token)

            if entry:
                return str(
                    entry["iso2"]
                ).upper()

        return None

    # ---------------------------------------------------------
    # ATTRIBUTION LAYER -- part 2: coastal gazetteer
    #
    # Epicenters with no country in the place string (open-ocean
    # trench systems, ridges) are matched to the NEAREST seismic
    # coastline anchor within GAZETTEER_MAX_KM.  Events beyond
    # every anchor are bucketed as international waters -- never
    # force-fit to a country.
    # ---------------------------------------------------------

    # (lat, lon, iso2) seismic-coastline anchors, one per major
    # subduction zone / ridge segment.
    _GAZETTEER = (
        # Western Pacific
        (36.0, 142.0, "JP"),   # Japan trench
        (32.0, 140.5, "JP"),   # Izu-Bonin
        (44.5, 148.5, "RU"),   # Kuril chain
        (53.0, 159.5, "RU"),   # Kamchatka
        (52.0, 171.5, "US"),   # Western Aleutians
        (46.0, 153.5, "RU"),   # NW Kuril basin
        (23.5, 122.5, "TW"),   # Taiwan trench
        (13.0, 128.0, "PH"),   # Luzon east
        (7.0, 127.0, "PH"),    # Mindanao east
        (13.5, 145.5, "GU"),   # Mariana
        (2.5, 128.0, "ID"),    # Halmahera / Molucca
        (-6.5, 130.5, "ID"),   # Banda Sea
        (-2.5, 140.0, "ID"),   # Papua north
        (-4.0, 132.0, "ID"),   # Seram
        (-5.5, 110.0, "ID"),   # North Java
        (-9.5, 108.0, "ID"),   # South Java
        (0.5, 99.0, "ID"),     # Sumatra west-equator
        (-3.5, 100.5, "ID"),   # Southern Sumatra
        (16.0, 94.5, "MM"),    # Myanmar / Andaman
        (10.5, 93.5, "IN"),    # Nicobar
        (-6.0, 155.0, "SB"),   # Solomon
        (-4.5, 154.0, "PG"),   # New Britain
        (-6.0, 148.0, "PG"),   # New Guinea north
        (-15.5, 167.5, "VU"),  # Vanuatu
        (-19.5, 173.5, "TO"),  # Tonga
        (-17.5, 179.5, "FJ"),  # Fiji
        (-30.5, -177.5, "NZ"), # Kermadec
        (-38.5, 177.5, "NZ"),  # Hikurangi
        (-51.5, 161.5, "NZ"),  # Puysegur
        (-24.5, 180.0, "FJ"),  # Fiji west
        # Americas
        (53.5, -163.5, "US"),  # Alaska Peninsula
        (38.5, -124.0, "US"),  # Cape Mendocino
        (33.5, -118.5, "US"),  # SoCal borderland
        (19.5, -155.0, "US"),  # Hawaii
        (17.0, -100.5, "MX"),  # Guerrero coast
        (16.0, -94.5, "MX"),   # Oaxaca
        (13.5, -91.5, "GT"),   # Guatemala coast
        (12.0, -87.5, "NI"),   # Nicaragua
        (9.5, -84.5, "CR"),    # Costa Rica
        (8.0, -79.0, "PA"),    # Panama
        (2.5, -82.0, "CO"),    # Colombia coast
        (-6.0, -81.5, "PE"),   # North Peru
        (-16.5, -73.0, "PE"),  # Central Peru
        (-23.0, -70.5, "CL"),  # North Chile
        (-33.5, -72.5, "CL"),  # Central Chile
        (-38.5, -74.5, "CL"),  # South-central Chile
        (-45.0, -75.5, "CL"),  # South Chile
        (-42.5, -64.5, "AR"),  # Argentina Atlantic
        (10.5, -67.0, "VE"),   # Venezuela coast
        (19.0, -68.5, "DO"),   # Hispaniola
        (18.5, -66.5, "PR"),   # Puerto Rico trench
        (15.5, -61.5, "DM"),   # Lesser Antilles
        (41.0, -65.5, "US"),   # New England seamounts
    )

    # Atlantic / Arctic / Mediterranean / Asia / Indian Ocean /
    # Africa segments of the gazetteer (continued).
    _GAZETTEER += (
        (64.0, -19.0, "IS"),   # Iceland
        (38.0, -30.0, "PT"),   # Azores
        (35.8, -7.0, "MA"),    # Gibraltar
        (54.5, -3.0, "GB"),    # Irish Sea / North Sea
        (71.0, -8.0, "NO"),    # Norwegian Sea
        (76.0, 7.0, "NO"),     # Svalbard
        (38.0, 15.5, "IT"),    # Sicily / Calabria
        (42.0, 14.5, "IT"),    # Central Apennines
        (37.5, 21.5, "GR"),    # West Greece
        (36.5, 26.5, "GR"),    # Dodecanese
        (35.5, 24.5, "GR"),    # Crete
        (38.5, 26.5, "TR"),    # Aegean
        (38.5, 39.5, "TR"),    # East Anatolia
        (38.5, 44.5, "TR"),    # Van / Iran border
        (28.0, 56.5, "IR"),    # SE Iran
        (35.5, 47.5, "IQ"),    # Zagros north
        (28.5, 62.5, "IR"),    # Iran-Pakistan border
        (36.5, 71.0, "AF"),    # Hindu Kush
        (34.5, 69.5, "AF"),    # Afghanistan
        (28.0, 84.5, "NP"),    # Nepal
        (30.0, 95.0, "CN"),    # Eastern Tibet
        (35.5, 92.5, "CN"),    # Kunlun
        (39.5, 75.0, "KG"),    # Tien Shan
        (43.0, 78.0, "KZ"),    # North Tien Shan
        (52.5, 105.5, "RU"),   # Baikal
        (43.0, 111.5, "MN"),   # Mongolia
        (-8.5, 118.5, "ID"),   # Lombok / Bali
        (-19.5, 168.5, "VU"),  # South Vanuatu
        (-33.5, 178.5, "NZ"),  # South Fiji basin
        (-6.5, 77.5, "LK"),    # Sri Lanka
        (-38.0, 46.5, "AU"),   # SW Australia
        (-13.5, 112.5, "AU"),  # West Australia
        (-54.5, 159.0, "AU"),  # Macquarie
        (-32.0, 57.5, "AU"),   # Australia SW
        (15.0, 41.5, "ER"),    # Eritrea / Red Sea
        (12.5, 43.5, "YE"),    # Gulf of Aden
        (11.5, 39.0, "ET"),    # Ethiopia rift
        (-2.5, 29.0, "RW"),    # Kivu rift
        (-6.5, 30.5, "TZ"),    # Tanzania rift
        (33.5, -5.5, "MA"),    # Morocco
        (37.0, 3.5, "DZ"),     # Algeria tell
        (36.0, 10.5, "TN"),    # Tunisia
        (25.0, 35.5, "EG"),    # Red Sea Egypt
        (12.5, -72.0, "CO"),   # Colombia-Caribbean
        (10.5, -75.5, "CO"),   # Cartagena
    )

    @staticmethod
    def _haversine_km(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:

        import math

        radius = 6371.0

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)

        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(d_phi / 2) ** 2
            + math.cos(phi1)
            * math.cos(phi2)
            * math.sin(d_lambda / 2) ** 2
        )

        return 2 * radius * math.asin(
            math.sqrt(a)
        )

    @classmethod
    def _country_from_coords(
        cls,
        lat: float,
        lon: float,
    ) -> Optional[str]:

        best_iso2 = None

        best_km = cls.GAZETTEER_MAX_KM

        for anchor_lat, anchor_lon, iso2 in (
            cls._GAZETTEER
        ):

            distance = cls._haversine_km(
                lat,
                lon,
                anchor_lat,
                anchor_lon,
            )

            if distance < best_km:

                best_km = distance
                best_iso2 = iso2

        return best_iso2

    # ---------------------------------------------------------
    # EVENT ATTRIBUTION
    # ---------------------------------------------------------

    @classmethod
    def _attribute_event(
        cls,
        properties: dict,
        geometry: Optional[dict],
    ):

        iso2 = cls._country_from_place(
            properties.get("place")
        )

        if iso2:
            return iso2, "place"

        coordinates = (geometry or {}).get(
            "coordinates",
            [],
        )

        if len(coordinates) >= 2:

            longitude = coordinates[0]
            latitude = coordinates[1]

            iso2 = cls._country_from_coords(
                latitude,
                longitude,
            )

            if iso2:
                return iso2, "gazetteer"

        return None, "international"

    # ---------------------------------------------------------
    # AGGREGATION: events -> country-year rows
    #
    # normalize_long_data dedupes on (country_code, year, metric),
    # so aggregation MUST collapse to exactly one value per
    # country-year BEFORE normalization.
    #
    # - count  (earthquake_count_m6): a year with no M6+ quake is a
    #   REAL ZERO, not missing data, so absent years are filled
    #   with 0.0 -- this keeps the series dense and story-compatible.
    # - max    (earthquake_max_magnitude): a year with no M6+ quake
    #   has NO magnitude value, so absent years stay NaN (filling
    #   with 0 would fabricate data).
    #
    # Events that cannot be attributed to any country (mid-ocean,
    # beyond every gazetteer anchor) are EXCLUDED from the country
    # table -- never force-fit -- and their share is logged.
    # ---------------------------------------------------------

    # Territory/region ISO2 codes app.countries does not carry
    # (display_name() returns None for them).
    _FALLBACK_NAMES = {
        "AS": "American Samoa",
        "DM": "Dominica",
        "ER": "Eritrea",
        "GL": "Greenland",
        "GU": "Guam",
        "LK": "Sri Lanka",
        "MP": "Northern Mariana Islands",
        "PF": "French Polynesia",
        "RW": "Rwanda",
        "YE": "Yemen",
    }

    @classmethod
    def _display_name_for(
        cls,
        iso2: str,
    ) -> str:

        name = _country_display(iso2)

        if name:
            return name

        return cls._FALLBACK_NAMES.get(
            iso2,
            iso2,
        )

    # ---------------------------------------------------------
    # STORY RANKING -- generic copies of the shared wide-data
    # story score + top-N selection (same semantics as the OWID
    # provider's private helpers: drop sparse rows, score each
    # country's series for the requested story type, rank, and
    # apply the optional "required + context" country
    # constraint).  Copied rather than imported so each provider
    # stays self-contained and the OWID path is untouched
    # (add-only rule).
    # ---------------------------------------------------------

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

        # OPTIONAL COUNTRY CONSTRAINT ("required + context")
        # Requested countries with usable data are guaranteed a
        # slot; the rest is filled up to min_countries from the
        # story ranking. Missing/unrecognized countries are
        # logged and skipped -- never a hard failure.
        if countries:

            required_keys, unmatched_tokens = (
                match_country_request(
                    countries,
                    scored_keys
                )
            )

            for token in unmatched_tokens:

                print(
                    f"  [USGS] Requested country "
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
                    f"  [USGS] Requested country "
                    f"'{key[1]}' has no usable data; "
                    "skipping it."
                )

            if required_keys:

                print(
                    "  [USGS] Country constraint: "
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

    # ---------------------------------------------------------
    # AGGREGATION: events -> country-year long rows
    #
    # normalize_long_data dedupes on (country_code, year, metric),
    # so aggregation MUST collapse to exactly one value per
    # country-year BEFORE normalization.
    #
    # - count  (earthquake_count_m6): a year with no M6+ quake is
    #   a REAL ZERO, not missing data, so absent years in the
    #   event window are filled with 0.0 -- a dense series keeps
    #   the story types honest (a decline to zero must show).
    # - max    (earthquake_max_magnitude): a year with no M6+ quake
    #   has NO magnitude value, so absent years stay absent
    #   (filling with 0 would fabricate data).
    #
    # Events that cannot be attributed to any country (mid-ocean,
    # beyond every gazetteer anchor) are counted and logged, but
    # EXCLUDED from the country table -- never force-fit.
    # ---------------------------------------------------------

    @classmethod
    def _aggregate_events(
        cls,
        events: List[dict],
        indicator_code: str,
        config: Dict,
    ) -> Tuple[List[dict], Dict, List[int]]:

        aggregate = config["aggregate"]

        metric = config["name"]

        count_table: Dict[
            Tuple[str, int], int
        ] = {}

        max_table: Dict[
            Tuple[str, int], float
        ] = {}

        attribution_stats = {
            "place": 0,
            "gazetteer": 0,
            "international": 0,
        }

        attributed = set()

        years_seen = set()

        skipped_no_mag = 0

        for feature in events:

            properties = (
                feature.get("properties")
                or {}
            )

            magnitude = (
                properties.get("mag")
            )

            if (
                magnitude is None
                or float(magnitude)
                < cls.MIN_MAGNITUDE
            ):
                skipped_no_mag += 1

                continue

            event_time = (
                properties.get("time")
            )

            if event_time is None:

                continue

            try:

                year = datetime.fromtimestamp(
                    event_time / 1000.0,
                    tz=timezone.utc,
                ).year

            except (
                ValueError,
                OSError,
                OverflowError,
            ):

                continue

            years_seen.add(year)

            iso2, how = (
                cls._attribute_event(
                    properties,
                    feature.get("geometry"),
                )
            )

            attribution_stats[how] = (
                attribution_stats.get(how, 0) + 1
            )

            if iso2 is None:

                # Genuinely unattributable (mid-ocean,
                # beyond every anchor): honestly
                # excluded from the country table.
                continue

            key = (iso2, year)

            attributed.add(iso2)

            if aggregate == "count":

                count_table[key] = (
                    count_table.get(key, 0) + 1
                )

            else:

                magnitude = float(magnitude)

                if (
                    key not in max_table
                    or magnitude
                    > max_table[key]
                ):
                    max_table[key] = magnitude

        # Count fills absent country-years in the event
        # window with a REAL ZERO (a year without an M6+
        # quake is data, not missingness).
        if aggregate == "count":

            span = range(
                min(years_seen),
                max(years_seen) + 1,
            )

            for iso2 in attributed:

                for year in span:

                    key = (iso2, year)

                    if key in count_table:

                        continue

                    count_table[key] = 0

        table = (
            count_table
            if aggregate == "count"
            else max_table
        )

        rows = []

        for (
            (iso2, year),
            value
        ) in table.items():

            rows.append(
                {
                    "country": (
                        cls._display_name_for(iso2)
                    ),
                    "country_code": iso2,
                    "year": int(year),
                    "metric": metric,
                    "value": float(value),
                    "provider": cls.provider_id,
                    "source_name": cls.provider_name,
                    "source_url": (
                        "https://earthquake.usgs.gov/"
                        "fdsnws/event/1/"
                    ),
                    "indicator_code": indicator_code,
                }
            )

        international_share = (
            attribution_stats["international"]
            / max(1, len(events))
            * 100.0
        )

        print(
            f"  [USGS] {len(events)} M{cls.MIN_MAGNITUDE}+ "
            f"events -> {len(attributed)} countries, "
            f"{len(table)} country-year rows "
            f"({aggregate} aggregation)."
        )

        print(
            f"  [USGS] Attribution: "
            f"{attribution_stats['place']} via place "
            f"string, {attribution_stats['gazetteer']} "
            f"via coastal gazetteer, "
            f"{attribution_stats['international']} "
            f"unattributable "
            f"({international_share:.1f}%) -> "
            "excluded (never force-fit)."
        )

        if skipped_no_mag:

            print(
                f"  [USGS] {skipped_no_mag} events "
                "below the magnitude floor skipped."
            )

        return (
            rows,
            attribution_stats,
            sorted(years_seen),
        )

    @classmethod
    def fetch_normalized(
        cls,
        indicator_code: str,
        years: int = 15,
        story_type: str = "fastest_growth",
        min_countries: int = 8,
        countries=None
    ) -> DataProviderResult:

        config = cls.INDICATORS.get(
            indicator_code
        )

        if config is None:

            raise ValueError(
                "Unknown USGS indicator: "
                f"'{indicator_code}'."
            )

        events = cls._fetch_events(
            years
        )

        if not events:

            raise ValueError(
                "USGS returned no events for the "
                f"{years}-year window."
            )

        rows, attribution_stats, event_years = (
            cls._aggregate_events(
                events,
                indicator_code,
                config,
            )
        )

        if not rows:

            raise ValueError(
                "USGS events could not be attributed "
                "to any country in this window."
            )

        source_url = (
            "https://earthquake.usgs.gov/"
            "fdsnws/event/1/"
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
            "usgs_min_magnitude": cls.MIN_MAGNITUDE,
            "usgs_event_window": [
                min(event_years),
                max(event_years),
            ],
            "usgs_attribution": attribution_stats,
            "framing": (
                "Magnitude-6+ events only (lower "
                "magnitudes are detected unevenly "
                "across regions); offshore events "
                "attributed to the nearest coastline "
                "country; mid-ocean events excluded."
            ),
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
                "USGS aggregation did not retain "
                "enough attributable countries after "
                f"filtering (got {len(wide_data)}, "
                f"need {min_countries})."
            )

        print(
            "USGS data accepted: "
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
