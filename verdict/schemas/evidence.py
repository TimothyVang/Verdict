"""EvidenceItem + EvidenceManifest schemas.

Implements evidence integrity as defined in CLAUDE.md §3.1 and
docs/ARCHITECTURE.md §5.

Design invariants:
- Every evidence file gets a SHA-256 at case_init (§3.1).
- The manifest_hash is blake3 of sorted (path, sha256) pairs.
- schema_version: int = SCHEMA_VERSION (W1.B.12).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

import blake3 as _blake3_mod
from pydantic import BaseModel

from verdict.schemas.version import SCHEMA_VERSION

EvidenceType = Literal[
    "memory",
    "disk_image",
    "event_log",
    "pcap",
    "registry_hive",
    "other",
]


class EvidenceItem(BaseModel):
    """One artifact in the case evidence directory, hashed at case_init."""

    path: Path
    sha256_at_init: str
    size_bytes: int
    discovered_at: datetime
    evidence_type: EvidenceType


class EvidenceManifest(BaseModel):
    """Generated at case_init.

    manifest_hash is a blake3 digest over the sorted (path, sha256) pairs.
    """

    case_id: str
    items: list[EvidenceItem]
    manifest_hash: str
    schema_version: int = SCHEMA_VERSION

    def compute_manifest_hash(self) -> str:
        """Compute blake3 of sorted (path_str, sha256) pairs."""
        pairs = sorted(
            [(str(i.path), i.sha256_at_init) for i in self.items],
            key=lambda p: p[0],
        )
        serialised = json.dumps(pairs, sort_keys=True).encode()
        return _blake3_mod.blake3(serialised).hexdigest()
