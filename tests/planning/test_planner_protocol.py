"""Planner Protocol contract — W2.A.1 / W1.G.5.

Asserts the `Planner` Protocol shape, that `CloudPlanner` and `LocalPlanner`
satisfy it via structural typing, and that the schemas the Protocol returns
enforce CLAUDE.md §3.5 (MITRE sub-technique precision) and §3.6 (negative
hypothesis quality).

The `plan()` body itself raises NotImplementedError until W2.A.2 wires the
real inference backends — this is intentional and called out in §3.10 as the
acceptable "scaffolded but not stubbed" pattern. We still require:

  - the Protocol shape to be real (runtime_checkable, correct method),
  - the constructors to validate their config (Pydantic),
  - the data classes returned by `plan()` to enforce the §3.5 / §3.6
    invariants now, so the day W2.A.2 lands a real backend, every fault
    path is already a hard test failure.

No mocks of `verdict.*` per §3.10. No `httpx_mock` / `responses` /
`unittest.mock` against verdict internals.
"""

from __future__ import annotations

import inspect
from typing import Protocol, get_type_hints

import pytest
from pydantic import ValidationError

from verdict.planning.planner import (
    CloudPlanner,
    LocalPlanner,
    Planner,
)
from verdict.planning.types import (
    EvidenceManifest,
    Hypothesis,
    InvestigationPlan,
    Mode,
)


# ---------------------------------------------------------------------------
# Protocol shape
# ---------------------------------------------------------------------------


def test_planner_is_runtime_checkable_protocol() -> None:
    """`Planner` MUST be a runtime-checkable Protocol so isinstance() works."""
    assert issubclass(Planner, Protocol), "Planner must be a typing.Protocol"
    # runtime_checkable Protocols carry _is_runtime_protocol = True
    assert getattr(Planner, "_is_runtime_protocol", False), (
        "Planner Protocol must be decorated @runtime_checkable so swarm code "
        "can check isinstance(impl, Planner) at gateway init"
    )


def test_planner_protocol_declares_plan_method() -> None:
    """Protocol must declare `plan(case_id, evidence_manifest, mode) -> InvestigationPlan`."""
    assert hasattr(Planner, "plan"), "Planner Protocol missing `plan` method"
    sig = inspect.signature(Planner.plan)
    params = list(sig.parameters.keys())
    # `self` plus three positional/keyword args.
    assert params == ["self", "case_id", "evidence_manifest", "mode"], (
        f"Planner.plan signature drift: got {params}; "
        "expected [self, case_id, evidence_manifest, mode]"
    )
    hints = get_type_hints(Planner.plan)
    assert hints.get("case_id") is str
    assert hints.get("evidence_manifest") is EvidenceManifest
    assert hints.get("mode") is Mode
    assert hints.get("return") is InvestigationPlan


# ---------------------------------------------------------------------------
# CloudPlanner / LocalPlanner satisfy the Protocol structurally
# ---------------------------------------------------------------------------


def test_cloud_planner_satisfies_protocol() -> None:
    p = CloudPlanner(api_key="sk-ant-test-fake-not-used-until-w2a2", model="claude-opus-4-7")
    assert isinstance(p, Planner), "CloudPlanner must structurally satisfy Planner"


def test_local_planner_satisfies_protocol() -> None:
    p = LocalPlanner(sglang_base_url="http://127.0.0.1:30000", model_path="/models/qwen3")
    assert isinstance(p, Planner), "LocalPlanner must structurally satisfy Planner"


# ---------------------------------------------------------------------------
# Constructor argument validation (Pydantic)
# ---------------------------------------------------------------------------


def test_cloud_planner_rejects_empty_api_key() -> None:
    with pytest.raises(ValidationError):
        CloudPlanner(api_key="", model="claude-opus-4-7")


def test_local_planner_rejects_invalid_sglang_url() -> None:
    with pytest.raises(ValidationError):
        LocalPlanner(sglang_base_url="not-a-url", model_path="/models/qwen3")


# ---------------------------------------------------------------------------
# Mode-awareness — CloudPlanner refuses AIRGAP, LocalPlanner refuses CLOUD.
# Mode dispatch lives in `verdict/runtime/mode_detect.py` (W1.G.5.a contract);
# the planner classes only enforce that they accept compatible modes.
# ---------------------------------------------------------------------------


def _evidence_stub() -> EvidenceManifest:
    """Build a minimal EvidenceManifest so we can exercise plan() routing.

    No mocks of verdict.* — this is a real EvidenceManifest constructed from
    real Pydantic types in `verdict.planning.types`.
    """
    return EvidenceManifest(
        case_id="case-w2a-protocol-001",
        evidence_paths=["/evidence/memory.mem"],
        evidence_hashes={"/evidence/memory.mem": "0" * 64},
    )


def test_cloud_planner_refuses_airgap_mode() -> None:
    p = CloudPlanner(api_key="sk-ant-test-fake-not-used-until-w2a2", model="claude-opus-4-7")
    with pytest.raises(ValueError, match=r"(?i)mode|airgap|backend"):
        p.plan(
            case_id="case-w2a-protocol-002",
            evidence_manifest=_evidence_stub(),
            mode=Mode.AIRGAP,
        )


def test_local_planner_refuses_cloud_only_mode() -> None:
    p = LocalPlanner(sglang_base_url="http://127.0.0.1:30000", model_path="/models/qwen3")
    with pytest.raises(ValueError, match=r"(?i)mode|cloud|backend"):
        p.plan(
            case_id="case-w2a-protocol-003",
            evidence_manifest=_evidence_stub(),
            mode=Mode.CLOUD,
        )


def test_planner_plan_body_is_not_implemented_yet() -> None:
    """W2.A.2 lands the real inference call; W2.A.1 only commits to the contract.

    A NotImplementedError on the inference path is the §3.10-compliant
    skeleton: the *protocol* is real, only the unfinished backend call
    raises. No mocks, no canned data.
    """
    p = CloudPlanner(api_key="sk-ant-test-fake-not-used-until-w2a2", model="claude-opus-4-7")
    with pytest.raises(NotImplementedError, match=r"W2\.A\.2"):
        p.plan(
            case_id="case-w2a-protocol-004",
            evidence_manifest=_evidence_stub(),
            mode=Mode.CLOUD,
        )

    q = LocalPlanner(sglang_base_url="http://127.0.0.1:30000", model_path="/models/qwen3")
    with pytest.raises(NotImplementedError, match=r"W2\.A\.2"):
        q.plan(
            case_id="case-w2a-protocol-005",
            evidence_manifest=_evidence_stub(),
            mode=Mode.AIRGAP,
        )


# ---------------------------------------------------------------------------
# §3.5 — MITRE sub-technique regex enforced on Hypothesis.mitre_technique
# ---------------------------------------------------------------------------


def test_mitre_subtechnique_T1055_012_accepted() -> None:
    h = Hypothesis(
        id="h1",
        polarity="positive",
        mitre_technique="T1055.012",
        artifact_families=["process_memory"],
        success_criteria="Process hollowing observed in vol3.malfind output.",
    )
    assert h.mitre_technique == "T1055.012"


def test_mitre_bare_parent_T1014_accepted() -> None:
    """`T1014` Rootkit has no sub-technique upstream — bare form is OK."""
    h = Hypothesis(
        id="h2",
        polarity="positive",
        mitre_technique="T1014",
        artifact_families=["process_memory"],
        success_criteria="DKOM divergence between pslist and psscan.",
    )
    assert h.mitre_technique == "T1014"


def test_mitre_invalid_format_rejected() -> None:
    with pytest.raises(ValidationError):
        Hypothesis(
            id="h3",
            polarity="positive",
            mitre_technique="T1055.0",  # 1-digit sub-tech -> invalid
            artifact_families=["process_memory"],
            success_criteria="bogus",
        )


def test_mitre_lowercase_rejected() -> None:
    with pytest.raises(ValidationError):
        Hypothesis(
            id="h4",
            polarity="positive",
            mitre_technique="t1055.012",
            artifact_families=["process_memory"],
            success_criteria="bogus",
        )


# ---------------------------------------------------------------------------
# §3.6 — Negative hypothesis quality is enforced at the schema layer.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "criteria",
    ["cosmic rays", "alien intervention", "nothing here", "not-relevant", "n-a"],
)
def test_negative_hypothesis_denylist_rejects_degenerate(criteria: str) -> None:
    with pytest.raises(ValidationError):
        Hypothesis(
            id="hneg",
            polarity="negative",
            mitre_technique="T1059.001",
            artifact_families=["evtx_4688"],
            success_criteria=criteria,
        )


def test_negative_hypothesis_requires_mitre_technique() -> None:
    with pytest.raises(ValidationError):
        Hypothesis(
            id="hneg",
            polarity="negative",
            mitre_technique=None,
            artifact_families=["evtx_4688"],
            success_criteria="No PowerShell execution observed in the EVTX channel.",
        )


def test_negative_hypothesis_requires_nonempty_artifact_families() -> None:
    with pytest.raises(ValidationError):
        Hypothesis(
            id="hneg",
            polarity="negative",
            mitre_technique="T1059.001",
            artifact_families=[],
            success_criteria="No PowerShell execution observed in the EVTX channel.",
        )


# ---------------------------------------------------------------------------
# §3.6 — Every InvestigationPlan must include ≥1 negative hypothesis.
# ---------------------------------------------------------------------------


def test_investigation_plan_requires_at_least_one_negative_hypothesis() -> None:
    pos = Hypothesis(
        id="h1",
        polarity="positive",
        mitre_technique="T1055.012",
        artifact_families=["process_memory"],
        success_criteria="Process hollowing observed in vol3.malfind output.",
    )
    with pytest.raises(ValidationError):
        InvestigationPlan(
            case_id="case-x",
            hypotheses=[pos],
            tool_budget=10,
            success_criteria="Confirm or refute T1055.012.",
        )


def test_investigation_plan_accepts_one_positive_one_negative() -> None:
    pos = Hypothesis(
        id="h1",
        polarity="positive",
        mitre_technique="T1055.012",
        artifact_families=["process_memory"],
        success_criteria="Process hollowing observed in vol3.malfind output.",
    )
    neg = Hypothesis(
        id="h2",
        polarity="negative",
        mitre_technique="T1059.001",
        artifact_families=["evtx_4688"],
        success_criteria="No PowerShell child of explorer.exe in EVTX 4688.",
    )
    plan = InvestigationPlan(
        case_id="case-x",
        hypotheses=[pos, neg],
        tool_budget=10,
        success_criteria="Confirm or refute T1055.012.",
    )
    assert len(plan.hypotheses) == 2
    assert sum(1 for h in plan.hypotheses if h.polarity == "negative") >= 1
