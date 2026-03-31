"""
Analytics Sync Worker
=====================
Runs in the background inside the Flask server.
Every 5 minutes, it fetches active projects from Snowflake,
queries ParseHub for their latest CSV/JSON analytics data,
and pushes the results into Snowflake via `store_analytics_data`.
"""

import os
import time
import json
import logging
import threading
from typing import List, Dict, Any
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.models.database import ParseHubDatabase

logger = logging.getLogger(__name__)

SYNC_INTERVAL_SECONDS = 5 * 60  # 5 minutes
MAX_WORKERS = 3

PARSEHUB_API_KEY = os.getenv("PARSEHUB_API_KEY", "")
PARSEHUB_BASE_URL = os.getenv("PARSEHUB_BASE_URL", "https://www.parsehub.com/api/v2")

class AnalyticsSyncWorker:
    def __init__(self):
        self.db = ParseHubDatabase()
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        """Starts the background 5-minute sync loop in a daemon thread."""
        if not PARSEHUB_API_KEY:
            logger.warning("[ANALYTICS-SYNC] PARSEHUB_API_KEY missing - background sync disabled")
            return

        if self._thread and self._thread.is_alive():
            logger.info("[ANALYTICS-SYNC] Thread already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="AnalyticsSyncWorker")
        self._thread.start()
        logger.info("[ANALYTICS-SYNC] Background polling started (every 5 mins)")

    def stop(self):
        """Signals the worker thread to stop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _get_active_projects(self) -> List[str]:
        """Fetch all known project tokens from the database."""
        conn = None
        try:
            conn = self.db.connect()
            cursor = self.db.cursor()
            cursor.execute("SELECT token FROM projects WHERE token IS NOT NULL")
            rows = cursor.fetchall()
            return [r['token'] if isinstance(r, dict) else r[0] for r in rows]
        except Exception as e:
            logger.error("[ANALYTICS-SYNC] Failed to fetch active projects: %s", e)
            return []
        finally:
            if conn:
                self.db.disconnect()

    def _parse_csv(self, csv_text: str) -> List[Dict[str, Any]]:
        """A lightweight robust CSV parser to dictionary rows."""
        lines = csv_text.strip().split('\n')
        if not lines:
            return []
        
        import csv
        from io import StringIO
        f = StringIO(csv_text)
        reader = csv.DictReader(f)
        try:
            return [dict(row) for row in reader]
        except Exception as e:
            logger.error("[ANALYTICS-SYNC] CSV Parse Error: %s", e)
            return []

    def _sync_single_project(self, project_token: str):
        """Fetch the latest run data from ParseHub and store it in Snowflake."""
        try:
            # 1. Get project info (to find the latest run token)
            proj_resp = requests.get(
                f"{PARSEHUB_BASE_URL}/projects/{project_token}",
                params={"api_key": PARSEHUB_API_KEY},
                timeout=15
            )
            
            # If 404, the project was deleted from ParseHub but still in DB
            if proj_resp.status_code == 404:
                return
            proj_resp.raise_for_status()
            project_data = proj_resp.json()

            last_run = project_data.get("last_run")
            if not last_run or not last_run.get("run_token"):
                return  # Never run

            run_token = last_run["run_token"]
            run_status = last_run.get("status", "unknown")
            
            logger.debug(f"[ANALYTICS-SYNC] Syncing {project_token} (run_token={run_token})")

            # 2. Try fetching CSV format first (preferred for speed and data alignment)
            csv_text = None
            records = []
            
            try:
                csv_resp = requests.get(
                    f"{PARSEHUB_BASE_URL}/runs/{run_token}/data",
                    params={"api_key": PARSEHUB_API_KEY, "format": "csv"},
                    timeout=30,  # larger timeout for potentially large data
                    headers={"Accept-Encoding": "gzip"}
                )
                csv_resp.raise_for_status()
                csv_text = csv_resp.text
                records = self._parse_csv(csv_text)
            except Exception as csv_err:
                logger.debug(f"[ANALYTICS-SYNC] CSV fetch failed for {project_token}, falling back to default: {csv_err}")
                # Fallback to pure JSON if CSV fails
                json_resp = requests.get(
                    f"{PARSEHUB_BASE_URL}/runs/{run_token}/data",
                    params={"api_key": PARSEHUB_API_KEY},
                    timeout=30
                )
                json_resp.raise_for_status()
                run_data = json_resp.json()
                
                # Extract records from the generic ParseHub nested response
                for key in run_data.keys():
                    if key not in ['offset', 'brand'] and isinstance(run_data[key], list):
                        records = run_data[key]
                        break

            total_records = len(records)
            
            # 3. Build the standardized analytics structure required by db.store_analytics_data
            analytics_payload = {
                "overview": {
                    "total_runs": 1,
                    "completed_runs": 1 if run_status in ('succeeded', 'complete') else 0,
                    "total_records_scraped": total_records,
                    "progress_percentage": 100 if run_status in ('succeeded', 'complete') else 50,
                },
                "performance": {
                    "items_per_minute": 0,
                    "estimated_total_items": total_records,
                    "average_run_duration_seconds": 0,
                    "current_items_count": total_records,
                },
                "recovery": {
                    "in_recovery": False,
                    "status": 'normal',
                    "total_recovery_attempts": 0,
                },
                "data_quality": {
                    "average_completion_percentage": 100,
                    "total_fields": len(records[0]) if records else 0,
                },
                "timeline": [],
                "source": "parsehub",
                "run_token": run_token
            }

            # 4. Write fully processed payload + individual normalized rows to Snowflake
            self.db.store_analytics_data(
                project_token=project_token,
                run_token=run_token,
                analytics_data=analytics_payload,
                records=records,
                csv_data=csv_text  # store raw CSV in Snowflake to bypass frontend generation
            )
            
            logger.info(f"✅ [ANALYTICS-SYNC] Successfully synced analytics for {project_token} ({total_records} rows)")

        except requests.exceptions.RequestException as e:
            logger.warning(f"❌ [ANALYTICS-SYNC] ParseHub HTTP Error for {project_token}: {e}")
        except Exception as e:
            logger.error(f"❌ [ANALYTICS-SYNC] Unexpected Error for {project_token}: {e}")

    def _sync_all_projects(self):
        """Fetch active projects and process them concurrently."""
        tokens = self._get_active_projects()
        if not tokens:
            return

        logger.info(f"[ANALYTICS-SYNC] Scheduled sync starting for {len(tokens)} active projects.")
        
        # We use a ThreadPoolExecutor for concurrent fetching
        # DO NOT mix Snowflake connection instantiation across threads;
        # store_analytics_data handles connecting/disconnecting cleanly inside its body.
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(self._sync_single_project, t) for t in tokens]
            for future in as_completed(futures):
                # We can check for _stop_event, but bounded HTTP threads will finish quickly anyway
                if self._stop_event.is_set():
                    logger.info("[ANALYTICS-SYNC] Stopping midway due to shutdown signal.")
                    break

    def _run_loop(self):
        """The long-running blocking loop executed by the daemon thread."""
        while not self._stop_event.is_set():
            try:
                # 1. Execute full system-wide background sync cycle
                self._sync_all_projects()
            except Exception as e:
                logger.error("[ANALYTICS-SYNC] Critical error in background loop: %s", e)
                
            # 2. Wait 5 minutes before the next cycle (with frequent short wakes to check stop_event)
            sleep_chunks = SYNC_INTERVAL_SECONDS / 2.0
            for _ in range(int(sleep_chunks)):
                if self._stop_event.is_set():
                    break
                time.sleep(2.0)

# Global singleton
_worker = AnalyticsSyncWorker()

def start_analytics_sync_job():
    global _worker
    _worker.start()

def stop_analytics_sync_job():
    global _worker
    _worker.stop()
