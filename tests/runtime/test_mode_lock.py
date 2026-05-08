from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from verdict.ledger.writer import LedgerWriter
from verdict.runtime.mode_detect import Mode
from verdict.runtime.mode_lock import ModeLockedError, assert_resume_mode, initialize_mode_lock
from verdict.schemas.ledger import LedgerEntry

if TYPE_CHECKING:
    from pathlib import Path


def test_resume_with_different_mode_refuses(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.jsonl"
    initialize_mode_lock(
        writer=LedgerWriter(ledger_path, hmac_key=b"k" * 32),
        case_id="case-001",
        mode=Mode.CLOUD,
    )

    with pytest.raises(ModeLockedError) as exc_info:
        assert_resume_mode(
            writer=LedgerWriter(ledger_path, hmac_key=b"k" * 32),
            case_id="case-001",
            detected_mode=Mode.AIRGAP,
        )

    assert exc_info.value.exit_code == 2
    assert "Case case-001 was initialized in mode=CLOUD; current environment is mode=AIRGAP" in str(
        exc_info.value,
    )


def test_mode_at_case_init_immutable(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(ledger_path, hmac_key=b"k" * 32)
    initialize_mode_lock(writer=writer, case_id="case-001", mode=Mode.CLOUD)

    with pytest.raises(ModeLockedError):
        initialize_mode_lock(writer=writer, case_id="case-001", mode=Mode.DUAL)

    assert writer.last_entry()["mode_at_case_init"] == "CLOUD"


def test_mode_lock_entry_matches_ledger_schema(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(ledger_path, hmac_key=b"k" * 32)

    entry = initialize_mode_lock(writer=writer, case_id="case-001", mode=Mode.CLOUD)

    assert LedgerEntry.model_validate(entry).event_type == "mode_lock"
