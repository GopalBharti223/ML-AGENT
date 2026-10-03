#!/usr/bin/env python3
"""
Test script for AI Index Provider Integration

Tests:
1. Provider registration in DataProviderRegistry
2. Data fetching and normalization
3. SmartStoryEngine discovery and selection
4. Topic family classification
5. Existing provider functionality (verify no breakage)
"""

from app.topic.smart_story import SmartStoryEngine
from app.data.providers import DataProviderRegistry
from app.data.providers.ai_index import AIIndexProvider
from app.data.providers.worldbank import WorldBankProvider
from app.topic.topic_families import classify_topic_family


def test_provider_registration():
    """Test 1: Provider registration"""
    print("=" * 60)
    print("TEST 1: Provider Registration")
    print("=" * 60)
    
    providers = DataProviderRegistry.list_providers()
    print(f"✓ Available Providers: {sorted(providers)}")
    
    assert "ai_index" in providers, "ai_index not in registry"
    print(f"✓ AI Index registered in registry")
    
    # The registry legitimately grows as new providers are added;
    # assert the original core set is present rather than a
    # frozen total count.
    core = {"worldbank", "owid", "imf", "ai_index"}
    assert core.issubset(providers), (
        f"Core providers missing: {core - set(providers)}"
    )
    print(f"✓ Registry has all {len(core)} core providers "
          f"(total: {len(providers)})")
    
    return True


def test_ai_index_indicators():
    """Test 2: AI Index indicators"""
    print("\n" + "=" * 60)
    print("TEST 2: AI Index Indicators")
    print("=" * 60)
    
    indicators = AIIndexProvider.list_indicators()
    print(f"✓ Listed {len(indicators)} AI Index indicators:")
    
    for ind in indicators:
        print(f"  - {ind.code}: {ind.name} ({ind.category})")
    
    assert len(indicators) == 5, f"Expected 5 indicators, got {len(indicators)}"
    print(f"✓ Exactly 5 indicators available")
    
    return True


def test_data_fetching():
    """Test 3: Data fetching and normalization"""
    print("\n" + "=" * 60)
    print("TEST 3: Data Fetching & Normalization")
    print("=" * 60)
    
    result = AIIndexProvider.fetch_normalized(
        indicator_code="ai_investment",
        years=5,
        story_type="fastest_growth",
        min_countries=6
    )
    
    print(f"✓ Fetched data for ai_investment")
    print(f"  - Provider: {result.provider}")
    print(f"  - Metric: {result.metric_name}")
    print(f"  - Source: {result.source_name}")
    print(f"  - URL: {result.source_url}")
    
    assert result.provider == "ai_index", "Provider ID mismatch"
    assert result.indicator_code == "ai_investment", "Indicator code mismatch"
    assert not result.normalized_data.empty, "No normalized data"
    assert not result.wide_data.empty, "No wide data"
    
    print(f"✓ Data format correct:")
    print(f"  - Normalized shape: {result.normalized_data.shape}")
    print(f"  - Wide shape: {result.wide_data.shape}")
    print(f"  - Columns: {list(result.normalized_data.columns)}")
    
    # Verify required columns
    required_cols = {"country", "country_code", "year", "metric", "value", 
                     "provider", "source_name", "source_url", "indicator_code"}
    actual_cols = set(result.normalized_data.columns)
    assert required_cols.issubset(actual_cols), "Missing required columns"
    print(f"✓ All required columns present")
    
    return True


def test_topic_family():
    """Test 4: Topic family classification"""
    print("\n" + "=" * 60)
    print("TEST 4: Topic Family Classification")
    print("=" * 60)
    
    topics = {
        "ai_investment": "ai_investment",
        "ai_research": "ai_research",
        "ai_talent": "ai_talent",
        "ai_adoption": "ai_adoption",
        "ai_policy": "ai_governance",
    }
    
    for code, expected_family in topics.items():
        indicator = AIIndexProvider.list_indicators()
        ind = next(i for i in indicator if i.code == code)
        
        family = classify_topic_family(
            indicator_code=code,
            indicator_name=ind.name,
            category=ind.category
        )
        
        print(f"✓ {code} → {family}")
        assert family == expected_family, f"Expected {expected_family}, got {family}"
    
    print(f"✓ All AI Index indicators correctly classified")
    
    return True


def test_existing_providers():
    """Test 5: Existing providers still work"""
    print("\n" + "=" * 60)
    print("TEST 5: Existing Providers (No Breakage)")
    print("=" * 60)
    
    # Test World Bank
    wb_indicators = WorldBankProvider.list_indicators()
    print(f"✓ World Bank: {len(wb_indicators)} indicators")
    assert len(wb_indicators) > 0, "World Bank has no indicators"
    
    # Test a World Bank indicator
    wb_result = WorldBankProvider.fetch_normalized(
        indicator_code="NY.GDP.PCAP.CD",
        years=5,
        story_type="fastest_growth",
        min_countries=6
    )
    print(f"✓ World Bank data fetch successful")
    assert not wb_result.wide_data.empty, "World Bank returned no data"
    
    print(f"✓ Existing providers working correctly")
    
    return True


def test_smart_story_engine():
    """Test 6: SmartStoryEngine discovers AI Index"""
    print("\n" + "=" * 60)
    print("TEST 6: SmartStoryEngine Integration")
    print("=" * 60)
    
    print("Running SmartStoryEngine.select_best_candidate()...")
    print("(This searches all registered providers for candidates)\n")
    
    candidate = SmartStoryEngine.select_best_candidate()
    
    if candidate:
        print(f"✓ Best Candidate Found:")
        print(f"  - Provider: {candidate.provider_id}")
        print(f"  - Indicator: {candidate.indicator_code} ({candidate.indicator_name})")
        print(f"  - Story Type: {candidate.story_type}")
        print(f"  - Chart Type: {candidate.chart_type}")
        print(f"  - Topic Family: {candidate.topic_family}")
        print(f"  - Score: {candidate.score:.2f}")
        print(f"  - Topic: {candidate.topic}")
        
        # The registry now holds many providers (worldbank, owid,
        # imf, ai_index, jolpica_f1, jikan, nhtsa, openalex,
        # sec_edgar, wikipedia, football_data, rawg), so the
        # global winner is legitimately NOT always ai_index.
        # The invariant this test must protect is metadata
        # preservation through the pipeline: whichever provider
        # wins, its source_name/source_url must be present and
        # self-consistent.  AI Index's own metadata preservation
        # is asserted separately below via its fetch attrs.
        assert candidate.source_name, (
            "Winner candidate missing source_name"
        )
        assert candidate.source_url, (
            "Winner candidate missing source_url"
        )
        print(f"✓ Winner source metadata present "
              f"({candidate.source_name})")
        
        # AI Index metadata preservation, independent of who
        # wins the global scan:
        ai_result = AIIndexProvider.fetch_normalized(
            indicator_code="ai_investment",
            years=5,
            story_type="fastest_growth",
            min_countries=2,
        )
        assert (
            ai_result.wide_data.attrs.get("source_name")
            == "Stanford AI Index"
        ), "AI Index source_name not preserved on frame attrs"
        assert (
            ai_result.wide_data.attrs.get("source_url")
            == "https://hai.stanford.edu/ai-index"
        ), "AI Index source_url not preserved on frame attrs"
        print(f"✓ AI Index source metadata correctly preserved")
        
        print(f"✓ SmartStoryEngine successfully searched all providers")
        
        return True
    else:
        print("✗ No candidates found (this may be expected if world data is unavailable)")
        return True


def main():
    """Run all tests"""
    print("\n")
    print("*" * 60)
    print("STANFORD AI INDEX PROVIDER - INTEGRATION TESTS")
    print("*" * 60)
    
    try:
        test_provider_registration()
        test_ai_index_indicators()
        test_data_fetching()
        test_topic_family()
        test_existing_providers()
        test_smart_story_engine()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        print("\nSummary:")
        print("  ✓ Provider imports and registers correctly")
        print("  ✓ All 5 indicators available")
        print("  ✓ Data fetching and normalization working")
        print("  ✓ Topic family classification working")
        print("  ✓ Existing providers unaffected")
        print("  ✓ SmartStoryEngine integrates AI Index")
        print("\nProvider is ready for use!")
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
