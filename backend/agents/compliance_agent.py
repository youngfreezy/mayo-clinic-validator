"""
Compliance Agent — validates regulatory, legal, and editorial policy language.

Rules are loaded dynamically from Neo4j (primary) or validation_rules.json (fallback).
"""

import json

from langchain_core.prompts import ChatPromptTemplate

from pipeline.state import ValidationState, AgentFinding
from agents.llm_factory import create_agent_llm
from rules.loader import get_rules_for_agent

SYSTEM_PROMPT = """You are a medical content compliance specialist for Mayo Clinic.
Review health content for regulatory compliance, legal language, and editorial policy violations.
Respond ONLY with valid JSON.

{rules_block}"""

USER_PROMPT = """Review this Mayo Clinic content for compliance violations.

Title: {title}
URL: {url}
Content: {body_text}

Evaluate the content against every rule listed in the system prompt.

Respond with this exact JSON structure:
{{
  "passed": true or false,
  "score": 0.0 to 1.0,
  "passed_checks": ["list of compliance checks that passed, e.g. 'No absolute cure claims found'"],
  "issues": ["list of specific compliance violations with quoted problematic text where possible"],
  "recommendations": ["list of specific language changes or additions needed"]
}}"""


async def run_compliance_agent(state: ValidationState) -> dict:
    content = state.get("scraped_content")
    if not content:
        finding = AgentFinding(
            agent="compliance",
            passed=False,
            score=0.0,
            issues=["Content could not be scraped"],
            recommendations=["Ensure the URL is accessible and returns HTML"],
        )
        return {
            "findings": [finding],
            "agent_statuses": {"compliance": "done"},
        }

    if not content.get("body_text"):
        finding = AgentFinding(
            agent="compliance",
            passed=False,
            score=0.0,
            issues=["No body text available for compliance review"],
            recommendations=["Ensure the page has extractable text content"],
        )
        return {"findings": [finding], "agent_statuses": {"compliance": "done"}}

    # Load rules dynamically
    routing = state.get("routing_decision") or {}
    content_type = routing.get("content_type", "standard")
    rule_set = await get_rules_for_agent("compliance", content_type)
    rules_block = rule_set.to_prompt_block()

    llm = create_agent_llm("compliance", validation_id=state.get("validation_id", ""))

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT),
    ])

    chain = prompt | llm

    try:
        response = await chain.ainvoke({
            "rules_block": rules_block,
            "title": content.get("title", ""),
            "url": state["url"],
            "body_text": content.get("body_text", "")[:5000],
        })

        result = json.loads(response.content)
        finding = AgentFinding(
            agent="compliance",
            passed=result.get("passed", False),
            score=float(result.get("score", 0.0)),
            passed_checks=result.get("passed_checks", []),
            issues=result.get("issues", []),
            recommendations=result.get("recommendations", []),
        )
    except Exception as e:
        finding = AgentFinding(
            agent="compliance",
            passed=False,
            score=0.0,
            issues=[f"Agent error: {str(e)}"],
            recommendations=["Check agent configuration and OpenAI API key"],
        )

    return {
        "findings": [finding],
        "agent_statuses": {"compliance": "done"},
    }
