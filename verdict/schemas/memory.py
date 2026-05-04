"""DFIR self-evolving memory schemas.

These models enforce evidence-backed memory evolution for SANS-aligned
incident response workflows. Memory is never overwritten in-place;
updates advance version while preserving lineage and auditability.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class MemoryType(str, Enum):
    """Allowed memory layers for DFIR workflows."""

    CASE = "case"
    TECHNIQUE = "technique"
    PATTERN = "pattern"
    META = "meta"


class ApprovalState(str, Enum):
    """Promotion state for memory entries."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class MemoryOperation(str, Enum):
    """Permitted mutation operations for controlled self-evolution."""

    STRENGTHEN = "strengthen"
    WEAKEN = "weaken"
    FORK = "fork"
    DEPRECATE = "deprecate"
    REVALIDATE = "revalidate"


class MemoryEntry(BaseModel):
    """Evidence-backed memory unit with governance fields."""

    memory_id: str
    type: MemoryType
    statement: str = Field(min_length=10)
    evidence_refs: list[str] = Field(default_factory=list)
    source_reliability: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    counterevidence: list[str] = Field(default_factory=list)
    scope: str
    mitre: list[str] = Field(default_factory=list)
    created_at: datetime
    last_validated_at: datetime
    expiry: datetime | None = None
    author: str
    approval_state: ApprovalState = ApprovalState.PROPOSED
    version: int = Field(ge=1)
    lineage: str | None = None

    @model_validator(mode="after")
    def validate_memory_constraints(self) -> "MemoryEntry":
        """Enforce DFIR constraints by memory layer."""
        if self.type in (MemoryType.TECHNIQUE, MemoryType.PATTERN, MemoryType.META):
            if not self.evidence_refs:
                raise ValueError("persistent memory requires at least one evidence reference")

        if self.expiry is not None and self.expiry <= self.created_at:
            raise ValueError("expiry must be after created_at")

        if self.last_validated_at < self.created_at:
            raise ValueError("last_validated_at must be on/after created_at")

        return self


class MemoryUpdateProposal(BaseModel):
    """Immutable update proposal subject to validation and policy gates."""

    proposal_id: str
    memory_id: str
    operation: MemoryOperation
    rationale: str = Field(min_length=10)
    new_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    new_statement: str | None = None
    additional_evidence_refs: list[str] = Field(default_factory=list)
    approver: str | None = None
    approved_at: datetime | None = None
