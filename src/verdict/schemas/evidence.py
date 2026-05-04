from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from blake3 import blake3
from pydantic import BaseModel

from verdict.schemas.version import SCHEMA_VERSION

EvidenceType = Literal["memory", "disk_image", "event_log", "pcap", "registry_hive", "other"]


class EvidenceItem(BaseModel):
    """One evidence file hashed at case initialization."""

    path: Path
    sha256_at_init: str
    size_bytes: int
    discovered_at: datetime
    evidence_type: EvidenceType


class EvidenceManifest(BaseModel):
    """Case evidence manifest generated at case initialization."""

    case_id: str
    items: list[EvidenceItem]
    manifest_hash: str
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def from_items(cls, *, case_id: str, items: list[EvidenceItem]) -> EvidenceManifest:
        return cls(case_id=case_id, items=items, manifest_hash=_manifest_hash(items))


def _manifest_hash(items: list[EvidenceItem]) -> str:
    pairs = sorted((str(item.path), item.sha256_at_init) for item in items)
    payload = b"\n".join(path.encode() + b"\x00" + sha256.encode() for path, sha256 in pairs)
    return blake3(payload).hexdigest()
