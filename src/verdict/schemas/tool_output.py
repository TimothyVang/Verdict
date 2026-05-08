from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Self

from blake3 import blake3
from pydantic import BaseModel

from verdict.schemas.version import SCHEMA_VERSION


class Artifact(BaseModel):
    """Structured artifact extracted from a tool output."""

    artifact_id: str
    evidence_path: Path
    artifact_type: str
    raw_fields: dict
    extraction_confidence: float = 1.0


class ToolOutput(BaseModel):
    """Base contract for SIFT tool wrapper outputs."""

    tool_name: str
    tool_version: str
    invocation_args: list[str]
    invocation_hash: str
    stdout_hash: str
    stderr_hash: str
    exit_code: int
    parsed_artifacts: list[Artifact]
    parse_warnings: list[str] = []
    sanitization_flags: list[str] = []
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def from_invocation(
        cls,
        *,
        tool_name: str,
        tool_version: str,
        invocation_args: list[str],
        evidence_hash: str,
        stdout: bytes,
        stderr: bytes,
        exit_code: int,
        parsed_artifacts: list[Artifact],
    ) -> Self:
        return cls(
            tool_name=tool_name,
            tool_version=tool_version,
            invocation_args=invocation_args,
            invocation_hash=compute_invocation_hash(
                tool_name=tool_name,
                tool_version=tool_version,
                invocation_args=invocation_args,
                evidence_hash=evidence_hash,
            ),
            stdout_hash=sha256(stdout).hexdigest(),
            stderr_hash=sha256(stderr).hexdigest(),
            exit_code=exit_code,
            parsed_artifacts=parsed_artifacts,
        )


def compute_invocation_hash(
    *, tool_name: str, tool_version: str, invocation_args: list[str], evidence_hash: str
) -> str:
    args_payload = b"\x00".join(arg.encode() for arg in invocation_args)
    payload = (
        tool_name.encode()
        + b"\x00"
        + tool_version.encode()
        + b"\x00"
        + args_payload
        + b"\x00"
        + evidence_hash.encode()
    )
    return blake3(payload).hexdigest()
