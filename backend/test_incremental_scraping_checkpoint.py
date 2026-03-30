"""
Unit tests: incremental_scraping_manager.check_and_match_pages uses merged checkpoint
(get_metadata_driven_scraper().get_checkpoint) so next page matches /resume/checkpoint,
not only metadata.current_page_scraped.

Run:
  cd Parsehub_Snowflake/backend
  python -m unittest test_incremental_scraping_checkpoint -v
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

os.environ.setdefault("QUIET_SNOWFLAKE_DB_CONNECT_PRINT", "1")
os.environ.setdefault("PARSEHUB_API_KEY", os.environ.get("PARSEHUB_API_KEY", "test-key-incremental"))

from src.services.incremental_scraping_manager import IncrementalScrapingManager  # noqa: E402


class TestIncrementalScrapingMergedCheckpoint(unittest.TestCase):
    """Merged checkpoint drives start_page and pages_to_scrape."""

    def _one_project_rows(self):
        return [
            {
                "id": 1,
                "token": "tExampleToken12",
                "total_pages": 3,
                "current_page_scraped": 0,
                "project_name": "Test listing",
            }
        ]

    @patch.object(IncrementalScrapingManager, "trigger_continuation_run")
    @patch.object(IncrementalScrapingManager, "_sum_completed_pages_for_project", return_value=0)
    @patch("src.services.incremental_scraping_manager.get_metadata_driven_scraper")
    def test_checkpoint_next_page_2_when_metadata_still_zero(
        self, mock_get_scraper, _mock_sum, mock_trigger
    ):
        """
        Regression: metadata.current_page_scraped=0 but analytics/scraped already
        completed page 1 → must schedule start_page=2, not 1.
        """
        mock_scraper = MagicMock()
        mock_scraper.get_checkpoint.return_value = {
            "highest_successful_page": 1,
            "next_start_page": 2,
            "total_persisted_records": 77,
        }
        mock_get_scraper.return_value = mock_scraper
        mock_trigger.return_value = {"success": True, "run_token": "runTok"}

        mgr = IncrementalScrapingManager()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = self._one_project_rows()
        mgr.db = MagicMock()
        mgr.db.cursor.return_value = mock_cursor
        mgr.db.connect = MagicMock()
        mgr.db.disconnect = MagicMock()

        out = mgr.check_and_match_pages()

        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["start_page"], 2)
        mock_trigger.assert_called_once()
        call_kw = mock_trigger.call_args[1]
        self.assertEqual(call_kw["start_page"], 2)
        self.assertEqual(call_kw["pages_to_scrape"], 2)  # 3 - 1
        self.assertEqual(call_kw["project_id"], 1)

    @patch.object(IncrementalScrapingManager, "trigger_continuation_run")
    @patch.object(IncrementalScrapingManager, "_sum_completed_pages_for_project", return_value=0)
    @patch("src.services.incremental_scraping_manager.get_metadata_driven_scraper")
    def test_no_schedule_when_merged_checkpoint_complete(
        self, mock_get_scraper, _mock_sum, mock_trigger
    ):
        mock_scraper = MagicMock()
        mock_scraper.get_checkpoint.return_value = {
            "highest_successful_page": 3,
            "next_start_page": 4,
            "total_persisted_records": 100,
        }
        mock_get_scraper.return_value = mock_scraper

        mgr = IncrementalScrapingManager()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = self._one_project_rows()
        mgr.db = MagicMock()
        mgr.db.cursor.return_value = mock_cursor
        mgr.db.connect = MagicMock()
        mgr.db.disconnect = MagicMock()

        out = mgr.check_and_match_pages()

        mock_trigger.assert_not_called()
        self.assertEqual(out, [])

    @patch.object(IncrementalScrapingManager, "trigger_continuation_run")
    @patch.object(IncrementalScrapingManager, "_sum_completed_pages_for_project", return_value=0)
    @patch("src.services.incremental_scraping_manager.get_metadata_driven_scraper")
    def test_get_checkpoint_failure_falls_back_to_metadata(
        self, mock_get_scraper, _mock_sum, mock_trigger
    ):
        mock_get_scraper.side_effect = RuntimeError("checkpoint unavailable")
        mock_trigger.return_value = {"success": True, "run_token": "runTok"}

        mgr = IncrementalScrapingManager()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = self._one_project_rows()
        mgr.db = MagicMock()
        mgr.db.cursor.return_value = mock_cursor
        mgr.db.connect = MagicMock()
        mgr.db.disconnect = MagicMock()

        mgr.check_and_match_pages()

        mock_trigger.assert_called_once()
        call_kw = mock_trigger.call_args[1]
        self.assertEqual(call_kw["start_page"], 1)
        self.assertEqual(call_kw["pages_to_scrape"], 3)


if __name__ == "__main__":
    unittest.main()
