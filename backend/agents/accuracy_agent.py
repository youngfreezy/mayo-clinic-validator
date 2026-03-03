"""
Accuracy Agent — fact-checks medical claims against the RAG knowledge base.

Uses PGVector (MMR retrieval) to fetch relevant Mayo Clinic medical facts,
then asks GPT-5.1 to compare the content claims against retrieved references.

Rules are loaded dynamically from Neo4j (primary) or validation_rules.json (fallback).
"""

import asyncio
import json

from langchain_core.prompts import ChatPromptTemplate

from pipeline.state import ValidationState, AgentFinding
from tools.rag_retriever import get_retriever
from agents.llm_factory import create_agent_llm
from rules.loader import get_rules_for_agent

SYSTEM_PROMPT = """You are a medical accuracy reviewer for Mayo Clinic.
You have been provided with verified medical reference documents from Mayo Clinic's knowledge base.
Compare the submitted content's medical claims against these references and identify inaccuracies.
Respond ONLY with valid JSON.

{rules_block}"""

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

    # Load rules dynamically
    routing = state.get("routing_decision") or {}
    content_type = routing.get("content_type", "standard")
    rule_set = await get_rules_for_agent("accuracy", content_type)
    rules_block = rule_set.to_prompt_block()

    # Build a query from title + first portion of body
    title = content.get("title", "")
    body = content.get("body_text", "")
    query = f"{title}\n{body[:1000]}"

    # Retrieve relevant references from PGVector knowledge base
    references_text = "No references available in knowledge base."
    try:
        retriever = get_retriever(k=5)
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
            "rules_block": rules_block,
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
