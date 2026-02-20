"""
Mayo Clinic Content Validator — FastAPI Backend

Endpoints:
  POST   /api/validate                    Submit a Mayo Clinic URL for validation
  GET    /api/validate/{id}/stream        SSE stream of live validation progress
  GET    /api/validate/{id}               Get current validation state (polling fallback)
  POST   /api/validate/{id}/decide        Human approve/reject (HITL resume)
  GET    /api/validations                 List recent validations (home page)
  GET    /api/health                      Health check

SSE + HITL Architecture:
  - Each validation gets an asyncio.Queue stored in sse_queues[vid]
  - _run_pipeline() background task pushes typed events to the queue
  - The SSE generator consumes from the queue and streams to the client
  - When interrupt() is hit, _run_pipeline exits (graph frozen in MemorySaver)
  - EventSource stays open (no "done" event received)
  - POST /decide spawns _resume_pipeline() which reuses the same queue
  - "done" event closes the EventSource on the frontend

Persistence:
  - validation_store dict = in-memory cache for active/recent validations
  - Postgres validations table = durable history (survives restarts)
  - upsert_validation() is called at every meaningful state transition
"""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from sse_starlette.sse import EventSourceResponse

from config.settings import settings
from models.schemas import ValidateRequest, HumanDecisionRequest
from pipeline.graph import validation_graph
import db


# ---------------------------------------------------------------------------
# App lifecycle — open/close DB pool
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool()
    yield
    await db.close_pool()


app = FastAPI(
    title="Mayo Clinic Content Validator",
    description="Multi-agent LangGraph content validation with HITL",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory stores (transient — for active pipeline coordination)
# ---------------------------------------------------------------------------

# Latest ValidationState snapshot for each active validation (in-memory cache)
validation_store: Dict[str, Dict[str, Any]] = {}

# SSE queue registry: validation_id → asyncio.Queue of event dicts
sse_queues: Dict[str, asyncio.Queue] = {}

# Track which agent_complete events have already been emitted (avoid duplicates)
emitted_agents: Dict[str, set] = {}


# ---------------------------------------------------------------------------
# Helper: build initial state
# ---------------------------------------------------------------------------

def _initial_state(vid: str, url: str, requested_by: str) -> Dict[str, Any]:
    return {
        "validation_id": vid,
        "url": url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "requested_by": requested_by,
        "scraped_content": None,
        "messages": [],
        "findings": [],
        "agent_statuses": {},
        "status": "pending",
        "overall_score": None,
        "overall_passed": None,
        "human_decision": None,
        "human_feedback": None,
        "reviewed_by": None,
        "errors": [],
    }


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

async def _run_pipeline(vid: str, initial_state: Dict, q: asyncio.Queue) -> None:
    """
    Runs the LangGraph validation pipeline in a background task.
    Streams typed events to the SSE queue.
    Exits after emitting the 'hitl' event (graph pauses at interrupt()).
    Persists state to Postgres at each meaningful lifecycle point.
    """
    config = RunnableConfig(configurable={"thread_id": vid})
    emitted_agents[vid] = set()

    try:
        await q.put({"type": "status", "data": {"status": "scraping", "validation_id": vid}})

        async for chunk in validation_graph.astream(
            initial_state, config=config, stream_mode="values"
        ):
            # chunk is the full ValidationState after each node completes
            validation_store[vid] = chunk
            await db.upsert_validation(chunk)

            current_status = chunk.get("status", "")

            # Emit "running" status once (after scraping)
            if current_status == "running":
                await q.put({"type": "status", "data": {"status": "running"}})

            # Emit agent_complete for each newly finished agent
            agent_statuses = chunk.get("agent_statuses", {})
            for agent_name, agent_status in agent_statuses.items():
                if agent_status == "done" and agent_name not in emitted_agents[vid]:
                    emitted_agents[vid].add(agent_name)
                    findings = chunk.get("findings", [])
                    finding = next(
                        (f for f in findings if f.agent == agent_name), None
                    )
                    await q.put({
                        "type": "agent_complete",
                        "data": {
                            "agent": agent_name,
                            "finding": finding.model_dump() if finding else None,
                        },
                    })

            # Emit HITL event when graph hits interrupt()
            if current_status == "awaiting_human":
                findings = chunk.get("findings", [])
                await q.put({
                    "type": "hitl",
                    "data": {
                        "validation_id": vid,
                        "overall_score": chunk.get("overall_score"),
                        "overall_passed": chunk.get("overall_passed"),
                        "findings": [f.model_dump() for f in findings],
                    },
                })
                # Graph is now suspended. Exit background task.
                return

            # Emit error status
            if current_status == "failed":
                errors = chunk.get("errors", [])
                await q.put({
                    "type": "error",
                    "data": {"message": "; ".join(errors) if errors else "Validation failed"},
                })
                await q.put({"type": "done", "data": {"status": "failed"}})
                return

    except Exception as e:
        if vid in validation_store:
            validation_store[vid]["status"] = "failed"
            await db.upsert_validation(validation_store[vid])
        await q.put({"type": "error", "data": {"message": str(e)}})
        await q.put({"type": "done", "data": {"status": "failed"}})


async def _resume_pipeline(
    vid: str,
    decision: str,
    feedback: str,
    reviewer_id: str,
    q: asyncio.Queue,
) -> None:
    """
    Resumes the suspended LangGraph graph after a human decision.
    The graph resumes from the interrupt() point in human_gate_node.
    """
    config = RunnableConfig(configurable={"thread_id": vid})

    try:
        resume_command = Command(resume={
            "human_decision": decision,
            "human_feedback": feedback,
            "reviewed_by": reviewer_id,
        })

        async for chunk in validation_graph.astream(
            resume_command, config=config, stream_mode="values"
        ):
            validation_store[vid] = chunk
            await db.upsert_validation(chunk)

        final_status = validation_store.get(vid, {}).get("status", "unknown")
        await q.put({"type": "done", "data": {"status": final_status}})

    except Exception as e:
        await q.put({"type": "error", "data": {"message": str(e)}})
        await q.put({"type": "done", "data": {"status": "failed"}})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/validate")
async def start_validation(
    req: ValidateRequest, background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """Submit a Mayo Clinic URL for validation. Returns validation_id immediately."""
    vid = str(uuid.uuid4())
    q: asyncio.Queue = asyncio.Queue()
    sse_queues[vid] = q

    state = _initial_state(vid, req.url, req.requested_by or "web-user")
    validation_store[vid] = state
    await db.upsert_validation(state)

    background_tasks.add_task(_run_pipeline, vid, state, q)

    return {"validation_id": vid}


@app.get("/api/validate/{vid}/stream")
async def stream_validation(vid: str) -> EventSourceResponse:
    """
    SSE endpoint. Frontend opens an EventSource connection here.
    Streams events until a "done" or "error" event is received.
    Sends a "ping" keepalive every 25 seconds to prevent proxy timeouts.
    """
    if vid not in sse_queues:
        raise HTTPException(status_code=404, detail="Validation not found or already complete")

    q = sse_queues[vid]

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=25.0)
                yield {"data": json.dumps(event)}
                if event["type"] in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                yield {"data": json.dumps({"type": "ping"})}

    return EventSourceResponse(event_generator())


@app.get("/api/validate/{vid}")
async def get_validation(vid: str) -> Dict[str, Any]:
    """
    Get current validation state.
    Checks in-memory cache first; falls back to Postgres for completed/restarted runs.
    """
    # In-memory cache hit (active pipeline)
    state = validation_store.get(vid)
    if state:
        result = dict(state)
        findings = result.get("findings", [])
        result["findings"] = [
            f.model_dump() if hasattr(f, "model_dump") else f for f in findings
        ]
        result.pop("messages", None)
        result.pop("scraped_content", None)
        return result

    # DB fallback (after restart or for old validations)
    row = await db.get_validation(vid)
    if not row:
        raise HTTPException(status_code=404, detail="Validation not found")
    return row


@app.post("/api/validate/{vid}/decide")
async def human_decision(
    vid: str, req: HumanDecisionRequest, background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """
    Resume the validation graph after human review.
    The graph was suspended at interrupt() in human_gate_node.
    """
    # Check memory first, then DB
    state = validation_store.get(vid) or await db.get_validation(vid)
    if not state:
        raise HTTPException(status_code=404, detail="Validation not found")

    current_status = state.get("status")
    if current_status != "awaiting_human":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit decision: current status is '{current_status}'",
        )

    if vid not in sse_queues:
        sse_queues[vid] = asyncio.Queue()
    q = sse_queues[vid]

    background_tasks.add_task(
        _resume_pipeline,
        vid,
        req.decision,
        req.feedback or "",
        req.reviewer_id or "web-user",
        q,
    )

    return {"status": "resuming", "validation_id": vid}


@app.get("/api/validations")
async def list_validations_endpoint() -> list:
    """Returns up to 20 most recent validations from Postgres (survives restarts)."""
    return await db.list_validations(limit=20)


@app.get("/api/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "mayo-clinic-validator"}
