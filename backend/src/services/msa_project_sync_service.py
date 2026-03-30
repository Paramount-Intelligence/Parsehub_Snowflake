"""
MSA Project Sync Service  (v2 — production hardened)
=====================================================
Concurrently fetches ParseHub projects via dynamic queue-based pagination,
upserts them sequentially into Snowflake, and returns only projects whose
title starts with "(MSA Pricing)".

This is an ISOLATED service — it does NOT modify or interact with
existing sync/fetch services (auto_sync_service, fetch_projects, etc.).

Design decisions
----------------
* Fetch  → concurrent  (ThreadPoolExecutor, max 5 workers)
* Write  → sequential  (single MERGE loop, never concurrent)
* Pagination → queue-driven; a page is only requested when the previous
               one proved non-empty, preventing over-fetching and handling
               a stale total_projects counter from ParseHub.
"""

import os
import logging
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from typing import Any, Dict, List, Tuple

import requests

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
PARSEHUB_PAGE_SIZE = 20      # ParseHub returns up to 20 projects per page
MAX_WORKERS        = 5       # concurrent fetch threads
FETCH_TIMEOUT      = 15      # seconds per API call
RETRY_DELAY        = 2       # seconds between retries on 429/5xx
MAX_RETRIES        = 1       # one automatic retry per page
UPSERT_BATCH_SIZE  = 50      # projects per MERGE statement
MSA_TITLE_PREFIX   = "(msa pricing)"   # compared lower-stripped


# ─────────────────────────────────────────────────────────────────────────────
# Section 1 — ParseHub concurrent fetch (queue-based pagination)
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_page(base_url: str, api_key: str, offset: int) -> Tuple[int, List[Dict]]:
    """
    Fetch one page of ParseHub projects.

    Returns (offset, projects_list).  On failure returns (offset, []).
    Retries once on 429 / 5xx with a short delay.
    """
    url = f"{base_url}/projects"
    params = {"api_key": api_key, "offset": offset}

    for attempt in range(1 + MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=FETCH_TIMEOUT)

            if resp.status_code == 200:
                projects = resp.json().get("projects", [])
                logger.debug("[MSA-Sync] offset=%d → %d projects", offset, len(projects))
                return offset, projects

            if resp.status_code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                logger.warning(
                    "[MSA-Sync] HTTP %d at offset=%d — retry in %ds",
                    resp.status_code, offset, RETRY_DELAY,
                )
                time.sleep(RETRY_DELAY)
                continue

            logger.error("[MSA-Sync] HTTP %d at offset=%d — giving up", resp.status_code, offset)
            return offset, []

        except requests.Timeout:
            if attempt < MAX_RETRIES:
                logger.warning("[MSA-Sync] Timeout at offset=%d — retrying", offset)
                time.sleep(RETRY_DELAY)
                continue
            logger.error("[MSA-Sync] Timeout at offset=%d — giving up", offset)
            return offset, []

        except requests.RequestException as exc:
            if attempt < MAX_RETRIES:
                logger.warning("[MSA-Sync] Network error at offset=%d (%s) — retrying", offset, exc)
                time.sleep(RETRY_DELAY)
                continue
            logger.error("[MSA-Sync] Network error at offset=%d: %s", offset, exc)
            return offset, []

    return offset, []


def fetch_all_projects_concurrent(api_key: str) -> Tuple[List[Dict], bool]:
    """
    Fetch every ParseHub project using dynamic queue-based pagination.

    Algorithm
    ---------
    1. Seed a work-queue with offset=0.
    2. Up to MAX_WORKERS threads each pop an offset, fetch the page, and—
       if the page is non-empty—push ``offset + PAGE_SIZE`` back.
    3. The queue drains naturally when a page returns 0 projects.
    4. All tokens are deduplicated via a lock-protected dict.

    Returns (all_projects, had_partial_failure).
    """
    base_url = os.getenv("PARSEHUB_API_SITE", "https://www.parsehub.com/api/v2")

    offset_queue: "queue.Queue[int]" = queue.Queue()
    offset_queue.put(0)

    seen: Dict[str, Dict] = {}
    seen_lock = threading.Lock()
    visited_offsets: set = set()
    visited_lock = threading.Lock()
    had_failure = False
    failure_lock = threading.Lock()

    # Sentinel: track how many workers are currently active
    active_workers = threading.Semaphore(0)

    def worker_task(offset: int) -> None:
        nonlocal had_failure
        try:
            _, projects = _fetch_page(base_url, api_key, offset)

            if projects:
                # Enqueue next page — but only if not already visited
                next_offset = offset + PARSEHUB_PAGE_SIZE
                with visited_lock:
                    if next_offset not in visited_offsets:
                        visited_offsets.add(next_offset)
                        offset_queue.put(next_offset)

                with seen_lock:
                    for p in projects:
                        token = p.get("token")
                        if token:
                            seen[token] = p
            # else: page was empty — no next offset pushed, queue drains
        except Exception as exc:
            logger.error("[MSA-Sync] Worker exception at offset=%d: %s", offset, exc)
            with failure_lock:
                had_failure = True

    # Mark offset 0 as visited so it cannot be re-queued
    visited_offsets.add(0)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        pending: "Dict[Future, int]" = {}

        # Drain the queue: keep feeding workers as long as there are offsets
        # or in-flight futures that might push more offsets.
        while True:
            # Submit all currently queued offsets
            while True:
                try:
                    off = offset_queue.get_nowait()
                except queue.Empty:
                    break
                future = executor.submit(worker_task, off)
                pending[future] = off

            if not pending:
                break  # No in-flight work and queue is empty → done

            # Wait for at least one future to finish, then loop to
            # check if it enqueued more offsets
            done_futures = []
            # Block until at least one future completes
            for f in list(pending):
                if f.done():
                    done_futures.append(f)
            if not done_futures:
                # None done yet — wait for the next one
                import concurrent.futures
                done_set, _ = concurrent.futures.wait(
                    list(pending), return_when=concurrent.futures.FIRST_COMPLETED
                )
                done_futures = list(done_set)

            for f in done_futures:
                try:
                    f.result()
                except Exception as exc:
                    logger.error("[MSA-Sync] Future error: %s", exc)
                    with failure_lock:
                        had_failure = True
                del pending[f]

    all_projects = list(seen.values())
    logger.info(
        "[MSA-Sync] Fetch complete: %d unique projects, partial_failure=%s",
        len(all_projects), had_failure,
    )
    return all_projects, had_failure


# ─────────────────────────────────────────────────────────────────────────────
# Section 2 — Snowflake sequential batched UPSERT (never concurrent)
# ─────────────────────────────────────────────────────────────────────────────

def upsert_projects_to_snowflake(db, projects: List[Dict]) -> Dict[str, Any]:
    """
    Sequentially batch-upsert projects into Snowflake using MERGE INTO.

    IMPORTANT: This function is NEVER called concurrently.  All DB writes
    happen on the single thread that calls sync_msa_projects(), preventing
    any contention or transaction conflicts.

    Processes in chunks of UPSERT_BATCH_SIZE (default 50).
    Returns { success, upserted, batches_failed }.
    """
    if not projects:
        return {"success": True, "upserted": 0, "batches_failed": 0}

    total_upserted = 0
    batches_failed = 0

    try:
        conn = db.connect()
        cursor = db.cursor()

        for batch_start in range(0, len(projects), UPSERT_BATCH_SIZE):
            batch = projects[batch_start: batch_start + UPSERT_BATCH_SIZE]

            value_rows: List[str] = []
            params: List[Any] = []

            for p in batch:
                token = p.get("token")
                if not token:
                    continue
                title      = (p.get("title") or p.get("name", "")).strip()
                owner_email = (p.get("owner_email") or "").strip()
                main_site  = (p.get("main_site") or "").strip()
                value_rows.append("(%s, %s, %s, %s)")
                params.extend([token, title, owner_email, main_site])

            if not value_rows:
                continue

            values_sql = ", ".join(value_rows)
            merge_sql = f"""
                MERGE INTO projects AS tgt
                USING (
                    SELECT
                        column1 AS token,
                        column2 AS title,
                        column3 AS owner_email,
                        column4 AS main_site
                    FROM VALUES {values_sql}
                ) AS src
                ON tgt.token = src.token
                WHEN MATCHED THEN UPDATE SET
                    tgt.title       = src.title,
                    tgt.owner_email = src.owner_email,
                    tgt.main_site   = src.main_site,
                    tgt.updated_at  = CURRENT_TIMESTAMP()
                WHEN NOT MATCHED THEN INSERT
                    (token, title, owner_email, main_site, updated_at)
                    VALUES (src.token, src.title, src.owner_email,
                            src.main_site, CURRENT_TIMESTAMP())
            """

            try:
                cursor.execute(merge_sql, params)
                total_upserted += len(value_rows)
            except Exception as batch_exc:
                batches_failed += 1
                logger.error(
                    "[MSA-Sync] MERGE batch failed (start=%d, size=%d): %s",
                    batch_start, len(value_rows), batch_exc,
                )
                # Continue — partial upsert is acceptable

        conn.commit()
        logger.info(
            "[MSA-Sync] Snowflake upsert done: %d rows, %d batch(es) failed",
            total_upserted, batches_failed,
        )
        return {"success": True, "upserted": total_upserted, "batches_failed": batches_failed}

    except Exception as exc:
        logger.error("[MSA-Sync] Snowflake connection/commit error: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "upserted": total_upserted,
            "batches_failed": batches_failed,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Section 3 — Data normalisation
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_project(p: Dict) -> Dict[str, Any]:
    """Normalize a raw ParseHub project dict to a clean frontend-ready shape."""
    last_run_raw = p.get("last_run")
    last_run = None
    if last_run_raw and isinstance(last_run_raw, dict):
        last_run = {
            "status":     last_run_raw.get("status", "unknown"),
            "pages":      last_run_raw.get("pages", 0),
            "start_time": last_run_raw.get("start_time", ""),
            "run_token":  last_run_raw.get("run_token", ""),
        }

    return {
        "token":       p.get("token", ""),
        "title":       (p.get("title") or p.get("name", "")).strip(),
        "main_site":   (p.get("main_site") or "").strip(),
        "owner_email": (p.get("owner_email") or "").strip(),
        "created_at":  p.get("created_at", ""),
        "last_run":    last_run,
    }


def _is_msa_project(p: Dict) -> bool:
    """Return True when the project title matches the MSA Pricing prefix (case-insensitive)."""
    title = (p.get("title") or p.get("name", "")).strip().lower()
    return title.startswith(MSA_TITLE_PREFIX)


# ─────────────────────────────────────────────────────────────────────────────
# Section 4 — Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def sync_msa_projects(api_key: str, db) -> Dict[str, Any]:
    """
    End-to-end MSA project sync pipeline.

    Steps
    -----
    1. Concurrent ParseHub fetch via dynamic queue-based pagination
    2. Sequential batched MERGE INTO Snowflake
    3. Case-insensitive ``(MSA Pricing)`` filter
    4. Return normalised project list with standardised response schema

    Response schema
    ---------------
    {
        "success":         bool,
        "count":           int,     # MSA projects returned
        "total_fetched":   int,     # all projects fetched from ParseHub
        "partial_failure": bool,    # True if any fetch worker failed
        "error":           str|null,
        "projects":        list
    }
    """
    logger.info("[MSA-Sync] ── Pipeline start ──────────────────────────────")
    t0 = time.time()
    partial_failure = False
    top_level_error: str | None = None

    # ── 1. Fetch ──────────────────────────────────────────────────────────────
    try:
        all_projects, partial_failure = fetch_all_projects_concurrent(api_key)
    except Exception as exc:
        logger.error("[MSA-Sync] Fetch phase crashed: %s", exc)
        return {
            "success":         False,
            "count":           0,
            "total_fetched":   0,
            "partial_failure": True,
            "error":           str(exc),
            "projects":        [],
        }

    fetch_time = time.time() - t0
    logger.info("[MSA-Sync] Fetch: %d projects in %.1fs", len(all_projects), fetch_time)

    if not all_projects:
        logger.warning("[MSA-Sync] No projects returned from ParseHub")
        return {
            "success":         True,
            "count":           0,
            "total_fetched":   0,
            "partial_failure": partial_failure,
            "error":           None,
            "projects":        [],
        }

    # ── 2. Upsert (sequential, never concurrent) ─────────────────────────────
    try:
        upsert_result = upsert_projects_to_snowflake(db, all_projects)
        if not upsert_result.get("success"):
            top_level_error = upsert_result.get("error")
            partial_failure = True
    except Exception as exc:
        logger.error("[MSA-Sync] Upsert phase crashed: %s", exc)
        top_level_error = str(exc)
        partial_failure = True
        upsert_result = {"success": False, "upserted": 0, "batches_failed": 0}

    upsert_time = time.time() - t0 - fetch_time
    logger.info("[MSA-Sync] Upsert: %.1fs — %s", upsert_time, upsert_result)

    # ── 3. Filter (case-insensitive, strips whitespace) ───────────────────────
    msa_projects = [_normalize_project(p) for p in all_projects if _is_msa_project(p)]

    total_time = time.time() - t0
    logger.info(
        "[MSA-Sync] ── Done in %.1fs: %d/%d MSA, partial_failure=%s ──────────",
        total_time, len(msa_projects), len(all_projects), partial_failure,
    )

    return {
        "success":         True,
        "count":           len(msa_projects),
        "total_fetched":   len(all_projects),
        "partial_failure": partial_failure,
        "error":           top_level_error,
        "projects":        msa_projects,
    }
