"use client";

import { RoutingInfo } from "@/lib/api";

interface Props {
  overallScore: number | null;
  overallPassed: boolean | null;
  status: string;
  url: string;
  routingInfo?: RoutingInfo | null;
}

export function ScoreSummary({ overallScore, overallPassed, status, url, routingInfo }: Props) {
  const pct = overallScore !== null ? Math.round(overallScore * 100) : null;

  const statusLabel: Record<string, { label: string; color: string; bg: string }> = {
    pending: { label: "Pending", color: "text-gray-600", bg: "bg-gray-100" },
    scraping: { label: "Scraping", color: "text-blue-600", bg: "bg-blue-100" },
    running: { label: "Validating", color: "text-blue-600", bg: "bg-blue-100" },
    awaiting_human: { label: "Awaiting Review", color: "text-yellow-700", bg: "bg-yellow-100" },
    approved: { label: "Approved", color: "text-green-700", bg: "bg-green-100" },
    rejected: { label: "Rejected", color: "text-red-700", bg: "bg-red-100" },
    failed: { label: "Failed", color: "text-red-700", bg: "bg-red-100" },
  };

  const s = statusLabel[status] || statusLabel.pending;

  const agentCount = routingInfo?.agents_to_run.length ?? 4;
  const isHil = routingInfo?.content_type === "hil";

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="min-w-0">
          <p className="text-xs text-gray-400 mb-1 truncate" title={url}>
            {url}
          </p>
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`text-xs font-semibold px-2.5 py-1 rounded-full ${s.bg} ${s.color}`}
            >
              {s.label}
            </span>
            {overallPassed !== null && (
              <span
                className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                  overallPassed
                    ? "bg-green-100 text-green-700"
                    : "bg-red-100 text-red-700"
                }`}
              >
                {overallPassed ? "All Checks Passed" : "Issues Found"}
              </span>
            )}
            {isHil && (
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-blue-100 text-blue-700">
                HIL Content
              </span>
            )}
          </div>
        </div>

        {pct !== null && (
          <div className="flex flex-col items-center">
            <div className="relative w-20 h-20">
              <svg className="w-20 h-20 -rotate-90" viewBox="0 0 36 36">
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke="#e5e7eb"
                  strokeWidth="3"
                />
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke={pct >= 85 ? "#22c55e" : pct >= 70 ? "#eab308" : "#ef4444"}
                  strokeWidth="3"
                  strokeDasharray={`${pct}, 100`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-xl font-bold text-gray-900">{pct}</span>
                <span className="text-xs text-gray-400">/ 100</span>
              </div>
            </div>
            <span className="text-xs text-gray-500 mt-1">Overall Score</span>
          </div>
        )}
      </div>

      {overallScore !== null && (
        <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">
            How scoring works
          </p>
          <p className="mt-1 text-xs text-gray-700">
            Overall score is the average of {agentCount} dispatched agent scores
            {isHil ? " (including empty tag check for HIL content)" : ""}.
            The content-level pass/fail flag requires all dispatched agents to pass, then a human
            reviewer makes the final approve/reject decision.
          </p>
          {routingInfo && routingInfo.agents_skipped.length > 0 && (
            <p className="mt-1 text-xs text-gray-500">
              Skipped: {routingInfo.agents_skipped.join(", ")}
            </p>
          )}
        </div>
      )}

      {/* LangSmith trace link */}
      {overallScore !== null && (
        <div className="mt-3 flex items-center gap-2">
          <a
            href="https://smith.langchain.com"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-800 font-medium"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
            View traces in LangSmith
          </a>
        </div>
      )}
    </div>
  );
}
