"""W3.A.2 — `DualLaneCrossEngine` consensus invariants.

Dual mode (CLAUDE.md §1; ARCHITECTURE.md §1 row 4) runs THREE engines in
parallel — cloud (Claude), Qwen3, GLM — and accepts the finding only
under the conjunctive rule:

    cloud agrees with ≥1 local AND locals agree with each other.

Both clauses are required (CLAUDE.md §8). The second clause is captured
in ``DUAL_REQUIRES_LOCALS_AGREE`` — flipping that flag would silently
weaken dual-mode verification to the air-gap rule on the local pair,
discarding the cloud lane's vote.

ARCHITECTURE.md §1 quorum-dispatch table rows 6-8:

| Engine outcome                                              | VerdictStatus |
|-------------------------------------------------------------|---------------|
| cloud agrees with ≥1 local AND locals agree with each other | VETTED_DUAL   |
| cloud disagrees with both locals                            | CONTESTED     |
| cloud agrees with 1 local, locals disagree with each other  | CONTESTED     |

"Agree" is the same predicate as in air-gap mode: identical
``mitre_technique`` AND Jaccard(``artifact_paths``) ≥ ``AIRGAP_JACCARD_THRESHOLD``.
Reusing the threshold means dual mode is "air-gap quorum on each pair
plus a cloud-anchor requirement" — one knob, one place.

Empty-set rule (ARCHITECTURE.md §1) carries: any participant with empty
artifacts is treated as DISAGREEMENT for every pairwise comparison
involving it.

The transport-level ``verify(...)`` raises ``NotImplementedError`` until
W2.B wires the cloud Claude client + the two SGLang clients
(CLAUDE.md §3.10 — backend stub permitted; consensus logic is real and
tested via ``compute_verdict``).
"""
from __future__ import annotations

import pytest

from verdict.schemas.verdict_status import VerdictStatus
from verdict.verification.dual_lane_cross_engine import DualLaneCrossEngine
from verdict.verification.engine_output import EngineOutput
from verdict.verification.strategy import (
    DUAL_REQUIRES_LOCALS_AGREE,
    VerdictResult,
    VerifierStrategy,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

CRED_ACCESS = "T1003.001"
PROC_INJECT = "T1055.012"


def _cloud(paths: list[str], mitre: str = CRED_ACCESS) -> EngineOutput:
    return EngineOutput(engine="claude-opus-4-5", artifact_paths=paths, mitre_technique=mitre)


def _qwen(paths: list[str], mitre: str = CRED_ACCESS) -> EngineOutput:
    return EngineOutput(
        engine="qwen3-30b-a3b-thinking", artifact_paths=paths, mitre_technique=mitre
    )


def _glm(paths: list[str], mitre: str = CRED_ACCESS) -> EngineOutput:
    return EngineOutput(engine="glm-4.5-air", artifact_paths=paths, mitre_technique=mitre)


# ---------------------------------------------------------------------------
# Happy path — all three agree
# ---------------------------------------------------------------------------


def test_three_way_agreement_vets_dual() -> None:
    """W3.A.2.a — all three engines emit identical artifact set + mitre.

    Cloud agrees with both locals; locals agree with each other; the
    conjunctive rule is satisfied → VETTED_DUAL.
    """
    common = ["a", "b", "c", "d"]
    result = DualLaneCrossEngine().compute_verdict(
        cloud=_cloud(common),
        qwen=_qwen(common),
        glm=_glm(common),
    )
    assert isinstance(result, VerdictResult)
    assert result.status == VerdictStatus.VETTED_DUAL


# ---------------------------------------------------------------------------
# Cloud-anchor rule — cloud must agree with ≥1 local
# ---------------------------------------------------------------------------


def test_cloud_agrees_with_one_local_and_locals_agree_vets_dual() -> None:
    """ARCHITECTURE.md §1 row 6 — only the conjunctive rule matters.

    Cloud + Qwen agree; GLM has slightly more artifacts but Jaccard ≥ 0.80
    against both cloud and Qwen, so locals also agree. → VETTED_DUAL.
    """
    cloud = _cloud(["a", "b", "c", "d"])
    qwen = _qwen(["a", "b", "c", "d"])
    glm = _glm(["a", "b", "c", "d", "e"])  # Jaccard 4/5 = 0.80 vs both
    result = DualLaneCrossEngine().compute_verdict(cloud=cloud, qwen=qwen, glm=glm)
    assert result.status == VerdictStatus.VETTED_DUAL


def test_cloud_disagrees_with_both_locals_is_contested() -> None:
    """ARCHITECTURE.md §1 row 7 — cloud vs both-locals divergence."""
    cloud = _cloud(["x", "y", "z"], mitre=CRED_ACCESS)
    qwen = _qwen(["a", "b", "c"], mitre=CRED_ACCESS)
    glm = _glm(["a", "b", "c"], mitre=CRED_ACCESS)
    # locals agree (identical), but cloud Jaccard = 0/6 = 0 with each local.
    result = DualLaneCrossEngine().compute_verdict(cloud=cloud, qwen=qwen, glm=glm)
    assert result.status == VerdictStatus.CONTESTED


def test_cloud_agrees_with_one_local_but_locals_disagree_is_contested() -> None:
    """ARCHITECTURE.md §1 row 8 — DUAL_REQUIRES_LOCALS_AGREE.

    The most subtle case. Cloud + Qwen agree on a credential-access
    finding; GLM disagrees on artifacts entirely. Without the
    locals-agree clause, cloud-vs-1-local would vet — and a DUAL
    verdict that doesn't actually require both locals to agree would
    silently degrade to "cloud + cherry-picked local". The flag
    ``DUAL_REQUIRES_LOCALS_AGREE`` is the load-bearing guard.
    """
    common = ["a", "b", "c", "d"]
    cloud = _cloud(common)
    qwen = _qwen(common)  # agrees with cloud
    glm = _glm(["x", "y", "z", "w"])  # disagrees with both
    result = DualLaneCrossEngine().compute_verdict(cloud=cloud, qwen=qwen, glm=glm)
    assert result.status == VerdictStatus.CONTESTED, (
        "cloud-agrees-with-1-local-but-locals-disagree must be CONTESTED. "
        "DUAL_REQUIRES_LOCALS_AGREE is the load-bearing second clause; "
        "without it, dual-mode silently degrades to 'cloud + cherry-picked local'."
    )


# ---------------------------------------------------------------------------
# Mitre-technique divergence (same paths, different technique)
# ---------------------------------------------------------------------------


def test_locals_agree_on_artifacts_but_disagree_on_mitre_is_contested() -> None:
    """All three engines cite the same artifact set, but the locals call
    different MITRE techniques. Cloud agrees with one local on
    technique; locals disagree with each other on technique. Locals-
    agree clause fails → CONTESTED.
    """
    common = ["a", "b", "c", "d"]
    cloud = _cloud(common, mitre=CRED_ACCESS)
    qwen = _qwen(common, mitre=CRED_ACCESS)  # agrees with cloud
    glm = _glm(common, mitre=PROC_INJECT)  # disagrees with cloud + qwen
    result = DualLaneCrossEngine().compute_verdict(cloud=cloud, qwen=qwen, glm=glm)
    assert result.status == VerdictStatus.CONTESTED


def test_cloud_disagrees_on_mitre_only_is_contested() -> None:
    """All three cite the same artifact set; locals agree on technique;
    cloud disagrees on technique. Cloud-vs-locals fails on the mitre
    side → CONTESTED.
    """
    common = ["a", "b", "c", "d"]
    cloud = _cloud(common, mitre=PROC_INJECT)  # alone on technique
    qwen = _qwen(common, mitre=CRED_ACCESS)
    glm = _glm(common, mitre=CRED_ACCESS)
    result = DualLaneCrossEngine().compute_verdict(cloud=cloud, qwen=qwen, glm=glm)
    assert result.status == VerdictStatus.CONTESTED


# ---------------------------------------------------------------------------
# Empty-set rule (ARCHITECTURE.md §1) — empty == DISAGREEMENT for every pair
# ---------------------------------------------------------------------------


def test_empty_cloud_against_agreeing_locals_is_contested() -> None:
    """Cloud crashes silently (empty artifacts). Even if locals agree
    perfectly, empty-vs-anything is DISAGREEMENT, so cloud-vs-each-local
    fails → cloud has no agreement-anchor → CONTESTED.

    This is the dual-mode flavor of the air-gap empty-set rule. A
    silently-failing cloud lane must NOT let the locals carry a vetted
    verdict — that would require the strategy be DualLane*OR*AirGap,
    not DualLane.
    """
    cloud = _cloud([])
    common = ["a", "b", "c", "d"]
    qwen = _qwen(common)
    glm = _glm(common)
    result = DualLaneCrossEngine().compute_verdict(cloud=cloud, qwen=qwen, glm=glm)
    assert result.status == VerdictStatus.CONTESTED


def test_empty_one_local_blocks_locals_agree_clause() -> None:
    """If one local is empty, locals-agree fails (empty == disagreement),
    so even cloud-vs-other-local agreement cannot vet → CONTESTED.
    """
    common = ["a", "b", "c", "d"]
    cloud = _cloud(common)
    qwen = _qwen(common)
    glm = _glm([])  # silent crash
    result = DualLaneCrossEngine().compute_verdict(cloud=cloud, qwen=qwen, glm=glm)
    assert result.status == VerdictStatus.CONTESTED


# ---------------------------------------------------------------------------
# Constant + Protocol invariants
# ---------------------------------------------------------------------------


def test_dual_requires_locals_agree_flag_is_consulted() -> None:
    """DualLaneCrossEngine MUST read DUAL_REQUIRES_LOCALS_AGREE from
    strategy.py — not embed True as a literal. The flag is the single
    source of truth (CLAUDE.md §8 / W1.C.3).

    We assert the flag is True AND that the strategy refuses
    cloud-agrees-with-1-local-only (which would vet under flag=False).
    """
    assert DUAL_REQUIRES_LOCALS_AGREE is True
    common = ["a", "b", "c", "d"]
    result = DualLaneCrossEngine().compute_verdict(
        cloud=_cloud(common),
        qwen=_qwen(common),
        glm=_glm(["x", "y", "z", "w"]),  # locals disagree
    )
    assert result.status == VerdictStatus.CONTESTED


def test_strategy_conforms_to_verifier_protocol() -> None:
    """DualLaneCrossEngine must satisfy the VerifierStrategy Protocol."""
    s: VerifierStrategy = DualLaneCrossEngine()
    assert callable(getattr(s, "verify", None))


def test_verify_raises_notimplemented_until_w2b_wires_clients() -> None:
    """Transport-level verify lands in W2.B (cloud Claude + two SGLang
    clients + ledger plumbing). Until then the call must raise — so a
    casual integrator does NOT plumb a half-wired strategy into
    quorum_node and ship a verdict that looks vetted but isn't.

    CLAUDE.md §3.10 backend-level stub permission applies; consensus
    logic is exercised via compute_verdict.
    """
    with pytest.raises(NotImplementedError):
        DualLaneCrossEngine().verify(
            case_id="case_001_lolbins",
            hypothesis="Evidence consistent with rundll32 + comsvcs.MiniDump.",
            mitre_technique=CRED_ACCESS,
            evidence_summary="Sysmon ID 1; Prefetch RUNDLL32.EXE-...",
        )


# ---------------------------------------------------------------------------
# Engine-identity invariants
# ---------------------------------------------------------------------------


def test_two_locals_from_same_family_is_rejected() -> None:
    """Dual mode = cloud + TWO different local engines. Passing two
    Qwen3 locals collapses the locals-agree clause to self-consistency
    and breaks the cross-family independence guarantee on the local
    side.
    """
    common = ["a", "b", "c", "d"]
    qwen_a = _qwen(common)
    qwen_b = EngineOutput(
        engine="qwen3-30b-a3b-thinking",  # same family as qwen_a
        artifact_paths=common,
        mitre_technique=CRED_ACCESS,
    )
    with pytest.raises(ValueError):
        DualLaneCrossEngine().compute_verdict(
            cloud=_cloud(common), qwen=qwen_a, glm=qwen_b
        )


def test_cloud_position_must_be_cloud_family_not_local() -> None:
    """Defensive: passing a Qwen3 output in the ``cloud`` slot is a
    programming error at the dispatch layer; the strategy refuses
    rather than silently mislabelling the verdict.
    """
    common = ["a", "b", "c", "d"]
    not_cloud = _qwen(common)
    with pytest.raises(ValueError):
        DualLaneCrossEngine().compute_verdict(
            cloud=not_cloud, qwen=_qwen(common), glm=_glm(common)
        )


# ---------------------------------------------------------------------------
# Notes-passthrough — ledger audit
# ---------------------------------------------------------------------------


def test_vetted_dual_carries_three_engine_summary() -> None:
    """VerdictResult.notes must record all three engines so the ledger
    has the full audit handle.
    """
    common = ["a", "b", "c", "d"]
    result = DualLaneCrossEngine().compute_verdict(
        cloud=_cloud(common), qwen=_qwen(common), glm=_glm(common)
    )
    notes_blob = " ".join(result.notes).lower()
    assert "claude" in notes_blob and "qwen" in notes_blob and "glm" in notes_blob, (
        "VerdictResult.notes must surface all three engines for ledger audit."
    )


def test_contested_carries_clause_failure_reason() -> None:
    """When CONTESTED, the notes must say WHY (locals-disagree vs
    cloud-vs-locals) so replan_node can route on disagreement type.
    """
    common = ["a", "b", "c", "d"]
    result = DualLaneCrossEngine().compute_verdict(
        cloud=_cloud(common),
        qwen=_qwen(common),
        glm=_glm(["x", "y", "z", "w"]),  # locals disagree
    )
    notes_blob = " ".join(result.notes).lower()
    assert "local" in notes_blob, (
        "Contested-by-locals-disagreement must surface in notes."
    )
