"use client";
import { useState } from "react";
import { X, Plus, Minus } from "lucide-react";

interface BatchConfig {
  execution_mode: "sequential" | "parallel";
  max_parallel: number;
  delay_seconds: number;
  retry_on_failure: boolean;
  max_retries: number;
}

interface BatchRunConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (config: BatchConfig) => void;
  projectCount: number;
}

export default function BatchRunConfigModal({
  isOpen,
  onClose,
  onSubmit,
  projectCount,
}: BatchRunConfigModalProps) {
  const [config, setConfig] = useState<BatchConfig>({
    execution_mode: "sequential",
    max_parallel: 3,
    delay_seconds: 1,
    retry_on_failure: false,
    max_retries: 0,
  });

  if (!isOpen) return null;

  const handleSubmit = () => {
    onSubmit(config);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-slate-800 rounded-lg shadow-2xl p-6 max-w-md w-full mx-4 border border-slate-700">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-slate-100">Batch Run Configuration</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="space-y-4">
          {/* Execution Mode */}
          <div>
            <label className="block text-sm font-semibold mb-2 text-slate-200">
              Execution Mode
            </label>
            <div className="flex gap-4">
              <label className="flex items-center cursor-pointer">
                <input
                  type="radio"
                  value="sequential"
                  checked={config.execution_mode === "sequential"}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      execution_mode: e.target.value as "sequential" | "parallel",
                    })
                  }
                  className="mr-2 cursor-pointer accent-blue-500"
                />
                <span className="text-slate-300">Sequential (one at a time)</span>
              </label>
              <label className="flex items-center cursor-pointer">
                <input
                  type="radio"
                  value="parallel"
                  checked={config.execution_mode === "parallel"}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      execution_mode: e.target.value as "sequential" | "parallel",
                    })
                  }
                  className="mr-2 cursor-pointer accent-blue-500"
                />
                <span className="text-slate-300">Parallel</span>
              </label>
            </div>
          </div>

          {/* Max Parallel Workers */}
          {config.execution_mode === "parallel" && (
            <div>
              <label className="block text-sm font-semibold mb-2 text-slate-200">
                Max Parallel Runs (1-{projectCount})
              </label>
              <div className="flex items-center gap-2">
                <button
                  onClick={() =>
                    setConfig({
                      ...config,
                      max_parallel: Math.max(1, config.max_parallel - 1),
                    })
                  }
                  className="p-1 hover:bg-slate-700 rounded transition-colors text-slate-300"
                >
                  <Minus size={16} />
                </button>
                <input
                  type="number"
                  min="1"
                  max={projectCount}
                  value={config.max_parallel}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      max_parallel: Math.min(
                        projectCount,
                        Math.max(1, parseInt(e.target.value) || 1)
                      ),
                    })
                  }
                  className="border border-slate-600 rounded px-3 py-1 w-16 text-center bg-slate-700 text-slate-200 focus:outline-none focus:border-blue-500"
                />
                <button
                  onClick={() =>
                    setConfig({
                      ...config,
                      max_parallel: Math.min(projectCount, config.max_parallel + 1),
                    })
                  }
                  className="p-1 hover:bg-slate-700 rounded transition-colors text-slate-300"
                >
                  <Plus size={16} />
                </button>
              </div>
            </div>
          )}

          {/* Delay Between Runs */}
          {config.execution_mode === "sequential" && (
            <div>
              <label className="block text-sm font-semibold mb-2 text-slate-200">
                Delay Between Runs (seconds)
              </label>
              <input
                type="number"
                min="0"
                max="60"
                step="0.5"
                value={config.delay_seconds}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    delay_seconds: parseFloat(e.target.value) || 0,
                  })
                }
                className="border border-slate-600 rounded px-3 py-1 w-full bg-slate-700 text-slate-200 focus:outline-none focus:border-blue-500"
              />
            </div>
          )}

          {/* Retry Settings */}
          <div>
            <label className="flex items-center mb-2 cursor-pointer">
              <input
                type="checkbox"
                checked={config.retry_on_failure}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    retry_on_failure: e.target.checked,
                  })
                }
                className="mr-2 cursor-pointer accent-blue-500"
              />
              <span className="text-sm font-semibold text-slate-200">Retry on Failure</span>
            </label>
          </div>

          {config.retry_on_failure && (
            <div>
              <label className="block text-sm font-semibold mb-2 text-slate-200">
                Max Retries per Project
              </label>
              <div className="flex items-center gap-2">
                <button
                  onClick={() =>
                    setConfig({
                      ...config,
                      max_retries: Math.max(0, config.max_retries - 1),
                    })
                  }
                  className="p-1 hover:bg-slate-700 rounded transition-colors text-slate-300"
                >
                  <Minus size={16} />
                </button>
                <input
                  type="number"
                  min="0"
                  max="5"
                  value={config.max_retries}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      max_retries: Math.max(0, parseInt(e.target.value) || 0),
                    })
                  }
                  className="border border-slate-600 rounded px-3 py-1 w-16 text-center bg-slate-700 text-slate-200 focus:outline-none focus:border-blue-500"
                />
                <button
                  onClick={() =>
                    setConfig({
                      ...config,
                      max_retries: Math.min(5, config.max_retries + 1),
                    })
                  }
                  className="p-1 hover:bg-slate-700 rounded transition-colors text-slate-300"
                >
                  <Plus size={16} />
                </button>
              </div>
            </div>
          )}

          {/* Summary */}
          <div className="bg-slate-700/50 border border-slate-600 p-3 rounded text-sm">
            <p className="font-semibold text-blue-300">Summary:</p>
            <ul className="text-blue-200 text-xs mt-1">
              <li>• Running {projectCount} projects</li>
              <li>
                •{" "}
                {config.execution_mode === "sequential"
                  ? `Sequential with ${config.delay_seconds}s delays`
                  : `In parallel (${config.max_parallel} at a time)`}
              </li>
              {config.retry_on_failure && (
                <li>• Will retry up to {config.max_retries} times on failure</li>
              )}
            </ul>
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-slate-600 rounded hover:bg-slate-700 text-slate-200 transition-colors font-medium"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors font-medium shadow-lg"
          >
            Start Run
          </button>
        </div>
      </div>
    </div>
  );
}
