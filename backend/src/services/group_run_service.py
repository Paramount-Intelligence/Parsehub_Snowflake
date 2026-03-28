"""
Group Run Service - Simplified batch execution of multiple projects
Runs each project token sequentially, same as individual project runs
"""

import logging
from typing import Dict, List, Optional
import requests
import os

logger = logging.getLogger(__name__)


class GroupRunService:
    """Simple sequential runner for group projects"""
    
    def __init__(self, db):
        self.db = db
        self.parsehub_api_key = os.getenv('PARSEHUB_API_KEY')
    
    def run_group(self, project_tokens: List[str]) -> Dict:
        """
        Run multiple projects sequentially by calling their run tokens.
        Returns list of results with run_tokens for each successful project.
        """
        if not project_tokens:
            logger.error('[GROUP_RUN] No tokens provided')
            return {
                'success': False,
                'error': 'No project tokens provided',
                'results': []
            }
        
        # Validate and clean tokens
        valid_tokens = [t.strip() for t in project_tokens if isinstance(t, str) and t.strip()]
        
        if not valid_tokens:
            logger.error('[GROUP_RUN] No valid tokens after validation')
            return {
                'success': False,
                'error': 'No valid project tokens provided',
                'results': []
            }
        
        logger.info(f'[GROUP_RUN] Starting batch run for {len(valid_tokens)} projects')
        
        results = []
        successful = 0
        failed = 0
        
        for i, token in enumerate(valid_tokens, 1):
            logger.info(f'[GROUP_RUN] [{i}/{len(valid_tokens)}] Running project with token: {token}')
            
            result = self._run_single_project(token)
            results.append({
                'token': token,
                'success': result['success'],
                'run_token': result.get('run_token'),
                'status': result.get('status'),
                'error': result.get('error')
            })
            
            if result['success']:
                successful += 1
                logger.info(f'[GROUP_RUN] ✓ Project {token} started successfully (run_token: {result.get("run_token")})')
            else:
                failed += 1
                logger.warning(f'[GROUP_RUN] ✗ Project {token} failed: {result.get("error")}')
        
        logger.info(f'[GROUP_RUN] Batch complete: {successful} successful, {failed} failed')
        
        return {
            'success': failed == 0,
            'total_projects': len(valid_tokens),
            'successful': successful,
            'failed': failed,
            'results': results
        }
    
    def _run_single_project(self, token: str) -> Dict:
        """Run a single project by calling ParseHub API - identical to single project run"""
        logger.info(f'[GROUP_RUN] Calling ParseHub API for token: {token}')
        
        if not token or not isinstance(token, str) or not token.strip():
            logger.error(f'[GROUP_RUN] Invalid token format: {repr(token)}')
            return {
                'success': False,
                'error': f'Invalid token format'
            }
        
        try:
            url = f'https://www.parsehub.com/api/v2/projects/{token}/run'
            params = {'api_key': self.parsehub_api_key}
            data = {'pages': 1}
            
            logger.info(f'[GROUP_RUN] POST {url}')
            response = requests.post(url, params=params, data=data, timeout=10)
            
            logger.info(f'[GROUP_RUN] Response status: {response.status_code}')
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f'[GROUP_RUN] ✓ Success - run_token: {result.get("run_token")}')
                return {
                    'success': True,
                    'run_token': result.get('run_token'),
                    'status': result.get('status')
                }
            
            # Handle error response
            try:
                error_data = response.json()
                error_msg = error_data.get('error', f'API error: {response.status_code}')
            except:
                error_msg = 'No such project found - verify correct token'
            
            logger.error(f'[GROUP_RUN] ✗ API error: {error_msg}')
            return {
                'success': False,
                'error': error_msg
            }
            
        except requests.exceptions.Timeout:
            logger.error(f'[GROUP_RUN] Request timeout')
            return {'success': False, 'error': 'Request timeout'}
        except requests.exceptions.ConnectionError:
            logger.error(f'[GROUP_RUN] Connection error')
            return {'success': False, 'error': 'Connection error'}
        except Exception as e:
            logger.error(f'[GROUP_RUN] Exception: {str(e)}')
            return {'success': False, 'error': str(e)}
