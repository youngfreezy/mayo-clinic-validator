"""
Compliance Agent — validates regulatory, legal, and editorial policy language.

Checks:
- No prohibited absolute claims ("cures", "eliminates", "guarantees recovery")
- Required medical disclaimer language present
- No FDA-regulated off-label promotion without appropriate caveats
- No HIPAA-sensitive personal health information exposure
- No unsubstantiated superlatives ("best", "only", "revolutionary")
- Appropriate hedging language for medical advice ("consult your doctor", "may", "can")
"""

import json

from langchain_core.prompts import ChatPromptTemplate

from pipeline.state import ValidationState, AgentFinding
from agents.llm_factory import create_agent_llm

SYSTEM_PROMPT = """You are a medical content compliance specialist for Mayo Clinic.
Review health content for regulatory compliance, legal language, and editorial policy violations.
Respond ONLY with valid JSON.

Prohibited language includes:
- Absolute cure claims: "cures", "eliminates", "eradicates", "guarantees recovery/remission"
- Unsubstantiated superlatives: "the only treatment", "best medicine", "revolutionary"
- Off-label drug promotion without caveats
- Personal health information exposure
- Missing required hedging: medical content should say "may help", "can reduce", "consult a doctor"

Score criteria (0.0 to 1.0):
- 1.0: Fully compliant, proper hedging, no prohibited language
- 0.8–0.9: Minor issues (one unsubstantiated claim, missing one disclaimer)
- 0.5–0.7: Moderate issues (multiple policy violations, missing critical disclaimers)
- Below 0.5: Major violations (absolute cure claims, HIPAA concerns, significant legal risk)

A page "passes" if score >= 0.75."""

USER_PROMPT = """Review this Mayo Clinic content for compliance violations.

Title: {title}
URL: {url}
Content: {body_text}

Evaluate:
1. Prohibited absolute claim language
2. Required disclaimers (e.g., "consult your healthcare provider")
3. FDA language compliance
4. HIPAA concerns (patient-identifiable information)
5. Appropriate medical hedging throughout
6. Unsubstantiated superlatives

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

    llm = create_agent_llm("compliance", validation_id=state.get("validation_id", ""))

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT),
    ])

    chain = prompt | llm

    try:
        response = await chain.ainvoke({
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
