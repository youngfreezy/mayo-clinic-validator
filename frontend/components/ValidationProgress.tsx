"use client";

const STEPS = [
  { key: "scraping", label: "Scraping URL", description: "Fetching Mayo Clinic page content" },
  { key: "metadata", label: "Metadata & SEO", description: "Checking meta tags, JSON-LD, canonical URL" },
  { key: "editorial", label: "Editorial Quality", description: "Headings, last reviewed, attribution" },
  { key: "compliance", label: "Regulatory Compliance", description: "FDA language, disclaimers, prohibited claims" },
  { key: "accuracy", label: "Medical Accuracy", description: "RAG fact-check against knowledge base" },
  { key: "hitl", label: "Human Review", description: "Awaiting editorial approval" },
];

type StepState = "pending" | "running" | "done" | "skipped";

interface Props {
  status: string;
  completedAgents: Set<string>;
  agentPassed: Record<string, boolean>;
}

export function ValidationProgress({ status, completedAgents, agentPassed }: Props) {
  function getStepState(key: string): StepState {
    if (key === "scraping") {
      if (status === "pending") return "pending";
      if (status === "scraping") return "running";
      return "done";
    }
    if (["metadata", "editorial", "compliance", "accuracy"].includes(key)) {
      if (status === "pending" || status === "scraping") return "pending";
      if (status === "running" && !completedAgents.has(key)) return "running";
      if (completedAgents.has(key)) return "done";
      return "pending";
    }
    if (key === "hitl") {
      if (status === "awaiting_human") return "running";
      if (status === "approved" || status === "rejected") return "done";
      return "pending";
    }
    return "pending";
  }

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-sm font-semibold text-gray-700 mb-5 uppercase tracking-wide">
        Pipeline Progress
      </h3>
      <div className="space-y-0">
        {STEPS.map((step, idx) => {
          const state = getStepState(step.key);
          const isAgent = ["metadata", "editorial", "compliance", "accuracy"].includes(step.key);
          const passed = isAgent ? agentPassed[step.key] : undefined;

          return (
            <div key={step.key} className="flex gap-4">
              {/* Connector line + icon */}
              <div className="flex flex-col items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 border-2 transition-all
                    ${state === "done"
                      ? passed === false
                        ? "bg-red-100 border-red-400"
                        : "bg-green-100 border-green-500"
                      : state === "running"
                      ? "bg-blue-100 border-mayo-blue animate-pulse"
                      : "bg-gray-100 border-gray-300"
                    }`}
                >
                  {state === "done" ? (
                    passed === false ? (
                      <svg className="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    )
                  ) : state === "running" ? (
                    <div className="w-3 h-3 rounded-full bg-mayo-blue animate-pulse" />
                  ) : (
                    <div className="w-2 h-2 rounded-full bg-gray-300" />
                  )}
                </div>
                {idx < STEPS.length - 1 && (
                  <div
                    className={`w-0.5 flex-1 min-h-6 my-1 ${
                      state === "done" ? "bg-green-300" : "bg-gray-200"
                    }`}
                  />
                )}
              </div>

              {/* Content */}
              <div className="pb-6 pt-0.5 flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className={`text-sm font-medium ${
                      state === "running"
                        ? "text-mayo-blue"
                        : state === "done"
                        ? "text-gray-900"
                        : "text-gray-400"
                    }`}
                  >
                    {step.label}
                  </span>
                  {state === "running" && (
                    <span className="text-xs text-mayo-blue animate-pulse">
                      Running...
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-400 mt-0.5">{step.description}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
