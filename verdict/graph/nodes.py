"""LangGraph node implementations for the Plan-then-Execute topology.

Currently implements:
  - ``planner_critique_node`` — CoVe pass between planner_node and
    comprehension_gate (W2.D.1 / W2.D.2).

Topology position (ARCHITECTURE.md §2):
  planner_node → planner_critique_node → comprehension_gate →
  executor_fanout → pivot → quorum → replan → unverifiable_finalize →
  finalize

ARCHITECTURE.md §2 — 9-node LangGraph topology.
ARCHITECTURE.md §9 — "critique_verdict" ledger event type.
BUILD_PLAN W2.D.2 — wire planner_critique_node between planner + gate.
"""

from __future__ import annotations

from verdict.ledger.memory import InMemoryLedger, Ledger
from verdict.planning.planner_critique import CritiqueConfig, critique_plan
from verdict.schemas.plan import InvestigationPlan, PlannerCritiqueVerdict


def planner_critique_node(
    plan: InvestigationPlan,
    *,
    ledger: Ledger | None = None,
    config: CritiqueConfig | None = None,
) -> PlannerCritiqueVerdict:
    """Run the CoVe critique pass and emit a ``critique_verdict`` ledger event.

    This is the second node in the 9-node topology.  It:
    1. Calls ``critique_plan(plan, config)`` to get the routing verdict.
    2. Writes a ``critique_verdict`` ``LedgerEntry`` with the route decision,
       all questions, and any failed questions.
    3. Returns the ``PlannerCritiqueVerdict`` for routing by the graph.

    Parameters
    ----------
    plan:
        The ``InvestigationPlan`` produced by ``planner_node``.
    ledger:
        Ledger to write the ``critique_verdict`` event to.  Defaults to
        a fresh ``InMemoryLedger`` when not supplied (e.g. in unit tests
        that don't need the full ledger chain).
    config:
        Optional ``CritiqueConfig``.  Defaults to ``CritiqueConfig()``.

    Returns
    -------
    PlannerCritiqueVerdict
        The routing verdict.  LangGraph conditional edges read
        ``verdict.route`` to branch to ``comprehension_gate`` or back
        to ``planner_node``.
    """
    active_ledger: Ledger = ledger if ledger is not None else InMemoryLedger()

    verdict = critique_plan(plan, config=config)

    active_ledger.write(
        event_type="critique_verdict",
        case_id=plan.case_id,
        payload={
            "plan_id": plan.plan_id,
            "route": verdict.route,
            "all_questions": verdict.all_questions,
            "failed_questions": verdict.failed_questions,
            "hint": verdict.hint,
        },
        mode="cloud",  # mode is locked at case_init; W3 wires the real mode
    )

    return verdict
