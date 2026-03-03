"""
Rule loader — Neo4j primary, JSON fallback.

Provides a single async function `get_rules_for_agent()` that:
  1. Tries to load rules from Neo4j (graph_store.query_rules)
  2. Falls back to loading from backend/data/validation_rules.json

The caller (each agent) doesn't need to know which store was used.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from config.settings import settings
from rules.schema import AgentRuleSet, Rule, RuleThreshold

logger = logging.getLogger(__name__)

# Cache the JSON file in memory after first load
_json_cache: Optional[dict] = None

RULES_JSON_PATH = Path(__file__).resolve().parent.parent / "data" / "validation_rules.json"


def _load_json() -> dict:
    """Load and cache the validation_rules.json file."""
    global _json_cache
    if _json_cache is None:
        with open(RULES_JSON_PATH) as f:
            _json_cache = json.load(f)
    return _json_cache


def _parse_rules_from_json(
    agent_name: str,
    content_type: str = "standard",
) -> Optional[AgentRuleSet]:
    """
    Parse rules for an agent from the JSON file.
    Filters by content_type applicability.
    """
    data = _load_json()
    agent_data = data.get("agents", {}).get(agent_name)
    if not agent_data:
        logger.warning("No rules found in JSON for agent: %s", agent_name)
        return None

    # Check if this agent applies to the requested content type
    applies_to = agent_data.get("applies_to", ["standard", "hil"])
    if content_type not in applies_to and "all" not in applies_to:
        return None

    rules = []
    for rule_data in agent_data.get("rules", []):
        threshold = None
        if rule_data.get("threshold"):
            threshold = RuleThreshold(**rule_data["threshold"])

        rules.append(Rule(
            id=rule_data["id"],
            description=rule_data["description"],
            severity=rule_data["severity"],
            category=rule_data["category"],
            threshold=threshold,
            depends_on=rule_data.get("depends_on", []),
        ))

    return AgentRuleSet(
        agent_name=agent_name,
        pass_threshold=agent_data["pass_threshold"],
        content_type=content_type,
        rules=rules,
        scoring=agent_data.get("scoring", {}),
        context=agent_data.get("context"),
        rules_version=data.get("version", "unknown"),
        source="json",
    )


async def get_rules_for_agent(
    agent_name: str,
    content_type: str = "standard",
) -> AgentRuleSet:
    """
    Load rules for an agent. Tries Neo4j first, falls back to JSON.

    Returns an AgentRuleSet with .source indicating where rules came from.
    """
    # Try Neo4j if credentials are configured
    neo4j_uri = getattr(settings, "NEO4J_URI", "")
    neo4j_user = getattr(settings, "NEO4J_USER", "")
    neo4j_password = getattr(settings, "NEO4J_PASSWORD", "")

    if neo4j_uri and neo4j_user and neo4j_password:
        try:
            from rules.graph_store import query_rules
            rule_set = await query_rules(
                uri=neo4j_uri,
                user=neo4j_user,
                password=neo4j_password,
                agent_name=agent_name,
                content_type=content_type,
            )
            if rule_set and rule_set.rules:
                logger.info(
                    "Loaded %d rules for %s from Neo4j (v%s)",
                    len(rule_set.rules), agent_name, rule_set.rules_version,
                )
                # Enrich with scoring/context from JSON (graph doesn't store these)
                json_data = _load_json()
                agent_json = json_data.get("agents", {}).get(agent_name, {})
                rule_set.scoring = agent_json.get("scoring", {})
                rule_set.context = agent_json.get("context")
                return rule_set
            else:
                logger.info("Neo4j returned no rules for %s/%s, falling back to JSON", agent_name, content_type)
        except Exception as e:
            logger.warning("Neo4j query failed for %s, falling back to JSON: %s", agent_name, e)

    # Fallback to JSON
    rule_set = _parse_rules_from_json(agent_name, content_type)
    if rule_set:
        logger.info(
            "Loaded %d rules for %s from JSON fallback (v%s)",
            len(rule_set.rules), agent_name, rule_set.rules_version,
        )
        return rule_set

    # Last resort: return an empty rule set so agents don't crash
    logger.error("No rules found for agent %s — returning empty rule set", agent_name)
    return AgentRuleSet(
        agent_name=agent_name,
        pass_threshold=0.7,
        content_type=content_type,
        rules=[],
        rules_version="none",
        source="empty",
    )


def get_rules_version() -> str:
    """Return the current rules version from the JSON file."""
    return _load_json().get("version", "unknown")
