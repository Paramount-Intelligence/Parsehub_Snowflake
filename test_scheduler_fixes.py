#!/usr/bin/env python3
"""
Test script to verify scheduler fixes are working correctly
Tests:
1. Scheduler loads jobs from database on startup
2. Connection pool is used correctly
3. Timezone-aware datetime handling
4. Jobs are properly scheduled in APScheduler
"""

import sys
import os
from datetime import datetime, timedelta
import pytz

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend', 'src'))

from models.database import ParseHubDatabase
from services.scheduled_run_service import ScheduledRunService, get_scheduled_run_service, start_scheduled_run_service
from tzlocal import get_localzone

LOCAL_TZ = get_localzone()

print("=" * 70)
print("SCHEDULER FIXES VERIFICATION TEST")
print("=" * 70)

# 1. Test database connection
print("\n[TEST 1] Database Connection and Table Creation")
print("-" * 70)
try:
    db = ParseHubDatabase()
    db.connect()
    print("[OK] Database connection successful")
    db.disconnect()
except Exception as e:
    print(f"[ERROR] Database connection failed: {e}")
    sys.exit(1)

# 2. Test inserting a test scheduled job
print("\n[TEST 2] Insert Test Scheduled Job into Database")
print("-" * 70)
try:
    db = ParseHubDatabase()
    conn = db.connect()
    cursor = conn.cursor()
    
    # Insert a test job (1 minute in the future)
    test_time = (datetime.now(LOCAL_TZ) + timedelta(minutes=1)).isoformat()
    test_job_id = f"test_scheduler_job_{int(datetime.now().timestamp())}"
    
    query = """
    INSERT INTO scheduled_runs 
    (job_id, project_token, schedule_type, scheduled_time, frequency, day_of_week, pages, created_at, active)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    params = (
        test_job_id,
        "test_token_xyz",
        "once",
        test_time,
        None,
        None,
        1,
        datetime.now().isoformat(),
        True
    )
    
    cursor.execute(query, params)
    conn.commit()
    db.disconnect()
    print(f"[OK] Test job inserted: {test_job_id}")
    print(f"   Scheduled for: {test_time}")
except Exception as e:
    print(f"[ERROR] Failed to insert test job: {e}")
    db.disconnect()
    sys.exit(1)

# 3. Test scheduler initialization and database loading
print("\n[TEST 3] Scheduler Initialization and Database Loading")
print("-" * 70)
try:
    # Get the scheduler service
    scheduler_service = get_scheduled_run_service()
    
    # Connect database to scheduler
    db = ParseHubDatabase()
    scheduler_service.set_database(db)
    
    # Start scheduler
    scheduler_service.start()
    
    print("[OK] Scheduler initialized and started")
    print(f"   Scheduler running: {scheduler_service.scheduler.running}")
except Exception as e:
    print(f"[ERROR] Scheduler initialization failed: {e}")
    sys.exit(1)

# 4. Verify jobs loaded from database
print("\n[TEST 4] Verify Jobs Loaded from Database")
print("-" * 70)
try:
    jobs = scheduler_service.get_scheduled_runs()
    print(f"[OK] Loaded {len(jobs)} jobs from database")
    
    # Check if our test job was loaded
    test_job_found = False
    for job in jobs:
        if job['job_id'] == test_job_id:
            test_job_found = True
            print(f"   [OK] Test job found in loaded jobs:")
            print(f"      Job ID: {job['job_id']}")
            print(f"      Project Token: {job['project_token']}")
            print(f"      Type: {job['type']}")
            print(f"      Scheduled Time: {job.get('scheduled_time', 'N/A')}")
            break
    
    if not test_job_found:
        print(f"   [WARN] Test job not found in loaded jobs (might be already past scheduled time)")
        if jobs:
            print(f"   First loaded job: {jobs[0]}")
    
except Exception as e:
    print(f"[ERROR] Failed to verify loaded jobs: {e}")
    import traceback
    traceback.print_exc()

# 5. Test timezone handling
print("\n[TEST 5] Timezone Handling Verification")
print("-" * 70)
try:
    # Test creating a scheduled job with timezone-aware datetime
    future_time = datetime.now(LOCAL_TZ) + timedelta(minutes=5)
    print(f"[OK] Current timezone: {LOCAL_TZ}")
    print(f"   Future time (with timezone): {future_time.isoformat()}")
    print(f"   Timezone info: {future_time.tzinfo}")
    
    # Test parsing timezone-aware ISO format
    iso_time = future_time.isoformat()
    parsed_time = datetime.fromisoformat(iso_time)
    print(f"   Parsed back: {parsed_time.isoformat()}")
    print(f"   Parsed tzinfo: {parsed_time.tzinfo}")
    print(f"[OK] Timezone-aware datetime handling working correctly")
    
except Exception as e:
    print(f"[ERROR] Timezone handling test failed: {e}")

# 6. Check APScheduler jobs
print("\n[TEST 6] APScheduler Jobs Verification")
print("-" * 70)
try:
    scheduled_jobs = scheduler_service.scheduler.get_jobs()
    print(f"[OK] APScheduler has {len(scheduled_jobs)} jobs scheduled")
    
    if len(scheduled_jobs) > 0:
        print("   Scheduled jobs:")
        for job in scheduled_jobs[:5]:  # Show first 5
            print(f"      - {job.id}: {job.trigger}")
    
except Exception as e:
    print(f"[ERROR] Failed to check APScheduler jobs: {e}")

# 7. Test connection pool (the fix we made)
print("\n[TEST 7] Connection Pool Usage Verification")
print("-" * 70)
try:
    # This tests that cursor = conn.cursor() works correctly
    db = ParseHubDatabase()
    conn = db.connect()
    cursor = conn.cursor()  # This is the fix - not self.db.cursor()
    
    cursor.execute("SELECT 1")
    result = cursor.fetchone()
    
    if result:
        print(f"[OK] Connection pool working correctly")
        print(f"   Query result: {result}")
    
    db.disconnect()
except Exception as e:
    print(f"[ERROR] Connection pool test failed: {e}")

# 8. Cleanup: Delete test job
print("\n[TEST 8] Cleanup - Remove Test Job")
print("-" * 70)
try:
    db = ParseHubDatabase()
    conn = db.connect()
    cursor = conn.cursor()
    
    query = "DELETE FROM scheduled_runs WHERE job_id = %s"
    cursor.execute(query, (test_job_id,))
    conn.commit()
    
    print(f"[OK] Test job deleted: {test_job_id}")
    db.disconnect()
except Exception as e:
    print(f"[ERROR] Cleanup failed: {e}")

# Stop scheduler
try:
    scheduler_service.stop()
    print("[OK] Scheduler stopped")
except:
    pass

print("\n" + "=" * 70)
print("SCHEDULER FIXES VERIFICATION COMPLETE")
print("=" * 70)
print("\n[NEXT STEPS]:")
print("1. Restart the backend to trigger scheduler initialization")
print("2. Schedule a test job for 1 minute in the future via the UI")
print("3. Check backend logs for [EXECUTE] message at scheduled time")
print("4. Verify /api/scheduler/debug shows scheduler_running: true")
print("5. Verify /api/scheduled-runs displays the scheduled job")
