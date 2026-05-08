from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING

import pytest

from verdict.ledger.writer import verify_ledger_chain
from verdict.runtime.evidence_recheck import HashMismatchError, recheck_evidence_if_due
from verdict.schemas.evidence import EvidenceItem, EvidenceManifest

if TYPE_CHECKING:
    from pathlib import Path


def _manifest_for(path: Path) -> EvidenceManifest:
    return EvidenceManifest.from_items(
        case_id="case-001",
        items=[
            EvidenceItem(
                path=path,
                sha256_at_init=sha256(path.read_bytes()).hexdigest(),
                size_bytes=path.stat().st_size,
                discovered_at=datetime(2026, 5, 2, tzinfo=UTC),
                evidence_type="memory",
            ),
        ],
    )


def test_recheck_every_10_super_steps(tmp_path: Path) -> None:
    evidence = tmp_path / "memory.raw"
    evidence.write_bytes(b"original evidence")
    manifest = _manifest_for(evidence)
    ledger_path = tmp_path / "ledger.jsonl"

    assert (
        recheck_evidence_if_due(super_step=9, manifest=manifest, ledger_path=ledger_path) is False
    )
    assert not ledger_path.exists()
    assert recheck_evidence_if_due(
        super_step=10,
        manifest=manifest,
        ledger_path=ledger_path,
        hmac_key=b"k" * 32,
    ) is True


def test_mismatch_writes_ledger_entry_and_halts(tmp_path: Path) -> None:
    evidence = tmp_path / "memory.raw"
    evidence.write_bytes(b"original evidence")
    manifest = _manifest_for(evidence)
    evidence.write_bytes(b"changed evidence")
    ledger_path = tmp_path / "ledger.jsonl"

    with pytest.raises(HashMismatchError):
        recheck_evidence_if_due(
            super_step=10,
            manifest=manifest,
            ledger_path=ledger_path,
            hmac_key=b"k" * 32,
        )

    entry = verify_ledger_chain(ledger_path, hmac_key=b"k" * 32)[0]
    assert entry["event_type"] == "evidence_hash_recheck"
    assert entry["case_id"] == "case-001"
    assert entry["prev_entry_hash"] is None
    assert entry["payload"]["path"] == str(evidence)
    assert entry["payload"]["expected_sha256"] == manifest.items[0].sha256_at_init
    assert entry["payload"]["actual_sha256"] == sha256(b"changed evidence").hexdigest()
