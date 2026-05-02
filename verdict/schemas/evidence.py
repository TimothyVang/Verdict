"""Evidence manifest schema."""

from pydantic import BaseModel

class EvidenceItem(BaseModel):
    path: str
    file_type: str
    size_bytes: int
    sha256: str

class EvidenceManifest(BaseModel):
    case_id: str
    items: list[EvidenceItem] = []
    created_at: str
