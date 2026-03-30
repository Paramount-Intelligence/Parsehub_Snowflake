#!/usr/bin/env python3
"""
Auto Sync Service - Automatically syncs data from ParseHub API to database
Fetches latest project details, run statuses, and updates database records
"""
import requests
import json
import os
import time
import logging
from datetime import datetime, timedelta
from threading import Thread, Event
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import sys
from pathlib import Path
root_dir = Path(__file__).parent.parent.parent  # backend/
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.models.database import ParseHubDatabase

load_dotenv('.env')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv('PARSEHUB_API_KEY')
BASE_URL = 'https://www.parsehub.com/api/v2'
SYNC_INTERVAL = int(os.getenv('AUTO_SYNC_INTERVAL', '5'))         # Project-sync interval (minutes)
DATA_FETCH_INTERVAL = int(os.getenv('DATA_FETCH_INTERVAL', '5'))  # Data-fetch interval (minutes)


class AutoSyncService:
    """
    Two independent background loops:

    Thread A — _sync_loop (every AUTO_SYNC_INTERVAL minutes)
        Syncs project metadata + run statuses from ParseHub API.
        Fast: no CSV downloads.

    Thread B — _data_fetch_loop (every DATA_FETCH_INTERVAL minutes)
        Finds completed runs whose CSV data is not yet in Snowflake,
        downloads the CSV, and stores it.  Uses its own Snowflake
        connection so it never interferes with Thread A.
    """

    def __init__(self, max_workers: int = 5):
        self.db = ParseHubDatabase()
        self.api_key = API_KEY
        self.base_url = BASE_URL
        self.sync_interval = SYNC_INTERVAL
        self.data_fetch_interval = DATA_FETCH_INTERVAL
        self.max_workers = max_workers
        self.running = False
        self.thread = None        # Thread A: project sync
        self.data_thread = None   # Thread B: data fetch
        self.stop_event = Event()

        if not self.api_key:
            raise Exception("PARSEHUB_API_KEY not configured in .env")

    def _get_with_retry(
        self,
        url: str,
        *,
        params: Optional[Dict] = None,
        timeout: int = 120,
        max_retries: int = 4,
        backoff_sec: float = 2.0,
    ) -> Optional[requests.Response]:
        """GET with retries for ParseHub timeouts and transient HTTP errors."""
        merged: Dict = {'api_key': self.api_key}
        if params:
            merged.update(params)
        retry_status = (429, 500, 502, 503, 504)
        for attempt in range(max_retries):
            try:
                resp = requests.get(url, params=merged, timeout=timeout)
                if resp.status_code in retry_status and attempt < max_retries - 1:
                    logger.warning(
                        "ParseHub GET %s returned %s (attempt %s/%s), retrying...",
                        url[:96],
                        resp.status_code,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(backoff_sec * (attempt + 1))
                    continue
                return resp
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                logger.warning(
                    "ParseHub GET %s: %s (attempt %s/%s)",
                    url[:96],
                    e,
                    attempt + 1,
                    max_retries,
                )
                if attempt < max_retries - 1:
                    time.sleep(backoff_sec * (attempt + 1))
                else:
                    logger.error("ParseHub GET failed after %s attempts: %s", max_retries, url[:96])
                    return None
        return None

    def start(self):
        """Start both background threads."""
        if self.running:
            logger.warning("Auto-sync service already running")
            return

        self.running = True
        self.stop_event.clear()

        # Thread A: project + run metadata sync
        self.thread = Thread(target=self._sync_loop, name="project-sync", daemon=True)
        self.thread.start()
        logger.info(f"[OK] Project-sync thread started (every {self.sync_interval} min)")

        # Thread B: CSV data fetch — independent timer, own DB connection
        self.data_thread = Thread(target=self._data_fetch_loop, name="data-fetch", daemon=True)
        self.data_thread.start()
        logger.info(f"[OK] Data-fetch thread started (every {self.data_fetch_interval} min)")

    def stop(self):
        """Stop both background threads."""
        if not self.running:
            return

        self.running = False
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        if self.data_thread:
            self.data_thread.join(timeout=5)
        logger.info("[OK] Auto-Sync Service stopped")

    def _sync_loop(self):
        """Background loop that runs sync periodically"""
        while self.running and not self.stop_event.is_set():
            try:
                logger.info("\n" + "="*80)
                logger.info(
                    f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running auto-sync...")
                logger.info("="*80)

                # Run sync
                results = self.sync_all()

                # Log summary
                logger.info(f"\n[OK] Sync completed:")
                logger.info(
                    f"  - Projects synced: {results.get('projects_synced', 0)}")
                logger.info(
                    f"  - Runs updated: {results.get('runs_updated', 0)}")
                logger.info(
                    f"  - Projects updated: {results.get('projects_updated', 0)}")

                next_sync = datetime.now() + timedelta(minutes=self.sync_interval)
                logger.info(
                    f"\nNext sync: {next_sync.strftime('%Y-%m-%d %H:%M:%S')}")

            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                import traceback
                traceback.print_exc()

            # Wait for next interval or stop event
            self.stop_event.wait(timeout=self.sync_interval * 60)

    def _data_fetch_loop(self):
        """
        Thread B — runs independently of the project-sync loop.

        Every DATA_FETCH_INTERVAL minutes it:
          1. Opens its own Snowflake connection (never shares with Thread A).
          2. Queries for completed runs that have no CSV data yet.
          3. Downloads the CSV from ParseHub and stores it.
          4. Disconnects.
        """
        # Own ParseHubDatabase instance → own thread-local Snowflake connection.
        db = ParseHubDatabase()
        logger.info("[data-fetch] Thread started — first run in 30 s to let project-sync settle.")
        # Small initial delay so project-sync has time to populate runs first.
        self.stop_event.wait(timeout=30)

        while self.running and not self.stop_event.is_set():
            try:
                logger.info(
                    f"\n[data-fetch] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                    "Checking for completed runs to fetch..."
                )
                results: Dict = {}
                self._fetch_completed_runs_data(db, results)
                stored = results.get('runs_data_stored', 0)
                logger.info(f"[data-fetch] Done — stored data for {stored} run(s).")
            except Exception as exc:
                logger.error(f"[data-fetch] Unexpected error: {exc}")
                import traceback
                traceback.print_exc()
            finally:
                # Always close the connection after each cycle so Snowflake
                # doesn't hold an idle session for the full interval.
                try:
                    db.disconnect()
                except Exception:
                    pass

            next_run = datetime.now() + timedelta(minutes=self.data_fetch_interval)
            logger.info(f"[data-fetch] Next run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            self.stop_event.wait(timeout=self.data_fetch_interval * 60)

    def sync_all(self):
        """
        Sync all data from ParseHub API:
        1. Fetch all projects
        2. Update project details
        3. Update last_run info for each project
        4. Update run statuses for active runs
        """
        results = {
            'projects_synced': 0,
            'runs_updated': 0,
            'projects_updated': 0,
            'failed_projects': []
        }

        try:
            # 1. Fetch all projects from ParseHub API
            logger.info("\n1. Fetching all projects from ParseHub API...")
            projects = self.fetch_all_projects()

            if not projects:
                logger.warning("No projects found in ParseHub account")
                return results

            logger.info(f"   Found {len(projects)} projects")
            results['projects_synced'] = len(projects)

            # 2. Sync each project IN PARALLEL using ThreadPoolExecutor
            logger.info(f"\n2. Syncing {len(projects)} projects using "
                       f"{self.max_workers} parallel workers...")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all sync tasks - use inline function to avoid missing method issues
                def sync_one_project(proj):
                    try:
                        # Keys required by sync_project / sync_run (parallel threads use local dict)
                        tr = {'projects_updated': 0, 'runs_updated': 0}
                        self.sync_project(proj, tr)
                        return True
                    except Exception as e:
                        logger.error(f"Error syncing {proj.get('token', 'unknown')}: {e}")
                        return False
                
                future_to_project = {
                    executor.submit(sync_one_project, project): project
                    for project in projects
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_project):
                    project = future_to_project[future]
                    project_token = project.get('token', 'unknown')[:8]
                    project_title = project.get('title', 'Unknown')[:30]
                    
                    try:
                        success = future.result()
                        if success:
                            results['projects_updated'] += 1
                            logger.info(f"   [OK] {project_title} ({project_token}...)")
                        else:
                            results['failed_projects'].append(project.get('token'))
                            logger.warning(f"   [FAIL] {project_title} ({project_token}...)")
                    except Exception as e:
                        logger.error(f"   [ERROR] {project_title} ({project_token}...): {e}")
                        results['failed_projects'].append(project.get('token'))

            logger.info(f"\n   [SUMMARY] {results['projects_updated']}/{len(projects)} "
                       f"projects synced successfully")
            if results['failed_projects']:
                logger.warning(f"   [WARN] {len(results['failed_projects'])} projects failed")

            # 3. Update active runs
            logger.info("\n3. Updating active runs...")
            self.update_active_runs(results)

            # NOTE: CSV data fetching is handled by the independent _data_fetch_loop thread.

            return results

        except Exception as e:
            logger.error(f"Error in sync_all: {e}")
            import traceback
            traceback.print_exc()
            return results

    def fetch_all_projects(self) -> List[Dict]:
        """Fetch all projects from ParseHub API with pagination"""
        try:
            all_projects = []
            offset = 0
            limit = 20  # ParseHub returns 20 projects per page

            while True:
                response = self._get_with_retry(
                    f"{self.base_url}/projects",
                    params={'offset': offset},
                    timeout=90,
                    max_retries=4,
                )
                if response is None:
                    logger.error("ParseHub projects list: no response after retries")
                    break

                if response.status_code != 200:
                    logger.error(f"API error: {response.status_code}")
                    break

                data = response.json()
                projects = data.get('projects', [])

                if not projects:
                    break

                all_projects.extend(projects)

                # Check if there are more projects
                total_projects = data.get('total_projects', 0)
                if len(all_projects) >= total_projects:
                    break

                offset += limit
                time.sleep(0.5)  # Rate limiting

            return all_projects

        except Exception as e:
            logger.error(f"Error fetching projects: {e}")
            return []

    def sync_project(self, project: Dict, results: Dict):
        """Sync a single project to database"""
        try:
            token = project.get('token')
            title = project.get('title', 'Unknown Project')

            logger.info(f"   Syncing project: {title} ({token[:8]}...)")

            # Update project in database
            conn = self.db.connect()
            cursor = self.db.cursor()

            # Check if project exists
            cursor.execute('SELECT id FROM projects WHERE token = %s', (token,))
            existing = cursor.fetchone()

            if existing:
                # Update existing project
                cursor.execute('''
                    UPDATE projects 
                    SET title = %s, 
                        owner_email = %s,
                        main_site = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE token = %s
                ''', (
                    title,
                    project.get('owner_email'),
                    project.get('main_site'),
                    token
                ))
                # Normalize dict keys from Snowflake (uppercase) to lowercase
                if isinstance(existing, dict):
                    existing_lower = {k.lower(): v for k, v in existing.items()}
                    project_id = existing_lower.get('id')
                else:
                    project_id = existing[0]
                logger.info(f"   [OK] Updated project (ID: {project_id})")
            else:
                # Insert new project - generate ID using hash of token
                # Snowflake doesn't auto-increment like SQLite, so we generate a unique ID
                import hashlib
                project_id = int(hashlib.md5(token.encode()).hexdigest(), 16) % (10**10)

                cursor.execute('''
                    INSERT INTO projects (id, token, title, owner_email, main_site)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (
                    project_id,
                    token,
                    title,
                    project.get('owner_email'),
                    project.get('main_site')
                ))
                logger.info(f"   [OK] Created new project (ID: {project_id})")

            conn.commit()
            results['projects_updated'] += 1

            # Sync last_run info if available
            last_run = project.get('last_run')
            if last_run:
                self.sync_run(project_id, last_run, results)

            conn.close()

        except Exception as e:
            logger.error(f"Error syncing project {project.get('token')}: {e}")

    def sync_run(self, project_id: int, run_data: Dict, results: Dict):
        """Sync run information to database"""
        try:
            run_token = run_data.get('run_token')
            if not run_token:
                return

            status = run_data.get('status', 'unknown')

            conn = self.db.connect()
            cursor = self.db.cursor()

            # Check if run exists
            cursor.execute(
                'SELECT id, status FROM runs WHERE run_token = %s', (run_token,))
            existing = cursor.fetchone()

            # Parse timestamps
            start_time = run_data.get('start_time')
            end_time = run_data.get('end_time')

            # Calculate duration
            duration = None
            if start_time and end_time:
                try:
                    start_dt = datetime.fromisoformat(
                        start_time.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(
                        end_time.replace('Z', '+00:00'))
                    duration = int((end_dt - start_dt).total_seconds())
                except:
                    pass

            # Get pages scraped
            pages_scraped = run_data.get('pages', 0)

            # Get data readiness
            data_ready = run_data.get('data_ready', 0)

            if existing:
                # Normalize dict keys from Snowflake (uppercase) to lowercase
                if isinstance(existing, dict):
                    existing_lower = {k.lower(): v for k, v in existing.items()}
                    run_id = existing_lower.get('id')
                    old_status = existing_lower.get('status')
                else:
                    run_id = existing[0]
                    old_status = existing[1]

                # Only update if status changed or run is active
                if old_status != status or status in ['running', 'initializing']:
                    cursor.execute('''
                        UPDATE runs
                        SET status = %s,
                            pages_scraped = %s,
                            start_time = %s,
                            end_time = %s,
                            duration_seconds = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE run_token = %s
                    ''', (
                        status,
                        pages_scraped,
                        start_time,
                        end_time,
                        duration,
                        run_token
                    ))

                    conn.commit()

                    if old_status != status:
                        logger.info(
                            f"   [OK] Updated run {run_token[:8]}... ({old_status} -> {status})")
                        results['runs_updated'] += 1
            else:
                # Insert new run - generate ID using Snowflake sequence or hash
                # Snowflake doesn't auto-increment like SQLite, so we generate a unique ID
                import hashlib
                # Generate a numeric ID from run_token (which is unique)
                run_id = int(hashlib.md5(run_token.encode()).hexdigest(), 16) % (10**10)

                cursor.execute('''
                    INSERT INTO runs (
                        id, project_id, run_token, status, pages_scraped,
                        start_time, end_time, duration_seconds
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    run_id,
                    project_id,
                    run_token,
                    status,
                    pages_scraped,
                    start_time,
                    end_time,
                    duration
                ))

                logger.info(
                    f"   [OK] Created new run {run_token[:8]}... (ID: {run_id}, status: {status})")
                results['runs_updated'] += 1

            conn.close()

        except Exception as e:
            logger.error(f"Error syncing run {run_data.get('run_token')}: {e}")

    def update_active_runs(self, results: Dict):
        """Update status of all active runs in database"""
        try:
            cursor = self.db.cursor()

            # Get all runs that might still be active
            cursor.execute('''
                SELECT r.id, r.run_token, p.token as project_token
                FROM runs r
                INNER JOIN projects p ON r.project_id = p.id
                WHERE r.status IN ('running', 'initializing')
                ORDER BY r.start_time DESC
                LIMIT 50
            ''')

            active_runs = cursor.fetchall()

            if not active_runs:
                logger.info("   No active runs to update")
                return

            logger.info(f"   Found {len(active_runs)} potentially active runs")

            for run in active_runs:
                # Normalize dict keys from Snowflake (uppercase) to lowercase
                if isinstance(run, dict):
                    run_lower = {k.lower(): v for k, v in run.items()}
                    run_id = run_lower.get('id')
                    run_token = run_lower.get('run_token')
                    project_token = run_lower.get('project_token')
                else:
                    run_id = run[0]
                    run_token = run[1]
                    project_token = run[2]

                # Fetch run details from ParseHub API
                run_details = self.fetch_run_details(project_token, run_token)

                if run_details:
                    old_status = run_details.get('status')
                    new_status = run_details.get('status')

                    if new_status:
                        # Update run status
                        cursor.execute('''
                            UPDATE runs
                            SET status = %s,
                                pages_scraped = %s,
                                end_time = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        ''', (
                            new_status,
                            run_details.get('pages', 0),
                            run_details.get('end_time'),
                            run_id
                        ))

                        logger.info(
                            f"   [OK] Updated run {run_token[:8]}... (status: {new_status})")
                        results['runs_updated'] += 1

                time.sleep(0.3)  # Rate limiting

        except Exception as e:
            logger.error(f"Error updating active runs: {e}")

    def fetch_run_details(self, project_token: str, run_token: str) -> Optional[Dict]:
        """Fetch run details from ParseHub API"""
        try:
            response = self._get_with_retry(
                f"{self.base_url}/projects/{project_token}/run/{run_token}",
                params={},
                timeout=90,
                max_retries=4,
            )
            if response is None:
                return None

            if response.status_code == 200:
                return response.json()

            return None

        except Exception as e:
            logger.error(f"Error fetching run {run_token}: {e}")
            return None

    def manual_sync(self):
        """Manually trigger a sync (useful for API endpoints)"""
        logger.info("Manual sync triggered")
        return self.sync_all()

    def fetch_and_store_run_data(self, project_token: str, run_token: str, project_title: str = "") -> bool:
        """
        Fetch scraped data from ParseHub run and store it to Snowflake
        Returns True if successful, False otherwise
        """
        try:
            logger.info(f"   [DATA] Fetching data for run {run_token[:8]}...")
            
            # Fetch data in CSV format (large payloads: long timeout + retries)
            response = self._get_with_retry(
                f"{self.base_url}/runs/{run_token}/data",
                params={'format': 'csv'},
                timeout=240,
                max_retries=5,
                backoff_sec=3.0,
            )
            if response is None:
                logger.error(f"   [DATA] No response from ParseHub data endpoint after retries")
                return False

            if response.status_code != 200:
                logger.error(f"   [DATA] Failed to fetch data: HTTP {response.status_code}")
                return False
            
            csv_data = response.text
            if not csv_data or len(csv_data.strip()) == 0:
                logger.warning(f"   [DATA] Empty data from ParseHub")
                return False
            
            # Parse CSV to records
            records = self._parse_csv_to_records(csv_data)
            if not records:
                logger.warning(f"   [DATA] No records parsed from CSV")
                return False
            
            logger.info(f"   [DATA] Parsed {len(records)} records from CSV")
            
            # Build analytics data structure
            analytics_data = {
                'overview': {
                    'total_records_scraped': len(records),
                    'total_runs': 1,
                    'completed_runs': 1,
                    'progress_percentage': 100,
                },
                'performance': {
                    'items_per_minute': 0,
                    'estimated_total_items': len(records),
                    'average_run_duration_seconds': 0,
                    'current_items_count': len(records),
                },
                'recovery': {
                    'in_recovery': False,
                    'status': 'complete',
                    'total_recovery_attempts': 0,
                },
                'data_quality': {
                    'average_completion_percentage': 100,
                    'total_fields': len(records[0].keys()) if records else 0,
                },
                'timeline': [],
            }
            
            # Store to database using the store_analytics_data method
            result = self.db.store_analytics_data(
                project_token=project_token,
                run_token=run_token,
                analytics_data=analytics_data,
                records=records,
                csv_data=csv_data
            )
            
            if result:
                logger.info(f"   [DATA] Successfully stored {len(records)} records to Snowflake")
                return True
            else:
                logger.error(f"   [DATA] Failed to store data to Snowflake")
                return False
                
        except Exception as e:
            logger.error(f"   [DATA] Error fetching/storing run data: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _parse_csv_to_records(self, csv_text: str) -> List[Dict]:
        """Parse CSV text to list of record dictionaries"""
        records = []
        try:
            lines = csv_text.strip().split('\n')
            if not lines:
                return records
            
            # Parse header
            headers = lines[0].split(',')
            headers = [h.strip().replace('"', '') for h in headers]
            
            # Parse rows
            for i in range(1, len(lines)):
                if not lines[i].strip():
                    continue
                
                # Simple CSV parsing (handles basic cases)
                values = []
                current = ''
                in_quotes = False
                
                for char in lines[i]:
                    if char == '"':
                        in_quotes = not in_quotes
                    elif char == ',' and not in_quotes:
                        values.append(current.strip().replace('"', ''))
                        current = ''
                    else:
                        current += char
                
                values.append(current.strip().replace('"', ''))
                
                # Create record
                record = {}
                for idx, header in enumerate(headers):
                    record[header] = values[idx] if idx < len(values) else ''
                
                records.append(record)
            
            return records
        except Exception as e:
            logger.error(f"Error parsing CSV: {e}")
            return records

    def _fetch_completed_runs_data(self, db: 'ParseHubDatabase', results: Dict):
        """
        Find completed runs whose CSV data is not yet stored, download it from
        ParseHub, and persist it to Snowflake.

        Uses the supplied *db* instance (Thread B's own connection) so it never
        touches the connection belonging to the project-sync thread.
        """
        since = datetime.now() - timedelta(hours=24)

        # --- 1. Load the list of candidate runs (fresh connection) ---
        conn = db.connect()
        cursor = db.cursor()
        cursor.execute('''
            SELECT r.id, r.run_token, p.token AS project_token, p.title
            FROM runs r
            JOIN projects p ON r.project_id = p.id
            WHERE LOWER(TRIM(r.status)) IN ('complete', 'completed')
            AND COALESCE(r.end_time, r.updated_at) >= %s
            ORDER BY COALESCE(r.end_time, r.updated_at) DESC
            LIMIT 10
        ''', (since.isoformat(),))
        runs = cursor.fetchall()
        # Close immediately — store_analytics_data will reopen when it needs to
        db.disconnect()

        if not runs:
            logger.info("[data-fetch]   No recent completed runs to process")
            results['runs_data_stored'] = 0
            return

        logger.info(f"[data-fetch]   Found {len(runs)} completed run(s) to check")
        stored_count = 0

        for run in runs:
            # Normalise Snowflake uppercase keys
            if isinstance(run, dict):
                rl = {k.lower(): v for k, v in run.items()}
                run_token = rl.get('run_token')
                project_token = rl.get('project_token')
                project_title = rl.get('title', '')
            else:
                run_token = run[1]
                project_token = run[2]
                project_title = run[3] if len(run) > 3 else ''

            # --- 2. Skip if data already stored (fresh connection per check) ---
            try:
                conn = db.connect()
                cursor = db.cursor()
                cursor.execute(
                    'SELECT COUNT(*) as count FROM analytics_cache WHERE run_token = %s',
                    (run_token,),
                )
                existing = cursor.fetchone()
                existing_count = (
                    existing.get('count', 0) if isinstance(existing, dict)
                    else (existing[0] if existing else 0)
                )
                db.disconnect()
            except Exception as chk_err:
                logger.warning(f"[data-fetch]   Could not check cache for {run_token[:8]}: {chk_err}")
                db.disconnect()
                existing_count = 0

            if existing_count > 0:
                logger.info(f"[data-fetch]   [SKIP] Already stored: {run_token[:8]}...")
                continue

            # --- 3. Download CSV + store to Snowflake ---
            logger.info(f"[data-fetch]   [FETCH] {project_title} — run {run_token[:8]}...")
            success = self._fetch_and_store_with_db(db, project_token, run_token, project_title)
            if success:
                stored_count += 1

            time.sleep(0.5)  # gentle rate-limiting between runs

        logger.info(f"[data-fetch]   [SUMMARY] Stored data for {stored_count} run(s)")
        results['runs_data_stored'] = stored_count

    def _fetch_and_store_with_db(
        self,
        db: 'ParseHubDatabase',
        project_token: str,
        run_token: str,
        project_title: str = "",
    ) -> bool:
        """
        Thin wrapper around fetch_and_store_run_data that temporarily swaps
        self.db to the caller-supplied *db* instance so that store_analytics_data
        writes via Thread B's own Snowflake connection.
        """
        original_db = self.db
        self.db = db
        try:
            return self.fetch_and_store_run_data(project_token, run_token, project_title)
        finally:
            self.db = original_db

    # ------------------------------------------------------------------
    # Legacy name kept for any external callers (e.g. manual_sync path).
    # Delegates to _fetch_completed_runs_data using the shared self.db.
    # ------------------------------------------------------------------
    def sync_completed_runs_data(self, results: Dict):
        """Backward-compatible wrapper — use _fetch_completed_runs_data directly."""
        self._fetch_completed_runs_data(self.db, results)


# Global instance
_auto_sync_service = None


def start_auto_sync_service(interval_minutes: int = None):
    """Start the auto-sync service globally"""
    global _auto_sync_service

    if _auto_sync_service is not None:
        logger.warning("Auto-sync service already started")
        return _auto_sync_service

    # Create service with custom interval if provided
    if interval_minutes:
        os.environ['AUTO_SYNC_INTERVAL'] = str(interval_minutes)

    _auto_sync_service = AutoSyncService()
    _auto_sync_service.start()

    return _auto_sync_service


def stop_auto_sync_service():
    """Stop the auto-sync service globally"""
    global _auto_sync_service

    if _auto_sync_service is None:
        logger.warning("Auto-sync service not running")
        return

    _auto_sync_service.stop()
    _auto_sync_service = None


def get_auto_sync_service():
    """Get the current auto-sync service instance"""
    return _auto_sync_service


# For standalone execution
if __name__ == '__main__':
    import sys

    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 5

    print(f"Starting Auto-Sync Service (interval: {interval} minutes)")
    print("Press Ctrl+C to stop\n")

    service = start_auto_sync_service(interval)

    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping Auto-Sync Service...")
        stop_auto_sync_service()
        print("Stopped.")
