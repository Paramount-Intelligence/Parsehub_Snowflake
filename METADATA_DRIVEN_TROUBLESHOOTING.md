# Metadata-Driven Resume Scraping - Troubleshooting Guide

**Date:** March 26, 2026  
**Status:** Quick diagnostic guide for common issues

---

## 🔍 Quick Diagnostics

### Symptom: "Failed to load metadata" or 404 Error

**What to check:**

1. **Backend is running?**
   ```bash
   curl http://localhost:5000/api/health
   # Should return: {"service":"parsehub-backend","status":"ok"}
   ```

2. **Project exists in database?**
   ```bash
   # Browser console (F12):
   console.log('Project Token:', projectToken);
   
   # Then test endpoint:
   curl http://localhost:5000/api/projects/YOUR_TOKEN/resume/metadata
   # Should NOT return 404
   ```

3. **Was migration applied?**
   ```bash
   cd backend
   python -m migrations.migrate_source_page_tracking
   # Look for: "✓ Migration completed successfully"
   ```

---

## 🛠️ Common Issues & Solutions

### Issue 1: Metadata Takes 10+ Seconds to Load

**Symptoms:**
- "Loading project info..." spinner stuck
- Times out after 60 seconds
- Browser becomes unresponsive

**Solutions:**

**A) Restart Backend Fresh**
```bash
# Kill all Python processes in Task Manager
# Then delete cache and restart:
cd backend
rm -rf __pycache__
python -m src.api.api_server
```

**B) Check Database Connection**
```bash
# Look for these messages in backend logs:
# ✓ [DEBUG] Database connected
# ✓ [DEBUG] Query took: X ms

# If "took: 5000+ ms" = slow queries
```

**C) Check Snowflake Connection**
```bash
# Test your database:
# SQL (Snowflake):
SELECT COUNT(*) FROM metadata;
SELECT COUNT(*) FROM scraped_records;
# Should return quickly (<2 seconds)
```

---

### Issue 2: "Failed to start scraping" Button Error

**Symptoms:**
- Metadata loads fine
- Click "Start Scraping"
- Red error appears
- No progress modal shown

**Solutions:**

**A) Check Backend Logs**
```bash
# Look for ERROR messages when you click "Start"
# Common errors:
# - "Project not found"
# - "Unable to connect to database"
# - "ParseHub API error"
# - "Invalid configuration"
```

**B) Test Endpoint Directly**
```bash
curl -X POST http://localhost:5000/api/projects/resume/start \
  -H "Content-Type: application/json" \
  -d '{"project_token":"tXXXXXXXXXXX"}'

# Should return JSON with "success": true
```

**C) Verify Project Token Format**
```bash
# Get a real token from the frontend:
# Open browser DevTools → Network tab
# Look at the URL when you click a project
# Copy the token and test it
```

---

### Issue 3: Backend Unreachable

**Symptoms:**
- Error: "Backend API is unreachable"
- "Make sure backend server is running on port 5000"

**Solutions:**

**A) Start Backend**
```bash
cd backend
python -m src.api.api_server
# Should show:
# ✓ [INFO] App starting on http://localhost:5000
# ✓ [DEBUG] Database connected
```

**B) Check Port is Free**
```powershell
# Windows:
netstat -ano | findstr :5000
# If shows a PID, kill it:
taskkill /PID <PID> /F
```

**C) Verify Frontend is Pointing to Right Backend**
```typescript
// frontend/lib/apiClient.ts should have:
timeout: 60_000  // Increased from 30_000
```

---

## 📊 Verification Checklist

After any fix, verify each step:

- [ ] `curl http://localhost:5000/api/health` → `{"status":"ok"}`
- [ ] Backend logs show: `[DEBUG] Database connected`
- [ ] Can access `http://localhost:3000` in browser
- [ ] Click a project → RunDialog opens
- [ ] Metadata displays (total_pages, base_url visible)
- [ ] Click "Start Scraping" → No error
- [ ] Progress modal appears
- [ ] Progress modal shows: data scraped, pages remaining, next URL

---

## 🎯 Debug Mode

### Enable Verbose Logging

**Backend:**
```bash
# Edit backend/src/api/api_server.py:
import logging
logging.basicConfig(level=logging.DEBUG)  # Changed from WARNING

# Restart and watch for [DEBUG] messages
python -m src.api.api_server 2>&1 | tee backend.log
```

**Frontend:**
```typescript
// Add to frontend/lib/apiClient.ts:
apiClient.interceptors.request.use(
  (config) => {
    console.log('[API] Request:', config.method?.toUpperCase(), config.url);
    return config;
  }
);

apiClient.interceptors.response.use(
  (response) => {
    console.log('[API] Response:', response.status, response.config.url);
    return response;
  }
);
```

---

## 🚀 Performance Optimization

### If Everything Works But Slow

**1. Database Indexes**
```sql
-- Snowflake:
CREATE INDEX idx_metadata_project_token ON metadata(project_token);
CREATE INDEX idx_scraped_records_project_page ON scraped_records(project_id, source_page);
SHOW INDEXES FROM metadata;
```

**2. Connection Pool**
```python
# backend/src/models/database.py
# Add before creating connection:
pool_size=5
max_overflow=10
```

**3. Metadata Caching**
```python
# Cache results for 5 minutes
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=100)
def get_cached_metadata(project_token):
    # Returns cached if < 5 min old
    pass
```

---

## 📁 File Locations

**When you see errors, check these files:**

| Error | File to Check |
|-------|---------------|
| "Failed to load metadata" | `frontend/components/RunDialog.tsx` line 50 |
| "Failed to start scraping" | `frontend/components/RunDialog.tsx` line 75 |
| 404 on metadata endpoint | `backend/src/api/resume_routes.py` line 185 |
| Backend not responding | `backend/src/api/api_server.py` (check if running) |
| Timeout errors | `frontend/lib/apiClient.ts` line 13 (check timeout setting) |

---

## ✅ Success Indicators

You know it's working when:

1. **Backend Logs Show:**
   ```
   [DEBUG] Database connected
   [INFO] App starting on http://localhost:5000
   ```

2. **Frontend Loads Metadata Quickly**
   - Metadata visible within 2 seconds
   - No spinner stuck

3. **Click "Start Scraping" Works**
   - No red error
   - Progress modal appears immediately
   - Shows: "Page 1 of X" with progress bar

4. **Progress Modal Shows All Details**
   - ✓ Data scraped counter
   - ✓ Pages remaining counter
   - ✓ Next URL to scrape
   - ✓ "If you stop now" info

---

## 📞 Still Stuck?

**Collect this info:**

1. Backend logs (last 100 lines):
   ```bash
   tail -100 backend.log
   ```

2. Browser Network tab screenshots:
   - Show failed request
   - Copy response body

3. Your project token and total_pages

4. Run these commands and share output:
   ```bash
   curl -s http://localhost:5000/api/health | jq .
   curl -s http://localhost:5000/api/metadata | jq '.metadata | length'
   ```

---

**Last Updated:** March 26, 2026  
**Created for:** Debugging metadata-driven system issues

For comprehensive guide, see: `README_METADATA_DRIVEN_SYSTEM.md`
