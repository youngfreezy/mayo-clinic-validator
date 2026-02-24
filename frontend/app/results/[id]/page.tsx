"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  createSSEConnection,
  AgentFinding,
  SSEEvent,
  RoutingInfo,
  JudgeRecommendation,
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
  const [skippedAgents, setSkippedAgents] = useState<Set<string>>(new Set());
  const [routingInfo, setRoutingInfo] = useState<RoutingInfo | null>(null);
  const [judgeRecommendation, setJudgeRecommendation] = useState<JudgeRecommendation | null>(null);

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

        // Restore routing info from persisted state
        if (s.routing_decision) {
          setRoutingInfo(s.routing_decision);
          setSkippedAgents(new Set(s.routing_decision.agents_skipped || []));
        } else if (s.skipped_agents?.length) {
          setSkippedAgents(new Set(s.skipped_agents));
        }

        if (s.judge_recommendation) setJudgeRecommendation(s.judge_recommendation);

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

        if (event.type === "routing") {
          setRoutingInfo(event.data);
          setSkippedAgents(new Set(event.data.agents_skipped));
        }

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

        if (event.type === "judge") {
          setJudgeRecommendation(event.data);
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
          if (event.data.skipped_agents) {
            setSkippedAgents(new Set(event.data.skipped_agents));
          }
          if (event.data.routing_decision) {
            setRoutingInfo(event.data.routing_decision);
          }
          if (event.data.judge_recommendation) {
            setJudgeRecommendation(event.data.judge_recommendation);
          }
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
        routingInfo={routingInfo}
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
            skippedAgents={skippedAgents}
            routingInfo={routingInfo}
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
              judgeRecommendation={judgeRecommendation}
              onDecisionSubmitted={() => setShowHITL(false)}
            />
          )}

          {/* Judge recommendation card (shown when not in HITL panel) */}
          {judgeRecommendation && !showHITL && (
            <div className="rounded-2xl border border-indigo-200 bg-indigo-50 p-5" data-testid="judge-card">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-6 h-6 bg-indigo-100 rounded-full flex items-center justify-center">
                  <svg className="w-3.5 h-3.5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
                <h3 className="text-sm font-semibold text-indigo-900">LLM Judge Recommendation</h3>
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
                    : "bg-gray-100 text-gray-600"
                }`}>
                  {judgeRecommendation.confidence} confidence
                </span>
              </div>
              <p className="text-sm text-indigo-800 mb-3">{judgeRecommendation.rationale}</p>
              <div className="grid grid-cols-2 gap-4">
                {judgeRecommendation.key_concerns.length > 0 && (
                  <div>
                    <p className="text-[11px] font-semibold text-red-600 uppercase tracking-wide mb-1">Key Concerns</p>
                    <ul className="text-xs text-gray-700 space-y-1">
                      {judgeRecommendation.key_concerns.map((c, i) => (
                        <li key={i} className="flex gap-1.5">
                          <span className="text-red-400 flex-shrink-0 mt-0.5">!</span>
                          <span>{c}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {judgeRecommendation.strengths.length > 0 && (
                  <div>
                    <p className="text-[11px] font-semibold text-green-600 uppercase tracking-wide mb-1">Strengths</p>
                    <ul className="text-xs text-gray-700 space-y-1">
                      {judgeRecommendation.strengths.map((s, i) => (
                        <li key={i} className="flex gap-1.5">
                          <span className="text-green-400 flex-shrink-0 mt-0.5">+</span>
                          <span>{s}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
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
