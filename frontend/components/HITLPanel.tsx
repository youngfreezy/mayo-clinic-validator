"use client";

import { useState } from "react";
import { submitDecision, AgentFinding, JudgeRecommendation } from "@/lib/api";

interface Props {
  validationId: string;
  overallScore: number;
  overallPassed: boolean;
  findings: AgentFinding[];
  judgeRecommendation?: JudgeRecommendation | null;
  onDecisionSubmitted: () => void;
}

export function HITLPanel({
  validationId,
  overallScore,
  overallPassed,
  findings,
  judgeRecommendation,
  onDecisionSubmitted,
}: Props) {
  const [feedback, setFeedback] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  const failedAgents = findings.filter((f) => !f.passed);
  const pct = Math.round(overallScore * 100);

  async function handleDecision(decision: "approve" | "reject") {
    setSubmitting(true);
    setError("");
    try {
      await submitDecision(validationId, decision, feedback);
      setSubmitted(true);
      onDecisionSubmitted();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to submit decision");
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="bg-blue-50 border border-blue-200 rounded-2xl p-6 text-center">
        <p className="text-sm text-blue-700 font-medium">
          Decision submitted — waiting for pipeline to complete...
        </p>
        <div className="mt-3 flex justify-center">
          <svg className="animate-spin h-5 w-5 text-blue-500" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-amber-50 border-2 border-amber-300 rounded-2xl p-6 shadow-sm">
      <div className="flex items-start gap-3 mb-4">
        <div className="w-8 h-8 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0">
          <svg className="w-4 h-4 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <div>
          <h3 className="text-base font-semibold text-amber-900">
            Human Review Required
          </h3>
          <p className="text-sm text-amber-700 mt-0.5">
            All agents have completed. Review the findings and approve or reject
            this content for publication.
          </p>
        </div>
      </div>

      {/* Quick summary */}
      <div className="flex gap-3 mb-4 text-sm">
        <div className="flex-1 bg-white rounded-lg border border-amber-200 p-3 text-center">
          <div className="text-2xl font-bold text-gray-900">{pct}</div>
          <div className="text-xs text-gray-500">Overall Score</div>
        </div>
        <div className="flex-1 bg-white rounded-lg border border-amber-200 p-3 text-center">
          <div className="text-2xl font-bold text-red-600">{failedAgents.length}</div>
          <div className="text-xs text-gray-500">Agents Failed</div>
        </div>
        <div className="flex-1 bg-white rounded-lg border border-amber-200 p-3 text-center">
          <div className="text-2xl font-bold text-green-600">
            {findings.length - failedAgents.length}
          </div>
          <div className="text-xs text-gray-500">Agents Passed</div>
        </div>
      </div>

      {/* Judge Recommendation */}
      {judgeRecommendation && (
        <div className="mb-4 rounded-lg border border-indigo-200 bg-indigo-50 p-4" data-testid="judge-recommendation">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-5 h-5 bg-indigo-100 rounded-full flex items-center justify-center">
              <svg className="w-3 h-3 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <h4 className="text-sm font-semibold text-indigo-900">LLM Judge Recommendation</h4>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              judgeRecommendation.recommendation === "approve"
                ? "bg-green-100 text-green-700"
                : judgeRecommendation.recommendation === "reject"
                ? "bg-red-100 text-red-700"
                : "bg-yellow-100 text-yellow-700"
            }`}>
              {judgeRecommendation.recommendation.replace("_", " ")}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              judgeRecommendation.confidence === "high"
                ? "bg-indigo-100 text-indigo-700"
                : judgeRecommendation.confidence === "medium"
                ? "bg-gray-100 text-gray-600"
                : "bg-gray-100 text-gray-500"
            }`}>
              {judgeRecommendation.confidence} confidence
            </span>
          </div>
          <p className="text-xs text-indigo-800 mb-2">{judgeRecommendation.rationale}</p>
          {judgeRecommendation.key_concerns.length > 0 && (
            <div className="mb-1.5">
              <p className="text-[11px] font-semibold text-red-600 uppercase tracking-wide mb-0.5">Key Concerns</p>
              <ul className="text-xs text-gray-700 space-y-0.5">
                {judgeRecommendation.key_concerns.map((c, i) => (
                  <li key={i} className="flex gap-1.5">
                    <span className="text-red-400 flex-shrink-0">!</span>
                    {c}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {judgeRecommendation.strengths.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold text-green-600 uppercase tracking-wide mb-0.5">Strengths</p>
              <ul className="text-xs text-gray-700 space-y-0.5">
                {judgeRecommendation.strengths.map((s, i) => (
                  <li key={i} className="flex gap-1.5">
                    <span className="text-green-400 flex-shrink-0">+</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Feedback */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-1.5">
          Reviewer Notes (optional)
        </label>
        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          rows={3}
          placeholder="Add any notes about your decision..."
          className="w-full border border-amber-300 rounded-lg px-3 py-2 text-sm
                     focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-transparent
                     bg-white resize-none"
          disabled={submitting}
        />
      </div>

      {error && (
        <p className="text-xs text-red-600 mb-3">{error}</p>
      )}

      {/* Action buttons */}
      <div className="flex gap-3">
        <button
          onClick={() => handleDecision("approve")}
          disabled={submitting}
          className="flex-1 bg-green-600 hover:bg-green-700 text-white font-semibold
                     py-3 rounded-xl text-sm transition-colors disabled:opacity-50
                     flex items-center justify-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          Approve for Publication
        </button>
        <button
          onClick={() => handleDecision("reject")}
          disabled={submitting}
          className="flex-1 bg-red-600 hover:bg-red-700 text-white font-semibold
                     py-3 rounded-xl text-sm transition-colors disabled:opacity-50
                     flex items-center justify-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
          Reject
        </button>
      </div>
    </div>
  );
}
