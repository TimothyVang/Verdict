from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from verdict.graph.interrupt import HumanInterrupt
from verdict.graph.nodes import unverifiable_finalize_node
from verdict.graph.wrappers.ledger_emitter import LedgerEmitter
from verdict.schemas.artifact_class import ArtifactClass
from verdict.schemas.plan import Hypothesis, InvestigationPlan
from verdict.schemas.verdict_status import VerdictStatus

if TYPE_CHECKING:
    from pathlib import Path as PathType


def _hypothesis() -> Hypothesis:
    return Hypothesis(
        id="hyp-001",
        polarity="positive",
        mitre_technique="T1014",
        artifact_families=["process_memory"],
        success_criteria="Resolve pslist/psscan divergence.",
    )


def _plan() -> InvestigationPlan:
    return InvestigationPlan(
        plan_id="plan-001",
        case_id="case-001",
        positive_hypotheses=[_hypothesis()],
        negative_hypotheses=[
            Hypothesis(
                id="hyp-negative-001",
                polarity="negative",
                mitre_technique="T1014",
                artifact_families=["process_memory"],
                success_criteria="No pslist/psscan divergence exists.",
            ),
        ],
        tool_budget=10,
        success_criteria="Resolve DKOM hypothesis.",
        planner_cot_gzip_hash="a" * 64,
    )


def _state(tmp_path: PathType) -> dict:
    return {
        "case_id": "case-001",
        "chain_id": "chain-001",
        "plan": _plan(),
        "hypothesis": _hypothesis(),
        "replan_iteration": 4,
        "ledger_emitter": LedgerEmitter(tmp_path / "ledger.jsonl", hmac_key=b"k" * 32),
        "artifact_paths": [Path("/case/psscan.json"), Path("/case/pslist.json")],
        "artifact_classes": [ArtifactClass.PROCESS_MEMORY, ArtifactClass.YARA_HIT],
    }


def test_writes_unverifiable_finding_at_replan_iteration_4(tmp_path: PathType) -> None:
    with pytest.raises(HumanInterrupt) as exc_info:
        unverifiable_finalize_node(_state(tmp_path))

    finding = exc_info.value.state["finding"]
    assert finding.status is VerdictStatus.UNVERIFIABLE
    assert finding.hypothesis_ids == ["hyp-001"]


def test_writes_exhausted_replan_ledger_event(tmp_path: PathType) -> None:
    state = _state(tmp_path)

    with pytest.raises(HumanInterrupt):
        unverifiable_finalize_node(state)

    entry = state["ledger_emitter"].last_entry()
    assert entry["event_type"] == "exhausted_replan"
    assert entry["payload"]["idempotency_key"] == "case-001:chain-001:hyp-001:4:exhausted_replan"


def test_calls_interrupt(tmp_path: PathType) -> None:
    with pytest.raises(HumanInterrupt):
        unverifiable_finalize_node(_state(tmp_path))


def test_resume_does_not_duplicate_exhausted_replan_ledger_entry(tmp_path: PathType) -> None:
    state = _state(tmp_path)

    for _ in range(2):
        with pytest.raises(HumanInterrupt):
            unverifiable_finalize_node(state)

    lines = (tmp_path / "ledger.jsonl").read_text().splitlines()
    assert len(lines) == 1
