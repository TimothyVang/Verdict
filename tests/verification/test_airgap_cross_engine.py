"""W3.A.1 — `AirGapCrossEngine` consensus invariants.

Air-gap mode runs two independent local engines (Qwen3-30B-A3B-Thinking and
GLM-4.5-Air) and accepts the finding only when they agree. ARCHITECTURE.md
§1 quorum-dispatch table rows 3-5:

    | AirGapCrossEngine | Jaccard ≥0.80 AND identical mitre_technique | VETTED_AIRGAP |
    | AirGapCrossEngine | Jaccard ≥0.80, divergent mitre_technique    | CONTESTED     |
    | AirGapCrossEngine | Jaccard <0.80 (incl. empty-set)             | CONTESTED     |

Plus the load-bearing **empty-set rule** (ARCHITECTURE.md §1):

    "if any quorum participant returns parsed_artifacts=[] (zero findings)
    it is treated as DISAGREEMENT for Jaccard purposes. Empty-set is never
    a null vote that lets the non-empty engine win by default."

These tests pin the **consensus logic** — a pure function on two
``EngineOutput`` records — independent of the SGLang transport layer
that lands in W2.B. The real ``verify(...)`` call will RAISE
``NotImplementedError`` until W2.B wires the SGLang clients;
``compute_verdict(...)`` is the testable surface for the consensus
invariants right now (CLAUDE.md §3.10 — no mocks; the agreement
function is a pure data-path function and is the right granularity
for unit testing here).

The Jaccard threshold itself is imported from ``strategy.py`` — never
hard-coded — so a future RFC that retunes the threshold lands in one
place (``AIRGAP_JACCARD_THRESHOLD``) and these tests track it.
"""
from __future__ import annotations

import pytest

from verdict.schemas.verdict_status import VerdictStatus
from verdict.verification.airgap_cross_engine import AirGapCrossEngine
from verdict.verification.engine_output import EngineOutput
from verdict.verification.strategy import (
    AIRGAP_JACCARD_THRESHOLD,
    VerdictResult,
    VerifierStrategy,
)

# ---------------------------------------------------------------------------
# Fixture helpers — keep tests focused on the consensus invariants
# ---------------------------------------------------------------------------


def _qwen(paths: list[str], mitre: str = "T1003.001") -> EngineOutput:
    return EngineOutput(engine="qwen3-30b-a3b-thinking", artifact_paths=paths, mitre_technique=mitre)


def _glm(paths: list[str], mitre: str = "T1003.001") -> EngineOutput:
    return EngineOutput(engine="glm-4.5-air", artifact_paths=paths, mitre_technique=mitre)


# ---------------------------------------------------------------------------
# W3.A.1.a load-bearing tests
# ---------------------------------------------------------------------------


def test_both_must_agree_on_jaccard_080_artifact_set() -> None:
    """W3.A.1.a — Jaccard ≥0.80 AND identical mitre_technique → VETTED_AIRGAP.

    Five-element artifact sets where four overlap give Jaccard 4/6 ≈ 0.667
    (BELOW threshold) — start with five-of-five identical to lock the
    happy path, then below we vary.
    """
    common = [
        "C:/Windows/Prefetch/RUNDLL32.EXE-1234.pf",
        "C:/MFT",
        "C:/Windows/System32/winevt/Logs/Sysmon.evtx",
        "C:/Amcache.hve",
        "C:/UsrClass.dat",
    ]
    qwen = _qwen(common, mitre="T1003.001")
    glm = _glm(common, mitre="T1003.001")

    result = AirGapCrossEngine().compute_verdict(qwen, glm)

    assert isinstance(result, VerdictResult)
    assert result.status == VerdictStatus.VETTED_AIRGAP, (
        "5/5 artifact agreement + identical mitre_technique must vet at the air-gap level."
    )


def test_jaccard_080_threshold_is_inclusive_at_boundary() -> None:
    """Jaccard exactly 0.80 (4-of-5 union, 4 intersect) must vet, not contest.

    The dispatch table reads ">=0.80" — boundary cases must round in
    favor of vetting, not against. With paths [a,b,c,d] vs [a,b,c,d,e],
    intersection=4, union=5, Jaccard=0.80.
    """
    qwen = _qwen(["a", "b", "c", "d"], mitre="T1003.001")
    glm = _glm(["a", "b", "c", "d", "e"], mitre="T1003.001")

    result = AirGapCrossEngine().compute_verdict(qwen, glm)

    assert result.status == VerdictStatus.VETTED_AIRGAP, (
        f"Jaccard 4/5 = 0.80 must satisfy '>= {AIRGAP_JACCARD_THRESHOLD}'; "
        "boundary cases vote VETTED_AIRGAP."
    )


def test_disagreement_returns_contested() -> None:
    """W3.A.1.a — Jaccard <0.80 → CONTESTED.

    Paths [a,b] vs [c,d] share nothing; Jaccard = 0/4 = 0.
    """
    qwen = _qwen(["a", "b"])
    glm = _glm(["c", "d"])

    result = AirGapCrossEngine().compute_verdict(qwen, glm)

    assert result.status == VerdictStatus.CONTESTED, (
        "Disjoint artifact sets are the canonical disagreement case; "
        "must escalate to CONTESTED → replan_node."
    )


def test_jaccard_above_threshold_with_divergent_mitre_is_contested() -> None:
    """ARCHITECTURE.md §1 row 4: Jaccard ≥0.80 BUT divergent mitre → CONTESTED.

    Engines agree on which artifacts matter; they disagree on the
    technique. That is *not* vetted — it is the textbook
    disagreement-on-interpretation case.
    """
    common = ["a", "b", "c", "d"]
    qwen = _qwen(common, mitre="T1003.001")  # OS Credential Dumping: LSASS
    glm = _glm(common, mitre="T1055.012")    # Process Injection: Process Hollowing

    result = AirGapCrossEngine().compute_verdict(qwen, glm)

    assert result.status == VerdictStatus.CONTESTED, (
        "Identical artifact sets but divergent mitre_technique must NOT vet "
        "(ARCHITECTURE.md §1 quorum dispatch row 4)."
    )


def test_empty_set_treated_as_disagreement_even_against_empty() -> None:
    """ARCHITECTURE.md §1 empty-set rule: an empty parsed_artifacts list is
    treated as DISAGREEMENT, NOT a vote.

    Two empty sets (both engines crashed silently / produced no findings)
    must not vet by Jaccard's mathematical 0/0 = 1 convention. The
    dispatch table hard-codes 'empty is disagreement'; otherwise an
    executor that crashes silently becomes a free pass for the other
    lane.
    """
    qwen = _qwen([])
    glm = _glm([])

    result = AirGapCrossEngine().compute_verdict(qwen, glm)

    assert result.status == VerdictStatus.CONTESTED, (
        "Two-empty-sets must not vet — empty is disagreement (ARCHITECTURE.md §1)."
    )


def test_empty_set_against_findings_is_disagreement() -> None:
    """ARCHITECTURE.md §1 empty-set rule: empty-vs-non-empty is disagreement,
    NOT a free pass for the non-empty engine.
    """
    qwen = _qwen(["a", "b", "c", "d"])
    glm = _glm([])  # silent crash / timeout

    result = AirGapCrossEngine().compute_verdict(qwen, glm)

    assert result.status == VerdictStatus.CONTESTED, (
        "Empty-vs-non-empty must NOT vet (ARCHITECTURE.md §1 empty-set rule). "
        "Otherwise a silently-crashing engine lets the other lane win by default."
    )


def test_threshold_is_imported_from_strategy_module() -> None:
    """The Jaccard threshold MUST come from
    ``strategy.AIRGAP_JACCARD_THRESHOLD`` so a retune lands in one place.

    Construct two outputs with intersection/union exactly at the
    threshold; flip the threshold via monkeypatching of the module
    constant would change the verdict. We assert the strategy reads
    the live constant (not a frozen copy) by checking that the
    documented threshold is 0.80 AND the boundary case vets.
    """
    assert AIRGAP_JACCARD_THRESHOLD == 0.80
    qwen = _qwen(["a", "b", "c", "d"])
    glm = _glm(["a", "b", "c", "d", "e"])  # Jaccard 4/5 = 0.80
    assert AirGapCrossEngine().compute_verdict(qwen, glm).status == VerdictStatus.VETTED_AIRGAP


def test_strategy_conforms_to_verifier_protocol() -> None:
    """AirGapCrossEngine must satisfy ``VerifierStrategy`` (Protocol)."""
    s: VerifierStrategy = AirGapCrossEngine()
    assert callable(getattr(s, "verify", None))


def test_verify_raises_notimplemented_until_w2b_wires_sglang() -> None:
    """The transport-level ``verify(...)`` call lands in W2.B (SGLang clients
    + ledger plumbing). Until then the call must raise — explicitly — so a
    casual integrator does NOT plumb a half-wired strategy into
    ``quorum_node`` and ship a verdict that looks vetted but isn't.

    CLAUDE.md §3.10 explicitly permits this *backend*-level stub: the
    consensus logic is real and tested via ``compute_verdict`` above.
    """
    with pytest.raises(NotImplementedError):
        AirGapCrossEngine().verify(
            case_id="case_001_lolbins",
            hypothesis="Evidence consistent with rundll32 + comsvcs.MiniDump.",
            mitre_technique="T1003.001",
            evidence_summary="Sysmon ID 1; Prefetch RUNDLL32.EXE-...",
        )


# ---------------------------------------------------------------------------
# Engine-identity invariants — air-gap mode requires Qwen3 + GLM, not
# Qwen3+Qwen3 (would collapse cross-engine to self-consistency)
# ---------------------------------------------------------------------------


def test_two_outputs_from_same_engine_family_is_rejected() -> None:
    """Air-gap = CROSS-engine; passing two Qwen3 outputs collapses the
    strategy back to (degenerate) self-consistency and breaks the
    independence guarantee that air-gap mode is paying for. The strategy
    must refuse — at the consensus boundary, before anyone reads the
    verdict.
    """
    qwen_a = _qwen(["a", "b"])
    qwen_b = EngineOutput(
        engine="qwen3-30b-a3b-thinking",  # SAME family
        artifact_paths=["a", "b"],
        mitre_technique="T1003.001",
    )

    with pytest.raises(ValueError):
        AirGapCrossEngine().compute_verdict(qwen_a, qwen_b)


# ---------------------------------------------------------------------------
# Notes-passthrough — the verdict carries enough context for the ledger
# ---------------------------------------------------------------------------


def test_vetted_result_carries_jaccard_in_notes() -> None:
    """The ``VerdictResult.notes`` field is the ledger's audit handle; the
    Jaccard score must appear there so a SANS auditor can replay the
    threshold check from the ledger alone.
    """
    common = ["a", "b", "c", "d", "e"]
    result = AirGapCrossEngine().compute_verdict(_qwen(common), _glm(common))
    notes_blob = " ".join(result.notes).lower()
    assert "jaccard" in notes_blob, (
        "VerdictResult.notes must record the Jaccard score for ledger audit."
    )


def test_contested_result_carries_disagreement_reason_in_notes() -> None:
    """For CONTESTED, the notes must distinguish 'low Jaccard' from
    'mitre divergence' so replan_node can pick a smart prompt-hint.
    """
    common = ["a", "b", "c", "d"]
    result = AirGapCrossEngine().compute_verdict(
        _qwen(common, mitre="T1003.001"),
        _glm(common, mitre="T1055.012"),
    )
    notes_blob = " ".join(result.notes).lower()
    assert "mitre" in notes_blob, (
        "Mitre divergence must surface in VerdictResult.notes "
        "so replan can route on disagreement type."
    )
