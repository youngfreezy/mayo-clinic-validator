"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  createSSEConnection,
  AgentFinding,
  SSEEvent,
} from "@/lib/api";
import { ValidationProgress } from "@/components/ValidationProgress";
import { AgentResultCard } from "@/components/AgentResultCard";
import { HITLPanel } from "@/components/HITLPanel";
import { ScoreSummary } from "@/components/ScoreSummary";

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [status, setStatus] = useState<string>("pending");
  const [url, setUrl] = useState<string>("");
  const [findings, setFindings] = useState<AgentFinding[]>([]);
  const [completedAgents, setCompletedAgents] = useState<Set<string>>(new Set());
  const [agentPassed, setAgentPassed] = useState<Record<string, boolean>>({});
  const [overallScore, setOverallScore] = useState<number | null>(null);
  const [overallPassed, setOverallPassed] = useState<boolean | null>(null);
  const [showHITL, setShowHITL] = useState(false);
  const [hitlData, setHitlData] = useState<{ overall_score: number; overall_passed: boolean; findings: AgentFinding[] } | null>(null);
  const [finalStatus, setFinalStatus] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");

  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!id) return;

    // Fetch current state first; only open SSE if not already in a terminal state.
    fetch(`/api/validate/${id}`)
      .then((r) => r.json())
      .then((s) => {
        if (s.url) setUrl(s.url);
        if (s.status) setStatus(s.status);
        if (s.overall_score !== null) setOverallScore(s.overall_score);
        if (s.overall_passed !== null) setOverallPassed(s.overall_passed);

        if (["approved", "rejected", "failed"].includes(s.status)) {
          // Already done — restore full state without opening SSE
          setFinalStatus(s.status);
          if (s.findings?.length) setFindings(s.findings);
          const cAgents = new Set<string>(s.findings?.map((f: AgentFinding) => f.agent) || []);
          setCompletedAgents(cAgents);
          const passed: Record<string, boolean> = {};
          (s.findings || []).forEach((f: AgentFinding) => { passed[f.agent] = f.passed; });
          setAgentPassed(passed);
          return; // skip SSE
        }

        if (s.status === "awaiting_human" && s.findings?.length) {
          // Graph is paused at HITL — restore agent findings and show HITL panel
          setFindings(s.findings);
          const cAgents = new Set<string>(s.findings.map((f: AgentFinding) => f.agent));
          setCompletedAgents(cAgents);
          const passed: Record<string, boolean> = {};
          s.findings.forEach((f: AgentFinding) => { passed[f.agent] = f.passed; });
          setAgentPassed(passed);
          setHitlData({ overall_score: s.overall_score, overall_passed: s.overall_passed, findings: s.findings });
          setShowHITL(true);
          setStatus("awaiting_human");
          // Still open SSE so the done event arrives after they approve/reject
        }

        // Open SSE for in-progress or awaiting_human validations
        const es = createSSEConnection(id);
        esRef.current = es;

        es.onmessage = handleSSEMessage(es);
        es.onerror = () => { if (finalStatus) es.close(); };
      })
      .catch(() => {
        // Backend unreachable — still try SSE
        const es = createSSEConnection(id);
        esRef.current = es;
        es.onmessage = handleSSEMessage(es);
      });

    function handleSSEMessage(es: EventSource) {
      return (e: MessageEvent) => {
        let event: SSEEvent;
        try { event = JSON.parse(e.data); } catch { return; }
        if (event.type === "ping") return;

        if (event.type === "status") setStatus(event.data.status);

        if (event.type === "agent_complete") {
          const { agent, finding } = event.data;
          setCompletedAgents((prev) => new Set([...prev, agent]));
          if (finding) {
            setFindings((prev) => {
              const exists = prev.some((f) => f.agent === agent);
              return exists ? prev : [...prev, finding];
            });
            setAgentPassed((prev) => ({ ...prev, [agent]: finding.passed }));
          }
        }

        if (event.type === "hitl") {
          const { overall_score, overall_passed, findings: f } = event.data;
          setOverallScore(overall_score);
          setOverallPassed(overall_passed);
          setFindings(f);
          const cAgents = new Set<string>(f.map((fi) => fi.agent));
          setCompletedAgents(cAgents);
          const passed: Record<string, boolean> = {};
          f.forEach((fi) => { passed[fi.agent] = fi.passed; });
          setAgentPassed(passed);
          setHitlData({ overall_score, overall_passed, findings: f });
          setShowHITL(true);
          setStatus("awaiting_human");
        }

        if (event.type === "done") {
          setFinalStatus(event.data.status);
          setStatus(event.data.status);
          setShowHITL(false);
          es.close();
        }

        if (event.type === "error") {
          setErrorMsg(event.data.message);
          setStatus("failed");
          es.close();
        }
      };
    }

    // No SSE opened here — done inside the fetch .then() above

    return () => {
      esRef.current?.close();
    };
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const isTerminal = finalStatus !== null || ["approved", "rejected", "failed"].includes(status);

  return (
    <div className="space-y-6">
      {/* Back link */}
      <button
        onClick={() => router.push("/")}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back to Dashboard
      </button>

      {/* Score summary */}
      <ScoreSummary
        overallScore={overallScore}
        overallPassed={overallPassed}
        status={finalStatus || status}
        url={url || `Validation ${id?.slice(0, 8)}...`}
      />

      {/* Error */}
      {errorMsg && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <p className="text-sm text-red-700 font-medium">Error</p>
          <p className="text-xs text-red-600 mt-1">{errorMsg}</p>
        </div>
      )}

      {/* Final status banner */}
      {isTerminal && !errorMsg && (
        <div
          className={`rounded-xl p-4 text-center font-semibold text-sm ${
            finalStatus === "approved" || status === "approved"
              ? "bg-green-50 border border-green-200 text-green-700"
              : finalStatus === "rejected" || status === "rejected"
              ? "bg-red-50 border border-red-200 text-red-700"
              : "bg-gray-50 border border-gray-200 text-gray-600"
          }`}
        >
          {(finalStatus || status) === "approved"
            ? "Content approved for publication."
            : (finalStatus || status) === "rejected"
            ? "Content rejected — review agent findings for required changes."
            : "Validation complete."}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: pipeline progress */}
        <div className="lg:col-span-1">
          <ValidationProgress
            status={finalStatus || status}
            completedAgents={completedAgents}
            agentPassed={agentPassed}
          />
        </div>

        {/* Right: agent results + HITL */}
        <div className="lg:col-span-2 space-y-4">
          {/* HITL panel */}
          {showHITL && hitlData && (
            <HITLPanel
              validationId={id}
              overallScore={hitlData.overall_score}
              overallPassed={hitlData.overall_passed}
              findings={hitlData.findings}
              onDecisionSubmitted={() => setShowHITL(false)}
            />
          )}

          {/* Agent result cards */}
          {findings.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                Agent Findings
              </h3>
              {findings.map((f) => (
                <AgentResultCard key={f.agent} finding={f} />
              ))}
            </div>
          )}

          {/* Waiting state */}
          {findings.length === 0 && !errorMsg && !isTerminal && (
            <div className="bg-white rounded-2xl border border-gray-200 p-10 text-center">
              <div className="flex justify-center mb-3">
                <svg className="animate-spin h-8 w-8 text-mayo-blue" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              </div>
              <p className="text-sm text-gray-500">
                {status === "scraping"
                  ? "Scraping Mayo Clinic page..."
                  : status === "running"
                  ? "Agents are analyzing content..."
                  : "Initializing pipeline..."}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
