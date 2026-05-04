from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from verdict.graph.nodes import planner_critique_node
from verdict.graph.wrappers.ledger_emitter import LedgerEmitter
from verdict.schemas.plan import PlannerCritiqueVerdict

if TYPE_CHECKING:
    from pathlib import Path


def _timestamp() -> datetime:
    return datetime(2026, 5, 2, tzinfo=UTC)


def test_schema_rejects_missing_failed_questions_when_route_back() -> None:
    with pytest.raises(ValidationError):
        PlannerCritiqueVerdict(
            plan_id="plan-001",
            questions_and_answers=[("Does the plan include negative hypotheses?", "No")],
            failed_questions=[],
            overall_pass=False,
            route="planner",
            timestamp_utc=_timestamp(),
        )


def test_ledger_emits_critique_verdict_event_with_route_decision(tmp_path: Path) -> None:
    emitter = LedgerEmitter(ledger_path=tmp_path / "ledger.jsonl", hmac_key=b"k" * 32)
    verdict = PlannerCritiqueVerdict(
        plan_id="plan-001",
        questions_and_answers=[("Does the plan include negative hypotheses?", "Yes")],
        failed_questions=[],
        overall_pass=True,
        route="comprehension_gate",
        timestamp_utc=_timestamp(),
    )

    state = planner_critique_node(
        {
            "case_id": "case-001",
            "critique_verdict": verdict,
            "ledger_emitter": emitter,
        },
    )

    entry = emitter.last_entry()
    assert state["planner_critique_route"] == "comprehension_gate"
    assert entry["event_type"] == "critique_verdict"
    assert entry["payload"]["route"] == "comprehension_gate"
