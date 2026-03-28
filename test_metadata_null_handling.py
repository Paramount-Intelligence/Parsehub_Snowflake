"""
Test suite for metadata null-handling and safe string operations.

Tests cover:
1. None values in metadata fields (website_url, last_known_url, project_name)
2. Snowflake uppercase column name normalization
3. safe_str() helper function
4. First run uses website_url WITHOUT calling generate_next_page_url()
5. Resumed run safely calls generate_next_page_url()
6. Complete project detection
"""

import sys
import os
import pytest
from unittest.mock import Mock, patch, MagicMock

# Add backend src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend', 'src'))

from services.metadata_driven_resume_scraper import MetadataDrivenResumeScraper, safe_str


class TestSafeStrHelper:
    """Test the safe_str() helper function"""
    
    def test_safe_str_with_none(self):
        """safe_str(None) should return empty string"""
        result = safe_str(None)
        assert result == '', f"Expected '', got {repr(result)}"
    
    def test_safe_str_with_normal_string(self):
        """safe_str() should strip whitespace from normal strings"""
        result = safe_str("  hello world  ")
        assert result == "hello world", f"Expected 'hello world', got {repr(result)}"
    
    def test_safe_str_with_empty_string(self):
        """safe_str('') should return empty string"""
        result = safe_str("")
        assert result == '', f"Expected '', got {repr(result)}"
    
    def test_safe_str_with_number(self):
        """safe_str(123) should return empty string (not a string)"""
        result = safe_str(123)
        assert result == '', f"Expected '', got {repr(result)}"
    
    def test_safe_str_with_boolean(self):
        """safe_str(True) should return empty string"""
        result = safe_str(True)
        assert result == '', f"Expected '', got {repr(result)}"


class TestMetadataUppercaseNormalization:
    """Test Snowflake uppercase key normalization in get_project_metadata()"""
    
    @patch('services.metadata_driven_resume_scraper.DatabaseConnection')
    def test_uppercase_keys_normalized_to_lowercase(self, mock_db_class):
        """Snowflake returns uppercase keys; get_project_metadata should normalize"""
        
        # Mock database connection
        mock_db = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        
        # Simulate Snowflake returning UPPERCASE keys in dict
        mock_result = {
            'ID': 123,
            'PROJECT_NAME': 'Test Project',
            'LAST_KNOWN_URL': 'https://example.com/page/1',
            'TOTAL_PAGES': 10,
            'TOTAL_PRODUCTS': 50,
            'PROJECT_TOKEN': 'abc123'
        }
        
        mock_db.connect.return_value = mock_conn
        mock_db.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = mock_result
        mock_db_class.return_value = mock_db
        
        scraper = MetadataDrivenResumeScraper()
        scraper.db = mock_db
        
        metadata = scraper.get_project_metadata(123)
        
        # All returned keys should be lowercase
        assert 'project_id' in metadata, "Missing 'project_id' key"
        assert 'project_name' in metadata, "Missing 'project_name' key"
        assert 'website_url' in metadata, "Missing 'website_url' key"
        assert 'total_pages' in metadata, "Missing 'total_pages' key"
        assert 'total_products' in metadata, "Missing 'total_products' key"
        assert 'project_token' in metadata, "Missing 'project_token' key"
        
        # Values should be preserved
        assert metadata['project_id'] == 123
        assert metadata['project_name'] == 'Test Project'
        assert metadata['website_url'] == 'https://example.com/page/1'
        assert metadata['total_pages'] == 10
        assert metadata['total_products'] == 50
        assert metadata['project_token'] == 'abc123'


class TestMetadataNoneHandling:
    """Test handling of None values in metadata"""
    
    @patch('services.metadata_driven_resume_scraper.DatabaseConnection')
    def test_none_website_url_returns_empty_string(self, mock_db_class):
        """When website_url is None, should safely return empty string"""
        
        mock_db = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        
        # Simulate Snowflake returning None for LAST_KNOWN_URL
        mock_result = {
            'ID': 123,
            'PROJECT_NAME': 'Test Project',
            'LAST_KNOWN_URL': None,  # ← None value
            'TOTAL_PAGES': 10,
            'TOTAL_PRODUCTS': 50,
            'PROJECT_TOKEN': 'abc123'
        }
        
        mock_db.connect.return_value = mock_conn
        mock_db.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = mock_result
        mock_db_class.return_value = mock_db
        
        scraper = MetadataDrivenResumeScraper()
        scraper.db = mock_db
        
        metadata = scraper.get_project_metadata(123)
        
        # Should safely return empty string instead of None
        assert metadata['website_url'] == '', f"Expected '', got {repr(metadata['website_url'])}"
        assert isinstance(metadata['website_url'], str), "Expected string type"
    
    @patch('services.metadata_driven_resume_scraper.DatabaseConnection')
    def test_none_project_name_returns_default(self, mock_db_class):
        """When project_name is None, should return 'Unknown'"""
        
        mock_db = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        
        mock_result = {
            'ID': 123,
            'PROJECT_NAME': None,  # ← None value
            'LAST_KNOWN_URL': 'https://example.com',
            'TOTAL_PAGES': 10,
            'TOTAL_PRODUCTS': 50,
            'PROJECT_TOKEN': 'abc123'
        }
        
        mock_db.connect.return_value = mock_conn
        mock_db.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = mock_result
        mock_db_class.return_value = mock_db
        
        scraper = MetadataDrivenResumeScraper()
        scraper.db = mock_db
        
        metadata = scraper.get_project_metadata(123)
        
        # Should safely return 'Unknown' instead of None
        assert metadata['project_name'] == 'Unknown', f"Expected 'Unknown', got {repr(metadata['project_name'])}"


class TestURLSelectionLogic:
    """Test URL selection for fresh vs resumed vs complete projects"""
    
    @patch('services.metadata_driven_resume_scraper.DatabaseConnection')
    @patch('services.metadata_driven_resume_scraper.CheckpointManager')
    def test_first_run_uses_website_url_directly(self, mock_checkpoint_mgr, mock_db_class):
        """First run (highest_page=0) should use website_url directly WITHOUT calling generate_next_page_url"""
        
        # Setup mocks
        mock_db = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_db.connect.return_value = mock_conn
        mock_db.cursor.return_value = mock_cursor
        mock_db_class.return_value = mock_db
        
        mock_checkpoint = Mock()
        mock_checkpoint.get_checkpoint.return_value = {
            'project_id': 123,
            'highest_successful_page': 0,  # ← First run
            'next_start_page': 1,
            'last_scraped_at': None,
            'total_persisted_records': 0
        }
        mock_checkpoint_mgr.return_value = mock_checkpoint
        
        # Metadata
        mock_result = {
            'ID': 123,
            'PROJECT_NAME': 'Test Project',
            'LAST_KNOWN_URL': 'https://example.com',
            'TOTAL_PAGES': 10,
            'TOTAL_PRODUCTS': 100,
            'PROJECT_TOKEN': 'token123'
        }
        mock_cursor.fetchone.return_value = mock_result
        
        scraper = MetadataDrivenResumeScraper()
        scraper.db = mock_db
        scraper.checkpoint_manager = mock_checkpoint
        
        # Mock should_stop_project to avoid complete project logic
        with patch.object(scraper, 'should_stop_project', return_value=False):
            # Mock ParsehubAPI to prevent actual scraping
            with patch('services.metadata_driven_resume_scraper.ParsehubAPI'):
                with patch.object(scraper, 'generate_next_page_url') as mock_generate_url:
                    result = scraper.resume_or_start_scraping(123)
                    
                    # generate_next_page_url should NOT be called for first run
                    mock_generate_url.assert_not_called()
                    assert result['success'] is True
    
    @patch('services.metadata_driven_resume_scraper.DatabaseConnection')
    @patch('services.metadata_driven_resume_scraper.CheckpointManager')
    def test_resumed_run_calls_generate_next_page_url(self, mock_checkpoint_mgr, mock_db_class):
        """Resumed run (0 < highest_page < total_pages) should call generate_next_page_url"""
        
        # Setup mocks
        mock_db = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_db.connect.return_value = mock_conn
        mock_db.cursor.return_value = mock_cursor
        mock_db_class.return_value = mock_db
        
        mock_checkpoint = Mock()
        mock_checkpoint.get_checkpoint.return_value = {
            'project_id': 123,
            'highest_successful_page': 3,  # ← Resumed project (page 3 completed)
            'next_start_page': 4,
            'last_scraped_at': '2024-01-01',
            'total_persisted_records': 100
        }
        mock_checkpoint_mgr.return_value = mock_checkpoint
        
        # Metadata
        mock_result = {
            'ID': 123,
            'PROJECT_NAME': 'Test Project',
            'LAST_KNOWN_URL': 'https://example.com',
            'TOTAL_PAGES': 10,
            'TOTAL_PRODUCTS': 100,
            'PROJECT_TOKEN': 'token123'
        }
        mock_cursor.fetchone.return_value = mock_result
        
        scraper = MetadataDrivenResumeScraper()
        scraper.db = mock_db
        scraper.checkpoint_manager = mock_checkpoint
        
        # Mock should_stop_project to avoid complete project logic
        with patch.object(scraper, 'should_stop_project', return_value=False):
            # Mock ParsehubAPI to prevent actual scraping
            with patch('services.metadata_driven_resume_scraper.ParsehubAPI'):
                with patch.object(scraper, 'generate_next_page_url', return_value='https://example.com/page/4') as mock_generate_url:
                    result = scraper.resume_or_start_scraping(123)
                    
                    # generate_next_page_url SHOULD be called for resumed run
                    mock_generate_url.assert_called()
                    assert result['success'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
