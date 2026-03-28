# Code Comparison: Old vs New System

This document shows the exact differences between the old ad-hoc system and the new batch-based system.

---

## System Flow Comparison

### OLD SYSTEM FLOW
```python
# Old: Polling-based with continuation projects

def check_and_match_pages():
    projects = get_incomplete_projects()
    
    for project_id, project_token, total_pages, current_page_scraped in projects:
        if current_page_scraped < total_pages:
            next_page = current_page_scraped + 1
            
            # PROBLEM 1: Creates NEW project
            continuation_project = create_continuation_project(
                original_token=project_token,
                modified_url=modify_url_for_page(start_url, next_page),
                start_page=next_page
            )
            
            # PROBLEM 2: Runs new project
            run_result = run_project(continuation_project['token'])
            
            # PROBLEM 3: No page tracking
            store_run_data(run_result)

# PROBLEM 4: Polling loop runs every 30 minutes
# This repeats indefinitely, creating more and more projects
```

**Issues:**
- ❌ New project created for each continuation
- ❌ Polls every 30 minutes regardless of need
- ❌ No source_page tracking (duplicates possible)
- ❌ Ad-hoc recovery creates even more projects
- ❌ Projects accumulate in ParseHub account
- ❌ Hard to resume or troubleshoot

---

### NEW SYSTEM FLOW
```python
# New: Batch-based with single project

def run_scraping_batch_cycle(project_id, project_token, base_url):
    max_batches = None  # Unlimited
    
    while True:
        # Step 1: Read checkpoint
        checkpoint = get_checkpoint(project_id)
        start_page = checkpoint['next_start_page']
        
        # Step 2: Generate batch URLs (10 pages)
        batch_urls = generate_batch_urls(base_url, start_page, batch_size=10)
        
        # Step 3: Trigger ONE run with first URL
        run_result = trigger_batch_run(
            project_token,  # SAME project (not new!)
            batch_urls[0],  # First URL only
            start_page,
            start_page + 9
        )
        
        if not run_result['success']:
            break
        
        # Step 4: Poll until done
        poll_result = poll_run_completion(run_result['run_token'])
        
        if not poll_result['success']:
            break
        
        # Step 5: Fetch results
        items = fetch_run_data(run_result['run_token'])
        
        # Step 6: Store WITH source_page
        store_batch_results(project_id, items)
        
        # Step 7: Update checkpoint
        update_checkpoint(project_id, max_source_page)
        
        # Step 8: Continue to next batch or exit
        if len(items) == 0:  # No more data, done
            break
```

**Benefits:**
- ✅ Single project for entire scraping session
- ✅ Synchronous batch processing (no polling needed)
- ✅ Each item tagged with source_page
- ✅ Built-in checkpoint resume
- ✅ Idempotent (can safely retry)
- ✅ Deterministic & traceable

---

## Method-by-Method Comparison

### Checkpoint Management

#### OLD: In metadata table only
```python
# Old
checkbox = get_checkpoint(project_id)
# Returns:
# {
#   'current_page_scraped': 25,  # Read from metadata.current_page_scraped
#   'total_pages': 100,
# }
# Problem: Can't track individual batches
```

#### NEW: Dedicated checkpoint table
```python
# New
checkpoint = get_checkpoint(project_id)
# Returns:
# {
#   'last_completed_page': 25,
#   'total_pages': 100,
#   'next_start_page': 26,
#   'checkpoint_timestamp': '2024-01-15T10:30:00',
#   'total_chunks_completed': 5,
#   'failed_chunks': 0
# }
# Benefit: Can track batch count, retry stats, timestamps
```

---

### URL Generation

#### OLD: Ad-hoc in memory
```python
# Old
def modify_url_for_page(url: str, page_number: int) -> str:
    # Simple regex replacement
    if '?page=' in url:
        return re.sub(r'([?&]page=)\d+', rf'\1{page_number}', url)
    elif '?p=' in url:
        return re.sub(r'([?&]p=)\d+', rf'\1{page_number}', url)
    # ... etc
    return f"{url}?page={page_number}"

# Problem: Single URL per call, called 50+ times for pagination resume
```

#### NEW: Batch generation
```python
# New
def generate_batch_urls(base_url, start_page, batch_size=10):
    urls = []
    for page_offset in range(batch_size):
        page_num = start_page + page_offset
        url = generate_page_url(base_url, page_num)
        urls.append(url)
    return urls  # [url_page1, url_page2, ..., url_page10]

# Benefit: All 10 URLs generated at once, reusable
```

---

### Running ParseHub

#### OLD: Creates continuation project
```python
# Old
def trigger_continuation_run(project_token, start_page):
    # 1. Fetch original project
    original = get_project_details(project_token)
    
    # 2. CREATE NEW PROJECT (!) with modified URL
    continuation_project = create_continuation_project(
        original_token=project_token,
        modified_url=start_url_with_page(original['start_url'], start_page),
        title=f"{original['title']} - Continuation (Page {start_page})"
    )
    
    # 3. Run the new project
    run_result = run_project(continuation_project['token'])
    
    return run_result

# Problem: Creates new project & token for EACH continuation
# Result: Account accumulates 50+ projects for one website
```

#### NEW: Uses same project
```python
# New
def trigger_batch_run(project_token, start_url, batch_start_page, batch_end_page):
    # 1. Trigger ParseHub with start_url
    response = requests.post(
        f'{BASE_URL}/projects/{project_token}/run',
        json={'start_url': start_url},  # Use provided URL
        params={'api_key': api_key}
    )
    
    data = response.json()
    return {
        'success': True,
        'run_token': data.get('run_token'),
        'batch_start_page': batch_start_page,
        'batch_end_page': batch_end_page
    }

# Benefit: Same project used throughout
# Result: Single project, multiple batches
```

---

### Data Storage

#### OLD: No page tracking
```python
# Old
def insert_product_data(project_id, run_token, products):
    for product in products:
        cursor.execute('''
            INSERT INTO product_data 
            (project_id, run_token, name, price, ...)
            VALUES (?, ?, ?, ?, ...)
        ''', (project_id, run_token, product['name'], product['price'], ...))

# Problem: No way to know which page product came from
# Result: Duplicates possible if batch retry needed
```

#### NEW: With source_page tracking
```python
# New
def store_batch_results(project_id, run_token, items, batch_start_page, batch_end_page):
    stored_count = 0
    max_source_page = batch_start_page - 1
    
    for item in items:
        # Extract or infer source_page
        source_page = item.get('source_page', batch_start_page)
        max_source_page = max(max_source_page, source_page)
        
        cursor.execute('''
            INSERT INTO product_data 
            (project_id, run_token, source_page, raw_data, created_date)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (project_id, source_page, raw_data)  -- Dedup key
            DO NOTHING
        ''', (project_id, run_token, source_page, json.dumps(item), datetime.now()))
        
        if cursor.rowcount > 0:
            stored_count += 1
    
    return {
        'stored_count': stored_count,
        'max_source_page': max_source_page
    }

# Benefit: source_page tracks origin, enables deduplication
# Result: Safe to retry - duplicates automatically skipped
```

---

### Checkpoint Update

#### OLD: Update after arbitrary batch
```python
# Old
def update_metadata_pages(project_id, pages_scraped):
    current_page = get_current_page_scraped(project_id)
    new_page = min(current_page + pages_scraped, total_pages)
    
    cursor.execute('''
        UPDATE metadata
        SET current_page_scraped = ?
        WHERE project_id = ?
    ''', (new_page, project_id))

# Problem: Assumes pages_scraped = 1 run
# Problem: No consistency check
# Result: Page count may drift
```

#### NEW: Update with max source_page
```python
# New
def update_checkpoint(project_id, last_completed_page):
    # last_completed_page = max(source_page) from batch
    cursor.execute('''
        UPDATE metadata
        SET current_page_scraped = %s, updated_date = %s
        WHERE project_id = %s
    ''', (last_completed_page, datetime.now(), project_id))
    
    # Also record in batch_checkpoints for tracking
    cursor.execute('''
        INSERT INTO batch_checkpoints 
        (project_id, checkpoint_type, last_completed_page, batch_status)
        VALUES (%s, %s, %s, %s)
    ''', (project_id, 'batch_complete', last_completed_page, 'completed'))

# Benefit: Tracks actual max page from items
# Benefit: Batch history recorded
# Result: Exact resume point known, audit trail available
```

---

## Database Schema Comparison

### OLD Schema
```sql
-- Metadata table (project tracking)
metadata
├── current_page_scraped  -- Where we think we are
├── total_pages           -- Target page count
├── project_token         -- ParseHub token
└── ... (other fields)

-- Runs table (tracking runs)
runs
├── project_id
├── run_token
├── status
├── pages_scraped
├── is_continuation       -- Flag showing it's a continuation attempt
└── ... 

-- Product data (results)
product_data
├── project_id
├── run_token
├── name, price, ...      -- Item fields
└── ... (NO page tracking!)
```

**Problems:**
- ❌ No way to track individual batches
- ❌ product_data has no source_page for dedup
- ❌ No batch checkpoint history
- ❌ Recovery operations scattered

---

### NEW Schema
```sql
-- Metadata table (unchanged core, but added fields)
metadata
├── current_page_scraped  -- Last completed page
├── total_pages           -- Target
├── start_url             -- For batch URL generation ← NEW
├── project_token
└── ...

-- Runs table (with batch tracking)
runs
├── project_id
├── run_token
├── status
├── pages_scraped
├── is_batch_run          -- Boolean: TRUE for new system ← NEW
├── batch_id              -- Links to batch cycle ← NEW
└── ...

-- Product data (with dedup support)
product_data
├── project_id
├── run_token
├── source_page           -- Which page item came from ← NEW
├── batch_id              -- Which batch ← NEW
├── name, price, ...
└── ...

-- NEW: Batch checkpoints (audit trail + recovery)
batch_checkpoints
├── project_id
├── batch_id
├── checkpoint_type       -- 'batch_start', 'batch_complete'
├── last_completed_page
├── batch_start_page
├── batch_end_page
├── total_items_from_batch
├── batch_status          -- 'in_progress', 'completed', 'failed'
├── run_token
├── checkpoint_timestamp  -- When checkpoint was taken
└── ...
```

**Benefits:**
- ✅ source_page enables deduplication
- ✅ batch_checkpoints provides audit trail
- ✅ is_batch_run distinguishes old from new runs
- ✅ Can track batch lifecycle
- ✅ Can derive retry stats

---

## Execution Flow: Full Example

### OLD System: Scrape pages 26-30
```
# Time 0: Initial Check
├─ projects = get_incomplete_projects()
├─ project = { id: 1, token: 'abc123...', current_page: 25, total_pages: 100 }
└─ next_page = 26

# Time 1: Create Continuation Project
├─ modified_url = 'https://example.com?page=26'
├─ NEW continuation_project = {
│   │   token: 'cont_001...',
│   │   title: '... - Continuation (Page 26)',
│   │   ...
│   }
└─ INSERT INTO projects (token='cont_001...', continuation=TRUE, original_id=1)

# Time 2: Run Continuation Project
├─ run = ParseHub.run('cont_001...')  ← NEW project
├─ run_token = 'run_001...'
└─ INSERT INTO runs (project_id=1, run_token='run_001...', continuation=TRUE)

# Time 3-20: Poll (every 5 sec)
├─ status = ParseHub.get_run_status('run_001...') = 'running'
├─ wait 5 sec
└─ repeat...

# Time 21: Run Complete
├─ data = ParseHub.get_data('run_001...')
├─ INSERT INTO product_data (project_id=1, run_token='run_001...', items)
│   # NO source_page, NO batch info!
└─ UPDATE metadata SET current_page_scraped=26

# Time 22: Loop again (no throttling)
# Time 23: Create ANOTHER continuation project (cont_002)
├─ modified_url = 'https://example.com?page=27'
├─ NEW continuation_project = { token: 'cont_002...', ... }
└─ repeat...

# Result after scraping 26-30:
# - 5 NEW projects created (cont_001...cont_005)
# - 5 runs executed
# - Account has 5x more projects!
# - next_page might be 30 or 40 (unclear)
# - If any item duplicated, no way to know source

# Time 30+: Monitoring finds no data
├─ stuck_detector sees 30 min no progress
├─ creates RECOVERY project (rec_001)
├─ still accumulating projects!
└─ human must manually investigate...
```

---

### NEW System: Scrape pages 26-35 (one batch)
```
# Time 0: Read Checkpoint
├─ checkpoint = get_checkpoint(project_id=1)
├─ checkpoint = {
│   │   last_completed_page: 25,
│   │   next_start_page: 26,
│   │   total_pages: 100,
│   │   batches_completed: 5
│   }
└─ start_page = 26

# Time 1: Generate Batch URLs
├─ batch_urls = generate_batch_urls(
│   │   base_url='https://example.com?page=25',
│   │   start_page=26,
│   │   batch_size=10
│   │ )
├─ batch_urls = [
│   │   'https://example.com?page=26',
│   │   'https://example.com?page=27',
│   │   ...,
│   │   'https://example.com?page=35'
│   │ ]
└─ No new URL resources needed

# Time 2: Trigger Batch Run (ONE project, ONE run)
├─ run = ParseHub.run(
│   │   project_token='abc123...',  ← SAME project (not new!)
│   │   start_url='https://example.com?page=26'
│   │ )
├─ run_token = 'run_batch_001...'
└─ INSERT INTO runs (
    │   project_id=1,
    │   run_token='run_batch_001...',
    │   is_batch_run=TRUE,  ← Marked as batch
    │   batch_id='batch_001'
    │ )

# Time 3-20: Poll (every 5 sec, same as before)
├─ status = ParseHub.get_run_status('run_batch_001...') = 'running'
└─ repeat...

# Time 21: Run Complete
├─ data = ParseHub.get_data('run_batch_001...')
├─ data includes items from pages 26-35
├─ INSERT INTO product_data:
│   ├─ item_1: { source_page: 26, ... }
│   ├─ item_2: { source_page: 26, ... }
│   ├─ item_3: { source_page: 27, ... }
│   └─ ... (all tagged with source_page!)
├─ INSERT INTO batch_checkpoints:
│   ├─ batch_id: 'batch_001'
│   ├─ last_completed_page: 35
│   ├─ batch_status: 'completed'
│   └─ items_from_batch: 47
└─ UPDATE metadata SET current_page_scraped=35

# Time 22: Next Batch (if needed)
├─ checkpoint = get_checkpoint(project_id=1)
├─ next_start_page = 36
├─ batch_urls = [page_36, ... page_45]
├─ run = ParseHub.run('abc123...', start_url=page_36)  ← SAME project AGAIN
└─ repeat...

# Result after scraping 26-55 (30 pages = 3 batches):
# - 0 new projects created (same 'abc123...' used 3 times)
# - 3 runs executed  
# - Account has 0 extra clutter
# - All items tagged with source_page 26-55
# - Exact checkpoint at page 55
# - If batch needs retry:
#   ├─ Checkpoint read = 35
#   ├─ Next batch starts at 36 (no duplication)
#   └─ source_page deduplication prevents double-count

# Time 30+: Project completes normally
├─ no anomalies
├─ no stuck detection needed
├─ progress is deterministic and logged
└─ audit trail in batch_checkpoints table
```

---

## Key Differences Summary

| Aspect | OLD | NEW |
|--------|-----|-----|
| **Projects** | Create 1 per continuation | Use 1 for entire scrape |
| **Runs** | 1 per continuation | 1 per 10-page batch |
| **Account Clutter** | 50+ projects | 1 project |
| **Page Tracking** | Metadata only | metadata + batch_checkpoints |
| **Item Origin** | Unknown | source_page tracked |
| **Deduplication** | Manual/if lucky | Automatic via source_page |
| **Retry Safety** | Probability of dupicates | Guaranteed safe |
| **Resume Point** | Approximate | Exact |
| **Recovery Method** | Reactive (stuck detection) | Preventive (checkpoint) |
| **Audit Trail** | Limited | Full batch_checkpoints table |
| **Determinism** | Ad-hoc | Deterministic |
| **Scalability** | Degrades (project bloat) | Linear with data size |

---

## Migration Path: Code Changes

### Step 1: Run Database Migration
```python
from backend.migrations.batch_pagination_migration import run_migration
result = run_migration(db)
# Adds new columns, tables, indexes
```

### Step 2: Deploy New Code
```bash
# New service
cp chunk_pagination_orchestrator.py backend/src/services/

# Refactored manager (uses new orchestrator)
cp incremental_scraping_manager_refactored.py backend/src/services/
# Rename to: incremental_scraping_manager.py (when ready to switch)

# Extended services
# (pagination_service.py, data_ingestion_service.py already updated)
```

### Step 3: Update Scheduler
```python
# OLD:
from src.services.incremental_scraping_manager import IncrementalScrapingManager
manager = IncrementalScrapingManager()
manager.check_and_match_pages()  # REMOVED
manager.monitor_continuation_runs()  # REMOVED

# NEW:
from src.services.incremental_scraping_manager import IncrementalScrapingManager
manager = IncrementalScrapingManager()
result = manager.check_and_run_batch_scraping(max_batches=1)  # NEW
# Use result for logging/alerting
```

### Step 4: Gradual Rollout (Optional)
```python
# Can keep both systems running in parallel during transition
# Route projects to old or new system based on flag

if project['use_new_system']:
    result = manager.check_and_run_batch_scraping(max_batches=1)
else:
    # old system still running
    pass
```

---

## Testing Migration

### Before
```bash
# Old system test
python -c "
from src.services.incremental_scraping_manager import IncrementalScrapingManager
m = IncrementalScrapingManager()
m.check_and_match_pages()
# May create 50+ projects
"
```

### After
```bash
# New system test
python test_batch_pagination.py --all-projects --batches 1
# Uses single project multiple times, creates 0 new projects
```

---

## Questions?

- **Architecture**: See `BATCH_PAGINATION_IMPLEMENTATION.md`
- **Deployment**: See `DEPLOYMENT_CHECKLIST.md`
- **API Details**: See docstrings in `chunk_pagination_orchestrator.py`
