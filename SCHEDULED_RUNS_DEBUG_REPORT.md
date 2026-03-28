# Scheduled Runs Debugging Report
**Investigation Date: March 25, 2026**

---

## Executive Summary
Scheduled runs aren't displaying in the frontend and projects aren't executing on schedule. The root causes are:

1. **CRITICAL: Table Name Case Mismatch** - Queries use `SCHEDULED_RUNS` but table is `scheduled_runs`
2. **Silent Database Failure** - DB errors aren't propagated to the API response
3. **No Explicit Error Handling** - Scheduler execution failures aren't logged with context
4. **Potential Database Connection Issues** - `_load_from_database()` may be failing silently during initialization

---

## Issue #1: Database Table Name Case Mismatch ⚠️ CRITICAL

### Problem
The database table is created as `scheduled_runs` (lowercase), but all queries attempt to access `SCHEDULED_RUNS` (uppercase).

### Code Locations

**Table Creation** - [backend/src/models/database.py](backend/src/models/database.py#L577)
```python
# Line 577 - Creates table as lowercase
cursor.execute('''
    CREATE TABLE IF NOT EXISTS scheduled_runs (
        job_id TEXT PRIMARY KEY,
        project_token TEXT NOT NULL,
        schedule_type TEXT NOT NULL,
        ...
    )
''')
```

**Query Locations Using UPPERCASE - ALL FAIL**:
- [scheduled_run_service.py:47](backend/src/services/scheduled_run_service.py#L47)
  ```python
  FROM SCHEDULED_RUNS WHERE active = TRUE
  ```
- [scheduled_run_service.py:304](backend/src/services/scheduled_run_service.py#L304)
  ```python
  SELECT ... FROM SCHEDULED_RUNS WHERE active = TRUE
  ```
- [scheduled_run_service.py:278](backend/src/services/scheduled_run_service.py#L278)
  ```python
  UPDATE SCHEDULED_RUNS SET active = FALSE
  ```
- [scheduled_run_service.py:342](backend/src/services/scheduled_run_service.py#L342)
  ```python
  INSERT INTO SCHEDULED_RUNS (...)
  ```

### Why This Breaks Everything

1. **On Startup**: `_load_from_database()` fails silently (line 36 catches all exceptions)
   - Server logs: `[WARN] No database available, skipping load from DB` *(misleading - DB exists, table name is wrong)*
   - In-memory `scheduled_runs` dict remains empty

2. **New Schedule Creation**: `_save_to_database()` fails silently (line 362)
   - Frontend shows success, but data never reaches database
   - Schedule isn't persisted across server restarts

3. **GET /api/scheduled-runs**: Returns only in-memory data (which is empty)
   - Frontend shows "No scheduled runs"
   - Even though they might be in the database

### Impact
✗ Scheduled runs never load from database on startup
✗ New scheduled runs aren't saved to database  
✗ Frontend displays empty list
✗ Jobs never execute

---

## Issue #2: Silent Database Failure in `get_scheduled_runs()` 🔴 MAJOR

### Problem
Exception handling swallows database errors, preventing frontend from detecting the problem.

### Code Location - [scheduled_run_service.py:297-333](backend/src/services/scheduled_run_service.py#L297)

```python
def get_scheduled_runs(self) -> list:
    result = []
    if self.db:
        try:
            # Database query
            cursor.execute(query)
            db_runs = cursor.fetchall()
        except Exception as e:
            # LINE 320: Logs warning but continues with empty results
            logger.warning(f"[WARN] Could not load from database in get_scheduled_runs: {e}")
    
    # Returns empty list if DB fails
    for job_id, run_data in self.scheduled_runs.items():
        result.append(...)
    return result
```

### Why This Is a Problem
- Frontend calls `GET /api/scheduled-runs` → receives `200 OK` with `scheduled_runs: []`
- No error indication
- User thinks "no schedules exist" when database query actually failed
- Database errors are logged but not visible in API response

### Impact
✗ No way to detect database problems from frontend
✗ Misleading success response with empty data
✗ Debugging impossible without checking server logs

---

## Issue #3: API Endpoint Doesn't Differentiate Between "No Data" and "Error" 🟡 MEDIUM

### Code Location - [api_server.py:1734-1747](backend/src/api/api_server.py#L1734)

```python
@app.route('/api/scheduled-runs', methods=['GET'])
def get_scheduled_runs():
    """Get all scheduled project runs"""
    try:
        scheduler = get_scheduled_run_service()
        runs = scheduler.get_scheduled_runs()
        
        logger.info(f'[API] Retrieved {len(runs)} scheduled runs')
        return jsonify({
            'success': True,
            'scheduled_runs': runs,
            'count': len(runs)
        }), 200
    except Exception as e:
        logger.error(f'[API] Error getting scheduled runs: {e}')
        return jsonify({'error': str(e), 'success': False}), 500
```

### Problems
1. Generic exception catch - doesn't distinguish between:
   - Database connection timeout
   - Query syntax error
   - Table doesn't exist
   - No data exists (intentional empty list)

2. No diagnostic information in response:
   - Database connection status
   - Scheduler running status
   - Number of jobs in scheduler vs. database

### Impact
✗ Can't determine actual cause of empty list
✗ Frontend shows generic error message
✗ Must check server logs to debug

---

## Issue #4: `_load_from_database()` Silently Fails During Initialization 🔴 MAJOR

### Code Location - [scheduled_run_service.py:33-120](backend/src/services/scheduled_run_service.py#L33)

```python
def _load_from_database(self):
    """Load scheduled runs from database on startup"""
    if not self.db:
        logger.warning("[WARN] No database available, skipping load from DB")
        return

    try:
        # LINE 40-47: Large try block that silently catches ALL exceptions
        result = cursor.fetchall()  # This fails with table name error
        
        for row in result:
            # Process rows...
    except Exception as e:
        # LINE 116: Catches error but only logs it
        logger.error(f"[ERROR] Failed to load from database: {e}")
        try:
            self.db.disconnect()
        except:
            pass  # Even disconnect errors are silently ignored
```

### The Flow
1. API Server starts
2. `_initialize_services()` called → calls `_start_background_services()` → `start_scheduled_run_service()` → `set_database()` → `_load_from_database()`
3. Query fails (table name mismatch): `FROM SCHEDULED_RUNS` fails
4. Exception caught at line 116
5. Error logged but service continues
6. `self.scheduled_runs` remains empty `{}`
7. No indication to user that loading failed

### Root Cause Chain
```
Table created: scheduled_runs (lowercase)
         ↓
Query: FROM SCHEDULED_RUNS (uppercase)
         ↓
Database returns: "Table 'SCHEDULED_RUNS' not found" or similar
         ↓
Exception caught silently
         ↓
scheduled_runs dict remains empty
         ↓
Frontend sees empty list
         ↓
User sees "No scheduled runs"
```

### Impact
✗ Scheduled runs never persist across server restarts
✗ Even if jobs exist in DB, they're not loaded/rescheduled
✗ Zero indication that something failed

---

## Issue #5: Job Execution Failures Not Tracked 🔴 MAJOR

### Code Location - [scheduled_run_service.py:370-385](backend/src/services/scheduled_run_service.py#L370)

```python
def _run_project(self, project_token: str, pages: int = 1):
    """Execute scheduled project run"""
    try:
        logger.info(f"[EXECUTE] Running {project_token} ({pages} pages)")
        url = f'{self.base_url}/projects/{project_token}/run'
        data = {'api_key': self.api_key, 'pages': pages}
        response = requests.post(url, data=data, timeout=10)

        if response.status_code == 200:
            run_info = response.json()
            logger.info(f"[SUCCESS] ParseHub run started: {run_info.get('run_token')}")
            return run_info
        else:
            logger.error(f"[ERROR] ParseHub error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        logger.error(f"[ERROR] Execution failed: {e}")
        return None
```

### Problems
1. No database update on execution
   - Job executes but status isn't recorded
   - No "last_run" timestamp
   - Frontend can't show execution status

2. Failures are logged but not visible to frontend
   - API key might be invalid
   - ParseHub API might be down
   - Network timeout
   - No way to troubleshoot from UI

3. No retry logic
   - If job fails, it's abandoned
   - No notification to user

### Impact
✗ Jobs execute but no feedback
✗ Failures invisible to frontend
✗ No audit trail of executions
✗ No way to diagnose why jobs aren't running

---

## Issue #6: Frontend Not Handling Empty/Error Responses

### Code Location - [components/ScheduledRunsModal.tsx:27-48](frontend/components/ScheduledRunsModal.tsx#L27)

```typescript
const fetchScheduledRuns = async () => {
    setLoading(true);
    setError(null);
    try {
        const response = await apiClient.get('/api/scheduled-runs');
        if (response.status === 200 && response.data.scheduled_runs) {
            setScheduledRuns(response.data.scheduled_runs);
        }
    } catch (err) {
        console.error('Error fetching scheduled runs:', err);
        setError('Failed to fetch scheduled runs');
    } finally {
        setLoading(false);
    }
};
```

### Problems
1. Only checks `response.status === 200`
   - Doesn't verify `response.data.scheduled_runs` exists
   - If response is `{scheduled_runs: null}`, no error shown

2. Generic error message "Failed to fetch scheduled runs"
   - User doesn't know if it's network error, server error, or no data
   - No indication to check backend logs

3. Silent failure if response format unexpected
   - If backend returns different structure, list shows empty
   - No console error for data structure issues

### Impact
✗ Frontend doesn't distinguish between errors and empty list
✗ User sees blank modal with no indication of what's wrong
✗ No actionable error messages

---

## Verification: Debug Endpoint Shows Status

There IS a debug endpoint available: [/api/scheduler/debug](backend/src/api/api_server.py#L1770)

```python
@app.route('/api/scheduler/debug', methods=['GET'])
def debug_scheduler():
    """Debug endpoint to check scheduler status and diagnostics"""
    diagnostics = {
        'success': True,
        'scheduler_running': scheduler.scheduler.running,
        'system_timezone': str(local_tz),
        'current_time': datetime.now(local_tz).isoformat(),
        'scheduled_runs': scheduler.get_scheduled_runs(),
        'scheduled_runs_count': len(scheduler.scheduled_runs),
        'scheduler_jobs': [...]
    }
    return jsonify(diagnostics), 200
```

### What To Check
Call `GET http://your-api/api/scheduler/debug` to see:
- ✓ Is scheduler running? (`scheduler_running`)
- ✓ How many runs in memory? (`scheduled_runs_count`)
- ✓ What are the actual scheduled runs? (`scheduled_runs`)
- ✓ What jobs are scheduled? (`scheduler_jobs`)

---

## Root Cause Summary

### Why Scheduled Runs Aren't Displaying

1. **Query fails due to table name case mismatch** (`SCHEDULED_RUNS` vs `scheduled_runs`)
2. **Exception is caught silently** in `_load_from_database()` and `get_scheduled_runs()`
3. **In-memory dictionary stays empty** → no data shown to frontend
4. **API returns success with empty list** → frontend thinks "no schedules exist"

### Why Projects Aren't Executing

1. **Jobs never load from database** → jobs aren't rescheduled after server restart
2. **Scheduler might not have any jobs** if only in-memory data existed
3. **If jobs do execute, status isn't tracked** → user has no feedback
4. **Execution failures are silently logged** → user doesn't know why jobs didn't run

---

## Recommended Fixes (Priority Order)

### 🔴 CRITICAL - Fix Table Name Case Mismatch
Replace all `SCHEDULED_RUNS` with `scheduled_runs` in queries:
- Line 47, 278, 304, 342 of scheduled_run_service.py

### 🔴 CRITICAL - Fix Silent Failures
- Make `_load_from_database()` log more details about table structure
- Make `get_scheduled_runs()` return error info if DB query fails
- Update API endpoint to return database diagnostics

### 🟡 MEDIUM - Add ExecutionTracking
- Record job execution attempts in database
- Track success/failure/response
- Update frontend with execution status

### 🟡 MEDIUM - Improve Error Messages
- Distinguish between "no data" and "data load failed"
- Provide diagnostic info in API responses
- Update frontend to show meaningful error messages

---

## Testing Checklist

After fixes:
- [ ] Create a new scheduled run - verify it appears in DB
- [ ] Restart backend - verify scheduled run still appears
- [ ] Wait for scheduled time - verify job executes
- [ ] Check `/api/scheduler/debug` - verify all counts match
- [ ] Check frontend modal - verify schedule appears
- [ ] Set future schedule - verify execution on time
- [ ] Check execution logs - verify job ran and status recorded
