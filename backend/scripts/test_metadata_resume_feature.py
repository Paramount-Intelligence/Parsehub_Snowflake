"""
Smoke / integration test for metadata-driven resume scraping (API + scraper).

Validates:
  - projects.id resolution from ParseHub token (matches scraped_records / checkpoints)
  - GET /api/projects/<token>/resume/checkpoint
  - GET /api/projects/<token>/resume/metadata
  - MetadataDrivenResumeScraper.get_checkpoint / get_project_metadata vs HTTP
  - Optional: POST /api/projects/resume/start (REAL ParseHub run — off by default)

Usage:
  cd Parsehub_Snowflake/backend
  python scripts/test_metadata_resume_feature.py

  # Also call POST /resume/start (starts a real ParseHub run — use with care):
  python scripts/test_metadata_resume_feature.py --parsehub-start

Requires: Snowflake (or configured DB), at least one project row with a metadata row.

Expected noise (usually harmless if this script still ends with SUCCESS):
  - init_snowflake.sql runs one statement per execute (CREATE INDEX lines skipped on Snowflake
    to avoid hybrid-table index errors). Remaining GRANT/DDL warnings may still appear.
  - Email / SMTP warnings: notifications disabled without SMTP env vars.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

backend = Path(__file__).resolve().parent.parent
if str(backend) not in sys.path:
    sys.path.insert(0, str(backend))

# No incremental scheduler / auto-sync noise during this test (see api_server._start_background_services).
os.environ.setdefault("SKIP_BACKGROUND_SERVICES", "1")
# Fewer repeated "Using Snowflake database: ..." lines (see ParseHubDatabase.__init__).
os.environ.setdefault("QUIET_SNOWFLAKE_DB_CONNECT_PRINT", "1")

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
logging.getLogger("src.services.notification_service").setLevel(logging.ERROR)

from src.api.api_server import _initialize_services, app
from src.api.resume_routes import _projects_id_for_token
from src.models.database import ParseHubDatabase
from src.services.metadata_driven_resume_scraper import get_metadata_driven_scraper


def _row_project_with_metadata() -> Optional[Tuple[int, str]]:
    """Return (projects.id, projects.token) for a project that has a metadata row."""
    db = ParseHubDatabase()
    db.connect()
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            SELECT p.id, p.token
            FROM projects p
            WHERE EXISTS (
                SELECT 1 FROM metadata m WHERE m.project_id = p.id
            )
            ORDER BY p.id
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if not row:
            return None
        if isinstance(row, dict):
            pid = row.get("id")
            tok = row.get("token")
        else:
            pid, tok = row[0], row[1]
        return int(pid), str(tok).strip()
    finally:
        db.disconnect()


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def run_http_tests(project_token: str, project_id: int) -> None:
    scraper = get_metadata_driven_scraper()
    cp_direct = scraper.get_checkpoint(project_id)
    meta_direct = scraper.get_project_metadata(project_id)
    _assert(meta_direct is not None, "get_project_metadata returned None")

    with app.test_client() as client:
        r_cp = client.get(f"/api/projects/{project_token}/resume/checkpoint")
        _assert(
            r_cp.status_code == 200,
            f"checkpoint HTTP {r_cp.status_code}: {r_cp.get_data(as_text=True)[:500]}",
        )
        body_cp = r_cp.get_json()
        _assert(body_cp.get("success") is True, "checkpoint should include success: true")
        _assert(
            "highest_successful_page" in body_cp,
            "checkpoint missing highest_successful_page",
        )
        hp_http = int(body_cp["highest_successful_page"] or 0)
        hp_dir = int(cp_direct["highest_successful_page"] or 0)
        _assert(
            hp_http == hp_dir,
            f"checkpoint mismatch HTTP highest={hp_http} vs scraper={hp_dir}",
        )
        tr_http = int(body_cp.get("total_persisted_records") or 0)
        tr_dir = int(cp_direct.get("total_persisted_records") or 0)
        _assert(
            tr_http == tr_dir,
            f"total_persisted_records mismatch HTTP={tr_http} vs scraper={tr_dir}",
        )

        r_md = client.get(f"/api/projects/{project_token}/resume/metadata")
        _assert(
            r_md.status_code == 200,
            f"metadata HTTP {r_md.status_code}: {r_md.get_data(as_text=True)[:500]}",
        )
        body_md = r_md.get_json()
        _assert(body_md.get("success") is True, "metadata should include success: true")
        _assert("website_url" in body_md or body_md.get("metadata"), "missing website_url")
        tp = int(body_md.get("total_pages") or 0)
        tp_d = int(meta_direct.get("total_pages") or 0)
        _assert(
            tp == tp_d,
            f"total_pages mismatch HTTP={tp} vs scraper={tp_d}",
        )
        nested = body_md.get("metadata")
        if isinstance(nested, dict):
            _assert(
                nested.get("website_url") is not None or nested.get("base_url") is not None,
                "nested metadata should include website_url or base_url",
            )

        print(
            f"  [ok] GET checkpoint: highest_page={hp_http}, records={tr_http}, "
            f"complete={body_cp.get('is_project_complete')}"
        )
        print(
            f"  [ok] GET metadata: total_pages={tp}, website_url_len="
            f"{len(str(body_md.get('website_url') or ''))}"
        )


def run_resolution_test(db: ParseHubDatabase, project_token: str, project_id: int) -> None:
    pid = _projects_id_for_token(db, project_token)
    _assert(pid == project_id, f"_projects_id_for_token got {pid}, expected {project_id}")
    pid2 = db.get_project_id_by_token(project_token)
    _assert(
        int(pid2) == project_id,
        f"get_project_id_by_token got {pid2}, expected {project_id}",
    )
    print("  [ok] Token -> projects.id resolution matches DB")


def run_negative_test(project_token: str) -> None:
    fake = project_token + "_INVALID_TOKEN_XYZ"
    with app.test_client() as client:
        r = client.get(f"/api/projects/{fake}/resume/checkpoint")
        _assert(r.status_code == 404, f"expected 404 for bad token, got {r.status_code}")
    print("  [ok] Invalid token -> checkpoint 404")


def run_parsehub_start(project_token: str, project_id: int) -> None:
    with app.test_client() as client:
        r = client.post(
            "/api/projects/resume/start",
            data=json.dumps(
                {"project_token": project_token, "project_id": project_id}
            ),
            content_type="application/json",
        )
        data = r.get_json(silent=True) or {}
        print(f"  POST /resume/start -> HTTP {r.status_code}")
        if r.status_code not in (200, 201):
            print(f"  [warn] body: {data}")
            return
        print(
            f"  [ok] start: success={data.get('success')} "
            f"complete={data.get('project_complete')} "
            f"run_token={str(data.get('run_token') or '')[:16]}..."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Test metadata-driven resume feature")
    parser.add_argument(
        "--parsehub-start",
        action="store_true",
        help="POST /api/projects/resume/start (starts a real ParseHub run)",
    )
    args = parser.parse_args()

    print("[test] Initializing services...")
    _initialize_services()

    pair = _row_project_with_metadata()
    if not pair:
        print(
            "[test] FAIL: No project with metadata found. "
            "Sync projects and ensure metadata rows exist."
        )
        return 1

    project_id, project_token = pair
    print(f"[test] Using projects.id={project_id} token={project_token[:12]}...")

    db = ParseHubDatabase()
    try:
        run_resolution_test(db, project_token, project_id)
        run_http_tests(project_token, project_id)
        run_negative_test(project_token)
        if args.parsehub_start:
            print("[test] --parsehub-start: calling ParseHub (real run may be created)...")
            run_parsehub_start(project_token, project_id)
        else:
            print(
                "[test] Skip POST /resume/start (no real ParseHub). "
                "Use --parsehub-start to exercise that path."
            )
    except AssertionError as e:
        print(f"[test] FAIL: {e}")
        return 1
    except Exception as e:
        print(f"[test] ERROR: {e}")
        raise

    print("[test] SUCCESS: metadata resume feature checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
