#!/usr/bin/env python3
"""
Incremental Scraping Manager (Refactored)
Orchestrates chunk-based (10-page batch) pagination using backend-owned URL generation
No more continuation projects or continuation runs - single project handles all batches

Architecture:
- Reads checkpoint from DB (current_page_scraped)
- Generates next 10-page batch URLs
- Triggers ParseHub run with first batch URL
- Polls for completion and fetches results
- Stores with source_page tracking
- Updates checkpoint (max source_page from batch)
- Repeats until no data returned

Key improvements:
✓ Single ParseHub project (no project duplication)
✓ Backend-owned batching logic
✓ Proper checkpoint resume
✓ Idempotent batch processing
✓ Deduplication via source_page tracking
"""

import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

root_dir = Path(__file__).parent.parent.parent  # backend/
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.models.database import ParseHubDatabase
from src.services.chunk_pagination_orchestrator import ChunkPaginationOrchestrator

load_dotenv('.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IncrementalScrapingManager:
    """
    Refactored manager using chunk-based orchestration instead of continuation projects
    """
    
    def __init__(self):
        self.db = ParseHubDatabase()
        self.orchestrator = ChunkPaginationOrchestrator()
        
        api_key = os.getenv('PARSEHUB_API_KEY')
        if not api_key:
            raise ValueError("PARSEHUB_API_KEY not configured")
    
    def check_and_run_batch_scraping(self, max_batches: Optional[int] = 1) -> Dict:
        """
        Check all projects needing completion and run batch cycles on each
        
        Args:
            max_batches: Max batches to run per project (None = unlimited)
        
        Returns:
            {
                'projects_processed': int,
                'total_items_stored': int,
                'projects': [
                    {
                        'project_id': int,
                        'project_name': str,
                        'success': bool,
                        'batches': int,
                        'items': int,
                        'end_reason': str,
                        'error': str
                    }
                ]
            }
        """
        logger.info("\n" + "="*80)
        logger.info("[MANAGER] Starting incremental scraping batch cycles")
        logger.info("="*80)
        
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            # Get projects that need completion
            cursor.execute('''
                SELECT p.id, p.token, m.total_pages, m.current_page_scraped, 
                       m.project_name, m.start_url
                FROM projects p
                INNER JOIN metadata m ON p.id = m.project_id
                WHERE m.total_pages > 0 AND m.current_page_scraped < m.total_pages
                ORDER BY p.id ASC
            ''')
            
            projects_needing_work = cursor.fetchall()
            self.db.disconnect()
            
            if not projects_needing_work:
                logger.info("[MANAGER] No projects need completion work")
                return {
                    'projects_processed': 0,
                    'total_items_stored': 0,
                    'projects': []
                }
            
            logger.info(f"[MANAGER] Found {len(projects_needing_work)} projects needing work")
            
            results = []
            total_items = 0
            
            for row in projects_needing_work:
                project_id = row.get('id') if isinstance(row, dict) else row[0]
                project_token = row.get('token') if isinstance(row, dict) else row[1]
                total_pages = row.get('total_pages') if isinstance(row, dict) else row[2]
                current_page_scraped = row.get('current_page_scraped') if isinstance(row, dict) else row[3]
                project_name = row.get('project_name') if isinstance(row, dict) else row[4]
                start_url = row.get('start_url') if isinstance(row, dict) else row[5]
                
                logger.info(f"\n[MANAGER] Processing project: {project_name}")
                logger.info(f"          ID: {project_id}, Progress: {current_page_scraped}/{total_pages}")
                
                if not start_url:
                    logger.warning(f"[MANAGER] Project {project_id} has no start_url, skipping")
                    results.append({
                        'project_id': project_id,
                        'project_name': project_name,
                        'success': False,
                        'batches': 0,
                        'items': 0,
                        'error': 'No start_url in metadata'
                    })
                    continue
                
                # Run batch cycle for this project
                cycle_result = self.orchestrator.run_scraping_batch_cycle(
                    project_id=project_id,
                    project_token=project_token,
                    base_url=start_url,
                    max_batches=max_batches
                )
                
                items_stored = cycle_result.get('total_items_stored', 0)
                total_items += items_stored
                
                results.append({
                    'project_id': project_id,
                    'project_name': project_name,
                    'success': cycle_result.get('success', False),
                    'batches': cycle_result.get('batches_completed', 0),
                    'items': items_stored,
                    'max_pages': cycle_result.get('total_pages_reached', 0),
                    'end_reason': cycle_result.get('end_reason', 'Unknown'),
                    'error': cycle_result.get('error')
                })
            
            logger.info("\n" + "="*80)
            logger.info(f"[MANAGER] Batch cycles complete: {len(results)} projects processed")
            logger.info(f"[MANAGER] Total items stored: {total_items}")
            logger.info("="*80 + "\n")
            
            return {
                'projects_processed': len(results),
                'total_items_stored': total_items,
                'projects': results
            }
        
        except Exception as e:
            logger.error(f"[MANAGER] Fatal error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'projects_processed': 0,
                'total_items_stored': 0,
                'projects': [],
                'error': str(e)
            }
    
    def run_batch_for_project(self, project_id: int, max_batches: Optional[int] = None) -> Dict:
        """
        Run batch scraping for a specific project
        
        Returns:
            {
                'success': bool,
                'batches_completed': int,
                'items_stored': int,
                'error': str
            }
        """
        logger.info(f"\n[SINGLE_PROJECT] Running batches for project {project_id}")
        
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            # Get project details
            cursor.execute('''
                SELECT p.token, m.project_name, m.start_url
                FROM projects p
                INNER JOIN metadata m ON p.id = m.project_id
                WHERE p.id = %s
            ''', (project_id,))
            
            result = cursor.fetchone()
            self.db.disconnect()
            
            if not result:
                return {
                    'success': False,
                    'error': f'Project {project_id} not found'
                }
            
            project_token = result.get('token') if isinstance(result, dict) else result[0]
            start_url = result.get('start_url') if isinstance(result, dict) else result[2]
            
            if not start_url:
                return {
                    'success': False,
                    'error': 'Project has no start_url'
                }
            
            # Run batch cycle
            cycle_result = self.orchestrator.run_scraping_batch_cycle(
                project_id=project_id,
                project_token=project_token,
                base_url=start_url,
                max_batches=max_batches
            )
            
            return {
                'success': cycle_result.get('success', False),
                'batches_completed': cycle_result.get('batches_completed', 0),
                'items_stored': cycle_result.get('total_items_stored', 0),
                'end_reason': cycle_result.get('end_reason'),
                'error': cycle_result.get('error')
            }
        
        except Exception as e:
            logger.error(f"[SINGLE_PROJECT] Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': str(e)
            }


def main():
    """Main entry point"""
    logger.info("="*80)
    logger.info("ParseHub Incremental Scraping Manager (Batch-Based)")
    logger.info("="*80)
    
    manager = IncrementalScrapingManager()
    
    # Run batch scraping for all projects needing completion (1 batch each)
    result = manager.check_and_run_batch_scraping(max_batches=1)
    
    logger.info("\n[SUMMARY]")
    logger.info(f"Projects processed: {result['projects_processed']}")
    logger.info(f"Total items stored: {result['total_items_stored']}")
    
    for project in result.get('projects', []):
        status = "✓" if project['success'] else "✗"
        logger.info(f"{status} {project['project_name']}: "
                   f"{project['batches']} batches, {project['items']} items")
        if project.get('error'):
            logger.error(f"  Error: {project['error']}")


if __name__ == '__main__':
    main()
