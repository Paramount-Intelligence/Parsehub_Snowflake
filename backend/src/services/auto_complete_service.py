"""
Auto-Complete Service for ParseHub Runs

Background service that automatically polls for run completion
and fetches/persists data without requiring frontend to stay open.

This ensures data is always saved to the database even if:
- User closes the browser
- Frontend times out
- Network interruption occurs
"""

import threading
import time
import logging
import traceback
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)

# In-memory store of active runs being monitored
# Format: {run_token: {project_id, project_token, starting_page, started_at, last_checked}}
_active_runs: Dict[str, dict] = {}
_run_history: deque = deque(maxlen=100)  # Last 100 completed runs

# Service thread
_service_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()

# Configuration
POLL_INTERVAL = 10  # Seconds between polls
MAX_RUN_TIME = 3600  # Max 1 hour per run


class AutoCompleteService:
    """
    Background service that automatically completes ParseHub runs.
    
    When a run is registered:
    1. Polls ParseHub for run status every 10 seconds
    2. When complete, fetches data from ParseHub
    3. Persists data to database with source_page tracking
    4. Updates checkpoint for resume capability
    5. Optionally continues to next page
    """
    
    def __init__(self):
        self.db = None
        self.scraper = None
        self._lock = threading.Lock()
    
    def set_database(self, db):
        """Link to database instance"""
        self.db = db
        
    def set_scraper(self, scraper):
        """Link to metadata-driven scraper"""
        from src.services.metadata_driven_resume_scraper import get_metadata_driven_scraper
        self.scraper = scraper or get_metadata_driven_scraper()
    
    def register_run(self, run_token: str, project_id: int, project_token: str, 
                     starting_page: int, auto_continue: bool = True) -> bool:
        """
        Register a new run for automatic completion monitoring
        
        Args:
            run_token: ParseHub run token
            project_id: Internal project ID
            project_token: ParseHub project token
            starting_page: Which page this run is scraping
            auto_continue: Whether to auto-start next page when complete
        
        Returns:
            bool: True if registered successfully
        """
        with self._lock:
            if run_token in _active_runs:
                logger.info(f"[AUTO-COMPLETE] Run {run_token[:8]}... already registered")
                return True
            
            _active_runs[run_token] = {
                'project_id': project_id,
                'project_token': project_token,
                'starting_page': starting_page,
                'auto_continue': auto_continue,
                'started_at': datetime.now(),
                'last_checked': datetime.now(),
                'status': 'monitoring',
                'attempts': 0
            }
            
            logger.info(f"[AUTO-COMPLETE] Registered run {run_token[:8]}... for page {starting_page}")
            return True
    
    def get_run_status(self, run_token: str) -> Optional[dict]:
        """Get current status of a monitored run"""
        with self._lock:
            return _active_runs.get(run_token)
    
    def get_active_runs(self) -> List[dict]:
        """Get list of all active runs"""
        with self._lock:
            return [
                {
                    'run_token': token,
                    **data
                }
                for token, data in _active_runs.items()
            ]
    
    def poll_and_complete_runs(self):
        """
        Poll all active runs and complete any that are finished
        Called by the background thread
        """
        if not self.scraper:
            from src.services.metadata_driven_resume_scraper import get_metadata_driven_scraper
            self.scraper = get_metadata_driven_scraper()
        
        with self._lock:
            # Copy to avoid modification during iteration
            runs_to_check = list(_active_runs.items())
        
        for run_token, run_data in runs_to_check:
            try:
                # Check if run has exceeded max time
                elapsed = (datetime.now() - run_data['started_at']).total_seconds()
                if elapsed > MAX_RUN_TIME:
                    logger.warning(f"[AUTO-COMPLETE] Run {run_token[:8]}... exceeded max time, removing")
                    with self._lock:
                        _active_runs.pop(run_token, None)
                        _run_history.append({
                            'run_token': run_token,
                            'status': 'timeout',
                            'error': 'Exceeded max run time',
                            'completed_at': datetime.now()
                        })
                    continue
                
                # Poll for completion
                logger.debug(f"[AUTO-COMPLETE] Polling run {run_token[:8]}...")
                poll_result = self.scraper.poll_run_completion(run_token)
                
                if not poll_result['success']:
                    # Run still in progress or error
                    if poll_result.get('status') in ['failed', 'cancelled', 'error']:
                        logger.error(f"[AUTO-COMPLETE] Run {run_token[:8]}... failed: {poll_result.get('error')}")
                        try:
                            if self.scraper and getattr(self.scraper, 'db', None):
                                self.scraper.db.mark_run_terminal(
                                    run_token, poll_result.get('status', 'failed'))
                        except Exception:
                            pass
                        with self._lock:
                            _active_runs.pop(run_token, None)
                            _run_history.append({
                                'run_token': run_token,
                                'status': 'failed',
                                'error': poll_result.get('error'),
                                'completed_at': datetime.now()
                            })
                    else:
                        # Still running - update last checked
                        with self._lock:
                            if run_token in _active_runs:
                                _active_runs[run_token]['last_checked'] = datetime.now()
                                _active_runs[run_token]['attempts'] += 1
                    continue
                
                # Run completed! Fetch and persist data
                logger.info(f"[AUTO-COMPLETE] Run {run_token[:8]}... completed, fetching data...")
                
                fetch_result = self.scraper.fetch_run_data(run_token)
                
                if not fetch_result['success']:
                    logger.error(f"[AUTO-COMPLETE] Failed to fetch data for {run_token[:8]}...: {fetch_result.get('error')}")
                    try:
                        if self.scraper and getattr(self.scraper, 'db', None):
                            self.scraper.db.mark_run_terminal(run_token, 'fetch_failed')
                    except Exception:
                        pass
                    with self._lock:
                        _active_runs.pop(run_token, None)
                        _run_history.append({
                            'run_token': run_token,
                            'status': 'fetch_failed',
                            'error': fetch_result.get('error'),
                            'completed_at': datetime.now()
                        })
                    continue
                
                # Persist data
                scraped_data = fetch_result['data']
                logger.info(f"[AUTO-COMPLETE] Fetched {len(scraped_data)} records, persisting...")
                logger.info(f"[AUTO-COMPLETE] project_id={run_data['project_id']} run_token={run_token[:12] if run_token else None}... starting_page={run_data['starting_page']}")
                
                # Log data sample for debugging
                if scraped_data and len(scraped_data) > 0:
                    sample = scraped_data[0] if isinstance(scraped_data[0], dict) else str(scraped_data[0])[:200]
                    logger.info(f"[AUTO-COMPLETE] Data sample: {sample}")
                    logger.info(f"[AUTO-COMPLETE] First 3 record types: {[type(r).__name__ for r in scraped_data[:3]]}")
                else:
                    logger.error(f"[AUTO-COMPLETE] WARNING: scraped_data is empty or None!")
                
                logger.info(f"[AUTO-COMPLETE] Calling persist_results...")
                persist_result = self.scraper.persist_results(
                    project_id=run_data['project_id'],
                    run_token=run_token,
                    data=scraped_data,
                    source_page=run_data['starting_page'],
                    session_id=None
                )
                
                success, inserted_count, highest_page = persist_result
                logger.info(f"[AUTO-COMPLETE] persist_results returned: success={success} inserted_count={inserted_count} highest_page={highest_page}")
                
                if success:
                    logger.info(f"[AUTO-COMPLETE] ✅ Persisted {inserted_count} records for page {run_data['starting_page']} (highest_page: {highest_page})")
                    try:
                        if self.scraper and getattr(self.scraper, 'db', None):
                            self.scraper.db.mark_run_terminal(
                                run_token, 'completed', records_count=inserted_count)
                    except Exception:
                        pass
                    
                    # Check if project is complete
                    metadata = self.scraper.get_project_metadata(run_data['project_id'])
                    is_complete, reason = self.scraper.is_project_complete(run_data['project_id'], metadata or {})

                    if is_complete:
                        self.scraper.mark_project_complete(run_data['project_id'])
                        logger.info(f"[AUTO-COMPLETE] Project {run_data['project_id']} is complete!")
                    else:
                        # AUTO-CONTINUE: Trigger next run if project not complete
                        logger.info(f"[AUTO-COMPLETE] Project {run_data['project_id']} not complete ({reason})")
                        logger.info(f"[AUTO-COMPLETE] Auto-continuing to next page...")

                        try:
                            # Get checkpoint to determine next page
                            checkpoint = self.scraper.get_checkpoint(run_data['project_id'])
                            next_page = checkpoint['next_start_page']
                            total_pages = metadata.get('total_pages', 0) if metadata else 0

                            logger.info(f"[AUTO-COMPLETE] Next page: {next_page}, Total pages: {total_pages}")

                            if next_page <= total_pages:
                                # Trigger next run using resume_or_start_scraping
                                resume_result = self.scraper.resume_or_start_scraping(
                                    project_id=run_data['project_id'],
                                    project_token=run_data['project_token']
                                )

                                if resume_result.get('success') and resume_result.get('run_token'):
                                    new_run_token = resume_result['run_token']
                                    logger.info(f"[AUTO-COMPLETE] ✅ Next run triggered: {new_run_token[:8]}... for page {next_page}")

                                    # Register the new run for monitoring
                                    with self._lock:
                                        _active_runs[new_run_token] = {
                                            'project_id': run_data['project_id'],
                                            'project_token': run_data['project_token'],
                                            'starting_page': next_page,
                                            'started_at': datetime.now(),
                                            'last_checked': datetime.now(),
                                            'attempts': 0
                                        }

                                    logger.info(f"[AUTO-COMPLETE] New run registered for monitoring: {new_run_token[:8]}...")
                                else:
                                    error_msg = resume_result.get('error', 'Unknown error')
                                    logger.error(f"[AUTO-COMPLETE] ❌ Failed to trigger next run: {error_msg}")
                            else:
                                logger.info(f"[AUTO-COMPLETE] Next page {next_page} exceeds total {total_pages}, not triggering")
                        except Exception as continue_err:
                            logger.error(f"[AUTO-COMPLETE] ❌ Error auto-continuing: {continue_err}")
                            logger.error(f"[AUTO-COMPLETE] Traceback: {traceback.format_exc()}")

                    # Remove completed run from active runs
                    with self._lock:
                        _active_runs.pop(run_token, None)
                else:
                    logger.error(f"[AUTO-COMPLETE] ❌ Failed to persist data for run {run_token[:8]}...")
                    with self._lock:
                        _run_history.append({
                            'run_token': run_token,
                            'status': 'persist_failed',
                            'error': 'Persistence returned False',
                            'completed_at': datetime.now()
                        })
                
            except Exception as e:
                logger.error(f"[AUTO-COMPLETE] Error processing run {run_token[:8]}...: {e}")
                with self._lock:
                    run_data = _active_runs.get(run_token)
                    if run_data:
                        run_data['attempts'] += 1
                        # Give up after 10 attempts
                        if run_data['attempts'] > 10:
                            _active_runs.pop(run_token, None)
                            _run_history.append({
                                'run_token': run_token,
                                'status': 'error',
                                'error': str(e),
                                'completed_at': datetime.now()
                            })


def _service_loop():
    """Background thread loop"""
    service = AutoCompleteService()
    
    while not _stop_event.is_set():
        try:
            service.poll_and_complete_runs()
        except Exception as e:
            logger.error(f"[AUTO-COMPLETE] Service loop error: {e}")
        
        # Wait before next poll
        _stop_event.wait(POLL_INTERVAL)


def start_auto_complete_service() -> AutoCompleteService:
    """Start the auto-complete background service"""
    global _service_thread, _stop_event
    
    if _service_thread is not None and _service_thread.is_alive():
        logger.info("[AUTO-COMPLETE] Service already running")
        return AutoCompleteService()
    
    _stop_event.clear()
    _service_thread = threading.Thread(target=_service_loop, daemon=True)
    _service_thread.start()
    
    logger.info("[AUTO-COMPLETE] Background service started")
    return AutoCompleteService()


def stop_auto_complete_service():
    """Stop the auto-complete background service"""
    global _service_thread, _stop_event
    
    _stop_event.set()
    if _service_thread:
        _service_thread.join(timeout=5)
    
    logger.info("[AUTO-COMPLETE] Background service stopped")


def get_auto_complete_service() -> Optional[AutoCompleteService]:
    """Get the current service instance if running"""
    if _service_thread is not None and _service_thread.is_alive():
        return AutoCompleteService()
    return None


def register_run_for_completion(run_token: str, project_id: int, project_token: str,
                                 starting_page: int, auto_continue: bool = True) -> bool:
    """
    Convenience function to register a run from other modules
    
    Usage:
        from src.services.auto_complete_service import register_run_for_completion
        register_run_for_completion('tRaF3uZQ6okz', 37, 't3GhXfO5a5Tf', 1)
    """
    service = get_auto_complete_service()
    if service:
        return service.register_run(run_token, project_id, project_token, starting_page, auto_continue)
    
    # If service not running, start it
    service = start_auto_complete_service()
    return service.register_run(run_token, project_id, project_token, starting_page, auto_continue)
