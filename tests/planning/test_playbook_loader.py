from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from verdict.planning.playbook_loader import load_playbook_prompt
from verdict.schemas.evidence import EvidenceItem, EvidenceManifest


def _manifest(evidence_type: str) -> EvidenceManifest:
    return EvidenceManifest.from_items(
        case_id="case-001",
        items=[
            EvidenceItem(
                path=Path(f"/evidence/{evidence_type}.bin"),
                sha256_at_init="a" * 64,
                size_bytes=1,
                discovered_at=datetime(2026, 5, 2, tzinfo=UTC),
                evidence_type=evidence_type,
            ),
        ],
    )


def test_loader_picks_by_evidence_type() -> None:
    memory_prompt = load_playbook_prompt(_manifest("memory"))
    disk_prompt = load_playbook_prompt(_manifest("disk_image"))

    assert "windows.info" in memory_prompt
    assert "DKOM" in memory_prompt
    assert "mmls" in disk_prompt
    assert "DKOM" not in disk_prompt
