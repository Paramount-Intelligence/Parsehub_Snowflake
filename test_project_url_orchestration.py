"""
Test suite for modified orchestration logic using project_url instead of metadata URLs

Tests cover:
1. First run uses project_url directly
2. Resumed run uses generate_next_page_url(project_url, max_page + 1)
3. Completed project does not start new run
4. Missing project_url fails clearly
5. metadata.WEBSITE_URL missing does not block first run if project_url exists
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(backend_path))

from services.metadata_driven_resume_scraper import MetadataDrivenResumeScraper


class TestProjectURLOrchestration:
    """Test suite for project_url-based orchestration"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.scraper = MetadataDrivenResumeScraper()
        # Mock database and API calls
        self.scraper.db = Mock()
        self.scraper.notification_service = Mock()
    
    def test_first_run_uses_project_url_directly(self):
        """Test that first run (highest_page == 0) uses project_url directly"""
        # Arrange
        project_id = 123
        project_token = "test_token"
        project_url = "https://example.com/products"
        
        # Mock database calls
        self.scraper.get_project_url = Mock(return_value=project_url)
        self.scraper.get_project_metadata = Mock(return_value={
            'project_id': project_id,
            'project_name': 'Test Project',
            'website_url': 'https://metadata.com',  # Different from project_url - should be IGNORED
            'total_pages': 10,
            'total_products': 100,
            'project_token': project_token
        })
        self.scraper.get_checkpoint = Mock(return_value={
            'highest_successful_page': 0,  # First run
            'next_start_page': 1,
            'total_persisted_records': 0,
            'checkpoint_timestamp': '2024-01-01T00:00:00'
        })
        self.scraper.is_project_complete = Mock(return_value=(False, ''))
        self.scraper.trigger_run = Mock(return_value={
            'success': True,
            'run_token': 'run_123'
        })
        
        # Act
        result = self.scraper.resume_or_start_scraping(project_id, project_token)
        
        # Assert
        assert result['success'] is True
        assert result['run_token'] == 'run_123'
        
        # Verify trigger_run was called with project_url, NOT metadata.website_url
        call_args = self.scraper.trigger_run.call_args
        assert call_args[0][1] == project_url  # start_url is second positional arg
        assert call_args[0][4] == 1  # next_page is 1 for fresh run
    
    def test_resumed_run_generates_url_from_project_url(self):
        """Test that resumed run generates URL from project_url, not metadata URLs"""
        # Arrange
        project_id = 123
        project_token = "test_token"
        project_url = "https://example.com/products"
        
        self.scraper.get_project_url = Mock(return_value=project_url)
        self.scraper.get_project_metadata = Mock(return_value={
            'project_id': project_id,
            'project_name': 'Test Project',
            'website_url': 'https://metadata.com',  # Should be IGNORED
            'last_known_url': 'https://old.com',  # Should be IGNORED
            'total_pages': 10,
            'total_products': 100,
            'project_token': project_token
        })
        self.scraper.get_checkpoint = Mock(return_value={
            'highest_successful_page': 3,  # Resumed from page 3
            'next_start_page': 4,
            'total_persisted_records': 45,
            'checkpoint_timestamp': '2024-01-01T00:00:00'
        })
        self.scraper.is_project_complete = Mock(return_value=(False, ''))
        self.scraper.generate_next_page_url = Mock(return_value="https://example.com/products?page=4")
        self.scraper.trigger_run = Mock(return_value={
            'success': True,
            'run_token': 'run_124'
        })
        
        # Act
        result = self.scraper.resume_or_start_scraping(project_id, project_token)
        
        # Assert
        assert result['success'] is True
        assert result['next_start_page'] == 4
        
        # Verify generate_next_page_url was called with project_url and next page
        self.scraper.generate_next_page_url.assert_called_once_with(project_url, 4, None)
        
        # Verify trigger_run was called with generated URL
        call_args = self.scraper.trigger_run.call_args
        assert call_args[0][1] == "https://example.com/products?page=4"
    
    def test_completed_project_does_not_start_new_run(self):
        """Test that completed project returns complete status without triggering run"""
        #Arrange
        project_id = 123
        project_token = "test_token"
        project_url = "https://example.com/products"
        
        self.scraper.get_project_url = Mock(return_value=project_url)
        self.scraper.get_project_metadata = Mock(return_value={
            'project_id': project_id,
            'project_name': 'Test Project',
            'total_pages': 10,
            'total_products': 100,
        })
        self.scraper.get_checkpoint = Mock(return_value={
            'highest_successful_page': 10,  # Already at total_pages
            'next_start_page': 11,
            'total_persisted_records': 150,
            'checkpoint_timestamp': '2024-01-01T00:00:00'
        })
        self.scraper.is_project_complete = Mock(return_value=(True, 'All pages scraped'))
        self.scraper.mark_project_complete = Mock()
        self.scraper.trigger_run = Mock()  # Should NOT be called
        
        # Act
        result = self.scraper.resume_or_start_scraping(project_id, project_token)
        
        # Assert
        assert result['success'] is True
        assert result['project_complete'] is True
        assert result['message'] == 'Project scraping is complete'
        
        # Verify trigger_run was NOT called
        self.scraper.trigger_run.assert_not_called()
        
        # Verify mark_project_complete was called
        self.scraper.mark_project_complete.assert_called_once_with(project_id)
    
    def test_missing_project_url_fails_clearly(self):
        """Test that missing project_url returns clear error"""
        # Arrange
        project_id = 123
        project_token = "test_token"
        
        self.scraper.get_project_url = Mock(return_value=None)  # No project URL
        self.scraper.trigger_run = Mock()  # Should NOT be called
        
        # Act
        result = self.scraper.resume_or_start_scraping(project_id, project_token)
        
        # Assert
        assert result['success'] is False
        assert 'No project URL found' in result['error']
        
        # Verify trigger_run was NOT called
        self.scraper.trigger_run.assert_not_called()
    
    def test_metadata_website_url_missing_does_not_block_first_run(self):
        """Test that missing metadata.WEBSITE_URL does not block first run if project_url exists"""
        # Arrange
        project_id = 123
        project_token = "test_token"
        project_url = "https://example.com/products"
        
        self.scraper.get_project_url = Mock(return_value=project_url)
        self.scraper.get_project_metadata = Mock(return_value={
            'project_id': project_id,
            'project_name': 'Test Project',
            'website_url': None,  # MISSING - should not cause failure
            'total_pages': 10,
            'total_products': 100,
        })
        self.scraper.get_checkpoint = Mock(return_value={
            'highest_successful_page': 0,  # Fresh run
            'next_start_page': 1,
            'total_persisted_records': 0,
            'checkpoint_timestamp': '2024-01-01T00:00:00'
        })
        self.scraper.is_project_complete = Mock(return_value=(False, ''))
        self.scraper.trigger_run = Mock(return_value={
            'success': True,
            'run_token': 'run_123'
        })
        
        # Act
        result = self.scraper.resume_or_start_scraping(project_id, project_token)
        
        # Assert
        assert result['success'] is True
        assert 'run_token' in result
        
        # Verify trigger_run was called with project_url (not blocked by missing metadata.website_url)
        call_args = self.scraper.trigger_run.call_args
        assert call_args[0][1] == project_url
    
    def test_get_project_url_fetches_from_projects_table(self):
        """Test that get_project_url correctly fetches from projects table"""
        # Arrange
        project_id = 123
        project_url = "https://example.com/products"
        
        # Mock database connection
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {'main_site': project_url}
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        self.scraper.db.connect = Mock(return_value=mock_conn)
        self.scraper.db.cursor = Mock(return_value=mock_cursor)
        
        # Act
        result = self.scraper.get_project_url(project_id)
        
        # Assert
        assert result == project_url
        
        # Verify database query
        mock_cursor.execute.assert_called_once()
        call_string = mock_cursor.execute.call_args[0][0]
        assert 'FROM projects' in call_string
        assert 'main_site' in call_string
    
    def test_get_project_url_handles_none_result(self):
        """Test that get_project_url handles None result gracefully"""
        # Arrange
        project_id = 999  # Non-existent project
        
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn = Mock()
        
        self.scraper.db.connect = Mock(return_value=mock_conn)
        self.scraper.db.cursor = Mock(return_value=mock_cursor)
        
        # Act
        result = self.scraper.get_project_url(project_id)
        
        # Assert
        assert result is None


class TestURLGenerationWithProjectURL:
    """Test URL generation logic works correctly with project_url"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.scraper = MetadataDrivenResumeScraper()
    
    def test_generate_next_page_url_appends_page_parameter(self):
        """Test that generate_next_page_url correctly appends page parameter"""
        # Arrange
        base_url = "https://example.com/products"
        next_page = 2
        
        # Act
        result = self.scraper.generate_next_page_url(base_url, next_page)
        
        # Assert
        assert "?page=2" in result or "&page=2" in result
    
    def test_generate_next_page_url_replaces_existing_page_parameter(self):
        """Test that generate_next_page_url replaces existing page parameter"""
        # Arrange
        base_url = "https://example.com/products?page=1"
        next_page = 3
        
        # Act
        result = self.scraper.generate_next_page_url(base_url, next_page)
        
        # Assert
        assert "page=3" in result
        assert "page=1" not in result
    
    def test_generate_next_page_url_rejects_none_url(self):
        """Test that generate_next_page_url rejects None URL"""
        # Arrange
        base_url = None
        next_page = 2
        
        # Act & Assert
        with pytest.raises((ValueError, TypeError)):
            self.scraper.generate_next_page_url(base_url, next_page)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
