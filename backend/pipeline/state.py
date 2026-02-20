from __future__ import annotations

import operator
from typing import TypedDict, Annotated, List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentFinding(BaseModel):
    agent: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    issues: List[str] = []
    recommendations: List[str] = []


def _merge_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reducer for agent_statuses.
    Without this, 4 parallel Send branches overwrite each other (last-write-wins).
    With this, each agent's {"agent_name": "done"} update is merged into one dict.
    """
    return {**a, **b}


class ValidationState(TypedDict):
    # Identity
    validation_id: str
    url: str
    created_at: str
    requested_by: str

    # Scraped content (set by fetch_content_node)
    scraped_content: Optional[Dict[str, Any]]

    # LangGraph message accumulation reducer
    messages: Annotated[List[BaseMessage], add_messages]

    # Agent findings — operator.add required for Send API parallel fan-out
    # Each agent returns {"findings": [one_finding]} which get concatenated
    findings: Annotated[List[AgentFinding], operator.add]

    # Per-agent status tracking.
    # _merge_dicts reducer is required — without it, parallel Send branches overwrite each other.
    agent_statuses: Annotated[Dict[str, str], _merge_dicts]

    # Pipeline lifecycle
    status: Literal[
        "pending", "scraping", "running",
        "awaiting_human", "approved", "rejected", "failed"
    ]

    # Computed by aggregate_node
    overall_score: Optional[float]
    overall_passed: Optional[bool]

    # Human-in-the-loop fields (set when graph resumes after interrupt)
    human_decision: Optional[Literal["approve", "reject"]]
    human_feedback: Optional[str]
    reviewed_by: Optional[str]

    # Error accumulation — operator.add so parallel agents can each append errors
    errors: Annotated[List[str], operator.add]
