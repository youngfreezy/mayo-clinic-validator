import Link from "next/link";
import { PipelineDiagram } from "@/components/PipelineDiagram";
import { CopyLinkButton } from "@/components/CopyLinkButton";

export const metadata = {
  title: "Pipeline Architecture — Mayo Clinic Content Validator",
  description:
    "MCP + Claude orchestrator agent pipeline: dynamic tool selection, parallel validation via 8 MCP tools, RAG fact-checking, and human-in-the-loop review.",
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
        <div className="px-6 py-4 border-b border-gray-200 flex items-start justify-between">
          <div>
            <h2 className="text-base font-semibold text-gray-900">
              Pipeline Architecture
            </h2>
            <p className="text-xs text-gray-500 mt-1">
              MCP + Claude orchestrator agent with dynamic tool selection, parallel validation, and human-in-the-loop review
            </p>
          </div>
          <CopyLinkButton />
        </div>
        <div className="p-6">
          <PipelineDiagram />
        </div>
      </div>
    </div>
  );
}
