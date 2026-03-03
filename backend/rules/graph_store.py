"""
Neo4j graph store for validation rules.

Graph model:
  (:Agent {name, pass_threshold})
  (:ContentType {name})           — "standard", "hil", "all"
  (:Category {name})              — "required_elements", "prohibited_language", etc.
  (:Rule {id, description, severity, threshold_json})

Relationships:
  (:Rule)-[:EVALUATED_BY]->(:Agent)
  (:Rule)-[:APPLIES_TO]->(:ContentType)
  (:Rule)-[:BELONGS_TO]->(:Category)
  (:Rule)-[:DEPENDS_ON]->(:Rule)
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Any

from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import ServiceUnavailable, AuthError

from rules.schema import Rule, RuleThreshold, AgentRuleSet

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

_driver: Optional[AsyncDriver] = None


async def get_driver(uri: str, user: str, password: str) -> AsyncDriver:
    """Get or create the Neo4j async driver singleton."""
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    return _driver


async def close_driver() -> None:
    """Close the Neo4j driver on shutdown."""
    global _driver
    if _driver:
        await _driver.close()
        _driver = None


async def verify_connection(uri: str, user: str, password: str) -> bool:
    """Test if Neo4j is reachable and credentials are valid."""
    try:
        driver = await get_driver(uri, user, password)
        async with driver.session() as session:
            result = await session.run("RETURN 1 AS n")
            record = await result.single()
            return record is not None and record["n"] == 1
    except (ServiceUnavailable, AuthError, OSError) as e:
        logger.warning("Neo4j connection check failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# Seeding: push rules from JSON into Neo4j
# ---------------------------------------------------------------------------

SEED_CYPHER = """
// Idempotent seed — MERGE prevents duplicates on re-run.

// Create Agent node
MERGE (agent:Agent {name: $agent_name})
SET agent.pass_threshold = $pass_threshold

// Create or match ContentType nodes and link
WITH agent
UNWIND $content_types AS ct_name
  MERGE (ct:ContentType {name: ct_name})
  MERGE (agent)-[:VALIDATES_FOR]->(ct)

// Create rules
WITH agent
UNWIND $rules AS r
  MERGE (rule:Rule {id: r.id})
  SET rule.description   = r.description,
      rule.severity      = r.severity,
      rule.threshold_json = r.threshold_json

  // Link rule → agent
  MERGE (rule)-[:EVALUATED_BY]->(agent)

  // Link rule → category
  WITH rule, r
  MERGE (cat:Category {name: r.category})
  MERGE (rule)-[:BELONGS_TO]->(cat)

  // Link rule → content types
  WITH rule, r
  UNWIND r.applies_to AS ct_name
    MERGE (ct:ContentType {name: ct_name})
    MERGE (rule)-[:APPLIES_TO]->(ct)
"""

SEED_DEPENDENCIES_CYPHER = """
// Wire up DEPENDS_ON relationships (second pass so all rules exist first)
UNWIND $deps AS d
  MATCH (child:Rule {id: d.child_id})
  MATCH (parent:Rule {id: d.parent_id})
  MERGE (child)-[:DEPENDS_ON]->(parent)
"""

SET_VERSION_CYPHER = """
MERGE (meta:RulesMeta {key: 'version'})
SET meta.version = $version
"""


async def seed_rules(
    uri: str,
    user: str,
    password: str,
    rules_data: Dict[str, Any],
) -> Dict[str, int]:
    """
    Seed the Neo4j graph from the validation_rules.json structure.
    Returns counts of created nodes.
    """
    driver = await get_driver(uri, user, password)
    version = rules_data.get("version", "unknown")
    agents = rules_data.get("agents", {})
    all_deps: List[Dict[str, str]] = []
    stats = {"agents": 0, "rules": 0, "dependencies": 0}

    async with driver.session() as session:
        for agent_name, agent_data in agents.items():
            rule_params = []
            for rule in agent_data.get("rules", []):
                threshold_json = json.dumps(rule.get("threshold")) if rule.get("threshold") else None
                rule_params.append({
                    "id": rule["id"],
                    "description": rule["description"],
                    "severity": rule["severity"],
                    "category": rule["category"],
                    "threshold_json": threshold_json,
                    "applies_to": agent_data.get("applies_to", ["standard", "hil"]),
                })
                # Collect dependencies for second pass
                for dep_id in rule.get("depends_on", []):
                    all_deps.append({"child_id": rule["id"], "parent_id": dep_id})

            await session.run(
                SEED_CYPHER,
                agent_name=agent_name,
                pass_threshold=agent_data["pass_threshold"],
                content_types=agent_data.get("applies_to", ["standard", "hil"]),
                rules=rule_params,
            )
            stats["agents"] += 1
            stats["rules"] += len(rule_params)

        # Second pass: wire up dependencies
        if all_deps:
            await session.run(SEED_DEPENDENCIES_CYPHER, deps=all_deps)
            stats["dependencies"] = len(all_deps)

        # Set version metadata
        await session.run(SET_VERSION_CYPHER, version=version)

    logger.info(
        "Seeded Neo4j: %d agents, %d rules, %d dependencies (v%s)",
        stats["agents"], stats["rules"], stats["dependencies"], version,
    )
    return stats


# ---------------------------------------------------------------------------
# Querying: fetch rules for a specific agent + content type
# ---------------------------------------------------------------------------

QUERY_RULES_CYPHER = """
MATCH (rule:Rule)-[:EVALUATED_BY]->(agent:Agent {name: $agent_name})
WHERE (rule)-[:APPLIES_TO]->(:ContentType {name: $content_type})
   OR (rule)-[:APPLIES_TO]->(:ContentType {name: 'all'})
OPTIONAL MATCH (rule)-[:BELONGS_TO]->(cat:Category)
OPTIONAL MATCH (rule)-[:DEPENDS_ON]->(dep:Rule)
WITH rule, agent, cat,
     collect(DISTINCT dep.id) AS dep_ids
RETURN rule.id          AS id,
       rule.description AS description,
       rule.severity    AS severity,
       cat.name         AS category,
       rule.threshold_json AS threshold_json,
       dep_ids,
       agent.pass_threshold AS pass_threshold
ORDER BY
  CASE rule.severity
    WHEN 'critical' THEN 0
    WHEN 'major'    THEN 1
    WHEN 'minor'    THEN 2
    ELSE 3
  END,
  rule.id
"""

QUERY_VERSION_CYPHER = """
MATCH (meta:RulesMeta {key: 'version'})
RETURN meta.version AS version
"""

QUERY_SCORING_CYPHER = """
MATCH (agent:Agent {name: $agent_name})
RETURN agent.pass_threshold AS pass_threshold
"""


async def query_rules(
    uri: str,
    user: str,
    password: str,
    agent_name: str,
    content_type: str = "standard",
) -> Optional[AgentRuleSet]:
    """
    Query the Neo4j graph for all rules applicable to an agent + content type.
    Returns None if Neo4j is unreachable.
    """
    try:
        driver = await get_driver(uri, user, password)
    except (ServiceUnavailable, AuthError, OSError) as e:
        logger.warning("Neo4j unavailable for query: %s", e)
        return None

    try:
        async with driver.session() as session:
            # Get version
            version_result = await session.run(QUERY_VERSION_CYPHER)
            version_record = await version_result.single()
            version = version_record["version"] if version_record else "unknown"

            # Get rules
            result = await session.run(
                QUERY_RULES_CYPHER,
                agent_name=agent_name,
                content_type=content_type,
            )
            records = [record async for record in result]

            if not records:
                return None

            rules = []
            pass_threshold = 0.7
            for record in records:
                threshold = None
                if record["threshold_json"]:
                    threshold = RuleThreshold(**json.loads(record["threshold_json"]))

                dep_ids = [d for d in record["dep_ids"] if d]

                rules.append(Rule(
                    id=record["id"],
                    description=record["description"],
                    severity=record["severity"],
                    category=record["category"] or "uncategorized",
                    threshold=threshold,
                    depends_on=dep_ids,
                ))
                pass_threshold = record["pass_threshold"]

            return AgentRuleSet(
                agent_name=agent_name,
                pass_threshold=pass_threshold,
                content_type=content_type,
                rules=rules,
                rules_version=version,
                source="neo4j",
            )
    except Exception as e:
        logger.error("Neo4j query failed for %s: %s", agent_name, e)
        return None


# ---------------------------------------------------------------------------
# Graph introspection (useful for evals and debugging)
# ---------------------------------------------------------------------------

QUERY_GRAPH_STATS_CYPHER = """
MATCH (r:Rule) WITH count(r) AS rules
MATCH (a:Agent) WITH rules, count(a) AS agents
MATCH (c:Category) WITH rules, agents, count(c) AS categories
MATCH (ct:ContentType) WITH rules, agents, categories, count(ct) AS content_types
MATCH ()-[d:DEPENDS_ON]->() WITH rules, agents, categories, content_types, count(d) AS dependencies
RETURN rules, agents, categories, content_types, dependencies
"""


async def get_graph_stats(
    uri: str, user: str, password: str
) -> Optional[Dict[str, int]]:
    """Return counts of all node and relationship types in the rules graph."""
    try:
        driver = await get_driver(uri, user, password)
        async with driver.session() as session:
            result = await session.run(QUERY_GRAPH_STATS_CYPHER)
            record = await result.single()
            if record:
                return dict(record)
    except Exception as e:
        logger.warning("Could not get graph stats: %s", e)
    return None
