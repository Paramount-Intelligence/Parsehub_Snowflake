#!/usr/bin/env python3
"""
Test the backend ParseHubDatabase.get_filters_schema_aware() method directly
to see why it returns empty arrays
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
print("BACKEND FILTER DIAGNOSIS - Using ParseHubDatabase Class")
print("=" * 80)
print()

try:
    # Create database instance
    db = ParseHubDatabase()
    print(f"✓ ParseHubDatabase created")
    print(f"  Account: {db.sf_account}")
    print(f"  Database: {db.sf_database}")
    print(f"  Schema: {db.sf_schema}")
    print()
except Exception as e:
    print(f"✗ Failed to create ParseHubDatabase: {e}")
    sys.exit(1)

# Test 1: Check metadata table columns
print("-" * 80)
print("TEST 1: get_metadata_table_columns()")
print("-" * 80)
try:
    columns = db.get_metadata_table_columns()
    print(f"✓ Retrieved {len(columns)} columns: {columns}")
    print()
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    print()

# Test 2: Check _get_distinct_regions_from_metadata()
print("-" * 80)
print("TEST 2: _get_distinct_regions_from_metadata()")
print("-" * 80)
try:
    db.connect()
    regions = db._get_distinct_regions_from_metadata()
    print(f"✓ Retrieved {len(regions)} regions: {regions}")
    db.disconnect()
    print()
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    print()

# Test 3: Check _get_distinct_values_for_metadata_column('COUNTRY')
print("-" * 80)
print("TEST 3: _get_distinct_values_for_metadata_column('COUNTRY')")
print("-" * 80)
try:
    db.connect()
    countries = db._get_distinct_values_for_metadata_column('COUNTRY')
    print(f"✓ Retrieved {len(countries)} countries: {countries}")
    db.disconnect()
    print()
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    print()

# Test 4: Check _get_distinct_values_for_metadata_column('BRAND')
print("-" * 80)
print("TEST 4: _get_distinct_values_for_metadata_column('BRAND')")
print("-" * 80)
try:
    db.connect()
    brands = db._get_distinct_values_for_metadata_column('BRAND')
    print(f"✓ Retrieved {len(brands)} brands: {brands}")
    db.disconnect()
    print()
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    print()

# Test 5: Check _get_distinct_values_for_metadata_column('WEBSITE_URL')
print("-" * 80)
print("TEST 5: _get_distinct_values_for_metadata_column('WEBSITE_URL')")
print("-" * 80)
try:
    db.connect()
    websites = db._get_distinct_values_for_metadata_column('WEBSITE_URL')
    print(f"✓ Retrieved {len(websites)} websites")
    print(f"  First 5: {websites[:5]}")
    db.disconnect()
    print()
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    print()

# Test 6: Full get_filters_schema_aware() - THE MAIN TEST
print("-" * 80)
print("TEST 6: get_filters_schema_aware() - FULL TEST")
print("-" * 80)
try:
    filters = db.get_filters_schema_aware()
    print(f"✓ Filters retrieved:")
    print(f"  Regions:   {len(filters.get('regions', []))} - {filters.get('regions', [])}")
    print(f"  Countries: {len(filters.get('countries', []))} - {filters.get('countries', [])[:5] if filters.get('countries') else []}")
    print(f"  Brands:    {len(filters.get('brands', []))} - {filters.get('brands', [])[:5] if filters.get('brands') else []}")
    print(f"  Websites:  {len(filters.get('websites', []))} - {filters.get('websites', [])[:2] if filters.get('websites') else []}")
    print()
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    print()

print("=" * 80)
print("DIAGNOSIS COMPLETE")
print("=" * 80)
