"""
Integration test: POST /api/monitor/start must succeed when project_token is sent.

Validates fixes for:
  - project_id resolution via project_token (Snowflake runs table may not have legacy columns)
  - create_monitoring_session returns explicit id (Snowflake lastrowid is None)

Usage:
  cd Parsehub_Snowflake/backend
  python scripts/test_monitor_start_api.py

Requires: Snowflake (or configured DB), at least one row in projects.
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from pathlib import Path

backend = Path(__file__).resolve().parent.parent
if str(backend) not in sys.path:
    sys.path.insert(0, str(backend))

os.environ.setdefault("SKIP_BACKGROUND_SERVICES", "1")
os.environ.setdefault("QUIET_SNOWFLAKE_DB_CONNECT_PRINT", "1")
# Do not run monitor_run_realtime loop in-process (blocks HTTP; hits ParseHub for fake tokens).
os.environ.setdefault("SKIP_MONITOR_REALTIME", "1")

from dotenv import load_dotenv

load_dotenv(backend / ".env")
load_dotenv(backend / "env")
os.chdir(backend)

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

from src.api.api_server import _initialize_services, app
from src.models.database import ParseHubDatabase, new_monitoring_session_id


def _get_first_project() -> tuple[int, str] | None:
    db = ParseHubDatabase()
    db.connect()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id, token FROM projects ORDER BY id LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return None
        if isinstance(row, dict):
            return int(row["id"]), str(row["token"]).strip()
        return int(row[0]), str(row[1]).strip()
    finally:
        db.disconnect()


def test_new_monitoring_session_id_unique() -> None:
    """Pure check: IDs are positive ints and differ between calls."""
    a = new_monitoring_session_id(1, "run_a")
    b = new_monitoring_session_id(1, "run_a")
    assert isinstance(a, int) and a > 0
    assert isinstance(b, int) and b > 0
    assert a != b, "new_monitoring_session_id should vary per call (time_ns)"


def test_create_monitoring_session_returns_int() -> None:
    """DB: explicit PK insert must return session id (not None)."""
    row = _get_first_project()
    assert row is not None, "Need at least one project in DB"
    project_id, _token = row
    db = ParseHubDatabase()
    run_token = f"test_mon_{uuid.uuid4().hex[:24]}"
    sid = db.create_monitoring_session(project_id, run_token, target_pages=1)
    assert sid is not None, "create_monitoring_session returned None"
    assert isinstance(sid, int) and sid > 0


def test_http_monitor_start() -> None:
    """Flask: POST /api/monitor/start with project_token -> 200 + session_id."""
    row = _get_first_project()
    assert row is not None, "Need at least one project in DB"
    project_id, project_token = row
    run_token = f"test_http_{uuid.uuid4().hex[:24]}"

    _initialize_services()

    with app.test_client() as client:
        resp = client.post(
            "/api/monitor/start",
            json={
                "run_token": run_token,
                "pages": 2,
                "project_token": project_token,
            },
        )

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.get_data(as_text=True)[:800]}"
    data = resp.get_json()
    assert data is not None
    assert "session_id" in data
    sid = data["session_id"]
    assert isinstance(sid, int) and sid > 0
    assert data.get("project_id") == project_id


def main() -> int:
    print("[test] new_monitoring_session_id ...")
    test_new_monitoring_session_id_unique()
    print("  [ok]")

    print("[test] create_monitoring_session returns int ...")
    test_create_monitoring_session_returns_int()
    print("  [ok]")

    print("[test] POST /api/monitor/start ...")
    test_http_monitor_start()
    print("  [ok]")

    print("[test] ALL PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as e:
        print(f"[test] FAILED: {e}")
        raise SystemExit(1)
