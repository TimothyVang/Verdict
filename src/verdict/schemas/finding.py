from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from verdict.schemas.artifact_class import ArtifactClass
from verdict.schemas.caveat_id import CaveatID
from verdict.schemas.verdict_status import VerdictStatus
from verdict.schemas.version import SCHEMA_VERSION

EXECUTION_TECHNIQUE_PREFIXES = ("T1059", "T1106", "T1204", "T1218", "T1543", "T1547")
AVAILABLE_CAVEAT_TRIGGERS = {
    ArtifactClass.AMCACHE: CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC,
    ArtifactClass.SHIMCACHE: CaveatID.SHIMCACHE_ORDER_CHANGED_WIN81,
    ArtifactClass.PREFETCH: CaveatID.PREFETCH_SSD_DISABLED,
    ArtifactClass.MFT: CaveatID.MFT_SI_STOMPABLE,
    ArtifactClass.SYSMON_1: CaveatID.SYSMON_PROCESSGUID_OVER_PID,
}


class ReviewState(str, Enum):
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
    caveats_acknowledged: list[CaveatID] = []
    mitre_technique: str | None
    evidence_hashes: dict[Path, str]
    rationale: str
    status: VerdictStatus
    review_state: ReviewState = ReviewState.DRAFT
    contested_reasons: list[str] = []

    @model_validator(mode="after")
    def _forensic_corroboration(self) -> Finding:
        if self.mitre_technique and self.mitre_technique.startswith(EXECUTION_TECHNIQUE_PREFIXES):
            if len(set(self.artifact_classes)) < 2:
                raise ValueError("execution claims require two distinct artifact classes")

        acknowledged = set(self.caveats_acknowledged)
        for artifact_class, required_caveat in AVAILABLE_CAVEAT_TRIGGERS.items():
            if artifact_class in self.artifact_classes and required_caveat not in acknowledged:
                raise ValueError(f"{required_caveat.value} must be acknowledged")

        return self
