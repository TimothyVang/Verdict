from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from verdict.schemas.evidence import EvidenceManifest


class HashMismatchError(RuntimeError):
    """Raised when evidence no longer matches the case-init manifest."""


def recheck_evidence_if_due(
    *, super_step: int, manifest: EvidenceManifest, ledger_path: Path, interval: int = 10
) -> bool:
    if super_step % interval != 0:
        return False

    for item in manifest.items:
        actual_sha256 = sha256(item.path.read_bytes()).hexdigest()
        if actual_sha256 != item.sha256_at_init:
            _write_mismatch_entry(
                ledger_path=ledger_path,
                case_id=manifest.case_id,
                path=item.path,
                expected_sha256=item.sha256_at_init,
                actual_sha256=actual_sha256,
            )
            raise HashMismatchError(f"Evidence hash mismatch for {item.path}")
    return True


def _write_mismatch_entry(
    *, ledger_path: Path, case_id: str, path: Path, expected_sha256: str, actual_sha256: str
) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "event_type": "evidence_hash_recheck",
        "case_id": case_id,
        "timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "path": str(path),
        "expected_sha256": expected_sha256,
        "actual_sha256": actual_sha256,
    }
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
