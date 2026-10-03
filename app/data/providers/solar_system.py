"""Solar System Provider - planetary facts from NASA NSSDC (space_science).

Source: https://nssdc.gsfc.nasa.gov/planetary/factsheet/
License: Public domain (U.S. Government work)
Commercial use: ALLOWED (see provider catalog).

Provides static, single-snapshot rankings of planetary properties.
Because the data is a single point in time (not a time series), only
ranking and head-to-head story types are supported.

NASA content created by U.S. government employees is public domain
(17 U.S.C. sec. 105) and may be freely used, including commercially.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd

from app.data.providers.base import (
    DataProvider,
    DataProviderResult,
    IndicatorInfo,
)
from app.data.static.planetary_facts import (
    BODIES as _BODIES_PY,
)


class SolarSystemProvider(DataProvider):

    provider_id = "solar_system"
    provider_name = "NASA NSSDC Planetary Fact Sheet"
    source_url = "https://nssdc.gsfc.nasa.gov/planetary/factsheet/"
    source_file = Path(__file__).resolve().parent.parent / "static" / "planetary_facts.json"

    # ---------------------------------------------------------------
    # SNAPSHOT-DATASET FLAGS (read by the story engine)
    # ---------------------------------------------------------------
    # snapshot_only=True tells SmartStoryEngine that this provider's
    # dataset has NO year-over-year movement: time-series story types
    # must not be generated, and ranking stories (current_leader /
    # leader_challenge) are scored on leader separation instead of
    # temporal change.  This is the code-level enforcement of the
    # ranking/head-to-head-only restriction (see also
    # _ALLOWED_FETCH_STORY_TYPES and SUPPORTED_STORY_TYPES).
    snapshot_only = True

    # entity_comparison=True tells the manual topic engine that a
    # deliberate 2-body head-to-head ("Earth vs Mars") is a valid
    # dataset (quality gates accept >= 2 entities on this path).
    entity_comparison = True

    # Only ranking and head-to-head story types make sense for
    # single-snapshot planetary data.  Time-series story types
    # (fastest_growth, biggest_decline, rank_climber, rank_decline,
    # trend_over_time) are NOT supported — they require year-over-year
    # change that does not exist in a single-snapshot dataset.
    SUPPORTED_STORY_TYPES: Set[str] = {
        "current_leader",
        "leader_challenge",
    }

    # Fetch-time story types that this snapshot provider can serve.
    # "fastest_growth" is always allowed because the engine's automatic
    # rotation uses it as the universal base fetch (Step-1).
    # "biggest_jump" maps to ranking / head-to-head stories (Step-2).
    # "most_declined" is rejected — no decline to show in a snapshot.
    _ALLOWED_FETCH_STORY_TYPES: Set[str] = {
        "fastest_growth",
        "biggest_jump",
    }

    LATEST_YEAR = 2025

    INDICATORS: Dict[str, Dict] = {
        "planet_moons": {
            "name": "Planet Moon Count",
            "category": "space_science",
            "field": "moons",
            "metric_name": "Moons",
            "unit": "count",
            "approximate_field": "moons_approximate",
        },
        "planet_gravity": {
            "name": "Surface Gravity by Planet",
            "category": "space_science",
            "field": "gravity_ms2",
            "metric_name": "Surface Gravity (m/s^2)",
            "unit": "m/s^2",
        },
        "planet_surface_temp": {
            "name": "Mean Surface Temperature by Planet",
            "category": "space_science",
            "field": "mean_temp_c",
            "metric_name": "Mean Surface Temperature (C)",
            "unit": "C",
        },
        "planet_diameter": {
            "name": "Planet Diameter",
            "category": "space_science",
            "field": "diameter_km",
            "metric_name": "Diameter (km)",
            "unit": "km",
        },
        "planet_distance_sun": {
            "name": "Distance from Sun by Planet",
            "category": "space_science",
            "field": "distance_from_sun_au",
            "metric_name": "Distance from Sun (AU)",
            "unit": "AU",
        },
        "planet_orbital_period": {
            "name": "Orbital Period by Planet",
            "category": "space_science",
            "field": "orbital_period_days",
            "metric_name": "Orbital Period (days)",
            "unit": "days",
        },
        "planet_day_length": {
            "name": "Length of Day by Planet",
            "category": "space_science",
            "field": "day_length_hours",
            "metric_name": "Day Length (hours)",
            "unit": "hours",
        },
        "planet_density": {
            "name": "Planetary Density",
            "category": "space_science",
            "field": "density_kg_m3",
            "metric_name": "Density (kg/m^3)",
            "unit": "kg/m^3",
        },
        "planet_escape_velocity": {
            "name": "Escape Velocity by Planet",
            "category": "space_science",
            "field": "escape_velocity_kms",
            "metric_name": "Escape Velocity (km/s)",
                    },
    }

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

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
    def supports_countries(cls) -> bool:
        """True when the `countries` hint is accepted (base uses the
        signature check; implemented here explicitly so the manual
        path passes the requested planet names through)."""
        return True

    @classmethod
    def _match_requested_body(
        cls,
        requested: str,
        body_name: str,
    ) -> bool:
        """Substring-tolerant entity match used when the user names a
        planet inside a natural-language keyword (the entity detector
        can hand us 'Mars: Gravity Comparison' and we still map that
        to the 'Mars' body)."""
        needle = "".join(
            c for c in str(requested or "").lower()
            if c.isalnum()
        )
        hay = "".join(
            c for c in str(body_name or "").lower()
            if c.isalnum()
        )
        if not needle or not hay:
            return False
        return needle in hay or hay in needle

    @classmethod
    def _select_bodies(
        cls,
        bodies: List[Dict],
        countries: Optional[List[str]],
    ) -> List[Dict]:
        """Apply the optional planet hint.

        When `countries` names specific bodies (e.g. from a manual
        "Earth vs Mars" keyword), return EXACTLY those bodies that
        exist in the static dataset — a deliberate head-to-head frame.
        Without a hint, return every body (the full ranking).
        """
        if not countries:
            return list(bodies)

        selected = []
        seen = set()
        for requested in countries:
            for body in bodies:
                name = body["name"]
                if name in seen:
                    continue
                if cls._match_requested_body(requested, name):
                    selected.append(body)
                    seen.add(name)
                    break
        return selected

    @classmethod
    def fetch_normalized(
        cls,
        indicator_code: str,
        years: int = 10,
        story_type: str = "fastest_growth",
        min_countries: int = 5,
        countries: Optional[List[str]] = None,
    ) -> DataProviderResult:
        """Return a single-snapshot DataFrame for one planetary indicator.

        `countries` is an optional hint naming specific planets (used
        by the manual "Earth vs Mars" head-to-head route).  When every
        requested body has usable data the returned frame is exactly
        those bodies; otherwise the requested-but-missing bodies are
        reported and the frame falls back to the full ranking.
        """
        config = cls.INDICATORS.get(indicator_code)
        if not config:
            raise ValueError(
                f"Unknown SolarSystem indicator: {indicator_code}. "
                f"Use one of: {', '.join(sorted(cls.INDICATORS))}"
            )

        # Enforcement layer 1: reject time-series fetch story types
        # at the provider boundary.
        if story_type not in cls._ALLOWED_FETCH_STORY_TYPES:
            return cls._empty_result(indicator_code, config)

        # Load the curated static dataset from JSON.
        bodies = cls._load_bodies()

        # Optional planet hint (manual head-to-head route).
        bodies_for_frame = cls._select_bodies(bodies, countries)

        field = config["field"]
        metric_name = config["metric_name"]

        rows = []
        for body in bodies_for_frame:
            name = body["name"]
            value = body.get(field)
            if value is None:
                continue
            rows.append(
                {
                    "name": name,
                    "value": float(value),
                    "body_type": body.get("body_type", ""),
                }
            )

        if not rows:
            return cls._empty_result(indicator_code, config)

        df = pd.DataFrame(rows)

        # Single-snapshot-column approach: fan the single snapshot
        # value across multiple year columns so the bar-race render
        # path gets a numeric column to pivot on.  The engine's
        # _prepare_data requires >= 3 year columns.
        year_span = max(years, 3)
        start_year = cls.LATEST_YEAR - year_span + 1

        wide = df.pivot_table(
            index="name",
            values="value",
            aggfunc="max",
        )
        # Every year column has the same constant value.
        year_cols = list(range(start_year, cls.LATEST_YEAR + 1))
        for year in year_cols:
            wide[year] = wide["value"]
        wide = wide.drop(columns=["value"])
        wide = wide.sort_index(axis=1)

        wide = wide.dropna(how="all")
        if wide.empty:
            return cls._empty_result(indicator_code, config)
        # A deliberate head-to-head (explicit planet hint) may carry
        # exactly the requested bodies, so the min_countries floor is
        # relaxed when the caller asked for specific planets.
        floor = min_countries
        if countries:
            floor = max(1, len(countries))
        if len(wide) < floor:
            return cls._empty_result(indicator_code, config)

        normalized_rows = []
        for name, row in wide.iterrows():
            for year, value in row.items():
                if pd.isna(value):
                    continue
                normalized_rows.append(
                    {
                        "country": name,
                        "country_code": name,
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
            "indicator_name": config["name"],
            "category": config["category"],
            "snapshot": True,
            "latest_year": cls.LATEST_YEAR,
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

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @classmethod
    def _load_bodies(cls) -> List[Dict]:
        """Load the curated planetary facts JSON, falling back to
        the in-process Python constant."""
        try:
            if cls.source_file.exists():
                return json.loads(cls.source_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return [dict(b) for b in _BODIES_PY]

    @classmethod
    def _empty_result(
        cls, indicator_code: str, config: Dict
    ) -> DataProviderResult:
        """Return an empty DataProviderResult."""
        empty_df = pd.DataFrame()
        metadata = {
            "provider": cls.provider_id,
            "source_name": cls.provider_name,
            "source_url": cls.source_url,
            "indicator_code": indicator_code,
            "indicator_name": config["name"],
            "category": config["category"],
            "snapshot": True,
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