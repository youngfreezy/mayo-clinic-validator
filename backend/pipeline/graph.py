from __future__ import annotations

from typing import List

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Send

from pipeline.state import ValidationState, AgentFinding
from agents.content_fetcher import fetch_content_node
from agents.triage_agent import triage_node
from agents.metadata_agent import run_metadata_agent
from agents.editorial_agent import run_editorial_agent
from agents.compliance_agent import run_compliance_agent
from agents.accuracy_agent import run_accuracy_agent
from agents.empty_tag_agent import run_empty_tag_agent


# ---------------------------------------------------------------------------
# Agent name → graph node name mapping
# ---------------------------------------------------------------------------

AGENT_NODE_MAP = {
    "metadata": "metadata_node",
    "editorial": "editorial_node",
    "compliance": "compliance_node",
    "accuracy": "accuracy_node",
    "empty_tag": "empty_tag_node",
}

ALL_AGENT_NODES = list(AGENT_NODE_MAP.values())


# ---------------------------------------------------------------------------
# Dispatch: conditional fan-out using LangGraph Send API
# ---------------------------------------------------------------------------

def dispatch_agents(state: ValidationState) -> List[Send]:
    """
    Reads routing_decision from state (set by triage_node) to decide
    which agents to dispatch. Falls back to all standard agents if
    routing_decision is missing.
    """
    routing = state.get("routing_decision")
    if routing:
        agents_to_run = routing.get("agents_to_run", ["metadata", "editorial", "compliance", "accuracy"])
    else:
        agents_to_run = ["metadata", "editorial", "compliance", "accuracy"]

    sends = []
    for agent_name in agents_to_run:
        node_name = AGENT_NODE_MAP.get(agent_name)
        if node_name:
            sends.append(Send(node_name, state))
    return sends


# ---------------------------------------------------------------------------
# Aggregate: fan-in after all dispatched agents complete
# ---------------------------------------------------------------------------

async def aggregate_node(state: ValidationState) -> dict:
    """
    LangGraph waits for all Send branches to complete before calling this node.
    Computes overall score and pass/fail from however many agents ran.
    """
    findings = state.get("findings", [])

    if findings:
        overall_score = round(sum(f.score for f in findings) / len(findings), 3)
        # Content passes only if ALL dispatched agents pass
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
        "skipped_agents": state.get("skipped_agents", []),
        "routing_decision": state.get("routing_decision"),
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
    g.add_node("triage", triage_node)
    g.add_node("metadata_node", run_metadata_agent)
    g.add_node("editorial_node", run_editorial_agent)
    g.add_node("compliance_node", run_compliance_agent)
    g.add_node("accuracy_node", run_accuracy_agent)
    g.add_node("empty_tag_node", run_empty_tag_agent)
    g.add_node("aggregate", aggregate_node)
    g.add_node("human_gate", human_gate_node)
    g.add_node("approve", approve_node)
    g.add_node("reject", reject_node)

    # Entry point
    g.add_edge(START, "fetch_content")

    # fetch_content → triage (classify content, select agents)
    g.add_edge("fetch_content", "triage")

    # Fan-out: triage → dispatch → selected agents
    g.add_conditional_edges(
        "triage",
        dispatch_agents,
        ALL_AGENT_NODES,
    )

    # Fan-in: all agent nodes → aggregate
    # LangGraph only waits for agents that were actually dispatched via Send
    for node in ALL_AGENT_NODES:
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
