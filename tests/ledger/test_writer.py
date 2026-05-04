from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from verdict.graph.wrappers.ledger_emitter import LedgerEmitter
from verdict.ledger.writer import InvalidLedgerChainError, LedgerWriter

if TYPE_CHECKING:
    from pathlib import Path


def test_write_fsync_verify_readback(tmp_path: Path) -> None:
    writer = LedgerWriter(tmp_path / "ledger.jsonl", hmac_key=b"k" * 32)
    entry = writer.write({"event_type": "tool_call", "case_id": "case-001", "payload": {}})

    persisted = json.loads((tmp_path / "ledger.jsonl").read_text().splitlines()[0])
    assert persisted["entry_hash"] == entry["entry_hash"]


def test_invalid_hmac_refuses_load(tmp_path: Path) -> None:
    writer = LedgerWriter(tmp_path / "ledger.jsonl", hmac_key=b"k" * 32)
    writer.write({"event_type": "tool_call", "case_id": "case-001", "payload": {}})

    with pytest.raises(InvalidLedgerChainError):
        LedgerWriter(tmp_path / "ledger.jsonl", hmac_key=b"x" * 32).last_entry()


def test_ledger_emitter_writes_and_verifies(tmp_path: Path) -> None:
    emitter = LedgerEmitter(ledger_path=tmp_path / "ledger.jsonl", hmac_key=b"k" * 32)
    entry = emitter.emit(event_type="tool_call", case_id="case-001", payload={"tool": "mmls"})

    assert entry["event_type"] == "tool_call"
    assert entry["prev_entry_hash"] is None
