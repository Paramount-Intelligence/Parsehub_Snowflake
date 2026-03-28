# Filter Population Debug Guide

## Quick View: Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND BROWSER                                │
├─────────────────────────────────────────────────────────────────────────┤
│ page.tsx:114 - useEffect()                                              │
│   ├─→ Line 137: fetchFilters() calls                                    │
│   │   ├─→ apiClient.get("/api/filters")                                │
│   │   └─→ Expects: { success, filters: {regions, countries, brands} }  │
│   │   └─→ Sets state: setRegions(), setCountries(), setBrands(), ...    │
│   │                                                                      │
│   └─→ Line 163: fetchMetadata() [currently just logs count]             │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
                   (apiClient routes to)
                              ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                    NEXT.JS FRONTEND APIS                                │
│                  (/api/filters route)                                   │
│  [Route handler would proxy to backend at:                              │
│   http://localhost:5000/api/filters]                                    │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                    PYTHON FLASK BACKEND                                 │
│                  api_server.py:1279                                     │
├─────────────────────────────────────────────────────────────────────────┤
│ @app.route('/api/filters', methods=['GET'])                             │
│ def get_filters():                                                      │
│   ├─→ Logs: "[API] Getting filter options (schema-aware)..."             │
│   ├─→ Calls: g.db.get_filters_schema_aware()                           │
│   │          ↓                                                           │
│   │          database.py:2247                                           │
│   │          ├─→ Connects to database: self.connect()                   │
│   │          ├─→ Gets metadata columns:                                 │
│   │          │   get_metadata_table_columns() → Line 2036               │
│   │          │   ├─→ Query: SELECT COLUMN_NAME FROM INFORMATION_SCHEMA │
│   │          │   └─→ WHERE TABLE_SCHEMA='PARSEHUB_DB'                  │
│   │          │        AND TABLE_NAME='METADATA'                         │
│   │          │   └─→ Returns: ['ID', 'REGION', 'COUNTRY', ...]         │
│   │          │                                                           │
│   │          ├─→ Query regions (Line 2268):                             │
│   │          │   _get_distinct_regions_from_metadata() → Line 2083      │
│   │          │   SELECT DISTINCT TRIM(region) FROM metadata             │
│   │          │   WHERE region IS NOT NULL                               │
│   │          │                                                           │
│   │          ├─→ Query countries (Line 2275):                           │
│   │          │   _get_distinct_values_for_metadata_column('COUNTRY')    │
│   │          │   SELECT DISTINCT "COUNTRY" FROM metadata                │
│   │          │   WHERE "COUNTRY" IS NOT NULL                            │
│   │          │                                                           │
│   │          ├─→ Query brands (Line 2280):                              │
│   │          │   _get_distinct_values_for_metadata_column('BRAND')      │
│   │          │   SELECT DISTINCT "BRAND" FROM metadata                  │
│   │          │   WHERE "BRAND" IS NOT NULL                              │
│   │          │                                                           │
│   │          └─→ Query websites (Line 2285):                            │
│   │              _get_distinct_values_for_metadata_column('WEBSITE_URL')│
│   │              SELECT DISTINCT "WEBSITE_URL" FROM metadata            │
│   │              WHERE "WEBSITE_URL" IS NOT NULL                        │
│   │                                                                      │
│   ├─→ Logs results:                                                     │
│   │   "[API] Filters - Regions: N, Countries: N, Brands: N, ..."        │
│   │   "[API] Full filters object: {...}"                                │
│   │                                                                      │
│   └─→ Returns: { success: true, filters: {...} }                        │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
                   (Response returns to)
                              ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                    FRONTEND EXTRACTION                                  │
│                  page.tsx:149-154                                       │
├─────────────────────────────────────────────────────────────────────────┤
│ if (data.filters) {                                                     │
│   setRegions(data.filters.regions || [])                                │
│   setCountries(data.filters.countries || [])                            │
│   setBrands(data.filters.brands || [])                                  │
│   setWebsites(data.filters.websites || [])                              │
│ }                                                                        │
│                                                                          │
│ Logs: "[Home] Loaded filters - Regions: X, Countries: Y, ..."           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Exact Line Numbers & Expected Data Structures

### Frontend Layer

| Location | Lines | Component | Purpose |
|----------|-------|-----------|---------|
| **page.tsx** | 92-98 | Filter state init | Declares: regions[], countries[], brands[], websites[] |
| **page.tsx** | 114-122 | useEffect() | Calls fetchFilters() on mount |
| **page.tsx** | 137-161 | fetchFilters() | Calls `/api/filters` endpoint |
| **page.tsx** | 149-154 | Filter extraction | Extracts from `data.filters.{regions,countries,brands,websites}` |
| **apiClient.ts** | 12-17 | Axios client | baseURL='' (same-origin routing) |

**Expected Response at Frontend**:
```json
{
  "success": true,
  "filters": {
    "regions": ["NA", "EMEA", "APAC"],
    "countries": ["USA", "UK", "Germany"],
    "brands": ["Brand1", "Brand2"],
    "websites": ["amazon.com", "ebay.com"]
  }
}
```

### Backend API Layer

| Location | Lines | Component | Purpose |
|----------|-------|-----------|---------|
| **api_server.py** | 1279-1300 | `/api/filters` endpoint | Main filter API route |
| **api_server.py** | 1282-1283 | Log statement | Shows what DB returned: "Filters - Regions: X, Countries: Y, ..." |

**Response from Backend**:
```json
{
  "success": true,
  "filters": {
    "regions": [...],
    "countries": [...],
    "brands": [...],
    "websites": [...]
  }
}
```

### Database Layer

| Location | Lines | Component | Purpose | Input | Output |
|----------|-------|-----------|---------|-------|--------|
| **database.py** | 2036-2057 | `get_metadata_table_columns()` | Schema discovery | (none) | List of column names: `['ID', 'REGION', 'COUNTRY', ...]` |
| **database.py** | 2247-2299 | `get_filters_schema_aware()` | Main filter logic | (none) | Dict: `{regions: [], countries: [], brands: [], websites: []}` |
| **database.py** | 2083-2106 | `_get_distinct_regions_from_metadata()` | Query regions | (none) | List: `['NA', 'EMEA', 'APAC']` |
| **database.py** | 2062-2082 | `_get_distinct_values_for_metadata_column()` | Query other columns | column_name='COUNTRY' | List: `['USA', 'UK']` |

### Metadata Table Schema

**File**: backend/src/models/database.py, Lines 526-549

```sql
CREATE TABLE metadata (
    id INTEGER PRIMARY KEY,
    personal_project_id TEXT UNIQUE NOT NULL,
    project_token TEXT UNIQUE,
    project_name TEXT NOT NULL,
    region TEXT,           ← Extracted as "regions"
    country TEXT,          ← Extracted as "countries"
    brand TEXT,            ← Extracted as "brands"
    website_url TEXT,      ← Extracted as "websites"
    total_pages INTEGER,
    total_products INTEGER,
    current_page_scraped INTEGER,
    current_product_scraped INTEGER,
    last_known_url TEXT,
    ...other fields...
)
```

**Indexes**: idx_metadata_region, idx_metadata_country, idx_metadata_brand

---

## Debugging Checklist (In Order)

### Step 1: Frontend Console Logs
**Where to check**: Browser DevTools Console

**What to look for**: Run this command in console:
```javascript
// Should see this log from page.tsx:148-150
[Home] Loaded filters - Regions: X, Countries: Y, Brands: Z, Websites: W
```

**If you see 0 for all**, go to Step 2.

---

### Step 2: Backend API Response
**Where to check**: Check backend logs OR call endpoint directly

```bash
# From terminal:
curl http://localhost:5000/api/filters

# Should return:
{
  "success": true,
  "filters": {
    "regions": [...],
    "countries": [...],
    ...
  }
}
```

**Backend logs to look for** (api_server.py:1282-1283):
```
[API] Getting filter options (schema-aware)...
[API] Filters - Regions: X, Countries: Y, Brands: Z, Websites: W
[API] Full filters object: {...}
```

**If you see 0 for all**, go to Step 3.

---

### Step 3: Database Connection Check
**Where to check**: Backend logs from get_filters_schema_aware() Line 2252

**Look for connection errors**:
```
Error in get_filters_schema_aware: [CONNECTION ERROR MESSAGE]
```

**Test connection manually**:
```python
# From backend directory:
from src.models.database import ParseHubDatabase
db = ParseHubDatabase()
db.connect()  # Should succeed
columns = db.get_metadata_table_columns()
print(f"Columns: {columns}")
```

**If connection fails**, go to Step 4.

---

### Step 4: Metadata Table Column Check
**Where to check**: Database directly OR test script

**SQL Query**:
```sql
SELECT COLUMN_NAME 
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'PARSEHUB_DB' AND TABLE_NAME = 'METADATA'
ORDER BY ORDINAL_POSITION;
```

**Expected columns**: Should include REGION, COUNTRY, BRAND, WEBSITE_URL

**If columns missing**, metadata table likely wasn't created or loaded properly.

---

### Step 5: Metadata Table Data Check
**SQL Query**:
```sql
SELECT COUNT(*) as total_rows,
       SUM(CASE WHEN region IS NOT NULL AND region != '' THEN 1 ELSE 0 END) as regions_with_data,
       SUM(CASE WHEN country IS NOT NULL AND country != '' THEN 1 ELSE 0 END) as countries_with_data,
       SUM(CASE WHEN brand IS NOT NULL AND brand != '' THEN 1 ELSE 0 END) as brands_with_data,
       SUM(CASE WHEN website_url IS NOT NULL AND website_url != '' THEN 1 ELSE 0 END) as websites_with_data
FROM metadata;
```

**Expected**: All count > 0

**If any count is 0**, metadata values are NULL/empty.

---

### Step 6: Individual Filter Query Check
**SQL Queries**:
```sql
-- Regions
SELECT DISTINCT TRIM(region) FROM metadata WHERE region IS NOT NULL AND TRIM(region) != '' ORDER BY 1;

-- Countries  
SELECT DISTINCT "COUNTRY" FROM metadata WHERE "COUNTRY" IS NOT NULL AND "COUNTRY" != '' ORDER BY 1;

-- Brands
SELECT DISTINCT "BRAND" FROM metadata WHERE "BRAND" IS NOT NULL AND "BRAND" != '' ORDER BY 1;

-- Websites
SELECT DISTINCT "WEBSITE_URL" FROM metadata WHERE "WEBSITE_URL" IS NOT NULL AND "WEBSITE_URL" != '' ORDER BY 1;
```

**Expected**: Each returns at least 1 row

---

## Critical Code Inspection Points

### Point 1: Column Name Matching (HIGH RISK)
**File**: database.py, Line 2066

```python
if column_name not in columns:  # Line 2066
    return []  # ← Returns empty if not found!
```

**Issue**: If column_name='COUNTRY' but `columns` has 'country' (lowercase), this fails.

**Check**: Print columns in `get_filters_schema_aware()`:
```python
print(f"[DEBUG] Columns: {columns}")  # Line 2263
print(f"[DEBUG] Checking COUNTRY in {columns}: {'COUNTRY' in columns}")
```

---

### Point 2: Connection State (CRITICAL)
**File**: database.py, Line 2252 & 2298

```python
def get_filters_schema_aware(self) -> dict:
    try:
        self.connect()  # ← Line 2252: Must succeed
        ...
    except Exception as e:
        print(f"Error in get_filters_schema_aware: {e}")  # ← Line 2297
        return {'regions': [], 'countries': [], 'brands': [], 'websites': []}  # ← Line 2298
```

**Check**: Add debug logging:
```python
import traceback
try:
    self.connect()
    print("[DEBUG] Connection successful")
except Exception as e:
    print(f"[ERROR] Connection failed: {e}")
    traceback.print_exc()
```

---

### Point 3: Snowflake Schema Qualification
**File**: database.py, Line 2046-2049

```python
cursor.execute("""
    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'PARSEHUB_DB' AND TABLE_NAME = 'METADATA'
""")
```

**Verify**:
```python
print("[DEBUG] Querying INFORMATION_SCHEMA for PARSEHUB_DB.METADATA")
```

---

## Most Likely Root Causes (Ranked)

1. **Metadata table is empty** (0 rows) → No data to extract
2. **Metadata columns have NULL/empty values** → Filters blank by design
3. **Database connection fails** → Silent return of empty arrays
4. **Snowflake schema not found** → INFORMATION_SCHEMA query returns 0 columns
5. **Column name case mismatch** → 'COUNTRY' vs 'country' comparison fails
6. **Frontend response parsing** → data.filters structure doesn't exist

---

## Quick fixes to try

```python
# In get_filters_schema_aware(), add debug at Line 2252:

def get_filters_schema_aware(self) -> dict:
    print("[DEBUG] Starting get_filters_schema_aware()")
    try:
        self.connect()
        print("[DEBUG] Connection successful")
        
        columns = self.get_metadata_table_columns(auto_disconnect=False)
        print(f"[DEBUG] Retrieved columns: {columns}")
        
        # Count records in metadata
        cursor = self.cursor()
        cursor.execute("SELECT COUNT(*) FROM metadata")
        count = cursor.fetchone()
        print(f"[DEBUG] Metadata table has {count} rows")
        
        # ... rest of logic
```

Add to api_server.py at Line 1281:
```python
logger.info('[API] Checking database state...')
logger.info(f'[API] g.db type: {type(g.db)}')
logger.info(f'[API] g.db.use_snowflake: {getattr(g.db, "use_snowflake", "N/A")}')
```

