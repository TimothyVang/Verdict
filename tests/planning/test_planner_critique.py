from __future__ import annotations

from datetime import UTC, datetime

from verdict.planning.planner_critique import critique_route
from verdict.schemas.plan import PlannerCritiqueVerdict


def test_failed_questions_route_back_to_planner() -> None:
    verdict = PlannerCritiqueVerdict(
        plan_id="plan-001",
        questions_and_answers=[("Does the plan include negative hypotheses?", "No")],
        failed_questions=["Does the plan include negative hypotheses?"],
        overall_pass=False,
        route="planner",
        timestamp_utc=datetime(2026, 5, 2, tzinfo=UTC),
    )

    assert critique_route(verdict) == "planner"


def test_all_pass_advances_to_comprehension_gate() -> None:
    verdict = PlannerCritiqueVerdict(
        plan_id="plan-001",
        questions_and_answers=[("Does the plan include negative hypotheses?", "Yes")],
        failed_questions=[],
        overall_pass=True,
        route="comprehension_gate",
        timestamp_utc=datetime(2026, 5, 2, tzinfo=UTC),
    )

    assert critique_route(verdict) == "comprehension_gate"
