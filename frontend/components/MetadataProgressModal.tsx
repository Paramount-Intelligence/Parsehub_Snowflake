'use client'

import { useState, useEffect } from 'react'
import Modal from './Modal'
import { Activity, AlertCircle, CheckCircle2, Loader, Zap, AlertTriangle, Copy } from 'lucide-react'
import apiClient from '@/lib/apiClient'
import { normalizeCheckpointResponse } from '@/lib/scrapingApi'

interface MetadataProgressModalProps {
  isOpen: boolean
  onClose: () => void
  projectToken: string
  projectTitle: string
  metadata?: any
  startingPage?: number
  /** ParseHub run token for this scraping session (display only) */
  runToken?: string
}

export default function MetadataProgressModal({
  isOpen,
  onClose,
  projectToken,
  projectTitle,
  metadata,
  startingPage = 1,
  runToken,
}: MetadataProgressModalProps) {
  const [checkpoint, setCheckpoint] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>('')
  const [nextUrl, setNextUrl] = useState<string>('')
  const [estimatedRecordsPerPage, setEstimatedRecordsPerPage] = useState(0)
  const [copiedUrl, setCopiedUrl] = useState(false)

  useEffect(() => {
    if (!isOpen) return
    setLoading(true)

    const pollProgress = async () => {
      try {
        setError('')

        // Get current checkpoint (unwrap { checkpoint: {...} } from Flask api_server)
        const cpRes = await apiClient.get(`/api/projects/${projectToken}/resume/checkpoint`)
        const cp = normalizeCheckpointResponse(cpRes.data)

        setCheckpoint(cp)
        setLoading(false)

        // Calculate next URL based on pagination pattern
        if (metadata && cp) {
          const nextPage = cp.next_start_page || (cp.highest_successful_page || 0) + 1
          const websiteUrl = metadata.website_url || ''

          if (websiteUrl.includes('?page=')) {
            setNextUrl(websiteUrl.replace(/page=\d+/, `page=${nextPage}`))
          } else if (websiteUrl.includes('?')) {
            setNextUrl(`${websiteUrl}&page=${nextPage}`)
          } else if (websiteUrl) {
            setNextUrl(`${websiteUrl}?page=${nextPage}`)
          }

          // Estimate records per page
          if (cp.total_persisted_records && cp.highest_successful_page > 0) {
            setEstimatedRecordsPerPage(Math.ceil(cp.total_persisted_records / cp.highest_successful_page))
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to load progress'
        // Only log errors in development, suppress in production to avoid console spam
        if (process.env.NODE_ENV === 'development') {
          console.error('Checkpoint error:', err)
        }
        setError(msg)
      }
    }

    pollProgress()
    const interval = setInterval(pollProgress, 10000)
    return () => clearInterval(interval)
  }, [isOpen, projectToken, metadata])

  const highestPage = checkpoint?.highest_successful_page || 0
  const nextPage = checkpoint?.next_start_page || startingPage
  const totalPages = metadata?.total_pages || 0
  const totalProductsMeta = metadata?.total_products
  const totalRecords = checkpoint?.total_persisted_records || 0
  const progressPercent = totalPages > 0 ? (highestPage / totalPages) * 100 : 0
  const remainingPages = Math.max(0, totalPages - highestPage)
  const estimatedRemainingRecords = estimatedRecordsPerPage * remainingPages
  const isComplete =
    Boolean(checkpoint?.is_project_complete) ||
    (totalPages > 0 && highestPage >= totalPages)
  const recordsBelowMeta =
    typeof totalProductsMeta === "number" &&
    totalProductsMeta > 0 &&
    totalRecords < totalProductsMeta &&
    isComplete

  const copyUrlToClipboard = () => {
    navigator.clipboard.writeText(nextUrl)
    setCopiedUrl(true)
    setTimeout(() => setCopiedUrl(false), 2000)
  }

  return (
    <Modal 
      isOpen={isOpen} 
      onClose={onClose} 
      title={`Scraping Progress: ${projectTitle}`}
    >
      <div className="space-y-6">
        {/* Status Header */}
        <div className="flex items-center justify-between p-4 bg-gradient-to-r from-blue-900/20 to-cyan-900/20 border border-blue-700/50 rounded-xl">
          <div className="flex items-center gap-3">
            {isComplete ? (
              <CheckCircle2 className="w-6 h-6 text-green-400 animate-pulse" />
            ) : loading ? (
              <Loader className="w-6 h-6 text-blue-400 animate-spin" />
            ) : (
              <Activity className="w-6 h-6 text-blue-400 animate-pulse" />
            )}
            <div>
              <p className="font-semibold text-slate-200">
                {isComplete ? '✅ Scraping Complete!' : 'Scraping in Progress'}
              </p>
              <p className="text-xs text-slate-400">
                {isComplete ? 'All pages processed' : `Page ${nextPage} of ${totalPages}`}
              </p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-blue-300">{progressPercent.toFixed(0)}%</p>
            <p className="text-xs text-slate-400">{highestPage}/{totalPages} pages</p>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="w-full h-3 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 transition-all duration-500"
              style={{ width: `${Math.min(progressPercent, 100)}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-slate-400">
            <span>0 pages</span>
            <span className="font-semibold text-slate-300">{progressPercent.toFixed(1)}%</span>
            <span>{totalPages} pages</span>
          </div>
        </div>

        {/* Run + metadata targets */}
        {(runToken || typeof totalProductsMeta === 'number') && (
          <div className="flex flex-wrap gap-3 text-xs text-slate-400 border border-slate-700/80 rounded-lg p-3 bg-slate-900/40">
            {runToken && (
              <span>
                <span className="text-slate-500">Run:</span>{' '}
                <span className="font-mono text-slate-300">{runToken.slice(0, 14)}…</span>
              </span>
            )}
            {typeof totalProductsMeta === 'number' && totalProductsMeta > 0 && (
              <span>
                <span className="text-slate-500">Metadata expected products:</span>{' '}
                <span className="font-semibold text-slate-200">{totalProductsMeta.toLocaleString()}</span>
              </span>
            )}
            {typeof totalProductsMeta === 'number' && totalProductsMeta > 0 && (
              <span>
                <span className="text-slate-500">Saved vs expected:</span>{' '}
                <span
                  className={
                    totalRecords >= totalProductsMeta ? 'text-emerald-400' : 'text-amber-300'
                  }
                >
                  {totalRecords.toLocaleString()} / {totalProductsMeta.toLocaleString()}
                </span>
              </span>
            )}
          </div>
        )}

        {recordsBelowMeta && (
          <div className="bg-amber-900/20 border border-amber-600/50 rounded-lg p-3 text-xs text-amber-200">
            All pages are processed, but saved record count is still below metadata{' '}
            <strong>total_products</strong>. This can happen if listing density changed or metadata is
            an estimate — verify in Snowflake <code className="text-amber-100">scraped_records</code>.
          </div>
        )}

        {/* Key Metrics */}
        <div className="grid grid-cols-3 gap-3">
          {/* Data Scraped */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
            <p className="text-xs text-slate-400 font-medium">DATA SCRAPED</p>
            <p className="text-xl font-bold text-slate-200 mt-1">{totalRecords.toLocaleString()}</p>
            <p className="text-xs text-slate-500 mt-1">
              {estimatedRecordsPerPage > 0 ? `~${estimatedRecordsPerPage}/page` : 'Calculating...'}
            </p>
          </div>

          {/* Pages Remaining */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
            <p className="text-xs text-slate-400 font-medium">REMAINING</p>
            <p className="text-xl font-bold text-slate-200 mt-1">{remainingPages}</p>
            <p className="text-xs text-slate-500 mt-1">pages</p>
          </div>

          {/* Est. Records */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
            <p className="text-xs text-slate-400 font-medium">EST. RECORDS</p>
            <p className="text-xl font-bold text-slate-200 mt-1">{estimatedRemainingRecords.toLocaleString()}</p>
            <p className="text-xs text-slate-500 mt-1">remaining</p>
          </div>
        </div>

        {/* Next URL to be Generated */}
        <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" />
              <p className="text-sm font-semibold text-slate-300">Next URL to Scrape</p>
            </div>
            {nextUrl && (
              <button
                onClick={copyUrlToClipboard}
                className="px-2 py-1 text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 rounded flex items-center gap-1 transition-colors"
              >
                <Copy className="w-3 h-3" />
                {copiedUrl ? 'Copied!' : 'Copy'}
              </button>
            )}
          </div>
          <div className="bg-slate-800/50 rounded p-2 border border-slate-600 overflow-x-auto">
            <p className="text-xs font-mono text-blue-300 break-all whitespace-pre-wrap">
              {nextUrl || `${metadata?.website_url || 'Loading...'}?page=${nextPage}`}
            </p>
          </div>
          <p className="text-xs text-slate-500">
            This URL will be used for page {nextPage} if scraping continues
          </p>
        </div>

        {/* Stop Point Info */}
        <div className="bg-amber-900/20 border border-amber-700/50 rounded-lg p-4 space-y-2">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <p className="text-sm font-semibold text-amber-300">If You Stop Now</p>
          </div>
          <div className="space-y-1 text-xs text-amber-200">
            <p>
              • Pages completed: <span className="font-semibold">{highestPage}/{totalPages}</span>
            </p>
            <p>
              • Data saved: <span className="font-semibold">{totalRecords.toLocaleString()} records</span>
            </p>
            <p>
              • Next resume from: <span className="font-semibold">Page {nextPage}</span>
            </p>
            <p>
              • Will still need: <span className="font-semibold">{remainingPages} more pages</span>
            </p>
            {estimatedRemainingRecords > 0 && (
              <p>
                • Est. records left: <span className="font-semibold">{estimatedRemainingRecords.toLocaleString()}</span>
              </p>
            )}
            <p className="mt-2 pt-2 border-t border-amber-700/50">
              ✓ Resuming later will skip completed pages and continue from page {nextPage}
            </p>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-3 flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-red-200">
              <p className="font-semibold">Warning</p>
              <p className="text-xs mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Info Box */}
        <div className="bg-blue-900/20 border border-blue-700/50 rounded-lg p-3">
          <p className="text-xs text-blue-200">
            <strong>💡 Tip:</strong> You can safely close this window. Scraping continues in the background. 
            The system automatically saves progress with source_page tracking, so you can resume anytime without losing data.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 font-medium rounded-lg transition-colors"
          >
            {isComplete ? 'Done' : 'Minimize'}
          </button>
          {isComplete && (
            <button
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <CheckCircle2 className="w-4 h-4" />
              Close
            </button>
          )}
        </div>
      </div>
    </Modal>
  )
}
