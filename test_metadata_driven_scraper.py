"""
Comprehensive tests for MetadataDrivenResumeScraper service

Run: pytest test_metadata_driven_scraper.py -v
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json

root_dir = Path(__file__).parent.parent  # backend/
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.services.metadata_driven_resume_scraper import MetadataDrivenResumeScraper
import requests


class TestMetadataDrivenScraperCheckpoint:
    """Tests for checkpoint reading and writing"""
    
    def test_get_checkpoint_no_records(self):
        """When no records exist, checkpoint should start at page 0"""
        scraper = MetadataDrivenResumeScraper()
        
        with patch.object(scraper.db, 'connect') as mock_connect:
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_connect.return_value.cursor.return_value = mock_cursor
            
            checkpoint = scraper.get_checkpoint(project_id=1)
            
            assert checkpoint['highest_successful_page'] == 0
            assert checkpoint['next_start_page'] == 1
            assert checkpoint['total_persisted_records'] == 0
            assert checkpoint['checkpoint_timestamp'] is not None
    
    def test_get_checkpoint_with_records(self):
        """When records exist, checkpoint should reflect MAX(source_page)"""
        scraper = MetadataDrivenResumeScraper()
        
        with patch.object(scraper.db, 'connect') as mock_connect:
            mock_cursor = Mock()
            # Return: highest_page=10, total_records=342
            mock_cursor.fetchone.return_value = {
                'highest_page': 10,
                'total_records': 342
            }
            mock_connect.return_value.cursor.return_value = mock_cursor
            
            checkpoint = scraper.get_checkpoint(project_id=1)
            
            assert checkpoint['highest_successful_page'] == 10
            assert checkpoint['next_start_page'] == 11
            assert checkpoint['total_persisted_records'] == 342
    
    def test_update_checkpoint_success(self):
        """Updating checkpoint should succeed"""
        scraper = MetadataDrivenResumeScraper()
        
        with patch.object(scraper.db, 'connect') as mock_connect:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            success = scraper.update_checkpoint(project_id=1, highest_successful_page=10)
            
            assert success is True
            mock_cursor.execute.assert_called_once()
            mock_conn.commit.assert_called_once()


class TestMetadataDrivenScraperURLGeneration:
    """Tests for URL generation and pagination pattern detection"""
    
    def test_generate_url_query_page_param(self):
        """Should detect and modify ?page= parameter"""
        scraper = MetadataDrivenResumeScraper()
        
        base_url = "https://example.com/products?page=1"
        next_page = 5
        
        url = scraper.generate_next_page_url(base_url, next_page)
        
        assert "page=5" in url
        assert url == "https://example.com/products?page=5"
    
    def test_generate_url_query_p_param(self):
        """Should detect and modify ?p= parameter"""
        scraper = MetadataDrivenResumeScraper()
        
        base_url = "https://example.com/products?p=1"
        next_page = 3
        
        url = scraper.generate_next_page_url(base_url, next_page)
        
        assert "p=3" in url
    
    def test_generate_url_offset_param(self):
        """Should detect and modify offset parameter"""
        scraper = MetadataDrivenResumeScraper()
        
        base_url = "https://example.com/products?offset=0"
        next_page = 3
        
        url = scraper.generate_next_page_url(base_url, next_page)
        
        # Page 3 = offset 40 (assuming 20 per page)
        assert "offset=40" in url
    
    def test_generate_url_path_style(self):
        """Should detect and modify /page/X/ style URLs"""
        scraper = MetadataDrivenResumeScraper()
        
        base_url = "https://example.com/page/1/"
        next_page = 5
        
        url = scraper.generate_next_page_url(base_url, next_page)
        
        assert "/page/5/" in url
    
    def test_generate_url_default_append(self):
        """Should append ?page= if no pattern detected"""
        scraper = MetadataDrivenResumeScraper()
        
        base_url = "https://example.com/products"
        next_page = 2
        
        url = scraper.generate_next_page_url(base_url, next_page)
        
        assert "page=2" in url
    
    def test_detect_pagination_pattern_query_page(self):
        """Should correctly detect ?page= pattern"""
        scraper = MetadataDrivenResumeScraper()
        
        result = scraper._detect_pagination_pattern("https://example.com?page=1")
        assert result == 'query_page'
    
    def test_detect_pagination_pattern_offset(self):
        """Should correctly detect offset parameter"""
        scraper = MetadataDrivenResumeScraper()
        
        result = scraper._detect_pagination_pattern("https://example.com?offset=0")
        assert result == 'offset'


class TestMetadataDrivenScraperParseHubIntegration:
    """Tests for ParseHub API interaction"""
    
    def test_trigger_run_success(self):
        """Should successfully trigger ParseHub run"""
        scraper = MetadataDrivenResumeScraper()
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'run_token': 'run_abc123'}
            mock_post.return_value = mock_response
            
            result = scraper.trigger_run(
                project_token='t123',
                start_url='https://example.com/page=1',
                project_id=1,
                project_name='Test Project',
                starting_page_number=1
            )
            
            assert result['success'] is True
            assert result['run_token'] == 'run_abc123'
    
    def test_trigger_run_api_error(self):
        """Should handle ParseHub API 500 error"""
        scraper = MetadataDrivenResumeScraper()
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_post.return_value = mock_response
            
            # Should trigger email notification (mocked)
            with patch.object(scraper, '_send_failure_notification') as mock_email:
                result = scraper.trigger_run(
                    project_token='t123',
                    start_url='https://example.com',
                    project_id=1,
                    project_name='Test Project',
                    starting_page_number=1
                )
                
                assert result['success'] is False
                assert result['error_type'] == 'server_error'
                mock_email.assert_called_once()
    
    def test_trigger_run_timeout(self):
        """Should handle timeout gracefully"""
        scraper = MetadataDrivenResumeScraper()
        
        with patch('requests.post') as mock_post:
            mock_post.side_effect = requests.Timeout()
            
            with patch.object(scraper, '_send_failure_notification') as mock_email:
                result = scraper.trigger_run(
                    project_token='t123',
                    start_url='https://example.com',
                    project_id=1,
                    project_name='Test Project',
                    starting_page_number=1
                )
                
                assert result['success'] is False
                assert result['error_type'] == 'timeout'
                mock_email.assert_called_once()
    
    def test_trigger_run_missing_token(self):
        """Should handle missing run_token in response"""
        scraper = MetadataDrivenResumeScraper()
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}  # Missing run_token
            mock_post.return_value = mock_response
            
            with patch.object(scraper, '_send_failure_notification'):
                result = scraper.trigger_run(
                    project_token='t123',
                    start_url='https://example.com',
                    project_id=1,
                    project_name='Test Project',
                    starting_page_number=1
                )
                
                assert result['success'] is False
                assert result['error_type'] == 'invalid_response'
    
    def test_poll_run_completion_success(self):
        """Should successfully poll and detect completion"""
        scraper = MetadataDrivenResumeScraper()
        scraper.POLL_INTERVAL = 0.001  # Fast for testing
        scraper.MAX_POLL_ATTEMPTS = 2
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'status': 'completed',
                'data': [{'item': 1}, {'item': 2}]
            }
            mock_get.return_value = mock_response
            
            result = scraper.poll_run_completion('run_abc123')
            
            assert result['success'] is True
            assert result['status'] == 'completed'
            assert result['data_count'] == 2
    
    def test_poll_run_completion_failed_run(self):
        """Should detect failed run status"""
        scraper = MetadataDrivenResumeScraper()
        scraper.POLL_INTERVAL = 0.001
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'status': 'failed',
                'error': 'Access denied'
            }
            mock_get.return_value = mock_response
            
            result = scraper.poll_run_completion('run_abc123')
            
            assert result['success'] is False
            assert result['status'] == 'failed'


class TestMetadataDrivenScraperPersistence:
    """Tests for data persistence"""
    
    def test_persist_results_success(self):
        """Should persist records with source_page"""
        scraper = MetadataDrivenResumeScraper()
        
        test_data = [
            {'name': 'Product 1', 'price': 10},
            {'name': 'Product 2', 'price': 20}
        ]
        
        with patch.object(scraper.db, 'connect') as mock_connect:
            mock_cursor = Mock()
            mock_connect.return_value.cursor.return_value = mock_cursor
            mock_connect.return_value.commit = Mock()
            
            # Mock checkpoint computation
            with patch.object(scraper, 'get_checkpoint') as mock_checkpoint:
                mock_checkpoint.return_value = {
                    'highest_successful_page': 5,
                    'next_start_page': 6,
                    'total_persisted_records': 342
                }
                
                success, inserted, highest = scraper.persist_results(
                    project_id=1,
                    run_token='run_abc123',
                    data=test_data,
                    source_page=5
                )
                
                assert success is True
                assert inserted == 2
                assert highest == 5
    
    def test_persist_results_partial_failure(self):
        """Should continue on individual record failure"""
        scraper = MetadataDrivenResumeScraper()
        
        test_data = [
            {'name': 'Product 1'},
            {'name': 'Product 2'},
        ]
        
        with patch.object(scraper.db, 'connect') as mock_connect:
            mock_cursor = Mock()
            # First call succeeds, second fails
            mock_cursor.execute.side_effect = [None, Exception("Duplicate"), None]
            mock_connect.return_value.cursor.return_value = mock_cursor
            mock_connect.return_value.commit = Mock()
            
            with patch.object(scraper, 'get_checkpoint') as mock_checkpoint:
                mock_checkpoint.return_value = {
                    'highest_successful_page': 5,
                    'next_start_page': 6,
                    'total_persisted_records': 341
                }
                
                success, inserted, highest = scraper.persist_results(
                    project_id=1,
                    run_token='run_abc123',
                    data=test_data,
                    source_page=5
                )
                
                # Should insert 1 record despite error on 2nd
                assert success is True
                assert inserted == 1  # Only first succeeded


class TestMetadataDrivenScraperCompletion:
    """Tests for project completion logic"""
    
    def test_project_complete_yes(self):
        """Should recognize project as complete"""
        scraper = MetadataDrivenResumeScraper()
        
        metadata = {
            'total_pages': 50,
            'total_products': 1500
        }
        
        with patch.object(scraper, 'get_checkpoint') as mock_checkpoint:
            mock_checkpoint.return_value = {
                'highest_successful_page': 50,
                'total_persisted_records': 1500
            }
            
            is_complete, reason = scraper.is_project_complete(project_id=1, metadata=metadata)
            
            assert is_complete is True
            assert 'highest_page' in reason.lower()
    
    def test_project_complete_no(self):
        """Should recognize project as incomplete"""
        scraper = MetadataDrivenResumeScraper()
        
        metadata = {
            'total_pages': 50,
            'total_products': 1500
        }
        
        with patch.object(scraper, 'get_checkpoint') as mock_checkpoint:
            mock_checkpoint.return_value = {
                'highest_successful_page': 25,
                'total_persisted_records': 750
            }
            
            is_complete, reason = scraper.is_project_complete(project_id=1, metadata=metadata)
            
            assert is_complete is False
            assert '25' in reason  # Shows current progress


class TestMetadataDrivenScraperOrchestration:
    """Tests for main orchestration flow"""
    
    def test_first_run_uses_original_url_not_generated(self):
        """CRITICAL: First run must use original website URL as-is, NOT generated URL"""
        scraper = MetadataDrivenResumeScraper()
        original_url = 'https://example.com/products'
        
        with patch.object(scraper, 'get_project_metadata') as mock_meta:
            mock_meta.return_value = {
                'project_id': 1,
                'project_name': 'Test Shop',
                'website_url': original_url,
                'total_pages': 50,
                'total_products': 1500,
                'project_token': 't123'
            }
            
            with patch.object(scraper, 'get_checkpoint') as mock_checkpoint:
                # First run: no prior progress
                mock_checkpoint.return_value = {
                    'highest_successful_page': 0,
                    'next_start_page': 1,
                    'total_persisted_records': 0
                }
                
                with patch.object(scraper, 'is_project_complete') as mock_complete:
                    mock_complete.return_value = (False, "Incomplete")
                    
                    # CRITICAL: generate_next_page_url should NOT be called on first run
                    with patch.object(scraper, 'generate_next_page_url') as mock_gen_url:
                        with patch.object(scraper, 'trigger_run') as mock_trigger:
                            mock_trigger.return_value = {
                                'success': True,
                                'run_token': 'run_first_123'
                            }
                            
                            result = scraper.resume_or_start_scraping(project_id=1, project_token='t123')
                            
                            # Verify success
                            assert result['success'] is True, "First run should succeed"
                            assert result['run_token'] == 'run_first_123'
                            assert result['next_start_page'] == 1
                            
                            # CRITICAL: generate_next_page_url must NOT be called
                            assert mock_gen_url.call_count == 0, \
                                "generate_next_page_url should NOT be called on first run"
                            
                            # Verify trigger_run was called with original URL, not generated
                            mock_trigger.assert_called_once()
                            call_args = mock_trigger.call_args
                            called_url = call_args[0][1]  # Second positional arg is start_url
                            assert called_url == original_url, \
                                f"First run should use original URL {original_url}, got {called_url}"

    def test_resumed_run_uses_generated_url(self):
        """Resumed run must use generated next-page URL, calling generate_next_page_url"""
        scraper = MetadataDrivenResumeScraper()
        original_url = 'https://example.com/products'
        generated_url = 'https://example.com/products?page=6'
        
        with patch.object(scraper, 'get_project_metadata') as mock_meta:
            mock_meta.return_value = {
                'project_id': 2,
                'project_name': 'Test Shop',
                'website_url': original_url,
                'total_pages': 50,
                'total_products': 1500,
                'project_token': 't456'
            }
            
            with patch.object(scraper, 'get_checkpoint') as mock_checkpoint:
                # Resumed run: already scraped 5 pages
                mock_checkpoint.return_value = {
                    'highest_successful_page': 5,
                    'next_start_page': 6,
                    'total_persisted_records': 500
                }
                
                with patch.object(scraper, 'is_project_complete') as mock_complete:
                    mock_complete.return_value = (False, "Incomplete")
                    
                    # generate_next_page_url MUST be called on resumed run
                    with patch.object(scraper, 'generate_next_page_url') as mock_gen_url:
                        mock_gen_url.return_value = generated_url
                        
                        with patch.object(scraper, 'trigger_run') as mock_trigger:
                            mock_trigger.return_value = {
                                'success': True,
                                'run_token': 'run_resumed_456'
                            }
                            
                            result = scraper.resume_or_start_scraping(project_id=2, project_token='t456')
                            
                            # Verify success
                            assert result['success'] is True, "Resumed run should succeed"
                            assert result['run_token'] == 'run_resumed_456'
                            assert result['next_start_page'] == 6
                            assert result['highest_successful_page'] == 5
                            
                            # CRITICAL: generate_next_page_url MUST be called for page 6
                            mock_gen_url.assert_called_once_with(original_url, 6, None)
                            
                            # Verify trigger_run was called with generated URL
                            mock_trigger.assert_called_once()
                            call_args = mock_trigger.call_args
                            called_url = call_args[0][1]  # Second positional arg is start_url
                            assert called_url == generated_url, \
                                f"Resumed run should use generated URL {generated_url}, got {called_url}"

    def test_project_complete_no_new_run(self):
        """Completed project must not start new run"""
        scraper = MetadataDrivenResumeScraper()
        
        with patch.object(scraper, 'get_project_metadata') as mock_meta:
            mock_meta.return_value = {
                'project_id': 3,
                'project_name': 'Complete Shop',
                'website_url': 'https://example.com/products',
                'total_pages': 10,
                'total_products': 300,
                'project_token': 't789'
            }
            
            with patch.object(scraper, 'get_checkpoint') as mock_checkpoint:
                # All pages already scraped
                mock_checkpoint.return_value = {
                    'highest_successful_page': 10,
                    'next_start_page': 11,
                    'total_persisted_records': 300
                }
                
                with patch.object(scraper, 'is_project_complete') as mock_complete:
                    mock_complete.return_value = (True, "All 10 pages completed")
                    
                    with patch.object(scraper, 'mark_project_complete') as mock_mark:
                        result = scraper.resume_or_start_scraping(project_id=3, project_token='t789')
                        
                        # Must return complete=True and not start a run
                        assert result['success'] is True
                        assert result['project_complete'] is True
                        assert 'run_token' not in result or result.get('run_token') is None
                        assert result['highest_successful_page'] == 10
                        assert result['total_pages'] == 10
                        
                        # Must mark project as complete
                        mock_mark.assert_called_once_with(3)

    def test_missing_website_url_error(self):
        """Missing website_url must fail with clear error"""
        scraper = MetadataDrivenResumeScraper()
        
        with patch.object(scraper, 'get_project_metadata') as mock_meta:
            mock_meta.return_value = {
                'project_id': 4,
                'project_name': 'No URL Shop',
                'website_url': '',  # EMPTY - this is the problem
                'total_pages': 50,
                'total_products': 1500,
                'project_token': 't_missing'
            }
            
            with patch.object(scraper, 'get_checkpoint') as mock_checkpoint:
                mock_checkpoint.return_value = {
                    'highest_successful_page': 0,
                    'next_start_page': 1,
                    'total_persisted_records': 0
                }
                
                with patch.object(scraper, 'is_project_complete') as mock_complete:
                    mock_complete.return_value = (False, "Incomplete")
                    
                    result = scraper.resume_or_start_scraping(project_id=4, project_token='t_missing')
                    
                    # Must fail gracefully
                    assert result['success'] is False
                    assert 'website_url' in result.get('error', '').lower() or 'url' in result.get('error', '').lower()
                    assert result.get('message', '').strip() != ''


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
