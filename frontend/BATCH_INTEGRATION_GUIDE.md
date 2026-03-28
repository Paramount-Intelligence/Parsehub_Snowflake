## Frontend Batch Scraping Integration Guide

This guide documents the migration from incremental scraping to batch-based scraping in the frontend.

### New Infrastructure (Already Created)

#### 1. **Type System** - `lib/types/scraping.ts`
Comprehensive TypeScript types for batch scraping:
- `BatchCheckpoint` - Resume state (last_completed_page, next_start_page)
- `BatchProgress` - Current batch info (batch_number, status, records_in_batch)
- `ScrapingSession` - Full session tracking
- `MonitoringSession` - Polling state
- `ScrapingError` - Typed error states

#### 2. **API Service Layer** - `lib/scrapingApi.ts`
Batch operations:
- `startBatchScraping(projectToken, resumeFromCheckpoint)` - Start/resume
- `stopBatchScraping(runToken)` - Stop current scraping
- `retryFailedBatch(projectToken, batchNumber)` - Retry specific batch
- `getBatchStatus(runToken)` - Poll current batch status
- `getCheckpoint(projectToken)` - Get resumable state
- `getBatchRecords(runToken)` - Get records from current batch
- `getScrapingHistory(projectToken, limit)` - Batch history
- Utilities: formatBatchRange(), calculateBatchProgress(), getResumeMessage()

#### 3. **Monitoring Hook** - `lib/useBatchMonitoring.ts`
Real-time monitoring with checkpoint support:
- Polls status every 3 seconds
- Polls records every 5 seconds
- Auto-stops on completion or error
- Supports resume from checkpoint
- Batch retry capability
- Interfaces:
  - `UseBatchMonitoringState`
  - `UseBatchMonitoringControls`

#### 4. **UI Components** - `components/`

**BatchProgress.tsx**
- Display current batch (e.g., "Pages 1-10 of 100")
- Checkpoint progress bar
- Statistics grid (batches, records, last updated)
- Retry failed batch button
- Stalled detector (3+ consecutive empty batches)
- Error rendering

**BatchScrapingDialog.tsx**
- Start fresh vs. resume from checkpoint
- Shows checkpoint info when available
- URL management
- Email notification settings
- Integrates BatchProgress for inline status

**BatchHistory.tsx** (NEW)
- Checkpoint summary (last completed, next start, progress)
- Batch-by-batch history
- Expandable batch details
- Failed batch tracking
- Last updated timestamp

**BatchStatistics.tsx** (NEW)
- 4-stat grid (total batches, success rate, total records, last activity)
- Estimated completion info
- Performance summary
- Batch efficiency metrics

### Files That Need Updates

#### High Priority (Most Impact)

1. **components/RunDialog.tsx**
   - **Current**: Starts single runs or incremental scraping
   - **Change**: Replace with BatchScrapingDialog imports or add batch mode option
   - **Impact**: Main scraping entry point for users

2. **components/RunProgress.tsx**
   - **Current**: Displays incremental progress (pages_scraped / pages_to_scrape)
   - **Change**: Replace with BatchProgress component
   - **Impact**: Real-time progress display on dashboard/project pages

3. **lib/useRealTimeMonitoring.ts**
   - **Current**: Polls /api/monitor/* endpoints for incremental sessions
   - **Change**: Archive and replace with useBatchMonitoring
   - **Impact**: Core polling mechanism

#### Medium Priority (Important Features)

4. **components/Analytics.tsx**
   - **Current**: 6-tab dashboard with incremental metrics
   - **Change**: Update stat calculations from pages-based to batch/checkpoint-based
   - **New Metrics**: 
     - Replace pages_scraped with checkpoint_progress
     - Replace avg_rate with records_per_batch
     - Add batch count statistics
   - **Impact**: Analytics data display accuracy

5. **app/page.tsx (Dashboard)**
   - **Current**: Uses useRealTimeMonitoring hook
   - **Change**: Switch monitoring to useBatchMonitoring
   - **Change**: Add BatchStatistics component for overview
   - **Change**: Update stat cards language (pages → batches, if applicable)
   - **Impact**: Main dashboard view

6. **app/projects/[token]/page.tsx (Project Detail)**
   - **Current**: Shows project details with incremental progress
   - **Change**: Integrate BatchProgress and BatchHistory components
   - **Change**: Update monitoring hook reference
   - **Impact**: Individual project monitoring page

#### Lower Priority (Polish/Completeness)

7. **components/DataViewer.tsx & DataModal.tsx**
   - **Current**: Displays scraped records
   - **Change**: Add source_page field awareness for batch deduplication
   - **New Field**: Show which batch/page each record came from
   - **Impact**: Data display clarity

8. **components/GroupRunProgress.tsx**
   - **Current**: Batch results modal (already batch-aware, but uses old terminology)
   - **Change**: Update copy "incremental" → "batch", terminology alignment
   - **Impact**: Minor UI text updates

9. **components/ProgressModal.tsx**
   - **Current**: Incremental session tracking with ETA calculation
   - **Decision**: Retire (batch model doesn't require session ETA)
   - **Alternative**: Archive instead of delete for reference

### Migration Strategy

#### Phase 1: Core Infrastructure (COMPLETE ✅)
- ✅ Created types/scraping.ts
- ✅ Created lib/scrapingApi.ts
- ✅ Created lib/useBatchMonitoring.ts
- ✅ Created components/BatchProgress.tsx
- ✅ Created components/BatchScrapingDialog.tsx
- ✅ Created components/BatchHistory.tsx
- ✅ Created components/BatchStatistics.tsx

#### Phase 2: Component Integration (NEXT)
1. Replace RunDialog with BatchScrapingDialog in page references
2. Replace RunProgress with BatchProgress in display logic
3. Update lib usage in all components
4. Update error handling for new ScrapingError types

#### Phase 3: Hook Replacement
1. Update app/page.tsx to use useBatchMonitoring
2. Update app/projects/[token]/page.tsx to use useBatchMonitoring
3. Archive useRealTimeMonitoring (keep for reference)
4. Update any other hook usages

#### Phase 4: Analytics & Metrics
1. Update Analytics.tsx calculations
2. Update status displays to show batch info
3. Update stat cards with checkpoint metrics
4. Add BatchStatistics component to dashboard

#### Phase 5: Polish & Testing
1. Update terminology throughout UI
2. Handle new error types
3. Test end-to-end workflows
4. Retire old components (ProgressModal, RunProgress)

### API Route Mapping

#### Old Incremental Routes (Being Replaced)
```
POST   /api/projects/incremental     → Start incremental scraping
GET    /api/monitor/start             → Get monitoring session
GET    /api/monitor/status            → Poll incremental status
GET    /api/monitor/data              → Get incremental data
POST   /api/monitor/stop              → Stop incremental
```

#### New Batch Routes (New Backend API)
```
POST   /api/projects/batch/start      → Start batch scraping (or resume)
GET    /api/projects/batch/status     → Poll batch status
GET    /api/projects/batch/records    → Get batch records
POST   /api/projects/batch/retry      → Retry failed batch
POST   /api/projects/batch/stop       → Stop scraping
GET    /api/projects/batch/checkpoint → Get resumable state
GET    /api/projects/batch/history    → Get batch history
GET    /api/projects/batch/statistics → Get batch stats
```

### Type Migration Examples

#### Before (Incremental)
```typescript
// Old incremental tracking
const session = await apiClient.get(`/api/monitor/start?run_token=${runToken}`)
// Result: { pages_scraped: 45, pages_to_scrape: 100, estimated_completion: "2h 15m" }
```

#### After (Batch)
```typescript
// New batch tracking (via scrapingApi)
const checkpoint = await getCheckpoint(projectToken)
// Result: { 
//   last_completed_page: 40, 
//   next_start_page: 41,
//   total_batches_completed: 4,
//   total_pages: 100
// }

const status = await getBatchStatus(runToken)
// Result: {
//   batch_number: 5,
//   batch_range: "41-50",
//   status: "scraping",
//   records_in_batch: 32,
//   error: null
// }
```

### Error Handling Updates

New ScrapingError types to handle:
```typescript
enum ScrapingErrorType {
  API_FAILURE = 'api_failure',
  NETWORK_ERROR = 'network_error',
  RATE_LIMITED = 'rate_limited',
  RUN_CANCELLED = 'run_cancelled',
  POLLING_TIMEOUT = 'polling_timeout',
  STALLED = 'stalled',
  CHECKPOINT_NOT_FOUND = 'checkpoint_not_found',
}
```

Update error displays to show human-readable messages:
- `api_failure` → "ParseHub API returned an error. Email notification sent."
- `stalled` → "No data received for 3+ batches. Resumable from checkpoint."
- `rate_limited` → "Temporarily rate limited. Will retry automatically."

### Testing Checklist

Before marking integration complete:
- [ ] Start fresh batch scraping
- [ ] Resume from checkpoint
- [ ] Retry failed batch
- [ ] Monitor real-time progress
- [ ] Handle network errors gracefully
- [ ] Verify email notifications sent on failure
- [ ] Test stop/cancel during scraping
- [ ] Verify batch history displays correctly
- [ ] Check analytics show batch metrics
- [ ] Confirm old incremental UI hidden/replaced

### Rollback Plan

If issues arise:
1. Keep old components archived (RunProgress.tsx, RunDialog.tsx, useRealTimeMonitoring.ts)
2. Keep old API routes functional on backend
3. Can revert components individually
4. Gradual rollout per-component recommended

### Known Limitations

1. Batch mode only (no single-run mode in new components)
   - Solution: SingleRunDialog for single-run workflows if needed

2. No ETA calculation (batch size variable)
   - Solution: Show estimated remaining batches instead

3. Email notifications only on failure
   - Enhancement: Add email on completion option

### Performance Notes

- Status polling: 3 seconds (down from previous intervals)
- Record polling: 5 seconds
- Checkpoint updates: Real-time on batch completion
- History queries: Configurable limit (default 20 batches)
- Stats refresh: 30 seconds (analytics dashboard)

### Questions & Support

For issues with batch scraping integration:
1. Check BatchProgress component for display issues
2. Verify getBatchStatus returns expected schema
3. Confirm checkpoint endpoint accessible
4. Check email notifications for API failure details
5. Review useRealTimeMonitoring vs useBatchMonitoring differences
