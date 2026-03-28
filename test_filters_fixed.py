#!/usr/bin/env python3
"""
Test the fixed backend ParseHubDatabase.get_filters_schema_aware() method
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
dotenv_path = Path(__file__).parent / "backend" / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from src.models.database import ParseHubDatabase

print("=" * 80)
print("BACKEND FILTER TEST AFTER FIX")
print("=" * 80)
print()

try:
    db = ParseHubDatabase()
    print("[OK] ParseHubDatabase created")
    print()
except Exception as e:
    print("[FAIL] Failed to create ParseHubDatabase: " + str(e))
    sys.exit(1)

# Test 2: Check _get_distinct_regions_from_metadata()
print("-" * 80)
print("TEST: _get_distinct_regions_from_metadata()")
print("-" * 80)
try:
    db.connect()
    regions = db._get_distinct_regions_from_metadata()
    print("[OK] Retrieved [" + str(len(regions)) + "] regions: " + str(regions))
    db.disconnect()
    print()
except Exception as e:
    print("[FAIL] Error: " + str(e))
    import traceback
    traceback.print_exc()
    print()

# Test 3: Check _get_distinct_values_for_metadata_column('COUNTRY')
print("-" * 80)
print("TEST: _get_distinct_values_for_metadata_column('COUNTRY')")
print("-" * 80)
try:
    db.connect()
    countries = db._get_distinct_values_for_metadata_column('COUNTRY')
    print("[OK] Retrieved [" + str(len(countries)) + "] countries: " + str(countries))
    db.disconnect()
    print()
except Exception as e:
    print("[FAIL] Error: " + str(e))
    import traceback
    traceback.print_exc()
    print()

# Test 6: Full get_filters_schema_aware() - THE MAIN TEST
print("-" * 80)
print("TEST: get_filters_schema_aware() - FULL TEST")
print("-" * 80)
try:
    filters = db.get_filters_schema_aware()
    print("[OK] Filters retrieved:")
    print("  Regions:   [" + str(len(filters.get('regions', []))) + "] " + str(filters.get('regions', [])))
    print("  Countries: [" + str(len(filters.get('countries', []))) + "] " + str(filters.get('countries', [])[:5]))
    print("  Brands:    [" + str(len(filters.get('brands', []))) + "] " + str(filters.get('brands', [])[:5]))
    print("  Websites:  [" + str(len(filters.get('websites', []))) + "]")
    print()
except Exception as e:
    print("[FAIL] Error: " + str(e))
    import traceback
    traceback.print_exc()
    print()

print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
