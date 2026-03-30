"""
E2E smoke test: POST /api/scraped-records/ingest → worker → scraped_records in DB.

Run from repo (or backend) with env loaded:
  cd Parsehub_Snowflake/backend
  python scripts/test_scraped_records_ingest_api.py

Requires: DB reachable (Snowflake per project config), at least one row in projects.
"""
from __future__ import annotations

import logging
import os
import sys
import time
import uuid
from pathlib import Path

backend = Path(__file__).resolve().parent.parent
if str(backend) not in sys.path:
    sys.path.insert(0, str(backend))

from dotenv import load_dotenv

load_dotenv(backend / ".env")
load_dotenv(backend / "env")

os.chdir(backend)

from src.api.api_server import BACKEND_API_KEY, _initialize_services, app
from src.models.database import ParseHubDatabase

# After api_server import (it sets basicConfig INFO), quiet noisy loggers for this script.
logging.getLogger().setLevel(logging.WARNING)
for _name in (
    "snowflake",
    "snowflake.connector",
    "apscheduler",
    "urllib3",
    "src.services",
    "src.api",
    "src.models",
):
    logging.getLogger(_name).setLevel(logging.WARNING)


def _count_scraped_records(run_token: str) -> int:
    db = ParseHubDatabase()
    conn = db.connect()
    cursor = db.cursor()
    try:
        cursor.execute(
            "SELECT COUNT(*) AS c FROM scraped_records WHERE run_token = %s",
            (run_token,),
        )
        row = cursor.fetchone()
        if not row:
            return 0
        if isinstance(row, dict):
            return int(row.get("c") or row.get("C") or 0)
        return int(row[0])
    finally:
        db.disconnect()


def main() -> int:
    print("[test] Initializing services (DB + ingest worker)...")
    _initialize_services()

    db = ParseHubDatabase()
    conn = db.connect()
    cursor = db.cursor()
    cursor.execute("SELECT id, token FROM projects LIMIT 1")
    row = cursor.fetchone()
    db.disconnect()
    if not row:
        print("[test] FAIL: No projects in database — add a project first.")
        return 1

    if isinstance(row, dict):
        project_id = row.get("id")
        project_token = row.get("token")
    else:
        project_id, project_token = row[0], row[1]

    run_token = f"test_ingest_{uuid.uuid4().hex[:20]}"
    body = {
        "project_id": int(project_id),
        "run_token": run_token,
        "source_page": 1,
        "records": [
            {"test_marker": "e2e_scraped_records_ingest_api", "n": 1},
            {"test_marker": "e2e_scraped_records_ingest_api", "n": 2},
        ],
        "mirror_scraped_data": False,
    }

    print(f"[test] Using project_id={project_id} token={str(project_token)[:12]}...")
    print(f"[test] POST /api/scraped-records/ingest run_token={run_token}")

    with app.test_client() as client:
        resp = client.post(
            "/api/scraped-records/ingest",
            json=body,
            headers={"x-api-key": BACKEND_API_KEY},
        )

    print(f"[test] HTTP {resp.status_code}: {resp.get_json(silent=True)}")
    if resp.status_code != 202:
        print("[test] FAIL: expected 202 Accepted")
        return 1

    print("[test] Waiting for background worker (up to ~15s)...")
    for i in range(75):
        time.sleep(0.2)
        n = _count_scraped_records(run_token)
        if n >= 2:
            print(f"[test] SUCCESS: {n} row(s) in scraped_records for this run_token (Snowflake/DB).")
            return 0
        if i % 10 == 0 and i:
            print(f"[test]   ... still waiting (count={n})")

    n = _count_scraped_records(run_token)
    print(f"[test] FAIL: expected 2 rows, found {n} for run_token={run_token}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
