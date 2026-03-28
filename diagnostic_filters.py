#!/usr/bin/env python3
"""
Comprehensive filter debugging script - checks all 6 diagnostic points
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
    from snowflake.connector.cursor import SnowflakeCursor
except ImportError:
    print("ERROR: Snowflake connector not installed")
    print("Try: pip install snowflake-connector-python")
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


def run_query(conn, query):
    """Run a single query and return results"""
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        results = cursor.fetchall()
        return results
    except Exception as e:
        return f"ERROR: {str(e)}"


def format_results(results):
    """Format query results for display"""
    if isinstance(results, str):
        return results
    if not results:
        return "NO RESULTS"
    return results


print("=" * 80)
print("FILTER DEBUGGING DIAGNOSTIC")
print("=" * 80)
print()

try:
    conn = get_connection()
    print(f"✓ Connected to Snowflake: {os.getenv('SNOWFLAKE_ACCOUNT')}")
    print(f"  Database: {os.getenv('SNOWFLAKE_DATABASE')}")
    print(f"  Schema: {os.getenv('SNOWFLAKE_SCHEMA')}")
    print()
except Exception as e:
    print(f"✗ Connection failed: {e}")
    sys.exit(1)

# ===== POINT 1: get_metadata_table_columns() - What columns exist? =====
print("-" * 80)
print("POINT 1: get_metadata_table_columns() - Column Discovery")
print("-" * 80)
query1 = """
SELECT COLUMN_NAME, DATA_TYPE, ORDINAL_POSITION
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'PARSEHUB_DB' AND TABLE_NAME = 'METADATA'
ORDER BY ORDINAL_POSITION
"""
print(f"Query: {query1}")
results1 = run_query(conn, query1)
if isinstance(results1, str):
    print(f"✗ {results1}")
else:
    print(f"✓ Found {len(results1)} columns:")
    for row in results1:
        col_name = row[0] if isinstance(row, tuple) else row['COLUMN_NAME']
        data_type = row[1] if isinstance(row, tuple) else row['DATA_TYPE']
        ordinal = row[2] if isinstance(row, tuple) else row['ORDINAL_POSITION']
        print(f"  {ordinal:2d}. {col_name:20s} {data_type}")
print()

# ===== POINT 2: Actual Snowflake column names (case sensitivity) =====
print("-" * 80)
print("POINT 2: Exact Column Names (Case Sensitivity Check)")
print("-" * 80)
column_list = []
for row in results1:
    col_name = row[0] if isinstance(row, tuple) else row['COLUMN_NAME']
    column_list.append(col_name)

filter_columns = ['REGION', 'COUNTRY', 'BRAND', 'WEBSITE_URL']
print("Filter columns to check:", filter_columns)
print("Found in schema:")
for col in filter_columns:
    found = col in column_list
    status = "✓ YES" if found else "✗ NO"
    print(f"  {status}: {col}")
print()

# ===== POINT 3 & 4: NULL/Empty filtering - Does metadata have data? =====
print("-" * 80)
print("POINT 3 & 4: Metadata Table - Row Count and Data Availability")
print("-" * 80)
query3 = """
SELECT 
    COUNT(*) as total_rows,
    SUM(CASE WHEN REGION IS NOT NULL THEN 1 ELSE 0 END) as regions_filled,
    SUM(CASE WHEN COUNTRY IS NOT NULL THEN 1 ELSE 0 END) as countries_filled,
    SUM(CASE WHEN BRAND IS NOT NULL THEN 1 ELSE 0 END) as brands_filled,
    SUM(CASE WHEN WEBSITE_URL IS NOT NULL THEN 1 ELSE 0 END) as websites_filled,
    SUM(CASE WHEN REGION IS NOT NULL AND TRIM(REGION) != '' THEN 1 ELSE 0 END) as regions_not_empty,
    SUM(CASE WHEN COUNTRY IS NOT NULL AND COUNTRY != '' THEN 1 ELSE 0 END) as countries_not_empty,
    SUM(CASE WHEN BRAND IS NOT NULL AND BRAND != '' THEN 1 ELSE 0 END) as brands_not_empty,
    SUM(CASE WHEN WEBSITE_URL IS NOT NULL AND WEBSITE_URL != '' THEN 1 ELSE 0 END) as websites_not_empty
FROM METADATA
"""
print(f"Query: {query3}")
results3 = run_query(conn, query3)
if isinstance(results3, str):
    print(f"✗ {results3}")
else:
    row = results3[0]
    total = row[0] if isinstance(row, tuple) else row['TOTAL_ROWS']
    regions_filled = row[1] if isinstance(row, tuple) else row['REGIONS_FILLED']
    countries_filled = row[2] if isinstance(row, tuple) else row['COUNTRIES_FILLED']
    brands_filled = row[3] if isinstance(row, tuple) else row['BRANDS_FILLED']
    websites_filled = row[4] if isinstance(row, tuple) else row['WEBSITES_FILLED']
    regions_not_empty = row[5] if isinstance(row, tuple) else row['REGIONS_NOT_EMPTY']
    countries_not_empty = row[6] if isinstance(row, tuple) else row['COUNTRIES_NOT_EMPTY']
    brands_not_empty = row[7] if isinstance(row, tuple) else row['BRANDS_NOT_EMPTY']
    websites_not_empty = row[8] if isinstance(row, tuple) else row['WEBSITES_NOT_EMPTY']
    
    print(f"✓ Total rows: {total}")
    print(f"  Region data:     {regions_filled} NOT NULL, {regions_not_empty} NOT EMPTY (after TRIM)")
    print(f"  Country data:    {countries_filled} NOT NULL, {countries_not_empty} NOT EMPTY")
    print(f"  Brand data:      {brands_filled} NOT NULL, {brands_not_empty} NOT EMPTY")
    print(f"  Website data:    {websites_filled} NOT NULL, {websites_not_empty} NOT EMPTY")
print()

# ===== POINT 5: Case sensitivity in WHERE clauses =====
print("-" * 80)
print("POINT 5: Case Sensitivity - WHERE Clause Testing")
print("-" * 80)
print("Testing lowercase vs uppercase column queries:")
print()

# Test 1: lowercase region
query5a = 'SELECT DISTINCT region FROM metadata WHERE region IS NOT NULL AND TRIM(region) != \'\' LIMIT 5'
print(f"Query (lowercase): SELECT DISTINCT region FROM metadata ...")
results5a = run_query(conn, query5a)
print(f"Result: {format_results(results5a)}")
print()

# Test 2: uppercase REGION with quotes
query5b = 'SELECT DISTINCT "REGION" FROM metadata WHERE "REGION" IS NOT NULL AND TRIM("REGION") != \'\' LIMIT 5'
print(f"Query (uppercase quoted): SELECT DISTINCT \"REGION\" FROM metadata ...")
results5b = run_query(conn, query5b)
print(f"Result: {format_results(results5b)}")
print()

# ===== POINT 6: Actual SQL queries being executed =====
print("-" * 80)
print("POINT 6: Actual Filter Queries - What returns 0 results?")
print("-" * 80)
print()

print("Query A: REGIONS (from _get_distinct_regions_from_metadata)")
query6a = """
SELECT DISTINCT TRIM(region) AS region
FROM metadata
WHERE region IS NOT NULL AND TRIM(region) != ''
ORDER BY 1
"""
print(f"SQL: {query6a.strip()}")
results6a = run_query(conn, query6a)
if isinstance(results6a, str):
    print(f"✗ ERROR: {results6a}")
else:
    print(f"✓ Results: {len(results6a)} regions found")
    for row in results6a[:10]:
        val = row[0] if isinstance(row, tuple) else row['REGION']
        print(f"  - {val}")
    if len(results6a) > 10:
        print(f"  ... and {len(results6a) - 10} more")
print()

print("Query B: COUNTRIES")
query6b = 'SELECT DISTINCT "COUNTRY" FROM metadata WHERE "COUNTRY" IS NOT NULL AND "COUNTRY" != \'\' ORDER BY 1'
print(f"SQL: {query6b}")
results6b = run_query(conn, query6b)
if isinstance(results6b, str):
    print(f"✗ ERROR: {results6b}")
else:
    print(f"✓ Results: {len(results6b)} countries found")
    for row in results6b[:10]:
        val = row[0] if isinstance(row, tuple) else row.get('COUNTRY', row[0])
        print(f"  - {val}")
    if len(results6b) > 10:
        print(f"  ... and {len(results6b) - 10} more")
print()

print("Query C: BRANDS")
query6c = 'SELECT DISTINCT "BRAND" FROM metadata WHERE "BRAND" IS NOT NULL AND "BRAND" != \'\' ORDER BY 1'
print(f"SQL: {query6c}")
results6c = run_query(conn, query6c)
if isinstance(results6c, str):
    print(f"✗ ERROR: {results6c}")
else:
    print(f"✓ Results: {len(results6c)} brands found")
    for row in results6c[:10]:
        val = row[0] if isinstance(row, tuple) else row.get('BRAND', row[0])
        print(f"  - {val}")
    if len(results6c) > 10:
        print(f"  ... and {len(results6c) - 10} more")
print()

print("Query D: WEBSITES")
query6d = 'SELECT DISTINCT "WEBSITE_URL" FROM metadata WHERE "WEBSITE_URL" IS NOT NULL AND "WEBSITE_URL" != \'\' ORDER BY 1'
print(f"SQL: {query6d}")
results6d = run_query(conn, query6d)
if isinstance(results6d, str):
    print(f"✗ ERROR: {results6d}")
else:
    print(f"✓ Results: {len(results6d)} websites found")
    for row in results6d[:10]:
        val = row[0] if isinstance(row, tuple) else row.get('WEBSITE_URL', row[0])
        print(f"  - {val}")
    if len(results6d) > 10:
        print(f"  ... and {len(results6d) - 10} more")
print()

# ===== SAMPLE DATA =====
print("-" * 80)
print("SAMPLE DATA: First 5 metadata records")
print("-" * 80)
query_sample = 'SELECT REGION, COUNTRY, BRAND, WEBSITE_URL FROM metadata LIMIT 5'
print(f"Query: {query_sample}")
results_sample = run_query(conn, query_sample)
if isinstance(results_sample, str):
    print(f"✗ {results_sample}")
else:
    print(f"✓ Found {len(results_sample)} records:")
    for i, row in enumerate(results_sample, 1):
        region = row[0] if isinstance(row, tuple) else row.get('REGION', row[0])
        country = row[1] if isinstance(row, tuple) else row.get('COUNTRY', row[1])
        brand = row[2] if isinstance(row, tuple) else row.get('BRAND', row[2])
        website = row[3] if isinstance(row, tuple) else row.get('WEBSITE_URL', row[3])
        print(f"  {i}. Region={region}, Country={country}, Brand={brand}, Website={website}")
print()

# ===== SUMMARY =====
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()

if total and total > 0:
    print(f"✓ Metadata table has {total} rows")
    
    # Check each filter
    issues = []
    
    if regions_not_empty == 0:
        issues.append(f"  ✗ REGION column: {regions_filled} NOT NULL but {regions_not_empty} NOT EMPTY (WHERE clause filtering all!)")
    else:
        print(f"✓ REGION has {regions_not_empty} non-empty values")
    
    if countries_not_empty == 0:
        issues.append(f"  ✗ COUNTRY column: {countries_filled} NOT NULL but {countries_not_empty} NOT EMPTY")
    else:
        print(f"✓ COUNTRY has {countries_not_empty} non-empty values")
    
    if brands_not_empty == 0:
        issues.append(f"  ✗ BRAND column: {brands_filled} NOT NULL but {brands_not_empty} NOT EMPTY")
    else:
        print(f"✓ BRAND has {brands_not_empty} non-empty values")
    
    if websites_not_empty == 0:
        issues.append(f"  ✗ WEBSITE_URL column: {websites_filled} NOT NULL but {websites_not_empty} NOT EMPTY")
    else:
        print(f"✓ WEBSITE_URL has {websites_not_empty} non-empty values")
    
    if issues:
        print()
        print("ISSUES FOUND:")
        for issue in issues:
            print(issue)
else:
    print("✗ CRITICAL: Metadata table is empty!")

print()
print("=" * 80)

conn.close()
