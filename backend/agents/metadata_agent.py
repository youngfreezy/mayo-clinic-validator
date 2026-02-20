"""
Metadata Agent — validates meta tags, JSON-LD structured data, Open Graph, canonical URL.

Checks:
- Meta description present and within 150–160 character sweet spot
- Canonical URL present and matches the submitted URL
- JSON-LD contains at least one MedicalWebPage or WebPage schema
- Open Graph og:title and og:description present
- og:type set to "website" or "article"
"""

import json
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from pipeline.state import ValidationState, AgentFinding
from config.settings import settings

SYSTEM_PROMPT = """You are a medical web content metadata specialist for Mayo Clinic.
Evaluate the metadata quality of a Mayo Clinic web page and respond ONLY with valid JSON.

IMPORTANT CONTEXT: The metadata provided was extracted from the initial server-side rendered (SSR)
HTML response — i.e. the raw HTML returned before any client-side JavaScript runs. Mayo Clinic pages
are Next.js applications; some meta tags (especially og:description and meta description) may be
populated only after client-side hydration and will therefore appear missing or empty in the SSR
snapshot. When reporting issues with missing or empty tags, note explicitly that the tag was absent
in the SSR HTML and may be injected client-side, which means search engine crawlers that rely on
the raw HTML response may also not see them.

Score criteria (0.0 to 1.0):
- 1.0: All metadata complete and optimal
- 0.8–0.9: Minor issues (slightly short/long description, missing one OG tag)
- 0.5–0.7: Moderate issues (no JSON-LD, missing canonical, poor description)
- Below 0.5: Major issues (no meta description, no structured data, broken canonical)

A page "passes" if score >= 0.7."""

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

    # Extract JSON-LD schema types for the prompt
    json_ld_types = []
    for obj in content.get("structured_data", []):
        if isinstance(obj, dict):
            schema_type = obj.get("@type", "Unknown")
            json_ld_types.append(schema_type)

    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        openai_api_key=settings.OPENAI_API_KEY,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT),
    ])

    chain = prompt | llm

    try:
        response = await chain.ainvoke({
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
