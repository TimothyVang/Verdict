"""EvidenceItem + EvidenceManifest schemas (W1.B.3).

Implements evidence integrity as defined in CLAUDE.md §3.1 and
docs/ARCHITECTURE.md §5, per BUILD_PLAN Appendix A.3.

Design invariants:
- Every evidence file gets a SHA-256 at case_init (§3.1).
- The manifest_hash is blake3 of sorted (path, sha256) pairs, providing
  a deterministic, order-independent fingerprint of the full evidence set.
- schema_version is 1 (W1.B.12 convention).
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

import blake3 as _blake3
from pydantic import BaseModel

EvidenceType = Literal[
    "memory",
    "disk_image",
    "event_log",
    "pcap",
    "registry_hive",
    "other",
]


class EvidenceItem(BaseModel):
    """One artifact in the case evidence directory, hashed at case_init.

    path is the absolute path under /evidence (read-only microsandbox mount).
    sha256_at_init is recorded at case_init; re-checked every 10 super-steps
    by verdict/runtime/evidence_recheck.py (§3.1).
    """

    path: Path
    sha256_at_init: str
    size_bytes: int
    discovered_at: datetime
    evidence_type: EvidenceType


class EvidenceManifest(BaseModel):
    """Generated at case_init.

    Every Finding must cite EvidenceItems by path.  The manifest_hash
    is a blake3 digest over the sorted (path, sha256) pairs, making it
    deterministic regardless of item insertion order.

    Appendix A.3: schema_version: int = 1.
    """

    case_id: str
    items: list[EvidenceItem]
    manifest_hash: str  # blake3 of sorted (path, sha256) pairs
    schema_version: int = 1

    def compute_manifest_hash(self) -> str:
        """Compute blake3 of sorted (path_str, sha256) pairs.

        Sorting by path ensures the hash is stable regardless of the order
        in which items were discovered.  The pairs are serialised as JSON
        (sort_keys=True for nested-dict stability) before hashing.
        """
        pairs = sorted(
            [(str(i.path), i.sha256_at_init) for i in self.items],
            key=lambda p: p[0],
        )
        serialised = json.dumps(pairs, sort_keys=True).encode()
        return _blake3.blake3(serialised).hexdigest()
