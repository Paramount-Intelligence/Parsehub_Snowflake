# Chunk-Based Pagination Refactoring - Complete Implementation Guide

## Overview

This document describes the refactored scraping system that replaces ad-hoc incremental scraping with **deterministic, batch-based (10-page chunk) pagination**.

### Key Improvements

✅ **Single ParseHub project** (no duplication)  
✅ **Backend-owned batching** (10 pages per batch)  
✅ **Proper checkpointing** (resume from last completed page)  
✅ **Deduplication** (source_page tracking)  
✅ **Deterministic** (same code path every time)  
✅ **Safe to retry** (idempotent batch processing)  

---

## Architecture

### Old System (Problems)
```
check_and_match_pages()
  → identify incomplete projects
  → trigger_continuation_run()
  → create_continuation_project()  ← NEW PROJECT (wasteful!)
  → modify_url_for_page()
  → run_project()
  → store with no page tracking
  → ad-hoc recovery with stuck detection
```

**Issues:**
- Creates new projects for each continuation
- Polls every 30 minutes (inefficient)
- Continuation projects clutter ParseHub account
- No proper page number tracking
- High chance of duplicates

---

### New System (Solution)
```
ChunkPaginationOrchestrator.run_scraping_batch_cycle()
  1. get_checkpoint()           → Read last_completed_page from DB
  2. generate_batch_urls()      → Create 10-page URLs from checkpoint
  3. trigger_batch_run()        → Single project run with first URL
  4. poll_run_completion()      → Block until done
  5. fetch_run_data()           → Get results from ParseHub
  6. store_batch_results()      → Store with source_page tracking
  7. update_checkpoint()        → Update last_completed_page to max source_page
  8. repeat steps 1-7           → Next batch starts at checkpoint+1
```

**Benefits:**
- Single project (uses same token throughout)
- Backend controls batching logic
- Checkpoint enables safe resume
- source_page prevents duplicates
- Deterministic & traceable

---

## Files Changed/Created

### 1. NEW: `chunk_pagination_orchestrator.py`
Main orchestrator implementing batch-based pagination logic.

**Key Methods:**
- `get_checkpoint(project_id)` - Read progress from DB
- `generate_batch_urls(base_url, start_page)` - Create 10-page batch URLs
- `trigger_batch_run(project_token, start_url)` - Trigger one run
- `poll_run_completion(run_token)` - Block until done
- `store_batch_results()` - Save with source_page tracking
- `update_checkpoint()` - Update progress
- `run_scraping_batch_cycle()` - Main orchestration

**Usage:**
```python
from src.services.chunk_pagination_orchestrator import ChunkPaginationOrchestrator

orchestrator = ChunkPaginationOrchestrator()
result = orchestrator.run_scraping_batch_cycle(
    project_id=123,
    project_token='abc123...',
    base_url='https://example.com/products?page=1',
    max_batches=1  # Run 1 batch (10 pages)
)

print(f"Stored {result['total_items_stored']} items")
print(f"Batches: {result['batches_completed']}")
print(f"Reason: {result['end_reason']}")
```

---

### 2. REFACTORED: `incremental_scraping_manager.py`
Simplified to use the new orchestrator.

**Changes:**
- Replaced `check_and_match_pages()` with `check_and_run_batch_scraping()`
- Removed continuation project logic
- Removed ad-hoc recovery
- Now just: get incomplete projects → run batch cycles

**Usage:**
```python
from src.services.incremental_scraping_manager import IncrementalScrapingManager

manager = IncrementalScrapingManager()

# Run 1 batch for each incomplete project
result = manager.check_and_run_batch_scraping(max_batches=1)

print(f"Projects: {result['projects_processed']}")
print(f"Items: {result['total_items_stored']}")

for project in result['projects']:
    if project['success']:
        print(f"✓ {project['project_name']}: {project['items']} items")
    else:
        print(f"✗ {project['project_name']}: {project['error']}")
```

---

### 3. EXTENDED: `pagination_service.py`
Added batch URL generation utilities.

**New Class: BatchUrlGenerator**
```python
from src.services.pagination_service import BatchUrlGenerator

urls = BatchUrlGenerator.generate_batch_urls(
    base_url='https://example.com/products?page=1',
    start_page=1,
    batch_size=10
)
# Returns: [url_for_page_1, url_for_page_2, ..., url_for_page_10]
```

**Methods:**
- `generate_batch_urls()` - Create 10-page batch
- `validate_batch_urls()` - Ensure URLs are different
- `extract_page_numbers_from_batch()` - Verify pagination

---

### 4. UPDATED: `data_ingestion_service.py`
Added source_page support for deduplication.

**Changes:**
- `ingest_run()` now accepts `source_page` parameter
- Each item automatically gets source_page tagged
- Deduplication via (project_id, source_page, data_hash)

**Usage:**
```python
ingestor = ParseHubDataIngestor()

# Ingest with source page tracking
result = ingestor.ingest_run(
    project_id=123,
    project_token='abc123...',
    run_token='run456...',
    source_page=10  # Mark all items as from page 10
)

print(f"Stored: {result['inserted']} items")
```

---

### 5. DATABASE: `batch_pagination_migration.py`
Migration script for Snowflake schema updates.

**New Table: batch_checkpoints**
Dedicated checkpoint tracking for batches.

**New Columns:**
- `runs.is_batch_run` - Boolean flag
- `runs.batch_id` - Batch identifier
- `product_data.source_page` - Page origin (for dedup)
- `product_data.batch_id` - Batch link
- `metadata.start_url` - For batch URL generation

**Run Migration:**
```python
from backend.migrations.batch_pagination_migration import run_migration
from src.models.database import ParseHubDatabase

db = ParseHubDatabase()
result = run_migration(db)

# result = {
#     'success': bool,
#     'messages': ['✓ Index created...', '⊘ Column already exists...'],
#     'errors': ['✗ Failed to...']
# }
```

---

## Step-by-Step Implementation

### Step 1: Database Migration
```bash
cd backend
python -c "
from migrations.batch_pagination_migration import run_migration
from src.models.database import ParseHubDatabase

db = ParseHubDatabase()
result = run_migration(db)
print('Migration result:', 'SUCCESS' if result['success'] else 'FAILED')
for msg in result['messages']:
    print(f'  {msg}')
"
```

### Step 2: Update Configuration
Ensure `.env` has:
```bash
PARSEHUB_API_KEY=your_key_here
SNOWFLAKE_ACCOUNT=account
SNOWFLAKE_USER=user
SNOWFLAKE_PASSWORD=pwd
SNOWFLAKE_DATABASE=db
SNOWFLAKE_SCHEMA=schema
```

### Step 3: Run Single Batch for Test Project
```python
from src.services.chunk_pagination_orchestrator import ChunkPaginationOrchestrator

orchestrator = ChunkPaginationOrchestrator()

# For a test project
result = orchestrator.run_scraping_batch_cycle(
    project_id=1,
    project_token='your_token_here',
    base_url='https://example.com/products?page=1',
    max_batches=1  # Run just 1 batch (10 pages)
)

print(f"Success: {result['success']}")
print(f"Items: {result['total_items_stored']}")
print(f"End reason: {result['end_reason']}")
```

### Step 4: Integrate into Scheduler/Cron
```python
# In your scheduled task/cron job:
from src.services.incremental_scraping_manager import IncrementalScrapingManager

manager = IncrementalScrapingManager()

# Run 1 batch per incomplete project
result = manager.check_and_run_batch_scraping(max_batches=1)

# Or run multiple batches to completion
result = manager.check_and_run_batch_scraping(max_batches=None)

# Log results
for project in result['projects']:
    status = "✓" if project['success'] else "✗"
    print(f"{status} {project['project_name']}: {project['batches']} batches, {project['items']} items")
```

---

## How Checkpoint Works

### Reading Checkpoint
```
table: metadata
┌─────────────────────────────────────────┐
│ project_id  │ current_page_scraped │ ...│
│ 1           │ 25                   │    │  ← Last page completed was 25
└─────────────────────────────────────────┘

next_start_page = current_page_scraped + 1 = 26
batch = pages 26-35
```

### After Batch Completes
```
Scraped data from batch:
┌────────────────────────────────────────┐
│ product_id │ source_page │ data        │
│ 1001       │ 26          │ {...}       │
│ 1002       │ 26          │ {...}       │
│ 1003       │ 27          │ {...}       │
│ 1004       │ 28          │ {...}       │
│ 1005       │ 29          │ {...}       │
└────────────────────────────────────────┘
max_source_page = 29

UPDATE metadata SET current_page_scraped = 29 WHERE project_id = 1
```

### Resume Safety
- If run fails after fetching data but before checkpoint update → retry safely
- Product duplicates prevented by source_page + data dedup
- Batch restart idempotent (same 10 pages attempted again)

---

## Pagination Pattern Detection

The system automatically detects and generates URLs for:

1. **Query Parameter: ?page=X**
   ```
   https://example.com/products?page=1
   → https://example.com/products?page=2
   → https://example.com/products?page=3
   ```

2. **Query Parameter: ?p=X**
   ```
   https://example.com?p=1
   → https://example.com?p=2
   ```

3. **Query Parameter: ?offset=X** (20 items/page assumed)
   ```
   https://example.com?offset=0
   → https://example.com?offset=20  (page 2)
   → https://example.com?offset=40  (page 3)
   ```

4. **Path-based: /page/X/**
   ```
   https://example.com/page/1/
   → https://example.com/page/2/
   ```

---

## Configuration Options

### Batch Size
```python
CHUNK_SIZE = 10  # Pages per batch
# (configured in chunk_pagination_orchestrator.py)
```

### Polling
```python
POLL_INTERVAL = 5  # Seconds between status checks
MAX_POLL_ATTEMPTS = 360  # 30 minutes max wait
```

### Empty Result Handling
```python
EMPTY_RESULT_THRESHOLD = 3  # Stop after 3 consecutive empty batches
```

---

## Monitoring & Logging

All components log to `logging` module with standardized prefixes:

```
[CHECKPOINT]   - Checkpoint read/write
[BATCH_URLS]   - URL generation
[RUN]          - ParseHub run triggering
[POLL]         - Status polling
[DATA]         - Data fetching
[STORE]        - Data storage
[MANAGER]      - Manager orchestration
[BATCH_CYCLE]  - Main cycle progress
```

Example output:
```
================================================================================
[BATCH_CYCLE] Starting: project 1
================================================================================

[CHECKPOINT] Reading checkpoint for project 1
[CHECKPOINT] Last page: 25

[BATCH 1] Starting page: 26
[BATCH_URLS] Generated 10 URLs: page 26-35
[RUN] Triggering batch run: pages 26-35
[RUN] Start URL: https://example.com/products?page=26
[RUN] Batch run started: run_token_12345

[POLL] Still running... (attempt 10/360)
[POLL] Run completed: 50 items

[DATA] Fetched 50 items from run

[STORE] Stored 50 items, skipped 0 duplicates
[STORE] Max page reached: 29

[CHECKPOINT] Updated project 1: page 29

================================================================================
[BATCH_CYCLE] Finished: 1 batches, 50 items stored
[BATCH_CYCLE] Reason: Completed normally
================================================================================
```

---

## Troubleshooting

### Run times out (30+ minutes)
- Check ParseHub API status
- Verify website is responsive
- Reduce CHUNK_SIZE to 5 pages
- Increase MAX_POLL_ATTEMPTS

### No data being returned
- Verify start_url in metadata is correct
- Check if website added anti-scraping measures
- Test with manual ParseHub run first
- Verify ParseHub project template still works

### Duplicates detected
- Check if source_page is being stored
- Verify database deduplication logic
- Inspect product_data table for existing items

### Checkpoint not updating
- Check database permissions
- Verify runs table is writable
- Check logs for update errors
- Verify project_id exists in metadata

---

## Performance Tuning

### Batch Size
- **Smaller (5 pages)**: Faster completion per batch, more runs needed
- **Larger (20 pages)**: Fewer runs, longer to complete each

### Polling Interval
- **Shorter (2 sec)**: Faster completion detection, more API calls
- **Longer (30 sec)**: Fewer API calls, slower detection

### Concurrent Projects
```python
# Serial (default)
result = manager.check_and_run_batch_scraping(max_batches=1)

# For parallel processing in future:
# Use ThreadPoolExecutor with batch per thread
```

---

## Migration from Old System

### Phase 1: Enable New System (Parallel)
1. Deploy new code
2. Run migrations
3. Keep old system running
4. Test new system with 1-2 projects
5. Monitor for issues

### Phase 2: Switch to New System (Gradual)
1. Move 10% of projects to new system
2. Monitor for 1 week
3. Move 50% if stable
4. Move 100% after 2 weeks

### Phase 3: Cleanup (Decommission Old)
1. Verify all data complete and correct
2. Remove old continuation projects from ParseHub
3. Archive old code/configuration
4. Update documentation

---

## API Reference

### ChunkPaginationOrchestrator

#### run_scraping_batch_cycle()
```python
result = orchestrator.run_scraping_batch_cycle(
    project_id: int,           # Database project ID
    project_token: str,        # ParseHub token
    base_url: str,             # Website base URL
    max_batches: Optional[int] # Limit (None = unlimited)
)

# Returns:
{
    'success': bool,                      # Success status
    'batches_completed': int,             # Number of batches run
    'total_items_stored': int,            # Total items inserted
    'total_pages_reached': int,           # Highest page number
    'end_reason': str,                    # Why it stopped
    'error': str                          # Error if failed
}
```

#### trigger_batch_run()
```python
result = orchestrator.trigger_batch_run(
    project_token: str,        # ParseHub token
    start_url: str,            # URL to start from
    batch_start_page: int,     # First page of batch
    batch_end_page: int        # Last page of batch
)

# Returns:
{
    'success': bool,
    'run_token': str,          # If successful
    'error': str               # If failed
}
```

### IncrementalScrapingManager

#### check_and_run_batch_scraping()
```python
result = manager.check_and_run_batch_scraping(
    max_batches: Optional[int] # Limit batches per project
)

# Returns:
{
    'projects_processed': int,
    'total_items_stored': int,
    'projects': [
        {
            'project_id': int,
            'project_name': str,
            'success': bool,
            'batches': int,
            'items': int,
            'max_pages': int,
            'end_reason': str,
            'error': str
        }
    ]
}
```

---

## Questions & Support

For issues or questions, refer to:
1. [DATABASE_ARCHITECTURE.md](./DATABASE_ARCHITECTURE.md)
2. [PAGINATION_PATTERNS.md](./PAGINATION_PATTERNS.md)
3. Log files in `backend/logs/`
