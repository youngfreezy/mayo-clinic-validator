"use client";

import { useState } from "react";

export function PipelineArchitectureModal() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="ml-2 text-gray-400 hover:text-mayo-blue transition-colors"
        title="View architecture diagram"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <circle cx="12" cy="12" r="10" strokeWidth={2} />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8h.01M11 12h1v4h1" />
        </svg>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          onClick={() => setOpen(false)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <h2 className="text-base font-semibold text-gray-900">Pipeline Architecture</h2>
              <button
                onClick={() => setOpen(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Diagram */}
            <div className="p-6 space-y-6 text-xs">

              {/* Row 1 — input */}
              <div className="flex flex-col items-center gap-1">
                <Node label="URL Input" color="blue" />
                <Arrow />
                <Node label="Scrape Content" sublabel="httpx + BeautifulSoup4 · title, meta, JSON-LD, headings, body text, OG tags" color="blue" wide />
                <Arrow />
                <div className="text-gray-400 font-medium text-[11px]">dispatch_agents() — Send API (parallel fan-out)</div>
              </div>

              {/* Row 2 — 4 agents */}
              <div className="grid grid-cols-4 gap-3">
                <AgentColumn
                  label="Metadata Agent"
                  color="indigo"
                  items={["Meta description length (150-160 chars)", "Canonical URL present", "JSON-LD schema type", "Open Graph tags"]}
                  threshold="≥ 0.7"
                />
                <AgentColumn
                  label="Editorial Agent"
                  color="indigo"
                  items={["H1-H4 hierarchy", "Last reviewed ≤ 2 years", "Mayo attribution", "Required sections", "Taxonomy"]}
                  threshold="≥ 0.7"
                />
                <AgentColumn
                  label="Compliance Agent"
                  color="indigo"
                  items={['No absolute claims ("cures")', "Required disclaimers", "FDA language", "HIPAA concerns", "Hedging language"]}
                  threshold="≥ 0.75"
                />
                <RagAgentColumn />
              </div>

              {/* Reducer note */}
              <div className="flex flex-col items-center gap-1">
                <div className="text-gray-400 font-mono text-[10px] text-center">
                  findings: Annotated[List, operator.add] — all 4 agents merge via reducer
                </div>
                <Arrow />

                {/* Row 3 — aggregate */}
                <Node
                  label="Aggregate Node"
                  sublabel="overall_score = mean(scores) · overall_passed = all(passed)"
                  color="violet"
                  wide
                />
                <Arrow />

                {/* Row 4 — human gate */}
                <Node
                  label="Human Gate (HITL)"
                  sublabel="interrupt() · graph suspends · MemorySaver checkpoints state · SSE {type:'hitl'} sent"
                  color="amber"
                  wide
                />
              </div>

              {/* Row 5 — approve / reject */}
              <div className="flex items-start justify-center gap-12">
                <div className="flex flex-col items-center gap-1">
                  <div className="text-gray-400 text-[11px]">POST /decide {"{decision:'approve'}"}</div>
                  <Arrow />
                  <Node label="Approve Node" sublabel="status = approved · SSE {type:'done'}" color="green" />
                </div>
                <div className="flex flex-col items-center gap-1">
                  <div className="text-gray-400 text-[11px]">POST /decide {"{decision:'reject'}"}</div>
                  <Arrow />
                  <Node label="Reject Node" sublabel="status = rejected · SSE {type:'done'}" color="red" />
                </div>
              </div>

              {/* Legend */}
              <div className="border-t border-gray-100 pt-4 flex flex-wrap gap-4 justify-center text-[11px] text-gray-500">
                <span><span className="inline-block w-3 h-3 rounded bg-blue-600 mr-1 align-middle" />Input / Scraping</span>
                <span><span className="inline-block w-3 h-3 rounded bg-indigo-600 mr-1 align-middle" />LLM Agents (GPT-4o)</span>
                <span><span className="inline-block w-3 h-3 rounded bg-purple-600 mr-1 align-middle" />RAG (PGVector)</span>
                <span><span className="inline-block w-3 h-3 rounded bg-violet-600 mr-1 align-middle" />Aggregation</span>
                <span><span className="inline-block w-3 h-3 rounded bg-amber-500 mr-1 align-middle" />Human-in-the-Loop</span>
                <span><span className="inline-block w-3 h-3 rounded bg-green-600 mr-1 align-middle" />Approve</span>
                <span><span className="inline-block w-3 h-3 rounded bg-red-500 mr-1 align-middle" />Reject</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

/* ── Helpers ─────────────────────────────────────────────────────────────── */

const colorMap: Record<string, string> = {
  blue:   "bg-blue-600 text-white",
  indigo: "bg-indigo-600 text-white",
  violet: "bg-violet-600 text-white",
  amber:  "bg-amber-500 text-white",
  green:  "bg-green-600 text-white",
  red:    "bg-red-500 text-white",
  purple: "bg-purple-600 text-white",
};

function Node({ label, sublabel, color, wide }: { label: string; sublabel?: string; color: string; wide?: boolean }) {
  return (
    <div className={`rounded-lg px-3 py-2 text-center ${colorMap[color]} ${wide ? "w-full max-w-xl" : "max-w-xs"}`}>
      <div className="font-semibold">{label}</div>
      {sublabel && <div className="opacity-80 mt-0.5 text-[10px] leading-tight">{sublabel}</div>}
    </div>
  );
}

function Arrow() {
  return (
    <svg className="w-4 h-4 text-gray-400 my-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  );
}

function AgentColumn({ label, color, items, threshold }: { label: string; color: string; items: string[]; threshold: string }) {
  return (
    <div className="flex flex-col gap-1">
      <div className={`rounded-lg px-2 py-1.5 text-center font-semibold ${colorMap[color]}`}>{label}</div>
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-2 space-y-1 flex-1">
        {items.map((item) => (
          <div key={item} className="text-gray-600 leading-tight">{item}</div>
        ))}
        <div className="text-gray-400 font-medium mt-1">Pass: {threshold}</div>
      </div>
    </div>
  );
}

function RagAgentColumn() {
  return (
    <div className="flex flex-col gap-1">
      <div className="rounded-lg px-2 py-1.5 text-center font-semibold bg-indigo-600 text-white">Accuracy Agent</div>
      <div className="rounded-lg border border-purple-200 bg-purple-50 p-2 space-y-1 flex-1">
        <div className="text-purple-700 font-semibold text-[10px] uppercase tracking-wide mb-1">RAG Pipeline</div>
        <div className="text-gray-600">Body text</div>
        <div className="text-gray-400">↓</div>
        <div className="text-gray-600">text-embedding-3-small</div>
        <div className="text-gray-400">↓</div>
        <div className="rounded bg-purple-600 text-white px-1.5 py-0.5 text-center">PGVector MMR Search</div>
        <div className="text-gray-500 text-[10px]">k=5, fetch_k=20</div>
        <div className="text-gray-400">↓</div>
        <div className="text-gray-600">Medical reference chunks</div>
        <div className="text-gray-400">↓</div>
        <div className="text-gray-600">GPT-4o fact-check</div>
        <div className="text-gray-400 font-medium mt-1">Pass: ≥ 0.75</div>
      </div>
    </div>
  );
}
