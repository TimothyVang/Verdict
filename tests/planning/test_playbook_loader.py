"""W1.F.6 — playbook_loader injects methodology by evidence type tests.

RED: runs before playbook_loader.py exists.
GREEN: passes after implementation.

load_playbook_prompt(manifest) -> str must:
- Accept an EvidenceManifest-like object with evidence_type attribute
- Return a string containing the playbook YAML formatted for the planner prompt
- Select memory.yml for evidence_type="memory"
- Select disk.yml for evidence_type="disk_image"
- Select triage.yml for evidence_type="triage"
- Raise ValueError for unknown evidence_type
"""
from __future__ import annotations

from pathlib import Path

import pytest


class _FakeManifest:
    """Minimal stand-in for EvidenceManifest — carries only evidence_type."""

    def __init__(self, evidence_type: str) -> None:
        self.evidence_type = evidence_type


def test_loader_picks_by_evidence_type_memory() -> None:
    """load_playbook_prompt selects memory.yml for evidence_type=memory."""
    from verdict.planning.playbook_loader import load_playbook_prompt

    result = load_playbook_prompt(_FakeManifest("memory"))
    assert "windows.info" in result, "memory playbook must include windows.info"
    assert "DKOM_divergence" in result, "memory playbook must include DKOM rule"


def test_loader_picks_by_evidence_type_disk() -> None:
    """load_playbook_prompt selects disk.yml for evidence_type=disk_image."""
    from verdict.planning.playbook_loader import load_playbook_prompt

    result = load_playbook_prompt(_FakeManifest("disk_image"))
    assert "image_hash_verify" in result
    assert "mmls" in result


def test_loader_picks_by_evidence_type_triage() -> None:
    """load_playbook_prompt selects triage.yml for evidence_type=triage."""
    from verdict.planning.playbook_loader import load_playbook_prompt

    result = load_playbook_prompt(_FakeManifest("triage"))
    assert "unzip_to_readonly_mount" in result
    assert "AMCACHE_LASTMODIFIED_NOT_EXEC" in result


def test_loader_raises_on_unknown_evidence_type() -> None:
    """load_playbook_prompt raises ValueError for unknown evidence_type."""
    from verdict.planning.playbook_loader import load_playbook_prompt

    with pytest.raises(ValueError, match="Unknown evidence_type"):
        load_playbook_prompt(_FakeManifest("pcap"))


def test_loader_output_is_nonempty_string() -> None:
    """Returned prompt string must be non-empty."""
    from verdict.planning.playbook_loader import load_playbook_prompt

    result = load_playbook_prompt(_FakeManifest("memory"))
    assert isinstance(result, str) and len(result.strip()) > 0


def test_loader_includes_evidence_type_header(tmp_path: Path) -> None:
    """Prompt must include a header identifying the evidence type."""
    from verdict.planning.playbook_loader import load_playbook_prompt

    result = load_playbook_prompt(_FakeManifest("disk_image"))
    assert "disk_image" in result or "disk" in result.lower(), (
        "Prompt must identify evidence type for planner orientation"
    )
