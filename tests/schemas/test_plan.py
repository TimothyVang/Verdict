from __future__ import annotations

import pytest
from pydantic import ValidationError

from verdict.schemas.plan import Hypothesis, InvestigationPlan


def test_mitre_subtechnique_regex_validates_t1055_012() -> None:
    hypothesis = Hypothesis(
        id="h_proc_inject_001",
        polarity="positive",
        mitre_technique="T1055.012",
        artifact_families=["process_memory"],
        success_criteria="Evidence consistent with process hollowing in memory artifacts.",
    )

    assert hypothesis.mitre_technique == "T1055.012"


def test_mitre_invalid_format_rejected() -> None:
    with pytest.raises(ValidationError):
        Hypothesis(
            id="h_bad_mitre_001",
            polarity="positive",
            mitre_technique="1055.012",
            artifact_families=["process_memory"],
            success_criteria="Reject malformed MITRE technique identifiers.",
        )


def test_negative_hypothesis_quality_rejects_degenerate() -> None:
    with pytest.raises(ValidationError):
        InvestigationPlan(
            plan_id="plan-001",
            case_id="case-001",
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
                    id="nothing",
                    polarity="negative",
                    mitre_technique=None,
                    artifact_families=[],
                    success_criteria="nothing",
                ),
            ],
            tool_budget=8,
            success_criteria="Resolve positive and negative hypotheses.",
            planner_cot_gzip_hash="c" * 64,
        )


def test_replan_budget_defaults_to_3() -> None:
    plan = InvestigationPlan(
        plan_id="plan-001",
        case_id="case-001",
        positive_hypotheses=[
            Hypothesis(
                id="hyp-positive-001",
                polarity="positive",
                mitre_technique="T1014",
                artifact_families=["process_memory"],
                success_criteria="Compare pslist and psscan process sets.",
            ),
        ],
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

    assert plan.replan_budget == 3
    assert plan.pivot_budget == 15
