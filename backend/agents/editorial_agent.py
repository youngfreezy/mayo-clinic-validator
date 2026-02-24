"""
Editorial Agent — validates heading hierarchy, last reviewed date, attribution,
content structure, and taxonomy alignment.

Checks:
- H1 present and descriptive
- H2s used for major sections (Symptoms, Causes, Treatment, etc.)
- No heading level skips (e.g., H4 without H3 parent)
- Last reviewed date present and within 2 years
- "By Mayo Clinic Staff" or reviewer attribution present in body
- Required sections present: Overview, Symptoms, Causes (inferred from headings)
- Adequate content length (>500 words estimated)
"""

import json

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from pipeline.state import ValidationState, AgentFinding
from config.settings import settings

SYSTEM_PROMPT = """You are a senior editorial standards reviewer for Mayo Clinic's digital health content.
Evaluate editorial quality and structure of a Mayo Clinic web page. Respond ONLY with valid JSON.

Score criteria (0.0 to 1.0):
- 1.0: Excellent structure, up-to-date, proper attribution, complete sections
- 0.8–0.9: Minor issues (one missing section, slightly outdated review date)
- 0.5–0.7: Moderate issues (poor heading structure, no review date, missing attribution)
- Below 0.5: Major issues (no discernible structure, severely outdated, missing critical sections)

A page "passes" if score >= 0.7."""

USER_PROMPT = """Review the editorial quality of this Mayo Clinic page.

URL: {url}
Title: {title}
Last Reviewed Date: {last_reviewed}
Heading Structure: {headings}
Body Text (first 2000 chars): {body_preview}
Internal Link Count: {internal_link_count}
External Link Count: {external_link_count}

Check for:
1. Heading hierarchy correctness (no skipped levels, logical progression)
2. Last reviewed date (should exist and be within 2 years of 2026)
3. Attribution ("Mayo Clinic Staff" or named reviewer)
4. Required sections (symptoms, causes, diagnosis, treatment, prevention — at least 3)
5. Adequate content depth (estimated from body text length)
6. Proper taxonomy (URL and headings suggest correct medical category)

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

    headings = content.get("headings", [])
    headings_formatted = "\n".join(
        f"  {'#' * h['level']} {h['text']}" for h in headings
    )

    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        openai_api_key=settings.OPENAI_API_KEY,
        model_kwargs={"response_format": {"type": "json_object"}},
        tags=["editorial-agent", "gpt-4o"],
        metadata={"agent": "editorial", "validation_id": state.get("validation_id", "")},
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
