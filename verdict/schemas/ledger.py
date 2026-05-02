"""LedgerEntry schema — cryptographic chain-of-custody record.

Every tool call, finding, approval, and lifecycle event is captured as a
LedgerEntry appended to ``cases/<id>/ledger.jsonl``.

The three-tier ID hierarchy (case_id → langfuse_trace_id →
langgraph_checkpoint_id) is the chain-of-custody backbone per NIST SP 800-86.

See ARCHITECTURE.md §5 for the full schema narrative.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from verdict.schemas.mode import Mode

# ---------------------------------------------------------------------------
# LedgerEntry
# ---------------------------------------------------------------------------

_EVENT_TYPES = Literal[
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


class LedgerEntry(BaseModel):
    """A single immutable record in the JSONL ledger.

    ``mode_at_case_init`` is written once by the ``case_init`` event and
    must remain identical on every subsequent entry within the same case.
    The field is therefore ``frozen=False`` at the Pydantic level — Pydantic
    v2 does not support per-field frozen on a non-frozen model — but the
    runtime enforces immutability via ``LedgerWriter.append()``, which
    rejects any attempt to write a ``mode_at_case_init`` value that differs
    from the value recorded in the first ``case_init`` entry.
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    entry_id: str = Field(description="ULID — unique per entry")
    case_id: str = Field(description="Eternal root ID for the whole case")
    finding_id: str | None = Field(default=None)
    event_type: _EVENT_TYPES

    timestamp_utc: datetime = Field(description="UTC timestamp with Z suffix")

    # ------------------------------------------------------------------
    # Mode lock — written once at case_init, immutable thereafter
    # ------------------------------------------------------------------
    mode_at_case_init: Mode = Field(
        description=(
            "The Mode that was active when this case was initialised. "
            "Identical on every entry within a case. "
            "Enforcement: LedgerWriter.append() raises ModeLockedError on mismatch."
        )
    )
    verifier_strategy_used: str = Field(default="")

    # ------------------------------------------------------------------
    # Langfuse cross-references
    # ------------------------------------------------------------------
    langfuse_session_id: str = Field(default="", description="= case_id")
    langfuse_trace_id: str = Field(default="")
    langfuse_root_span_id: str = Field(default="")
    langfuse_leaf_span_ids: list[str] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # LangGraph cross-references
    # ------------------------------------------------------------------
    langgraph_thread_id: str = Field(default="", description="= case_id")
    langgraph_checkpoint_id: str = Field(default="")

    # ------------------------------------------------------------------
    # Examination-environment metadata (NIST SP 800-86 §5.1.4)
    # ------------------------------------------------------------------
    microsandbox_version: str | None = None
    rootfs_sha256: str | None = None
    tool_version: str | None = None
    kernel_version: str | None = None

    # ------------------------------------------------------------------
    # Per-output-file hashes (NIST SP 800-86 §5.1.2)
    # ------------------------------------------------------------------
    output_files_sha256: dict[str, str] = Field(default_factory=dict)

    # ------------------------------------------------------------------
    # Ledger chain integrity
    # ------------------------------------------------------------------
    payload: dict = Field(default_factory=dict)
    payload_redactions: list[str] = Field(default_factory=list)
    prev_entry_hash: str = Field(default="")
    hmac_sig: str = Field(default="")
    schema_version: int = Field(default=1)

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _timestamp_must_be_utc(self) -> LedgerEntry:
        """Timestamps must be timezone-aware UTC (Z suffix when serialised)."""
        ts = self.timestamp_utc
        if ts.tzinfo is None:
            raise ValueError(
                f"timestamp_utc must be timezone-aware UTC; got naive datetime {ts!r}"
            )
        return self

    model_config = {"frozen": False}
