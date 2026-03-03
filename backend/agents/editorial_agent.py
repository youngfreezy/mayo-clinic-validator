"""
Editorial Agent — validates heading hierarchy, last reviewed date, attribution,
content structure, and taxonomy alignment.

Rules are loaded dynamically from Neo4j (primary) or validation_rules.json (fallback).
"""

import json

from langchain_core.prompts import ChatPromptTemplate

from pipeline.state import ValidationState, AgentFinding
from agents.llm_factory import create_agent_llm
from rules.loader import get_rules_for_agent

SYSTEM_PROMPT = """You are a senior editorial standards reviewer for Mayo Clinic's digital health content.
Evaluate editorial quality and structure of a Mayo Clinic web page. Respond ONLY with valid JSON.

{rules_block}"""

USER_PROMPT = """Review the editorial quality of this Mayo Clinic page.

URL: {url}
Title: {title}
Last Reviewed Date: {last_reviewed}
Heading Structure: {headings}
Body Text (first 2000 chars): {body_preview}
Internal Link Count: {internal_link_count}
External Link Count: {external_link_count}

Evaluate the content against every rule listed in the system prompt.

Respond with this exact JSON structure:
{{
  "passed": true or false,
  "score": 0.0 to 1.0,
  "passed_checks": ["list of checks that passed, e.g. specific validations that were OK"],
  "issues": ["list of specific issues found"],
  "recommendations": ["list of specific fixes"]
}}"""


async def run_editorial_agent(state: ValidationState) -> dict:
    content = state.get("scraped_content")
    if not content:
        finding = AgentFinding(
            agent="editorial",
            passed=False,
            score=0.0,
            issues=["Content could not be scraped"],
            recommendations=["Ensure the URL is accessible and returns HTML"],
        )
        return {
            "findings": [finding],
            "agent_statuses": {"editorial": "done"},
        }

    if not content.get("body_text") and not content.get("headings"):
        finding = AgentFinding(
            agent="editorial",
            passed=False,
            score=0.0,
            issues=["Scraped content missing both body_text and headings"],
            recommendations=["Verify the scraper is extracting content correctly"],
        )
        return {"findings": [finding], "agent_statuses": {"editorial": "done"}}

    # Load rules dynamically
    routing = state.get("routing_decision") or {}
    content_type = routing.get("content_type", "standard")
    rule_set = await get_rules_for_agent("editorial", content_type)
    rules_block = rule_set.to_prompt_block()

    headings = content.get("headings", [])
    headings_formatted = "\n".join(
        f"  {'#' * h['level']} {h['text']}" for h in headings
    )

    llm = create_agent_llm("editorial", validation_id=state.get("validation_id", ""))

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT),
    ])

    chain = prompt | llm

    try:
        response = await chain.ainvoke({
            "rules_block": rules_block,
            "url": state["url"],
            "title": content.get("title", ""),
            "last_reviewed": content.get("last_reviewed") or "Not found",
            "headings": headings_formatted or "No headings detected",
            "body_preview": content.get("body_text", "")[:2000],
            "internal_link_count": len(content.get("internal_links", [])),
            "external_link_count": len(content.get("external_links", [])),
        })

        result = json.loads(response.content)
        finding = AgentFinding(
            agent="editorial",
            passed=result.get("passed", False),
            score=float(result.get("score", 0.0)),
            passed_checks=result.get("passed_checks", []),
            issues=result.get("issues", []),
            recommendations=result.get("recommendations", []),
        )
    except Exception as e:
        finding = AgentFinding(
            agent="editorial",
            passed=False,
            score=0.0,
            issues=[f"Agent error: {str(e)}"],
            recommendations=["Check agent configuration and OpenAI API key"],
        )

    return {
        "findings": [finding],
        "agent_statuses": {"editorial": "done"},
    }
