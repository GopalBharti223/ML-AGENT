"""
Generate 30 sample topic candidates using the modified
topic selection logic (TopicDistributionPreference + new
topic-family classification).

Candidates are built from REAL provider indicators so the
sample reflects what production can actually generate:
- World Bank: 11 indicators
- OWID: 7 indicators
- AI Index: 5 indicators
- IMF: 5 indicators (captured in economy family)
"""
import random
from collections import Counter

from app.topic.smart_story import StoryCandidate
from app.topic.topic_distribution import TopicDistributionPreference
from app.topic.topic_families import classify_topic_family


# =========================================================
# REAL INDICATORS (verified against provider lists)
# =========================================================

REAL_INDICATORS = [
    # World Bank
    ("worldbank", "NY.GDP.MKTP.CD", "GDP (Current US$)", "economy"),
    ("worldbank", "NY.GDP.PCAP.CD", "GDP Per Capita (Current US$)", "economy"),
    ("worldbank", "SP.POP.TOTL", "Population", "demographics"),
    ("worldbank", "SP.DYN.LE00.IN", "Life Expectancy at Birth", "health"),
    ("worldbank", "IT.NET.USER.ZS", "Internet Users (% of Population)", "technology_connectivity"),
    ("worldbank", "SP.URB.TOTL.IN.ZS", "Urban Population (%)", "urbanization"),
    ("worldbank", "SE.XPD.TOTL.GD.ZS", "Gov Education Expenditure (% GDP)", "education"),
    ("worldbank", "MS.MIL.XPND.GD.ZS", "Military Expenditure (% GDP)", "military"),
    ("worldbank", "EG.ELC.ACCS.ZS", "Access to Electricity (%)", "electricity"),
    ("worldbank", "SH.DYN.MORT", "Under-5 Mortality Rate", "health"),
    ("worldbank", "SH.XPD.CHEX.GD.ZS", "Health Expenditure (% GDP)", "health"),
    # OWID
    ("owid", "population", "Population", "demographics"),
    ("owid", "life_expectancy", "Life Expectancy", "health"),
    ("owid", "co2_emissions", "Annual CO2 Emissions", "environment"),
    ("owid", "co2_per_capita", "CO2 Emissions Per Capita", "environment"),
    ("owid", "energy_per_capita", "Energy Use Per Person", "energy"),
    ("owid", "gdp_per_capita", "GDP Per Capita", "economy"),
    ("owid", "internet_users", "Share Using Internet", "technology_connectivity"),
    # AI Index
    ("ai_index", "ai_investment", "AI Investment", "ai_investment"),
    ("ai_index", "ai_research", "AI Research Publications", "ai_research"),
    ("ai_index", "ai_talent", "AI Talent", "ai_talent"),
    ("ai_index", "ai_policy", "AI Policy", "ai_governance"),
    # IMF
    ("imf", "NGDPD", "GDP, current prices", "economy"),
    ("imf", "NGDP_RPCH", "Real GDP growth", "economy"),
    ("imf", "NGDPDPC", "GDP per capita", "economy"),
    ("imf", "PCPIPCH", "Inflation rate", "economy"),
    ("imf", "GGXWDG_NGDP", "General government gross debt", "economy"),
]

# Countries for realistic pool (major + assorted)
ENTITIES = [
    "India", "United States", "China", "Russia", "Ukraine",
    "Israel", "Bangladesh", "Brazil", "Germany", "Japan",
    "United Kingdom", "France", "South Korea", "Vietnam",
    "Saudi Arabia", "Turkey", "Indonesia", "Mexico",
]

STORY_TYPES = [
    "fastest_growth", "biggest_decline", "rank_climber",
    "rank_decline", "current_leader", "leader_challenge",
    "trend_over_time",
]


def make_candidate(
    provider_id,
    indicator_code,
    indicator_name,
    entity,
    story_type,
    score,
    family=None,
):
    """Build a realistic StoryCandidate."""
    if family is None:
        family = classify_topic_family(indicator_code, indicator_name)

    metrics = {
        "entity": entity,
        "start_year": 2016,
        "end_year": 2025,
        "start_value": 100.0,
        "end_value": 150.0,
        "absolute_change": 50.0,
        "percentage_change": 50.0,
        "start_rank": 5.0,
        "end_rank": 3.0,
        "rank_change": 2.0,
        "number_of_valid_countries": 8,
        "number_of_valid_years": 10,
        "data_completeness": 0.95,
        "leader_separation": 0.40,
        "trend_strength": 0.85,
        "story_type": story_type,
        "indicator_code": indicator_code,
        "indicator_name": indicator_name,
        "topic_family": family,
    }

    topic = f"{indicator_name}: {entity} {story_type.replace('_', ' ')}"

    return StoryCandidate(
        provider_id=provider_id,
        indicator_code=indicator_code,
        indicator_name=indicator_name,
        story_type=story_type,
        chart_type="top5_change",
        topic_family=family,
        years=10,
        category="World Data",
        source_name="Test Provider",
        source_url="https://example.com",
        topic=topic,
        score=score,
        metrics=metrics,
    )


def build_pool():
    """Build a diverse candidate pool across all real indicators."""
    random.seed(42)
    candidates = []

    for provider_id, code, name, family in REAL_INDICATORS:
        for entity in random.sample(ENTITIES, 1):
            story_type = random.choice(STORY_TYPES)

            # Score range varies slightly so quality still matters
            score = random.uniform(60, 85)

            candidates.append(
                make_candidate(
                    provider_id=provider_id,
                    indicator_code=code,
                    indicator_name=name,
                    entity=entity,
                    story_type=story_type,
                    score=score,
                    family=family,
                )
            )

    return candidates


def main():
    random.seed(42)

    history = []
    selected = []
    family_counts = Counter()
    country_counts = Counter()

    print("=" * 90)
    print("SAMPLE TOPIC GENERATION (30 candidates)")
    print("Using: TopicDistributionPreference.apply_preference()")
    print("       + new topic-family classifier (real providers)")
    print("=" * 90)

    for i in range(30):
        pool = build_pool()

        ranked = TopicDistributionPreference.apply_preference(pool, history)

        winner = ranked[0]
        metrics = winner.metrics
        entity = metrics.get("entity", "")
        family = winner.topic_family
        provider = winner.provider_id
        indicator = winner.indicator_code

        family_counts[family] += 1
        country_counts[entity] += 1

        history.append({
            "topic": winner.topic,
            "indicator_code": indicator,
            "story_type": winner.story_type,
        })

        selected.append(winner)

        print(f"\n--- Topic {i + 1} ---")
        print(f"Topic: {winner.topic}")
        print(f"Family: {family}")
        print(f"Country: {entity}")
        print(f"Story type: {winner.story_type}")
        print(f"Provider/Indicator: {provider}/{indicator}")
        print(f"Score: {winner.score:.2f}")

    # =========================================================
    # FAMILY DISTRIBUTION SUMMARY
    # =========================================================
    print("\n" + "=" * 90)
    print("FAMILY DISTRIBUTION (30 selections)")
    print("=" * 90)

    total = len(selected)
    for family in sorted(family_counts):
        count = family_counts[family]
        pct = (count / total) * 100
        print(f"  {family:24s} {count:2d}  {pct:5.1f}%")

    print("\n--- COUNTRY SPREAD ---")
    for country in sorted(country_counts, key=lambda c: -country_counts[c]):
        print(f"  {country:20s} {country_counts[country]:2d}")

    print("\n--- CHECKS ---")
    families_used = len(family_counts)
    print(f"  Distinct families used: {families_used}")
    print(f"  Distinct countries used: {len(country_counts)}")

    # Verify no repeated concept (entity+indicator) in the selected batch
    concepts = set()
    repeats = 0
    for w in selected:
        concept = f"{w.metrics['entity']}|{w.indicator_code}"
        if concept in concepts:
            repeats += 1
        concepts.add(concept)
    print(f"  Repeated concepts in batch: {repeats}")
    print(f"  Population-family share: {family_counts.get('demographics', 0) / total * 100:.1f}%")
    print(f"  GDP/economy share: {family_counts.get('economy', 0) / total * 100:.1f}%")


if __name__ == "__main__":
    main()