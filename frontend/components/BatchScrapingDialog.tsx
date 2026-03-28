"use client";

import React, { useState, useEffect } from "react";
import Modal from "./Modal";
import BatchProgress from "./BatchProgress";
import BatchMonitoringPanel from "./BatchMonitoringPanel";
import { Play, AlertCircle, Zap, CheckCircle, RotateCcw } from "lucide-react";
import apiClient from "@/lib/apiClient";

interface BatchScrapingDialogProps {
  isOpen: boolean;
  onClose: () => void;
  projectToken: string;
  projectName: string;
  projectURL?: string;
  onScrapingStart: (sessionId: string) => void;
  isLoading?: boolean;
}

/**
 * BatchScrapingDialog - Start or resume batch-based scraping
 * 
 * Features:
 * - Start new batch scraping from page 1
 * - Resume from last checkpoint
 * - Shows checkpoint information if available
 * - Starts batch processing (10-page chunks)
 * - Real-time batch monitoring with progress and data extraction
 */
export default function BatchScrapingDialog({
  isOpen,
  onClose,
  projectToken,
  projectName,
  projectURL = "",
  onScrapingStart,
  isLoading = false,
}: BatchScrapingDialogProps) {
  const [checkpoint, setCheckpoint] = useState<any>(null);
  const [resumeMode, setResumeMode] = useState(false);
  const [error, setError] = useState<string>("");
  const [isStarting, setIsStarting] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeRunToken, setActiveRunToken] = useState<string | null>(null);
  const [showProgress, setShowProgress] = useState(false);

  // Load checkpoint information when dialog opens
  useEffect(() => {
    if (isOpen && projectToken) {
      const loadCheckpoint = async () => {
        try {
          const response = await apiClient.get(
            `/api/projects/${projectToken}/checkpoint`
          );
          if (response.status === 200) {
            setCheckpoint(response.data);
            // If there's a completed page > 0, resume mode is available
            if (response.data.last_completed_page > 0) {
              setResumeMode(true);
            }
          }
        } catch (err) {
          console.error("Failed to load checkpoint:", err);
          setCheckpoint(null);
        }
      };

      loadCheckpoint();
    }
  }, [isOpen, projectToken]);

  const handleStartScraping = async (resume: boolean) => {
    setError("");
    setIsStarting(true);

    try {
      let urlToUse = projectURL;

      // Fetch project URL from backend if not provided
      if (!urlToUse) {
        try {
          const projectRes = await apiClient.get(`/api/projects/${projectToken}`);
          if (projectRes.status === 200) {
            urlToUse =
              projectRes.data.project?.url ||
              projectRes.data.project?.main_site ||
              "";
          }
        } catch (err) {
          console.error("Failed to fetch project URL:", err);
        }
      }

      if (!urlToUse) {
        setError("Please provide a URL for batch scraping");
        setIsStarting(false);
        return;
      }

      // Start batch scraping
      const response = await apiClient.post("/api/projects/batch/start", {
        project_token: projectToken,
        project_name: projectName,
        base_url: urlToUse,
        resume_from_checkpoint: resume,
      });

      if (response.status !== 200) {
        throw new Error(response.data?.error || "Failed to start batch scraping");
      }

      const data = response.data;
      const sessionId = data.session_id || data.sessionId;
      const runToken = data.run_token;

      if (sessionId) {
        setActiveSessionId(sessionId);
        setActiveRunToken(runToken);
        setShowProgress(true);
        onScrapingStart(sessionId);
        
        // Close dialog after session starts
        setTimeout(() => {
          onClose();
        }, 1000);
      } else {
        setError("No session ID returned from backend");
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "An error occurred";
      setError(errorMsg);
      console.error("Error starting batch scraping:", err);
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} title={`Batch Scraping: ${projectName}`}>
        <div className="space-y-6">
          {/* Batch Scraping Info */}
          <div className="border-b border-slate-700/50 pb-5">
            <div className="flex items-start gap-3">
              <Zap className="w-5 h-5 text-blue-600 mt-0.5" />
              <div className="flex-1">
                <h3 className="font-semibold text-slate-200 text-base">
                  Batch-Based Pagination
                </h3>
                <p className="text-sm text-slate-400 mt-1.5">
                  Scraping processes the website in batches of 10 pages at a time.
                  Checkpoints are saved after each completed batch, allowing you to
                  resume from where the scraper stopped.
                </p>
              </div>
            </div>
          </div>

          {/* Checkpoint Status */}
          {checkpoint && checkpoint.last_completed_page > 0 ? (
            <div className="bg-gradient-to-br from-green-900/20 to-emerald-900/20 border border-green-700/30 rounded-lg p-4 space-y-2">
              <div className="flex items-center gap-2 text-sm font-semibold text-green-300">
                <CheckCircle className="w-4 h-4" />
                Checkpoint Found
              </div>
              <div className="text-sm text-slate-300 space-y-1">
                <p>
                  <span className="text-slate-400">Last Completed Page:</span>{" "}
                  <span className="font-semibold">{checkpoint.last_completed_page}</span>
                </p>
                <p>
                  <span className="text-slate-400">Next Batch Starts:</span>{" "}
                  <span className="font-semibold">Page {checkpoint.next_start_page}</span>
                </p>
                <p>
                  <span className="text-slate-400">Batches Completed:</span>{" "}
                  <span className="font-semibold">
                    {checkpoint.total_batches_completed}
                  </span>
                </p>
                {checkpoint.failed_batches > 0 && (
                  <p className="text-orange-400">
                    <span className="text-slate-400">Failed Batches:</span>{" "}
                    <span className="font-semibold">{checkpoint.failed_batches}</span>
                  </p>
                )}
                <p className="text-xs text-slate-500 mt-2">
                  Last checkpoint: {new Date(checkpoint.checkpoint_timestamp).toLocaleString()}
                </p>
              </div>
            </div>
          ) : (
            <div className="bg-gradient-to-br from-blue-900/20 to-cyan-900/20 border border-blue-700/30 rounded-lg p-4">
              <p className="text-sm text-slate-300">
                No checkpoint found. Starting fresh scraping from page 1.
              </p>
            </div>
          )}

          {/* Error Alert */}
          {error && (
            <div className="bg-red-900/30 border border-red-700/50 rounded-lg p-4 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-300">{error}</p>
            </div>
          )}

          {/* URL Info */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
            <p className="text-xs text-slate-500 font-medium mb-1">Website URL</p>
            <p className="text-sm text-slate-300 truncate font-mono">
              {projectURL || "(will be fetched from project)"}
            </p>
          </div>

          {/* Action Buttons */}
          <div className="space-y-3 pt-2">
            {checkpoint && checkpoint.last_completed_page > 0 && (
              <button
                onClick={() => handleStartScraping(true)}
                disabled={isStarting || isLoading}
                className="w-full px-4 py-3 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-lg hover:from-green-700 hover:to-emerald-700 disabled:from-slate-600 disabled:to-slate-700 disabled:text-slate-400 font-semibold transition-all flex items-center justify-center gap-2"
              >
                <RotateCcw className="w-4 h-4" />
                {isStarting ? "Resuming..." : `Resume from Checkpoint (Page ${checkpoint.next_start_page})`}
              </button>
            )}

            <button
              onClick={() => handleStartScraping(false)}
              disabled={isStarting || isLoading}
              className="w-full px-4 py-3 bg-gradient-to-r from-blue-600 to-cyan-600 text-white rounded-lg hover:from-blue-700 hover:to-cyan-700 disabled:from-slate-600 disabled:to-slate-700 disabled:text-slate-400 font-semibold transition-all flex items-center justify-center gap-2"
            >
              <Play className="w-4 h-4" />
              {isStarting ? "Starting..." : "Start Fresh Scraping"}
            </button>
          </div>

          <p className="text-xs text-slate-500 text-center pt-2">
            📧 API failures will send email notifications to: {process.env.NEXT_PUBLIC_ERROR_EMAIL || "configured email"}
          </p>
        </div>
      </Modal>

      {/* Progress Modal */}
      {showProgress && activeSessionId && (
        <Modal
          isOpen={showProgress}
          onClose={() => setShowProgress(false)}
          title="Batch Scraping in Progress"
        >
          <div className="space-y-6">
            {/* Batch Monitoring Panel */}
            {activeRunToken && (
              <BatchMonitoringPanel runToken={activeRunToken} />
            )}
            
            {/* Batch Progress Component */}
            <BatchProgress
              projectToken={projectToken}
              projectName={projectName}
              sessionId={activeSessionId}
              isActive={true}
            />
            
            <button
              onClick={() => setShowProgress(false)}
              className="w-full px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors"
            >
              Close
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
