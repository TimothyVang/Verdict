from datetime import datetime, timedelta, timezone

from verdict.memory.store import MemoryStore
from verdict.schemas.memory import ApprovalState, MemoryEntry, MemoryOperation, MemoryType, MemoryUpdateProposal


def _entry(version: int = 1) -> MemoryEntry:
    now = datetime.now(timezone.utc)
    return MemoryEntry(
        memory_id="pat-01",
        type=MemoryType.PATTERN,
        statement="Suspicious scheduled task plus encoded PowerShell observed.",
        evidence_refs=["evt:a:1"],
        confidence=0.7,
        scope="windows",
        created_at=now,
        last_validated_at=now,
        expiry=now + timedelta(days=30),
        author="agent",
        approval_state=ApprovalState.APPROVED,
        version=version,
    )


def test_append_only_latest_version(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.put_entry(_entry(version=1))
    store.put_entry(_entry(version=2))

    latest = store.get_latest_entry("pat-01")
    assert latest is not None
    assert latest.version == 2


def test_store_update_proposal(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    proposal = MemoryUpdateProposal(
        proposal_id="prop-1",
        memory_id="pat-01",
        operation=MemoryOperation.STRENGTHEN,
        rationale="Second host corroborates pattern.",
    )

    store.put_proposal(proposal)
