"""
Tests for the validation rules system.

Covers:
- JSON fallback loading
- Rule schema validation
- Prompt block generation
- Agent rule coverage (every agent has rules)
- Rule dependency integrity
- Content type filtering
"""

import json
from pathlib import Path

import pytest

from rules.schema import Rule, RuleThreshold, AgentRuleSet
from rules.loader import _load_json, _parse_rules_from_json, get_rules_version

RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "validation_rules.json"


# ---------------------------------------------------------------------------
# JSON structure tests
# ---------------------------------------------------------------------------

class TestValidationRulesJSON:
    """Validate the structure and integrity of validation_rules.json."""

    @pytest.fixture(autouse=True)
    def load_rules(self):
        with open(RULES_PATH) as f:
            self.data = json.load(f)

    def test_has_version(self):
        assert "version" in self.data
        # Semver-ish format
        parts = self.data["version"].split(".")
        assert len(parts) == 3

    def test_has_all_agents(self):
        expected_agents = {"metadata", "editorial", "compliance", "accuracy", "empty_tag"}
        actual_agents = set(self.data["agents"].keys())
        assert actual_agents == expected_agents

    def test_every_agent_has_pass_threshold(self):
        for name, agent in self.data["agents"].items():
            assert "pass_threshold" in agent, f"{name} missing pass_threshold"
            assert 0.0 < agent["pass_threshold"] <= 1.0, f"{name} threshold out of range"

    def test_every_agent_has_rules(self):
        for name, agent in self.data["agents"].items():
            assert len(agent.get("rules", [])) > 0, f"{name} has no rules"

    def test_every_rule_has_required_fields(self):
        for agent_name, agent in self.data["agents"].items():
            for rule in agent["rules"]:
                assert "id" in rule, f"Rule in {agent_name} missing id"
                assert "description" in rule, f"Rule {rule.get('id')} missing description"
                assert "severity" in rule, f"Rule {rule.get('id')} missing severity"
                assert "category" in rule, f"Rule {rule.get('id')} missing category"

    def test_severity_values_are_valid(self):
        valid_severities = {"critical", "major", "minor", "info"}
        for agent_name, agent in self.data["agents"].items():
            for rule in agent["rules"]:
                assert rule["severity"] in valid_severities, (
                    f"Rule {rule['id']} has invalid severity: {rule['severity']}"
                )

    def test_rule_ids_are_unique_globally(self):
        all_ids = []
        for agent in self.data["agents"].values():
            for rule in agent["rules"]:
                all_ids.append(rule["id"])
        assert len(all_ids) == len(set(all_ids)), "Duplicate rule IDs found"

    def test_dependency_targets_exist(self):
        """Every depends_on reference must point to an existing rule ID."""
        all_ids = set()
        for agent in self.data["agents"].values():
            for rule in agent["rules"]:
                all_ids.add(rule["id"])

        for agent_name, agent in self.data["agents"].items():
            for rule in agent["rules"]:
                for dep_id in rule.get("depends_on", []):
                    assert dep_id in all_ids, (
                        f"Rule {rule['id']} depends on {dep_id} which doesn't exist"
                    )

    def test_applies_to_values_are_valid(self):
        valid_types = {"standard", "hil", "all"}
        for name, agent in self.data["agents"].items():
            for ct in agent.get("applies_to", []):
                assert ct in valid_types, f"{name} has invalid applies_to: {ct}"


# ---------------------------------------------------------------------------
# Rule schema model tests
# ---------------------------------------------------------------------------

class TestRuleSchema:
    def test_rule_creation(self):
        rule = Rule(
            id="test_rule",
            description="Test description",
            severity="major",
            category="test",
        )
        assert rule.id == "test_rule"
        assert rule.depends_on == []

    def test_rule_with_threshold(self):
        rule = Rule(
            id="meta_desc_length",
            description="Meta desc length check",
            severity="major",
            category="quality",
            threshold=RuleThreshold(min=150, max=160, unit="characters"),
        )
        assert rule.threshold.min == 150
        assert rule.threshold.max == 160

    def test_agent_rule_set_to_prompt_block(self):
        rule_set = AgentRuleSet(
            agent_name="metadata",
            pass_threshold=0.7,
            content_type="standard",
            rules=[
                Rule(id="r1", description="Rule one", severity="critical", category="test"),
                Rule(id="r2", description="Rule two", severity="minor", category="test"),
            ],
            scoring={"perfect": "1.0: All good", "major": "Below 0.5: Bad"},
            rules_version="1.0.0",
            source="json",
        )
        block = rule_set.to_prompt_block()
        assert "VALIDATION RULES:" in block
        assert "[CRITICAL] Rule one" in block
        assert "[MINOR] Rule two" in block
        assert "score >= 0.7" in block
        assert "SCORING CRITERIA:" in block

    def test_prompt_block_includes_context(self):
        rule_set = AgentRuleSet(
            agent_name="metadata",
            pass_threshold=0.7,
            content_type="standard",
            rules=[Rule(id="r1", description="X", severity="major", category="test")],
            context="Some SSR context note",
            rules_version="1.0.0",
            source="json",
        )
        block = rule_set.to_prompt_block()
        assert "IMPORTANT CONTEXT:" in block
        assert "SSR context" in block

    def test_prompt_block_includes_thresholds(self):
        rule_set = AgentRuleSet(
            agent_name="editorial",
            pass_threshold=0.7,
            content_type="standard",
            rules=[
                Rule(
                    id="content_depth",
                    description="Must have enough words",
                    severity="minor",
                    category="quality",
                    threshold=RuleThreshold(min_words=500),
                ),
            ],
            rules_version="1.0.0",
            source="json",
        )
        block = rule_set.to_prompt_block()
        assert "Minimum words: 500" in block


# ---------------------------------------------------------------------------
# Loader tests (JSON fallback)
# ---------------------------------------------------------------------------

class TestRuleLoader:
    def test_load_json_returns_dict(self):
        data = _load_json()
        assert isinstance(data, dict)
        assert "version" in data

    def test_parse_metadata_rules(self):
        rule_set = _parse_rules_from_json("metadata", "standard")
        assert rule_set is not None
        assert rule_set.agent_name == "metadata"
        assert rule_set.pass_threshold == 0.7
        assert len(rule_set.rules) > 0
        assert rule_set.source == "json"

    def test_parse_compliance_rules_higher_threshold(self):
        rule_set = _parse_rules_from_json("compliance", "standard")
        assert rule_set is not None
        assert rule_set.pass_threshold == 0.75

    def test_parse_empty_tag_only_for_hil(self):
        rule_set = _parse_rules_from_json("empty_tag", "hil")
        assert rule_set is not None
        assert len(rule_set.rules) > 0

    def test_parse_empty_tag_not_for_standard(self):
        """empty_tag only applies to hil content."""
        rule_set = _parse_rules_from_json("empty_tag", "standard")
        assert rule_set is None

    def test_nonexistent_agent_returns_none(self):
        rule_set = _parse_rules_from_json("nonexistent_agent", "standard")
        assert rule_set is None

    def test_rules_version(self):
        version = get_rules_version()
        assert version == "1.0.0"

    @pytest.mark.asyncio
    async def test_get_rules_for_agent_fallback(self):
        """With no Neo4j configured, should fall back to JSON."""
        from rules.loader import get_rules_for_agent
        rule_set = await get_rules_for_agent("editorial", "standard")
        assert rule_set.source == "json"
        assert len(rule_set.rules) > 0


# ---------------------------------------------------------------------------
# Rule coverage tests — ensure no agent lost rules during migration
# ---------------------------------------------------------------------------

class TestRuleCoverage:
    """Verify that the JSON file has adequate rule coverage per agent."""

    @pytest.fixture(autouse=True)
    def load_rules(self):
        with open(RULES_PATH) as f:
            self.data = json.load(f)

    def test_metadata_has_key_rules(self):
        rule_ids = {r["id"] for r in self.data["agents"]["metadata"]["rules"]}
        assert "meta_desc_present" in rule_ids
        assert "canonical_url_present" in rule_ids
        assert "json_ld_present" in rule_ids
        assert "og_title_present" in rule_ids

    def test_editorial_has_key_rules(self):
        rule_ids = {r["id"] for r in self.data["agents"]["editorial"]["rules"]}
        assert "h1_present" in rule_ids
        assert "heading_hierarchy" in rule_ids
        assert "last_reviewed_present" in rule_ids
        assert "attribution_present" in rule_ids

    def test_compliance_has_key_rules(self):
        rule_ids = {r["id"] for r in self.data["agents"]["compliance"]["rules"]}
        assert "no_absolute_cure_claims" in rule_ids
        assert "no_hipaa_exposure" in rule_ids
        assert "hedging_language" in rule_ids
        assert "disclaimer_present" in rule_ids

    def test_accuracy_has_key_rules(self):
        rule_ids = {r["id"] for r in self.data["agents"]["accuracy"]["rules"]}
        assert "claims_match_references" in rule_ids
        assert "no_wrong_dosages" in rule_ids

    def test_empty_tag_has_key_rules(self):
        rule_ids = {r["id"] for r in self.data["agents"]["empty_tag"]["rules"]}
        assert "no_self_closing_tags" in rule_ids
        assert "no_empty_tags" in rule_ids

    def test_total_rule_count(self):
        """Sanity check: we should have ~34 rules across all agents."""
        total = sum(len(a["rules"]) for a in self.data["agents"].values())
        assert total >= 30, f"Expected at least 30 rules, got {total}"
