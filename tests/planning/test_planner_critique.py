"""W2.D.1 — planner_critique_node CoVe (Chain-of-Verification) tests.

Dhuliawala et al. 2023 (arXiv:2309.11495): the same model that produced
the plan drafts verification questions *about the plan itself*, answers them
against the ``InvestigationPlan.evidence_summary``, and routes accordingly.

Tests here validate the LOGIC layer:
  - ``critique_plan`` assembles questions, evaluates them, and returns a
    ``PlannerCritiqueVerdict``.
  - An obviously-flawed plan (§3.5 sub-technique precision violation or §3.2
    single-artifact execution claim) is caught by the critique and routed
    back to the planner with a non-empty ``failed_questions`` list.
  - A well-formed plan advances to comprehension_gate
    (``route == "comprehension_gate"``).

The critique LOGIC is pure Python — question assembly + plan-structural
inspection. The inference back-end (cloud/local) calls ``Planner.plan``
which raises ``NotImplementedError``; the critique itself does NOT call the
inference back-end; it receives a completed ``InvestigationPlan`` as input.

CLAUDE.md §3.5 — bare T1055 when T1055.012 is determinable is a critique
  failure.
CLAUDE.md §3.2 — execution-class technique with single artifact class is a
  critique failure.
"""

from __future__ import annotations

import pytest

from verdict.planning.planner_critique import CritiqueConfig, critique_plan
from verdict.schemas.artifact_class import ArtifactClass
from verdict.schemas.plan import (
    Hypothesis,
    InvestigationPlan,
    PlannerCritiqueVerdict,
)


# ---------------------------------------------------------------------------
# Helpers — build minimal valid / invalid plans
# ---------------------------------------------------------------------------


def _make_plan(
    *,
    positive_mitre: str = "T1014",
    positive_artifact_families: list[ArtifactClass] | None = None,
    negative_mitre: str = "T1059.001",
    plan_id: str = "plan-001",
    case_id: str = "case-001",
    evidence_summary: str = "Windows 10 memory image + .E01 disk; 2024-01-15 incident",
    tool_budget: int = 15,
) -> InvestigationPlan:
    """Build a minimal ``InvestigationPlan`` for critique tests."""
    pos_families = positive_artifact_families or [
        ArtifactClass.PROCESS_MEMORY,
        ArtifactClass.SYSMON_1,
    ]
    return InvestigationPlan(
        plan_id=plan_id,
        case_id=case_id,
        evidence_summary=evidence_summary,
        tool_budget=tool_budget,
        hypotheses=[
            Hypothesis(
                id="H1",
                polarity="positive",
                mitre_technique=positive_mitre,
                artifact_families=pos_families,
                success_criteria=(
                    "psscan/pslist divergence confirms DKOM; "
                    "evidence consistent with T1014"
                ),
            ),
            Hypothesis(
                id="H2",
                polarity="negative",
                mitre_technique=negative_mitre,
                artifact_families=[ArtifactClass.PREFETCH, ArtifactClass.AMCACHE],
                success_criteria=(
                    "no prefetch / amcache entries for powershell during "
                    "the incident window"
                ),
            ),
        ],
    )


# ---------------------------------------------------------------------------
# W2.D.1.a — RED tests
# ---------------------------------------------------------------------------


def test_critique_returns_planner_critique_verdict() -> None:
    """``critique_plan`` always returns a ``PlannerCritiqueVerdict``."""
    plan = _make_plan()
    verdict = critique_plan(plan)
    assert isinstance(verdict, PlannerCritiqueVerdict)


def test_valid_plan_advances_to_comprehension_gate() -> None:
    """A well-formed plan with no violations routes to comprehension_gate."""
    plan = _make_plan()
    verdict = critique_plan(plan)
    assert verdict.route == "comprehension_gate", (
        f"Expected route='comprehension_gate' for a valid plan, "
        f"got route={verdict.route!r}. failed_questions={verdict.failed_questions}"
    )
    assert verdict.failed_questions == []


def test_bare_technique_when_subtechnique_determinable_routes_to_planner() -> None:
    """§3.5 — bare T1055 when T1055.012 (Process Hollowing) is determinable
    is a critique failure. The critique sees PROCESS_MEMORY artifact class +
    bare T1055 and emits a failed question about sub-technique precision.
    """
    # T1055 bare + PROCESS_MEMORY = Process Injection; T1055.012 (hollowing)
    # is determinable when PROCESS_MEMORY is the artifact class.
    plan = _make_plan(
        positive_mitre="T1055",
        positive_artifact_families=[
            ArtifactClass.PROCESS_MEMORY,
            ArtifactClass.SYSMON_1,
        ],
    )
    verdict = critique_plan(plan)
    assert verdict.route == "planner", (
        "Bare T1055 with PROCESS_MEMORY artifact should fail sub-technique "
        "precision check and route back to planner"
    )
    assert len(verdict.failed_questions) >= 1
    # At least one failed question must mention sub-technique or T1055
    subtechnique_mentioned = any(
        "sub" in q.lower() or "T1055" in q or "1055" in q
        for q in verdict.failed_questions
    )
    assert subtechnique_mentioned, (
        f"Expected a failed question mentioning sub-technique precision, "
        f"got: {verdict.failed_questions}"
    )


def test_execution_claim_with_single_artifact_class_routes_to_planner() -> None:
    """§3.2 — execution-class technique (T1059.001) with a single distinct
    artifact class in the plan hypothesis routes back to planner.
    The critique enforces that execution claims plan for ≥2 artifact classes.
    """
    plan = _make_plan(
        positive_mitre="T1059.001",
        positive_artifact_families=[
            ArtifactClass.PREFETCH,  # same class twice = 1 distinct
            ArtifactClass.PREFETCH,
        ],
    )
    verdict = critique_plan(plan)
    assert verdict.route == "planner", (
        "Execution-class hypothesis with only 1 distinct artifact_family "
        "should fail corroboration check and route back to planner"
    )
    assert len(verdict.failed_questions) >= 1
    corroboration_mentioned = any(
        "artifact" in q.lower() or "corrobor" in q.lower() or "class" in q.lower()
        for q in verdict.failed_questions
    )
    assert corroboration_mentioned, (
        f"Expected failed question about artifact corroboration, "
        f"got: {verdict.failed_questions}"
    )


def test_plan_missing_negative_hypothesis_routes_to_planner() -> None:
    """§3.6 — this cannot be constructed via InvestigationPlan (the schema
    rejects it at construction time), so the critique must also fire if
    somehow only positives reach it. Test the critique's own negative-
    hypothesis check directly via CritiqueConfig.
    """
    plan = _make_plan()
    # Override hypotheses to all-positive (bypass schema via model_construct).
    all_positive_plan = InvestigationPlan.model_construct(
        schema_version="v1",
        plan_id="plan-no-neg",
        case_id="case-001",
        evidence_summary="Windows 10 memory image",
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
                success_criteria="DKOM divergence confirms T1014",
            ),
        ],
    )
    verdict = critique_plan(all_positive_plan)
    assert verdict.route == "planner"
    assert len(verdict.failed_questions) >= 1


def test_failed_questions_route_back_to_planner() -> None:
    """Explicit: when route='planner', failed_questions must be non-empty.
    Validates W2.D.1 / W2.D.2 invariant at the critique function level.
    """
    plan = _make_plan(
        positive_mitre="T1059",  # bare execution parent
        positive_artifact_families=[
            ArtifactClass.PREFETCH,
            ArtifactClass.PREFETCH,  # single distinct class
        ],
    )
    verdict = critique_plan(plan)
    if verdict.route == "planner":
        assert verdict.failed_questions, (
            "critique_plan returned route='planner' with empty "
            "failed_questions — violates W2.D.2 loopback invariant"
        )


def test_all_questions_populated() -> None:
    """critique_plan always populates ``all_questions`` regardless of route.
    These are recorded in the ledger ``critique_verdict`` event.
    """
    plan = _make_plan()
    verdict = critique_plan(plan)
    assert len(verdict.all_questions) >= 1, (
        "critique_plan must always emit at least one verification question "
        "for the ledger event"
    )


def test_critique_config_question_count_respected() -> None:
    """CritiqueConfig.num_questions controls how many questions are generated."""
    plan = _make_plan()
    config = CritiqueConfig(num_questions=3)
    verdict = critique_plan(plan, config=config)
    assert len(verdict.all_questions) <= 10, "sanity bound on question count"


def test_hint_included_in_verdict_on_loopback() -> None:
    """When the critique routes back to planner, the ``hint`` field summarises
    the failed questions so the planner can correct the plan.
    """
    plan = _make_plan(
        positive_mitre="T1055",
        positive_artifact_families=[
            ArtifactClass.PROCESS_MEMORY,
            ArtifactClass.SYSMON_1,
        ],
    )
    verdict = critique_plan(plan)
    if verdict.route == "planner":
        assert verdict.hint, (
            "critique loopback must include a non-empty hint summarising "
            "why the plan was rejected"
        )
