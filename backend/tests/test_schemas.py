"""
Pydantic schema validation tests.

Ensures that request/response models enforce correct types and constraints.
"""

import pytest
from pydantic import ValidationError

from models.schemas import ValidateRequest, HumanDecisionRequest, AgentFindingResponse, ValidationResponse
from pipeline.state import AgentFinding


# ---------------------------------------------------------------------------
# ValidateRequest
# ---------------------------------------------------------------------------

class TestValidateRequest:
    def test_valid_mayo_url(self):
        req = ValidateRequest(url="https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444")
        assert req.url.startswith("https://")

    def test_rejects_non_mayo_url(self):
        with pytest.raises(ValidationError) as exc_info:
            ValidateRequest(url="https://www.webmd.com/diabetes")
        assert "mayoclinic.org" in str(exc_info.value)

    def test_default_requested_by(self):
        req = ValidateRequest(url="https://www.mayoclinic.org/test")
        assert req.requested_by == "web-user"

    def test_custom_requested_by(self):
        req = ValidateRequest(url="https://www.mayoclinic.org/test", requested_by="editor@mayo.org")
        assert req.requested_by == "editor@mayo.org"


# ---------------------------------------------------------------------------
# HumanDecisionRequest
# ---------------------------------------------------------------------------

class TestHumanDecisionRequest:
    def test_approve_decision(self):
        req = HumanDecisionRequest(decision="approve")
        assert req.decision == "approve"
        assert req.feedback == ""
        assert req.reviewer_id == "web-user"

    def test_reject_decision(self):
        req = HumanDecisionRequest(decision="reject", feedback="Needs more references")
        assert req.decision == "reject"
        assert req.feedback == "Needs more references"

    def test_rejects_invalid_decision(self):
        with pytest.raises(ValidationError):
            HumanDecisionRequest(decision="maybe")

    def test_rejects_empty_decision(self):
        with pytest.raises(ValidationError):
            HumanDecisionRequest(decision="")


# ---------------------------------------------------------------------------
# AgentFinding (pipeline state model)
# ---------------------------------------------------------------------------

class TestAgentFinding:
    def test_valid_finding(self):
        f = AgentFinding(agent="metadata", passed=True, score=0.9, issues=[], recommendations=[])
        assert f.agent == "metadata"
        assert f.passed is True
        assert f.score == 0.9

    def test_score_must_be_0_to_1(self):
        with pytest.raises(ValidationError):
            AgentFinding(agent="metadata", passed=True, score=1.5)
        with pytest.raises(ValidationError):
            AgentFinding(agent="metadata", passed=True, score=-0.1)

    def test_score_boundary_values(self):
        f_min = AgentFinding(agent="compliance", passed=False, score=0.0)
        f_max = AgentFinding(agent="compliance", passed=True, score=1.0)
        assert f_min.score == 0.0
        assert f_max.score == 1.0

    def test_default_empty_lists(self):
        f = AgentFinding(agent="editorial", passed=True, score=0.8)
        assert f.issues == []
        assert f.recommendations == []

    def test_serialization(self):
        f = AgentFinding(
            agent="accuracy",
            passed=False,
            score=0.6,
            issues=["Outdated statistics"],
            recommendations=["Update 2019 data to 2024"],
        )
        d = f.model_dump()
        assert d["agent"] == "accuracy"
        assert d["issues"] == ["Outdated statistics"]
        assert isinstance(d["score"], float)


# ---------------------------------------------------------------------------
# AgentFindingResponse (API response model)
# ---------------------------------------------------------------------------

class TestAgentFindingResponse:
    def test_matches_agent_finding(self):
        finding = AgentFinding(agent="compliance", passed=True, score=0.95, issues=[], recommendations=[])
        resp = AgentFindingResponse(**finding.model_dump())
        assert resp.agent == "compliance"
        assert resp.score == 0.95
        assert resp.passed is True
