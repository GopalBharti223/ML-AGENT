"""Tests for curated viral datasets and ViralTopicsProvider integration."""

import pytest
import pandas as pd
from app.data.static.viral_datasets import VIRAL_INDICATORS
from app.data.providers.viral_topics import ViralTopicsProvider
from app.topic.manual_topic import ManualTopicEngine


def test_viral_indicators_integrity():
    """All 14 viral indicators must have non-empty metadata, years, and data."""
    assert len(VIRAL_INDICATORS) >= 14
    for code, info in VIRAL_INDICATORS.items():
        assert "name" in info and len(info["name"]) > 5
        assert "category" in info
        assert "source_name" in info
        assert "source_url" in info
        assert "metric_name" in info
        assert "years" in info and len(info["years"]) >= 4
        assert "data" in info and len(info["data"]) >= 4
        # Every entity must have the exact same length as years
        expected_len = len(info["years"])
        for entity, series in info["data"].items():
            assert len(series) == expected_len, f"{code}: {entity} has length {len(series)}, expected {expected_len}"


def test_viral_provider_fetch_normalized():
    """Provider fetch_normalized must return valid Wide and Normalized DataFrames."""
    for code in VIRAL_INDICATORS.keys():
        result = ViralTopicsProvider.fetch_normalized(code)
        assert result.provider == "viral_topics"
        assert result.indicator_code == code
        assert isinstance(result.wide_data, pd.DataFrame)
        assert isinstance(result.normalized_data, pd.DataFrame)
        assert not result.wide_data.empty
        assert not result.normalized_data.empty
        assert not result.normalized_data["value"].isna().any()
        assert set(result.normalized_data.columns).issuperset({
            "country", "country_code", "year", "metric", "value",
            "provider", "source_name", "source_url", "indicator_code"
        })


def test_manual_topic_resolution():
    """Key viral search phrases must resolve to viral_topics indicators."""
    test_queries = {
        "gta sales": "gta_sales",
        "best selling games": "all_time_games_sales",
        "roblox": "most_played_games_mau",
        "consoles": "all_time_gaming_consoles",
        "billionaires": "top_billionaires_net_worth",
        "market cap": "top_companies_market_cap",
        "mrbeast": "youtube_subscribers_race",
        "ronaldo": "football_goals_ronaldo_vs_messi",
        "virat kohli": "cricket_international_runs",
        "tesla": "tesla_vs_byd_ev_sales",
        "smartphones": "smartphone_market_shipments",
        "tiktok": "social_media_active_users",
        "box office": "all_time_box_office",
        "programming": "programming_languages_race",
        "python": "programming_languages_race",
        "browser wars": "browser_wars_race",
        "mobile os": "mobile_os_market_share",
        "android": "mobile_os_market_share",
        "fastest apps": "fastest_apps_100m_users",
        "electric cars": "tesla_vs_byd_ev_sales",
        "xiaomi su7": "tesla_vs_byd_ev_sales",
        "nvidia": "top_companies_market_cap",
        "oil": "global_oil_reserves",
        "oil reserves": "global_oil_reserves",
        "crude oil": "global_oil_reserves",
    }
    for query, expected_code in test_queries.items():
        matches = ManualTopicEngine.resolve_keyword(query)
        assert len(matches) > 0, f"Query '{query}' returned no matches"
        matched_codes = [ind.code for p, ind in matches]
        assert expected_code in matched_codes, f"Query '{query}' expected '{expected_code}', got {matched_codes}"


def test_end_to_end_topic_generation():
    """ManualTopicEngine can generate a complete topic_data candidate."""
    topic_data = ManualTopicEngine.generate_manual_topic("gta sales")
    assert topic_data is not None
    assert topic_data["provider_id"] == "viral_topics"
    assert topic_data["indicator_code"] == "gta_sales"
    assert topic_data["chart_type"] in ("bar_race", "bar_static", "multi_line", "slope", "area", "top5_change", "vertical_duel")
    assert len(topic_data["topic"]) > 0
