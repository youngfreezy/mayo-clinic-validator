---
title: Mayo Clinic Content Validator
emoji: 🏥
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# Mayo Clinic Content Validator

A multi-agent LangGraph content validation platform with human-in-the-loop (HITL) approval. Input any Mayo Clinic URL and get automated compliance, editorial, and medical accuracy validation with real-time SSE updates and a Next.js review dashboard.

---

## Architecture Overview

### LangGraph Pipeline

```
                        ┌─────────────────────────────────────────────┐
                        │          LANGGRAPH STATE MACHINE            │
                        │  (PostgresCheckpointer — durable HITL)      │
                        └─────────────────────────────────────────────┘

                                          │
                              ┌───────────▼────────────┐
                              │    fetch_content_node  │
                              │  ┌──────────────────┐  │
                              │  │  Web Scraper     │  │
                              │  │ (httpx + BS4)    │  │
                              │  │                  │  │
                              │  │ Extracts:        │  │
                              │  │ • Title          │  │
                              │  │ • Meta tags      │  │
                              │  │ • JSON-LD        │  │
                              │  │ • Body text      │  │
                              │  │ • Headings       │  │
                              │  │ • Last reviewed  │  │
                              │  │ • OG tags        │  │
                              │  └──────────────────┘  │
                              └────────────┬───────────┘
                                           │
                              ┌────────────▼───────────┐
                              │      triage_node       │
                              │  URL-based router      │
                              │  HIL → 5 agents        │
                              │  Standard → 4 agents   │
                              └────────────┬───────────┘
                                           │
                              dispatch_agents() — Send API
                              (conditional based on routing_decision)
                    ┌──────────┬───────────┼───────────┬──────────────┐
                    │          │           │           │              │
          ┌─────────▼──┐ ┌────▼─────┐ ┌───▼──────┐ ┌─▼───────────┐ ┌▼───────────┐
          │ metadata   │ │editorial │ │compliance│ │accuracy     │ │empty_tag   │
          │ _node      │ │_node     │ │_node     │ │_node        │ │_node       │
          │            │ │          │ │          │ │             │ │(HIL only)  │
          │  GPT-4o    │ │ GPT-4o   │ │ GPT-4o   │ │ PGVector RAG│ │ Regex scan │
          │            │ │          │ │          │ │ ────────────│ │ raw HTML   │
          │ • Meta desc│ │ • H1-H4  │ │ • No     │ │ MMR k=5    │ │            │
          │ • Canonical│ │ • Review │ │  "cures" │ │ GPT-4o     │ │ • <title/> │
          │ • JSON-LD  │ │ • Attrib│ │ • Discl. │ │ fact-check │ │ • <h1/>    │
          │ • OG tags  │ │ • Sect. │ │ • FDA    │ │ vs refs    │ │ • <p/>     │
          └─────┬──────┘ └───┬─────┘ └────┬─────┘ └─────┬──────┘ └─────┬──────┘
                │            │            │              │    (cond.)   │
                findings (Annotated[List, operator.add] reducer)
                                        │
                              ┌─────────▼──────────┐
                              │   aggregate_node   │
                              │ overall_score =    │
                              │ mean(all scores)   │
                              │ overall_passed =   │
                              │ all(passed)        │
                              └─────────┬──────────┘
                                        │
                              ┌─────────▼──────────┐
                              │    judge_node      │
                              │ LLM-as-a-Judge     │
                              │ (GPT-4o-mini)      │
                              │ → approve/reject/  │
                              │   needs_revision   │
                              │ → confidence level │
                              └─────────┬──────────┘
                                        │
                              ┌─────────▼──────────┐
                              │  human_gate_node   │
                              │                    │
                              │  interrupt()  ◄────┼──── SSE: {type:"hitl"}
                              │  judge rec shown   │         graph suspends
                              │  to reviewer       │         state persisted
                              │  PostgresChkpt     │
                              │  checkpoints here  │
                              └────────┬───────────┘
                                       │ Command(resume={decision, feedback})
                          ┌────────────┼─────────────┐
                          │                          │
               ┌──────────▼──────┐       ┌──────────▼──────┐
               │  approve_node   │       │   reject_node   │
               │  status=approved│       │  status=rejected│
               └──────────┬──────┘       └──────────┬──────┘
                          │                          │
                          └──────────┬───────────────┘
                                   END
                           SSE: {type:"done"}
```

### SSE Event Flow (Client ↔ Server)

```
Browser                         FastAPI Backend                    LangGraph
   │                                  │                               │
   │─── POST /api/validate ──────────►│                               │
   │◄── {validation_id: "abc-123"} ───│                               │
   │                                  │                               │
   │─── GET /api/validate/abc/stream ►│ (SSE connection stays open)   │
   │                                  │──── astream(initial_state) ──►│
   │◄── data:{type:"status",          │                               │ fetch_content
   │         data:{status:"scraping"}}│◄── chunk: status=running ─────│ done
   │◄── data:{type:"status",          │                               │
   │         data:{status:"running"}} │                               │ 4 parallel
   │                                  │                               │ agents run
   │◄── data:{type:"agent_complete",  │◄── chunk: findings=[...] ─────│ all done
   │         data:{agent:"metadata"}} │                               │
   │◄── data:{type:"agent_complete",  │                               │ aggregate
   │         data:{agent:"editorial"}}│                               │ node
   │◄── data:{type:"agent_complete",  │                               │
   │         data:{agent:"compliance"}}                               │
   │◄── data:{type:"agent_complete",  │◄── chunk: status=            │ human_gate
   │         data:{agent:"accuracy"}} │     awaiting_human ───────────│ interrupt()
   │◄── data:{type:"hitl",            │     (graph frozen)            │
   │         data:{overall_score,...}}│                               │
   │                                  │   [EventSource stays open — no "done" yet]
   │                                  │                               │
   │─── POST /api/validate/abc/decide►│                               │
   │    {decision:"approve",...}      │── astream(Command(resume=)) ─►│
   │                                  │                               │ human_gate
   │                                  │◄── chunk: status=approved ────│ resumes
   │◄── data:{type:"done",            │                               │ → approve
   │         data:{status:"approved"}}│                               │ node → END
   │   (EventSource closes)           │                               │
```

### Web Scraper

The **web scraper** (`backend/tools/web_scraper.py`) uses `httpx` + `BeautifulSoup4` to parse server-side rendered HTML from Mayo Clinic pages. It extracts:

| Data Point | HTML Target |
|------------|-------------|
| Title | `<h1>` → fallback `<title>` |
| Meta description | `<meta name="description">` |
| Canonical URL | `<link rel="canonical">` |
| JSON-LD structured data | `<script type="application/ld+json">` |
| Open Graph tags | `<meta property="og:*">` |
| Body text | `#main-content` → `<main>` → `<article>` cascade |
| Last reviewed date | Text containing "Updated by Mayo Clinic Staff" |
| Heading hierarchy | All `<h1>`–`<h4>` within main content |
| Internal links | `href` starting with `/` or `mayoclinic.org` |
| External links | Other `http` hrefs |

> **Note:** Mayo Clinic pages are server-side rendered. A real browser `User-Agent` header is required (included in the scraper) — without it you receive a 403.

### RAG Knowledge Base (PGVector)

The **accuracy agent** uses Retrieval-Augmented Generation to fact-check medical content against a curated knowledge base of verified Mayo Clinic reference material.

```
Content body text
       │
       ▼
OpenAI text-embedding-3-small
       │
       ▼
PGVector MMR Search (k=5, fetch_k=20)
       │
       ▼
Retrieved Mayo medical reference chunks
       │ (diabetes, hypertension, heart disease,
       │  cancer screening, mental health, COVID-19,
       │  Mayo editorial standards)
       ▼
GPT-4o fact-checks content claims vs references
       │
       ▼
AgentFinding {passed, score, issues, recommendations}
```

#### Seed Data

All reference content lives in `backend/data/knowledge_base.json`. Each entry has a `content` field (the medical text) and a `metadata` object with `topic` and `source` tags. The knowledge base currently contains **9 entries** across **8 topics**:

| Topic | Entries | What it covers |
|-------|---------|---------------|
| `diabetes` | 2 | Type 1 vs Type 2 definitions, symptoms, risk factors, A1C targets, treatment (insulin, metformin, SGLT2i, GLP-1 RA), monitoring (CGMs), complication prevention |
| `hypertension` | 2 | BP classifications (normal through hypertensive crisis), risk factors, DASH diet, medication classes (ACE inhibitors, ARBs, CCBs, diuretics, beta-blockers), home monitoring |
| `heart_disease` | 1 | CAD pathophysiology, angina and heart attack symptoms, atypical female presentation, door-to-balloon time, PCI/CABG/thrombolytics |
| `cancer_screening` | 1 | Screening protocols for breast, colorectal, lung, prostate, cervical, and skin cancer with age thresholds and intervals |
| `mental_health` | 1 | Depression and anxiety disorder definitions, DSM-5 criteria, PHQ-9 screening, treatment (CBT, SSRIs/SNRIs, TMS, ECT, ketamine), suicide prevention (988 Lifeline) |
| `mayo_editorial_standards` | 1 | Reading level targets (Flesch-Kincaid 6-8), attribution rules, 2-year review cycle, prohibited language ("cures", "guarantees"), required page elements (H1, meta description, JSON-LD, canonical URL) |
| `covid19` | 1 | SARS-CoV-2 symptoms, Long COVID, vaccine types and booster schedule, Paxlovid/remdesivir treatment, airborne transmission |

To add new topics, append entries to `knowledge_base.json` following the same `{ "content": "...", "metadata": { "topic": "...", "source": "mayo_clinic" } }` structure, then re-run the seed script.

#### Seeding Process

The seed script (`backend/scripts/seed_knowledge.py`) transforms raw knowledge entries into searchable vector embeddings:

1. **Load** -- reads all entries from `knowledge_base.json`
2. **Chunk** -- splits each entry with `RecursiveCharacterTextSplitter` using separators `["\n\n", "\n", ". ", " "]`, chunk size of 400 characters, and 80-character overlap to preserve context across boundaries
3. **Embed** -- generates vector embeddings for each chunk using OpenAI `text-embedding-3-small` (1536 dimensions)
4. **Store** -- writes chunks + embeddings into a PGVector collection named `mayo_medical_knowledge` in PostgreSQL 16 with `use_jsonb=True` for efficient metadata filtering. The script sets `pre_delete_collection=True`, so each run wipes and re-seeds from scratch

```bash
cd backend
source venv/bin/activate
python scripts/seed_knowledge.py   # ~30 seconds (OpenAI embedding calls)
```

The database runs in Docker (`pgvector/pgvector:pg16`) on port 5433. The `init-pgvector.sql` init script enables the `vector` extension on first container start.

#### Retrieval at Query Time

When the accuracy agent runs (`backend/agents/accuracy_agent.py`), it:

1. Builds a query string from the page title + first 1000 characters of body text
2. Calls `get_retriever(k=5)` from `backend/tools/rag_retriever.py`, which creates a PGVector retriever configured for **MMR (Maximal Marginal Relevance)** search
3. MMR balances relevance with diversity -- it fetches 20 candidate chunks (`fetch_k=20`), then selects the top 5 (`k=5`) using `lambda_mult=0.5` (equal weight to relevance and diversity), reducing redundancy when multiple chunks from the same entry match
4. Retrieved chunks are formatted as numbered references and injected into the GPT-4o prompt alongside the page content
5. GPT-4o compares the page's medical claims against the references, returning a score (0.0-1.0), pass/fail determination (threshold >= 0.75), specific issues found, and recommendations

If the knowledge base is unreachable or returns no relevant results, the agent scores 0.7 and notes the limitation rather than failing outright.

### State Design (LangGraph TypedDict + Annotated Reducers)

```python
class ValidationState(TypedDict):
    findings: Annotated[List[AgentFinding], operator.add]   # merge all dispatched agents
    agent_statuses: Annotated[Dict[str, str], _merge_dicts] # merge dict keys
    errors: Annotated[List[str], operator.add]               # accumulate errors
    messages: Annotated[List[BaseMessage], add_messages]     # LangChain messages
    # ... plus status, url, scraped_content, overall_score, HITL fields
```

The `Annotated` reducers are **mandatory** for the `Send` API parallel fan-out. Without them, only one agent's findings would survive (last-write-wins).

---

## Stack

| Layer | Technology |
|-------|-----------|
| Orchestration | LangGraph 1.0 (StateGraph, Send API, interrupt/Command, PostgresCheckpointer) |
| LLM | OpenAI GPT-4o (agents) + GPT-4o-mini (judge) |
| Vector DB | PostgreSQL 16 + pgvector (Docker) |
| Embeddings | OpenAI text-embedding-3-small |
| Web Scraping | httpx + BeautifulSoup4 + lxml |
| API | FastAPI + uvicorn + sse-starlette |
| Frontend | Next.js 14 App Router + TypeScript + Tailwind CSS |
| Observability | LangSmith (tracing, per-agent tags, trace URL correlation) |
| Checkpointer | AsyncPostgresSaver (durable HITL state, survives restarts) |
| Testing | pytest + Playwright |
| Runtime | Python 3.11 + Node 20 |

---

## Quick Start

### Prerequisites
- **Docker Desktop** — running before anything else
- **Python 3.11** — install with `brew install python@3.11` (available at `/opt/homebrew/bin/python3.11`)
- **Node 20** — install with `brew install node@20` (available at `/opt/homebrew/opt/node@20/bin/node`)
- **OpenAI API key** — already set in `backend/.env`

> **Ports used:** PostgreSQL on `5433`, FastAPI on `8000`, Next.js on `3000`.

---

### Step 1 — Database (one-time setup)

```bash
cd backend

# Start PostgreSQL + pgvector container on port 5433
docker compose up -d

# Create virtualenv with Python 3.11
/opt/homebrew/bin/python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Seed the RAG knowledge base (calls OpenAI Embeddings — run once)
python scripts/seed_knowledge.py
```

### Step 2 — Backend (Terminal 1)

```bash
cd backend
source venv/bin/activate          # activate the Python 3.11 venv
uvicorn main:app --host 0.0.0.0 --port 8000

# Verify: http://localhost:8000/api/health → {"status":"ok"}
```

> **Note:** HITL state is persisted to Postgres via `AsyncPostgresSaver`. You can safely restart uvicorn without losing pending reviews.

### Step 3 — Frontend (Terminal 2)

```bash
cd frontend
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"   # use Node 20
npm install          # first time only
npm run dev
# → http://localhost:3000
```

### Step 4 — Validate on the UI

1. Open **http://localhost:3000**
2. Paste any `mayoclinic.org` URL (e.g. `https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444`)
3. Click **Validate**
4. Watch agents complete in real time (4-5 agents depending on URL, plus LLM Judge)
5. Review the Judge's recommendation, then click **Approve** or **Reject** in the Human Review panel

Validation history is persisted to Postgres and survives backend restarts.

---

### Run Tests

```bash
# Backend unit tests (no network calls, no OpenAI)
cd backend
source venv/bin/activate
/opt/homebrew/bin/python3.11 -m pytest tests/test_scraper.py tests/test_schemas.py -v

# Frontend Playwright E2E tests (requires both servers running on 8000 + 3000)
cd frontend
PATH="/opt/homebrew/opt/node@20/bin:$PATH" npx playwright test
```

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/validate` | Submit Mayo Clinic URL |
| `GET` | `/api/validate/{id}/stream` | SSE stream of live progress |
| `GET` | `/api/validate/{id}` | Get current validation state |
| `POST` | `/api/validate/{id}/decide` | Human approve/reject (HITL) |
| `GET` | `/api/validations` | List recent validations |
| `GET` | `/api/health` | Health check |

---

## Validation Agents

| Agent | Checks | Pass Threshold | Routing |
|-------|--------|---------------|---------|
| **Metadata** | Meta description length (150-160 chars), canonical URL, JSON-LD schema type, OG tags | ≥ 0.7 | Always |
| **Editorial** | H1-H4 hierarchy, last reviewed date (≤2 years), Mayo attribution, required sections | ≥ 0.7 | Always |
| **Compliance** | No absolute claims ("cures"), required disclaimers, FDA language, HIPAA concerns, hedging | ≥ 0.75 | Always |
| **Accuracy** | Medical fact-checking vs PGVector knowledge base (RAG) | ≥ 0.75 | Always |
| **Empty Tag** | Self-closing/empty HTML tags (`<title/>`, `<h1></h1>`, etc.) | ≥ 0.8 | HIL only |
| **Judge** | LLM-as-a-Judge meta-evaluator — synthesizes all findings into recommendation | N/A | Always |

Overall pass = **all dispatched agents pass**. Overall score = **mean of agent scores**. Judge provides recommendation to human reviewer.

---

## HITL + PostgresCheckpointer

Human gate uses LangGraph's `interrupt()` + `Command(resume=...)` pattern:
- Graph pauses at `human_gate_node`, state persisted in `AsyncPostgresSaver` (Postgres)
- SSE stream stays open (no `done` event)
- `POST /api/validate/{id}/decide` resumes graph via `Command(resume={decision})`
- `interrupt()` returns the decision dict — node routes to approve/reject

**How the checkpointer works:**

| Event | What happens |
|-------|-------------|
| Every graph node completes | Checkpointer serializes full `ValidationState` to Postgres (keyed by `thread_id`) |
| `interrupt()` called in `human_gate_node` | Graph suspends — checkpointer saves exact execution position |
| Human submits decision | `astream(Command(resume=...))` reloads saved state from Postgres and resumes from where it paused |
| Server restarts while awaiting review | Pending HITL validations survive — state is durable in Postgres |

> Falls back to in-memory `MemorySaver` when Postgres is unavailable (e.g., local development without Docker).

## Conditional Routing (Content Triage)

The `triage_node` classifies URLs before agent dispatch:

| URL Pattern | Content Type | Agents Dispatched |
|-------------|-------------|-------------------|
| `/healthy-lifestyle/*` | HIL (Healthy Living) | Metadata, Editorial, Compliance, Accuracy, **Empty Tag** |
| Everything else | Standard medical | Metadata, Editorial, Compliance, Accuracy |

Routing uses LangGraph's **Send API** for parallel fan-out — all dispatched agents execute concurrently. The `dispatch_agents()` function reads the `routing_decision` from state (set by triage) and returns `Send(node_name, state)` for each selected agent.

## LLM-as-a-Judge

After all agents complete, the **judge node** (GPT-4o-mini) synthesizes findings into a recommendation:

- **approve** — content meets all standards
- **reject** — content has significant issues
- **needs_revision** — content has minor issues that should be addressed

The judge's recommendation and confidence level are shown to the human reviewer alongside the detailed agent findings, helping inform the final HITL decision.

## Observability (LangSmith Tracing)

LangSmith tracing is enabled by default. Every LLM call, graph node execution, and tool invocation is captured as a **trace** — a hierarchical tree of operations that shows exactly what happened during a validation run.

**What tracing gives us:**

| Capability | What it shows |
|-----------|--------------|
| **Full execution timeline** | See every graph node (fetch → triage → agents → judge → human_gate) with exact durations |
| **LLM call inspection** | View the exact prompts sent to GPT-4o/GPT-4o-mini, the raw responses, token counts, and latency per call |
| **Token & cost tracking** | LangSmith automatically calculates token usage and estimated cost for each LLM call and aggregates across the full run |
| **Error diagnosis** | When an agent fails, the trace shows the exact exception, which node it occurred in, and the state at that point |
| **RAG retrieval debugging** | For the accuracy agent, see which PGVector documents were retrieved and how they influenced the fact-check |
| **Run correlation** | Each trace is linked to its `validation_id` via `run_id`, so you can jump from a validation in the UI directly to its trace |
| **Per-agent tagging** | Each LLM call is tagged with the agent name (e.g., `editorial-agent`, `accuracy-agent`) for filtering and comparison |
| **Latency bottlenecks** | Identify which agents are slowest and whether parallel fan-out is working as expected |

**Configuration:**

- **Trace URLs**: Stored in the `trace_url` field of each validation after the HITL gate
- **Pipeline timeout**: 5-minute deadline per validation, 1-minute deadline per resume
- **Centralized LLM factory**: All agents use `create_agent_llm()` with `request_timeout=120s` per LLM call

> Set `LANGCHAIN_TRACING_V2=false` in `.env` to disable tracing.
