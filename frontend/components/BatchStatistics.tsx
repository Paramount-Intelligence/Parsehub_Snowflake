/**
 * Batch Statistics Dashboard
 * Displays batch-based scraping metrics and insights
 */

'use client'

import React, { useEffect, useState } from 'react'
import {
  BarChart3,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Zap,
  Clock,
  Database,
} from 'lucide-react'
import apiClient from '@/lib/apiClient'

interface BatchStatsProps {
  projectToken: string
  refreshInterval?: number
}

interface BatchStats {
  total_batches: number
  completed_batches: number
  failed_batches: number
  total_records: number
  avg_records_per_batch: number
  last_completed_batch: number
  success_rate: number
  last_scraped_at: string
  estimated_completion?: {
    batches_remaining: number
    estimated_pages_remaining: number
  }
}

export default function BatchStatistics({ projectToken, refreshInterval = 30000 }: BatchStatsProps) {
  const [stats, setStats] = useState<BatchStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadStats = async () => {
      try {
        const res = await apiClient.get(`/api/projects/${projectToken}/batch-statistics`)
        if (res.status === 200) {
          setStats(res.data)
          setError(null)
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Failed to load statistics'
        setError(errorMsg)
      } finally {
        setIsLoading(false)
      }
    }

    loadStats()
    const interval = setInterval(loadStats, refreshInterval)
    return () => clearInterval(interval)
  }, [projectToken, refreshInterval])

  if (isLoading && !stats) {
    return (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 h-32 animate-pulse" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-900/30 border border-red-700/50 rounded-lg p-4 flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-red-300">Error loading statistics</p>
          <p className="text-sm text-red-200">{error}</p>
        </div>
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="bg-slate-800/30 border border-slate-700 rounded-lg p-6 text-center text-slate-400">
        No batch statistics available yet.
      </div>
    )
  }

  const successRateColor =
    stats.success_rate >= 95
      ? 'from-green-900/40 to-emerald-900/40 border-green-700/50'
      : stats.success_rate >= 80
        ? 'from-yellow-900/40 to-amber-900/40 border-yellow-700/50'
        : 'from-red-900/40 to-orange-900/40 border-red-700/50'

  const successRateTextColor =
    stats.success_rate >= 95
      ? 'text-green-400'
      : stats.success_rate >= 80
        ? 'text-yellow-400'
        : 'text-red-400'

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Total Batches */}
        <div className="bg-gradient-to-br from-blue-900/40 to-blue-800/40 border border-blue-700/50 rounded-lg p-4">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <p className="text-xs font-semibold text-blue-300 uppercase">Total Batches</p>
              <p className="text-3xl font-bold text-blue-200 mt-2">{stats.total_batches}</p>
              <p className="text-xs text-blue-400 mt-2">
                {stats.completed_batches} completed
              </p>
            </div>
            <BarChart3 className="w-8 h-8 text-blue-500/40" />
          </div>
        </div>

        {/* Success Rate */}
        <div className={`bg-gradient-to-br ${successRateColor} rounded-lg p-4 border`}>
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <p className="text-xs font-semibold text-slate-300 uppercase">Success Rate</p>
              <p className={`text-3xl font-bold mt-2 ${successRateTextColor}`}>
                {stats.success_rate.toFixed(1)}%
              </p>
              <p className="text-xs text-slate-400 mt-2">
                {stats.failed_batches} failed
              </p>
            </div>
            <CheckCircle className={`w-8 h-8 ${successRateTextColor}/40`} />
          </div>
        </div>

        {/* Total Records */}
        <div className="bg-gradient-to-br from-emerald-900/40 to-emerald-800/40 border border-emerald-700/50 rounded-lg p-4">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <p className="text-xs font-semibold text-emerald-300 uppercase">Total Records</p>
              <p className="text-3xl font-bold text-emerald-200 mt-2">
                {stats.total_records.toLocaleString()}
              </p>
              <p className="text-xs text-emerald-400 mt-2">
                {stats.avg_records_per_batch.toFixed(0)} avg/batch
              </p>
            </div>
            <Database className="w-8 h-8 text-emerald-500/40" />
          </div>
        </div>

        {/* Last Activity */}
        <div className="bg-gradient-to-br from-purple-900/40 to-purple-800/40 border border-purple-700/50 rounded-lg p-4">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <p className="text-xs font-semibold text-purple-300 uppercase">Last Activity</p>
              <p className="text-sm text-purple-200 mt-2 font-mono">
                {stats.last_scraped_at
                  ? new Date(stats.last_scraped_at).toLocaleString()
                  : 'Never'}
              </p>
              <p className="text-xs text-purple-400 mt-2">
                Batch {stats.last_completed_batch}
              </p>
            </div>
            <Clock className="w-8 h-8 text-purple-500/40" />
          </div>
        </div>
      </div>

      {/* Estimated Completion */}
      {stats.estimated_completion && stats.estimated_completion.batches_remaining > 0 && (
        <div className="bg-gradient-to-r from-cyan-900/40 to-blue-900/40 border border-cyan-700/50 rounded-lg p-4">
          <div className="flex items-center gap-3 mb-3">
            <Zap className="w-5 h-5 text-cyan-400" />
            <h3 className="font-semibold text-slate-200">Estimated Remaining</h3>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-cyan-400 font-semibold">
                {stats.estimated_completion.batches_remaining}
              </p>
              <p className="text-xs text-slate-400">batches remaining</p>
            </div>
            <div>
              <p className="text-cyan-400 font-semibold">
                ~{stats.estimated_completion.estimated_pages_remaining}
              </p>
              <p className="text-xs text-slate-400">pages to scrape</p>
            </div>
          </div>
        </div>
      )}

      {/* Performance Summary */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
          <TrendingUp className="w-4 h-4" />
          Performance Summary
        </h3>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Batch Efficiency</span>
            <span className="text-slate-200 font-medium">
              {stats.avg_records_per_batch.toFixed(0)} records/batch
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Completion Rate</span>
            <span className="text-slate-200 font-medium">
              {((stats.completed_batches / Math.max(stats.total_batches, 1)) * 100).toFixed(1)}%
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Failed Batches</span>
            <span className={`font-medium ${stats.failed_batches > 0 ? 'text-red-400' : 'text-green-400'}`}>
              {stats.failed_batches}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
