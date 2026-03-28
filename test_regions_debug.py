#!/usr/bin/env python3
"""
Deep dive into _get_distinct_regions_from_metadata() error
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import traceback

# Load environment variables
dotenv_path = Path(__file__).parent / "backend" / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from src.models.database import ParseHubDatabase

print("=" * 80)
print("DEEP DIAGNOSTIC: _get_distinct_regions_from_metadata() ERROR")
print("=" * 80)
print()

try:
    db = ParseHubDatabase()
    print(f"✓ ParseHubDatabase created")
    print()
except Exception as e:
    print(f"✗ Failed to create ParseHubDatabase: {e}")
    sys.exit(1)

print("-" * 80)
print("Manually stepping through _get_distinct_regions_from_metadata()")
print("-" * 80)
print()

try:
    print("Step 1: Connect to database...")
    db.connect()
    print(f"  ✓ Connected")
    print()
    
    print("Step 2: Get cursor...")
    cursor = db.cursor()
    print(f"  ✓ Cursor created: {type(cursor)}")
    print()
    
    print("Step 3: Execute SQL query...")
    sql = '''
        SELECT DISTINCT TRIM(region) AS region
        FROM metadata
        WHERE region IS NOT NULL AND TRIM(region) != ''
        ORDER BY 1
    '''
    print(f"  SQL: {sql.strip()}")
    cursor.execute(sql)
    print(f"  ✓ Query executed")
    print()
    
    print("Step 4: Fetch results...")
    rows = cursor.fetchall()
    print(f"  ✓ Fetched {len(rows)} rows")
    print(f"  Row type: {type(rows)}")
    if rows:
        print(f"  First row type: {type(rows[0])}")
        print(f"  First row: {rows[0]}")
    print()
    
    print("Step 5: Process results...")
    out = []
    for i, r in enumerate(rows):
        print(f"  Row {i}: {r} (type: {type(r)})")
        if isinstance(r, dict):
            print(f"    - Is dict, trying r.get('region'): {r.get('region')}")
            val = r.get('region', r[0] if r else None)
        else:
            print(f"    - Not dict, trying r[0]")
            try:
                val = r[0]
                print(f"    - r[0] = {val}")
            except Exception as e:
                print(f"    - ERROR accessing r[0]: {e}")
                val = None
        
        if val:
            out.append(val)
            print(f"    - Appended: {val}")
    
    print(f"\n  Final result: {out}")
    print()
    
    print("Step 6: Disconnect...")
    db.disconnect()
    print(f"  ✓ Disconnected")
    print()
    
except Exception as e:
    print(f"\n✗ ERROR at step: {e}")
    print(f"  Error type: {type(e).__name__}")
    print(f"  Error repr: {repr(e)}")
    print("\nFull traceback:")
    traceback.print_exc()
    print()

print("=" * 80)
print("TESTING COMPLETE")
print("=" * 80)
