"""Finding schema — §3.2 multi-artifact corroboration enforcement.

artifact_classes: list[ArtifactClass] with min_length=2 (W1.B.8).
SANS FOR500 doctrine: no single artifact class proves execution.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from verdict.schemas.artifact_class import ArtifactClass


class VerdictStatus(str, Enum):
    """§3.6 — canonical verdict statuses. Exactly six values, no others."""

    VETTED_CLOUD = "vetted_cloud"
    VETTED_AIRGAP = "vetted_airgap"
    VETTED_DUAL = "vetted_dual"
    CONTESTED = "contested"
    UNVERIFIABLE = "unverifiable"
    EXHAUSTED_REPLAN = "exhausted_replan"


ReviewState = Literal["DRAFT", "APPROVED", "REJECTED"]


class Finding(BaseModel):
    """Vetted forensic conclusion with multi-artifact corroboration (§3.2)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: Literal["v1"] = "v1"

    finding_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)

    mitre_technique: str

    # §3.2 — both fields require >=2 entries; single-artifact claims are
    # forensically unsound per FOR500 doctrine.
    artifact_paths: list[str] = Field(min_length=2)
    artifact_classes: list[ArtifactClass] = Field(min_length=2)

    status: VerdictStatus
    review_state: ReviewState = "DRAFT"
