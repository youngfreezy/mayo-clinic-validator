import Link from "next/link";
import { URLInputForm } from "@/components/URLInputForm";
import { ValidationHistoryTable } from "@/components/ValidationHistoryTable";

export default function HomePage() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Content Validation Dashboard</h2>
        <p className="text-gray-500 mt-1 text-sm">
          Multi-agent LangGraph pipeline: Triage · Metadata · Editorial · Compliance · Accuracy (RAG) · Empty Tag · LLM Judge
        </p>
      </div>

      {/* Agent pipeline diagram */}
      <div className="bg-white rounded-2xl border border-gray-200 p-5">
        <div className="flex items-center mb-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Pipeline Architecture
          </p>
          <Link
            href="/pipeline"
            className="ml-2 text-gray-400 hover:text-mayo-blue transition-colors"
            title="View full architecture diagram"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <circle cx="12" cy="12" r="10" strokeWidth={2} />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8h.01M11 12h1v4h1" />
            </svg>
          </Link>
        </div>
        <div className="flex items-center gap-2 flex-wrap text-xs">
          {[
            "URL Input",
            "Scrape Content",
            "Content Triage",
            "Metadata Agent",
            "Editorial Agent",
            "Compliance Agent",
            "Accuracy Agent (RAG)",
            "Empty Tag Check",
            "Aggregate",
            "LLM Judge",
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
