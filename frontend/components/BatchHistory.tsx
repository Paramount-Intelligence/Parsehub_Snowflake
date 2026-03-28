/**
 * Batch History and Status Display
 * Shows detailed batch-by-batch scraping history and current checkpoint
 */

'use client'

import React, { useEffect, useState } from 'react'
import { ChevronDown, CheckCircle, AlertCircle, Clock, Zap, TrendingUp } from 'lucide-react'
import apiClient from '@/lib/apiClient'

interface BatchHistoryProps {
  projectToken: string
  projectName?: string
  maxRecords?: number
}

/**
 * BatchHistory component displays:
 * - Checkpoint information (last completed page, next start)
 * - List of completed batches
 * - Batch details (page range, records, status)
 * - Failed batch information
 */
export default function BatchHistory({
  projectToken,
  projectName,
  maxRecords = 20,
}: BatchHistoryProps) {
  const [history, setHistory] = useState<any>(null)
  const [checkpoint, setCheckpoint] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedBatches, setExpandedBatches] = useState<Set<number>>(new Set())

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const [historyRes, checkpointRes] = await Promise.all([
          apiClient.get(`/api/projects/${projectToken}/scraping-history?limit=${maxRecords}`),
          apiClient.get(`/api/projects/${projectToken}/checkpoint`),
        ])

        if (historyRes.status === 200) {
          setHistory(historyRes.data)
        }

        if (checkpointRes.status === 200) {
          setCheckpoint(checkpointRes.data)
        }

        setError(null)
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Failed to load history'
        setError(errorMsg)
        console.error('Error loading batch history:', err)
      } finally {
        setIsLoading(false)
      }
    }

    loadHistory()
  }, [projectToken, maxRecords])

  const toggleBatchExpand = (batchNumber: number) => {
    const newSet = new Set(expandedBatches)
    if (newSet.has(batchNumber)) {
      newSet.delete(batchNumber)
    } else {
      newSet.add(batchNumber)
    }
    setExpandedBatches(newSet)
  }

  if (isLoading) {
    return (
      <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6 text-center">
        <div className="animate-spin inline-block">
          <Zap className="w-6 h-6 text-blue-500" />
        </div>
        <p className="text-slate-400 mt-2">Loading batch history...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-900/30 border border-red-700/50 rounded-lg p-4 flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-red-300">Error loading history</p>
          <p className="text-sm text-red-200">{error}</p>
        </div>
      </div>
    )
  }

  const batches = history?.batch_history || []
  const ckpt = checkpoint || history?.last_checkpoint

  return (
    <div className="space-y-4">
      {/* Checkpoint Summary */}
      {ckpt && (
        <div className="bg-gradient-to-r from-blue-900/40 to-cyan-900/40 border border-blue-700/50 rounded-lg p-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase">Last Completed</p>
              <p className="text-2xl font-bold text-blue-400">
                {ckpt.last_completed_page || 0}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase">Next Start</p>
              <p className="text-2xl font-bold text-cyan-400">
                {ckpt.next_start_page || 0}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase">Total Pages</p>
              <p className="text-2xl font-bold text-slate-300">
                {ckpt.total_pages || 0}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase">Completed</p>
              <p className="text-2xl font-bold text-emerald-400">
                {ckpt.total_batches_completed || 0}
              </p>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-blue-700/30">
            <p className="text-xs text-slate-400">
              Last updated: {new Date(ckpt.checkpoint_timestamp).toLocaleString()}
            </p>
            {ckpt.failed_batches > 0 && (
              <p className="text-xs text-orange-400 mt-1 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                {ckpt.failed_batches} batch(es) failed
              </p>
            )}
            {ckpt.consecutive_empty_batches > 0 && (
              <p className="text-xs text-amber-400 mt-1">
                {ckpt.consecutive_empty_batches} consecutive empty batches
              </p>
            )}
          </div>
        </div>
      )}

      {/* Batches List */}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-slate-200">Batch History</h3>
        
        {batches.length === 0 ? (
          <div className="bg-slate-800/30 border border-slate-700 rounded-lg p-4 text-center text-slate-400 text-sm">
            No batches yet. Start scraping to create batch history.
          </div>
        ) : (
          <div className="space-y-2">
            {batches.map((batch: any, idx: number) => (
              <div
                key={idx}
                className={`border rounded-lg overflow-hidden transition-colors ${
                  batch.status === 'completed'
                    ? 'bg-green-900/20 border-green-700/50 hover:bg-green-900/30'
                    : batch.status === 'failed'
                      ? 'bg-red-900/20 border-red-700/50 hover:bg-red-900/30'
                      : 'bg-slate-800/50 border-slate-700 hover:bg-slate-800/70'
                }`}
              >
                {/* Batch Header */}
                <button
                  onClick={() => toggleBatchExpand(batch.batch_number)}
                  className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-black/20 transition-colors"
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    {/* Status Icon */}
                    <div className="flex-shrink-0">
                      {batch.status === 'completed' ? (
                        <CheckCircle className="w-5 h-5 text-green-400" />
                      ) : batch.status === 'failed' ? (
                        <AlertCircle className="w-5 h-5 text-red-400" />
                      ) : (
                        <Clock className="w-5 h-5 text-yellow-400" />
                      )}
                    </div>

                    {/* Batch Info */}
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-slate-200">
                        Batch {batch.batch_number}:{' '}
                        <span className="text-slate-400">{batch.batch_range}</span>
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {batch.records_scraped} records
                      </p>
                    </div>

                    {/* Status Badge */}
                    <span
                      className={`px-2 py-1 rounded text-xs font-semibold flex-shrink-0 ${
                        batch.status === 'completed'
                          ? 'bg-green-900/60 text-green-300'
                          : batch.status === 'failed'
                            ? 'bg-red-900/60 text-red-300'
                            : 'bg-yellow-900/60 text-yellow-300'
                      }`}
                    >
                      {batch.status === 'completed' ? 'Complete' : batch.status === 'failed' ? 'Failed' : 'Pending'}
                    </span>
                  </div>

                  <ChevronDown
                    className={`w-4 h-4 flex-shrink-0 text-slate-500 transition-transform ${
                      expandedBatches.has(batch.batch_number) ? 'rotate-180' : ''
                    }`}
                  />
                </button>

                {/* Batch Details (Expanded) */}
                {expandedBatches.has(batch.batch_number) && (
                  <div className="border-t border-current/10 px-4 py-3 bg-black/20 space-y-2 text-sm">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <p className="text-xs text-slate-500 font-medium">Run Token</p>
                        <p className="text-xs text-slate-300 font-mono truncate">
                          {batch.run_token || 'N/A'}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500 font-medium">Records</p>
                        <p className="text-slate-300 font-semibold">{batch.records_scraped}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500 font-medium">Started</p>
                        <p className="text-xs text-slate-300">
                          {batch.started_at
                            ? new Date(batch.started_at).toLocaleString()
                            : 'N/A'}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500 font-medium">Completed</p>
                        <p className="text-xs text-slate-300">
                          {batch.completed_at
                            ? new Date(batch.completed_at).toLocaleString()
                            : 'Pending'}
                        </p>
                      </div>
                    </div>

                    {batch.error_message && (
                      <div className="bg-red-900/30 border border-red-700/50 rounded p-2 mt-2">
                        <p className="text-xs text-red-300">
                          <strong>Error:</strong> {batch.error_message}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex gap-4 text-xs text-slate-500 pt-2 border-t border-slate-700/50">
        <div className="flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-green-400" />
          <span>Completed</span>
        </div>
        <div className="flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-400" />
          <span>Failed</span>
        </div>
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-yellow-400" />
          <span>Pending</span>
        </div>
      </div>
    </div>
  )
}
