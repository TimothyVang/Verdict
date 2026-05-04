from __future__ import annotations

from typing import Any

from verdict.graph.comprehension_gate import comprehension_gate
from verdict.graph.interrupt import interrupt
from verdict.planning.planner_critique import critique_route
from verdict.schemas.finding import Finding
from verdict.schemas.verdict_status import VerdictStatus

GraphState = dict[str, Any]


def planner_node(state: GraphState) -> GraphState:
    return {**state, "last_node": "planner"}


def planner_critique_node(state: GraphState) -> GraphState:
    verdict = state["critique_verdict"]
    route = critique_route(verdict)
    emitter = state.get("ledger_emitter")
    if emitter is not None:
        emitter.emit(
            event_type="critique_verdict",
            case_id=state["case_id"],
            payload={
                "plan_id": verdict.plan_id,
                "route": route,
                "failed_questions": verdict.failed_questions,
                "overall_pass": verdict.overall_pass,
            },
        )
    return {**state, "last_node": "planner_critique", "planner_critique_route": route}


def comprehension_gate_node(state: GraphState) -> GraphState:
    route = comprehension_gate(state.get("comprehension_echoes", []))
    return {**state, "last_node": "comprehension_gate", "comprehension_route": route}


def executor_fanout_node(state: GraphState) -> GraphState:
    return {**state, "last_node": "executor_fanout"}


def quorum_node(state: GraphState) -> GraphState:
    return {**state, "last_node": "quorum"}


def pivot_node(state: GraphState) -> GraphState:
    plan = state["plan"]
    pivot_count = state.get("pivot_count", 0)
    if pivot_count >= plan.pivot_budget:
        return {**state, "last_node": "pivot", "next_node": "quorum"}

    pivot_hypothesis = state["pivot_hypothesis"]
    updated_plan = plan.model_copy(
        update={"positive_hypotheses": [*plan.positive_hypotheses, pivot_hypothesis]},
    )
    return {
        **state,
        "plan": updated_plan,
        "pivot_count": pivot_count + 1,
        "last_node": "pivot",
        "next_node": "executor_fanout",
    }


def replan_node(state: GraphState) -> GraphState:
    return {**state, "last_node": "replan"}


def unverifiable_finalize_node(state: GraphState) -> GraphState:
    hypothesis = state["hypothesis"]
    plan = state["plan"]
    replan_iteration = state["replan_iteration"]
    idempotency_key = (
        f"{state['case_id']}:{state['chain_id']}:{hypothesis.id}:"
        f"{replan_iteration}:exhausted_replan"
    )
    finding = Finding(
        finding_id=f"finding-{idempotency_key}",
        case_id=state["case_id"],
        plan_id=plan.plan_id,
        hypothesis_ids=[hypothesis.id],
        artifact_paths=state["artifact_paths"],
        artifact_classes=state["artifact_classes"],
        caveats_acknowledged=[],
        mitre_technique=hypothesis.mitre_technique,
        evidence_hashes={path: "unknown" for path in state["artifact_paths"]},
        rationale="Evidence remained unverifiable after exhausting the replan budget.",
        status=VerdictStatus.UNVERIFIABLE,
    )
    next_state = {**state, "last_node": "unverifiable_finalize", "finding": finding}

    emitter = state["ledger_emitter"]
    if not _ledger_has_idempotency_key(emitter, idempotency_key):
        emitter.emit(
            event_type="exhausted_replan",
            case_id=state["case_id"],
            payload={
                "idempotency_key": idempotency_key,
                "hypothesis_id": hypothesis.id,
                "replan_iteration": replan_iteration,
                "finding_id": finding.finding_id,
            },
        )

    interrupt(next_state)
    return next_state


def finalize_node(state: GraphState) -> GraphState:
    return {**state, "last_node": "finalize"}


def _ledger_has_idempotency_key(emitter: Any, idempotency_key: str) -> bool:
    if not emitter.ledger_path.exists():
        return False
    return idempotency_key in emitter.ledger_path.read_text()
