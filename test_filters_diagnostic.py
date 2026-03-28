#!/usr/bin/env python3
"""
Diagnostic script to test filter queries directly
"""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend' / 'src'))

from models.database import Database

def main():
    print("=" * 80)
    print("FILTER DIAGNOSTIC TEST")
    print("=" * 80)
    
    # Create database instance
    db = Database()
    
    print("\n1. Testing Database Connection...")
    try:
        db.connect()
        print("   ✓ Connected to Snowflake")
        
        # Test schema name
        print(f"\n2. Schema Configuration:")
        print(f"   Database: {db.sf_database}")
        print(f"   Schema: {db.sf_schema}")
        
        # Test column retrieval
        print(f"\n3. Testing get_metadata_table_columns()...")
        columns = db.get_metadata_table_columns(auto_disconnect=False)
        print(f"   ✓ Retrieved {len(columns)} columns:")
        for col in columns:
            print(f"     - {col}")
        
        if not columns:
            print("   ✗ ERROR: No columns found! Schema mismatch likely.")
            return
        
        # Test regions query
        print(f"\n4. Testing _get_distinct_regions_from_metadata()...")
        regions = db._get_distinct_regions_from_metadata()
        print(f"   ✓ Retrieved {len(regions)} regions:")
        for reg in regions:
            print(f"     - {reg}")
        
        # Test countries query
        print(f"\n5. Testing _get_distinct_values_for_metadata_column('COUNTRY')...")
        countries = db._get_distinct_values_for_metadata_column('COUNTRY')
        print(f"   ✓ Retrieved {len(countries)} countries:")
        for country in countries:
            print(f"     - {country}")
        
        # Test brands query
        print(f"\n6. Testing _get_distinct_values_for_metadata_column('BRAND')...")
        brands = db._get_distinct_values_for_metadata_column('BRAND')
        print(f"   ✓ Retrieved {len(brands)} brands:")
        for brand in brands:
            print(f"     - {brand}")
        
        # Test websites query
        print(f"\n7. Testing _get_distinct_values_for_metadata_column('WEBSITE_URL')...")
        websites = db._get_distinct_values_for_metadata_column('WEBSITE_URL')
        print(f"   ✓ Retrieved {len(websites)} websites:")
        for i, website in enumerate(websites[:5]):
            print(f"     - {website}")
        if len(websites) > 5:
            print(f"     ... and {len(websites) - 5} more")
        
        # Test full filter method
        print(f"\n8. Testing get_filters_schema_aware()...")
        result = db.get_filters_schema_aware()
        print(f"   ✓ Result:")
        print(f"     Regions: {len(result['regions'])} items - {result['regions']}")
        print(f"     Countries: {len(result['countries'])} items - {result['countries'][:3]}...")
        print(f"     Brands: {len(result['brands'])} items - {result['brands'][:3]}...")
        print(f"     Websites: {len(result['websites'])} items")
        
        print("\n" + "=" * 80)
        if result['regions'] and result['countries'] and result['brands'] and result['websites']:
            print("✓ ALL TESTS PASSED - Filters should work!")
        else:
            print("✗ TESTS FAILED - Some filters returned 0 items")
        print("=" * 80)
        
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.disconnect()

if __name__ == '__main__':
    main()
