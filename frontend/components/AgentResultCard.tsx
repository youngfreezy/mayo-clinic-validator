"use client";

import { AgentFinding, agentLabel, agentMethodology, scoreColor, scoreBg } from "@/lib/api";

interface Props {
  finding: AgentFinding;
  rulesSource?: string;
  rulesVersion?: string;
}

export function AgentResultCard({ finding, rulesSource, rulesVersion }: Props) {
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
        {rulesSource && (
          <div className="mt-2 flex items-center gap-1.5">
            <span
              className={`inline-block w-1.5 h-1.5 rounded-full ${
                rulesSource === "neo4j" ? "bg-cyan-500" : "bg-gray-400"
              }`}
            />
            <span className="text-[11px] text-gray-500">
              Rules: {rulesSource === "neo4j" ? "Neo4j Graph" : "JSON Fallback"}
              {rulesVersion ? ` v${rulesVersion}` : ""}
            </span>
          </div>
        )}
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

      {/* RAGAS metrics — only shown for accuracy agent when available */}
      {finding.ragas_scores && Object.keys(finding.ragas_scores).length > 0 && (
        <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50/50 px-3 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-rose-600 mb-2">
            RAGAS Evaluation — RAG Quality Metrics
          </p>
          <div className="grid grid-cols-2 gap-2">
            {[
              { key: "faithfulness" as const, label: "Faithfulness", desc: "Claims supported by evidence", type: "GEN" },
              { key: "answer_relevancy" as const, label: "Answer Relevancy", desc: "Output stays on-topic", type: "GEN" },
              { key: "context_precision" as const, label: "Context Precision", desc: "Relevant chunks ranked higher", type: "RET" },
              { key: "context_recall" as const, label: "Context Recall", desc: "All needed refs retrieved", type: "RET" },
            ].map((metric) => {
              const val = finding.ragas_scores?.[metric.key];
              if (val === undefined) return null;
              const pctVal = Math.round(val * 100);
              return (
                <div key={metric.key} className="flex items-center gap-2 text-xs">
                  <span className={`text-[9px] font-bold px-1 py-0.5 rounded ${
                    metric.type === "GEN" ? "bg-rose-200 text-rose-700" : "bg-purple-200 text-purple-700"
                  }`}>
                    {metric.type}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-700 font-medium truncate" title={metric.desc}>{metric.label}</span>
                      <span className={`font-bold ml-1 ${
                        val >= 0.85 ? "text-green-600" : val >= 0.7 ? "text-yellow-600" : "text-red-600"
                      }`}>
                        {pctVal}%
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-1 mt-0.5">
                      <div
                        className={`h-1 rounded-full ${
                          val >= 0.85 ? "bg-green-500" : val >= 0.7 ? "bg-yellow-500" : "bg-red-500"
                        }`}
                        style={{ width: `${pctVal}%` }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
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
