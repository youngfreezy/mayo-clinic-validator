"""
Accuracy Agent — fact-checks medical claims against the RAG knowledge base.

Uses PGVector (MMR retrieval) to fetch relevant Mayo Clinic medical facts,
then asks GPT-5.1 to compare the content claims against retrieved references.

This is a single LLM call with retrieved context (rather than full ReAct loop)
to keep it deterministic and avoid infinite tool loops inside a Send branch.
"""

import asyncio
import json

from langchain_core.prompts import ChatPromptTemplate

from pipeline.state import ValidationState, AgentFinding
from tools.rag_retriever import get_retriever
from agents.llm_factory import create_agent_llm

SYSTEM_PROMPT = """You are a medical accuracy reviewer for Mayo Clinic.
You have been provided with verified medical reference documents from Mayo Clinic's knowledge base.
Compare the submitted content's medical claims against these references and identify inaccuracies.
Respond ONLY with valid JSON.

Score criteria (0.0 to 1.0):
- 1.0: All verifiable claims align with reference material
- 0.8–0.9: Minor discrepancies (outdated statistics, imprecise terminology)
- 0.5–0.7: Moderate inaccuracies (wrong dosage ranges, incorrect symptom attribution)
- Below 0.5: Significant factual errors or contradictions with reference material

A page "passes" if score >= 0.75.
If no relevant references are found, score 0.7 and note the limitation."""

USER_PROMPT = """Fact-check this Mayo Clinic content against the provided medical references.

=== CONTENT TO REVIEW ===
Title: {title}
URL: {url}
Body: {body_text}

=== VERIFIED MEDICAL REFERENCES ===
{references}

Compare the content's key medical claims against the references above.
Identify any factual inaccuracies, outdated information, or unsupported claims.

Respond with this exact JSON structure:
{{
  "passed": true or false,
  "score": 0.0 to 1.0,
  "passed_checks": ["list of claims verified as accurate against references, e.g. 'Insulin deficiency as cause of Type 1 diabetes confirmed'"],
  "issues": ["list of specific factual inaccuracies or unsupported claims"],
  "recommendations": ["list of specific corrections or additions needed"]
}}"""


async def run_accuracy_agent(state: ValidationState) -> dict:
    content = state.get("scraped_content")
    if not content:
        finding = AgentFinding(
            agent="accuracy",
            passed=False,
            score=0.0,
            issues=["Content could not be scraped"],
            recommendations=["Ensure the URL is accessible and returns HTML"],
        )
        return {
            "findings": [finding],
            "agent_statuses": {"accuracy": "done"},
        }

    if not content.get("body_text"):
        finding = AgentFinding(
            agent="accuracy",
            passed=False,
            score=0.0,
            issues=["No body text available for accuracy review"],
            recommendations=["Ensure the page has extractable text content"],
        )
        return {"findings": [finding], "agent_statuses": {"accuracy": "done"}}

    # Build a query from title + first portion of body
    title = content.get("title", "")
    body = content.get("body_text", "")
    query = f"{title}\n{body[:1000]}"

    # Retrieve relevant references from PGVector knowledge base
    references_text = "No references available in knowledge base."
    try:
        retriever = get_retriever(k=5)
        # PGVector was initialized with a sync connection string, so run
        # the sync retriever in a thread pool to avoid blocking the event loop.
        docs = await asyncio.to_thread(retriever.invoke, query)
        if docs:
            references_text = "\n\n---\n\n".join(
                f"[Ref {i+1}] {doc.page_content}" for i, doc in enumerate(docs)
            )
    except Exception as e:
        references_text = f"Knowledge base unavailable: {str(e)}"

    llm = create_agent_llm("accuracy", validation_id=state.get("validation_id", ""))

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT),
    ])

    chain = prompt | llm

    try:
        response = await chain.ainvoke({
            "title": title,
            "url": state["url"],
            "body_text": body[:4000],
            "references": references_text,
        })

        result = json.loads(response.content)
        finding = AgentFinding(
            agent="accuracy",
            passed=result.get("passed", False),
            score=float(result.get("score", 0.0)),
            passed_checks=result.get("passed_checks", []),
            issues=result.get("issues", []),
            recommendations=result.get("recommendations", []),
        )
    except Exception as e:
        finding = AgentFinding(
            agent="accuracy",
            passed=False,
            score=0.0,
            issues=[f"Agent error: {str(e)}"],
            recommendations=["Check agent configuration and OpenAI API key"],
        )

    return {
        "findings": [finding],
        "agent_statuses": {"accuracy": "done"},
    }
