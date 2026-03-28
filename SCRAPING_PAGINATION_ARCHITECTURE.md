# ParseHub Scraping & Pagination Architecture Overview

**Last Updated:** March 25, 2026  
**Status:** Pre-Refactoring Analysis

---

## 1. CURRENT CHECKPOINT STRATEGY

### 1.1 Database Schema for Checkpoints

**Primary Checkpoint Tables:**
- `run_checkpoints` - Stores progress snapshots during scraping
- `scraping_sessions` - Tracks incremental scraping campaigns
- `iteration_runs` - Records each individual ParseHub run within a session
- `combined_scraped_data` - Consolidated final results from all iterations

### 1.2 Checkpoint Data Structure

**Location:** [backend/src/models/database.py](backend/src/models/database.py#L345)

```python
# run_checkpoints table structure
- id: INTEGER PRIMARY KEY
- run_id: INTEGER (FK to runs)
- snapshot_timestamp: TIMESTAMP
- item_count_at_time: INTEGER
- items_per_minute: REAL
- estimated_completion_time: TIMESTAMP
- created_at: TIMESTAMP

# Key checkpoints tracked:
1. 'target_pages' - Total pages to scrape (stored in checkpoint_data JSON)
2. 'last_page' - Last page successfully scraped
3. Pagination state with current_page_scraped in metadata table
```

### 1.3 Metadata-Based Tracking

**Location:** [backend/src/models/database.py](backend/src/models/database.py#L560) - `metadata` table

Progress fields per project:
- `total_pages: INTEGER` - Target number of pages to scrape
- `total_products: INTEGER` - Expected product count
- `current_page_scraped: INTEGER` - Last page completed (DEFAULT 0)
- `current_product_scraped: INTEGER` - Last product index (DEFAULT 0)
- `last_known_url: VARCHAR(1000)` - Last successfully scraped URL
- `status: VARCHAR(50)` - Project status (pending/running/complete/failed)
- `last_run_date: TIMESTAMP` - Timestamp of last execution

**How it works:**
- The incremental scraping manager reads `current_page_scraped < total_pages`
- If incomplete, triggers continuation starting from `current_page_scraped + 1`
- Updates metadata after each run completes

---

## 2. CURRENT PAGINATION STRATEGY

### 2.1 URL-Based Pagination Detection

**Location:** [backend/src/utils/url_generator.py](backend/src/utils/url_generator.py)

**Supported Pagination Patterns:**

| Pattern Type | Regex | Example |
|---|---|---|
| Query Page | `[?&]page=(\d+)` | `example.com?page=5` |
| Query p | `[?&]p=(\d+)` | `example.com?p=5` |
| Query Offset | `[?&]offset=(\d+)` | `example.com?offset=100` |
| Query Start | `[?&]start=(\d+)` | `example.com?start=100` |
| Path Page | `/page[/-](\d+)` | `example.com/page/5` or `/page-5` |
| Path p | `/p/(\d+)` | `example.com/p/5` |
| Path Products | `/products/page[/-](\d+)` | `example.com/products/page/5` |
| Query Custom | `[?&](\w+)=(\d+)` | Generic catch-all for unknown params |

**Detection Method:**
```python
URLGenerator.detect_pattern(url) -> Dict
# Returns:
{
    'pattern_type': 'query_page' | 'path_page' | etc,
    'pattern_regex': regex string,
    'current_page': extracted page number,
    'match_groups': regex groups
}
```

### 2.2 URL Generation for Next Page

**Location:** [backend/src/utils/url_generator.py](backend/src/utils/url_generator.py#L55)

```python
URLGenerator.generate_next_url(url, next_page_number, pattern_info)
```

**Strategy:**
1. Detects pagination pattern
2. Uses regex substitution to replace page number
3. For offset-based: calculates new offset as `(page - 1) * 20`
4. Fallback: appends `?page=N` if no pattern detected

### 2.3 Pagination Service

**Location:** [backend/src/services/pagination_service.py](backend/src/services/pagination_service.py)

**Key Methods:**
- `extract_page_number(url)` - Extract current page from URL
- `generate_next_page_url(base_url, current_page)` - Generate next page URL
- `detect_pagination_pattern(url)` - Detect pagination style
- `check_pagination_needed(project_id, target_pages)` - Check if recovery needed
- `create_recovery_project_info(url, current_page, target_pages)` - Prepare recovery data
- `record_scraping_progress(project_id, page_number, data_count, items_per_minute)` - Log progress

---

## 3. DATA PER SCRAPE RUN

### 3.1 Run-Level Storage

**Location:** [backend/src/models/database.py](backend/src/models/database.py#L280) - `runs` table

```
Run Record Fields:
- id: INTEGER PRIMARY KEY (auto-increment)
- project_id: INTEGER FK
- run_token: TEXT UNIQUE (from ParseHub API)
- status: TEXT (starting, running, completed, failed)
- pages_scraped: INTEGER
- start_time: TIMESTAMP
- end_time: TIMESTAMP
- duration_seconds: INTEGER
- records_count: INTEGER (total products/items scraped)
- data_file: TEXT (path to CSV/export)
- is_empty: BOOLEAN
- is_continuation: BOOLEAN (marks runs that continue from previous)
- completion_percentage: REAL (0.0-100.0)
- created_at, updated_at: TIMESTAMPS
```

### 3.2 Scraped Data Storage

**Location:** [backend/src/models/database.py](backend/src/models/database.py#L317) - `scraped_data` table (legacy format)

```
- id: INTEGER PRIMARY KEY
- run_id: INTEGER FK
- project_id: INTEGER FK
- data_key: TEXT (field name)
- data_value: TEXT (field value)
- created_at: TIMESTAMP
```

**Modern Product Data Format:**

**Location:** [backend/src/models/database.py](backend/src/models/database.py#L680) - `product_data` table

```
- id: INTEGER PRIMARY KEY
- project_id: INTEGER FK
- run_id: INTEGER FK
- run_token: TEXT
- name: TEXT
- part_number: TEXT
- brand: TEXT
- list_price: REAL
- sale_price: REAL
- case_unit_price: REAL
- country: TEXT
- currency: TEXT
- product_url: TEXT
- page_number: INTEGER (which page this came from)
- extraction_date: TIMESTAMP
- data_source: TEXT
- created_at, updated_at: TIMESTAMPS
- UNIQUE(project_id, run_token, product_url, page_number)
```

### 3.3 Data Lineage & Recovery Info

**Location:** [backend/src/models/database.py](backend/src/models/database.py#L365) - `data_lineage` table

```
- id: INTEGER PRIMARY KEY
- scraped_data_id: INTEGER FK
- source_run_id: INTEGER FK
- recovery_operation_id: INTEGER FK
- is_duplicate: BOOLEAN
- duplicate_of_data_id: INTEGER
- product_url: TEXT
- product_hash: TEXT (for deduplication)
- created_at: TIMESTAMP
```

---

## 4. RUN ORCHESTRATION

### 4.1 Trigger Mechanisms

#### 4.1.1 Incremental Scraping Manager
**Location:** [backend/src/services/incremental_scraping_manager.py](backend/src/services/incremental_scraping_manager.py)

**Main Flow:**
1. `check_and_match_pages()` - Scans all projects with metadata
2. Compares `current_page_scraped < total_pages`
3. If incomplete:
   - Calculates `start_page = current_page_scraped + 1`
   - Modifies URL for next page using `modify_url_for_page()`
   - Triggers continuation run

**Key Method:**
```python
IncrementalScrapingManager.trigger_continuation_run(
    project_token,
    project_id,
    start_page,
    total_pages,
    pages_to_scrape,
    project_name
)
# Returns: {'success': True, 'run_token': '...', ...}
```

**Database Storage:**
```python
store_continuation_run(
    original_project_id,
    continuation_token,
    run_token,
    start_page,
    pages_count
)
# Inserts into runs table with is_continuation=TRUE
```

#### 4.1.2 Auto Runner Service
**Location:** [backend/src/services/auto_runner_service.py](backend/src/services/auto_runner_service.py)

**New Iteration-Based Approach** (recommended):
```python
execute_iteration(
    session_id,
    iteration_number,
    original_project_token,
    project_name,
    start_page,
    end_page,
    original_url
)
```

**Flow:**
1. Generates next URL using URLGenerator
2. Triggers run directly with custom URL: `project/run?start_url=...`
3. Waits for completion
4. Fetches CSV data
5. Updates session and iteration_runs table

#### 4.1.3 API Triggers
**Location:** [backend/src/api/api_server.py](backend/src/api/api_server.py)

**Endpoints:**
- `POST /api/runs/batch-execute` - Batch run execution
- `POST /api/monitor/start` - Start real-time monitoring
- `POST /api/runs/<run_token>/cancel` - Cancel a run

### 4.2 Scheduling

**Location:** [backend/src/services/incremental_scraping_scheduler.py](backend/src/services/incremental_scraping_scheduler.py)

**Background Service:**
- Runs in separate thread
- Configurable check interval (default: 30 minutes)
- Calls `IncrementalScrapingManager.check_and_match_pages()` periodically
- Monitors continuation runs for status updates

**Usage:**
```python
# In api_server.py initialization:
start_incremental_scraping_scheduler(check_interval_minutes=30)
stop_incremental_scraping_scheduler()
```

### 4.3 Session-Based Orchestration

**Location:** [backend/src/services/scraping_session_service.py](backend/src/services/scraping_session_service.py)

**Session Management:**
```python
# Create session for multi-page scraping
session = ScrapingSessionService().create_session(
    project_token,
    project_name,
    total_pages_target=100
)
# Returns: {'success': True, 'session_id': 1}

# Add iteration
iteration = session_service.add_iteration_run(
    session_id,
    iteration_number=1,
    parsehub_project_token,
    project_name,
    start_page,
    end_page,
    run_token
)

# Update progress
session_service.update_iteration_run(
    run_id,
    csv_data,
    records_count,
    status='completed'
)

# Get consolidated results
combined = session_service.get_combined_data(session_id)
```

---

## 5. DATA PERSISTENCE LAYER

### 5.1 Database Architecture

**Location:** [backend/src/models/database.py](backend/src/models/database.py)

**Connection Management:**
- Uses **Snowflake** connection (not SQLite - fully migrated)
- Thread-local connection pooling via `threading.local()`
- Connection caching per thread
- Implementation: `ParseHubDatabase` class

**Schema Initialization:**
```python
self.db.init_db()  # Called at startup
# Creates all tables if they don't exist
```

### 5.2 Data Ingestion Pipeline

**Location:** [backend/src/services/data_ingestion_service.py](backend/src/services/data_ingestion_service.py)

**Ingestion Flow:**
```python
ingestor = ParseHubDataIngestor()

# 1. Fetch run data
run_data = ingestor.get_run_data(run_token)

# 2. Extract products from nested structure
products = ingestor.get_run_output_data(run_token)

# 3. Normalize product records
for product in products:
    normalized = ingestor._normalize_product_record(product)

# 4. Insert into database
result = db.insert_product_data(
    project_id,
    run_id,
    run_token,
    product_data_list
)
```

**Field Mapping Logic:**
Maps common field names to standard columns:
- `part_number`: partnumber, sku, article, product_code
- `name`: product_name, title, description
- `brand`: manufacturer, vendor
- `sale_price`: price, current_price, selling_price
- `product_url`: url, link, href
- Custom fields preserved as-is

### 5.3 Export & Analytics Storage

**Location:** [backend/src/models/database.py](backend/src/models/database.py#L655)

```
CSV Exports Table (csv_exports):
- id: INTEGER PRIMARY KEY
- project_token: TEXT UNIQUE
- run_token: TEXT
- csv_data: TEXT (full CSV content)
- row_count: INTEGER
- stored_at, updated_at: TIMESTAMPS

Analytics Cache (analytics_cache):
- id: INTEGER PRIMARY KEY
- project_token: TEXT UNIQUE
- run_token: TEXT
- total_records: INTEGER
- total_fields: INTEGER
- total_runs: INTEGER
- completed_runs: INTEGER
- progress_percentage: REAL
- status: TEXT
- analytics_json: TEXT
- stored_at, updated_at: TIMESTAMPS

Analytics Records (analytics_records):
- Individual scraped records for display
- Indexed by project_token, run_token, record_index
```

---

## 6. EXISTING STATE & RESUME LOGIC

### 6.1 Recovery Service

**Location:** [backend/src/services/recovery_service.py](backend/src/services/recovery_service.py)

**Auto-Recovery Features:**

1. **Stopped Detection:**
   ```python
   check_project_status(project_token)
   # Detects if run is stuck (no data for 5+ minutes)
   # Returns: 'running', 'completed', 'cancelled', 'stuck', 'error'
   ```

2. **Last Product Tracking:**
   ```python
   get_last_product_url(run_token)
   # Fetches last successful product via /data endpoint
   # Extracts URL and name for recovery start point
   ```

3. **Next Page URL Detection:**
   ```python
   detect_next_page_url(current_url, pagination_pattern)
   # Determines next URL to continue from
   ```

4. **Recovery Project Creation:**
   ```python
   create_recovery_project(original_project_token, last_product_url)
   # Creates new project clone for recovery
   # Clones template, uses next URL
   ```

5. **Deduplication:**
   ```python
   deduplicate_data(original_run_id, recovery_run_id)
   # Compares URLs from both runs
   # Identifies duplicates and new items
   # Returns merge statistics
   ```

### 6.2 Recovery Operations Tracking

**Location:** [backend/src/models/database.py](backend/src/models/database.py#L329) - `recovery_operations` table

```
- id: INTEGER PRIMARY KEY
- original_run_id: INTEGER FK
- recovery_run_id: INTEGER FK
- project_id: INTEGER FK
- original_project_token: TEXT
- recovery_project_token: TEXT
- last_product_url: TEXT
- last_product_name: TEXT
- stopped_timestamp: TIMESTAMP
- recovery_triggered_timestamp: TIMESTAMP
- recovery_started_timestamp: TIMESTAMP
- recovery_completed_timestamp: TIMESTAMP
- status: TEXT (pending, in_progress, completed, failed)
- original_data_count: INTEGER
- recovery_data_count: INTEGER
- final_data_count: INTEGER (after dedup)
- duplicates_removed: INTEGER
- attempt_number: INTEGER
- error_message: TEXT
- created_at: TIMESTAMP
```

### 6.3 Continuation Run Storage

**Current Implementation:**

Projects with incomplete scraping are marked via:
1. `metadata.current_page_scraped < metadata.total_pages`
2. `runs.is_continuation = TRUE` (for runs that continue)
3. Incremental runs tracked in `iteration_runs` with session linkage

**State Restoration:**
```python
# Check if pagination recovery needed
check_result = pagination_service.check_pagination_needed(
    project_id,
    target_pages
)
# Returns:
{
    'needs_recovery': True/False,
    'last_page_scraped': N,
    'target_pages': M,
    'total_data_count': K,
    'pages_remaining': M - N
}
```

---

## 7. COMPLETE WORKFLOW EXAMPLES

### 7.1 Incremental Scraping Workflow (Current)

```
1. Scheduler runs check_and_match_pages() every 30 min
   ↓
2. Query: metadata WHERE current_page_scraped < total_pages
   ↓
3. For each incomplete project:
   a. Calculate next_page = current_page_scraped + 1
   b. Modify URL for pagination
   c. Call trigger_continuation_run(project_token, next_page)
      ↓
4. API creates run with modified URL
   ↓
5. Run completes, data ingested
   ↓
6. update metadata.current_page_scraped = new_page
   ↓
7. Next check: repeat from step 2 if still incomplete
```

### 7.2 Session-Based Multi-Page Workflow (New)

```
1. Create session (target pages = 100)
   ↓
2. Start iteration 1:
   a. Generate URL for pages 1-10
   b. Create iteration_run record
   c. Trigger run with custom URL
   d. Wait for completion
   e. Ingest data
   f. Update iteration_run with CSV data
   ↓
3. Consolidate data (deduplicate)
   ↓
4. Update session progress
   ↓
5. Repeat for next pages if target not reached
   ↓
6. Mark session complete, save combined_scraped_data
```

### 7.3 Recovery Workflow

```
1. check_project_status(token) → 'stuck'
   ↓
2. get_last_product_url(run_token)
   ↓
3. detect_next_page_url(last_url)
   ↓
4. create_recovery_project(original_token, next_url)
   ↓
5. start_recovery_run(new_token)
   ↓
6. Wait for completion
   ↓
7. deduplicate_data(original_run_id, recovery_run_id)
   ↓
8. Store results in recovery_operations table
   ↓
9. Merge final datasets
```

---

## 8. KEY TABLES SUMMARY

| Table | Purpose | Key Columns |
|-------|---------|------------|
| `metadata` | Project scraping targets & progress | total_pages, current_page_scraped, status |
| `runs` | Individual execution records | project_id, run_token, pages_scraped, is_continuation |
| `run_checkpoints` | Progress snapshots | run_id, item_count_at_time, items_per_minute |
| `scraping_sessions` | Multi-page scraping campaigns | project_token, total_pages_target, pages_completed |
| `iteration_runs` | ParseHub runs within sessions | session_id, start_page, end_page, run_token |
| `combined_scraped_data` | Consolidated multi-run results | session_id, consolidated_csv, total_records |
| `product_data` | Normalized product records | project_id, run_id, name, part_number, product_url |
| `recovery_operations` | Stuck/failed run recovery tracking | original_run_id, recovery_run_id, status |
| `scraping_sessions` | URL pattern storage | project_token, original_url, pattern_type |

---

## 9. IMPORTANT NOTES FOR REFACTORING

### Current Limitations
1. **URL Pagination:** Generic approach - may not handle all custom pagination patterns
2. **Offset Calculation:** Hard-coded assumption of 20 items per page (varies by site)
3. **Duplicate Detection:** Basic URL comparison - could use content hashing
4. **Session Redundancy:** Both `runs.is_continuation` AND `iteration_runs` track continuations
5. **Continuation Strategy:** Creates projects vs. using custom start_url parameter inconsistently

### Optimization Opportunities
1. Move from incremental polling to event-based triggers
2. Consolidate checkpoint tracking (run_checkpoints seems underutilized)
3. Implement exponential backoff for stuck detection
4. Add batch pagination support (multiple pages per run)
5. Standardize session/iteration vs. continuation run concepts

### Database Considerations
1. Snowflake integration complete - no SQLite dependencies
2. Product_data table has good indexes but scraping_sessions lacks coverage
3. Consider partitioning large tables by project_id or date
4. JSON storage in checkpoint_data could use better schema design

---

## 10. FILES REFERENCE

**Core Services:**
- [incremental_scraping_manager.py](backend/src/services/incremental_scraping_manager.py) - Continuation triggering
- [incremental_scraping_scheduler.py](backend/src/services/incremental_scraping_scheduler.py) - Background scheduler
- [pagination_service.py](backend/src/services/pagination_service.py) - Pagination detection
- [auto_runner_service.py](backend/src/services/auto_runner_service.py) - Run orchestration
- [scraping_session_service.py](backend/src/services/scraping_session_service.py) - Session management
- [recovery_service.py](backend/src/services/recovery_service.py) - Auto-recovery
- [data_ingestion_service.py](backend/src/services/data_ingestion_service.py) - Data pipeline

**Database & Models:**
- [database.py](backend/src/models/database.py) - Core DB operations & schema
- [url_generator.py](backend/src/utils/url_generator.py) - URL pattern detection

**APIs:**
- [api_server.py](backend/src/api/api_server.py) - REST endpoints
