from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from verdict.schemas.version import SCHEMA_VERSION

MITRE_TECHNIQUE_RE = re.compile(r"^T\d{4}(\.\d{3})?$")
DEGENERATE_NEGATIVE_IDS = {"cosmic", "alien", "nothing", "not-relevant", "n-a"}


class Hypothesis(BaseModel):
    """A positive or negative claim the investigation is testing."""

    id: str
    polarity: Literal["positive", "negative"]
    mitre_technique: str | None
    artifact_families: list[str]
    success_criteria: str

    @field_validator("mitre_technique")
    @classmethod
    def _mitre_technique_shape(cls, value: str | None) -> str | None:
        if value is not None and not MITRE_TECHNIQUE_RE.fullmatch(value):
            raise ValueError("mitre_technique must match ^T\\d{4}(\\.\\d{3})?$")
        return value


class PlanComprehensionEcho(BaseModel):
    """Executor echo of its parsed view of an investigation plan."""

    executor_id: str
    plan_id: str
    parsed_positive_hypothesis_ids: list[str]
    parsed_negative_hypothesis_ids: list[str]
    parsed_success_criteria_hash: str
    confirmation_timestamp: datetime


class PlannerCritiqueVerdict(BaseModel):
    """Planner critique result used before executor fanout."""

    plan_id: str
    questions_and_answers: list[tuple[str, str]]
    failed_questions: list[str]
    overall_pass: bool
    route: Literal["planner", "comprehension_gate"]
    timestamp_utc: datetime

    @model_validator(mode="after")
    def _route_matches_failed_questions(self) -> PlannerCritiqueVerdict:
        if self.route == "planner" and not self.failed_questions:
            raise ValueError("route=planner requires failed_questions")
        if self.route == "comprehension_gate" and (self.failed_questions or not self.overall_pass):
            raise ValueError("route=comprehension_gate requires an all-pass critique")
        return self


class InvestigationPlan(BaseModel):
    """Planner output shared byte-for-byte with executors."""

    plan_id: str
    case_id: str
    schema_version: int = SCHEMA_VERSION
    positive_hypotheses: list[Hypothesis]
    negative_hypotheses: list[Hypothesis]
    tool_budget: int
    pivot_budget: int = 15
    replan_budget: int = 3
    success_criteria: str
    planner_cot_gzip_hash: str
    comprehension_echoes: list[PlanComprehensionEcho] = []
    comprehension_consensus: bool = False
    critique_verdict: PlannerCritiqueVerdict | None = None

    @model_validator(mode="after")
    def _negative_hypothesis_quality(self) -> InvestigationPlan:
        for hypothesis in self.negative_hypotheses:
            if hypothesis.id.lower() in DEGENERATE_NEGATIVE_IDS:
                raise ValueError("negative hypothesis id is degenerate")
            if hypothesis.mitre_technique is None:
                raise ValueError("negative hypothesis requires mitre_technique")
            if not hypothesis.artifact_families:
                raise ValueError("negative hypothesis requires artifact_families")
        return self
