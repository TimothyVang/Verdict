from __future__ import annotations

import platform
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from verdict.ledger.writer import LedgerWriter


@dataclass(frozen=True)
class LedgerEmitter:
    """Graph wrapper that persists events through the hardened ledger writer."""

    ledger_path: Path
    hmac_key: bytes

    def emit(self, *, event_type: str, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        return LedgerWriter(self.ledger_path, self.hmac_key).write(
            {
                "entry_id": f"{case_id}:{event_type}:{timestamp}",
                "event_type": event_type,
                "case_id": case_id,
                "finding_id": payload.get("finding_id"),
                "timestamp_utc": timestamp,
                "mode_at_case_init": payload.get("mode_at_case_init", "CLOUD"),
                "verifier_strategy_used": payload.get("verifier_strategy_used", "not_run"),
                "langfuse_session_id": case_id,
                "langfuse_trace_id": payload.get("langfuse_trace_id", "local-graph"),
                "langfuse_root_span_id": payload.get("langfuse_root_span_id", "local-graph-root"),
                "langfuse_leaf_span_ids": payload.get("langfuse_leaf_span_ids", []),
                "langgraph_thread_id": case_id,
                "langgraph_checkpoint_id": payload.get("langgraph_checkpoint_id", event_type),
                "microsandbox_version": payload.get("microsandbox_version", "not_invoked"),
                "rootfs_sha256": payload.get("rootfs_sha256", "not_invoked"),
                "tool_version": payload.get("tool_version", "verdict-graph"),
                "kernel_version": platform.platform(),
                "output_files_sha256": payload.get("output_files_sha256", {}),
                "payload": payload,
            },
        )

    def last_entry(self) -> dict[str, Any]:
        return LedgerWriter(self.ledger_path, self.hmac_key).last_entry()
