"""LangGraph node functions for the 9-node Plan-then-Execute topology.

Topology (see `docs/ARCHITECTURE.md` §2):

    planner -> planner_critique -> comprehension_gate
        -> executor_fanout (n=4 parallel branches)
        -> pivot -> quorum
        -> {finalize | replan -> planner | unverifiable_finalize}

Each function takes a `GraphState` dict and returns a partial-state update,
matching LangGraph's reducer-friendly node signature.

Inference-backend leaves — `planner.plan()`, `executor.execute()`,
`planner_critique.run()` — are intentionally `NotImplementedError` stubs:
they belong to W2.A (tool wrappers), W2.D (CoVe critique) and the planner
protocol task in W1.G.5. The graph **topology, reducers and routing** are
real and tested here in W2.B.

Budget invariants (CLAUDE.md §8):
    pivot_max  = 15
    replan_max = 3   (iteration 4 -> unverifiable_finalize -> interrupt())
"""

from __future__ import annotations

from typing import Any

from verdict.graph.state import GraphState

# Budget invariants per CLAUDE.md §8 / ARCHITECTURE.md §2.
PIVOT_MAX = 15
REPLAN_MAX = 3


# ---------------------------------------------------------------------------
# Routing constants
# ---------------------------------------------------------------------------

# `comprehension_gate` consensus -> next node
ROUTE_GATE_PASS = "executor_fanout"
ROUTE_GATE_REPLAN = "replan"

# `quorum_node` outcome -> next node (per ARCHITECTURE.md §1 dispatch table)
ROUTE_VETTED = "finalize"
ROUTE_CONTESTED = "replan"
ROUTE_UNVERIFIABLE = "unverifiable_finalize"

# `replan_node` budget exhaustion -> next node
ROUTE_REPLAN_RETRY = "planner"
ROUTE_REPLAN_EXHAUSTED = "unverifiable_finalize"

# `planner_critique_node` -> next node
ROUTE_CRITIQUE_PASS = "comprehension_gate"
ROUTE_CRITIQUE_FAIL = "planner"


# ---------------------------------------------------------------------------
# Node functions — each returns a partial GraphState update.
# ---------------------------------------------------------------------------


def planner_node(state: GraphState) -> dict[str, Any]:
    """Produce or rewrite an `InvestigationPlan`.

    In CLOUD mode this calls Claude Code via the Agent SDK; in AIRGAP mode
    it calls Qwen3 via SGLang; in DUAL it runs both in parallel. The actual
    inference call lives in `verdict/planning/planner.py` (W1.G.5).
    """

    # The Planner protocol implementation lands in W1.G.5 / W2.A. This stub
    # is intentional — see module docstring.
    raise NotImplementedError(
        "planner_node requires verdict.planning.planner.Planner (W1.G.5)"
    )


def planner_critique_node(state: GraphState) -> dict[str, Any]:
    """CoVe critique of the plan (Dhuliawala 2023, arXiv:2309.11495).

    Same model that produced the plan drafts verification questions ABOUT
    THE PLAN ITSELF and answers them against the case_init evidence summary.
    Failed questions route back to `planner_node` with a hint; all-pass
    advances to `comprehension_gate`.

    The implementation lives in `verdict/planning/planner_critique.py`
    (W2.D.1); this node is a thin wrapper that owns Langfuse span emission
    and ledger `critique_verdict` event writes.
    """

    raise NotImplementedError(
        "planner_critique_node requires verdict.planning.planner_critique (W2.D.1)"
    )


def comprehension_gate_node(state: GraphState) -> dict[str, Any]:
    """Validate that all 4 executors parsed the plan identically.

    Each executor emits a `PlanComprehensionEcho` containing
    `parsed_positive_hypothesis_ids`, `parsed_negative_hypothesis_ids`,
    `parsed_success_criteria_hash`. The gate is purely a consensus check —
    no LLM call — and is therefore implemented for real here in W2.B.2
    (not stubbed).

    For W2.B.1 the consensus logic is a placeholder that defaults to
    "consensus reached" so the topology can compile and route. The real
    consensus + clarify sub-state logic lands in W2.B.2.
    """

    # W2.B.2 will replace this with the real consensus + clarify logic.
    return {"comprehension_consensus": True}


def executor_fanout_node(state: GraphState) -> dict[str, Any]:
    """Dispatch to 4 parallel executor branches (vol/hay/pls/mft).

    LangGraph's parallel-edge mechanism is what actually runs the 4
    branches concurrently — this node is the **fan-in collector** that
    LangGraph routes to after all 4 branches return. The reducer in
    `verdict/graph/reducers.py` (W2.B.4) merges the four parallel writes
    deterministically.

    The branches themselves invoke `DenyRuleWrapper -> ToolExecutor ->
    LedgerEmitter` (see W2.C.1 / W2.C.2 / W2.C.3); each branch composition
    lives in `verdict/graph/wrappers/`.
    """

    # The fanout collector itself does no work — the reducer-merged
    # `executor_results` are already in state. Return an empty patch so
    # LangGraph advances to `pivot_node`.
    return {}


def pivot_node(state: GraphState) -> dict[str, Any]:
    """Cheap follow-up: ONE Hypothesis added on basis of an executor finding.

    Re-enters `executor_fanout` only (not the planner). Bounded by
    `pivot_max=15`; once the budget is exhausted, advance to `quorum_node`.
    Pivot-vs-replan distinction per ARCHITECTURE.md §2.
    """

    pivot_count = int(state.get("pivot_count") or 0)
    if pivot_count >= PIVOT_MAX:
        # Budget exhausted; the conditional edge sends us to quorum.
        return {}
    # The actual pivot-Hypothesis selection lives in W2.A planner work;
    # for the topology test it suffices to advance the counter.
    return {"pivot_count": pivot_count + 1}


def quorum_node(state: GraphState) -> dict[str, Any]:
    """Apply the locked-mode `VerifierStrategy` to merged executor outputs.

    Returns a `quorum_verdict` containing one of the canonical
    `VerdictStatus` values (CLAUDE.md §3.6). Dispatch table:
    ARCHITECTURE.md §1.

    The `VerifierStrategy` implementations land in W1.C.2 / W3.A.1 / W3.A.2;
    this node is the dispatcher that picks the right strategy by mode.
    """

    raise NotImplementedError(
        "quorum_node requires verdict.verification.strategy.VerifierStrategy "
        "(W1.C.2 / W3.A.*)"
    )


def replan_node(state: GraphState) -> dict[str, Any]:
    """Full plan rewrite on quorum CONTESTED.

    Bounded by `replan_max=3`. Iteration 4 routes to
    `unverifiable_finalize_node` instead of looping back to `planner_node`.
    """

    replan_count = int(state.get("replan_count") or 0)
    return {"replan_count": replan_count + 1}


def unverifiable_finalize_node(state: GraphState) -> dict[str, Any]:
    """Write `Finding(status=UNVERIFIABLE)` and `interrupt()` for HITL.

    Triggered on `replan_max` exhaustion or terminal `UNVERIFIABLE` from
    the quorum dispatch table. UNVERIFIABLE is a **first-class outcome**
    (CLAUDE.md §3.6); the 15-item judge rubric specifically rewards
    explicit UNVERIFIABLE rather than hidden failure.
    """

    finding = {
        "status": "UNVERIFIABLE",
        "failure_reason": state.get("contested_hint") or "exhausted_replan",
        "artifact_paths": [],
        "caveats_acknowledged": [],
    }
    findings = list(state.get("findings") or [])
    findings.append(finding)
    return {"findings": findings}


def finalize_node(state: GraphState) -> dict[str, Any]:
    """HMAC-sign the verdict, write `finding` ledger entry, terminate."""

    # Real HMAC signing lives in W2.G.1 / W1.G.6. The topology test only
    # needs this node to terminate the graph cleanly.
    findings = list(state.get("findings") or [])
    return {"findings": findings}


# ---------------------------------------------------------------------------
# Conditional-edge routers — pure functions, no I/O.
# ---------------------------------------------------------------------------


def route_after_critique(state: GraphState) -> str:
    """`planner_critique_node` -> {planner | comprehension_gate}.

    The W2.D.1 critique result is a `PlannerCritiqueVerdict` with a `route`
    field; for W2.B.1 we default to PASS so the topology test can traverse
    the happy path.
    """

    critique = state.get("plan_critique") or {}
    route = critique.get("route", "comprehension_gate")
    if route == "planner":
        return ROUTE_CRITIQUE_FAIL
    return ROUTE_CRITIQUE_PASS


def route_after_gate(state: GraphState) -> str:
    """`comprehension_gate` -> {executor_fanout | replan}.

    Default PASS for W2.B.1; real consensus logic lands in W2.B.2.
    """

    if state.get("comprehension_consensus") is False:
        return ROUTE_GATE_REPLAN
    return ROUTE_GATE_PASS


def route_after_pivot(state: GraphState) -> str:
    """`pivot_node` -> {executor_fanout | quorum}.

    Loop back to executor_fanout while budget remains and a new hypothesis
    was injected; otherwise advance to quorum.
    """

    pivot_count = int(state.get("pivot_count") or 0)
    if pivot_count >= PIVOT_MAX:
        return "quorum"
    # The pivot-injection signal is `state["plan"]["pending_pivot_hypothesis"]`
    # written by the planner; for W2.B.1 we exit straight to quorum.
    plan = state.get("plan") or {}
    if plan.get("pending_pivot_hypothesis"):
        return "executor_fanout"
    return "quorum"


def route_after_quorum(state: GraphState) -> str:
    """`quorum_node` -> {finalize | replan | unverifiable_finalize}.

    Per ARCHITECTURE.md §1 dispatch table. UNVERIFIABLE is reachable
    directly (e.g., tool/sandbox exhaustion) without going through replan.
    """

    verdict = state.get("quorum_verdict") or ""
    if verdict.startswith("VETTED_"):
        return ROUTE_VETTED
    if verdict == "UNVERIFIABLE":
        return ROUTE_UNVERIFIABLE
    if verdict == "EXHAUSTED_REPLAN":
        return ROUTE_UNVERIFIABLE
    # CONTESTED or unknown -> replan
    return ROUTE_CONTESTED


def route_after_replan(state: GraphState) -> str:
    """`replan_node` -> {planner | unverifiable_finalize}.

    Budget exhausted at `REPLAN_MAX` -> unverifiable_finalize.
    """

    replan_count = int(state.get("replan_count") or 0)
    if replan_count > REPLAN_MAX:
        return ROUTE_REPLAN_EXHAUSTED
    return ROUTE_REPLAN_RETRY
