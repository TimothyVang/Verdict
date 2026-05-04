from __future__ import annotations

from datetime import UTC, datetime

from verdict.graph.comprehension_gate import build_comprehension_mismatch_event
from verdict.schemas.plan import PlanComprehensionEcho


def _echo(*, executor_id: str, criteria_hash: str) -> PlanComprehensionEcho:
    return PlanComprehensionEcho(
        executor_id=executor_id,
        plan_id="plan-001",
        parsed_positive_hypothesis_ids=["h_positive_001"],
        parsed_negative_hypothesis_ids=["h_negative_001"],
        parsed_success_criteria_hash=criteria_hash,
        confirmation_timestamp=datetime(2026, 5, 2, tzinfo=UTC),
    )


def test_ledger_contains_structured_per_executor_diff_on_mismatch() -> None:
    event = build_comprehension_mismatch_event(
        [
            _echo(executor_id="a", criteria_hash="a" * 64),
            _echo(executor_id="b", criteria_hash="b" * 64),
        ],
    )

    assert event["event_type"] == "comprehension_mismatch"
    assert event["plan_id"] == "plan-001"
    assert event["diffs"] == [
        {
            "executor_id": "b",
            "field": "parsed_success_criteria_hash",
            "expected": "a" * 64,
            "actual": "b" * 64,
        },
    ]
