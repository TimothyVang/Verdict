"""ToolOutput and Artifact schemas — W1.B.7.

Chain-of-custody contract for every tool invocation (CLAUDE.md §3.1):
  - invocation_hash = blake3(tool_name + tool_version + args_json + evidence_hash)
  - output_files_sha256: per-output-file SHA-256 map (NIST SP 800-86 §5.1.2/§5.1.4)
  - stdout_sha256: SHA-256 of raw stdout bytes

These fields are MANDATORY and cryptographically verified at construction via
model_validator; they are not Optional, not nullable, and cannot be bypassed.
"""

from __future__ import annotations

import json
from pathlib import Path
from blake3 import blake3 as _blake3
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Artifact(BaseModel):
    """A single parsed artifact extracted from tool output.

    Appendix A.4 of BUILD_PLAN.md.  The `parsed_artifacts` list on ToolOutput
    is the discriminator surface for cross-engine quorum Jaccard comparison.
    """

    model_config = ConfigDict(frozen=True)

    artifact_id: str
    evidence_path: Path
    artifact_type: str
    raw_fields: dict
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ToolOutput(BaseModel):
    """Typed output for every SIFT tool invocation.

    Fields (per CLAUDE.md §3.1 + Appendix A.4):
      tool_name          — dotted name, e.g. "vol3.windows.pslist"
      tool_version       — version string, e.g. "vol3 2.10.0"
      args               — raw invocation arguments as a dict (serialised to
                           JSON deterministically when computing invocation_hash)
      evidence_hash      — SHA-256 hex of the evidence file(s) passed to this call,
                           as recorded in the EvidenceManifest at case_init
      invocation_hash    — blake3(tool_name + tool_version + args_json + evidence_hash)
                           computed over UTF-8 bytes; validated at construction
      output_files_sha256— {relative_path: sha256_hex} for every file the tool emits
      stdout_sha256      — SHA-256 hex of raw stdout bytes

    The model is intentionally NOT frozen so that LedgerEmitter can attach
    supplementary fields post-spawn; however, invocation_hash is enforced at
    model_validator time and cannot be patched without triggering re-validation
    (callers must reconstruct).
    """

    tool_name: str
    tool_version: str
    args: dict
    evidence_hash: str
    invocation_hash: str
    output_files_sha256: dict[str, str] = Field(default_factory=dict)
    stdout_sha256: str

    # Optional enrichment populated by wrappers / sanitisation scanner
    parsed_artifacts: list[Artifact] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)
    sanitization_flags: list[str] = Field(default_factory=list)

    # Schema versioning (W1.B.12 — bumping v1→v2 is a coordinated change)
    schema_version: int = 1

    @model_validator(mode="after")
    def _verify_invocation_hash(self) -> "ToolOutput":
        """Enforce §3.1: invocation_hash must equal blake3(name+version+args+evidence).

        Uses json.dumps(args, sort_keys=True) for deterministic serialisation
        regardless of dict insertion order.
        """
        args_json = json.dumps(self.args, sort_keys=True)
        raw = (
            self.tool_name + self.tool_version + args_json + self.evidence_hash
        ).encode()
        expected = _blake3(raw).hexdigest()
        if self.invocation_hash != expected:
            raise ValueError(
                f"invocation_hash mismatch: "
                f"provided={self.invocation_hash!r}, "
                f"computed={expected!r} "
                f"(blake3(tool_name={self.tool_name!r} + tool_version={self.tool_version!r} "
                f"+ args_json + evidence_hash={self.evidence_hash!r}))"
            )
        return self
