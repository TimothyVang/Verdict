from __future__ import annotations

import json
from typing import TYPE_CHECKING

from verdict.ledger.writer import LedgerWriter

if TYPE_CHECKING:
    from pathlib import Path


def test_redacts_authorization_header_before_hash(tmp_path: Path) -> None:
    writer = LedgerWriter(tmp_path / "ledger.jsonl", hmac_key=b"k" * 32)

    entry = writer.write(
        {
            "event_type": "tool_call",
            "case_id": "case-001",
            "payload": {"headers": {"authorization": "Bearer secret-token"}},
        },
    )

    persisted = (tmp_path / "ledger.jsonl").read_text()
    assert "secret-token" not in persisted
    assert entry["payload"]["headers"]["authorization"] == "<redacted>"
    assert entry["payload_redactions"] == ["payload.headers.authorization"]
    assert writer.last_entry() == json.loads(persisted.splitlines()[0])


def test_redacts_auth_user_and_api_key(tmp_path: Path) -> None:
    writer = LedgerWriter(tmp_path / "ledger.jsonl", hmac_key=b"k" * 32)

    entry = writer.write(
        {
            "event_type": "tool_call",
            "case_id": "case-001",
            "payload": {"auth_user": "analyst@example.com", "api_key": "key-123"},
        },
    )

    assert entry["payload"] == {"auth_user": "<redacted>", "api_key": "<redacted>"}
    assert entry["payload_redactions"] == ["payload.api_key", "payload.auth_user"]
