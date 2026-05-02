"""Tests for EvidenceItem + EvidenceManifest schemas (W1.B.3).

TDD: run this before implementing verdict/schemas/evidence.py → RED.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from verdict.schemas.evidence import EvidenceItem, EvidenceManifest


# ---------------------------------------------------------------------------
# EvidenceItem tests
# ---------------------------------------------------------------------------

class TestEvidenceItem:
    """EvidenceItem represents one artifact hashed at case_init (§3.1)."""

    def test_evidence_path_is_path_type(self):
        """§3.1: evidence_path field must be Path, not bare str."""
        item = EvidenceItem(
            path=Path("/evidence/mem.raw"),
            sha256_at_init="a" * 64,
            size_bytes=1024,
            discovered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            evidence_type="memory",
        )
        assert isinstance(item.path, Path)

    def test_sha256_field_present_on_evidence_item(self):
        """§3.1: every evidence file gets a SHA-256 at case_init."""
        item = EvidenceItem(
            path=Path("/evidence/disk.E01"),
            sha256_at_init="b" * 64,
            size_bytes=2048,
            discovered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            evidence_type="disk_image",
        )
        assert len(item.sha256_at_init) == 64

    def test_evidence_type_accepts_all_literals(self):
        valid_types = [
            "memory",
            "disk_image",
            "event_log",
            "pcap",
            "registry_hive",
            "other",
        ]
        for et in valid_types:
            item = EvidenceItem(
                path=Path(f"/evidence/{et}.bin"),
                sha256_at_init="c" * 64,
                size_bytes=0,
                discovered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                evidence_type=et,
            )
            assert item.evidence_type == et

    def test_evidence_type_rejects_unknown(self):
        with pytest.raises(ValidationError):
            EvidenceItem(
                path=Path("/evidence/bad.xyz"),
                sha256_at_init="d" * 64,
                size_bytes=0,
                discovered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                evidence_type="unknown_type",
            )

    def test_evidence_item_round_trips_json(self):
        item = EvidenceItem(
            path=Path("/evidence/sysmon.evtx"),
            sha256_at_init="e" * 64,
            size_bytes=512,
            discovered_at=datetime(2026, 3, 14, 9, 26, 0, tzinfo=timezone.utc),
            evidence_type="event_log",
        )
        restored = EvidenceItem.model_validate_json(item.model_dump_json())
        assert restored.path == item.path
        assert restored.sha256_at_init == item.sha256_at_init
        assert restored.evidence_type == item.evidence_type


# ---------------------------------------------------------------------------
# EvidenceManifest tests
# ---------------------------------------------------------------------------

class TestEvidenceManifest:
    """EvidenceManifest is the collection of all items hashed at case_init."""

    def _make_items(self):
        return [
            EvidenceItem(
                path=Path("/evidence/mem.raw"),
                sha256_at_init="a" * 64,
                size_bytes=1024,
                discovered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                evidence_type="memory",
            ),
            EvidenceItem(
                path=Path("/evidence/disk.E01"),
                sha256_at_init="b" * 64,
                size_bytes=2048,
                discovered_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                evidence_type="disk_image",
            ),
        ]

    def test_manifest_is_collection_of_evidence_items(self):
        """EvidenceManifest.items is list[EvidenceItem]."""
        items = self._make_items()
        manifest = EvidenceManifest(
            case_id="case-001",
            items=items,
            manifest_hash="placeholder",
        )
        assert len(manifest.items) == 2
        assert all(isinstance(i, EvidenceItem) for i in manifest.items)

    def test_manifest_has_case_id(self):
        manifest = EvidenceManifest(
            case_id="case-42",
            items=self._make_items(),
            manifest_hash="placeholder",
        )
        assert manifest.case_id == "case-42"

    def test_manifest_schema_version_default_1(self):
        """Appendix A.3: schema_version: int = 1."""
        manifest = EvidenceManifest(
            case_id="case-001",
            items=self._make_items(),
            manifest_hash="placeholder",
        )
        assert manifest.schema_version == 1

    def test_manifest_hash_is_blake3_of_sorted_pairs(self):
        """W1.B.3.a canonical test.

        manifest_hash = blake3 of sorted (path_str, sha256) pairs serialised as
        JSON. Sorting by path ensures the hash is deterministic regardless of
        item insertion order.
        """
        import blake3 as _blake3

        items = self._make_items()
        manifest = EvidenceManifest(
            case_id="case-001",
            items=items,
            manifest_hash="placeholder",
        )

        # Compute expected hash: sorted by path string, then blake3 of JSON
        pairs = sorted(
            [(str(i.path), i.sha256_at_init) for i in items],
            key=lambda p: p[0],
        )
        serialised = json.dumps(pairs, sort_keys=True).encode()
        expected_hash = _blake3.blake3(serialised).hexdigest()

        assert manifest.compute_manifest_hash() == expected_hash

    def test_manifest_hash_order_independent(self):
        """The manifest_hash must not depend on item insertion order."""
        items_a = self._make_items()          # [mem, disk]
        items_b = list(reversed(items_a))     # [disk, mem]

        manifest_a = EvidenceManifest(
            case_id="same-case",
            items=items_a,
            manifest_hash="placeholder",
        )
        manifest_b = EvidenceManifest(
            case_id="same-case",
            items=items_b,
            manifest_hash="placeholder",
        )
        assert manifest_a.compute_manifest_hash() == manifest_b.compute_manifest_hash()

    def test_manifest_round_trips_json(self):
        items = self._make_items()
        manifest = EvidenceManifest(
            case_id="case-99",
            items=items,
            manifest_hash=EvidenceManifest(
                case_id="case-99",
                items=items,
                manifest_hash="temp",
            ).compute_manifest_hash(),
        )
        restored = EvidenceManifest.model_validate_json(manifest.model_dump_json())
        assert restored.case_id == manifest.case_id
        assert restored.manifest_hash == manifest.manifest_hash
        assert len(restored.items) == len(manifest.items)
