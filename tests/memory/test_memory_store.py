from datetime import datetime, timedelta, timezone

import pytest

from verdict.memory.store import MemoryStore
from verdict.schemas.memory import ApprovalState, MemoryEntry, MemoryOperation, MemoryType, MemoryUpdateProposal


def _entry(memory_id: str = "pat-01", version: int = 1, confidence: float = 0.7, scope: str = "windows") -> MemoryEntry:
    now = datetime.now(timezone.utc)
    return MemoryEntry(
        memory_id=memory_id,
        type=MemoryType.PATTERN,
        statement="Suspicious scheduled task plus encoded PowerShell observed.",
        evidence_refs=["evt:a:1"],
        confidence=confidence,
        scope=scope,
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


def test_approve_proposal_transition(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    proposal = MemoryUpdateProposal(
        proposal_id="prop-2",
        memory_id="pat-01",
        operation=MemoryOperation.WEAKEN,
        rationale="Counterevidence reduced confidence.",
    )
    store.put_proposal(proposal)

    store.approve_proposal("prop-2", approver="analyst", approved_at="2026-05-04T12:00:00Z")
    assert store.get_proposal_state("prop-2") == ApprovalState.APPROVED.value


def test_reject_invalid_approval_transition(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    with pytest.raises(ValueError):
        store.approve_proposal("missing", approver="analyst", approved_at="2026-05-04T12:00:00Z")


def test_list_entries_by_scope_and_confidence(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.put_entry(_entry(memory_id="pat-a", confidence=0.8, scope="windows"))
    store.put_entry(_entry(memory_id="pat-b", confidence=0.5, scope="windows"))
    store.put_entry(_entry(memory_id="pat-c", confidence=0.9, scope="linux"))

    result = store.list_entries_by_scope(scope="windows", min_confidence=0.7)
    assert len(result) == 1
    assert result[0].memory_id == "pat-a"
