#!/usr/bin/env python3
"""Final verification of all providers"""

from app.data.providers import DataProviderRegistry

print("=" * 60)
print("FINAL VERIFICATION - ALL PROVIDERS")
print("=" * 60)

providers = DataProviderRegistry.list_providers()
print(f"\nRegistered Providers: {sorted(providers)}\n")

for prov_id in sorted(providers):
    prov = DataProviderRegistry.get(prov_id)
    indicators = prov.list_indicators()
    print(f"{prov_id:12} | {prov.provider_name:30} | {len(indicators):3} indicators")

print("\n" + "=" * 60)
print("✓ All providers available and working")
print("=" * 60)
