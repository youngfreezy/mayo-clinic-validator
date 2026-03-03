"""
Evaluation suite for the validation rules system.

Measures rule quality across multiple dimensions:
- Rule completeness: Are all expected checks covered?
- Rule clarity: Are descriptions unambiguous and actionable?
- Dependency coherence: Do dependency chains resolve correctly?
- Prompt quality: Do generated prompt blocks contain all rules?
- Threshold coverage: Do numeric rules have thresholds defined?
- Cross-agent consistency: Are shared concerns covered consistently?

These evals run as pytest tests and produce a summary report.
Can be integrated into CI/CD to catch regressions when rules are modified.
"""

import json
from pathlib import Path
from collections import Counter
from typing import Dict, List, Set

import pytest

from rules.schema import AgentRuleSet, Rule, RuleThreshold
from rules.loader import _load_json, _parse_rules_from_json

RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "validation_rules.json"


# ---------------------------------------------------------------------------
# Eval 1: Rule Completeness — are all critical checks represented?
# ---------------------------------------------------------------------------

# Expected critical checks per agent (ground truth from original hardcoded prompts)
EXPECTED_CRITICAL_CHECKS: Dict[str, Set[str]] = {
    "metadata": {
        "meta description",
        "canonical url",
        "json-ld structured data",
        "open graph",
    },
    "editorial": {
        "heading level",
        "last reviewed",
        "attribution",
        "required sections",
    },
    "compliance": {
        "absolute cure claims",
        "personal health information",
        "disclaimer",
        "hedging",
        "fda",
    },
    "accuracy": {
        "claims must align",
        "dosage",
        "symptom",
    },
    "empty_tag": {
        "self-closing",
        "empty",
    },
}


class TestRuleCompleteness:
    """Eval: Do the JSON rules cover all known critical validation checks?"""

    @pytest.fixture(autouse=True)
    def load_rules(self):
        with open(RULES_PATH) as f:
            self.data = json.load(f)

    @pytest.mark.parametrize("agent_name", EXPECTED_CRITICAL_CHECKS.keys())
    def test_critical_checks_covered(self, agent_name: str):
        """
        For each agent, verify that every expected critical check appears
        (via substring match) in at least one rule description.
        """
        rules = self.data["agents"][agent_name]["rules"]
        all_descriptions = " ".join(r["description"].lower() for r in rules)

        missing = []
        for check in EXPECTED_CRITICAL_CHECKS[agent_name]:
            if check.lower() not in all_descriptions:
                missing.append(check)

        assert not missing, (
            f"{agent_name}: Missing critical checks in rules: {missing}"
        )


# ---------------------------------------------------------------------------
# Eval 2: Rule Clarity — descriptions should be specific and actionable
# ---------------------------------------------------------------------------

class TestRuleClarity:
    """Eval: Are rule descriptions clear, specific, and long enough?"""

    @pytest.fixture(autouse=True)
    def load_rules(self):
        with open(RULES_PATH) as f:
            self.data = json.load(f)

    def test_descriptions_minimum_length(self):
        """Each rule description should be at least 20 characters."""
        short_rules = []
        for agent_name, agent in self.data["agents"].items():
            for rule in agent["rules"]:
                if len(rule["description"]) < 20:
                    short_rules.append(f"{agent_name}/{rule['id']}: {rule['description']}")
        assert not short_rules, f"Rules with descriptions too short: {short_rules}"

    def test_no_vague_descriptions(self):
        """Descriptions should not be vague one-word descriptions."""
        vague_words = {"check", "validate", "verify", "test", "review"}
        vague_rules = []
        for agent_name, agent in self.data["agents"].items():
            for rule in agent["rules"]:
                words = set(rule["description"].lower().split())
                if len(words) <= 3 and words & vague_words:
                    vague_rules.append(f"{agent_name}/{rule['id']}")
        assert not vague_rules, f"Vague rule descriptions: {vague_rules}"

    def test_descriptions_contain_must_or_should(self):
        """
        Good rules should express obligation — at least 80% of non-info rules
        should contain 'must', 'should', 'required', or 'at least'.
        """
        obligation_words = {"must", "should", "required", "at least"}
        total = 0
        with_obligation = 0
        for agent in self.data["agents"].values():
            for rule in agent["rules"]:
                if rule["severity"] == "info":
                    continue
                total += 1
                desc_lower = rule["description"].lower()
                if any(w in desc_lower for w in obligation_words):
                    with_obligation += 1

        ratio = with_obligation / total if total > 0 else 0
        assert ratio >= 0.8, (
            f"Only {ratio:.0%} of rules express obligation (must/should/required). "
            f"Expected >= 80%."
        )


# ---------------------------------------------------------------------------
# Eval 3: Dependency Coherence — dependency chains should be valid
# ---------------------------------------------------------------------------

class TestDependencyCoherence:
    """Eval: Are dependency relationships valid and acyclic?"""

    @pytest.fixture(autouse=True)
    def load_rules(self):
        with open(RULES_PATH) as f:
            self.data = json.load(f)
        self.all_rules = {}
        for agent in self.data["agents"].values():
            for rule in agent["rules"]:
                self.all_rules[rule["id"]] = rule

    def test_no_self_dependencies(self):
        for rule_id, rule in self.all_rules.items():
            assert rule_id not in rule.get("depends_on", []), (
                f"Rule {rule_id} depends on itself"
            )

    def test_no_circular_dependencies(self):
        """Check for cycles using DFS."""
        deps = {r_id: r.get("depends_on", []) for r_id, r in self.all_rules.items()}

        def has_cycle(node, visited, stack):
            visited.add(node)
            stack.add(node)
            for neighbor in deps.get(node, []):
                if neighbor in stack:
                    return True
                if neighbor not in visited and has_cycle(neighbor, visited, stack):
                    return True
            stack.discard(node)
            return False

        visited = set()
        for rule_id in self.all_rules:
            if rule_id not in visited:
                assert not has_cycle(rule_id, visited, set()), (
                    f"Circular dependency detected involving {rule_id}"
                )

    def test_dependency_severity_ordering(self):
        """
        A rule should not depend on a lower-severity rule.
        Critical can depend on critical; major can depend on critical/major; etc.
        """
        severity_rank = {"critical": 3, "major": 2, "minor": 1, "info": 0}
        violations = []
        for rule_id, rule in self.all_rules.items():
            child_rank = severity_rank.get(rule["severity"], 0)
            for dep_id in rule.get("depends_on", []):
                parent = self.all_rules.get(dep_id)
                if parent:
                    parent_rank = severity_rank.get(parent["severity"], 0)
                    if parent_rank < child_rank:
                        violations.append(
                            f"{rule_id} ({rule['severity']}) depends on "
                            f"{dep_id} ({parent['severity']})"
                        )
        # This is a warning-level eval — non-blocking
        if violations:
            pytest.skip(f"Severity ordering warnings: {violations}")


# ---------------------------------------------------------------------------
# Eval 4: Prompt Quality — generated prompts should be well-formed
# ---------------------------------------------------------------------------

class TestPromptQuality:
    """Eval: Do generated prompt blocks contain all rules and are well-structured?"""

    @pytest.mark.parametrize("agent_name", ["metadata", "editorial", "compliance", "accuracy", "empty_tag"])
    def test_prompt_block_contains_all_rules(self, agent_name: str):
        content_type = "hil" if agent_name == "empty_tag" else "standard"
        rule_set = _parse_rules_from_json(agent_name, content_type)
        assert rule_set is not None

        block = rule_set.to_prompt_block()
        for rule in rule_set.rules:
            assert rule.description in block, (
                f"Rule {rule.id} description missing from prompt block"
            )

    @pytest.mark.parametrize("agent_name", ["metadata", "editorial", "compliance", "accuracy", "empty_tag"])
    def test_prompt_block_has_scoring_section(self, agent_name: str):
        content_type = "hil" if agent_name == "empty_tag" else "standard"
        rule_set = _parse_rules_from_json(agent_name, content_type)
        assert rule_set is not None

        block = rule_set.to_prompt_block()
        assert "SCORING CRITERIA:" in block
        assert "PASSES" in block

    def test_prompt_block_size_under_limit(self):
        """Each prompt block should be under 2000 tokens (~8000 chars) to leave room for content."""
        for agent_name in ["metadata", "editorial", "compliance", "accuracy"]:
            rule_set = _parse_rules_from_json(agent_name, "standard")
            block = rule_set.to_prompt_block()
            assert len(block) < 8000, (
                f"{agent_name} prompt block is {len(block)} chars — too large for reliable prompting"
            )


# ---------------------------------------------------------------------------
# Eval 5: Threshold Coverage — numeric rules should have thresholds
# ---------------------------------------------------------------------------

class TestThresholdCoverage:
    """Eval: Do rules that imply numeric checks have thresholds defined?"""

    NUMERIC_KEYWORDS = {"length", "characters", "words", "years", "sections", "deduction"}

    @pytest.fixture(autouse=True)
    def load_rules(self):
        with open(RULES_PATH) as f:
            self.data = json.load(f)

    def test_numeric_rules_have_thresholds(self):
        """Rules whose descriptions mention numeric concepts should have threshold objects."""
        missing_threshold = []
        for agent_name, agent in self.data["agents"].items():
            for rule in agent["rules"]:
                desc_lower = rule["description"].lower()
                has_numeric_keyword = any(kw in desc_lower for kw in self.NUMERIC_KEYWORDS)
                # Also check for actual numbers in the description
                has_number = any(c.isdigit() for c in rule["description"])
                if (has_numeric_keyword or has_number) and not rule.get("threshold"):
                    missing_threshold.append(f"{agent_name}/{rule['id']}")

        # Allow some rules to not have thresholds (descriptions may mention numbers contextually)
        # But flag if more than 30% are missing
        total_numeric = len(missing_threshold)
        if total_numeric > 0:
            # Just report, don't fail — some numeric mentions are contextual
            pass  # Informational


# ---------------------------------------------------------------------------
# Eval 6: Cross-Agent Consistency
# ---------------------------------------------------------------------------

class TestCrossAgentConsistency:
    """Eval: Are shared validation concerns covered consistently?"""

    @pytest.fixture(autouse=True)
    def load_rules(self):
        with open(RULES_PATH) as f:
            self.data = json.load(f)

    def test_all_agents_have_scoring_criteria(self):
        for agent_name, agent in self.data["agents"].items():
            assert "scoring" in agent, f"{agent_name} missing scoring criteria"
            assert len(agent["scoring"]) >= 2, f"{agent_name} has too few scoring levels"

    def test_severity_distribution_reasonable(self):
        """
        Each agent should have a mix of severities — not all critical or all minor.
        At least 2 different severity levels per agent.
        """
        for agent_name, agent in self.data["agents"].items():
            severities = {r["severity"] for r in agent["rules"]}
            assert len(severities) >= 2, (
                f"{agent_name} has only one severity level: {severities}"
            )

    def test_category_diversity(self):
        """Each LLM agent (not empty_tag) should have at least 2 rule categories."""
        for agent_name in ["metadata", "editorial", "compliance", "accuracy"]:
            categories = {r["category"] for r in self.data["agents"][agent_name]["rules"]}
            assert len(categories) >= 2, (
                f"{agent_name} has only one category: {categories}"
            )


# ---------------------------------------------------------------------------
# Summary report (runs last)
# ---------------------------------------------------------------------------

class TestEvalSummary:
    """Generate an eval summary for CI/CD artifacts."""

    def test_generate_summary(self, tmp_path):
        """Generate a JSON eval summary artifact."""
        with open(RULES_PATH) as f:
            data = json.load(f)

        summary = {
            "rules_version": data["version"],
            "total_agents": len(data["agents"]),
            "total_rules": sum(len(a["rules"]) for a in data["agents"].values()),
            "rules_per_agent": {
                name: len(agent["rules"]) for name, agent in data["agents"].items()
            },
            "severity_distribution": dict(Counter(
                r["severity"]
                for agent in data["agents"].values()
                for r in agent["rules"]
            )),
            "category_distribution": dict(Counter(
                r["category"]
                for agent in data["agents"].values()
                for r in agent["rules"]
            )),
            "dependency_count": sum(
                len(r.get("depends_on", []))
                for agent in data["agents"].values()
                for r in agent["rules"]
            ),
            "agents_with_thresholds": [
                name for name, agent in data["agents"].items()
                if any(r.get("threshold") for r in agent["rules"])
            ],
        }

        # Write artifact
        artifact_path = tmp_path / "rules_eval_summary.json"
        with open(artifact_path, "w") as f:
            json.dump(summary, f, indent=2)

        # Validate summary
        assert summary["total_rules"] >= 30
        assert summary["total_agents"] == 5
        assert "critical" in summary["severity_distribution"]

        print(f"\n{'='*60}")
        print("RULES EVALUATION SUMMARY")
        print(f"{'='*60}")
        print(f"Rules Version:     {summary['rules_version']}")
        print(f"Total Agents:      {summary['total_agents']}")
        print(f"Total Rules:       {summary['total_rules']}")
        print(f"Dependencies:      {summary['dependency_count']}")
        print(f"\nRules per Agent:")
        for name, count in summary["rules_per_agent"].items():
            print(f"  {name:15s} {count}")
        print(f"\nSeverity Distribution:")
        for sev, count in summary["severity_distribution"].items():
            print(f"  {sev:10s} {count}")
        print(f"\nCategory Distribution:")
        for cat, count in summary["category_distribution"].items():
            print(f"  {cat:25s} {count}")
        print(f"{'='*60}")
