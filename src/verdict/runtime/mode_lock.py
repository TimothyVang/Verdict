from __future__ import annotations

import json
import platform
from datetime import UTC, datetime

from verdict.ledger.writer import LedgerWriter
from verdict.runtime.mode_detect import Mode


class ModeLockedError(RuntimeError):
    def __init__(self, *, case_id: str, original_mode: Mode, detected_mode: Mode) -> None:
        super().__init__(
            f"Case {case_id} was initialized in mode={original_mode.value}; "
            f"current environment is mode={detected_mode.value}. "
            "To re-run under the new mode, use: "
            f"verdict reverify {case_id} --mode {detected_mode.value}",
        )
        self.exit_code = 2


def initialize_mode_lock(*, writer: LedgerWriter, case_id: str, mode: Mode) -> dict:
    original_mode = _locked_mode(writer=writer, case_id=case_id)
    if original_mode is not None and original_mode is not mode:
        raise ModeLockedError(case_id=case_id, original_mode=original_mode, detected_mode=mode)
    if original_mode is mode:
        return writer.last_entry()
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return writer.write(
        {
            "entry_id": f"{case_id}:mode_lock:{timestamp}",
            "event_type": "mode_lock",
            "case_id": case_id,
            "finding_id": None,
            "timestamp_utc": timestamp,
            "mode_at_case_init": mode.value,
            "verifier_strategy_used": "not_run_mode_lock",
            "langfuse_session_id": case_id,
            "langfuse_trace_id": "local-runtime",
            "langfuse_root_span_id": "local-runtime-root",
            "langfuse_leaf_span_ids": [],
            "langgraph_thread_id": case_id,
            "langgraph_checkpoint_id": "mode_lock",
            "microsandbox_version": "not_invoked",
            "rootfs_sha256": "not_invoked",
            "tool_version": "verdict-runtime",
            "kernel_version": platform.platform(),
            "output_files_sha256": {},
            "payload": {"mode_at_case_init": mode.value},
        },
    )


def assert_resume_mode(*, writer: LedgerWriter, case_id: str, detected_mode: Mode) -> None:
    original_mode = _locked_mode(writer=writer, case_id=case_id)
    if original_mode is None:
        return
    if original_mode is not detected_mode:
        raise ModeLockedError(
            case_id=case_id,
            original_mode=original_mode,
            detected_mode=detected_mode,
        )


def _locked_mode(*, writer: LedgerWriter, case_id: str) -> Mode | None:
    if not writer.ledger_path.exists():
        return None
    for line in writer.ledger_path.read_text().splitlines():
        entry = json.loads(line)
        if entry.get("case_id") == case_id and entry.get("mode_at_case_init"):
            return Mode(entry["mode_at_case_init"])
    return None
