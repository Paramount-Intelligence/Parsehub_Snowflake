"""
Chunk Pagination Orchestrator
Orchestrates batch-based scraping using 10-page chunks with proper checkpoint management
Replaces ad-hoc incremental scraping with deterministic, resumable batch processing

Architecture:
1. Read checkpoint (last completed page from DB)
2. Generate next 10-page batch URLs
3. Trigger ParseHub with first URL of batch
4. Poll for completion
5. Fetch results
6. Store with source_page tracking
7. Update checkpoint (max source_page from batch)
8. Repeat until no more data

Key Features:
- Single ParseHub project per scraping session (no duplication)
- Backend owns batching logic
- Proper source_page tracking for deduplication
- Safe resume from checkpoint
- Idempotent batch processing
"""

import os
import sys
import json
import time
import re
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

root_dir = Path(__file__).parent.parent.parent  # backend/
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.models.database import ParseHubDatabase
from src.services.notification_service import get_notification_service

load_dotenv()

logger_module = __import__('logging')
logger = logger_module.getLogger(__name__)


class ChunkPaginationOrchestrator:
    """
    Manages batch-based (chunk) pagination for ParseHub scraping
    Each chunk = 10 pages worth of content from a website
    """
    
    CHUNK_SIZE = 10  # Pages per batch
    POLL_INTERVAL = 5  # Seconds between status checks
    MAX_POLL_ATTEMPTS = 360  # 30 minutes max wait (360 * 5sec)
    EMPTY_RESULT_THRESHOLD = 3  # Consecutive empty batches = done
    
    def __init__(self):
        self.db = ParseHubDatabase()
        self.api_key = os.getenv('PARSEHUB_API_KEY')
        self.base_url = os.getenv('PARSEHUB_BASE_URL', 'https://www.parsehub.com/api/v2')
        self.notification_service = get_notification_service()
        
        if not self.api_key:
            raise ValueError("PARSEHUB_API_KEY not configured")
    
    # ===== CHECKPOINT MANAGEMENT =====
    
    def get_checkpoint(self, project_id: int) -> Dict:
        """
        Get current checkpoint for a project
        
        Returns:
            {
                'last_completed_page': int,
                'total_pages': int,
                'next_start_page': int,
                'checkpoint_timestamp': str,
                'total_chunks_completed': int,
                'failed_chunks': int
            }
        """
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            # Get metadata
            cursor.execute('''
                SELECT current_page_scraped, total_pages, updated_date
                FROM metadata
                WHERE project_id = %s
                LIMIT 1
            ''', (project_id,))
            
            metadata = cursor.fetchone()
            if not metadata:
                logger.warning(f"[CHECKPOINT] No metadata for project {project_id}")
                return self._default_checkpoint()
            
            current_page = metadata.get('current_page_scraped', 0) if isinstance(metadata, dict) else metadata[0] or 0
            total_pages = metadata.get('total_pages', 0) if isinstance(metadata, dict) else metadata[1] or 0
            
            # Get batch completion stats from runs table
            cursor.execute('''
                SELECT COUNT(*) as total_runs,
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_runs,
                       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_runs
                FROM runs
                WHERE project_id = %s AND is_batch_run = TRUE
            ''', (project_id,))
            
            run_stats = cursor.fetchone()
            total_chunks = (run_stats.get('total_runs', 0) if isinstance(run_stats, dict) else run_stats[0] or 0) if run_stats else 0
            completed_chunks = (run_stats.get('completed_runs', 0) if isinstance(run_stats, dict) else run_stats[1] or 0) if run_stats else 0
            failed_chunks = (run_stats.get('failed_runs', 0) if isinstance(run_stats, dict) else run_stats[2] or 0) if run_stats else 0
            
            self.db.disconnect()
            
            return {
                'last_completed_page': current_page,
                'total_pages': total_pages,
                'next_start_page': current_page + 1,
                'checkpoint_timestamp': datetime.now().isoformat(),
                'total_chunks_completed': completed_chunks,
                'failed_chunks': failed_chunks
            }
        
        except Exception as e:
            logger.error(f"[CHECKPOINT] Error reading checkpoint: {e}")
            return self._default_checkpoint()
    
    def _default_checkpoint(self) -> Dict:
        """Default checkpoint at start"""
        return {
            'last_completed_page': 0,
            'total_pages': 0,
            'next_start_page': 1,
            'checkpoint_timestamp': datetime.now().isoformat(),
            'total_chunks_completed': 0,
            'failed_chunks': 0
        }
    
    def update_checkpoint(self, project_id: int, last_completed_page: int, 
                         metadata: Optional[Dict] = None) -> bool:
        """
        Update checkpoint after successful batch completion
        
        Args:
            project_id: Project ID
            last_completed_page: Highest page number successfully processed
            metadata: Optional metadata dict with additional info
        """
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            # Update metadata.current_page_scraped with highest completed page
            cursor.execute('''
                UPDATE metadata
                SET current_page_scraped = %s,
                    updated_date = %s
                WHERE project_id = %s
            ''', (last_completed_page, datetime.now(), project_id))
            
            conn.commit()
            self.db.disconnect()
            
            logger.info(f"[CHECKPOINT] Updated project {project_id}: page {last_completed_page}")
            return True
        
        except Exception as e:
            logger.error(f"[CHECKPOINT] Error updating checkpoint: {e}")
            try:
                conn.close()
            except:
                pass
            return False
    
    # ===== BATCH URL GENERATION =====
    
    def generate_batch_urls(self, base_url: str, start_page: int, 
                           pagination_pattern: Optional[str] = None) -> List[str]:
        """
        Generate URLs for next 10-page batch
        
        Args:
            base_url: Website base URL or starting URL with pagination parameter
            start_page: Page number to start from
            pagination_pattern: Optional pattern hint ('query_page', 'offset', 'path', etc.)
        
        Returns:
            List of 10 URLs for the batch
        """
        urls = []
        
        for page_offset in range(self.CHUNK_SIZE):
            page_num = start_page + page_offset
            url = self._generate_page_url(base_url, page_num, pagination_pattern)
            urls.append(url)
        
        logger.info(f"[BATCH_URLS] Generated {len(urls)} URLs: page {start_page}-{start_page + self.CHUNK_SIZE - 1}")
        return urls
    
    def _generate_page_url(self, base_url: str, page_num: int, 
                          pattern: Optional[str] = None) -> str:
        """
        Generate URL for specific page number
        Detects pagination pattern if not provided
        """
        if not pattern:
            pattern = self._detect_pagination_pattern(base_url)
        
        # Pattern 1: Query parameter ?page=X
        if pattern == 'query_page' or '?page=' in base_url or '&page=' in base_url:
            if '?page=' in base_url or '&page=' in base_url:
                return re.sub(r'([?&])page=\d+', rf'\1page={page_num}', base_url)
            elif '?' in base_url:
                return f"{base_url}&page={page_num}"
            else:
                return f"{base_url}?page={page_num}"
        
        # Pattern 2: Query parameter ?p=X
        elif pattern == 'query_p' or '?p=' in base_url or '&p=' in base_url:
            if '?p=' in base_url or '&p=' in base_url:
                return re.sub(r'([?&])p=\d+', rf'\1p={page_num}', base_url)
            elif '?' in base_url:
                return f"{base_url}&p={page_num}"
            else:
                return f"{base_url}?p={page_num}"
        
        # Pattern 3: Offset parameter ?offset=X (assume 20 items per page)
        elif pattern == 'offset' or '?offset=' in base_url or '&offset=' in base_url:
            offset = (page_num - 1) * 20
            if '?offset=' in base_url or '&offset=' in base_url:
                return re.sub(r'([?&])offset=\d+', rf'\1offset={offset}', base_url)
            elif '?' in base_url:
                return f"{base_url}&offset={offset}"
            else:
                return f"{base_url}?offset={offset}"
        
        # Pattern 4: Path-based /page/X/
        elif pattern == 'path_style' or '/page/' in base_url:
            if '/page/' in base_url:
                return re.sub(r'/page/\d+/', f'/page/{page_num}/', base_url)
            else:
                return f"{base_url}/page/{page_num}/"
        
        # Default: append ?page=X
        else:
            if '?' in base_url:
                return f"{base_url}&page={page_num}"
            else:
                return f"{base_url}?page={page_num}"
    
    def _detect_pagination_pattern(self, url: str) -> str:
        """Detect pagination pattern in URL"""
        if '?page=' in url or '&page=' in url:
            return 'query_page'
        elif '?p=' in url or '&p=' in url:
            return 'query_p'
        elif '?offset=' in url or '&offset=' in url:
            return 'offset'
        elif '/page/' in url:
            return 'path_style'
        else:
            return 'unknown'
    
    # ===== PARSEHU B RUN ORCHESTRATION =====
    
    def trigger_batch_run(self, project_token: str, start_url: str, 
                         batch_start_page: int, batch_end_page: int,
                         project_id: int = None, project_name: str = None) -> Dict:
        """
        Trigger a ParseHub run for a batch
        Uses the first URL of batch as start_url
        
        Args:
            project_token: ParseHub project token
            start_url: URL for first page of batch
            batch_start_page: Page number (for tracking)
            batch_end_page: End page number (for tracking)
            project_id: Project ID (for notifications)
            project_name: Project name (for notifications)
        
        Returns:
            {
                'success': bool,
                'run_token': str (if successful),
                'error': str (if failed)
            }
        """
        try:
            logger.info(f"[RUN] Triggering batch run: pages {batch_start_page}-{batch_end_page}")
            logger.info(f"[RUN] Start URL: {start_url}")
            
            # Trigger ParseHub run with pages limit to 10 (CHUNK_SIZE)
            params = {'api_key': self.api_key}
            run_data = {
                'start_url': start_url,
                'pages': self.CHUNK_SIZE  # Limit to 10 pages per batch
            }
            
            response = requests.post(
                f"{self.base_url}/projects/{project_token}/run",
                params=params,
                data=run_data
            )
            
            logger.info(f"[RUN] ParseHub API request with pages={self.CHUNK_SIZE}")
            
            if response.status_code != 200:
                error_msg = f"ParseHub API returned {response.status_code}: {response.text}"
                logger.error(f"[RUN] {error_msg}")
                
                # Send email notification
                if project_id and project_name and self.notification_service.is_enabled():
                    self.notification_service.send_api_failure_alert({
                        'project_id': project_id,
                        'project_name': project_name,
                        'error_type': 'http_error',
                        'error_message': error_msg,
                        'batch_info': {
                            'start_page': batch_start_page,
                            'end_page': batch_end_page,
                            'last_completed_page': batch_start_page - 1
                        },
                        'run_token': None,
                        'timestamp': datetime.now().isoformat(),
                        'retry_count': 0,
                        'max_retries': 3
                    })
                
                return {
                    'success': False,
                    'error': error_msg
                }
            
            data = response.json()
            run_token = data.get('run_token')
            
            if not run_token:
                error_msg = f"No run_token in response: {data}"
                logger.error(f"[RUN] {error_msg}")
                
                # Send email notification
                if project_id and project_name and self.notification_service.is_enabled():
                    self.notification_service.send_api_failure_alert({
                        'project_id': project_id,
                        'project_name': project_name,
                        'error_type': 'missing_run_token',
                        'error_message': error_msg,
                        'batch_info': {
                            'start_page': batch_start_page,
                            'end_page': batch_end_page,
                            'last_completed_page': batch_start_page - 1
                        },
                        'run_token': None,
                        'timestamp': datetime.now().isoformat(),
                        'retry_count': 0,
                        'max_retries': 1
                    })
                
                return {
                    'success': False,
                    'error': error_msg
                }
            
            logger.info(f"[RUN] Batch run started: {run_token}")
            
            return {
                'success': True,
                'run_token': run_token,
                'batch_start_page': batch_start_page,
                'batch_end_page': batch_end_page
            }
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[RUN] Exception triggering batch: {error_msg}")
            
            # Send email notification
            if project_id and project_name and self.notification_service.is_enabled():
                self.notification_service.send_api_failure_alert({
                    'project_id': project_id,
                    'project_name': project_name,
                    'error_type': 'exception',
                    'error_message': error_msg,
                    'batch_info': {
                        'start_page': batch_start_page,
                        'end_page': batch_end_page,
                        'last_completed_page': batch_start_page - 1
                    },
                    'run_token': None,
                    'timestamp': datetime.now().isoformat(),
                    'retry_count': 0,
                    'max_retries': 3
                })
            
            return {
                'success': False,
                'error': error_msg
            }
    
    # ===== RUN STATUS POLLING =====
    
    def poll_run_completion(self, run_token: str, max_attempts: Optional[int] = None,
                           project_id: int = None, project_name: str = None,
                           batch_start_page: int = None, batch_end_page: int = None) -> Dict:
        """
        Poll for run completion
        
        Args:
            run_token: ParseHub run token
            max_attempts: Max polling attempts
            project_id: Project ID (for notifications)
            project_name: Project name (for notifications)
            batch_start_page: Batch start page (for notifications)
            batch_end_page: Batch end page (for notifications)
        
        Returns:
            {
                'success': bool (true if completed),
                'status': str ('completed', 'running', 'cancelled', 'error'),
                'data_count': int (if successful),
                'error': str (if failed)
            }
        """
        if max_attempts is None:
            max_attempts = self.MAX_POLL_ATTEMPTS
        
        attempt = 0
        
        while attempt < max_attempts:
            try:
                response = requests.get(
                    f"{self.base_url}/runs/{run_token}",
                    params={'api_key': self.api_key}
                )
                
                if response.status_code != 200:
                    logger.warning(f"[POLL] API error: {response.status_code}")
                    attempt += 1
                    time.sleep(self.POLL_INTERVAL)
                    continue
                
                data = response.json()
                status = data.get('status')
                
                if status == 'completed':
                    data_count = len(data.get('data', []))
                    logger.info(f"[POLL] Run completed: {data_count} items")
                    return {
                        'success': True,
                        'status': 'completed',
                        'data_count': data_count
                    }
                
                elif status == 'cancelled':
                    logger.warning(f"[POLL] Run was cancelled")
                    
                    # Send email notification
                    if project_id and project_name and self.notification_service.is_enabled():
                        self.notification_service.send_api_failure_alert({
                            'project_id': project_id,
                            'project_name': project_name,
                            'error_type': 'run_cancelled',
                            'error_message': 'ParseHub run was cancelled',
                            'batch_info': {
                                'start_page': batch_start_page or 0,
                                'end_page': batch_end_page or 0,
                                'last_completed_page': (batch_start_page - 1) if batch_start_page else 0
                            },
                            'run_token': run_token,
                            'timestamp': datetime.now().isoformat(),
                            'retry_count': 0,
                            'max_retries': 1
                        })
                    
                    return {
                        'success': False,
                        'status': 'cancelled',
                        'error': 'Run was cancelled'
                    }
                
                elif status == 'error':
                    error = data.get('error', 'Unknown error')
                    logger.error(f"[POLL] Run error: {error}")
                    
                    # Send email notification
                    if project_id and project_name and self.notification_service.is_enabled():
                        self.notification_service.send_api_failure_alert({
                            'project_id': project_id,
                            'project_name': project_name,
                            'error_type': 'run_failed',
                            'error_message': f'ParseHub run failed: {error}',
                            'batch_info': {
                                'start_page': batch_start_page or 0,
                                'end_page': batch_end_page or 0,
                                'last_completed_page': (batch_start_page - 1) if batch_start_page else 0
                            },
                            'run_token': run_token,
                            'timestamp': datetime.now().isoformat(),
                            'retry_count': 0,
                            'max_retries': 1
                        })
                    
                    return {
                        'success': False,
                        'status': 'error',
                        'error': error
                    }
                
                # Still running
                attempt += 1
                if attempt % 12 == 0:  # Log every 60 seconds
                    logger.info(f"[POLL] Still running... (attempt {attempt}/{max_attempts})")
                
                time.sleep(self.POLL_INTERVAL)
            
            except Exception as e:
                logger.error(f"[POLL] Exception: {e}")
                attempt += 1
                time.sleep(self.POLL_INTERVAL)
        
        # Send timeout notification
        if project_id and project_name and self.notification_service.is_enabled():
            self.notification_service.send_api_failure_alert({
                'project_id': project_id,
                'project_name': project_name,
                'error_type': 'polling_timeout',
                'error_message': f'Run did not complete within {max_attempts * self.POLL_INTERVAL / 60:.0f} minutes',
                'batch_info': {
                    'start_page': batch_start_page or 0,
                    'end_page': batch_end_page or 0,
                    'last_completed_page': (batch_start_page - 1) if batch_start_page else 0
                },
                'run_token': run_token,
                'timestamp': datetime.now().isoformat(),
                'retry_count': max_attempts,
                'max_retries': max_attempts
            })
        
        return {
            'success': False,
            'status': 'timeout',
            'error': f'Run did not complete within {max_attempts * self.POLL_INTERVAL / 60:.0f} minutes'
        }
    
    # ===== DATA FETCHING & STORAGE =====
    
    def fetch_run_data(self, run_token: str) -> Optional[List[Dict]]:
        """
        Fetch data from completed run
        
        Returns:
            List of data items or None if error
        """
        try:
            response = requests.get(
                f"{self.base_url}/runs/{run_token}/data",
                params={'api_key': self.api_key}
            )
            
            if response.status_code != 200:
                logger.error(f"[DATA] Failed to fetch: {response.status_code}")
                return None
            
            data = response.json()
            
            # Handle different response formats
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                # Look for common data array keys
                for key in ['data', 'results', 'items', 'products', 'records']:
                    if key in data and isinstance(data[key], list):
                        items = data[key]
                        break
                else:
                    items = [data]  # Single item
            else:
                items = []
            
            logger.info(f"[DATA] Fetched {len(items)} items from run")
            return items
        
        except Exception as e:
            logger.error(f"[DATA] Exception fetching: {e}")
            return None
    
    def store_batch_results(self, project_id: int, project_token: str, 
                           run_token: str, batch_start_page: int, 
                           batch_end_page: int, items: List[Dict]) -> Dict:
        """
        Store batch results with source_page tracking
        
        Returns:
            {
                'success': bool,
                'stored_count': int,
                'duplicates_skipped': int,
                'max_source_page': int,
                'error': str
            }
        """
        if not items:
            logger.warning(f"[STORE] No items to store for batch {batch_start_page}-{batch_end_page}")
            return {
                'success': True,
                'stored_count': 0,
                'duplicates_skipped': 0,
                'max_source_page': batch_start_page - 1  # No progress
            }
        
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            stored_count = 0
            duplicate_count = 0
            max_page = batch_start_page - 1
            
            for item in items:
                try:
                    # Extract or infer source_page
                    source_page = item.get('source_page')
                    if not source_page:
                        # Infer from batch range (simple distribution)
                        idx = items.index(item)
                        source_page = batch_start_page + (idx // (len(items) // (batch_end_page - batch_start_page + 1)))
                    
                    source_page = int(source_page) if source_page else batch_start_page
                    source_page = min(source_page, batch_end_page)  # Cap at batch end
                    max_page = max(max_page, source_page)
                    
                    # Store item (implementation depends on project-specific schema)
                    # This is generic - adapt to your product_data table structure
                    cursor.execute('''
                        INSERT INTO product_data 
                        (project_id, project_token, run_token, source_page, 
                         raw_data, created_date)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (project_id, project_token, source_page, raw_data)
                        DO NOTHING
                    ''', (project_id, project_token, run_token, source_page, 
                          json.dumps(item), datetime.now()))
                    
                    if cursor.rowcount > 0:
                        stored_count += 1
                    else:
                        duplicate_count += 1
                
                except Exception as item_error:
                    logger.warning(f"[STORE] Skipping item: {item_error}")
                    continue
            
            conn.commit()
            self.db.disconnect()
            
            logger.info(f"[STORE] Stored {stored_count} items, skipped {duplicate_count} duplicates")
            
            return {
                'success': True,
                'stored_count': stored_count,
                'duplicates_skipped': duplicate_count,
                'max_source_page': max_page
            }
        
        except Exception as e:
            logger.error(f"[STORE] Exception storing results: {e}")
            try:
                conn.close()
            except:
                pass
            return {
                'success': False,
                'stored_count': 0,
                'duplicates_skipped': 0,
                'error': str(e)
            }
    
    # ===== MAIN ORCHESTRATION =====
    
    def run_scraping_batch_cycle(self, project_id: int, project_token: str, 
                                 base_url: str, project_name: str = None,
                                 max_batches: Optional[int] = None) -> Dict:
        """
        Run one complete batch cycle: checkpoint → generate URLs → run → poll → store → update checkpoint
        
        Args:
            project_id: Project ID
            project_token: ParseHub project token
            base_url: Base URL for pagination
            project_name: Project name (for notifications)
            max_batches: Limit batches to run (None = unlimited until empty)
        
        Returns:
            {
                'success': bool,
                'batches_completed': int,
                'total_items_stored': int,
                'total_pages_reached': int,
                'end_reason': str,
                'error': str (if failed)
            }
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"[BATCH_CYCLE] Starting: project {project_id} ({project_name or 'Unknown'})")
        logger.info(f"{'='*80}")
        
        batches_completed = 0
        total_stored = 0
        empty_batch_count = 0
        max_page_reached = 0
        end_reason = None
        last_checkpoint = None
        
        try:
            while True:
                # Check limits
                if max_batches and batches_completed >= max_batches:
                    end_reason = f"Reached max batches limit ({max_batches})"
                    logger.info(f"[BATCH_CYCLE] {end_reason}")
                    break
                
                # Get checkpoint
                checkpoint = self.get_checkpoint(project_id)
                start_page = checkpoint['next_start_page']
                last_checkpoint = checkpoint
                
                logger.info(f"\n[BATCH {batches_completed + 1}] Starting page: {start_page}")
                
                # Generate batch URLs
                batch_urls = self.generate_batch_urls(base_url, start_page)
                batch_start_page = start_page
                batch_end_page = start_page + self.CHUNK_SIZE - 1
                
                # Trigger run
                run_result = self.trigger_batch_run(
                    project_token, batch_urls[0], batch_start_page, batch_end_page,
                    project_id=project_id, project_name=project_name
                )
                
                if not run_result['success']:
                    logger.error(f"[BATCH_CYCLE] Failed to trigger run: {run_result.get('error')}")
                    return {
                        'success': False,
                        'batches_completed': batches_completed,
                        'total_items_stored': total_stored,
                        'total_pages_reached': max_page_reached,
                        'error': run_result.get('error')
                    }
                
                run_token = run_result['run_token']
                
                # Poll for completion
                poll_result = self.poll_run_completion(
                    run_token,
                    project_id=project_id, project_name=project_name,
                    batch_start_page=batch_start_page, batch_end_page=batch_end_page
                )
                
                if not poll_result['success']:
                    logger.error(f"[BATCH_CYCLE] Run failed: {poll_result.get('error')}")
                    return {
                        'success': False,
                        'batches_completed': batches_completed,
                        'total_items_stored': total_stored,
                        'total_pages_reached': max_page_reached,
                        'error': poll_result.get('error')
                    }
                
                # Fetch data
                items = self.fetch_run_data(run_token)
                
                if items is None:
                    logger.error(f"[BATCH_CYCLE] Failed to fetch data")
                    
                    # Send email notification for data fetch failure
                    if project_name and self.notification_service.is_enabled():
                        self.notification_service.send_api_failure_alert({
                            'project_id': project_id,
                            'project_name': project_name,
                            'error_type': 'data_fetch_failed',
                            'error_message': 'Failed to fetch run results data from ParseHub',
                            'batch_info': {
                                'start_page': batch_start_page,
                                'end_page': batch_end_page,
                                'last_completed_page': max_page_reached
                            },
                            'run_token': run_token,
                            'timestamp': datetime.now().isoformat(),
                            'retry_count': 1,
                            'max_retries': 1
                        })
                    
                    return {
                        'success': False,
                        'batches_completed': batches_completed,
                        'total_items_stored': total_stored,
                        'total_pages_reached': max_page_reached,
                        'error': 'Failed to fetch run data'
                    }
                
                # Check for empty results
                if len(items) == 0:
                    empty_batch_count += 1
                    logger.info(f"[BATCH_CYCLE] Empty batch #{empty_batch_count}")
                    
                    if empty_batch_count >= self.EMPTY_RESULT_THRESHOLD:
                        end_reason = f"No data returned for {empty_batch_count} consecutive batches"
                        logger.info(f"[BATCH_CYCLE] {end_reason} - stopping")
                        
                        # Send stalled scraping alert
                        if project_name and self.notification_service.is_enabled():
                            self.notification_service.send_scraping_stalled_alert({
                                'project_id': project_id,
                                'project_name': project_name,
                                'last_completed_page': max_page_reached,
                                'consecutive_empty_batches': empty_batch_count,
                                'time_stalled_minutes': batches_completed * 5,  # Approximate
                                'last_run_token': run_token,
                                'timestamp': datetime.now().isoformat()
                            })
                        
                        break
                else:
                    empty_batch_count = 0  # Reset counter on non-empty batch
                
                # Store results
                store_result = self.store_batch_results(
                    project_id, project_token, run_token,
                    batch_start_page, batch_end_page, items
                )
                
                if not store_result['success']:
                    logger.error(f"[BATCH_CYCLE] Failed to store: {store_result.get('error')}")
                    
                    # Send email notification for storage failure
                    if project_name and self.notification_service.is_enabled():
                        self.notification_service.send_api_failure_alert({
                            'project_id': project_id,
                            'project_name': project_name,
                            'error_type': 'storage_failed',
                            'error_message': f"Failed to store batch results: {store_result.get('error')}",
                            'batch_info': {
                                'start_page': batch_start_page,
                                'end_page': batch_end_page,
                                'last_completed_page': max_page_reached
                            },
                            'run_token': run_token,
                            'timestamp': datetime.now().isoformat(),
                            'retry_count': 1,
                            'max_retries': 1
                        })
                    
                    return {
                        'success': False,
                        'batches_completed': batches_completed,
                        'total_items_stored': total_stored,
                        'total_pages_reached': max_page_reached,
                        'error': store_result.get('error')
                    }
                
                stored = store_result['stored_count']
                dup_skipped = store_result['duplicates_skipped']
                max_page_from_batch = store_result['max_source_page']
                max_page_reached = max(max_page_reached, max_page_from_batch)
                
                total_stored += stored
                
                logger.info(f"[BATCH {batches_completed + 1}] Results: {stored} stored, {dup_skipped} duplicates")
                logger.info(f"[BATCH {batches_completed + 1}] Max page reached: {max_page_from_batch}")
                
                # Update checkpoint
                if not self.update_checkpoint(project_id, max_page_from_batch):
                    logger.error(f"[BATCH_CYCLE] Failed to update checkpoint")
                    # Don't fail entirely, but continue with caution
                
                batches_completed += 1
                logger.info(f"[BATCH {batches_completed}] Complete")
            
            # Success
            if not end_reason:
                end_reason = "Completed normally"
            
            logger.info(f"\n[BATCH_CYCLE] Finished: {batches_completed} batches, {total_stored} items stored")
            logger.info(f"[BATCH_CYCLE] Reason: {end_reason}")
            logger.info(f"{'='*80}\n")
            
            return {
                'success': True,
                'batches_completed': batches_completed,
                'total_items_stored': total_stored,
                'total_pages_reached': max_page_reached,
                'end_reason': end_reason
            }
        
        except Exception as e:
            logger.error(f"[BATCH_CYCLE] Fatal exception: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Send email notification for fatal error
            if project_name and self.notification_service.is_enabled():
                self.notification_service.send_api_failure_alert({
                    'project_id': project_id,
                    'project_name': project_name,
                    'error_type': 'fatal_exception',
                    'error_message': f"Fatal error in batch cycle: {str(e)}",
                    'batch_info': {
                        'start_page': 0,
                        'end_page': 0,
                        'last_completed_page': max_page_reached
                    },
                    'run_token': None,
                    'timestamp': datetime.now().isoformat(),
                    'retry_count': 0,
                    'max_retries': 0
                })
            
            return {
                'success': False,
                'batches_completed': batches_completed,
                'total_items_stored': total_stored,
                'total_pages_reached': max_page_reached,
                'error': str(e)
            }
