"""W1.C.3 — `VerifierStrategy` Protocol + Universal Self-Consistency stub.

The quorum dispatch table (ARCHITECTURE.md §1) selects one of:

- ``CloudSelfConsistency``     (cloud-only mode; W1.C.2)
- ``AirGapCrossEngine``        (air-gap mode; W3.A.1)
- ``DualLaneCrossEngine``      (dual mode; W3.A.2)
- ``UniversalSelfConsistency`` (judge of last resort; W3.A.3 — stub here)

For the dispatch to be substitution-safe, every strategy must conform to a
``VerifierStrategy`` Protocol that returns a ``VerdictResult``. This file
locks the contract:

1. ``VerifierStrategy`` is a structural type with one method, ``verify``,
   returning a ``VerdictResult``.
2. ``VerdictResult`` carries a ``status: VerdictStatus`` (the canonical
   6-state enum from CLAUDE.md §3.6) plus engine-quorum metadata.
3. ``VerdictStatus`` has exactly the six members CLAUDE.md §3.6 mandates
   — no DRAFT_* leftovers from v4.5.
4. Mode-keyed constants (``AIRGAP_JACCARD_THRESHOLD``,
   ``DUAL_REQUIRES_LOCALS_AGREE``) are exported with the values
   CLAUDE.md §8 names. Future implementations of ``AirGapCrossEngine``
   and ``DualLaneCrossEngine`` (W3.A.1, W3.A.2) read these constants
   rather than embedding magic numbers.
5. ``UniversalSelfConsistency`` is a stub for W1.C.3 — full Chen 2023
   implementation lands in W3.A.3 — but it MUST already conform to
   the Protocol so the dispatch table can wire it as the
   judge-of-last-resort.
"""
from __future__ import annotations

import pytest

from verdict.schemas.verdict_status import VerdictStatus
from verdict.verification.strategy import (
    AIRGAP_JACCARD_THRESHOLD,
    DUAL_REQUIRES_LOCALS_AGREE,
    UniversalSelfConsistency,
    VerdictResult,
    VerifierStrategy,
)

# ---------------------------------------------------------------------------
# VerdictStatus enum (CLAUDE.md §3.6 — exactly six canonical states)
# ---------------------------------------------------------------------------


def test_verdict_status_has_exactly_six_canonical_states() -> None:
    """CLAUDE.md §3.6 lists exactly six. No DRAFT_*; no others."""
    expected = {
        "VETTED_CLOUD",
        "VETTED_AIRGAP",
        "VETTED_DUAL",
        "CONTESTED",
        "UNVERIFIABLE",
        "EXHAUSTED_REPLAN",
    }
    actual = {m.name for m in VerdictStatus}
    assert actual == expected, (
        f"VerdictStatus must have exactly the 6 CLAUDE.md §3.6 states. "
        f"missing: {expected - actual}; extra: {actual - expected}"
    )


# ---------------------------------------------------------------------------
# VerifierStrategy Protocol
# ---------------------------------------------------------------------------


def test_universal_self_consistency_conforms_to_protocol() -> None:
    """USC stub must already satisfy the Protocol (substitution-safe)."""
    s: VerifierStrategy = UniversalSelfConsistency()
    # The body is a stub (W1.C.3); the type-check at assignment time is
    # the load-bearing assertion.
    assert callable(getattr(s, "verify", None)), (
        "VerifierStrategy must expose a verify(...) method"
    )


def test_strategy_returns_verdict_result() -> None:
    """Post W3.A.3 — ``verify(..., candidates=...)`` returns a
    ``VerdictResult`` (delegating to ``judge``).

    The W1.C.3 stub returned a hardcoded ``VETTED_CLOUD``; W3.A.3
    replaces that with real substance-clustering. With a 2-of-3
    substance majority the result is a vetted ``VerdictResult``;
    with no candidates ``verify`` raises ``NotImplementedError``
    (covered by ``test_universal_self_consistency.py``). This test
    pins the Protocol-level "verify returns a VerdictResult"
    contract on the candidates-supplied path.
    """
    from verdict.verification.engine_output import EngineOutput

    common = ["a", "b"]
    candidates = [
        EngineOutput(engine="eng-a", artifact_paths=common, mitre_technique="T1003.001"),
        EngineOutput(engine="eng-b", artifact_paths=common, mitre_technique="T1003.001"),
        EngineOutput(engine="eng-c", artifact_paths=["x"], mitre_technique="T1059.001"),
    ]
    result = UniversalSelfConsistency().verify(
        case_id="case_001_lolbins",
        hypothesis="Evidence consistent with rundll32 invoking comsvcs.MiniDump.",
        mitre_technique="T1003.001",
        evidence_summary="Sysmon ID 1; Prefetch RUNDLL32.EXE-...",
        candidates=candidates,
    )
    assert isinstance(result, VerdictResult), (
        f"verify(...) must return VerdictResult, got {type(result).__name__}"
    )
    # 2-of-3 substance majority must NOT be CONTESTED.
    assert result.status != VerdictStatus.CONTESTED


def test_verdict_result_status_must_be_canonical() -> None:
    """VerdictResult cannot be constructed with a non-VerdictStatus status."""
    with pytest.raises((TypeError, ValueError)):
        # Passing a raw string instead of VerdictStatus is a programming
        # error and must surface at construction time.
        VerdictResult(status="bogus_status")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Mode-keyed constants (CLAUDE.md §8)
# ---------------------------------------------------------------------------


def test_airgap_jaccard_threshold_is_zero_eighty() -> None:
    """ARCHITECTURE.md §1 quorum table: AirGapCrossEngine -> Jaccard >=0.80."""
    assert AIRGAP_JACCARD_THRESHOLD == 0.80, (
        f"AIRGAP_JACCARD_THRESHOLD must be 0.80 (CLAUDE.md §8); "
        f"got {AIRGAP_JACCARD_THRESHOLD!r}"
    )


def test_dual_requires_locals_agree_flag_is_true() -> None:
    """CLAUDE.md §8: DualLaneCrossEngine -> 'cloud agrees with >=1 local
    AND locals agree with each other'. Both clauses are required; the
    flag captures the second clause as a single source of truth."""
    assert DUAL_REQUIRES_LOCALS_AGREE is True, (
        "Dual-lane verification requires the locals to also agree "
        "(CLAUDE.md §8 / ARCHITECTURE.md §1 quorum dispatch row 4)."
    )


# ---------------------------------------------------------------------------
# Stub-vs-real boundary (regression guard)
# ---------------------------------------------------------------------------


def test_usc_stub_marker_cleared_post_w3a3() -> None:
    """Post W3.A.3 — the stub-vs-real boundary moved.

    The W1.C.3 ``STUB_FOR`` class attribute was a regression-guard
    signal: while the stub was in place it carried a non-empty
    "W3.A.3 (Chen et al. 2023 ...)" string so a casual reader could
    not plumb the stub into a real ``quorum_node``. W3.A.3 lands the
    real strategy and clears the marker — empty string signals
    "no stub-warning is owed".

    The substantive coverage of USC's invariants lives in
    ``test_universal_self_consistency.py``.
    """
    assert UniversalSelfConsistency.STUB_FOR == "", (
        "W3.A.3 lands the real Chen 2023 USC; STUB_FOR must be cleared. "
        "If you are seeing this assertion fail, either (a) you reverted to "
        "the stub and need to revert this test too, or (b) the stub-vs-real "
        "boundary moved again and the marker semantics need refreshing."
    )
