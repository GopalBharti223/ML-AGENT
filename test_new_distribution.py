"""
Test the new country distribution preference.

Simulates 100 selection cycles with a mix of candidates
and reports the actual distribution.
"""
from collections import Counter

from app.topic.topic_distribution import (
    TARGET_DISTRIBUTION,
    TopicDistributionPreference,
)
from app.topic.smart_story import StoryCandidate


def make_candidate(
    entity,
    score,
    topic=None,
    leader=None,
    challenger=None,
):
    """Build a StoryCandidate for testing."""
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
        "story_type": "fastest_growth",
        "indicator_code": "NY.GDP.PCAP.CD",
        "indicator_name": "GDP Per Capita",
        "topic_family": "economy",
    }

    if leader:
        metrics["leader"] = leader
    if challenger:
        metrics["challenger"] = challenger

    if topic is None:
        topic = f"{entity} GDP Growth"

    return StoryCandidate(
        provider_id="worldbank",
        indicator_code="NY.GDP.PCAP.CD",
        indicator_name="GDP Per Capita",
        story_type="fastest_growth",
        chart_type="top5_change",
        topic_family="economy",
        years=10,
        category="World Data",
        source_name="World Bank",
        source_url="https://data.worldbank.org",
        topic=topic,
        score=score,
        metrics=metrics,
    )


# Candidate entities with equal score ranges per category.
# Each category gets 3 candidates at scores 60, 65, 70 so the
# soft preference (not score differences) drives the distribution.
ENTITIES = [
    # India-related
    ("India", 60.0),
    ("India", 65.0),
    ("India", 70.0),
    # USA-related
    ("United States", 60.0),
    ("United States", 65.0),
    ("United States", 70.0),
    # China-related
    ("China", 60.0),
    ("China", 65.0),
    ("China", 70.0),
    # Russia-related
    ("Russia", 60.0),
    ("Russia", 65.0),
    ("Russia", 70.0),
    # Israel-related
    ("Israel", 60.0),
    ("Israel", 65.0),
    ("Israel", 70.0),
    # Iran-related
    ("Iran", 60.0),
    ("Iran", 65.0),
    ("Iran", 70.0),
    # Other countries
    ("Brazil", 60.0),
    ("Germany", 65.0),
    ("Japan", 70.0),
    ("France", 60.0),
    ("UK", 65.0),
    ("Mexico", 70.0),
    ("Nigeria", 60.0),
    ("Vietnam", 65.0),
    ("South Africa", 70.0),
    ("Australia", 60.0),
]


def main():
    print("=" * 70)
    print("NEW COUNTRY DISTRIBUTION TEST")
    print("=" * 70)

    print("\nTarget distribution:")
    for cat, target in TARGET_DISTRIBUTION.items():
        print(f"  {cat}: {target * 100:.0f}%")

    history = []
    selected_count = Counter()
    total = 100

    for cycle in range(total):
        # Build candidate pool with all entities
        candidates = []
        for entity, base_score in ENTITIES:
            # Vary scores slightly per cycle
            score = base_score + (cycle % 5) * 2.0
            candidates.append(
                make_candidate(
                    entity=entity,
                    score=score,
                    topic=f"{entity} GDP Growth",
                )
            )

        # Apply preference
        result = TopicDistributionPreference.apply_preference(
            candidates,
            history
        )

        # Select the best
        selected = result[0]
        category = TopicDistributionPreference.country_category(
            selected.metrics["entity"]
        )
        selected_count[category] += 1

        # Add to history
        history.append(
            {
                "topic": selected.topic,
                "title": selected.topic,
            }
        )

    print(f"\n{'=' * 70}")
    print(f"ACTUAL DISTRIBUTION ({total} selections)")
    print(f"{'=' * 70}")

    for cat in TARGET_DISTRIBUTION:
        count = selected_count.get(cat, 0)
        pct = (count / total) * 100
        target_pct = TARGET_DISTRIBUTION[cat] * 100
        print(f"  {cat:8s}: {count:3d}  {pct:5.1f}%  (target {target_pct:.0f}%)")

    print(f"\n{'=' * 70}")
    print("SAMPLE SELECTED TOPICS (first 20)")
    print(f"{'=' * 70}")

    for i, record in enumerate(history[:20], 1):
        print(f"  {i:2d}. {record['topic']}")

    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print("  India and USA should be the top two categories.")
    print("  China, Russia, Israel, Iran should appear but less frequently.")
    print("  Other countries should still appear (~15%).")
    print("  Quality always wins over distribution.")


if __name__ == "__main__":
    main()