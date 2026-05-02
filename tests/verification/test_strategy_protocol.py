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
    """W1.C.3.a stub contract: hardcoded VETTED_CLOUD on a minimal call."""
    result = UniversalSelfConsistency().verify(
        case_id="case_001_lolbins",
        hypothesis="Evidence consistent with rundll32 invoking comsvcs.MiniDump.",
        mitre_technique="T1003.001",
        evidence_summary="Sysmon ID 1; Prefetch RUNDLL32.EXE-...",
    )
    assert isinstance(result, VerdictResult), (
        f"verify(...) must return VerdictResult, got {type(result).__name__}"
    )
    assert result.status == VerdictStatus.VETTED_CLOUD, (
        "W1.C.3 stub returns VETTED_CLOUD; W3.A.3 lands the real Chen 2023 logic."
    )


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


def test_usc_stub_does_not_pretend_to_implement_chen_2023() -> None:
    """The stub must announce itself. W3.A.3 is the real implementation;
    until then the stub MUST flag that it is not Chen 2023 -- otherwise
    a casual reader could plumb it into a quorum and ship a verdict that
    looks vetted but isn't."""
    # Either the class docstring or a class attribute must explicitly
    # mark this as a W1.C.3 stub.
    cls = UniversalSelfConsistency
    text = (cls.__doc__ or "") + " " + str(getattr(cls, "STUB_FOR", ""))
    assert "stub" in text.lower() or "w3.a.3" in text.lower(), (
        "UniversalSelfConsistency must announce itself as a W1.C.3 stub "
        "until W3.A.3 lands the real Chen 2023 (UCSC) implementation."
    )
