"""
Tests for metadata-driven resume checkpoint merging (why resume "restarts" at page 1).

`get_checkpoint` merges:
  - scraped_records MAX(source_page)
  - metadata.current_page_scraped
  - analytics_records (record_data JSON: source_page, page, URLs with ?page=)

If all are 0/empty, next_start_page stays 1 — that is the failure mode users describe as "didn't resume".

Run from backend:
  cd Parsehub_Snowflake/backend
  python -m unittest test_resume_checkpoint_diagnosis -v
  # or: pytest test_resume_checkpoint_diagnosis.py -v  (if pytest installed)
"""

from __future__ import annotations

import json
import os
import sys
import unittest

os.environ.setdefault("QUIET_SNOWFLAKE_DB_CONNECT_PRINT", "1")
from pathlib import Path
from typing import Any, List, Tuple
from unittest.mock import MagicMock

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from src.services.metadata_driven_resume_scraper import (  # noqa: E402
    MetadataDrivenResumeScraper,
    _max_page_from_record_dict,
)


def diagnose_checkpoint(cp: dict) -> str:
    """
    Human-readable explanation for QA / logs.
    next_start_page == 1 with highest_successful_page == 0 => will not resume (re-scrapes page 1).
    """
    h = int(cp.get("highest_successful_page") or 0)
    n = int(cp.get("next_start_page") or 1)
    tr = int(cp.get("total_persisted_records") or 0)
    if h == 0 and n == 1:
        return (
            "ISSUE: No checkpoint — merged progress is empty. "
            "Resume will target page 1. "
            "Fix: persist source_page in scraped_records, set metadata.current_page_scraped, "
            "or ensure analytics_records rows for this project_token include page fields (or any rows for heuristic)."
        )
    return (
        f"OK: highest_successful_page={h}, next_start_page={n}, "
        f"total_persisted_records={tr}"
    )


def _token_row(token: str) -> dict:
    return {"token": token}


def _scraped_row(highest_page: Any, total_count: int) -> dict:
    return {"highest_page": highest_page, "total_records": total_count}


def _meta_row(current_page: int) -> dict:
    return {"current_page_scraped": current_page}


def _analytics_rows_from_dicts(record_dicts: List[dict]) -> List[dict]:
    return [{"record_data": json.dumps(d)} for d in record_dicts]


def _patch_db_for_checkpoint(
    scraper: MetadataDrivenResumeScraper,
    *,
    project_token: str,
    scraped: Tuple[Any, int],
    meta_current: int,
    analytics_record_dicts: List[dict],
) -> None:
    """
    Mock connect/cursor/disconnect so get_checkpoint sees a deterministic DB state.
    fetchone order: projects.token, scraped MAX/COUNT, metadata.current_page_scraped.
    Then analytics SELECT uses fetchall.
    """
    mock_cursor = MagicMock()
    mock_cursor.fetchone.side_effect = [
        _token_row(project_token),
        _scraped_row(scraped[0], scraped[1]),
        _meta_row(meta_current),
    ]
    mock_cursor.fetchall.return_value = _analytics_rows_from_dicts(analytics_record_dicts)

    def cursor_factory():
        return mock_cursor

    scraper.db.connect = MagicMock()
    scraper.db.cursor = cursor_factory
    scraper.db.disconnect = MagicMock()


class TestResumeCheckpointMerging(unittest.TestCase):
    """Merged checkpoint: resume targets next_start_page = highest_successful_page + 1."""

    def setUp(self) -> None:
        os.environ.setdefault("PARSEHUB_API_KEY", "test-key-for-resume-tests")

    def test_scraped_records_only_source_page_1_resumes_at_page_2(self):
        scraper = MetadataDrivenResumeScraper()
        _patch_db_for_checkpoint(
            scraper,
            project_token="t_proj",
            scraped=(1, 77),
            meta_current=0,
            analytics_record_dicts=[],
        )
        cp = scraper.get_checkpoint(42)
        self.assertEqual(cp["highest_successful_page"], 1, cp)
        self.assertEqual(cp["next_start_page"], 2, cp)
        self.assertIn("OK", diagnose_checkpoint(cp))

    def test_metadata_current_page_only_resumes_next(self):
        scraper = MetadataDrivenResumeScraper()
        _patch_db_for_checkpoint(
            scraper,
            project_token="t_proj",
            scraped=(None, 0),
            meta_current=1,
            analytics_record_dicts=[],
        )
        cp = scraper.get_checkpoint(42)
        self.assertEqual(cp["highest_successful_page"], 1)
        self.assertEqual(cp["next_start_page"], 2)

    def test_analytics_source_page_1_resumes_at_page_2(self):
        scraper = MetadataDrivenResumeScraper()
        _patch_db_for_checkpoint(
            scraper,
            project_token="t_apac",
            scraped=(0, 0),
            meta_current=0,
            analytics_record_dicts=[{"source_page": 1, "title": "x"}],
        )
        cp = scraper.get_checkpoint(99)
        self.assertEqual(cp["highest_successful_page"], 1)
        self.assertEqual(cp["next_start_page"], 2)
        self.assertGreaterEqual(cp["total_persisted_records"], 1)

    def test_analytics_rows_but_no_page_fields_uses_heuristic_page_1(self):
        """Matches comment in get_checkpoint: product-only rows => assume page 1 completed."""
        scraper = MetadataDrivenResumeScraper()
        _patch_db_for_checkpoint(
            scraper,
            project_token="t_legacy",
            scraped=(0, 0),
            meta_current=0,
            analytics_record_dicts=[{"name": "product", "sku": "1"}],
        )
        cp = scraper.get_checkpoint(1)
        self.assertEqual(
            cp["highest_successful_page"],
            1,
            "With analytics rows but no page in JSON, checkpoint should assume page 1 "
            f"so next run is page 2. Got: {cp}",
        )
        self.assertEqual(cp["next_start_page"], 2)

    def test_failure_mode_no_data_anywhere_restarts_at_page_1(self):
        """This is the regression case: user sees 'did not resume' — next stays 1."""
        scraper = MetadataDrivenResumeScraper()
        _patch_db_for_checkpoint(
            scraper,
            project_token="t_empty",
            scraped=(None, 0),
            meta_current=0,
            analytics_record_dicts=[],
        )
        cp = scraper.get_checkpoint(7)
        self.assertEqual(cp["highest_successful_page"], 0)
        self.assertEqual(cp["next_start_page"], 1)
        diag = diagnose_checkpoint(cp)
        self.assertIn("ISSUE", diag)
        self.assertIn("No checkpoint", diag)

    def test_analytics_url_in_record_extracts_page(self):
        scraper = MetadataDrivenResumeScraper()
        _patch_db_for_checkpoint(
            scraper,
            project_token="t_url",
            scraped=(0, 0),
            meta_current=0,
            analytics_record_dicts=[
                {"url": "https://example.com/listing?page=2&foo=1"},
            ],
        )
        cp = scraper.get_checkpoint(3)
        self.assertEqual(cp["highest_successful_page"], 2)
        self.assertEqual(cp["next_start_page"], 3)

    def test_max_of_three_sources(self):
        scraper = MetadataDrivenResumeScraper()
        _patch_db_for_checkpoint(
            scraper,
            project_token="t_merge",
            scraped=(1, 10),
            meta_current=2,
            analytics_record_dicts=[{"source_page": 1}],
        )
        cp = scraper.get_checkpoint(1)
        self.assertEqual(cp["highest_successful_page"], 2)
        self.assertEqual(cp["next_start_page"], 3)


class TestMaxPageHelpers(unittest.TestCase):
    """Direct checks for page extraction from analytics-shaped dicts."""

    def test_max_page_from_nested_url(self):
        d = {"item": {"product_url": "https://shop.example.com/cat?page=3"}}
        self.assertEqual(_max_page_from_record_dict(d), 3)

    def test_max_page_from_source_page_key(self):
        self.assertEqual(_max_page_from_record_dict({"source_page": 2}), 2)


class TestGetCheckpointExceptionReturnsSafeDefault(unittest.TestCase):
    """If DB raises, API returns zeros — same symptom as 'no resume'."""

    def setUp(self) -> None:
        os.environ.setdefault("PARSEHUB_API_KEY", "test-key-for-resume-tests")

    def test_exception_returns_default_checkpoint(self):
        scraper = MetadataDrivenResumeScraper()
        scraper.db.connect = MagicMock()

        def broken_cursor():
            raise RuntimeError("snowflake down")

        scraper.db.cursor = broken_cursor
        scraper.db.disconnect = MagicMock()
        cp = scraper.get_checkpoint(1)
        self.assertEqual(cp["highest_successful_page"], 0)
        self.assertEqual(cp["next_start_page"], 1)
        self.assertIn("ISSUE", diagnose_checkpoint(cp))


if __name__ == "__main__":
    unittest.main()
