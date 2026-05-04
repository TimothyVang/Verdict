from __future__ import annotations

from typing import Literal

from verdict.schemas.plan import PlannerCritiqueVerdict


def critique_route(verdict: PlannerCritiqueVerdict) -> Literal["planner", "comprehension_gate"]:
    if verdict.route == "planner":
        return "planner"
    if verdict.route == "comprehension_gate":
        return "comprehension_gate"
    if verdict.failed_questions or not verdict.overall_pass:
        return "planner"
    return "comprehension_gate"
