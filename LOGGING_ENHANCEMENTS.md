# Logging Enhancements for Null-Handling Debugging

## Overview

Comprehensive logging has been added throughout the codebase to identify where None values are occurring and which code paths are being executed. This will help trace the root cause of the `'NoneType' object has no attribute 'strip'` error.

## Files Modified

### 1. backend/src/services/metadata_driven_resume_scraper.py

#### New Utility Functions:
- **`log_value(name, value, log_func=logger.debug)`** - Logs values with type information for debugging

#### Enhanced Methods:
- **`get_project_metadata(project_id)`**
  - Logs database result: `log_value("DATABASE_RESULT", result)`
  - Logs each metadata field individually with type
  - Logs raw values before safe_str() conversion
  - Logs final result dictionary

- **`get_checkpoint(project_id)`**
  - Logs checkpoint database result with type
  - Logs highest_page and total_records before and after normalization
  - Added detailed traceback logging on error

- **`generate_next_page_url(base_url, next_page, pagination_pattern)`**
  - Added SAFETY CHECKS for None/empty base_url
  - Logs base_url type before string operations
  - Logs detected/provided pagination pattern
  - Added TypeError/ValueError with detailed error messages

- **`_detect_pagination_pattern(url)`**
  - Added SAFETY CHECKS for None/empty url
  - Logs url with type information
  - Returns 'unknown' safely for None values
  - Prevents crash if url is not a string

- **`resume_or_start_scraping(project_id, project_token)` - Main Orchestration Method**
  - Logs website_url_raw and last_known_url_raw before safe_str()
  - Logs website_url_safe and last_known_url_safe after processing
  - Logs base_url type in resumed project path
  - Added try-catch around generate_next_page_url() call
  - **Enhanced exception handler:**
    - Logs FULL traceback
    - Searches traceback for ".strip()" calls
    - Identifies null-handling errors specifically
    - Logs all local variables at time of crash

- **`trigger_run(project_token, start_url, project_id, project_name, starting_page_number)`**
  - Added SAFETY CHECKS for start_url (None/empty/type validation)
  - Logs all parameters with type information
  - Logs TypeError/ValueError with detailed messages

### 2. backend/src/models/database.py

#### New Setup:
- Added `import logging`
- Added logger: `logger = logging.getLogger(__name__)`

#### Enhanced Methods:
- **`_link_projects_to_metadata()`**
  - Logs count of unlinked metadata records
  - Logs each metadata_id being processed
  - Logs project_name_raw with type before processing
  - Added try-catch with logging for safe_str equivalent operation
  - Logs project matches and link results
  - Enhanced error logging with traceback

- **`normalize_region(token)` (Inner function)**
  - Logs input token with type information
  - Logs when token is empty/None
  - Added try-catch with detailed error logging
  - Logs token type on error
  - Logs normalized result

### 3. backend/src/utils/url_generator.py

#### New Setup:
- Added `import logging`
- Added logger: `logger = logging.getLogger(__name__)`

#### Enhanced Methods:
- **`URLGenerator.detect_pattern(url)` (Static method)**
  - Added SAFETY CHECK for None/empty url
  - Added type validation for url parameter
  - Returns safe default if url is None
  - Logs url with type information
  - Logs detected pattern
  - Added comprehensive try-catch with error details

- **`URLGenerator.generate_next_url(url, next_page_number, pattern_info)` (Static method)**
  - Added SAFETY CHECKS for None/empty/type validation
  - Logs all parameters with truncation for long URLs
  - Added ValueError/TypeError with detailed messages
  - Logs each pattern matching attempt
  - Enhanced error handling with try-catch

## Log Format

All logs follow a consistent tagging format:

```
[TAG] Message content

Example:
[METADATA] {project_name}: {total_pages} pages
[CHECKPOINT] Project {id}: highest_page={page}, records={count}
[URL_GEN] Generating URL for page {page} from: {url}
[ERROR] Detailed error message with context
```

## What to Look For in Logs

When the error occurs, look for these key indicators:

1. **Null/None Detection:**
   ```log
   [LOG] website_url_raw = None (type: NoneType)
   [LOG] last_known_url_safe = '' (type: str)
   ```

2. **Type Mismatches:**
   ```log
   [LOG] base_url_type = dict (should be str!)
   [ERROR] base_url is not a string: dict
   ```

3. **Database Issues:**
   ```log
   [DATABASE_RESULT] None  # Metadata not found
   [METADATA_FIELD[website_url]] None  # Missing field
   ```

4. **Exact Crash Location:**
   ```log
   [ERROR] FULL TRACEBACK:
   ...
   [ERROR] FOUND .strip() CALL in traceback: File "path/to/file.py", line X, ...
   ```

5. **Local Variables at Crash:**
   ```log
   [ERROR] Local variables at time of crash:
   - project_id: 123
   - website_url: None  <-- FOUND IT!
   - checkpoint: {...}
   ```

## How to Enable Debug Logging

The logging will capture:
- `logger.debug()` - Detailed tracking of values
- `logger.info()` - Flow of execution with key checkpoints
- `logger.error()` - Errors with full context and tracebacks

To see all debug logs, configure logging in your application:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or configure specific logger:

```python
logging.getLogger('src.services.metadata_driven_resume_scraper').setLevel(logging.DEBUG)
logging.getLogger('src.models.database').setLevel(logging.DEBUG)
logging.getLogger('src.utils.url_generator').setLevel(logging.DEBUG)
```

## Next Steps

1. **Run the orchestration** that triggers the error
2. **Capture all logs** from the start to finish
3. **Look for:**
   - First occurrence of None value being logged
   - Which method logged it
   - What was the source (database, parameter, return value)
   - Trace back to root cause

4. **Once identified, specific fixes can be applied** to the exact location where None is coming from

## Safety Guards Added

All `.strip()` calls are now protected by:
1. Type checking: `isinstance(value, str)`
2. Null checking: `if not value:`
3. Try-catch with error logging
4. Alternative safe functions: `safe_str()` for metadata values

These guards will log detailed information about what went wrong instead of crashing silently.
