"""
Metadata Agent — validates meta tags, JSON-LD structured data, Open Graph, canonical URL.

Rules are loaded dynamically from Neo4j (primary) or validation_rules.json (fallback).
"""

import json

from langchain_core.prompts import ChatPromptTemplate

from pipeline.state import ValidationState, AgentFinding
from agents.llm_factory import create_agent_llm
from rules.loader import get_rules_for_agent

SYSTEM_PROMPT = """You are a medical web content metadata specialist for Mayo Clinic.
Evaluate the metadata quality of a Mayo Clinic web page and respond ONLY with valid JSON.

{rules_block}"""

USER_PROMPT = """Validate the metadata for this Mayo Clinic page.

URL: {url}
Title: {title}
Meta Description: {meta_description} (length: {meta_desc_length} chars)
Canonical URL: {canonical_url}
Open Graph Tags: {og_tags}
JSON-LD Structured Data types: {json_ld_types}

Respond with this exact JSON structure:
{{
  "passed": true or false,
  "score": 0.0 to 1.0,
  "passed_checks": ["list of checks that passed, e.g. 'Canonical URL present and correct'"],
  "issues": ["list of specific issues found"],
  "recommendations": ["list of specific fixes"]
}}"""


async def run_metadata_agent(state: ValidationState) -> dict:
    content = state.get("scraped_content")
    if not content:
        finding = AgentFinding(
            agent="metadata",
            passed=False,
            score=0.0,
            issues=["Content could not be scraped"],
            recommendations=["Ensure the URL is accessible and returns HTML"],
        )
        return {
            "findings": [finding],
            "agent_statuses": {"metadata": "done"},
        }

    # Load rules dynamically
    routing = state.get("routing_decision") or {}
    content_type = routing.get("content_type", "standard")
    rule_set = await get_rules_for_agent("metadata", content_type)
    rules_block = rule_set.to_prompt_block()

    # Extract JSON-LD schema types for the prompt
    json_ld_types = []
    for obj in content.get("structured_data", []):
        if isinstance(obj, dict):
            schema_type = obj.get("@type", "Unknown")
            json_ld_types.append(schema_type)

    llm = create_agent_llm("metadata", validation_id=state.get("validation_id", ""))

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
            "meta_description": content.get("meta_description", ""),
            "meta_desc_length": len(content.get("meta_description", "")),
            "canonical_url": content.get("canonical_url", "Not found"),
            "og_tags": json.dumps(content.get("og_tags", {}), indent=2),
            "json_ld_types": json_ld_types if json_ld_types else ["None found"],
        })

        result = json.loads(response.content)
        finding = AgentFinding(
            agent="metadata",
            passed=result.get("passed", False),
            score=float(result.get("score", 0.0)),
            passed_checks=result.get("passed_checks", []),
            issues=result.get("issues", []),
            recommendations=result.get("recommendations", []),
        )
    except Exception as e:
        finding = AgentFinding(
            agent="metadata",
            passed=False,
            score=0.0,
            issues=[f"Agent error: {str(e)}"],
            recommendations=["Check agent configuration and OpenAI API key"],
        )

    return {
        "findings": [finding],
        "agent_statuses": {"metadata": "done"},
    }
