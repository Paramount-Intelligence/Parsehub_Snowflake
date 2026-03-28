#!/usr/bin/env python3
"""
Test the actual get_filters_schema_aware() method to see why it returns 0s
"""
import os
import sys
from pathlib import Path

# Set up path to import backend modules
sys.path.insert(0, str(Path(__file__).parent / "backend" / "src"))

# Load environment variables first
from dotenv import load_dotenv
dotenv_path = Path(__file__).parent / "backend" / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)

from models.database import ParseHubDatabase

print("Testing get_filters_schema_aware()")
print("=" * 80)
print()

try:
    db = ParseHubDatabase()
    print(f"✓ Database object created")
    print()
    
    # Test 1: Test get_metadata_table_columns directly
    print("Test 1: get_metadata_table_columns()")
    print("-" * 80)
    columns = db.get_metadata_table_columns(auto_disconnect=False)
    print(f"Columns returned: {columns}")
    print(f"Type: {type(columns)}")
    print()
    
    # Test 2: Test _get_distinct_regions_from_metadata directly
    print("Test 2: _get_distinct_regions_from_metadata()")
    print("-" * 80)
    db.connect()
    regions = db._get_distinct_regions_from_metadata()
    print(f"Regions: {regions}")
    print(f"Count: {len(regions)}")
    print()
    
    # Test 3: Test _get_distinct_values_for_metadata_column directly
    print("Test 3: _get_distinct_values_for_metadata_column('COUNTRY')")
    print("-" * 80)
    countries = db._get_distinct_values_for_metadata_column('COUNTRY')
    print(f"Countries: {countries}")
    print(f"Count: {len(countries)}")
    print()
    
    # Test 4: Test get_filters_schema_aware
    print("Test 4: get_filters_schema_aware()")
    print("-" * 80)
    filters = db.get_filters_schema_aware()
    print(f"Filters returned:")
    print(f"  Regions: {len(filters.get('regions', []))} items")
    print(f"    Data: {filters.get('regions', [])}")
    print(f"  Countries: {len(filters.get('countries', []))} items")
    print(f"    Data: {filters.get('countries', [])}")
    print(f"  Brands: {len(filters.get('brands', []))} items")
    print(f"    Data: {filters.get('brands', [])}")
    print(f"  Websites: {len(filters.get('websites', []))} items")
    print(f"    First 3: {filters.get('websites', [])[:3]}")
    print()
    
except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    print()
    print("Full traceback:")
    traceback.print_exc()
