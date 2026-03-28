# Backend Flask API Structure - Complete Exploration

## 1. Flask Application Entry Point

**File:** [backend/src/api/api_server.py](backend/src/api/api_server.py)

### Main Application Setup
```python
# Lines 1-50: App initialization with CORS configuration
from flask import Flask, request, jsonify, g
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": _cors_origins}})
```

### Service Registry Pattern (Lines 60-90)
```python
_db = None                      # Module-level ParseHubDatabase instance
_monitoring_service = None
_analytics_service = None
_excel_import_service = None
_auto_runner_service = None
_group_run_service = None
_services_initialized = False

def get_db() -> 'ParseHubDatabase':
    global _db
    if _db is None:
        _db = ParseHubDatabase()
    return _db

def _initialize_services():
    # Lazy initialization of all services after boot
```

### Request Lifecycle (Lines 155-185)
```python
@app.before_request
def ensure_services():
    """Attach request_id and lazily initialize services"""
    g.request_id = uuid.uuid4().hex[:12]
    g.db = get_db()
    if request.path not in ('/health', '/api/health'):
        if not _services_initialized:
            _initialize_services()

@app.teardown_appcontext
def return_db_connection(exc=None):
    """Return PostgreSQL connection to pool after request"""
    # Guarded disconnect for connection recycling
```

---

## 2. API Routes & Endpoints

### Health Check Endpoints
| Route | Method | Purpose | Line |
|-------|--------|---------|------|
| `/health` | GET | Root health probe (Railway) | 191 |
| `/api/health` | GET | Liveness probe (never hits DB) | 197 |
| `/api/health/db` | GET | Readiness probe (tests DB + counts) | 213 |

### Monitoring Endpoints
| Route | Method | Purpose | Line |
|-------|--------|---------|------|
| `/api/monitor/start` | POST | Start real-time monitoring | 282 |
| `/api/monitor/status` | GET | Get monitoring progress | 347 |
| `/api/monitor/data` | GET | Fetch scraped records (paginated) | 393 |
| `/api/monitor/data/csv` | GET | Export session data as CSV | 434 |
| `/api/monitor/stop` | POST | Cancel monitoring session | 464 |

### Run & Batch Execution Endpoints
| Route | Method | Purpose | Line |
|-------|--------|---------|------|
| `/api/runs/batch-execute` | POST | Execute multiple metadata IDs sequentially | 845 |
| `/api/runs/<run_token>/cancel` | POST | Cancel running scrape | 504 |
| `/api/projects/<token>/run` | POST | Run single project | 1529 |
| `/api/projects/batch/run` | POST | **Run multiple projects by tokens** | 1626 |
| `/api/projects/schedule` | POST | Schedule project runs (once/recurring) | 1658 |
| `/api/scheduled-runs` | GET | List all scheduled runs | 1734 |
| `/api/scheduled-runs/<job_id>` | DELETE | Delete scheduled run | 1752 |

### Project Endpoints
| Route | Method | Purpose | Line |
|-------|--------|---------|------|
| `/api/projects` | GET | Fetch paginated projects with metadata | 903 |
| `/api/projects/bulk` | GET | Fetch bulk projects with optimizations | 1086 |
| `/api/projects/search` | GET | Search projects by filters | 1204 |
| `/api/projects/sync` | POST | Sync projects from ParseHub API | 1164 |
| `/api/projects/<int:project_id>` | GET | Get single project by ID | 1304 |
| `/api/projects/<project_token>` | GET | Get single project by token | 1383 |
| `/api/projects/<token>/analytics` | GET | Get project analytics | 1807 |

### Metadata Endpoints
| Route | Method | Purpose | Line |
|-------|--------|---------|------|
| `/api/metadata` | GET | List all metadata | 567 |
| `/api/metadata/<int:metadata_id>` | GET | Get metadata entry | 622 |
| `/api/metadata/<int:metadata_id>` | PUT | Update metadata | 642 |
| `/api/metadata/<int:metadata_id>` | DELETE | Delete metadata | 699 |
| `/api/metadata/<int:metadata_id>/completion-status` | GET | Get completion status | 718 |
| `/api/metadata/import` | POST | Import metadata from Excel | 738 |
| `/api/metadata/import-history` | GET | Get import history | 786 |

### Filter Endpoints
| Route | Method | Purpose | Line |
|-------|--------|---------|------|
| `/api/filters` | GET | Get available filter options | 1279 |
| `/api/filters/values` | GET | Get filter values (region/country/brand/website) | 814 |
| `/api/debug/metadata-columns` | GET | Debug metadata columns | 1268 |

### Data/Product Endpoints
| Route | Method | Purpose | Line |
|-------|--------|---------|------|
| `/api/products/<int:project_id>` | GET | Get products by project | 1948 |
| `/api/products/run/<run_token>` | GET | Get products by run token | 1978 |
| `/api/products/<int:project_id>/stats` | GET | Get product statistics | 1999 |
| `/api/products/<int:project_id>/export` | GET | Export products as CSV | 2017 |
| `/api/ingest/<project_token>` | POST | Ingest scraped data | 1898 |

### Scraping & Continuation Endpoints
| Route | Method | Purpose | Line |
|-------|--------|---------|------|
| `/api/scraping/check-and-continue` | POST | Check run completion and auto-continue | 2043 |
| `/api/scraping/monitor-continuations` | GET | Monitor all active continuations | 2082 |
| `/api/scraping/project/<int:project_id>/status` | GET | Get project scraping status | 2117 |
| `/api/scraping/projects/incomplete` | GET | List incomplete projects | 2215 |
| `/api/sync/trigger` | POST | Trigger manual sync | 2162 |
| `/api/sync/status` | GET | Get sync status | 2190 |

---

## 3. Key Service Classes & Files

### Database Service
**File:** [backend/src/models/database.py](backend/src/models/database.py)

Key class: `ParseHubDatabase`

**Key Methods:**
```python
class ParseHubDatabase:
    def __init__(self)                          # Snowflake-only configuration
    def connect(self)                           # Get thread-local connection
    def disconnect(self)                        # Return connection to pool
    def cursor(self)                            # Get SnowflakeCursorShim
    def init_db(self)                           # Initialize schema (calls init_snowflake.sql)
    
    # Query methods (used throughout API):
    def get_metadata_table_columns()            # Get dynamic metadata columns
    def get_projects_with_website_grouping()    # Get grouped projects
    def get_metadata_by_id(metadata_id)         # Get metadata entry
    def create_monitoring_session()              # Create monitoring session
    def get_session_summary()                   # Get monitoring status
    def get_session_records()                   # Fetch paginated records
    def update_monitoring_session()              # Update session status
```

### Chunk Pagination Orchestrator
**File:** [backend/src/services/chunk_pagination_orchestrator.py](backend/src/services/chunk_pagination_orchestrator.py) (Lines 1-450+)

Key class: `ChunkPaginationOrchestrator`

**Key Methods & Properties:**
```python
class ChunkPaginationOrchestrator:
    CHUNK_SIZE = 10                             # Pages per batch
    POLL_INTERVAL = 5                           # Seconds between status checks
    MAX_POLL_ATTEMPTS = 360                     # 30 minutes max wait
    EMPTY_RESULT_THRESHOLD = 3                  # Consecutive empty = done
    
    # Checkpoint Management
    def get_checkpoint(project_id) -> Dict      # Line ~65: Get current checkpoint
        # Returns: {
        #     'last_completed_page': int,
        #     'total_pages': int,
        #     'next_start_page': int,
        #     'checkpoint_timestamp': str,
        #     'total_chunks_completed': int,
        #     'failed_chunks': int
        # }
    
    def update_checkpoint(project_id, last_completed_page, metadata=None) -> bool
        # Line ~115: Update checkpoint after batch completion
    
    # Batch URL Generation
    def generate_batch_urls(base_url, start_page, pagination_pattern=None) -> List[str]
        # Line ~195: Generate 10-page batch of URLs
    
    def _generate_page_url(base_url, page_num, pattern=None) -> str
        # Line ~210: Generate single page URL (detects ?page=, /page/, offset, etc.)
    
    # ParseHub Run Orchestration
    def trigger_batch_run(project_token, start_url, batch_start_page, batch_end_page, 
                         project_id=None, project_name=None) -> Dict
        # Line ~300: Trigger ParseHub run for batch (posts to ParseHub API with start_url)
        # Returns: {'success': bool, 'run_token': str, 'error': str}
    
    # Run Status Polling
    def poll_run_completion(run_token, max_attempts=None, project_id=None, 
                           project_name=None, batch_start_page=None, batch_end_page=None) -> Dict
        # Line ~400: Poll until ParseHub run completes
        # Returns: {'success': bool, 'status': str, 'data_count': int, 'error': str}
    
    # Data Fetching & Storage
    def fetch_batch_data(run_token) -> dict
        # Fetch results from completed run
    
    def store_batch_results(project_id, batch_data, batch_number) -> bool
        # Store results with source_page tracking
```

**Usage Pattern:**
- Called from scheduled run service to handle incremental pagination
- Manages deterministic, resumable batch processing
- Tracks checkpoint (last completed page) in database
- Detects pagination patterns (query_page, path_style, offset)
- Handles email notifications on failures

### Group Run Service
**File:** [backend/src/services/group_run_service.py](backend/src/services/group_run_service.py)

Key class: `GroupRunService`

**Key Methods:**
```python
class GroupRunService:
    def __init__(self, db)                      # Initialize with DB connection
    
    def run_group(project_tokens: List[str]) -> Dict
        # Lines 24-68: Run multiple projects sequentially
        # Returns: {
        #     'success': bool,
        #     'total_projects': int,
        #     'successful': int,
        #     'failed': int,
        #     'results': [
        #         {
        #             'token': str,
        #             'success': bool,
        #             'run_token': str,
        #             'status': str,
        #             'error': str
        #         }
        #     ]
        # }
    
    def _run_single_project(token: str) -> Dict
        # Lines 70-130: Call ParseHub API to run single project
```

**Used By:**
- `/api/projects/batch/run` endpoint (line 1626)
- Called to execute multiple project tokens sequentially

### Pagination Service
**File:** [backend/src/services/pagination_service.py](backend/src/services/pagination_service.py)

Key class: `PaginationService`

**Key Methods:**
```python
class PaginationService:
    def extract_page_number(url: str) -> int
        # Extract page number from URL patterns
    
    def generate_next_page_url(base_url: str, current_page: int) -> str
        # Generate URL for next page
    
    def detect_pagination_pattern(url: str) -> Dict
        # Detect: query_page, query_p, path_style, offset
    
    def check_pagination_needed(project_id: int, target_pages: int) -> Dict
        # Returns: {
        #     'needs_recovery': bool,
        #     'last_page_scraped': int,
        #     'target_pages': int,
        #     'total_data_count': int,
        #     'pages_remaining': int
        # }
```

### Scheduled Run Service
**File:** [backend/src/services/scheduled_run_service.py](backend/src/services/scheduled_run_service.py)

**Key Methods:**
```python
def start_scheduled_run_service()            # Start scheduler background service
def get_scheduled_run_service()              # Get service instance
def stop_scheduled_run_service()             # Stop scheduler

# Service methods:
def schedule_once(project_token, scheduled_time, pages) -> Dict
def schedule_recurring(project_token, scheduled_time, frequency, day_of_week, pages) -> Dict
def get_scheduled_runs() -> List[Dict]
def set_database(db)                        # Link DB to service
```

### Auto Runner Service
**File:** [backend/src/services/auto_runner_service.py](backend/src/services/auto_runner_service.py)

Handles automatic execution of projects

### Monitoring Service
**File:** [backend/src/services/monitoring_service.py](backend/src/services/monitoring_service.py)

**Key Methods:**
```python
def monitor_run_realtime(project_id, run_token, pages)
    # Lines 1-100: Run real-time monitoring loop
```

### Excel Import Service
**File:** [backend/src/services/excel_import_service.py](backend/src/services/excel_import_service.py)

Handles importing metadata from Excel files

---

## 4. Database Models & Tables

### Primary Tables Structure

**File:** [backend/src/models/database.py](backend/src/models/database.py) (Lines 150-500)

#### Projects Table
```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    owner_email TEXT,
    main_site TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

#### Metadata Table (Dynamic Project Metadata)
```sql
CREATE TABLE metadata (
    id INTEGER PRIMARY KEY,
    personal_project_id VARCHAR(255) UNIQUE NOT NULL,
    project_id INTEGER,
    project_token VARCHAR(255) UNIQUE,
    project_name VARCHAR(1000) NOT NULL,
    last_run_date TIMESTAMP,
    created_date TIMESTAMP,
    updated_date TIMESTAMP,
    region VARCHAR(500),                     -- Filter column
    country VARCHAR(500),                    -- Filter column
    brand VARCHAR(500),                      -- Filter column
    website_url VARCHAR(1000),                -- Filter column
    total_pages INTEGER,                     -- Target pages for scraping
    total_products INTEGER,                  -- Expected product count
    current_page_scraped INTEGER DEFAULT 0, -- CHECKPOINT: last completed page
    current_product_scraped INTEGER DEFAULT 0,
    last_known_url VARCHAR(1000),           -- For pagination recovery
    import_batch_id INTEGER,
    status VARCHAR(50) DEFAULT 'pending',
    FOREIGN KEY (project_id) REFERENCES projects(id)
)
```

**Key Checkpoint Field:** `current_page_scraped` - Used by ChunkPaginationOrchestrator

#### Runs Table (Batch/Execution History)
```sql
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    run_token TEXT UNIQUE NOT NULL,
    status TEXT,                            -- 'pending', 'running', 'completed', 'failed'
    pages_scraped INTEGER DEFAULT 0,        -- Pages processed in this run
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_seconds INTEGER,
    records_count INTEGER DEFAULT 0,        -- Records from this run
    data_file TEXT,
    is_empty BOOLEAN DEFAULT 0,
    is_continuation BOOLEAN DEFAULT 0,      -- Marks resume/continuation runs
    completion_percentage REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
)
```

#### Run Checkpoints Table (Progress Snapshots)
```sql
CREATE TABLE run_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    snapshot_timestamp TIMESTAMP,
    item_count_at_time INTEGER,             -- Records at snapshot time
    items_per_minute REAL,                  -- Velocity metric
    estimated_completion_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(id)
)
```

#### Monitoring Sessions Table (Real-Time Monitoring)
```sql
CREATE TABLE monitoring_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    run_token TEXT NOT NULL,
    target_pages INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active',           -- 'active', 'completed', 'cancelled', 'error'
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    total_records INTEGER DEFAULT 0,
    total_pages INTEGER DEFAULT 0,          -- Actual pages fetched
    progress_percentage REAL DEFAULT 0,
    current_url TEXT,                       -- Current URL being scraped
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
)
```

#### Scraped Records Table
```sql
CREATE TABLE scraped_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,            -- Links to monitoring_sessions
    project_id INTEGER NOT NULL,
    run_token TEXT NOT NULL,
    page_number INTEGER,                    -- Source page for deduplication
    data_hash TEXT,
    data_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES monitoring_sessions(id),
    UNIQUE(run_token, page_number, data_hash)
)
```

#### Scheduled Runs Table
```sql
CREATE TABLE scheduled_runs (
    id INTEGER PRIMARY KEY,
    job_id VARCHAR(255) UNIQUE NOT NULL,
    project_token VARCHAR(255) NOT NULL,
    schedule_type VARCHAR(50),              -- 'once' or 'recurring'
    scheduled_time TIMESTAMP,
    frequency VARCHAR(50),                  -- 'daily', 'weekly', 'monthly'
    day_of_week VARCHAR(50),                -- For weekly recurring
    pages INTEGER,                          -- Pages to run
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (project_token) REFERENCES projects(token)
)
```

#### Recovery Operations Table
```sql
CREATE TABLE recovery_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_run_id INTEGER NOT NULL,
    recovery_run_id INTEGER,
    project_id INTEGER NOT NULL,
    original_project_token TEXT,
    recovery_project_token TEXT,
    last_product_url TEXT,                  -- Where it stopped
    stopped_timestamp TIMESTAMP,
    recovery_triggered_timestamp TIMESTAMP,
    recovery_started_timestamp TIMESTAMP,
    recovery_completed_timestamp TIMESTAMP,
    status TEXT DEFAULT 'pending',          -- 'pending', 'running', 'completed', 'failed'
    original_data_count INTEGER DEFAULT 0,
    recovery_data_count INTEGER DEFAULT 0,
    final_data_count INTEGER DEFAULT 0,
    duplicates_removed INTEGER DEFAULT 0,
    attempt_number INTEGER DEFAULT 1,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
)
```

#### Data Lineage Table
```sql
CREATE TABLE data_lineage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scraped_data_id INTEGER NOT NULL,
    source_run_id INTEGER NOT NULL,         -- Which run produced this data
    recovery_operation_id INTEGER,
    is_duplicate BOOLEAN DEFAULT 0,
    duplicate_of_data_id INTEGER,           -- For deduplication tracking
    product_url TEXT,
    product_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scraped_data_id) REFERENCES scraped_data(id)
)
```

#### Scraping Sessions Table (Campaign-Level Tracking)
```sql
CREATE TABLE scraping_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_token TEXT NOT NULL,
    project_name TEXT NOT NULL,
    total_pages_target INTEGER NOT NULL,    -- Target page count for campaign
    current_iteration INTEGER DEFAULT 1,    -- Current batch #
    pages_completed INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
)
```

#### Iteration Runs Table (Batch-Level Tracking)
```sql
CREATE TABLE iteration_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,            -- Parent campaign
    iteration_number INTEGER NOT NULL,      -- Batch #
    parsehub_project_token TEXT NOT NULL,
    start_page_number INTEGER NOT NULL,
    end_page_number INTEGER NOT NULL,
    pages_in_this_run INTEGER NOT NULL,
    run_token TEXT NOT NULL,                -- ParseHub run token
    csv_data TEXT,
    records_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES scraping_sessions(id)
)
```

#### Analytics Cache Table
```sql
CREATE TABLE analytics_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_token TEXT UNIQUE NOT NULL,
    run_token TEXT,
    total_records INTEGER DEFAULT 0,
    total_fields INTEGER DEFAULT 0,
    total_runs INTEGER DEFAULT 0,
    completed_runs INTEGER DEFAULT 0,
    progress_percentage REAL DEFAULT 0,
    status TEXT,
    analytics_json TEXT,
    stored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

---

## 5. Key Function Signatures for Batch Implementation

### Endpoint Implementation Template (Batch Operations)

```python
# For POST /api/batches/create
def create_batch():
    """
    Create a new batch for incremental scraping
    Request:
    {
        "project_token": str,
        "total_pages": int,
        "start_page": int (default 1),
        "pages_per_chunk": int (default 10)
    }
    Returns:
    {
        "batch_id": int,
        "status": "created",
        "chunks": [{page_range, url}]
    }
    """
    data = request.get_json()
    project_token = data['project_token']
    total_pages = data['total_pages']
    
    orchestrator = ChunkPaginationOrchestrator()
    checkpoint = orchestrator.get_checkpoint(project_id)
    # ... create batch from checkpoint

# For POST /api/batches/<batch_id>/checkpoint
def update_batch_checkpoint(batch_id):
    """Update checkpoint after chunk completion"""
    data = request.get_json()
    last_completed_page = data['last_completed_page']
    
    orchestrator = ChunkPaginationOrchestrator()
    orchestrator.update_checkpoint(project_id, last_completed_page)
    
    return jsonify({'success': True})

# For GET /api/batches/<batch_id>/status
def get_batch_status(batch_id):
    """Get batch progress"""
    checkpoint = orchestrator.get_checkpoint(project_id)
    return jsonify({
        'batch_id': batch_id,
        'last_completed_page': checkpoint['last_completed_page'],
        'total_pages': checkpoint['total_pages'],
        'progress_percentage': (checkpoint['last_completed_page'] / checkpoint['total_pages']) * 100,
        'chunks_completed': checkpoint['total_chunks_completed'],
        'chunks_failed': checkpoint['failed_chunks']
    })

# For GET /api/batches/<batch_id>/data
def get_batch_data(batch_id):
    """Fetch data from completed batch"""
    cursor = g.db.cursor()
    cursor.execute('''
        SELECT * FROM scraped_data 
        WHERE run_id IN (SELECT id FROM runs WHERE batch_id = %s)
        LIMIT %s OFFSET %s
    ''', (batch_id, limit, offset))
    
    return jsonify({'data': cursor.fetchall()})
```

### Service Integration Points

```python
# Update ChunkPaginationOrchestrator to expose batch endpoints
# File: backend/src/services/chunk_pagination_orchestrator.py

def get_batch_status_summary(self, batch_id: int) -> Dict:
    """Return batch progress summary"""
    checkpoint = self.get_checkpoint(batch_id)
    cursor = self.db.cursor()
    cursor.execute('''
        SELECT COUNT(*) as completed_chunks FROM runs 
        WHERE batch_id = %s AND status = 'completed'
    ''', (batch_id,))
    result = cursor.fetchone()
    
    return {
        'batch_id': batch_id,
        'progress': checkpoint['last_completed_page'] / checkpoint['total_pages'],
        'completed_chunks': result.get('completed_chunks', 0),
        'next_chunk_start': checkpoint['next_start_page']
    }

def get_next_batch_chunk(self, batch_id: int) -> Dict:
    """Get next 10-page chunk to process"""
    checkpoint = self.get_checkpoint(batch_id)
    start_page = checkpoint['next_start_page']
    base_url = self.get_project_base_url(batch_id)
    
    urls = self.generate_batch_urls(base_url, start_page)
    return {
        'chunk_start': start_page,
        'chunk_end': start_page + 9,
        'urls': urls
    }
```

---

## 6. Data Flow for Batch Execution

### Batch Execution Flow

```
POST /api/projects/batch/run
    ↓
GroupRunService.run_group([token1, token2, ...])
    ↓ (for each token)
ParseHub API Call → run_token
    ↓
Monitor via /api/monitor/status
    ↓
Poll until completion
    ↓
GET /api/monitor/data → fetch records
    ↓
Store in monitoring_sessions + scraped_records + data_lineage
```

### Checkpoint-Based Pagination Flow

```
GET /api/metadata/:id
    ↓
Request scraping task
    ↓
ChunkPaginationOrchestrator.get_checkpoint(project_id)
    ↓ reads current_page_scraped from metadata
    ↓
ChunkPaginationOrchestrator.generate_batch_urls(base_url, start_page)
    ↓ generates 10 URLs for next batch
    ↓
ChunkPaginationOrchestrator.trigger_batch_run(token, first_url)
    ↓ calls ParseHub with start_url
    ↓
ChunkPaginationOrchestrator.poll_run_completion(run_token)
    ↓ polls every 5 seconds until done
    ↓
fetch_batch_data(run_token)
    ↓ fetch results from ParseHub
    ↓
Store with source_page tracking
    ↓
ChunkPaginationOrchestrator.update_checkpoint(project_id, max_page_from_batch)
    ↓ updates current_page_scraped in metadata
```

---

## 7. Configuration & Environment Variables

**File:** `.env` (in backend/src/api/)

Required for API operation:
```
PARSEHUB_API_KEY=<key>
PARSEHUB_BASE_URL=https://www.parsehub.com/api/v2
BACKEND_API_KEY=<secret>
ALLOWED_ORIGINS=*

# Snowflake
SNOWFLAKE_ACCOUNT=<account>
SNOWFLAKE_USER=<user>
SNOWFLAKE_PASSWORD=<password>
SNOWFLAKE_DATABASE=<db>
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_SCHEMA=PUBLIC

# Background services
INCREMENTAL_SCRAPING_INTERVAL=30  # minutes
AUTO_SYNC_INTERVAL=5              # minutes
```

---

## 8. Summary: Files & Key Signatures

### Essential Files for Batch/Checkpoint Implementation

| File | Purpose | Key Classes/Functions |
|------|---------|-----|
| [backend/src/api/api_server.py](backend/src/api/api_server.py) | Flask app + routes | `@app.route()`, `validate_api_key()` |
| [backend/src/models/database.py](backend/src/models/database.py) | DB models + queries | `ParseHubDatabase`, `cursor()`, `connect()`, `init_db()` |
| [backend/src/services/chunk_pagination_orchestrator.py](backend/src/services/chunk_pagination_orchestrator.py) | **Batch orchestration** | `get_checkpoint()`, `update_checkpoint()`, `generate_batch_urls()`, `trigger_batch_run()`, `poll_run_completion()` |
| [backend/src/services/group_run_service.py](backend/src/services/group_run_service.py) | Multi-project runs | `run_group()`, `_run_single_project()` |
| [backend/src/services/pagination_service.py](backend/src/services/pagination_service.py) | URL pagination logic | `detect_pagination_pattern()`, `generate_next_page_url()` |
| [backend/src/services/scheduled_run_service.py](backend/src/services/scheduled_run_service.py) | Scheduled execution | `schedule_once()`, `schedule_recurring()` |
| [backend/src/services/monitoring_service.py](backend/src/services/monitoring_service.py) | Real-time monitoring | `monitor_run_realtime()` |
| [backend/src/models/init_snowflake.sql](backend/src/models/init_snowflake.sql) | Database schema | Tables: `metadata`, `runs`, `run_checkpoints`, `scraping_sessions`, `iteration_runs` |

### Batch-Related Endpoints for Implementation

**Currently Existing:**
- `POST /api/projects/batch/run` - Run multiple projects
- `POST /api/projects/schedule` - Schedule runs
- `GET /api/scheduled-runs` - List scheduled runs

**Recommended New Endpoints:**
- `POST /api/batches` - Create batch task
- `GET /api/batches/:batch_id` - Get batch status
- `GET /api/batches/:batch_id/checkpoint` - Get checkpoint info
- `PUT /api/batches/:batch_id/checkpoint` - Update checkpoint
- `GET /api/batches/:batch_id/data` - Fetch batch results
- `POST /api/batches/:batch_id/resume` - Resume checkpoint
- `DELETE /api/batches/:batch_id` - Cancel batch

---

## 9. Integration Testing Points

### Test Checkpoint Recovery
```python
# Test flow:
1. Start batch scraping → ChunkPaginationOrchestrator.trigger_batch_run()
2. Interrupt mid-batch
3. Resume → ChunkPaginationOrchestrator.get_checkpoint()
4. Verify next_start_page is correct
5. Continue from last_completed_page
```

### Test URL Pagination Pattern Detection
```python
# Test URLs:
- ?page=2 → query_page
- /page/2/ → path_style  
- ?offset=20 → offset
- ?p=2 → query_p
```

### Test Batch Result Storage
```python
# Verify:
1. source_page tracking in scrape d_records
2. Deduplication via data_hash + run_token
3. Data lineage tracking in data_lineage table
```

