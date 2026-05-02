"""W1.C.3 — `VerifierStrategy` Protocol + per-mode constants + USC stub.

The ``quorum_node`` (W2.B / W3.A) selects one strategy per locked mode:

+----------+----------------------------+---------------------+
| Mode     | Strategy                   | Implementation gate |
+==========+============================+=====================+
| cloud    | CloudSelfConsistency       | W1.C.2              |
| airgap   | AirGapCrossEngine          | W3.A.1              |
| dual     | DualLaneCrossEngine        | W3.A.2              |
| any      | UniversalSelfConsistency   | W3.A.3 (W1.C.3 stub)|
|          | (judge of last resort)     |                     |
+----------+----------------------------+---------------------+

For the dispatch to be substitution-safe, every strategy conforms to a
``VerifierStrategy`` Protocol and returns a ``VerdictResult``. The Protocol
is structural (``typing.Protocol``) -- concrete strategies do NOT inherit
from it; they merely satisfy its shape. This keeps the verification layer
decoupled from the dispatch layer and avoids spurious abstract-base
inheritance issues during the W3.A wiring.

This module also exports two mode-keyed *constants* that future strategies
read instead of hard-coding magic numbers:

- ``AIRGAP_JACCARD_THRESHOLD = 0.80``
  ARCHITECTURE.md §1 quorum-dispatch row 2: "Jaccard ≥0.80".
- ``DUAL_REQUIRES_LOCALS_AGREE = True``
  CLAUDE.md §8: "cloud agrees with ≥1 local AND locals agree with each
  other". The second clause is the reason cloud-vs-1-local-only is not
  enough.

Centralising these here means ``W3.A.1`` (AirGapCrossEngine) and
``W3.A.2`` (DualLaneCrossEngine) cannot accidentally diverge from the
ARCHITECTURE / CLAUDE contract -- the values are imported, not retyped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from verdict.schemas.verdict_status import VerdictStatus

# ---------------------------------------------------------------------------
# Mode-keyed constants (single source of truth)
# ---------------------------------------------------------------------------

#: ARCHITECTURE.md §1 quorum-dispatch table, row 2:
#: "Jaccard(``parsed_artifacts``) ≥0.80 AND identical ``mitre_technique``
#: -> VETTED_AIRGAP". Below threshold -> CONTESTED.
AIRGAP_JACCARD_THRESHOLD: float = 0.80

#: CLAUDE.md §8: DualLaneCrossEngine requires "cloud agrees with ≥1 local
#: AND locals agree with each other". This flag pins the second conjunct
#: as a load-bearing invariant; flipping it to ``False`` would silently
#: weaken dual-mode verification to the air-gap rule on the local pair.
DUAL_REQUIRES_LOCALS_AGREE: bool = True


# ---------------------------------------------------------------------------
# VerdictResult — return type for every VerifierStrategy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerdictResult:
    """Engine-quorum verdict returned by a ``VerifierStrategy``.

    Carries the ``VerdictStatus`` plus optional metadata that the ledger
    records (which engines voted which way; what the disagreement was).
    The full agreement-detail schema lands with ``W3.A.1`` /
    ``W3.A.2`` -- this dataclass is intentionally minimal so the
    Protocol contract can be locked at W1.C.3 without prejudicing
    later design work on the agreement-set representation.

    Construction enforces ``status`` is a real ``VerdictStatus``;
    passing a raw string raises ``TypeError`` so a typo in dispatch
    code surfaces immediately rather than producing an
    untrustworthy verdict.
    """

    status: VerdictStatus
    #: Per-sample / per-engine notes. List of strings is the W1.C.3
    #: floor; W3.A.1+ may upgrade to a richer structured type. Empty
    #: by default to keep the stub trivially constructible.
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.status, VerdictStatus):
            raise TypeError(
                "VerdictResult.status must be a VerdictStatus member; "
                f"got {type(self.status).__name__}={self.status!r}. "
                "If you want to construct from a string, use "
                "VerdictStatus(<value>) explicitly."
            )


# ---------------------------------------------------------------------------
# VerifierStrategy Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class VerifierStrategy(Protocol):
    """Structural type for any verifier strategy plumbed into ``quorum_node``.

    Concrete implementations:

    - ``CloudSelfConsistency`` (cloud-only mode; W1.C.2)
    - ``AirGapCrossEngine`` (air-gap mode; W3.A.1)
    - ``DualLaneCrossEngine`` (dual mode; W3.A.2)
    - ``UniversalSelfConsistency`` (judge of last resort; W3.A.3 -
      this module ships the W1.C.3 stub)

    Implementations do NOT need to inherit from this Protocol; they
    merely need to expose a ``verify(...)`` method with the matching
    signature. Subclassing ``Protocol`` directly is permitted but not
    required (PEP 544).
    """

    def verify(
        self,
        *,
        case_id: str,
        hypothesis: str,
        mitre_technique: str,
        evidence_summary: str,
    ) -> VerdictResult:
        """Verify ``hypothesis`` and return an engine-quorum verdict.

        Implementations must be pure with respect to the inputs in the
        sense that audit replay is supported: rerunning ``verify`` with
        the same inputs and the same backing model state must produce
        the same ``VerdictStatus`` (CLAUDE.md §3.4 mode-lock). Network
        calls are permitted; the determinism guarantee is at the
        seed-derivation + payload-construction layer, not at the
        wire-output layer.
        """
        ...


# ---------------------------------------------------------------------------
# UniversalSelfConsistency stub (W1.C.3 -> W3.A.3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UniversalSelfConsistency:
    """Stub for the Chen et al. 2023 (UCSC) judge-of-last-resort strategy.

    Stub-status: this is the **W1.C.3 placeholder**. The full Chen 2023
    (Universal Self-Consistency, arXiv:2311.17311) implementation lands
    in **W3.A.3** -- which uses a final LLM judge over the n=3 / n=2
    candidate verdicts to pick the most consistent one before declaring
    ``CONTESTED``.

    Until W3.A.3 lands, ``verify(...)`` returns a hardcoded
    ``VerdictStatus.VETTED_CLOUD`` so downstream wiring (graph nodes,
    dispatch tables, ledger sinks) can integrate against a real
    Protocol implementation. The Reviewer agent should reject any
    attempt to plumb this stub into the actual ``quorum_node`` until
    the real implementation lands.
    """

    #: Class-level marker so the regression-guard test can introspect
    #: that this is still a stub. When W3.A.3 lands, set this to the
    #: empty string and remove the guard test.
    STUB_FOR: str = "W3.A.3 (Chen et al. 2023 Universal Self-Consistency)"

    def verify(
        self,
        *,
        case_id: str,
        hypothesis: str,
        mitre_technique: str,
        evidence_summary: str,
    ) -> VerdictResult:
        """W1.C.3 stub -- returns a hardcoded VETTED_CLOUD.

        DO NOT plumb this into the real ``quorum_node`` until W3.A.3.
        BUILD_PLAN W1.C.3.a explicitly defines the stub return as
        ``VETTED_CLOUD`` so the Protocol contract can be locked
        substitution-safely.
        """
        # Touch the inputs so static analysers don't flag them as unused
        # in the stub body. W3.A.3 reads them all.
        _ = (case_id, hypothesis, mitre_technique, evidence_summary)
        return VerdictResult(
            status=VerdictStatus.VETTED_CLOUD,
            notes=[
                f"W1.C.3 stub; full Chen 2023 USC lands in W3.A.3. "
                f"case_id={case_id!r}, mitre={mitre_technique!r}"
            ],
        )


__all__ = [
    "AIRGAP_JACCARD_THRESHOLD",
    "DUAL_REQUIRES_LOCALS_AGREE",
    "UniversalSelfConsistency",
    "VerdictResult",
    "VerifierStrategy",
]
