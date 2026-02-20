"use client";

interface Props {
  overallScore: number | null;
  overallPassed: boolean | null;
  status: string;
  url: string;
}

export function ScoreSummary({ overallScore, overallPassed, status, url }: Props) {
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
    </div>
  );
}
