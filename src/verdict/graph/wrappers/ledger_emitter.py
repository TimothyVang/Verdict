from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from verdict.ledger.writer import LedgerWriter


@dataclass(frozen=True)
class LedgerEmitter:
    """Graph wrapper that persists events through the hardened ledger writer."""

    ledger_path: Path
    hmac_key: bytes

    def emit(self, *, event_type: str, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return LedgerWriter(self.ledger_path, self.hmac_key).write(
            {"event_type": event_type, "case_id": case_id, "payload": payload},
        )

    def last_entry(self) -> dict[str, Any]:
        return LedgerWriter(self.ledger_path, self.hmac_key).last_entry()
