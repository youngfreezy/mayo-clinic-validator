"""
Orchestrator Agent — Claude-powered agentic validation loop.

Replaces the fixed LangGraph state machine with a Claude tool-use loop
that dynamically decides which validation tools to call, in what order,
and how to interpret results.

The orchestrator:
  1. Receives a URL
  2. Scrapes content via MCP tools
  3. Reasons about which validators are relevant
  4. Runs validators (potentially in parallel)
  5. Synthesizes a judge recommendation
  6. Returns structured results for HITL review

SSE events are emitted at each step to match the existing frontend contract.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import anthropic

from config.settings import settings
from mcp_server import call_tool, TOOL_DEFINITIONS
from pipeline.state import AgentFinding

logger = logging.getLogger(__name__)

ORCHESTRATOR_MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """\
You are the Mayo Clinic Content Validation Orchestrator. Your job is to validate
Mayo Clinic web content for publication readiness by calling the right validation
tools in the right order.

## Your workflow

1. **Scrape** the URL using `scrape_url` to get the page content.
2. **Analyze** the scraped content to determine:
   - What type of content this is (standard medical article, HIL page, etc.)
   - Which validators are relevant for this content type
3. **Load rules** using `load_rules` for each validator you plan to run.
4. **For accuracy checks**: also call `retrieve_medical_refs` to get reference material.
5. **Run validators**: Call the appropriate `validate_*` tools. You can call multiple
   validators in a single response to run them in parallel.
6. **Synthesize**: After all validators complete, provide your final judge recommendation.

## Decision guidelines

- **Always run**: metadata, editorial, compliance (these apply to all content)
- **Always run for medical content**: accuracy (fact-checking against knowledge base)
- **Only run for HIL pages**: empty_tag (URL contains "healthy-lifestyle")
- **Skip validators** when their input data is missing (e.g., skip accuracy if no body text)
- **Re-run a validator** if you suspect the results are unreliable or incomplete

## Final output

After all validations complete, respond with your final assessment as a JSON block:
```json
{
  "recommendation": "approve" or "reject" or "revise",
  "confidence": 0.0 to 1.0,
  "key_concerns": ["list of critical issues"],
  "strengths": ["list of things done well"],
  "rationale": "2-3 sentence explanation of your recommendation"
}
```

Be thorough but efficient. Skip tools that won't add value for the specific content."""


# ---------------------------------------------------------------------------
# Scraped content cache — the raw_html is too large for the agent context,
# so we store scraped results and pass only summaries to the agent.
# ---------------------------------------------------------------------------

_scraped_cache: dict[str, dict] = {}


async def _execute_tool_call(
    tool_name: str,
    tool_input: dict,
    session_id: str,
) -> str:
    """Execute a single tool call, handling the scraped content cache."""

    # For validate_* tools, inject full scraped_content from cache if the agent
    # passed a reference instead of the full object
    if tool_name.startswith("validate_") and tool_name != "validate_empty_tags":
        sc = tool_input.get("scraped_content")
        if isinstance(sc, str) or (isinstance(sc, dict) and "body_text" not in sc):
            cached = _scraped_cache.get(session_id)
            if cached:
                tool_input["scraped_content"] = cached

    # For validate_empty_tags, inject raw_html from cache if not provided
    if tool_name == "validate_empty_tags":
        if not tool_input.get("raw_html") or len(tool_input.get("raw_html", "")) < 100:
            cached = _scraped_cache.get(session_id)
            if cached and cached.get("raw_html"):
                tool_input["raw_html"] = cached["raw_html"]

    result = await call_tool(tool_name, tool_input)

    # Cache scraped content (with raw_html) for later tool calls
    if tool_name == "scrape_url":
        try:
            parsed = json.loads(result)
            # The scrape_url tool strips raw_html from the result, but we need
            # the full content for validate_* tools. Re-scrape is wasteful, so
            # we call the underlying scraper and cache the full result.
            from tools.web_scraper import scrape_mayo_url
            full_result = await scrape_mayo_url(tool_input["url"])
            _scraped_cache[session_id] = full_result
        except Exception:
            pass

    return result


async def run_orchestrator(
    url: str,
    validation_id: str,
    requested_by: str = "web-user",
    q: Optional[asyncio.Queue] = None,
) -> Dict[str, Any]:
    """
    Run the agentic validation loop.

    Args:
        url: Mayo Clinic URL to validate
        validation_id: Unique ID for this validation
        requested_by: Who requested the validation
        q: Optional SSE event queue for streaming progress to frontend

    Returns:
        Complete validation result dict matching the existing state shape.
    """
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def emit(event_type: str, data: dict):
        if q:
            await q.put({"type": event_type, "data": data})

    # Initialize result state
    result_state: Dict[str, Any] = {
        "validation_id": validation_id,
        "url": url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "requested_by": requested_by,
        "status": "pending",
        "findings": [],
        "agent_statuses": {},
        "overall_score": None,
        "overall_passed": None,
        "judge_recommendation": None,
        "routing_decision": None,
        "skipped_agents": [],
        "errors": [],
    }

    await emit("status", {"status": "scraping", "validation_id": validation_id})

    # Build initial messages
    messages: list[dict] = [
        {
            "role": "user",
            "content": f"Validate this Mayo Clinic URL for publication readiness: {url}",
        }
    ]

    completed_agents: set[str] = set()
    routing_emitted = False
    agent_findings: List[AgentFinding] = []

    try:
        # Agentic loop — keep calling Claude until it stops requesting tools
        for iteration in range(20):  # Safety cap
            response = await client.messages.create(
                model=ORCHESTRATOR_MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            # Process response content blocks
            assistant_content = response.content
            tool_calls = [b for b in assistant_content if b.type == "tool_use"]
            text_blocks = [b for b in assistant_content if b.type == "text"]

            # Add assistant response to conversation
            messages.append({"role": "assistant", "content": assistant_content})

            # If no tool calls, the agent is done — extract final recommendation
            if not tool_calls:
                final_text = " ".join(b.text for b in text_blocks)
                judge_rec = _extract_judge_recommendation(final_text)
                if judge_rec:
                    result_state["judge_recommendation"] = judge_rec
                    await emit("judge", judge_rec)
                break

            # Emit routing event on first tool call after scraping
            if not routing_emitted and any(
                tc.name.startswith("validate_") or tc.name == "load_rules"
                for tc in tool_calls
            ):
                routing_emitted = True
                # Determine which agents the orchestrator plans to run
                agents_planned = set()
                for tc in tool_calls:
                    if tc.name.startswith("validate_"):
                        agent_name = tc.name.replace("validate_", "")
                        agents_planned.add(agent_name)
                    elif tc.name == "load_rules":
                        agent_name = tc.input.get("agent_name", "")
                        if agent_name:
                            agents_planned.add(agent_name)

                all_agents = {"metadata", "editorial", "compliance", "accuracy", "empty_tag"}
                skipped = all_agents - agents_planned if agents_planned else set()

                routing_decision = {
                    "agents_to_run": sorted(agents_planned),
                    "agents_skipped": sorted(skipped),
                    "content_type": "standard",
                    "routing_method": "agentic",
                }
                result_state["routing_decision"] = routing_decision
                result_state["skipped_agents"] = sorted(skipped)
                await emit("status", {"status": "running"})
                await emit("routing", routing_decision)

            # Execute tool calls (concurrently when multiple)
            tool_results = []
            if len(tool_calls) > 1:
                # Run in parallel
                tasks = [
                    _execute_tool_call(tc.name, tc.input, validation_id)
                    for tc in tool_calls
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for tc, res in zip(tool_calls, results):
                    if isinstance(res, Exception):
                        tool_results.append((tc, json.dumps({"error": str(res)})))
                    else:
                        tool_results.append((tc, res))
            else:
                tc = tool_calls[0]
                try:
                    res = await _execute_tool_call(tc.name, tc.input, validation_id)
                    tool_results.append((tc, res))
                except Exception as e:
                    tool_results.append((tc, json.dumps({"error": str(e)})))

            # Build tool result messages and emit SSE events
            tool_result_contents = []
            for tc, result_str in tool_results:
                tool_result_contents.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result_str,
                })

                # Emit agent_complete for validate_* tools
                if tc.name.startswith("validate_"):
                    agent_name = tc.name.replace("validate_", "")
                    if agent_name not in completed_agents:
                        completed_agents.add(agent_name)
                        try:
                            finding_data = json.loads(result_str)
                            finding = AgentFinding(
                                agent=agent_name,
                                passed=finding_data.get("passed", False),
                                score=float(finding_data.get("score", 0.0)),
                                passed_checks=finding_data.get("passed_checks", []),
                                issues=finding_data.get("issues", []),
                                recommendations=finding_data.get("recommendations", []),
                            )
                            agent_findings.append(finding)
                            result_state["agent_statuses"][agent_name] = "done"
                            await emit("agent_complete", {
                                "agent": agent_name,
                                "finding": finding.model_dump(),
                            })
                        except Exception:
                            result_state["agent_statuses"][agent_name] = "done"
                            await emit("agent_complete", {
                                "agent": agent_name,
                                "finding": None,
                            })

            messages.append({"role": "user", "content": tool_result_contents})

        # Compute aggregate scores
        result_state["findings"] = agent_findings
        if agent_findings:
            scores = [f.score for f in agent_findings]
            result_state["overall_score"] = round(sum(scores) / len(scores), 3)
            result_state["overall_passed"] = all(f.passed for f in agent_findings)
        else:
            result_state["overall_score"] = 0.0
            result_state["overall_passed"] = False

        # Set status to awaiting_human
        result_state["status"] = "awaiting_human"

        # Emit HITL event
        await emit("hitl", {
            "validation_id": validation_id,
            "overall_score": result_state["overall_score"],
            "overall_passed": result_state["overall_passed"],
            "findings": [f.model_dump() for f in agent_findings],
            "skipped_agents": result_state.get("skipped_agents", []),
            "routing_decision": result_state.get("routing_decision"),
            "judge_recommendation": result_state.get("judge_recommendation"),
        })

        return result_state

    except Exception as e:
        logger.exception("Orchestrator failed for %s", url)
        result_state["status"] = "failed"
        result_state["errors"] = [f"Orchestrator error: {str(e)}"]
        await emit("error", {"message": str(e)})
        await emit("done", {"status": "failed"})
        return result_state

    finally:
        # Clean up scraped content cache
        _scraped_cache.pop(validation_id, None)


def _extract_judge_recommendation(text: str) -> Optional[dict]:
    """Extract the JSON judge recommendation from the agent's final text response."""
    # Try to find JSON block in the text
    import re

    # Look for ```json ... ``` blocks
    json_match = re.search(r"```json\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Look for raw JSON object with expected keys
    json_match = re.search(r'\{[^{}]*"recommendation"[^{}]*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback: try to parse the entire text as JSON
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "recommendation" in parsed:
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    return None
