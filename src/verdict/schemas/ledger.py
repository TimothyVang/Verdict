from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from verdict.schemas.version import SCHEMA_VERSION

LedgerEventType = Literal[
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
    "case_conclusion",
]


class LedgerEntry(BaseModel):
    """Append-only ledger row with explicit observability and checkpoint IDs."""

    entry_id: str
    schema_version: int = SCHEMA_VERSION
    case_id: str
    finding_id: str | None
    event_type: LedgerEventType
    timestamp_utc: datetime
    mode_at_case_init: str
    verifier_strategy_used: str
    langfuse_session_id: str
    langfuse_trace_id: str
    langfuse_root_span_id: str
    langfuse_leaf_span_ids: list[str]
    langgraph_thread_id: str
    langgraph_checkpoint_id: str
    microsandbox_version: str
    rootfs_sha256: str
    tool_version: str
    kernel_version: str
    output_files_sha256: dict[str, str] = {}
    payload: dict
    payload_redactions: list[str] = []
    prev_entry_hash: str
    hmac_sig: str
