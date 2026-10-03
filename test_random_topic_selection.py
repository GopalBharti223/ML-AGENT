"""
Verify that SmartStoryEngine produces random topic variety
even when population dominates the top-ranked candidates.
"""
from collections import Counter

from app.topic.smart_story import SmartStoryEngine


class FakeCandidate:
    def __init__(self, topic, score, indicator_code):
        self.topic = topic
        self.score = score
        self.provider_id = "test"
        self.indicator_code = indicator_code
        self.story_type = "fastest_growth"


# Simulate the real scenario: population generates MANY high-scoring
# candidates across all story types, dominating the top 5.
candidates = [
    # Population dominates the top 5 (7 population candidates)
    FakeCandidate("Population: Fastest Growth", 95.0, "SP.POP.TOTL"),
    FakeCandidate("Population: Biggest Declines", 93.0, "SP.POP.TOTL"),
    FakeCandidate("Population: Rank Climbers", 91.0, "SP.POP.TOTL"),
    FakeCandidate("Population: Current Leader", 90.0, "SP.POP.TOTL"),
    FakeCandidate("Population: Leader Challenge", 89.0, "SP.POP.TOTL"),
    FakeCandidate("Population: Ranking Drops", 88.0, "SP.POP.TOTL"),
    FakeCandidate("Population: Trend", 87.0, "SP.POP.TOTL"),
    # Other topics with lower scores
    FakeCandidate("GDP Per Capita: Rank Climbers", 80.0, "NY.GDP.PCAP.CD"),
    FakeCandidate("CO2 Emissions: Biggest Declines", 78.0, "co2_emissions"),
    FakeCandidate("Life Expectancy: Current Leader", 75.0, "SP.DYN.LE00.IN"),
    FakeCandidate("Internet Users: Fastest Growth", 72.0, "IT.NET.USER.ZS"),
]

# Run selection 200 times and count how often each topic wins
results = Counter()
for _ in range(200):
    chosen = SmartStoryEngine._select_candidate_with_randomness(candidates)
    results[chosen.topic] += 1

print("\n=== Random Topic Selection Distribution (200 runs) ===")
for topic, count in sorted(results.items(), key=lambda x: -x[1]):
    pct = (count / 200) * 100
    print(f"  {pct:5.1f}%  {topic}")

unique = len(results)
print(f"\nUnique topics selected: {unique} / 5 distinct indicators")

# Count population vs non-population
population = sum(
    count for topic, count in results.items() if "Population" in topic
)
non_population = 200 - population
print(f"Population selections: {population} / 200 runs")
print(f"Non-population selections: {non_population} / 200 runs")

# Verify diversity: at least 3 distinct indicators should be selected
assert unique >= 3, f"FAIL: Only {unique} distinct topics selected!"
assert non_population >= 50, (
    f"FAIL: Non-population topics selected too rarely ({non_population}/200)."
)
print("\nPASS: Diverse topic selection works even when population dominates.")