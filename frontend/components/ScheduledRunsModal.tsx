'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Modal from './Modal';
import apiClient from '@/lib/apiClient';
import { ExternalLink, Trash2 } from 'lucide-react';

interface ScheduledRun {
  job_id: string;
  project_token: string;
  type: 'once' | 'recurring';
  scheduled_time?: string;
  frequency?: 'daily' | 'weekly' | 'monthly';
  time?: string;
  day_of_week?: string;
  pages: number;
  created_at: string;
}

interface ScheduledRunsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function ScheduledRunsModal({ isOpen, onClose }: ScheduledRunsModalProps) {
  const router = useRouter();
  const [scheduledRuns, setScheduledRuns] = useState<ScheduledRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch scheduled runs on modal open and poll every 3 seconds
  useEffect(() => {
    if (!isOpen) return;

    // Fetch immediately when modal opens
    fetchScheduledRuns();

    // Set up polling every 3 seconds to detect newly scheduled runs
    const interval = setInterval(fetchScheduledRuns, 3000);

    return () => clearInterval(interval);
  }, [isOpen]);

  const fetchScheduledRuns = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/api/scheduled-runs');
      if (response.status === 200 && response.data.scheduled_runs) {
        setScheduledRuns(response.data.scheduled_runs);
      }
    } catch (err) {
      console.error('Error fetching scheduled runs:', err);
      setError('Failed to fetch scheduled runs');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async (run: ScheduledRun) => {
    if (!window.confirm('Cancel this scheduled run?')) return;

    try {
      const response = await apiClient.delete(`/api/scheduled-runs/${run.job_id}`);
      if (response.status === 200) {
        setScheduledRuns(scheduledRuns.filter(r => r.job_id !== run.job_id));
        alert('✅ Scheduled run cancelled');
      }
    } catch (err) {
      console.error('Error cancelling run:', err);
      alert('Failed to cancel scheduled run');
    }
  };

  const formatScheduleInfo = (run: ScheduledRun) => {
    if (run.type === 'once') {
      const date = new Date(run.scheduled_time!);
      return `${date.toLocaleDateString()} at ${date.toLocaleTimeString([], { 
        hour: '2-digit', 
        minute: '2-digit' 
      })}`;
    } else {
      const dayInfo = run.frequency === 'weekly' ? ` every ${run.day_of_week}` : '';
      return `${run.frequency}${dayInfo} at ${run.time}`;
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Scheduled Runs" size="large">
      <div className="flex flex-col h-full gap-4">
        {error && (
          <div className="p-3 bg-red-500/20 border border-red-500/30 text-red-200 rounded-lg text-sm flex-shrink-0">
            {error}
          </div>
        )}

        <div className="flex-1 overflow-hidden flex flex-col">
          {loading ? (
            <div className="flex items-center justify-center flex-1">
              <div className="text-center">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500"></div>
                <p className="text-slate-400 mt-2">Loading scheduled runs...</p>
              </div>
            </div>
          ) : scheduledRuns.length === 0 ? (
            <div className="flex items-center justify-center flex-1">
              <div className="text-center">
                <p className="text-slate-400">No scheduled runs yet</p>
                <p className="text-slate-500 text-sm mt-1">Use the Schedule button on a project to create one</p>
              </div>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto space-y-3">
              {scheduledRuns.map((run, idx) => (
                <div
                  key={idx}
                  className="p-4 bg-gradient-to-r from-purple-900/30 to-blue-900/20 border border-purple-500/30 rounded-lg hover:border-purple-500/50 transition-all"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <h4 className="font-semibold text-white text-sm truncate">
                          {run.project_token}
                        </h4>
                        <span className="px-2 py-0.5 bg-purple-600/50 text-purple-200 text-xs rounded-full flex-shrink-0">
                          {run.type === 'once' ? 'Once' : 'Recurring'}
                        </span>
                        {run.pages > 1 && (
                          <span className="px-2 py-0.5 bg-blue-600/50 text-blue-200 text-xs rounded-full flex-shrink-0">
                            {run.pages} pages
                          </span>
                        )}
                      </div>

                      <p className="text-slate-300 text-sm mb-2">
                        📅 {formatScheduleInfo(run)}
                      </p>

                      <p className="text-slate-400 text-xs">
                        Created {new Date(run.created_at).toLocaleDateString()}
                      </p>
                    </div>

                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={() => router.push(`/projects/${run.project_token}`)}
                        className="px-3 py-1.5 bg-indigo-600/50 hover:bg-indigo-600 text-indigo-100 text-sm rounded-lg transition-colors whitespace-nowrap flex items-center gap-1.5"
                        title="View project details"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        Details
                      </button>
                      <button
                        onClick={() => handleCancel(run)}
                        className="px-3 py-1.5 bg-red-600/50 hover:bg-red-600 text-red-100 text-sm rounded-lg transition-colors whitespace-nowrap flex items-center gap-1.5"
                        title="Cancel this schedule"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex gap-2 pt-4 border-t border-slate-700/50 flex-shrink-0">
          <button
            onClick={fetchScheduledRuns}
            disabled={loading}
            className="flex-1 px-4 py-2.5 bg-slate-700/50 hover:bg-slate-700 disabled:bg-slate-800 text-slate-300 rounded-lg font-medium transition-all"
          >
            Refresh
          </button>
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2.5 bg-gradient-to-r from-purple-600 to-purple-500 hover:from-purple-500 hover:to-purple-400 text-white rounded-lg font-medium transition-all"
          >
            Close
          </button>
        </div>
      </div>
    </Modal>
  );
}
