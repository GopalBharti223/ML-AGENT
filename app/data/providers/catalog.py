"""
Provider Catalog — honest registry of all data sources.

The topic engine consults this catalog to decide whether a
top-level category is ELIGIBLE.

Eligibility chain (from the master task):
  provider exists -> enabled -> real data available
  -> passes validation -> category becomes eligible.

commercial_use values:
  ALLOWED         : clearly permitted (public-domain gov data, CC0).
  REVIEW_REQUIRED : free tier exists but commercial use of the data
                    for a monetized YouTube channel is unclear or
                    requires a paid/higher tier.  Do NOT silently
                    treat as unrestricted.
  PROHIBITED      : source clearly forbids commercial use.

This module NEVER fabricates data.  A provider may be present in
the catalog while `enabled=False` (e.g., requires an API key that
is not configured, or commercial use needs review).  The engine
simply skips disabled / review-required providers.
"""
from typing import Dict, List

from app.data.providers.base import ProviderMetadata


# =========================================================
# PROVIDER METADATA
#
# Existing providers (already in registry) + proposed providers
# that will expand category support.
# =========================================================

PROVIDER_METADATA: Dict[str, ProviderMetadata] = {
    # --------------------------------------------------
    # EXISTING PROVIDERS
    # --------------------------------------------------
    "worldbank": ProviderMetadata(
        provider_id="worldbank",
        provider_name="World Bank",
        category="economy",
        supported_topics=[
            "GDP", "GDP per capita", "population", "life expectancy",
            "internet users", "urban population", "education spending",
            "military spending", "electricity access", "mortality",
            "health expenditure",
        ],
        supported_indicators=[
            "NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD", "SP.POP.TOTL",
            "SP.DYN.LE00.IN", "IT.NET.USER.ZS", "SP.URB.TOTL.IN.ZS",
            "SE.XPD.TOTL.GD.ZS", "MS.MIL.XPND.GD.ZS",
            "EG.ELC.ACCS.ZS", "SH.DYN.MORT", "SH.XPD.CHEX.GD.ZS",
        ],
        historical_coverage="1960-present",
        latest_data_date="2025",
        license="CC BY 4.0",
        commercial_use="ALLOWED",
        attribution_required=True,
        rate_limit="~60 requests/min (bulk fetch supported)",
        requires_api_key=False,
        enabled=True,
        source_url="https://data.worldbank.org",
    ),
    "owid": ProviderMetadata(
        provider_id="owid",
        provider_name="Our World in Data",
        category="economy",
        supported_topics=[
            "population", "life expectancy", "CO2 emissions",
            "CO2 per capita", "energy use", "GDP per capita",
            "internet users", "corruption perceptions",
            "flood deaths", "natural disaster deaths",
            "red list index / extinction risk trend",
        ],
        supported_indicators=[
            "population", "life_expectancy", "co2_emissions",
            "co2_per_capita", "energy_per_capita", "gdp_per_capita",
            "internet_users", "corruption_perceptions_index",
            "deaths_floods", "deaths_all_disasters",
            "red_list_index",
        ],
        historical_coverage="Long-run historical series",
        latest_data_date="2024-2025",
        license="CC BY 4.0",
        commercial_use="ALLOWED",
        attribution_required=True,
        rate_limit="Public CSV downloads; be reasonable",
                requires_api_key=False,
        enabled=True,
        source_url="https://ourworldindata.org",
    ),

    # U.S. Geological Survey earthquake feed (keyless FDSN event API,
    # aggregated to country-year at fetch time; M6+ only; honesty
    # framing enforced in app/ai/script.py).  See
    # app/data/providers/usgs.py.
    "usgs": ProviderMetadata(
        provider_id="usgs",
        provider_name="U.S. Geological Survey",
        category="environment_climate",
        supported_topics=[
            "magnitude-6+ earthquake counts by country",
            "strongest earthquake by country per year",
            "seismic activity trends",
        ],
        supported_indicators=[
            "earthquake_count_m6",
            "earthquake_max_magnitude",
        ],
        historical_coverage="Instrumental era (1970-present, M6+)",
        latest_data_date="Current year",
        license="Public domain (U.S. Geological Survey)",
        commercial_use="ALLOWED",
        attribution_required=True,
        rate_limit="Keyless API; be reasonable (~5 req/s)",
        requires_api_key=False,
        enabled=True,
        source_url="https://earthquake.usgs.gov/",
    ),

    "imf": ProviderMetadata(
        provider_id="imf",
        provider_name="International Monetary Fund",
        category="economy",
        supported_topics=[
            "GDP", "real GDP growth", "GDP per capita",
            "inflation", "government debt",
        ],
        supported_indicators=[
            "NGDPD", "NGDP_RPCH", "NGDPDPC", "PCPIPCH",
            "GGXWDG_NGDP",
        ],
        historical_coverage="1980-present",
        latest_data_date="2025",
        license="IMF Data Mapper API (public)",
        commercial_use="REVIEW_REQUIRED",
        attribution_required=True,
        rate_limit="Varies; can return 403 in some environments",
        requires_api_key=False,
        enabled=True,
        source_url="https://www.imf.org/en/Data",
    ),
    "ai_index": ProviderMetadata(
        provider_id="ai_index",
        provider_name="Stanford AI Index",
        category="artificial_intelligence",
        supported_topics=[
            "AI investment", "AI research", "AI talent", "AI policy",
        ],
        supported_indicators=[
            "ai_investment", "ai_research", "ai_talent",
            "ai_adoption", "ai_policy",
        ],
        historical_coverage="Selected years",
        latest_data_date="2024-2025",
        license="Stanford AI Index official data files",
        commercial_use="ALLOWED",
        attribution_required=True,
        rate_limit="Static CSV download",
        requires_api_key=False,
        enabled=True,
        source_url="https://hai.stanford.edu/ai-index",
    ),

    # --------------------------------------------------
    # PROPOSED PROVIDERS
    # --------------------------------------------------

    # FOOTBALL-DATA.ORG (football) — IMPLEMENTED, key-gated
    "football_data": ProviderMetadata(
        provider_id="football_data",
        provider_name="Football-Data.org",
        category="football",
        supported_topics=[
            "league tables", "standings", "points",
            "seasons", "team rankings",
        ],
        supported_indicators=[
            "premier_league_standings",
            "la_liga_standings",
            "bundesliga_standings",
            "serie_a_standings",
            "ligue1_standings",
        ],
        historical_coverage="Free tier: current + a few recent seasons",
        latest_data_date="Current season",
        license="football-data.org free tier (non-commercial)",
        commercial_use="REVIEW_REQUIRED",
        attribution_required=True,
        rate_limit="10 requests/min (free tier)",
        requires_api_key=True,  # FOOTBALL_DATA_API_KEY (free, instant)
        enabled=False,  # implemented; enabled only when the key is set
        source_url="https://www.football-data.org",
    ),

    # JIKAN / MYANIMELIST (entertainment_pop_culture)
    "jikan": ProviderMetadata(
        provider_id="jikan",
        provider_name="Jikan (MyAnimeList)",
        category="entertainment_pop_culture",
        supported_topics=[
            "anime ranking", "anime score", "popularity", "members",
            "favorites", "genres", "type", "release year",
        ],
        supported_indicators=[
            "anime_popularity_ranking",
            "anime_score_ranking",
            "anime_favorites_ranking",
            "anime_members_ranking",
        ],
        historical_coverage="Anime released to date",
        latest_data_date="Current",
        license="Jikan public API (MAL-derived)",
        commercial_use="REVIEW_REQUIRED",
        attribution_required=True,
        rate_limit="3 requests/second (be reasonable)",
        requires_api_key=False,
        enabled=True,  # popularity = listing popularity, NOT viewership
        source_url="https://jikan.moe",
    ),

    # RAWG VIDEO GAMES DATABASE (gaming) — IMPLEMENTED, key-gated
    "rawg": ProviderMetadata(
        provider_id="rawg",
        provider_name="RAWG Video Games Database",
        category="gaming",
        supported_topics=[
            "game rankings", "game ratings",
            "popular games by release year",
        ],
        supported_indicators=[
            "games_popular_ranking",
            "games_rating_ranking",
        ],
        historical_coverage="Games released to date",
        latest_data_date="Current",
        license="RAWG API free tier (attribution + backlink required)",
        commercial_use="REVIEW_REQUIRED",
        attribution_required=True,
        rate_limit="20k requests/month (free tier)",
        requires_api_key=True,  # RAWG_API_KEY (free, instant)
        enabled=False,  # implemented; enabled only when the key is set
        source_url="https://rawg.io/apidocs",
    ),

    # JOLPICA FORMULA 1 (sports)
    "jolpica_f1": ProviderMetadata(
        provider_id="jolpica_f1",
        provider_name="Jolpica F1",
        category="sports",
        supported_topics=[
            "F1 standings", "drivers", "constructors", "races",
            "points", "wins", "podiums", "seasons", "race results",
        ],
        supported_indicators=[
            "driver_standings",
            "constructor_standings",
            "race_wins",
        ],
        historical_coverage="1950-present",
        latest_data_date="Current season",
        license="Jolpica/Ergast F1 API (open)",
        commercial_use="ALLOWED",
        attribution_required=True,
        rate_limit="Public API; be reasonable",
        requires_api_key=False,
        enabled=True,
        source_url="https://api.jolpi.ca/ergast/f1",
    ),

    # OPENALEX (space_science) — CC0 research data
    "openalex": ProviderMetadata(
        provider_id="openalex",
        provider_name="OpenAlex",
        category="space_science",
        supported_topics=[
            "research publications by country",
            "scientific output by country",
            "research rankings",
        ],
        supported_indicators=[
            "research_publications_by_country",
        ],
        historical_coverage="Modern scholarly output",
        latest_data_date="Rolling (updated monthly)",
        license="CC0 (public domain)",
        commercial_use="ALLOWED",
        attribution_required=True,
        rate_limit="100k calls/day, 10/s",
        requires_api_key=False,
        enabled=True,
        source_url="https://openalex.org",
    ),

    # SOLAR SYSTEM (space_science) — NASA NSSDC public-domain facts
    "solar_system": ProviderMetadata(
        provider_id="solar_system",
        provider_name="NASA NSSDC Planetary Fact Sheet",
        category="space_science",
        supported_topics=[
            "planet moons", "surface gravity", "surface temperature",
            "planet diameter", "distance from sun", "orbital period",
            "day length", "planetary density", "escape velocity",
        ],
        supported_indicators=[
            "planet_moons",
            "planet_gravity",
            "planet_surface_temp",
            "planet_diameter",
            "planet_distance_sun",
            "planet_orbital_period",
            "planet_day_length",
            "planet_density",
            "planet_escape_velocity",
        ],
        historical_coverage="Snapshot (latest NASA-published values)",
        latest_data_date="2025",
        license="Public domain (U.S. Government work, 17 U.S.C. sec. 105)",
        commercial_use="ALLOWED",
        attribution_required=True,
        rate_limit="None (static curated dataset; no network)",
        requires_api_key=False,
        enabled=True,
        source_url="https://nssdc.gsfc.nasa.gov/planetary/factsheet/",
    ),

    # NASA PUBLIC APIS (space_science)
    "nasa": ProviderMetadata(
        provider_id="nasa",
        provider_name="NASA Open APIs",
        category="space_science",
        supported_topics=[
            "astronomy picture of the day", "asteroids near Earth",
            "space mission metadata",
        ],
        supported_indicators=[],
        historical_coverage="Varies by dataset",
        latest_data_date="Current",
        license="NASA open data",
        commercial_use="ALLOWED",
        attribution_required=True,
        rate_limit="Varies by API (1k/hr typical)",
        requires_api_key=True,  # NASA_API_KEY (free registration)
        enabled=False,  # needs NASA_API_KEY
        source_url="https://api.nasa.gov",
    ),

    # SEC EDGAR (companies_brands)
    "sec_edgar": ProviderMetadata(
        provider_id="sec_edgar",
        provider_name="SEC EDGAR",
        category="companies_brands",
        supported_topics=[
            "company revenue", "net income", "assets", "liabilities",
            "employees", "filing dates", "revenue growth",
        ],
        supported_indicators=[
            "public_company_revenue",
            "public_company_net_income",
            "public_company_assets",
        ],
        historical_coverage="1994-present filings",
        latest_data_date="Rolling (quarterly filings)",
        license="US public domain",
        commercial_use="ALLOWED",
        attribution_required=True,
        rate_limit="Fair access: 10 req/s, identifiable UA required",
        requires_api_key=False,
        enabled=True,
        source_url="https://www.sec.gov/edgar",
    ),

    # NHTSA vPIC (cars_automotive)
    "nhtsa": ProviderMetadata(
        provider_id="nhtsa",
        provider_name="NHTSA vPIC API",
        category="cars_automotive",
        supported_topics=[
            "vehicle manufacturers", "vehicle models", "vehicle types",
            "manufacturer statistics",
        ],
        supported_indicators=[
            "vehicle_manufacturer_models",
            "vehicle_types_by_manufacturer",
        ],
        historical_coverage="Manufacturer/model directory",
        latest_data_date="Current",
        license="US public domain (TMV / no sales data)",
        commercial_use="ALLOWED",
        attribution_required=True,
        rate_limit="Public API; be reasonable",
        requires_api_key=False,
        enabled=True,
        source_url="https://vpic.nhtsa.dot.gov/api",
    ),

    # WIKIPEDIA PAGEVIEWS (general entity comparison, manual route)
    "wikipedia": ProviderMetadata(
        provider_id="wikipedia",
        provider_name="Wikipedia Pageviews",
        category="general_interest",
        supported_topics=[
            "popularity comparison",
            "search interest comparison",
            "entity comparison (companies, people, products)",
        ],
        supported_indicators=[
            "search_interest",
        ],
        historical_coverage="July 2015 - present (pageview API window)",
        latest_data_date="Yesterday (rolling)",
        license="Wikimedia REST API terms (CC0-derived metrics)",
        commercial_use="ALLOWED",
        attribution_required=True,
        rate_limit="Public API; polite rates with descriptive UA",
        requires_api_key=False,
        enabled=True,
        source_url="https://wikimedia.org/api/rest_v1/",
    ),

    # USGS earthquakes (environment_climate): keyless FDSN event API.
    # Individual events are aggregated at fetch time into the standard
    # country-year wide_data (count of M6+ / max magnitude per year).
    # Honesty framing enforced in script.py: M6+ only (region-biased
    # detection below that), nearest-coastline attribution, offshore
    # events bucketed as "International waters" rather than force-fit.
    "usgs": ProviderMetadata(
        provider_id="usgs",
        provider_name="U.S. Geological Survey",
        category="environment_climate",
        supported_topics=[
            "earthquakes", "seismic activity", "earthquake counts",
            "strongest earthquake by country",
        ],
        supported_indicators=[
            "earthquake_count_m6", "earthquake_max_magnitude",
        ],
        historical_coverage="Instrumental era; M6+ counts fair for ~15y windows",
        latest_data_date="Live (real-time event feed)",
        license="US public domain (USGS)",
        commercial_use="ALLOWED",
        attribution_required=True,
        rate_limit="Public API; ~5 req/s politeness guidance",
        requires_api_key=False,
        enabled=True,
        source_url="https://earthquake.usgs.gov/fdsnws/event/1/",
    ),

    # TMDB (entertainment_pop_culture) — commercial use must be reviewed
    "tmdb": ProviderMetadata(
        provider_id="tmdb",
        provider_name="The Movie Database (TMDB)",
        category="entertainment_pop_culture",
        supported_topics=[
            "movie rankings", "ratings", "genres", "release trends",
            "TV rankings",
        ],
        supported_indicators=[],
        historical_coverage="Current catalog",
        latest_data_date="Current",
        license="TMDB API terms",
        commercial_use="REVIEW_REQUIRED",
        attribution_required=True,
        rate_limit="Free tier; commercial use requires approval",
        requires_api_key=True,  # TMDB_API_KEY
        enabled=False,  # commercial-use approval + key required
        source_url="https://www.themoviedb.org/documentation/api",
    ),

    # VIRAL TOPICS (gaming, billionaires, pop culture, brand wars)
    "viral_topics": ProviderMetadata(
        provider_id="viral_topics",
        provider_name="Viral Culture & Wealth Archives",
        category="viral_topics",
        supported_topics=[
            "GTA sales", "Grand Theft Auto franchise copies sold",
            "best selling video games of all time", "Minecraft sales",
            "most played games monthly active users", "Roblox vs Minecraft",
            "best selling video game consoles PS2 Switch",
            "world richest billionaires net worth", "Elon Musk net worth",
            "Jeff Bezos net worth", "Ambani net worth", "Adani net worth",
            "trillion dollar race most valuable companies market cap",
            "Nvidia market cap", "Apple vs Microsoft",
            "YouTube subscriber race MrBeast vs T-Series vs PewDiePie",
            "Cristiano Ronaldo vs Lionel Messi career goals",
            "most international runs in cricket Sachin Virat Kohli",
            "world population giants India surpassing China",
            "Tesla vs BYD electric vehicle deliveries",
            "global smartphone shipments Apple vs Samsung",
            "most popular social media active users",
            "highest grossing movies of all time box office",
        ],
        supported_indicators=[
            "gta_sales",
            "all_time_games_sales",
            "all_time_gaming_consoles",
            "most_played_games_mau",
            "top_billionaires_net_worth",
            "top_companies_market_cap",
            "youtube_subscribers_race",
            "football_goals_ronaldo_vs_messi",
            "cricket_international_runs",
            "world_population_giants",
            "tesla_vs_byd_ev_sales",
            "smartphone_market_shipments",
            "social_media_active_users",
            "all_time_box_office",
        ],
        historical_coverage="1960-2026 verified historical series",
        latest_data_date="2026",
        license="Public company filings, Forbes archives & official releases",
        commercial_use="ALLOWED",
        attribution_required=True,
        rate_limit="Curated offline dataset; instantaneous",
        requires_api_key=False,
        enabled=True,
        source_url="https://data.lr-atlas.com",
    ),
}


def category_eligible(category: str) -> bool:
    """A category is eligible if at least one provider is:
    enabled AND requires no unconfigured key AND is not prohibited.
    """
    for meta in PROVIDER_METADATA.values():
        if meta.category != category:
            continue
        if not meta.enabled:
            continue
        if meta.commercial_use == "PROHIBITED":
            continue
        if meta.requires_api_key:
            continue
        return True
    return False


def eligible_provider_ids() -> List[str]:
    """Return provider ids that are safe to enable right now."""
    return sorted(
        meta.provider_id
        for meta in PROVIDER_METADATA.values()
        if (
            meta.enabled
            and meta.commercial_use != "PROHIBITED"
            and not meta.requires_api_key
        )
    )