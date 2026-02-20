from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional, List, Literal


class ValidateRequest(BaseModel):
    url: str
    requested_by: Optional[str] = "web-user"

    @field_validator("url")
    @classmethod
    def must_be_mayo_url(cls, v: str) -> str:
        if "mayoclinic.org" not in v:
            raise ValueError("URL must be a mayoclinic.org URL")
        return v


class HumanDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    feedback: Optional[str] = ""
    reviewer_id: Optional[str] = "web-user"


class AgentFindingResponse(BaseModel):
    agent: str
    passed: bool
    score: float
    issues: List[str]
    recommendations: List[str]


class ValidationResponse(BaseModel):
    validation_id: str
    url: str
    status: str
    overall_score: Optional[float] = None
    overall_passed: Optional[bool] = None
    findings: List[AgentFindingResponse] = []
    errors: List[str] = []
    created_at: str
