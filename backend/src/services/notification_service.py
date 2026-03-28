"""
Email Notification Service
Handles error notifications via SMTP email
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)


class EmailNotificationService:
    """
    Sends email notifications for ParseHub scraping errors and alerts
    """
    
    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.smtp_from = os.getenv('SMTP_FROM')
        self.smtp_use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
        self.notification_email = os.getenv('ERROR_NOTIFICATION_EMAIL')
        
        self._validate_config()
    
    def _validate_config(self):
        """Validate SMTP configuration is complete"""
        required_fields = {
            'SMTP_HOST': self.smtp_host,
            'SMTP_PORT': self.smtp_port,
            'SMTP_USER': self.smtp_user,
            'SMTP_PASSWORD': self.smtp_password,
            'SMTP_FROM': self.smtp_from,
            'ERROR_NOTIFICATION_EMAIL': self.notification_email
        }
        
        missing = [k for k, v in required_fields.items() if not v]
        if missing:
            logger.warning(f"[EMAIL] Missing SMTP config: {', '.join(missing)}. Email notifications will be disabled.")
            self._disabled = True
        else:
            self._disabled = False
    
    def is_enabled(self) -> bool:
        """Check if email notifications are enabled"""
        return not getattr(self, '_disabled', False)
    
    def send_api_failure_alert(self, error_details: Dict) -> bool:
        """
        Send alert for ParseHub API failure
        
        Args:
            error_details: {
                'project_name': str,
                'project_id': int,
                'error_type': str,  # e.g., 'connection_error', 'timeout', 'invalid_response'
                'error_message': str,
                'batch_info': {
                    'start_page': int,
                    'end_page': int,
                    'last_completed_page': int
                },
                'run_token': Optional[str],
                'timestamp': str,
                'retry_count': int,
                'max_retries': int
            }
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_enabled():
            logger.debug("[EMAIL] Notifications disabled, skipping API failure alert")
            return False
        
        try:
            subject = f"[PARSEHUB] API Failure - {error_details.get('project_name', 'Unknown')} (Page {error_details.get('batch_info', {}).get('start_page', '?')})"
            
            body = self._format_api_failure_email(error_details)
            
            return self._send_email(subject, body)
            
        except Exception as e:
            logger.error(f"[EMAIL] Failed to send API failure alert: {e}")
            return False
    
    def send_chunk_completion_notification(self, completion_details: Dict) -> bool:
        """
        Send notification for successful chunk completion (optional, for tracking)
        
        Args:
            completion_details: {
                'project_name': str,
                'project_id': int,
                'chunk_number': int,
                'pages_in_chunk': Tuple[int, int],
                'records_scraped': int,
                'timestamp': str
            }
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_enabled():
            return False
        
        try:
            subject = f"[PARSEHUB] Chunk Completed - {completion_details.get('project_name')} (Chunk #{completion_details.get('chunk_number')})"
            
            body = self._format_completion_email(completion_details)
            
            return self._send_email(subject, body, priority='low')
            
        except Exception as e:
            logger.error(f"[EMAIL] Failed to send chunk completion notification: {e}")
            return False
    
    def send_scraping_stalled_alert(self, stall_details: Dict) -> bool:
        """
        Send alert when scraping has stalled (empty batches, no progress)
        
        Args:
            stall_details: {
                'project_name': str,
                'project_id': int,
                'last_completed_page': int,
                'consecutive_empty_batches': int,
                'time_stalled_minutes': int,
                'last_run_token': Optional[str],
                'timestamp': str
            }
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_enabled():
            return False
        
        try:
            subject = f"[PARSEHUB] Scraping Stalled - {stall_details.get('project_name')} (Last page: {stall_details.get('last_completed_page')})"
            
            body = self._format_stall_alert_email(stall_details)
            
            return self._send_email(subject, body, priority='high')
            
        except Exception as e:
            logger.error(f"[EMAIL] Failed to send scraping stalled alert: {e}")
            return False
    
    def _format_api_failure_email(self, error_details: Dict) -> str:
        """Format API failure email body"""
        batch_info = error_details.get('batch_info', {})
        timestamp = error_details.get('timestamp', datetime.now().isoformat())
        retry_count = error_details.get('retry_count', 0)
        max_retries = error_details.get('max_retries', 3)
        
        return f"""
ParseHub API Failure Alert
================================

Project: {error_details.get('project_name', 'Unknown')}
Project ID: {error_details.get('project_id')}
Timestamp: {timestamp}

Error Details:
--------------
Type: {error_details.get('error_type', 'Unknown')}
Message: {error_details.get('error_message', 'No details available')}

Batch Information:
------------------
Start Page: {batch_info.get('start_page', '?')}
End Page: {batch_info.get('end_page', '?')}
Last Completed Page: {batch_info.get('last_completed_page', 'Unknown')}

Run Token: {error_details.get('run_token', 'Not generated')}

Retry Status:
-----------
Attempt: {retry_count} of {max_retries}
Status: {'Retrying...' if retry_count < max_retries else 'Max retries exhausted - Manual intervention required'}

Action Required:
- Check ParseHub API status at https://status.parsehub.com
- Verify API key and project configuration in .env
- Check network connectivity and firewall settings
- If issue persists, contact ParseHub support
- Check batch page range validity for target website

Generated by: Parsehub-Snowflake Orchestrator
"""

    def _format_completion_email(self, completion_details: Dict) -> str:
        """Format chunk completion email body"""
        pages = completion_details.get('pages_in_chunk', (0, 0))
        
        return f"""
ParseHub Chunk Completion Notification
=====================================

Project: {completion_details.get('project_name', 'Unknown')}
Project ID: {completion_details.get('project_id')}
Timestamp: {completion_details.get('timestamp', datetime.now().isoformat())}

Chunk Information:
------------------
Chunk Number: #{completion_details.get('chunk_number')}
Pages Processed: {pages[0]} - {pages[1]}
Records Scraped: {completion_details.get('records_scraped', 0)}

Status: ✓ Successfully Completed

Next Action:
- Orchestrator will automatically process next chunk
- No manual intervention required
- Check dashboard for real-time progress

Generated by: Parsehub-Snowflake Orchestrator
"""

    def _format_stall_alert_email(self, stall_details: Dict) -> str:
        """Format scraping stalled alert email body"""
        
        return f"""
ALERT: ParseHub Scraping Stalled
=================================

Project: {stall_details.get('project_name', 'Unknown')}
Project ID: {stall_details.get('project_id')}
Timestamp: {stall_details.get('timestamp', datetime.now().isoformat())}

Stall Information:
------------------
Last Completed Page: {stall_details.get('last_completed_page')}
Consecutive Empty Batches: {stall_details.get('consecutive_empty_batches')}
Time Stalled: {stall_details.get('time_stalled_minutes', 'Unknown')} minutes
Last Run Token: {stall_details.get('last_run_token', 'None')}

Possible Causes:
- Website structure changed (no more data at pagination URLs)
- ParseHub found all available data (legitimate completion)
- API rate limiting or temporary service degradation
- Network connectivity issues
- Invalid pagination pattern detection

Action Required:
1. Verify website still has paginated content
2. Check website's robots.txt and Terms of Service
3. Review ParseHub project settings and patterns
4. Contact ParseHub support if API appears degraded
5. Consider adjusting pagination URL patterns

Generated by: Parsehub-Snowflake Orchestrator
"""

    def _send_email(self, subject: str, body: str, priority: str = 'normal') -> bool:
        """
        Send email via SMTP
        
        Args:
            subject: Email subject
            body: Email body (plain text)
            priority: 'low', 'normal', or 'high' (affects X-Priority header)
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_from
            msg['To'] = self.notification_email
            msg['Subject'] = subject
            
            # Add priority header
            priority_values = {'low': '5', 'normal': '3', 'high': '1'}
            msg['X-Priority'] = priority_values.get(priority, '3')
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect and send
            if self.smtp_use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"[EMAIL] Successfully sent: {subject}")
            return True
            
        except smtplib.SMTPAuthenticationError:
            logger.error(f"[EMAIL] SMTP authentication failed - check SMTP_USER and SMTP_PASSWORD")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"[EMAIL] SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"[EMAIL] Unexpected error sending email: {e}")
            return False


# Global instance
_notification_service = None

def get_notification_service() -> EmailNotificationService:
    """Get or create global notification service instance"""
    global _notification_service
    if _notification_service is None:
        _notification_service = EmailNotificationService()
    return _notification_service
