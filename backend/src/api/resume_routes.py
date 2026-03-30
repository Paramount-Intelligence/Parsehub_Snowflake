"""
Metadata-Driven Resume Scraping API Routes

Replaces old batch/chunk-based scraping with metadata-driven resume logic.
Key improvements:
- Uses metadata (total_pages, total_products) to drive scraping
- Checkpoints based on MAX(source_page) from persisted records
- Dynamic URL generation  
- Single ParseHub project per scraping session
- Email notifications for critical failures
"""

from flask import Blueprint, request, jsonify, g
import logging
import os
import requests
from typing import Dict, Optional, Any
from src.services.metadata_driven_resume_scraper import get_metadata_driven_scraper
from src.models.database import ParseHubDatabase
from src.services.auto_complete_service import register_run_for_completion

logger = logging.getLogger(__name__)

# Create blueprint
resume_bp = Blueprint('resume', __name__, url_prefix='/api/projects')


def _projects_id_for_token(db: ParseHubDatabase, project_token: str) -> Optional[int]:
    """
    scraped_records / checkpoints use projects.id (FK), not metadata.id.
    Always resolve via projects.token.
    """
    if not project_token:
        return None
    try:
        pid = db.get_project_id_by_token(project_token)
        return int(pid) if pid is not None else None
    except Exception as e:
        logger.warning(f"[resume] project id lookup failed: {e}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# START OR RESUME SCRAPING
# ──────────────────────────────────────────────────────────────────────────────

@resume_bp.route('/resume/start', methods=['POST'])
def start_resume_scraping():
    """
    Start or resume metadata-driven scraping for a project
    
    Request body:
    {
        "project_token": "tXXXXXXXXXXXXX",
        "project_id": 123  (optional - if not provided, token is used to lookup)
    }
    
    Response:
    {
        "success": true,
        "project_complete": false,
        "run_token": "abc123def456",
        "highest_successful_page": 5,
        "next_start_page": 6,
        "total_pages": 50,
        "checkpoint": {
            "highest_successful_page": 5,
            "next_start_page": 6,
            "total_persisted_records": 342
        },
        "message": "Run started for page 6"
    }
    
    OR if project is already complete:
    {
        "success": true,
        "project_complete": true,
        "highest_successful_page": 50,
        "total_pages": 50,
        "message": "Project scraping is complete",
        "reason": "Primary: highest_page (50) >= total_pages (50)"
    }
    """
    try:
        data = request.get_json()
        project_token = data.get('project_token')
        project_id = data.get('project_id')
        
        if not project_token:
            return jsonify({
                'success': False,
                'error': 'project_token is required'
            }), 400
        
        db: ParseHubDatabase = g.db
        scraper = get_metadata_driven_scraper()

        # Resolve projects.id from token (required for Snowflake runs / checkpoints)
        if not project_id:
            try:
                pid = db.get_project_id_by_token(project_token)
                project_id = pid
            except Exception as e:
                logger.warning(f"[resume/start] project id lookup: {e}")
                project_id = None
        if not project_id:
            return jsonify({
                'success': False,
                'error': 'Project not found in database for this token. Sync projects first.',
            }), 400
        
        logger.info(f"[resume/start] Starting/resuming scraping for project {project_id} (token={project_token[:8]}...)")
        
        # Call orchestrator
        result = scraper.resume_or_start_scraping(project_id, project_token)
        
        if not result['success']:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"[resume/start] Failed: {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg,
                'error_type': result.get('error_type', 'unknown')
            }), 500
        
        checkpoint = scraper.get_checkpoint(project_id)
        
        logger.info(f"[resume/start] ✅ Success: {result.get('message')}")
        
        # Auto-register run for background completion monitoring
        # This ensures data is fetched and persisted even if frontend disconnects
        run_token = result.get('run_token')
        next_page = result.get('next_start_page', 1)
        if run_token and not result.get('project_complete', False):
            try:
                register_run_for_completion(
                    run_token=run_token,
                    project_id=project_id,
                    project_token=project_token,
                    starting_page=next_page,
                    auto_continue=False  # Manual control for now, can enable auto_continue later
                )
                try:
                    db.ensure_run_started(project_id, run_token, 'running', 0)
                except Exception as se:
                    logger.warning(f"[resume/start] ensure_run_started: {se}")
                logger.info(f"[resume/start] Auto-registered run {run_token[:8]}... for background completion")
            except Exception as reg_err:
                logger.warning(f"[resume/start] Failed to auto-register run: {reg_err}")
        
        return jsonify({
            'success': True,
            'project_complete': result.get('project_complete', False),
            'run_token': result.get('run_token'),
            'highest_successful_page': result.get('highest_successful_page', 0),
            'next_start_page': result.get('next_start_page', 1),
            'total_pages': result.get('total_pages', 0),
            'total_persisted_records': result.get(
                'total_persisted_records', checkpoint.get('total_persisted_records', 0)
            ),
            'checkpoint': {
                'highest_successful_page': checkpoint['highest_successful_page'],
                'next_start_page': checkpoint['next_start_page'],
                'total_persisted_records': checkpoint['total_persisted_records']
            },
            'message': result.get('message', 'OK'),
            'reason': result.get('reason')
        }), 201
        
    except Exception as e:
        logger.error(f'[resume/start] Uncaught error: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET CURRENT CHECKPOINT
# ──────────────────────────────────────────────────────────────────────────────

@resume_bp.route('/<project_token>/resume/checkpoint', methods=['GET'])
def get_resume_checkpoint(project_token: str):
    """
    Get the current checkpoint (resume state) for a project
    
    Response:
    {
        "highest_successful_page": 5,
        "next_start_page": 6,
        "total_persisted_records": 342,
        "checkpoint_timestamp": "2024-03-26T14:00:00"
    }
    """
    try:
        db: ParseHubDatabase = g.db
        scraper = get_metadata_driven_scraper()
        
        # Lookup project_id from token
        project_id = _projects_id_for_token(db, project_token)
        if not project_id:
            return jsonify({
                'success': False,
                'error': 'Project not found for token',
                'highest_successful_page': 0,
                'next_start_page': 1,
                'total_persisted_records': 0,
            }), 404
        
        checkpoint = scraper.get_checkpoint(project_id)
        metadata = scraper.get_project_metadata(project_id) or {}
        is_complete, _ = scraper.is_project_complete(project_id, metadata)
        body = dict(checkpoint)
        body['is_project_complete'] = is_complete
        body['success'] = True
        body['project_token'] = project_token
        return jsonify(body), 200
        
    except Exception as e:
        logger.error(f'[checkpoint] Uncaught error: {e}', exc_info=True)
        return jsonify({
            'highest_successful_page': 0,
            'next_start_page': 1,
            'total_persisted_records': 0,
            'error': str(e)
        }), 200  # Return best-effort response


# ──────────────────────────────────────────────────────────────────────────────
# GET PROJECT METADATA
# ──────────────────────────────────────────────────────────────────────────────

@resume_bp.route('/<project_token>/resume/metadata', methods=['GET'])
def get_resume_metadata(project_token: str):
    """
    Get metadata and current progress for a project
    
    Response:
    {
        "project_id": 1,
        "project_name": "Example Project",
        "website_url": "https://example.com",
        "total_pages": 50,
        "total_products": 1500,
        "current_page_scraped": 5,
        "checkpoint": {
            "highest_successful_page": 5,
            "next_start_page": 6,
            "total_persisted_records": 342
        },
        "is_complete": false,
        "progress_percentage": 10
    }
    """
    try:
        db: ParseHubDatabase = g.db
        scraper = get_metadata_driven_scraper()
        
        project_id = _projects_id_for_token(db, project_token)
        if not project_id:
            return jsonify({
                'success': False,
                'error': 'Project not found for token',
            }), 404
        
        # Get metadata
        metadata = scraper.get_project_metadata(project_id)
        if not metadata:
            return jsonify({
                'success': False,
                'error': 'Metadata not found'
            }), 404
        
        # Get checkpoint
        checkpoint = scraper.get_checkpoint(project_id)
        
        # Check completion
        is_complete, _ = scraper.is_project_complete(project_id, metadata)
        
        # Calculate progress
        total_pages = int(metadata.get('total_pages') or 0)
        hp = int(checkpoint.get('highest_successful_page') or 0)
        progress_percentage = 0
        if total_pages > 0:
            progress_percentage = min(100, int((hp / total_pages) * 100))

        listing_url = metadata.get('website_url') or ''
        meta_block = {
            'project_id': metadata['project_id'],
            'project_name': metadata['project_name'],
            'website_url': listing_url,
            'base_url': listing_url,
            'total_pages': total_pages,
            'total_products': int(metadata.get('total_products') or 0),
            'current_page_scraped': hp,
        }

        return jsonify({
            'success': True,
            'metadata': meta_block,
            'project_id': metadata['project_id'],
            'project_name': metadata['project_name'],
            'website_url': listing_url,
            'total_pages': total_pages,
            'total_products': int(metadata.get('total_products') or 0),
            'current_page_scraped': hp,
            'checkpoint': {
                'highest_successful_page': checkpoint['highest_successful_page'],
                'next_start_page': checkpoint['next_start_page'],
                'total_persisted_records': checkpoint['total_persisted_records'],
                'is_project_complete': is_complete,
            },
            'is_complete': is_complete,
            'progress_percentage': progress_percentage,
        }), 200
        
    except Exception as e:
        logger.error(f'[metadata] Uncaught error: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# COMPLETE RUN AND PERSIST DATA (Webhook from backend or called after run)
# ──────────────────────────────────────────────────────────────────────────────

@resume_bp.route('/resume/complete-run', methods=['POST'])
def complete_run_and_persist():
    """
    Complete a ParseHub run, fetch data, persist to DB, and determine next action
    
    This endpoint should be called after a ParseHub run completes
    (either via webhook or manual polling)
    
    Request body:
    {
        "run_token": "run_token_from_parsehub",
        "project_id": 123,
        "project_token": "parsehub_project_token",
        "starting_page_number": 6  (which page this run was for)
    }
    
    Response:
    {
        "success": true,
        "run_completed": true,
        "records_persisted": 45,
        "highest_successful_page": 6,
        "project_complete": false,
        "next_action": "continue",
        "message": "Page 6 completed, ready to scrape page 7"
    }
    
    OR:
    {
        "success": true,
        "run_completed": true,
        "records_persisted": 50,
        "highest_successful_page": 50,
        "project_complete": true,
        "next_action": "complete",
        "message": "All 50 pages scraped, project complete"
    }
    """
    try:
        data = request.get_json()
        run_token = data.get('run_token')
        project_id = data.get('project_id')
        project_token = data.get('project_token')
        starting_page = data.get('starting_page_number', 1)
        
        if not all([run_token, project_id]):
            return jsonify({
                'success': False,
                'error': 'run_token and project_id required'
            }), 400
        
        scraper = get_metadata_driven_scraper()
        
        logger.info(f"[complete-run] Completing run {run_token} for project {project_id}, page {starting_page}")
        
        # Step 1: Poll for completion
        logger.info(f"[complete-run] Polling for completion...")
        poll_result = scraper.poll_run_completion(run_token)
        
        if not poll_result['success']:
            error_msg = poll_result.get('error', 'Run failed')
            logger.error(f"[complete-run] Run failed/timeout: {error_msg}")
            return jsonify({
                'success': False,
                'run_completed': False,
                'error': error_msg,
                'status': poll_result.get('status')
            }), 500
        
        # Step 2: Fetch data
        logger.info(f"[complete-run] Fetching data...")
        fetch_result = scraper.fetch_run_data(run_token)
        
        if not fetch_result['success']:
            error_msg = fetch_result.get('error', 'Failed to fetch data')
            logger.error(f"[complete-run] {error_msg}")
            return jsonify({
                'success': False,
                'run_completed': True,
                'error': error_msg
            }), 500
        
        scraped_data = fetch_result['data']
        logger.info(f"[complete-run] Fetched {len(scraped_data)} records from ParseHub")
        
        # Log data sample for debugging
        if scraped_data and len(scraped_data) > 0:
            sample = scraped_data[0] if isinstance(scraped_data[0], dict) else str(scraped_data[0])[:200]
            logger.info(f"[complete-run] Data sample: {sample}")
        
        # Step 3: Persist data with source_page tracking
        logger.info(f"[complete-run] Persisting data to database...")
        success, inserted_count, highest_page = scraper.persist_results(
            project_id=project_id,
            run_token=run_token,
            data=scraped_data,
            source_page=starting_page,
            session_id=None
        )
        
        if not success:
            logger.error(f"[complete-run] ❌ Persistence failed - no records stored")
            return jsonify({
                'success': False,
                'run_completed': True,
                'records_persisted': 0,
                'error': 'Failed to persist data to database'
            }), 500
        
        logger.info(f"[complete-run] ✅ Persisted {inserted_count} records to database")
        
        # Step 4: Check if project is now complete
        metadata = scraper.get_project_metadata(project_id)
        is_complete, complete_reason = scraper.is_project_complete(project_id, metadata)
        
        if is_complete:
            logger.info(f"[complete-run] ✅ Project now complete")
            scraper.mark_project_complete(project_id)
            next_action = 'complete'
            message = f"Project complete: all {metadata['total_pages']} pages scraped"
        else:
            logger.info(f"[complete-run] Project incomplete, ready for next run")
            next_action = 'continue'
            message = f"Page {starting_page} completed, ready for next page"
        
        return jsonify({
            'success': True,
            'run_completed': True,
            'records_persisted': inserted_count,
            'highest_successful_page': highest_page,
            'project_complete': is_complete,
            'next_action': next_action,
            'message': message
        }), 200
        
    except Exception as e:
        logger.error(f'[complete-run] Uncaught error: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500


# Backwards compatibility alias for old batch routes
@resume_bp.route('/batch/start', methods=['POST'])
def batch_start_alias():
    """Backwards compatibility wrapper that calls the new resume start"""
    data = request.get_json()
    
    # Convert old batch params to new resume params if needed
    if 'project_token' in data:
        request.json = {
            'project_token': data.get('project_token'),
            'project_id': data.get('project_id')
        }
    
    return start_resume_scraping()


# ──────────────────────────────────────────────────────────────────────────────
# LIVE RUN (Snowflake + ParseHub) — monitoring UI
# ──────────────────────────────────────────────────────────────────────────────

@resume_bp.route('/<project_token>/runs/live', methods=['GET'])
def get_project_runs_live(project_token: str):
    """
    Latest run row from Snowflake RUNS plus live pages from ParseHub GET /runs/{token}.
    completion: pages_scraped >= total_pages from metadata (when both set).
    """
    try:
        db: ParseHubDatabase = g.db
        pid = db.get_project_id_by_token(project_token)
        if not pid:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        meta_list = db.get_metadata_by_project_token(project_token) or []
        total_pages = None
        if meta_list:
            m0 = meta_list[0]
            total_pages = m0.get('total_pages') or m0.get('TOTAL_PAGES')

        row = db.get_latest_run_row_for_project(pid)
        run_token = None
        db_pages = 0
        db_status = None
        if row:
            rl = {k.lower(): v for k, v in row.items()} if isinstance(row, dict) else row
            run_token = rl.get('run_token')
            db_pages = int(rl.get('pages_scraped') or 0)
            db_status = rl.get('status')

        live_pages = db_pages
        parsehub_status = None
        api_key = os.getenv('PARSEHUB_API_KEY')
        base = os.getenv('PARSEHUB_API_SITE', 'https://www.parsehub.com/api/v2')
        if api_key and run_token:
            try:
                r = requests.get(
                    f'{base.rstrip("/")}/runs/{run_token}',
                    params={'api_key': api_key},
                    timeout=15,
                )
                if r.status_code == 200:
                    j = r.json()
                    parsehub_status = j.get('status')
                    lp = j.get('pages_scraped')
                    if lp is None:
                        lp = j.get('pages')
                    if lp is not None:
                        try:
                            live_pages = int(lp)
                        except (TypeError, ValueError):
                            pass
            except Exception as ex:
                logger.debug(f'[runs/live] ParseHub run fetch: {ex}')

        max_pages = live_pages
        highest_source_page = None
        try:
            cur = db.cursor()
            cur.execute(
                'SELECT MAX(source_page) AS mx FROM scraped_records WHERE project_id = %s',
                (pid,),
            )
            sr = cur.fetchone()
            if sr:
                h = sr.get('mx') if isinstance(sr, dict) else (sr[0] if sr else None)
                if h is not None:
                    highest_source_page = int(h)
                    max_pages = max(max_pages or 0, highest_source_page)
        except Exception as hx:
            logger.debug(f'[runs/live] scraped_records max page: {hx}')

        if total_pages is not None:
            try:
                tp = int(total_pages)
                is_complete = (max_pages or 0) >= tp
            except (TypeError, ValueError):
                is_complete = False
        else:
            is_complete = False

        return jsonify({
            'success': True,
            'project_token': project_token,
            'project_id': pid,
            'total_pages': total_pages,
            'run_token': run_token,
            'pages_scraped': live_pages,
            'highest_source_page': highest_source_page,
            'max_pages_seen': max_pages,
            'db_pages_scraped': db_pages,
            'status': parsehub_status or db_status,
            'is_complete': is_complete,
            'complete_reason': (
                f'Progress ({max_pages}) reached metadata total_pages ({total_pages})'
                if is_complete and total_pages is not None
                else None
            ),
        }), 200
    except Exception as e:
        logger.error(f'[runs/live] {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# AUTO-COMPLETION STATUS
# ──────────────────────────────────────────────────────────────────────────────

def _fetch_parsehub_last_run(project_token: str) -> Optional[Dict[str, Any]]:
    """
    Live status from ParseHub for runs started outside this app (e.g. ParseHub UI).
    GET /v2/projects/{project_token} includes last_run with status.
    """
    api_key = os.getenv('PARSEHUB_API_KEY')
    if not api_key or not project_token:
        return None
    try:
        base = os.getenv('PARSEHUB_API_SITE', 'https://www.parsehub.com/api/v2')
        r = requests.get(
            f'{base.rstrip("/")}/projects/{project_token}',
            params={'api_key': api_key},
            timeout=15,
        )
        if r.status_code != 200:
            logger.debug(f'[parsehub_live] project {project_token[:8]}... HTTP {r.status_code}')
            return None
        data = r.json()
        last_run = data.get('last_run')
        if not last_run or not isinstance(last_run, dict):
            return None
        status_raw = (last_run.get('status') or '').lower()
        # ParseHub uses various in-progress states
        running_like = status_raw in (
            'running', 'queued', 'initialized', 'starting'
        )
        return {
            'run_token': last_run.get('run_token'),
            'status': last_run.get('status'),
            'pages_scraped': last_run.get('pages_scraped') or last_run.get('pages') or 0,
            'is_running': running_like,
            'source': 'parsehub',
        }
    except Exception as e:
        logger.warning(f'[parsehub_live] Failed to fetch live run for {project_token}: {e}')
        return None


@resume_bp.route('/auto-complete/status', methods=['GET'])
def get_auto_complete_status():
    """
    Get status of all auto-completing runs
    
    Response:
    {
        "success": true,
        "active_runs": [
            {
                "run_token": "tRaF3uZQ6okz",
                "project_id": 37,
                "starting_page": 5,
                "status": "monitoring",
                "started_at": "2026-03-27T10:30:00",
                "attempts": 12
            }
        ],
        "recent_history": [
            {
                "run_token": "tRaF3uZQ6okz",
                "status": "completed",
                "records_persisted": 50,
                "completed_at": "2026-03-27T10:35:00"
            }
        ]
    }
    """
    try:
        from src.services.auto_complete_service import get_auto_complete_service, _active_runs, _run_history
        
        service = get_auto_complete_service()
        
        # Format active runs (include project_token for frontend filtering)
        active_runs = []
        for token, data in _active_runs.items():
            active_runs.append({
                'run_token': token,
                'project_id': data.get('project_id'),
                'project_token': data.get('project_token'),
                'starting_page': data.get('starting_page'),
                'status': data.get('status'),
                'started_at': data.get('started_at').isoformat() if data.get('started_at') else None,
                'last_checked': data.get('last_checked').isoformat() if data.get('last_checked') else None,
                'attempts': data.get('attempts', 0),
                'auto_continue': data.get('auto_continue', False)
            })
        
        # Format history
        history = []
        for item in _run_history:
            history.append({
                'run_token': item.get('run_token'),
                'status': item.get('status'),
                'error': item.get('error'),
                'records_persisted': item.get('records_persisted'),
                'highest_page': item.get('highest_page'),
                'project_complete': item.get('project_complete'),
                'completed_at': item.get('completed_at').isoformat() if item.get('completed_at') else None
            })
        
        project_token_q = request.args.get('project_token')
        parsehub_live = None
        if project_token_q:
            parsehub_live = _fetch_parsehub_last_run(project_token_q)

        return jsonify({
            'success': True,
            'service_running': service is not None,
            'active_runs': active_runs,
            'active_count': len(active_runs),
            'recent_history': history,
            'parsehub_live': parsehub_live,
        }), 200
        
    except Exception as e:
        logger.error(f'[auto-complete/status] Error: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to get status: {str(e)}'
        }), 500
