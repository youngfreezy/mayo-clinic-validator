"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { listValidations, ValidationSummary } from "@/lib/api";

const STATUS_STYLES: Record<string, { pill: string; label: string }> = {
  pending:        { pill: "bg-gray-100 text-gray-600",    label: "Pending" },
  scraping:       { pill: "bg-blue-100 text-blue-700",    label: "Scraping" },
  running:        { pill: "bg-blue-100 text-blue-700",    label: "Running" },
  awaiting_human: { pill: "bg-yellow-100 text-yellow-700", label: "Awaiting Review" },
  approved:       { pill: "bg-green-100 text-green-700",  label: "Approved" },
  rejected:       { pill: "bg-red-100 text-red-700",      label: "Rejected" },
  failed:         { pill: "bg-red-100 text-red-700",      label: "Failed" },
};

function ScoreBar({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-gray-400">—</span>;
  const pct = Math.round(score * 100);
  const color = score >= 0.85 ? "bg-green-500" : score >= 0.7 ? "bg-yellow-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold text-gray-700 w-7 text-right">{pct}</span>
    </div>
  );
}

function RelativeTime({ iso }: { iso: string }) {
  const date = new Date(iso);
  const now = Date.now();
  const diff = Math.floor((now - date.getTime()) / 1000);

  let label: string;
  if (diff < 60) label = `${diff}s ago`;
  else if (diff < 3600) label = `${Math.floor(diff / 60)}m ago`;
  else if (diff < 86400) label = `${Math.floor(diff / 3600)}h ago`;
  else label = date.toLocaleDateString();

  return (
    <span title={date.toLocaleString()} className="text-xs text-gray-400 whitespace-nowrap">
      {label}
    </span>
  );
}

export function ValidationHistoryTable() {
  const router = useRouter();
  const [rows, setRows] = useState<ValidationSummary[]>([]);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await listValidations();
      setRows(data);
      setLastRefreshed(new Date());
    } catch {
      // backend offline
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 10000);
    return () => clearInterval(interval);
  }, [refresh]);

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-6 text-center text-sm text-gray-400">
        Loading validation history...
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-6 text-center text-sm text-gray-400">
        No validations yet. Submit a URL above to get started.
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
          Validation History
        </h3>
        <div className="flex items-center gap-3">
          {lastRefreshed && (
            <span className="text-xs text-gray-400">
              Refreshed {lastRefreshed.toLocaleTimeString()} · auto every 10s
            </span>
          )}
          <button
            onClick={refresh}
            className="text-xs text-mayo-blue hover:underline"
          >
            Refresh now
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
              <th className="px-6 py-3 text-left font-medium">URL</th>
              <th className="px-4 py-3 text-left font-medium">Status</th>
              <th className="px-4 py-3 text-left font-medium">Score</th>
              <th className="px-4 py-3 text-left font-medium">Result</th>
              <th className="px-4 py-3 text-left font-medium">Last Attempted</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((v) => {
              const st = STATUS_STYLES[v.status] ?? STATUS_STYLES.pending;
              const isActive = ["scraping", "running", "awaiting_human"].includes(v.status);
              return (
                <tr
                  key={v.validation_id}
                  className="hover:bg-gray-50 transition-colors cursor-pointer"
                  onClick={() => router.push(`/results/${v.validation_id}`)}
                >
                  {/* URL */}
                  <td className="px-6 py-3 max-w-xs">
                    <span className="block truncate text-gray-700 text-xs font-mono">
                      {v.url.replace("https://www.mayoclinic.org", "")}
                    </span>
                    <span className="text-xs text-gray-400 truncate block">
                      {v.validation_id.slice(0, 8)}…
                    </span>
                  </td>

                  {/* Status */}
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${st.pill}`}>
                      {isActive && (
                        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
                      )}
                      {st.label}
                    </span>
                  </td>

                  {/* Score bar */}
                  <td className="px-4 py-3">
                    <ScoreBar score={v.overall_score} />
                  </td>

                  {/* Pass / Fail */}
                  <td className="px-4 py-3 whitespace-nowrap">
                    {v.overall_passed === null ? (
                      <span className="text-xs text-gray-400">—</span>
                    ) : v.overall_passed ? (
                      <span className="text-xs font-semibold text-green-600">Pass</span>
                    ) : (
                      <span className="text-xs font-semibold text-red-500">Fail</span>
                    )}
                  </td>

                  {/* Timestamp */}
                  <td className="px-4 py-3">
                    <RelativeTime iso={v.created_at} />
                  </td>

                  {/* Arrow */}
                  <td className="px-4 py-3 text-right">
                    <svg className="w-4 h-4 text-gray-300 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
