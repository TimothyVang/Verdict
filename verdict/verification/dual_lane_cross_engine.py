"""W3.A.2 — `DualLaneCrossEngine` strategy.

Dual mode (CLAUDE.md §1; ARCHITECTURE.md §1 row 4) runs THREE engines
in parallel — cloud (Claude), Qwen3, GLM-4.5-Air — and accepts the
finding only under the conjunctive rule (CLAUDE.md §8):

    cloud agrees with ≥1 local  AND  locals agree with each other.

Both clauses are required. The second clause is captured in
``DUAL_REQUIRES_LOCALS_AGREE`` from ``strategy.py``; flipping it to
``False`` would silently weaken dual-mode verification to the air-gap
rule on the local pair, discarding the cloud lane's vote.

Quorum dispatch (ARCHITECTURE.md §1 quorum-dispatch table rows 6-8):

| Engine outcome                                              | VerdictStatus |
|-------------------------------------------------------------|---------------|
| cloud agrees with ≥1 local AND locals agree with each other | VETTED_DUAL   |
| cloud disagrees with both locals                            | CONTESTED     |
| cloud agrees with 1 local, locals disagree with each other  | CONTESTED     |

"Agree" is the same predicate used in air-gap mode: identical
``mitre_technique`` AND Jaccard(``artifact_paths``) ≥
``AIRGAP_JACCARD_THRESHOLD``. Reusing the threshold means dual mode is
"air-gap quorum on each pair plus a cloud-anchor requirement" — one
knob, one place.

Empty-set rule (ARCHITECTURE.md §1) carries: any participant with
empty artifacts is treated as DISAGREEMENT for every pairwise
comparison involving it.

Like ``AirGapCrossEngine``, this module owns the **consensus logic
only**. The transport layer — cloud Claude client + the two SGLang
clients + ledger plumbing — lands in W2.B; ``verify(...)`` raises
``NotImplementedError`` until then. CLAUDE.md §3.10 explicitly permits
this backend-level stub: the consensus logic is real and exercised by
the unit suite via ``compute_verdict(cloud, qwen, glm)`` against
``EngineOutput`` records.
"""
from __future__ import annotations

from dataclasses import dataclass

from verdict.schemas.verdict_status import VerdictStatus
from verdict.verification import strategy as _strategy
from verdict.verification.engine_output import EngineOutput
from verdict.verification.strategy import VerdictResult


def _jaccard(a: list[str], b: list[str]) -> float:
    """Jaccard similarity over two artifact-path lists.

    Identical helper to ``airgap_cross_engine._jaccard``; duplicated
    rather than imported across module boundaries to keep each
    strategy's consensus rule self-contained and obviously identical
    by inspection. The single-source-of-truth is the
    ``AIRGAP_JACCARD_THRESHOLD`` constant — *not* the helper itself.
    """
    set_a, set_b = set(a), set(b)
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def _pair_agrees(a: EngineOutput, b: EngineOutput) -> bool:
    """The dual-mode "agree" predicate: identical mitre_technique AND
    Jaccard ≥ ``AIRGAP_JACCARD_THRESHOLD``.

    Empty-set rule: if either side has empty artifact_paths, the pair
    DISAGREES. This mirrors ``AirGapCrossEngine`` behaviour and pre-
    empts the mathematical 0/0=1.0 convention.

    Mitre divergence is checked first so the function returns ``False``
    cheaply on the common "engines agree on artifacts but disagree on
    interpretation" case without computing Jaccard.
    """
    if not a.artifact_paths or not b.artifact_paths:
        return False
    if a.mitre_technique != b.mitre_technique:
        return False
    return _jaccard(a.artifact_paths, b.artifact_paths) >= _strategy.AIRGAP_JACCARD_THRESHOLD


@dataclass(frozen=True)
class DualLaneCrossEngine:
    """Dual-mode quorum strategy: cloud + Qwen3 + GLM, three-way verification.

    Construction is parameter-less; all knobs are module-level
    constants in ``strategy.py``.
    """

    def compute_verdict(
        self,
        *,
        cloud: EngineOutput,
        qwen: EngineOutput,
        glm: EngineOutput,
    ) -> VerdictResult:
        """Apply the dual-mode consensus rule and return a VerdictResult.

        This is the **pure consensus surface** — input is three
        already-rendered ``EngineOutput`` records, output is the
        engine-quorum verdict. The transport layer (W2.B) calls this
        after all three engines have responded.

        Boundary refusals at the dispatch layer:
        - ``cloud`` slot must be a cloud-family output.
        - ``qwen`` and ``glm`` slots must be from different local
          families (passing two Qwen3 outputs would collapse the
          locals-agree clause to self-consistency).

        These refusals raise ``ValueError`` rather than returning a
        ``VerdictResult`` because they signal a programming error at
        the dispatch site, not a real verification outcome.
        """
        # ------------------------------------------------------------
        # Boundary refusals — programming-error guards
        # ------------------------------------------------------------
        # Cloud slot must be a cloud-family output. Air-gap-only outputs
        # in the cloud slot would silently mislabel the verdict.
        if cloud.family() != "claude":
            raise ValueError(
                "DualLaneCrossEngine: cloud slot must be a cloud-family "
                f"output (engine starts with 'claude-...'); got "
                f"engine={cloud.engine!r}, family={cloud.family()!r}. "
                "Refused at the consensus boundary so a misrouted "
                "verdict cannot ship under VETTED_DUAL."
            )
        # Locals-agree clause requires CROSS-engine outputs on the
        # local pair. Two Qwen3 outputs collapses locals-agree to
        # self-consistency and breaks the air-gap independence
        # guarantee that dual mode inherits.
        if qwen.family() == glm.family():
            raise ValueError(
                "DualLaneCrossEngine: local pair must be CROSS-engine; "
                f"got two from family={qwen.family()!r} "
                f"(local_a={qwen.engine!r}, local_b={glm.engine!r}). "
                "Locals-agree clause collapses to self-consistency "
                "without engine independence."
            )

        # ------------------------------------------------------------
        # Conjunctive rule (CLAUDE.md §8 / ARCHITECTURE.md §1)
        # ------------------------------------------------------------
        cloud_qwen = _pair_agrees(cloud, qwen)
        cloud_glm = _pair_agrees(cloud, glm)
        locals_agree = _pair_agrees(qwen, glm)

        cloud_anchor = cloud_qwen or cloud_glm  # ≥1 local
        # ``DUAL_REQUIRES_LOCALS_AGREE`` is read from strategy.py per
        # call so a future RFC that retunes the flag lands in one place.
        # The attribute access (not a captured local) is the load-bearing
        # bit — flipping the flag at runtime would change behaviour.
        require_locals_agree = _strategy.DUAL_REQUIRES_LOCALS_AGREE

        if cloud_anchor and (locals_agree or not require_locals_agree):
            if cloud_qwen and cloud_glm:
                anchored_with = "qwen+glm"
            elif cloud_qwen:
                anchored_with = "qwen"
            else:
                anchored_with = "glm"
            return VerdictResult(
                status=VerdictStatus.VETTED_DUAL,
                notes=[
                    f"DualLaneCrossEngine: cloud agrees with {anchored_with} "
                    f"AND locals agree (require_locals_agree={require_locals_agree}). "
                    f"cloud={cloud.engine!r}, qwen={qwen.engine!r}, glm={glm.engine!r}, "
                    f"mitre={cloud.mitre_technique!r}."
                ],
            )

        # CONTESTED — record which clause failed for replan_node routing
        reason_parts = []
        if not cloud_anchor:
            reason_parts.append(
                "cloud disagrees with both locals "
                f"(cloud-vs-qwen={cloud_qwen}, cloud-vs-glm={cloud_glm})"
            )
        if cloud_anchor and require_locals_agree and not locals_agree:
            reason_parts.append(
                "cloud agrees with one local but locals disagree with "
                "each other (DUAL_REQUIRES_LOCALS_AGREE=True)"
            )
        return VerdictResult(
            status=VerdictStatus.CONTESTED,
            notes=[
                "DualLaneCrossEngine CONTESTED: " + "; ".join(reason_parts) + ". "
                f"cloud={cloud.engine!r}, qwen={qwen.engine!r}, glm={glm.engine!r}, "
                f"mitre(cloud)={cloud.mitre_technique!r}, "
                f"mitre(qwen)={qwen.mitre_technique!r}, "
                f"mitre(glm)={glm.mitre_technique!r}."
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
        """Transport-level verify: drive cloud + Qwen3 + GLM and compute the verdict.

        Wiring lands in **W2.B** (cloud Claude client + two SGLang
        clients + ledger plumbing). Until then this MUST raise so a
        casual integrator does NOT plumb a half-wired strategy into
        ``quorum_node`` and ship a verdict that looks vetted but
        isn't.

        CLAUDE.md §3.10 explicitly permits this backend-level stub:
        the consensus logic is real and exercised via
        ``compute_verdict``. The forbidden pattern is mocking
        *internal* logic; raising at the network boundary until the
        client adapters land is the opposite of that pattern.
        """
        _ = (case_id, hypothesis, mitre_technique, evidence_summary)
        raise NotImplementedError(
            "DualLaneCrossEngine.verify(): transport layer (cloud Claude + "
            "Qwen3-SGLang + GLM-4.5-Air-SGLang clients, ledger emission, "
            "payload construction) lands in W2.B. The consensus logic is "
            "exercised via compute_verdict(cloud=, qwen=, glm=) — see "
            "tests/verification/test_dual_lane_cross_engine.py."
        )


__all__ = ["DualLaneCrossEngine"]
