from __future__ import annotations

from typing import List

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Send

from pipeline.state import ValidationState, AgentFinding
from agents.content_fetcher import fetch_content_node
from agents.metadata_agent import run_metadata_agent
from agents.editorial_agent import run_editorial_agent
from agents.compliance_agent import run_compliance_agent
from agents.accuracy_agent import run_accuracy_agent


# ---------------------------------------------------------------------------
# Dispatch: fan-out to 4 parallel agents using LangGraph Send API
# ---------------------------------------------------------------------------

def dispatch_agents(state: ValidationState) -> List[Send]:
    """
    Called after fetch_content_node completes.
    Returns 4 Send objects — LangGraph runs them in parallel.
    Each agent receives a copy of the full state and returns a partial update.
    The 'findings' field uses operator.add reducer so all 4 results merge correctly.
    """
    return [
        Send("metadata_node", state),
        Send("editorial_node", state),
        Send("compliance_node", state),
        Send("accuracy_node", state),
    ]


# ---------------------------------------------------------------------------
# Aggregate: fan-in after all 4 parallel agents complete
# ---------------------------------------------------------------------------

async def aggregate_node(state: ValidationState) -> dict:
    """
    LangGraph waits for all Send branches to complete before calling this node.
    By this point, state["findings"] contains all 4 agent findings (merged by operator.add).
    Compute overall score and pass/fail, then set status to awaiting_human.
    """
    findings = state.get("findings", [])

    if findings:
        overall_score = round(sum(f.score for f in findings) / len(findings), 3)
        # Content passes only if ALL agents pass
        overall_passed = all(f.passed for f in findings)
    else:
        overall_score = 0.0
        overall_passed = False

    return {
        "overall_score": overall_score,
        "overall_passed": overall_passed,
        "status": "awaiting_human",
    }


# ---------------------------------------------------------------------------
# Human Gate: interrupt() suspends the graph here for HITL review
# ---------------------------------------------------------------------------

async def human_gate_node(state: ValidationState) -> dict:
    """
    Calls interrupt() — graph execution suspends completely.
    The entire ValidationState is persisted by MemorySaver under thread_id.

    When POST /api/validate/{id}/decide is called, the graph resumes from
    this exact point and interrupt() returns the human input dict.
    """
    human_input = interrupt({
        "validation_id": state["validation_id"],
        "url": state["url"],
        "overall_score": state.get("overall_score"),
        "overall_passed": state.get("overall_passed"),
        "findings": [f.model_dump() for f in state.get("findings", [])],
        "message": "Human review required. Approve or reject this content.",
    })

    # human_input is the dict passed to astream() on resume:
    # {"human_decision": "approve"|"reject", "human_feedback": "...", "reviewed_by": "..."}
    return {
        "human_decision": human_input.get("human_decision"),
        "human_feedback": human_input.get("human_feedback", ""),
        "reviewed_by": human_input.get("reviewed_by", "web-user"),
    }


# ---------------------------------------------------------------------------
# Terminal nodes
# ---------------------------------------------------------------------------

async def approve_node(state: ValidationState) -> dict:
    return {"status": "approved"}


async def reject_node(state: ValidationState) -> dict:
    return {"status": "rejected"}


# ---------------------------------------------------------------------------
# Routing after human gate
# ---------------------------------------------------------------------------

def route_after_human(state: ValidationState) -> str:
    return "approve" if state.get("human_decision") == "approve" else "reject"


# ---------------------------------------------------------------------------
# Build and compile the graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    g = StateGraph(ValidationState)

    # Register all nodes
    g.add_node("fetch_content", fetch_content_node)
    g.add_node("metadata_node", run_metadata_agent)
    g.add_node("editorial_node", run_editorial_agent)
    g.add_node("compliance_node", run_compliance_agent)
    g.add_node("accuracy_node", run_accuracy_agent)
    g.add_node("aggregate", aggregate_node)
    g.add_node("human_gate", human_gate_node)
    g.add_node("approve", approve_node)
    g.add_node("reject", reject_node)

    # Entry point
    g.add_edge(START, "fetch_content")

    # Fan-out: fetch_content → dispatch → 4 parallel agents
    g.add_conditional_edges(
        "fetch_content",
        dispatch_agents,
        ["metadata_node", "editorial_node", "compliance_node", "accuracy_node"],
    )

    # Fan-in: all 4 agents → aggregate (LangGraph waits for all Send branches)
    for node in ["metadata_node", "editorial_node", "compliance_node", "accuracy_node"]:
        g.add_edge(node, "aggregate")

    # Linear from aggregate through HITL gate
    g.add_edge("aggregate", "human_gate")

    # Conditional routing after human decision
    g.add_conditional_edges(
        "human_gate",
        route_after_human,
        {"approve": "approve", "reject": "reject"},
    )

    g.add_edge("approve", END)
    g.add_edge("reject", END)

    # Compile with MemorySaver for HITL state persistence
    # NOTE: MemorySaver = single uvicorn worker only (no --workers flag)
    return g.compile(checkpointer=MemorySaver())


# Module-level singleton graph instance
validation_graph = build_graph()
