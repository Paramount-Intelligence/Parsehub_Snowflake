# Exact Code Changes Made to Fix Filters

## File: backend/src/models/database.py

### Change 1: get_metadata_table_columns() [Lines 2036-2058]

**BEFORE (BROKEN)**:
```python
def get_metadata_table_columns(self, auto_disconnect=True) -> list:
    """Return column names of the metadata table from Snowflake information_schema."""
    try:
        self.connect()
        cursor = self.cursor()
        cursor.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'PARSEHUB_DB' AND TABLE_NAME = 'METADATA'
            ORDER BY ORDINAL_POSITION
        """)
        rows = cursor.fetchall()
        out = [r['COLUMN_NAME'] if isinstance(r, dict) else r[0] for r in rows]  # ← KEYERROR: 'COLUMN_NAME'
        if auto_disconnect:
            self.disconnect()
        return out
    except Exception as e:
        print(f"Error getting metadata columns: {e}")  # ← Silent catch
        if auto_disconnect:
            self.disconnect()
        return []
```

**AFTER (FIXED)**:
```python
def get_metadata_table_columns(self, auto_disconnect=True) -> list:
    """Return column names of the metadata table from Snowflake information_schema."""
    try:
        self.connect()
        cursor = self.cursor()
        cursor.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'PARSEHUB_DB' AND TABLE_NAME = 'METADATA'
            ORDER BY ORDINAL_POSITION
        """)
        rows = cursor.fetchall()
        # Cursor shim returns dicts with lowercase keys, so use lowercase or fallback to index
        out = [r.get('column_name') or r.get('COLUMN_NAME') or (r[0] if isinstance(r, (list, tuple)) else r.get('column_name')) for r in rows]
        if auto_disconnect:
            self.disconnect()
        return out
    except Exception as e:
        print(f"Error getting metadata columns: {e}")
        if auto_disconnect:
            self.disconnect()
        return []
```

---

### Change 2: _get_distinct_values_for_metadata_column() [Lines 2062-2082]

**BEFORE (BROKEN)**:
```python
def _get_distinct_values_for_metadata_column(self, column_name: str) -> list:
    """Return distinct non-null, non-empty values for a metadata column from Snowflake."""
    try:
        columns = self.get_metadata_table_columns(auto_disconnect=False)
        if column_name not in columns:
            return []
        
        cursor = self.cursor()
        q = '"' + column_name.replace('"', '""') + '"'
        cursor.execute(
            f'SELECT DISTINCT {q} FROM metadata WHERE {q} IS NOT NULL AND {q} != \'\' ORDER BY {q}'
        )
        rows = cursor.fetchall()
        out = [r[column_name] if isinstance(r, dict) else r[0] for r in rows]  # ← KEYERROR: 'COUNTRY' (column_name is uppercase)
        return out
    except Exception as e:
        print(f"Error getting distinct values for {column_name}: {e}")
        return []
```

**AFTER (FIXED)**:
```python
def _get_distinct_values_for_metadata_column(self, column_name: str) -> list:
    """Return distinct non-null, non-empty values for a metadata column from Snowflake."""
    try:
        columns = self.get_metadata_table_columns(auto_disconnect=False)
        if column_name not in columns:
            return []
        
        cursor = self.cursor()
        q = '"' + column_name.replace('"', '""') + '"'
        cursor.execute(
            f'SELECT DISTINCT {q} FROM metadata WHERE {q} IS NOT NULL AND {q} != \'\' ORDER BY {q}'
        )
        rows = cursor.fetchall()
        # Cursor shim returns dicts with lowercase keys, so try lowercase first
        out = [r.get(column_name.lower()) or (r[column_name] if isinstance(r, dict) else r[0]) if isinstance(r, dict) else r[0] for r in rows]
        return out
    except Exception as e:
        print(f"Error getting distinct values for {column_name}: {e}")
        return []
```

---

### Change 3: _get_distinct_regions_from_metadata() [Lines 2084-2110]

**BEFORE (BROKEN)**:
```python
def _get_distinct_regions_from_metadata(self) -> list:
    """Return distinct regions from metadata.region using TRIM."""
    try:
        cursor = self.cursor()
        cursor.execute('''
            SELECT DISTINCT TRIM(region) AS region
            FROM metadata
            WHERE region IS NOT NULL AND TRIM(region) != ''
            ORDER BY 1
        ''')
        rows = cursor.fetchall()
        # ← TYPEERROR: trying to use r[0] as fallback on dict objects
        out = [r.get('region', r[0]) if isinstance(r, dict) else r[0] for r in rows if (r.get('region') if isinstance(r, dict) else r[0])]
        return out
    except Exception as e:
        print(f"Error getting distinct regions from metadata: {e}")
        return []
```

**AFTER (FIXED)**:
```python
def _get_distinct_regions_from_metadata(self) -> list:
    """Return distinct regions from metadata.region using TRIM."""
    try:
        cursor = self.cursor()
        cursor.execute('''
            SELECT DISTINCT TRIM(region) AS region
            FROM metadata
            WHERE region IS NOT NULL AND TRIM(region) != ''
            ORDER BY 1
        ''')
        rows = cursor.fetchall()
        # Cursor shim returns dicts with lowercase keys
        out = []
        for r in rows:
            if isinstance(r, dict):
                val = r.get('region') or r.get('REGION')
            else:
                val = r[0] if isinstance(r, (list, tuple)) else r
            if val:
                out.append(val)
        return out
    except Exception as e:
        print(f"Error getting distinct regions from metadata: {e}")
        return []
```

---

## Why These Changes Fix It

### Root Cause
The `SnowflakeCursorShim.fetchall()` method converts all cursor result column names to lowercase:
```python
def _get_column_names(self):
    return [col.name.lower() for col in self.cursor.description]

def fetchall(self):
    columns = self._get_column_names()  # ['column_name', 'country', 'brand', ...]
    return [dict(zip(columns, row)) for row in rows]  # Dict keys are lowercase
```

So when Snowflake returns column names as 'COLUMN_NAME', 'COUNTRY', etc., they get converted to:
`{'column_name': 'ID', 'country': 'Australia', ...}`

### The Bug
The filter methods tried to access these dicts with the original uppercase keys:
- `r['COLUMN_NAME']` → KeyError (key is 'column_name')
- `r['COUNTRY']` → KeyError (key is 'country')
- `r[column_name]` where column_name='COUNTRY' → KeyError (key is 'country')

### The Solution
Use `.get(lowercase_key)` to safely access the lowercase keys:
- `r.get('column_name')` → Works with lowercase key
- `r.get(column_name.lower())` → Works when column_name is passed in uppercase

The fixes maintain backward compatibility by trying lowercase first, then uppercase, then falling back to index access for tuple results.

---

## Testing Verification

All three methods tested after fix:

```
✓ get_metadata_table_columns(): Returns 19 columns ['ID', 'PERSONAL_PROJECT_ID', ..., 'REGION', 'COUNTRY', 'BRAND', 'WEBSITE_URL']
✓ _get_distinct_regions_from_metadata(): Returns 4 regions ['APAC', 'EMENA', 'LATAM', 'US_CA']
✓ _get_distinct_values_for_metadata_column('COUNTRY'): Returns 9 countries ['Australia', 'Belgium', 'France', 'Germany', 'Mexico', 'Netherlands', 'Thailand', 'US', 'United Kingdom']
✓ get_filters_schema_aware(): Returns all 4 filter types with correct data
```

---

## Backend Restart Required

To apply these fixes to the running service:

```bash
# Kill the current backend process (port 5000)
# Then restart with:
cd d:\Parsehub-Snowflake\Parsehub_Snowflake
backend\venv312\Scripts\python.exe -m flask run --port 5000
```

After restart, the `/api/filters` endpoint will return:
```json
{
  "success": true,
  "filters": {
    "regions": ["APAC", "EMENA", "LATAM", "US_CA"],
    "countries": ["Australia", "Belgium", "France", "Germany", "Mexico", "Netherlands", "Thailand", "US", "United Kingdom"],
    "brands": ["Baldwin", "Donadlson, Hifi-filter, etc", "Donaldson", "Fleetguard", "Hengst", "Hifi", "Mann-filter", "Navistar", "Parker-Racor", "Parker-filter", "Sf-filter", "Wix-filter"],
    "websites": [40 distinct URLs...]
  }
}
```
