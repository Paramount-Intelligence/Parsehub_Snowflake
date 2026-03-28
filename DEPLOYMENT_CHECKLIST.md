# Chunk-Based Pagination - Deployment Checklist

Use this checklist to ensure proper deployment and testing of the new system.

## Pre-Deployment (1 day before)

- [ ] Review `BATCH_PAGINATION_SUMMARY.md`
- [ ] Review `BATCH_PAGINATION_IMPLEMENTATION.md`
- [ ] Backup current database (Snowflake snapshot)
- [ ] Backup ParseHub account (note all current projects)
- [ ] Notify team of deployment window
- [ ] Prepare rollback plan (if needed)

---

## Files Deployment

### Copy New Files
- [ ] `backend/src/services/chunk_pagination_orchestrator.py` → backend/
- [ ] `backend/migrations/batch_pagination_migration.py` → backend/
- [ ] `BATCH_PAGINATION_IMPLEMENTATION.md` → root/
- [ ] `BATCH_PAGINATION_SUMMARY.md` → root/
- [ ] `test_batch_pagination.py` → root/

### Update Existing Files
- [ ] `backend/src/services/incremental_scraping_manager_refactored.py` → new version
  - Keep old version as `incremental_scraping_manager_old.py` for now
- [ ] `backend/src/services/pagination_service.py` → added BatchUrlGenerator
- [ ] `backend/src/services/data_ingestion_service.py` → added source_page parameter

### Verify File Integrity
- [ ] All files have correct imports
- [ ] No syntax errors (check with `python -m py_compile`)
- [ ] File permissions are readable/executable

---

## Environment Configuration

- [ ] `.env` has `PARSEHUB_API_KEY` set
- [ ] `.env` has `SNOWFLAKE_ACCOUNT` set
- [ ] `.env` has `SNOWFLAKE_USER` set
- [ ] `.env` has `SNOWFLAKE_PASSWORD` set
- [ ] `.env` has `SNOWFLAKE_DATABASE` set
- [ ] `.env` has `SNOWFLAKE_SCHEMA` set (default: PUBLIC)
- [ ] `.env` has `SNOWFLAKE_WAREHOUSE` set (default: COMPUTE_WH)

---

## Database Migration

### Run Migration
```bash
cd backend
python -c "
from migrations.batch_pagination_migration import run_migration
from src.models.database import ParseHubDatabase

db = ParseHubDatabase()
result = run_migration(db)
print('Success!' if result['success'] else 'Failed!')
for msg in result['messages']:
    print(f'  ✓ {msg}')
for err in result['errors']:
    print(f'  ✗ {err}')
"
```

- [ ] Migration runs without fatal errors
- [ ] Check output for "Success!"
- [ ] Verify new columns exist:
  - [ ] `runs.is_batch_run`
  - [ ] `runs.batch_id`
  - [ ] `product_data.source_page`
  - [ ] `product_data.batch_id`
  - [ ] `metadata.start_url`
- [ ] Verify new table created:
  - [ ] `batch_checkpoints` table exists
- [ ] Verify indexes created
- [ ] No permission errors

### Verify Database State
```sql
-- In Snowflake SQL worksheet
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'PRODUCT_DATA' AND column_name = 'SOURCE_PAGE';
-- Should return one row

SELECT table_name FROM information_schema.tables 
WHERE table_name = 'BATCH_CHECKPOINTS';
-- Should return one row
```

- [ ] product_data.source_page column exists
- [ ] batch_checkpoints table exists
- [ ] runs.is_batch_run column exists
- [ ] metadata.start_url column exists

---

## Dependency Verification

### Required Python Packages
```bash
pip list | grep -E "snowflake|dotenv|requests"
```

- [ ] snowflake-connector-python installed
- [ ] python-dotenv installed (for .env support)
- [ ] requests installed (for ParseHub API)

### Test Imports
```bash
python -c "
import snowflake.connector
from dotenv import load_dotenv
import requests
print('✓ All dependencies available')
"
```

- [ ] No ImportError for snowflake.connector
- [ ] No ImportError for dotenv
- [ ] No ImportError for requests

---

## System Tests

### Test 1: Database Connection
```bash
python -c "
from src.models.database import ParseHubDatabase
db = ParseHubDatabase()
conn = db.connect()
print('✓ Database connection successful')
conn.close()
"
```

- [ ] No connection errors
- [ ] Snowflake credentials accepted
- [ ] Connection closes cleanly

### Test 2: Orchestrator Instantiation
```bash
cd backend
python -c "
from src.services.chunk_pagination_orchestrator import ChunkPaginationOrchestrator
orch = ChunkPaginationOrchestrator()
print('✓ Orchestrator instantiated')
"
```

- [ ] No import errors
- [ ] No initialization errors
- [ ] API key is detected

### Test 3: Pagination Detection
```bash
python test_batch_pagination.py --pagination-url 'https://example.com/products?page=1'
```

- [ ] Detection completes
- [ ] Batch URLs generated (10 expected)
- [ ] URLs are unique
- [ ] Page numbers extracted correctly

### Test 4: Checkpoint System
```bash
# For a project ID that exists in your DB
python test_batch_pagination.py --checkpoint 1
```

- [ ] Checkpoint reads successfully
- [ ] Last completed page displayed
- [ ] Next start page calculated correctly
- [ ] Checkpoint update succeeds
- [ ] Update verification passes

### Test 5: Test Project Batch Run (DRY RUN)
```bash
# Don't actually run yet - just test the code path
python -c "
from src.services.chunk_pagination_orchestrator import ChunkPaginationOrchestrator
orch = ChunkPaginationOrchestrator()

# Verify methods exist
assert hasattr(orch, 'get_checkpoint')
assert hasattr(orch, 'generate_batch_urls')
assert hasattr(orch, 'trigger_batch_run')
assert hasattr(orch, 'poll_run_completion')
assert hasattr(orch, 'fetch_run_data')
assert hasattr(orch, 'store_batch_results')
assert hasattr(orch, 'update_checkpoint')
assert hasattr(orch, 'run_scraping_batch_cycle')

print('✓ All orchestrator methods present')
"
```

- [ ] All core methods exist
- [ ] No AttributeError

---

## Small-Scale Testing

### Test 6: Run 1 Batch for Test Project (REAL)

First, pick a project that:
- Has total_pages > 0
- Has current_page_scraped < total_pages
- Has valid start_url in metadata

```bash
# Replace PROJECT_ID
python test_batch_pagination.py --project-id PROJECT_ID --batches 1
```

**Follow the output:**
- [ ] Checkpoint reads successfully
- [ ] Batch URLs generated (should be 10)
- [ ] ParseHub run triggered (look for run_token)
- [ ] Polling begins (should see "Still running..." messages)
- [ ] Run completes (should return to prompt)
- [ ] Items stored (should see count > 0 or 0 if website empty)
- [ ] Checkpoint updated
- [ ] No fatal errors in logs

**Verify Results:**
```sql
SELECT count(*) as total FROM product_data 
WHERE project_id = PROJECT_ID AND source_page IS NOT NULL;
```

- [ ] Query returns a count
- [ ] Count matches "Stored X items" from output above
- [ ] Items have source_page values

```sql
SELECT max(source_page) as max_page 
FROM product_data WHERE project_id = PROJECT_ID;

SELECT current_page_scraped 
FROM metadata WHERE project_id = PROJECT_ID;
```

- [ ] max_page and current_page_scraped should match (or be close)

### Test 7: Resume Same Project (2nd Batch)

Run same test again:
```bash
python test_batch_pagination.py --project-id PROJECT_ID --batches 1
```

**Verify Resume Works:**
- [ ] Checkpoint starts from new page (should be max_page + 1)
- [ ] Different URLs generated (not repeat of first batch)
- [ ] New items stored (or empty if website scrolls to end)
- [ ] No duplicate items (if website allows repeat)

---

## Medium-Scale Testing

### Test 8: Run All Projects (1 batch each)

```bash
python test_batch_pagination.py --all-projects --batches 1
```

**Verify:**
- [ ] All incomplete projects processed
- [ ] At least 1 project shows ✓ (success)
- [ ] Total items > 0
- [ ] No fatal errors
- [ ] Log file created (batch_pagination_test.log)

**Check logs:**
```bash
tail -100 batch_pagination_test.log | grep -E "SUCCESS|FAILED|ERROR"
```

- [ ] Mostly SUCCESS entries
- [ ] Few or no ERROR entries
- [ ] Errors are expected (e.g., "Project not found" if deleted)

---

## Production Rollout

### Phase 1: Preparation
- [ ] All tests above pass
- [ ] Team notified
- [ ] Monitoring set up
- [ ] Logs are being collected

### Phase 2: Enable for 1 Project
- [ ] Pick lowest-risk project (smallest dataset)
- [ ] Run batch cycle once
- [ ] Monitor for 24 hours
- [ ] Verify data quality
- [ ] Check for duplicates or data loss

### Phase 3: Enable for 10% of Projects
- [ ] Select 10% of total projects (by count)
- [ ] Run batch cycles for 3 days
- [ ] Compare metrics with old system:
  - [ ] Data count matches (or exceeds)
  - [ ] source_page values present
  - [ ] No unexplained data gaps
  - [ ] Performance comparable

### Phase 4: Enable for 100% of Projects
- [ ] Move all remaining projects
- [ ] Run batch cycles for 1 week
- [ ] Verify all projects complete normally
- [ ] Check for any new issues
- [ ] Confirm old continuation projects are no longer needed

### Phase 5: Cleanup (Optional but Recommended)
- [ ] Delete old continuation projects from ParseHub
- [ ] Archive old code (keep for reference)
- [ ] Update runbooks/documentation
- [ ] Train team on new system

---

## Monitoring & Alerts

### Set Up Monitoring For:

**Success Metrics:**
- [ ] Batch completion rate > 95%
- [ ] Average batch time < 10 minutes
- [ ] Items stored per batch > expected
- [ ] Checkpoint accuracy = 100%

**Error Metrics:**
- [ ] Failed runs alert if > 1 per day
- [ ] Stuck batches alert if > 30 min without completion
- [ ] Database errors alert immediately

**Recommended:**
```python
# Add to your monitoring service
def monitor_batch_health():
    conn = db.connect()
    cursor = db.cursor()
    
    # Check failed runs
    cursor.execute('''
        SELECT count(*) FROM runs 
        WHERE is_batch_run = TRUE 
        AND status = 'failed' 
        AND created_at > CURRENT_TIMESTAMP - INTERVAL 1 DAY
    ''')
    
    failed_count = cursor.fetchone()[0]
    if failed_count > 1:
        ALERT(f"More than 1 failed batch run today: {failed_count}")
    
    # Check checkpoint staleness
    cursor.execute('''
        SELECT project_id, max(checkpoint_timestamp) 
        FROM batch_checkpoints 
        GROUP BY project_id
    ''')
    
    # etc...
```

---

## Rollback Plan

If issues occur:

### Quick Rollback
1. Stop new system (comment out or disable from scheduler)
2. Revert old incrementalscaping_manager to active version
3. No data migration needed (old data still exists)
4. Resume old system from where it left off

### Full Rollback
```bash
# Restore database from pre-migration snapshot
# (Snowflake can do this in 1 minute)

# Revert code changes
git revert <commit-hash>

# Resume using old code
```

- [ ] Rollback procedure documented
- [ ] Team trained on rollback
- [ ] Database backups accessible

---

## Post-Deployment

### Week 1 Checklist
- [ ] Daily monitoring of batch runs
- [ ] Check data quality (no unexplained gaps)
- [ ] Verify projects complete on schedule
- [ ] Monitor logs for warnings/errors
- [ ] Check checkpoint accuracy
- [ ] Team training completed

### Week 2+ Checklist
- [ ] All projects running on new system
- [ ] Old continuation projects no longer being created
- [ ] Data quality stable
- [ ] Performance meets expectations
- [ ] Document lessons learned
- [ ] Plan for optimization

---

## Troubleshooting During Deployment

### Issue: "PARSEHUB_API_KEY not configured"
**Solution:**
- [ ] Check `.env` file exists
- [ ] Check PARSEHUB_API_KEY line exists
- [ ] Verify no spaces around `=`
- [ ] Restart Python process (env is loaded at startup)

### Issue: Snowflake connection refused
**Solution:**
- [ ] Verify Snowflake account/user/password in `.env`
- [ ] Test connection in Snowflake SQL editor directly
- [ ] Check firewall/network access to Snowflake

### Issue: Migration fails with "column already exists"
**Solution:**
- [ ] This is OK - means column was already added
- [ ] Check that no ERROR entries (as opposed to ⊘)
- [ ] Verify column actually exists after migration

### Issue: Batch times out (>30 min)
**Solution:**
- [ ] Check if website is responsive (test in browser)
- [ ] Check ParseHub project manually in UI
- [ ] Try reducing CHUNK_SIZE to 5 in orchestrator.py
- [ ] Check ParseHub API status page

### Issue: No items stored but run completed
**Solution:**
- [ ] Normal if website end reached (empty pages)
- [ ] Check if URL pattern is correct for target website
- [ ] Verify ParseHub project template works manually
- [ ] Check ParseHub project preview in UI

---

## Sign-Off

When ready to declare deployment complete:

- [ ] All tests passing
- [ ] Monitoring active
- [ ] Team trained
- [ ] Documentation updated
- [ ] Rollback procedure verified
- [ ] Business stakeholders notified

**Deployment Date:** ______________

**Completed By:** ______________

**Verified By:** ______________

---

## Additional Resources

- **Quick Start**: `BATCH_PAGINATION_SUMMARY.md`
- **Full Guide**: `BATCH_PAGINATION_IMPLEMENTATION.md`
- **API Docs**: Docstrings in `chunk_pagination_orchestrator.py`
- **Tests**: `test_batch_pagination.py`
- **Migration**: `backend/migrations/batch_pagination_migration.py`

---

## Questions?

Refer to:
1. Implementation guide for architecture questions
2. Code comments for technical details
3. Logs (with `[BATCH_CYCLE]` prefix) for runtime details
4. Rollback plan if you need to revert
