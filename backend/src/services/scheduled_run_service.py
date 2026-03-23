"""
Scheduled Run Service
Manages scheduled project runs using APScheduler with database persistence
"""
import logging
import os
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import requests
from pytz import utc
from tzlocal import get_localzone

logger = logging.getLogger(__name__)

# Get system's local timezone
LOCAL_TZ = get_localzone()


class ScheduledRunService:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=LOCAL_TZ)
        self.scheduled_runs = {}
        self.api_key = os.getenv('PARSEHUB_API_KEY')
        self.base_url = os.getenv('PARSEHUB_BASE_URL', 'https://www.parsehub.com/api/v2')
        self.db = None  # Will be set by the API server

    def set_database(self, db):
        """Set database connection for persistence"""
        self.db = db
        self._load_from_database()

    def _load_from_database(self):
        """Load scheduled runs from database on startup"""
        if not self.db:
            logger.warning("[WARN] No database available, skipping load from DB")
            return

        try:
            conn = self.db.connect()
            cursor = self.db.cursor()
            
            query = """
            SELECT job_id, project_token, schedule_type, scheduled_time, frequency, 
                   day_of_week, pages, created_at 
            FROM SCHEDULED_RUNS 
            WHERE active = TRUE
            """
            cursor.execute(query)
            result = cursor.fetchall()
            
            for row in result:
                try:
                    job_id = row[0]
                    project_token = row[1]
                    schedule_type = row[2]
                    scheduled_time = row[3]
                    frequency = row[4]
                    day_of_week = row[5]
                    pages = int(row[6])

                    # Recreate scheduler job
                    if schedule_type == 'once':
                        run_time = datetime.fromisoformat(scheduled_time)
                        if run_time > datetime.now(LOCAL_TZ):
                            self.scheduler.add_job(
                                self._run_project,
                                trigger='date',
                                run_date=run_time,
                                args=[project_token, pages],
                                id=job_id,
                                replace_existing=True
                            )
                    elif schedule_type == 'recurring':
                        time_str = scheduled_time
                        hour, minute = map(int, time_str.split(':'))
                        
                        if frequency == 'daily':
                            trigger = CronTrigger(hour=hour, minute=minute, timezone=LOCAL_TZ)
                        elif frequency == 'weekly':
                            day_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                                      'friday': 4, 'saturday': 5, 'sunday': 6}
                            day_num = day_map.get(day_of_week or 'monday', 0)
                            trigger = CronTrigger(day_of_week=day_num, hour=hour, minute=minute, timezone=LOCAL_TZ)
                        elif frequency == 'monthly':
                            trigger = CronTrigger(day=1, hour=hour, minute=minute, timezone=LOCAL_TZ)
                        else:
                            continue

                        self.scheduler.add_job(
                            self._run_project,
                            trigger=trigger,
                            args=[project_token, pages],
                            id=job_id,
                            replace_existing=True
                        )

                    # Store in memory
                    self.scheduled_runs[job_id] = {
                        'project_token': project_token,
                        'type': schedule_type,
                        'scheduled_time': scheduled_time if schedule_type == 'once' else None,
                        'frequency': frequency if schedule_type == 'recurring' else None,
                        'time': scheduled_time if schedule_type == 'recurring' else None,
                        'day_of_week': day_of_week,
                        'pages': pages,
                        'created_at': row[7]
                    }
                    logger.info(f"[OK] Loaded from DB: {job_id}")
                except Exception as e:
                    logger.error(f"[ERROR] Failed to load job {job_id}: {e}")
                    continue
            
            self.db.disconnect()
            logger.info(f"[OK] Loaded {len(self.scheduled_runs)} scheduled runs from database")
        except Exception as e:
            logger.error(f"[ERROR] Failed to load from database: {e}")
            try:
                self.db.disconnect()
            except:
                pass

    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("[OK] Scheduled Run Service started")

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("[OK] Scheduled Run Service stopped")

    def schedule_once(self, project_token: str, scheduled_time: str, pages: int = 1) -> dict:
        """Schedule project to run once at specific time"""
        try:
            # Validate pages
            if pages < 1:
                return {'success': False, 'error': 'Pages must be at least 1'}
            
            # Parse and validate scheduled time
            run_time = datetime.fromisoformat(scheduled_time)
            
            # Check if scheduled time is in the past
            now = datetime.now(LOCAL_TZ) if run_time.tzinfo else datetime.now()
            if run_time < now:
                return {'success': False, 'error': f'Scheduled time must be in the future. Current time: {now.isoformat()}'}
            
            job_id = f"{project_token}_{run_time.timestamp()}"

            self.scheduler.add_job(
                self._run_project,
                trigger='date',
                run_date=run_time,
                args=[project_token, pages],
                id=job_id,
                replace_existing=True
            )

            run_data = {
                'project_token': project_token,
                'type': 'once',
                'scheduled_time': scheduled_time,
                'pages': pages,
                'created_at': datetime.now().isoformat()
            }
            
            self.scheduled_runs[job_id] = run_data

            # Save to database
            if self.db:
                self._save_to_database(job_id, run_data)

            logger.info(f"[OK] Scheduled once: {project_token} at {scheduled_time}")
            return {
                'success': True,
                'job_id': job_id,
                'message': f'Scheduled for {scheduled_time}',
                'scheduled_time': scheduled_time
            }
        except Exception as e:
            logger.error(f"[ERROR] Schedule failed: {e}")
            return {'success': False, 'error': str(e)}

    def schedule_recurring(self, project_token: str, scheduled_time: str, frequency: str,
                          day_of_week: str = None, pages: int = 1) -> dict:
        """Schedule project to run recurring"""
        try:
            # Validate pages
            if pages < 1:
                return {'success': False, 'error': 'Pages must be at least 1'}
            
            # Validate frequency
            if frequency not in ['daily', 'weekly', 'monthly']:
                return {'success': False, 'error': f'Invalid frequency: {frequency}. Must be daily, weekly, or monthly'}
            
            # Validate day_of_week for weekly frequency
            valid_days = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                         'friday': 4, 'saturday': 5, 'sunday': 6}
            
            if frequency == 'weekly' and day_of_week:
                day_lower = day_of_week.lower()
                if day_lower not in valid_days:
                    return {'success': False, 'error': f'Invalid day_of_week: {day_of_week}. Must be one of: {", ".join(valid_days.keys())}'}
            
            time_str = scheduled_time.split('T')[1] if 'T' in scheduled_time else scheduled_time
            
            # Validate time format
            try:
                hour, minute = map(int, time_str.split(':'))
                if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                    return {'success': False, 'error': 'Invalid time: hours must be 0-23, minutes must be 0-59'}
            except ValueError:
                return {'success': False, 'error': 'Invalid time format: expected HH:MM'}
            
            job_id = f"{project_token}_recurring_{frequency}_{day_of_week or 'daily'}"

            if frequency == 'daily':
                trigger = CronTrigger(hour=hour, minute=minute, timezone=LOCAL_TZ)
            elif frequency == 'weekly':
                day_num = valid_days.get(day_of_week.lower() if day_of_week else 'monday', 0)
                trigger = CronTrigger(day_of_week=day_num, hour=hour, minute=minute, timezone=LOCAL_TZ)
            elif frequency == 'monthly':
                trigger = CronTrigger(day=1, hour=hour, minute=minute, timezone=LOCAL_TZ)
            else:
                return {'success': False, 'error': f'Unknown frequency: {frequency}'}

            self.scheduler.add_job(
                self._run_project,
                trigger=trigger,
                args=[project_token, pages],
                id=job_id,
                replace_existing=True
            )

            run_data = {
                'project_token': project_token,
                'type': 'recurring',
                'frequency': frequency,
                'time': time_str,
                'day_of_week': day_of_week,
                'pages': pages,
                'created_at': datetime.now().isoformat()
            }

            self.scheduled_runs[job_id] = run_data

            # Save to database
            if self.db:
                self._save_to_database(job_id, run_data)

            logger.info(f"[OK] Scheduled recurring: {project_token} {frequency} at {time_str}")
            return {
                'success': True,
                'job_id': job_id,
                'message': f'Scheduled {frequency} at {time_str}',
                'frequency': frequency,
                'time': time_str
            }
        except Exception as e:
            logger.error(f"[ERROR] Recurring schedule failed: {e}")
            return {'success': False, 'error': str(e)}

    def cancel_scheduled_run(self, job_id: str) -> dict:
        """Cancel a scheduled run"""
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self.scheduled_runs:
                del self.scheduled_runs[job_id]

            # Update database
            if self.db:
                try:
                    conn = self.db.connect()
                    cursor = self.db.cursor()
                    query = "UPDATE SCHEDULED_RUNS SET active = FALSE WHERE job_id = %s"
                    cursor.execute(query, (job_id,))
                    conn.commit()
                    self.db.disconnect()
                except Exception as db_error:
                    logger.error(f"[ERROR] Failed to update database: {db_error}")
                    try:
                        self.db.disconnect()
                    except:
                        pass

            logger.info(f"[OK] Cancelled: {job_id}")
            return {'success': True, 'message': f'Cancelled: {job_id}'}
        except Exception as e:
            logger.error(f"[ERROR] Cancel failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_scheduled_runs(self) -> list:
        """Get all scheduled runs"""
        # Return runs with job_id included
        result = []
        for job_id, run_data in self.scheduled_runs.items():
            run_with_id = dict(run_data)
            run_with_id['job_id'] = job_id
            result.append(run_with_id)
        return result

    def _save_to_database(self, job_id: str, run_data: dict):
        """Save scheduled run to database"""
        try:
            conn = self.db.connect()
            cursor = self.db.cursor()
            
            query = """
            INSERT INTO SCHEDULED_RUNS 
            (job_id, project_token, schedule_type, scheduled_time, frequency, day_of_week, pages, created_at, active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            params = (
                job_id,
                run_data['project_token'],
                run_data['type'],
                run_data.get('scheduled_time') or run_data.get('time'),
                run_data.get('frequency'),
                run_data.get('day_of_week'),
                run_data.get('pages', 1),
                run_data.get('created_at'),
                True  # active flag - set to True for all scheduled runs
            )
            
            cursor.execute(query, params)
            conn.commit()
            self.db.disconnect()
            logger.info(f"[OK] Saved to DB: {job_id}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to save to database: {e}")
            try:
                self.db.disconnect()
            except:
                pass

    def _run_project(self, project_token: str, pages: int = 1):
        """Execute scheduled project run"""
        try:
            logger.info(f"[EXECUTE] Running {project_token} ({pages} pages)")
            url = f'{self.base_url}/projects/{project_token}/run'
            data = {'api_key': self.api_key, 'pages': pages}
            response = requests.post(url, data=data, timeout=10)

            if response.status_code == 200:
                run_info = response.json()
                logger.info(f"[SUCCESS] ParseHub run started: {run_info.get('run_token')}")
                return run_info
            else:
                logger.error(f"[ERROR] ParseHub error {response.status_code}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"[ERROR] Execution failed: {e}")
            return None


_service = None


def get_scheduled_run_service() -> ScheduledRunService:
    global _service
    if _service is None:
        _service = ScheduledRunService()
    return _service


def start_scheduled_run_service():
    service = get_scheduled_run_service()
    service.start()
    return service


def stop_scheduled_run_service():
    global _service
    if _service:
        _service.stop()
        _service = None
