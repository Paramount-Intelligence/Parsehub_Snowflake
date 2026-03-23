"use client";
import apiClient from "@/lib/apiClient";

import { useState } from "react";
import Modal from "./Modal";
import { Calendar, Clock, RotateCw, AlertCircle } from "lucide-react";

interface SchedulerModalProps {
  projectToken: string;
  onClose: () => void;
  onSchedule: (scheduledTime: string) => void;
}

export default function SchedulerModal({
  projectToken,
  onClose,
  onSchedule,
}: SchedulerModalProps) {
  const [scheduleType, setScheduleType] = useState<"once" | "recurring">(
    "once",
  );
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [frequency, setFrequency] = useState<"daily" | "weekly" | "monthly">(
    "daily",
  );
  const [dayOfWeek, setDayOfWeek] = useState("monday");
  const [pages, setPages] = useState("1");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSchedule = async () => {
    setError(null);

    if (!time) {
      setError("Please select a time");
      return;
    }

    if (scheduleType === "once" && !date) {
      setError("Please select a date for one-time scheduling");
      return;
    }

    setLoading(true);
    try {
      const scheduledDateTime = scheduleType === "once" ? `${date}T${time}` : time;

      const response = await apiClient.post("/api/projects/schedule", {
        projectToken,
        scheduleType,
        scheduledTime: scheduledDateTime,
        frequency: scheduleType === "recurring" ? frequency : undefined,
        dayOfWeek:
          scheduleType === "recurring" && frequency === "weekly"
            ? dayOfWeek
            : undefined,
        pages: parseInt(pages) || 1,
      });

      if (response.status === 200) {
        alert(`✅ Scheduled successfully!`);
        onSchedule(scheduledDateTime);
        onClose();
      } else {
        setError("Failed to schedule");
      }
    } catch (error) {
      console.error("Schedule error:", error);
      setError("Error scheduling run. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={true} onClose={onClose} title="Schedule Project Run" size="large">
      <div className="space-y-6">
        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <p className="text-red-200 text-sm">{error}</p>
          </div>
        )}

        {/* Schedule Type Selection */}
        <div>
          <label className="block text-sm font-bold text-slate-200 mb-3 uppercase tracking-wide">
            Schedule Type
          </label>
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => setScheduleType("once")}
              className={`p-4 rounded-xl border-2 transition-all duration-200 ${
                scheduleType === "once"
                  ? "bg-gradient-to-br from-purple-600/40 to-purple-500/20 border-purple-500/60 shadow-lg shadow-purple-500/20"
                  : "bg-slate-800/40 border-slate-700/50 hover:border-slate-600/70"
              }`}
            >
              <Calendar className="w-5 h-5 mx-auto mb-2" style={{ color: scheduleType === "once" ? "#c084fc" : "#94a3b8" }} />
              <div className="font-semibold text-sm" style={{ color: scheduleType === "once" ? "#c084fc" : "#cbd5e1" }}>
                Run Once
              </div>
              <div className="text-xs text-slate-400 mt-1">
                Execute at specific date/time
              </div>
            </button>

            <button
              onClick={() => setScheduleType("recurring")}
              className={`p-4 rounded-xl border-2 transition-all duration-200 ${
                scheduleType === "recurring"
                  ? "bg-gradient-to-br from-blue-600/40 to-blue-500/20 border-blue-500/60 shadow-lg shadow-blue-500/20"
                  : "bg-slate-800/40 border-slate-700/50 hover:border-slate-600/70"
              }`}
            >
              <RotateCw className="w-5 h-5 mx-auto mb-2" style={{ color: scheduleType === "recurring" ? "#60a5fa" : "#94a3b8" }} />
              <div className="font-semibold text-sm" style={{ color: scheduleType === "recurring" ? "#60a5fa" : "#cbd5e1" }}>
                Recurring
              </div>
              <div className="text-xs text-slate-400 mt-1">
                Execute on a schedule
              </div>
            </button>
          </div>
        </div>

        {/* Date & Time Input */}
        <div className="bg-slate-900/40 rounded-xl p-5 border border-slate-700/50 space-y-4">
          <h3 className="font-semibold text-slate-200 flex items-center gap-2">
            <Clock className="w-4 h-4 text-purple-400" />
            Schedule Details
          </h3>

          <div className="grid grid-cols-2 gap-4">
            {scheduleType === "once" && (
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wide">
                  Date
                </label>
                <input
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="w-full px-4 py-2.5 bg-slate-800/70 border border-slate-600/50 text-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 transition-all"
                />
              </div>
            )}
            
            <div className={scheduleType === "once" ? "" : "col-span-2"}>
              <label className="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wide">
                {scheduleType === "once" ? "Time" : "Time (HH:MM)"}
              </label>
              <input
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                className="w-full px-4 py-2.5 bg-slate-800/70 border border-slate-600/50 text-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 transition-all"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wide">
              Pages to Scrape
            </label>
            <input
              type="number"
              min="1"
              value={pages}
              onChange={(e) => setPages(e.target.value)}
              className="w-full px-4 py-2.5 bg-slate-800/70 border border-slate-600/50 text-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 transition-all"
            />
          </div>
        </div>

        {/* Recurring Options */}
        {scheduleType === "recurring" && (
          <div className="bg-blue-900/20 rounded-xl p-5 border border-blue-500/30 space-y-4">
            <h3 className="font-semibold text-slate-200 flex items-center gap-2">
              <RotateCw className="w-4 h-4 text-blue-400" />
              Recurrence Settings
            </h3>

            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wide">
                Frequency
              </label>
              <select
                value={frequency}
                onChange={(e) => setFrequency(e.target.value as any)}
                className="w-full px-4 py-2.5 bg-slate-800/70 border border-slate-600/50 text-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all appearance-none cursor-pointer"
              >
                <option value="daily" className="bg-slate-900">
                  Daily
                </option>
                <option value="weekly" className="bg-slate-900">
                  Weekly
                </option>
                <option value="monthly" className="bg-slate-900">
                  Monthly
                </option>
              </select>
            </div>

            {frequency === "weekly" && (
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wide">
                  Day of Week
                </label>
                <select
                  value={dayOfWeek}
                  onChange={(e) => setDayOfWeek(e.target.value)}
                  className="w-full px-4 py-2.5 bg-slate-800/70 border border-slate-600/50 text-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all appearance-none cursor-pointer"
                >
                  <option value="monday" className="bg-slate-900">
                    Monday
                  </option>
                  <option value="tuesday" className="bg-slate-900">
                    Tuesday
                  </option>
                  <option value="wednesday" className="bg-slate-900">
                    Wednesday
                  </option>
                  <option value="thursday" className="bg-slate-900">
                    Thursday
                  </option>
                  <option value="friday" className="bg-slate-900">
                    Friday
                  </option>
                  <option value="saturday" className="bg-slate-900">
                    Saturday
                  </option>
                  <option value="sunday" className="bg-slate-900">
                    Sunday
                  </option>
                </select>
              </div>
            )}
          </div>
        )}

        {/* Preview */}
        {time && (
          <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
              Schedule Summary
            </p>
            <p className="text-slate-300 text-sm">
              {scheduleType === "once"
                ? `📅 ${date ? new Date(date).toLocaleDateString() + " at " : ""}${time}`
                : `🔁 Every ${frequency}${frequency === "weekly" ? ` on ${dayOfWeek}` : ""} at ${time}`}
            </p>
            <p className="text-slate-400 text-xs mt-2">
              📄 Will scrape {pages} page{pages !== "1" ? "s" : ""}
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3 pt-2">
          <button
            onClick={onClose}
            disabled={loading}
            className="flex-1 px-4 py-3 border border-slate-600/50 text-slate-300 rounded-lg hover:bg-slate-800/40 hover:text-slate-100 font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
          <button
            onClick={handleSchedule}
            disabled={loading}
            className="flex-1 px-4 py-3 bg-gradient-to-r from-purple-600 to-purple-500 hover:from-purple-500 hover:to-purple-400 disabled:from-slate-700 disabled:to-slate-600 disabled:text-slate-400 text-white rounded-lg font-semibold transition-all duration-200 shadow-lg shadow-purple-500/20 hover:shadow-purple-400/30 disabled:shadow-none disabled:cursor-not-allowed"
          >
            {loading ? "Scheduling..." : "Schedule Run"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
