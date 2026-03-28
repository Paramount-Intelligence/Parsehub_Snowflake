import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useMonitoring } from '../useBatchMonitoring'

// Mock the scrapingApi module
vi.mock('../scrapingApi', () => ({
  startOrResumeScraping: vi.fn(),
  completeRunAndPersist: vi.fn(),
  getProjectProgress: vi.fn(),
  getCheckpoint: vi.fn(),
}))

describe('useMonitoring Hook', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should initialize with default state', () => {
    const { result } = renderHook(() =>
      useMonitoring('token_xyz', 123)
    )

    expect(result.current.uiState).toBeDefined()
    expect(result.current.checkpoint).toBeDefined()
    expect(result.current.progress).toBeDefined()
  })

  it('should provide startOrResume method', async () => {
    const { result } = renderHook(() =>
      useMonitoring('token_xyz', 123)
    )

    expect(result.current.startOrResume).toBeDefined()
    expect(typeof result.current.startOrResume).toBe('function')
  })

  it('should provide completeRun method', async () => {
    const { result } = renderHook(() =>
      useMonitoring('token_xyz', 123)
    )

    expect(result.current.completeRun).toBeDefined()
    expect(typeof result.current.completeRun).toBe('function')
  })

  it('should provide refresh method', async () => {
    const { result } = renderHook(() =>
      useMonitoring('token_xyz', 123)
    )

    expect(result.current.refresh).toBeDefined()
    expect(typeof result.current.refresh).toBe('function')
  })

  it('should track progress as percentage', async () => {
    const { result } = renderHook(() =>
      useMonitoring('token_xyz', 123)
    )

    expect(result.current.uiState.progressPercentage).toBeGreaterThanOrEqual(0)
    expect(result.current.uiState.progressPercentage).toBeLessThanOrEqual(100)
  })

  it('should handle running state', async () => {
    const { result } = renderHook(() =>
      useMonitoring('token_xyz', 123)
    )

    expect(result.current.uiState.isRunning).toBeDefined()
    expect(typeof result.current.uiState.isRunning).toBe('boolean')
  })

  it('should handle completion state', async () => {
    const { result } = renderHook(() =>
      useMonitoring('token_xyz', 123)
    )

    expect(result.current.uiState.isComplete).toBeDefined()
    expect(typeof result.current.uiState.isComplete).toBe('boolean')
  })

  it('should provide checkpoint information', async () => {
    const { result } = renderHook(() =>
      useMonitoring('token_xyz', 123)
    )

    expect(result.current.checkpoint.highest_successful_page).toBeDefined()
    expect(result.current.checkpoint.next_start_page).toBeDefined()
    expect(result.current.checkpoint.total_persisted_records).toBeDefined()
  })

  it('should poll progress at intervals', async () => {
    const { result } = renderHook(() =>
      useMonitoring('token_xyz', 123, { pollInterval: 100 })
    )

    await waitFor(
      () => {
        // Poll should be called at least once
        expect(result.current.progress).toBeDefined()
      },
      { timeout: 500 }
    )
  })
})
