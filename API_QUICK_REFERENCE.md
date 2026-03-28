# API Quick Reference

**Metadata-Driven Resume Scraping System - API Reference**

---

## Authentication

No authentication required for this version. For production, add:
```bash
Authorization: Bearer YOUR_API_KEY
```

---

## 1. Start or Resume Scraping

### Endpoint
```
POST /api/projects/resume/start
```

### Purpose
Mark project as ready to scrape. If resuming, skips already-scraped pages.

### Request
```json
{
  "project_token": "tXXXXXXXXXXXXXXXXXXXXXX",
  "project_id": 123
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| project_token | string | ✅ Yes | ParseHub project token |
| project_id | integer | ✅ Yes | Your internal project ID |

### Response - New Run

```json
{
  "success": true,
  "project_complete": false,
  "run_token": "run_abc123def456...",
  "highest_successful_page": 0,
  "next_start_page": 1,
  "total_pages": 50,
  "total_persisted_records": 0,
  "checkpoint": {
    "highest_successful_page": 0,
    "next_start_page": 1,
    "total_persisted_records": 0,
    "checkpoint_timestamp": "2024-03-26T14:15:30.123456Z"
  },
  "message": "Run started for page 1"
}
```

### Response - Resuming

```json
{
  "success": true,
  "project_complete": false,
  "run_token": "run_xyz789...",
  "highest_successful_page": 5,
  "next_start_page": 6,
  "total_pages": 50,
  "total_persisted_records": 125,
  "message": "Run started for page 6 (resuming from checkpoint)"
}
```

### Response - Already Complete

```json
{
  "success": true,
  "project_complete": true,
  "message": "Project scraping is complete",
  "reason": "Primary: highest_page (50) >= total_pages (50)",
  "highest_successful_page": 50,
  "total_pages": 50
}
```

### HTTP Status Codes
- **201** - New run created successfully
- **200** - Already complete or resuming
- **400** - Missing required fields
- **404** - Project/metadata not found
- **500** - Server error

### Curl Example
```bash
curl -X POST http://localhost:5000/api/projects/resume/start \
  -H "Content-Type: application/json" \
  -d '{
    "project_token": "tXXXXXXXXXXXXXXXXXXXXXX",
    "project_id": 123
  }'
```

---

## 2. Get Checkpoint

### Endpoint
```
GET /api/projects/<project_token>/resume/checkpoint
```

### Purpose
Get current scraping status without starting a new run.

### Parameters
| Param | Type | Notes |
|-------|------|-------|
| project_token | string (URL) | ParseHub project token |

### Response
```json
{
  "success": true,
  "checkpoint": {
    "highest_successful_page": 5,
    "next_start_page": 6,
    "total_persisted_records": 125,
    "checkpoint_timestamp": "2024-03-26T15:30:45.123456Z"
  },
  "total_pages": 50,
  "progress_percentage": 10
}
```

### HTTP Status Codes
- **200** - Success
- **404** - Project token not found
- **500** - Server error

### Curl Example
```bash
curl http://localhost:5000/api/projects/tXXXXXXXXXXXXXXXXXXXXXX/resume/checkpoint
```

---

## 3. Get Project Progress

### Endpoint
```
GET /api/projects/<project_token>/resume/metadata
```

### Purpose
Get complete project status: metadata + checkpoint + progress.

### Parameters
| Param | Type | Notes |
|-------|------|-------|
| project_token | string (URL) | ParseHub project token |

### Response
```json
{
  "success": true,
  "project_id": 123,
  "project_name": "E-commerce Store",
  "project_metadata": {
    "base_url": "https://store.com/products?page=1",
    "total_pages": 50,
    "total_products": 2500
  },
  "checkpoint": {
    "highest_successful_page": 5,
    "next_start_page": 6,
    "total_persisted_records": 125,
    "checkpoint_timestamp": "2024-03-26T15:30:45.123456Z"
  },
  "is_complete": false,
  "progress_percentage": 10,
  "current_page_scraped": 5
}
```

### HTTP Status Codes
- **200** - Success
- **404** - Project token not found
- **500** - Server error

### Curl Example
```bash
curl http://localhost:5000/api/projects/tXXXXXXXXXXXXXXXXXXXXXX/resume/metadata
```

---

## 4. Complete Run & Persist

### Endpoint
```
POST /api/projects/resume/complete-run
```

### Purpose
Finalize a scraping run: get data from ParseHub, persist to database, check completion.

### Request
```json
{
  "run_token": "run_abc123def456...",
  "project_id": 123,
  "project_token": "tXXXXXXXXXXXXXXXXXXXXXX",
  "starting_page_number": 1
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| run_token | string | ✅ Yes | From `/resume/start` response |
| project_id | integer | ✅ Yes | Your internal project ID |
| project_token | string | ✅ Yes | ParseHub project token |
| starting_page_number | integer | ✅ Yes | Which page this run scraped (1, 2, 3, etc.) |

### Response - Success, Continue Scraping

```json
{
  "success": true,
  "run_completed": true,
  "records_persisted": 25,
  "highest_successful_page": 1,
  "project_complete": false,
  "next_action": "continue",
  "message": "Page 1 completed: 25 records persisted. Ready to scrape page 2."
}
```

### Response - Complete

```json
{
  "success": true,
  "run_completed": true,
  "records_persisted": 30,
  "highest_successful_page": 50,
  "project_complete": true,
  "next_action": "complete",
  "message": "Project scraping complete: all 50 pages processed, 1250 total records."
}
```

### Response - Error

```json
{
  "success": false,
  "error": "run_timeout",
  "error_details": "ParseHub run did not complete within 30 minutes",
  "run_completed": false,
  "project_complete": false,
  "next_action": "retry"
}
```

### HTTP Status Codes
- **200** - Run completed and results persisted
- **202** - Run still processing (try again later)
- **400** - Invalid request
- **404** - Run token not found
- **500** - Server error

### Curl Example
```bash
curl -X POST http://localhost:5000/api/projects/resume/complete-run \
  -H "Content-Type: application/json" \
  -d '{
    "run_token": "run_abc123def456...",
    "project_id": 123,
    "project_token": "tXXXXXXXXXXXXXXXXXXXXXX",
    "starting_page_number": 1
  }'
```

---

## API Workflow

### Scenario 1: First-Time Scrape

```
1. POST /resume/start
   → Returns: run_token, next_start_page=1, project_complete=false

2. [Wait for ParseHub to complete - 2-10 minutes]

3. POST /resume/complete-run
   → Returns: records_persisted=25, highest_page=1, next_action="continue"

4. [Loop: Repeat steps 1-3 until next_action="complete"]

5. Final POST /resume/complete-run
   → Returns: project_complete=true, next_action="complete"
```

### Scenario 2: Resume After Interruption

```
1. GET /resume/metadata
   → Returns: highest_page=5, next_start_page=6, progress=10%

2. POST /resume/start
   → Automatically skips pages 1-5, starts page 6
   → Returns: run_token, next_start_page=6

3. [Continue as Scenario 1]
```

### Scenario 3: Check Status Without Action

```
1. GET /resume/metadata
   → Returns: progress, checkpoint, is_complete flag
   → No side effects, safe to call frequently
```

---

## Error Responses

### Common Error Codes

| Code | Meaning | Likely Cause | Solution |
|------|---------|--------------|----------|
| `invalid_token` | ParseHub token invalid | Wrong token or revoked | Check token in dashboard |
| `project_not_found` | No metadata for project_id | Not created yet | Create metadata record first |
| `metadata_incomplete` | Missing required fields | Bad metadata record | Ensure base_url and total_pages set |
| `run_timeout` | ParseHub didn't finish in 30 min | Large dataset or network issue | Try again, or increase pages |
| `run_failed` | ParseHub job failed | Website blocked/changed | Check ParseHub dashboard |
| `persistence_failed` | Couldn't save to database | DB connection lost | Check database status |
| `url_generation_failed` | Couldn't generate next URL | Invalid base_url format | Check base_url has `?page=1` |

### Error Response Format

```json
{
  "success": false,
  "error": "error_code_here",
  "error_details": "Human-readable explanation",
  "troubleshooting_steps": [
    "Step 1 to fix",
    "Step 2 to fix"
  ]
}
```

---

## Rate Limiting

- **No rate limit per API call**
- **ParseHub API:** 20 requests/minute per API key
  - Respect ParseHub limits or calls will fail with 429 status
  - See ParseHub documentation for details

---

## Data Types

### ScrapingCheckpoint
```json
{
  "highest_successful_page": 5,     // integer: highest page scraped so far
  "next_start_page": 6,              // integer: next page to scrape
  "total_persisted_records": 125,    // integer: total records in database
  "checkpoint_timestamp": "2024-03-26T15:30:45.123456Z"  // ISO 8601 timestamp
}
```

### ProjectMetadata
```json
{
  "project_id": 123,                 // integer: your internal ID
  "project_name": "Shop Name",       // string: display name
  "base_url": "https://...?page=1",  // string: starting URL
  "total_pages": 50,                 // integer: expected pages
  "total_products": 2500,            // integer: expected products (optional)
  "current_page_scraped": 5          // integer: highest page completed
}
```

### RunResponse
```json
{
  "run_token": "run_abc123...",      // string: unique run ID from ParseHub
  "status": "completed",             // string: completed, running, failed
  "data_count": 25,                  // integer: items scraped
  "error": null                      // string or null: error message if failed
}
```

---

## Implementation Examples

### Python (Requests)

```python
import requests
import time

BASE_URL = "http://localhost:5000/api"
PROJECT_TOKEN = "tXXXXXXXXXXXXXXXXXXXXXX"
PROJECT_ID = 123

# Start scraping
response = requests.post(
    f"{BASE_URL}/projects/resume/start",
    json={"project_token": PROJECT_TOKEN, "project_id": PROJECT_ID}
)
data = response.json()
run_token = data["run_token"]
starting_page = data["next_start_page"]

# Wait for ParseHub to complete
time.sleep(60)  # Actually implement proper polling

# Complete and persist
response = requests.post(
    f"{BASE_URL}/projects/resume/complete-run",
    json={
        "run_token": run_token,
        "project_id": PROJECT_ID,
        "project_token": PROJECT_TOKEN,
        "starting_page_number": starting_page
    }
)
print(response.json())
```

### JavaScript/TypeScript

```typescript
const BASE_URL = "http://localhost:5000/api";
const PROJECT_TOKEN = "tXXXXXXXXXXXXXXXXXXXXXX";
const PROJECT_ID = 123;

// Start scraping
const startResponse = await fetch(`${BASE_URL}/projects/resume/start`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ 
    project_token: PROJECT_TOKEN, 
    project_id: PROJECT_ID 
  })
});

const startData = await startResponse.json();
const runToken = startData.run_token;
const startingPage = startData.next_start_page;

// Wait for ParseHub
await new Promise(resolve => setTimeout(resolve, 60000));

// Complete and persist
const completeResponse = await fetch(`${BASE_URL}/projects/resume/complete-run`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    run_token: runToken,
    project_id: PROJECT_ID,
    project_token: PROJECT_TOKEN,
    starting_page_number: startingPage
  })
});

const completeData = await completeResponse.json();
console.log(completeData);
```

### cURL

```bash
#!/bin/bash

BASE_URL="http://localhost:5000/api"
PROJECT_TOKEN="tXXXXXXXXXXXXXXXXXXXXXX"
PROJECT_ID=123

# Start
START_RESPONSE=$(curl -s -X POST "$BASE_URL/projects/resume/start" \
  -H "Content-Type: application/json" \
  -d "{\"project_token\": \"$PROJECT_TOKEN\", \"project_id\": $PROJECT_ID}")

RUN_TOKEN=$(echo $START_RESPONSE | jq -r '.run_token')
STARTING_PAGE=$(echo $START_RESPONSE | jq -r '.next_start_page')

echo "Started run: $RUN_TOKEN (page $STARTING_PAGE)"

# Wait
sleep 60

# Complete
curl -s -X POST "$BASE_URL/projects/resume/complete-run" \
  -H "Content-Type: application/json" \
  -d "{
    \"run_token\": \"$RUN_TOKEN\",
    \"project_id\": $PROJECT_ID,
    \"project_token\": \"$PROJECT_TOKEN\",
    \"starting_page_number\": $STARTING_PAGE
  }" | jq .
```

---

## Testing Endpoints

### Health Check
```bash
curl http://localhost:5000/api/health
# Response: {"status": "ok"}
```

### API Info
```bash
curl http://localhost:5000/api/info
# Response: {"version": "2.0", "system": "metadata-driven-resume"}
```

---

## Migration from Old API

### Old Endpoint → New Endpoint

| Old | New | Notes |
|-----|-----|-------|
| `POST /batch/start` | `POST /resume/start` | Same payload structure |
| `GET /batch/status/<token>` | `GET /resume/metadata/<token>` | Response structure changed |
| `POST /batch/complete` | `POST /resume/complete-run` | New endpoint |

### Response Structure Changes

**Old batch/status response:**
```json
{
  "batch_number": 1,
  "batch_range": "1-10",
  "status": "running",
  "records_processed": 50
}
```

**New resume/metadata response:**
```json
{
  "highest_successful_page": 1,
  "next_start_page": 2,
  "total_persisted_records": 50,
  "progress_percentage": 2,
  "is_complete": false
}
```

---

## Support

- **Documentation:** See [README_METADATA_DRIVEN_SYSTEM.md](README_METADATA_DRIVEN_SYSTEM.md)
- **Testing:** See [MANUAL_TESTING_GUIDE.md](MANUAL_TESTING_GUIDE.md)
- **Deployment:** See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

---

**Version:** 2.0 | **Last Updated:** March 26, 2026
