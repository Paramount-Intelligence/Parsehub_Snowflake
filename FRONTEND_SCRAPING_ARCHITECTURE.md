# Frontend Application Architecture - Scraping & Monitoring

## Overview
Complete mapping of all frontend files related to scraping operations, monitoring, progress tracking, batch processing, and API integration.

---

## 1. PAGE FILES (User Interface Entry Points)

### [frontend/app/page.tsx](frontend/app/page.tsx)
- **Purpose**: Main dashboard/home page
- **Scraping Features**:
  - Displays all projects with status indicators
  - Shows real-time statistics: total, running, completed, queued runs
  - Integrates `useRealTimeMonitoring` hook for live updates
  - Provides "Run Project" button to trigger scraping
  - Shows backend connectivity status with error handling
  - Contains `RunDialog` modal for configuring individual runs
  - Displays analytics and project cards

### [frontend/app/projects/page.tsx](frontend/app/projects/page.tsx)
- **Purpose**: Projects list and filtering page
- **Scraping Features**:
  - Lists all projects with metadata (region, country, brand)
  - Displays progress metrics: total_pages, current_page_scraped, last_run_date
  - Shows execution queue status
  - Provides project filtering by region, country, brand
  - 30-second auto-refresh for queue updates
  - Integration with batch run capabilities
  - Selection checkboxes for bulk operations
  - Sorting by name, date, or progress

### [frontend/app/projects/[token]/page.tsx](frontend/app/projects/%5Btoken%5D/page.tsx)
- **Purpose**: Individual project detail page
- **Scraping Features**:
  - Displays project metadata and URLs
  - Shows comprehensive run statistics (total_runs, completed_runs, active_runs, success_rate)
  - Last run details with status, pages, duration
  - "Start Scraping" button to initiate new runs
  - Scheduler button for scheduling future runs
  - Analytics visualization (performance, recovery status)
  - CSV data viewer for scraped results
  - Column statistics modal
  - Import history tracking

---

## 2. COMPONENT FILES (UI Components)

### Progress & Status Display Components

#### [frontend/components/RunProgress.tsx](frontend/components/RunProgress.tsx)
- **Purpose**: Real-time progress display for individual project runs
- **Features**:
  - Polls run status every 3 seconds
  - Displays: status, pages completed, current iteration
  - Auto-stops polling when run completes
  - Shows status icons: Activity, CheckCircle, Clock, AlertCircle
  - Props: projectToken, runToken, isActive, refreshInterval

#### [frontend/components/GroupRunProgress.tsx](frontend/components/GroupRunProgress.tsx)
- **Purpose**: Batch run progress modal showing results for multiple projects
- **Features**:
  - Displays results from batch operations
  - Shows success/failure status for each project
  - Shows run_token for each successful execution
  - Expandable error details with copy-to-clipboard functionality
  - Props: groupRunId, brand, isOpen, onClose, results
  - Tracks: total_projects, successful, failed counts

#### [frontend/components/ProgressModal.tsx](frontend/components/ProgressModal.tsx)
- **Purpose**: Incremental scraping progress tracking
- **Features**:
  - Displays session progress with live updates
  - Shows: total_pages_target, pages_completed, percentage, estimated_remaining_time
  - Lists individual runs with iteration, pages, records, status
  - Polls `/api/projects/incremental/progress` endpoint
  - Auto-refresh every 5 seconds
  - Auto-close on completion
  - Props: isOpen, onClose, sessionId, projectName

### Configuration & Input Components

#### [frontend/components/BatchRunConfigModal.tsx](frontend/components/BatchRunConfigModal.tsx)
- **Purpose**: Configuration UI for batch run execution
- **Features**:
  - Execution mode: sequential or parallel
  - Parallel settings: max_parallel (1-10)
  - Delay between runs: 1-60 seconds
  - Retry settings: on_failure, max_retries
  - Props: isOpen, onClose, onSubmit, projectCount

#### [frontend/components/RunDialog.tsx](frontend/components/RunDialog.tsx)
- **Purpose**: Modal to configure and start individual project runs
- **Features**:
  - Page count input (manual or from metadata)
  - Incremental scraping option with target page configuration
  - Auto-loads project metadata (total_pages)
  - Shows project info: token, title, URL
  - Displays warning about incremental vs. normal run
  - Calls `/api/projects/run` or `/api/projects/incremental` endpoint
  - Props: isOpen, onClose, projectToken, projectTitle, projectURL, onRunStart

#### [frontend/components/SchedulerModal.tsx](frontend/components/SchedulerModal.tsx)
- **Purpose**: Schedule scraping runs for future execution
- **Features**:
  - Schedule type: once (specific date/time) or recurring
  - Frequency options: daily, weekly, monthly
  - Day of week selection for weekly schedules
  - Page count specification
  - Validation and error handling
  - Calls `/api/projects/schedule` endpoint
  - Props: projectToken, onClose, onSchedule

#### [frontend/components/ScheduledRunsModal.tsx](frontend/components/ScheduledRunsModal.tsx)
- **Purpose**: View and manage scheduled scraping jobs
- **Features**:
  - Lists all scheduled runs with details
  - Polling every 3 seconds to detect new schedules
  - Delete scheduled jobs
  - Shows job_id, project_token, schedule type, frequency, pages
  - Displays created_at timestamp
  - Calls `/api/scheduled-runs` endpoint for fetch and delete
  - Props: isOpen, onClose

### Analytics & Data Visualization Components

#### [frontend/components/Analytics.tsx](frontend/components/Analytics.tsx)
- **Purpose**: Project analytics dashboard showing scraping performance
- **Features**:
  - Overview: total_runs, completed_runs, total_records_scraped, progress_percentage
  - Performance metrics: items_per_minute, estimated_total_items, average_run_duration
  - Recovery status: in_recovery flag, recovery_attempts count
  - Data quality metrics: average_completion_percentage, total_fields
  - Multi-tab interface: overview, performance, quality, recovery, statistics, data
  - 30-second auto-refresh
  - Calls `/api/analytics?token={projectToken}` endpoint
  - Props: projectToken

#### [frontend/components/AllProjectsAnalyticsModal.tsx](frontend/components/AllProjectsAnalyticsModal.tsx)
- **Purpose**: Aggregate analytics across multiple projects
- **Features**:
  - Summarizes all running/completed projects
  - Tabs: all, summary, progress
  - Tracks running projects separately
  - Fetches analytics for each project in parallel
  - Props: isOpen, onClose, projects

#### [frontend/components/DataViewer.tsx](frontend/components/DataViewer.tsx)
- **Purpose**: Display and paginate scraped data records
- **Features**:
  - Pagination: 10 items per page
  - Record detail expansion
  - Calls `/api/data?token={projectToken}` endpoint
  - Props: projectToken, projectId, refreshTrigger
  - Displays: data array with pagination controls

#### [frontend/components/DataModal.tsx](frontend/components/DataModal.tsx)
- **Purpose**: Modal to view scraped data from runs
- **Features**:
  - Lists runs with expand/collapse
  - Shows run metadata: status, pages, records_count, timestamps
  - Displays key-value data for each record
  - Copy and download functionality
  - Props: token, title, isOpen, onClose

#### [frontend/components/ProjectsList.tsx](frontend/components/ProjectsList.tsx)
- **Purpose**: Main project list with batch operations
- **Features**:
  - Groups projects by brand
  - Expandable brand sections
  - Page input for batch runs
  - Scheduler modal integration
  - Batch run config modal
  - Group progress tracking
  - Run individual or batch projects
  - Analytics per project
  - Statistics, CSV, and column stats modals
  - Props: projects[], onRunProject callback

---

## 3. API SERVICE FILES (Backend Integration)

### Library Files

#### [frontend/lib/apiClient.ts](frontend/lib/apiClient.ts)
- **Purpose**: Axios HTTP client for all API requests
- **Features**:
  - Same-origin requests to Next.js `/api/*` routes
  - Automatic inclusion of API key from `NEXT_PUBLIC_BACKEND_API_KEY`
  - 30-second timeout
  - Error handling for network errors
  - Response interceptor for user-friendly error messages
  - Handles both successful and error responses

#### [frontend/lib/api.ts](frontend/lib/api.ts)
- **Purpose**: High-level API wrapper functions
- **Functions**:
  - `fetchProjects()` - GET all projects
  - `runProject(token)` - POST to run single project
  - `runAllProjects()` - POST to run all projects
  - `getRunData(token, runToken)` - GET run details

#### [frontend/lib/apiBase.ts](frontend/lib/apiBase.ts)
- **Purpose**: API configuration and utility functions
- **Features**:
  - Frontend API URL resolution
  - API headers with authentication key
  - Used by both library code and server-side API routes

### Custom Hooks

#### [frontend/lib/useRealTimeMonitoring.ts](frontend/lib/useRealTimeMonitoring.ts)
- **Purpose**: Custom React hook for real-time scraping monitoring
- **Features**:
  - Continuous polling of run status (every 2 seconds)
  - Continuous polling of scraped data (every 3 seconds)
  - Tracks: sessionId, projectId, runToken, status, progress
  - Functions:
    - `startMonitoring(projectToken, runToken, pages)`
    - `stopMonitoring()`
    - `fetchMoreData()`
    - `refresh()`
    - `clearError()`
  - Returns: session, data, isMonitoring, error, statistics
  - Data pagination with offset management

---

## 4. API ROUTE FILES (Next.js Server-Side)

### Project Run APIs

#### [frontend/app/api/projects/route.ts](frontend/app/api/projects/route.ts)
- **Method**: GET, POST
- **Purpose**: Proxy to backend project listing and creation
- **Behavior**:
  - Forwards query parameters (page, limit, api_key)
  - Adds ParseHub API key server-side
  - Sets defaults: page=1, limit=50

#### [frontend/app/api/projects/run/route.ts](frontend/app/api/projects/run/route.ts)
- **Method**: POST
- **Purpose**: Start a single project scrape run
- **Behavior**:
  - Calls ParseHub API directly: `POST /projects/{token}/run`
  - Saves run token to `active_runs.json`
  - Returns: run_token, status
  - Handles API errors from ParseHub

#### [frontend/app/api/projects/run-all/route.ts](frontend/app/api/projects/run-all/route.ts)
- **Method**: POST
- **Purpose**: Start scraping all projects simultaneously
- **Behavior**:
  - Fetches all projects from ParseHub
  - Runs each project via POST calls
  - Collects results: token, success, run_token, error
  - Saves all run tokens to `active_runs.json`
  - Returns aggregate results with success/failure counts

### Batch Processing APIs

#### [frontend/app/api/projects/batch/run/route.ts](frontend/app/api/projects/batch/run/route.ts)
- **Method**: POST
- **Purpose**: Run multiple specific projects with configuration
- **Behavior**:
  - Body: `project_tokens[]` array
  - Sequential iteration through projects
  - Each project run via ParseHub API
  - Returns: array of results with token, success, run_token, error
  - Logs progress for each project (e.g., "[BATCH] [1/5] Running token:")

### Incremental Scraping APIs

#### [frontend/app/api/projects/incremental/route.ts](frontend/app/api/projects/incremental/route.ts)
- **Method**: POST
- **Purpose**: Start incremental (progressive pagination) scraping
- **Behavior**:
  - Input: projectToken, projectName, originalUrl, totalPages, pagesPerIteration
  - Executes Python backend script: `start_incremental_scraping.py`
  - Tracks session with sessionId
  - Returns: success, sessionId for progress tracking

#### [frontend/app/api/projects/incremental/progress/route.ts](frontend/app/api/projects/incremental/progress/route.ts)
- **Method**: GET
- **Purpose**: Get incremental scraping session progress
- **Behavior**:
  - Query param: `session_id`
  - Executes Python script: `get_session_progress.py`
  - Returns: pages_completed, total_pages, iterations, estimated_time_remaining
  - Runs every 5 seconds from frontend

### Pagination APIs

#### [frontend/app/api/projects/pagination/route.ts](frontend/app/api/projects/pagination/route.ts)
- **Method**: POST
- **Purpose**: Check pagination requirements and status
- **Behavior**:
  - Input: token, targetPages
  - Executes Python backend check
  - Returns: paginationStatus, needsRecovery, paginationDetails

### Recovery APIs

#### [frontend/app/api/projects/recovery/route.ts](frontend/app/api/projects/recovery/route.ts)
- **Method**: Unknown (route found but not fully read)
- **Purpose**: Handle recovery of failed scraping attempts

### Monitoring APIs

#### [frontend/app/api/monitor/start.ts](frontend/app/api/monitor/start.ts)
- **Method**: POST
- **Purpose**: Start real-time monitoring of a run
- **Behavior**:
  - Input: projectToken, runToken, pages
  - Calls backend: `POST /api/monitor/start`
  - Returns: sessionId, runToken, startedAt

#### [frontend/app/api/monitor/status.ts](frontend/app/api/monitor/status.ts)
- **Method**: GET
- **Purpose**: Get current monitoring/run status
- **Behavior**:
  - Query params: projectId OR sessionId
  - Proxies to backend: `GET /api/monitor/status`
  - Returns: session object with status, progress, metrics

#### [frontend/app/api/monitor/data.ts](frontend/app/api/monitor/data.ts)
- **Method**: GET
- **Purpose**: Get scraped data records for a monitoring session
- **Behavior**:
  - Query params: sessionId, limit (default 100), offset (default 0)
  - Proxies to backend: `GET /api/monitor/data`
  - Returns: records[], total count, pagination info

#### [frontend/app/api/monitor/stop.ts](frontend/app/api/monitor/stop.ts)
- **Method**: Unknown (route found but not fully read)
- **Purpose**: Stop monitoring a run session

### Scheduling APIs

#### [frontend/app/api/scheduled-runs/route.ts](frontend/app/api/scheduled-runs/route.ts)
- **Method**: GET, POST
- **Purpose**: Manage scheduled scraping jobs
- **Behavior**:
  - GET: Proxies to backend `GET /api/scheduled-runs` - lists all scheduled jobs
  - POST: Proxies to backend `POST /api/projects/schedule` - schedule new run
  - Also handles DELETE operations for canceling schedules

#### [frontend/app/api/scheduled-runs/[jobId]/route.ts](frontend/app/api/scheduled-runs/%5BjobId%5D/route.ts)
- **Method**: Unknown (route found but not fully read)
- **Purpose**: Individual scheduled job management (details, cancel, etc.)

### Analytics APIs

#### [frontend/app/api/analytics/route.ts](frontend/app/api/analytics/route.ts)
- **Method**: GET
- **Purpose**: Get comprehensive analytics for a project
- **Behavior**:
  - Query param: `token`
  - Parses CSV output from Python backend
  - Returns:
    - Overview: total_runs, completed_runs, total_records_scraped, progress_percentage
    - Performance: items_per_minute, estimated_total_items, average_run_duration
    - Recovery: in_recovery, status, recovery_attempts
    - Data quality: average_completion_percentage, total_fields
    - Timeline data for charting

#### [frontend/app/api/analytics/statistics/route.ts](frontend/app/api/analytics/statistics/route.ts)
- **Method**: Unknown (route found but not fully read)
- **Purpose**: Detailed statistics for analytics dashboard

### Data APIs

#### [frontend/app/api/data/route.ts](frontend/app/api/data/route.ts)
- **Method**: Unknown (route found but not fully read)
- **Purpose**: Fetch scraped data records

### Import History APIs

#### [frontend/app/api/import-history/route.ts](frontend/app/api/import-history/route.ts)
- **Method**: GET
- **Purpose**: Get batch import/scraping history
- **Behavior**:
  - Query params: limit (default 50), offset (default 0)
  - Proxies to backend: `GET /api/metadata/import-history`
  - Returns: count, batches with timestamps and details

### Runs APIs

#### [frontend/app/api/runs/[run_token]/route.ts](frontend/app/api/runs/%5Brun_token%5D/route.ts)
- **Method**: Unknown (route found but not fully read)
- **Purpose**: Get details for specific run by run_token

#### [frontend/app/api/runs/[run_token]/cancel/route.ts](frontend/app/api/runs/%5Brun_token%5D/cancel/route.ts)
- **Method**: Unknown (route found but not fully read)
- **Purpose**: Cancel an active run

### Proxy Utility

#### [frontend/app/api/_proxy.ts](frontend/app/api/_proxy.ts)
- **Purpose**: Central server-side proxy utility for all backend calls
- **Features**:
  - Forwards all requests to Flask backend
  - Timeout: 30 seconds
  - Retry logic for idempotent methods (GET, HEAD, DELETE) - max 3 attempts
  - No retry for unsafe methods (POST, PUT, PATCH)
  - Exponential backoff between retries
  - Handles 502, 503, 504 errors
  - Lazy backend URL resolution (prevents cold-start crashes)
  - Requires: BACKEND_API_URL or BACKEND_URL env var

---

## 5. TYPE DEFINITIONS & INTERFACES

### Key Interfaces (inferred from component props and state):

```typescript
// Run/Execution Related
interface RunProgressProps {
  projectToken: string
  runToken?: string
  isActive?: boolean
  refreshInterval?: number
}

interface BatchRunConfigModal {
  execution_mode: "sequential" | "parallel"
  max_parallel: number
  delay_seconds: number
  retry_on_failure: boolean
  max_retries: number
}

interface BatchResults {
  success: boolean
  total_projects: number
  successful: number
  failed: number
  results: BatchResult[]
}

interface BatchResult {
  token: string
  success: boolean
  run_token?: string
  status?: string
  error?: string
}

// Project/Metadata Related
interface Project {
  token: string
  title: string
  owner_email: string
  projecturl?: string
  main_site?: string
  last_run?: {
    status: string
    pages: number
    start_time: string
    run_token: string
  } | null
}

interface Metadata {
  id: number
  project_name: string
  region?: string
  country?: string
  brand?: string
  website_url?: string
  total_pages?: number
  total_products?: number
  current_page_scraped?: number
  current_product_scraped?: number
  last_run_date?: string
}

// Monitoring Related
interface MonitoringSession {
  sessionId: number
  projectId: number
  runToken: string
  targetPages: number
  status: 'active' | 'completed' | 'failed' | 'cancelled'
  totalPages: number
  totalRecords: number
  progressPercentage: number
  currentUrl?: string
  errorMessage?: string
  startTime: string
  endTime?: string
}

interface ScrapedRecord {
  id: number
  pageNumber: number
  data: Record<string, any>
  createdAt: string
}

// Scheduling Related
interface ScheduledRun {
  job_id: string
  project_token: string
  type: 'once' | 'recurring'
  scheduled_time?: string
  frequency?: 'daily' | 'weekly' | 'monthly'
  time?: string
  day_of_week?: string
  pages: number
  created_at: string
}

// Analytics Related
interface AnalyticsData {
  overview: {
    total_runs: number
    completed_runs: number
    total_records_scraped: number
    progress_percentage: number
  }
  performance: {
    items_per_minute: number
    estimated_total_items: number
    average_run_duration_seconds: number
    current_items_count: number
  }
  recovery: {
    in_recovery: boolean
    status: string
    total_recovery_attempts: number
  }
  data_quality: {
    average_completion_percentage: number
    total_fields: number
  }
  timeline: any[]
}
```

---

## 6. DATA FLOW SUMMARY

### Single Project Run Flow
1. User clicks "Run Project" → `RunDialog` modal opens
2. User enters page count → Calls `POST /api/projects/run`
3. Frontend API route calls ParseHub API directly
4. ParseHub returns `run_token`
5. Token saved to `active_runs.json`
6. `useRealTimeMonitoring` hook starts polling:
   - Status: `GET /api/monitor/status` every 2 seconds
   - Data: `GET /api/monitor/data` every 3 seconds
7. `RunProgress` component displays live updates
8. Auto-refresh stops when status === 'complete'

### Batch Project Run Flow
1. User selects multiple projects → `BatchRunConfigModal` opens
2. User configures: mode (sequential/parallel), delays, retries
3. Calls `POST /api/projects/batch/run` with `project_tokens[]`
4. Frontend API iterates through tokens, calls ParseHub for each
5. Returns aggregate results with success/failure counts
6. `GroupRunProgress` displays results per project
7. Each successful run can be further monitored individually

### Incremental Scraping Flow
1. User enables "Incremental" in `RunDialog`
2. Calls `POST /api/projects/incremental`
3. Backend Python script: `start_incremental_scraping.py` runs
4. Returns `sessionId` for progress tracking
5. `ProgressModal` shows progress:
   - Polls `GET /api/projects/incremental/progress?session_id={sessionId}` every 5 seconds
6. Displays: pages_completed, iterations, estimated_remaining_time
7. Auto-close on completion

### Scheduled Run Flow
1. User clicks scheduler icon → `SchedulerModal` opens
2. User sets schedule: once (date+time) or recurring (daily/weekly/monthly)
3. Calls `POST /api/projects/schedule`
4. `ScheduledRunsModal` polls `GET /api/scheduled-runs` every 3 seconds
5. Shows all scheduled jobs with details
6. User can delete job via endpoint

### Analytics Flow
1. User clicks "Analyze" → `Analytics` component loads
2. Calls `GET /api/analytics?token={projectToken}`
3. Backend returns comprehensive analytics object
4. Component renders tabs: overview, performance, quality, recovery, statistics, data
5. Auto-refreshes every 30 seconds

---

## 7. POLLING & REFRESH INTERVALS

| Component | Endpoint | Interval | Purpose |
|-----------|----------|----------|---------|
| RunProgress | /api/monitor/status | 3 seconds | Poll run status |
| Monitoring Hook | /api/monitor/status | 2 seconds | Poll run status (aggressive) |
| Monitoring Hook | /api/monitor/data | 3 seconds | Poll scraped records |
| ProgressModal | /api/projects/incremental/progress | 5 seconds | Incremental progress |
| ScheduledRunsModal | /api/scheduled-runs | 3 seconds | Detect new schedules |
| ProjectsPage | /api/metadata | 30 seconds | Refresh project list |
| Analytics | /api/analytics | 30 seconds | Refresh analytics |
| AllProjectsAnalytics | /api/analytics (per project) | Variable | Multi-project analytics |

---

## 8. ERROR HANDLING & RECOVERY

### Network Error Detection
- `apiClient` intercepts network errors (ECONNREFUSED, ENOTFOUND, ECONNABORTED)
- Returns user-friendly message: "Backend API is currently unreachable"
- Detects cold-start backend (502/503 errors): `isBackendDown()` function

### Validation Errors
- Missing required fields → HTTP 400
- Invalid token format → Skipped with error message in batch results
- Missing query parameters → HTTP 400 with specific requirement message

### Retry Logic
- Server-side proxy (`_proxy.ts`) retries idempotent requests (GET/HEAD/DELETE)
- Max 3 total attempts with exponential backoff
- Non-idempotent methods (POST/PUT/PATCH) never auto-retry

### User Feedback
- Error messages displayed in toasts/alerts
- Troubleshooting suggestions in error UI
- Retry buttons for user-triggered refresh
- Loading states with spinners during async operations

---

## 9. ENVIRONMENT VARIABLES REQUIRED

### Frontend (.env.local or Railway Variables)
- `NEXT_PUBLIC_BACKEND_API_KEY` - API key for backend authentication
- `BACKEND_API_URL` or `BACKEND_URL` - Flask backend URL (server-side only)
- `PARSEHUB_API_KEY` - ParseHub API key (server-side only)
- `PARSEHUB_BASE_URL` - ParseHub API base URL (default: https://www.parsehub.com/api/v2)

---

## 10. KEY FILES SUMMARY TABLE

| File | Type | Purpose | Key Features |
|------|------|---------|--------------|
| page.tsx | Page | Main dashboard | Project list, stats, real-time monitoring |
| projects/page.tsx | Page | Projects browser | Filtering, bulk operations, queue |
| projects/[token]/page.tsx | Page | Project details | Full analytics, run history, stats |
| RunProgress | Component | Progress display | Live polling, auto-refresh |
| GroupRunProgress | Component | Batch results | Multi-project status, expandable errors |
| ProgressModal | Component | Incremental progress | Session tracking, ETA |
| BatchRunConfigModal | Component | Batch config | Sequential/parallel, delays, retries |
| RunDialog | Component | Run setup | Page count, incremental option |
| Analytics | Component | Analytics dashboard | 6 tabs, live metrics, 30s refresh |
| ProjectsList | Component | Project list UI | Brand grouping, batch ops |
| useRealTimeMonitoring | Hook | Live monitoring | Dual polling (2s/3s), data pagination |
| apiClient | Library | HTTP client | Axios wrapper, auth, error handling |
| _proxy.ts | Utility | Backend proxy | Request forwarding, retries, timeout |
| /api/projects/run | Route | Single run | Direct ParseHub call, token save |
| /api/projects/batch/run | Route | Batch run | Multi-project execution |
| /api/projects/incremental | Route | Incremental scrape | Python script execution, session ID |
| /api/monitor/status | Route | Run status | Proxy to backend monitor |
| /api/monitor/data | Route | Scraped data | Pagination, offset management |
| /api/scheduled-runs | Route | Scheduling | List, create, delete schedules |
| /api/analytics | Route | Analytics | CSV parsing, multi-metric aggregation |

