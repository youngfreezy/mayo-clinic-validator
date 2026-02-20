import { URLInputForm } from "@/components/URLInputForm";
import { listValidations } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let recent: Awaited<ReturnType<typeof listValidations>> = [];
  try {
    recent = await listValidations();
  } catch {
    // Backend might not be running yet
  }

  const statusBadge = (status: string) => {
    const map: Record<string, string> = {
      pending: "bg-gray-100 text-gray-600",
      scraping: "bg-blue-100 text-blue-700",
      running: "bg-blue-100 text-blue-700",
      awaiting_human: "bg-yellow-100 text-yellow-700",
      approved: "bg-green-100 text-green-700",
      rejected: "bg-red-100 text-red-700",
      failed: "bg-red-100 text-red-700",
    };
    return map[status] || "bg-gray-100 text-gray-600";
  };

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
          {["URL Input", "Scrape Content", "Metadata Agent", "Editorial Agent", "Compliance Agent", "Accuracy Agent (RAG)", "Aggregate", "Human Gate (HITL)", "Approve / Reject"].map(
            (step, i, arr) => (
              <div key={step} className="flex items-center gap-2">
                <span className="bg-mayo-blue text-white px-2.5 py-1 rounded-md font-medium whitespace-nowrap">
                  {step}
                </span>
                {i < arr.length - 1 && (
                  <svg className="w-3 h-3 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                )}
              </div>
            )
          )}
        </div>
      </div>

      {/* URL Input */}
      <URLInputForm />

      {/* Recent validations */}
      {recent.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">
            Recent Validations
          </h3>
          <div className="space-y-2">
            {recent.map((v) => (
              <a
                key={v.validation_id}
                href={`/results/${v.validation_id}`}
                className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 transition-colors group"
              >
                <div className="min-w-0 flex-1 mr-4">
                  <p className="text-sm text-gray-700 truncate group-hover:text-mayo-blue">
                    {v.url}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {new Date(v.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {v.overall_score !== null && (
                    <span className="text-sm font-semibold text-gray-700">
                      {Math.round(v.overall_score * 100)}
                    </span>
                  )}
                  <span
                    className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusBadge(v.status)}`}
                  >
                    {v.status.replace("_", " ")}
                  </span>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
