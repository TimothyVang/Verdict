"""Evidence manifest schema for W1.B.3."""

from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel


class EvidenceItem(BaseModel):
    """A single evidence file or memory image."""
    path: Path
    file_type: str  # "E01" | "raw" | "mem" | "pcap" | "zip"
    size_bytes: int
    sha256: str


class EvidenceManifest(BaseModel):
    """Case-level evidence inventory with chain-of-custody hashes."""
    case_id: str
    items: list[EvidenceItem] = []
    created_at: str  # ISO 8601 UTC with Z suffix
