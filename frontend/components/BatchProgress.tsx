'use client'

import React, { useState, useEffect } from 'react'
import { Activity, AlertCircle, CheckCircle, Clock, Zap, RotateCcw } from 'lucide-react'
import apiClient from "@/lib/apiClient"

interface BatchProgressProps {
  projectToken: string
  projectName?: string
  sessionId?: string
  isActive?: boolean
  refreshInterval?: number
  onBatchComplete?: (batch: any) => void
  onError?: (error: string) => void
}

/**
 * BatchProgress Component - Displays chunk-based batch scraping progress
 * 
 * Shows:
 * - Current batch range (e.g., "Batch 1: Pages 1-10")
 * - Last completed page and checkpoint
 * - Progress through batches
 * - Records scraped in current batch
 * - Status (running, completed, failed)
 * - Retry option for failed batches
 */
export default function BatchProgress({
  projectToken,
  projectName = "Project",
  sessionId,
  isActive = false,
  refreshInterval = 3000,
  onBatchComplete,
  onError,
}: BatchProgressProps) {
  const [batchStatus, setBatchStatus] = useState<any>(null)
  const [checkpoint, setCheckpoint] = useState<any>(null)
  const [shouldAuto, setShouldAuto] = useState(isActive)
  const [isRetrying, setIsRetrying] = useState(false)

  useEffect(() => {
    if (!shouldAuto && !isActive) {
      return
    }

    const loadStatus = async () => {
      try {
        const endpoint = sessionId
          ? `/api/projects/batch/status?session_id=${sessionId}`
          : `/api/projects/${projectToken}/checkpoint`

        const response = await apiClient.get(endpoint)
        if (response.status === 200) {
          const data = response.data
          setBatchStatus(data)
          
          if (data.checkpoint) {
            setCheckpoint(data.checkpoint)
          }

          // Trigger callback on batch completion
          if (
            onBatchComplete &&
            data.current_batch?.status === 'completed'
          ) {
            onBatchComplete(data.current_batch)
          }

          // Stop auto-refresh if scraping is complete or failed
          if (data.status === 'completed' || data.status === 'failed') {
            setShouldAuto(false)
          }
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Error loading batch status'
        console.error(errorMsg)
        onError?.(errorMsg)
      }
    }

    loadStatus()
    const interval = setInterval(loadStatus, refreshInterval)
    return () => clearInterval(interval)
  }, [shouldAuto, isActive, projectToken, sessionId, refreshInterval, onBatchComplete, onError])

  if (!batchStatus) {
    return null
  }

  const currentBatch = batchStatus.current_batch || {}
  const ckpt = checkpoint || batchStatus.checkpoint || {}
  
  const batchRange = `${currentBatch.batch_start_page || '?'}-${currentBatch.batch_end_page || '?'}`
  const lastCompletedPage = ckpt.last_completed_page || 0
  const nextStartPage = ckpt.next_start_page || 1
  const totalPages = ckpt.total_pages || 0
  const completedBatches = ckpt.total_batches_completed || 0
  const failedBatches = ckpt.failed_batches || 0

  const progressPercent = totalPages > 0 ? (lastCompletedPage / totalPages) * 100 : 0

  const getStatusIcon = () => {
    if (batchStatus.status === 'completed') {
      return <CheckCircle className="w-5 h-5 text-green-600" />
    }
    if (batchStatus.status === 'failed' || batchStatus.status === 'error') {
      return <AlertCircle className="w-5 h-5 text-red-600" />
    }
    return <Activity className="w-5 h-5 text-blue-600 animate-spin" />
  }

  const getStatusColor = () => {
    if (batchStatus.status === 'completed') return 'bg-green-50 border-green-200'
    if (batchStatus.status === 'failed' || batchStatus.status === 'error') return 'bg-red-50 border-red-200'
    return 'bg-blue-50 border-blue-200'
  }

  const getStatusText = () => {
    if (batchStatus.status === 'completed') return 'Completed'
    if (batchStatus.status === 'failed') return 'Failed'
    if (batchStatus.status === 'error') return 'Error'
    if (batchStatus.status === 'paused') return 'Paused'
    return 'Running'
  }

  const handleRetry = async () => {
    if (!sessionId || !currentBatch.batch_number) return
    
    setIsRetrying(true)
    try {
      await apiClient.post(`/api/projects/batch/retry`, {
        session_id: sessionId,
        batch_number: currentBatch.batch_number,
      })
      // Status will update on next poll
    } catch (err) {
      console.error('Error retrying batch:', err)
    } finally {
      setIsRetrying(false)
    }
  }

  return (
    <div className={`border rounded-lg p-4 space-y-3 ${getStatusColor()}`}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          {getStatusIcon()}
          <div>
            <p className="font-semibold text-gray-900">Batch Scraping Progress</p>
            {projectName && (
              <p className="text-xs text-gray-600">{projectName}</p>
            )}
            {batchStatus.started_at && (
              <p className="text-xs text-gray-600 flex items-center gap-1 mt-0.5">
                <Clock className="w-3 h-3" />
                Started {new Date(batchStatus.started_at).toLocaleString()}
              </p>
            )}
          </div>
        </div>
        <div className="text-right">
          <span className="text-sm font-medium text-gray-600 block">
            {getStatusText()}
          </span>
          {batchStatus.status === 'running' && (
            <span className="text-xs text-gray-500">
              Batch {currentBatch.batch_number || '?'}
            </span>
          )}
        </div>
      </div>

      {/* Current Batch Info */}
      <div className="bg-white bg-opacity-60 rounded p-2.5 border border-gray-300 text-sm">
        <div className="flex justify-between items-center">
          <span className="text-gray-700 font-medium">Current Batch</span>
          <span className="text-gray-900 font-semibold">
            Pages {batchRange}
          </span>
        </div>
        {currentBatch.records_in_batch !== undefined && (
          <div className="text-xs text-gray-600 mt-1">
            {currentBatch.records_in_batch} records in this batch
          </div>
        )}
      </div>

      {/* Checkpoint Progress */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-gray-700 font-medium">Overall Progress</span>
          <span className="text-gray-600">
            Page {lastCompletedPage} / {totalPages}
          </span>
        </div>
        <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-300"
            style={{ width: `${Math.min(progressPercent, 100)}%` }}
          />
        </div>
        <div className="text-xs text-gray-700 flex justify-between">
          <span>{progressPercent.toFixed(1)}% complete</span>
          <span className="text-gray-600">
            {completedBatches} batches • Next: page {nextStartPage}
          </span>
        </div>
      </div>

      {/* Batch Statistics */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-white rounded p-2 border border-gray-200">
          <p className="text-xs text-gray-600 font-medium">Batches</p>
          <p className="text-lg font-bold text-gray-900">
            {completedBatches}
            {failedBatches > 0 && (
              <span className="text-sm font-normal text-red-600 ml-1">
                ({failedBatches} failed)
              </span>
            )}
          </p>
        </div>
        <div className="bg-white rounded p-2 border border-gray-200">
          <p className="text-xs text-gray-600 font-medium">Stored Records</p>
          <p className="text-lg font-bold text-gray-900">
            {batchStatus.total_records_stored || 0}
          </p>
        </div>
        <div className="bg-white rounded p-2 border border-gray-200">
          <p className="text-xs text-gray-600 font-medium">Last Updated</p>
          <p className="text-xs font-bold text-gray-900">
            {batchStatus.last_updated
              ? new Date(batchStatus.last_updated).toLocaleTimeString()
              : 'Now'}
          </p>
        </div>
      </div>

      {/* Checkpoint/Resume Message */}
      {batchStatus.status === 'running' && nextStartPage > 1 && (
        <div className="text-xs bg-white bg-opacity-60 p-2.5 rounded border-l-4 border-blue-400 text-blue-800 flex items-start gap-2">
          <Zap className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>
            Checkpoint saved at page {lastCompletedPage}. If interrupted, you can
            resume from page {nextStartPage}.
          </span>
        </div>
      )}

      {/* Error Message */}
      {(batchStatus.status === 'failed' || batchStatus.status === 'error') && 
       batchStatus.last_error && (
        <div className="text-xs bg-white bg-opacity-60 p-2.5 rounded border-l-4 border-red-400 text-red-800">
          <strong>Error:</strong> {batchStatus.last_error}
        </div>
      )}

      {/* Stalled Alert */}
      {batchStatus.checkpoint?.consecutive_empty_batches >= 3 && (
        <div className="text-xs bg-amber-50 p-2.5 rounded border border-amber-300 text-amber-900 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>
            Scraping appears to be stalled ({batchStatus.checkpoint.consecutive_empty_batches} empty batches).
            The website may have no more data or the pagination pattern changed.
          </span>
        </div>
      )}

      {/* Action Buttons */}
      <div className="border-t pt-3 space-y-2">
        {!shouldAuto && batchStatus.status !== 'completed' && (
          <button
            onClick={() => setShouldAuto(true)}
            className="w-full text-sm px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors font-medium"
          >
            Resume Monitoring
          </button>
        )}

        {batchStatus.status === 'failed' && currentBatch.batch_number && (
          <button
            onClick={handleRetry}
            disabled={isRetrying}
            className="w-full text-sm px-3 py-2 bg-orange-600 text-white rounded hover:bg-orange-700 transition-colors font-medium disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <RotateCcw className="w-4 h-4" />
            {isRetrying ? 'Retrying...' : `Retry Batch ${currentBatch.batch_number}`}
          </button>
        )}

        {shouldAuto && batchStatus.status === 'running' && (
          <button
            onClick={() => setShouldAuto(false)}
            className="w-full text-sm px-3 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors font-medium"
          >
            Pause Monitoring
          </button>
        )}
      </div>
    </div>
  )
}
