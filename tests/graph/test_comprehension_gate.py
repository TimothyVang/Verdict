from __future__ import annotations

from datetime import UTC, datetime

from verdict.graph.comprehension_gate import comprehension_gate
from verdict.schemas.plan import PlanComprehensionEcho


def _echo(*, executor_id: str, criteria_hash: str = "a" * 64) -> PlanComprehensionEcho:
    return PlanComprehensionEcho(
        executor_id=executor_id,
        plan_id="plan-001",
        parsed_positive_hypothesis_ids=["h_positive_001"],
        parsed_negative_hypothesis_ids=["h_negative_001"],
        parsed_success_criteria_hash=criteria_hash,
        confirmation_timestamp=datetime(2026, 5, 2, tzinfo=UTC),
    )


def test_consensus_advances_executor_work() -> None:
    route = comprehension_gate([_echo(executor_id="a"), _echo(executor_id="b")])

    assert route == "executor_work"


def test_mismatch_routes_to_clarify() -> None:
    route = comprehension_gate(
        [_echo(executor_id="a"), _echo(executor_id="b", criteria_hash="b" * 64)],
    )

    assert route == "clarify"
