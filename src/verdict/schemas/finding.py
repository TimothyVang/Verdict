from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from verdict.schemas.artifact_class import ArtifactClass
from verdict.schemas.caveat_id import CaveatID
from verdict.schemas.verdict_status import VerdictStatus
from verdict.schemas.version import SCHEMA_VERSION

EXECUTION_TECHNIQUE_PREFIXES = ("T1059", "T1106", "T1204", "T1218", "T1543", "T1547")
MITRE_TECHNIQUE_RE = re.compile(r"^T\d{4}(\.\d{3})?$")
AVAILABLE_CAVEAT_TRIGGERS = {
    ArtifactClass.AMCACHE: CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC,
    ArtifactClass.SHIMCACHE: CaveatID.SHIMCACHE_ORDER_CHANGED_WIN81,
    ArtifactClass.PREFETCH: CaveatID.PREFETCH_SSD_DISABLED,
    ArtifactClass.MFT: CaveatID.MFT_SI_STOMPABLE,
    ArtifactClass.USNJRNL: CaveatID.USNJRNL_WRAPS,
    ArtifactClass.SYSMON_1: CaveatID.SYSMON_PROCESSGUID_OVER_PID,
}


class ReviewState(StrEnum):
    """Human review state, separate from forensic verdict status."""

    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Finding(BaseModel):
    """Investigation finding awaiting schema validators in later W1.B tasks."""

    finding_id: str
    schema_version: int = SCHEMA_VERSION
    case_id: str
    plan_id: str
    hypothesis_ids: list[str]
    artifact_paths: list[Path] = Field(min_length=2)
    artifact_classes: list[ArtifactClass] = Field(min_length=2)
    caveats_acknowledged: list[CaveatID] = Field(default_factory=list)
    mitre_technique: str | None
    evtx_4624_logon_types: list[int] = Field(default_factory=list)
    evidence_hashes: dict[Path, str]
    rationale: str
    status: VerdictStatus
    review_state: ReviewState = ReviewState.DRAFT
    contested_reasons: list[str] = Field(default_factory=list)

    @field_validator("mitre_technique")
    @classmethod
    def _mitre_technique_shape(cls, value: str | None) -> str | None:
        if value is not None and not MITRE_TECHNIQUE_RE.fullmatch(value):
            raise ValueError("mitre_technique must match ^T\\d{4}(\\.\\d{3})?$")
        return value

    @model_validator(mode="after")
    def _forensic_corroboration(self) -> Finding:
        is_execution = self.mitre_technique and self.mitre_technique.startswith(
            EXECUTION_TECHNIQUE_PREFIXES
        )
        if is_execution and len(set(self.artifact_classes)) < 2:
            raise ValueError("execution claims require two distinct artifact classes")

        acknowledged = set(self.caveats_acknowledged)
        for artifact_class, required_caveat in AVAILABLE_CAVEAT_TRIGGERS.items():
            if artifact_class in self.artifact_classes and required_caveat not in acknowledged:
                raise ValueError(f"{required_caveat.value} must be acknowledged")

        evtx_4624_cited = ArtifactClass.EVTX_4624 in self.artifact_classes
        evtx_type_requires_caveat = not self.evtx_4624_logon_types or any(
            logon_type in {3, 10} for logon_type in self.evtx_4624_logon_types
        )
        if (
            evtx_4624_cited
            and evtx_type_requires_caveat
            and CaveatID.LOGON_TYPE_3_VS_10 not in acknowledged
        ):
            raise ValueError(f"{CaveatID.LOGON_TYPE_3_VS_10.value} must be acknowledged")

        return self
