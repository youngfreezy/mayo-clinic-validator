export interface AgentFinding {
  agent: string;
  passed: boolean;
  score: number;
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

export type SSEEvent =
  | { type: "status"; data: { status: string; validation_id?: string } }
  | { type: "agent_complete"; data: { agent: string; finding: AgentFinding | null } }
  | { type: "hitl"; data: { validation_id: string; overall_score: number; overall_passed: boolean; findings: AgentFinding[] } }
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
  const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return new EventSource(`${base}/api/validate/${validationId}/stream`);
}

export function agentLabel(agent: string): string {
  const labels: Record<string, string> = {
    metadata: "Metadata & SEO",
    editorial: "Editorial Quality",
    compliance: "Regulatory Compliance",
    accuracy: "Medical Accuracy",
  };
  return labels[agent] || agent;
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
