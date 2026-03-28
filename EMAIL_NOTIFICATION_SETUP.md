# Email Notification System - Implementation Guide

## Overview

The ParseHub-Snowflake system now includes **email notifications** for API failures and scraping issues. When critical errors occur, administrators receive immediate email alerts with detailed context for debugging.

## Quick Setup

### 1. Configure SMTP Settings in `.env`

Create or update `.env` file in `backend/src/config/`:

```bash
# SMTP Configuration
SMTP_HOST=smtp.gmail.com              # Gmail SMTP server
SMTP_PORT=587                          # Standard TLS port
SMTP_USER=your-email@gmail.com         # Your Gmail address
SMTP_PASSWORD=your-app-password        # Gmail App Password (NOT regular password)
SMTP_FROM=parsehub-alerts@yourdomain.com  # Sender email address
SMTP_USE_TLS=true                      # Use TLS encryption

# Recipient for failure alerts
ERROR_NOTIFICATION_EMAIL=admin@yourdomain.com
```

### 2. Gmail Setup (Recommended)

If using Gmail for email delivery:

**Step 1: Enable 2-Step Verification**
- Go to: https://myaccount.google.com/security
- Click "2-Step Verification"
- Follow prompts to enable it

**Step 2: Generate App Password**
- Return to https://myaccount.google.com/apppasswords
- Select "Mail" and "Windows Computer" (or your OS)
- Gmail will generate a 16-character password
- Copy this password to `SMTP_PASSWORD` in .env

**Step 3: Set Environment Variables**
```bash
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx  # 16-char app password (spaces removed)
SMTP_FROM=your-email@gmail.com     # Same as SMTP_USER for Gmail
```

### 3. Other Email Providers

**Outlook/Office365:**
```bash
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USER=your-email@outlook.com
SMTP_PASSWORD=your-password
SMTP_FROM=your-email@outlook.com
SMTP_USE_TLS=true
```

**Yahoo:**
```bash
SMTP_HOST=smtp.mail.yahoo.com
SMTP_PORT=465          # Note: Different port
SMTP_USER=your-email@yahoo.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@yahoo.com
SMTP_USE_TLS=false     # Yahoo uses SSL, not TLS
```

## How It Works

### Triggered Events

Email notifications are automatically sent when:

1. **API Connection Errors** - ParseHub API returns non-200 status
2. **Missing Run Token** - Response doesn't contain expected run_token
3. **Run Cancellation** - ParseHub cancels the batch run
4. **Run Failure** - ParseHub reports run error
5. **Polling Timeout** - Run takes >30 minutes to complete
6. **Data Fetch Failure** - Cannot retrieve results from ParseHub
7. **Storage Failure** - Cannot save data to Snowflake
8. **Scraping Stalled** - 3 consecutive empty batches (no progress)
9. **Fatal Errors** - Unexpected exceptions during batch cycle

### Email Content

Each notification includes:

```
Project: ProductScraper
Project ID: 42
Timestamp: 2025-01-20T14:23:45.123456

Error Details:
Type: http_error
Message: ParseHub API returned 429: Rate limit exceeded

Batch Information:
Start Page: 21
End Page: 30
Last Completed Page: 20

Run Token: abc123def456
Retry Status: Attempt 1 of 3
```

## Code Usage

### Manual Trigger

```python
from src.services.notification_service import get_notification_service

notification_service = get_notification_service()

# Send API failure alert
notification_service.send_api_failure_alert({
    'project_id': 42,
    'project_name': 'ProductScraper',
    'error_type': 'connection_error',
    'error_message': 'Connection timeout after 30 seconds',
    'batch_info': {
        'start_page': 21,
        'end_page': 30,
        'last_completed_page': 20
    },
    'run_token': 'abc123def456',
    'timestamp': datetime.now().isoformat(),
    'retry_count': 1,
    'max_retries': 3
})
```

### Automatic Integration

The `ChunkPaginationOrchestrator` automatically sends notifications:

```python
orchestrator = ChunkPaginationOrchestrator()
result = orchestrator.run_scraping_batch_cycle(
    project_id=42,
    project_token='xyz789',
    base_url='https://example.com/products',
    project_name='ProductScraper'  # ← Pass project name for notifications
)
```

## Disabling Notifications

If SMTP is not configured, notifications are automatically disabled (graceful degradation):

```python
notification_service = get_notification_service()

if notification_service.is_enabled():
    print("Email notifications are active")
else:
    print("Email notifications disabled (SMTP not configured)")
```

Notifications can also be disabled by omitting `ERROR_NOTIFICATION_EMAIL` from `.env`.

## Testing

### Test 1: Configuration Validation

```python
from src.services.notification_service import get_notification_service

service = get_notification_service()
print(f"Notifications enabled: {service.is_enabled()}")
```

### Test 2: Send Test Email

```python
from src.services.notification_service import get_notification_service
from datetime import datetime

service = get_notification_service()
service.send_api_failure_alert({
    'project_id': 1,
    'project_name': 'Test Project',
    'error_type': 'test',
    'error_message': 'This is a test notification',
    'batch_info': {
        'start_page': 1,
        'end_page': 10,
        'last_completed_page': 0
    },
    'run_token': 'test-token-123',
    'timestamp': datetime.now().isoformat(),
    'retry_count': 1,
    'max_retries': 3
})
```

### Test 3: Simulate API Failure

```python
from src.services.chunk_pagination_orchestrator import ChunkPaginationOrchestrator

# This will trigger email notification if run fails
orchestrator = ChunkPaginationOrchestrator()
result = orchestrator.run_scraping_batch_cycle(
    project_id=999,
    project_token='invalid-token',
    base_url='https://example.com',
    project_name='TestProject'
)

if not result['success']:
    print(f"Failed: {result['error']}")
    # Email notification already sent automatically
```

## Troubleshooting

### Emails Not Sending

**Check SMTP Configuration:**
```python
import os
from dotenv import load_dotenv

load_dotenv()
print(f"SMTP_HOST: {os.getenv('SMTP_HOST')}")
print(f"SMTP_PORT: {os.getenv('SMTP_PORT')}")
print(f"SMTP_USER: {os.getenv('SMTP_USER')}")
print(f"ERROR_NOTIFICATION_EMAIL: {os.getenv('ERROR_NOTIFICATION_EMAIL')}")
```

**Common Issues:**

| Issue | Solution |
|-------|----------|
| "Authentication failed" | Verify SMTP_USER/PASSWORD and that 2-Step is enabled (Gmail) |
| "Connection refused" | Check SMTP_HOST and SMTP_PORT are correct |
| "Email not received" | Check spam folder, verify ERROR_NOTIFICATION_EMAIL |
| "TLS error" | Set SMTP_USE_TLS=true for port 587, false for port 465 |
| "SMTP disabled" | Verify ERROR_NOTIFICATION_EMAIL is set in .env |

### Email Content Missing

If email arrives but with incomplete details:
- Ensure `project_name` is passed to `run_scraping_batch_cycle()`
- Verify batch_info dict includes all required fields
- Check application logs for exceptions

### Logs

Enable debug logging to see notification attempts:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Now run orchestrator - you'll see:
# [EMAIL] Successfully sent: [PARSEHUB] API Failure - ProjectName...
# [EMAIL] Failed to send API failure alert: SMTP error...
```

## Production Deployment

### Kubernetes Secrets

For Kubernetes deployments, add SMTP variables to secrets:

```bash
kubectl create secret generic parsehub-email \
  --from-literal=SMTP_HOST=smtp.gmail.com \
  --from-literal=SMTP_PORT=587 \
  --from-literal=SMTP_USER=alerts@company.com \
  --from-literal=SMTP_PASSWORD='your-app-password' \
  --from-literal=SMTP_FROM=alerts@company.com \
  --from-literal=ERROR_NOTIFICATION_EMAIL=admin@company.com
```

Reference in deployment:
```yaml
spec:
  containers:
  - name: backend
    env:
    - name: SMTP_HOST
      valueFrom:
        secretKeyRef:
          name: parsehub-email
          key: SMTP_HOST
    # ... other SMTP variables
```

### Best Practices

1. **Use dedicated email account** - Don't use personal email
2. **Enable 2-Factor Authentication** - Use app passwords, not regular passwords
3. **Monitor notification emails** - Set up email filters to highlight ParseHub alerts
4. **Test after deployment** - Run Test 1 and Test 2 in new environments
5. **Error tracking** - Archive notification emails for audit trail
6. **Rate limiting** - SMTP can fail if sending too many emails rapidly

## Architecture

```
ChunkPaginationOrchestrator
    ├── trigger_batch_run()  ──┐
    ├── poll_run_completion()  ├──→ Error Detected
    ├── fetch_run_data()      ─┤    ║
    ├── store_batch_results() ─┤    ║
    └── run_scraping_batch_cycle()┘   ║
                                      ▼
                        EmailNotificationService
                                      │
                        ┌─────────────┼─────────────┐
                        ▼             ▼             ▼
                    SMTP Server   Error Log   [Optional] Slack
                        │
                        ▼
                  admin@company.com
```

## Files Modified

- `backend/src/services/notification_service.py` ✨ NEW
- `backend/src/services/chunk_pagination_orchestrator.py` (enhanced with email integration)
- `backend/src/config/.env.example` (SMTP config added)
- `config/.env.example` (SMTP config added)

---

## Questions?

For issues or feature requests:
1. Check logs: `tail -f logs/parsehub.log | grep EMAIL`
2. Verify configuration: Run Test 1 above
3. Test SMTP directly: Run Test 2 above
