"""W2.B.3 — `ComprehensionMismatch` ledger entry on disagreement.

When the comprehension_gate concedes after MAX_CLARIFY_ITERATIONS, it
must emit a structured per-executor diff that downstream LedgerEmitter
(W2.C.3) writes as `event_type="comprehension_check"` with payload
schema `ComprehensionMismatch`.

The schema invariants tested here:

- Pydantic v2 model in `verdict.schemas.comprehension_mismatch` with the
  three CONSENSUS_KEYS captured per executor;
- per-executor diff structure: which echoes disagreed on which key;
- ULID-shaped event_id, UTC-Z timestamp;
- the gate node populates `state["pending_ledger_entry"]` with the
  structured payload so the next ledger super-step picks it up.

The ledger writer itself (write+fsync+verify-readback) lives in W2.G.1;
this task is purely about the EVENT TYPE + PAYLOAD SCHEMA contract that
W2.G.1 will consume.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from verdict.graph.nodes import (
    MAX_CLARIFY_ITERATIONS,
    comprehension_gate_node,
)
from verdict.schemas.comprehension_mismatch import (
    ComprehensionMismatch,
    ExecutorEchoDiff,
)


def _echo(branch: str, pos: list[str], neg: list[str], succ_hash: str) -> dict:
    return {
        "branch_name": branch,
        "parsed_positive_hypothesis_ids": pos,
        "parsed_negative_hypothesis_ids": neg,
        "parsed_success_criteria_hash": succ_hash,
    }


# ---------------------------------------------------------------------------
# Schema-level tests
# ---------------------------------------------------------------------------


def test_comprehension_mismatch_schema_round_trip() -> None:
    """ComprehensionMismatch round-trips through Pydantic."""
    payload = ComprehensionMismatch(
        case_id="case_001",
        clarify_iterations_spent=2,
        disagreeing_keys=["parsed_negative_hypothesis_ids"],
        per_executor=[
            ExecutorEchoDiff(
                branch_name="vol_exec",
                parsed_positive_hypothesis_ids=["H1", "H2"],
                parsed_negative_hypothesis_ids=["N1"],
                parsed_success_criteria_hash="abc123",
            ),
            ExecutorEchoDiff(
                branch_name="hay_exec",
                parsed_positive_hypothesis_ids=["H1", "H2"],
                parsed_negative_hypothesis_ids=["N1"],
                parsed_success_criteria_hash="abc123",
            ),
            ExecutorEchoDiff(
                branch_name="pls_exec",
                parsed_positive_hypothesis_ids=["H1", "H2"],
                parsed_negative_hypothesis_ids=["N1"],
                parsed_success_criteria_hash="abc123",
            ),
            ExecutorEchoDiff(
                branch_name="mft_exec",
                parsed_positive_hypothesis_ids=["H1", "H2"],
                parsed_negative_hypothesis_ids=["DIFFERENT"],
                parsed_success_criteria_hash="abc123",
            ),
        ],
        timestamp_utc=datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC),
    )
    assert payload.event_type == "comprehension_check"
    assert payload.timestamp_utc.tzinfo is not None  # always TZ-aware
    dumped = payload.model_dump(mode="json")
    # UTC Z-suffix per CLAUDE.md §3 forensic doctrine.
    assert dumped["timestamp_utc"].endswith("Z") or "+00:00" in dumped["timestamp_utc"]
    # Round-trip
    reloaded = ComprehensionMismatch.model_validate(dumped)
    assert reloaded == payload


def test_comprehension_mismatch_rejects_naive_timestamp() -> None:
    """Naive datetime is forensically unsound (CLAUDE.md §3 — UTC Z)."""
    with pytest.raises(ValidationError):
        ComprehensionMismatch(
            case_id="case_001",
            clarify_iterations_spent=2,
            disagreeing_keys=["parsed_positive_hypothesis_ids"],
            per_executor=[
                ExecutorEchoDiff(
                    branch_name="vol_exec",
                    parsed_positive_hypothesis_ids=["H1"],
                    parsed_negative_hypothesis_ids=["N1"],
                    parsed_success_criteria_hash="abc",
                )
            ],
            timestamp_utc=datetime(2026, 5, 2, 12, 0, 0),  # NAIVE
        )


def test_comprehension_mismatch_rejects_empty_disagreeing_keys() -> None:
    """A `comprehension_check` mismatch event with NO disagreeing keys is
    a contradiction in terms — the gate should never emit it."""
    with pytest.raises(ValidationError):
        ComprehensionMismatch(
            case_id="case_001",
            clarify_iterations_spent=2,
            disagreeing_keys=[],  # empty — invalid
            per_executor=[
                ExecutorEchoDiff(
                    branch_name="vol_exec",
                    parsed_positive_hypothesis_ids=["H1"],
                    parsed_negative_hypothesis_ids=["N1"],
                    parsed_success_criteria_hash="abc",
                )
            ],
            timestamp_utc=datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC),
        )


def test_comprehension_mismatch_event_id_ulid_shape() -> None:
    """`event_id` defaults to a ULID — 26 chars Crockford base32 per
    LedgerEntry contract (ARCHITECTURE.md §5).
    """
    payload = ComprehensionMismatch(
        case_id="case_001",
        clarify_iterations_spent=2,
        disagreeing_keys=["parsed_positive_hypothesis_ids"],
        per_executor=[
            ExecutorEchoDiff(
                branch_name="vol_exec",
                parsed_positive_hypothesis_ids=["H1"],
                parsed_negative_hypothesis_ids=["N1"],
                parsed_success_criteria_hash="abc",
            )
        ],
        timestamp_utc=datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC),
    )
    assert re.match(r"^[0-9A-HJKMNP-TV-Z]{26}$", payload.event_id), (
        f"event_id={payload.event_id!r} is not a ULID"
    )


# ---------------------------------------------------------------------------
# Gate -> ledger-payload integration
# ---------------------------------------------------------------------------


def test_gate_emits_pending_ledger_entry_on_concede() -> None:
    """When the gate concedes after MAX_CLARIFY_ITERATIONS rounds, it
    populates `pending_ledger_entry` with a ComprehensionMismatch
    payload that downstream LedgerEmitter (W2.C.3) will write.
    """
    pos, neg, hsh = ["H1"], ["N1"], "abc"
    echoes = [
        _echo("vol_exec", pos, neg, hsh),
        _echo("hay_exec", pos, neg, hsh),
        _echo("pls_exec", pos, neg, hsh),
        _echo("mft_exec", pos, ["DIFFERENT"], hsh),
    ]
    state = {
        "case_id": "case_test_001",
        "comprehension_echoes": echoes,
        "clarify_iterations": MAX_CLARIFY_ITERATIONS,
    }
    update = comprehension_gate_node(state)

    assert update["comprehension_consensus"] is False
    assert "pending_ledger_entry" in update, (
        "gate must populate pending_ledger_entry on concede so the "
        "ledger emitter can write the mismatch event"
    )
    payload = update["pending_ledger_entry"]
    # Validate as the schema directly to enforce the contract.
    parsed = ComprehensionMismatch.model_validate(payload)
    assert parsed.event_type == "comprehension_check"
    assert parsed.case_id == "case_test_001"
    assert "parsed_negative_hypothesis_ids" in parsed.disagreeing_keys
    # All 4 executor echoes preserved verbatim for forensic auditability.
    assert {d.branch_name for d in parsed.per_executor} == {
        "vol_exec", "hay_exec", "pls_exec", "mft_exec"
    }


def test_gate_omits_ledger_entry_on_consensus() -> None:
    """Happy path: 4-way consensus -> no ledger event needed."""
    pos, neg, hsh = ["H1"], ["N1"], "abc"
    echoes = [
        _echo(b, pos, neg, hsh)
        for b in ("vol_exec", "hay_exec", "pls_exec", "mft_exec")
    ]
    state = {"case_id": "case_001", "comprehension_echoes": echoes, "clarify_iterations": 0}
    update = comprehension_gate_node(state)
    assert update["comprehension_consensus"] is True
    assert "pending_ledger_entry" not in update


def test_gate_omits_ledger_entry_during_clarify() -> None:
    """Mid-clarify (budget not exhausted) -> no mismatch ledger event yet.
    Ledger entries are emitted only on terminal disagreement, not on
    every re-prompt round.
    """
    pos, neg, hsh = ["H1"], ["N1"], "abc"
    echoes = [
        _echo("vol_exec", pos, neg, hsh),
        _echo("hay_exec", pos, neg, hsh),
        _echo("pls_exec", pos, neg, hsh),
        _echo("mft_exec", pos, ["DIFFERENT"], hsh),
    ]
    state = {
        "case_id": "case_001",
        "comprehension_echoes": echoes,
        "clarify_iterations": 0,  # budget remaining
    }
    update = comprehension_gate_node(state)
    assert update["clarify_iterations"] == 1
    assert "pending_ledger_entry" not in update
