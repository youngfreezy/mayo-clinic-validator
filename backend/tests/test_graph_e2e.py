"""
End-to-end tests for the Neo4j graph-based rules system.

Tests the full flow:
- Neo4j connection and authentication
- Graph seeding (idempotent)
- Rule querying by agent + content type
- Fallback from Neo4j to JSON
- Graph-to-JSON parity (both sources produce equivalent rules)
- Prompt block generation from graph-sourced rules
- Graph introspection and stats

Requires NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in .env to run.
Tests are skipped if Neo4j credentials are not configured.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict

import pytest

from config.settings import settings
from rules.schema import AgentRuleSet, Rule, RuleThreshold
from rules.loader import (
    _load_json,
    _parse_rules_from_json,
    get_rules_for_agent,
    get_rules_version,
)

# Reset the Neo4j driver singleton between tests to avoid event loop issues
@pytest.fixture(autouse=True)
def reset_neo4j_driver():
    """Clear the cached Neo4j driver between tests so each test gets a fresh connection."""
    yield
    try:
        import rules.graph_store as gs
        gs._driver = None
    except Exception:
        pass

RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "validation_rules.json"

# Skip all tests if Neo4j is not configured
neo4j_configured = bool(
    getattr(settings, "NEO4J_URI", "")
    and getattr(settings, "NEO4J_USER", "")
    and getattr(settings, "NEO4J_PASSWORD", "")
)

skip_no_neo4j = pytest.mark.skipif(
    not neo4j_configured,
    reason="Neo4j credentials not configured (NEO4J_URI/USER/PASSWORD missing from .env)",
)


def get_neo4j_creds() -> Dict[str, str]:
    return {
        "uri": settings.NEO4J_URI,
        "user": settings.NEO4J_USER,
        "password": settings.NEO4J_PASSWORD,
    }


# ---------------------------------------------------------------------------
# E2E 1: Neo4j Connection
# ---------------------------------------------------------------------------

class TestNeo4jConnection:
    """Verify connectivity to Neo4j Aura."""

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_neo4j_connection(self):
        """Can we connect to Neo4j and run a trivial query?"""
        from rules.graph_store import verify_connection
        creds = get_neo4j_creds()
        result = await verify_connection(**creds)
        assert result is True, "Failed to connect to Neo4j — check credentials"

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_neo4j_returns_data(self):
        """Does the seeded graph contain data?"""
        from rules.graph_store import get_graph_stats
        creds = get_neo4j_creds()
        stats = await get_graph_stats(**creds)
        assert stats is not None, "get_graph_stats returned None"
        assert stats["rules"] >= 30, f"Expected ≥30 rules, got {stats['rules']}"
        assert stats["agents"] == 5, f"Expected 5 agents, got {stats['agents']}"


# ---------------------------------------------------------------------------
# E2E 2: Graph Seeding Idempotency
# ---------------------------------------------------------------------------

class TestGraphSeeding:
    """Verify that seeding is idempotent and produces correct counts."""

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_seed_is_idempotent(self):
        """Running seed twice should not create duplicates."""
        from rules.graph_store import seed_rules, get_graph_stats
        creds = get_neo4j_creds()

        with open(RULES_PATH) as f:
            rules_data = json.load(f)

        # Seed once
        stats1 = await seed_rules(**creds, rules_data=rules_data)

        # Get graph counts after first seed
        graph1 = await get_graph_stats(**creds)

        # Seed again
        stats2 = await seed_rules(**creds, rules_data=rules_data)

        # Get graph counts after second seed
        graph2 = await get_graph_stats(**creds)

        # Counts should be identical (MERGE prevents duplicates)
        assert graph1["rules"] == graph2["rules"], "Duplicate rules created on re-seed"
        assert graph1["agents"] == graph2["agents"], "Duplicate agents created on re-seed"
        assert graph1["dependencies"] == graph2["dependencies"], "Duplicate deps created"


# ---------------------------------------------------------------------------
# E2E 3: Rule Querying per Agent
# ---------------------------------------------------------------------------

class TestGraphRuleQuerying:
    """Verify rules can be queried from Neo4j for each agent."""

    @skip_no_neo4j
    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_name", ["metadata", "editorial", "compliance", "accuracy"])
    async def test_query_standard_agents(self, agent_name: str):
        """Each standard agent should return rules from Neo4j."""
        from rules.graph_store import query_rules
        creds = get_neo4j_creds()
        rule_set = await query_rules(**creds, agent_name=agent_name, content_type="standard")
        assert rule_set is not None, f"No rules returned for {agent_name}"
        assert rule_set.source == "neo4j"
        assert len(rule_set.rules) > 0, f"{agent_name} has no rules"
        assert rule_set.pass_threshold > 0

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_query_empty_tag_hil(self):
        """empty_tag agent should return rules for HIL content type."""
        from rules.graph_store import query_rules
        creds = get_neo4j_creds()
        rule_set = await query_rules(**creds, agent_name="empty_tag", content_type="hil")
        assert rule_set is not None, "No rules returned for empty_tag/hil"
        assert rule_set.source == "neo4j"
        assert len(rule_set.rules) >= 2

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_query_empty_tag_standard_returns_none(self):
        """empty_tag should NOT return rules for standard content (HIL only)."""
        from rules.graph_store import query_rules
        creds = get_neo4j_creds()
        rule_set = await query_rules(**creds, agent_name="empty_tag", content_type="standard")
        assert rule_set is None, "empty_tag should not have standard rules"

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_query_nonexistent_agent(self):
        """Querying a non-existent agent should return None."""
        from rules.graph_store import query_rules
        creds = get_neo4j_creds()
        rule_set = await query_rules(**creds, agent_name="nonexistent_agent", content_type="standard")
        assert rule_set is None

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_rules_have_required_fields(self):
        """Every rule from Neo4j should have id, description, severity, category."""
        from rules.graph_store import query_rules
        creds = get_neo4j_creds()
        rule_set = await query_rules(**creds, agent_name="compliance", content_type="standard")
        assert rule_set is not None
        for rule in rule_set.rules:
            assert rule.id, "Rule missing id"
            assert rule.description, "Rule missing description"
            assert rule.severity in {"critical", "major", "minor", "info"}, f"Invalid severity: {rule.severity}"
            assert rule.category, "Rule missing category"

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_rules_ordered_by_severity(self):
        """Rules should be returned ordered critical → major → minor → info."""
        from rules.graph_store import query_rules
        creds = get_neo4j_creds()
        rule_set = await query_rules(**creds, agent_name="compliance", content_type="standard")
        assert rule_set is not None

        severity_rank = {"critical": 0, "major": 1, "minor": 2, "info": 3}
        ranks = [severity_rank[r.severity] for r in rule_set.rules]
        assert ranks == sorted(ranks), f"Rules not sorted by severity: {[r.severity for r in rule_set.rules]}"


# ---------------------------------------------------------------------------
# E2E 4: Graph ↔ JSON Parity
# ---------------------------------------------------------------------------

class TestGraphJsonParity:
    """Verify that Neo4j and JSON produce equivalent rule sets."""

    @skip_no_neo4j
    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_name,content_type", [
        ("metadata", "standard"),
        ("editorial", "standard"),
        ("compliance", "standard"),
        ("accuracy", "standard"),
        ("empty_tag", "hil"),
    ])
    async def test_same_rule_ids(self, agent_name: str, content_type: str):
        """Neo4j and JSON should contain the same rule IDs for each agent."""
        from rules.graph_store import query_rules
        creds = get_neo4j_creds()

        graph_rules = await query_rules(**creds, agent_name=agent_name, content_type=content_type)
        json_rules = _parse_rules_from_json(agent_name, content_type)

        assert graph_rules is not None, f"Neo4j returned None for {agent_name}"
        assert json_rules is not None, f"JSON returned None for {agent_name}"

        graph_ids = {r.id for r in graph_rules.rules}
        json_ids = {r.id for r in json_rules.rules}

        assert graph_ids == json_ids, (
            f"Rule ID mismatch for {agent_name}:\n"
            f"  Only in Neo4j: {graph_ids - json_ids}\n"
            f"  Only in JSON:  {json_ids - graph_ids}"
        )

    @skip_no_neo4j
    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_name,content_type", [
        ("metadata", "standard"),
        ("editorial", "standard"),
        ("compliance", "standard"),
        ("accuracy", "standard"),
        ("empty_tag", "hil"),
    ])
    async def test_same_rule_count(self, agent_name: str, content_type: str):
        """Neo4j and JSON should have the same number of rules per agent."""
        from rules.graph_store import query_rules
        creds = get_neo4j_creds()

        graph_rules = await query_rules(**creds, agent_name=agent_name, content_type=content_type)
        json_rules = _parse_rules_from_json(agent_name, content_type)

        assert graph_rules is not None
        assert json_rules is not None
        assert len(graph_rules.rules) == len(json_rules.rules), (
            f"{agent_name}: Neo4j has {len(graph_rules.rules)} rules, JSON has {len(json_rules.rules)}"
        )

    @skip_no_neo4j
    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_name,content_type", [
        ("metadata", "standard"),
        ("compliance", "standard"),
        ("accuracy", "standard"),
    ])
    async def test_same_descriptions(self, agent_name: str, content_type: str):
        """Rule descriptions should match between Neo4j and JSON."""
        from rules.graph_store import query_rules
        creds = get_neo4j_creds()

        graph_rules = await query_rules(**creds, agent_name=agent_name, content_type=content_type)
        json_rules = _parse_rules_from_json(agent_name, content_type)

        graph_descs = {r.id: r.description for r in graph_rules.rules}
        json_descs = {r.id: r.description for r in json_rules.rules}

        for rule_id, graph_desc in graph_descs.items():
            assert rule_id in json_descs, f"Rule {rule_id} missing from JSON"
            assert graph_desc == json_descs[rule_id], (
                f"Description mismatch for {rule_id}:\n"
                f"  Neo4j: {graph_desc}\n"
                f"  JSON:  {json_descs[rule_id]}"
            )

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_same_pass_thresholds(self):
        """Pass thresholds should match between Neo4j and JSON."""
        from rules.graph_store import query_rules
        creds = get_neo4j_creds()

        for agent_name in ["metadata", "editorial", "compliance", "accuracy"]:
            graph_rules = await query_rules(**creds, agent_name=agent_name, content_type="standard")
            json_rules = _parse_rules_from_json(agent_name, "standard")
            assert graph_rules.pass_threshold == json_rules.pass_threshold, (
                f"{agent_name}: threshold mismatch — Neo4j={graph_rules.pass_threshold}, JSON={json_rules.pass_threshold}"
            )


# ---------------------------------------------------------------------------
# E2E 5: Loader Integration (get_rules_for_agent uses Neo4j first)
# ---------------------------------------------------------------------------

class TestLoaderIntegration:
    """Verify the loader correctly uses Neo4j as primary source."""

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_loader_uses_neo4j_when_available(self):
        """get_rules_for_agent should return source='neo4j' when Neo4j is configured."""
        rule_set = await get_rules_for_agent("metadata", "standard")
        assert rule_set.source == "neo4j", f"Expected source='neo4j', got '{rule_set.source}'"

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_loader_enriches_with_scoring(self):
        """Rules from Neo4j should be enriched with scoring criteria from JSON."""
        rule_set = await get_rules_for_agent("compliance", "standard")
        assert rule_set.source == "neo4j"
        # Scoring comes from JSON enrichment
        assert rule_set.scoring is not None
        assert len(rule_set.scoring) > 0, "Scoring criteria missing from Neo4j-sourced rules"

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_loader_all_agents(self):
        """All 5 agents should successfully load rules."""
        agents = [
            ("metadata", "standard"),
            ("editorial", "standard"),
            ("compliance", "standard"),
            ("accuracy", "standard"),
            ("empty_tag", "hil"),
        ]
        for agent_name, content_type in agents:
            rule_set = await get_rules_for_agent(agent_name, content_type)
            assert rule_set is not None, f"No rules for {agent_name}"
            assert len(rule_set.rules) > 0, f"{agent_name} has no rules"


# ---------------------------------------------------------------------------
# E2E 6: Prompt Block Generation from Graph
# ---------------------------------------------------------------------------

class TestPromptBlockFromGraph:
    """Verify prompt blocks generated from Neo4j-sourced rules are well-formed."""

    @skip_no_neo4j
    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_name", ["metadata", "editorial", "compliance", "accuracy", "empty_tag"])
    async def test_prompt_block_well_formed(self, agent_name: str):
        """Prompt blocks from Neo4j should contain all required sections."""
        content_type = "hil" if agent_name == "empty_tag" else "standard"
        rule_set = await get_rules_for_agent(agent_name, content_type)
        assert rule_set.source == "neo4j"

        block = rule_set.to_prompt_block()
        assert "VALIDATION RULES:" in block
        assert "SCORING CRITERIA:" in block
        assert "PASSES" in block

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_prompt_block_contains_all_rule_descriptions(self):
        """Every rule description should appear in the generated prompt block."""
        rule_set = await get_rules_for_agent("compliance", "standard")
        block = rule_set.to_prompt_block()
        for rule in rule_set.rules:
            assert rule.description in block, (
                f"Rule {rule.id} description missing from prompt block"
            )

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_prompt_block_severity_tags(self):
        """Prompt block should include severity tags like [CRITICAL], [MAJOR]."""
        rule_set = await get_rules_for_agent("compliance", "standard")
        block = rule_set.to_prompt_block()
        assert "[CRITICAL]" in block, "Missing [CRITICAL] tag"
        assert "[MAJOR]" in block or "[MINOR]" in block, "Missing severity tags"

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_prompt_blocks_under_size_limit(self):
        """Each prompt block should be under 8000 chars."""
        for agent_name in ["metadata", "editorial", "compliance", "accuracy"]:
            rule_set = await get_rules_for_agent(agent_name, "standard")
            block = rule_set.to_prompt_block()
            assert len(block) < 8000, (
                f"{agent_name} prompt block is {len(block)} chars — too large"
            )


# ---------------------------------------------------------------------------
# E2E 7: Dependency Integrity in Graph
# ---------------------------------------------------------------------------

class TestGraphDependencies:
    """Verify dependency relationships are correctly stored in Neo4j."""

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_dependencies_exist(self):
        """Graph should have dependency relationships."""
        from rules.graph_store import get_graph_stats
        creds = get_neo4j_creds()
        stats = await get_graph_stats(**creds)
        assert stats["dependencies"] >= 3, f"Expected ≥3 dependencies, got {stats['dependencies']}"

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_dependency_ids_are_valid(self):
        """All depends_on IDs should reference existing rules."""
        from rules.graph_store import query_rules
        creds = get_neo4j_creds()

        all_rule_ids = set()
        all_deps = []

        for agent_name in ["metadata", "editorial", "compliance", "accuracy"]:
            rule_set = await query_rules(**creds, agent_name=agent_name, content_type="standard")
            if rule_set:
                for rule in rule_set.rules:
                    all_rule_ids.add(rule.id)
                    for dep_id in rule.depends_on:
                        all_deps.append((rule.id, dep_id))

        for child_id, parent_id in all_deps:
            assert parent_id in all_rule_ids, (
                f"Rule {child_id} depends on {parent_id} which doesn't exist"
            )

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_dependencies_match_json(self):
        """Dependencies in Neo4j should match those in JSON."""
        from rules.graph_store import query_rules
        creds = get_neo4j_creds()

        for agent_name in ["metadata", "editorial", "compliance", "accuracy"]:
            graph_rules = await query_rules(**creds, agent_name=agent_name, content_type="standard")
            json_rules = _parse_rules_from_json(agent_name, "standard")

            graph_deps = {r.id: set(r.depends_on) for r in graph_rules.rules}
            json_deps = {r.id: set(r.depends_on) for r in json_rules.rules}

            for rule_id in graph_deps:
                assert graph_deps[rule_id] == json_deps.get(rule_id, set()), (
                    f"{agent_name}/{rule_id}: dependency mismatch — "
                    f"Neo4j={graph_deps[rule_id]}, JSON={json_deps.get(rule_id, set())}"
                )


# ---------------------------------------------------------------------------
# E2E 8: Version Tracking
# ---------------------------------------------------------------------------

class TestVersionTracking:
    """Verify version is tracked in both Neo4j and JSON."""

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_graph_version_matches_json(self):
        """Version stored in Neo4j should match validation_rules.json."""
        rule_set = await get_rules_for_agent("metadata", "standard")
        json_version = get_rules_version()
        assert rule_set.rules_version == json_version, (
            f"Version mismatch: Neo4j={rule_set.rules_version}, JSON={json_version}"
        )

    @skip_no_neo4j
    @pytest.mark.asyncio
    async def test_rules_version_in_loader(self):
        """get_rules_version should return a semver string."""
        version = get_rules_version()
        parts = version.split(".")
        assert len(parts) == 3, f"Expected semver, got {version}"
