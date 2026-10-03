"""Static planetary facts derived from NASA's NSSDC Planetary Fact Sheet.

Values compiled from NASA's National Space Science Data Center
(NSSDC) Planetary Fact Sheet and companion sheets:

    https://nssdc.gsfc.nasa.gov/planetary/factsheet/

NASA content created by U.S. government employees is public domain
(17 U.S.C. sec. 105) and may be freely used, including commercially.

Values are intentionally stored as NASA-published figures; where a
quantity is quoted as a range (e.g. mean surface temperature of a
body with no atmosphere or extreme day/night swing), a single
representative NASA-quoted value is recorded here for chart display.
Moon counts reflect best-known counts at time of compilation and are
flagged `approximate=True` for bodies with unconfirmed small-moon
populations (Jupiter, Saturn, Uranus, Neptune).
"""

from typing import Dict, List

PROVIDER_ID = "solar_system"
SOURCE_NAME = "NASA NSSDC Planetary Fact Sheet"
SOURCE_URL = "https://nssdc.gsfc.nasa.gov/planetary/factsheet/"
LICENSE = "Public domain (U.S. Government work)"
LATEST_DATA_DATE = "2025"
HISTORICAL_COVERAGE = "Snapshot (latest values)"
F_PORTFOLIO_YEARS = 1  # snapshot providers only


class planet:
    """Canonical NASA planet name (keys used by story engine)."""

    MERCURY = "Mercury"
    VENUS = "Venus"
    EARTH = "Earth"
    MARS = "Mars"
    JUPITER = "Jupiter"
    SATURN = "Saturn"
    URANUS = "Uranus"
    NEPTUNE = "Neptune"


def _body(
    name: str,
    body_type: str,
    mass_kg: float,
    diameter_km: float,
    density_kg_m3: float,
    gravity_ms2: float,
    escape_vel_kms: float,
    mean_temp_k: float,
    mean_temp_c: float,
    dist_from_sun_au: float,
    dist_from_sun_mkm: float,
    orbital_period_days: float,
    orbital_period_earth_years: float,
    day_length_hours: float,
    moons: int,
    moons_approximate: bool,
    has_rings: bool,
    magnetic_field: str,
) -> Dict:
    return {
        "name": name,
        "body_type": body_type,
        # Mass / size
        "mass_kg": mass_kg,
        "diameter_km": diameter_km,
        "density_kg_m3": density_kg_m3,
        "gravity_ms2": gravity_ms2,
        "escape_velocity_kms": escape_vel_kms,
        # Temperature
        "mean_temp_k": mean_temp_k,
        "mean_temp_c": mean_temp_c,
        # Orbit
        "distance_from_sun_au": dist_from_sun_au,
        "distance_from_sun_mkm": dist_from_sun_mkm,
        "orbital_period_days": orbital_period_days,
        "orbital_period_earth_years": orbital_period_earth_years,
        # Day length
        "day_length_hours": day_length_hours,
        # Moons / rings
        "moons": moons,
        "moons_approximate": moons_approximate,
        "has_rings": has_rings,
        "magnetic_field": magnetic_field,
    }


BODIES: List[Dict] = [
    _body(
        name=planet.MERCURY,
        body_type="Terrestrial planet",
        mass_kg=3.3011e23,
        diameter_km=4879.0,
        density_kg_m3=5427.0,
        gravity_ms2=3.7,
        escape_vel_kms=4.25,
        mean_temp_k=167.0,
        mean_temp_c=-106.0,
        dist_from_sun_au=0.387,
        dist_from_sun_mkm=57.9,
        orbital_period_days=88.0,
        orbital_period_earth_years=0.241,
        day_length_hours=1407.6,
        moons=0,
        moons_approximate=False,
        has_rings=False,
        magnetic_field="Very weak",
    ),
    _body(
        name=planet.VENUS,
        body_type="Terrestrial planet",
        mass_kg=4.8675e24,
        diameter_km=12104.0,
        density_kg_m3=5243.0,
        gravity_ms2=8.87,
        escape_vel_kms=10.36,
        mean_temp_k=737.0,
        mean_temp_c=464.0,
        dist_from_sun_au=0.723,
        dist_from_sun_mkm=108.2,
        orbital_period_days=224.7,
        orbital_period_earth_years=0.615,
        day_length_hours=5832.2,
        moons=0,
        moons_approximate=False,
        has_rings=False,
        magnetic_field="None",
    ),
    _body(
        name=planet.EARTH,
        body_type="Terrestrial planet",
        mass_kg=5.9722e24,
        diameter_km=12742.0,
        density_kg_m3=5513.0,
        gravity_ms2=9.81,
        escape_vel_kms=11.19,
        mean_temp_k=288.0,
        mean_temp_c=15.0,
        dist_from_sun_au=1.0,
        dist_from_sun_mkm=149.6,
        orbital_period_days=365.26,
        orbital_period_earth_years=1.0,
        day_length_hours=24.0,
        moons=1,
        moons_approximate=False,
        has_rings=False,
        magnetic_field="Strong",
    ),
    _body(
        name=planet.JUPITER,
        body_type="Gas giant",
        mass_kg=1.8982e27,
        diameter_km=139822.0,
        density_kg_m3=1326.0,
        gravity_ms2=24.79,
        escape_vel_kms=59.5,
        mean_temp_k=165.0,
        mean_temp_c=-108.0,
        dist_from_sun_au=5.203,
        dist_from_sun_mkm=778.5,
        orbital_period_days=4332.59,
        orbital_period_earth_years=11.862,
        day_length_hours=9.93,
        moons=95,
        moons_approximate=True,
        has_rings=True,
        magnetic_field="Very strong",
    ),
    _body(
        name=planet.MARS,
        body_type="Terrestrial planet",
        mass_kg=6.4171e23,
        diameter_km=6779.0,
        density_kg_m3=3933.0,
        gravity_ms2=3.71,
        escape_vel_kms=5.03,
        mean_temp_k=210.0,
        mean_temp_c=-63.0,
        dist_from_sun_au=1.52,
        dist_from_sun_mkm=227.9,
        orbital_period_days=687.0,
        orbital_period_earth_years=1.881,
        day_length_hours=24.7,
        moons=2,
        moons_approximate=False,
        has_rings=False,
        magnetic_field="None",
    ),
    _body(
        name=planet.SATURN,
        body_type="Gas giant",
        mass_kg=5.6832e26,
        diameter_km=116460.0,
        density_kg_m3=687.0,
        gravity_ms2=10.44,
        escape_vel_kms=35.5,
        mean_temp_k=95.0,
        mean_temp_c=-178.0,
        dist_from_sun_au=9.537,
        dist_from_sun_mkm=1427.0,
        orbital_period_days=10759.0,
        orbital_period_earth_years=29.46,
        day_length_hours=10.7,
        moons=146,
        moons_approximate=True,
        has_rings=True,
        magnetic_field="Very strong",
    ),
    _body(
        name=planet.URANUS,
        body_type="Ice giant",
        mass_kg=8.6810e25,
        diameter_km=50724.0,
        density_kg_m3=1271.0,
        gravity_ms2=8.69,
        escape_vel_kms=21.3,
        mean_temp_k=76.0,
        mean_temp_c=-197.0,
        dist_from_sun_au=19.191,
        dist_from_sun_mkm=2871.0,
        orbital_period_days=30688.5,
        orbital_period_earth_years=84.017,
        day_length_hours=17.24,
        moons=27,
        moons_approximate=False,
        has_rings=True,
        magnetic_field="Tilted/offset",
    ),
    _body(
        name=planet.NEPTUNE,
        body_type="Ice giant",
        mass_kg=1.0241e26,
        diameter_km=49244.0,
        density_kg_m3=1638.0,
        gravity_ms2=11.15,
        escape_vel_kms=23.5,
        mean_temp_k=72.0,
        mean_temp_c=-201.0,
        dist_from_sun_au=30.069,
        dist_from_sun_mkm=4495.0,
        orbital_period_days=60182.0,
        orbital_period_earth_years=164.791,
        day_length_hours=16.11,
        moons=16,
        moons_approximate=True,
        has_rings=True,
        magnetic_field="Tilted/offset",
    ),
]
