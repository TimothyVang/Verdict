"""VerdictStatus enum — canonical epistemic vocabulary for VERDICT findings.

CLAUDE.md §3.6 defines exactly six values. No others are permitted.

  VETTED_CLOUD      — CloudSelfConsistency ≥2-of-3 samples agreed on
                      (mitre_technique, parsed_artifacts). Best-effort;
                      same-model correlated failure modes apply.
  VETTED_AIRGAP     — AirGapCrossEngine: Qwen3 + GLM-4.5-Air both ran;
                      Jaccard(artifact_paths) ≥0.80 AND identical
                      mitre_technique. Cross-family independent verification.
  VETTED_DUAL       — DualLaneCrossEngine: cloud agrees with ≥1 local AND
                      locals agree with each other. Strongest epistemic claim.
  CONTESTED         — Engines disagreed; replan_node is entered (up to
                      replan_max=3 iterations). Still no consensus after
                      replanning → EXHAUSTED_REPLAN.
  UNVERIFIABLE      — First-class outcome (CLAUDE.md §3.6, judge rubric item
                      14). Tool exhaustion, sandbox failure, TSI proxy
                      unreachable, or tool_arg_retry_max exceeded.
  EXHAUSTED_REPLAN  — replan_max=3 exceeded; finalize_node maps this from
                      the replan budget. unverifiable_finalize_node writes
                      Finding(status=UNVERIFIABLE) and calls interrupt().

Engine-quorum verdict (VerifierStrategy output) uses:
  VETTED_CLOUD | VETTED_AIRGAP | VETTED_DUAL | CONTESTED | UNVERIFIABLE

Case verdict (Finding.status) additionally uses:
  EXHAUSTED_REPLAN  — produced by finalize_node, not VerifierStrategy.

Finding.review_state (DRAFT / APPROVED / REJECTED) is orthogonal to
VerdictStatus and is defined as a Literal in verdict/schemas/finding.py.
"""

from enum import Enum


class VerdictStatus(str, Enum):
    """Canonical verdict statuses per CLAUDE.md §3.6.

    Inherits from str for JSON/JSONL serialisation compatibility — the
    ledger stores raw values; Pydantic v2 coerces str → enum on
    deserialisation.

    Exactly six members. Adding a seventh requires updating CLAUDE.md §3.6,
    ARCHITECTURE.md §1 quorum-dispatch table, and DEVPOST_COMPLIANCE.md.
    """

    VETTED_CLOUD = "vetted_cloud"
    VETTED_AIRGAP = "vetted_airgap"
    VETTED_DUAL = "vetted_dual"
    CONTESTED = "contested"
    UNVERIFIABLE = "unverifiable"
    EXHAUSTED_REPLAN = "exhausted_replan"
