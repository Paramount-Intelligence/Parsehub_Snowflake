"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Activity, CheckCircle, Clock, AlertCircle, Loader2 } from "lucide-react";
import apiClient from "@/lib/apiClient";

interface RunStatus {
  run_token: string;
  project_id: number;
  project_token?: string;
  starting_page: number;
  status: string;
  started_at: string;
  last_checked: string;
  attempts: number;
  auto_continue: boolean;
}

/** Live run info from ParseHub API (runs started outside this app) */
interface ParsehubLive {
  run_token?: string;
  status?: string;
  pages_scraped?: number;
  is_running?: boolean;
  source?: string;
}

interface HistoryItem {
  run_token: string;
  status: string;
  error?: string;
  records_persisted?: number;
  highest_page?: number;
  project_complete?: boolean;
  completed_at: string;
}

interface AutoCompleteStatusData {
  success: boolean;
  service_running: boolean;
  active_runs: RunStatus[];
  active_count: number;
  recent_history: HistoryItem[];
  parsehub_live?: ParsehubLive | null;
}

interface SnowflakeLiveRun {
  success?: boolean;
  pages_scraped?: number;
  total_pages?: number | null;
  max_pages_seen?: number;
  highest_source_page?: number | null;
  status?: string | null;
  is_complete?: boolean;
  complete_reason?: string | null;
  run_token?: string | null;
}

interface AutoCompleteStatusProps {
  projectToken?: string; // If provided, filter to show only this project's runs
  refreshInterval?: number; // Seconds between refreshes (default: 10)
  className?: string;
}

export default function AutoCompleteStatus({
  projectToken,
  refreshInterval = 10,
  className = "",
}: AutoCompleteStatusProps) {
  const [status, setStatus] = useState<AutoCompleteStatusData | null>(null);
  const [liveRun, setLiveRun] = useState<SnowflakeLiveRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const fetchStatus = useCallback(async () => {
    try {
      const params = projectToken
        ? { project_token: projectToken }
        : undefined;
      const [acRes, liveRes] = await Promise.all([
        apiClient.get("/api/projects/auto-complete/status", { params }),
        projectToken
          ? apiClient
              .get(`/api/projects/${projectToken}/runs/live`)
              .catch(() => ({ data: null }))
          : Promise.resolve({ data: null }),
      ]);
      if (acRes.status === 200) {
        setStatus(acRes.data);
        setLastUpdated(new Date());
        setError(null);
      }
      if (liveRes && "data" in liveRes && liveRes.data) {
        setLiveRun(liveRes.data as SnowflakeLiveRun);
      } else {
        setLiveRun(null);
      }
    } catch {
      setError((prev) => prev ?? "Failed to fetch status");
    } finally {
      setLoading(false);
    }
  }, [projectToken]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, refreshInterval * 1000);
    return () => clearInterval(interval);
  }, [fetchStatus, refreshInterval]);

  // Match runs to this project by project_token (run_token is NOT the project token)
  const filteredRuns =
    projectToken && status?.active_runs
      ? status.active_runs.filter((run) => run.project_token === projectToken)
      : status?.active_runs || [];

  const hasActiveRuns = filteredRuns.length > 0;
  const parsehubLive = status?.parsehub_live;
  const showParsehubRunning =
    !!projectToken &&
    parsehubLive?.is_running &&
    parsehubLive?.run_token &&
    !hasActiveRuns;
  const hasHistory = status?.recent_history && status.recent_history.length > 0;

  // Format relative time
  const formatTime = (isoString: string) => {
    if (!isoString) return "Unknown";
    const date = new Date(isoString);
    const now = new Date();
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000);
    
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  };

  // Get status icon
  const getStatusIcon = (runStatus: string) => {
    switch (runStatus) {
      case "monitoring":
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      case "completed":
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case "failed":
      case "error":
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Activity className="w-4 h-4 text-gray-500" />;
    }
  };

  if (loading && !status) {
    return (
      <div className={`bg-slate-900 border border-slate-700 rounded-lg p-4 ${className}`}>
        <div className="flex items-center gap-2 text-slate-400">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">Loading auto-complete status...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-slate-900 border border-slate-700 rounded-lg p-4 ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-blue-500" />
          <h3 className="font-semibold text-slate-200">Auto-Complete Monitor</h3>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Clock className="w-3 h-3" />
          <span>Updated {formatTime(lastUpdated.toISOString())}</span>
          {status?.service_running && (
            <span
              className="flex items-center gap-1 text-green-500"
              title="Background auto-complete service is running (not the same as a ParseHub run)"
            >
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              Service on
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="text-xs text-red-400 bg-red-900/20 rounded p-2 mb-3">
          {error}
        </div>
      )}

      {/* Snowflake + ParseHub live progress (persisted run row) */}
      {projectToken && liveRun?.success && (
        <div className="mb-4 rounded-lg border border-cyan-500/30 bg-cyan-500/5 p-3">
          <h4 className="mb-2 text-xs font-medium uppercase text-cyan-400">
            Live progress (Snowflake + ParseHub)
          </h4>
          <div className="grid grid-cols-2 gap-2 text-xs text-slate-300">
            <div>
              <span className="text-slate-500">Pages scraped</span>
              <p className="font-mono text-lg text-white">
                {liveRun.max_pages_seen ?? liveRun.pages_scraped ?? "—"}
                {liveRun.total_pages != null && liveRun.total_pages !== undefined && (
                  <span className="text-slate-500">
                    {" "}
                    / {liveRun.total_pages}
                  </span>
                )}
              </p>
            </div>
            <div>
              <span className="text-slate-500">ParseHub status</span>
              <p className="font-medium text-cyan-200">
                {liveRun.status ?? "—"}
              </p>
            </div>
            {liveRun.highest_source_page != null && liveRun.highest_source_page !== undefined && (
              <div className="col-span-2 text-slate-400">
                Highest page in stored data:{" "}
                <span className="text-slate-200">{liveRun.highest_source_page}</span>
              </div>
            )}
            {liveRun.is_complete && (
              <div className="col-span-2 rounded bg-emerald-500/15 px-2 py-1 text-emerald-300">
                Completed — {liveRun.complete_reason ?? "Target pages reached"}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Active Runs (registered with this backend for auto-persist) */}
      {hasActiveRuns ? (
        <div className="space-y-2 mb-4">
          <h4 className="text-xs font-medium text-slate-400 uppercase">
            Active Runs ({filteredRuns.length})
          </h4>
          {filteredRuns.map((run) => (
            <div
              key={run.run_token}
              className="bg-slate-800/50 rounded p-3 border border-slate-700/50"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {getStatusIcon(run.status)}
                  <span className="text-sm font-medium text-slate-200">
                    Page {run.starting_page}
                  </span>
                  <span className="text-xs text-slate-500">
                    (ID: {run.run_token.substring(0, 8)}...)
                  </span>
                </div>
                <span className="text-xs text-slate-500">
                  {formatTime(run.started_at)}
                </span>
              </div>
              <div className="flex items-center gap-4 text-xs text-slate-400">
                <span>Status: {run.status}</span>
                <span>Attempts: {run.attempts}</span>
                {run.auto_continue && (
                  <span className="text-blue-400">Auto-continue enabled</span>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : showParsehubRunning ? (
        <div className="space-y-2 mb-4">
          <h4 className="text-xs font-medium text-slate-400 uppercase">
            Running on ParseHub
          </h4>
          <div className="bg-amber-500/10 rounded p-3 border border-amber-500/30">
            <div className="flex items-center gap-2 mb-2">
              <Loader2 className="w-4 h-4 text-amber-400 animate-spin" />
              <span className="text-sm text-slate-200">
                Live run detected — not registered for auto-persist on this server
              </span>
            </div>
            <div className="text-xs text-slate-400 space-y-1">
              <p>
                Status:{" "}
                <span className="text-amber-300">{parsehubLive?.status}</span>
              </p>
              <p>
                Run: {parsehubLive?.run_token?.substring(0, 12)}… · Pages:{" "}
                {parsehubLive?.pages_scraped ?? "—"}
              </p>
              <p className="text-slate-500 mt-2">
                Start scraping from this dialog (or use Run Project here) so the
                backend can register the run and save results when it finishes.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-sm text-slate-500 mb-4">
          No active runs being monitored for this project
        </div>
      )}

      {/* Recent History */}
      {hasHistory && (
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-slate-400 uppercase">
            Recent History
          </h4>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {status?.recent_history.slice(0, 5).map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between text-xs p-2 rounded bg-slate-800/30"
              >
                <div className="flex items-center gap-2">
                  {getStatusIcon(item.status)}
                  <span className="text-slate-300">
                    {item.status === "completed" ? (
                      <>
                        ✅ {item.records_persisted || 0} records saved
                        {item.project_complete && (
                          <span className="text-green-400 ml-1">(Complete!)</span>
                        )}
                      </>
                    ) : item.status === "failed" ? (
                      <span className="text-red-400">Failed: {item.error}</span>
                    ) : (
                      item.status
                    )}
                  </span>
                </div>
                <span className="text-slate-500">
                  {formatTime(item.completed_at)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Info */}
      <div className="mt-3 pt-3 border-t border-slate-700/50 text-xs text-slate-500">
        <p>
          Runs are automatically monitored and data is persisted when complete.
          You can close the browser - scraping continues in the background.
        </p>
      </div>
    </div>
  );
}
