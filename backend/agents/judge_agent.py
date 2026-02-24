"""
LLM-as-a-Judge Agent — meta-evaluator that reviews all agent findings and provides
a synthesized recommendation before human review.

Runs after aggregate_node, before human_gate_node. Receives all agent findings
and produces an overall assessment with:
- A recommendation (approve / reject / needs_revision)
- Confidence level
- Key concerns across all agents
- A brief rationale synthesizing the findings

This gives the human reviewer an LLM "second opinion" to speed up decision-making.
"""

import json

from langchain_core.prompts import ChatPromptTemplate

from pipeline.state import ValidationState, AgentFinding
from agents.llm_factory import create_agent_llm

SYSTEM_PROMPT = """You are a senior content quality judge for Mayo Clinic's digital publishing pipeline.
You have received the outputs of multiple specialized validation agents that each checked
a different aspect of a Mayo Clinic web page. Your job is to synthesize their findings
into a single, actionable recommendation for the human reviewer.

You must respond ONLY with valid JSON.

Your recommendation must be one of:
- "approve": Content meets quality standards, safe to publish
- "reject": Significant issues that must be fixed before publishing
- "needs_revision": Minor issues that should be addressed but aren't blockers

Confidence levels:
- "high": Clear-cut decision based on agent findings (all pass or clear failures)
- "medium": Mixed signals across agents, some ambiguity
- "low": Agent findings are contradictory or insufficient to judge

Be concise but specific. The human reviewer is busy — highlight what matters most."""

USER_PROMPT = """Review the following agent findings for a Mayo Clinic page and provide your recommendation.

URL: {url}
Content Type: {content_type}
Overall Score: {overall_score}
All Agents Passed: {overall_passed}

=== AGENT FINDINGS ===
{findings_text}

=== SKIPPED AGENTS ===
{skipped_agents}

Synthesize the findings above and respond with this exact JSON structure:
{{
  "recommendation": "approve" | "reject" | "needs_revision",
  "confidence": "high" | "medium" | "low",
  "key_concerns": ["list of the most important issues across all agents"],
  "strengths": ["list of notable strengths across all agents"],
  "rationale": "2-3 sentence summary explaining your recommendation"
}}"""


def _format_findings(findings: list) -> str:
    """Format agent findings into a readable text block for the judge."""
    parts = []
    for f in findings:
        if isinstance(f, AgentFinding):
            d = f.model_dump()
        elif isinstance(f, dict):
            d = f
        else:
            continue

        parts.append(
            f"--- {d.get('agent', 'unknown').upper()} AGENT ---\n"
            f"Passed: {d.get('passed')}\n"
            f"Score: {d.get('score')}\n"
            f"Passed Checks: {', '.join(d.get('passed_checks', []))}\n"
            f"Issues: {', '.join(d.get('issues', []))}\n"
            f"Recommendations: {', '.join(d.get('recommendations', []))}"
        )
    return "\n\n".join(parts) if parts else "No findings available."


async def run_judge_agent(state: ValidationState) -> dict:
    """
    LLM-as-a-Judge: synthesizes all agent findings into a recommendation.
    Runs after aggregate, before human_gate.
    """
    findings = state.get("findings", [])
    routing = state.get("routing_decision", {}) or {}

    if not findings:
        return {
            "judge_recommendation": {
                "recommendation": "reject",
                "confidence": "low",
                "key_concerns": ["No agent findings available to evaluate"],
                "strengths": [],
                "rationale": "Cannot make a recommendation without agent findings.",
            },
            "status": "awaiting_human",
        }

    llm = create_agent_llm("judge", validation_id=state.get("validation_id", ""), model="gpt-4o-mini")

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT),
    ])

    chain = prompt | llm

    try:
        response = await chain.ainvoke({
            "url": state.get("url", ""),
            "content_type": routing.get("content_type", "unknown"),
            "overall_score": state.get("overall_score", 0.0),
            "overall_passed": state.get("overall_passed", False),
            "findings_text": _format_findings(findings),
            "skipped_agents": ", ".join(state.get("skipped_agents", [])) or "None",
        })

        result = json.loads(response.content)
        return {
            "judge_recommendation": {
                "recommendation": result.get("recommendation", "needs_revision"),
                "confidence": result.get("confidence", "low"),
                "key_concerns": result.get("key_concerns", []),
                "strengths": result.get("strengths", []),
                "rationale": result.get("rationale", ""),
            },
            "status": "awaiting_human",
        }
    except Exception as e:
        return {
            "judge_recommendation": {
                "recommendation": "needs_revision",
                "confidence": "low",
                "key_concerns": [f"Judge agent error: {str(e)}"],
                "strengths": [],
                "rationale": "Judge could not evaluate findings due to an error.",
            },
            "status": "awaiting_human",
        }
