# Filter Population: Exact Code Locations & Data Flow

## COMPLETE LINE-BY-LINE REFERENCE

### 1. FRONTEND: [frontend/app/page.tsx](frontend/app/page.tsx)

#### State Declarations
```
Lines 92-98: Filter state variables
─────────────────────────────────────
92    const [regions, setRegions] = useState<string[]>([]);
93    const [countries, setCountries] = useState<string[]>([]);
94    const [brands, setBrands] = useState<string[]>([]);
95    const [websites, setWebsites] = useState<string[]>([]);
96    const [selectedRegion, setSelectedRegion] = useState<string>("");
97    const [selectedCountry, setSelectedCountry] = useState<string>("");
98    const [selectedBrand, setSelectedBrand] = useState<string>("");
```

#### Initial Data Load
```
Lines 114-122: Setup effects & polling
─────────────────────────────────────
114   useEffect(() => {
115     fetchFilters();        ← CALLS fetchFilters() here
116     fetchMetadata();
117     const interval = setInterval(() => {
118       fetchProjects();
119       fetchMetadata();
120     }, 30000); // Refresh every 30s
121     return () => clearInterval(interval);
122   }, []);
```

#### fetchFilters() Function
```
Lines 137-161: Fetch filters from /api/filters endpoint
─────────────────────────────────────────────────────────
137   const fetchFilters = async () => {
138     try {
139       console.log("[Home] Fetching filter options...");
140
141       const response = await apiClient.get("/api/filters");  ← API CALL
142       const data = response.data;
143       console.log("[Home] Successfully fetched filter options");
144
145
146       if (data.filters) {                               ← CHECK structure
147         setRegions(data.filters.regions || []);        ← Extract regions
148         setCountries(data.filters.countries || []);    ← Extract countries
149         setBrands(data.filters.brands || []);          ← Extract brands
150         setWebsites(data.filters.websites || []);      ← Extract websites
151
152         console.log(
153           `[Home] Loaded filters - Regions: ${data.filters.regions?.length || 0}, ` +
154           `Countries: ${data.filters.countries?.length || 0}, ` +
155           `Brands: ${data.filters.brands?.length || 0}, ` +
156           `Websites: ${data.filters.websites?.length || 0}`,
157         );
158       }
159     } catch (err) {
160       console.error("[Home] Error fetching filter options:", extractErrorMessage(err));
161     }
162   };
```

**EXPECTED RESPONSE STRUCTURE at Line 141**:
```json
{
  "success": true,
  "filters": {
    "regions": ["NA", "EMEA", "APAC", ...],
    "countries": ["USA", "UK", ...],
    "brands": ["Brand1", ...],
    "websites": ["amazon.com", ...]
  }
}
```

**CRITICAL**: Line 146 checks `if (data.filters)`. If this is false, arrays stay empty.

#### fetchMetadata() Function
```
Lines 163-175: Fetch metadata (currently just logs)
─────────────────────────────────────────────────────
163   const fetchMetadata = async () => {
164     try {
165       console.log("[Home] Fetching metadata...");
166
167       const params = new URLSearchParams();
168       const response = await apiClient.get("/api/metadata", { params });
169       const data = response.data;
170
171       console.log(
172         "[Home] Successfully fetched",
173         data.count || 0,
174         "metadata records",
175       );
```

---

### 2. API CLIENT: [frontend/lib/apiClient.ts](frontend/lib/apiClient.ts)

#### Client Configuration
```
Lines 12-17: Axios client setup
─────────────────────────────────
12    const apiClient: AxiosInstance = axios.create({
13      baseURL: '',              ← Forces same-origin routing
14      headers: {
15        'Content-Type': 'application/json',
16        ...getApiHeaders(),     ← Adds x-api-key
17      },
18      timeout: 30_000,
19    });
```

---

### 3. BACKEND API: [backend/src/api/api_server.py](backend/src/api/api_server.py)

#### GET /api/filters Endpoint
```
Lines 1279-1300: Main filter API endpoint
──────────────────────────────────────────
1279  @app.route('/api/filters', methods=['GET'])
1280  def get_filters():
1281      """Get all available filter options (schema-aware from metadata table)."""
1282      try:
1283          logger.info('[API] Getting filter options (schema-aware)...')
1284          filters = g.db.get_filters_schema_aware()  ← CALLS DATABASE METHOD
1285          logger.info(
1286              f'[API] Filters - Regions: {len(filters["regions"])}, '
1287              f'Countries: {len(filters["countries"])}, '
1288              f'Brands: {len(filters["brands"])}, '
1289              f'Websites: {len(filters["websites"])}'
1290          )
1291          logger.info(f'[API] Full filters object: {filters}')
1292          return jsonify({
1293              'success': True,
1294              'filters': filters                      ← RESPONSE
1295          }), 200
1296
1297      except Exception as e:
1298          logger.error(f'[API] Error getting filters: {str(e)}')
1299          import traceback
1300          logger.error(traceback.format_exc())
```

**RETURNS**:
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

---

### 4. DATABASE LAYER: [backend/src/models/database.py](backend/src/models/database.py)

#### Main Filter Extraction Method
```
Lines 2247-2299: get_filters_schema_aware()
────────────────────────────────────────────
2247  def get_filters_schema_aware(self) -> dict:
2248      """Return filters using actual metadata columns (schema-aware)."""
2249      CANDIDATES = {
2250          'region': ['region', 'Region', 'msa_region', 'project_region'],
2251          'country': ['country', 'Country', 'msa_country', 'project_country'],
2252          'brand': ['brand', 'Brand', 'msa_brand'],
2253          'website': ['website', 'Website', 'site', 'domain', 'main_site', 'website_url'],
2254      }
2255      try:
2256          # Establish connection once at the start
2257          self.connect()                 ← LINE 2257: CONNECTION ATTEMPT
2258
2259          columns = self.get_metadata_table_columns(auto_disconnect=False)  ← LINE 2259: GET SCHEMA
2260          print(f"[FILTERS] Retrieved {len(columns)} columns: {columns}")
2261          columns_lookup = {c.lower(): c for c in columns}
2262
2263          result = {'regions': [], 'countries': [], 'brands': [], 'websites': []}
2264          region_source = 'none'
2265
2266          # Query regions
2267          if any(k.lower() in columns_lookup for k in CANDIDATES['region']):
2268              result['regions'] = self._get_distinct_regions_from_metadata()  ← LINE 2268
2269              print(f"[FILTERS] Regions: {result['regions']}")
2270              if result['regions']:
2271                  region_source = f'metadata.region'
2272
2273          # Query countries
2274          if any(k.lower() in columns_lookup for k in CANDIDATES['country']):
2275              result['countries'] = self._get_distinct_values_for_metadata_column('COUNTRY')  ← LINE 2275
2276              print(f"[FILTERS] Countries: {result['countries']}")
2277
2278          # Query brands
2279          if any(k.lower() in columns_lookup for k in CANDIDATES['brand']):
2280              result['brands'] = self._get_distinct_values_for_metadata_column('BRAND')  ← LINE 2280
2281              print(f"[FILTERS] Brands: {result['brands']}")
2282
2283          # Query websites
2284          if any(k.lower() in columns_lookup for k in CANDIDATES['website']):
2285              result['websites'] = self._get_distinct_values_for_metadata_column('WEBSITE_URL')  ← LINE 2285
2286              print(f"[FILTERS] Websites count: {len(result['websites'])}")
2287
2288          # Fallback for regions if not found
2289          if not result['regions'] and result['countries']:
2290              result['regions'] = self._infer_regions_from_country_values(result['countries'])
2291              if result['regions']:
2292                  region_source = 'metadata.country->inferred-region'
2293
2294          print(f"[FILTERS] Final result: Regions={len(result['regions'])}, Countries={len(result['countries'])}, Brands={len(result['brands'])}, Websites={len(result['websites'])}")
2295
2296          return result
2297      except Exception as e:
2298          print(f"Error in get_filters_schema_aware: {e}")  ← LINE 2298: ERROR LOG
2299          import traceback
2300          traceback.print_exc()
2301          return {'regions': [], 'countries': [], 'brands': [], 'websites': []}  ← RETURNS EMPTY
2302      finally:
2303          self.disconnect()
```

**FLOW DIAGRAM**:
```
Line 2247: get_filters_schema_aware()
  ├─ Line 2257: self.connect()  <-- MUST SUCCEED
  │
  ├─ Line 2259: get_metadata_table_columns()  <-- GET COLUMN NAMES
  │  │  Returns: ['ID', 'REGION', 'COUNTRY', 'BRAND', 'WEBSITE_URL', ...]
  │  └─ Line 2260-2261: Build columns_lookup with lowercase keys
  │
  ├─ Line 2267-2268: Query regions
  │  └─ _get_distinct_regions_from_metadata()  <-- LINE 2083
  │     Returns: ['NA', 'EMEA', 'APAC']
  │
  ├─ Line 2274-2275: Query countries
  │  └─ _get_distinct_values_for_metadata_column('COUNTRY')  <-- LINE 2062
  │     Returns: ['USA', 'UK', ...]
  │
  ├─ Line 2279-2280: Query brands
  │  └─ _get_distinct_values_for_metadata_column('BRAND')  <-- LINE 2062
  │     Returns: ['Brand1', 'Brand2', ...]
  │
  ├─ Line 2284-2285: Query websites
  │  └─ _get_distinct_values_for_metadata_column('WEBSITE_URL')  <-- LINE 2062
  │     Returns: ['amazon.com', 'ebay.com', ...]
  │
  └─ Line 2296: return result
```

#### Column Discovery Method
```
Lines 2036-2057: get_metadata_table_columns()
──────────────────────────────────────────────
2036  def get_metadata_table_columns(self, auto_disconnect=True) -> list:
2037      """Return column names from Snowflake INFORMATION_SCHEMA."""
2038      try:
2039          self.connect()
2040          cursor = self.cursor()
2041          cursor.execute("""           ← SNOWFLAKE QUERY
2042              SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
2043              WHERE TABLE_SCHEMA = 'PARSEHUB_DB' AND TABLE_NAME = 'METADATA'
2044              ORDER BY ORDINAL_POSITION
2045          """)
2046          rows = cursor.fetchall()
2047          out = [r['COLUMN_NAME'] if isinstance(r, dict) else r[0] for r in rows]
2048          if auto_disconnect:
2049              self.disconnect()
2050          return out    ← Returns: ['ID', 'PERSONAL_PROJECT_ID', ..., 'REGION', 'COUNTRY', ...]
2051      except Exception as e:
2052          print(f"Error getting metadata columns: {e}")
2053          if auto_disconnect:
2054              self.disconnect()
2055          return []    ← Returns EMPTY if error
```

#### Generic Distinct Values Query
```
Lines 2062-2082: _get_distinct_values_for_metadata_column(column_name)
──────────────────────────────────────────────────────────────
2062  def _get_distinct_values_for_metadata_column(self, column_name: str) -> list:
2063      """Return distinct non-null values for a metadata column."""
2064      try:
2065          columns = self.get_metadata_table_columns(auto_disconnect=False)
2066          if column_name not in columns:        ← LINE 2066: CRITICAL CHECK
2067              return []                         ← Returns EMPTY if column not found
2068
2069          cursor = self.cursor()
2070          q = '"' + column_name.replace('"', '""') + '"'
2071          cursor.execute(
2072              f'SELECT DISTINCT {q} FROM metadata WHERE {q} IS NOT NULL AND {q} != \'\' ORDER BY {q}'
2073          )
2074          rows = cursor.fetchall()
2075          out = [r[column_name] if isinstance(r, dict) else r[0] for r in rows]
2076          return out    ← Returns list of values or empty
2077      except Exception as e:
2078          print(f"Error getting distinct values for {column_name}: {e}")
2079          return []
```

**CRITICAL**: Line 2066 checks if `'COUNTRY' in ['ID', 'REGION', 'COUNTRY', ...]`

#### Regions-Specific Query
```
Lines 2083-2106: _get_distinct_regions_from_metadata()
───────────────────────────────────────────────────────
2083  def _get_distinct_regions_from_metadata(self) -> list:
2084      """Return distinct regions from metadata.region using TRIM."""
2085      try:
2086          cursor = self.cursor()
2087          cursor.execute('''                    ← SQL QUERY
2088              SELECT DISTINCT TRIM(region) AS region
2089              FROM metadata
2090              WHERE region IS NOT NULL AND TRIM(region) != ''
2091              ORDER BY 1
2092          ''')
2093          rows = cursor.fetchall()
2094          out = [r.get('region', r[0]) if isinstance(r, dict) else r[0] 
2095                 for r in rows if (r.get('region') if isinstance(r, dict) else r[0])]
2096          return out    ← Returns: ['NA', 'EMEA', 'APAC', ...]
2097      except Exception as e:
2098          print(f"Error getting distinct regions from metadata: {e}")
2099          return []
```

---

### 5. METADATA TABLE SCHEMA

#### Table Definition
```
Lines 526-549: CREATE TABLE metadata
─────────────────────────────────────
526       CREATE TABLE IF NOT EXISTS metadata (
527           id INTEGER PRIMARY KEY AUTOINCREMENT,
528           personal_project_id TEXT UNIQUE NOT NULL,
529           project_id INTEGER,
530           project_token TEXT UNIQUE,
531           project_name TEXT NOT NULL,
532           last_run_date TIMESTAMP,
533           created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
534           updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
535           region TEXT,              ← FILTER COLUMN #1
536           country TEXT,             ← FILTER COLUMN #2
537           brand TEXT,               ← FILTER COLUMN #3
538           website_url TEXT,         ← FILTER COLUMN #4
539           total_pages INTEGER,
540           total_products INTEGER,
541           current_page_scraped INTEGER DEFAULT 0,
542           current_product_scraped INTEGER DEFAULT 0,
543           last_known_url TEXT,
544           import_batch_id INTEGER,
545           status TEXT DEFAULT 'pending',
546           FOREIGN KEY (project_id) REFERENCES projects(id),
547           FOREIGN KEY (import_batch_id) REFERENCES import_batches(id),
548           FOREIGN KEY (project_token) REFERENCES projects(token)
549       )
```

#### Indexes Created
```
Lines 551-560: CREATE INDEX statements
─────────────────────────────────────
551   CREATE INDEX IF NOT EXISTS idx_metadata_region ON metadata(region)
552   CREATE INDEX IF NOT EXISTS idx_metadata_country ON metadata(country)
553   CREATE INDEX IF NOT EXISTS idx_metadata_brand ON metadata(brand)
554   CREATE INDEX IF NOT EXISTS idx_metadata_updated_date ON metadata(updated_date)
```

---

## EXECUTION ORDER & DATA FLOW

```
USER LOADS HOME PAGE
         ↓
Line 114-122 (page.tsx): useEffect runs on mount
         ↓
Line 115 (page.tsx): fetchFilters() called
         ↓
Line 141 (page.tsx): apiClient.get("/api/filters")
         ↓
Line 1279 (api_server.py): @app.route('/api/filters')
         ↓
Line 1284 (api_server.py): g.db.get_filters_schema_aware()
         ↓
Line 2257 (database.py): self.connect() ← CONNECTION ATTEMPT #1
         ↓
Line 2259 (database.py): get_metadata_table_columns() ← SCHEMA DISCOVERY
         ↓
Line 2041-2045 (database.py): Query INFORMATION_SCHEMA.COLUMNS
         ↓
Receives: ['ID', 'REGION', 'COUNTRY', 'BRAND', 'WEBSITE_URL', ...]
         ↓
Line 2268 (database.py): _get_distinct_regions_from_metadata()
         ↓
Line 2087-2091 (database.py): SELECT DISTINCT TRIM(region) FROM metadata ...
         ↓
Returns: ['NA', 'EMEA', ...] or []
         ↓
Line 2275 (database.py): _get_distinct_values_for_metadata_column('COUNTRY')
         ↓
Line 2073 (database.py): SELECT DISTINCT "COUNTRY" FROM metadata ...
         ↓
Returns: ['USA', 'UK', ...] or []
         ↓
[Similar for BRAND and WEBSITE_URL]
         ↓
Line 2296 (database.py): return { regions: [...], countries: [...], ... }
         ↓
Line 1294 (api_server.py): return jsonify({ 'success': True, 'filters': {...} })
         ↓
Line 141 (page.tsx): Response received
         ↓
Line 146 (page.tsx): if (data.filters)
         ↓
Lines 147-150 (page.tsx): setRegions(), setCountries(), setBrands(), setWebsites()
         ↓
Lines 152-157 (page.tsx): Console log shows filter counts
         ↓
FILTERS POPULATED (or empty)
```

---

## FAILURE POINTS (Where 0-item filters originate)

| # | Location | Point | Condition | Result | Fix |
|---|----------|-------|-----------|--------|-----|
| 1 | p.2257 | Connection | `self.connect()` fails | Exception caught, returns `[]` | Check DB credentials |
| 2 | p.2259 | Schema | `get_metadata_table_columns()` returns `[]` | Columns not detected | Check Snowflake schema |
| 3 | p.2066 | Column check | `'COUNTRY' not in columns` | Returns `[]` at line 2067 | Case mismatch? |
| 4 | p.2287-2291 | Metadata empty | `SELECT DISTINCT ... FROM metadata` returns 0 rows | Empty result sets | Load metadata |
| 5 | p.2090, 2072 | WHERE clause | `WHERE region IS NOT NULL` filters all rows | Empty result sets | Check data values |
| 6 | p.146 | Response parse | `data.filters` undefined | Skip setters | Check API response |

---

## DEBUG LOGGING LOCATIONS

Add these to identify failure point:

**In database.py Line 2259** (after get_metadata_table_columns):
```python
columns = self.get_metadata_table_columns(auto_disconnect=False)
print(f"[DEBUG] Columns retrieved: {columns}")
if not columns:
    print("[DEBUG] WARNING: No columns found! Schema query failed.")
```

**In database.py Line 2066** (before column check):
```python
columns = self.get_metadata_table_columns(auto_disconnect=False)
print(f"[DEBUG] Checking column '{column_name}' in {columns}")
if column_name not in columns:
    print(f"[DEBUG] WARNING: Column '{column_name}' not found!")
    return []
```

**In api_server.py Line 1283** (before filter call):
```python
logger.info(f'[API] g.db object: {type(g.db)}')
logger.info(f'[API] g.db methods: {dir(g.db)}')
```

