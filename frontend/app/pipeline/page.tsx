import Link from "next/link";
import { PipelineDiagram } from "@/components/PipelineDiagram";

export const metadata = {
  title: "Pipeline Architecture — Mayo Clinic Content Validator",
  description:
    "Multi-agent LangGraph validation pipeline architecture: Triage, Metadata, Editorial, Compliance, Accuracy (RAG), Empty Tag Check, LLM Judge, and Human-in-the-Loop review.",
};

export default function PipelinePage() {
  return (
    <div className="space-y-6">
      {/* Breadcrumb / back link */}
      <div className="flex items-center gap-2 text-sm">
        <Link
          href="/"
          className="text-mayo-blue hover:underline flex items-center gap-1"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Dashboard
        </Link>
        <span className="text-gray-300">/</span>
        <span className="text-gray-500">Pipeline Architecture</span>
      </div>

      {/* Page content */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-base font-semibold text-gray-900">
            Pipeline Architecture
          </h2>
          <p className="text-xs text-gray-500 mt-1">
            LangGraph validation pipeline with parallel agent dispatch, LLM judge, and human-in-the-loop review
          </p>
        </div>
        <div className="p-6">
          <PipelineDiagram />
        </div>
      </div>
    </div>
  );
}
