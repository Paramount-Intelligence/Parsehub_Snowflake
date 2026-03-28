'use client';

import React, { useEffect, useState } from 'react';
import { useRealTimeMonitoring } from '@/lib/useRealTimeMonitoring';

interface BatchProgress {
  run_token: string;
  batch_number: number;
  batch_start_page: number;
  batch_end_page: number;
  current_page: number;
  records_extracted: number;
  pages_completed: number;
  status: 'running' | 'completed' | 'failed' | 'idle';
  estimated_time_remaining?: number;
  extraction_rate?: number; // records per page
}

export default function BatchMonitoringPanel({ runToken }: { runToken?: string }) {
  const [batchProgress, setBatchProgress] = useState<BatchProgress | null>(null);
  const [isMonitoring, setIsMonitoring] = useState(false);
  const { runStatus } = useRealTimeMonitoring(runToken || '');

  useEffect(() => {
    if (!runToken) return;

    setIsMonitoring(true);

    // Poll for batch progress
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`/api/batch/progress/${runToken}`);
        if (response.ok) {
          const data = await response.json();
          setBatchProgress(data);

          // Stop monitoring when batch completes
          if (data.status === 'completed' || data.status === 'failed') {
            setIsMonitoring(false);
          }
        }
      } catch (error) {
        console.error('Failed to fetch batch progress:', error);
      }
    }, 2000); // Update every 2 seconds

    return () => clearInterval(pollInterval);
  }, [runToken]);

  if (!runToken || !batchProgress) {
    return null;
  }

  const totalPagesInBatch = batchProgress.batch_end_page - batchProgress.batch_start_page + 1;
  const progressPercentage = (batchProgress.pages_completed / totalPagesInBatch) * 100;
  const recordsPerPage = batchProgress.extraction_rate || 0;

  return (
    <div className="w-full bg-gradient-to-br from-blue-50 to-indigo-50 border-2 border-indigo-200 rounded-lg p-6 shadow-lg">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h3 className="text-xl font-bold text-gray-800">Batch Processing</h3>
          <p className="text-sm text-gray-600">
            Batch #{batchProgress.batch_number} • Pages {batchProgress.batch_start_page}-
            {batchProgress.batch_end_page}
          </p>
        </div>
        <div className="text-right">
          <div className="text-sm font-semibold text-indigo-600">
            {batchProgress.status === 'running' && (
              <span className="inline-flex items-center">
                <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse mr-2"></span>
                In Progress
              </span>
            )}
            {batchProgress.status === 'completed' && (
              <span className="text-green-600">✓ Completed</span>
            )}
            {batchProgress.status === 'failed' && <span className="text-red-600">✗ Failed</span>}
          </div>
          <p className="text-xs text-gray-500 mt-1">Run: {runToken.substring(0, 8)}...</p>
        </div>
      </div>

      {/* Progress Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {/* Current Page */}
        <div className="bg-white rounded-lg p-4 border border-gray-200">
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
            Current Page
          </p>
          <p className="text-2xl font-bold text-indigo-600 mt-1">
            {batchProgress.current_page || batchProgress.batch_start_page}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            of {batchProgress.batch_end_page}
          </p>
        </div>

        {/* Records Extracted */}
        <div className="bg-white rounded-lg p-4 border border-gray-200">
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
            Records Extracted
          </p>
          <p className="text-2xl font-bold text-green-600 mt-1">
            {batchProgress.records_extracted.toLocaleString()}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {recordsPerPage > 0 ? `${recordsPerPage.toFixed(1)} per page` : 'Extracting...'}
          </p>
        </div>

        {/* Pages Completed */}
        <div className="bg-white rounded-lg p-4 border border-gray-200">
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
            Pages Completed
          </p>
          <p className="text-2xl font-bold text-blue-600 mt-1">
            {batchProgress.pages_completed}/{totalPagesInBatch}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {progressPercentage.toFixed(0)}% complete
          </p>
        </div>

        {/* Time Remaining */}
        <div className="bg-white rounded-lg p-4 border border-gray-200">
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
            Est. Time Left
          </p>
          <p className="text-2xl font-bold text-orange-600 mt-1">
            {batchProgress.estimated_time_remaining
              ? `${Math.ceil(batchProgress.estimated_time_remaining / 60)}m`
              : 'Calculating...'}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {batchProgress.status === 'running' ? 'at current rate' : 'N/A'}
          </p>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="flex justify-between items-center mb-2">
          <p className="text-sm font-semibold text-gray-700">Batch Progress</p>
          <p className="text-sm font-bold text-indigo-600">{progressPercentage.toFixed(1)}%</p>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden border border-gray-300">
          <div
            className="bg-gradient-to-r from-blue-500 to-indigo-600 h-full transition-all duration-300 ease-out"
            style={{ width: `${progressPercentage}%` }}
          ></div>
        </div>
      </div>

      {/* Status Details */}
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-gray-600">Batch Range</p>
            <p className="font-semibold text-gray-900">
              Page {batchProgress.batch_start_page} - {batchProgress.batch_end_page}
            </p>
          </div>
          <div>
            <p className="text-gray-600">Total Pages in Batch</p>
            <p className="font-semibold text-gray-900">{totalPagesInBatch} pages</p>
          </div>
          <div>
            <p className="text-gray-600">Extraction Rate</p>
            <p className="font-semibold text-gray-900">
              {recordsPerPage > 0 ? `${recordsPerPage.toFixed(1)} records/page` : 'N/A'}
            </p>
          </div>
          <div>
            <p className="text-gray-600">Status</p>
            <p className="font-semibold text-gray-900 capitalize">{batchProgress.status}</p>
          </div>
        </div>
      </div>

      {/* Status Message */}
      {batchProgress.status === 'completed' && (
        <div className="mt-4 bg-green-50 border-l-4 border-green-600 p-4 rounded">
          <p className="text-sm text-green-800 font-semibold">
            ✓ Batch completed successfully
          </p>
          <p className="text-xs text-green-700 mt-1">
            Extracted {batchProgress.records_extracted.toLocaleString()} records from all{' '}
            {totalPagesInBatch} pages
          </p>
        </div>
      )}

      {batchProgress.status === 'failed' && (
        <div className="mt-4 bg-red-50 border-l-4 border-red-600 p-4 rounded">
          <p className="text-sm text-red-800 font-semibold">✗ Batch processing failed</p>
          <p className="text-xs text-red-700 mt-1">
            Extracted {batchProgress.records_extracted.toLocaleString()} records before failure
          </p>
        </div>
      )}
    </div>
  );
}
