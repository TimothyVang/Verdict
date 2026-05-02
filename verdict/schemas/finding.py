"""Finding schema — §3.2 multi-artifact corroboration + §3.3 caveat field.

artifact_classes field (W1.B.8) present.
caveats_acknowledged field (W1.B.9): list[CaveatID] defaults to [].
Validators enforcing §3.3 triggers are added in W1.B.10.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from verdict.schemas.artifact_class import ArtifactClass
from verdict.schemas.caveat_id import CaveatID


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

    # §3.2 — both fields require >=2 entries.
    artifact_paths: list[str] = Field(min_length=2)
    artifact_classes: list[ArtifactClass] = Field(min_length=2)

    # §3.3 — Tier-1 caveat acknowledgment. Typed list[CaveatID] so that
    # bare strings not in the enum are rejected by Pydantic before any
    # model validator runs. Default is empty; validators in W1.B.10 enforce
    # that the right caveats are present when the matching artifact_classes
    # trigger them.
    caveats_acknowledged: list[CaveatID] = Field(default_factory=list)

    status: VerdictStatus
    review_state: ReviewState = "DRAFT"
