"use client";
import apiClient from "@/lib/apiClient";

import React, { useState } from "react";
import Modal from "./Modal";
import ProgressModal from "./ProgressModal";
import { Play, AlertCircle, Zap } from "lucide-react";

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
  const [pages, setPages] = useState<string>("");
  const [useIncremental, setUseIncremental] = useState(false);
  const [totalPages, setTotalPages] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [isRunning, setIsRunning] = useState(false);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [showProgress, setShowProgress] = useState(false);
  const [metadataId, setMetadataId] = useState<number | null>(null);

  // Load metadata when dialog opens
  React.useEffect(() => {
    if (isOpen && projectToken) {
      const loadMetadata = async () => {
        try {
          const response = await fetch(`/api/metadata?project_token=${projectToken}`);
          const data = await response.json();
          
          if (data.success && data.records && data.records.length > 0) {
            const metadata = data.records[0];
            setMetadataId(metadata.id);
            
            // Pre-fill pages with total_pages from metadata
            if (metadata.total_pages) {
              setPages(metadata.total_pages.toString());
            }
          }
        } catch (err) {
          console.error("Failed to load metadata:", err);
        }
      };
      
      loadMetadata();
    }
  }, [isOpen, projectToken]);

  const handleRun = async () => {
    const pagesNum = parseInt(pages);
    const totalPagesNum = parseInt(totalPages);

    if (!pages || isNaN(pagesNum) || pagesNum < 1) {
      setError("Please enter a valid number of pages");
      return;
    }

    if (
      useIncremental &&
      (!totalPages || isNaN(totalPagesNum) || totalPagesNum < pagesNum)
    ) {
      setError(
        "Total pages must be greater than or equal to pages per iteration",
      );
      return;
    }

    setError("");
    setIsRunning(true);

    try {
      if (useIncremental) {
        // Fetch project details from ParseHub to get the URL if not provided
        let urlToUse = projectURL;
        if (!urlToUse) {
          try {
            const projectDetailsRes = await apiClient.get(
              `/api/projects/${projectToken}`,
            );
            if (projectDetailsRes.status === 200) {
              const projectData = projectDetailsRes.data;
              urlToUse =
                projectData.project?.url ||
                projectData.project?.main_site ||
                "";
            }
          } catch (err) {
            console.error("Failed to fetch project URL:", err);
            // Continue with empty URL, let backend handle the error
          }
        }

        // Start incremental scraping
        const response = await apiClient.post("/api/projects/incremental", {
          project_token: projectToken,
          project_name: projectTitle,
          original_url: urlToUse,
          total_pages: totalPagesNum,
          pages_per_iteration: pagesNum,
        });

        if (!response.status || response.status >= 400) {
          throw new Error("Failed to start incremental scraping");
        }

        const data = response.data;

        if (data.success) {
          setPages("");
          setTotalPages("");
          setUseIncremental(false);
          setSessionId(data.session_id);
          setShowProgress(true);
          onClose();
        } else {
          setError(data.error || "Failed to start incremental scraping");
        }
      } else {
        // Regular run
        const response = await apiClient.post("/api/projects/run", {
          token: projectToken,
          pages: pagesNum,
        });

        if (!response.status || response.status >= 400) {
          throw new Error("Failed to start run");
        }

        const data = response.data;

        if (data.success && data.run_token) {
          // Update metadata with the pages value
          if (metadataId) {
            try {
              await fetch(`/api/metadata/${metadataId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ total_pages: pagesNum })
              });
            } catch (err) {
              console.error("Failed to update metadata:", err);
              // Don't fail the run just because metadata update failed
            }
          }
          
          onRunStart(data.run_token, pagesNum);
          setPages("");
          onClose();
        } else {
          setError(data.error || "Failed to start run");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsRunning(false);
    }
  };

  const handlePagesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPages(e.target.value);
    setError("");
  };

  const handleTotalPagesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTotalPages(e.target.value);
    setError("");
  };

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} title={`Run: ${projectTitle}`}>
        <div className="space-y-6">
          {/* Incremental Scraping Toggle */}
          <div className="border-b border-slate-700/50 pb-5">
            <div className="flex items-start gap-3">
              <input
                type="checkbox"
                id="incremental-toggle"
                checked={useIncremental}
                onChange={(e) => {
                  setUseIncremental(e.target.checked);
                  setError("");
                }}
                disabled={isRunning || isLoading}
                className="w-5 h-5 text-blue-600 bg-slate-700 border-slate-600 rounded focus:ring-2 focus:ring-blue-500 mt-0.5"
              />
              <div className="flex-1">
                <label
                  htmlFor="incremental-toggle"
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <Zap className="w-5 h-5 text-amber-500" />
                  <span className="font-semibold text-slate-200 text-base">
                    Enable Incremental Scraping
                  </span>
                </label>
                <p className="text-sm text-slate-400 mt-1.5">
                  Automatically creates and runs multiple jobs to scrape all
                  pages, combining results
                </p>
              </div>
            </div>
          </div>

          {/* Regular Pages Input */}
          {!useIncremental && (
            <div className="space-y-3">
              <label className="block text-sm font-semibold text-slate-300">
                Number of Pages to Scrape
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  value={pages}
                  onChange={handlePagesChange}
                  disabled={isRunning || isLoading}
                  className="flex-1 px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-slate-200 font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-slate-800 disabled:text-slate-500 transition-all"
                  placeholder="Enter number of pages"
                />
                <span className="text-sm text-slate-400 font-medium px-3 py-3 bg-slate-800/50 rounded-lg border border-slate-700">
                  pages
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Specify how many pages to scrape in a single run.
              </p>
            </div>
          )}

          {/* Incremental Scraping Inputs */}
          {useIncremental && (
            <div className="space-y-5 bg-gradient-to-br from-amber-900/20 to-orange-900/20 border border-amber-700/30 rounded-xl p-5">
              <div className="space-y-3">
                <label className="block text-sm font-semibold text-slate-300">
                  Pages per Iteration
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    value={pages}
                    onChange={handlePagesChange}
                    disabled={isRunning || isLoading}
                    className="flex-1 px-4 py-3 bg-slate-900/50 border border-amber-600/50 rounded-xl text-slate-200 font-semibold focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent disabled:bg-slate-800 disabled:text-slate-500 transition-all"
                    placeholder="e.g., 5"
                  />
                  <span className="text-sm text-slate-300 font-medium px-3 py-3 bg-slate-800/50 rounded-lg border border-slate-700">
                    pages/run
                  </span>
                </div>
                <p className="text-xs text-slate-400">
                  How many pages to scrape per ParseHub project iteration
                </p>
              </div>

              <div className="space-y-3">
                <label className="block text-sm font-semibold text-slate-300">
                  Total Pages Target
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    value={totalPages}
                    onChange={handleTotalPagesChange}
                    disabled={isRunning || isLoading}
                    className="flex-1 px-4 py-3 bg-slate-900/50 border border-amber-600/50 rounded-xl text-slate-200 font-semibold focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent disabled:bg-slate-800 disabled:text-slate-500 transition-all"
                    placeholder="e.g., 50"
                  />
                  <span className="text-sm text-slate-300 font-medium px-3 py-3 bg-slate-800/50 rounded-lg border border-slate-700">
                    pages total
                  </span>
                </div>
                <p className="text-xs text-slate-400">
                  Total pages you want to scrape (system will create{" "}
                  {pages && totalPages
                    ? Math.ceil(parseInt(totalPages) / parseInt(pages))
                    : "?"}{" "}
                  iterations)
                </p>
              </div>

              <div className="bg-slate-900/50 border border-amber-600/30 rounded-xl p-4">
                <p className="text-sm font-semibold text-amber-300 mb-2">
                  📊 Scraping Plan
                </p>
                <p className="text-sm text-slate-300">
                  Will create{" "}
                  <strong className="text-amber-400">
                    {pages && totalPages
                      ? Math.ceil(parseInt(totalPages) / parseInt(pages))
                      : "?"}
                  </strong>{" "}
                  automatic runs of{" "}
                  <strong className="text-amber-400">
                    {pages || "?"} pages each
                  </strong>{" "}
                  to reach{" "}
                  <strong className="text-amber-400">
                    {totalPages || "?"} pages
                  </strong>
                </p>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-start gap-3 p-4 bg-red-900/20 border border-red-700/50 rounded-xl">
              <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
              <span className="text-sm text-red-300 font-medium">{error}</span>
            </div>
          )}

          {!useIncremental && (
            <div className="bg-blue-900/20 border border-blue-700/30 rounded-xl p-4">
              <p className="text-sm text-blue-300">
                <strong className="text-blue-400">
                  🔄 Auto-Recovery Enabled:
                </strong>{" "}
                If the scraping stops before reaching all {pages || "?"} pages,
                you can resume without losing progress.
              </p>
            </div>
          )}

          {useIncremental && (
            <div className="bg-amber-900/20 border border-amber-700/30 rounded-xl p-4">
              <p className="text-sm text-amber-300">
                <strong className="text-amber-400">
                  ⚡ Automated Pagination:
                </strong>{" "}
                URL pattern will be detected automatically. New projects will be
                created for each iteration and combined results will be saved.
              </p>
            </div>
          )}

          <div className="flex gap-3 justify-end pt-4 border-t border-slate-700/50">
            <button
              onClick={onClose}
              disabled={isRunning || isLoading}
              className="px-6 py-3 text-slate-300 font-semibold border border-slate-600 rounded-xl hover:bg-slate-700/50 disabled:bg-slate-800 disabled:text-slate-500 disabled:cursor-not-allowed transition-all duration-200"
            >
              Cancel
            </button>
            <button
              onClick={handleRun}
              disabled={isRunning || isLoading}
              className={`px-6 py-3 text-white font-semibold rounded-xl flex items-center gap-2 disabled:cursor-not-allowed transition-all duration-200 shadow-lg ${useIncremental
                ? "bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-700 hover:to-orange-700 disabled:from-slate-700 disabled:to-slate-700 shadow-amber-500/25"
                : "bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 disabled:from-slate-700 disabled:to-slate-700 shadow-blue-500/25"
                }`}
            >
              <Play className="w-4 h-4" />
              {isRunning || isLoading
                ? "Starting..."
                : useIncremental
                  ? "Start Incremental Scrape"
                  : "Start Run"}
            </button>
          </div>
        </div>
      </Modal>

      <ProgressModal
        isOpen={showProgress}
        onClose={() => setShowProgress(false)}
        sessionId={sessionId || 0}
        projectName={projectTitle}
      />
    </>
  );
}
