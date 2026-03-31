"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  TrendingUp,
  Zap,
  Download,
  AlertCircle,
  BarChart3,
  Play,
  Filter,
  X,
  RefreshCw,
  WifiOff,
} from "lucide-react";
import ProjectsList from "@/components/ProjectsList";
import StatsCard from "@/components/StatsCard";
import Header from "@/components/Header";
import AllProjectsAnalyticsModal from "@/components/AllProjectsAnalyticsModal";
import apiClient from "@/lib/apiClient";
import axios from "axios";

import RunDialog from "@/components/RunDialog";
import { useRealTimeMonitoring } from "@/lib/useRealTimeMonitoring";

/**
 * Extract a human-readable message from anything that can be thrown.
 * apiClient rejects with a plain object { message, status, data, ... }
 * (not an Error instance), so we must check .message before String().
 */
function extractErrorMessage(err: unknown): string {
  if (!err) return "An unexpected error occurred.";
  if (err instanceof Error) return err.message;
  if (typeof err === "object") {
    const e = err as Record<string, unknown>;
    if (typeof e.message === "string" && e.message) return e.message;
    if (typeof e.error === "string" && e.error) return e.error;
  }
  return "An unexpected error occurred. Please try again.";
}

/** True when the error is almost certainly a 502/503 from a cold backend. */
function isBackendDown(err: unknown): boolean {
  const msg = extractErrorMessage(err).toLowerCase();
  return (
    msg.includes("502") ||
    msg.includes("503") ||
    msg.includes("unreachable") ||
    msg.includes("failed to fetch") ||
    msg.includes("network error") ||
    msg.includes("backend")
  );
}

/** Aborted request — timeout, navigation, HMR, or explicit abort. Not a server failure. */
function isRequestCanceled(err: unknown): boolean {
  if (axios.isCancel(err)) return true;
  if (err instanceof DOMException && err.name === "AbortError") return true;
  if (typeof err === "object" && err !== null) {
    const e = err as Record<string, unknown>;
    const orig = e.originalError as { code?: string; name?: string } | undefined;
    if (orig?.code === "ERR_CANCELED" || orig?.name === "CanceledError") return true;
  }
  const msg = extractErrorMessage(err).toLowerCase();
  return (
    msg === "canceled" ||
    msg === "cancelled" ||
    msg.includes("request aborted") ||
    msg.includes("the user aborted a request")
  );
}

interface Project {
  token: string;
  title: string;
  owner_email: string;
  projecturl?: string;
  main_site?: string;
  metadata?: {
    id: number;
    total_pages?: number;
    total_products?: number;
  };
  last_run: {
    status: string;
    pages: number;
    start_time: string;
    run_token: string;
  } | null;
}

interface Stats {
  total: number;
  running: number;
  completed: number;
  queued: number;
}

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [stats, setStats] = useState<Stats>({
    total: 0,
    running: 0,
    completed: 0,
    queued: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [backendDown, setBackendDown] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [analyticsOpen, setAnalyticsOpen] = useState(false);
  const [runDialogOpen, setRunDialogOpen] = useState(false);
  const [projectToRun, setProjectToRun] = useState<Project | null>(null);

  // Filter states
  const [regions, setRegions] = useState<string[]>([]);
  const [countries, setCountries] = useState<string[]>([]);
  const [brands, setBrands] = useState<string[]>([]);
  const [websites, setWebsites] = useState<string[]>([]);
  const [selectedRegion, setSelectedRegion] = useState<string>("");
  const [selectedCountry, setSelectedCountry] = useState<string>("");
  const [selectedBrand, setSelectedBrand] = useState<string>("");
  const [selectedWebsite, setSelectedWebsite] = useState<string>("");
  const [showFilters, setShowFilters] = useState(true); // Show filters by default
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [msaSyncing, setMsaSyncing] = useState(false); // guard: prevents duplicate sync-msa calls
  const [fetchAll, setFetchAll] = useState(false); // Toggle for fetching all projects vs paginated

  // Real-time monitoring hook
  const monitoring = useRealTimeMonitoring();

  useEffect(() => {
    fetchFilters();
    fetchMetadata();
    fetchMsaProjects();
    // Auto-refresh uses the lightweight fetchProjects (DB read only).
    // fetchMsaProjects (full ParseHub sync) is only triggered manually.
    const interval = setInterval(() => {
      fetchMetadata();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    fetchMsaProjects();
  }, [
    selectedRegion,
    selectedCountry,
    selectedBrand,
    selectedWebsite,
    fetchAll,
  ]);

  const fetchFilters = async () => {
    try {
      console.log("[Home] Fetching filter options...");

      const response = await apiClient.get("/api/filters");
      const data = response.data;
      console.log("[Home] Successfully fetched filter options");


      if (data.filters) {
        setRegions(data.filters.regions || []);
        setCountries(data.filters.countries || []);
        setBrands(data.filters.brands || []);
        setWebsites(data.filters.websites || []);

        console.log(
          `[Home] Loaded filters - Regions: ${data.filters.regions?.length || 0}, Countries: ${data.filters.countries?.length || 0}, Brands: ${data.filters.brands?.length || 0}, Websites: ${data.filters.websites?.length || 0}`,
        );
      }
    } catch (err) {
      console.error("[Home] Error fetching filter options:", extractErrorMessage(err));
    }
  };

  const fetchMetadata = async () => {
    try {
      console.log("[Home] Fetching metadata...");

      const params = new URLSearchParams();
      const response = await apiClient.get("/api/metadata", { params });
      const data = response.data;

      console.log(
        "[Home] Successfully fetched",
        data.count || 0,
        "metadata records",
      );
    } catch (err) {
      console.error("[Home] Error fetching metadata:", extractErrorMessage(err));
    }
  };

  const fetchProjects = async () => {
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    try {
      setError(null);
      let url = "/api/projects";

      // Build query params
      const params = new URLSearchParams();

      // Default 50 per page, or 1000 for "All" mode
      const limit = fetchAll ? "1000" : "50";

      params.append("page", "1");
      params.append("limit", limit);

      // Add active filters (now supported by backend)
      if (selectedRegion) params.append("region", selectedRegion);
      if (selectedCountry) params.append("country", selectedCountry);
      if (selectedBrand) params.append("brand", selectedBrand);
      if (selectedWebsite) params.append("website", selectedWebsite);

      url = "/api/projects?" + params.toString();

      console.log("[Home] Fetching projects from:", url);

      // Use 120 second timeout for paginated requests - backend can be slow
      const controller = new AbortController();
      timeoutId = setTimeout(() => controller.abort(), 120000);

      const response = await apiClient.get(url, {
        signal: controller.signal,
      });
      if (timeoutId !== undefined) {
        clearTimeout(timeoutId);
        timeoutId = undefined;
      }

      const data = response.data;
      console.log(
        "[Home] Backend returned response with keys:",
        Object.keys(data),
      );

      // Handle both grouped (by_website) and flat (projects) response formats
      let allProjects: Project[] = [];

      if (data.by_website && Array.isArray(data.by_website)) {
        // Grouped response format (from /api/projects or /api/projects/search with grouping)
        console.log(
          "[Home] Processing grouped response with",
          data.by_website.length,
          "website groups",
        );
        for (const group of data.by_website) {
          if (group.projects && Array.isArray(group.projects)) {
            allProjects.push(...group.projects);
          }
        }
      } else if (data.by_project && Array.isArray(data.by_project)) {
        // Alternative grouped format from search endpoint
        allProjects = data.by_project;
      } else if (data.projects && Array.isArray(data.projects)) {
        // Flat response format
        allProjects = data.projects;
      }

      console.log(
        "[Home] Successfully fetched",
        allProjects.length,
        "total projects",
      );

      if (allProjects.length > 0) {
        console.log(
          "[Home] First 3 projects:",
          allProjects.slice(0, 3).map((p: Project) => p.title),
        );
      }

      // Enrich projects with metadata
      const projectsWithMetadata = await Promise.all(
        allProjects.map(async (project: Project) => {
          try {
            const metaRes = await fetch(`/api/metadata?project_token=${project.token}`);
            const metaData = await metaRes.json();

            if (metaData.success && metaData.records?.length > 0) {
              project.metadata = metaData.records[0];
            }
          } catch (err) {
            if (!isRequestCanceled(err)) {
              console.error(`Failed to fetch metadata for ${project.token}:`, err);
            }
          }
          return project;
        })
      );

      setProjects(projectsWithMetadata);
      setLastUpdate(new Date());
      setBackendDown(false);

      // Calculate stats
      const running =
        allProjects.filter((p: Project) => p.last_run?.status === "running")
          .length || 0;
      const completed =
        allProjects.filter((p: Project) => p.last_run?.status === "complete")
          .length || 0;
      const queued =
        allProjects.filter((p: Project) => p.last_run?.status === "queued")
          .length || 0;

      setStats({
        total: allProjects.length,
        running,
        completed,
        queued,
      });

      setLoading(false);
    } catch (err) {
      if (timeoutId !== undefined) {
        clearTimeout(timeoutId);
      }
      if (isRequestCanceled(err)) {
        // Timeout abort, Fast Refresh, navigation, or replaced request — not a backend fault
        setLoading(false);
        return;
      }
      const errorMsg = extractErrorMessage(err);
      // Only log non-network errors to avoid console spam
      if (!isBackendDown(err)) {
        console.error("[Home] Error fetching projects:", errorMsg);
      }
      setError(errorMsg);
      setBackendDown(isBackendDown(err));
      setLoading(false);
    }
  };

  const syncProjects = async () => {
    try {
      setSyncing(true);
      setSyncMessage(null);
      setError(null);

      console.log("[Home] Starting project sync...");

      const response = await apiClient.post("/api/projects/sync");
      const data = response.data;

      console.log("[Home] Sync completed:", data);

      setSyncMessage(
        `✅ ${data.message || `Synced ${data.total} projects to database`}`,
      );

      // Refresh projects after sync
      setTimeout(() => {
        fetchMsaProjects();
        setSyncing(false);
      }, 1000);
    } catch (err) {
      const errorMsg = extractErrorMessage(err);
      console.error("[Home] Sync error:", errorMsg);
      setError(errorMsg);
      setSyncing(false);
    }
  };

  /**
   * Fetch MSA projects via the optimised sync-msa endpoint.
   * Concurrent ParseHub fetch + Snowflake upsert + (MSA Pricing) filter.
   */
  const fetchMsaProjects = async () => {
    // Duplicate-call guard: prevent concurrent sync-msa requests
    if (msaSyncing) {
      console.log("[Home] MSA sync already in progress — skipping");
      return;
    }
    try {
      setError(null);
      setLoading(true);
      setMsaSyncing(true);

      console.log("[Home] Fetching MSA projects via sync-msa pipeline...");

      const response = await apiClient.post("/api/projects/sync-msa");
      const data = response.data;

      console.log(
        "[Home] MSA sync returned",
        data.count,
        "projects (total fetched:",
        data.total_fetched,
        ", partial_failure:",
        data.partial_failure,
        ")"
      );

      if (data.partial_failure) {
        console.warn("[Home] sync-msa reported partial_failure:", data.error);
      }

      const allProjects: Project[] = data.projects || [];

      setProjects(allProjects);
      setLastUpdate(new Date());
      setBackendDown(false);

      // Calculate stats from returned projects
      const running = allProjects.filter(
        (p: Project) => p.last_run?.status === "running"
      ).length;
      const completed = allProjects.filter(
        (p: Project) => p.last_run?.status === "complete"
      ).length;
      const queued = allProjects.filter(
        (p: Project) => p.last_run?.status === "queued"
      ).length;

      setStats({
        total: allProjects.length,
        running,
        completed,
        queued,
      });

      setLoading(false);
      setMsaSyncing(false);
    } catch (err) {
      setMsaSyncing(false);
      if (isRequestCanceled(err)) {
        setLoading(false);
        return;
      }
      const errorMsg = extractErrorMessage(err);
      if (!isBackendDown(err)) {
        console.error("[Home] Error fetching MSA projects:", errorMsg);
      }
      setError(errorMsg);
      setBackendDown(isBackendDown(err));
      setLoading(false);
    }
  };

  const handleRunAll = async () => {
    try {
      setError(null);
      await apiClient.post("/api/projects/run-all");
      setTimeout(fetchMsaProjects, 1000);

    } catch (err) {
      setError(extractErrorMessage(err));
    }
  };

  const clearFilters = () => {
    setSelectedRegion("");
    setSelectedCountry("");
    setSelectedBrand("");
    setSelectedWebsite("");
  };

  const hasActiveFilters =
    selectedRegion || selectedCountry || selectedBrand || selectedWebsite;

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <Header />

      {/* Error / Backend-down banner */}
      {error && (
        <div className="container mx-auto px-6 py-4 mt-6">
          {backendDown ? (
            /* Full-bleed backend-down card with instructions */
            <div className="bg-amber-900/20 backdrop-blur-sm border border-amber-700/40 rounded-xl p-6 shadow-lg shadow-amber-900/10">
              <div className="flex items-start gap-4">
                <WifiOff className="w-6 h-6 text-amber-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-amber-200 text-base">
                    Backend is unreachable
                  </p>
                  <p className="text-amber-400/90 text-sm mt-1 leading-relaxed">
                    The Flask API server is not responding (502/503). This usually means
                    the backend service is still <strong>starting up on Railway</strong> or
                    the <code className="px-1 py-0.5 bg-amber-900/50 rounded text-xs">BACKEND_API_URL</code> environment
                    variable is not set on the frontend service.
                  </p>
                  <p className="text-amber-500 text-xs mt-2">
                    Detail: <span className="font-mono">{error}</span>
                  </p>
                </div>
                <button
                  onClick={() => { setError(null); setBackendDown(false); fetchMsaProjects(); }}
                  className="flex-shrink-0 flex items-center gap-2 px-4 py-2 bg-amber-700 hover:bg-amber-600 text-white text-sm font-medium rounded-lg transition-colors"
                >
                  <RefreshCw className="w-4 h-4" />
                  Retry
                </button>
              </div>
            </div>
          ) : (
            /* Standard error banner */
            <div className="bg-red-900/30 backdrop-blur-sm border border-red-700/50 rounded-xl p-4 flex items-start gap-3 shadow-lg shadow-red-900/20">
              <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-red-300">Error</p>
                <p className="text-red-400 text-sm mt-0.5 break-words">{error}</p>
              </div>
              <button
                onClick={() => { setError(null); fetchMsaProjects(); }}
                className="flex-shrink-0 flex items-center gap-2 px-4 py-1.5 bg-red-800 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Retry
              </button>
            </div>
          )}
        </div>
      )}

      {/* Success Message */}
      {syncMessage && (
        <div className="container mx-auto px-6 py-4 mt-6">
          <div className="bg-green-900/30 backdrop-blur-sm border border-green-700/50 rounded-xl p-4 flex items-start gap-3 shadow-lg shadow-green-900/20">
            <div className="text-green-400 flex-shrink-0 mt-0.5">✅</div>
            <div>
              <p className="font-semibold text-green-300">Success</p>
              <p className="text-green-400 text-sm mt-0.5">{syncMessage}</p>
            </div>
          </div>
        </div>
      )}

      {/* Stats Section */}
      <section className="container mx-auto px-6 py-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-5 mb-8">
          <StatsCard
            title="Total Projects"
            value={stats.total}
            icon={<TrendingUp className="w-6 h-6" />}
            color="bg-blue-500"
          />
          <StatsCard
            title="Running"
            value={stats.running}
            icon={<Activity className="w-6 h-6" />}
            color="bg-green-500"
          />
          <StatsCard
            title="Queued"
            value={stats.queued}
            icon={<Zap className="w-6 h-6" />}
            color="bg-yellow-500"
          />
          <StatsCard
            title="Completed"
            value={stats.completed}
            icon={<Download className="w-6 h-6" />}
            color="bg-purple-500"
          />
        </div>

        {/* Action Buttons */}
        <div className="mb-8 flex gap-4 flex-wrap items-center">
          <button
            onClick={syncProjects}
            disabled={syncing || loading}
            className="inline-flex items-center gap-2 px-6 py-3.5 bg-gradient-to-r from-cyan-600 to-cyan-700 hover:from-cyan-700 hover:to-cyan-800 disabled:from-slate-700 disabled:to-slate-700 rounded-xl font-semibold transition-all duration-200 shadow-lg hover:shadow-cyan-500/25 disabled:shadow-none transform hover:scale-105 disabled:scale-100 disabled:cursor-not-allowed"
          >
            <Download className={`w-5 h-5 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? "Syncing..." : "Sync Projects"}
          </button>
          <button
            onClick={handleRunAll}
            disabled={loading}
            className="inline-flex items-center gap-2 px-6 py-3.5 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 disabled:from-slate-700 disabled:to-slate-700 rounded-xl font-semibold transition-all duration-200 shadow-lg hover:shadow-blue-500/25 disabled:shadow-none transform hover:scale-105 disabled:scale-100 disabled:cursor-not-allowed"
          >
            <Play className="w-5 h-5" />
            Run All Projects
          </button>
          <button
            onClick={() => setAnalyticsOpen(true)}
            className="inline-flex items-center gap-2 px-6 py-3.5 bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 rounded-xl font-semibold transition-all duration-200 shadow-lg hover:shadow-purple-500/25 transform hover:scale-105"
          >
            <BarChart3 className="w-5 h-5" />
            Analytics
          </button>
          <button
            onClick={() => setFetchAll(!fetchAll)}
            className={`inline-flex items-center gap-2 px-6 py-3.5 rounded-xl font-semibold transition-all duration-200 border ${fetchAll
              ? "bg-orange-900/30 border-orange-600/50 text-orange-300"
              : "bg-slate-800 hover:bg-slate-700 border-slate-700"
              }`}
          >
            <Download className="w-5 h-5" />
            {fetchAll ? "All Projects" : "View per 50"}
          </button>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`inline-flex items-center gap-2 px-6 py-3.5 rounded-xl font-semibold transition-all duration-200 border ${hasActiveFilters
              ? "bg-amber-900/30 border-amber-600/50 text-amber-300"
              : "bg-slate-800 hover:bg-slate-700 border-slate-700"
              }`}
          >
            <Filter className="w-5 h-5" />
            {showFilters ? "Hide" : "Show"} Filters {hasActiveFilters && "✓"}
          </button>
          <button
            onClick={fetchMsaProjects}
            disabled={loading || msaSyncing}
            className="inline-flex items-center gap-2 px-6 py-3.5 bg-slate-800 hover:bg-slate-700 disabled:bg-slate-800/50 border border-slate-700 hover:border-slate-600 rounded-xl font-semibold transition-all duration-200 disabled:cursor-not-allowed"
          >
            <Activity className={`w-5 h-5 ${msaSyncing ? "animate-spin" : ""}`} />
            {msaSyncing ? "Syncing..." : "Refresh"}
          </button>
          {lastUpdate && (
            <div className="ml-auto flex items-center gap-2 px-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-xl">
              <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></div>
              <span className="text-slate-400 text-sm font-medium">
                Updated {lastUpdate.toLocaleTimeString()}
              </span>
            </div>
          )}
        </div>

        {/* Filters Panel */}
        {showFilters && (
          <div className="mb-8 p-6 bg-slate-800/50 border border-slate-700/50 rounded-xl backdrop-blur-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-slate-200">Filters</h3>
              <button
                onClick={() => setShowFilters(false)}
                className="p-1 hover:bg-slate-700 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Region
                </label>
                <select
                  value={selectedRegion}
                  onChange={(e) => setSelectedRegion(e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-200 focus:outline-none focus:border-blue-500"
                >
                  <option value="">All Regions</option>
                  {regions.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Country
                </label>
                <select
                  value={selectedCountry}
                  onChange={(e) => setSelectedCountry(e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-200 focus:outline-none focus:border-blue-500"
                >
                  <option value="">All Countries</option>
                  {countries.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Brand
                </label>
                <select
                  value={selectedBrand}
                  onChange={(e) => setSelectedBrand(e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-200 focus:outline-none focus:border-blue-500"
                >
                  <option value="">All Brands</option>
                  {brands.map((b) => (
                    <option key={b} value={b}>
                      {b}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Website
                </label>
                <select
                  value={selectedWebsite}
                  onChange={(e) => setSelectedWebsite(e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-200 focus:outline-none focus:border-blue-500"
                >
                  <option value="">All Websites</option>
                  {websites.map((w) => (
                    <option key={w} value={w}>
                      {w}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-slate-300 transition-colors"
              >
                Clear Filters
              </button>
            )}
          </div>
        )}

        {/* Projects List */}
        {loading ? (
          <div className="text-center py-20">
            <div className="inline-flex flex-col items-center gap-6">
              <div className="relative">
                <div className="animate-spin rounded-full h-16 w-16 border-4 border-slate-700 border-t-blue-500"></div>
                <div className="absolute inset-0 rounded-full bg-blue-500/20 animate-pulse"></div>
              </div>
              <div>
                <p className="text-slate-300 text-lg font-semibold">
                  Loading projects...
                </p>
                <p className="text-slate-500 text-sm mt-1">
                  Please wait while we fetch your data
                </p>
              </div>
            </div>
          </div>
        ) : (
          <ProjectsList
            projects={projects}
            onRunProject={async (token: string) => {
              const project = projects.find((p) => p.token === token);
              if (project) {
                setProjectToRun(project);
                setRunDialogOpen(true);
              }
            }}
          />
        )}
      </section>

      {/* Run Dialog */}
      {projectToRun && (
        <RunDialog
          isOpen={runDialogOpen}
          onClose={() => setRunDialogOpen(false)}
          projectToken={projectToRun.token}
          projectTitle={projectToRun.title}
          projectURL={projectToRun.projecturl || projectToRun.main_site || ""}
          onRunStart={async (runToken: string, pages: number) => {
            // Start real-time monitoring
            try {
              await monitoring.startMonitoring(
                projectToRun.token,
                runToken,
                pages,
              );
            } catch (err) {
              console.error("Failed to start monitoring:", err);
            }

            await fetchMsaProjects();
            // Show analytics modal for all projects
            setAnalyticsOpen(true);
          }}
        />
      )}

      {/* Analytics Modal */}
      <AllProjectsAnalyticsModal
        isOpen={analyticsOpen}
        onClose={() => {
          setAnalyticsOpen(false);
        }}
        projects={projects}
      />
    </main>
  );
}
