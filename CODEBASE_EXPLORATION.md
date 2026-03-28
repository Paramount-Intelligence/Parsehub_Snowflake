# ParseHub-Snowflake Codebase Exploration

## 1. CURRENT SCRAPING LOGIC

### Core Orchestration Files

#### [Chunk Pagination Orchestrator](backend/src/services/chunk_pagination_orchestrator.py)
**Primary file for batch-based pagination**

- **Class**: `ChunkPaginationOrchestrator`
- **Key Features**:
  - Manages 10-page batches (`CHUNK_SIZE = 10`)
  - Checkpoint-based resume capability
  - Polling mechanism with 5-second intervals (`POLL_INTERVAL = 5`)
  - Max 30 minutes polling timeout (`MAX_POLL_ATTEMPTS = 360`)
  - Deduplication via source_page tracking
  - Single project per session (no duplication)

- **Key Methods**:
  - `get_checkpoint(project_id)` - Retrieves last completed page from DB
  - `generate_next_batch_urls(batch_number, batch_size)` - Creates next 10-page URLs
  - `trigger_run(project_token, start_url, pages)` - Starts ParseHub run
  - `poll_for_completion(run_token)` - Monitors run status with 360 max attempts
  - `fetch_results(run_token)` - Retrieves scraped data from completed run
  - `store_batch_results(project_id, batch_data, source_page)` - Saves results with lineage
  - `update_checkpoint(project_id, max_page)` - Updates progress in DB

- **Architecture**: Backend owns batching logic; single ParseHub project handles all pages

---

#### [Incremental Scraping Manager](backend/src/services/incremental_scraping_manager.py)
**Refactored manager using chunk-based orchestration**

- **Class**: `IncrementalScrapingManager`
- **Key Components**:
  - Uses `ChunkPaginationOrchestrator` internally
  - Replaces old continuation project model
  - Automatically detects incomplete projects

- **Key Methods**:
  - `check_and_match_pages()` - Finds projects needing continuation
  - `monitor_continuation_runs()` - Monitors active batch runs
  - Matches `project_id` from projects table with metadata table
  - Triggers continuation if `scraped_pages < total_pages`

- **Logic**: SELECT projects WHERE total_pages > current_page_scraped, then trigger next batch

---

#### [Incremental Scraping Scheduler](backend/src/services/incremental_scraping_scheduler.py)
**Background scheduler for continuous batch processing**

- **Class**: `IncrementalScrapingScheduler`
- **Configuration**:
  - Default check interval: 30 minutes
  - Runs in background thread (daemon=True)
  - Configured via `CHECK_INTERVAL_MINUTES` env var

- **Key Methods**:
  - `start()` - Spawns background thread
  - `stop()` - Gracefully shutdown
  - `_scheduler_loop()` - Main loop that periodically checks for incomplete projects

- **Global Functions**:
  - `start_incremental_scraping_scheduler(check_interval_minutes)`
  - `stop_incremental_scraping_scheduler()`
  - `get_scheduler()` - Returns singleton instance

---

#### [Pagination Service](backend/src/services/pagination_service.py)
**Handles pagination pattern detection and URL generation**

- **Class**: `PaginationService`
- **Supported Patterns**:
  - Query param: `?page=N`, `?p=N`, `?offset=N`
  - Path-style: `/page/N`, `/page-N`, `/p/N`
  - Custom: `?offset=N` (with item count calculation)

- **Key Methods**:
  - `extract_page_number(url)` - Detects current page from URL
  - `generate_next_page_url(base_url, current_page)` - Creates next page URL
  - `detect_pagination_pattern(url)` - Returns pattern metadata Dict

- **Pattern Detection**: Regex-based with fallback to default `?page=N` append

---

### Related Scraping Services

#### [Auto Runner Service](backend/src/services/auto_runner_service.py)
**Automates project creation and iterative execution**

- **Class**: `AutoRunnerService`
- **Key Methods**:
  - `get_project_details(project_token)` - Fetches project via API
  - `create_project(original_token, new_name, new_start_url)` - Clones project with new URL
  - `run_project(project_token, pages)` - Starts scraping run
  - `handle_continuation(run_token, last_url)` - Manages multi-page scraping

- **Use Case**: Creating new projects for pagination continuation (now largely replaced by orchestrator)

---

#### [Recovery Service](backend/src/services/recovery_service.py)
**Auto-recovery of stopped/stuck projects**

- **Class**: `RecoveryService`
- **Stop Detection**: 5-minute inactivity threshold (`STOP_DETECTION_MINUTES = 5`)

- **Key Methods**:
  - `check_project_status(project_token)` - Checks if run stopped
  - `get_last_product_url(run_token)` - Extracts last successful item URL
  - `trigger_recovery(project_token, last_url)` - Restarts from last known position

- **Status Checks**: completed|cancelled|stuck|running|error

---

#### [Monitoring Service](backend/src/services/monitoring_service.py)
**Continuous project monitoring with APScheduler**

- **Class**: `MonitoringService`
- **Scheduler**: APScheduler with `BackgroundScheduler`
- **Check Interval**: Configurable via `MONITOR_CHECK_INTERVAL` (default 60 seconds)

- **Key Methods**:
  - `start()` - Starts background monitoring
  - `check_all_projects()` - Monitors for stopped projects
  - Recovery attempts tracked (limit: `MAX_RECOVERY_ATTEMPTS = 3`)

- **Trigger Mechanism**: Interval-based scheduling using `IntervalTrigger`

---

---

## 2. PARSEHUB API INTEGRATION

### API Client Configuration

#### Environment Variables (from [backend/src/config/.env.example](backend/src/config/.env.example))
```
PARSEHUB_API_KEY=<your_api_key>
PARSEHUB_BASE_URL=https://www.parsehub.com/api/v2
```

### API Endpoints Used

| Endpoint | Method | Service | Purpose |
|----------|--------|---------|---------|
| `/api/v2/projects/{token}` | GET | Auto Runner, Recovery | Fetch project details |
| `/api/v2/projects/{token}/run` | POST | Group Run, Auto Runner, Chunk Orchestrator | Trigger new run |
| `/api/v2/runs/{run_token}` | GET | Chunk Orchestrator | Check run status |
| `/api/v2/runs/{run_token}/data` | GET | Recovery, Chunk Orchestrator | Fetch scraped data |

### Run Triggering Logic

#### [Group Run Service](backend/src/services/group_run_service.py) - Sequential Batch Execution
```python
# _run_single_project() method
url = 'https://www.parsehub.com/api/v2/projects/{token}/run'
data = {'api_key': api_key, 'pages': 1}
response = requests.post(url, data=data, timeout=10)
```
- Returns: `run_token` in response JSON
- Runs projects sequentially (not parallel)
- Each project gets 1 page per run (configurable via `pages` param)

#### [Chunk Pagination Orchestrator](backend/src/services/chunk_pagination_orchestrator.py) - Batch Runs with URL
```python
# trigger_run() method
url = f'{base_url}/projects/{project_token}/run'
payload = {
    'api_key': api_key,
    'start_url': <generated_next_page_url>,  # e.g., https://example.com/page=2
    'pages': 10  # Batch size
}
response = requests.post(url, data=payload)
```
- Sends next page URL to ParseHub
- ParseHub respects pagination and follows pages from that URL
- Returns run immediately with `run_token`

### Result Fetching & Polling

#### Status Polling Loop ([chunk_pagination_orchestrator.py](backend/src/services/chunk_pagination_orchestrator.py#L360-L410))
```python
# poll_for_completion() method
for attempt in range(max_attempts):
    response = requests.get(f'{base_url}/runs/{run_token}', params={'api_key': api_key})
    data = response.json()
    status = data.get('status')  # 'completed', 'running', 'cancelled', 'error'
    
    if status == 'completed':
        return {'success': True, 'status': 'completed', 'data_count': len(data.get('data', []))}
    
    time.sleep(5)  # Poll interval
```

- Maximum 30 minutes of polling (360 attempts × 5 seconds)
- Returns immediately on completion, cancellation, or error

#### Data Fetching
```python
# fetch_results() method
response = requests.get(f'{base_url}/runs/{run_token}/data', params={'api_key': api_key})
data = response.json()  # Array of scraped items
```

### URL Generation for Pagination

#### [URL Generator Utility](backend/src/utils/url_generator.py)
**Pattern-aware URL generation**

- **Class**: `URLGenerator`
- **Key Methods**:
  - `detect_pattern(url)` - Returns pattern_type, regex, current_page
  - `generate_next_url(url, next_page_number, pattern_info)` - Creates next page URL

- **Patterns Detected**:
  1. `query_page`: `?page=N` → replaces with `?page={N+1}`
  2. `query_p`: `?p=N` → replaces with `?p={N+1}`
  3. `query_offset`: `?offset=N` → replaces with `?offset={(N+1)*20}`
  4. `query_start`: `?start=N` → replaces with `?start={(N+1)*20}`
  5. `path_page`: `/page-N` or `/page/N` → `/page-{N+1}`
  6. `path_p`: `/p/N` → `/p/{N+1}`
  7. `path_products`: `/products/page-N` → `/products/page-{N+1}`
  8. `query_custom`: Generic fallback for unknown params

- **Fallback**: Appends `?page={N+1}` if no pattern detected

### State & Checkpoint Management

#### Metadata Table ([database.py](backend/src/models/database.py#L196-L250))
Stores current pagination checkpoint:
- `current_page_scraped` - Last completed page number
- `total_pages` - Target pages to scrape
- `project_token` - Associated project
- `project_name` - Human-readable name
- `last_known_url` - Last successful page URL

#### Checkpoint Read/Write
```python
# From ChunkPaginationOrchestrator.get_checkpoint()
SELECT current_page_scraped, total_pages FROM metadata WHERE project_id = %s

# Update after batch completion
UPDATE metadata SET current_page_scraped = %s, updated_date = CURRENT_TIMESTAMP
WHERE project_id = %s
```

---

---

## 3. DATABASE MODELS & SCHEMA

### Database Configuration
- **Type**: Snowflake (migrated from SQLite)
- **Connection**: [ParseHubDatabase](backend/src/models/database.py)
- **Config**: Environment variables in `SNOWFLAKE_*` prefix
- **Schema Location**: [backend/src/models/init_snowflake.sql](backend/src/models/init_snowflake.sql)

### Project & Tracking Tables

#### [Projects Table](backend/src/models/init_snowflake.sql#L7-L16)
```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    token VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(1000) NOT NULL,
    owner_email VARCHAR(255),
    main_site VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
```
- Stores ParseHub project token and metadata
- `owner_email` for notification tracking
- `main_site` for project configuration

#### [Metadata Table](backend/src/models/init_snowflake.sql#L27-L55)
**Core pagination checkpoint storage**
```sql
CREATE TABLE metadata (
    id INTEGER PRIMARY KEY,
    personal_project_id VARCHAR(255) UNIQUE,
    project_id INTEGER REFERENCES projects(id),
    project_token VARCHAR(255) UNIQUE REFERENCES projects(token),
    project_name VARCHAR(1000) NOT NULL,
    
    -- Pagination checkpoint
    total_pages INTEGER,
    current_page_scraped INTEGER DEFAULT 0,
    current_product_scraped INTEGER DEFAULT 0,
    last_known_url VARCHAR(1000),
    
    -- Metadata fields
    region VARCHAR(500),
    country VARCHAR(500),
    brand VARCHAR(500),
    website_url VARCHAR(1000),
    
    -- Tracking
    total_products INTEGER,
    last_run_date TIMESTAMP,
    import_batch_id INTEGER,
    status VARCHAR(50) DEFAULT 'pending',
    
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE INDEX idx_metadata_region ON metadata (region);
CREATE INDEX idx_metadata_country ON metadata (country);
CREATE INDEX idx_metadata_brand ON metadata (brand);
CREATE INDEX idx_metadata_status ON metadata (status);
```

### Execution & Result Tables

#### [Runs Table](backend/src/models/init_snowflake.sql#L86-L103)
**Tracks each scraping execution**
```sql
CREATE TABLE runs (
    id INTEGER PRIMARY KEY,
    project_token VARCHAR(255) NOT NULL REFERENCES projects(token),
    run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    pages_scraped INTEGER,
    execution_time_seconds INTEGER,
    status VARCHAR(50),  -- 'running', 'completed', 'cancelled', 'error'
    error_message TEXT,
    is_continuation BOOLEAN DEFAULT FALSE,
    
    FOREIGN KEY (project_token) REFERENCES projects(token)
);
```
- One row per run execution
- `is_continuation` flag tracks incremental scraping
- `pages_scraped` counts results returned

#### [Scraped Data Table](backend/src/models/init_snowflake.sql#L105-L116)
**Raw scraped results**
```sql
CREATE TABLE scraped_data (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    project_token VARCHAR(255) NOT NULL REFERENCES projects(token),
    data_url VARCHAR(1000),          -- Source page URL
    row_json TEXT,                   -- JSON data from item
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    
    FOREIGN KEY (run_id) REFERENCES runs(id),
    FOREIGN KEY (project_token) REFERENCES projects(token)
);
```

### State & Lineage Tracking

#### [Recovery Operations Table](backend/src/models/database.py#L301-L319)
**Tracks auto-recovery attempts** 
```sql
CREATE TABLE recovery_operations (
    id INTEGER PRIMARY KEY,
    recovery_run_id INTEGER,
    project_id INTEGER NOT NULL,
    original_project_token TEXT,
    recovery_project_token TEXT,
    last_product_url TEXT,
    last_product_name TEXT,
    
    -- Timestamps
    stopped_timestamp TIMESTAMP,
    recovery_triggered_timestamp TIMESTAMP,
    recovery_started_timestamp TIMESTAMP,
    recovery_completed_timestamp TIMESTAMP,
    
    -- Metrics
    status TEXT DEFAULT 'pending',
    original_data_count INTEGER DEFAULT 0,
    recovery_data_count INTEGER DEFAULT 0,
    final_data_count INTEGER DEFAULT 0,
    duplicates_removed INTEGER DEFAULT 0,
    attempt_number INTEGER DEFAULT 1,
    error_message TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (recovery_run_id) REFERENCES runs(id)
);
```

#### [Data Lineage Table](backend/src/models/database.py#L323-L340)
**Tracks data provenance for deduplication**
```sql
CREATE TABLE data_lineage (
    id INTEGER PRIMARY KEY,
    scraped_data_id INTEGER NOT NULL,
    source_run_id INTEGER NOT NULL,
    recovery_operation_id INTEGER,
    
    -- Deduplication
    is_duplicate BOOLEAN DEFAULT 0,
    duplicate_of_data_id INTEGER,
    
    -- Tracking
    product_url TEXT,
    product_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    
    FOREIGN KEY (scraped_data_id) REFERENCES scraped_data(id),
    FOREIGN KEY (source_run_id) REFERENCES runs(id)
);
```

### Scheduling & State Tables

#### [Scheduled Runs Table](backend/src/models/init_snowflake.sql#L62-L75)
**Persistent cron job storage**
```sql
CREATE TABLE scheduled_runs (
    id INTEGER PRIMARY KEY,
    job_id VARCHAR(255) UNIQUE NOT NULL,
    project_token VARCHAR(255) NOT NULL REFERENCES projects(token),
    schedule_type VARCHAR(50),      -- 'once' or 'recurring'
    scheduled_time TIMESTAMP,       -- For 'once' type
    frequency VARCHAR(50),          -- 'daily', 'weekly', 'monthly'
    day_of_week VARCHAR(50),        -- For weekly frequency
    pages INTEGER,                  -- Pages to scrape
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (project_token) REFERENCES projects(token)
);
```

#### [Scraping Sessions Table](backend/src/models/database.py#L358-L389)
**Tracks incremental scraping sessions**
```sql
CREATE TABLE scraping_sessions (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    run_token TEXT NOT NULL,
    page_number INTEGER,
    data_hash TEXT,
    data_json TEXT NOT NULL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (session_id) REFERENCES monitoring_sessions(id),
    FOREIGN KEY (project_id) REFERENCES projects(id),
    UNIQUE(run_token, page_number, data_hash)
);
```

### Analytics & Caching

#### [Analytics Cache Table](backend/src/models/database.py#L393-L410)
```sql
CREATE TABLE analytics_cache (
    id INTEGER PRIMARY KEY,
    project_token TEXT UNIQUE NOT NULL,
    run_token TEXT,
    total_records INTEGER DEFAULT 0,
    total_fields INTEGER DEFAULT 0,
    total_runs INTEGER DEFAULT 0,
    completed_runs INTEGER DEFAULT 0,
    progress_percentage REAL DEFAULT 0,
    status TEXT,
    analytics_json TEXT,
    stored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
```

#### [CSV Exports Table](backend/src/models/database.py#L412-L425)
```sql
CREATE TABLE csv_exports (
    id INTEGER PRIMARY KEY,
    project_token TEXT NOT NULL,
    run_token TEXT,
    csv_data TEXT,
    row_count INTEGER DEFAULT 0,
    stored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    UNIQUE(project_token, run_token)
);
```

#### [Import Batches Table](backend/src/models/init_snowflake.sql#L122-L130)
**Tracks Excel file imports**
```sql
CREATE TABLE import_batches (
    id INTEGER PRIMARY KEY,
    file_name VARCHAR(500),
    file_path VARCHAR(1000),
    row_count INTEGER,
    status VARCHAR(50),
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
```

### Metrics Table

#### [Metrics Table](backend/src/models/init_snowflake.sql#L118-L127)
```sql
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY,
    project_token VARCHAR(255) NOT NULL REFERENCES projects(token),
    metric_type VARCHAR(100),
    metric_value FLOAT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (project_token) REFERENCES projects(token)
);
```

---

---

## 4. NOTIFICATION & EMAIL SYSTEM

### Current Notification Infrastructure

#### Slack Integration (Only)
**Config**: [backend/src/config/.env.example](backend/src/config/.env.example#L45-L47)
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/your/webhook/url
```

**Status**: Configured but not actively implemented in v1
- Webhook URL stored in `.env`
- No active Slack notification code in services directory
- Intended for future error/completion alerts

### Email Tracking (No Active SMTP Service)

#### Project Owner Email Storage
**Table**: `projects.owner_email` (metadata field)
- Stores contact email per project
- Used by `auto_sync_service.py` and database initialization

Example from [auto_sync_service.py](backend/src/services/auto_sync_service.py#L210-L240):
```python
# Projects sync includes email tracking
cursor.execute('''
    UPDATE projects 
    SET owner_email = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE token = %s
''', (project.get('owner_email'), token))
```

### Monitoring Service Error Handling

#### [Monitoring Service](backend/src/services/monitoring_service.py#L40-L75)
**Error detection with recovery trigger**
- Detects stopped/stuck runs
- Triggers `RecoveryService` for auto-recovery
- Tracks recovery attempts (`MAX_RECOVERY_ATTEMPTS = 3`)
- Logs all errors to console/logger

**No dedicated alerting mechanism** - errors logged only

---

---

## 5. JOB SCHEDULING SYSTEM

### Scheduler Framework: APScheduler

#### [Scheduled Run Service](backend/src/services/scheduled_run_service.py)
**Main scheduler for planned scraping jobs**

- **Class**: `ScheduledRunService`
- **Scheduler Type**: `BackgroundScheduler` (APScheduler)
- **Timezone**: System local timezone (`get_localzone()`)

##### Schedule Types Supported

**One-Time Runs**:
```python
schedule_once(project_token, scheduled_time, pages=1)
# Example: 2024-03-25T14:30:00
# trigger='date', run_date=<ISO datetime>
```

**Recurring Runs**:
```python
schedule_recurring(project_token, scheduled_time, frequency, day_of_week=None, pages=1)
# frequency: 'daily', 'weekly', 'monthly'
# time format: 'HH:MM' (24-hour)
# day_of_week: 'monday', 'tuesday', ..., 'sunday' (for weekly)
# Uses CronTrigger(hour, minute, [day_of_week], timezone)
```

##### Database Persistence
**Table**: `scheduled_runs` (Snowflake)
```python
# On startup: _load_from_database()
# - Retrieves all active=TRUE rows
# - Recreates APScheduler jobs
# - Restores in-memory registry

# On schedule: _save_to_database(job_id, run_data)
# - Stores job metadata to DB
# - Allows recovery across restarts
```

##### Key Configuration
```python
LOCAL_TZ = get_localzone()  # System timezone
self.scheduler = BackgroundScheduler(timezone=LOCAL_TZ)
```

---

### Background Task Services

#### [Auto Sync Service](backend/src/services/auto_sync_service.py)
**Periodic sync of ParseHub project data**

- **Class**: `AutoSyncService`
- **Sync Interval**: 5 minutes (config: `AUTO_SYNC_INTERVAL` env var)
- **Implementation**: Background thread with `threading.Event`

##### Sync Operations
```python
sync_all()  # Main method called every 5 minutes
# - Fetches all projects from ParseHub API
# - Updates project titles, emails, main_site
# - Syncs run statuses (running/completed/cancelled)
# - Updates latest run details in DB
```

##### Thread Management
```python
start()  # Spawns daemon thread with _sync_loop()
stop()   # Sets stop_event, waits for join(timeout=5)
```

---

#### [Incremental Scraping Scheduler](backend/src/services/incremental_scraping_scheduler.py)
**Background batch pagination checker**

- **Class**: `IncrementalScrapingScheduler`
- **Check Interval**: 30 minutes (config: `INCREMENTAL_SCRAPING_INTERVAL` env var)
- **Implementation**: Background thread

##### Main Loop (`_scheduler_loop`)
```python
while self.running:
    if (current_time - last_check) >= check_interval:
        continuation_runs = self.manager.check_and_match_pages()
        # Finds incomplete projects and triggers next batch
        
        self.manager.monitor_continuation_runs()
        # Monitors active batches
    
    time.sleep(60)  # Check every minute
```

---

#### [Monitoring Service](backend/src/services/monitoring_service.py)
**Continuous project status monitoring**

- **Class**: `MonitoringService`
- **Scheduler Type**: `BackgroundScheduler` (APScheduler)
- **Check Interval**: 60 seconds (config: `MONITOR_CHECK_INTERVAL` env var)

##### Monitoring Job
```python
scheduler.add_job(
    self.check_all_projects,
    trigger=IntervalTrigger(seconds=60),
    id='monitor_projects',
    name='Monitor all projects for stops'
)
```

##### Monitored Events
- Project run completion
- Stuck projects (no data > 5 minutes)
- Run cancellation
- API errors

---

### Service Initialization & Startup

#### [API Server](backend/src/api/api_server.py#L240-L260)
**Bootstrap code starts all background services**

```python
def _start_background_services():
    """Called from Flask app initialization"""
    check_interval = int(os.getenv('INCREMENTAL_SCRAPING_INTERVAL', '30'))
    sync_interval  = int(os.getenv('AUTO_SYNC_INTERVAL', '5'))
    
    start_incremental_scraping_scheduler(check_interval)
    start_auto_sync_service(sync_interval)
    
    # Start scheduled run service and link database
    scheduled_service = start_scheduled_run_service()
    if _db is not None:
        scheduled_service.set_database(_db)
```

#### Service Singleton Pattern
Each service has a module-level singleton:
```python
_scheduler = None

def start_incremental_scraping_scheduler(check_interval):
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler
    _scheduler = IncrementalScrapingScheduler(check_interval)
    _scheduler.start()
    return _scheduler

def get_scheduler():
    return _scheduler
```

---

### Configuration Summary

| Service | Type | Interval | Env Var | Purpose |
|---------|------|----------|---------|---------|
| ScheduledRunService | APScheduler | Variable | N/A | Cron-based project runs |
| AutoSyncService | Thread-based | 5 min | `AUTO_SYNC_INTERVAL` | Sync ParseHub project data |
| IncrementalScrapingScheduler | Thread-based | 30 min | `INCREMENTAL_SCRAPING_INTERVAL` | Check for incomplete projects |
| MonitoringService | APScheduler | 60 sec | `MONITOR_CHECK_INTERVAL` | Monitor for stuck/stopped runs |

---

---

## KEY IMPLEMENTATION PATTERNS

### 1. Pagination Flow (Current Architecture)

```
Database Checkpoint (metadata.current_page_scraped=5)
    ↓
IncrementalScrapingScheduler checks every 30 min
    ↓
IncrementalScrapingManager.check_and_match_pages()
    ↓
ChunkPaginationOrchestrator.get_checkpoint() → current_page=5
    ↓
URLGenerator.detect_pattern(base_url) + generate_next_url(page=6)
    ↓
ChunkPaginationOrchestrator.trigger_run(
    project_token=<1 project for entire scrape>,
    start_url=<page 6 URL>,
    pages=10  ← Batch size
)
    ↓
ParseHub processes pages 6-15 automatically
    ↓
ChunkPaginationOrchestrator.poll_for_completion() → max 30 min
    ↓
fetch_results() → extract data + source_page tracking
    ↓
store_batch_results() in scraped_data table
    ↓
UPDATE metadata SET current_page_scraped=15
    ↓
(Repeat on next 30-min check)
```

### 2. Error Recovery Flow

```
MonitoringService (60-sec interval)
    ↓
check_all_projects()
    ↓
Detect stuck run (no data > 5 min)
    ↓
RecoveryService.check_project_status()
    ↓
get_last_product_url() from last successful run
    ↓
trigger_recovery(project_token, last_url)
    ↓
Create new run from last_url
    ↓
Track recovery attempt count (max 3)
    ↓
Store in recovery_operations table
```

### 3. Scheduled Execution Flow

```
ScheduledRunService.schedule_recurring(
    project_token, time="14:30", frequency="daily"
)
    ↓
Create CronTrigger(hour=14, minute=30, timezone=LOCAL_TZ)
    ↓
Add job to APScheduler
    ↓
Save to scheduled_runs table (persistent)
    ↓
On trigger time: _run_project(project_token, pages)
    ↓
Calls GroupRunService._run_single_project()
    ↓
POST to ParseHub API
```

---

---

## FILE INVENTORY

### Services (`backend/src/services/`)

| File | Class | Purpose |
|------|-------|---------|
| [scheduled_run_service.py](backend/src/services/scheduled_run_service.py) | `ScheduledRunService` | APScheduler-based cron jobs |
| [auto_sync_service.py](backend/src/services/auto_sync_service.py) | `AutoSyncService` | Periodic ParseHub data sync |
| [incremental_scraping_scheduler.py](backend/src/services/incremental_scraping_scheduler.py) | `IncrementalScrapingScheduler` | Background batch checker |
| [incremental_scraping_manager.py](backend/src/services/incremental_scraping_manager.py) | `IncrementalScrapingManager` | Manager for batch orchestration |
| [chunk_pagination_orchestrator.py](backend/src/services/chunk_pagination_orchestrator.py) | `ChunkPaginationOrchestrator` | 10-page batch processor |
| [pagination_service.py](backend/src/services/pagination_service.py) | `PaginationService` | Pagination pattern detection |
| [auto_runner_service.py](backend/src/services/auto_runner_service.py) | `AutoRunnerService` | Project automation (legacy) |
| [group_run_service.py](backend/src/services/group_run_service.py) | `GroupRunService` | Sequential batch execution |
| [recovery_service.py](backend/src/services/recovery_service.py) | `RecoveryService` | Auto-recovery of stuck runs |
| [monitoring_service.py](backend/src/services/monitoring_service.py) | `MonitoringService` | Continuous status monitoring |
| [scraping_session_service.py](backend/src/services/scraping_session_service.py) | `ScrapingSessionService` | Session tracking |
| [data_consolidation_service.py](backend/src/services/data_consolidation_service.py) | `DataConsolidationService` | CSV merging & deduplication |
| [analytics_service.py](backend/src/services/analytics_service.py) | `AnalyticsService` | Analytics calculations |
| [advanced_analytics.py](backend/src/services/advanced_analytics.py) | `AdvancedAnalyticsService` | Advanced metrics |
| [excel_import_service.py](backend/src/services/excel_import_service.py) | `ExcelImportService` | Excel metadata imports |

### Models (`backend/src/models/`)

| File | Purpose |
|------|---------|
| [database.py](backend/src/models/database.py) | Snowflake connection & DB operations |
| [init_snowflake.sql](backend/src/models/init_snowflake.sql) | Schema DDL |
| [db_pool.py](backend/src/models/db_pool.py) | Connection pooling |

### Utils (`backend/src/utils/`)

| File | Class | Purpose |
|------|-------|---------|
| [url_generator.py](backend/src/utils/url_generator.py) | `URLGenerator` | Pagination URL generation |

### API (`backend/src/api/`)

| File | Purpose |
|------|---------|
| [api_server.py](backend/src/api/api_server.py) | Flask REST server & service initialization |
| [fetch_projects.py](backend/src/api/fetch_projects.py) | Project fetching utilities |

---

---

## SUMMARY OF KEY CHANGES FROM OLD ARCHITECTURE

### ✓ Legacy (Pre-Orchestrator)
- Continuation projects (created temp projects for each page)
- Complex state management
- No backend batching control

### ✓ Current (Orchestrator-Based)
- **Single project per session** - all pages through one project
- **Backend owns batching** - decides when/how to paginate
- **Chunk-based (10-page)** - deterministic batch sizes
- **Checkpoint-based resume** - safe pause/resume
- **Idempotent** - same batch twice = same results
- **Proper lineage tracking** - deduplication via source_page

