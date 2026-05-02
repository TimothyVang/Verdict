"""W3.A.1 — `AirGapCrossEngine` strategy.

Air-gap mode (CLAUDE.md §1; ARCHITECTURE.md §1 row 2) runs two
independent local engines — Qwen3-30B-A3B-Thinking and GLM-4.5-Air —
and accepts the finding only when they agree.

Quorum dispatch (ARCHITECTURE.md §1 quorum-dispatch table rows 3-5):

| Engine outcome                                       | VerdictStatus  |
|------------------------------------------------------|----------------|
| Jaccard(artifact_paths) >= 0.80 AND identical mitre  | VETTED_AIRGAP  |
| Jaccard >= 0.80, divergent mitre_technique           | CONTESTED      |
| Jaccard < 0.80 (incl. empty-set case)                | CONTESTED      |

**Empty-set rule (ARCHITECTURE.md §1):** if any participant returns
``artifact_paths=[]`` (zero findings — e.g., GLM crashed silently,
executor branch timed out per FAILURE_MODES.md R6), it is treated as
DISAGREEMENT, *never* a null vote that lets the non-empty engine win
by default. Otherwise an executor that crashes silently becomes a
free pass for the other lane and destroys the cross-engine guarantee.

This module owns the **consensus logic only**. The transport layer
(SGLang clients for Qwen3 + GLM, ledger plumbing, payload
construction) lands in W2.B; ``verify(...)`` raises
``NotImplementedError`` until then. CLAUDE.md §3.10 explicitly permits
this *backend*-level stub: the consensus logic is real, exercised by
the unit suite via ``compute_verdict(qwen, glm)`` against
``EngineOutput`` records, and is not a mock — it is the strategy's
load-bearing decision function.

The Jaccard threshold is read from ``strategy.AIRGAP_JACCARD_THRESHOLD``
on every call so a future RFC that retunes the threshold lands in one
place. Hard-coding the literal ``0.80`` here would be a bug.
"""
from __future__ import annotations

from dataclasses import dataclass

from verdict.schemas.verdict_status import VerdictStatus
from verdict.verification import strategy as _strategy
from verdict.verification.engine_output import EngineOutput
from verdict.verification.strategy import VerdictResult


def _jaccard(a: list[str], b: list[str]) -> float:
    """Jaccard similarity over two artifact-path lists.

    ``|a ∩ b| / |a ∪ b|``. Set semantics — duplicate paths within an
    engine output collapse before comparison (the engine emitted the
    same artifact twice, which we count as one vote).

    The ARCHITECTURE.md §1 empty-set rule pre-empts this function:
    callers that detect any empty side route to CONTESTED *before*
    Jaccard is consulted, so ``_jaccard`` does NOT have to handle
    the 0/0 case (which is mathematically undefined and
    conventionally 1.0 — exactly the wrong answer for our dispatch).
    Defensive return of ``0.0`` on union-empty is a belt-and-braces
    measure for any future caller that forgets the empty check.
    """
    set_a, set_b = set(a), set(b)
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


@dataclass(frozen=True)
class AirGapCrossEngine:
    """Air-gap quorum strategy: Qwen3 vs GLM-4.5-Air.

    Construction is parameter-less by design — the threshold is a
    module-level constant in ``strategy.py``, and the engine identities
    are determined by the SGLang clients wired in W2.B. A future
    extension that adds per-strategy options (e.g. ``threshold_override``
    for sensitivity studies) can take the standard dataclass-default
    route without breaking the no-arg constructor.
    """

    def compute_verdict(
        self,
        qwen: EngineOutput,
        glm: EngineOutput,
    ) -> VerdictResult:
        """Apply the air-gap consensus rule and return a VerdictResult.

        This is the **pure consensus surface** — input is two already-
        rendered ``EngineOutput`` records, output is the engine-quorum
        verdict. The transport layer (W2.B) calls this after both
        engines have responded.

        Engine-family distinctness is enforced: passing two Qwen3
        outputs (or two GLM outputs) raises ``ValueError`` rather than
        silently collapsing cross-engine quorum to self-consistency.

        Empty artifact sets are treated as DISAGREEMENT
        (ARCHITECTURE.md §1 empty-set rule).
        """
        # Cross-engine guarantee: two outputs MUST come from different
        # families. Passing the same family twice would silently collapse
        # the strategy to a (degenerate) self-consistency check; that is
        # not air-gap quorum and we refuse it at the boundary.
        if qwen.family() == glm.family():
            raise ValueError(
                "AirGapCrossEngine requires two CROSS-engine outputs; "
                f"got two from family={qwen.family()!r} "
                f"(engine_a={qwen.engine!r}, engine_b={glm.engine!r}). "
                "Air-gap quorum collapses to self-consistency without "
                "engine independence — refused at the consensus boundary."
            )

        # Empty-set rule (ARCHITECTURE.md §1): any participant with
        # zero findings is DISAGREEMENT. Pre-empts Jaccard so the
        # 0/0 = 1 mathematical convention cannot vet by accident.
        if not qwen.artifact_paths or not glm.artifact_paths:
            empty_side = []
            if not qwen.artifact_paths:
                empty_side.append(qwen.engine)
            if not glm.artifact_paths:
                empty_side.append(glm.engine)
            return VerdictResult(
                status=VerdictStatus.CONTESTED,
                notes=[
                    "AirGapCrossEngine: empty-set rule (ARCHITECTURE.md §1). "
                    f"Empty parsed_artifacts from: {empty_side}. "
                    "Empty is DISAGREEMENT, never a null vote."
                ],
            )

        jaccard = _jaccard(qwen.artifact_paths, glm.artifact_paths)
        threshold = _strategy.AIRGAP_JACCARD_THRESHOLD

        if jaccard < threshold:
            return VerdictResult(
                status=VerdictStatus.CONTESTED,
                notes=[
                    f"AirGapCrossEngine: Jaccard={jaccard:.3f} < "
                    f"AIRGAP_JACCARD_THRESHOLD={threshold} "
                    f"(qwen={qwen.engine!r}, glm={glm.engine!r}). "
                    "Disagreement on artifact set."
                ],
            )

        # Above threshold; decide on mitre_technique identity.
        if qwen.mitre_technique != glm.mitre_technique:
            return VerdictResult(
                status=VerdictStatus.CONTESTED,
                notes=[
                    f"AirGapCrossEngine: Jaccard={jaccard:.3f} >= {threshold} "
                    "but divergent mitre_technique "
                    f"(qwen={qwen.mitre_technique!r}, "
                    f"glm={glm.mitre_technique!r}). "
                    "Engines agree on artifacts, disagree on technique — "
                    "ARCHITECTURE.md §1 row 4."
                ],
            )

        return VerdictResult(
            status=VerdictStatus.VETTED_AIRGAP,
            notes=[
                f"AirGapCrossEngine: Jaccard={jaccard:.3f} >= {threshold}, "
                f"identical mitre_technique={qwen.mitre_technique!r} "
                f"(qwen={qwen.engine!r}, glm={glm.engine!r})."
            ],
        )

    def verify(
        self,
        *,
        case_id: str,
        hypothesis: str,
        mitre_technique: str,
        evidence_summary: str,
    ) -> VerdictResult:
        """Transport-level verify: drive Qwen3 + GLM via SGLang and compute the verdict.

        Wiring lands in **W2.B** (SGLang clients + ledger plumbing).
        Until then this MUST raise so a casual integrator does NOT plumb
        a half-wired strategy into ``quorum_node`` and ship a verdict
        that looks vetted but isn't.

        CLAUDE.md §3.10 explicitly permits this backend-level stub: the
        consensus logic is real and exercised via ``compute_verdict``.
        The forbidden-pattern is mocking *internal* logic; raising at
        the network boundary until the SGLang adapter lands is the
        opposite of that pattern.
        """
        _ = (case_id, hypothesis, mitre_technique, evidence_summary)
        raise NotImplementedError(
            "AirGapCrossEngine.verify(): SGLang transport (Qwen3 + GLM-4.5-Air "
            "clients, ledger emission, payload construction) lands in W2.B. "
            "The consensus logic is exercised via compute_verdict(qwen, glm) — "
            "see tests/verification/test_airgap_cross_engine.py."
        )


__all__ = ["AirGapCrossEngine"]
