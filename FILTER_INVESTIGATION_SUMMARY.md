# Filter Population Investigation - Executive Summary

## Problem
Filters (Regions, Countries, Brands, Websites) display 0 items on the home page despite metadata table having 40+ records.

---

## Root Cause Candidates (In Priority Order)

### 1. 🔴 DATABASE CONNECTION FAILURE (CRITICAL)
**Location**: `backend/src/models/database.py:2257`

**Symptom**: `get_filters_schema_aware()` fails silently
```python
try:
    self.connect()  # ← If this fails, returns empty {} at line 2301
```

**Check**:
```bash
curl http://localhost:5000/api/filters
# If response has all empty arrays → connection issue
```

**Debug**: Look for logs:
```
Error in get_filters_schema_aware: [CONNECTION ERROR]
```

---

### 2. 🔴 METADATA TABLE IS EMPTY (CRITICAL)  
**Location**: Any of the SELECT DISTINCT queries

**Symptom**: Snowflake metadata table has 0 rows

**SQL Check**:
```sql
SELECT COUNT(*) FROM metadata;  -- Should be 40+
```

**If 0**: Data wasn't loaded from CSV

---

### 3. 🟠 COLUMN NAME MISMATCH (HIGH RISK)
**Location**: `backend/src/models/database.py:2066`

**Symptom**: Column 'COUNTRY' exists but isn't found

```python
if column_name not in columns:  # Line 2066
    return []  # ← Returns empty!
```

**Reason**: Snowflake returns uppercase column names, but comparison might fail on case

**Check**:
```sql
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA='PARSEHUB_DB' AND TABLE_NAME='METADATA';
```

**Expected**: ['ID', 'REGION', 'COUNTRY', 'BRAND', 'WEBSITE_URL', ...]

---

### 4. 🟠 NO DATA IN FILTER COLUMNS (HIGH RISK)
**Location**: WHERE clauses in SELECT DISTINCT queries

**Symptom**: Metadata table has rows but region/country/brand/website_url are all NULL

**Check**:
```sql
SELECT COUNT(*),
       SUM(CASE WHEN region IS NOT NULL THEN 1 ELSE 0 END) as regions_filled,
       SUM(CASE WHEN country IS NOT NULL THEN 1 ELSE 0 END) as countries_filled,
       SUM(CASE WHEN brand IS NOT NULL THEN 1 ELSE 0 END) as brands_filled,
       SUM(CASE WHEN website_url IS NOT NULL THEN 1 ELSE 0 END) as websites_filled
FROM metadata;
```

**If filled columns = 0**: CSV imported with NULL values

---

### 5. 🟡 SNOWFLAKE SCHEMA NOT FOUND (MEDIUM RISK)
**Location**: `backend/src/models/database.py:2043`

```sql
WHERE TABLE_SCHEMA = 'PARSEHUB_DB' AND TABLE_NAME = 'METADATA'
```

**Problem**: Schema name might be different in Snowflake

**Check**: List all schemas in Snowflake:
```sql
SHOW SCHEMAS;
```

---

### 6. 🟡 FRONTEND API RESPONSE PARSING (MEDIUM RISK)
**Location**: `frontend/app/page.tsx:146`

```typescript
if (data.filters) {  // Line 146
    // If this is false, filters stay empty
}
```

**Check**: Browser DevTools → Network tab
- Call to `/api/filters`
- Look at Response body
- Verify `"filters"` key exists

---

## EXACT DATA FLOW: Where To Inspect

```
┌─────────────────────┐
│   FRONTEND LOGS     │
│ page.tsx Line 156   │  ← See filter counts here
└──────────┬──────────┘
           │
           ↓
┌─────────────────────────────────────────┐
│  BROWSER NETWORK TAB                    │
│  Response to GET /api/filters           │  ← Verify JSON structure
│  Expected: {success, filters: {...}}    │
└──────────┬──────────────────────────────┘
           │
           ↓
┌──────────────────────────────────────────┐
│  BACKEND API RESPONSE                    │
│  api_server.py Line 1292-1295            │  ← Source of response
│  Calls: g.db.get_filters_schema_aware()  │
└──────────┬───────────────────────────────┘
           │
           ↓
┌──────────────────────────────────────────┐
│  BACKEND DATABASE LAYER                  │
│  database.py Line 2247-2299              │  ← Where data extraction happens
│                                          │
│  Step 1: Connect (Line 2257)             │
│  Step 2: Get schema (Line 2259)          │
│  Step 3-6: Run 4 SELECT DISTINCT (Ln 2268,2275,2280,2285) │
└──────────┬───────────────────────────────┘
           │
           ↓
┌──────────────────────────────────────────┐
│  SNOWFLAKE DATABASE                      │
│  Table: PARSEHUB_DB.METADATA             │  ← Actual data source
│  40+ rows with region/country/brand data │
└──────────────────────────────────────────┘
```

---

## QUICK DIAGNOSTIC SCRIPT

Run this in backend Python shell:

```python
from src.models.database import ParseHubDatabase

db = ParseHubDatabase()

# Test 1: Connection
print("=== TEST 1: Connection ===")
try:
    db.connect()
    print("✓ Connection successful")
except Exception as e:
    print(f"✗ Connection failed: {e}")
    exit(1)

# Test 2: Table exists and has data
print("\n=== TEST 2: Metadata table ===")
cursor = db.cursor()
cursor.execute("SELECT COUNT(*) FROM metadata")
count = cursor.fetchone()
print(f"Row count: {count}")
if not count or count[0] == 0:
    print("✗ Table is empty!")
    db.disconnect()
    exit(1)

# Test 3: Columns exist
print("\n=== TEST 3: Columns ===")
cols = db.get_metadata_table_columns(auto_disconnect=False)
print(f"Columns: {cols}")
for col in ['REGION', 'COUNTRY', 'BRAND', 'WEBSITE_URL']:
    if col in cols:
        print(f"✓ {col} found")
    else:
        print(f"✗ {col} NOT found")

# Test 4: Data in filter columns
print("\n=== TEST 4: Filter columns have data ===")
cursor.execute("""
    SELECT 
        COUNT(DISTINCT region) as regions,
        COUNT(DISTINCT country) as countries,
        COUNT(DISTINCT brand) as brands,
        COUNT(DISTINCT website_url) as websites
    FROM metadata
    WHERE region IS NOT NULL OR country IS NOT NULL OR brand IS NOT NULL OR website_url IS NOT NULL
""")
result = cursor.fetchone()
print(f"Regions: {result[0]}, Countries: {result[1]}, Brands: {result[2]}, Websites: {result[3]}")
if all(x > 0 for x in result):
    print("✓ All filter columns have data")
else:
    print("✗ Some filter columns are empty")

# Test 5: Run actual API function
print("\n=== TEST 5: get_filters_schema_aware() ===")
try:
    db.connect()
    filters = db.get_filters_schema_aware()
    print(f"Regions: {len(filters['regions'])}, " \
          f"Countries: {len(filters['countries'])}, " \
          f"Brands: {len(filters['brands'])}, " \
          f"Websites: {len(filters['websites'])}")
    if any(len(v) > 0 for v in filters.values()):
        print("✓ get_filters_schema_aware() returns data")
    else:
        print("✗ get_filters_schema_aware() returns empty")
except Exception as e:
    print(f"✗ get_filters_schema_aware() failed: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.disconnect()
```

---

## IMMEDIATE ACTIONS

### Action 1: Check Backend Logs
```bash
# Look for errors in backend output:
# - "Error in get_filters_schema_aware"
# - "Error getting metadata columns"
# - Connection timeouts
```

### Action 2: Test API Directly
```bash
curl -H "x-api-key: t_hmXetfMCq3" http://localhost:5000/api/filters | jq .
```

**Expected output**:
```json
{
  "success": true,
  "filters": {
    "regions": ["NA", "EMEA", ...],
    "countries": ["USA", ...],
    ...
  }
}
```

### Action 3: Check Snowflake Directly
```sql
-- Via Snowflake Web UI or connection string

-- Check metadata table exists
SELECT COUNT(*) FROM PARSEHUB_DB.METADATA;

-- Check columns have data
SELECT DISTINCT region FROM metadata WHERE region IS NOT NULL LIMIT 5;
SELECT DISTINCT country FROM metadata WHERE country IS NOT NULL LIMIT 5;
SELECT DISTINCT brand FROM metadata WHERE brand IS NOT NULL LIMIT 5;
SELECT DISTINCT website_url FROM metadata WHERE website_url IS NOT NULL LIMIT 5;
```

---

## FALLBACK REGIONS LOGIC

**Location**: `database.py:2289-2292`

If direct regions query returns empty, code tries:
```python
if not result['regions'] and result['countries']:
    result['regions'] = self._infer_regions_from_country_values(result['countries'])
```

So even if `region` column is empty, regions can be inferred from `country` values.

**This means**: Might need to verify COUNTRY column at least has data.

---

## LOG LINES TO MONITOR

### Frontend (Browser Console)
- Line 139: `[Home] Fetching filter options...`
- Line 156: `[Home] Loaded filters - Regions: X, Countries: Y, ...` ← Shows 0 if problem

### Backend (Server Logs)
- Line 1283: `[API] Getting filter options (schema-aware)...`
- Line 1285-1290: `[API] Filters - Regions: X, Countries: Y, ...` ← Shows 0 if problem
- Line 2260: `[FILTERS] Retrieved N columns: [...]` ← Shows 0 if schema failed
- Line 2297: `Error in get_filters_schema_aware: ...` ← Shows exceptions

---

## KEY FILES FOR REFERENCE

| File | Lines | Purpose |
|------|-------|---------|
| frontend/app/page.tsx | 92-161 | Filter state & API call |
| backend/src/api/api_server.py | 1279-1300 | Filter endpoint |
| backend/src/models/database.py | 2036-2099 | Filter extraction logic |
| backend/src/models/database.py | 526-549 | Metadata table schema |

---

## NEXT STEPS

1. ✅ Run diagnostic script above
2. ✅ Check Snowflake: verify metadata table has data
3. ✅ Check API response: verify JSON structure
4. ✅ Check logs: look for connection/schema errors
5. ✅ If all pass but filters still 0: check column casing in Snowflake
6. ✅ If metadata empty: re-run CSV import to Snowflake

