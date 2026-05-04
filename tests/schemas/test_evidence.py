from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from blake3 import blake3

from verdict.schemas.evidence import EvidenceItem, EvidenceManifest


def test_manifest_hash_is_blake3_of_sorted_pairs() -> None:
    discovered_at = datetime(2026, 5, 2, tzinfo=UTC)
    first = EvidenceItem(
        path=Path("/evidence/z.mem"),
        sha256_at_init="b" * 64,
        size_bytes=2,
        discovered_at=discovered_at,
        evidence_type="memory",
    )
    second = EvidenceItem(
        path=Path("/evidence/a.E01"),
        sha256_at_init="a" * 64,
        size_bytes=1,
        discovered_at=discovered_at,
        evidence_type="disk_image",
    )

    expected = blake3(
        b"/evidence/a.E01\x00" + b"a" * 64 + b"\n" + b"/evidence/z.mem\x00" + b"b" * 64,
    ).hexdigest()

    manifest = EvidenceManifest.from_items(case_id="case-001", items=[first, second])

    assert manifest.manifest_hash == expected
    assert manifest.schema_version == 1
