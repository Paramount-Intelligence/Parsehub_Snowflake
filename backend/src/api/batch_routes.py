"""
Batch Scraping API Routes

Handles all batch-based scraping operations:
- Start batch scraping (fresh or resume from checkpoint)
- Monitor batch progress in real-time
- Retry failed batches
- Get batch history and statistics
"""

from flask import Blueprint, request, jsonify, g
import logging
from typing import Dict, Optional, Tuple
from src.services.chunk_pagination_orchestrator import ChunkPaginationOrchestrator
from src.models.database import ParseHubDatabase

logger = logging.getLogger(__name__)

# Create blueprint
batch_bp = Blueprint('batch', __name__, url_prefix='/api/projects')


# ──────────────────────────────────────────────────────────────────────────────
# START BATCH SCRAPING
# ──────────────────────────────────────────────────────────────────────────────

@batch_bp.route('/batch/start', methods=['POST'])
def start_batch_scraping():
    """
    Start a new batch scraping session or resume from checkpoint.
    
    Request body:
    {
        "project_token": "tXXXXXXXXXXXXX",
        "project_url": "https://example.com/page=1",  (optional - will use metadata URL if not provided)
        "project_name": "Project Name",  (optional - for logging)
        "resume_from_checkpoint": false  (true to resume from last completed page)
    }
    
    Response:
    {
        "success": true,
        "run_token": "abc123def456",
        "session_id": "sess_123",
        "batch_number": 1,
        "batch_range": "1-10 pages",
        "checkpoint": {
            "last_completed_page": 0,
            "next_start_page": 1,
            "total_pages": 100
        }
    }
    """
    try:
        data = request.get_json()
        project_token = data.get('project_token')
        project_url = data.get('project_url', '')
        project_name = data.get('project_name', 'Unknown')
        resume_from_checkpoint = data.get('resume_from_checkpoint', False)
        
        if not project_token:
            return jsonify({
                'success': False,
                'error': 'project_token is required'
            }), 400
        
        db: ParseHubDatabase = g.db
        orchestrator = ChunkPaginationOrchestrator()
        
        # Try to get project metadata, but don't fail if it doesn't exist
        # Metadata is optional - we can work with frontend-provided data
        project_id = project_token  # Use token as project_id fallback
        total_pages = 100  # Default total pages
        
        try:
            metadata = db.get_metadata_filtered(project_token=project_token, limit=1)
            if metadata and len(metadata) > 0:
                metadata_record = metadata[0]
                project_id = metadata_record.get('id') or metadata_record.get('ID') or project_token
                total_pages = int(metadata_record.get('total_pages') or metadata_record.get('TOTAL_PAGES') or 100)
                
                # Use provided URL or fall back to metadata
                if not project_url:
                    project_url = metadata_record.get('last_known_url') or metadata_record.get('LAST_KNOWN_URL') or project_url
                
                logger.info(f'[batch/start] Found metadata for project {project_token}: id={project_id}, total_pages={total_pages}')
            else:
                logger.info(f'[batch/start] No metadata found for project {project_token}, using defaults: id={project_token}, total_pages={total_pages}')
        except Exception as e:
            logger.warning(f'[batch/start] Error fetching metadata for {project_token}: {e}. Using defaults.')
            # Continue with defaults
            pass
        
        # Get or create checkpoint
        try:
            checkpoint = orchestrator.get_checkpoint(project_id)
            logger.info(f'[batch/start] Checkpoint for project {project_token}: {checkpoint}')
        except Exception as e:
            logger.warning(f'[batch/start] No checkpoint found, starting fresh: {e}')
            checkpoint = {
                'last_completed_page': 0,
                'next_start_page': 1,
                'total_pages': total_pages,
                'total_batches_completed': 0
            }
        
        # Determine start page
        if resume_from_checkpoint and checkpoint.get('last_completed_page', 0) > 0:
            start_page = checkpoint.get('next_start_page', checkpoint.get('last_completed_page', 0) + 1)
            batch_number = checkpoint.get('total_batches_completed', 0) + 1
            logger.info(f'[batch/start] Resuming from page {start_page}, batch {batch_number}')
        else:
            start_page = 1
            batch_number = 1
            logger.info(f'[batch/start] Starting fresh from page 1')
        
        # Generate batch URLs (10 pages per batch)
        try:
            batch_urls = orchestrator.generate_batch_urls(project_url, start_page)
            if not batch_urls:
                return jsonify({
                    'success': False,
                    'error': f'Failed to generate batch URLs from {project_url}'
                }), 400
            
            end_page = min(start_page + len(batch_urls) - 1, total_pages)
            batch_range = f"{start_page}-{end_page} pages"
            
        except Exception as e:
            logger.error(f'[batch/start] Error generating batch URLs: {e}')
            return jsonify({
                'success': False,
                'error': f'Failed to generate batch URLs: {str(e)}'
            }), 500
        
        # Trigger batch run with ParseHub
        try:
            start_url = batch_urls[0] if batch_urls else project_url
            logger.info(f'[batch/start] About to call trigger_batch_run with: project_token={project_token}, start_url={start_url}, batch_start_page={start_page}, batch_end_page={end_page}')
            run_result = orchestrator.trigger_batch_run(
                project_token=project_token,
                start_url=start_url,
                batch_start_page=start_page,
                batch_end_page=end_page
            )
            logger.info(f'[batch/start] trigger_batch_run returned: {run_result}')
            
            if not run_result.get('success'):
                return jsonify({
                    'success': False,
                    'error': run_result.get('error', 'Failed to trigger ParseHub run')
                }), 500
            
            run_token = run_result.get('run_token')
            
        except Exception as e:
            logger.error(f'[batch/start] Error triggering batch run: {e}')
            return jsonify({
                'success': False,
                'error': f'Failed to trigger batch run: {str(e)}'
            }), 500
        
        # Store batch metadata using monitoring session
        try:
            # Create monitoring session for this batch run
            session_id = db.create_monitoring_session(
                project_id=project_id,
                run_token=run_token,
                target_pages=end_page - start_page + 1
            )
            
        except Exception as e:
            logger.warning(f'[batch/start] Could not save session metadata: {e}')
            session_id = None  # Will use run_token as fallback
        
        logger.info(
            f'[batch/start] ✅ Started batch {batch_number} for {project_name} '
            f'({batch_range}), run_token={run_token}'
        )
        
        return jsonify({
            'success': True,
            'run_token': run_token,
            'session_id': session_id or run_token,
            'batch_number': batch_number,
            'batch_range': batch_range,
            'checkpoint': {
                'last_completed_page': checkpoint.get('last_completed_page', 0),
                'next_start_page': start_page,
                'total_pages': total_pages,
                'total_batches_completed': checkpoint.get('total_batches_completed', 0)
            }
        }), 201
        
    except Exception as e:
        logger.error(f'[batch/start] Uncaught error: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET CHECKPOINT
# ──────────────────────────────────────────────────────────────────────────────

@batch_bp.route('/<project_token>/checkpoint', methods=['GET'])
def get_checkpoint(project_token: str):
    """
    Get the checkpoint (resumable state) for a project.
    
    Response:
    {
        "last_completed_page": 40,
        "next_start_page": 41,
        "total_pages": 100,
        "total_batches_completed": 4,
        "failed_batches": 0,
        "consecutive_empty_batches": 0,
        "checkpoint_timestamp": "2024-01-15T14:00:00"
    }
    """
    try:
        db: ParseHubDatabase = g.db
        orchestrator = ChunkPaginationOrchestrator()
        
        # Get project metadata
        try:
            metadata = db.get_metadata_filtered(project_token=project_token, limit=1)
            if not metadata or len(metadata) == 0:
                return jsonify({
                    'last_completed_page': 0,
                    'next_start_page': 1,
                    'total_pages': 0,
                    'total_batches_completed': 0,
                    'failed_batches': 0
                }), 200  # Return empty checkpoint, don't fail
            
            metadata_record = metadata[0]
            project_id = metadata_record.get('id') or metadata_record.get('ID')
            total_pages = metadata_record.get('total_pages') or metadata_record.get('TOTAL_PAGES') or 100
            
        except Exception as e:
            logger.warning(f'[checkpoint] Error fetching metadata: {e}')
            return jsonify({
                'last_completed_page': 0,
                'next_start_page': 1,
                'total_pages': 0,
                'total_batches_completed': 0
            }), 200
        
        # Get checkpoint from orchestrator
        try:
            checkpoint = orchestrator.get_checkpoint(project_id)
        except Exception as e:
            logger.debug(f'[checkpoint] No checkpoint found: {e}')
            checkpoint = {
                'last_completed_page': 0,
                'next_start_page': 1,
                'total_batches_completed': 0
            }
        
        return jsonify({
            'last_completed_page': checkpoint.get('last_completed_page', 0),
            'next_start_page': checkpoint.get('next_start_page', 
                                             checkpoint.get('last_completed_page', 0) + 1),
            'total_pages': total_pages,
            'total_batches_completed': checkpoint.get('total_batches_completed', 0),
            'failed_batches': checkpoint.get('failed_batches', 0),
            'consecutive_empty_batches': checkpoint.get('consecutive_empty_batches', 0),
            'checkpoint_timestamp': checkpoint.get('checkpoint_timestamp', None)
        }), 200
        
    except Exception as e:
        logger.error(f'[checkpoint] Uncaught error: {e}', exc_info=True)
        return jsonify({
            'last_completed_page': 0,
            'next_start_page': 1,
            'error': str(e)
        }), 200  # Return best-effort response


# ──────────────────────────────────────────────────────────────────────────────
# BATCH STATUS
# ──────────────────────────────────────────────────────────────────────────────

@batch_bp.route('/batch/status', methods=['GET'])
def get_batch_status():
    """
    Poll the status of a running batch.
    
    Query params:
    - run_token: The run token to poll
    
    Response:
    {
        "batch_number": 5,
        "batch_range": "41-50 pages",
        "status": "scraping",  (scraping|paused|completed|failed)
        "records_in_batch": 32,
        "total_records_to_date": 425,
        "error": null
    }
    """
    try:
        run_token = request.args.get('run_token')
        if not run_token:
            return jsonify({
                'success': False,
                'error': 'run_token query parameter is required'
            }), 400
        
        orchestrator = ChunkPaginationOrchestrator()
        
        # Poll ParseHub for run status
        try:
            status_result = orchestrator.poll_run_completion(run_token)
            
            # For now, return simplified status
            # In production, you'd query the monitoring session to get batch details
            return jsonify({
                'batch_number': 1,
                'batch_range': "1-10 pages",
                'status': 'completed' if status_result.get('success') else 'scraping',
                'records_in_batch': status_result.get('data_count', 0),
                'total_records_to_date': status_result.get('data_count', 0),
                'error': status_result.get('error')
            }), 200
            
        except Exception as e:
            logger.error(f'[batch/status] Error polling run: {e}')
            return jsonify({
                'batch_number': 0,
                'status': 'error',
                'error': str(e)
            }), 500
        
    except Exception as e:
        logger.error(f'[batch/status] Uncaught error: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# BATCH RECORDS
# ──────────────────────────────────────────────────────────────────────────────

@batch_bp.route('/batch/records', methods=['GET'])
def get_batch_records():
    """
    Get records scraped in current batch.
    
    Query params:
    - run_token: The run token
    - limit: Max records to return (default 100)
    
    Response:
    {
        "records": [
            { "id": 1, "title": "...", "source_page": 1, ... },
            ...
        ],
        "total_count": 425,
        "batch_count": 432
    }
    """
    try:
        run_token = request.args.get('run_token')
        limit = request.args.get('limit', 100, type=int)
        
        if not run_token:
            return jsonify({
                'success': False,
                'error': 'run_token query parameter is required'
            }), 400
        
        db: ParseHubDatabase = g.db
        
        # Get records for this run using cursor
        try:
            cursor = db.cursor()
            cursor.execute(
                """
                SELECT * FROM data 
                WHERE run_token = %s 
                ORDER BY created_at DESC 
                LIMIT %s
                """,
                (run_token, limit)
            )
            
            records = cursor.fetchall()
            if not records:
                records = []
            
            # Count total records
            cursor.execute(
                "SELECT COUNT(*) as count FROM data WHERE run_token = %s",
                (run_token,)
            )
            result = cursor.fetchone()
            total_count = result.get('count') if isinstance(result, dict) else (result[0] if result else 0)
            
            return jsonify({
                'records': records if isinstance(records, list) else list(records),
                'total_count': total_count,
                'batch_count': len(records) if records else 0
            }), 200
            
        except Exception as e:
            logger.error(f'[batch/records] Error fetching records: {e}')
            return jsonify({
                'records': [],
                'total_count': 0,
                'batch_count': 0,
                'error': str(e)
            }), 500
        
    except Exception as e:
        logger.error(f'[batch/records] Uncaught error: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# RETRY FAILED BATCH
# ──────────────────────────────────────────────────────────────────────────────

@batch_bp.route('/<project_token>/batch/retry', methods=['POST'])
def retry_failed_batch(project_token: str):
    """
    Retry a failed batch.
    
    Request body:
    {
        "batch_number": 5  (optional - if not provided, retries last batch)
    }
    
    Response:
    {
        "success": true,
        "run_token": "new_run_token",
        "batch_number": 5,
        "message": "Batch retry initiated"
    }
    """
    try:
        data = request.get_json() or {}
        db: ParseHubDatabase = g.db
        orchestrator = ChunkPaginationOrchestrator()
        
        # Get project metadata (optional - use defaults if not found)
        project_url = None
        project_id = project_token  # Fallback to token
        
        try:
            metadata = db.get_metadata_filtered(project_token=project_token, limit=1)
            if metadata and len(metadata) > 0:
                metadata_record = metadata[0]
                project_id = metadata_record.get('id') or metadata_record.get('ID') or project_token
                project_url = metadata_record.get('last_known_url') or metadata_record.get('LAST_KNOWN_URL')
                logger.info(f'[retry] Found metadata for project {project_token}')
            else:
                logger.warning(f'[retry] No metadata found for project {project_token}, using defaults')
                # Use defaults - project_url can be empty for retry, we'll work with what we have
                
        except Exception as e:
            logger.warning(f'[retry] Error fetching metadata: {e}, using defaults')
        
        # Get checkpoint to find the failed batch pages
        try:
            checkpoint = orchestrator.get_checkpoint(project_id)
            failed_batch_number = checkpoint.get('total_batches_completed', 0) + 1
            start_page = checkpoint.get('next_start_page', 1)
            end_page = min(start_page + 9, checkpoint.get('total_pages', 100))
            
        except Exception as e:
            logger.warning(f'[retry] Error getting checkpoint: {e}')
            return jsonify({
                'success': False,
                'error': 'Could not determine failed batch'
            }), 400
        
        # Retry the batch
        try:
            batch_urls = orchestrator.generate_batch_urls(project_url, start_page)
            run_result = orchestrator.trigger_batch_run(
                project_token=project_token,
                start_url=batch_urls[0] if batch_urls else project_url,
                batch_start_page=start_page,
                batch_end_page=end_page
            )
            
            if not run_result.get('success'):
                return jsonify({
                    'success': False,
                    'error': run_result.get('error', 'Failed to retry batch')
                }), 500
            
            return jsonify({
                'success': True,
                'run_token': run_result.get('run_token'),
                'batch_number': failed_batch_number,
                'message': f'Batch {failed_batch_number} retry initiated'
            }), 200
            
        except Exception as e:
            logger.error(f'[retry] Error retrying batch: {e}')
            return jsonify({
                'success': False,
                'error': f'Failed to retry batch: {str(e)}'
            }), 500
        
    except Exception as e:
        logger.error(f'[retry] Uncaught error: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# STOP BATCH SCRAPING
# ──────────────────────────────────────────────────────────────────────────────

@batch_bp.route('/batch/stop', methods=['POST'])
def stop_batch_scraping():
    """
    Stop a running batch scraping session.
    
    Request body:
    {
        "run_token": "abc123def456"
    }
    
    Response:
    {
        "success": true,
        "message": "Batch scraping stopped"
    }
    """
    try:
        data = request.get_json()
        run_token = data.get('run_token')
        
        if not run_token:
            return jsonify({
                'success': False,
                'error': 'run_token is required'
            }), 400
        
        db: ParseHubDatabase = g.db
        
        # Mark session as stopped using cursor
        try:
            cursor = db.cursor()
            cursor.execute(
                """UPDATE runs SET status = %s WHERE run_token = %s""",
                ('stopped', run_token)
            )
            logger.info(f'[batch/stop] Stopped batch run {run_token}')
            
            return jsonify({
                'success': True,
                'message': 'Batch scraping stopped'
            }), 200
            
        except Exception as e:
            logger.error(f'[batch/stop] Error stopping batch: {e}')
            return jsonify({
                'success': False,
                'error': f'Failed to stop batch: {str(e)}'
            }), 500
        
    except Exception as e:
        logger.error(f'[batch/stop] Uncaught error: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# BATCH HISTORY
# ──────────────────────────────────────────────────────────────────────────────

@batch_bp.route('/<project_token>/batch/history', methods=['GET'])
def get_batch_history(project_token: str):
    """
    Get batch scraping history for a project.
    
    Query params:
    - limit: Max batches to return (default 20)
    
    Response:
    {
        "batch_history": [
            {
                "batch_number": 1,
                "batch_range": "1-10",
                "status": "completed|failed",
                "records_scraped": 125,
                "started_at": "2024-01-15T10:00:00",
                "completed_at": "2024-01-15T10:15:00",
                "error_message": null
            },
            ...
        ],
        "last_checkpoint": { ... }
    }
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        db: ParseHubDatabase = g.db
        orchestrator = ChunkPaginationOrchestrator()
        
        # Get project metadata
        try:
            metadata = db.get_metadata_filtered(project_token=project_token, limit=1)
            if not metadata or len(metadata) == 0:
                return jsonify({
                    'batch_history': [],
                    'last_checkpoint': None
                }), 200
            
            metadata_record = metadata[0]
            project_id = metadata_record.get('id') or metadata_record.get('ID')
            
        except Exception as e:
            logger.warning(f'[history] Error fetching metadata: {e}')
            return jsonify({
                'batch_history': [],
                'last_checkpoint': None
            }), 200
        
        # Get batch history using cursor
        try:
            cursor = db.cursor()
            cursor.execute(
                """
                SELECT * FROM runs 
                WHERE project_id = %s AND is_batch_run = TRUE
                ORDER BY created_at DESC 
                LIMIT %s
                """,
                (project_id, limit)
            )
            
            history_records = cursor.fetchall()
            if not history_records:
                history_records = []
            
            checkpoint = orchestrator.get_checkpoint(project_id)
            
            # Format history
            formatted_history = []
            for idx, run in enumerate(history_records, 1):
                if isinstance(run, dict):
                    formatted_history.append({
                        'batch_number': idx,
                        'batch_range': f"{run.get('start_page', 1)}-{run.get('end_page', 10)}",
                        'status': run.get('status', 'unknown'),
                        'records_scraped': run.get('records_count', 0),
                        'started_at': run.get('created_at'),
                        'completed_at': run.get('updated_at'),
                        'error_message': run.get('error_message', '')
                    })
                else:
                    # Tuple format - map indices based on run table schema
                    formatted_history.append({
                        'batch_number': idx,
                        'batch_range': f"{run[5] if len(run) > 5 else 1}-{run[6] if len(run) > 6 else 10}",
                        'status': run[3] if len(run) > 3 else 'unknown',
                        'records_scraped': run[4] if len(run) > 4 else 0,
                        'started_at': run[1] if len(run) > 1 else None,
                        'completed_at': run[2] if len(run) > 2 else None,
                        'error_message': ''
                    })
            
            return jsonify({
                'batch_history': formatted_history,
                'last_checkpoint': checkpoint
            }), 200
            
        except Exception as e:
            logger.error(f'[history] Error fetching history: {e}')
            return jsonify({
                'batch_history': [],
                'last_checkpoint': None,
                'error': str(e)
            }), 500
        
    except Exception as e:
        logger.error(f'[history] Uncaught error: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# BATCH STATISTICS
# ──────────────────────────────────────────────────────────────────────────────

@batch_bp.route('/<project_token>/batch/statistics', methods=['GET'])
def get_batch_statistics(project_token: str):
    """
    Get batch scraping statistics for a project.
    
    Response:
    {
        "total_batches": 15,
        "completed_batches": 14,
        "failed_batches": 1,
        "total_records": 4250,
        "avg_records_per_batch": 283,
        "success_rate": 93.3,
        "last_scraped_at": "2024-01-15T14:30:00",
        "estimated_completion": {
            "batches_remaining": 2,
            "estimated_pages_remaining": 20
        }
    }
    """
    try:
        db: ParseHubDatabase = g.db
        orchestrator = ChunkPaginationOrchestrator()
        
        # Get project metadata
        try:
            metadata = db.get_metadata_filtered(project_token=project_token, limit=1)
            if not metadata or len(metadata) == 0:
                return jsonify({
                    'total_batches': 0,
                    'completed_batches': 0,
                    'failed_batches': 0,
                    'total_records': 0,
                    'success_rate': 0,
                }), 200
            
            metadata_record = metadata[0]
            project_id = metadata_record.get('id') or metadata_record.get('ID')
            total_pages = metadata_record.get('total_pages') or metadata_record.get('TOTAL_PAGES') or 100
            
        except Exception as e:
            logger.warning(f'[statistics] Error fetching metadata: {e}')
            return jsonify({
                'total_batches': 0,
                'completed_batches': 0,
                'error': str(e)
            }), 200
        
        # Get statistics
        try:
            checkpoint = orchestrator.get_checkpoint(project_id)
            
            # Calculate statistics
            total_batches_completed = checkpoint.get('total_batches_completed', 0)
            failed_batches = checkpoint.get('failed_batches', 0)
            total_batches = total_batches_completed + failed_batches if failed_batches else total_batches_completed
            success_rate = (total_batches_completed / total_batches * 100) if total_batches > 0 else 0
            
            # Get record count
            cursor = db.cursor()
            cursor.execute(
                "SELECT COUNT(*) as count FROM data WHERE project_id = %s",
                (project_id,)
            )
            result = cursor.fetchone()
            total_records = result['count'] if isinstance(result, dict) else result[0]
            
            avg_records_per_batch = (total_records / total_batches_completed) if total_batches_completed > 0 else 0
            
            # Calculate remaining
            last_completed_page = checkpoint.get('last_completed_page', 0)
            pages_remaining = max(0, total_pages - last_completed_page)
            batches_remaining = (pages_remaining + 9) // 10  # Round up to nearest batch
            
            last_scraped = checkpoint.get('checkpoint_timestamp')
            
            return jsonify({
                'total_batches': total_batches if total_batches > 0 else total_batches_completed,
                'completed_batches': total_batches_completed,
                'failed_batches': failed_batches,
                'total_records': total_records,
                'avg_records_per_batch': round(avg_records_per_batch, 0),
                'success_rate': round(success_rate, 1),
                'last_scraped_at': last_scraped,
                'estimated_completion': {
                    'batches_remaining': batches_remaining,
                    'estimated_pages_remaining': pages_remaining
                } if pages_remaining > 0 else None
            }), 200
            
        except Exception as e:
            logger.error(f'[statistics] Error calculating statistics: {e}')
            return jsonify({
                'total_batches': 0,
                'completed_batches': 0,
                'error': str(e)
            }), 500
        
    except Exception as e:
        logger.error(f'[statistics] Uncaught error: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# BATCH PROGRESS MONITORING
# ──────────────────────────────────────────────────────────────────────────────

@batch_bp.route('/batch/progress/<run_token>', methods=['GET'])
def get_batch_progress(run_token: str):
    """
    Get real-time progress for a batch run.
    
    Response:
    {
        "run_token": "abc123def456",
        "batch_number": 1,
        "batch_start_page": 1,
        "batch_end_page": 10,
        "current_page": 5,
        "records_extracted": 1250,
        "pages_completed": 4,
        "status": "running",
        "estimated_time_remaining": 120,
        "extraction_rate": 250.5
    }
    """
    try:
        db: ParseHubDatabase = g.db
        
        # Get run details
        cursor = db.cursor()
        cursor.execute('''
            SELECT 
                run_token,
                project_id,
                status,
                created_at,
                updated_at,
                source_page as current_page,
                record_count as records_extracted
            FROM runs
            WHERE run_token = %s
            LIMIT 1
        ''', (run_token,))
        
        run_record = cursor.fetchone()
        
        if not run_record:
            return jsonify({
                'error': 'Run not found',
                'run_token': run_token
            }), 404
        
        # Extract data
        status = run_record.get('status') if isinstance(run_record, dict) else run_record[2]
        created_at = run_record.get('created_at') if isinstance(run_record, dict) else run_record[4]
        updated_at = run_record.get('updated_at') if isinstance(run_record, dict) else run_record[5]
        current_page = run_record.get('current_page') if isinstance(run_record, dict) else run_record[6]
        records_extracted = run_record.get('records_extracted') if isinstance(run_record, dict) else run_record[7]
        
        # Get batch info from batch metadata (if stored in JSON)
        cursor.execute('''
            SELECT 
                extra_data,
                completed_pages
            FROM runs
            WHERE run_token = %s
        ''', (run_token,))
        
        batch_meta = cursor.fetchone()
        batch_start_page = 1
        batch_end_page = 10
        batch_number = 1
        
        if batch_meta:
            try:
                extra = batch_meta.get('extra_data') if isinstance(batch_meta, dict) else batch_meta[0]
                if extra and isinstance(extra, str):
                    import json
                    extra_data = json.loads(extra)
                    batch_start_page = extra_data.get('batch_start_page', 1)
                    batch_end_page = extra_data.get('batch_end_page', 10)
                    batch_number = extra_data.get('batch_number', 1)
            except:
                pass
        
        # Calculate metrics
        total_batch_pages = batch_end_page - batch_start_page + 1
        pages_completed = max(0, (current_page or batch_start_page) - batch_start_page)
        
        # Calculate extraction rate (records per page)
        extraction_rate = 0.0
        if pages_completed > 0:
            extraction_rate = (records_extracted or 0) / pages_completed
        
        # Estimate time remaining
        estimated_seconds_remaining = None
        if status == 'running':
            # Calculate based on extraction rate and pages left
            from datetime import datetime
            if created_at:
                elapsed = (datetime.now() - created_at).total_seconds()
                if elapsed > 0 and pages_completed > 0:
                    avg_seconds_per_page = elapsed / pages_completed
                    pages_remaining = total_batch_pages - pages_completed
                    estimated_seconds_remaining = avg_seconds_per_page * pages_remaining
        
        db.disconnect()
        
        return jsonify({
            'run_token': run_token,
            'batch_number': batch_number,
            'batch_start_page': batch_start_page,
            'batch_end_page': batch_end_page,
            'current_page': current_page or batch_start_page,
            'records_extracted': records_extracted or 0,
            'pages_completed': pages_completed,
            'status': status,
            'estimated_time_remaining': estimated_seconds_remaining,
            'extraction_rate': round(extraction_rate, 1),
            'total_batch_pages': total_batch_pages
        }), 200
        
    except Exception as e:
        logger.error(f'[batch_progress] Error: {e}', exc_info=True)
        return jsonify({
            'error': f'Failed to get batch progress: {str(e)}',
            'run_token': run_token
        }), 500
