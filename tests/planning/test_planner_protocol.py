from __future__ import annotations

from verdict.planning.planner import CloudPlanner, LocalPlanner, Planner, PlannerInput
from verdict.runtime.mode_detect import Mode, bind_planner_at_gateway_init
from verdict.schemas.plan import Hypothesis, InvestigationPlan


class ConcretePlanner:
    def plan(self, request: PlannerInput) -> InvestigationPlan:
        return InvestigationPlan(
            plan_id="plan-001",
            case_id=request.case_id,
            positive_hypotheses=[
                Hypothesis(
                    id="h_positive_001",
                    polarity="positive",
                    mitre_technique="T1059",
                    artifact_families=["evtx"],
                    success_criteria="Evidence consistent with command execution.",
                ),
            ],
            negative_hypotheses=[
                Hypothesis(
                    id="h_negative_001",
                    polarity="negative",
                    mitre_technique="T1014",
                    artifact_families=["process_memory"],
                    success_criteria="No DKOM divergence between process listings.",
                ),
            ],
            tool_budget=4,
            success_criteria="Resolve planner protocol contract.",
            planner_cot_gzip_hash="c" * 64,
        )


def test_protocol_returns_investigation_plan() -> None:
    planner: Planner = ConcretePlanner()
    plan = planner.plan(
        PlannerInput(
            case_id="case-001",
            evidence_summary="memory image with process anomalies",
            playbook_prompt="First move: windows.info",
        ),
    )

    assert isinstance(plan, InvestigationPlan)
    assert plan.case_id == "case-001"
    assert plan.negative_hypotheses


def test_planner_bound_at_gateway_init() -> None:
    assert isinstance(bind_planner_at_gateway_init(Mode.CLOUD), CloudPlanner)
    assert isinstance(bind_planner_at_gateway_init(Mode.AIRGAP), LocalPlanner)
    assert isinstance(bind_planner_at_gateway_init(Mode.DUAL), CloudPlanner)
