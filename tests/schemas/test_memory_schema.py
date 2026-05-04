"""Tests for DFIR self-evolving memory schemas."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from verdict.schemas.memory import ApprovalState, MemoryEntry, MemoryType


def _base_memory_entry(**overrides):
    now = datetime.now(timezone.utc)
    payload = {
        "memory_id": "pat-2026-0001",
        "type": MemoryType.PATTERN,
        "statement": "Encoded PowerShell + suspicious parent process observed.",
        "evidence_refs": ["evt:host01:sysmon:1001"],
        "source_reliability": "B",
        "confidence": 0.72,
        "counterevidence": [],
        "scope": "windows_enterprise",
        "mitre": ["T1059.001"],
        "created_at": now,
        "last_validated_at": now,
        "expiry": now + timedelta(days=30),
        "author": "agent:verdict",
        "approval_state": ApprovalState.PROPOSED,
        "version": 1,
        "lineage": None,
    }
    payload.update(overrides)
    return payload


def test_persistent_memory_requires_evidence_refs():
    with pytest.raises(ValidationError):
        MemoryEntry(**_base_memory_entry(evidence_refs=[]))


def test_case_memory_can_be_ephemeral_without_evidence_refs():
    entry = MemoryEntry(**_base_memory_entry(type=MemoryType.CASE, evidence_refs=[]))
    assert entry.type == MemoryType.CASE


def test_expiry_must_be_after_created_at():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        MemoryEntry(**_base_memory_entry(created_at=now, expiry=now))
