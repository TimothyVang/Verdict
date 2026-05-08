from __future__ import annotations

import json

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
    return writer.write(
        {
            "event_type": "mode_lock",
            "case_id": case_id,
            "mode_at_case_init": mode.value,
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
