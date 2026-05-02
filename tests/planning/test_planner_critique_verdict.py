"""W2.D.2 — PlannerCritiqueVerdict schema + critique_verdict ledger event.

Two test groups per BUILD_PLAN W2.D.2.a:

1. ``test_schema_rejects_missing_failed_questions_when_route_back`` —
   ``PlannerCritiqueVerdict(route="planner", failed_questions=[])``
   raises ``ValidationError``.  This is the W2.D.2 schema invariant.

2. ``test_ledger_emits_critique_verdict_event_with_route_decision`` —
   ``planner_critique_node(state, ledger)`` writes a
   ``LedgerEntry(event_type="critique_verdict")`` to the ledger.  This
   verifies the ARCHITECTURE.md §9 event type is emitted.

The ledger used in the second group is ``InMemoryLedger`` — a real
implementation (not a mock) that holds entries in a list rather than
persisting to JSONL.  Real HMAC signing is skipped at this layer because
the key-management story (TPM / gpg) lands in W1.G.6; the in-memory ledger
is the production path for tests that run without a TPM.  Contrast with
the JSONL+HMAC path in ``verdict/ledger/writer.py`` (W1.G.6+).

CLAUDE.md §3.10 — no Mock*, MagicMock, patch against verdict.*.
ARCHITECTURE.md §2 — planner_critique_node is the second node in the graph.
BUILD_PLAN W2.D.2 — explicit acceptance criteria.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from verdict.graph.nodes import planner_critique_node
from verdict.ledger.memory import InMemoryLedger
from verdict.schemas.artifact_class import ArtifactClass
from verdict.schemas.plan import (
    Hypothesis,
    InvestigationPlan,
    PlannerCritiqueVerdict,
)

# ---------------------------------------------------------------------------
# W2.D.2 — Group 1: PlannerCritiqueVerdict schema invariant
# ---------------------------------------------------------------------------


def test_schema_rejects_loopback_with_empty_failed_questions() -> None:
    """``PlannerCritiqueVerdict(route="planner", failed_questions=[])``
    must raise ``ValidationError`` — a loopback with no reason is an
    infinite loop.  This is the W2.D.2 schema invariant.
    """
    with pytest.raises(ValidationError) as exc_info:
        PlannerCritiqueVerdict(route="planner", failed_questions=[])
    errors = exc_info.value.errors()
    assert len(errors) >= 1
    # The error must reference the invariant, not a field type mismatch
    error_messages = " ".join(str(e) for e in errors)
    assert "failed_questions" in error_messages or "loopback" in error_messages or (
        "planner" in error_messages
    ), f"Expected ValidationError to mention failed_questions/loopback, got: {errors}"


def test_schema_accepts_loopback_with_non_empty_failed_questions() -> None:
    """``PlannerCritiqueVerdict(route="planner", failed_questions=[...])``
    must succeed when ``failed_questions`` is non-empty.
    """
    verdict = PlannerCritiqueVerdict(
        route="planner",
        failed_questions=["Question 1: missing sub-technique precision"],
        hint="Use T1055.012 not bare T1055",
    )
    assert verdict.route == "planner"
    assert len(verdict.failed_questions) == 1


def test_schema_accepts_advance_with_empty_failed_questions() -> None:
    """``PlannerCritiqueVerdict(route="comprehension_gate", failed_questions=[])``
    must succeed — advancing does not require failed questions.
    """
    verdict = PlannerCritiqueVerdict(
        route="comprehension_gate",
        failed_questions=[],
    )
    assert verdict.route == "comprehension_gate"
    assert verdict.failed_questions == []


def test_schema_rejects_unknown_route() -> None:
    """Route must be one of the two Literal values."""
    with pytest.raises(ValidationError):
        PlannerCritiqueVerdict(  # type: ignore[call-arg]
            route="executor_fanout",  # not a valid route
            failed_questions=[],
        )


# ---------------------------------------------------------------------------
# W2.D.2 — Group 2: critique_verdict ledger event
# ---------------------------------------------------------------------------


def _make_valid_plan() -> InvestigationPlan:
    """Minimal valid plan for planner_critique_node tests."""
    return InvestigationPlan(
        plan_id="plan-w2d2-001",
        case_id="case-w2d2-001",
        evidence_summary="Windows 10 memory + disk; 2024-03-01 incident",
        tool_budget=10,
        hypotheses=[
            Hypothesis(
                id="H1",
                polarity="positive",
                mitre_technique="T1014",
                artifact_families=[
                    ArtifactClass.PROCESS_MEMORY,
                    ArtifactClass.SYSMON_1,
                ],
                success_criteria="DKOM divergence via psscan/pslist confirms T1014",
            ),
            Hypothesis(
                id="H2",
                polarity="negative",
                mitre_technique="T1059.001",
                artifact_families=[
                    ArtifactClass.PREFETCH,
                    ArtifactClass.AMCACHE,
                ],
                success_criteria=(
                    "no PowerShell prefetch/amcache within the incident window"
                ),
            ),
        ],
    )


def _make_flawed_plan() -> InvestigationPlan:
    """Plan with bare T1055 + PROCESS_MEMORY to trigger critique loopback."""
    return InvestigationPlan(
        plan_id="plan-w2d2-002",
        case_id="case-w2d2-002",
        evidence_summary="Windows 10 memory image only; 2024-03-01",
        tool_budget=10,
        hypotheses=[
            Hypothesis(
                id="H1",
                polarity="positive",
                mitre_technique="T1055",  # bare — T1055.012 is determinable
                artifact_families=[
                    ArtifactClass.PROCESS_MEMORY,
                    ArtifactClass.SYSMON_1,
                ],
                success_criteria="hollowed process detected via malfind",
            ),
            Hypothesis(
                id="H2",
                polarity="negative",
                mitre_technique="T1218.010",
                artifact_families=[ArtifactClass.PREFETCH, ArtifactClass.SIGMA_HIT],
                success_criteria="no regsvr32 prefetch entries",
            ),
        ],
    )


def test_planner_critique_node_emits_critique_verdict_event_on_pass() -> None:
    """planner_critique_node writes event_type='critique_verdict' on PASS.

    The ledger entry payload must include the route decision and the
    list of all verification questions.
    """
    plan = _make_valid_plan()
    ledger = InMemoryLedger()

    result = planner_critique_node(plan, ledger=ledger)

    assert result.route == "comprehension_gate"
    assert len(ledger.entries) == 1
    entry = ledger.entries[0]
    assert entry.event_type == "critique_verdict"
    assert entry.payload["route"] == "comprehension_gate"
    assert "all_questions" in entry.payload
    assert len(entry.payload["all_questions"]) >= 1


def test_planner_critique_node_emits_critique_verdict_event_on_fail() -> None:
    """planner_critique_node writes event_type='critique_verdict' on FAIL
    (route back to planner) and includes failed_questions in payload.
    """
    plan = _make_flawed_plan()
    ledger = InMemoryLedger()

    result = planner_critique_node(plan, ledger=ledger)

    assert result.route == "planner"
    assert len(ledger.entries) == 1
    entry = ledger.entries[0]
    assert entry.event_type == "critique_verdict"
    assert entry.payload["route"] == "planner"
    assert "failed_questions" in entry.payload
    assert len(entry.payload["failed_questions"]) >= 1
    assert "hint" in entry.payload


def test_planner_critique_node_sets_case_id_in_ledger_entry() -> None:
    """The critique_verdict ledger entry carries the correct case_id."""
    plan = _make_valid_plan()
    ledger = InMemoryLedger()
    planner_critique_node(plan, ledger=ledger)
    entry = ledger.entries[0]
    assert entry.case_id == plan.case_id


def test_planner_critique_node_returns_plandner_critique_verdict() -> None:
    """planner_critique_node always returns a PlannerCritiqueVerdict."""
    plan = _make_valid_plan()
    ledger = InMemoryLedger()
    result = planner_critique_node(plan, ledger=ledger)
    assert isinstance(result, PlannerCritiqueVerdict)
