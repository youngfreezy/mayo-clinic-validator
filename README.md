# Mayo Clinic Content Validator

A multi-agent LangGraph content validation platform with human-in-the-loop (HITL) approval. Input any Mayo Clinic URL and get automated compliance, editorial, and medical accuracy validation with real-time SSE updates and a Next.js review dashboard.

---

## Architecture Overview

### LangGraph Pipeline

```
                        ┌─────────────────────────────────────────────┐
                        │          LANGGRAPH STATE MACHINE            │
                        │   (MemorySaver checkpointer — HITL safe)    │
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
                              dispatch_agents() — Send API
                            ┌──────────────┼──────────────┐──────────────┐
                            │              │              │              │
               ┌────────────▼──┐ ┌─────────▼───┐ ┌──────▼──────┐ ┌────▼──────────┐
               │ metadata_node │ │editorial_node│ │compliance_  │ │ accuracy_node  │
               │               │ │              │ │node         │ │                │
               │  GPT-4o       │ │  GPT-4o      │ │  GPT-4o     │ │ PGVector RAG  │
               │               │ │              │ │             │ │ ──────────────│
               │ Checks:       │ │ Checks:      │ │ Checks:     │ │ MMR retrieval │
               │ • Meta desc   │ │ • H1-H4 hier.│ │ • No "cures"│ │ k=5 chunks   │
               │ • Canonical   │ │ • Last review│ │ • Disclaimers│ │              │
               │ • JSON-LD     │ │ • Attribution│ │ • FDA lang  │ │  GPT-4o      │
               │ • OG tags     │ │ • Sections   │ │ • HIPAA     │ │ fact-checks  │
               │               │ │ • Taxonomy   │ │ • Hedging   │ │ vs refs      │
               └───────┬───────┘ └──────┬──────┘ └──────┬──────┘ └──────┬────────┘
                       │                │               │               │
               findings (Annotated[List, operator.add] reducer — all 4 merge correctly)
                                        │
                              ┌─────────▼──────────┐
                              │   aggregate_node   │
                              │                    │
                              │ overall_score =    │
                              │ mean(all scores)   │
                              │                    │
                              │ overall_passed =   │
                              │ all(passed)        │
                              └─────────┬──────────┘
                                        │
                              ┌─────────▼──────────┐
                              │  human_gate_node   │
                              │                    │
                              │  interrupt()  ◄────┼──── SSE: {type:"hitl"}
                              │                    │         graph suspends
                              │  MemorySaver       │         state persisted
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

The **accuracy agent** uses Retrieval-Augmented Generation:

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

### State Design (LangGraph TypedDict + Annotated Reducers)

```python
class ValidationState(TypedDict):
    findings: Annotated[List[AgentFinding], operator.add]   # merge all 4 agents
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
| Orchestration | LangGraph 1.0 (StateGraph, Send API, interrupt/Command) |
| LLM | OpenAI GPT-4o (temperature=0, JSON response mode) |
| Vector DB | PostgreSQL 16 + pgvector (Docker) |
| Embeddings | OpenAI text-embedding-3-small |
| Web Scraping | httpx + BeautifulSoup4 + lxml |
| API | FastAPI + uvicorn + sse-starlette |
| Frontend | Next.js 14 App Router + TypeScript + Tailwind CSS |
| Testing | pytest + Playwright |
| Runtime | Python 3.11 + Node 20 |

---

## Quick Start

### Prerequisites
- Docker Desktop running
- Python 3.11 (`/opt/homebrew/bin/python3.11`)
- Node 20 (`/opt/homebrew/opt/node@20/bin/node`)
- OpenAI API key (already set in `backend/.env`)

### Backend

```bash
cd backend

# Create virtualenv (Python 3.11 required)
/opt/homebrew/bin/python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start PostgreSQL + pgvector on port 5433
docker compose up -d

# Seed knowledge base (one time, calls OpenAI Embeddings API)
python scripts/seed_knowledge.py

# Start API server
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend

# Use Node 20
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
npm install
npm run dev
# → http://localhost:3000
```

### Run Tests

```bash
# Backend unit tests (no network calls)
cd backend
/opt/homebrew/bin/python3.11 -m pytest tests/test_scraper.py tests/test_schemas.py -v

# Frontend Playwright tests (requires both servers running)
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

| Agent | Checks | Pass Threshold |
|-------|--------|---------------|
| **Metadata** | Meta description length (150-160 chars), canonical URL, JSON-LD schema type, OG tags | ≥ 0.7 |
| **Editorial** | H1-H4 hierarchy, last reviewed date (≤2 years), Mayo attribution, required sections | ≥ 0.7 |
| **Compliance** | No absolute claims ("cures"), required disclaimers, FDA language, HIPAA concerns, hedging | ≥ 0.75 |
| **Accuracy** | Medical fact-checking vs PGVector knowledge base (RAG) | ≥ 0.75 |

Overall pass = **all 4 agents pass**. Overall score = **mean of 4 agent scores**.

---

## HITL Note

Human gate uses LangGraph's `interrupt()` + `Command(resume=...)` pattern:
- Graph pauses at `human_gate_node`, state persisted in `MemorySaver`
- SSE stream stays open (no `done` event)
- `POST /api/validate/{id}/decide` resumes graph via `Command(resume={decision})`
- `interrupt()` returns the decision dict — node routes to approve/reject

> **Important:** `MemorySaver` is in-process only. Restarting uvicorn clears all pending validations. For production, replace with `AsyncPostgresSaver`.
