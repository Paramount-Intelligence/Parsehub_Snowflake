import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  startOrResumeScraping,
  completeRunAndPersist,
  getProjectProgress,
  getCheckpoint,
  getProjectMetadata,
  startBatchScrapingLegacy,
} from '../scrapingApi'

describe('scrapingApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(global.fetch as any).mockClear()
  })

  // ============= startOrResumeScraping Tests =============
  describe('startOrResumeScraping', () => {
    it('should start a new scraping run when first called', async () => {
      const mockResponse = {
        success: true,
        project_complete: false,
        run_token: 'run_abc123',
        next_start_page: 1,
        highest_successful_page: 0,
        total_pages: 50,
        total_persisted_records: 0,
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        status: 201,
        json: async () => mockResponse,
      })

      const result = await startOrResumeScraping('token_xyz', 123)
      
      expect(result).toBeDefined()
      expect(result.run_token).toBe('run_abc123')
      expect(result.next_start_page).toBe(1)
      expect(result.project_complete).toBe(false)
    })

    it('should resume from checkpoint on subsequent calls', async () => {
      const mockResponse = {
        success: true,
        project_complete: false,
        run_token: 'run_def456',
        next_start_page: 6,
        highest_successful_page: 5,
        total_pages: 50,
        total_persisted_records: 125,
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        status: 201,
        json: async () => mockResponse,
      })

      const result = await startOrResumeScraping('token_xyz', 123)
      
      expect(result.next_start_page).toBe(6)
      expect(result.highest_successful_page).toBe(5)
      expect(result.total_persisted_records).toBe(125)
    })

    it('should return project_complete: true when all pages scraped', async () => {
      const mockResponse = {
        success: true,
        project_complete: true,
        total_pages: 50,
        highest_successful_page: 50,
        message: 'Project scraping is complete',
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        status: 200,
        json: async () => mockResponse,
      })

      const result = await startOrResumeScraping('token_xyz', 123)
      
      expect(result.project_complete).toBe(true)
      expect(result.highest_successful_page).toBe(50)
    })

    it('should throw error on API failure', async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        status: 400,
        json: async () => ({ error: 'Invalid token' }),
      })

      await expect(startOrResumeScraping('invalid_token', 123)).rejects.toThrow()
    })
  })

  // ============= completeRunAndPersist Tests =============
  describe('completeRunAndPersist', () => {
    it('should persist records and return next action: continue', async () => {
      const mockResponse = {
        success: true,
        run_completed: true,
        records_persisted: 25,
        highest_successful_page: 1,
        project_complete: false,
        next_action: 'continue',
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        status: 200,
        json: async () => mockResponse,
      })

      const result = await completeRunAndPersist('run_abc', 123, 'token_xyz', 1)
      
      expect(result.records_persisted).toBe(25)
      expect(result.next_action).toBe('continue')
      expect(result.project_complete).toBe(false)
    })

    it('should indicate completion when all pages done', async () => {
      const mockResponse = {
        success: true,
        run_completed: true,
        records_persisted: 30,
        highest_successful_page: 50,
        project_complete: true,
        next_action: 'complete',
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        status: 200,
        json: async () => mockResponse,
      })

      const result = await completeRunAndPersist('run_final', 123, 'token_xyz', 50)
      
      expect(result.next_action).toBe('complete')
      expect(result.project_complete).toBe(true)
    })

    it('should handle run still processing', async () => {
      const mockResponse = {
        success: false,
        error: 'run_still_processing',
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        status: 202,
        json: async () => mockResponse,
      })

      await expect(completeRunAndPersist('run_abc', 123, 'token_xyz', 1)).rejects.toThrow()
    })
  })

  // ============= getProjectProgress Tests =============
  describe('getProjectProgress', () => {
    it('should return full project progress with metadata and checkpoint', async () => {
      const mockResponse = {
        success: true,
        project_id: 123,
        project_name: 'Test Store',
        project_metadata: {
          base_url: 'https://shop.com/items?page=1',
          total_pages: 50,
          total_products: 2500,
        },
        checkpoint: {
          highest_successful_page: 5,
          next_start_page: 6,
          total_persisted_records: 125,
        },
        is_complete: false,
        progress_percentage: 10,
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        status: 200,
        json: async () => mockResponse,
      })

      const result = await getProjectProgress('token_xyz')
      
      expect(result.project_metadata.total_pages).toBe(50)
      expect(result.checkpoint.highest_successful_page).toBe(5)
      expect(result.progress_percentage).toBe(10)
      expect(result.is_complete).toBe(false)
    })

    it('should show 100% progress when all pages scraped', async () => {
      const mockResponse = {
        success: true,
        project_metadata: {
          total_pages: 50,
        },
        checkpoint: {
          highest_successful_page: 50,
        },
        is_complete: true,
        progress_percentage: 100,
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        status: 200,
        json: async () => mockResponse,
      })

      const result = await getProjectProgress('token_xyz')
      
      expect(result.progress_percentage).toBe(100)
      expect(result.is_complete).toBe(true)
    })
  })

  // ============= getCheckpoint Tests =============
  describe('getCheckpoint', () => {
    it('should return checkpoint information', async () => {
      const mockResponse = {
        success: true,
        checkpoint: {
          highest_successful_page: 8,
          next_start_page: 9,
          total_persisted_records: 200,
          checkpoint_timestamp: '2024-03-26T14:30:00Z',
        },
        total_pages: 50,
        progress_percentage: 16,
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        status: 200,
        json: async () => mockResponse,
      })

      const result = await getCheckpoint('token_xyz')
      
      expect(result.checkpoint.highest_successful_page).toBe(8)
      expect(result.checkpoint.next_start_page).toBe(9)
      expect(result.progress_percentage).toBe(16)
    })
  })

  // ============= getProjectMetadata Tests =============
  describe('getProjectMetadata', () => {
    it('should return project metadata', async () => {
      const mockResponse = {
        success: true,
        project_metadata: {
          base_url: 'https://shop.com/items?page=1',
          total_pages: 50,
          total_products: 2500,
        },
        project_name: 'E-commerce Store',
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        status: 200,
        json: async () => mockResponse,
      })

      const result = await getProjectMetadata('token_xyz')
      
      expect(result.base_url).toContain('page=1')
      expect(result.total_products).toBe(2500)
    })
  })

  // ============= startBatchScrapingLegacy Tests =============
  describe('startBatchScrapingLegacy', () => {
    it('should forward to new startOrResumeScraping function', async () => {
      const mockResponse = {
        success: true,
        run_token: 'run_legacy',
        project_complete: false,
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        status: 201,
        json: async () => mockResponse,
      })

      const result = await startBatchScrapingLegacy(
        'token_xyz',
        'https://shop.com/items?page=1',
        false
      )
      
      expect(result).toBeDefined()
      expect(result.run_token).toBe('run_legacy')
    })
  })

  // ============= Error Handling =============
  describe('Error handling', () => {
    it('should handle network errors gracefully', async () => {
      ;(global.fetch as any).mockRejectedValueOnce(new Error('Network error'))

      await expect(startOrResumeScraping('token_xyz', 123)).rejects.toThrow('Network error')
    })

    it('should handle missing required fields', async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        status: 400,
        json: async () => ({ error: 'Missing project_token' }),
      })

      await expect(startOrResumeScraping('', 123)).rejects.toThrow()
    })
  })
})
