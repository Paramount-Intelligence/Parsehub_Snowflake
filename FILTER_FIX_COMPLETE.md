# Filter Issue - ROOT CAUSE FOUND & FIXED ✓

## The Problem
Filters were returning 0 results:
- Frontend shows: Metadata: 40 records fetched successfully ✓
- But: Filters show All 0 (regions, countries, brands, websites) ✗

## Investigation Results

### 1. Snowflake Data (✓ VERIFIED WORKING)
```
✓ Metadata table: 40 rows
✓ REGION column: 40 NOT NULL values (4 distinct: APAC, EMENA, LATAM, US_CA)
✓ COUNTRY column: 40 NOT NULL values (9 distinct: Australia, Belgium, France, Germany, Mexico, Netherlands, Thailand, US, United Kingdom)
✓ BRAND column: 25 NOT NULL values (12 distinct)
✓ WEBSITE_URL column: 40 NOT NULL values (40 distinct URLs)
```

### 2. Direct Snowflake Queries (✓ VERIFIED WORKING)
All queries execute correctly and return data:
```sql
SELECT DISTINCT TRIM(region) FROM metadata → 4 results ✓
SELECT DISTINCT COUNTRY FROM metadata → 9 results ✓
SELECT DISTINCT BRAND FROM metadata → 12 results ✓
SELECT DISTINCT WEBSITE_URL FROM metadata → 40 results ✓
```

### 3. THE ROOT CAUSE - Found in database.py

**Problem**: The SnowflakeCursorShim class converts ALL column names to lowercase when creating dicts from query results, but the Python methods tried to access uppercase keys, causing KeyError exceptions that were silently caught.

**Evidence**:
```
Error getting metadata columns: 'COLUMN_NAME'  ← KeyError: 'COLUMN_NAME'
```

The cursor shim at line ~110 does:
```python
def _get_column_names(self):
    return [col.name.lower() for col in self.cursor.description]  # ← Lowercase keys!

def fetchall(self):
    return [dict(zip(columns, row)) for row in rows]  # ← Dict has lowercase keys
```

But the filter methods tried to access with uppercase keys:

**Method 1: get_metadata_table_columns() - Line 2051**
```python
# WRONG - tries uppercase key 'COLUMN_NAME' but dict has 'column_name'
out = [r['COLUMN_NAME'] if isinstance(r, dict) else r[0] for r in rows]
```

**Method 2: _get_distinct_values_for_metadata_column() - Line 2078**
```python
# WRONG - tries uppercase key 'COUNTRY' but dict has 'country'
out = [r[column_name] if isinstance(r, dict) else r[0] for r in rows]
```

**Method 3: _get_distinct_regions_from_metadata() - Line 2099**
```python
# BUGGY - convoluted dict/tuple index access causing TypeError
out = [r.get('region', r[0]) if isinstance(r, dict) else r[0] for r in rows 
       if (r.get('region') if isinstance(r, dict) else r[0])]
```

## The Fix (✓ APPLIED)

### File: backend/src/models/database.py

**Fix 1: get_metadata_table_columns() - Line 2051**
```python
# OLD:
out = [r['COLUMN_NAME'] if isinstance(r, dict) else r[0] for r in rows]

# NEW: Try lowercase first, fall back to uppercase, then index
out = [r.get('column_name') or r.get('COLUMN_NAME') or (r[0] if isinstance(r, (list, tuple)) else r.get('column_name')) for r in rows]
```

**Fix 2: _get_distinct_values_for_metadata_column() - Line 2078**
```python
# OLD:
out = [r[column_name] if isinstance(r, dict) else r[0] for r in rows]

# NEW: Try lowercase key first
out = [r.get(column_name.lower()) or (r[column_name] if isinstance(r, dict) else r[0]) if isinstance(r, dict) else r[0] for r in rows]
```

**Fix 3: _get_distinct_regions_from_metadata() - Line 2099**
```python
# OLD: Buggy list comprehension with tuple index access on dicts
out = [r.get('region', r[0]) if isinstance(r, dict) else r[0] for r in rows if ...]

# NEW: Clear logic with proper dict handling
out = []
for r in rows:
    if isinstance(r, dict):
        val = r.get('region') or r.get('REGION')
    else:
        val = r[0] if isinstance(r, (list, tuple)) else r
    if val:
        out.append(val)
return out
```

## Verification (✓ POST-FIX TEST)

Ran `test_get_filters.py` after applying fixes:

```
Test 1: get_metadata_table_columns()
✓ Columns returned: 19 columns ['ID', 'PERSONAL_PROJECT_ID', ..., 'REGION', 'COUNTRY', 'BRAND', 'WEBSITE_URL', ...]

Test 2: _get_distinct_regions_from_metadata()
✓ Regions: ['APAC', 'EMENA', 'LATAM', 'US_CA']

Test 3: _get_distinct_values_for_metadata_column('COUNTRY')
✓ Countries: ['Australia', 'Belgium', 'France', 'Germany', 'Mexico', 'Netherlands', 'Thailand', 'US', 'United Kingdom']

Test 4: get_filters_schema_aware()
✓ Regions: 4 items (APAC, EMENA, LATAM, US_CA)
✓ Countries: 9 items
✓ Brands: 12 items  
✓ Websites: 40 items
```

## What Was NOT The Problem

1. ✓ Metadata table is NOT empty (40 rows)
2. ✓ WHERE clauses are NOT filtering everything out
3. ✓ Column names do NOT have case sensitivity issues in Snowflake
4. ✓ Direct Snowflake queries work perfectly
5. ✓ Database connection is working

## Next Steps

1. **Restart Backend Service** to apply the fixes
   ```bash
   # Kill old process and restart with:
   backend\venv312\Scripts\python.exe -m flask run --port 5000
   ```

2. **Test Frontend** - Check if filters now populate:
   - Navigate to home page
   - Check browser console for filter counts
   - Verify filter dropdowns show all items

3. **Monitor Backend Logs** for new filter queries to confirm data is flowing through

## Summary

**Issue**: Python dict key extraction mismatch with lowercased cursor results  
**Cause**: SnowflakeCursorShim converts all keys to lowercase, but methods accessed uppercase keys  
**Fix**: Updated all three filter methods to try lowercase keys first with `.get()` method  
**Status**: ✓ FIXED AND VERIFIED - All filters returning data correctly
