# Mayo Clinic Content Validator — Architecture

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                        MAYO CLINIC CONTENT VALIDATOR                           ║
║                   Multi-Agent LangGraph + HITL Platform                        ║
╚══════════════════════════════════════════════════════════════════════════════════╝

  Browser (Next.js 14 · TypeScript · Tailwind CSS)
  ┌─────────────────────────────────────────────────────────┐
  │  Home Page                       Results Page            │
  │  ┌──────────────────┐            ┌───────────────────┐  │
  │  │ URL Input Form   │  POST      │ Pipeline Progress  │  │
  │  │ mayoclinic.org   │──────────► │ SSE live updates  │  │
  │  └──────────────────┘ /validate  │                   │  │
  │  ┌──────────────────┐            │ Agent Result Cards │  │
  │  │ Pipeline diagram │            │ ┌───┐┌───┐┌───┐   │  │
  │  │ ? → modal        │            │ │ M ││ E ││ C │   │  │
  │  └──────────────────┘            │ └───┘└───┘└───┘   │  │
  │  ┌──────────────────┐            │ ┌───────────────┐  │  │
  │  │ Validation       │            │ │  Accuracy(RAG)│  │  │
  │  │ History Table    │            │ └───────────────┘  │  │
  │  └──────────────────┘            │                   │  │
  │  (auto-refresh 10s)              │ HITL Review Panel  │  │
  │                                  │ Approve · Reject   │  │
  └─────────────────────────────────────────────────────────┘
          │ fetch("/api/*")                   │ EventSource
          │ (relative URL)                    │ /api/validate/{id}/stream
          ▼                                   ▼
  ┌─────────────────────────────────────────────────────────┐
  │                  nginx  (port 7860 in prod)              │
  │  /api/validate/*/stream → uvicorn :8000  [SSE no-buf]   │
  │  /api/*                → uvicorn :8000                  │
  │  /*                    → Next.js :3000                  │
  └────────────────────────┬────────────────────────────────┘
                           │
  ┌────────────────────────▼────────────────────────────────┐
  │               FastAPI + uvicorn  (port 8000)             │
  │                                                          │
  │   POST /api/validate          → start pipeline           │
  │   GET  /api/validate/{id}/stream → SSE stream            │
  │   GET  /api/validate/{id}     → polling fallback         │
  │   POST /api/validate/{id}/decide → HITL resume           │
  │   GET  /api/validations       → history list             │
  │   GET  /api/health            → health check             │
  │                                                          │
  │   asyncio.Queue per validation                           │
  │   _run_pipeline() → background task → pushes to queue   │
  │   SSE generator   → consumes queue  → streams to client  │
  └────────────────────────┬────────────────────────────────┘
                           │  astream()  /  Command(resume)
                           ▼
╔══════════════════════════════════════════════════════════════╗
║              LANGGRAPH STATE MACHINE                        ║
║         (MemorySaver checkpointer — HITL safe)              ║
╚══════════════════════════════════════════════════════════════╝

         ┌──────────────────────────────────┐
         │        fetch_content_node         │
         │   httpx + BeautifulSoup4          │
         │   Extracts from Mayo HTML:        │
         │   • Title / H1–H4 headings        │
         │   • Meta description / canonical  │
         │   • JSON-LD structured data       │
         │   • Open Graph tags               │
         │   • Body text (#main-content)     │
         │   • Last-reviewed date            │
         │   • Internal / external links     │
         │   • Raw HTML (for empty tag scan) │
         └───────────────┬──────────────────┘
                         │
         ┌───────────────▼──────────────────┐
         │           triage_node             │
         │  Deterministic URL-based router   │
         │  • "healthy-lifestyle" → HIL      │
         │    (5 agents: + empty_tag)        │
         │  • All other URLs → Standard      │
         │    (4 agents)                     │
         │  SSE: {type:"routing"}            │
         └───────────────┬──────────────────┘
                         │
              dispatch_agents() — Send API
              (reads routing_decision from state)
          ┌──────────┬───┼──────────┬──────────────┐
          │          │   │          │              │
  ┌───────▼─────┐ ┌─▼───▼───┐ ┌───▼──────┐ ┌────▼──────────────┐ ┌────────────┐
  │  metadata   │ │editorial│ │compliance│ │     accuracy      │ │ empty_tag  │
  │    node     │ │  node   │ │   node   │ │      node         │ │   node     │
  │             │ │         │ │          │ │                   │ │ (HIL only) │
  │  GPT-4o     │ │ GPT-4o  │ │  GPT-4o  │ │ ┌──────────────┐ │ │            │
  │             │ │         │ │          │ │ │ RAG Pipeline │ │ │ Regex scan │
  │  Checks:    │ │ Checks: │ │ Checks:  │ │ │              │ │ │ raw HTML   │
  │  • Meta desc│ │ • H1-H4 │ │ • No     │ │ │ body text    │ │ │            │
  │    150-160  │ │  hier.  │ │  "cures" │ │ │     ↓        │ │ │ Checks:    │
  │  • Canonical│ │ • Review│ │ • Discl- │ │ │ embed-3-small│ │ │ • <title/> │
  │  • JSON-LD  │ │  ≤2 yrs │ │  aimers  │ │ │     ↓        │ │ │ • <h1/>    │
  │  • OG tags  │ │ • Mayo  │ │ • FDA    │ │ │ PGVector MMR │ │ │ • <p/>     │
  │             │ │  attrib.│ │  language│ │ │ k=5, f=20    │ │ │ • <a/>     │
  │  Pass ≥0.7  │ │ • Sect. │ │ • HIPAA  │ │ │     ↓        │ │ │ etc.       │
  │             │ │ • Taxon.│ │ • Hedging│ │ │ GPT-4o fact  │ │ │            │
  │             │ │         │ │          │ │ │ check vs ref │ │ │ Pass ≥0.8  │
  │             │ │Pass≥0.7 │ │Pass≥0.75 │ │ └──────────────┘ │ │            │
  └──────┬──────┘ └───┬────┘ └────┬─────┘ │  Pass ≥0.75      │ └─────┬──────┘
         │            │           │        └──────┬───────────┘       │
         │            │           │               │      (conditional)│
         └────────────┴───────────┴───────────────┴───────────────────┘
                         │
              Annotated[List, operator.add] reducer
              (all dispatched findings merge correctly)
                         │
         ┌───────────────▼──────────────────┐
         │          aggregate_node           │
         │  overall_score = mean(scores)     │
         │  overall_passed = all(passed)     │
         └───────────────┬──────────────────┘
                         │
         ┌───────────────▼──────────────────┐
         │          judge_node               │
         │  LLM-as-a-Judge (GPT-4o-mini)    │
         │  Synthesizes all agent findings   │
         │  → recommendation: approve /      │
         │    reject / needs_revision        │
         │  → confidence: high/medium/low    │
         │  → key_concerns + strengths       │
         │  SSE: {type:"judge"}              │
         └───────────────┬──────────────────┘
                         │
         ┌───────────────▼──────────────────┐
         │        human_gate_node            │
         │  interrupt() ◄── graph suspends   │
         │  MemorySaver checkpoints state    │
         │  SSE: {type:"hitl"} → client      │
         │  Judge recommendation shown to    │
         │  reviewer as decision aid         │
         │  EventSource stays open           │
         └────────────┬─────────────────────┘
                      │ POST /decide
                      │ Command(resume={decision, feedback})
            ┌─────────┴──────────┐
            │                    │
  ┌─────────▼─────┐    ┌─────────▼──────┐
  │  approve_node │    │  reject_node    │
  │  status =     │    │  status =       │
  │  "approved"   │    │  "rejected"     │
  └─────────┬─────┘    └─────────┬───────┘
            └─────────┬──────────┘
                    END
             SSE: {type:"done"}
             EventSource closes

╔══════════════════════════════════════════════════════════════╗
║                      DATA LAYER                              ║
╚══════════════════════════════════════════════════════════════╝

  ┌────────────────────────────────────────────────────┐
  │          PostgreSQL 16 + pgvector                   │
  │                                                     │
  │  validations table                                  │
  │  ┌──────────────────────────────────────────────┐  │
  │  │ id · url · status · overall_score            │  │
  │  │ overall_passed · findings (JSONB)            │  │
  │  │ routing_decision (JSONB)                     │  │
  │  │ skipped_agents (JSONB)                       │  │
  │  │ judge_recommendation (JSONB)                 │  │
  │  │ trace_url · errors · created_at · updated_at │  │
  │  └──────────────────────────────────────────────┘  │
  │  → upsert on every state transition                 │
  │  → survives backend restarts                        │
  │                                                     │
  │  langchain_pg_embedding table (PGVector)            │
  │  ┌──────────────────────────────────────────────┐  │
  │  │ collection: mayo_medical_knowledge            │  │
  │  │ 7 topics × N chunks × 1536-dim embeddings    │  │
  │  │ (diabetes, hypertension, heart disease,       │  │
  │  │  cancer screening, mental health, COVID-19,   │  │
  │  │  Mayo editorial standards)                    │  │
  │  └──────────────────────────────────────────────┘  │
  │  → seeded once via scripts/seed_knowledge.py        │
  │  → queried by accuracy agent (MMR k=5)              │
  └────────────────────────────────────────────────────┘

╔══════════════════════════════════════════════════════════════╗
║                   DEPLOYMENT TOPOLOGY                        ║
╚══════════════════════════════════════════════════════════════╝

  Local Dev                         HF Spaces (Docker)
  ─────────────────────────         ──────────────────────────
  Terminal 1: docker compose up     Single container (port 7860)
  Terminal 2: uvicorn :8000         supervisord manages:
  Terminal 3: npm run dev :3000       • seed_knowledge.py (once)
                                      • uvicorn        :8000
  OR: npm start (root)                • next node      :3000
      └─ scripts/start.js             • nginx          :7860
         orchestrates all 3
                                    Secrets (HF Space settings):
  npm run record                      OPENAI_API_KEY
  └─ scripts/record-demo.js          DATABASE_URL (Neon)
     Playwright video of full         CORS_ORIGINS=["*"]
     app walkthrough

╔══════════════════════════════════════════════════════════════╗
║                       TECH STACK                             ║
╚══════════════════════════════════════════════════════════════╝

  Layer             Technology
  ────────────────  ──────────────────────────────────────────
  Orchestration     LangGraph 1.0 (StateGraph, Send API,
                    interrupt / Command, MemorySaver)
  LLM               OpenAI GPT-4o  (agents, temp=0, JSON mode)
                    + GPT-4o-mini (judge, temp=0, JSON mode)
  Embeddings        OpenAI text-embedding-3-small
  Vector DB         PostgreSQL 16 + pgvector (Docker / Neon)
  Web Scraping      httpx + BeautifulSoup4 + lxml
  API               FastAPI + uvicorn + sse-starlette
  Frontend          Next.js 14 App Router + TypeScript
                    + Tailwind CSS
  Process mgmt      supervisord (prod) / npm start (dev)
  Web proxy         nginx (prod only)
  Testing           pytest + Playwright E2E
  Runtime           Python 3.11 + Node 20
```
