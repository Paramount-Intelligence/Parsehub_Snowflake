# ParseHub Scraping Architecture - Quick Reference

## Core Components & Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TRIGGER MECHANISMS                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  API Endpoints                IncrementalScheduler          Manual   │
│  └─ POST /batch-execute       └─ Every 30 min               Trigger │
│                                 (configurable)                       │
│         │                            │                        │      │
│         └────────────┬───────────────┴────────────┬───────────┘      │
│                      ▼                            ▼                  │
│            ┌──────────────────────────────────────────┐              │
│            │  IncrementalScrapingManager OR          │              │
│            │  AutoRunnerService                       │              │
│            │                                          │              │
│            │  1. Check project status                 │              │
│            │  2. Detect pagination pattern             │              │
│            │  3. Generate next URL                     │              │
│            │  4. Trigger ParseHub run                  │              │
│            └──────────────────────────────────────────┘              │
│                           ▼                                          │
│        ┌──────────────────────────────────────────┐                 │
│        │  ParseHub API                             │                 │
│        │  - Create project (if needed)             │                 │
│        │  - Trigger run (with custom URL)          │                 │
│        │  - Poll status                            │                 │
│        │  - Fetch data                             │                 │
│        └──────────────────────────────────────────┘                 │
│                           ▼                                          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    DATA INGESTION PIPELINE                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  DataIngestorService                                                 │
│  └─ get_run_output_data(run_token)                                  │
│     └─ Extract from nested structure                                 │
│     └─ Normalize to standard schema                                  │
│                    ▼                                                 │
│  ┌──────────────────────────────────┐                              │
│  │  Normalize Product Record        │                              │
│  │                                   │                              │
│  │  Maps incoming fields to:        │                              │
│  │  - part_number                   │                              │
│  │  - name                          │                              │
│  │  - brand                         │                              │
│  │  - list_price / sale_price       │                              │
│  │  - product_url                   │                              │
│  │  - page_number (from iteration)  │                              │
│  │  - extraction_date               │                              │
│  └──────────────────────────────────┘                              │
│                    ▼                                                 │
│  ┌──────────────────────────────────────┐                          │
│  │  Insert into product_data table      │                          │
│  │  (with deduplication by            │                          │
│  │   UNIQUE(project_id, run_token,     │                          │
│  │          product_url, page_number)) │                          │
│  └──────────────────────────────────────┘                          │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    CHECKPOINT & STATE TRACKING                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─ Metadata Table ◄────────────┐                                   │
│  │  - total_pages               │                                   │
│  │  - current_page_scraped      │──── Primary progress tracking    │
│  │  - total_products            │                                   │
│  │  - current_product_scraped   │                                   │
│  │  - status (pending/running)  │                                   │
│  │  - last_known_url            │                                   │
│  └───────────────────────────────┘                                   │
│                     │ checked every 30 min by scheduler             │
│                     ▼                                                 │
│  ┌─────────────────────────────────────┐                           │
│  │  IF current_page_scraped            │                           │
│  │  < total_pages:                     │                           │
│  │                                     │                           │
│  │  Trigger continuation run           │                           │
│  │  starting from next page            │                           │
│  └─────────────────────────────────────┘                           │
│                                                                       │
│  ┌─ Runs Table (is_continuation=TRUE)                              │
│  │  - Tracks continuation runs                                      │
│  └─ Iteration Runs Table (session-based)                           │
│  │  - Tracks structured multi-page campaigns                        │
│  └─ Run Checkpoints Table                                          │
│     - Snapshots: item_count, items/min, ETA                        │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    RECOVERY & DEDUPLICATION                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. Detect Stuck Run                                                │
│     └─ No data for 5+ min                                           │
│                    ▼                                                 │
│  2. GetLastProductURL(run_token)                                   │
│     └─ Fetch /data endpoint                                        │
│     └─ Extract last item URL                                       │
│                    ▼                                                 │
│  3. DetectNextPageURL(last_url)                                    │
│     └─ Apply pagination pattern                                    │
│                    ▼                                                 │
│  4. CreateRecoveryProject(original, next_url)                      │
│     └─ Clone with new URL                                          │
│                    ▼                                                 │
│  5. StartRecoveryRun()                                              │
│     └─ Ingest data                                                 │
│                    ▼                                                 │
│  6. DeduplicateData(original_run, recovery_run)                    │
│     └─ Compare URLs                                                │
│     └─ Remove duplicates                                           │
│     └─ Store in recovery_operations table                          │
│                                                                       │
│  ┌─ Recovery Operations Table                                       │
│  │  - original_run_id                                              │
│  │  - recovery_run_id                                              │
│  │  - original_data_count / recovery_data_count                    │
│  │  - final_data_count (after dedup)                               │
│  │  - duplicates_removed                                           │
│  │  - status (pending/in_progress/completed/failed)                │
│  └─────────────────────────────────────────────────────────────────│
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## State Transitions

```
┌──────────────────────────────────────────────────────────────────────┐
│                    PROJECT LIFECYCLE                                 │
├──────────────────────────────────────────────────────────────────────┤

  NEW PROJECT
      │
      ▼
  ┌─────────────────────┐
  │ Import Metadata     │
  │ (from Excel)        │
  │                     │
  │ total_pages: 100    │
  │ status: pending     │
  └─────────────────────┘
      │
      ▼
  ┌─────────────────────────────────────────┐
  │ Initial Run                             │
  │ Scrapes: pages 1-10 (first 10 pages)    │
  │                                         │
  │ current_page_scraped → 10               │
  │ status → running                        │
  └─────────────────────────────────────────┘
      │
      ▼
  ┌─────────────────────────────────────────┐
  │ Scheduler Check (every 30 min)          │
  │                                         │
  │ 10 < 100 ? YES → Trigger continuation   │
  └─────────────────────────────────────────┘
      │
      ▼
  ┌─────────────────────────────────────────┐
  │ Continuation Run #1                     │
  │ Pages 11-20 (next 10 pages)             │
  │                                         │
  │ current_page_scraped → 20               │
  │ runs.is_continuation = TRUE             │
  └─────────────────────────────────────────┘
      │
      ├─ Loop until current_page_scraped == total_pages
      │  (pages 21-30, 31-40, ... 91-100)
      │
      ▼
  ┌─────────────────────────────────────────┐
  │ Final State                             │
  │                                         │
  │ current_page_scraped: 100               │
  │ == total_pages: 100                     │
  │                                         │
  │ status: complete                        │
  └─────────────────────────────────────────┘
```

## Pagination Pattern Examples

```
┌──────────────────────────────────────────────────────────────────────┐
│                  SUPPORTED URL PATTERNS                              │
├──────────────────────────────────────────────────────────────────────┤

Pattern Type         | Example                    | Detection Method
─────────────────────┼────────────────────────────┼──────────────────
Query Page           | site.com?page=5            | Regex: [?&]page=(\d+)
Query p              | site.com?p=5               | Regex: [?&]p=(\d+)
Query Offset         | site.com?offset=100        | Regex: [?&]offset=(\d+)
Query Start          | site.com?start=100         | Regex: [?&]start=(\d+)
Path Page Slash      | site.com/page/5            | Regex: /page[/-](\d+)
Path Page Dash       | site.com/page-5            | (same as above)
Path p               | site.com/p/5               | Regex: /p/(\d+)
Path Products        | site.com/products/page/5   | Regex: /products/page[/-](\d+)
Unknown              | (custom parameter)         | Fallback: append ?page=N

Generation Examples:
─────────────────────────────────────────────────────────────────────

From page 5 to page 6:

?page=5  ──regex──> ?page=6
?p=5     ──regex──> ?p=6
?offset=100  ──regex──> ?offset=120  (assuming 20 items/page)
/page/5  ──regex──> /page/6
/page-5  ──regex──> /page-6

```

## Database Schema - Critical Tables

```
┌──────────────────────────────────────────────────────────────────────┐
│                       KEY TABLES SCHEMA                              │
├──────────────────────────────────────────────────────────────────────┤

metadata
├─ id (PK)
├─ personal_project_id (UNIQUE)
├─ project_id → projects.id
├─ project_token → projects.token
├─ project_name
├─ total_pages ◄──── TARGET
├─ current_page_scraped ◄──── CURRENT PROGRESS (0 = not started)
├─ total_products
├─ current_product_scraped
├─ last_known_url
├─ status (pending/running/complete)
├─ region, country, brand, website_url (filters)
└─ import_batch_id → import_batches.id

runs (EXECUTION RECORDS)
├─ id (PK)
├─ project_id → projects.id
├─ run_token (UNIQUE, from ParseHub API)
├─ status (starting/running/completed/failed)
├─ pages_scraped
├─ records_count
├─ is_continuation ◄──── Boolean flag
├─ start_time, end_time
├─ duration_seconds
└─ error_message

run_checkpoints (PROGRESS SNAPSHOTS)
├─ id (PK)
├─ run_id → runs.id
├─ snapshot_timestamp
├─ item_count_at_time
├─ items_per_minute
├─ estimated_completion_time
└─ created_at

product_data (NORMALIZED PRODUCTS)
├─ id (PK)
├─ project_id → projects.id
├─ run_id → runs.id
├─ run_token
├─ name, part_number, brand
├─ list_price, sale_price, case_unit_price
├─ country, currency
├─ product_url
├─ page_number ◄──── Which page this came from
├─ extraction_date
└─ UNIQUE(project_id, run_token, product_url, page_number) ◄──── DEDUP

scraping_sessions (CAMPAIGN TRACKING)
├─ id (PK)
├─ project_token
├─ project_name
├─ total_pages_target
├─ current_iteration
├─ pages_completed
├─ status (running/complete)
└─ completed_at

iteration_runs (PER-RUN DETAILS)
├─ id (PK)
├─ session_id → scraping_sessions.id
├─ iteration_number
├─ parsehub_project_token
├─ start_page_number
├─ end_page_number
├─ pages_in_this_run
├─ run_token
├─ csv_data (full CSV export)
├─ records_count
├─ status (pending/running/completed)
└─ completed_at

recovery_operations (AUTO-RECOVERY TRACKING)
├─ id (PK)
├─ original_run_id → runs.id
├─ recovery_run_id → runs.id
├─ project_id
├─ original_project_token
├─ recovery_project_token
├─ last_product_url
├─ stopped_timestamp
├─ recovery_completed_timestamp
├─ status (pending/in_progress/completed/failed)
├─ original_data_count, recovery_data_count
├─ final_data_count (after dedup)
├─ duplicates_removed
├─ attempt_number
└─ error_message
```

## Service Responsibilities

```
┌──────────────────────────────────────────────────────────────────────┐
│              SERVICE LAYER RESPONSIBILITIES                          │
├──────────────────────────────────────────────────────────────────────┤

IncrementalScrapingManager
├─ check_and_match_pages()
│  └─ Queries metadata for incomplete projects
│  └─ Compares current_page_scraped vs total_pages
│  └─ Triggers continuation if incomplete
├─ trigger_continuation_run()
│  └─ Modifies URL for pagination
│  └─ Creates/updates project if needed
│  └─ Starts ParseHub run
│  └─ Stores run record with is_continuation=TRUE
└─ monitor_continuation_runs()
   └─ Polls active continuation runs
   └─ Updates status

IncrementalScrapingScheduler
├─ Background thread (configurable interval)
├─ Calls IncrementalScrapingManager.check_and_match_pages()
└─ Thread-safe, daemon mode

URLGenerator / PaginationService
├─ detect_pattern(url) → pattern info
├─ generate_next_url(url, page_num) → next URL
├─ extract_page_number(url) → current page
└─ Support 8+ pagination patterns

AutoRunnerService (NEW SESSION-BASED)
├─ execute_iteration(session_id, iteration_num, ...)
│  ├─ Generate URL for page range
│  ├─ Trigger run with custom URL
│  ├─ Wait for completion
│  ├─ Fetch CSV data
│  └─ Update session/iteration records
├─ wait_for_completion(run_token)
│  └─ Poll status with configurable interval
└─ get_run_data(run_token) → CSV

ScrapingSessionService (SESSION MANAGEMENT)
├─ create_session(project_token, total_pages) → session_id
├─ add_iteration_run(session_id, iteration_num, ...) → run_id
├─ update_iteration_run(run_id, csv_data, records_count, status)
├─ get_session_runs(session_id) → all iteration runs
├─ update_session_progress(session_id, pages_completed, status)
├─ mark_session_complete(session_id)
└─ save_combined_data(session_id, consolidated_csv, ...)

DataIngestorService
├─ get_run_data(run_token) → raw data
├─ get_run_output_data(run_token) → extracted products
├─ _extract_products_from_structure(data) → normalize
├─ _normalize_product_record(product) → standard schema
└─ ingest_run(project_id, run_token) → inserted count

RecoveryService
├─ check_project_status(token) → running/stuck/completed/cancelled
├─ get_last_product_url(run_token) → {url, name, data}
├─ detect_next_page_url(current_url, pattern) → next URL
├─ create_recovery_project(original_token, next_url) → new token
├─ start_recovery_run(project_token) → run_token
└─ deduplicate_data(original_run_id, recovery_run_id) → stats

ParseHubDatabase
├─ connect() / disconnect() → Snowflake conn
├─ cursor() → DB cursor with shim
├─ init_db() → Create all tables
├─ insert_product_data(project_id, run_id, products) → count
├─ get/update/delete metadata operations
└─ Connection caching (thread-local)
```

## Configuration

```yaml
# Key Environment Variables

PARSEHUB_API_KEY
  └─ Required for all ParseHub API calls

SNOWFLAKE_ACCOUNT
SNOWFLAKE_USER
SNOWFLAKE_PASSWORD
SNOWFLAKE_DATABASE
SNOWFLAKE_SCHEMA
SNOWFLAKE_WAREHOUSE
  └─ Snowflake connection parameters

INCREMENTAL_SCRAPING_INTERVAL (default: 30 min)
  └─ How often scheduler checks for incomplete projects

AUTO_SYNC_INTERVAL (default: 5 min)
  └─ How often background sync runs
```
