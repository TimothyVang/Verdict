"""W1.C.3 / W3.A.3 — `VerifierStrategy` Protocol + per-mode constants
+ `UniversalSelfConsistency` (Chen et al. 2023).

The ``quorum_node`` (W2.B / W3.A) selects one strategy per locked mode:

+----------+----------------------------+---------------------+
| Mode     | Strategy                   | Implementation gate |
+==========+============================+=====================+
| cloud    | CloudSelfConsistency       | W1.C.2              |
| airgap   | AirGapCrossEngine          | W3.A.1              |
| dual     | DualLaneCrossEngine        | W3.A.2              |
| any      | UniversalSelfConsistency   | W3.A.3              |
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

from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from verdict.schemas.verdict_status import VerdictStatus

if TYPE_CHECKING:
    from collections.abc import Sequence

    from verdict.verification.engine_output import EngineOutput

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
    - ``UniversalSelfConsistency`` (judge of last resort; W3.A.3)

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
# UniversalSelfConsistency — Chen et al. 2023 (W3.A.3)
# ---------------------------------------------------------------------------


_VETTED_STATUSES: frozenset[VerdictStatus] = frozenset(
    {VerdictStatus.VETTED_CLOUD, VerdictStatus.VETTED_AIRGAP, VerdictStatus.VETTED_DUAL}
)


@dataclass(frozen=True)
class USCJudgement:
    """Outcome of ``UniversalSelfConsistency.judge(candidates)``.

    Carries the index of the selected candidate (or ``None`` if no
    judgement was possible) plus a ``VerdictStatus`` and audit notes.

    - ``selected_index is not None and status in {VETTED_CLOUD, _AIRGAP, _DUAL}``
      means USC found a substance-majority and chose its index.
    - ``selected_index is None and status == CONTESTED`` means no
      substance-majority existed; the dispatching ``quorum_node``
      escalates to ``replan_node``.

    The dispatching code passes the locked mode's ``vetted_status``
    into ``judge`` so this object's ``status`` already carries the
    correct ``VETTED_*`` discriminator and the ``quorum_node`` does
    not need to remap.
    """

    selected_index: int | None
    status: VerdictStatus
    notes: list[str] = field(default_factory=list)


def _substance_key(candidate: EngineOutput) -> tuple[str, frozenset[str]]:
    """Cluster key for substance-majority detection.

    Two candidates are in the same substance cluster iff they have
    identical ``mitre_technique`` AND identical artifact path SETS
    (order-insensitive). This is the ARCHITECTURE.md §1 row-3 / row-4
    discriminator collapsed into a single hashable tuple.
    """
    return (candidate.mitre_technique, frozenset(candidate.artifact_paths))


@dataclass(frozen=True)
class UniversalSelfConsistency:
    """Chen et al. 2023 Universal Self-Consistency judge of last resort.

    ``UniversalSelfConsistency`` (Chen et al. 2023, arXiv:2311.17311) is
    invoked AFTER another strategy returns ``CONTESTED``. It reads the
    prior strategy's candidate outputs and either:

    1. **Substance-majority case (deterministic)**: when a clear
       majority cluster exists in the candidate set
       — keyed by ``(mitre_technique, frozenset(artifact_paths))`` —
       USC selects the first candidate of that cluster and returns a
       ``USCJudgement`` with the caller-specified ``vetted_status``.
       This is the load-bearing testable surface (BUILD_PLAN W3.A.3.a).
    2. **No-majority case (LLM-as-judge fallback)**: when no substance
       cluster has a strict majority, USC falls back to the Chen 2023
       LLM-as-judge prompt — the model reads all candidate rationales
       and picks the most consistent one. The LLM call itself lands in
       **W2.B**; until that transport lands, ``judge`` correctly returns
       ``CONTESTED`` for the no-majority case (USC admits "no winner"
       rather than invent one).

    Empty-set rule (ARCHITECTURE.md §1) carries: candidates with empty
    ``artifact_paths`` drop out of clustering rather than counting as a
    "majority of empties". A silently-crashing engine must NOT carry a
    vetted verdict by virtue of producing nothing.

    USC is mode-agnostic — the dispatching ``quorum_node`` knows the
    locked mode and passes the appropriate ``vetted_status`` so USC's
    output carries the right ``VETTED_*`` discriminator.
    """

    #: Stub-vs-real boundary marker. Empty string post-W3.A.3; the W1.C.3
    #: era populated this with a "W3.A.3 (Chen et al. 2023 ...)" warning.
    STUB_FOR: str = ""

    def judge(
        self,
        candidates: Sequence[EngineOutput],
        *,
        vetted_status: VerdictStatus = VerdictStatus.VETTED_CLOUD,
    ) -> USCJudgement:
        """Pick the most-consistent candidate via substance-clustering.

        Parameters
        ----------
        candidates:
            The candidate outputs to judge over. Typically the n=3
            ``CloudSelfConsistency`` trio or the 2-engine cross-engine
            pair that just returned ``CONTESTED``. At least 2
            candidates required.
        vetted_status:
            The ``VETTED_*`` status the dispatching ``quorum_node``
            wants USC to stamp on a successful judgement. Default
            ``VETTED_CLOUD`` matches the W1.C.3 stub surface so
            non-mode-aware callers get a sensible default; air-gap
            dispatch passes ``VETTED_AIRGAP``; dual passes
            ``VETTED_DUAL``. Must be a ``VETTED_*`` member —
            passing ``CONTESTED`` / ``UNVERIFIABLE`` raises
            ``ValueError`` since the dispatcher would be asking USC
            to mislabel its own verdict.
        """
        if vetted_status not in _VETTED_STATUSES:
            raise ValueError(
                "UniversalSelfConsistency.judge: vetted_status must be a "
                f"VETTED_* member; got {vetted_status!r}. The dispatching "
                "quorum_node passes the locked mode's VETTED_* "
                "discriminator; CONTESTED / UNVERIFIABLE are output "
                "states, not input parameters."
            )
        if len(candidates) < 2:
            raise ValueError(
                "UniversalSelfConsistency.judge: at least 2 candidates "
                f"required to judge; got {len(candidates)}. With <2 "
                "candidates there is no judgement to make and a "
                "default-vetted return would silently mislabel a verdict."
            )

        # Empty-set rule (ARCHITECTURE.md §1) — drop empty-artifact
        # candidates from clustering. They are silent-crash signals,
        # not votes. We retain their ORIGINAL indices so a real
        # candidate's selected_index still maps back to the input list.
        real_indexed = [
            (i, c) for i, c in enumerate(candidates) if c.artifact_paths
        ]
        if len(real_indexed) < 2:
            return USCJudgement(
                selected_index=None,
                status=VerdictStatus.CONTESTED,
                notes=[
                    "UniversalSelfConsistency: <2 non-empty candidates after "
                    "empty-set rule (ARCHITECTURE.md §1). Empty artifact_paths "
                    "is a silent-crash signal, not a vote — cannot judge."
                ],
            )

        # Substance-cluster the surviving candidates. Counter preserves
        # first-insertion order for ties (Python 3.7+); .most_common
        # then picks the largest cluster, with the first-seen cluster
        # winning a tie (deterministic tie-breaker).
        keys = [_substance_key(c) for _, c in real_indexed]
        cluster_counts = Counter(keys)
        top_key, top_count = cluster_counts.most_common(1)[0]

        # A "majority" is strict — > 50% of the original candidate count.
        # Three candidates: 2 = majority. Four candidates: 3 = majority.
        # The total denominator is len(candidates), NOT len(real_indexed),
        # so a single empty-vs-two-agreeing case still counts the empty
        # against the majority threshold (otherwise an empty silent-crash
        # would let two-of-three vet at the lowest possible bar — that
        # is "majority of survivors", not "majority of voters").
        majority_threshold = len(candidates) // 2 + 1
        if top_count >= majority_threshold:
            # Pick the FIRST candidate (by original index) whose key
            # matches the top cluster — deterministic tie-breaker.
            selected_index = next(
                i for i, c in real_indexed if _substance_key(c) == top_key
            )
            return USCJudgement(
                selected_index=selected_index,
                status=vetted_status,
                notes=[
                    f"UniversalSelfConsistency: substance majority "
                    f"({top_count}/{len(candidates)}, threshold={majority_threshold}); "
                    f"selected index={selected_index}, "
                    f"mitre={top_key[0]!r}, "
                    f"|artifact_paths|={len(top_key[1])}."
                ],
            )

        # No substance majority. Chen 2023 §3 prescribes an LLM-as-judge
        # fallback here; the LLM transport lands in W2.B. Until then, USC
        # honestly admits "no winner" rather than invent one.
        return USCJudgement(
            selected_index=None,
            status=VerdictStatus.CONTESTED,
            notes=[
                f"UniversalSelfConsistency: no substance majority "
                f"(top cluster {top_count}/{len(candidates)} < threshold "
                f"{majority_threshold}). LLM-as-judge fallback (Chen 2023 §3) "
                "lands in W2.B; CONTESTED until then."
            ],
        )

    def verify(
        self,
        *,
        case_id: str,
        hypothesis: str,
        mitre_technique: str,
        evidence_summary: str,
        candidates: Sequence[EngineOutput] | None = None,
        vetted_status: VerdictStatus = VerdictStatus.VETTED_CLOUD,
    ) -> VerdictResult:
        """Protocol-level entry point — delegates to ``judge``.

        ``candidates`` is the prior strategy's output set. When the
        ``quorum_node`` invokes USC after another strategy returned
        ``CONTESTED``, it passes the prior candidates here.

        Standalone (no ``candidates``) USC has nothing to judge over
        and raises ``NotImplementedError`` rather than silently
        mislabelling a verdict — the LLM-as-judge transport that
        constructs candidates from ``(case_id, hypothesis, ...)``
        lands in W2.B. Until then, USC must be invoked with the prior
        candidates already in hand.
        """
        if candidates is None:
            _ = (case_id, hypothesis, mitre_technique, evidence_summary)
            raise NotImplementedError(
                "UniversalSelfConsistency.verify(): standalone USC "
                "(without prior candidates) requires the LLM-as-judge "
                "transport that lands in W2.B. Dispatch USC after "
                "another strategy has returned CONTESTED, passing that "
                "strategy's candidate outputs via the candidates kwarg, "
                "or call judge(candidates) directly."
            )

        judgement = self.judge(candidates, vetted_status=vetted_status)
        return VerdictResult(
            status=judgement.status,
            notes=[
                *judgement.notes,
                f"USC.verify wrapper: case_id={case_id!r}, "
                f"hypothesis_mitre={mitre_technique!r}, "
                f"selected_index={judgement.selected_index}.",
            ],
        )


__all__ = [
    "AIRGAP_JACCARD_THRESHOLD",
    "DUAL_REQUIRES_LOCALS_AGREE",
    "USCJudgement",
    "UniversalSelfConsistency",
    "VerdictResult",
    "VerifierStrategy",
]
