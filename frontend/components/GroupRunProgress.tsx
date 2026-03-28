"use client";
import { useState } from "react";
import { X, CheckCircle2, AlertCircle, ChevronDown, Copy } from "lucide-react";

interface BatchResult {
  token: string;
  success: boolean;
  run_token?: string;
  status?: string;
  error?: string;
}

interface BatchResults {
  success: boolean;
  total_projects: number;
  successful: number;
  failed: number;
  results: BatchResult[];
}

interface GroupRunProgressProps {
  groupRunId: string;
  brand: string;
  isOpen: boolean;
  onClose: () => void;
  results?: BatchResults;
}

export default function GroupRunProgress({
  brand,
  isOpen,
  onClose,
  results,
}: GroupRunProgressProps) {
  const [expandedErrors, setExpandedErrors] = useState<Set<string>>(new Set());
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  const toggleErrorExpand = (token: string) => {
    const newSet = new Set(expandedErrors);
    if (newSet.has(token)) {
      newSet.delete(token);
    } else {
      newSet.add(token);
    }
    setExpandedErrors(newSet);
  };

  const copyToClipboard = (text: string, token: string) => {
    navigator.clipboard.writeText(text);
    setCopiedToken(token);
    setTimeout(() => setCopiedToken(null), 2000);
  };

  if (!isOpen || !results) return null;

  const progressPercent = results.success
    ? 100
    : Math.round((results.successful / results.total_projects) * 100) || 0;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-slate-800 rounded-lg shadow-2xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto border border-slate-700">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-100">Batch Run Results</h2>
            <p className="text-slate-400 text-sm mt-1">{brand}</p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200"
          >
            <X size={24} />
          </button>
        </div>

        {/* Overall Progress Bar */}
        <div className="mb-6">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-semibold text-slate-200">
              Completion Status
            </span>
            <span className="text-sm text-slate-400">
              {results.successful}/{results.total_projects} completed
            </span>
          </div>
          <div className="w-full bg-slate-700 rounded-full h-3">
            <div
              className={`h-3 rounded-full transition-all ${
                results.failed > 0 ? "bg-orange-500" : "bg-green-500"
              }`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className="flex gap-6 mt-3 text-sm">
            <span className="text-green-400 font-medium">
              ✓ {results.successful} successful
            </span>
            <span className={`font-medium ${results.failed > 0 ? "text-orange-400" : "text-green-400"}`}>
              {results.failed > 0 ? `✗ ${results.failed} failed` : "Perfect! All projects started."}
            </span>
          </div>
        </div>

        {/* Status Badge */}
        <div className="mb-6">
          <span
            className={`px-3 py-1 rounded text-xs font-semibold ${
              results.success
                ? "bg-green-900/50 text-green-300 border border-green-700"
                : "bg-orange-900/50 text-orange-300 border border-orange-700"
            }`}
          >
            {results.success ? "All Projects Started" : "Some Projects Failed"}
          </span>
        </div>

        {/* Error Summary Alert */}
        {results.failed > 0 && (
          <div className="mb-4 p-3 bg-orange-900/20 border border-orange-700/50 rounded-lg">
            <div className="flex items-start gap-2">
              <AlertCircle size={18} className="text-orange-400 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-orange-300 font-semibold text-sm">
                  {results.failed} project(s) failed
                </p>
                <p className="text-orange-400 text-xs mt-1">
                  Verify project tokens are valid, API key is correct, and projects exist in ParseHub
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Project Results List */}
        <div>
          <h3 className="font-semibold mb-3 text-slate-200">
            Projects ({results.total_projects})
          </h3>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {results.results?.map((project: BatchResult) => (
              <div
                key={project.token}
                className="flex items-start gap-3 p-3 bg-slate-700/30 rounded border border-slate-600 hover:border-slate-500 transition-colors"
              >
                {/* Status Icon */}
                <div className="flex-shrink-0 pt-0.5">
                  {project.success ? (
                    <CheckCircle2 size={20} className="text-green-400" />
                  ) : (
                    <AlertCircle size={20} className="text-orange-400" />
                  )}
                </div>

                {/* Project Info */}
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm text-slate-100 truncate">
                    {project.token}
                  </div>

                  {project.success ? (
                    <>
                      {project.run_token && (
                        <div className="text-slate-400 text-xs mt-1 flex items-center gap-2">
                          <span className="truncate">
                            Run Token: {project.run_token}
                          </span>
                          <button
                            onClick={() =>
                              copyToClipboard(project.run_token || "", project.token)
                            }
                            className="text-slate-500 hover:text-slate-300 transition-colors flex-shrink-0"
                            title="Copy run token"
                          >
                            <Copy size={14} />
                          </button>
                          {copiedToken === project.token && (
                            <span className="text-green-400 text-xs">Copied!</span>
                          )}
                        </div>
                      )}
                      {project.status && (
                        <div className="text-slate-400 text-xs mt-1">
                          Status: {project.status}
                        </div>
                      )}
                    </>
                  ) : (
                    <div>
                      {project.error && (
                        <div>
                          {project.error.length > 80 ? (
                            <button
                              onClick={() => toggleErrorExpand(project.token)}
                              className="text-orange-400 text-xs hover:text-orange-300 flex items-center gap-1 mt-1 transition-colors"
                            >
                              <ChevronDown
                                size={14}
                                className={`transform transition-transform ${
                                  expandedErrors.has(project.token)
                                    ? "rotate-180"
                                    : ""
                                }`}
                              />
                              {expandedErrors.has(project.token)
                                ? "Hide error"
                                : "Show error"}
                            </button>
                          ) : (
                            <div className="text-orange-400 text-xs mt-1">
                              {project.error}
                            </div>
                          )}
                          {expandedErrors.has(project.token) && (
                            <div className="text-orange-400 text-xs mt-1 p-2 bg-orange-900/20 rounded border border-orange-700/50 break-words">
                              {project.error}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Status Label */}
                <span
                  className={`text-xs font-semibold px-2 py-1 rounded flex-shrink-0 ${
                    project.success
                      ? "bg-green-900/50 text-green-300 border border-green-700"
                      : "bg-orange-900/50 text-orange-300 border border-orange-700"
                  }`}
                >
                  {project.success ? "Started" : "Failed"}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Close Button */}
        <button
          onClick={onClose}
          className="w-full mt-6 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors font-medium"
        >
          Close
        </button>
      </div>
    </div>
  );
}
