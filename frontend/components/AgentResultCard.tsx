"use client";

import { AgentFinding, agentLabel, agentMethodology, scoreColor, scoreBg } from "@/lib/api";

interface Props {
  finding: AgentFinding;
}

export function AgentResultCard({ finding }: Props) {
  const pct = Math.round(finding.score * 100);
  const method = agentMethodology(finding.agent);

  return (
    <div className={`rounded-xl border p-5 ${scoreBg(finding.score)}`}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <span className="text-sm font-semibold text-gray-900">
            {agentLabel(finding.agent)}
          </span>
          <span
            className={`ml-2 text-xs font-medium px-2 py-0.5 rounded-full ${
              finding.passed
                ? "bg-green-100 text-green-700"
                : "bg-red-100 text-red-700"
            }`}
          >
            {finding.passed ? "PASS" : "FAIL"}
          </span>
        </div>
        <div className="text-right">
          <span className={`text-2xl font-bold ${scoreColor(finding.score)}`}>
            {pct}
          </span>
          <span className="text-xs text-gray-400 ml-0.5">/ 100</span>
        </div>
      </div>

      {/* Score bar */}
      <div className="w-full bg-gray-200 rounded-full h-1.5 mb-4">
        <div
          className={`h-1.5 rounded-full transition-all ${
            finding.score >= 0.85
              ? "bg-green-500"
              : finding.score >= 0.7
              ? "bg-yellow-500"
              : "bg-red-500"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>

      <div className="mb-4 rounded-lg border border-gray-200 bg-white/70 px-3 py-2.5">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Agent used</p>
        <p className="mt-0.5 text-xs font-medium text-gray-900">{method.agentType}</p>
        <p className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-gray-500">Methodology</p>
        <p className="mt-0.5 text-xs text-gray-700">{method.methodology}</p>
        <p className="mt-2 text-[11px] text-gray-500">Model: {method.model}</p>
      </div>

      {finding.passed_checks?.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
            Passed Checks
          </p>
          <ul className="space-y-1">
            {finding.passed_checks.map((check, i) => (
              <li key={i} className="flex gap-2 text-xs text-gray-700">
                <span className="text-green-500 flex-shrink-0 mt-0.5">✓</span>
                <span>{check}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {finding.issues.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
            Issues
          </p>
          <ul className="space-y-1">
            {finding.issues.map((issue, i) => (
              <li key={i} className="flex gap-2 text-xs text-gray-700">
                <span className="text-red-400 flex-shrink-0 mt-0.5">•</span>
                <span>{issue}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {finding.recommendations.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
            Recommendations
          </p>
          <ul className="space-y-1">
            {finding.recommendations.map((rec, i) => (
              <li key={i} className="flex gap-2 text-xs text-gray-700">
                <span className="text-blue-400 flex-shrink-0 mt-0.5">→</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {finding.issues.length === 0 && finding.recommendations.length === 0 && (
        <p className="text-xs text-gray-500 italic">No issues found.</p>
      )}

      {finding.agent === "metadata" && (
        <div className="mt-4 flex gap-2 rounded-lg bg-blue-50 border border-blue-100 px-3 py-2">
          <svg className="w-3.5 h-3.5 text-blue-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20A10 10 0 0012 2z" />
          </svg>
          <p className="text-xs text-blue-700">
            Analysis is based on the <strong>initial SSR HTML response</strong> — before
            client-side JavaScript runs. Tags injected via JS hydration (common in Next.js
            apps) will appear missing here, and will also be invisible to search engine
            crawlers that parse raw HTML.
          </p>
        </div>
      )}
    </div>
  );
}
