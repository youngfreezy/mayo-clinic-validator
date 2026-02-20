import { URLInputForm } from "@/components/URLInputForm";
import { ValidationHistoryTable } from "@/components/ValidationHistoryTable";

export default function HomePage() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Content Validation Dashboard</h2>
        <p className="text-gray-500 mt-1 text-sm">
          4-agent LangGraph pipeline: Metadata · Editorial · Compliance · Accuracy (RAG)
        </p>
      </div>

      {/* Agent pipeline diagram */}
      <div className="bg-white rounded-2xl border border-gray-200 p-5">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-4">
          Pipeline Architecture
        </p>
        <div className="flex items-center gap-2 flex-wrap text-xs">
          {[
            "URL Input",
            "Scrape Content",
            "Metadata Agent",
            "Editorial Agent",
            "Compliance Agent",
            "Accuracy Agent (RAG)",
            "Aggregate",
            "Human Gate (HITL)",
            "Approve / Reject",
          ].map((step, i, arr) => (
            <div key={step} className="flex items-center gap-2">
              <span className="bg-mayo-blue text-white px-2.5 py-1 rounded-md font-medium whitespace-nowrap">
                {step}
              </span>
              {i < arr.length - 1 && (
                <svg
                  className="w-3 h-3 text-gray-400 flex-shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* URL Input */}
      <URLInputForm />

      {/* Validation history — client component, auto-refreshes every 10s */}
      <ValidationHistoryTable />
    </div>
  );
}
