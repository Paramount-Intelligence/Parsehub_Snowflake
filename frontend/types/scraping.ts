/**
 * Type definitions for metadata-driven resume scraping system
 * Replaces old batch/chunk-based types with metadata-driven concepts
 * 
 * Key changes:
 * - Checkpoint = highest_successful_page (not batch-based)
 * - Progress tracked by pages, not batches
 * - Database source_page field for reliable resume
 */

// ============= Metadata & Progress =============

export interface ProjectMetadata {
  project_id: number
  project_name: string
  /** Canonical listing URL for pagination (matches backend metadata.website_url) */
  website_url: string
  /** Alias for website_url — kept for older UI/tests */
  base_url: string
  total_pages: number
  total_products: number
  current_page_scraped: number
}

export interface ScrapingCheckpoint {
  highest_successful_page: number
  next_start_page: number
  total_persisted_records: number
  checkpoint_timestamp: string
  /** Set when API includes completion flag; otherwise derive from metadata + pages */
  is_project_complete?: boolean
}

export interface ProjectProgress {
  project_id: number
  project_name: string
  highest_successful_page: number
  next_start_page: number
  total_pages: number
  total_products: number
  total_persisted_records: number
  is_complete: boolean
  progress_percentage: number
  checkpoint: ScrapingCheckpoint
}

// ============= Scraping Session =============

export interface ScrapingSession {
  // Session Identifiers
  session_id?: string
  run_token?: string
  project_id: number
  project_token: string
  project_name: string
  
  // Metadata & Progress
  metadata: ProjectMetadata
  checkpoint: ScrapingCheckpoint
  
  // Status
  status: 'idle' | 'running' | 'completed' | 'failed' | 'error'
  is_complete: boolean
  
  // Timing
  started_at?: string
  last_updated: string
  completed_at?: string
  
  // Error Info (optional)
  last_error?: string
  error_type?: string
}

// ============= Run Data =============

export interface ScrapedRecord {
  id: number
  source_page: number  // Which website page this came from
  data: Record<string, any>
  created_at: string
}

export interface RunResult {
  success: boolean
  run_token?: string
  records_persisted: number
  highest_successful_page: number
  project_complete: boolean
  next_action: 'continue' | 'complete'  // What to do next
  message: string
}

// ============= API Requests =============

export interface StartScrapingRequest {
  project_token: string
  project_id?: number
}

export interface CompleteRunRequest {
  run_token: string
  project_id: number
  project_token: string
  starting_page_number: number
}

// ============= API Responses =============

export interface StartScrapingResponse {
  success: boolean
  project_complete: boolean
  run_token?: string
  highest_successful_page: number
  next_start_page: number
  total_pages: number
  total_persisted_records: number
  checkpoint: ScrapingCheckpoint
  message: string
  reason?: string
  error?: string
  error_type?: string
}

export interface CompleteRunResponse {
  success: boolean
  run_completed: boolean
  records_persisted: number
  highest_successful_page: number
  project_complete: boolean
  next_action: 'continue' | 'complete'
  message: string
  error?: string
}

// ============= UI State =============

export interface ScrapingUIState {
  isRunning: boolean
  isComplete: boolean
  hasError: boolean
  
  projectName: string
  projectToken: string
  
  // Progress info
  highestSuccessfulPage: number
  nextStartPage: number
  totalPages: number
  totalProducts: number
  totalPersistedRecords: number
  progressPercentage: number
  
  // Current run
  currentRunToken?: string
  
  // Error state
  lastError?: string
  errorType?: string
  
  // Timing
  lastUpdated?: Date
}

// ============= Monitoring =============

export interface MonitoringSession {
  sessionId: string
  projectToken: string
  projectName: string
  
  // Progress
  progress: ProjectProgress
  
  // Status
  status: 'running' | 'completed' | 'failed' | 'paused'
  isComplete: boolean
  
  // Timing
  startTime: string
  endTime?: string
  lastUpdated: string
  
  // Error
  lastError?: string
}

// ============= Runnable Actions =============

export interface ScrapingControl {
  // Start/Resume
  startOrResumeScraping: (projectToken: string, projectId?: number) => Promise<void>
  
  // Complete & Persist
  completeRunAndPersist: (
    runToken: string,
    projectId: number,
    projectToken: string,
    startingPage: number
  ) => Promise<void>
  
  // Status
  getProgress: (projectToken: string) => Promise<ProjectProgress>
  getCheckpoint: (projectToken: string) => Promise<ScrapingCheckpoint>
  
  // Error handling
  clearError: () => void
}

// ============= Analytics/Metrics =============

export interface ScrapingMetrics {
  total_pages_scraped: number
  total_records_persisted: number
  total_runs: number
  avg_records_per_page: number
  
  successful_pages: number
  failed_pages: number
  success_rate: number  // percentage
  
  highest_successful_page: number
  next_page_to_scrape: number
  pages_remaining: number
  
  project_complete: boolean
}

// ============= History =============

export interface RunHistoryRecord {
  run_token: string
  starting_page: number
  records_scraped: number
  status: 'success' | 'failed' | 'error'
  started_at: string
  completed_at?: string
  error_message?: string
}

export interface ProjectHistory {
  project_token: string
  project_name: string
  total_records_persisted: number
  highest_successful_page: number
  total_pages: number
  is_complete: boolean
  last_run: RunHistoryRecord
  all_runs: RunHistoryRecord[]
}

// ============= Error Handling =============

export interface ScrapingError {
  type: 'api' | 'timeout' | 'storage' | 'parse' | 'unknown'
  message: string
  page_number?: number
  run_token?: string
  timestamp: string
  recovery_action?: string  // e.g., "retry_page", "resume_from_checkpoint"
}

export type ScrapingErrorType = 
  | 'api_connection_error'
  | 'api_rate_limit'
  | 'missing_run_token'
  | 'run_cancelled'
  | 'run_failed'
  | 'polling_timeout'
  | 'data_fetch_failed'
  | 'storage_failed'
  | 'scraping_stalled'
  | 'fatal_exception'
  | 'unknown_error'
