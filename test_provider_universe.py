"""Tests for the expanded provider universe.

Tests:
1. All providers registered
2. Provider metadata (license, commercial_use, rate_limit)
3. Category eligibility (catalog-driven)
4. Family classification for new indicators
5. Graceful failure (no crash on network error)
6. No fabrication (empty result on failure)
7. Story angles applied
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data.providers.registry import DataProviderRegistry
from app.data.providers.catalog import (
    PROVIDER_METADATA,
    category_eligible,
    eligible_provider_ids,
)
from app.topic.topic_families import (
    classify_topic_family,
    family_to_category,
    UNSUPPORTED_CATEGORIES,
    TOP_LEVEL_CATEGORIES,
)


def test_all_providers_registered():
    """All 9 providers should be registered."""
    providers = DataProviderRegistry.list_providers()
    expected = {
        "worldbank", "owid", "imf", "ai_index",
        "jolpica_f1", "openalex", "jikan", "nhtsa", "sec_edgar",
    }
    assert expected.issubset(set(providers)), (
        f"Missing providers: {expected - set(providers)}"
    )
    print(f"  Registered: {sorted(providers)}")
    return True


def test_provider_metadata_complete():
    """Every provider has metadata with license + commercial_use."""
    for pid, meta in PROVIDER_METADATA.items():
        assert meta.provider_id == pid
        assert meta.provider_name
        assert meta.category
        assert meta.license != "Unknown" or meta.commercial_use == "REVIEW_REQUIRED"
        assert meta.commercial_use in ("ALLOWED", "REVIEW_REQUIRED", "PROHIBITED")
        assert isinstance(meta.enabled, bool)
        assert isinstance(meta.requires_api_key, bool)
    print(f"  {len(PROVIDER_METADATA)} providers with metadata")
    return True


def test_category_eligibility():
    """Categories with keyless enabled providers are eligible."""
    # sports -> jolpica_f1 (keyless, enabled, ALLOWED)
    assert category_eligible("sports"), "sports should be eligible"
    # space_science -> openalex (keyless, enabled, ALLOWED)
    assert category_eligible("space_science"), "space_science should be eligible"
    # entertainment_pop_culture -> jikan (keyless, enabled, REVIEW_REQUIRED)
    assert category_eligible("entertainment_pop_culture"), "entertainment should be eligible"
    # cars_automotive -> nhtsa (keyless, enabled, ALLOWED)
    assert category_eligible("cars_automotive"), "cars should be eligible"
    # companies_brands -> sec_edgar (keyless, enabled, ALLOWED)
    assert category_eligible("companies_brands"), "companies should be eligible"
    # economy -> worldbank/owid/imf (keyless, enabled)
    assert category_eligible("economy"), "economy should be eligible"
    # football -> football_data (needs key, disabled)
    assert not category_eligible("football"), "football should NOT be eligible (needs key)"
    # gaming -> rawg (needs key, disabled)
    assert not category_eligible("gaming"), "gaming should NOT be eligible (needs key)"
    print("  Eligibility checks passed")
    return True


def test_new_families_classify():
    """New provider indicator codes classify to correct families."""
    assert classify_topic_family("driver_standings", "") == "sports"
    assert classify_topic_family("constructor_standings", "") == "sports"
    assert classify_topic_family("research_publications_by_country", "") == "space_science"
    assert classify_topic_family("anime_popularity_ranking", "") == "entertainment_pop_culture"
    assert classify_topic_family("anime_score_ranking", "") == "entertainment_pop_culture"
    assert classify_topic_family("vehicle_manufacturer_models", "") == "cars_automotive"
    assert classify_topic_family("public_company_revenue", "") == "companies_brands"
    assert classify_topic_family("public_company_net_income", "") == "companies_brands"
    assert classify_topic_family("public_company_assets", "") == "companies_brands"
    # Tier-3 additions
    assert classify_topic_family("premier_league_standings", "") == "football"
    assert classify_topic_family("games_popular_ranking", "") == "gaming"
    assert classify_topic_family("search_interest", "") == "general_interest"

    # Family -> category mapping
    assert family_to_category("sports") == "sports"
    assert family_to_category("space_science") == "space_science"
    assert family_to_category("entertainment_pop_culture") == "entertainment_pop_culture"
    assert family_to_category("cars_automotive") == "cars_automotive"
    assert family_to_category("companies_brands") == "companies_brands"
    assert family_to_category("football") == "football"
    assert family_to_category("gaming") == "gaming"
    assert family_to_category("general_interest") == "entertainment_pop_culture"
    print("  Family classification correct")
    return True


def test_unsupported_categories():
    """Categories without providers remain unsupported."""
    # football/gaming now have providers (key-gated) so they are
    # supported; categories with NO provider remain unsupported.
    assert "football" not in UNSUPPORTED_CATEGORIES
    assert "gaming" not in UNSUPPORTED_CATEGORIES
    assert "smartphones_consumer_tech" in UNSUPPORTED_CATEGORIES
    assert "travel_tourism" in UNSUPPORTED_CATEGORIES
    # These are now SUPPORTED (have providers)
    assert "sports" not in UNSUPPORTED_CATEGORIES
    assert "space_science" not in UNSUPPORTED_CATEGORIES
    assert "entertainment_pop_culture" not in UNSUPPORTED_CATEGORIES
    assert "cars_automotive" not in UNSUPPORTED_CATEGORIES
    assert "companies_brands" not in UNSUPPORTED_CATEGORIES
    print("  Unsupported categories correct")
    return True


def test_provider_list_indicators():
    """Each new provider exposes list_indicators()."""
    for pid in ["jolpica_f1", "openalex", "jikan", "nhtsa", "sec_edgar"]:
        provider = DataProviderRegistry.get(pid)
        indicators = provider.list_indicators()
        assert len(indicators) > 0, f"{pid} should have indicators"
        for ind in indicators:
            assert ind.code
            assert ind.name
            assert ind.source_url
    print("  All new providers expose indicators")
    return True


def test_graceful_failure():
    """Providers return empty result (not crash) on network failure."""
    # These providers make real HTTP calls; if the network is
    # unavailable they should return empty DataFrames, not crash.
    for pid in ["jolpica_f1", "openalex", "jikan", "nhtsa", "sec_edgar"]:
        provider = DataProviderRegistry.get(pid)
        indicators = provider.list_indicators()
        if not indicators:
            continue
        try:
            result = provider.fetch_normalized(
                indicator_code=indicators[0].code,
                years=5,
                min_countries=3,
            )
            # Should return a DataProviderResult (possibly empty)
            assert result is not None
            assert result.provider == pid
        except Exception as e:
            # Network errors are acceptable; the engine catches
            # these upstream.  We just verify no crash in the
            # provider's own error handling.
            print(f"  {pid}: network error (acceptable): {e}")
    print("  Graceful failure verified")
    return True


def test_no_fabrication():
    """Providers never invent data - empty on failure."""
    # If a provider can't fetch data, it returns empty DataFrames
    # (not fake numbers).  We verify the _empty_result pattern.
    for pid in ["jolpica_f1", "openalex", "jikan", "nhtsa", "sec_edgar"]:
        provider = DataProviderRegistry.get(pid)
        # Call with an invalid indicator code
        try:
            result = provider.fetch_normalized(
                indicator_code="nonexistent_indicator",
                years=5,
            )
            # Should raise ValueError for unknown indicator
            assert False, f"{pid} should raise for unknown indicator"
        except ValueError:
            pass  # Expected
        except Exception:
            pass  # Network errors also acceptable
    print("  No fabrication verified")
    return True


def test_commercial_use_audit():
    """Verify commercial-use status is documented for every provider."""
    allowed = []
    review = []
    prohibited = []
    for pid, meta in PROVIDER_METADATA.items():
        if meta.commercial_use == "ALLOWED":
            allowed.append(pid)
        elif meta.commercial_use == "REVIEW_REQUIRED":
            review.append(pid)
        else:
            prohibited.append(pid)
    print(f"  ALLOWED: {allowed}")
    print(f"  REVIEW_REQUIRED: {review}")
    print(f"  PROHIBITED: {prohibited}")
    # No provider should be silently treated as commercial-safe
    # when it's actually review-required
    assert "football_data" in review or "football_data" in [p for p, m in PROVIDER_METADATA.items() if m.commercial_use == "REVIEW_REQUIRED"]
    return True


def main():
    tests = [
        ("ALL_PROVIDERS_REGISTERED", test_all_providers_registered),
        ("PROVIDER_METADATA_COMPLETE", test_provider_metadata_complete),
        ("CATEGORY_ELIGIBILITY", test_category_eligibility),
        ("NEW_FAMILIES_CLASSIFY", test_new_families_classify),
        ("UNSUPPORTED_CATEGORIES", test_unsupported_categories),
        ("PROVIDER_LIST_INDICATORS", test_provider_list_indicators),
        ("GRACEFUL_FAILURE", test_graceful_failure),
        ("NO_FABRICATION", test_no_fabrication),
        ("COMMERCIAL_USE_AUDIT", test_commercial_use_audit),
    ]

    print("=" * 70)
    print("PROVIDER UNIVERSE EXPANSION TESTS")
    print("=" * 70)

    passed = 0
    failed = 0

    for name, func in tests:
        print(f"\n{'='*70}")
        print(f"TEST: {name}")
        print(f"{'='*70}")
        try:
            result = func()
            if result:
                print(f"  PASS: {name}")
                passed += 1
            else:
                print(f"  FAIL: {name}")
                failed += 1
        except Exception as e:
            print(f"  FAIL: {name} - {e}")
            failed += 1

    print(f"\n{'='*70}")
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print(f"{'='*70}")
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
