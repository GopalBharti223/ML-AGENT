"""Verify hot topic boosting and chart type distribution."""
from collections import Counter
import pandas as pd
from app.topic.topic_distribution import (
    HOT_TOPIC_COUNTRIES, HOT_TOPIC_EXTRA_BOOST, MAX_BOOST,
    TopicDistributionPreference,
)
from app.topic.chart_selector import ChartSelector
from app.visuals.scene_engine import VisualEngine


def test_hot_topics():
    print("TEST 1: Hot topics identified")
    for c in ["United States", "USA", "India", "China"]:
        assert TopicDistributionPreference.is_hot_topic(c), f"{c} should be hot"
    assert not TopicDistributionPreference.is_hot_topic("Ukraine")
    assert not TopicDistributionPreference.is_hot_topic("Iran")
    assert not TopicDistributionPreference.is_hot_topic("Brazil")
    print(f"  OK: {sorted(HOT_TOPIC_COUNTRIES)}")


def test_hot_boost():
    print("TEST 2: Hot topic boost")
    h = []
    usa = TopicDistributionPreference.distribution_multiplier("United States", h)
    ind = TopicDistributionPreference.distribution_multiplier("India", h)
    bra = TopicDistributionPreference.distribution_multiplier("Brazil", h)
    # USA is underrepresented (target 15%, current 0%):
    # deficit 0.15 * BOOST_SCALE 0.25 = 0.0375, capped at COUNTRY_MAX_BOOSTS["usa"] 0.06
    assert usa == 1.0 + min(0.06, 0.15 * 0.25), f"USA: {usa}"
    # India is underrepresented (target 30%, current 0%):
    # deficit 0.30 * BOOST_SCALE 0.25 = 0.075, capped at COUNTRY_MAX_BOOSTS["india"] 0.08
    assert ind == 1.0 + min(0.08, 0.30 * 0.25), f"India: {ind}"
    # Brazil is "other" (target 18%, current 0%):
    # deficit 0.18 * BOOST_SCALE 0.25 = 0.045, capped at OTHER_BOOST 0.02
    assert bra == 1.0 + 0.02, f"Brazil: {bra}"
    print(f"  USA={usa:.4f} India={ind:.4f} Brazil={bra:.4f}")


def test_chart_dist():
    print("TEST 3: Chart distribution")
    data = pd.DataFrame({2015: [1, 2, 3], 2016: [1.5, 2.5, 3.5], 2017: [2, 3, 4]},
                         index=["A", "B", "C"])
    m = {"number_of_valid_years": 3, "number_of_valid_countries": 3,
         "rank_change": 1, "trend_strength": 0.5, "leader_separation": 0.5,
         "percentage_change": 0.1}
    r = Counter()
    for _ in range(1000):
        r[ChartSelector.select_chart("fastest_growth", m, data)] += 1
    t = sum(r.values())
    bar = (r.get("bar_race", 0) + r.get("top5_change", 0)) / t * 100
    area = r.get("area", 0) / t * 100
    line = r.get("line", 0) / t * 100
    print(f"  bar={bar:.1f}% area={area:.1f}% line={line:.1f}%")
    assert 60 <= bar <= 80, f"bar {bar}"
    assert 10 <= area <= 20, f"area {area}"
    assert 2 <= line <= 8, f"line {line}"


def test_area_renderer():
    print("TEST 4: Area renderer registered")
    assert hasattr(VisualEngine, "render_area")
    import inspect
    src = inspect.getsource(VisualEngine.render_scenes)
    assert '"area"' in src
    print("  OK")


if __name__ == "__main__":
    test_hot_topics()
    test_hot_boost()
    test_chart_dist()
    test_area_renderer()
    print("\nALL TESTS PASSED")