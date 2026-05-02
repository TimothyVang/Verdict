"""Investigation plan schema for W1.B.5."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Hypothesis(BaseModel):
    """A single investigative hypothesis (positive or negative)."""
    id: str
    description: str
    mitre_technique: str | None = None  # ^T\d{4}(\.\d{3})?$
    artifact_families: list[str] = Field(default_factory=list)


class InvestigationPlan(BaseModel):
    """The planner's investigation strategy for a case."""
    case_id: str
    hypotheses: list[Hypothesis]
    tool_budget: int = 30
    success_criteria: str | None = None


class PlanComprehensionEcho(BaseModel):
    """Executor's echo of its understanding of the plan (W1.B.5)."""
    parsed_positive_hypothesis_ids: list[str]
    parsed_negative_hypothesis_ids: list[str]
    parsed_success_criteria_hash: str


class PlannerCritiqueVerdict(BaseModel):
    """CoVe verdict on plan quality (W1.B.5)."""
    is_plan_adequate: bool
    critique: str
    hint_for_replanning: str | None = None
