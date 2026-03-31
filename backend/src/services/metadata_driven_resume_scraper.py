"""
Metadata-Driven Resume Scraper
Orchestrates ParseHub scraping using metadata to drive pagination

Architecture:
1. Read metadata: base_url, total_pages, total_products
2. Read checkpoint: highest_successful_page from persisted data
3. Generate next page URL from highest_successful_page + 1
4. Trigger ParseHub run with generated URL
5. Fetch and persist results with source_page tracking
6. Update checkpoint: compute MAX(source_page) from newly persisted records
7. Compare highest_successful_page with total_pages
8. If complete, mark project done. Otherwise, continue from next page.
9. On critical failure, send email notification.

Key design principles:
- Checkpoint = MAX(source_page) from successfully persisted records (not "last batch")
- Each record must have source_page to track which website page it came from
- Single ParseHub project for all runs (no project duplication)
- Backend owns all pagination logic
- Email notifications for critical failures only
"""

import os
import sys
import json
import time
import re
import requests
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
import logging

root_dir = Path(__file__).parent.parent.parent  # backend/
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.models.database import ParseHubDatabase
from src.services.notification_service import get_notification_service
from src.services.pagination_service import PaginationService

load_dotenv()

logger = logging.getLogger(__name__)


def _coerce_int(val, default: int = 0) -> int:
    """Snowflake/drivers may return numbers as str; normalize for comparisons and arithmetic."""
    if val is None:
        return default
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    try:
        s = str(val).strip()
        if not s:
            return default
        return int(float(s))
    except (ValueError, TypeError, OverflowError):
        return default


# Lazy: PaginationService only wraps regex helpers (no DB connect on extract_page_number)
_pagination_url_pages = PaginationService()


def _parse_record_data_blob(raw) -> Optional[dict]:
    """analytics_records.record_data may be JSON text or a dict (e.g. VARIANT)."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else None
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
    return None


def _max_page_from_record_dict(record: dict, depth: int = 0) -> int:
    """
    Best-effort page number from one analytics / ParseHub row.
    Checks common keys and URL fields, then shallow-recurses into nested dicts/lists.
    """
    if not isinstance(record, dict) or depth > 6:
        return 0

    key_candidates = (
        'source_page',
        'page_number',
        'page',
        'Page',
        'current_page',
        'listing_page',
        'scraped_page',
    )
    best = 0
    for k in key_candidates:
        if k in record:
            best = max(best, _coerce_int(record.get(k), 0))

    for uk in ('url', 'product_url', 'link', 'page_url', 'listing_url', 'href'):
        u = record.get(uk)
        if isinstance(u, str) and u.strip():
            best = max(best, _pagination_url_pages.extract_page_number(u))

    for v in record.values():
        if isinstance(v, dict):
            best = max(best, _max_page_from_record_dict(v, depth + 1))
        elif isinstance(v, list) and depth < 4:
            for item in v:
                if isinstance(item, dict):
                    best = max(best, _max_page_from_record_dict(item, depth + 1))
    return best


def _analytics_checkpoint_for_token(cursor, project_token: str) -> Tuple[int, int]:
    """
    Max page and row count from analytics_records for this ParseHub project token.
    Rows are the same source the /api/analytics UI uses (record_data JSON).
    """
    if not project_token:
        return 0, 0
    try:
        cursor.execute(
            '''
            SELECT record_data
            FROM analytics_records
            WHERE project_token = %s
            ''',
            (project_token,),
        )
        rows = cursor.fetchall() or []
    except Exception as ex:
        logger.warning('[CHECKPOINT] analytics_records query failed (ignored): %s', ex)
        return 0, 0

    max_page = 0
    n = 0
    for row in rows:
        n += 1
        raw = row.get('record_data') if isinstance(row, dict) else (row[0] if row else None)
        parsed = _parse_record_data_blob(raw)
        if parsed:
            max_page = max(max_page, _max_page_from_record_dict(parsed))
    return max_page, n


# ============= HELPER FUNCTIONS =============

def safe_str(value):
    """
    Safely convert a value to string, handling None and non-string types.
    Strips whitespace if value is a non-empty string.
    Returns empty string if value is None or not a string.
    """
    if isinstance(value, str):
        return value.strip()
    return ''

def log_value(name: str, value, log_func=logger.debug):
    """
    Utility to log a value with type information for debugging
    """
    try:
        log_func(f"[LOG] {name} = {repr(value)} (type: {type(value).__name__})")
    except Exception as e:
        log_func(f"[LOG] {name} = <unable to log> (error: {str(e)})")


class MetadataDrivenResumeScraper:
    """
    Orchestrates metadata-driven resume scraping for ParseHub projects
    Uses robustcheckpoint tracking based on MAX(source_page) from persisted records
    """
    
    POLL_INTERVAL = 5  # Seconds between status checks
    MAX_POLL_ATTEMPTS = 360  # 30 minutes max wait (360 * 5sec)
    EMPTY_RESULT_THRESHOLD = 3  # Consecutive empty runs = done
    
    def __init__(self):
        self.db = ParseHubDatabase()
        self.api_key = os.getenv('PARSEHUB_API_KEY')
        self.base_url = os.getenv('PARSEHUB_BASE_URL', 'https://www.parsehub.com/api/v2')
        self.notification_service = get_notification_service()
        
        if not self.api_key:
            raise ValueError("PARSEHUB_API_KEY not configured")
    
    # ===== PROJECT URL OPERATIONS =====
    
    def get_project_url(self, project_id: int) -> Optional[str]:
        """
        Fetch listing URL for pagination: projects.main_site first, then metadata.website_url / last_known_url.

        Always use self.db.disconnect() (not raw conn.close()) so thread-local Snowflake state stays valid.
        """
        try:
            logger.info(f"[PROJECT_URL] Fetching URL for project_id={project_id}")
            self.db.connect()
            cursor = self.db.cursor()

            cursor.execute(
                '''
                SELECT main_site
                FROM projects
                WHERE id = %s
                LIMIT 1
                ''',
                (project_id,),
            )
            result = cursor.fetchone()
            log_value("project_url_from_projects", result)

            if result:
                if isinstance(result, dict):
                    project_url = result.get('main_site')
                else:
                    project_url = result[0] if len(result) > 0 else None
                project_url = safe_str(project_url) if project_url else None
                if project_url:
                    logger.info(f"[PROJECT_URL] ✓ projects.main_site: {project_url}")
                    return project_url

            logger.info("[PROJECT_URL] main_site empty; trying metadata website_url / last_known_url...")
            cursor.execute(
                '''
                SELECT website_url, last_known_url
                FROM metadata
                WHERE project_id = %s
                LIMIT 1
                ''',
                (project_id,),
            )
            metadata_result = cursor.fetchone()
            log_value("project_url_from_metadata", metadata_result)

            if metadata_result:
                if isinstance(metadata_result, dict):
                    wu = metadata_result.get('website_url') or metadata_result.get('WEBSITE_URL')
                    lk = metadata_result.get('last_known_url') or metadata_result.get('LAST_KNOWN_URL')
                else:
                    wu = metadata_result[0] if len(metadata_result) > 0 else None
                    lk = metadata_result[1] if len(metadata_result) > 1 else None
                for cand in (wu, lk):
                    u = safe_str(cand) if cand else None
                    if u:
                        logger.info(f"[PROJECT_URL] ✓ metadata URL: {u}")
                        return u

            logger.error(
                f"[PROJECT_URL] ✗ No URL for project_id={project_id} (projects.main_site + metadata)"
            )
            return None

        except Exception as e:
            logger.error(f"[PROJECT_URL] Error: {e}")
            logger.error(traceback.format_exc())
            return None
        finally:
            try:
                self.db.disconnect()
            except Exception:
                pass
    
    # ===== METADATA OPERATIONS =====
    
    def get_project_metadata(self, project_id: int) -> Optional[Dict]:
        """
        Load metadata for projects.id = project_id (not metadata.id).

        Exposes website_url (prefer WEBSITE_URL column, else LAST_KNOWN_URL) and coerced ints.
        """
        try:
            logger.info(f"[METADATA] Fetching metadata for projects.id={project_id}")
            self.db.connect()
            cursor = self.db.cursor()

            cursor.execute(
                '''
                SELECT *
                FROM metadata
                WHERE project_id = %s
                LIMIT 1
                ''',
                (project_id,),
            )
            result = cursor.fetchone()
            log_value("DATABASE_RESULT", result)

            if not result:
                logger.warning(f"[METADATA] No metadata row for project_id={project_id}")
                return None

            if isinstance(result, dict):
                normalized = {
                    (k.lower() if isinstance(k, str) else k): v
                    for k, v in result.items()
                }
            else:
                logger.warning("[METADATA] Unexpected non-dict row from SnowflakeCursorShim")
                return None

            pid_row = _coerce_int(normalized.get('project_id'), project_id)
            meta_id = _coerce_int(normalized.get('id'), 0)
            wu = safe_str(normalized.get('website_url', ''))
            lk = safe_str(normalized.get('last_known_url', ''))
            listing_url = wu or lk

            final_result = {
                'project_id': pid_row or project_id,
                'metadata_row_id': meta_id,
                'project_name': safe_str(normalized.get('project_name', 'Unknown')) or 'Unknown',
                'website_url': listing_url,
                'last_known_url': lk,
                'next_page_url': safe_str(normalized.get('next_page_url', '')),
                'total_pages': _coerce_int(normalized.get('total_pages'), 0),
                'total_products': _coerce_int(normalized.get('total_products'), 0),
                'project_token': safe_str(normalized.get('project_token', '')),
            }

            logger.info(f"[METADATA] Final metadata: {final_result}")
            return final_result

        except Exception as e:
            logger.error(f"[METADATA] Error reading metadata: {e}")
            logger.error(traceback.format_exc())
            return None
        finally:
            try:
                self.db.disconnect()
            except Exception:
                pass
    
    # ===== CHECKPOINT MANAGEMENT =====
    
    def get_checkpoint(self, project_id: int) -> Dict:
        """
        Get current checkpoint (highest successfully scraped page)

        Merges progress from:
        1) scraped_records.MAX(source_page) — canonical when the resume pipeline persists here
        2) metadata.current_page_scraped — updated when checkpoint is written from the scraper
        3) analytics_records — same rows as /api/analytics; max page from each record_data JSON
           (source_page, page_number, page, URLs with ?page=, etc.)

        Without (3), runs that only populated analytics (e.g. legacy ingest) showed highest_page=0
        and incorrectly restarted at page 1 instead of resuming.

        Returns:
            {
                'highest_successful_page': int,
                'next_start_page': int,
                'total_persisted_records': int,
                'checkpoint_timestamp': str
            }
        """
        try:
            logger.info(f"[CHECKPOINT] Fetching checkpoint for project {project_id}")
            self.db.connect()
            cursor = self.db.cursor()

            project_token = None
            try:
                cursor.execute(
                    'SELECT token FROM projects WHERE id = %s LIMIT 1',
                    (project_id,),
                )
                prow = cursor.fetchone()
                if prow:
                    if isinstance(prow, dict):
                        project_token = safe_str(prow.get('token'))
                    else:
                        project_token = safe_str(prow[0]) if len(prow) > 0 else ''
            except Exception as e:
                logger.warning('[CHECKPOINT] Could not load projects.token: %s', e)

            cursor.execute(
                '''
                SELECT MAX(source_page) as highest_page,
                       COUNT(*) as total_records
                FROM scraped_records
                WHERE project_id = %s
                ''',
                (project_id,),
            )

            result = cursor.fetchone()
            log_value("checkpoint_database_result", result)

            sr_highest = 0
            sr_count = 0

            if result:
                if isinstance(result, dict):
                    sr_highest = result.get('highest_page')
                    sr_count = result.get('total_records')
                else:
                    sr_highest = result[0] if len(result) > 0 else None
                    sr_count = result[1] if len(result) > 1 else None

            log_value("checkpoint_highest_page_raw", sr_highest)
            log_value("checkpoint_total_records_raw", sr_count)

            sr_highest = _coerce_int(sr_highest, 0)
            sr_count = _coerce_int(sr_count, 0)

            meta_cur = 0
            try:
                cursor.execute(
                    '''
                    SELECT current_page_scraped
                    FROM metadata
                    WHERE project_id = %s
                    LIMIT 1
                    ''',
                    (project_id,),
                )
                mrow = cursor.fetchone()
                if mrow:
                    if isinstance(mrow, dict):
                        meta_cur = _coerce_int(mrow.get('current_page_scraped'), 0)
                    else:
                        meta_cur = _coerce_int(mrow[0] if len(mrow) > 0 else 0, 0)
            except Exception as e:
                logger.warning('[CHECKPOINT] metadata.current_page_scraped read failed: %s', e)

            ar_highest, ar_count = _analytics_checkpoint_for_token(cursor, project_token or '')

            highest_page = max(sr_highest, meta_cur, ar_highest)
            total_records = max(sr_count, ar_count)

            # If analytics has rows but no page/source_page in JSON, max page stays 0 even though
            # a run already scraped listing page 1 (common for product-only rows). Assume page 1.
            if highest_page == 0 and ar_count > 0:
                logger.info(
                    '[CHECKPOINT] analytics_records has %s rows but no page fields; '
                    'assuming highest_successful_page=1',
                    ar_count,
                )
                highest_page = 1

            logger.info(
                '[CHECKPOINT] Project %s: merged highest_page=%s '
                '(scraped_records=%s, metadata.current_page_scraped=%s, analytics_records max=%s, '
                'counts sr=%s ar=%s -> total_persisted_records=%s)',
                project_id,
                highest_page,
                sr_highest,
                meta_cur,
                ar_highest,
                sr_count,
                ar_count,
                total_records,
            )

            return {
                'highest_successful_page': highest_page,
                'next_start_page': highest_page + 1,
                'total_persisted_records': total_records,
                'checkpoint_timestamp': datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"[CHECKPOINT] Error reading checkpoint: {e}")
            logger.error(f"[CHECKPOINT] Traceback: {traceback.format_exc()}")
            return {
                'highest_successful_page': 0,
                'next_start_page': 1,
                'total_persisted_records': 0,
                'checkpoint_timestamp': datetime.now().isoformat(),
            }
        finally:
            try:
                self.db.disconnect()
            except Exception:
                pass
    
    def update_checkpoint(self, project_id: int, highest_successful_page: int) -> bool:
        """
        Update checkpoint in metadata after successful persistence
        
        This updates metadata.current_page_scraped to reflect the highest successfully scraped page
        """
        try:
            conn = self.db.connect()
            cursor = self.db.cursor()

            cursor.execute(
                '''
                UPDATE metadata
                SET current_page_scraped = %s,
                    updated_date = %s
                WHERE project_id = %s
                ''',
                (highest_successful_page, datetime.now(), project_id),
            )

            conn.commit()
            logger.info(
                f"[CHECKPOINT] Updated project {project_id}: highest_page={highest_successful_page}"
            )
            return True

        except Exception as e:
            logger.error(f"[CHECKPOINT] Error updating checkpoint: {e}")
            return False
        finally:
            try:
                self.db.disconnect()
            except Exception:
                pass
    
    # ===== URL GENERATION =====
    
    def generate_next_page_url(self, base_url: str, next_page: int, 
                              pagination_pattern: Optional[str] = None) -> str:
        """
        Generate URL for the next page based on pagination pattern
        
        Detects pagination style (query param, path, offset, etc.) and generates appropriate URL
        
        Args:
            base_url: Base/template URL or starting URL
            next_page: Page number to generate URL for
            pagination_pattern: Optional hint for pagination style
        
        Returns:
            URL for the specified page
        """
        log_value("generate_next_page_url:base_url", base_url)
        log_value("generate_next_page_url:next_page", next_page)
        log_value("generate_next_page_url:pagination_pattern", pagination_pattern)
        
        # SAFETY CHECK: base_url must be a valid string
        if not base_url:
            logger.error(f"[ERROR] base_url is None or empty in generate_next_page_url")
            raise ValueError(f"base_url cannot be None or empty (got {repr(base_url)})")
        
        if not isinstance(base_url, str):
            logger.error(f"[ERROR] base_url is not a string: {type(base_url).__name__}")
            raise TypeError(f"base_url must be a string, got {type(base_url).__name__}: {repr(base_url)}")
        
        logger.debug(f"[URL_GEN] Generating URL for page {next_page} from: {base_url}")
        
        pattern = pagination_pattern
        if not pattern:
            pattern = self._detect_pagination_pattern(base_url)
        
        logger.debug(f"[URL_GEN] Detected/provided pattern: {pattern}")
        
        # Pattern 1: Query parameter ?page=X
        if pattern == 'query_page' or '?page=' in base_url or '&page=' in base_url:
            if '?page=' in base_url or '&page=' in base_url:
                return re.sub(r'([?&])page=\d+', rf'\1page={next_page}', base_url)
            elif '?' in base_url:
                return f"{base_url}&page={next_page}"
            else:
                return f"{base_url}?page={next_page}"
        
        # Pattern 2: Query parameter ?p=X
        elif pattern == 'query_p' or '?p=' in base_url or '&p=' in base_url:
            if '?p=' in base_url or '&p=' in base_url:
                return re.sub(r'([?&])p=\d+', rf'\1p={next_page}', base_url)
            elif '?' in base_url:
                return f"{base_url}&p={next_page}"
            else:
                return f"{base_url}?p={next_page}"
        
        # Pattern 3: Offset parameter ?offset=X (assume 20 items per page)
        elif pattern == 'offset' or '?offset=' in base_url or '&offset=' in base_url:
            offset = (next_page - 1) * 20
            if '?offset=' in base_url or '&offset=' in base_url:
                return re.sub(r'([?&])offset=\d+', rf'\1offset={offset}', base_url)
            elif '?' in base_url:
                return f"{base_url}&offset={offset}"
            else:
                return f"{base_url}?offset={offset}"
        
        # Pattern 4: Path-based /page/X/
        elif pattern == 'path_style' or '/page/' in base_url:
            if '/page/' in base_url:
                return re.sub(r'/page/\d+/', f'/page/{next_page}/', base_url)
            else:
                return f"{base_url}/page/{next_page}/"
        
        # Default: append ?page=X
        else:
            if '?' in base_url:
                return f"{base_url}&page={next_page}"
            else:
                return f"{base_url}?page={next_page}"
                
    def build_resume_url_from_next_page_url(self, next_page_url_template: str, next_page: int) -> str:
        """
        Build resume URL by replacing the numeric pagination token inside the next_page_url template.
        """
        if not next_page_url_template or not isinstance(next_page_url_template, str):
            raise ValueError(f"next_page_url_template must be a non-empty string, got {type(next_page_url_template).__name__}")
            
        url = next_page_url_template.strip()
        if not url:
            raise ValueError("next_page_url_template string is empty")
            
        logger.debug(f"[URL_GEN] Building resume URL from template: {url} for page {next_page}")
        
        # Pattern 1: ?page=X or &page=X
        if re.search(r'[?&]page=\d+', url):
            return re.sub(r'([?&]page=)\d+', rf'\g<1>{next_page}', url)
            
        # Pattern 2: ?p=X or &p=X
        if re.search(r'[?&]p=\d+', url):
            return re.sub(r'([?&]p=)\d+', rf'\g<1>{next_page}', url)
            
        # Pattern 3: ?offset=X or &offset=X
        if re.search(r'[?&]offset=\d+', url):
            offset = (next_page - 1) * 20
            return re.sub(r'([?&]offset=)\d+', rf'\g<1>{offset}', url)
            
        # Pattern 4: /page/X/ or /page/X
        if re.search(r'/page/\d+', url):
            return re.sub(r'(/page/)\d+', rf'\g<1>{next_page}', url)
            
        # Fallback: replace the last sequence of digits in the URL
        def replace_last_digits(match):
            return str(next_page) + match.group(2)
            
        # (\d+) matches the last sequence of digits
        # ([^0-9]*)$ matches everything after it until the end of string
        new_url, count = re.subn(r'(\d+)([^0-9]*)$', replace_last_digits, url)
        if count == 0:
            raise ValueError(f"Could not find any numeric pagination token in next_page_url: {url}")
            
        return new_url
    
    def _detect_pagination_pattern(self, url: str) -> str:
        """Detect pagination pattern in URL"""
        log_value("_detect_pagination_pattern:url", url)
        
        # SAFETY CHECK: url must be a valid string
        if not url:
            logger.warning(f"[PATTERN] url is None or empty in _detect_pagination_pattern, returning 'unknown'")
            return 'unknown'
        
        if not isinstance(url, str):
            logger.error(f"[ERROR] url is not a string in _detect_pagination_pattern: {type(url).__name__}")
            logger.error(f"[ERROR] url repr: {repr(url)}")
            return 'unknown'
        
        logger.debug(f"[PATTERN] Detecting pagination pattern in: {url}")
        
        if '?page=' in url or '&page=' in url:
            logger.debug(f"[PATTERN] Detected 'query_page' pattern")
            return 'query_page'
        elif '?p=' in url or '&p=' in url:
            logger.debug(f"[PATTERN] Detected 'query_p' pattern")
            return 'query_p'
        elif '?offset=' in url or '&offset=' in url:
            logger.debug(f"[PATTERN] Detected 'offset' pattern")
            return 'offset'
        elif '/page/' in url:
            logger.debug(f"[PATTERN] Detected 'path_style' pattern")
            return 'path_style'
        else:
            logger.debug(f"[PATTERN] No pattern detected, returning 'unknown'")
            return 'unknown'
    
    # ===== PARSEHUB RUN ORCHESTRATION =====
    
    def trigger_run(self, project_token: str, start_url: str, 
                    project_id: int, project_name: str,
                    starting_page_number: int) -> Dict:
        """
        Trigger a ParseHub run with the given start URL
        
        Args:
            project_token: ParseHub project token
            start_url: Starting URL for this run
            project_id: Project ID for tracking
            project_name: Project name for logging/notifications
            starting_page_number: Which website page this run starts from
        
        Returns:
            {
                'success': bool,
                'run_token': str (if successful),
                'error': str (if failed),
                'error_type': str
            }
        """
        try:
            # SAFETY CHECKS: Log and validate all required parameters
            log_value("trigger_run:project_token", project_token)
            log_value("trigger_run:start_url", start_url)
            log_value("trigger_run:project_id", project_id)
            log_value("trigger_run:project_name", project_name)
            log_value("trigger_run:starting_page_number", starting_page_number)
            
            # Validate start_url
            if not start_url:
                error_msg = "start_url is None or empty in trigger_run"
                logger.error(f"[ERROR] {error_msg}")
                raise ValueError(error_msg)
            
            if not isinstance(start_url, str):
                error_msg = f"start_url is not a string: {type(start_url).__name__}"
                logger.error(f"[ERROR] {error_msg}")
                raise TypeError(error_msg)
            
            logger.info(f"[RUN] Triggering ParseHub run for {project_name}")
            logger.info(f"[RUN] Start URL: {start_url}")
            logger.info(f"[RUN] Starting page: {starting_page_number}")
            
            params = {'api_key': self.api_key}
            run_data = {'start_url': start_url}
            
            response = requests.post(
                f"{self.base_url}/projects/{project_token}/run",
                params=params,
                json=run_data,
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = f"ParseHub API error: {response.status_code}"
                if response.status_code >= 500:
                    error_type = 'server_error'
                elif response.status_code >= 400:
                    error_type = 'client_error'
                else:
                    error_type = 'http_error'
                
                logger.error(f"[RUN] {error_msg}")
                
                # Send failure notification
                self._send_failure_notification({
                    'project_name': project_name,
                    'project_id': project_id,
                    'error_type': error_type,
                    'error_message': error_msg,
                    'start_page': starting_page_number,
                    'start_url': start_url
                })
                
                return {
                    'success': False,
                    'error': error_msg,
                    'error_type': error_type
                }
            
            result = response.json()
            run_token = result.get('run_token')
            
            if not run_token:
                error_msg = "No run_token in ParseHub response"
                logger.error(f"[RUN] {error_msg}")
                
                self._send_failure_notification({
                    'project_name': project_name,
                    'project_id': project_id,
                    'error_type': 'invalid_response',
                    'error_message': error_msg,
                    'start_page': starting_page_number,
                    'start_url': start_url
                })
                
                return {
                    'success': False,
                    'error': error_msg,
                    'error_type': 'invalid_response'
                }
            
            logger.info(f"[RUN] Successfully triggered: {run_token}")
            
            return {
                'success': True,
                'run_token': run_token
            }
        
        except requests.Timeout:
            error_msg = f"ParseHub API timeout (30s)"
            logger.error(f"[RUN] {error_msg}")
            
            self._send_failure_notification({
                'project_name': project_name,
                'project_id': project_id,
                'error_type': 'timeout',
                'error_message': error_msg,
                'start_page': starting_page_number,
                'start_url': start_url
            })
            
            return {
                'success': False,
                'error': error_msg,
                'error_type': 'timeout'
            }
        
        except requests.RequestException as e:
            error_msg = f"ParseHub API connection error: {str(e)}"
            logger.error(f"[RUN] {error_msg}")
            
            self._send_failure_notification({
                'project_name': project_name,
                'project_id': project_id,
                'error_type': 'connection_error',
                'error_message': error_msg,
                'start_page': starting_page_number,
                'start_url': start_url
            })
            
            return {
                'success': False,
                'error': error_msg,
                'error_type': 'connection_error'
            }
        
        except Exception as e:
            error_msg = f"Unexpected error triggering run: {str(e)}"
            logger.error(f"[RUN] {error_msg}")
            
            self._send_failure_notification({
                'project_name': project_name,
                'project_id': project_id,
                'error_type': 'unexpected',
                'error_message': error_msg,
                'start_page': starting_page_number,
                'start_url': start_url
            })
            
            return {
                'success': False,
                'error': error_msg,
                'error_type': 'unexpected'
            }
    
    def _pages_from_parsehub_run(self, result: dict) -> int:
        """Best-effort page count from ParseHub GET /runs/{token} JSON."""
        v = result.get('pages_scraped')
        if v is None:
            v = result.get('pages')
        try:
            return int(v) if v is not None else 0
        except (TypeError, ValueError):
            return 0

    def poll_run_completion(self, run_token: str) -> Dict:
        """
        Poll ParseHub run until completion
        
        Returns:
            {
                'success': bool,
                'status': str ('completed', 'failed', 'cancelled', 'error'),
                'data_count': int,
                'error': str (if failed)
            }
        """
        try:
            logger.info(f"[POLL] Polling run: {run_token}")
            
            for attempt in range(self.MAX_POLL_ATTEMPTS):
                response = requests.get(
                    f"{self.base_url}/runs/{run_token}",
                    params={'api_key': self.api_key},
                    timeout=30
                )
                
                if response.status_code != 200:
                    logger.warning(f"[POLL] API error on attempt {attempt}: {response.status_code}")
                    time.sleep(self.POLL_INTERVAL)
                    continue
                
                result = response.json()
                status = result.get('status')
                data = result.get('data', [])
                data_count = len(data) if data else 0

                # Live progress in Snowflake (runs.pages_scraped)
                try:
                    pages_live = self._pages_from_parsehub_run(result)
                    if pages_live >= 0 and self.db:
                        self.db.update_run_progress(run_token, pages_live, 'running')
                except Exception as prog_e:
                    logger.debug(f"[POLL] Progress DB update skipped: {prog_e}")
                
                logger.debug(f"[POLL] Attempt {attempt}: status={status}, data_count={data_count}")
                
                if status == 'completed':
                    logger.info(f"[POLL] Run completed: {data_count} records")
                    return {
                        'success': True,
                        'status': 'completed',
                        'data_count': data_count,
                        'data': data
                    }
                
                elif status in ['failed', 'cancelled', 'error']:
                    error_msg = result.get('error', f"Run {status}")
                    logger.error(f"[POLL] Run {status}: {error_msg}")
                    try:
                        if self.db:
                            self.db.mark_run_terminal(run_token, status)
                    except Exception:
                        pass
                    return {
                        'success': False,
                        'status': status,
                        'error': error_msg,
                        'data_count': data_count
                    }
                
                # Still running, wait and retry
                time.sleep(self.POLL_INTERVAL)
            
            # Max attempts reached
            error_msg = f"Run polling timeout after {self.MAX_POLL_ATTEMPTS * self.POLL_INTERVAL}s"
            logger.error(f"[POLL] {error_msg}")
            
            try:
                if self.db:
                    self.db.mark_run_terminal(run_token, 'timeout')
            except Exception:
                pass
            return {
                'success': False,
                'status': 'timeout',
                'error': error_msg,
                'data_count': 0
            }
        
        except Exception as e:
            error_msg = f"Error polling run: {str(e)}"
            logger.error(f"[POLL] {error_msg}")
            
            return {
                'success': False,
                'status': 'error',
                'error': error_msg,
                'data_count': 0
            }
    
    def _largest_dict_list_in_tree(self, obj, depth: int = 0) -> List[Dict]:
        """Return the longest list of dicts in nested JSON (ParseHub selection arrays)."""
        if depth > 15:
            return []
        best: List[Dict] = []
        if isinstance(obj, list):
            if obj and all(isinstance(x, dict) for x in obj):
                return obj
            for x in obj:
                sub = self._largest_dict_list_in_tree(x, depth + 1)
                if len(sub) > len(best):
                    best = sub
        elif isinstance(obj, dict):
            for v in obj.values():
                sub = self._largest_dict_list_in_tree(v, depth + 1)
                if len(sub) > len(best):
                    best = sub
        return best

    def _parsehub_data_response_to_records(self, raw) -> List[Dict]:
        """
        Turn ParseHub GET /runs/{token}/data JSON into a list of row dicts.
        Prefer product-oriented extraction; fall back to structural heuristics.
        """
        from src.services.data_ingestion_service import ParseHubDataIngestor
        
        raw_type = type(raw).__name__
        logger.info(f"[FETCH-PARSE] Parsing raw data of type: {raw_type}")

        try:
            ingestor = ParseHubDataIngestor()
            products = ingestor._extract_products_from_structure(raw)
            if products:
                logger.info(f"[FETCH-PARSE] Extracted {len(products)} products via ParseHubDataIngestor")
                return products
            else:
                logger.info(f"[FETCH-PARSE] ParseHubDataIngestor returned 0 products")
        except Exception as ex:
            logger.warning(f"[FETCH-PARSE] ParseHubDataIngestor extract failed: {ex}")

        if isinstance(raw, list):
            rows = [x for x in raw if isinstance(x, dict)]
            logger.info(f"[FETCH-PARSE] Raw is list, found {len(rows)} dict rows out of {len(raw)} items")
            if rows:
                return rows

        if isinstance(raw, dict):
            logger.info(f"[FETCH-PARSE] Raw is dict with keys: {list(raw.keys())[:10]}...")
            for key in ('data', 'results', 'items', 'products', 'records'):
                v = raw.get(key)
                if isinstance(v, list):
                    rows = [x for x in v if isinstance(x, dict)]
                    logger.info(f"[FETCH-PARSE] Found key '{key}' with {len(v)} items, {len(rows)} are dicts")
                    if rows:
                        return rows

            nested = self._largest_dict_list_in_tree(raw)
            if nested:
                logger.info(f"[FETCH-PARSE] Found {len(nested)} rows via tree traversal")
                return nested

            if raw:
                logger.info("[FETCH-PARSE] Storing root object as a single row (no list of dicts found)")
                return [raw]

        logger.error(f"[FETCH-PARSE] Could not extract any records from {raw_type}")
        return []

    def fetch_run_data(self, run_token: str) -> Dict:
        """
        Fetch final data from completed ParseHub run.

        Uses GET /runs/{run_token}/data — the endpoint that returns scraped output.
        The bare /runs/{run_token} object often omits or empties `data` even when
        the run is complete.

        Returns:
            {
                'success': bool,
                'data': List[Dict],
                'error': str (if failed)
            }
        """
        try:
            logger.info(f"[FETCH] Fetching /data for run: {run_token}")

            response = requests.get(
                f"{self.base_url}/runs/{run_token}/data",
                params={'api_key': self.api_key},
                timeout=180,
            )

            if response.status_code != 200:
                error_msg = f"Failed to fetch run data: {response.status_code}"
                logger.error(f"[FETCH] {error_msg}")

                return {
                    'success': False,
                    'data': [],
                    'error': error_msg,
                }

            raw = response.json()
            raw_type = type(raw).__name__
            raw_preview = str(raw)[:500] if raw else "None"
            logger.info(f"[FETCH] Response type: {raw_type}, preview: {raw_preview}...")
            
            data = self._parsehub_data_response_to_records(raw)

            logger.info(f"[FETCH] Retrieved {len(data)} records from /data (raw was {raw_type})")
            if len(data) == 0:
                logger.error(f"[FETCH] WARNING: Zero records extracted! Raw response type: {raw_type}")
                logger.error(f"[FETCH] Raw response preview: {raw_preview}...")

            return {
                'success': True,
                'data': data,
                'error': None,
            }

        except Exception as e:
            error_msg = f"Error fetching run data: {str(e)}"
            logger.error(f"[FETCH] {error_msg}")

            return {
                'success': False,
                'data': [],
                'error': error_msg,
            }
    
    # ===== PERSISTENCE LAYER =====
    
    def persist_results(self, project_id: int, run_token: str, data: List[Dict],
                       source_page: int, session_id: Optional[int] = None) -> Tuple[bool, int, int]:
        """
        Persist scraped results to database with source_page tracking
        
        Each record is stored with source_page to enable reliable checkpoint tracking
        
        Args:
            project_id: Project ID
            run_token: ParseHub run token
            data: List of scraped records
            source_page: Website page number these records came from
            session_id: Optional monitoring session ID
        
        Returns:
            (success: bool, records_inserted: int, highest_page: int)
        """
        conn = None
        try:
            logger.info(f"[PERSIST] Persisting {len(data)} records from page {source_page} for project {project_id}")
            
            if not data:
                logger.warning(f"[PERSIST] No data to persist for project {project_id}")
                try:
                    self.db.disconnect()
                except Exception:
                    pass
                return (True, 0, source_page)  # Success but nothing inserted
            
            conn = self.db.connect()
            cursor = self.db.cursor()
            
            # Log first record for debugging
            if len(data) > 0:
                sample = data[0] if isinstance(data[0], dict) else str(data[0])[:100]
                logger.debug(f"[PERSIST] Sample record: {sample}")
            
            inserted_count = 0
            highest_page = source_page
            
            for record in data:
                try:
                    # Convert record to JSON string
                    data_json = json.dumps(record) if isinstance(record, dict) else str(record)
                    
                    cursor.execute('''
                        INSERT INTO scraped_records 
                        (session_id, project_id, run_token, source_page, data_json, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (
                        session_id,
                        project_id,
                        run_token,
                        source_page,
                        data_json,
                        datetime.now()
                    ))
                    
                    inserted_count += 1
                
                except Exception as record_err:
                    logger.warning(f"[PERSIST] Failed to insert individual record: {record_err}")
                    # Continue with next record on individual insert failure
                    continue
            
            conn.commit()
            logger.info(f"[PERSIST] committed {inserted_count} rows to scraped_records")

            # Mirror rows into scraped_data (Snowflake) for reporting / exports
            logger.info(f"[PERSIST] Calling insert_scraped_rows_for_run with run_token={run_token[:12] if run_token else None}... project_id={project_id} data_count={len(data)}")
            try:
                sd_count = self.db.insert_scraped_rows_for_run(run_token, project_id, data)
                logger.info(f"[PERSIST] scraped_data rows inserted: {sd_count}")
                if sd_count == 0:
                    logger.error(f"[PERSIST] WARNING: scraped_data insert returned 0 rows! run_token={run_token[:12] if run_token else None}... project_id={project_id}")
            except Exception as sd_e:
                logger.error(f"[PERSIST] scraped_data insert FAILED: {sd_e}", exc_info=True)
            
            # After successful persistence, compute new highest page
            checkpoint = self.get_checkpoint(project_id)
            highest_page = checkpoint['highest_successful_page']
            
            logger.info(f"[PERSIST] Inserted {inserted_count} records, new highest_page={highest_page}")
            
            return (True, inserted_count, highest_page)
        
        except Exception as e:
            logger.error(f"[PERSIST] Error persisting results: {e}", exc_info=True)
            try:
                if conn:
                    conn.rollback()
            except Exception:
                pass
            return (False, 0, 0)
        finally:
            try:
                self.db.disconnect()
            except Exception:
                pass
    
    def compute_highest_successful_page(self, project_id: int) -> int:
        """
        Compute the highest successfully scraped website page
        
        This is the core checkpoint mechanism - uses MAX(source_page) from persisted records
        """
        checkpoint = self.get_checkpoint(project_id)
        return checkpoint['highest_successful_page']
    
    # ===== COMPLETION LOGIC =====
    
    def is_project_complete(self, project_id: int, metadata: Dict) -> Tuple[bool, str]:
        """
        Determine if project scraping is complete
        
        Completion Rule:
        When merged highest_successful_page (see get_checkpoint) >= total_pages from metadata,
        project is complete.
        
        Returns:
            (is_complete: bool, reason: str)
        """
        checkpoint = self.get_checkpoint(project_id)
        highest_page = _coerce_int(checkpoint['highest_successful_page'], 0)
        total_pages = _coerce_int(metadata.get('total_pages'), 0)
        total_products = _coerce_int(metadata.get('total_products'), 0)

        logger.info(f"\n[COMPLETE] Checking completion for project {project_id}")
        logger.info(f"[COMPLETE] Highest page scraped (max source_page): {highest_page}")
        logger.info(f"[COMPLETE] Total pages required: {total_pages}")
        logger.debug(f"[COMPLETE] total_products (metadata): {total_products}")

        # Primary check: all pages scraped
        # When highest_page >= total_pages, all required pages have been scraped
        if highest_page >= total_pages and total_pages > 0:
            logger.info(f"[COMPLETE] ✓ Project COMPLETE: max(source_page) {highest_page} >= total_pages {total_pages}")
            return (True, f"Complete: All {total_pages} pages scraped (highest_page={highest_page})")
        
        # Additional safety check: if total_pages is 0 or invalid
        if total_pages <= 0:
            logger.warning(f"[COMPLETE] Warning: total_pages is {total_pages}")
            if highest_page > 0:
                return (True, f"Complete: At least 1 page scraped (highest_page={highest_page})")
            return (False, "Incomplete: Invalid total_pages and no progress")
        
        logger.info(f"[COMPLETE] ✗ Project INCOMPLETE: {highest_page}/{total_pages} pages scraped")
        logger.info(f"[COMPLETE] Remaining: {total_pages - highest_page} pages to scrape")
        return (False, f"Incomplete: {highest_page}/{total_pages} pages scraped, {total_pages - highest_page} remaining")
    
    def mark_project_complete(self, project_id: int) -> bool:
        """
        Mark project as complete in metadata
        """
        try:
            conn = self.db.connect()
            cursor = self.db.cursor()

            cursor.execute(
                '''
                UPDATE metadata
                SET status = 'complete',
                    updated_date = %s
                WHERE project_id = %s
                ''',
                (datetime.now(), project_id),
            )

            conn.commit()
            logger.info(f"[COMPLETE] Marked project {project_id} as complete")
            return True

        except Exception as e:
            logger.error(f"[COMPLETE] Error marking project complete: {e}")
            return False
        finally:
            try:
                self.db.disconnect()
            except Exception:
                pass
    
    # ===== FAILURE NOTIFICATIONS =====
    
    def _send_failure_notification(self, error_details: Dict) -> bool:
        """
        Send email notification for critical failures
        
        Args:
            error_details: {
                'project_name': str,
                'project_id': int,
                'error_type': str,
                'error_message': str,
                'start_page': int,
                'start_url': str
            }
        """
        if not self.notification_service or not self.notification_service.is_enabled():
            logger.debug("[EMAIL] Email notifications disabled")
            return False
        
        try:
            # Enrich error details
            error_details['timestamp'] = datetime.now().isoformat()
            error_details['batch_info'] = {
                'start_page': error_details.get('start_page', 0),
                'end_page': error_details.get('start_page', 0)  # Single page run
            }
            
            return self.notification_service.send_api_failure_alert(error_details)
        
        except Exception as e:
            logger.error(f"[EMAIL] Error sending failure notification: {e}")
            return False
    
    # ===== ORCHESTRATION ENTRY POINT =====
    
    def resume_or_start_scraping(self, project_id: int, project_token: str) -> Dict:
        """
        Main orchestration method: resume or start scraping for a project
        
        URL Behavior:
        - First run uses project URL
        - Resumed runs prefer metadata.next_page_url template
        - Fallback exists if metadata template is missing or invalid
        
        Returns:
            {
                'success': bool,
                'run_token': str (if run started),
                'project_complete': bool,
                'highest_successful_page': int,
                'next_start_page': int,
                'total_pages': int,
                'message': str,
                'error': str (if failed)
            }
        """
        try:
            logger.info(f"\n{'='*80}")
            logger.info(f"[BEGIN] Resume or start scraping for project {project_id}")
            logger.info(f"{'='*80}")
            
            # Step 1: Fetch project URL from projects table
            logger.info("[STEP 1] Fetching project URL...")
            project_url = self.get_project_url(project_id)
            
            if not project_url:
                error_msg = f"No project URL found for project {project_id}"
                logger.error(f"[ERROR] {error_msg}")
                return {
                    'success': False,
                    'message': error_msg,
                    'error': error_msg
                }
            
            # Step 2: Read metadata (for total_pages and project_name only)
            logger.info("[STEP 2] Reading metadata...")
            metadata = self.get_project_metadata(project_id)
            
            if not metadata:
                error_msg = f"No metadata found for project {project_id}"
                logger.error(f"[ERROR] {error_msg}")
                return {
                    'success': False,
                    'message': error_msg,
                    'error': error_msg
                }
            
            # Normalize all metadata keys to lowercase and numeric fields
            metadata = metadata or {}
            metadata = {str(k).lower(): v for k, v in metadata.items()}
            metadata['total_pages'] = _coerce_int(metadata.get('total_pages'), 0)
            metadata['total_products'] = _coerce_int(metadata.get('total_products'), 0)

            logger.info(
                f"[METADATA] {metadata.get('project_name', 'Unknown')}: {metadata.get('total_pages', 0)} pages"
            )
            
            # Step 3: Read checkpoint
            logger.info("[STEP 3] Reading checkpoint...")
            checkpoint = self.get_checkpoint(project_id)
            
            logger.info(f"[CHECKPOINT] Highest successful page: {checkpoint['highest_successful_page']}")
            logger.info(f"[CHECKPOINT] Total persisted records: {checkpoint['total_persisted_records']}")
            
            # Step 4: Check if already complete
            is_complete, complete_reason = self.is_project_complete(project_id, metadata)
            
            if is_complete:
                logger.info(f"[COMPLETE] {complete_reason}")
                
                # Mark as complete
                self.mark_project_complete(project_id)
                
                return {
                    'success': True,
                    'project_complete': True,
                    'message': 'Project scraping is complete',
                    'highest_successful_page': checkpoint['highest_successful_page'],
                    'total_pages': metadata.get('total_pages', 0),
                    'total_persisted_records': checkpoint['total_persisted_records'],
                    'reason': complete_reason
                }
            
            # Step 5: Determine start URL based on checkpoint and project_url
            logger.info("[STEP 4] Determining start URL...")
            highest_page = _coerce_int(checkpoint['highest_successful_page'], 0)
            log_value("checkpoint_highest_page", highest_page)
            log_value("project_url", project_url)
            
            # FRESH PROJECT: use project_url directly (first run)
            if highest_page == 0:
                start_url = project_url
                next_page = 1
                log_value("start_url (fresh)", start_url)
                logger.info(f"[URL] Fresh project (first run) - using project URL: {start_url}")
            
            # RESUMED PROJECT: use metadata.next_page_url template, fallback to project_url
            elif highest_page < metadata.get('total_pages', 0):
                next_page = _coerce_int(checkpoint['next_start_page'], highest_page + 1)
                log_value("next_page (resumed)", next_page)
                log_value("total_pages (metadata)", metadata.get('total_pages'))
                
                next_page_url = safe_str(metadata.get('next_page_url', ''))
                start_url = None
                
                if next_page_url:
                    logger.info(f"[URL] Resumed project - using metadata.next_page_url template")
                    try:
                        start_url = self.build_resume_url_from_next_page_url(next_page_url, next_page)
                        logger.info(f"[URL] Built resume URL from next_page_url: {start_url}")
                    except Exception as e:
                        logger.warning(f"[URL] Error building resume URL from next_page_url: {e}")
                        logger.info(f"[URL] metadata.next_page_url invalid; falling back to project_url generation")
                else:
                    logger.info(f"[URL] metadata.next_page_url missing; falling back to project_url generation")
                
                # Fallback path
                if not start_url:
                    try:
                        start_url = self.generate_next_page_url(project_url, next_page, None)
                        log_value("start_url_generated", start_url)
                        logger.info(f"[URL] Fallback - generated URL for page {next_page}: {start_url}")
                    except Exception as e:
                        logger.error(f"[ERROR] Failed to generate next page URL: {str(e)}")
                        raise
            
            # PROJECT COMPLETE: should not reach here (caught earlier)
            else:
                error_msg = f"Project already complete but reached URL determination"
                logger.error(f"[ERROR] {error_msg}")
                return {
                    'success': False,
                    'message': error_msg,
                    'error': error_msg
                }
            
            # Step 6: Trigger ParseHub run
            logger.info("[STEP 5] Triggering ParseHub run...")
            run_result = self.trigger_run(
                project_token,
                start_url,
                project_id,
                metadata.get('project_name', 'Unknown'),
                next_page
            )
            
            if not run_result['success']:
                error_msg = run_result.get('error', 'Unknown error')
                logger.error(f"[ERROR] {error_msg}")
                return {
                    'success': False,
                    'message': error_msg,
                    'error': error_msg,
                    'error_type': run_result.get('error_type', 'unknown')
                }
            
            run_token = run_result['run_token']
            
            logger.info(f"[RUN] Started run: {run_token}")
            
            return {
                'success': True,
                'run_token': run_token,
                'project_complete': False,
                'highest_successful_page': checkpoint['highest_successful_page'],
                'next_start_page': next_page,
                'total_pages': metadata.get('total_pages', 0),
                'total_persisted_records': checkpoint.get('total_persisted_records', 0),
                'message': f"Run started for page {next_page}",
            }
        
        except Exception as e:
            error_msg = f"Orchestration error: {str(e)}"
            logger.error(f"[ERROR] {error_msg}")
            tb_str = traceback.format_exc()
            logger.error(f"[ERROR] FULL TRACEBACK:\n{tb_str}")
            
            # Extract line and file from traceback
            tb_lines = tb_str.split('\n')
            for line in tb_lines:
                if '.strip()' in line:
                    logger.error(f"[ERROR] FOUND .strip() CALL in traceback: {line}")
            
            # Try to identify which variable caused the issue
            error_str = str(e)
            if "'NoneType' object has no attribute 'strip'" in error_str:
                logger.error(f"[ERROR] Null-handling error detected!")
                logger.error(f"[ERROR] Local variables at time of crash:")
                # Log all known local variables
                try:
                    logger.error(f"  - project_id: {repr(project_id)}")
                    logger.error(f"  - project_token: {repr(project_token)}")
                    logger.error(f"  - project_url: {repr(project_url) if 'project_url' in locals() else 'NOT SET'}")
                    logger.error(f"  - metadata: {repr(metadata) if 'metadata' in locals() else 'NOT SET'}")
                    logger.error(f"  - checkpoint: {repr(checkpoint) if 'checkpoint' in locals() else 'NOT SET'}")
                    logger.error(f"  - start_url: {repr(start_url) if 'start_url' in locals() else 'NOT SET'}")
                except Exception as debug_e:
                    logger.error(f"  - Error logging variables: {debug_e}")
            
            return {
                'success': False,
                'message': error_msg,
                'error': error_msg
            }


def get_metadata_driven_scraper() -> MetadataDrivenResumeScraper:
    """Factory function to get scraper instance"""
    return MetadataDrivenResumeScraper()
