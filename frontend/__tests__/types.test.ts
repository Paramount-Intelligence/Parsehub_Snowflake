import { describe, it, expect } from 'vitest'
import type {
  ProjectMetadata,
  ScrapingCheckpoint,
  ProjectProgress,
  ScrapingSession,
  StartScrapingResponse,
  CompleteRunResponse,
  ScrapingUIState,
} from '../types/scraping'

describe('Type Definitions', () => {
  describe('ProjectMetadata', () => {
    it('should define project metadata structure', () => {
      const metadata: ProjectMetadata = {
        base_url: 'https://shop.com/items?page=1',
        total_pages: 50,
        total_products: 2500,
      }

      expect(metadata.base_url).toBeDefined()
      expect(metadata.total_pages).toBe(50)
      expect(metadata.total_products).toBe(2500)
    })

    it('should allow optional total_products', () => {
      const metadata: ProjectMetadata = {
        base_url: 'https://shop.com/items?page=1',
        total_pages: 100,
      }

      expect(metadata.total_products).toBeUndefined()
    })
  })

  describe('ScrapingCheckpoint', () => {
    it('should define checkpoint structure with page tracking', () => {
      const checkpoint: ScrapingCheckpoint = {
        highest_successful_page: 5,
        next_start_page: 6,
        total_persisted_records: 125,
        checkpoint_timestamp: '2024-03-26T14:30:00Z',
      }

      expect(checkpoint.highest_successful_page).toBe(5)
      expect(checkpoint.next_start_page).toBe(6)
      expect(checkpoint.total_persisted_records).toBe(125)
    })

    it('should ensure next_start_page is always highest + 1', () => {
      const checkpoint: ScrapingCheckpoint = {
        highest_successful_page: 10,
        next_start_page: 11,
        total_persisted_records: 500,
        checkpoint_timestamp: '2024-03-26T14:30:00Z',
      }

      expect(checkpoint.next_start_page).toBe(checkpoint.highest_successful_page + 1)
    })
  })

  describe('ProjectProgress', () => {
    it('should combine metadata with checkpoint and progress info', () => {
      const progress: ProjectProgress = {
        metadata: {
          base_url: 'https://shop.com/items?page=1',
          total_pages: 50,
          total_products: 2500,
        },
        checkpoint: {
          highest_successful_page: 5,
          next_start_page: 6,
          total_persisted_records: 125,
          checkpoint_timestamp: '2024-03-26T14:30:00Z',
        },
        is_complete: false,
        progress_percentage: 10,
      }

      expect(progress.progress_percentage).toBe(10)
      expect(progress.is_complete).toBe(false)
    })

    it('should show 100% progress when complete', () => {
      const progress: ProjectProgress = {
        metadata: {
          base_url: 'https://shop.com/items?page=1',
          total_pages: 50,
          total_products: 2500,
        },
        checkpoint: {
          highest_successful_page: 50,
          next_start_page: 51,
          total_persisted_records: 2500,
          checkpoint_timestamp: '2024-03-26T14:30:00Z',
        },
        is_complete: true,
        progress_percentage: 100,
      }

      expect(progress.progress_percentage).toBe(100)
      expect(progress.is_complete).toBe(true)
    })
  })

  describe('ScrapingUIState', () => {
    it('should define UI-friendly state for rendering', () => {
      const uiState: ScrapingUIState = {
        isRunning: true,
        isComplete: false,
        progressPercentage: 20,
        highestSuccessfulPage: 10,
        totalPages: 50,
        message: 'Scraping page 11...',
      }

      expect(uiState.isRunning).toBe(true)
      expect(uiState.progressPercentage).toBe(20)
      expect(uiState.message).toContain('page 11')
    })

    it('should reflect completion state', () => {
      const uiState: ScrapingUIState = {
        isRunning: false,
        isComplete: true,
        progressPercentage: 100,
        highestSuccessfulPage: 50,
        totalPages: 50,
        message: 'Scraping complete',
      }

      expect(uiState.isComplete).toBe(true)
      expect(uiState.isRunning).toBe(false)
    })
  })

  describe('StartScrapingResponse', () => {
    it('should represent API response from /resume/start', () => {
      const response: StartScrapingResponse = {
        success: true,
        project_complete: false,
        run_token: 'run_abc123',
        highest_successful_page: 0,
        next_start_page: 1,
        total_pages: 50,
        total_persisted_records: 0,
        checkpoint: {
          highest_successful_page: 0,
          next_start_page: 1,
          total_persisted_records: 0,
          checkpoint_timestamp: '2024-03-26T14:30:00Z',
        },
        message: 'Run started for page 1',
      }

      expect(response.success).toBe(true)
      expect(response.run_token).toBeDefined()
      expect(response.next_start_page).toBe(1)
    })

    it('should indicate project complete', () => {
      const response: StartScrapingResponse = {
        success: true,
        project_complete: true,
        message: 'Project scraping is complete',
        highest_successful_page: 50,
        total_pages: 50,
      }

      expect(response.project_complete).toBe(true)
      expect(response.run_token).toBeUndefined()
    })
  })

  describe('CompleteRunResponse', () => {
    it('should represent API response from /resume/complete-run', () => {
      const response: CompleteRunResponse = {
        success: true,
        run_completed: true,
        records_persisted: 25,
        highest_successful_page: 1,
        project_complete: false,
        next_action: 'continue',
        message: 'Page 1 completed: 25 records persisted',
      }

      expect(response.success).toBe(true)
      expect(response.records_persisted).toBe(25)
      expect(response.next_action).toBe('continue')
    })

    it('should indicate project completion after final page', () => {
      const response: CompleteRunResponse = {
        success: true,
        run_completed: true,
        records_persisted: 30,
        highest_successful_page: 50,
        project_complete: true,
        next_action: 'complete',
        message: 'Project scraping complete',
      }

      expect(response.project_complete).toBe(true)
      expect(response.next_action).toBe('complete')
    })
  })
})
