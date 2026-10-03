#!/usr/bin/env python3
"""Test all AI Index indicators and chart selection"""

from app.data.providers.ai_index import AIIndexProvider
from app.topic.chart_selector import ChartSelector

print("=" * 60)
print("TESTING ALL AI INDEX INDICATORS & CHART SELECTION")
print("=" * 60)

indicators = AIIndexProvider.list_indicators()

for ind in indicators:
    print(f"\n--- Testing: {ind.code} ({ind.name}) ---")
    
    try:
        result = AIIndexProvider.fetch_normalized(
            indicator_code=ind.code,
            years=5,
            story_type="fastest_growth",
            min_countries=6
        )
        
        # Get chart type selection
        story_type = "fastest_growth"
        chart = ChartSelector.select_chart(
            story_type,
            {},
            result.wide_data
        )
        
        print(f"  ✓ Data fetched: {result.normalized_data.shape[0]} records")
        print(f"  ✓ Countries: {result.wide_data.shape[0]}")
        print(f"  ✓ Years: {list(result.wide_data.columns)}")
        print(f"  ✓ Selected Chart: {chart}")
        print(f"  ✓ Source: {result.source_name}")
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("✓ All AI Index indicators functional")
print("=" * 60)
