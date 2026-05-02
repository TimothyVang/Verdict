"""InvestigationPlan schema — top-level plan emitted by the planner node.

Minimal implementation for W1.B.12 schema_version discipline.
Full implementation (with Hypothesis, PlanComprehensionEcho,
PlannerCritiqueVerdict) is W1.B.5.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from verdict.schemas.version import SCHEMA_VERSION


class InvestigationPlan(BaseModel):
    """Top-level plan emitted by the planner node.

    schema_version: int = SCHEMA_VERSION (W1.B.12).
    """

    plan_id: str = Field(min_length=1)
    schema_version: int = SCHEMA_VERSION
