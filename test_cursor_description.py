#!/usr/bin/env python3
"""
Test Snowflake cursor.description to see if column names are available
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
dotenv_path = Path(__file__).parent / "backend" / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)

try:
    import snowflake.connector
except ImportError:
    print("ERROR: Snowflake connector not installed")
    sys.exit(1)


def get_connection():
    """Connect to Snowflake"""
    conn = snowflake.connector.connect(
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
        database=os.getenv('SNOWFLAKE_DATABASE'),
        schema=os.getenv('SNOWFLAKE_SCHEMA')
    )
    return conn

print("Testing Snowflake Cursor Description")
print("=" * 80)
print()

conn = get_connection()
cursor = conn.cursor()

# Test 1: Simple query
print("Test 1: Simple query - cursor.description")
query = "SELECT DISTINCT TRIM(region) AS region FROM metadata WHERE region IS NOT NULL LIMIT 3"
print(f"Query: {query}")
cursor.execute(query)

print(f"\ncursor.description: {cursor.description}")
if cursor.description:
    print(f"Type: {type(cursor.description)}")
    print(f"Length: {len(cursor.description)}")
    for i, desc in enumerate(cursor.description):
        print(f"  [{i}]: {desc}")
        print(f"       type={type(desc)}")
        if hasattr(desc, 'name'):
            print(f"       name={desc.name}")
        if hasattr(desc, '__dict__'):
            print(f"       dict={desc.__dict__}")
else:
    print("  cursor.description is None or empty!")

print(f"\nFetching rows...")
rows = cursor.fetchall()
print(f"Rows returned: {len(rows)}")
for i, row in enumerate(rows):
    print(f"  [{i}]: {row} (type: {type(row)})")

cursor.close()

# Test 2: Check if description works after fetchall
print("\n" + "=" * 80)
print("Test 2: Description after fetchall")
cursor2 = conn.cursor()
query2 = 'SELECT DISTINCT "COUNTRY" FROM metadata LIMIT 3'
print(f"Query: {query2}")
cursor2.execute(query2)
rows2 = cursor2.fetchall()
print(f"cursor2.description after fetchall: {cursor2.description}")
print(f"rows2: {rows2}")
cursor2.close()

# Test 3: Check SnowflakeCursor class directly
print("\n" + "=" * 80)
print("Test 3: Check SnowflakeCursor class")
cursor3 = conn.cursor()
print(f"Type of cursor3: {type(cursor3)}")
print(f"Has 'description': {hasattr(cursor3, 'description')}")
print(f"cursor3.description: {cursor3.description}")

query3 = 'SELECT DISTINCT "BRAND" FROM metadata LIMIT 3'
cursor3.execute(query3)
print(f"\nAfter execute:")
print(f"cursor3.description: {cursor3.description}")
if cursor3.description:
    for col in cursor3.description:
        print(f"  - {col.name}")

rows3 = cursor3.fetchall()
print(f"\nrows3: {rows3}")
cursor3.close()

conn.close()
print("\nTest Complete")
