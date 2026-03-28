# Manual Testing & Verification Guide

**Metadata-Driven Resume Scraping System**
**Last Updated:** March 26, 2026

---

## Pre-Testing Setup

### 1. Environment & Dependencies

```bash
# Backend
cd backend
python -m pip install pytest pytest-cov
python -m pip install requests python-dotenv

# Ensure .env has:
PARSEHUB_API_KEY=your_key_here
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=your_db

# Optional for email notifications:
SMTP_HOST=mail.example.com
SMTP_PORT=587
SMTP_USER=notifier@example.com
SMTP_PASSWORD=password
SMTP_FROM=ParseHub <notifier@example.com>
ERROR_NOTIFICATION_EMAIL=admin@example.com
```

### 2. Database Migration

```bash
# Run migration to add source_page tracking
cd /path/to/Parsehub-Snowflake
python -c "from backend.migrations.migrate_source_page_tracking import run_migration; run_migration()"
```

Expected output:
```
================================================================================
MIGRATION: Add source_page tracking for metadata-driven resume scraping
================================================================================

[Step 1] Checking if scraped_records table exists...
  ✓ scraped_records table exists

[Step 2] Adding source_page column if missing...
  ✓ source_page column verified/added

[Step 3] Creating indexes...
  ✓ Index on (project_id, source_page) created
  ✓ Index on source_page created

[Step 4] Checking data integrity...
  Total records: 0
  Records with source_page: 0
  Records missing source_page: 0
  ✓ Table is empty (migration ready for new data)

[Step 5] Testing checkpoint query...
  ✓ Checkpoint query executes successfully

[Summary]
  ✓ scraped_records table has source_page column
  ✓ Indexes created for efficient checkpoint queries
  ✓ Data integrity verified

================================================================================
MIGRATION COMPLETED SUCCESSFULLY
================================================================================
```

### 3. Start Backend Server

```bash
cd backend
# Run Flask API server
python -m src.api.api_server

# Expected output:
# * Running on http://127.0.0.1:5000
# [INFO] Registered blueprints: batch, resume
```

### 4. Start Frontend Development Server

```bash
cd frontend
npm run dev

# Expected output:
# - ready started server on [...], url: http://localhost:3000
```

---

## Test Scenario 1: Fresh Project Start (No Prior Scraping)

### Test Data Setup

Before starting, prepare a test metadata record:

```sql
-- In Snowflake, ensure metadata table has test project
INSERT INTO metadata (
  personal_project_id, project_name, base_url, total_pages, 
  total_products, current_page_scraped
)
VALUES (
  'test_project_001',
  'Test E-commerce Site',
  'https://testsite.com/products?page=1',
  5,
  100,
  0
);

SELECT id FROM metadata WHERE personal_project_id = 'test_project_001';
-- Note the ID returned (we'll call it PROJECT_ID=123)
```

Ensure you have a ParseHub project set up with token (e.g., `PROJECT_TOKEN=tXXX...`).

### Manual Test Steps

#### Step 1.1: Start Fresh Scraping

```bash
# Call the new metadata-driven endpoint
curl -X POST http://localhost:5000/api/projects/resume/start \
  -H "Content-Type: application/json" \
  -d '{
    "project_token": "tXXX...",
    "project_id": 123
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "project_complete": false,
  "run_token": "run_abc123...",
  "highest_successful_page": 0,
  "next_start_page": 1,
  "total_pages": 5,
  "total_persisted_records": 0,
  "checkpoint": {
    "highest_successful_page": 0,
    "next_start_page": 1,
    "total_persisted_records": 0,
    "checkpoint_timestamp": "2024-03-26T14:15:30.123456"
  },
  "message": "Run started for page 1"
}
```

**Verification Checklist:**
- [ ] HTTP 201 (Created) status
- [ ] success = true
- [ ] project_complete = false
- [ ] run_token not empty (copy for next step)
- [ ] highest_successful_page = 0 (first time)
- [ ] next_start_page = 1
- [ ] total_pages matches metadata (5)

**Logs to Check:**
```bash
# In backend logs, should see:
[BEGIN] Resume or start scraping for project 123
[STEP 1] Reading metadata...
[METADATA] Test E-commerce Site: 5 pages, 100 products
[STEP 2] Reading checkpoint...
[CHECKPOINT] Highest successful page: 0
[STEP 3] Generating next page URL...
[URL] Generated URL for page 1
[STEP 4] Triggering ParseHub run...
[RUN] Successfully triggered: run_abc123...
```

#### Step 1.2: Wait for ParseHub Run to Complete

Wait until the ParseHub run completes (typically 2-5 minutes depending on site).

Check ParseHub dashboard:
- [ ] Run shows status "Completed"
- [ ] Data items scraped (should be > 0)

#### Step 1.3: Complete Run & Persist Data

```bash
# Call complete-run endpoint
curl -X POST http://localhost:5000/api/projects/resume/complete-run \
  -H "Content-Type: application/json" \
  -d '{
    "run_token": "run_abc123...",
    "project_id": 123,
    "project_token": "tXXX...",
    "starting_page_number": 1
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "run_completed": true,
  "records_persisted": 25,
  "highest_successful_page": 1,
  "project_complete": false,
  "next_action": "continue",
  "message": "Page 1 completed, ready to scrape page 2"
}
```

**Verification Checklist:**
- [ ] HTTP 200 status
- [ ] success = true
- [ ] run_completed = true
- [ ] records_persisted > 0 (should match ParseHub data count)
- [ ] highest_successful_page = 1
- [ ] project_complete = false (not done yet)
- [ ] next_action = "continue"

**Database Verification:**
```sql
-- Check if records were persisted with source_page
SELECT COUNT(*) as total, 
       MAX(source_page) as highest_page,
       MIN(source_page) as lowest_page
FROM scraped_records
WHERE project_id = 123;

-- Expected output: total=25, highest_page=1, lowest_page=1
```

---

## Test Scenario 2: Resume from Checkpoint

### Step 2.1: Get Current Progress

```bash
curl http://localhost:5000/api/projects/tXXX.../resume/metadata
```

**Expected Response:**
```json
{
  "success": true,
  "project_id": 123,
  "project_name": "Test E-commerce Site",
  "base_url": "https://testsite.com/products?page=1",
  "total_pages": 5,
  "total_products": 100,
  "current_page_scraped": 1,
  "checkpoint": {
    "highest_successful_page": 1,
    "next_start_page": 2,
    "total_persisted_records": 25
  },
  "is_complete": false,
  "progress_percentage": 20
}
```

**Verification Checklist:**
- [ ] progress_percentage = 20 (1 of 5 pages)
- [ ] next_start_page = 2 (correct calculation)
- [ ] highest_successful_page = 1 (from MAX query)

### Step 2.2: Resume Scraping from Page 2

```bash
curl -X POST http://localhost:5000/api/projects/resume/start \
  -H "Content-Type: application/json" \
  -d '{
    "project_token": "tXXX...",
    "project_id": 123
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "project_complete": false,
  "run_token": "run_def456...",
  "highest_successful_page": 1,
  "next_start_page": 2,
  "total_pages": 5,
  "message": "Run started for page 2"
}
```

**Verification:**
- [ ] next_start_page = 2 (correctly resumed from checkpoint + 1)
- [ ] Different run_token than first run

### Step 2.3: Complete Second Run

```bash
# After ParseHub finishes run_def456...

curl -X POST http://localhost:5000/api/projects/resume/complete-run \
  -H "Content-Type: application/json" \
  -d '{
    "run_token": "run_def456...",
    "project_id": 123,
    "project_token": "tXXX...",
    "starting_page_number": 2
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "records_persisted": 24,
  "highest_successful_page": 2,
  "project_complete": false,
  "next_action": "continue"
}
```

**Database Verification:**
```sql
SELECT COUNT(*) as total, 
       MAX(source_page) as highest_page
FROM scraped_records
WHERE project_id = 123;

-- Expected: total=49 (25+24), highest_page=2
```

---

## Test Scenario 3: Project Completion

### Step 3: Continue Until Completion

Repeat Test Scenario 2 for pages 3, 4, and 5.

After page 5 is persisted:

```bash
curl http://localhost:5000/api/projects/tXXX.../resume/metadata
```

**Expected Response (when complete):**
```json
{
  "success": true,
  "highest_successful_page": 5,
  "total_pages": 5,
  "current_page_scraped": 5,
  "is_complete": true,
  "progress_percentage": 100,
  "checkpoint": {
    "highest_successful_page": 5,
    "next_start_page": 6,
    "total_persisted_records": 120
  }
}
```

### Step 3.1: Verify Auto-Complete Flag

On next resume call:

```bash
curl -X POST http://localhost:5000/api/projects/resume/start \
  -H "Content-Type: application/json" \
  -d '{
    "project_token": "tXXX...",
    "project_id": 123
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "project_complete": true,
  "message": "Project scraping is complete",
  "reason": "Primary: highest_page (5) >= total_pages (5)",
  "highest_successful_page": 5,
  "total_pages": 5
}
```

**Verification:**
- [ ] No run_token returned
- [ ] project_complete = true
- [ ] No more runs should be triggered

---

## Test Scenario 4: Error Handling

### Test 4.1: Invalid ParseHub Token

```bash
curl -X POST http://localhost:5000/api/projects/resume/start \
  -H "Content-Type: application/json" \
  -d '{
    "project_token": "invalid_token",
    "project_id": 123
  }'
```

**Expected:**
- [ ] error response with helpful message
- [ ] Email notification sent (if SMTP configured)

### Test 4.2: Missing Metadata

```bash
curl -X POST http://localhost:5000/api/projects/resume/start \
  -H "Content-Type: application/json" \
  -d '{
    "project_token": "tXXX...",
    "project_id": 99999
  }'
```

**Expected:**
- [ ] success = false
- [ ] error = "No metadata found for project"

### Test 4.3: Database Persistence Failure

*(Simulate by causing DB connection error)*

**Expected:**
- [ ] In complete-run response, error handled gracefully
- [ ] Checkpoint NOT updated if persistence failed
- [ ] Email notification sent for storage_failed

---

## Test Scenario 5: Frontend Integration

### Test 5.1: Start Scraping from UI

1. Visit http://localhost:3000
2. Find a project
3. Click "Resume Scraping" button
4. Observe:
   - [ ] Loading spinner appears
   - [ ] Run token is displayed
   - [ ] Progress bar shows 0/total_pages
   - [ ] Status shows "Running"

### Test 5.2: Monitor Progress

While ParseHub run executes:
- [ ] Progress updates every 3 seconds
- [ ] Page indicator updates (e.g., "1 / 50 pages")
- [ ] Product count updates
- [ ] Total persisted records displayed

### Test 5.3: View Checkpoint

Click "View Details":
- [ ] Shows highest_successful_page
- [ ] Shows total_persisted_records
- [ ] Shows progress percentage
- [ ] Shows next_start_page

---

## Backwards Compatibility Tests

### Test Old Batch Routes Still Work

```bash
# Old batch/start endpoint
curl -X POST http://localhost:5000/api/projects/batch/start \
  -H "Content-Type: application/json" \
  -d '{
    "project_token": "tXXX...",
    "project_id": 123
  }'
```

**Expected:**
- [ ] Works and forwards to resume system  
- [ ] Returns similar response structure

---

## Performance & Stress Tests

### Test 5: Large Data Persistence

Create test data with 1000+ records:

```python
from backend.src.services.metadata_driven_resume_scraper import MetadataDrivenResumeScraper
scraper = MetadataDrivenResumeScraper()

test_data = [{'item': i} for i in range(1000)]
success, inserted, highest = scraper.persist_results(
    project_id=123,
    run_token='test_run',
    data=test_data,
    source_page=1
)

assert inserted == 1000
assert success is True
```

**Expected:**
- [ ] All 1000 records inserted successfully
- [ ] Completes in < 5 seconds
- [ ] No memory spikes

---

## Automated Test Execution

### Run Backend Unit Tests

```bash
cd /path/to/Parsehub-Snowflake/backend
python -m pytest test_metadata_driven_scraper.py -v
```

**Expected Output:**
```
test_metadata_driven_scraper.py::TestMetadataDrivenScraperCheckpoint::test_get_checkpoint_no_records PASSED
test_metadata_driven_scraper.py::TestMetadataDrivenScraperCheckpoint::test_get_checkpoint_with_records PASSED
test_metadata_driven_scraper.py::TestMetadataDrivenScraperURLGeneration::test_generate_url_query_page_param PASSED
... (many more tests)
======================== 25 passed in 2.34s ========================
```

All tests should pass with ✅ status.

---

## Troubleshooting

### Issue: "No module named 'src'"

**Solution:**
```bash
cd backend
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python test_metadata_driven_scraper.py
```

### Issue: Database connection error

**Check:**
```bash
# Verify .env has correct Snowflake credentials
cat backend/.env | grep SNOWFLAKE

# Test connection
python -c "from src.models.database import ParseHubDatabase; db = ParseHubDatabase(); print('OK')"
```

### Issue: Email notifications not working

**Check:**
```bash
# Verify SMTP settings in .env
SMTP_HOST=mail.example.com
SMTP_PORT=587
SMTP_USER=user@example.com
SMTP_PASSWORD=***

# Test email service directly
python -c "from src.services.notification_service import get_notification_service; n = get_notification_service(); print('Enabled' if n.is_enabled() else 'Disabled')"
```

### Issue: ParseHub runs not triggering

**Check:**
```bash
# Verify API key
echo $PARSEHUB_API_KEY

# Test API connectivity
curl https://www.parsehub.com/api/v2/projects \
  -H "Authorization: Bearer YOUR_API_KEY"
```

---

## Sign-Off Checklist

After all tests pass, verify:

- [ ] Test Scenario 1 (Fresh start): ✅ Passed
- [ ] Test Scenario 2 (Resume): ✅ Passed
- [ ] Test Scenario 3 (Completion): ✅ Passed
- [ ] Test Scenario 4 (Error handling): ✅ Passed
- [ ] Test Scenario 5 (Frontend): ✅ Passed
- [ ] Backwards compatibility: ✅ Passed
- [ ] Performance tests: ✅ Passed
- [ ] Automated unit tests: ✅ All passed
- [ ] No error emails sent for normal operations
- [ ] Error emails sent for failures
- [ ] Logs are clean without warnings

**Project Status:** ✅ Ready for Production

---

## Support & Further Testing

For additional testing:
1. Real ParseHub account with live websites
2. Load testing with 100+ simultaneous projects
3. Long-running scrapes (24+ hours)
4. Network failure simulation (firewall blocking)
5. Database failover testing

See METADATA_DRIVEN_REFACTORING_SUMMARY.md for architecture details.
