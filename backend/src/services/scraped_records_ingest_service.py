"""
Background worker queue for async inserts into scraped_records (+ scraped_data mirror).

POST /api/scraped-records/ingest enqueues jobs; a single daemon thread processes them
using ParseHubDatabase.insert_scraped_resume_batch (same schema as resume scraper).
"""

from __future__ import annotations

import logging
import queue
import threading
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_MAX_QUEUE = 5000
_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=_MAX_QUEUE)
_worker_started = False
_worker_lock = threading.Lock()
_stats_lock = threading.Lock()
_jobs_ok = 0
_jobs_err = 0


def _process_job(job: Dict[str, Any]) -> None:
    global _jobs_ok, _jobs_err
    from src.models.database import ParseHubDatabase

    job_id = job.get("job_id", "?")
    try:
        db = ParseHubDatabase()
        inserted, err = db.insert_scraped_resume_batch(
            project_id=int(job["project_id"]),
            run_token=str(job["run_token"]),
            source_page=int(job["source_page"]),
            records=job["records"],
            session_id=job.get("session_id"),
            mirror_scraped_data=bool(job.get("mirror_scraped_data", True)),
        )
        if err:
            logger.error(
                "[ingest] job %s finished with error: %s (inserted=%s)",
                job_id,
                err,
                inserted,
            )
            with _stats_lock:
                _jobs_err += 1
        else:
            logger.info(
                "[ingest] job %s ok: inserted=%s into scraped_records",
                job_id,
                inserted,
            )
            with _stats_lock:
                _jobs_ok += 1
    except Exception as exc:
        logger.error("[ingest] job %s crashed: %s", job_id, exc, exc_info=True)
        with _stats_lock:
            _jobs_err += 1


def _worker_loop() -> None:
    logger.info("[ingest] worker thread started")
    while True:
        try:
            job = _queue.get(timeout=1.0)
        except queue.Empty:
            continue
        try:
            _process_job(job)
        finally:
            _queue.task_done()


def start_scraped_records_ingest_worker() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        t = threading.Thread(
            target=_worker_loop,
            name="scraped-records-ingest",
            daemon=True,
        )
        t.start()
        _worker_started = True
        logger.info("[ingest] Scraped records ingest worker registered")


def enqueue_scraped_records_ingest(payload: Dict[str, Any]) -> str:
    """
    Enqueue a batch insert. payload must include:
      project_id, run_token, source_page, records (list of dicts)
    Optional: session_id, mirror_scraped_data (default True)
    """
    job_id = uuid.uuid4().hex
    item = dict(payload)
    item["job_id"] = job_id
    _queue.put(item, timeout=60)
    return job_id


def get_scraped_records_ingest_stats() -> Dict[str, Any]:
    with _stats_lock:
        ok = _jobs_ok
        err = _jobs_err
    return {
        "queue_depth": _queue.qsize(),
        "jobs_succeeded": ok,
        "jobs_failed": err,
        "worker_running": _worker_started,
        "max_queue": _MAX_QUEUE,
    }
