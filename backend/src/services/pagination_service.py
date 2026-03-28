"""
Pagination Service - Handles pagination detection, URL generation, and recovery
"""

import re
import json
import sys
from datetime import datetime
from typing import Dict, Optional, Tuple
from pathlib import Path

root_dir = Path(__file__).parent.parent.parent  # backend/
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.models.database import ParseHubDatabase


class PaginationService:
    """Service for managing pagination and automatic recovery"""
    
    def __init__(self):
        self.db = ParseHubDatabase()
    
    def extract_page_number(self, url: str) -> int:
        """
        Extract page number from URL
        Supports: ?page=N, ?p=N, /page/N, /page-N, ?offset=N
        """
        if not url:
            return 1
        
        patterns = [
            r'[?&]page[=](\d+)',
            r'[?&]p[=](\d+)',
            r'/page[/-](\d+)',
            r'[?&]offset[=](\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        return 1
    
    def generate_next_page_url(self, base_url: str, current_page: int) -> str:
        """
        Generate URL for next page based on detected pattern
        """
        next_page = current_page + 1
        
        patterns = [
            (r'([?&]page[=])\d+', rf'\g<1>{next_page}', 'query'),
            (r'([?&]p[=])\d+', rf'\g<1>{next_page}', 'query'),
            (r'(/page[/-])\d+', rf'\g<1>{next_page}', 'path'),
            (r'([?&]offset[=])\d+', rf'\g<1>{current_page * 20}', 'offset'),
        ]
        
        for pattern, replacement, style in patterns:
            if re.search(pattern, base_url):
                return re.sub(pattern, replacement, base_url)
        
        # Default: append page parameter
        separator = '&' if '?' in base_url else '?'
        return f"{base_url}{separator}page={next_page}"
    
    def detect_pagination_pattern(self, url: str) -> Dict:
        """Detect pagination pattern in URL"""
        patterns = {
            'query_page': r'[?&]page[=]\d+',
            'query_p': r'[?&]p[=]\d+',
            'path_style': r'/page[/-]\d+',
            'offset': r'[?&]offset[=]\d+'
        }
        
        detected = {}
        for pattern_name, pattern in patterns.items():
            if re.search(pattern, url):
                detected[pattern_name] = True
        
        return detected
    
    def check_pagination_needed(self, project_id: int, target_pages: int) -> Dict:
        """
        Check if pagination recovery is needed
        
        Returns:
            {
                'needs_recovery': bool,
                'last_page_scraped': int,
                'target_pages': int,
                'total_data_count': int,
                'pages_remaining': int
            }
        """
        try:
            conn = self.db.connect()
            if not conn:
                return {
                    'needs_recovery': True,
                    'last_page_scraped': 0,
                    'target_pages': target_pages,
                    'total_data_count': 0,
                    'pages_remaining': target_pages
                }
            cursor = conn.cursor()
            
            # Get last page number from data
            cursor.execute('''
                SELECT MAX(CAST(json_extract(data, '$.page_number') AS INTEGER)) as last_page
                FROM scraped_data 
                WHERE project_id = %s
            ''', (project_id,))
            
            result = cursor.fetchone()
            last_page = (result.get('last_page') if isinstance(result, dict) else result[0]) if result else 0
            if not last_page:
                last_page = 0
            
            # Get total data count
            cursor.execute('''
                SELECT COUNT(*) as total FROM scraped_data 
                WHERE project_id = %s
            ''', (project_id,))
            
            total_result = cursor.fetchone()
            total_count = (total_result.get('total') if isinstance(total_result, dict) else total_result[0]) if total_result else 0
            
            self.db.disconnect()
        except Exception as e:
            print(f"[ERROR] check_pagination_needed failed: {e}", file=sys.stderr)
            return {
                'needs_recovery': True,
                'last_page_scraped': 0,
                'target_pages': target_pages,
                'total_data_count': 0,
                'pages_remaining': target_pages
            }
        
        return {
            'needs_recovery': last_page < target_pages,
            'last_page_scraped': last_page,
            'target_pages': target_pages,
            'total_data_count': total_count,
            'pages_remaining': max(0, target_pages - last_page)
        }
    
    def create_recovery_project_info(self, original_url: str, current_page: int, 
                                     target_pages: int) -> Dict:
        """
        Create recovery project information
        Generates next page URL and metadata
        """
        next_url = self.generate_next_page_url(original_url, current_page)
        
        return {
            'original_url': original_url,
            'recovery_url': next_url,
            'start_page': current_page + 1,
            'target_pages': target_pages,
            'created_at': datetime.now().isoformat()
        }
    
    def record_scraping_progress(self, project_id: int, page_number: int, 
                                data_count: int, items_per_minute: float) -> None:
        """Record scraping progress checkpoint"""
        try:
            conn = self.db.connect()
            if not conn:
                return
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO run_checkpoints
                (run_id, snapshot_timestamp, item_count_at_time, items_per_minute)
                VALUES (
                    (SELECT id FROM runs WHERE project_id = %s ORDER BY created_at DESC LIMIT 1),
                    CURRENT_TIMESTAMP,
                    %s,
                    %s
                )
            ''', (project_id, data_count, items_per_minute))
            
            conn.commit()
            self.db.disconnect()
        except Exception as e:
            print(f"[ERROR] record_scraping_progress failed: {e}", file=sys.stderr)


class PaginationDetector:
    """Advanced pagination detection using data analysis"""
    
    @staticmethod
    def estimate_total_pages(url_patterns: list) -> Optional[int]:
        """
        Estimate total pages from URL patterns
        """
        if not url_patterns:
            return None
        
        page_numbers = []
        detector = PaginationService()
        
        for url in url_patterns:
            page_num = detector.extract_page_number(url)
            if page_num:
                page_numbers.append(page_num)
        
        if page_numbers:
            return max(page_numbers)
        
        return None
    
    @staticmethod
    def detect_items_per_page(data_per_page: list) -> Tuple[int, float]:
        """
        Analyze data count per page to estimate items per page
        Returns: (average_items_per_page, consistency_score)
        """
        if not data_per_page:
            return 0, 0.0
        
        avg = sum(data_per_page) / len(data_per_page)
        
        # Calculate consistency (coefficient of variation)
        if avg > 0:
            variance = sum((x - avg) ** 2 for x in data_per_page) / len(data_per_page)
            std_dev = variance ** 0.5
            consistency = 1 - (std_dev / avg)  # 0-1 scale
        else:
            consistency = 0.0
        
        return int(avg), max(0, consistency)


# ===== BATCH URL GENERATION (NEW) =====

class BatchUrlGenerator:
    """Generate batch URLs for chunk-based pagination"""
    
    BATCH_SIZE = 10  # Default batch size
    
    @staticmethod
    def generate_batch_urls(base_url: str, start_page: int, batch_size: int = BATCH_SIZE) -> list:
        """
        Generate a batch of URLs for consecutive pages
        
        Args:
            base_url: Base URL or template URL (can contain page number parameter)
            start_page: Starting page number (1-indexed)
            batch_size: Number of URLs to generate (default 10)
        
        Returns:
            List of URLs for pages [start_page, start_page+batch_size)
        """
        urls = []
        service = PaginationService()
        
        for i in range(batch_size):
            page_num = start_page + i
            
            # Use existing method to generate URL for this page
            if i == 0:
                # First page - use base_url directly if it already has a page param
                url = base_url
            else:
                # Subsequent pages - generate URL
                url = service.generate_next_page_url(base_url, start_page + i - 1)
            
            urls.append(url)
        
        return urls
    
    @staticmethod
    def validate_batch_urls(urls: list) -> bool:
        """
        Validate that batch URLs are properly differentiated
        
        Returns:
            True if all URLs in batch are unique (good pagination)
        """
        return len(urls) == len(set(urls))
    
    @staticmethod
    def extract_page_numbers_from_batch(urls: list) -> list:
        """
        Extract page numbers from batch of URLs
        
        Returns:
            List of page numbers (or None if not detected)
        """
        service = PaginationService()
        page_numbers = []
        
        for url in urls:
            page_num = service.extract_page_number(url)
            page_numbers.append(page_num)
        
        return page_numbers
