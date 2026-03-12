"""
MCP Server — exposes Mayo Clinic validation capabilities as composable tools.

Tools:
  scrape_url               Fetch + parse a Mayo Clinic URL
  load_rules               Load validation rules for an agent (Neo4j/JSON)
  retrieve_medical_refs    Query PGVector knowledge base for medical references
  validate_metadata        Run metadata checks (meta tags, JSON-LD, OG)
  validate_editorial       Run editorial quality checks (headings, dates, structure)
  validate_compliance      Run regulatory compliance checks (FDA, HIPAA, disclaimers)
  validate_accuracy        Run medical accuracy fact-checking against RAG references
  validate_empty_tags      Scan raw HTML for empty/self-closing content tags

Each tool wraps existing logic and returns structured JSON.
The MCP server can be used in-process (orchestrator calls tool functions directly)
or run standalone over stdio/SSE for external MCP clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from mcp.server import Server
from mcp.server.stdio import run_server
from mcp.types import Tool, TextContent

logger = logging.getLogger(__name__)

server = Server("mayo-clinic-validator")


# ---------------------------------------------------------------------------
# Tool registry — maps tool names to handler functions for in-process calls
# ---------------------------------------------------------------------------

_tool_handlers: dict[str, Any] = {}


def _register(name: str):
    """Decorator that registers a handler for both MCP and in-process use."""
    def decorator(fn):
        _tool_handlers[name] = fn
        return fn
    return decorator


async def call_tool(name: str, arguments: dict) -> str:
    """Call a tool by name (in-process). Returns JSON string result."""
    handler = _tool_handlers.get(name)
    if not handler:
        raise ValueError(f"Unknown tool: {name}")
    return await handler(arguments)


# ---------------------------------------------------------------------------
# Tool definitions for Claude API (Anthropic format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "scrape_url",
        "description": (
            "Fetch and parse a Mayo Clinic URL. Returns structured content including "
            "title, meta description, body text, headings, canonical URL, Open Graph tags, "
            "JSON-LD structured data, last reviewed date, and internal/external links."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The Mayo Clinic URL to scrape",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "load_rules",
        "description": (
            "Load validation rules for a specific agent and content type. "
            "Rules are loaded from Neo4j (primary) or JSON fallback. "
            "Returns the rule set as a formatted text block for prompt injection."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "enum": ["metadata", "editorial", "compliance", "accuracy", "empty_tag"],
                    "description": "Which validation agent's rules to load",
                },
                "content_type": {
                    "type": "string",
                    "enum": ["standard", "hil"],
                    "description": "Content type: 'standard' for most pages, 'hil' for Health Information Library pages",
                    "default": "standard",
                },
            },
            "required": ["agent_name"],
        },
    },
    {
        "name": "retrieve_medical_refs",
        "description": (
            "Query the PGVector medical knowledge base using MMR retrieval. "
            "Returns relevant medical reference chunks from Mayo Clinic's verified knowledge base. "
            "Use this before running validate_accuracy to provide reference material."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (typically the page title + first portion of body text)",
                },
                "k": {
                    "type": "integer",
                    "description": "Number of reference chunks to retrieve (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "validate_metadata",
        "description": (
            "Run metadata validation on scraped Mayo Clinic content. "
            "Checks meta description length, canonical URL, JSON-LD structured data, "
            "and Open Graph tags. Requires scraped content and rules."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The page URL"},
                "scraped_content": {
                    "type": "object",
                    "description": "The scraped content object from scrape_url",
                },
                "rules_block": {
                    "type": "string",
                    "description": "Formatted rules text from load_rules",
                },
            },
            "required": ["url", "scraped_content", "rules_block"],
        },
    },
    {
        "name": "validate_editorial",
        "description": (
            "Run editorial quality validation on scraped Mayo Clinic content. "
            "Checks heading hierarchy, last reviewed date, internal links, attribution, "
            "and content structure. Requires scraped content and rules."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The page URL"},
                "scraped_content": {
                    "type": "object",
                    "description": "The scraped content object from scrape_url",
                },
                "rules_block": {
                    "type": "string",
                    "description": "Formatted rules text from load_rules",
                },
            },
            "required": ["url", "scraped_content", "rules_block"],
        },
    },
    {
        "name": "validate_compliance",
        "description": (
            "Run regulatory compliance validation on scraped Mayo Clinic content. "
            "Checks for prohibited 'cure' language, proper disclaimers, FDA compliance, "
            "and HIPAA considerations. Requires scraped content and rules."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The page URL"},
                "scraped_content": {
                    "type": "object",
                    "description": "The scraped content object from scrape_url",
                },
                "rules_block": {
                    "type": "string",
                    "description": "Formatted rules text from load_rules",
                },
            },
            "required": ["url", "scraped_content", "rules_block"],
        },
    },
    {
        "name": "validate_accuracy",
        "description": (
            "Run medical accuracy fact-checking on scraped Mayo Clinic content. "
            "Compares content claims against provided medical references from the knowledge base. "
            "Requires scraped content, rules, and reference material from retrieve_medical_refs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The page URL"},
                "scraped_content": {
                    "type": "object",
                    "description": "The scraped content object from scrape_url",
                },
                "rules_block": {
                    "type": "string",
                    "description": "Formatted rules text from load_rules",
                },
                "references": {
                    "type": "string",
                    "description": "Formatted reference text from retrieve_medical_refs",
                },
            },
            "required": ["url", "scraped_content", "rules_block", "references"],
        },
    },
    {
        "name": "validate_empty_tags",
        "description": (
            "Scan raw HTML for self-closing or empty tags that should have content "
            "(e.g., <title/>, <h1></h1>). This is a deterministic check (no LLM call). "
            "Primarily relevant for HIL (Health Information Library) pages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "raw_html": {
                    "type": "string",
                    "description": "The raw HTML of the page to scan",
                },
            },
            "required": ["raw_html"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

@_register("scrape_url")
async def _handle_scrape_url(args: dict) -> str:
    from tools.web_scraper import scrape_mayo_url

    url = args["url"]
    result = await scrape_mayo_url(url)
    # Don't return raw_html in the result (too large for agent context)
    safe_result = {k: v for k, v in result.items() if k != "raw_html"}
    safe_result["has_raw_html"] = bool(result.get("raw_html"))
    safe_result["raw_html_length"] = len(result.get("raw_html", ""))
    return json.dumps(safe_result, default=str)


@_register("load_rules")
async def _handle_load_rules(args: dict) -> str:
    from rules.loader import get_rules_for_agent

    agent_name = args["agent_name"]
    content_type = args.get("content_type", "standard")
    rule_set = await get_rules_for_agent(agent_name, content_type)
    return json.dumps({
        "agent_name": rule_set.agent_name,
        "content_type": rule_set.content_type,
        "rules_count": len(rule_set.rules),
        "pass_threshold": rule_set.pass_threshold,
        "rules_version": rule_set.rules_version,
        "source": rule_set.source,
        "rules_block": rule_set.to_prompt_block(),
    })


@_register("retrieve_medical_refs")
async def _handle_retrieve_refs(args: dict) -> str:
    from tools.rag_retriever import get_retriever

    query = args["query"]
    k = args.get("k", 5)

    try:
        retriever = get_retriever(k=k)
        docs = await asyncio.to_thread(retriever.invoke, query)
        chunks = []
        for i, doc in enumerate(docs):
            chunks.append({
                "index": i + 1,
                "content": doc.page_content,
                "metadata": doc.metadata,
            })
        references_text = "\n\n---\n\n".join(
            f"[Ref {c['index']}] {c['content']}" for c in chunks
        )
        return json.dumps({
            "references_count": len(chunks),
            "references_text": references_text,
            "chunks": chunks,
        })
    except Exception as e:
        return json.dumps({
            "references_count": 0,
            "references_text": f"Knowledge base unavailable: {str(e)}",
            "chunks": [],
            "error": str(e),
        })


@_register("validate_metadata")
async def _handle_validate_metadata(args: dict) -> str:
    from agents.llm_factory import create_agent_llm
    from langchain_core.prompts import ChatPromptTemplate

    content = args["scraped_content"]
    rules_block = args["rules_block"]
    url = args["url"]

    json_ld_types = []
    for obj in content.get("structured_data", []):
        if isinstance(obj, dict):
            json_ld_types.append(obj.get("@type", "Unknown"))

    llm = create_agent_llm("metadata")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a medical web content metadata specialist for Mayo Clinic.\n"
                   "Evaluate the metadata quality of a Mayo Clinic web page and respond ONLY with valid JSON.\n\n"
                   "{rules_block}"),
        ("human", "Validate the metadata for this Mayo Clinic page.\n\n"
                  "URL: {url}\nTitle: {title}\nMeta Description: {meta_description} (length: {meta_desc_length} chars)\n"
                  "Canonical URL: {canonical_url}\nOpen Graph Tags: {og_tags}\n"
                  "JSON-LD Structured Data types: {json_ld_types}\n\n"
                  "Respond with this exact JSON structure:\n"
                  '{{"passed": true or false, "score": 0.0 to 1.0, '
                  '"passed_checks": ["list of checks that passed"], '
                  '"issues": ["list of specific issues found"], '
                  '"recommendations": ["list of specific fixes"]}}'),
    ])
    chain = prompt | llm

    try:
        response = await chain.ainvoke({
            "rules_block": rules_block,
            "url": url,
            "title": content.get("title", ""),
            "meta_description": content.get("meta_description", ""),
            "meta_desc_length": len(content.get("meta_description", "")),
            "canonical_url": content.get("canonical_url", "Not found"),
            "og_tags": json.dumps(content.get("og_tags", {}), indent=2),
            "json_ld_types": json_ld_types if json_ld_types else ["None found"],
        })
        result = json.loads(response.content)
        result["agent"] = "metadata"
        return json.dumps(result)
    except Exception as e:
        return json.dumps({
            "agent": "metadata",
            "passed": False,
            "score": 0.0,
            "issues": [f"Agent error: {str(e)}"],
            "recommendations": ["Check agent configuration and OpenAI API key"],
        })


@_register("validate_editorial")
async def _handle_validate_editorial(args: dict) -> str:
    from agents.llm_factory import create_agent_llm
    from langchain_core.prompts import ChatPromptTemplate

    content = args["scraped_content"]
    rules_block = args["rules_block"]
    url = args["url"]

    headings = content.get("headings", [])
    headings_formatted = "\n".join(
        f"  {'#' * h['level']} {h['text']}" for h in headings
    )

    llm = create_agent_llm("editorial")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a senior editorial standards reviewer for Mayo Clinic's digital health content.\n"
                   "Evaluate editorial quality and structure of a Mayo Clinic web page. Respond ONLY with valid JSON.\n\n"
                   "{rules_block}"),
        ("human", "Review the editorial quality of this Mayo Clinic page.\n\n"
                  "URL: {url}\nTitle: {title}\nLast Reviewed Date: {last_reviewed}\n"
                  "Heading Structure: {headings}\n"
                  "Body Text (first 2000 chars): {body_preview}\n"
                  "Internal Link Count: {internal_link_count}\nExternal Link Count: {external_link_count}\n\n"
                  "Respond with this exact JSON structure:\n"
                  '{{"passed": true or false, "score": 0.0 to 1.0, '
                  '"passed_checks": ["list of checks that passed"], '
                  '"issues": ["list of specific issues found"], '
                  '"recommendations": ["list of specific fixes"]}}'),
    ])
    chain = prompt | llm

    try:
        response = await chain.ainvoke({
            "rules_block": rules_block,
            "url": url,
            "title": content.get("title", ""),
            "last_reviewed": content.get("last_reviewed") or "Not found",
            "headings": headings_formatted or "No headings detected",
            "body_preview": content.get("body_text", "")[:2000],
            "internal_link_count": len(content.get("internal_links", [])),
            "external_link_count": len(content.get("external_links", [])),
        })
        result = json.loads(response.content)
        result["agent"] = "editorial"
        return json.dumps(result)
    except Exception as e:
        return json.dumps({
            "agent": "editorial",
            "passed": False,
            "score": 0.0,
            "issues": [f"Agent error: {str(e)}"],
            "recommendations": ["Check agent configuration and OpenAI API key"],
        })


@_register("validate_compliance")
async def _handle_validate_compliance(args: dict) -> str:
    from agents.llm_factory import create_agent_llm
    from langchain_core.prompts import ChatPromptTemplate

    content = args["scraped_content"]
    rules_block = args["rules_block"]
    url = args["url"]

    llm = create_agent_llm("compliance")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a medical content compliance specialist for Mayo Clinic.\n"
                   "Review health content for regulatory compliance, legal language, and editorial policy violations.\n"
                   "Respond ONLY with valid JSON.\n\n{rules_block}"),
        ("human", "Review this Mayo Clinic content for compliance violations.\n\n"
                  "Title: {title}\nURL: {url}\nContent: {body_text}\n\n"
                  "Respond with this exact JSON structure:\n"
                  '{{"passed": true or false, "score": 0.0 to 1.0, '
                  '"passed_checks": ["list of compliance checks that passed"], '
                  '"issues": ["list of specific compliance violations"], '
                  '"recommendations": ["list of specific language changes needed"]}}'),
    ])
    chain = prompt | llm

    try:
        response = await chain.ainvoke({
            "rules_block": rules_block,
            "title": content.get("title", ""),
            "url": url,
            "body_text": content.get("body_text", "")[:5000],
        })
        result = json.loads(response.content)
        result["agent"] = "compliance"
        return json.dumps(result)
    except Exception as e:
        return json.dumps({
            "agent": "compliance",
            "passed": False,
            "score": 0.0,
            "issues": [f"Agent error: {str(e)}"],
            "recommendations": ["Check agent configuration and OpenAI API key"],
        })


@_register("validate_accuracy")
async def _handle_validate_accuracy(args: dict) -> str:
    from agents.llm_factory import create_agent_llm
    from langchain_core.prompts import ChatPromptTemplate

    content = args["scraped_content"]
    rules_block = args["rules_block"]
    url = args["url"]
    references = args.get("references", "No references available.")

    llm = create_agent_llm("accuracy")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a medical accuracy reviewer for Mayo Clinic.\n"
                   "Compare submitted content's medical claims against verified references.\n"
                   "Respond ONLY with valid JSON.\n\n{rules_block}"),
        ("human", "Fact-check this Mayo Clinic content against the provided medical references.\n\n"
                  "=== CONTENT TO REVIEW ===\n"
                  "Title: {title}\nURL: {url}\nBody: {body_text}\n\n"
                  "=== VERIFIED MEDICAL REFERENCES ===\n{references}\n\n"
                  "Respond with this exact JSON structure:\n"
                  '{{"passed": true or false, "score": 0.0 to 1.0, '
                  '"passed_checks": ["list of claims verified as accurate"], '
                  '"issues": ["list of factual inaccuracies or unsupported claims"], '
                  '"recommendations": ["list of corrections needed"]}}'),
    ])
    chain = prompt | llm

    try:
        response = await chain.ainvoke({
            "rules_block": rules_block,
            "title": content.get("title", ""),
            "url": url,
            "body_text": content.get("body_text", "")[:4000],
            "references": references,
        })
        result = json.loads(response.content)
        result["agent"] = "accuracy"
        return json.dumps(result)
    except Exception as e:
        return json.dumps({
            "agent": "accuracy",
            "passed": False,
            "score": 0.0,
            "issues": [f"Agent error: {str(e)}"],
            "recommendations": ["Check agent configuration and OpenAI API key"],
        })


@_register("validate_empty_tags")
async def _handle_validate_empty_tags(args: dict) -> str:
    """Deterministic HTML scan — no LLM call."""
    raw_html = args["raw_html"]

    CONTENT_TAGS = ["title", "h1", "h2", "h3", "h4", "p", "a", "li", "td", "th", "label", "button"]
    SELF_CLOSING_RE = re.compile(
        r"<(" + "|".join(CONTENT_TAGS) + r")(\s[^>]*)?\s*/>",
        re.IGNORECASE,
    )
    EMPTY_TAG_RE = re.compile(
        r"<(" + "|".join(CONTENT_TAGS) + r")(\s[^>]*)?>\s*</\1>",
        re.IGNORECASE,
    )

    issues = []
    lines = raw_html.split("\n")
    for line_num, line in enumerate(lines, start=1):
        for match in SELF_CLOSING_RE.finditer(line):
            tag = match.group(1).lower()
            issues.append(f"Self-closing <{tag}/> at line {line_num}")
        for match in EMPTY_TAG_RE.finditer(line):
            tag = match.group(1).lower()
            issues.append(f"Empty <{tag}></{tag}> at line {line_num}")

    deduction = 0.05
    score = max(0.0, round(1.0 - len(issues) * deduction, 2))

    return json.dumps({
        "agent": "empty_tag",
        "passed": score >= 0.8,
        "score": score,
        "passed_checks": ["No self-closing or empty content tags found"] if not issues else [],
        "issues": issues,
        "recommendations": [
            f"Fix {len(issues)} empty/self-closing tag(s)"
        ] if issues else [],
    })


# ---------------------------------------------------------------------------
# MCP server list_tools + call_tool handlers (for external MCP clients)
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return all available tools for MCP clients."""
    return [
        Tool(
            name=t["name"],
            description=t["description"],
            inputSchema=t["input_schema"],
        )
        for t in TOOL_DEFINITIONS
    ]


@server.call_tool()
async def mcp_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle MCP tool calls from external clients."""
    result = await call_tool(name, arguments)
    return [TextContent(type="text", text=result)]


# ---------------------------------------------------------------------------
# Standalone entry point (for external MCP clients via stdio)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    asyncio.run(run_server(server))
