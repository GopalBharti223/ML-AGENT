"""200-selection simulation for the expanded provider universe.

Runs SmartStoryEngine.select_best_candidate() 200 times using
the default provider list (all 9 providers) and reports:
  - A sample of 20-30 selected topics with full details
  - Country distribution percentages
  - Category distribution
  - Consecutive-repeat check
"""
import sys
import os
import random
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.topic.smart_story import SmartStoryEngine
from app.topic.topic_families import family_to_category


def classify_country(topic, provider_id, indicator_code):
    """Classify a selected topic by country relevance."""
    topic_lower = (topic or "").lower()
    indicator_lower = (indicator_code or "").lower()

    # Check for explicit country mentions in topic
    countries = {
        "india": "India",
        "usa": "USA",
        "united states": "USA",
        "america": "USA",
        "china": "China",
        "russia": "Russia",
        "ukraine": "Ukraine",
        "israel": "Israel",
        "bangladesh": "Bangladesh",
        "japan": "Japan",
        "germany": "Germany",
        "uk": "UK",
        "united kingdom": "UK",
        "france": "France",
        "brazil": "Brazil",
        "indonesia": "Indonesia",
        "pakistan": "Pakistan",
    }

    for keyword, country in countries.items():
        if keyword in topic_lower or keyword in indicator_lower:
            return country

    # Provider-based classification
    if provider_id == "jolpica_f1":
        return "Global (Sports)"
    if provider_id == "openalex":
        return "Global (Science)"
    if provider_id == "jikan":
        return "Global (Anime)"
    if provider_id == "nhtsa":
        return "Global (Auto)"
    if provider_id == "sec_edgar":
        return "Global (Companies)"

    return "Other"


def is_india_related(topic, provider_id, indicator_code):
    t = (topic or "").lower()
    return "india" in t or "indian" in t


def is_usa_related(topic, provider_id, indicator_code):
    t = (topic or "").lower()
    return any(k in t for k in ["usa", "united states", "america", "american"])


def main():
    print("=" * 70)
    print("200-SELECTION SIMULATION")
    print("Providers: worldbank, owid, imf, ai_index,")
    print("           jolpica_f1, openalex, jikan, nhtsa, sec_edgar")
    print("=" * 70)

    random.seed(42)  # Reproducible for the simulation

    results = []
    consecutive_repeats = 0
    last_topic = None

    for i in range(200):
        try:
            candidate = SmartStoryEngine.select_best_candidate(
                years=5,
                min_countries=6,
            )
        except Exception as e:
            print(f"  Run {i+1}: ERROR - {e}")
            continue

        if candidate is None:
            print(f"  Run {i+1}: No candidate (acceptable)")
            continue

        country = classify_country(
            candidate.topic,
            candidate.provider_id,
            candidate.indicator_code,
        )

        results.append({
            "topic": candidate.topic,
            "provider": candidate.provider_id,
            "indicator": candidate.indicator_code,
            "story_type": candidate.story_type,
            "category": family_to_category(candidate.topic_family),
            "family": candidate.topic_family,
            "country": country,
            "india": is_india_related(
                candidate.topic,
                candidate.provider_id,
                candidate.indicator_code,
            ),
            "usa": is_usa_related(
                candidate.topic,
                candidate.provider_id,
                candidate.indicator_code,
            ),
            "score": candidate.score,
        })

        if last_topic == candidate.topic:
            consecutive_repeats += 1
        last_topic = candidate.topic

    print(f"\n{'='*70}")
    print(f"SIMULATION COMPLETE: {len(results)}/200 selections succeeded")
    print(f"Consecutive repeats: {consecutive_repeats}")
    print(f"{'='*70}")

    if not results:
        print("No results - check network connectivity")
        return

    # Show sample of 25 topics
    print(f"\n{'='*70}")
    print("SAMPLE TOPICS (25 of {len(results)}):")
    print(f"{'='*70}")

    sample_indices = random.sample(
        range(len(results)),
        min(25, len(results)),
    )
    sample_indices.sort()

    for idx in sample_indices:
        r = results[idx]
        print(f"\n  {idx+1}. Topic: {r['topic']}")
        print(f"     Country: {r['country']}")
        print(f"     Category: {r['category']}")
        print(f"     Story Type: {r['story_type']}")
        print(f"     Provider: {r['provider']}/{r['indicator']}")
        print(f"     Score: {r['score']:.2f}")
        print(f"     USA-related: {r['usa']}")
        print(f"     India-related: {r['india']}")

    # Calculate distribution
    print(f"\n{'='*70}")
    print("COUNTRY DISTRIBUTION:")
    print(f"{'='*70}")

    country_counts = Counter(r["country"] for r in results)
    total = len(results)

    target_countries = [
        "India", "USA", "China", "Russia",
        "Ukraine", "Israel", "Bangladesh",
    ]

    for country in target_countries:
        count = country_counts.get(country, 0)
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {country:20s}: {count:4d} ({pct:5.1f}%)")

    other_count = sum(
        count for country, count in country_counts.items()
        if country not in target_countries
    )
    other_pct = (other_count / total * 100) if total > 0 else 0
    print(f"  {'Other':20s}: {other_count:4d} ({other_pct:5.1f}%)")

    # Category distribution
    print(f"\n{'='*70}")
    print("CATEGORY DISTRIBUTION:")
    print(f"{'='*70}")

    cat_counts = Counter(r["category"] for r in results)
    for cat, count in cat_counts.most_common():
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {cat:30s}: {count:4d} ({pct:5.1f}%)")

    # Provider distribution
    print(f"\n{'='*70}")
    print("PROVIDER DISTRIBUTION:")
    print(f"{'='*70}")

    prov_counts = Counter(r["provider"] for r in results)
    for prov, count in prov_counts.most_common():
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {prov:20s}: {count:4d} ({pct:5.1f}%)")

    # Story type distribution
    print(f"\n{'='*70}")
    print("STORY TYPE DISTRIBUTION:")
    print(f"{'='*70}")

    st_counts = Counter(r["story_type"] for r in results)
    for st, count in st_counts.most_common():
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {st:25s}: {count:4d} ({pct:5.1f}%)")


if __name__ == "__main__":
    main()
