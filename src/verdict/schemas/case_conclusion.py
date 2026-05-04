from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class CaseConclusion(BaseModel):
    """Terminal case-level conclusion, separate from per-finding verdict status."""

    status: Literal["NO_EVIL_FOUND", "EVIL_FOUND", "UNVERIFIABLE"]
    playbook_steps_executed: list[str] = Field(min_length=1)
    evidence_hashes: dict[Path, str]
    rationale: str
