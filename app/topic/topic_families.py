# =========================================================
# TOP-LEVEL CATEGORIES
#
# The channel ("The World, By The Numbers") covers many
# sectors.  These are the top-level categories used for
# category rotation.
#
# Each category maps to a "family" indicator-code classifier.
# A category is ELIGIBLE only if the current data providers
# can actually supply a real indicator for it.  Categories
# with no data source (e.g., football, gaming, anime) are
# present in the universe but SKIPPED during selection
# (real-data-only rule - never fabricate).
# =========================================================
TOP_LEVEL_CATEGORIES = [
    "countries_geography",
    "population_demographics",
    "economy",
    "smartphones_consumer_tech",
    "technology_internet",
    "artificial_intelligence",
    "cars_automotive",
    "gaming",
    "entertainment_pop_culture",
    "football",
    "sports",
    "companies_brands",
    "energy",
    "environment_climate",
    "health",
    "education",
    "travel_tourism",
    "lifestyle_society",
    "cities",
    "industry_manufacturing",
    "agriculture_food",
    "commodities_natural_resources",
    "finance_markets",
    "space_science",
    "retail_consumer_markets",
    "transport_infrastructure",
]

# Map family (from classify_topic_family) -> top-level category.
#
# The 26 top-level categories are much finer than the family
# classifier.  A family maps to exactly ONE category so the
# rotation layer has a clean grouped view of the pool.
FAMILY_TO_CATEGORY = {
    "economy": "economy",
    "demographics": "population_demographics",
    "health": "health",
    "education": "education",
    "military": "countries_geography",
    "energy": "energy",
    "environment": "environment_climate",
    "technology_connectivity": "technology_internet",
    "urbanization": "cities",
    "electricity": "energy",
    "ai_investment": "artificial_intelligence",
    "ai_research": "artificial_intelligence",
    "ai_talent": "artificial_intelligence",
    "ai_adoption": "artificial_intelligence",
    "ai_governance": "artificial_intelligence",
    "sports": "sports",
    "space_science": "space_science",
    "entertainment_pop_culture": "entertainment_pop_culture",
    "cars_automotive": "cars_automotive",
    "companies_brands": "companies_brands",
    "football": "football",
    "gaming": "gaming",
    "general_interest": "entertainment_pop_culture",
    "general": "countries_geography",
}

# Categories that exist in the universe but currently have NO
# real provider data.  They stay in TOP_LEVEL_CATEGORIES (so
# the list remains complete) but are never selected because
# no indicator maps to them. This keeps the system honest:
# we never fabricate football/gaming/smartphone/car data.
UNSUPPORTED_CATEGORIES = {
    "smartphones_consumer_tech",
    "travel_tourism",
    "lifestyle_society",
    "agriculture_food",
    "commodities_natural_resources",
    "finance_markets",
    "retail_consumer_markets",
    "transport_infrastructure",
}


def family_to_category(family: str) -> str:
    """Map a topic family to a top-level category.

    Falls back to 'countries_geography' for unknown families.
    """
    return FAMILY_TO_CATEGORY.get(
        str(family or "").strip().lower(),
        "countries_geography",
    )


TOPIC_FAMILIES = {
    "economy": {
        "codes": {
            "NY.GDP.MKTP.CD",
            "NY.GDP.PCAP.CD",
            "NGDPD",
            "NGDP_RPCH",
            "NGDPDPC",
            "PCPIPCH",
            "GGXWDG_NGDP",
            "gdp_per_capita",
        },
        "keywords": [
            "gdp",
            "inflation",
            "debt",
            "economic",
            "economy",
            "prices",
        ],
    },
    "demographics": {
        "codes": {
            "SP.POP.TOTL",
            "population",
        },
        "keywords": [
            "population",
            "demographic",
        ],
    },
    "health": {
        "codes": {
            "SP.DYN.LE00.IN",
            "SH.DYN.MORT",
            "SH.XPD.CHEX.GD.ZS",
            "life_expectancy",
        },
        "keywords": [
            "life expectancy",
            "health",
            "mortality",
            "doctor",
            "medicine",
        ],
    },
    "education": {
        "codes": {
            "SE.XPD.TOTL.GD.ZS",
        },
        "keywords": [
            "education",
            "school",
            "literacy",
        ],
    },
    "military": {
        "codes": {
            "MS.MIL.XPND.GD.ZS",
        },
        "keywords": [
            "military",
            "defense",
            "defence",
            "army",
            "armed forces",
        ],
    },
    "energy": {
        "codes": {
            "energy_per_capita",
        },
        "keywords": [
            "energy",
            "oil",
            "gas",
            "petroleum",
        ],
    },
    "environment": {
        "codes": {
            "co2_emissions",
            "co2_per_capita",
            "deaths_floods",
            "deaths_all_disasters",
            "red_list_index",
            "earthquake_count_m6",
            "earthquake_max_magnitude",
        },
        "keywords": [
            "co2",
            "emission",
            "climate",
            "environment",
            "pollution",
            "flood",
            "disaster",
            "earthquake",
            "seismic",
            "species",
            "biodiversity",
            "extinction",
            "red list",
            "wildlife",
            "endangered",
        ],
    },
    "technology_connectivity": {
        "codes": {
            "IT.NET.USER.ZS",
            "internet_users",
        },
        "keywords": [
            "internet",
            "technology",
            "connectivity",
            "online",
            "digital",
            "smartphone",
            "mobile",
        ],
    },
    "urbanization": {
        "codes": {
            "SP.URB.TOTL.IN.ZS",
        },
        "keywords": [
            "urban",
            "city",
        ],
    },
    "electricity": {
        "codes": {
            "EG.ELC.ACCS.ZS",
        },
        "keywords": [
            "electricity",
            "power access",
        ],
    },
    "sports": {
        "codes": {
            "driver_standings",
            "constructor_standings",
            "race_wins",
        },
        "keywords": [
            "f1",
            "formula 1",
            "driver",
            "constructor",
            "championship",
            "standings",
            "race",
            "grand prix",
        ],
    },
    "space_science": {
        "codes": {
            "research_publications_by_country",
            "planet_moons",
            "planet_gravity",
            "planet_surface_temp",
            "planet_diameter",
            "planet_distance_sun",
            "planet_orbital_period",
            "planet_day_length",
            "planet_density",
            "planet_escape_velocity",
        },
        "keywords": [
            "research",
            "publications",
            "scientific",
            "space",
            "astronomy",
            "astrophysics",
            "satellite",
            "cosmos",
            "planet",
            "moons",
            "gravity",
            "temperature",
            "diameter",
            "orbital",
            "escape velocity",
            "day length",
        ],
    },
    "entertainment_pop_culture": {
        "codes": {
            "anime_popularity_ranking",
            "anime_score_ranking",
            "anime_members_ranking",
            "anime_favorites_ranking",
        },
        "keywords": [
            "anime",
            "manga",
            "popularity ranking",
            "score ranking",
            "members ranking",
            "favorites ranking",
        ],
    },
    "cars_automotive": {
        "codes": {
            "vehicle_manufacturer_models",
            "vehicle_types_by_manufacturer",
        },
        "keywords": [
            "vehicle",
            "automotive",
            "manufacturer",
            "model count",
        ],
    },
    "companies_brands": {
        "codes": {
            "public_company_revenue",
            "public_company_net_income",
            "public_company_assets",
        },
        "keywords": [
            "revenue",
            "net income",
            "total assets",
            "public company",
        ],
    },
    "football": {
        "codes": {
            "premier_league_standings",
            "la_liga_standings",
            "bundesliga_standings",
            "serie_a_standings",
            "ligue1_standings",
        },
        "keywords": [
            "standings",
            "league",
            "football",
            "soccer",
            "premier league",
            "la liga",
            "bundesliga",
            "serie a",
            "ligue 1",
        ],
    },
    "gaming": {
        "codes": {
            "games_popular_ranking",
            "games_rating_ranking",
        },
        "keywords": [
            "game",
            "gaming",
            "video game",
            "games",
            "release year",
            "added count",
            "rating ranking",
        ],
    },
    "general_interest": {
        "codes": {
            "search_interest",
        },
        "keywords": [
            "search interest",
            "pageviews",
            "wikipedia",
            "popularity comparison",
        ],
    },
    "ai_investment": {
        "codes": {
            "ai_investment",
        },
        "keywords": [
            "ai investment",
            "artificial intelligence investment",
            "ai funding",
            "ai venture",
            "machine learning investment",
        ],
    },
    "ai_research": {
        "codes": {
            "ai_research",
        },
        "keywords": [
            "ai research",
            "artificial intelligence research",
            "ai publications",
            "machine learning research",
            "deep learning research",
        ],
    },
    "ai_talent": {
        "codes": {
            "ai_talent",
        },
        "keywords": [
            "ai talent",
            "artificial intelligence talent",
            "ai workforce",
            "ai experts",
            "machine learning experts",
        ],
    },
    "ai_adoption": {
        "codes": {
            "ai_adoption",
        },
        "keywords": [
            "ai adoption",
            "artificial intelligence adoption",
            "ai use",
            "ai deployment",
            "machine learning adoption",
        ],
    },
    "ai_governance": {
        "codes": {
            "ai_policy",
        },
        "keywords": [
            "ai policy",
            "ai governance",
            "artificial intelligence regulation",
            "ai regulation",
            "ai ethics",
            "ai framework",
        ],
    },
    # Governance indices (Corruption Perceptions Index etc.).
    # Deliberately its OWN rotation bucket so sensitive
    # governance content is spaced out like every other
    # family instead of blending into "general".
    "governance": {
        "codes": {
            "corruption_perceptions_index",
        },
        "keywords": [
            "corruption perceptions index",
            "corruption perception index",
            "perceptions index",
            "transparency international",
            "governance index",
        ],
    },
}


def classify_topic_family(
    indicator_code: str = "",
    indicator_name: str = "",
    category: str = ""
) -> str:

    code = str(
        indicator_code or ""
    ).strip()

    text = " ".join(
        [
            str(indicator_name or ""),
            str(category or ""),
        ]
    ).lower()

    # Pass 1: exact indicator-code match has the highest priority.
    # This ensures, for example, that "MS.MIL.XPND.GD.ZS" maps to
    # "military" even though its display name contains "GDP"
    # ("Military Expenditure (% of GDP)"), and that
    # "SE.XPD.TOTL.GD.ZS" maps to "education", etc.
    for family, config in TOPIC_FAMILIES.items():
        if code in config.get(
            "codes",
            set()
        ):
            return family

    # Pass 2: keyword fallback (indicator name / category text).
    for family, config in TOPIC_FAMILIES.items():
        for keyword in config.get(
            "keywords",
            []
        ):
            if keyword in text:
                return family

    return "general"
