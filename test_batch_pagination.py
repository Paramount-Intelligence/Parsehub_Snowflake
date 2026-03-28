#!/usr/bin/env python3
"""
Integration Test: Chunk-Based Pagination System
Demonstrates how to use the new batch-based scraping system

Usage:
    python test_batch_pagination.py --project-id 1 --batches 1
    python test_batch_pagination.py --all-projects --batches 5
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Setup path
root_dir = Path(__file__).parent / 'backend'
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('batch_pagination_test.log')
    ]
)
logger = logging.getLogger(__name__)

from src.models.database import ParseHubDatabase
from src.services.chunk_pagination_orchestrator import ChunkPaginationOrchestrator
from src.services.incremental_scraping_manager import IncrementalScrapingManager
from backend.migrations.batch_pagination_migration import (
    run_migration, get_latest_checkpoint, record_batch_checkpoint
)


class BatchPaginationTester:
    """Test harness for batch pagination system"""
    
    def __init__(self):
        self.db = ParseHubDatabase()
        self.orchestrator = ChunkPaginationOrchestrator()
        self.manager = IncrementalScrapingManager()
    
    def test_single_batch(self, project_id: int, max_batches: int = 1) -> dict:
        """Test batch scraping for a single project"""
        logger.info(f"\n{'='*80}")
        logger.info(f"TEST: Single project batch scraping")
        logger.info(f"Project ID: {project_id}, Max batches: {max_batches}")
        logger.info(f"{'='*80}")
        
        try:
            conn = self.db.connect()
            cursor = self.db.cursor()
            
            # Get project details
            cursor.execute('''
                SELECT p.id, p.token, m.project_name, m.start_url, 
                       m.total_pages, m.current_page_scraped
                FROM projects p
                INNER JOIN metadata m ON p.id = m.project_id
                WHERE p.id = %s
            ''', (project_id,))
            
            project = cursor.fetchone()
            self.db.disconnect()
            
            if not project:
                logger.error(f"Project {project_id} not found")
                return {'success': False, 'error': 'Project not found'}
            
            project_token = project.get('token') if isinstance(project, dict) else project[1]
            project_name = project.get('project_name') if isinstance(project, dict) else project[2]
            start_url = project.get('start_url') if isinstance(project, dict) else project[3]
            total_pages = project.get('total_pages') if isinstance(project, dict) else project[4]
            current_page = project.get('current_page_scraped') if isinstance(project, dict) else project[5]
            
            logger.info(f"Project: {project_name}")
            logger.info(f"Token: {project_token[:15]}...")
            logger.info(f"URL: {start_url}")
            logger.info(f"Progress: {current_page}/{total_pages}")
            
            if not start_url:
                logger.error("Project has no start_url in metadata")
                return {'success': False, 'error': 'No start_url'}
            
            # Run batch cycle
            result = self.orchestrator.run_scraping_batch_cycle(
                project_id=project_id,
                project_token=project_token,
                base_url=start_url,
                max_batches=max_batches
            )
            
            logger.info(f"\nRESULT:")
            logger.info(f"  Success: {result['success']}")
            logger.info(f"  Batches: {result['batches_completed']}")
            logger.info(f"  Items: {result['total_items_stored']}")
            logger.info(f"  Max Page: {result['total_pages_reached']}")
            logger.info(f"  Reason: {result['end_reason']}")
            
            if not result['success']:
                logger.error(f"  Error: {result.get('error')}")
            
            return result
        
        except Exception as e:
            logger.error(f"Test failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}
    
    def test_all_projects(self, max_batches: int = 1) -> dict:
        """Test batch scraping for all incomplete projects"""
        logger.info(f"\n{'='*80}")
        logger.info(f"TEST: All incomplete projects ({max_batches} batches each)")
        logger.info(f"{'='*80}")
        
        result = self.manager.check_and_run_batch_scraping(max_batches=max_batches)
        
        logger.info(f"\nRESULTS:")
        logger.info(f"  Projects processed: {result['projects_processed']}")
        logger.info(f"  Total items: {result['total_items_stored']}")
        
        for project in result.get('projects', []):
            status = "✓" if project['success'] else "✗"
            logger.info(f"  {status} {project['project_name']}: "
                       f"{project['batches']} batches, {project['items']} items")
            if project.get('error'):
                logger.error(f"    Error: {project['error']}")
        
        return result
    
    def test_checkpoint_system(self, project_id: int) -> dict:
        """Test checkpoint reading/writing"""
        logger.info(f"\n{'='*80}")
        logger.info(f"TEST: Checkpoint system for project {project_id}")
        logger.info(f"{'='*80}")
        
        try:
            # 1. Get current checkpoint
            checkpoint = self.orchestrator.get_checkpoint(project_id)
            logger.info(f"\nCurrent checkpoint:")
            logger.info(f"  Last completed page: {checkpoint['last_completed_page']}")
            logger.info(f"  Next start page: {checkpoint['next_start_page']}")
            logger.info(f"  Total pages: {checkpoint['total_pages']}")
            logger.info(f"  Batches completed: {checkpoint['total_chunks_completed']}")
            
            # 2. Update checkpoint (test - doesn't actually run)
            test_page = checkpoint['last_completed_page'] + 1
            success = self.orchestrator.update_checkpoint(project_id, test_page)
            logger.info(f"\nCheckpoint update test:")
            logger.info(f"  Updated to page: {test_page}")
            logger.info(f"  Success: {success}")
            
            # 3. Verify update
            new_checkpoint = self.orchestrator.get_checkpoint(project_id)
            logger.info(f"\nVerify checkpoint update:")
            logger.info(f"  Last completed page: {new_checkpoint['last_completed_page']}")
            logger.info(f"  Match: {new_checkpoint['last_completed_page'] == test_page}")
            
            return {
                'success': True,
                'original_page': checkpoint['last_completed_page'],
                'updated_page': test_page,
                'verified': new_checkpoint['last_completed_page'] == test_page
            }
        
        except Exception as e:
            logger.error(f"Checkpoint test failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}
    
    def test_pagination_detection(self, url: str) -> dict:
        """Test pagination pattern detection"""
        from src.services.pagination_service import PaginationService, BatchUrlGenerator
        
        logger.info(f"\n{'='*80}")
        logger.info(f"TEST: Pagination detection")
        logger.info(f"URL: {url}")
        logger.info(f"{'='*80}")
        
        try:
            # 1. Detect pattern
            pattern = PaginationService.detect_pagination_pattern(url)
            logger.info(f"\nPattern: {pattern}")
            
            # 2. Generate batch URLs
            batch_urls = BatchUrlGenerator.generate_batch_urls(
                base_url=url,
                start_page=1,
                batch_size=10
            )
            logger.info(f"\nGenerated {len(batch_urls)} URLs:")
            for i, batch_url in enumerate(batch_urls[:3], 1):
                logger.info(f"  Page {i}: {batch_url}")
            if len(batch_urls) > 3:
                logger.info(f"  ... ({len(batch_urls) - 3} more)")
            
            # 3. Validate
            is_valid = BatchUrlGenerator.validate_batch_urls(batch_urls)
            logger.info(f"\nValidation: {'✓ Valid' if is_valid else '✗ Invalid (URLs not unique)'}")
            
            # 4. Extract page numbers
            page_numbers = BatchUrlGenerator.extract_page_numbers_from_batch(batch_urls)
            logger.info(f"\nPage numbers: {page_numbers}")
            
            return {
                'success': True,
                'pattern': pattern,
                'batch_count': len(batch_urls),
                'is_valid': is_valid,
                'page_numbers': page_numbers
            }
        
        except Exception as e:
            logger.error(f"Pagination detection test failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}
    
    def test_database_migration(self) -> dict:
        """Test database migration"""
        logger.info(f"\n{'='*80}")
        logger.info(f"TEST: Database migration")
        logger.info(f"{'='*80}")
        
        result = run_migration(self.db)
        
        logger.info(f"\nMigration result: {'✓ SUCCESS' if result['success'] else '✗ FAILED'}")
        logger.info(f"Operations: {len(result['messages'])} succeeded, {len(result['errors'])} errors")
        
        if result['messages']:
            logger.info(f"\nMessages:")
            for msg in result['messages'][:5]:
                logger.info(f"  {msg}")
            if len(result['messages']) > 5:
                logger.info(f"  ... ({len(result['messages']) - 5} more)")
        
        if result['errors']:
            logger.error(f"\nErrors:")
            for error in result['errors']:
                logger.error(f"  {error}")
        
        return result


def main():
    parser = argparse.ArgumentParser(description='Test chunk-based pagination system')
    parser.add_argument('--project-id', type=int, help='Test single project ID')
    parser.add_argument('--all-projects', action='store_true', help='Test all projects')
    parser.add_argument('--batches', type=int, default=1, help='Max batches per project')
    parser.add_argument('--checkpoint', type=int, help='Test checkpoint for project ID')
    parser.add_argument('--pagination-url', help='Test pagination detection for URL')
    parser.add_argument('--migration', action='store_true', help='Test database migration')
    
    args = parser.parse_args()
    
    tester = BatchPaginationTester()
    
    if args.migration:
        tester.test_database_migration()
    elif args.pagination_url:
        tester.test_pagination_detection(args.pagination_url)
    elif args.checkpoint:
        tester.test_checkpoint_system(args.checkpoint)
    elif args.project_id:
        tester.test_single_batch(args.project_id, args.batches)
    elif args.all_projects:
        tester.test_all_projects(args.batches)
    else:
        print("Use --help for usage options")
        print("\nExamples:")
        print("  python test_batch_pagination.py --project-id 1 --batches 1")
        print("  python test_batch_pagination.py --all-projects --batches 5")
        print("  python test_batch_pagination.py --checkpoint 1")
        print("  python test_batch_pagination.py --pagination-url 'https://example.com/page=1'")
        print("  python test_batch_pagination.py --migration")


if __name__ == '__main__':
    main()
