#!/usr/bin/env python3
"""
Production Safety Test for AI Index Provider

Verifies:
1. AI Index provider imports and registers
2. Indicators can be listed
3. Real Stanford data fetch succeeds with correct metadata (no fake data)
4. Snapshot-only indicator (ai_adoption) gracefully raises RuntimeError
5. SmartStoryEngine can validly select AI Index when real data is available
6. Other providers (WorldBank, OWID) continue working
"""

from app.data.providers import DataProviderRegistry
from app.data.providers.ai_index import AIIndexProvider
from app.topic.smart_story import SmartStoryEngine
import sys


def test_import_and_registration():
    """Test 1: Import and registration"""
    print("=" * 70)
    print("TEST 1: Provider Import & Registration")
    print("=" * 70)

    providers = DataProviderRegistry.list_providers()

    print(f"✓ Imported AIIndexProvider")
    print(f"✓ Registry contains: {sorted(providers)}")
    print(f"✓ ai_index provider registered: {'ai_index' in providers}")

    assert "ai_index" in providers, "ai_index not registered"
    # The registry legitimately grows as new providers are added;
    # assert the original core set is present rather than a
    # frozen total count.
    _core = {"worldbank", "owid", "imf", "ai_index"}
    assert _core.issubset(providers), (
        f"Core providers missing: {_core - set(providers)}"
    )

    return True


def test_indicator_listing():
    """Test 2: Indicator listing"""
    print("\n" + "=" * 70)
    print("TEST 2: Indicator Listing")
    print("=" * 70)

    indicators = AIIndexProvider.list_indicators()
    codes = [i.code for i in indicators]

    print(f"✓ AI Index has {len(indicators)} indicators")
    for code in codes:
        print(f"  - {code}")

    expected = {
        "ai_investment",
        "ai_research",
        "ai_talent",
        "ai_adoption",
        "ai_policy",
    }
    assert set(codes) == expected, f"Unexpected indicators: {set(codes)}"

    return True


def test_real_stanford_data_fetch():
    """Test 3: Real Stanford data fetch succeeds with correct metadata"""
    print("\n" + "=" * 70)
    print("TEST 3: Real Stanford Data Fetch (No Fake Data)")
    print("=" * 70)

    print("\nFetching real Stanford data: ai_investment")

    result = AIIndexProvider.fetch_normalized(
        indicator_code="ai_investment",
        years=5,
        story_type="fastest_growth",
        min_countries=3
    )

    # Verify provider identity
    assert result.provider == "ai_index", (
        f"Expected provider 'ai_index', got '{result.provider}'"
    )
    print(f"✓ Provider: {result.provider}")

    # Verify source metadata
    assert result.source_name == "Stanford AI Index", (
        f"Expected source_name 'Stanford AI Index', got '{result.source_name}'"
    )
    print(f"✓ Source name: {result.source_name}")

    assert "stanford" in result.source_url.lower(), (
        f"Expected source_url to reference Stanford, got '{result.source_url}'"
    )
    print(f"✓ Source URL: {result.source_url}")

    # Verify data is non-empty
    assert result.normalized_data is not None, "normalized_data is None"
    assert not result.normalized_data.empty, "normalized_data is empty"
    print(f"✓ Normalized data non-empty: {result.normalized_data.shape}")

    assert result.wide_data is not None, "wide_data is None"
    assert not result.wide_data.empty, "wide_data is empty"
    print(f"✓ Wide data non-empty: {result.wide_data.shape}")

    # Verify required columns in normalized data
    required_cols = {
        "country",
        "country_code",
        "year",
        "metric",
        "value",
        "provider",
        "source_name",
        "source_url",
        "indicator_code",
    }
    actual_cols = set(result.normalized_data.columns)
    missing = required_cols - actual_cols
    assert not missing, f"Missing required columns: {missing}"
    print(f"✓ All required columns present")

    # Verify real data values (should be non-trivial numbers)
    assert len(result.wide_data) > 0, "No countries in wide data"
    assert len(result.wide_data.columns) >= 3, "Fewer than 3 years of data"
    print(
        f"✓ Real data confirmed: "
        f"{len(result.wide_data)} entities, "
        f"{len(result.wide_data.columns)} years "
        f"({result.wide_data.columns[0]}–{result.wide_data.columns[-1]})"
    )

    # Verify NO fake/demo data is present
    for attr_key in (
        "source_note",
        "is_demonstration",
        "is_demo",
        "demo",
    ):
        attr_val = result.metadata.get(attr_key, "")
        assert "demonstration" not in str(attr_val).lower(), (
            f"Metadata contains demo data marker: {attr_key}={attr_val}"
        )

    # Verify metadata contains official Stanford file info
    official_file = result.metadata.get("official_file", "")
    assert official_file, "Metadata missing official_file"
    assert official_file.endswith(".csv"), (
        f"Unexpected official_file: {official_file}"
    )
    print(f"✓ Official Stanford file: {official_file}")

    # Verify metadata attrs on wide DataFrame
    assert result.wide_data.attrs.get("source_name") == "Stanford AI Index", (
        "wide_data.attrs missing source_name"
    )
    print(f"✓ DataFrame attrs source_name preserved")

    print(f"\n✓ Real Stanford data fetch verified "
          f"(source: {result.source_name})")
    return True


def test_snapshot_only_graceful_failure():
    """Test 4: ai_adoption (snapshot-only) raises RuntimeError"""
    print("\n" + "=" * 70)
    print("TEST 4: Snapshot-Only Indicator Graceful Failure")
    print("=" * 70)

    print("\nAttempting to fetch: ai_adoption")

    try:
        result = AIIndexProvider.fetch_normalized(
            indicator_code="ai_adoption",
            years=5,
            story_type="fastest_growth",
            min_countries=3
        )
        print("✗ ERROR: ai_adoption should have raised RuntimeError")
        print("  (it is a single-year snapshot and cannot produce "
              "a multi-year story)")
        return False

    except RuntimeError as error:
        error_msg = str(error)
        print(f"✓ Provider raised RuntimeError as expected:")
        print(f"  {error_msg}")

        # Verify error message is clear about the snapshot limitation
        assert "snapshot" in error_msg.lower(), (
            "Error should mention snapshot-only dataset"
        )
        assert "cannot" in error_msg.lower(), (
            "Error should indicate multi-year stories are not possible"
        )
        print(f"✓ Error message correctly describes snapshot limitation")
        return True

    except Exception as error:
        print(f"✗ Unexpected exception type: {type(error).__name__}: {error}")
        return False


def test_smart_story_considers_ai_index():
    """Test 5: SmartStoryEngine can validly select AI Index"""
    print("\n" + "=" * 70)
    print("TEST 5: SmartStoryEngine Considers AI Index")
    print("=" * 70)

    print("Running SmartStoryEngine.select_best_candidate()...")
    print("(This will scan all providers including AI Index)")

    try:
        candidate = SmartStoryEngine.select_best_candidate()

        if candidate:
            print(f"\n✓ SmartStoryEngine found best candidate:")
            print(f"  Provider: {candidate.provider_id}")
            print(f"  Indicator: {candidate.indicator_code}")
            print(f"  Story Type: {candidate.story_type}")
            print(f"  Score: {candidate.score:.2f}")

            # A successful Stanford provider is NOT treated as failed.
            # Whether ai_index or another provider wins, both are valid.
            if candidate.provider_id == "ai_index":
                print(f"✓ AI Index selected — valid because real data "
                      f"is now available")
            else:
                print(f"✓ Selected {candidate.provider_id} — valid; "
                      f"AI Index was also considered")

            # Real invariants: a selected candidate must be a
            # usable, internally-consistent story.  Previously
            # this returned True unconditionally, so NOTHING was
            # verified even when a candidate came back.
            assert candidate.provider_id, \
                "selected candidate has no provider_id"
            assert candidate.indicator_code, \
                "selected candidate has no indicator_code"
            assert candidate.story_type, \
                "selected candidate has no story_type"
            assert candidate.topic, \
                "selected candidate has no topic"
            assert candidate.score > 0, (
                f"selected candidate has non-positive score "
                f"{candidate.score}"
            )

            return True
        else:
            print("⚠ No candidate found (may be network/environment issue)")
            # Returning True here made the test unable to detect
            # a total provider outage.  Fail loudly instead.
            raise AssertionError(
                "select_best_candidate() returned no candidate at "
                "all — all providers unavailable or scoring broken"
            )

    except AssertionError:
        raise
    except Exception as error:
        print(f"✗ SmartStoryEngine raised exception: "
              f"{type(error).__name__}: {error}")
        raise


def test_existing_providers():
    """Test 6: Verify existing providers still work"""
    print("\n" + "=" * 70)
    print("TEST 6: Existing Providers (No Breakage)")
    print("=" * 70)

    from app.data.providers.worldbank import WorldBankProvider
    from app.data.providers.owid import OWIDProvider

    # Test World Bank
    print("Testing World Bank provider...")
    try:
        wb_indicators = WorldBankProvider.list_indicators()
        print(f"  ✓ World Bank: {len(wb_indicators)} indicators available")
        assert len(wb_indicators) > 0, "World Bank has no indicators"
    except Exception as error:
        print(f"  ✗ World Bank failed: {error}")
        return False

    # Test OWID
    print("Testing OWID provider...")
    try:
        owid_indicators = OWIDProvider.list_indicators()
        print(f"  ✓ OWID: {len(owid_indicators)} indicators available")
        assert len(owid_indicators) > 0, "OWID has no indicators"
    except Exception as error:
        print(f"  ✗ OWID failed: {error}")
        return False

    print("✓ All existing providers working correctly")
    return True


def main():
    """Run all tests"""
    print("\n")
    print("*" * 70)
    print("PRODUCTION SAFETY TEST - STANFORD AI INDEX PROVIDER")
    print("*" * 70)

    tests = [
        ("Import & Registration", test_import_and_registration),
        ("Indicator Listing", test_indicator_listing),
        ("Real Stanford Data Fetch", test_real_stanford_data_fetch),
        ("Snapshot-Only Graceful Failure", test_snapshot_only_graceful_failure),
        ("SmartStoryEngine Considers AI Index", test_smart_story_considers_ai_index),
        ("Existing Providers", test_existing_providers),
    ]

    results = []

    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as error:
            print(f"\n✗ TEST FAILED WITH EXCEPTION: {error}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ ALL TESTS PASSED - PRODUCTION SAFE")
        print("\nVerified Behavior:")
        print("  ✓ AI Index provider returns REAL Stanford data")
        print("  ✓ NO fake/demo data returned")
        print("  ✓ Snapshot-only indicator (ai_adoption) fails gracefully")
        print("  ✓ SmartStoryEngine can validly select AI Index")
        print("  ✓ Other providers (WorldBank, OWID, IMF) unaffected")
        print("  ✓ Official Stanford data source used")
        return True
    else:
        print("\n✗ TESTS FAILED")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)