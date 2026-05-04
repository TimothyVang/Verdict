from __future__ import annotations

from verdict.graph.nodes import pivot_node
from verdict.schemas.plan import Hypothesis, InvestigationPlan


def _hypothesis(hypothesis_id: str) -> Hypothesis:
    return Hypothesis(
        id=hypothesis_id,
        polarity="positive",
        mitre_technique="T1014",
        artifact_families=["process_memory"],
        success_criteria="Compare pslist and psscan process sets.",
    )


def _plan() -> InvestigationPlan:
    return InvestigationPlan(
        plan_id="plan-001",
        case_id="case-001",
        positive_hypotheses=[_hypothesis("hyp-001")],
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


def test_adds_one_hypothesis_within_pivot_max_15() -> None:
    state = pivot_node({"plan": _plan(), "pivot_hypothesis": _hypothesis("hyp-002")})

    assert len(state["plan"].positive_hypotheses) == 2
    assert state["pivot_count"] == 1


def test_pivot_does_not_re_enter_planner() -> None:
    state = pivot_node({"plan": _plan(), "pivot_hypothesis": _hypothesis("hyp-002")})

    assert state["last_node"] == "pivot"
    assert state["next_node"] == "executor_fanout"
