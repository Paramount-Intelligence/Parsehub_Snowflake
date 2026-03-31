"use client";

import React, { useState, useEffect } from "react";
import Modal from "./Modal";
import MetadataProgressModal from "./MetadataProgressModal";
import AutoCompleteStatus from "./AutoCompleteStatus";
import { Play, AlertCircle, CheckCircle2, Loader } from "lucide-react";
import { startOrResumeScraping, getCheckpoint, getProjectMetadata } from "@/lib/scrapingApi";

interface RunDialogProps {
  isOpen: boolean;
  onClose: () => void;
  projectToken: string;
  projectTitle: string;
  projectURL?: string;
  onRunStart: (runToken: string, pages: number) => void;
  isLoading?: boolean;
}

export default function RunDialog({
  isOpen,
  onClose,
  projectToken,
  projectTitle,
  projectURL = "",
  onRunStart,
  isLoading = false,
}: RunDialogProps) {
  const [error, setError] = useState<string>("");
  const [isRunning, setIsRunning] = useState(false);
  const [checkpoint, setCheckpoint] = useState<any>(null);
  const [metadata, setMetadata] = useState<any>(null);
  const [batchRunToken, setBatchRunToken] = useState<string | null>(null);
  const [showBatchProgress, setShowBatchProgress] = useState(false);
  const [loadingData, setLoadingData] = useState(true);

  // Load checkpoint and metadata when dialog opens
  useEffect(() => {
    if (isOpen && projectToken) {
      loadData();
    }
  }, [isOpen, projectToken]);

  const loadData = async () => {
    setLoadingData(true);
    setError("");
    
    try {
      // Load checkpoint
      try {
        const ckpt = await getCheckpoint(projectToken);
        setCheckpoint(ckpt);
      } catch (err) {
        console.error("Failed to load checkpoint:", err);
        // Checkpoint failure is not critical - continue
      }

      // Load metadata
      try {
        const meta = await getProjectMetadata(projectToken);
        setMetadata(meta);
      } catch (err) {
        console.error("Failed to load metadata:", err);
        // Extract error message properly
        const errMsg = err instanceof Error ? err.message : String(err);
        if (errMsg.includes('404')) {
          setError('Project metadata not found. Make sure the project has been properly imported.');
        } else if (errMsg.includes('timeout')) {
          setError('Request timed out. Backend may be slow. Try again in a moment.');
        } else {
          setError('Failed to load project information. Please try again.');
        }
      }
    } finally {
      setLoadingData(false);
    }
  };

  const handleStart = async () => {
    setError("");
    setIsRunning(true);

    try {
      const result = await startOrResumeScraping(projectToken);

      if (result.success && result.run_token) {
        setBatchRunToken(result.run_token);
        setShowBatchProgress(true);
        onRunStart(result.run_token, result.total_pages || metadata?.total_pages || 0);
      } else {
        const errMsg = result.error || result.message || result.reason || "Failed to start scraping";
        if (errMsg.includes('already complete')) {
          setError('This project is already complete - all pages have been scraped!');
        } else if (errMsg.includes('not found')) {
          setError('Project not found. Please refresh and try again.');
        } else {
          setError(errMsg);
        }
      }
    } catch (err) {
      // Extract error message properly
      const errMsg = err instanceof Error ? err.message : String(err);
      if (errMsg.includes('timeout')) {
        setError('Request timed out. Backend is not responding. Start the backend and try again.');
      } else if (errMsg.includes('unreachable')) {
        setError('Backend API is unreachable. Make sure the backend server is running on port 5000.');
      } else {
        setError(errMsg || "Failed to start scraping");
      }
    } finally {
      setIsRunning(false);
    }
  };

  const handleResume = async () => {
    setError("");
    setIsRunning(true);

    try {
      const result = await startOrResumeScraping(projectToken);

      if (result.success && result.run_token) {
        setBatchRunToken(result.run_token);
        setShowBatchProgress(true);
        onRunStart(result.run_token, result.total_pages || metadata?.total_pages || 0);
      } else {
        const errMsg = result.error || result.message || result.reason || "Failed to resume scraping";
        if (errMsg.includes('already complete')) {
          setError('This project is already complete - all pages have been scraped!');
        } else if (errMsg.includes('not found')) {
          setError('Project not found. Please refresh and try again.');
        } else {
          setError(errMsg);
        }
      }
    } catch (err) {
      // Extract error message properly
      const errMsg = err instanceof Error ? err.message : String(err);
      if (errMsg.includes('timeout')) {
        setError('Request timed out. Backend is not responding. Start the backend and try again.');
      } else if (errMsg.includes('unreachable')) {
        setError('Backend API is unreachable. Make sure the backend server is running on port 5000.');
      } else {
        setError(errMsg || "Failed to resume scraping");
      }
    } finally {
      setIsRunning(false);
    }
  };

  const totalPagesMeta = metadata?.total_pages ?? 0
  const highestPage = checkpoint?.highest_successful_page ?? 0
  const pagesComplete =
    totalPagesMeta > 0 && highestPage >= totalPagesMeta
  const isComplete =
    Boolean(checkpoint?.is_project_complete) || pagesComplete
  const canResume = checkpoint && highestPage > 0 && !isComplete

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} title={`Start Scraping: ${projectTitle}`}>
        <div className="space-y-6">
          {/* Header Info */}
          <div className="bg-gradient-to-r from-blue-900/30 to-cyan-900/30 border border-blue-700/50 rounded-xl p-5 space-y-3">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center flex-shrink-0">
                <Play className="w-5 h-5 text-blue-400" />
              </div>
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-blue-300">
                  Metadata-Driven Resume Scraping
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Intelligent scraping with automatic checkpoint tracking and resume capability
                </p>
              </div>
            </div>
          </div>

          {/* Loading State */}
          {loadingData && (
            <div className="flex items-center justify-center py-6">
              <Loader className="w-5 h-5 text-blue-400 animate-spin mr-2" />
              <span className="text-sm text-slate-300">Loading project info...</span>
            </div>
          )}

          {/* Data Display */}
          {!loadingData && (
            <>
              {/* Project Info */}
              <div className="bg-slate-900/50 border border-slate-700 rounded-xl p-4 space-y-3">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Project Details</p>
                
                {metadata && (
                  <div className="space-y-2 text-sm">
                    {metadata.total_pages && (
                      <div className="flex justify-between items-center">
                        <span className="text-slate-400">Total Pages:</span>
                        <span className="font-semibold text-slate-200">{metadata.total_pages}</span>
                      </div>
                    )}
                    {metadata.total_products && (
                      <div className="flex justify-between items-center">
                        <span className="text-slate-400">Expected Records:</span>
                        <span className="font-semibold text-slate-200">{metadata.total_products.toLocaleString()}</span>
                      </div>
                    )}
                    {metadata.website_url && (
                      <div className="flex justify-between items-start gap-2">
                        <span className="text-slate-400">Website URL:</span>
                        <span className="font-mono text-xs text-blue-300 text-right break-all">{metadata.website_url}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Checkpoint Info */}
              {checkpoint && (
                <div className={`border rounded-xl p-4 space-y-3 ${
                  checkpoint.highest_successful_page > 0
                    ? "bg-emerald-900/20 border-emerald-700/50"
                    : "bg-slate-900/50 border-slate-700"
                }`}>
                  <p className="text-xs font-semibold uppercase tracking-wider">
                    {checkpoint.highest_successful_page > 0 ? (
                      <span className="text-emerald-400">✓ Progress Detected</span>
                    ) : (
                      <span className="text-slate-400">No Previous Progress</span>
                    )}
                  </p>
                  
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between items-center">
                      <span className={checkpoint.highest_successful_page > 0 ? "text-emerald-300" : "text-slate-400"}>
                        Highest Page Completed:
                      </span>
                      <span className="font-semibold text-slate-200">
                        {checkpoint.highest_successful_page || "None"}
                      </span>
                    </div>
                    
                    <div className="flex justify-between items-center">
                      <span className={checkpoint.highest_successful_page > 0 ? "text-emerald-300" : "text-slate-400"}>
                        Next Page to Scrape:
                      </span>
                      <span className="font-semibold text-blue-300">
                        Page {checkpoint.next_start_page ?? 1}
                      </span>
                    </div>

                    {metadata?.total_pages != null && (
                      <div className="flex justify-between items-center">
                        <span className="text-slate-400">Pages (metadata):</span>
                        <span className="font-semibold text-slate-200">
                          {highestPage} / {metadata.total_pages}
                        </span>
                      </div>
                    )}

                    {checkpoint.total_persisted_records !== undefined && (
                      <div className="flex justify-between items-center">
                        <span className="text-slate-400">Records Saved:</span>
                        <span className="font-semibold text-slate-200">
                          {checkpoint.total_persisted_records.toLocaleString()}
                          {metadata?.total_products != null && (
                            <span className="text-slate-500 font-normal">
                              {" "}
                              / {metadata.total_products.toLocaleString()} expected
                            </span>
                          )}
                        </span>
                      </div>
                    )}
                  </div>

                  {isComplete && (
                    <div className="flex items-center gap-2 p-3 bg-emerald-900/30 border border-emerald-700/50 rounded-lg">
                      <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                      <span className="text-sm font-medium text-emerald-300">
                        🎉 Project scraping is complete!
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* System Features */}
              <div className="bg-slate-900/30 border border-slate-700/50 rounded-xl p-4">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">System Features</p>
                <ul className="space-y-2 text-xs text-slate-400">
                  <li className="flex gap-2">
                    <span className="text-blue-400 font-bold">•</span>
                    <span>Automatic checkpoint tracking via database</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-blue-400 font-bold">•</span>
                    <span>Dynamic pagination pattern detection</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-blue-400 font-bold">•</span>
                    <span>Resume from any checkpoint without data loss</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-blue-400 font-bold">•</span>
                    <span>Email alerts on critical failures</span>
                  </li>
                </ul>
              </div>

              {/* Error Display */}
              {error && (
                <div className="bg-red-900/20 border border-red-700/50 rounded-xl p-4 space-y-2">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="text-sm font-semibold text-red-300">Error</p>
                      <p className="text-xs text-red-200 mt-1">{error}</p>
                      
                      {/* Diagnostic suggestions */}
                      {error.includes('404') && (
                        <p className="text-xs text-red-300 mt-2 p-2 bg-red-900/30 rounded">
                          💡 Project metadata not found. Try refreshing or check METADATA_DRIVEN_TROUBLESHOOTING.md
                        </p>
                      )}
                      
                      {error.includes('timeout') && (
                        <p className="text-xs text-red-300 mt-2 p-2 bg-red-900/30 rounded">
                          💡 Backend is slow. Check: backend logs | database connection | try again in 10 seconds
                        </p>
                      )}
                      
                      {error.includes('unreachable') && (
                        <p className="text-xs text-red-300 mt-2 p-2 bg-red-900/30 rounded">
                          💡 Backend not running. Start with: cd backend && python -m src.api.api_server
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex gap-3 justify-end pt-4 border-t border-slate-700/50">
                <button
                  onClick={onClose}
                  disabled={isRunning || isLoading}
                  className="px-6 py-3 text-slate-300 font-semibold border border-slate-600 rounded-xl hover:bg-slate-700/50 disabled:bg-slate-800 disabled:text-slate-500 disabled:cursor-not-allowed transition-all duration-200"
                >
                  Cancel
                </button>

                {canResume ? (
                  <button
                    onClick={handleResume}
                    disabled={isRunning || isLoading}
                    className="px-8 py-3 bg-gradient-to-r from-emerald-600 to-emerald-700 hover:from-emerald-700 hover:to-emerald-800 disabled:from-slate-700 disabled:to-slate-700 text-white font-semibold rounded-xl flex items-center gap-2 disabled:cursor-not-allowed transition-all duration-200 shadow-lg shadow-emerald-500/25"
                  >
                    {isRunning ? (
                      <>
                        <Loader className="w-4 h-4 animate-spin" />
                        Resuming...
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4" />
                        Resume Scraping
                      </>
                    )}
                  </button>
                ) : (
                  <button
                    onClick={handleStart}
                    disabled={isRunning || isLoading || isComplete}
                    className="px-8 py-3 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 disabled:from-slate-700 disabled:to-slate-700 text-white font-semibold rounded-xl flex items-center gap-2 disabled:cursor-not-allowed transition-all duration-200 shadow-lg shadow-blue-500/25"
                  >
                    {isRunning ? (
                      <>
                        <Loader className="w-4 h-4 animate-spin" />
                        Starting...
                      </>
                    ) : isComplete ? (
                      <>
                        <CheckCircle2 className="w-4 h-4" />
                        Complete
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4" />
                        Start Scraping
                      </>
                    )}
                  </button>
                )}
              </div>

              {/* Auto-Complete Status */}
              <AutoCompleteStatus 
                projectToken={projectToken}
                refreshInterval={10}
                className="mt-4"
              />
            </>
          )}
        </div>
      </Modal>

      {/* Metadata Progress Modal */}
      {showBatchProgress && batchRunToken && (
        <MetadataProgressModal
          isOpen={showBatchProgress}
          onClose={() => {
            setShowBatchProgress(false);
            onClose();
          }}
          projectToken={projectToken}
          projectTitle={projectTitle}
          metadata={metadata}
          startingPage={checkpoint?.next_start_page || 1}
          runToken={batchRunToken}
        />
      )}
    </>
  );
}
