"""Minimal Pydantic types the Planner Protocol contract returns.

These are scoped to the planner's *interface surface* — `Mode` enum,
`EvidenceManifest`, `Hypothesis`, `InvestigationPlan`. The full schema
bundle (Finding, ToolOutput, LedgerEntry, …) lives under
`verdict/schemas/` and lands across W1.B in separate branches.

When `verdict/schemas/hypothesis.py`, `verdict/schemas/plan.py`, and
`verdict/schemas/evidence.py` merge, the planner package re-exports
those types and removes the local definitions here. The validators
encoded below MUST match the schema bundle's validators byte-for-byte
so the swap is mechanical.

Hard rules referenced:
  * §3.5  MITRE technique regex `^T\\d{4}(\\.\\d{3})?$`
  * §3.6  Negative-hypothesis quality:
            - non-None mitre_technique
            - non-empty artifact_families
            - success_criteria deny-list
          InvestigationPlan: >= 1 negative hypothesis required.
  * §3.10 No mocks: every validator is real Pydantic, no
          os.environ short-circuits.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Mode — operational mode locked at case_init (CLAUDE.md §3.4)
# ---------------------------------------------------------------------------


class Mode(str, Enum):
    """Operational mode auto-detected at case_init and immutable thereafter.

    Mode-locking is enforced in `verdict/runtime/mode_detect.py`
    (BUILD_PLAN W1.G.5.a). The Planner classes only assert that the
    `mode` argument they are dispatched with is one they support — the
    *which-planner-for-which-mode* gateway dispatch lives in
    `runtime/mode_detect.py`, not in the Planner classes.
    """

    CLOUD = "cloud"
    AIRGAP = "airgap"
    DUAL = "dual"


# ---------------------------------------------------------------------------
# EvidenceManifest — minimal contract the Planner consumes
# ---------------------------------------------------------------------------


class EvidenceManifest(BaseModel):
    """Manifest of evidence files for a case. Hashes recorded at case_init.

    Full implementation (with blake3-of-sorted-pairs manifest hash + per-file
    blake3) lands in `verdict/schemas/evidence.py` (W1.B.3). The planner
    consumes only the case_id + evidence_paths + evidence_hashes surface
    so this minimal shape is sufficient for the Protocol contract.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    evidence_paths: list[str] = Field(min_length=1)
    evidence_hashes: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Hypothesis — §3.5 MITRE regex + §3.6 negative-hypothesis quality
# ---------------------------------------------------------------------------


_MITRE_RE = re.compile(r"^T\d{4}(\.\d{3})?$")

# Deny-list tokens checked via substring match on lower-cased success_criteria.
# CLAUDE.md §3.6: cosmic | alien | nothing | not-relevant | n-a
# (plus the canonical alternates n/a + "not relevant" already encoded in the
# existing W1.B.4 hypothesis schema).
_NEGATIVE_DENY_TOKENS: tuple[str, ...] = (
    "cosmic",
    "alien",
    "nothing",
    "not-relevant",
    "not relevant",
    "n-a",
    "n/a",
)


class Hypothesis(BaseModel):
    """A claim under investigation — positive OR negative.

    Positive hypotheses posit a specific MITRE technique was used and name
    the artifact families that would confirm it.

    Negative hypotheses assert the technique was NOT used; they must be
    specific enough for the investigation to *rule out* alternatives, not
    just declare the absence of evidence (§3.6).
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    polarity: Literal["positive", "negative"]
    mitre_technique: str | None = None
    artifact_families: list[str] = Field(default_factory=list)
    success_criteria: str = Field(min_length=1)

    @field_validator("mitre_technique", mode="before")
    @classmethod
    def _validate_mitre_format(cls, v: object) -> object:
        """Enforce ^T\\d{4}(\\.\\d{3})?$ shape per §3.5."""
        if v is None:
            return v
        if not isinstance(v, str) or not _MITRE_RE.match(v):
            raise ValueError(
                f"MITRE technique must match T#### or T####.### (e.g. T1055.012); got {v!r}"
            )
        return v

    @model_validator(mode="after")
    def _negative_hypothesis_quality(self) -> Hypothesis:
        """§3.6 — negative hypotheses must be specific and non-degenerate."""
        if self.polarity != "negative":
            return self

        if self.mitre_technique is None:
            raise ValueError(
                "negative hypothesis must name a MITRE technique it is ruling out"
            )

        if not self.artifact_families:
            raise ValueError(
                "negative hypothesis must name artifact families that would refute it"
            )

        criteria_lower = self.success_criteria.lower()
        hit = next((tok for tok in _NEGATIVE_DENY_TOKENS if tok in criteria_lower), None)
        if hit is not None:
            raise ValueError(
                f"negative hypothesis success_criteria contains deny-listed token "
                f"{hit!r} (§3.6 forbids cosmic / alien / nothing / not-relevant / "
                f"n-a / n/a). Be specific about what would refute the hypothesis."
            )
        return self


# ---------------------------------------------------------------------------
# InvestigationPlan — output of `Planner.plan(...)`
# ---------------------------------------------------------------------------


class InvestigationPlan(BaseModel):
    """A plan the executor branches will run against the evidence.

    §3.6: every plan must include >= 1 negative hypothesis. The full schema
    (with `parsed_positive_hypothesis_ids`, `parsed_negative_hypothesis_ids`,
    `parsed_success_criteria_hash` for the comprehension_gate) lands in
    `verdict/schemas/plan.py` (W1.B.5).
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    hypotheses: list[Hypothesis] = Field(min_length=1)
    tool_budget: int = Field(gt=0)
    success_criteria: str = Field(min_length=1)

    @model_validator(mode="after")
    def _at_least_one_negative_hypothesis(self) -> InvestigationPlan:
        """§3.6 — every plan ships at least one negative hypothesis."""
        negatives = [h for h in self.hypotheses if h.polarity == "negative"]
        if not negatives:
            raise ValueError(
                "InvestigationPlan requires >= 1 negative hypothesis (§3.6). "
                "A plan without a falsifiable null is not a plan."
            )
        return self
