# Deployment Checklist & Quick Start

**Metadata-Driven Resume Scraping System**
**Last Updated:** March 26, 2026

---

## Pre-Deployment Verification

### ✅ Code Review Checklist

- [ ] **Backend Services**
  - [ ] `backend/src/services/metadata_driven_resume_scraper.py` exists (650+ lines)
  - [ ] `backend/src/api/resume_routes.py` exists (300+ lines)
  - [ ] `backend/src/api/api_server.py` has blueprint registered
  - [ ] All imports compile without errors

- [ ] **Frontend Components**
  - [ ] `frontend/types/scraping.ts` updated with ProjectMetadata, ScrapingCheckpoint types
  - [ ] `frontend/lib/scrapingApi.ts` has startOrResumeScraping() function
  - [ ] `frontend/lib/useBatchMonitoring.ts` has new interface (UseMonitoringReturn)
  - [ ] Components compile without TypeScript errors

- [ ] **Database Migration**
  - [ ] `backend/migrations/migrate_source_page_tracking.py` exists
  - [ ] Migration script is idempotent (safe for re-runs)
  - [ ] source_page column strategy correct (INTEGER NOT NULL DEFAULT 0)

- [ ] **Tests**
  - [ ] `test_metadata_driven_scraper.py` has 30+ test cases
  - [ ] All tests mock external dependencies correctly
  - [ ] Error scenarios covered

- [ ] **Documentation**
  - [ ] METADATA_DRIVEN_REFACTORING_SUMMARY.md complete
  - [ ] MANUAL_TESTING_GUIDE.md complete
  - [ ] API contract examples provided

### Configuration Verification

```bash
# 1. Environment Variables (.env file)
cd backend
grep -E "PARSEHUB_API_KEY|SNOWFLAKE_" .env

# Should output (example):
# PARSEHUB_API_KEY=xxxxxxxxxx
# SNOWFLAKE_ACCOUNT=ab12345.us-east-1
# SNOWFLAKE_USER=parsehubot
# SNOWFLAKE_PASSWORD=SecurePassword123
# SNOWFLAKE_DATABASE=PARSEHUB_DB
```

- [ ] PARSEHUB_API_KEY present
- [ ] SNOWFLAKE_ACCOUNT valid format (account.region)
- [ ] SNOWFLAKE_DATABASE exists in Snowflake account

### Optional Email Configuration

```bash
# Email notifications (OPTIONAL but RECOMMENDED)
grep -E "SMTP_" backend/.env

# Should output (example):
# SMTP_HOST=mail.company.com
# SMTP_PORT=587
# SMTP_USER=notifier@company.com
# SMTP_PASSWORD=AppPassword123!
# SMTP_FROM=ParseHub Scraper <notifier@company.com>
# ERROR_NOTIFICATION_EMAIL=admin@company.com
```

- [ ] SMTP settings configured (or intentionally left blank for graceful degradation)
- [ ] ERROR_NOTIFICATION_EMAIL is valid

---

## Deployment Steps (Dev First!)

### Phase 1: Database Setup (Dev Environment)

**IMPORTANT:** Do this on dev database FIRST before production!

```bash
# Step 1: Navigate to backend folder
cd /path/to/Parsehub-Snowflake/backend

# Step 2: Run migration with virtual environment
.\venv312\Scripts\python -m migrations.migrate_source_page_tracking
```

**Expected Output:**
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
  ✓ Index on (source_page) created
[Step 4] Checking data integrity...
  Total records: X
  ✓ Data integrity verified
[Step 5] Testing checkpoint query...
  ✓ Checkpoint query executes successfully
[Summary]
  ✓ scraped_records table ready for metadata-driven scraping
================================================================================
MIGRATION COMPLETED SUCCESSFULLY
================================================================================
```

- [ ] Migration completes with no errors
- [ ] Check Snowflake UI to confirm column exists:
  ```sql
  DESCRIBE TABLE scraped_records;
  -- Find source_page in column list
  ```

### Phase 2: Backend Setup (Dev Environment)

```bash
# Step 1: Install test dependencies
cd backend
python -m pip install pytest pytest-cov

# Step 2: Run automated tests
python -m pytest test_metadata_driven_scraper.py -v --tb=short

# Expected:
# ====================== 25+ passed in X.XXs ======================
```

- [ ] All tests pass (green checkmarks)
- [ ] No pytest errors
- [ ] Coverage > 80% for core methods

**If tests fail:**
```bash
# Run with verbose output to debug
python -m pytest test_metadata_driven_scraper.py -vv --tb=long

# Check specific test class
python -m pytest test_metadata_driven_scraper.py::TestMetadataDrivenScraperCheckpoint -vv
```

### Phase 3: Backend Server Startup (Dev Environment)

```bash
cd backend

# Option A: Direct Python
python -m src.api.api_server

# Option B: Using Gunicorn (for production-like testing)
pip install gunicorn
gunicorn --bind 0.0.0.0:5000 src.api.api_server:app

# Expected output:
# * Running on http://127.0.0.1:5000
# [INFO] Registered blueprints: batch, resume
```

- [ ] Server starts without errors
- [ ] No import errors logged
- [ ] Both batch and resume blueprints registered

### Phase 4: Frontend Setup (Dev Environment)

```bash
cd frontend

# Step 1: Verify TypeScript compiles
npm run build

# Expected:
# > next build
# ▲ Next.js 13.X.X
# ✓ Linting and type checking
# ✓ Collecting page data
# ✓ Generating static pages (X/X)
# Route (pages) Size
```

- [ ] TypeScript compilation succeeds
- [ ] No type errors
- [ ] No missing imports

**If TypeScript errors occur:**
```bash
# Check for specific types
grep -r "UseBatchMonitoringReturn" frontend/components/

# If errors, double-check types/scraping.ts and lib/useBatchMonitoring.ts imports
```

### Phase 5: Manual Testing (Dev Environment)

Follow **MANUAL_TESTING_GUIDE.md** completely:

- [ ] Test Scenario 1: Fresh project start ✅
- [ ] Test Scenario 2: Resume from checkpoint ✅
- [ ] Test Scenario 3: Project completion ✅
- [ ] Test Scenario 4: Error handling ✅
- [ ] Test Scenario 5: Frontend integration ✅

---

## Production Submission Checklist

Before deploying to production, ensure:

### Backend Validation

```bash
# 1. Static analysis
cd backend
pylint src/services/metadata_driven_resume_scraper.py --max-line-length=100
pylint src/api/resume_routes.py --max-line-length=100

# 2. Type checking (if using mypy)
mypy src/services/metadata_driven_resume_scraper.py --ignore-missing-imports
mypy src/api/resume_routes.py --ignore-missing-imports

# 3. Security check
bandit -r src/services/metadata_driven_resume_scraper.py
```

- [ ] No high-severity linting issues
- [ ] Type checking passes
- [ ] No security vulnerabilities

### Frontend Validation

```bash
cd frontend

# 1. Build check
npm run build
# Should show ✓ Linting and type checking

# 2. ESLint check
npm run lint

# 3. TypeScript strict mode
npm run tsc --noEmit
```

- [ ] Build succeeds
- [ ] No ESLint errors
- [ ] TypeScript strict checks pass

### Data Backup Before Production

```bash
# CRITICAL: Backup existing data before migration

# Snowflake backup
CREATE TABLE scraped_records_BACKUP_2026_03_26 AS 
SELECT * FROM scraped_records;

SELECT COUNT(*) as backup_count FROM scraped_records_BACKUP_2026_03_26;
# Should match pre-migration count

# Archive old code for rollback
git tag -a v1.0-old-batch-system -m "Backup before metadata-driven migration"
git push origin v1.0-old-batch-system
```

- [ ] Backup verified and counts match
- [ ] Git tag created for rollback capability
- [ ] Backup location documented

### Database Migration (Production)

```bash
# Production migration (on production database)
cd backend
.\venv312\Scripts\python -m migrations.migrate_source_page_tracking

# Verify in Snowflake:
SELECT INDEX_NAME, INDEX_KEYS FROM INFORMATION_SCHEMA.INDEXES 
WHERE TABLE_NAME = 'scraped_records';
# Should list new indexes

SELECT * FROM scraped_records LIMIT 1;
# Should have source_page column
```

- [ ] Migration succeeds on production DB
- [ ] Indexes created
- [ ] No data loss (verify row counts match backup)

### Production Deployment

```bash
# 1. Deploy code
git pull origin main
git checkout v2.0-metadata-driven

# 2. Install dependencies
pip install -r requirements.txt

# 3. Restart services
# (Use your deployment method: Docker, systemd, k8s, etc.)
systemctl restart parsehub-backend
systemctl restart parsehub-frontend

# 4. Health check
curl http://api.example.com/api/projects/health
# Expected: {"status": "ok"}

# 5. Verify blueprints
curl -H "Authorization: Bearer $API_KEY" http://api.example.com/api/projects/test/resume/metadata
```

- [ ] New code deployed successfully
- [ ] API responding to requests
- [ ] No 500 errors in logs
- [ ] Resume endpoints accessible

### Post-Deployment Monitoring

```bash
# 1. Monitor logs for first 24 hours
tail -f backend/logs/app.log | grep -i "error\|failed"

# 2. Check success rate
curl http://api.example.com/api/projects/health/stats

# 3. Monitor email notifications (if configured)
tail -f backend/logs/notifications.log

# 4. Database query performance (verify indexes working)
SELECT * FROM scraped_records 
WHERE project_id = 123 
ORDER BY source_page DESC 
LIMIT 10;
# Should be < 100ms
```

- [ ] No error spikes in first hour
- [ ] Checkpoint queries executing fast (< 100ms)
- [ ] Email notifications sending correctly
- [ ] No database locks or deadlocks

---

## Quick Start Commands

### One-Time Initial Setup

```bash
# Full setup from scratch
cd /path/to/Parsehub-Snowflake/backend

# 1. Database
.\venv312\Scripts\python -m migrations.migrate_source_page_tracking

# 2. Backend tests
python -m pytest test_metadata_driven_scraper.py -v

# 3. Backend server  
python -m src.api.api_server &

# 4. Frontend (in new terminal)
cd frontend && npm run dev &
cd ..

# 5. Verify
curl http://localhost:5000/api/projects/health
# Should show: {"status": "ok"}
```

### Daily Start (After Initial Setup)

```bash
# Terminal 1: Backend
cd backend && python -m src.api.api_server

# Terminal 2: Frontend
cd frontend && npm run dev

# Terminal 3: Monitor logs
tail -f backend/logs/app.log
```

### Test New Feature

```bash
# Before deploying changes
cd backend
python -m pytest test_metadata_driven_scraper.py -v -k "test_checkpoint"

# Run specific test
python -m pytest test_metadata_driven_scraper.py::TestMetadataDrivenScraperCheckpoint::test_get_checkpoint_with_records -vv
```

---

## Rollback Plan

If issues occur in production:

### Quick Rollback (Code Only)

```bash
# Revert to previous version
git checkout v1.0-old-batch-system
pip install -r requirements.txt

# Restart services
systemctl restart parsehub-backend
systemctl restart parsehub-frontend

# Database schema remains (non-destructive, source_page field persists)
```

### Full Rollback (Code + Database)

```bash
# Revert database to backup
TRUNCATE TABLE scraped_records;
INSERT INTO scraped_records 
SELECT * FROM scraped_records_BACKUP_2026_03_26;

VERIFY: SELECT COUNT(*) FROM scraped_records;
# Should match pre-migration count

# Revert code
git checkout v1.0-old-batch-system
systemctl restart parsehub-backend
```

---

## Support Contacts

- **Backend Issues:** Check logs in `backend/logs/app.log`
- **Database Issues:** Snowflake query history in Snowflake UI
- **API Issues:** Enable DEBUG logging in .env
- **Email Notifications:** Check SMTP configuration and logs/notifications.log

---

## Documentation References

| Document | Purpose |
|----------|---------|
| METADATA_DRIVEN_REFACTORING_SUMMARY.md | Architecture & implementation details |
| MANUAL_TESTING_GUIDE.md | Step-by-step test scenarios |
| README.md | Project overview |
| BACKEND.md | Backend architecture |

---

## Version Info

**Metadata-Driven Resume Scraping System v2.0**
- Release Date: March 26, 2026
- Previous Version: v1.0 (old batch system)
- Next Version: v2.1 (UI improvements)

**Key Changes from v1.0 → v2.0:**
- ✅ Removed: Incremental scraping (continuation projects)
- ✅ Removed: Hard-coded 10-page batch logic
- ✅ Added: MAX(source_page) checkpoint system
- ✅ Added: Dynamic pagination detection
- ✅ Added: Email notifications for failures
- ✅ Added: Comprehensive test suite

---

**Sign-Off: Ready for Deployment**

```
Deployment approved by: _________________
Date: _________________
Environment: [ ] Dev [ ] Staging [ ] Production
```
