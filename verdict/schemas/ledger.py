"""LedgerEntry — append-only HMAC-signed JSONL row.

Three-tier ID hierarchy (ARCHITECTURE.md §5):
  case_id               — ROOT; eternal for case lifetime
  langfuse_trace_id     — one per graph.invoke() call (many per case)
  langgraph_checkpoint_id — super-step checkpoint at write time

Mode lock: mode_at_case_init is set once at case_init and immutable
thereafter (CLAUDE.md §3.4). ConfigDict(frozen=True) enforces this.

NIST SP 800-86:
  §5.1.2 — per-output-file SHA-256 in output_files_sha256
  §5.1.4 — examination-environment metadata:
            microsandbox_version, rootfs_sha256, tool_version, kernel_version

Chain integrity: prev_entry_hash + hmac_sig form the HMAC-signed append-only
chain. Credential isolation (CLAUDE.md §3.9): auth fields are redacted before
hashing; payload_redactions records which keys were stripped.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from verdict.schemas.version import SCHEMA_VERSION

# ---------------------------------------------------------------------------
# Type aliases — canonical string Literals per ARCHITECTURE.md §1 and §9
# ---------------------------------------------------------------------------

Mode = Literal["cloud", "airgap", "dual"]

EventType = Literal[
    "case_init",
    "tool_call",
    "finding",
    "approval",
    "rejection",
    "mode_lock",
    "comprehension_check",
    "critique_verdict",
    "pivot",
    "exhausted_replan",
    "evidence_hash_recheck",
    "sandbox_failure",
    "planner_cot",
]


# ---------------------------------------------------------------------------
# LedgerEntry schema
# ---------------------------------------------------------------------------

class LedgerEntry(BaseModel):
    """Append-only HMAC-signed JSONL row.

    Frozen post-construction — any mutation attempt raises ValidationError.
    """

    model_config = ConfigDict(frozen=True)

    entry_id: str
    schema_version: int = SCHEMA_VERSION

    # Three-tier ID hierarchy (ARCHITECTURE.md §5)
    case_id: str
    finding_id: str | None = None
    event_type: EventType
    timestamp_utc: datetime
    mode_at_case_init: Mode
    verifier_strategy_used: str

    # Langfuse cross-references
    langfuse_session_id: str
    langfuse_trace_id: str
    langfuse_root_span_id: str
    langfuse_leaf_span_ids: list[str] = Field(default_factory=list)

    # LangGraph cross-references
    langgraph_thread_id: str
    langgraph_checkpoint_id: str

    # Examination-environment metadata (NIST SP 800-86 §5.1.4)
    microsandbox_version: str | None = None
    rootfs_sha256: str | None = None
    tool_version: str | None = None
    kernel_version: str | None = None

    # Per-output-file hashes (NIST SP 800-86 §5.1.2)
    output_files_sha256: dict[str, str] = Field(default_factory=dict)

    # Ledger chain integrity
    payload: dict
    payload_redactions: list[str] = Field(default_factory=list)
    prev_entry_hash: str
    hmac_sig: str
