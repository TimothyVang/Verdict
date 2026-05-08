from __future__ import annotations

import hmac
import json
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from verdict.ledger.redaction import redact_payload


class InvalidLedgerChainError(RuntimeError):
    """Raised when a ledger row hash or HMAC fails verification."""


@dataclass(frozen=True)
class LedgerWriter:
    ledger_path: Path
    hmac_key: bytes

    def write(self, entry: dict[str, Any]) -> dict[str, Any]:
        previous = self.last_entry() if self.ledger_path.exists() else None
        payload, payload_redactions = redact_payload(entry.get("payload", {}))
        entry_to_sign = {
            **entry,
            "payload": payload,
            "payload_redactions": payload_redactions,
            "prev_entry_hash": previous["entry_hash"] if previous else None,
        }
        entry_hash = _hash_payload(entry_to_sign)
        signed = {
            **entry_to_sign,
            "entry_hash": entry_hash,
            "hmac_sig": hmac.new(self.hmac_key, entry_hash.encode(), sha256).hexdigest(),
        }

        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(signed, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

        if self.last_entry() != signed:
            raise InvalidLedgerChainError("ledger verify-readback failed")
        return signed

    def last_entry(self) -> dict[str, Any]:
        entries = verify_ledger_chain(self.ledger_path, hmac_key=self.hmac_key)
        return entries[-1]


def verify_ledger_chain(ledger_path: Path, *, hmac_key: bytes) -> list[dict[str, Any]]:
    lines = ledger_path.read_text().splitlines()
    if not lines:
        raise InvalidLedgerChainError("ledger is empty")

    entries: list[dict[str, Any]] = []
    previous_hash: str | None = None
    for line in lines:
        entry = json.loads(line)
        _verify_entry(entry, hmac_key)
        if entry.get("prev_entry_hash") != previous_hash:
            raise InvalidLedgerChainError("ledger prev_entry_hash chain mismatch")
        entries.append(entry)
        previous_hash = entry["entry_hash"]
    return entries


def _hash_payload(entry: dict[str, Any]) -> str:
    return sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()


def _verify_entry(entry: dict[str, Any], hmac_key: bytes) -> None:
    entry_hash = entry["entry_hash"]
    unsigned = {key: value for key, value in entry.items() if key not in {"entry_hash", "hmac_sig"}}
    expected_hash = _hash_payload(unsigned)
    if not hmac.compare_digest(entry_hash, expected_hash):
        raise InvalidLedgerChainError("ledger entry hash mismatch")
    expected_sig = hmac.new(hmac_key, entry_hash.encode(), sha256).hexdigest()
    if not hmac.compare_digest(entry["hmac_sig"], expected_sig):
        raise InvalidLedgerChainError("ledger entry HMAC mismatch")
