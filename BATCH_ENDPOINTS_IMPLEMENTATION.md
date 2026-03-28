# Backend Batch Endpoints Implementation

**Status**: ✅ COMPLETE - All 8 batch endpoints implemented and registered

**Date**: 2024-01-15  
**Files Created**: 1 new file (`backend/src/api/batch_routes.py`)  
**Files Modified**: 1 file (`backend/src/api/api_server.py`)

---

## Summary

Successfully implemented all 8 batch scraping endpoints required by the frontend. These endpoints enable:
- Starting/resuming batch scraping with checkpoint support
- Real-time polling of batch progress
- Retrieving scraped records
- Batch history and statistics
- Retry capability for failed batches
- Graceful stopping of scraping sessions

---

## Endpoints Implemented

### 1. **Start Batch Scraping**
- **Route**: `POST /api/projects/batch/start`
- **Purpose**: Start a new batch scraping session or resume from checkpoint
- **Request**:
  ```json
  {
    "project_token": "tXXXXXXXXXXXXX",
    "project_url": "https://example.com/page=1",
    "project_name": "Project Name",
    "resume_from_checkpoint": false
  }
  ```
- **Response** (201 Created):
  ```json
  {
    "success": true,
    "run_token": "abc123def456",
    "session_id": "sess_123",
    "batch_number": 1,
    "batch_range": "1-10 pages",
    "checkpoint": {
      "last_completed_page": 0,
      "next_start_page": 1,
      "total_pages": 100,
      "total_batches_completed": 0
    }
  }
  ```
- **Key Features**:
  - Validates project exists in metadata
  - Gets checkpoint from `ChunkPaginationOrchestrator`
  - Generates batch URLs (10-page chunks)
  - Triggers ParseHub run via orchestrator
  - Creates monitoring session for tracking
  - Supports resume-from-checkpoint mode

### 2. **Get Checkpoint**
- **Route**: `GET /api/projects/{project_token}/checkpoint`
- **Purpose**: Retrieve checkpoint (resumable state) for a project
- **Response** (200 OK):
  ```json
  {
    "last_completed_page": 40,
    "next_start_page": 41,
    "total_pages": 100,
    "total_batches_completed": 4,
    "failed_batches": 0,
    "consecutive_empty_batches": 0,
    "checkpoint_timestamp": "2024-01-15T14:00:00"
  }
  ```
- **Key Features**:
  - Non-destructive read (safe to call multiple times)
  - Returns gracefully if project not found (empty checkpoint)
  - Queries `ChunkPaginationOrchestrator` for active checkpoint
  - Frontend uses this on component load

### 3. **Get Batch Status** (Polling)
- **Route**: `GET /api/projects/batch/status?run_token={token}`
- **Purpose**: Poll the status of a currently running batch
- **Response** (200 OK):
  ```json
  {
    "batch_number": 5,
    "batch_range": "41-50 pages",
    "status": "scraping",
    "records_in_batch": 32,
    "total_records_to_date": 425,
    "error": null
  }
  ```
- **Poll Intervals**: Frontend polls every 3 seconds (via `useBatchMonitoring` hook)
- **Key Features**:
  - Queries ParseHub via orchestrator
  - Returns current batch metadata
  - Indicates if scraping is complete
  - Provides incremental record counts

### 4. **Get Batch Records**
- **Route**: `GET /api/projects/batch/records?run_token={token}&limit=100`
- **Purpose**: Retrieve data records scraped in current batch
- **Response** (200 OK):
  ```json
  {
    "records": [
      { "id": 1, "title": "...", "source_page": 1, ... },
      ...
    ],
    "total_count": 425,
    "batch_count": 32
  }
  ```
- **Poll Intervals**: Frontend polls every 5 seconds (batched with status queries)
- **Key Features**:
  - Queries Snowflake data table directly
  - Supports pagination via `limit` parameter
  - Returns record count for UI updates
  - Efficient batch record retrieval

### 5. **Retry Failed Batch**
- **Route**: `POST /api/projects/{project_token}/batch/retry`
- **Purpose**: Retry the last failed batch
- **Request**:
  ```json
  {
    "batch_number": 5
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "success": true,
    "run_token": "new_run_token",
    "batch_number": 5,
    "message": "Batch retry initiated"
  }
  ```
- **Key Features**:
  - Queries checkpoint to find failed batch page range
  - Regenerates batch URLs for retry
  - Triggers new ParseHub run
  - Returns new run_token for monitoring

### 6. **Stop Batch Scraping**
- **Route**: `POST /api/projects/batch/stop`
- **Purpose**: Gracefully stop a running or paused batch session
- **Request**:
  ```json
  {
    "run_token": "abc123def456"
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "success": true,
    "message": "Batch scraping stopped"
  }
  ```
- **Key Features**:
  - Updates run status to 'stopped' in database
  - Acknowledges frontend's stop request
  - Stops polling on frontend side

### 7. **Get Batch History**
- **Route**: `GET /api/projects/{project_token}/batch/history?limit=20`
- **Purpose**: Retrieve history of completed and failed batches
- **Response** (200 OK):
  ```json
  {
    "batch_history": [
      {
        "batch_number": 1,
        "batch_range": "1-10",
        "status": "completed",
        "records_scraped": 125,
        "started_at": "2024-01-15T10:00:00",
        "completed_at": "2024-01-15T10:15:00",
        "error_message": null
      },
      ...
    ],
    "last_checkpoint": { ... }
  }
  ```
- **Key Features**:
  - Queries all runs table filtered by project and batch flag
  - Formats history with pagination support
  - Includes current checkpoint
  - Used by `BatchHistory` component in UI

### 8. **Get Batch Statistics**
- **Route**: `GET /api/projects/{project_token}/batch/statistics`
- **Purpose**: Retrieve aggregate statistics for batch campaign
- **Response** (200 OK):
  ```json
  {
    "total_batches": 15,
    "completed_batches": 14,
    "failed_batches": 1,
    "total_records": 4250,
    "avg_records_per_batch": 283,
    "success_rate": 93.3,
    "last_scraped_at": "2024-01-15T14:30:00",
    "estimated_completion": {
      "batches_remaining": 2,
      "estimated_pages_remaining": 20
    }
  }
  ```
- **Key Features**:
  - Calculates success rate and averages
  - Provides estimated completion metrics
  - Used by `BatchStatistics` dashboard component
  - Updated periodically via frontend polling

---

## Architecture

### File Structure
```
backend/
├── src/
│   ├── api/
│   │   ├── api_server.py (MODIFIED - added blueprint registration)
│   │   └── batch_routes.py (NEW - 8 endpoints)
│   ├── models/
│   │   └── database.py (used for queries)
│   └── services/
│       └── chunk_pagination_orchestrator.py (used for batch logic)
```

### Integration Points

**1. ChunkPaginationOrchestrator** (backend/src/services/)
- `get_checkpoint(project_id)` → Fetch checkpoint from metadata table
- `generate_batch_urls(base_url, start_page)` → Create 10-page batch URLs
- `trigger_batch_run(token, url, start_page, end_page)` → Call ParseHub API
- `poll_run_completion(run_token)` → Check run status

**2. ParseHubDatabase** (backend/src/models/)
- `connect()` / `cursor()` → Execute SQL queries
- `get_metadata_filtered()` → Find project by token
- `create_monitoring_session()` → Create session record
- Direct cursor queries for runs, data tables

**3. Flask Application** (backend/src/api/api_server.py)
- Blueprint registered: `app.register_blueprint(batch_bp)`
- Prefix: `/api/projects`
- CORS enabled for all origins

---

## Database Dependencies

### Tables Used

**metadata**
- `id` - Project ID  
- `project_token` - Unique project identifier
- `current_page_scraped` - Current checkpoint page
- `total_pages` - Total pages in project
- `last_known_url` - URL for pagination pattern detection

**runs**
- `run_token` - Unique run identifier
- `project_id` - FK to project
- `status` - Run status (completed, running, failed, stopped)
- `records_count` - Number of records scraped
- `created_at`, `updated_at` - Timestamps
- `is_batch_run` - Boolean flag for batch runs

**data**
- `run_token` - FK to run
- `project_id` - FK to project
- Records with `source_page` for deduplication

**run_checkpoints** (used by ChunkPaginationOrchestrator)
- Stores progress checkpoints for resume capability

---

## Frontend Integration

### API Calls Made
All endpoints are called from [lib/scrapingApi.ts](lib/scrapingApi.ts):
- `startBatchScraping()` → POST /batch/start
- `getCheckpoint()` → GET /{token}/checkpoint
- `getBatchStatus()` → GET /batch/status
- `getBatchRecords()` → GET /batch/records
- `stopBatchScraping()` → POST /batch/stop
- `retryFailedBatch()` → POST /{token}/batch/retry
- `getScrapingHistory()` → GET /{token}/batch/history
- `getBatchStatistics()` → GET /{token}/batch/statistics

### UI Components
- **RunDialog** - Calls `/batch/start` when user initiates batch mode
- **BatchProgress** - Polls `/batch/status` every 3s and `/batch/records` every 5s
- **BatchHistory** - Displays data from `/batch/history`
- **BatchStatistics** - Updates dashboard with `/batch/statistics`

---

## Error Handling

### Graceful Degradation
- If project not found: Returns empty checkpoint (won't crash)
- If database down: Returns 500 with error details
- If ParseHub API fails: Returns 500 with error and sends email alert
- If checkpoint corrupted: Returns default checkpoint

### Logging
- All operations logged with `[batch/.*]` prefix
- Request IDs from Flask included in all logs
- Stack traces logged on exceptions
- Email alerts sent for critical failures

---

## Testing Checklist

✅ **Syntax Validation**
- [x] batch_routes.py compiles without errors
- [x] api_server.py compiles with blueprint import
- [x] BlueprintRegistration is successful

⏳ **Integration Testing** (Next Steps)
- [ ] Database connected properly
- [ ] Metadata query returns valid project
- [ ] ChunkPaginationOrchestrator initializes
- [ ] Batch start endpoint returns valid run_token
- [ ] Checkpoint endpoint returns valid data
- [ ] Polling endpoints return data without errors
- [ ] Stop endpoint gracefully stops session

⏳ **Frontend Testing** (After Backend Ready)
- [ ] RunDialog can call /batch/start
- [ ] BatchProgress displays without errors
- [ ] Polling loop completes successfully
- [ ] Records display in UI
- [ ] Checkpoint resume works

---

## Next Steps

1. **Start Backend Server**: Test if endpoints are accessible
   ```bash
   cd backend
   python src/api/api_server.py
   ```

2. **Verify Routes Registered**: Check Flask routes
   ```python
   from src.api.api_server import app
   print([rule.rule for rule in app.url_map.iter_rules()])
   ```

3. **Manual Endpoint Testing**: Use curl/Postman
   ```bash
   # Get checkpoint
   curl -X GET "http://localhost:5000/api/projects/tXXXXXXXXXXXXX/checkpoint"
   
   # Start batch
   curl -X POST "http://localhost:5000/api/projects/batch/start" \
     -H "Content-Type: application/json" \
     -d '{"project_token":"tXXXXXXXXXXXXX","project_url":"https://example.com"}'
   ```

4. **Frontend Testing**: Try batch scraping in UI
   - Open RunDialog
   - Select "Batch" mode
   - Click "Start Scraping"
   - Should see BatchProgress with real-time updates

5. **Performance Validation**
   - Check polling doesn't overwhelm backend
   - Verify memory usage during polling
   - Test with multiple concurrent batches

---

## Documentation

### Endpoint Details
All endpoint documentation is inline in [backend/src/api/batch_routes.py](backend/src/api/batch_routes.py):
- Request/response schemas with examples
- Query parameters documented
- Error conditions specified
- HTTP status codes defined

### Architecture Overview
See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for system architecture
See [BACKEND.md](docs/BACKEND.md) for backend service architecture

---

## Version History

**v1.0** - Initial Implementation
- Created batch_routes.py with 8 endpoints
- Integrated ChunkPaginationOrchestrator
- Updated api_server.py with blueprint registration
- Comprehensive error handling
- Database query patterns for Snowflake

**Created**: 2024-01-15  
**Status**: Ready for Backend Testing
