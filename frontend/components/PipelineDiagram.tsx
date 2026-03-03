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
  cyan:    "bg-cyan-600 text-white",
  teal:    "bg-teal-600 text-white",
  rose:    "bg-rose-500 text-white",
  orange:  "bg-orange-500 text-white",
};

function Node({ label, sublabel, color, wide }: { label: string; sublabel?: string; color: string; wide?: boolean }) {
  return (
    <div className={`rounded-lg px-3 py-2 text-center ${colorMap[color]} ${wide ? "w-full max-w-xl" : "max-w-xs"}`}>
      <div className="font-semibold">{label}</div>
      {sublabel && <div className="opacity-80 mt-0.5 text-[10px] leading-tight">{sublabel}</div>}
    </div>
  );
}

function Arrow({ label }: { label?: string } = {}) {
  return (
    <div className="flex flex-col items-center">
      <svg className="w-4 h-4 text-gray-400 my-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      </svg>
      {label && <div className="text-[9px] text-gray-400 font-mono -mt-0.5">{label}</div>}
    </div>
  );
}

function RightArrow() {
  return (
    <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  );
}

function SectionTitle({ children, color = "gray" }: { children: React.ReactNode; color?: string }) {
  const colors: Record<string, string> = {
    gray: "text-gray-500 border-gray-200",
    purple: "text-purple-600 border-purple-200",
    cyan: "text-cyan-600 border-cyan-200",
    indigo: "text-indigo-600 border-indigo-200",
    amber: "text-amber-600 border-amber-200",
  };
  return (
    <div className={`text-[11px] font-bold uppercase tracking-widest ${colors[color]} border-b pb-1 mb-3`}>
      {children}
    </div>
  );
}

function AgentColumn({ label, color, rules, threshold, description }: {
  label: string; color: string; rules: { text: string; severity: string }[]; threshold: string; description: string;
}) {
  const severityColor: Record<string, string> = {
    critical: "text-red-600 bg-red-50",
    major: "text-orange-600 bg-orange-50",
    minor: "text-yellow-700 bg-yellow-50",
    info: "text-blue-600 bg-blue-50",
  };
  return (
    <div className="flex flex-col gap-1">
      <div className={`rounded-lg px-2 py-1.5 text-center font-semibold ${colorMap[color]}`}>{label}</div>
      <div className="text-[10px] text-gray-500 leading-snug px-1 mb-0.5">{description}</div>
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-2 space-y-1 flex-1">
        {rules.map((rule) => (
          <div key={rule.text} className="flex items-start gap-1">
            <span className={`text-[8px] px-1 py-px rounded font-bold uppercase shrink-0 mt-px ${severityColor[rule.severity]}`}>
              {rule.severity === "critical" ? "CRIT" : rule.severity === "major" ? "MAJ" : rule.severity === "minor" ? "MIN" : "INFO"}
            </span>
            <span className="text-gray-600 leading-tight">{rule.text}</span>
          </div>
        ))}
        <div className="text-gray-400 font-medium mt-1.5 pt-1 border-t border-gray-200">Pass threshold: {threshold}</div>
      </div>
    </div>
  );
}

function RagAgentColumn() {
  return (
    <div className="flex flex-col gap-1">
      <div className="rounded-lg px-2 py-1.5 text-center font-semibold bg-indigo-600 text-white">Accuracy Agent</div>
      <div className="text-[10px] text-gray-500 leading-snug px-1 mb-0.5">
        Fact-checks medical claims against a RAG knowledge base of verified Mayo Clinic references using vector similarity search.
      </div>
      <div className="rounded-lg border border-purple-200 bg-purple-50 p-2 space-y-1 flex-1">
        <div className="text-purple-700 font-semibold text-[10px] uppercase tracking-wide mb-1">RAG Pipeline</div>
        <div className="text-gray-600">Body text (first 1,000 chars)</div>
        <div className="text-gray-400">↓</div>
        <div className="text-gray-600">text-embedding-3-small</div>
        <div className="text-gray-400">↓</div>
        <div className="rounded bg-purple-600 text-white px-1.5 py-0.5 text-center">PGVector MMR Search</div>
        <div className="text-gray-500 text-[10px] font-mono">k=5, fetch_k=20, lambda=0.5</div>
        <div className="text-gray-400">↓</div>
        <div className="text-gray-600">5 reference chunks injected</div>
        <div className="text-gray-400">↓</div>
        <div className="text-gray-600">GPT-5.1 fact-check</div>
        <div className="text-gray-400 font-medium mt-1.5 pt-1 border-t border-gray-200">Pass threshold: &ge; 0.75</div>
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
      "The entry point of the pipeline. A Mayo Clinic URL is submitted via the frontend, then fetched server-side using httpx (an async Python HTTP client that supports HTTP/2) and parsed with BeautifulSoup4 (a Python library for extracting structured data from raw HTML/XML). The scraper extracts: page title, meta description, JSON-LD (JavaScript Object Notation for Linked Data \u2014 a structured data format embedded in <script> tags that search engines like Google use to understand page content and show rich snippets), heading hierarchy (H1 through H4), body text, Open Graph tags (og:title, og:description, og:type \u2014 metadata that controls how URLs appear when shared on social platforms like Facebook, Twitter, and Slack), canonical URL (the preferred version of a page URL to prevent duplicate content issues in search engines), internal/external links, and the raw HTML source (needed by the Empty Tag agent since HTML parsers silently fix malformed tags).",
  },
  {
    color: "bg-sky-500",
    label: "Triage / Conditional Routing",
    description:
      "A deterministic (non-AI, rule-based) routing layer that inspects the URL path to classify the content type. Pages whose URL contains '/healthy-lifestyle/' are classified as HIL (Health Information Library) content \u2014 these are wellness articles that often contain HTML formatting issues. HIL pages receive all 5 validation agents including the Empty Tag Check. Standard pages (disease/condition pages, symptom pages, etc.) receive only the 4 LLM-based agents. Because this routing is pure string matching, it adds zero latency and zero cost. The triage node also records a 'rules_version' string from the JSON rules file so that every validation result can be traced back to the exact rule set that was applied.",
  },
  {
    color: "bg-cyan-600",
    label: "Rules Engine (Neo4j + JSON)",
    description:
      "Every agent loads its validation rules dynamically at runtime instead of having them hardcoded into prompts. The primary source is Neo4j Aura (a cloud-hosted graph database) which stores rules as interconnected nodes with relationships like EVALUATED_BY, DEPENDS_ON, BELONGS_TO (category), and APPLIES_TO (content type). If Neo4j is unavailable, the system falls back to a local JSON file (validation_rules.json) containing all 34 rules. Rules include severity levels (critical, major, minor, info), categories, numeric thresholds, and dependency chains. The loader serializes the rules into a text block that is injected into each agent's system prompt, ensuring the LLM knows exactly what to check. This architecture means rules can be updated in the graph database without any code changes or redeployments.",
  },
  {
    color: "bg-indigo-600",
    label: "LLM Agents (GPT-5.1)",
    description:
      "Four specialized LLM (Large Language Model) agents powered by OpenAI\u2019s GPT-5.1 run in parallel via LangGraph\u2019s Send API (a mechanism for fanning out work to multiple graph nodes simultaneously, similar to Python\u2019s asyncio.gather but within the graph execution framework). Each agent receives the scraped content plus its dynamically-loaded rule set, evaluates the content against those rules, and returns a structured JSON finding with: a boolean pass/fail status, a 0.0\u20131.0 confidence score, a list of passed checks (rules the content satisfied), issues found (specific violations with details), and actionable recommendations. All agents use JSON mode (which constrains the model to only output syntactically valid JSON, preventing parsing errors), temperature=0 (making output fully deterministic \u2014 the same input always produces the same output), and a 120-second request timeout to prevent hanging on slow API calls.",
  },
  {
    color: "bg-purple-600",
    label: "RAG (Retrieval-Augmented Generation)",
    description:
      "RAG is a technique where an LLM is provided with relevant reference documents retrieved from a knowledge base before generating its answer, so it can ground its output in verified facts rather than relying solely on training data (which may be outdated or hallucinated). The Accuracy Agent uses RAG to fact-check medical claims: the page title and first 1,000 characters of body text are converted into a numerical vector (called an 'embedding' \u2014 a list of numbers that captures the semantic meaning of text, so similar concepts have similar numbers) using OpenAI\u2019s text-embedding-3-small model. This embedding is then compared against all stored embeddings in a PGVector database (PostgreSQL with the pgvector extension for high-performance vector similarity search) using MMR (Maximal Marginal Relevance) search \u2014 an algorithm that selects results by balancing relevance (how similar each result is to the query) with diversity (ensuring results don\u2019t all say the same thing, giving the LLM broader evidence). The top 5 reference chunks (k=5, selected from 20 candidates via fetch_k=20) are injected into the GPT-5.1 prompt as verified evidence for medical fact-checking.",
  },
  {
    color: "bg-violet-600",
    label: "Aggregation",
    description:
      "After all dispatched agents complete their work in parallel, the aggregate node collects their findings using a LangGraph reducer \u2014 a function that automatically merges results from parallel branches back into a single unified state object. The type annotation 'Annotated[List[AgentFinding], operator.add]' tells LangGraph to concatenate the findings lists from all branches. The aggregate node then computes: overall_score as the arithmetic mean of all individual agent scores (e.g., if 4 agents score 0.9, 0.8, 1.0, 0.7, the overall is 0.85), and overall_passed as the logical AND of all agent pass statuses (meaning every single agent must pass for the overall result to pass \u2014 one failure means the whole validation fails). This single summary is what the LLM Judge and human reviewer both use to make their decisions.",
  },
  {
    color: "bg-fuchsia-600",
    label: "LLM Judge (GPT-5-mini)",
    description:
      "A meta-evaluator that synthesizes all individual agent findings into a single holistic recommendation: 'approve', 'reject', or 'needs_revision'. The judge uses GPT-5-mini (a smaller, faster, and cheaper variant of GPT-5 optimized for structured evaluation tasks where reasoning complexity is lower) in JSON mode. It produces: a recommended decision, a confidence level (high, medium, or low), and a written rationale explaining its reasoning by cross-referencing findings across agents. For example, it might note that while metadata passes, the combination of compliance issues and accuracy concerns warrants rejection. This provides the human reviewer with an AI-generated second opinion that considers the full picture, reducing review time while preserving editorial oversight. The judge never makes the final decision \u2014 a human always does.",
  },
  {
    color: "bg-amber-500",
    label: "Human-in-the-Loop (HITL)",
    description:
      "HITL means a human must review and approve the AI\u2019s output before it becomes final \u2014 the system never auto-approves or auto-rejects content. The graph suspends execution using LangGraph\u2019s interrupt() primitive (a built-in mechanism that pauses a running graph mid-execution and returns control to the caller). The complete pipeline state (all agent findings, scores, the judge recommendation, scraped content, everything) is checkpointed (serialized and saved) to PostgreSQL via LangGraph\u2019s AsyncPostgresSaver, so it survives server restarts, crashes, or deployments \u2014 a reviewer can come back hours later and the state is still there. An SSE (Server-Sent Events \u2014 a one-way HTTP protocol where the server pushes real-time updates to the browser over a persistent connection, simpler than WebSockets for server-to-client streaming) event of type 'hitl' is pushed to the frontend, which renders the full review panel with all findings, scores, the judge recommendation, and approve/reject buttons. The reviewer can add written feedback before submitting their decision.",
  },
  {
    color: "bg-green-600",
    label: "Approve",
    description:
      "When the human reviewer clicks 'Approve', the frontend sends a POST request to /validate/{id}/decide with {decision: 'approve', feedback: '...'}. The backend resumes the graph from the saved checkpoint using LangGraph\u2019s Command(resume=...) mechanism. The approve node sets the validation status to 'approved', records the reviewer\u2019s feedback, persists the final state to the PostgreSQL database, and emits an SSE event of type 'done' that includes all final data. The frontend receives this event in real time via its EventSource connection and transitions to the final approved state, displaying a complete score summary across all agents with individual breakdowns, issues, and recommendations.",
  },
  {
    color: "bg-red-500",
    label: "Reject",
    description:
      "When the reviewer clicks 'Reject', the reject node sets the status to 'rejected' and records the reviewer\u2019s written feedback explaining what needs to change. The content is flagged for revision by the editorial team. Like approval, the final state is persisted to PostgreSQL and the browser receives a real-time SSE event closing the validation stream. The rejection feedback is stored alongside all agent findings so the editorial team can see both the AI analysis and the human reviewer\u2019s specific concerns when revising the content.",
  },
  {
    color: "bg-rose-500",
    label: "RAGAS (RAG Assessment)",
    description:
      "RAGAS (Retrieval-Augmented Generation Assessment) is an open-source framework that evaluates RAG pipelines using four standardized metrics: Faithfulness (are LLM claims supported by retrieved evidence?), Answer Relevancy (is the output on-topic?), Context Precision (are relevant chunks ranked higher?), and Context Recall (did retrieval find all needed references?). These metrics decompose the Accuracy Agent\u2019s single composite score into separate retrieval quality and generation quality measurements, enabling targeted improvements. For example, low Context Recall suggests the knowledge base needs more content, while low Faithfulness suggests the LLM prompt needs tighter grounding instructions. RAGAS is installed (ragas>=2.0 in requirements.txt) and the pipeline already produces the three required inputs: question, contexts, and answer.",
  },
];

function LegendItem({ color, label, description }: { color: string; label: string; description: string }) {
  return (
    <div className="group/legend relative">
      <span className="cursor-help flex items-center gap-1.5">
        <span className={`inline-block w-3 h-3 rounded ${color} flex-shrink-0`} />
        <span className="underline decoration-dotted decoration-gray-300 underline-offset-2">{label}</span>
      </span>
      <div className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-30 hidden w-96 rounded-xl border border-gray-200 bg-white p-4 shadow-lg group-hover/legend:block">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400 mb-1">{label}</p>
        <p className="text-xs leading-relaxed text-gray-700">{description}</p>
      </div>
    </div>
  );
}

/* ── Neo4j Rules Engine deep-dive section ────────────────────────────── */

function RulesEngineArchitecture() {
  return (
    <div className="border border-cyan-200 rounded-xl bg-gradient-to-b from-cyan-50/50 to-white p-5 space-y-4">
      <div className="flex items-center gap-2">
        <span className="inline-block w-3 h-3 rounded bg-cyan-600" />
        <h4 className="text-sm font-semibold text-gray-900">Rules Engine Architecture &mdash; Neo4j Graph Database + JSON Fallback</h4>
      </div>

      <div className="text-xs text-gray-600 leading-relaxed">
        Instead of hardcoding validation rules inside each agent&rsquo;s system prompt (which requires code changes and redeployment to update),
        all 34 rules across 5 agents are stored externally and loaded dynamically at runtime. The primary store is a
        <span className="font-semibold text-cyan-700"> Neo4j Aura</span> graph database (a cloud-hosted, fully-managed graph database where data is stored as nodes and relationships rather than rows and columns).
        If Neo4j is unreachable, the system automatically falls back to a local
        <span className="font-semibold text-gray-800"> validation_rules.json</span> file. This dual-source architecture ensures zero downtime &mdash; rules always load.
      </div>

      {/* Graph model — nodes */}
      <div className="rounded-lg border border-cyan-200 bg-white p-4 space-y-3">
        <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide">Neo4j Graph Model &mdash; Node Types</div>
        <div className="text-xs text-gray-500 mb-2">
          In a graph database, data is stored as <strong>nodes</strong> (entities) connected by <strong>relationships</strong> (named, directed edges).
          Unlike relational databases with rigid tables, graphs naturally model interconnected data like rules, agents, and their dependencies.
        </div>
        <div className="grid grid-cols-4 gap-3 text-xs">
          <div className="rounded-lg border-2 border-indigo-300 bg-indigo-50 p-3">
            <div className="font-bold text-indigo-700 mb-1">:Agent</div>
            <div className="text-gray-600 space-y-0.5">
              <div><span className="font-mono text-[10px] text-indigo-500">name</span> &mdash; e.g. &ldquo;compliance&rdquo;</div>
              <div><span className="font-mono text-[10px] text-indigo-500">pass_threshold</span> &mdash; e.g. 0.75</div>
            </div>
            <div className="text-[10px] text-gray-400 mt-1">5 nodes (one per agent)</div>
          </div>
          <div className="rounded-lg border-2 border-cyan-300 bg-cyan-50 p-3">
            <div className="font-bold text-cyan-700 mb-1">:Rule</div>
            <div className="text-gray-600 space-y-0.5">
              <div><span className="font-mono text-[10px] text-cyan-500">id</span> &mdash; e.g. &ldquo;no_absolute_cure_claims&rdquo;</div>
              <div><span className="font-mono text-[10px] text-cyan-500">description</span> &mdash; the check text</div>
              <div><span className="font-mono text-[10px] text-cyan-500">severity</span> &mdash; critical / major / minor / info</div>
              <div><span className="font-mono text-[10px] text-cyan-500">threshold_json</span> &mdash; numeric limits</div>
            </div>
            <div className="text-[10px] text-gray-400 mt-1">34 nodes total</div>
          </div>
          <div className="rounded-lg border-2 border-teal-300 bg-teal-50 p-3">
            <div className="font-bold text-teal-700 mb-1">:Category</div>
            <div className="text-gray-600 space-y-0.5">
              <div><span className="font-mono text-[10px] text-teal-500">name</span> &mdash; e.g. &ldquo;prohibited_language&rdquo;</div>
            </div>
            <div className="text-[10px] text-gray-400 mt-1">Groups related rules together</div>
          </div>
          <div className="rounded-lg border-2 border-sky-300 bg-sky-50 p-3">
            <div className="font-bold text-sky-700 mb-1">:ContentType</div>
            <div className="text-gray-600 space-y-0.5">
              <div><span className="font-mono text-[10px] text-sky-500">name</span> &mdash; &ldquo;standard&rdquo;, &ldquo;hil&rdquo;, or &ldquo;all&rdquo;</div>
            </div>
            <div className="text-[10px] text-gray-400 mt-1">Filters which rules apply to which pages</div>
          </div>
        </div>
      </div>

      {/* Graph model — relationships */}
      <div className="rounded-lg border border-cyan-200 bg-white p-4 space-y-3">
        <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide">Neo4j Relationships &mdash; How Nodes Connect</div>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 flex items-start gap-3">
            <div className="bg-cyan-600 text-white text-[9px] font-bold px-2 py-1 rounded whitespace-nowrap mt-0.5">EVALUATED_BY</div>
            <div>
              <div className="text-gray-700"><span className="font-mono text-cyan-600">(:Rule)</span> &rarr; <span className="font-mono text-indigo-600">(:Agent)</span></div>
              <div className="text-gray-500 mt-0.5">&ldquo;Which agent is responsible for checking this rule?&rdquo; Links each of the 34 rules to the agent that enforces it.</div>
            </div>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 flex items-start gap-3">
            <div className="bg-teal-600 text-white text-[9px] font-bold px-2 py-1 rounded whitespace-nowrap mt-0.5">BELONGS_TO</div>
            <div>
              <div className="text-gray-700"><span className="font-mono text-cyan-600">(:Rule)</span> &rarr; <span className="font-mono text-teal-600">(:Category)</span></div>
              <div className="text-gray-500 mt-0.5">&ldquo;What category does this rule fall under?&rdquo; Groups rules like &ldquo;no_absolute_cure_claims&rdquo; under &ldquo;prohibited_language&rdquo;.</div>
            </div>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 flex items-start gap-3">
            <div className="bg-sky-600 text-white text-[9px] font-bold px-2 py-1 rounded whitespace-nowrap mt-0.5">APPLIES_TO</div>
            <div>
              <div className="text-gray-700"><span className="font-mono text-cyan-600">(:Rule)</span> &rarr; <span className="font-mono text-sky-600">(:ContentType)</span></div>
              <div className="text-gray-500 mt-0.5">&ldquo;Does this rule apply to standard pages, HIL pages, or all?&rdquo; Enables content-type filtering at query time.</div>
            </div>
          </div>
          <div className="rounded-lg border border-orange-200 bg-orange-50 p-3 flex items-start gap-3">
            <div className="bg-orange-500 text-white text-[9px] font-bold px-2 py-1 rounded whitespace-nowrap mt-0.5">DEPENDS_ON</div>
            <div>
              <div className="text-gray-700"><span className="font-mono text-cyan-600">(:Rule)</span> &rarr; <span className="font-mono text-cyan-600">(:Rule)</span></div>
              <div className="text-gray-500 mt-0.5">&ldquo;Must this other rule pass first?&rdquo; E.g. &ldquo;meta_desc_length&rdquo; depends on &ldquo;meta_desc_present&rdquo; &mdash; no point checking length if the tag is missing.</div>
            </div>
          </div>
        </div>
      </div>

      {/* How rules flow into agents */}
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide mb-2">How Rules Flow Into Agent Prompts</div>
        <div className="flex items-start gap-3 text-xs">
          <div className="flex-1 rounded-lg border border-cyan-200 bg-cyan-50 p-3 space-y-1.5">
            <div className="font-semibold text-cyan-800 text-[11px] uppercase tracking-wide">1. Rule Loading</div>
            <div className="text-gray-600">
              When an agent starts, it calls <span className="font-mono text-cyan-700">get_rules_for_agent(agent_name, content_type)</span>.
              This async function first tries Neo4j via a Cypher query (Cypher is Neo4j&rsquo;s query language, similar to how SQL queries relational databases).
              If Neo4j fails (connection error, timeout, not configured), it falls back to parsing the local JSON file.
            </div>
            <div className="font-mono text-[9px] text-cyan-700 bg-cyan-100 rounded p-1.5 mt-1">
              MATCH (a:Agent {"{"} name: $agent_name {"}"})-[:EVALUATED_BY]-(r:Rule)-[:APPLIES_TO]-&gt;(ct:ContentType)
              WHERE ct.name IN [&lsquo;all&rsquo;, $content_type]
              RETURN r ORDER BY r.severity_rank DESC
            </div>
          </div>
          <RightArrow />
          <div className="flex-1 rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-1.5">
            <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide">2. Prompt Serialization</div>
            <div className="text-gray-600">
              The loaded rules are converted into a structured text block by <span className="font-mono text-gray-700">AgentRuleSet.to_prompt_block()</span>.
              This creates a human-readable format the LLM can follow, with severity tags, thresholds, and scoring criteria.
            </div>
            <div className="font-mono text-[9px] text-gray-700 bg-gray-100 rounded p-1.5 mt-1 whitespace-pre leading-relaxed">
{`VALIDATION RULES:
[CRITICAL] No absolute cure claims
[MAJOR] Required disclaimers present
[MINOR] Hedging language used
SCORING CRITERIA:
PASSES if score >= 0.75`}
            </div>
          </div>
          <RightArrow />
          <div className="flex-1 rounded-lg border border-indigo-200 bg-indigo-50 p-3 space-y-1.5">
            <div className="font-semibold text-indigo-800 text-[11px] uppercase tracking-wide">3. LLM Evaluation</div>
            <div className="text-gray-600">
              The serialized rules block is injected into the agent&rsquo;s system prompt via a <span className="font-mono text-indigo-700">{"{rules_block}"}</span> placeholder.
              GPT-5.1 reads these rules, evaluates the scraped content against each one, and returns a JSON finding with per-rule pass/fail results.
            </div>
          </div>
        </div>
      </div>

      {/* Dual-source architecture */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="rounded-lg border border-cyan-200 bg-white p-3">
          <div className="flex items-center gap-1.5 mb-1.5">
            <span className="bg-cyan-600 text-white text-[8px] font-bold px-1.5 py-0.5 rounded">PRIMARY</span>
            <span className="font-semibold text-gray-800 text-[11px]">Neo4j Aura (Graph Database)</span>
          </div>
          <div className="space-y-1 text-gray-600">
            <div>Cloud-hosted, fully managed graph database</div>
            <div>Rules stored as interconnected nodes</div>
            <div>4 relationship types model rule dependencies</div>
            <div>Rules updateable via Cypher without code changes</div>
            <div>Seeded from JSON using idempotent MERGE queries</div>
            <div className="text-[10px] text-gray-400 font-mono mt-1">driver: neo4j-python-driver (async)</div>
          </div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="flex items-center gap-1.5 mb-1.5">
            <span className="bg-gray-500 text-white text-[8px] font-bold px-1.5 py-0.5 rounded">FALLBACK</span>
            <span className="font-semibold text-gray-800 text-[11px]">validation_rules.json (Local File)</span>
          </div>
          <div className="space-y-1 text-gray-600">
            <div>34 rules across 5 agents, versioned (v1.0.0)</div>
            <div>Structured JSON with severity, category, thresholds</div>
            <div>Loaded once and cached in memory</div>
            <div>Content type filtering (standard / HIL / all)</div>
            <div>Source of truth for seeding Neo4j</div>
            <div className="text-[10px] text-gray-400 font-mono mt-1">path: backend/data/validation_rules.json</div>
          </div>
        </div>
      </div>

      {/* Rule statistics */}
      <div className="grid grid-cols-4 gap-3 text-xs">
        <div className="rounded-lg border border-gray-200 bg-white p-2.5 text-center">
          <div className="text-2xl font-bold text-cyan-600">34</div>
          <div className="text-gray-500">Total Rules</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-2.5 text-center">
          <div className="text-2xl font-bold text-cyan-600">5</div>
          <div className="text-gray-500">Agents</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-2.5 text-center">
          <div className="text-2xl font-bold text-cyan-600">4</div>
          <div className="text-gray-500">Severity Levels</div>
          <div className="text-[9px] text-gray-400">critical &middot; major &middot; minor &middot; info</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-2.5 text-center">
          <div className="text-2xl font-bold text-cyan-600">4</div>
          <div className="text-gray-500">Relationship Types</div>
          <div className="text-[9px] text-gray-400">EVALUATED_BY &middot; DEPENDS_ON &middot; BELONGS_TO &middot; APPLIES_TO</div>
        </div>
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
        <h4 className="text-sm font-semibold text-gray-900">RAG (Retrieval-Augmented Generation) Architecture &mdash; Accuracy Agent</h4>
      </div>

      <div className="text-xs text-gray-600 leading-relaxed">
        RAG is a technique that grounds LLM responses in verified evidence instead of relying on the model&rsquo;s training data alone.
        When the Accuracy Agent receives a page to validate, it first searches a knowledge base of trusted Mayo Clinic medical facts
        to find relevant references, then provides those references to GPT-5.1 alongside the page content. This way,
        the AI compares claims against <em>actual verified medical information</em> rather than &ldquo;what it thinks is true.&rdquo;
      </div>

      {/* Flow diagram */}
      <div className="flex flex-col items-center gap-1 text-xs">
        <div className="flex items-center gap-4 w-full max-w-2xl">
          {/* Left: query construction */}
          <div className="flex-1 rounded-lg border border-gray-200 bg-white p-3 space-y-1.5">
            <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide">1. Query Construction</div>
            <div className="text-gray-600">Page title + first 1,000 characters of body text are concatenated into a single query string. This captures the main topic and key claims without exceeding embedding model limits.</div>
          </div>
          <RightArrow />
          {/* Middle: embedding + retrieval */}
          <div className="flex-1 rounded-lg border border-purple-200 bg-purple-50 p-3 space-y-1.5">
            <div className="font-semibold text-purple-800 text-[11px] uppercase tracking-wide">2. Embedding &amp; Retrieval</div>
            <div className="text-gray-600">
              <span className="font-medium text-purple-700">text-embedding-3-small</span> (an OpenAI model that converts text into 1,536-dimensional numerical vectors capturing semantic meaning) creates an embedding of the query. <span className="font-medium text-purple-700">PGVector</span> then searches stored embeddings using MMR.
            </div>
            <div className="flex gap-2 mt-1 text-[10px] flex-wrap">
              <span className="bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded font-mono">k=5 (return 5 results)</span>
              <span className="bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded font-mono">fetch_k=20 (consider 20)</span>
              <span className="bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded font-mono">&lambda;=0.5 (relevance/diversity)</span>
            </div>
          </div>
          <RightArrow />
          {/* Right: LLM evaluation */}
          <div className="flex-1 rounded-lg border border-indigo-200 bg-indigo-50 p-3 space-y-1.5">
            <div className="font-semibold text-indigo-800 text-[11px] uppercase tracking-wide">3. LLM Fact-Check</div>
            <div className="text-gray-600">
              <span className="font-medium text-indigo-700">GPT-5.1</span> receives both the original page content and the 5 retrieved reference chunks. It compares every medical claim in the page against the references, flagging inaccuracies, unsupported claims, and outdated information.
            </div>
          </div>
        </div>
      </div>

      {/* How the knowledge base is seeded */}
      <div className="rounded-lg border border-gray-200 bg-white p-3 text-xs">
        <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide mb-1.5">How the Knowledge Base is Built (One-Time Seeding Process)</div>
        <p className="text-gray-600 leading-relaxed">
          Before the pipeline can fact-check anything, it needs a library of trusted medical facts to compare against.
          This library is created by a seeding script (<span className="font-mono text-gray-700">tools/seed_medical_kb.py</span>) that runs at server startup.
          It reads a curated JSON file containing 8 medical topics written by hand (verified Mayo Clinic medical information covering
          conditions like Type 1 &amp; Type 2 diabetes, hypertension, coronary artery disease, cancer screening guidelines,
          clinical depression, COVID-19, and Mayo Clinic editorial standards). Each topic is then split into small, overlapping
          text chunks using a <span className="font-medium">RecursiveCharacterTextSplitter</span> (a LangChain utility that intelligently splits text at
          sentence boundaries rather than mid-word) with chunk_size=400 characters and overlap=80 characters (so context is preserved
          across chunk boundaries and no sentence gets cut off mid-thought). Every chunk is converted into a 1,536-dimensional numerical
          embedding using OpenAI&rsquo;s text-embedding-3-small model, then stored in a PostgreSQL database with the pgvector extension.
          The seeding is idempotent &mdash; running it multiple times does not create duplicate entries.
        </p>
      </div>

      {/* Knowledge base details */}
      <div className="grid grid-cols-3 gap-3 text-xs">
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide mb-1.5">Knowledge Base Stats</div>
          <div className="space-y-1 text-gray-600">
            <div>8 curated medical topics</div>
            <div>Chunked with RecursiveCharacterTextSplitter</div>
            <div className="text-[10px] text-gray-400 font-mono">chunk_size=400 chars &middot; overlap=80 chars</div>
            <div className="text-[10px] text-gray-400 font-mono">embedding_dim=1,536</div>
          </div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide mb-1.5">Topics Covered</div>
          <div className="flex flex-wrap gap-1">
            {["Type 1 Diabetes", "Type 2 Diabetes", "Hypertension", "Coronary Artery Disease", "Cancer Screening", "Depression", "COVID-19", "Editorial Standards"].map((t) => (
              <span key={t} className="bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded text-[10px]">{t}</span>
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide mb-1.5">Vector Store</div>
          <div className="space-y-1 text-gray-600">
            <div>PostgreSQL 16 + pgvector extension</div>
            <div className="text-[10px] text-gray-400 font-mono">collection: mayo_medical_knowledge</div>
            <div className="text-[10px] text-gray-400 font-mono">driver: psycopg3 (async) &middot; JSONB metadata</div>
            <div className="text-[10px] text-gray-400 font-mono">index: ivfflat (approximate nearest neighbor)</div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── LangGraph State Management section ──────────────────────────────── */

function StateManagement() {
  return (
    <div className="border border-amber-200 rounded-xl bg-gradient-to-b from-amber-50/50 to-white p-5 space-y-4">
      <div className="flex items-center gap-2">
        <span className="inline-block w-3 h-3 rounded bg-amber-500" />
        <h4 className="text-sm font-semibold text-gray-900">LangGraph State Management &amp; Checkpointing</h4>
      </div>

      <div className="text-xs text-gray-600 leading-relaxed">
        LangGraph (an open-source framework by LangChain for building stateful, multi-step AI workflows as directed graphs)
        manages the entire validation pipeline as a <span className="font-semibold">state machine</span>. Every node in the graph reads from and writes to
        a shared <span className="font-mono text-amber-700">ValidationState</span> TypedDict (a Python dictionary with defined types for each key).
        The state is automatically checkpointed (saved) after every node completes, enabling the pipeline to pause for human review and resume later.
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs">
        {/* State shape */}
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide mb-2">ValidationState (TypedDict)</div>
          <div className="font-mono text-[9px] text-gray-700 bg-gray-50 rounded p-2 space-y-0.5">
            <div><span className="text-blue-600">url</span>: str <span className="text-gray-400"># Mayo Clinic page URL</span></div>
            <div><span className="text-blue-600">validation_id</span>: str <span className="text-gray-400"># unique ID (UUIDv4)</span></div>
            <div><span className="text-blue-600">status</span>: str <span className="text-gray-400"># running|hitl|approved|rejected|failed</span></div>
            <div><span className="text-blue-600">scraped_content</span>: dict <span className="text-gray-400"># title, body, meta, headings, HTML...</span></div>
            <div><span className="text-blue-600">routing_decision</span>: dict <span className="text-gray-400"># agents_to_run, content_type, reasoning</span></div>
            <div><span className="text-blue-600">findings</span>: Annotated[List, add] <span className="text-gray-400"># reducer: merge parallel results</span></div>
            <div><span className="text-blue-600">overall_score</span>: float <span className="text-gray-400"># mean of all agent scores</span></div>
            <div><span className="text-blue-600">overall_passed</span>: bool <span className="text-gray-400"># all agents must pass</span></div>
            <div><span className="text-blue-600">judge_recommendation</span>: dict <span className="text-gray-400"># decision, confidence, rationale</span></div>
            <div><span className="text-blue-600">human_decision</span>: str <span className="text-gray-400"># approve or reject</span></div>
            <div><span className="text-blue-600">human_feedback</span>: str <span className="text-gray-400"># reviewer&rsquo;s written notes</span></div>
            <div><span className="text-blue-600">rules_version</span>: str <span className="text-gray-400"># e.g. &ldquo;1.0.0&rdquo; for audit trail</span></div>
          </div>
        </div>

        {/* Checkpointing */}
        <div className="rounded-lg border border-gray-200 bg-white p-3 space-y-3">
          <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide">Checkpointing &amp; Persistence</div>
          <div className="text-gray-600 leading-relaxed">
            After every node executes, LangGraph serializes the entire state and saves it to PostgreSQL via
            <span className="font-mono text-amber-700"> AsyncPostgresSaver</span>. This means:
          </div>
          <div className="space-y-1.5">
            <div className="flex items-start gap-2">
              <span className="bg-green-100 text-green-700 text-[8px] font-bold px-1.5 py-0.5 rounded mt-0.5">SURVIVE</span>
              <span className="text-gray-600">Server restarts &mdash; state persists in PostgreSQL</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="bg-green-100 text-green-700 text-[8px] font-bold px-1.5 py-0.5 rounded mt-0.5">SURVIVE</span>
              <span className="text-gray-600">Deployments &mdash; pending reviews survive code updates</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="bg-green-100 text-green-700 text-[8px] font-bold px-1.5 py-0.5 rounded mt-0.5">SURVIVE</span>
              <span className="text-gray-600">Crashes &mdash; resume from last completed node</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="bg-blue-100 text-blue-700 text-[8px] font-bold px-1.5 py-0.5 rounded mt-0.5">FEATURE</span>
              <span className="text-gray-600">Time travel &mdash; replay any past state for debugging</span>
            </div>
          </div>
          <div className="text-gray-600 leading-relaxed">
            Each checkpoint is keyed by <span className="font-mono text-gray-700">thread_id</span> (the validation ID) and <span className="font-mono text-gray-700">checkpoint_ns</span> (the node name),
            creating a complete execution history.
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Technology Stack section ────────────────────────────────────────── */

function TechStack() {
  const sections = [
    {
      title: "Frontend",
      color: "bg-blue-100 border-blue-200",
      items: [
        { name: "Next.js 14", desc: "React framework with App Router for server-side rendering and API routes" },
        { name: "TypeScript", desc: "Type-safe JavaScript for catching errors at compile time" },
        { name: "Tailwind CSS", desc: "Utility-first CSS framework for rapid UI development" },
        { name: "EventSource API", desc: "Browser API for receiving Server-Sent Events (real-time updates)" },
      ],
    },
    {
      title: "Backend / Pipeline",
      color: "bg-indigo-100 border-indigo-200",
      items: [
        { name: "FastAPI", desc: "High-performance async Python web framework with auto-generated OpenAPI docs" },
        { name: "LangGraph", desc: "Framework for building stateful, multi-step AI workflows as directed graphs" },
        { name: "LangChain", desc: "Toolkit for LLM application development (prompts, chains, document loaders)" },
        { name: "SSE-Starlette", desc: "Server-Sent Events plugin for FastAPI enabling real-time streaming" },
      ],
    },
    {
      title: "AI / LLM",
      color: "bg-purple-100 border-purple-200",
      items: [
        { name: "GPT-5.1", desc: "OpenAI's flagship model used by 4 validation agents (temp=0, JSON mode)" },
        { name: "GPT-5-mini", desc: "Smaller, faster OpenAI model used by the Judge agent" },
        { name: "text-embedding-3-small", desc: "OpenAI embedding model (1,536 dims) for RAG vector search" },
      ],
    },
    {
      title: "Databases",
      color: "bg-cyan-100 border-cyan-200",
      items: [
        { name: "PostgreSQL 16", desc: "Primary relational database for validation results + vector storage" },
        { name: "pgvector", desc: "PostgreSQL extension for vector similarity search (RAG knowledge base)" },
        { name: "Neo4j Aura", desc: "Cloud graph database for validation rules (nodes + relationships)" },
      ],
    },
  ];

  return (
    <div className="border border-gray-200 rounded-xl bg-gradient-to-b from-gray-50/50 to-white p-5 space-y-3">
      <h4 className="text-sm font-semibold text-gray-900">Technology Stack</h4>
      <div className="grid grid-cols-4 gap-3 text-xs">
        {sections.map((section) => (
          <div key={section.title} className={`rounded-lg border p-3 ${section.color}`}>
            <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide mb-2">{section.title}</div>
            <div className="space-y-1.5">
              {section.items.map((item) => (
                <div key={item.name}>
                  <div className="font-medium text-gray-800">{item.name}</div>
                  <div className="text-gray-500 text-[10px] leading-snug">{item.desc}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Testing & Evals section ─────────────────────────────────────────── */

function TestingEvals() {
  return (
    <div className="border border-green-200 rounded-xl bg-gradient-to-b from-green-50/50 to-white p-5 space-y-3">
      <div className="flex items-center gap-2">
        <span className="inline-block w-3 h-3 rounded bg-green-600" />
        <h4 className="text-sm font-semibold text-gray-900">Testing &amp; Evaluation Suite (55 Tests)</h4>
      </div>

      <div className="text-xs text-gray-600 leading-relaxed">
        The rules system includes a comprehensive test suite that validates both the structural integrity of rules
        and their quality as LLM evaluation criteria. These tests run in CI/CD (Continuous Integration/Continuous Deployment)
        to catch regressions whenever rules are modified.
      </div>

      <div className="grid grid-cols-3 gap-3 text-xs">
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide mb-1.5">Unit Tests (28 tests)</div>
          <div className="space-y-1 text-gray-600">
            <div>JSON structure validation</div>
            <div>Rule schema model tests</div>
            <div>Prompt block generation</div>
            <div>Loader fallback behavior</div>
            <div>Rule coverage per agent</div>
            <div>Dependency integrity</div>
            <div>Content type filtering</div>
          </div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide mb-1.5">Eval Suite (27 tests)</div>
          <div className="space-y-1 text-gray-600">
            <div>Rule completeness (ground truth)</div>
            <div>Rule clarity (min length, no vague)</div>
            <div>Obligation language (&ge;80%)</div>
            <div>Dependency coherence (no cycles)</div>
            <div>Prompt quality (all rules present)</div>
            <div>Cross-agent consistency</div>
            <div>Severity distribution checks</div>
          </div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide mb-1.5">Eval Metrics</div>
          <div className="space-y-1.5 text-gray-600">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <span>55/55 tests passing</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <span>&ge;80% rules use obligation words</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <span>Zero circular dependencies</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <span>All prompt blocks &lt; 8,000 chars</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <span>&ge;2 severity levels per agent</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── RAGAS Evaluation Framework section ────────────────────────────── */

function RagasEvaluation() {
  return (
    <div className="border border-rose-200 rounded-xl bg-gradient-to-b from-rose-50/50 to-white p-5 space-y-4">
      <div className="flex items-center gap-2">
        <span className="inline-block w-3 h-3 rounded bg-rose-500" />
        <h4 className="text-sm font-semibold text-gray-900">RAGAS &mdash; RAG Assessment Framework for Accuracy Agent</h4>
      </div>

      <div className="text-xs text-gray-600 leading-relaxed">
        <a href="https://docs.ragas.io" target="_blank" rel="noopener noreferrer" className="font-semibold text-rose-700 hover:underline">RAGAS</a> (Retrieval-Augmented Generation Assessment) is an open-source framework
        for evaluating RAG pipelines using standardized, research-backed metrics. It measures how well the retrieval step finds relevant evidence
        and how faithfully the LLM uses that evidence &mdash; catching problems like hallucinations, incomplete retrieval, and irrelevant context
        that custom scoring alone can miss.
      </div>

      {/* How it connects to the Accuracy Agent */}
      <div className="rounded-lg border border-rose-100 bg-white p-4 space-y-3 text-xs">
        <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide">How RAGAS Evaluates the Accuracy Agent&rsquo;s RAG Pipeline</div>
        <div className="text-gray-600 leading-relaxed">
          The Accuracy Agent uses a 3-step RAG pipeline: (1) construct a query from page content, (2) retrieve 5 reference chunks via PGVector MMR search,
          (3) GPT-5.1 fact-checks claims against those references. RAGAS evaluates each of these steps independently using four core metrics,
          giving granular visibility into <em>where</em> the pipeline succeeds or fails &mdash; retrieval quality vs. generation quality.
        </div>
      </div>

      {/* Four RAGAS metrics */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="rounded-lg border border-rose-200 bg-rose-50/50 p-3 space-y-1.5">
          <div className="flex items-center gap-1.5">
            <span className="bg-rose-600 text-white text-[9px] font-bold px-1.5 py-0.5 rounded">GENERATION</span>
            <span className="font-semibold text-gray-800 text-[11px]">Faithfulness</span>
          </div>
          <div className="text-gray-600 leading-relaxed">
            Measures what fraction of the LLM&rsquo;s claims are actually supported by the retrieved references.
            A faithfulness score of 0.85 means 85% of generated statements can be traced back to a reference chunk.
            <span className="block mt-1 text-rose-600 font-medium">Catches: hallucinations, unsupported claims, fabricated statistics</span>
          </div>
          <div className="text-[10px] text-gray-400 font-mono">score: 0.0&ndash;1.0 &middot; higher = more grounded in evidence</div>
        </div>

        <div className="rounded-lg border border-rose-200 bg-rose-50/50 p-3 space-y-1.5">
          <div className="flex items-center gap-1.5">
            <span className="bg-rose-600 text-white text-[9px] font-bold px-1.5 py-0.5 rounded">GENERATION</span>
            <span className="font-semibold text-gray-800 text-[11px]">Answer Relevancy</span>
          </div>
          <div className="text-gray-600 leading-relaxed">
            Measures how relevant the LLM&rsquo;s output is to the original question/task. Generates multiple hypothetical questions
            from the answer, then computes cosine similarity between those questions and the original query.
            <span className="block mt-1 text-rose-600 font-medium">Catches: off-topic responses, tangential information, unfocused analysis</span>
          </div>
          <div className="text-[10px] text-gray-400 font-mono">score: 0.0&ndash;1.0 &middot; higher = more on-topic</div>
        </div>

        <div className="rounded-lg border border-purple-200 bg-purple-50/50 p-3 space-y-1.5">
          <div className="flex items-center gap-1.5">
            <span className="bg-purple-600 text-white text-[9px] font-bold px-1.5 py-0.5 rounded">RETRIEVAL</span>
            <span className="font-semibold text-gray-800 text-[11px]">Context Precision</span>
          </div>
          <div className="text-gray-600 leading-relaxed">
            Measures whether the relevant reference chunks are ranked higher than irrelevant ones in the retrieval results.
            High precision means PGVector&rsquo;s MMR search is putting the most useful references at the top of the k=5 results.
            <span className="block mt-1 text-purple-600 font-medium">Catches: diluted context, noisy retrieval, poor ranking</span>
          </div>
          <div className="text-[10px] text-gray-400 font-mono">score: 0.0&ndash;1.0 &middot; higher = better ranked results</div>
        </div>

        <div className="rounded-lg border border-purple-200 bg-purple-50/50 p-3 space-y-1.5">
          <div className="flex items-center gap-1.5">
            <span className="bg-purple-600 text-white text-[9px] font-bold px-1.5 py-0.5 rounded">RETRIEVAL</span>
            <span className="font-semibold text-gray-800 text-[11px]">Context Recall</span>
          </div>
          <div className="text-gray-600 leading-relaxed">
            Measures what fraction of the ground-truth answer is attributable to the retrieved context. High recall means
            the retrieval found all the reference material needed for a complete fact-check, not just some of it.
            <span className="block mt-1 text-purple-600 font-medium">Catches: missing references, incomplete knowledge base, retrieval gaps</span>
          </div>
          <div className="text-[10px] text-gray-400 font-mono">score: 0.0&ndash;1.0 &middot; higher = more complete retrieval</div>
        </div>
      </div>

      {/* Pipeline mapping */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 text-xs space-y-2">
        <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide">Mapping RAGAS Metrics to Accuracy Agent Pipeline Steps</div>
        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1.5">
            <div className="font-medium text-gray-700">Step 1: Query Construction</div>
            <div className="text-gray-500">
              <span className="font-mono text-[10px] bg-gray-100 px-1 rounded">title + body[:1000]</span>
            </div>
            <div className="text-gray-400 text-[10px]">Affects both retrieval metrics &mdash; a poor query leads to irrelevant context</div>
          </div>
          <div className="space-y-1.5">
            <div className="font-medium text-gray-700">Step 2: PGVector MMR Retrieval</div>
            <div className="text-gray-500">
              <span className="font-mono text-[10px] bg-purple-100 text-purple-700 px-1 rounded">Context Precision</span>
              {" + "}
              <span className="font-mono text-[10px] bg-purple-100 text-purple-700 px-1 rounded">Context Recall</span>
            </div>
            <div className="text-gray-400 text-[10px]">Are the right references found? Are they ranked well?</div>
          </div>
          <div className="space-y-1.5">
            <div className="font-medium text-gray-700">Step 3: GPT-5.1 Fact-Check</div>
            <div className="text-gray-500">
              <span className="font-mono text-[10px] bg-rose-100 text-rose-700 px-1 rounded">Faithfulness</span>
              {" + "}
              <span className="font-mono text-[10px] bg-rose-100 text-rose-700 px-1 rounded">Answer Relevancy</span>
            </div>
            <div className="text-gray-400 text-[10px]">Does the LLM stick to the evidence? Is the output focused?</div>
          </div>
        </div>
      </div>

      {/* Current vs RAGAS comparison */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="rounded-lg border border-gray-200 bg-white p-3 space-y-1.5">
          <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide">Current Evaluation (Custom)</div>
          <div className="space-y-1 text-gray-600">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <span>GPT-5.1 scores claims against references (0.0&ndash;1.0)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <span>Binary pass/fail per claim (passed_checks vs issues)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <span>Actionable recommendations for each issue</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-yellow-500" />
              <span>Single composite score &mdash; no retrieval vs. generation breakdown</span>
            </div>
          </div>
        </div>
        <div className="rounded-lg border border-rose-200 bg-rose-50/30 p-3 space-y-1.5">
          <div className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide">RAGAS Enhancement (Integrated)</div>
          <div className="space-y-1 text-gray-600">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-rose-500" />
              <span>4 independent metrics separate retrieval from generation quality</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-rose-500" />
              <span>Standardized benchmarks enable comparison across runs</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-rose-500" />
              <span>Catches hallucinations even when custom score is high</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-rose-500" />
              <span>Pinpoints whether to improve retrieval (k, &lambda;) or prompts</span>
            </div>
          </div>
        </div>
      </div>

      {/* Technical integration note */}
      <div className="flex gap-2 rounded-lg bg-rose-50 border border-rose-100 px-3 py-2">
        <svg className="w-3.5 h-3.5 text-rose-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20A10 10 0 0012 2z" />
        </svg>
        <p className="text-xs text-rose-700">
          <strong>Status: Integrated.</strong> RAGAS runs as a post-processing step after each Accuracy Agent evaluation.
          The agent captures its three pipeline outputs &mdash; the question (constructed query), the contexts (5 retrieved PGVector chunks),
          and the answer (GPT-5.1 fact-check JSON) &mdash; and feeds them into RAGAS&rsquo;s <span className="font-mono">evaluate()</span> function.
          Scores are stored in the <span className="font-mono">ragas_scores</span> field of AgentFinding and displayed on the Accuracy Agent&rsquo;s result card.
        </p>
      </div>
    </div>
  );
}

/* ── Main export ─────────────────────────────────────────────────────── */

export function PipelineDiagram() {
  return (
    <div className="space-y-6 text-xs">
      {/* Section: Pipeline Flow */}
      <SectionTitle>Pipeline Flow &mdash; From URL Input to Human Decision</SectionTitle>

      {/* Row 1 — input + triage */}
      <div className="flex flex-col items-center gap-1">
        <Node label="URL Input" sublabel="User submits a Mayo Clinic page URL via the frontend form" color="blue" />
        <Arrow label="httpx.AsyncClient.get(url)" />
        <Node
          label="Scrape Content"
          sublabel="httpx (async HTTP/2 client) fetches the page · BeautifulSoup4 (HTML parser) extracts: title, meta description, JSON-LD structured data, heading hierarchy (H1-H4), body text, Open Graph tags (og:title, og:description, og:type), canonical URL, internal/external links, and raw HTML source"
          color="blue"
          wide
        />
        <Arrow label="scraped_content → state" />
        <Node
          label="Content Triage (Deterministic Router)"
          sublabel="Inspects URL path · '/healthy-lifestyle/' → HIL content (5 agents) · all other URLs → standard content (4 agents) · No LLM call — pure string matching, zero cost · Records rules_version for audit trail"
          color="sky"
          wide
        />
        <Arrow />
        <div className="text-gray-400 font-medium text-[11px] text-center max-w-xl leading-relaxed">
          <span className="font-mono text-sky-600">dispatch_agents()</span> &mdash; LangGraph Send API (parallel fan-out: sends scraped content to all selected agents simultaneously)<br />
          <span className="text-sky-500">Standard pages &rarr; 4 LLM agents</span> &middot; <span className="text-sky-500">HIL pages (healthy-lifestyle) &rarr; 5 agents (+ Empty Tag Check)</span>
        </div>
      </div>

      {/* Row 2 — 5 agents (4 standard + conditional empty tag) */}
      <div className="grid grid-cols-5 gap-3">
        <AgentColumn
          label="Metadata Agent"
          color="indigo"
          description="Validates SEO (Search Engine Optimization) and structured data completeness. Ensures search engines and social platforms can properly index and display the page."
          rules={[
            { text: "Meta description present (150-160 chars)", severity: "critical" },
            { text: "Canonical URL present and matching", severity: "critical" },
            { text: "JSON-LD structured data with schema type", severity: "major" },
            { text: "Open Graph tags (og:title, og:description)", severity: "major" },
            { text: "og:type set to website or article", severity: "minor" },
          ]}
          threshold="≥ 0.7 (70%)"
        />
        <AgentColumn
          label="Editorial Agent"
          color="indigo"
          description="Checks content structure, recency, and attribution standards. Ensures the page follows Mayo Clinic's editorial guidelines for health content."
          rules={[
            { text: "H1 heading present and descriptive", severity: "critical" },
            { text: "No heading level skips (H2→H4 invalid)", severity: "major" },
            { text: "Last reviewed date within 2 years", severity: "critical" },
            { text: "Author attribution present", severity: "major" },
            { text: "≥3 required sections (Overview, Symptoms...)", severity: "major" },
            { text: "≥500 words for adequate depth", severity: "minor" },
          ]}
          threshold="≥ 0.7 (70%)"
        />
        <AgentColumn
          label="Compliance Agent"
          color="indigo"
          description="Scans for regulatory violations and dangerous medical claims. Catches language that could mislead patients or violate FDA/HIPAA guidelines."
          rules={[
            { text: "No absolute cure claims ('cures', 'eliminates')", severity: "critical" },
            { text: "No unsubstantiated superlatives", severity: "critical" },
            { text: "No off-label drug promotion without FDA caveats", severity: "critical" },
            { text: "No patient-identifiable data (HIPAA)", severity: "critical" },
            { text: "Required medical disclaimers present", severity: "major" },
            { text: "Appropriate hedging language ('may help')", severity: "minor" },
            { text: "FDA language compliance", severity: "major" },
          ]}
          threshold="≥ 0.75 (75%)"
        />
        <RagAgentColumn />
        <AgentColumn
          label="Empty Tag Check"
          color="sky"
          description="Deterministic (no LLM) scanner for malformed HTML. Runs ONLY on HIL content. Checks raw HTML before parser cleanup."
          rules={[
            { text: "No self-closing content tags (<title/>)", severity: "major" },
            { text: "No empty/whitespace-only tags", severity: "major" },
            { text: "Checks: title, h1-h4, p, a, li, td, th, label, button", severity: "info" },
          ]}
          threshold="≥ 0.8 (80%)"
        />
      </div>

      {/* Section: Rules Engine */}
      <SectionTitle color="cyan">Rules Engine &mdash; Dynamic Rule Loading from Neo4j Graph Database</SectionTitle>
      <RulesEngineArchitecture />

      {/* Section: RAG */}
      <SectionTitle color="purple">RAG Architecture &mdash; Evidence-Based Medical Fact-Checking</SectionTitle>
      <RagArchitecture />

      {/* Reducer note */}
      <div className="flex flex-col items-center gap-1">
        <div className="text-gray-400 font-mono text-[10px] text-center leading-relaxed">
          findings: Annotated[List[AgentFinding], operator.add]<br />
          <span className="text-gray-500">LangGraph reducer automatically merges findings from all parallel agent branches into a single list</span>
        </div>
        <Arrow />

        {/* Row 3 — aggregate */}
        <Node
          label="Aggregate Node"
          sublabel="overall_score = arithmetic mean of all agent scores · overall_passed = logical AND of all pass statuses (every agent must pass) · Collects per-agent breakdowns for review panel"
          color="violet"
          wide
        />
        <Arrow label="findings + overall_score → judge" />

        {/* Row 3.5 — LLM Judge */}
        <Node
          label="LLM Judge (Meta-Evaluator)"
          sublabel="GPT-5-mini (smaller, faster model) · JSON mode · Reads ALL agent findings and cross-references them · Produces: decision (approve/reject/needs_revision), confidence (high/medium/low), written rationale · Provides AI second opinion — never makes the final call"
          color="fuchsia"
          wide
        />
        <Arrow label="judge_recommendation → human gate" />

        {/* Row 4 — human gate */}
        <Node
          label="Human Review Gate (HITL — Human-in-the-Loop)"
          sublabel="LangGraph interrupt() pauses the graph · Full state checkpointed to PostgreSQL via AsyncPostgresSaver (survives restarts) · SSE event {type:'hitl'} pushed to browser · Frontend renders review panel with all findings, scores, judge recommendation, and approve/reject buttons"
          color="amber"
          wide
        />
      </div>

      {/* Row 5 — approve / reject */}
      <div className="flex items-start justify-center gap-12">
        <div className="flex flex-col items-center gap-1">
          <div className="text-gray-400 text-[11px] font-mono">POST /validate/{"{id}"}/decide</div>
          <div className="text-gray-400 text-[10px]">{"{decision: 'approve', feedback: '...'}"}</div>
          <Arrow />
          <Node label="Approve Node" sublabel="status = 'approved' · feedback recorded · persisted to PostgreSQL · SSE {type:'done'} sent" color="green" />
        </div>
        <div className="flex flex-col items-center gap-1">
          <div className="text-gray-400 text-[11px] font-mono">POST /validate/{"{id}"}/decide</div>
          <div className="text-gray-400 text-[10px]">{"{decision: 'reject', feedback: '...'}"}</div>
          <Arrow />
          <Node label="Reject Node" sublabel="status = 'rejected' · feedback recorded · flagged for editorial revision · SSE {type:'done'} sent" color="red" />
        </div>
      </div>

      {/* Section: State Management */}
      <SectionTitle color="amber">State Management &amp; Checkpointing</SectionTitle>
      <StateManagement />

      {/* Section: RAGAS Evaluation */}
      <SectionTitle color="rose">RAGAS &mdash; RAG Quality Evaluation Framework</SectionTitle>
      <RagasEvaluation />

      {/* Section: Testing */}
      <SectionTitle color="cyan">Testing &amp; Evaluation Suite</SectionTitle>
      <TestingEvals />

      {/* Section: Tech Stack */}
      <TechStack />

      {/* Legend with hover descriptions */}
      <div className="border-t border-gray-100 pt-5">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 text-center mb-3">
          Legend &mdash; hover over any item for a detailed explanation of what it is and how it works
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
