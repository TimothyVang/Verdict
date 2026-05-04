from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from verdict.schemas.verdict_status import VerdictStatus


class VerificationCandidate(BaseModel):
    """Single verifier's verdict over a finding candidate."""

    source: str
    artifact_paths: tuple[str, ...]
    mitre_technique: str | None
    status: VerdictStatus


class VerificationResult(BaseModel):
    """Quorum result emitted by a verification strategy."""

    status: VerdictStatus
    agreement_count: int
    candidates: list[VerificationCandidate]


class VerifierStrategy(Protocol):
    """Verification strategy contract used by quorum dispatch."""

    def verify(self, candidates: list[VerificationCandidate]) -> VerificationResult: ...
