"use client";

import { useState } from "react";
import { submitDecision, AgentFinding } from "@/lib/api";

interface Props {
  validationId: string;
  overallScore: number;
  overallPassed: boolean;
  findings: AgentFinding[];
  onDecisionSubmitted: () => void;
}

export function HITLPanel({
  validationId,
  overallScore,
  overallPassed,
  findings,
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
