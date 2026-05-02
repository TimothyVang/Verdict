"""LedgerEntry — append-only HMAC-signed JSONL row.

Implements W1.B.11: three-tier ID hierarchy + examination-environment metadata.

Three explicit ID hierarchies (ARCHITECTURE.md §5):
  case_id               — ROOT; eternal for case lifetime
  langfuse_trace_id     — one per graph.invoke() call (many per case)
  langgraph_checkpoint_id — super-step checkpoint at write time

Mode lock: mode_at_case_init is set once at case_init and immutable
thereafter (CLAUDE.md §3.4). ConfigDict(frozen=True) enforces this at the
schema layer — any mutation attempt raises ValidationError.

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
    This enforces CLAUDE.md §3.4 mode lock and §3.9 chain-of-custody integrity
    at the schema layer; the ledger writer never needs to defend against
    accidental in-place updates.
    """

    model_config = ConfigDict(frozen=True)

    # ------------------------------------------------------------------
    # Entry identity
    # ------------------------------------------------------------------
    entry_id: str
    """ULID — unique per entry; used as key in Langfuse span attribute."""

    schema_version: int = 1
    """Schema version for migration safety; bump via verdict/schemas/version.py."""

    # ------------------------------------------------------------------
    # Three-tier ID hierarchy (ARCHITECTURE.md §5 / BUILD_PLAN W1.B.11)
    # ------------------------------------------------------------------
    case_id: str
    """ROOT — eternal; never changes for the lifetime of a case."""

    finding_id: str | None = None
    """None for infrastructure events; populated for finding/approval/rejection."""

    # ------------------------------------------------------------------
    # Event classification
    # ------------------------------------------------------------------
    event_type: EventType
    """One of 13 event types from CLAUDE.md §9 Ledger discipline."""

    timestamp_utc: datetime
    """UTC timestamp with tzinfo; must carry trailing Z when serialised."""

    # ------------------------------------------------------------------
    # Mode lock (CLAUDE.md §3.4)
    # ------------------------------------------------------------------
    mode_at_case_init: Mode
    """Set once at case_init. Immutable because the schema is frozen."""

    verifier_strategy_used: str
    """e.g. "CloudSelfConsistency" | "AirGapCrossEngine" | "DualLaneCrossEngine"."""

    # ------------------------------------------------------------------
    # Langfuse cross-references — explicit three-tier hierarchy
    # ------------------------------------------------------------------
    langfuse_session_id: str
    """= case_id; lifetime: full case."""

    langfuse_trace_id: str
    """One per graph.invoke() call; many per case."""

    langfuse_root_span_id: str
    """The planner_node span for this trace."""

    langfuse_leaf_span_ids: list[str] = Field(default_factory=list)
    """Tool-call spans contributing to this ledger entry."""

    # ------------------------------------------------------------------
    # LangGraph cross-references — explicit three-tier hierarchy
    # ------------------------------------------------------------------
    langgraph_thread_id: str
    """= case_id; lifetime: full case (SqliteSaver thread key)."""

    langgraph_checkpoint_id: str
    """Super-step checkpoint at write time; used for kill-9 resume."""

    # ------------------------------------------------------------------
    # Examination-environment metadata (NIST SP 800-86 §5.1.4 / W1.B.11)
    # ------------------------------------------------------------------
    microsandbox_version: str | None = None
    """Version of the microsandbox runtime that executed the tool call."""

    rootfs_sha256: str | None = None
    """SHA-256 / blake3 digest of the rootfs image used in the microVM."""

    tool_version: str | None = None
    """Version string of the forensic tool invoked (e.g. "volatility3 2.10.0")."""

    kernel_version: str | None = None
    """Kernel version string of the microVM host (e.g. "5.15.0-118-generic")."""

    # ------------------------------------------------------------------
    # Per-output-file hashes (NIST SP 800-86 §5.1.2 / CLAUDE.md §3.1)
    # ------------------------------------------------------------------
    output_files_sha256: dict[str, str] = Field(default_factory=dict)
    """Maps output-file path → SHA-256 digest for every file the tool emits."""

    # ------------------------------------------------------------------
    # Ledger chain integrity
    # ------------------------------------------------------------------
    payload: dict
    """Event-type-specific structured payload."""

    payload_redactions: list[str] = Field(default_factory=list)
    """Keys stripped from payload before hashing (e.g. "authorization", "api_key").
    Redaction happens in verdict/ledger/redaction.py BEFORE hashing/signing,
    per CLAUDE.md §3.9. Records what was removed for auditability."""

    prev_entry_hash: str
    """blake3 digest of the previous entry — forms the append-only chain."""

    hmac_sig: str
    """HMAC-SHA256 over (redacted payload + prev_entry_hash + entry_id).
    Key is TPM-backed when /dev/tpmrm0 is available, else gpg-encrypted per
    CLAUDE.md §3.9."""
