from __future__ import annotations

import hmac
import json
from hashlib import sha256
from typing import TYPE_CHECKING

import pytest

from verdict.graph.wrappers.ledger_emitter import LedgerEmitter
from verdict.ledger.writer import InvalidLedgerChainError, LedgerWriter, verify_ledger_chain
from verdict.schemas.ledger import LedgerEntry

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
    assert LedgerEntry.model_validate(entry).event_type == "tool_call"


def test_verify_ledger_chain_rejects_valid_row_with_wrong_previous_hash(tmp_path: Path) -> None:
    key = b"k" * 32
    ledger_path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(ledger_path, hmac_key=key)
    writer.write({"event_type": "case_init", "case_id": "case-001", "payload": {}})
    writer.write({"event_type": "tool_call", "case_id": "case-001", "payload": {}})

    first, second = (json.loads(line) for line in ledger_path.read_text().splitlines())
    second["prev_entry_hash"] = "0" * 64
    _resign_entry(second, key)
    ledger_path.write_text("\n".join(json.dumps(entry, sort_keys=True) for entry in [first, second]))

    with pytest.raises(InvalidLedgerChainError, match="prev_entry_hash"):
        verify_ledger_chain(ledger_path, hmac_key=key)


def _resign_entry(entry: dict, key: bytes) -> None:
    unsigned = {
        field: value for field, value in entry.items() if field not in {"entry_hash", "hmac_sig"}
    }
    entry_hash = sha256(json.dumps(unsigned, sort_keys=True).encode()).hexdigest()
    entry["entry_hash"] = entry_hash
    entry["hmac_sig"] = hmac.new(key, entry_hash.encode(), sha256).hexdigest()
