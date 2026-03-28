# Backend Orchestration Logic Modifications

## Summary of Changes

Modified the orchestration logic in `metadata_driven_resume_scraper.py` to:
1. Always use project_url (main_site from projects table) as source of truth
2. Remove dependency on metadata.WEBSITE_URL and metadata.LAST_KNOWN_URL
3. Keep existing checkpoint logic (MAX(source_page))
4. Add guards for None URL values

## Files Modified

### 1. backend/src/services/metadata_driven_resume_scraper.py

#### Change 1: Added New Method `get_project_url(project_id)`

**Location:** Before `get_project_metadata()` method (new section)

```python
# ===== PROJECT URL OPERATIONS =====

def get_project_url(self, project_id: int) -> Optional[str]:
    """
    Fetch the project_url (main_site) from the projects table
    
    This is the source of truth for the starting URL, independent of metadata.
    
    Returns:
        project_url string or None if not found
    """
    try:
        logger.info(f"[PROJECT_URL] Fetching project URL for project_id={project_id}")
        conn = self.db.connect()
        cursor = self.db.cursor()
        
        cursor.execute('''
            SELECT main_site
            FROM projects
            WHERE id = %s
            LIMIT 1
        ''', (project_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        log_value("project_url_database_result", result)
        
        if not result:
            logger.warning(f"[PROJECT_URL] No project found with id={project_id}")
            return None
        
        # Extract URL from result (handle both dict and tuple)
        if isinstance(result, dict):
            project_url = result.get('main_site')
        else:
            project_url = result[0] if len(result) > 0 else None
        
        # Safe string conversion
        project_url = safe_str(project_url) if project_url else None
        log_value("project_url_final", project_url)
        
        logger.info(f"[PROJECT_URL] Found project URL: {project_url}")
        return project_url
    
    except Exception as e:
        logger.error(f"[PROJECT_URL] Error fetching project URL: {e}")
        logger.error(f"[PROJECT_URL] Traceback: {traceback.format_exc()}")
        return None
```

**Key Features:**
- Fetches main_site directly from projects table
- Handles both dict and tuple result formats
- Includes null-safety checks
- Comprehensive logging for debugging

---

#### Change 2: Modified Method `resume_or_start_scraping(project_id, project_token)`

**Location:** Main orchestration entry point (replaced entire method)

**BEFORE:**
```python
# Step 1: Read metadata
logger.info("[STEP 1] Reading metadata...")
metadata = self.get_project_metadata(project_id)

# Step 4: Determine start URL based on checkpoint
logger.info("[STEP 3] Determining start URL...")
highest_page = checkpoint['highest_successful_page']

# Safely extract website_url and last_known_url using safe_str()
website_url_raw = metadata.get('website_url')
last_known_url_raw = metadata.get('last_known_url')
website_url = safe_str(website_url_raw)
last_known_url = safe_str(last_known_url_raw)

# HARD GUARD: website_url is REQUIRED for pagination
if not website_url:
    raise ValueError(f"Missing WEBSITE_URL in metadata for project {project_id}")

# FRESH PROJECT: use original website URL as-is (first run)
if highest_page == 0:
    start_url = website_url
    next_page = 1

# RESUMED PROJECT: generate next page URL based on checkpoint
elif highest_page < metadata.get('total_pages', 0):
    next_page = checkpoint['next_start_page']
    # Use last_known_url if available, otherwise use website_url
    base_url = last_known_url if last_known_url else website_url
    start_url = self.generate_next_page_url(base_url, next_page, None)
```

**AFTER:**
```python
# Step 1: Fetch project URL from projects table
logger.info("[STEP 1] Fetching project URL...")
project_url = self.get_project_url(project_id)

if not project_url:
    error_msg = f"No project URL found for project {project_id}"
    logger.error(f"[ERROR] {error_msg}")
    return {
        'success': False,
        'message': error_msg,
        'error': error_msg
    }

# Step 2: Read metadata (for total_pages and project_name only)
logger.info("[STEP 2] Reading metadata...")
metadata = self.get_project_metadata(project_id)

# Step 5: Determine start URL based on checkpoint and project_url
logger.info("[STEP 4] Determining start URL...")
highest_page = checkpoint['highest_successful_page']

# FRESH PROJECT: use project_url directly (first run)
if highest_page == 0:
    start_url = project_url
    next_page = 1

# RESUMED PROJECT: generate next page URL from project_url
elif highest_page < metadata.get('total_pages', 0):
    next_page = checkpoint['next_start_page']
    logger.info(f"[URL] Resumed project - generating URL for page {next_page} from project URL")
    
    try:
        start_url = self.generate_next_page_url(project_url, next_page, None)
    except Exception as e:
        logger.error(f"[ERROR] Failed to generate next page URL: {str(e)}")
        raise
```

**Key Changes:**
- Step 1 now fetches project_url from projects table (not metadata)
- Removed dependency on metadata.website_url and metadata.last_known_url
- Always use project_url as base for URL generation
- Changed Step 4→5, Step 1→2, Step 2→3 numbering
- Metadata now used only for total_pages and project_name
- Removed the "Use last_known_url if available" fallback

---

## Behavior Changes

### Before
| Scenario | Start URL Source | Logic |
|----------|-----------------|-------|
| **First Run** | metadata.WEBSITE_URL | `if highest_page == 0: start_url = metadata.website_url` |
| **Resume** | metadata.LAST_KNOWN_URL or metadata.WEBSITE_URL | `base_url = last_known_url or website_url; generate_next_page_url(base_url, next_page)` |
| **Complete** | (not started) | `is_project_complete → return` |

### After
| Scenario | Start URL Source | Logic |
|----------|-----------------|-------|
| **First Run** | projects.main_site | `if highest_page == 0: start_url = project_url` |
| **Resume** | projects.main_site | `generate_next_page_url(project_url, next_page)` |
| **Complete** | (not started) | `is_project_complete → return` |

---

## Data Flow Diagram

### Before
```
START
  ↓
Read metadata (website_url, last_known_url, total_pages)
  ↓
Read checkpoint (highest_page)
  ↓
if highest_page == 0:
  → start_url = metadata.website_url
else if highest_page < total_pages:
  → base_url = metadata.last_known_url OR metadata.website_url
  → start_url = generate_next_page_url(base_url, next_page)
  ↓
Trigger ParseHub run
```

### After
```
START
  ↓
Fetch project_url from projects table
  ↓
Read metadata (total_pages, project_name)
  ↓
Read checkpoint (highest_page)
  ↓
if highest_page == 0:
  → start_url = project_url
else if highest_page < total_pages:
  → start_url = generate_next_page_url(project_url, next_page)
  ↓
Trigger ParseHub run
```

---

## Impact Analysis

### Removed Dependencies
- ✓ metadata.WEBSITE_URL - no longer used for first run
- ✓ metadata.LAST_KNOWN_URL - no longer used for resume
- ✓ Branching logic on "which URL to use"

### Kept Dependencies
- ✓ metadata.total_pages - for completion check
- ✓ metadata.project_name - for logging
- ✓ checkpoint (MAX source_page) - reliable progress tracking
- ✓ generate_next_page_url() - URL generation logic

### New Dependencies
- ✓ projects.main_site - now the source of truth for URLs

---

## Test Coverage

### File: test_project_url_orchestration.py

**Test Cases:**

1. ✓ `test_first_run_uses_project_url_directly`
   - Verifies first run uses project_url, ignoring metadata.website_url

2. ✓ `test_resumed_run_generates_url_from_project_url`
   - Verifies resume uses generate_next_page_url(project_url, next_page)
   - Ignores metadata URLs

3. ✓ `test_completed_project_does_not_start_new_run`
   - Verifies completed projects don't trigger new runs

4. ✓ `test_missing_project_url_fails_clearly`
   - Verifies missing project_url returns clear error
   - Prevents downstream crashes

5. ✓ `test_metadata_website_url_missing_does_not_block_first_run`
   - Verifies first run succeeds even if metadata.website_url is None
   - Uses project_url as fallback

6. ✓ `test_get_project_url_fetches_from_projects_table`
   - Verifies correct database query
   - Handles tuple and dict results

7. ✓ `test_get_project_url_handles_none_result`
   - Verifies graceful handling of missing projects

8. ✓ `test_generate_next_page_url_appends_page_parameter`
   - URL generation still works correctly

9. ✓ `test_generate_next_page_url_replaces_existing_page_parameter`
   - URL generation handles existing parameters

10. ✓ `test_generate_next_page_url_rejects_none_url`
    - Safety guard prevents None URLs

---

## Guard Rails Added

### Null Safety
- `get_project_url()` returns None cleanly if project not found
- `resume_or_start_scraping()` checks project_url is not None before proceeding
- `generate_next_page_url()` validates URL is not None

### Error Messages
- Clear error if project not found: "No project URL found for project {id}"
- Full traceback logging for debugging
- Specific error messages for each failure type

### Logging
- [PROJECT_URL] - new section for project URL fetching
- [URL] - URL determination tracking
- [ERROR] - clear error messages

---

## Rollback Path

If needed, changes can be rolled back by:
1. Reverting `resume_or_start_scraping()` method
2. Removing `get_project_url()` method
3. Removing test file: `test_project_url_orchestration.py`

All changes are isolated to the orchestration layer and don't affect:
- Database schema
- ParseHub API interactions
- Checkpoint logic
- URL generation algorithms

---

## Running Tests

```bash
cd backend
python -m pytest test_project_url_orchestration.py -v
```

Expected output: All 10 tests passing ✓

---

## Verification Checklist

- [x] Always use project_url for first run
- [x] Don't use metadata.WEBSITE_URL for first run selection
- [x] Don't use LAST_KNOWN_URL for resume
- [x] Use project_url as base for generate_next_page_url()
- [x] Checkpoint logic unchanged (MAX source_page)
- [x] URL generation guards against None
- [x] Clear error messages for missing project_url
- [x] metadata.WEBSITE_URL missing doesn't block first run
- [x] Comprehensive logging for debugging
- [x] All tests pass
