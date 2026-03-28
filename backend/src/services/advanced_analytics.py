"""
Advanced Analytics Service - Comprehensive data analysis and statistics
"""

import json
import csv
import sys
from io import StringIO
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

root_dir = Path(__file__).parent.parent.parent  # backend/
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.models.database import ParseHubDatabase


class AdvancedAnalyticsService:
    """Service for comprehensive analytics and statistics"""
    
    def __init__(self):
        self.db = ParseHubDatabase()
    
    def get_project_analytics(self, project_id: int) -> Optional[Dict]:
        """
        Get comprehensive analytics for a project
        
        Returns:
            {
                'project': {...},
                'data': {...},
                'runs': {...},
                'data_quality': {...},
                'pagination_status': {...}
            }
        """
        try:
            conn = self.db.connect()
            if not conn:
                return None
            cursor = conn.cursor()
            
            # Get project info
            cursor.execute('''
                SELECT id, token, title FROM projects WHERE id = %s
            ''', (project_id,))
            project = cursor.fetchone()
            
            if not project:
                self.db.disconnect()
                return None
        
            # Get data stats
            cursor.execute('''
                SELECT COUNT(*) as total FROM scraped_data WHERE project_id = %s
            ''', (project_id,))
            result = cursor.fetchone()
            # Handle both dict and tuple results
            total_records = (result.get('total') if isinstance(result, dict) else result[0]) if result else 0
        
            # Get runs info
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_runs,
                    SUM(CASE WHEN status='complete' THEN 1 ELSE 0 END) as completed_runs,
                    MAX(end_time) as last_completed
                FROM runs WHERE project_id = %s
            ''', (project_id,))
            runs_info = cursor.fetchone()
            
            # Calculate statistics
            stats = self.calculate_statistics(project_id)
            
            # Get pagination info
            cursor.execute('''
                SELECT 
                    MAX(CAST(json_extract(data, '$.page_number') AS INTEGER)) as last_page
                FROM scraped_data WHERE project_id = %s
            ''', (project_id,))
            page_result = cursor.fetchone()
            last_page = (page_result.get('last_page') if isinstance(page_result, dict) else page_result[0]) if page_result else 1
            
            self.db.disconnect()
        except Exception as e:
            print(f"[ERROR] get_project_analytics failed: {e}", file=sys.stderr)
            return None
        
        
        # Extract values from project row
        if isinstance(project, dict):
            project_data = {k.lower(): v for k, v in project.items()}
            proj_id = project_data.get('id')
            proj_token = project_data.get('token')
            proj_title = project_data.get('title')
        else:
            proj_id = project[0]
            proj_token = project[1]
            proj_title = project[2]
        
        # Extract values from runs_info row
        if isinstance(runs_info, dict):
            runs_lower = {k.lower(): v for k, v in runs_info.items()}
            total_runs = runs_lower.get('total_runs') or 0
            completed_runs = runs_lower.get('completed_runs') or 0
            last_completed = runs_lower.get('last_completed')
        else:
            total_runs = runs_info[0] or 0
            completed_runs = runs_info[1] or 0
            last_completed = runs_info[2]
        
        analytics = {
            'project': {
                'id': proj_id,
                'token': proj_token,
                'title': proj_title
            },
            'data': {
                'total_records': total_records,
                'last_page_scraped': last_page,
                'completion_score': self._calculate_completion_score(stats)
            },
            'runs': {
                'total_runs': total_runs,
                'completed_runs': completed_runs,
                'last_completed': last_completed
            },
            'data_quality': stats,
            'timestamp': datetime.now().isoformat()
        }
        
        return analytics
    
    def calculate_statistics(self, project_id: int) -> Dict:
        """
        Calculate detailed statistics for each column
        
        Returns:
            {
                'column_name': {
                    'total_count': int,
                    'filled_count': int,
                    'empty_count': int,
                    'completion_percentage': float,
                    'unique_count': int,
                    'sample_values': list
                }
            }
        """
        try:
            conn = self.db.connect()
            if not conn:
                return {}
            cursor = conn.cursor()
        
            # Get all data for this project
            cursor.execute('''
                SELECT data FROM scraped_data WHERE project_id = %s
                ORDER BY created_at ASC
        ''', (project_id,))
        
        raw_data = cursor.fetchall()
        conn.close()
        
        if not raw_data:
            return {}
        
        # Parse JSON data
        data_list = []
        for row in raw_data:
            try:
                data_list.append(json.loads(row['data']))
            except:
                continue
        
        if not data_list:
            return {}
        
        # Extract all keys
        all_keys = set()
        for item in data_list:
            if isinstance(item, dict):
                all_keys.update(item.keys())
        
        # Calculate per-column statistics
        stats = {}
        
        for key in sorted(all_keys):
            values = []
            filled_count = 0
            unique_values = set()
            
            for item in data_list:
                if isinstance(item, dict):
                    value = item.get(key)
                    values.append(value)
                    
                    if value is not None and str(value).strip():
                        filled_count += 1
                        unique_values.add(str(value))
            
            completion_pct = (filled_count / len(data_list) * 100) if data_list else 0
            
            stats[key] = {
                'total_count': len(data_list),
                'filled_count': filled_count,
                'empty_count': len(data_list) - filled_count,
                'completion_percentage': round(completion_pct, 2),
                'unique_count': len(unique_values),
                'sample_values': list(unique_values)[:5]
            }
        
        return stats
    
    def get_field_completion_report(self, project_id: int) -> Dict:
        """
        Get detailed field completion report
        Useful for identifying which fields have the most/least data
        """
        stats = self.calculate_statistics(project_id)
        
        # Sort by completion percentage
        sorted_fields = sorted(
            stats.items(),
            key=lambda x: x[1]['completion_percentage'],
            reverse=True
        )
        
        return {
            'fields': [
                {
                    'name': field_name,
                    **field_stats
                }
                for field_name, field_stats in sorted_fields
            ],
            'total_fields': len(stats),
            'average_completion': sum(s['completion_percentage'] for s in stats.values()) / len(stats) if stats else 0
        }
    
    def get_data_by_column(self, project_id: int, column_name: str, 
                          limit: int = 100) -> List:
        """
        Get all values for a specific column
        """
        try:
            conn = self.db.connect()
            if not conn:
                return []
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT data FROM scraped_data WHERE project_id = %s
                LIMIT %s
            ''', (project_id, limit))
            
            rows = cursor.fetchall()
            self.db.disconnect()
        except Exception as e:
            print(f"[ERROR] get_data_by_column failed: {e}", file=sys.stderr)
            return []
        
        values = []
        for row in rows:
            try:
                data = json.loads(row['data'])
                if isinstance(data, dict) and column_name in data:
                    values.append(data[column_name])
            except:
                continue
        
        return values
    
    def export_data_csv(self, project_id: int) -> str:
        """Export project data as CSV"""
        try:
            conn = self.db.connect()
            if not conn:
                return ""
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT data FROM scraped_data WHERE project_id = %s
                ORDER BY created_at ASC
            ''', (project_id,))
            
            rows = cursor.fetchall()
            self.db.disconnect()
        except Exception as e:
            print(f"[ERROR] export_data_csv failed: {e}", file=sys.stderr)
            return ""
        
        if not rows:
            return ""
        
        # Parse data
        data_list = []
        all_keys = set()
        
        for row in rows:
            try:
                item = json.loads(row['data'])
                if isinstance(item, dict):
                    data_list.append(item)
                    all_keys.update(item.keys())
            except:
                continue
        
        if not data_list:
            return ""
        
        # Generate CSV
        output = StringIO()
        fieldnames = sorted(list(all_keys))
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data_list)
        
        return output.getvalue()
    
    def export_data_json(self, project_id: int) -> str:
        """Export project data as JSON"""
        try:
            conn = self.db.connect()
            if not conn:
                return ""
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT data FROM scraped_data WHERE project_id = %s
                ORDER BY created_at ASC
            ''', (project_id,))
            
            rows = cursor.fetchall()
            self.db.disconnect()
        except Exception as e:
            print(f"[ERROR] export_data_json failed: {e}", file=sys.stderr)
            return ""
        
        data_list = []
        for row in rows:
            try:
                data_list.append(json.loads(row['data']))
            except:
                continue
        
        return json.dumps(data_list, indent=2)
    
    def _calculate_completion_score(self, stats: Dict) -> float:
        """
        Calculate overall data completion score (0-100)
        Based on average completion percentage across all fields
        """
        if not stats:
            return 0.0
        
        completions = [s['completion_percentage'] for s in stats.values()]
        return round(sum(completions) / len(completions), 2) if completions else 0.0
