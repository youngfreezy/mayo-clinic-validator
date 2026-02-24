"""
Triage Agent — URL-based content classifier that determines which agents to dispatch.

Routing rules (scoped):
- URLs containing "healthy-lifestyle" → HIL (Health Information Library) content
  → run all 4 standard agents + empty_tag agent (5 total)
- All other URLs → standard 4 agents only
"""

from typing import Dict, Any, List

from pipeline.state import ValidationState

ALL_STANDARD_AGENTS = ["metadata", "editorial", "compliance", "accuracy"]
HIL_EXTRA_AGENTS = ["empty_tag"]
HIL_URL_PATTERNS = ["healthy-lifestyle"]


def _is_hil_content(url: str) -> bool:
    """Check if the URL matches a Health Information Library path."""
    return any(pattern in url for pattern in HIL_URL_PATTERNS)


async def triage_node(state: ValidationState) -> dict:
    """
    Inspects the URL to classify content type and select agents.
    Deterministic — no LLM call needed for URL-based routing.
    """
    url = state.get("url", "")
    is_hil = _is_hil_content(url)

    if is_hil:
        agents_to_run = ALL_STANDARD_AGENTS + HIL_EXTRA_AGENTS
        agents_skipped: List[str] = []
        content_type = "hil"
    else:
        agents_to_run = ALL_STANDARD_AGENTS
        agents_skipped = HIL_EXTRA_AGENTS
        content_type = "standard"

    return {
        "routing_decision": {
            "agents_to_run": agents_to_run,
            "agents_skipped": agents_skipped,
            "content_type": content_type,
            "routing_method": "url_based",
            "reasoning": {
                "empty_tag": "run:hil_content" if is_hil
                else "skip:not_hil_content",
            },
        },
        "skipped_agents": agents_skipped,
        "status": "running",
    }
