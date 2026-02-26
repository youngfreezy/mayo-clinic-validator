const colorMap: Record<string, string> = {
  blue:    "bg-blue-600 text-white",
  sky:     "bg-sky-500 text-white",
  indigo:  "bg-indigo-600 text-white",
  violet:  "bg-violet-600 text-white",
  fuchsia: "bg-fuchsia-600 text-white",
  amber:   "bg-amber-500 text-white",
  green:   "bg-green-600 text-white",
  red:     "bg-red-500 text-white",
  purple:  "bg-purple-600 text-white",
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

/* ── Legend items with hover descriptions ─────────────────────────────── */

const LEGEND_ITEMS: { color: string; label: string; description: string }[] = [
  {
    color: "bg-blue-600",
    label: "Input / Scraping",
    description:
      "The entry point of the pipeline. A Mayo Clinic URL is submitted, then fetched using httpx and parsed with BeautifulSoup4. The scraper extracts structured data including the page title, meta description, JSON-LD schema markup, heading hierarchy, body text, Open Graph tags, canonical URL, internal/external links, and raw HTML. This structured content object is passed downstream to all validation agents.",
  },
  {
    color: "bg-sky-500",
    label: "Triage / Conditional",
    description:
      "A deterministic routing layer that inspects the URL path to classify the content type. Pages under /healthy-lifestyle/ are classified as HIL (Health Information Library) content and receive all five validation agents including the Empty Tag Check. Standard pages receive four agents. This avoids running unnecessary checks and keeps pipeline execution efficient.",
  },
  {
    color: "bg-indigo-600",
    label: "LLM Agents (GPT-4o)",
    description:
      "Four specialized GPT-4o agents run in parallel via LangGraph's Send API. Each agent receives the scraped content, evaluates it against domain-specific criteria, and returns a structured JSON finding with a pass/fail status, a 0\u20131 score, a list of passed checks, issues found, and recommendations. All agents use JSON mode with temperature 0 for deterministic output and a 120-second request timeout.",
  },
  {
    color: "bg-purple-600",
    label: "RAG (PGVector)",
    description:
      "The Accuracy Agent uses Retrieval-Augmented Generation to fact-check page content against a curated medical knowledge base. The page title and first 1,000 characters of body text are embedded using OpenAI\u2019s text-embedding-3-small model, then matched against PGVector using MMR (Maximal Marginal Relevance) search with k=5 results from 20 candidates and a lambda of 0.5 balancing relevance and diversity. The retrieved reference chunks are injected into the GPT-4o prompt for evidence-based fact-checking.",
  },
  {
    color: "bg-violet-600",
    label: "Aggregation",
    description:
      "After all dispatched agents complete, the aggregate node collects their findings via a LangGraph reducer (Annotated[List, operator.add]). It computes an overall_score as the mean of all agent scores and overall_passed as the logical AND of all agent pass statuses. This single summary is what the LLM Judge and human reviewer use to make their decision.",
  },
  {
    color: "bg-fuchsia-600",
    label: "LLM Judge (GPT-4o-mini)",
    description:
      "A meta-evaluator that synthesizes all agent findings into a single recommendation: approve, reject, or needs_revision. The judge uses GPT-4o-mini in JSON mode to produce a confidence level (high, medium, low) and a written rationale. This provides the human reviewer with an AI-generated second opinion before they make the final call, reducing review time while preserving editorial oversight.",
  },
  {
    color: "bg-amber-500",
    label: "Human-in-the-Loop",
    description:
      "The graph suspends execution using LangGraph\u2019s interrupt() primitive, and state is checkpointed to PostgreSQL via AsyncPostgresSaver so it survives server restarts. An SSE event of type \u2018hitl\u2019 is pushed to the frontend, which renders the HITL review panel with all findings, the judge recommendation, and approve/reject buttons. The reviewer can add written feedback before submitting their decision.",
  },
  {
    color: "bg-green-600",
    label: "Approve",
    description:
      "When the human reviewer approves the content, the graph resumes from the checkpoint. The approve node sets the validation status to \u2018approved\u2019, persists the final state to the database, and emits an SSE event of type \u2018done\u2019 with the reviewer\u2019s feedback. The frontend transitions to the final approved state with a full score summary.",
  },
  {
    color: "bg-red-500",
    label: "Reject",
    description:
      "When the reviewer rejects the content, the reject node sets status to \u2018rejected\u2019 and includes the reviewer\u2019s feedback explaining what needs to change. The content is flagged for revision by the editorial team. Like approval, this persists to the database and closes the SSE stream with a \u2018done\u2019 event.",
  },
];

function LegendItem({ color, label, description }: { color: string; label: string; description: string }) {
  return (
    <div className="group/legend relative">
      <span className="cursor-help flex items-center gap-1.5">
        <span className={`inline-block w-3 h-3 rounded ${color} flex-shrink-0`} />
        <span className="underline decoration-dotted decoration-gray-300 underline-offset-2">{label}</span>
      </span>
      <div className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-30 hidden w-80 rounded-xl border border-gray-200 bg-white p-4 shadow-lg group-hover/legend:block">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400 mb-1">{label}</p>
        <p className="text-xs leading-relaxed text-gray-700">{description}</p>
      </div>
    </div>
  );
}

/* ── RAG deep-dive section ───────────────────────────────────────────── */

function RagArchitecture() {
  return (
    <div className="border border-purple-200 rounded-xl bg-gradient-to-b from-purple-50/50 to-white p-5 space-y-4">
      <div className="flex items-center gap-2">
        <span className="inline-block w-3 h-3 rounded bg-purple-600" />
        <h4 className="text-sm font-semibold text-gray-900">RAG Architecture — Accuracy Agent</h4>
      </div>

      {/* Flow diagram */}
      <div className="flex flex-col items-center gap-1 text-xs">
        <div className="flex items-center gap-4 w-full max-w-2xl">
          {/* Left: query construction */}
          <div className="flex-1 rounded-lg border border-gray-200 bg-white p-3 space-y-1.5">
            <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide">1. Query Construction</div>
            <div className="text-gray-600">Page title + first 1,000 chars of body text are concatenated into a query string for retrieval.</div>
          </div>
          <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          {/* Middle: embedding + retrieval */}
          <div className="flex-1 rounded-lg border border-purple-200 bg-purple-50 p-3 space-y-1.5">
            <div className="font-semibold text-purple-800 text-[11px] uppercase tracking-wide">2. Embedding &amp; Retrieval</div>
            <div className="text-gray-600">
              <span className="font-medium text-purple-700">text-embedding-3-small</span> embeds the query, then <span className="font-medium text-purple-700">PGVector</span> performs MMR search.
            </div>
            <div className="flex gap-2 mt-1 text-[10px]">
              <span className="bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded font-mono">k=5</span>
              <span className="bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded font-mono">fetch_k=20</span>
              <span className="bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded font-mono">&lambda;=0.5</span>
            </div>
          </div>
          <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          {/* Right: LLM evaluation */}
          <div className="flex-1 rounded-lg border border-indigo-200 bg-indigo-50 p-3 space-y-1.5">
            <div className="font-semibold text-indigo-800 text-[11px] uppercase tracking-wide">3. LLM Fact-Check</div>
            <div className="text-gray-600">
              <span className="font-medium text-indigo-700">GPT-4o</span> receives the retrieved reference chunks alongside the scraped content and evaluates medical accuracy.
            </div>
          </div>
        </div>
      </div>

      {/* Knowledge base details */}
      <div className="grid grid-cols-3 gap-3 text-xs">
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide mb-1.5">Knowledge Base</div>
          <div className="space-y-1 text-gray-600">
            <div>8 curated medical topics</div>
            <div>Chunked with RecursiveCharacterTextSplitter</div>
            <div className="text-[10px] text-gray-400 font-mono">chunk_size=400 · overlap=80</div>
          </div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide mb-1.5">Topics Covered</div>
          <div className="flex flex-wrap gap-1">
            {["Diabetes", "Hypertension", "CAD", "Cancer Screening", "Depression", "COVID-19", "Editorial Standards"].map((t) => (
              <span key={t} className="bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded text-[10px]">{t}</span>
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide mb-1.5">Vector Store</div>
          <div className="space-y-1 text-gray-600">
            <div>PostgreSQL 16 + pgvector</div>
            <div className="text-[10px] text-gray-400 font-mono">collection: mayo_medical_knowledge</div>
            <div className="text-[10px] text-gray-400 font-mono">driver: psycopg3 · JSONB metadata</div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Main export ─────────────────────────────────────────────────────── */

export function PipelineDiagram() {
  return (
    <div className="space-y-6 text-xs">
      {/* Row 1 — input + triage */}
      <div className="flex flex-col items-center gap-1">
        <Node label="URL Input" color="blue" />
        <Arrow />
        <Node label="Scrape Content" sublabel="httpx + BeautifulSoup4 · title, meta, JSON-LD, headings, body text, OG tags, raw HTML" color="blue" wide />
        <Arrow />
        <Node label="Content Triage" sublabel="Deterministic URL-based routing · classifies HIL vs standard · selects agent set" color="sky" wide />
        <Arrow />
        <div className="text-gray-400 font-medium text-[11px] text-center max-w-xl">
          dispatch_agents() — Send API (parallel fan-out)<br />
          <span className="text-sky-500">Standard pages → 4 agents</span> · <span className="text-sky-500">HIL pages (healthy-lifestyle) → 5 agents (+ Empty Tag Check)</span>
        </div>
      </div>

      {/* Row 2 — 5 agents (4 standard + conditional empty tag) */}
      <div className="grid grid-cols-5 gap-3">
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
        <AgentColumn
          label="Empty Tag Check"
          color="sky"
          items={["Self-closing tags (<title/>)", "Empty content tags", "HIL content only", "Line-number reporting"]}
          threshold="≥ 0.8"
        />
      </div>

      {/* RAG deep-dive */}
      <RagArchitecture />

      {/* Reducer note */}
      <div className="flex flex-col items-center gap-1">
        <div className="text-gray-400 font-mono text-[10px] text-center">
          findings: Annotated[List, operator.add] — dispatched agents merge via reducer
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

        {/* Row 3.5 — LLM Judge */}
        <Node
          label="LLM Judge"
          sublabel="GPT-4o-mini (JSON mode) · synthesizes all findings → approve / reject / needs_revision · confidence + rationale"
          color="fuchsia"
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

      {/* Legend with hover descriptions */}
      <div className="border-t border-gray-100 pt-5">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 text-center mb-3">
          Legend — hover for details
        </p>
        <div className="flex flex-wrap gap-x-5 gap-y-3 justify-center text-[11px] text-gray-500">
          {LEGEND_ITEMS.map((item) => (
            <LegendItem key={item.label} {...item} />
          ))}
        </div>
      </div>
    </div>
  );
}
