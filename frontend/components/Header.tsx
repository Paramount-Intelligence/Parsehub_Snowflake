"use client";

import { useEffect, useState } from "react";
import { Layers, Clock, Wifi, Home, FileUp, Settings, CalendarClock } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import ScheduledRunsModal from "./ScheduledRunsModal";

export default function Header() {
  const [time, setTime] = useState<string>("");
  const [date, setDate] = useState<string>("");
  const [showScheduledRuns, setShowScheduledRuns] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTime(
        now.toLocaleTimeString("en-US", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
      );
      setDate(
        now.toLocaleDateString("en-US", {
          weekday: "long",
          year: "numeric",
          month: "long",
          day: "numeric",
        }),
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const isActive = (path: string) => pathname === path;
  const navLinkClass = (path: string) =>
    `inline-flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-all duration-200 ${
      isActive(path)
        ? "bg-blue-600/20 text-blue-400 border border-blue-600/30"
        : "text-slate-400 hover:text-slate-300 hover:bg-slate-800/50"
    }`;

  return (
    <header className="bg-slate-900/95 backdrop-blur-md border-b border-slate-800/50 sticky top-0 z-50 shadow-2xl">
      <div className="container mx-auto px-6">
        {/* Main Header */}
        <div className="py-5 flex items-center justify-between border-b border-slate-800/30">
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 shadow-lg shadow-blue-500/25">
              <Layers className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 via-cyan-400 to-blue-500 bg-clip-text text-transparent tracking-tight">
                ParseHub Dashboard
              </h1>
              <p className="text-slate-400 text-sm mt-0.5 flex items-center gap-2">
                <Wifi className="w-3.5 h-3.5 text-emerald-400" />
                Real-time project monitoring & management
              </p>
            </div>
          </div>
          <div className="flex items-center gap-6">
            <div className="text-right">
              <div className="flex items-center gap-2 text-slate-300 font-semibold text-sm">
                <Clock className="w-4 h-4 text-blue-400" />
                {time}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">{date}</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="py-3 flex items-center gap-4">
          <Link href="/" className={navLinkClass("/")}>
            <Home className="w-4 h-4" />
            Home
          </Link>
          <Link href="/projects" className={navLinkClass("/projects")}>
            <Settings className="w-4 h-4" />
            Projects
          </Link>
          <Link href="/import-metadata" className={navLinkClass("/import-metadata")}>
            <FileUp className="w-4 h-4" />
            Import
          </Link>
          <button
            onClick={() => setShowScheduledRuns(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-all duration-200 text-slate-400 hover:text-slate-300 hover:bg-slate-800/50 ml-auto"
            title="View scheduled project runs"
          >
            <CalendarClock className="w-4 h-4" />
            Scheduled Runs
          </button>
        </nav>

        <ScheduledRunsModal
          isOpen={showScheduledRuns}
          onClose={() => setShowScheduledRuns(false)}
        />
      </div>
    </header>
  );
}
