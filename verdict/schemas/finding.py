"""Finding — the schema a SANS judge will scrutinise.

Encodes CLAUDE.md §3.1–§3.6 invariants at the Pydantic v2 layer. The
validator IS the contract; if a contributor can construct a Finding that
violates §3, the validator is broken.

§3.1 — evidence integrity (per-output-file SHA-256 lives on LedgerEntry,
       not Finding; this schema does not write evidence).
§3.2 — multi-artifact corroboration: artifact_paths and artifact_classes
       both have min_length=2; execution-class techniques (T1059, T1106,
       T1204, T1218, T1543, T1547) require >=2 *distinct* ArtifactClass
       values, enforced by `_execution_requires_two_classes`.
§3.3 — Tier-1 caveat acknowledgment: keyed by `artifact_classes`
       membership. Citing an AMCACHE artifact without
       AMCACHE_LASTMODIFIED_NOT_EXEC is rejected.
§3.4 — mode lock lives on LedgerEntry, not Finding.
§3.5 — MITRE technique regex `^T\\d{4}(\\.\\d{3})?$` enforces shape.
       Sub-technique-required is an Inspect AI scorer, not a schema rule.
§3.6 — VerdictStatus is exactly the canonical six values; review_state
       (DRAFT / APPROVED / REJECTED) is a separate Literal field.

Phrasing ("evidence consistent with X" vs "X did this") is a prompt-layer
concern; schema validates structure, not narrative.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from verdict.schemas.artifact_class import ArtifactClass
from verdict.schemas.caveat_id import CaveatID
from verdict.schemas.version import SCHEMA_VERSION

# §3.5 — MITRE technique regex. Shape only; sub-technique-required policy
# lives in the Inspect AI `mitre_subtechnique_precision` scorer.
_MITRE_TECHNIQUE_RE: re.Pattern[str] = re.compile(r"^T\d{4}(\.\d{3})?$")

# §3.2 — execution-class MITRE technique parents that require >=2 distinct
# ArtifactClass values. Sub-techniques (e.g. T1059.001) match by parent.
_EXECUTION_PARENTS: tuple[str, ...] = (
    "T1059",  # Command and Scripting Interpreter
    "T1106",  # Native API
    "T1204",  # User Execution
    "T1218",  # System Binary Proxy Execution (LOLBins)
    "T1543",  # Create or Modify System Process
    "T1547",  # Boot or Logon Autostart Execution
)

# §3.3 — caveat triggers keyed by ArtifactClass membership.  Each row
# says: if any of the listed ArtifactClass members appears in
# `artifact_classes`, the matching CaveatID must appear in
# `caveats_acknowledged`.
#
# MFT_SI_STOMPABLE and USNJRNL_WRAPS both share the MFT artifact class
# (MFT covers $MFT and $J/UsnJrnl per the existing enum's docstring).
# Acknowledging *either* caveat satisfies an MFT citation; both must be
# permitted.
_CAVEAT_TRIGGERS: tuple[tuple[tuple[CaveatID, ...], ArtifactClass], ...] = (
    ((CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC,), ArtifactClass.AMCACHE),
    ((CaveatID.SHIMCACHE_ORDER_CHANGED_WIN81,), ArtifactClass.SHIMCACHE),
    ((CaveatID.PREFETCH_SSD_DISABLED,), ArtifactClass.PREFETCH),
    ((CaveatID.MFT_SI_STOMPABLE, CaveatID.USNJRNL_WRAPS), ArtifactClass.MFT),
)


class VerdictStatus(str, Enum):
    """§3.6 — canonical verdict statuses. Exactly six values, no others.

    `VETTED_*` come out of a `VerifierStrategy` quorum; `EXHAUSTED_REPLAN`
    comes from `finalize_node` mapping the replan budget; `UNVERIFIABLE`
    is a first-class outcome rewarded by the SANS judge rubric.
    """

    VETTED_CLOUD = "vetted_cloud"
    VETTED_AIRGAP = "vetted_airgap"
    VETTED_DUAL = "vetted_dual"
    CONTESTED = "contested"
    UNVERIFIABLE = "unverifiable"
    EXHAUSTED_REPLAN = "exhausted_replan"


# §3.6 — review_state is orthogonal to VerdictStatus. Tracks human approval
# on a Finding regardless of the engine quorum outcome.
ReviewState = Literal["DRAFT", "APPROVED", "REJECTED"]


class Finding(BaseModel):
    """A vetted forensic conclusion with multi-artifact corroboration.

    Constructed by `quorum_node`, persisted to the ledger, and signed at
    approval time. Validators in this class are the §3 contract.
    """

    model_config = ConfigDict(
        # Reject extra fields — drift in the schema is drift in the contract.
        extra="forbid",
        # Run validators on attribute assignment too (defence-in-depth).
        validate_assignment=True,
    )

    schema_version: int = SCHEMA_VERSION

    finding_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)

    # §3.5 — shape-validated MITRE technique. Required (not Optional) so the
    # execution-class validator has deterministic input.
    mitre_technique: str = Field(pattern=_MITRE_TECHNIQUE_RE.pattern)

    # §3.2 — multi-artifact corroboration. Both fields min_length=2.
    artifact_paths: list[str] = Field(min_length=2)
    artifact_classes: list[ArtifactClass] = Field(min_length=2)

    # §3.3 — Tier-1 caveat acknowledgment. Typed list[CaveatID] — bare
    # strings that don't map to an enum member are rejected by Pydantic
    # before the validator runs.
    caveats_acknowledged: list[CaveatID] = Field(default_factory=list)

    # §3.6 — engine-quorum verdict (one of six canonical values).
    status: VerdictStatus

    # §3.6 — orthogonal human-approval state.
    review_state: ReviewState = "DRAFT"

    # ------------------------------------------------------------------
    # §3.2 — execution-class techniques require >=2 distinct ArtifactClass
    # values, not just two paths in the same class.
    # ------------------------------------------------------------------
    @model_validator(mode="after")
    def _execution_requires_two_classes(self) -> "Finding":
        if not self._is_execution_claim():
            return self
        if len(set(self.artifact_classes)) < 2:
            raise ValueError(
                "execution-class MITRE technique "
                f"{self.mitre_technique!r} requires >=2 distinct "
                f"artifact_classes; got {[c.value for c in self.artifact_classes]} "
                "(see CLAUDE.md §3.2)"
            )
        return self

    def _is_execution_claim(self) -> bool:
        """True if `mitre_technique` parent matches the §3.2 execution set.

        Matches both bare parent (`T1059`) and sub-techniques (`T1059.001`)
        by anchoring on the leading 5 characters.
        """
        head = self.mitre_technique.split(".", 1)[0]
        return head in _EXECUTION_PARENTS

    # ------------------------------------------------------------------
    # §3.3 — Tier-1 caveat acknowledgment. AMCACHE artifact requires
    # AMCACHE_LASTMODIFIED_NOT_EXEC, etc. The full _CAVEAT_TRIGGERS table
    # encodes the seven canonical mappings.
    # ------------------------------------------------------------------
    @model_validator(mode="after")
    def _caveats_acknowledged_required(self) -> "Finding":
        cited = set(self.artifact_classes)
        ack = set(self.caveats_acknowledged)
        for acceptable_caveats, triggering_class in _CAVEAT_TRIGGERS:
            if triggering_class in cited and not ack.intersection(acceptable_caveats):
                expected = " or ".join(c.value for c in acceptable_caveats)
                raise ValueError(
                    f"Finding cites {triggering_class.value!r} without "
                    f"acknowledging caveat ({expected}) "
                    "(see CLAUDE.md §3.3)"
                )
        return self
