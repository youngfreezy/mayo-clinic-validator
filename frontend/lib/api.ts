export interface AgentFinding {
  agent: string;
  passed: boolean;
  score: number;
  passed_checks: string[];
  issues: string[];
  recommendations: string[];
}

export interface ValidationSummary {
  validation_id: string;
  url: string;
  status: string;
  overall_score: number | null;
  overall_passed: boolean | null;
  created_at: string;
}

export interface ValidationState extends ValidationSummary {
  findings: AgentFinding[];
  errors: string[];
}

export interface RoutingInfo {
  agents_to_run: string[];
  agents_skipped: string[];
  content_type: string;
  routing_method: string;
}

export interface JudgeRecommendation {
  recommendation: "approve" | "reject" | "needs_revision";
  confidence: "high" | "medium" | "low";
  key_concerns: string[];
  strengths: string[];
  rationale: string;
}

export type SSEEvent =
  | { type: "status"; data: { status: string; validation_id?: string } }
  | { type: "routing"; data: RoutingInfo }
  | { type: "agent_complete"; data: { agent: string; finding: AgentFinding | null } }
  | { type: "judge"; data: JudgeRecommendation }
  | { type: "hitl"; data: { validation_id: string; overall_score: number; overall_passed: boolean; findings: AgentFinding[]; skipped_agents?: string[]; routing_decision?: RoutingInfo; judge_recommendation?: JudgeRecommendation } }
  | { type: "done"; data: { status: string } }
  | { type: "error"; data: { message: string } }
  | { type: "ping" };

export async function startValidation(url: string): Promise<{ validation_id: string }> {
  const res = await fetch("/api/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, requested_by: "web-user" }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to start validation");
  }
  return res.json();
}

export async function submitDecision(
  validationId: string,
  decision: "approve" | "reject",
  feedback?: string
): Promise<void> {
  const res = await fetch(`/api/validate/${validationId}/decide`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      decision,
      feedback: feedback || "",
      reviewer_id: "web-user",
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to submit decision");
  }
}

export async function listValidations(): Promise<ValidationSummary[]> {
  const res = await fetch("/api/validations");
  if (!res.ok) return [];
  return res.json();
}

export function createSSEConnection(validationId: string): EventSource {
  // In development, connect directly to the FastAPI backend to avoid
  // Next.js rewrite proxy buffering SSE events. In production, nginx
  // handles SSE with proxy_buffering off, so the relative URL works.
  const base =
    process.env.NEXT_PUBLIC_API_URL ||
    (typeof window !== "undefined" && window.location.port === "3000"
      ? "http://localhost:8000"
      : "");
  return new EventSource(`${base}/api/validate/${validationId}/stream`);
}

export function agentLabel(agent: string): string {
  const labels: Record<string, string> = {
    metadata: "Metadata & SEO",
    editorial: "Editorial Quality",
    compliance: "Regulatory Compliance",
    accuracy: "Medical Accuracy",
    empty_tag: "Empty Tag Check",
  };
  return labels[agent] || agent;
}

export interface AgentMethodology {
  agentType: string;
  model: string;
  methodology: string;
}

const AGENT_METHODOLOGY: Record<string, AgentMethodology> = {
  metadata: {
    agentType: "Metadata Agent",
    model: "Rule-based parser",
    methodology:
      "Validates SSR HTML metadata: title, description, canonical URL, OpenGraph, and JSON-LD structure.",
  },
  editorial: {
    agentType: "Editorial Agent",
    model: "LLM evaluation + structure checks",
    methodology:
      "Reviews readability, heading hierarchy, sourcing/attribution, and review-date signals for editorial quality.",
  },
  compliance: {
    agentType: "Compliance Agent",
    model: "Policy prompt + deterministic checks",
    methodology:
      "Flags unsupported medical claims, missing disclaimers, and language that may violate healthcare communication rules.",
  },
  accuracy: {
    agentType: "Accuracy Agent",
    model: "RAG fact-checking",
    methodology:
      "Compares extracted page claims with trusted Mayo knowledge chunks and scores factual alignment and contradictions.",
  },
  empty_tag: {
    agentType: "Empty Tag Agent",
    model: "Deterministic HTML scanner",
    methodology:
      "Scans raw HTML for self-closing or empty tags (e.g. <title/>) that should contain content. Only runs on HIL pages.",
  },
  judge: {
    agentType: "LLM-as-a-Judge",
    model: "GPT-5-mini (JSON mode)",
    methodology:
      "Synthesizes all agent findings into a single recommendation (approve/reject/needs_revision) with confidence level and rationale.",
  },
};

export function agentMethodology(agent: string): AgentMethodology {
  return (
    AGENT_METHODOLOGY[agent] || {
      agentType: `${agentLabel(agent)} Agent`,
      model: "Specialized evaluation",
      methodology: "Runs targeted quality checks for this validation stage.",
    }
  );
}

export function scoreColor(score: number): string {
  if (score >= 0.85) return "text-green-600";
  if (score >= 0.7) return "text-yellow-600";
  return "text-red-600";
}

export function scoreBg(score: number): string {
  if (score >= 0.85) return "bg-green-50 border-green-200";
  if (score >= 0.7) return "bg-yellow-50 border-yellow-200";
  return "bg-red-50 border-red-200";
}
