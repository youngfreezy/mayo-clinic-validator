"""
Pydantic models for the validation rules system.

These models are used by both the Neo4j graph store and the JSON fallback loader,
ensuring a consistent interface regardless of the backing store.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class RuleThreshold(BaseModel):
    """Numeric thresholds attached to a rule (e.g., min/max character counts)."""
    min: Optional[float] = None
    max: Optional[float] = None
    unit: Optional[str] = None
    min_sections: Optional[int] = None
    min_words: Optional[int] = None
    max_age_years: Optional[int] = None
    deduction_per_issue: Optional[float] = None


class Rule(BaseModel):
    """A single validation rule that an agent evaluates."""
    id: str
    description: str
    severity: str = Field(description="critical | major | minor | info")
    category: str
    threshold: Optional[RuleThreshold] = None
    depends_on: List[str] = Field(default_factory=list)


class AgentRuleSet(BaseModel):
    """Complete rule set for a single agent, ready to inject into a prompt."""
    agent_name: str
    pass_threshold: float
    content_type: str
    rules: List[Rule]
    scoring: Dict[str, str] = Field(default_factory=dict)
    context: Optional[str] = None
    rules_version: str = "unknown"
    source: str = Field(default="json", description="neo4j | json")

    def to_prompt_block(self) -> str:
        """
        Serialize the rule set into a text block suitable for injection
        into an LLM system or user prompt.
        """
        lines = []

        if self.context:
            lines.append(f"IMPORTANT CONTEXT:\n{self.context}\n")

        lines.append("VALIDATION RULES:")
        for i, rule in enumerate(self.rules, 1):
            severity_tag = f"[{rule.severity.upper()}]"
            lines.append(f"  {i}. {severity_tag} {rule.description}")
            if rule.threshold:
                thresh_parts = []
                t = rule.threshold
                if t.min is not None and t.max is not None:
                    thresh_parts.append(f"Range: {t.min}-{t.max} {t.unit or ''}")
                elif t.min is not None:
                    thresh_parts.append(f"Minimum: {t.min} {t.unit or ''}")
                elif t.max is not None:
                    thresh_parts.append(f"Maximum: {t.max} {t.unit or ''}")
                if t.min_sections:
                    thresh_parts.append(f"Minimum sections: {t.min_sections}")
                if t.min_words:
                    thresh_parts.append(f"Minimum words: {t.min_words}")
                if t.max_age_years:
                    thresh_parts.append(f"Max age: {t.max_age_years} years")
                if t.deduction_per_issue:
                    thresh_parts.append(f"Deduction per issue: {t.deduction_per_issue}")
                if thresh_parts:
                    lines.append(f"     Threshold: {', '.join(thresh_parts)}")

        lines.append(f"\nSCORING CRITERIA:")
        for level, desc in self.scoring.items():
            lines.append(f"  - {desc}")

        lines.append(f"\nA page PASSES if score >= {self.pass_threshold}.")
        return "\n".join(lines)
