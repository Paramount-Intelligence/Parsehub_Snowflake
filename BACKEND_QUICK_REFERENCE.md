# Backend API - Quick Reference Guide

## 1. Flask Entry Point
- **File:** `backend/src/api/api_server.py`
- **App:** Flask instance with CORS enabled
- **Pattern:** Lazy service initialization with request-scoped DB connections

## 2. Batch-Related Endpoints

### Execute Batch Operations
- `POST /api/projects/batch/run` (Line 1626)
  - **Input:** `{"project_tokens": ["token1", "token2"]}`
  - **Uses:** `GroupRunService.run_group()`
  - **Returns:** `{success, total_projects, successful, failed, results}`

### Schedule Runs
- `POST /api/projects/schedule` (Line 1658)
  - **Input:** `{projectToken, scheduleType, scheduledTime, frequency, pages}`
  - **Uses:** `ScheduledRunService.schedule_once/recurring()`

### Monitor Batch Progress
- `GET /api/monitor/status?session_id=X` (Line 347)
  - **Returns:** `{status, total_records, progress_percentage, current_url}`

## 3. Database Classes & Methods

### ParseHubDatabase (backend/src/models/database.py)
```python
# Main methods:
db.connect()                           # Get Snowflake connection
db.cursor()                            # Get cursor with shim
db.get_checkpoint(project_id)          # Read checkpoint
db.update_checkpoint(project_id, page) # Update checkpoint
```

### Key Tables
| Table | Purpose | Checkpoint Field |
|-------|---------|------------------|
| `metadata` | Project info | `current_page_scraped` |
| `runs` | Execution history | `pages_scraped`, `records_count` |
| `run_checkpoints` | Progress snapshots | `item_count_at_time`, `snapshot_timestamp` |
| `scraping_sessions` | Campaign-level tracking | `pages_completed` |
| `iteration_runs` | Batch-level tracking | `status`, `completed_at` |
| `monitoring_sessions` | Real-time monitoring | `total_pages`, `progress_percentage` |
| `scraped_records` | Actual data rows | `page_number` (for deduplication) |

## 4. Orchestrator (ChunkPaginationOrchestrator)
**File:** `backend/src/services/chunk_pagination_orchestrator.py`

### Key Constants
```python
CHUNK_SIZE = 10                    # Pages per batch
POLL_INTERVAL = 5                  # Seconds between status checks
MAX_POLL_ATTEMPTS = 360            # 30 minutes max wait
```

### Core Methods
```python
# Checkpoint Management
checkpoint = orch.get_checkpoint(project_id)
orch.update_checkpoint(project_id, last_completed_page)

# Batch URL Generation
urls = orch.generate_batch_urls(base_url, start_page)  # Returns 10 URLs

# ParseHub Integration
result = orch.trigger_batch_run(token, start_url, start_page, end_page)
status = orch.poll_run_completion(run_token, max_attempts=360)

# Storage
orch.store_batch_results(project_id, data, batch_number)
```

### Pagination Patterns Detected
- `?page=N` → query_page
- `/page/N/` → path_style
- `?offset=N` → offset
- `?p=N` → query_p

## 5. Checkpoint Data Structure

```python
checkpoint = {
    'last_completed_page': int,          # Highest page completed
    'total_pages': int,                  # Target pages
    'next_start_page': int,              # Where to resume
    'checkpoint_timestamp': str,         # ISO timestamp
    'total_chunks_completed': int,       # Batch count
    'failed_chunks': int                 # Failed batches
}
```

## 6. Batch Execution Flow

```
1. POST /api/projects/batch/run
   ↓
2. GroupRunService.run_group([tokens])
   ↓ (for each token)
3. ParseHub API: requests.post("/projects/{token}/run")
   ↓
4. Returns run_token
   ↓
5. GET /api/monitor/status?session_id=X
   ↓
6. Poll until completion
   ↓
7. Fetch data, store with source_page tracking
```

## 7. Service Classes (to import in new endpoints)

```python
from src.models.database import ParseHubDatabase
from src.services.chunk_pagination_orchestrator import ChunkPaginationOrchestrator
from src.services.group_run_service import GroupRunService
from src.services.pagination_service import PaginationService
from src.services.scheduled_run_service import get_scheduled_run_service
from src.services.monitoring_service import MonitoringService
```

## 8. Adding New Batch Endpoints - Template

```python
@app.route('/api/batches/<batch_id>/checkpoint', methods=['GET'])
def get_batch_checkpoint(batch_id):
    try:
        orch = ChunkPaginationOrchestrator()
        checkpoint = orch.get_checkpoint(batch_id)
        return jsonify({
            'success': True,
            'checkpoint': checkpoint
        }), 200
    except Exception as e:
        logger.error(f'[BATCH] Error: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/batches/<batch_id>/checkpoint', methods=['PUT'])
def update_batch_checkpoint(batch_id):
    try:
        data = request.get_json()
        last_page = data.get('last_completed_page')
        
        orch = ChunkPaginationOrchestrator()
        orch.update_checkpoint(batch_id, last_page)
        
        return jsonify({'success': True}), 200
    except Exception as e:
        logger.error(f'[BATCH] Error: {e}')
        return jsonify({'error': str(e)}), 500
```

## 9. Database Connection Pattern

```python
# In route handlers, use:
conn = g.db.connect()              # Get connection
cursor = conn.cursor()             # Get cursor
cursor.execute(sql, params)        # Execute query
result = cursor.fetchone()         # Fetch result
g.db.disconnect()                  # Return to pool (auto on teardown)
```

## 10. Environment Configuration

**Location:** `.env` in `backend/src/api/`

Required vars:
```
PARSEHUB_API_KEY=<your_key>
PARSEHUB_BASE_URL=https://www.parsehub.com/api/v2
SNOWFLAKE_ACCOUNT=<account>
SNOWFLAKE_USER=<user>
SNOWFLAKE_PASSWORD=<password>
SNOWFLAKE_DATABASE=<database>
BACKEND_API_KEY=<secret>
INCREMENTAL_SCRAPING_INTERVAL=30
```

## 11. Key File Paths for Implementation

| Component | File |
|-----------|------|
| **API Routes** | `backend/src/api/api_server.py` |
| **Database Models** | `backend/src/models/database.py` |
| **Batch Orchestration** | `backend/src/services/chunk_pagination_orchestrator.py` |
| **Group Execution** | `backend/src/services/group_run_service.py` |
| **URL Pagination** | `backend/src/services/pagination_service.py` |
| **Scheduling** | `backend/src/services/scheduled_run_service.py` |
| **Database Schema** | `backend/src/models/init_snowflake.sql` |

## 12. Recommended New Batch Endpoints

```
POST   /api/batches                    - Create new batch
GET    /api/batches/:batch_id          - Get batch details
GET    /api/batches/:batch_id/status   - Get batch progress
PUT    /api/batches/:batch_id/checkpoint - Update checkpoint
GET    /api/batches/:batch_id/data     - Fetch batch results
POST   /api/batches/:batch_id/resume   - Resume from checkpoint
DELETE /api/batches/:batch_id          - Cancel batch
GET    /api/batches/:batch_id/chunks   - List batch chunks
```

