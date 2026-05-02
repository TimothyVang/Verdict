"""ToolOutput and Artifact schemas.

Chain-of-custody contract for every tool invocation (CLAUDE.md §3.1):
  - invocation_hash = blake3(tool_name + tool_version + args_json + evidence_hash)
  - output_files_sha256: per-output-file SHA-256 map (NIST SP 800-86 §5.1.2)
  - stdout_sha256: SHA-256 of raw stdout bytes
"""

from __future__ import annotations

import json
from pathlib import Path

from blake3 import blake3 as _blake3
from pydantic import BaseModel, ConfigDict, Field, model_validator

from verdict.schemas.version import SCHEMA_VERSION


class Artifact(BaseModel):
    """A single parsed artifact extracted from tool output."""

    model_config = ConfigDict(frozen=True)

    artifact_id: str
    evidence_path: Path
    artifact_type: str
    raw_fields: dict
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ToolOutput(BaseModel):
    """Typed output for every SIFT tool invocation."""

    tool_name: str
    tool_version: str
    args: dict
    evidence_hash: str
    invocation_hash: str
    output_files_sha256: dict[str, str] = Field(default_factory=dict)
    stdout_sha256: str

    parsed_artifacts: list[Artifact] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)
    sanitization_flags: list[str] = Field(default_factory=list)

    schema_version: int = SCHEMA_VERSION

    @model_validator(mode="after")
    def _verify_invocation_hash(self) -> "ToolOutput":
        """Enforce §3.1: invocation_hash must equal blake3(name+version+args+evidence)."""
        args_json = json.dumps(self.args, sort_keys=True)
        raw = (
            self.tool_name + self.tool_version + args_json + self.evidence_hash
        ).encode()
        expected = _blake3(raw).hexdigest()
        if self.invocation_hash != expected:
            raise ValueError(
                f"invocation_hash mismatch: "
                f"provided={self.invocation_hash!r}, "
                f"computed={expected!r}"
            )
        return self
