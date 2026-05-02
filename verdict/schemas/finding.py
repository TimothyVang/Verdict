"""Finding schema — §3.1–§3.6 contract enforcement.

Encodes CLAUDE.md §3.1–§3.6 invariants at the Pydantic v2 layer. The
validator IS the contract; if a contributor can construct a Finding that
violates §3, the validator is broken.

§3.2 — multi-artifact corroboration: artifact_paths and artifact_classes
       both have min_length=2. Execution-class techniques (T1059, T1106,
       T1204, T1218, T1543, T1547) require >=2 *distinct* ArtifactClass
       values, enforced by `_execution_claims_need_two_classes`.
§3.3 — Tier-1 caveat acknowledgment: keyed by `artifact_classes`
       membership. Four pure-membership triggers encoded here:
         AMCACHE    → AMCACHE_LASTMODIFIED_NOT_EXEC
         SHIMCACHE  → SHIMCACHE_ORDER_CHANGED_WIN81
         PREFETCH   → PREFETCH_SSD_DISABLED
         MFT        → MFT_SI_STOMPABLE  or  USNJRNL_WRAPS
       Not encoded here (see comment below):
         LOGON_TYPE_3_VS_10       — keyed by EVTX_4624 AND LogonType field
         SYSMON_PROCESSGUID_OVER_PID — keyed by a correlation step, not class
§3.4 — mode lock lives on LedgerEntry, not Finding.
§3.5 — MITRE technique regex `^T\\d{4}(\\.\\d{3})?$` enforces shape.
§3.6 — VerdictStatus is exactly the canonical six values; review_state
       (DRAFT / APPROVED / REJECTED) is a separate Literal field.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from verdict.schemas.artifact_class import ArtifactClass
from verdict.schemas.caveat_id import CaveatID

# §3.2 — execution-class MITRE technique parents that require >=2 distinct
# ArtifactClass values. Sub-techniques (e.g. T1059.001) match by parent.
_EXECUTION_PARENTS: frozenset[str] = frozenset(
    (
        "T1059",  # Command and Scripting Interpreter
        "T1106",  # Native API
        "T1204",  # User Execution
        "T1218",  # System Binary Proxy Execution (LOLBins)
        "T1543",  # Create or Modify System Process
        "T1547",  # Boot or Logon Autostart Execution
    )
)

# §3.3 — caveat triggers keyed by ArtifactClass membership. Each entry:
#   (frozenset of acceptable CaveatIDs, triggering ArtifactClass)
#
# "acceptable" means: if the triggering class is cited, AT LEAST ONE of
# the acceptable caveats must appear in caveats_acknowledged. For AMCACHE,
# SHIMCACHE, and PREFETCH there is exactly one acceptable caveat. For MFT
# either MFT_SI_STOMPABLE or USNJRNL_WRAPS satisfies the trigger (both
# cover different aspects of the same MFT artifact family).
#
# Two Tier-1 caveats are deliberately NOT in this table:
#
#   * LOGON_TYPE_3_VS_10 — triggered by EVTX_4624 class AND
#     EvtxRecord.LogonType ∈ {3, 10}. LogonType lives on EvtxRecord, not
#     on Finding; this caveat is enforced upstream by the EVTX executor
#     wrapper at parse time. (EVTX_4624 is also not in the ArtifactClass
#     enum's 13-member set per W1.B.1.)
#
#   * SYSMON_PROCESSGUID_OVER_PID — triggered by a *correlation step*
#     that uses PID alone, not by SYSMON_1 citation per se. A Finding can
#     legitimately cite SYSMON_1 while keying correlation on ProcessGuid;
#     the caveat fires on a wrong-shaped correlation, not a citation.
#     Enforcement belongs in the correlator, not the Finding schema.
_CAVEAT_TRIGGERS: tuple[tuple[frozenset[CaveatID], ArtifactClass], ...] = (
    (frozenset({CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC}), ArtifactClass.AMCACHE),
    (frozenset({CaveatID.SHIMCACHE_ORDER_CHANGED_WIN81}), ArtifactClass.SHIMCACHE),
    (frozenset({CaveatID.PREFETCH_SSD_DISABLED}), ArtifactClass.PREFETCH),
    (frozenset({CaveatID.MFT_SI_STOMPABLE, CaveatID.USNJRNL_WRAPS}), ArtifactClass.MFT),
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

    schema_version: Literal["v1"] = "v1"

    finding_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)

    # §3.5 — shape-validated MITRE technique.
    mitre_technique: str

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
    def _execution_claims_need_two_classes(self) -> "Finding":
        """Reject execution-class techniques that only cite one distinct class.

        Checks whether `mitre_technique` parent is in the execution set, then
        asserts len(set(artifact_classes)) >= 2. Two paths from PROCESS_MEMORY
        alone do not constitute multi-class corroboration.
        """
        head = self.mitre_technique.split(".", 1)[0]
        if head not in _EXECUTION_PARENTS:
            return self
        if len(set(self.artifact_classes)) < 2:
            raise ValueError(
                f"execution-class MITRE technique {self.mitre_technique!r} requires "
                ">=2 distinct artifact_classes; got "
                f"{[c.value for c in self.artifact_classes]} "
                "(see CLAUDE.md §3.2)"
            )
        return self

    # ------------------------------------------------------------------
    # §3.3 — Tier-1 caveat acknowledgment validators.
    # One validator per CaveatID where the trigger is pure class-membership.
    # ------------------------------------------------------------------
    @model_validator(mode="after")
    def _amcache_caveat_required(self) -> "Finding":
        """§3.3 — citing AMCACHE requires AMCACHE_LASTMODIFIED_NOT_EXEC."""
        if ArtifactClass.AMCACHE in self.artifact_classes:
            if CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC not in self.caveats_acknowledged:
                raise ValueError(
                    "Finding cites 'amcache' without acknowledging caveat "
                    f"'{CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC.value}' "
                    "(see CLAUDE.md §3.3)"
                )
        return self

    @model_validator(mode="after")
    def _shimcache_caveat_required(self) -> "Finding":
        """§3.3 — citing SHIMCACHE requires SHIMCACHE_ORDER_CHANGED_WIN81."""
        if ArtifactClass.SHIMCACHE in self.artifact_classes:
            if CaveatID.SHIMCACHE_ORDER_CHANGED_WIN81 not in self.caveats_acknowledged:
                raise ValueError(
                    "Finding cites 'shimcache' without acknowledging caveat "
                    f"'{CaveatID.SHIMCACHE_ORDER_CHANGED_WIN81.value}' "
                    "(see CLAUDE.md §3.3)"
                )
        return self

    @model_validator(mode="after")
    def _prefetch_caveat_required(self) -> "Finding":
        """§3.3 — citing PREFETCH requires PREFETCH_SSD_DISABLED."""
        if ArtifactClass.PREFETCH in self.artifact_classes:
            if CaveatID.PREFETCH_SSD_DISABLED not in self.caveats_acknowledged:
                raise ValueError(
                    "Finding cites 'prefetch' without acknowledging caveat "
                    f"'{CaveatID.PREFETCH_SSD_DISABLED.value}' "
                    "(see CLAUDE.md §3.3)"
                )
        return self

    @model_validator(mode="after")
    def _mft_caveat_required(self) -> "Finding":
        """§3.3 — citing MFT requires MFT_SI_STOMPABLE or USNJRNL_WRAPS.

        ArtifactClass.MFT covers both $MFT and $J/UsnJrnl. Either caveat
        satisfies the trigger because they cover different evidentiary risks
        that both apply to the MFT artifact family.
        """
        if ArtifactClass.MFT in self.artifact_classes:
            ack = set(self.caveats_acknowledged)
            if not ack.intersection(
                {CaveatID.MFT_SI_STOMPABLE, CaveatID.USNJRNL_WRAPS}
            ):
                raise ValueError(
                    "Finding cites 'mft' without acknowledging either caveat "
                    f"('{CaveatID.MFT_SI_STOMPABLE.value}' or "
                    f"'{CaveatID.USNJRNL_WRAPS.value}') "
                    "(see CLAUDE.md §3.3)"
                )
        return self
