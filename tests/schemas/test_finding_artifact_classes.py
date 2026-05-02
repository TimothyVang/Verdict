"""W1.B.8 — Finding.artifact_classes field with min_length=2.

Tests the §3.2 invariant: `artifact_classes` must carry at least two
entries. A Finding that names only one artifact class (or none) is
forensically insufficient and must be rejected at the schema layer.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from verdict.schemas.artifact_class import ArtifactClass
from verdict.schemas.finding import Finding, VerdictStatus


def _base_kwargs() -> dict:
    """Minimal valid kwargs once artifact_classes exists on Finding."""
    return {
        "finding_id": "F-W1B8-001",
        "title": "evidence consistent with PowerShell execution",
        "description": "Two artifact classes corroborate the claim",
        "mitre_technique": "T1014",
        "artifact_paths": [
            "/evidence/case_001/memory.raw::pid=4112",
            "/evidence/case_001/sysmon.evtx::record=8842",
        ],
        "artifact_classes": [
            ArtifactClass.PROCESS_MEMORY,
            ArtifactClass.SYSMON_1,
        ],
        "status": VerdictStatus.VETTED_CLOUD,
    }


def test_artifact_classes_min_length_2() -> None:
    """§3.2 — Finding.artifact_classes must have min_length=2.

    A single artifact class is forensically unsound (FOR500 doctrine).
    Pydantic must reject it with a ValidationError.
    """
    kw = _base_kwargs()
    kw["artifact_classes"] = [ArtifactClass.SYSMON_1]
    with pytest.raises(ValidationError) as exc_info:
        Finding(**kw)
    assert "artifact_classes" in str(exc_info.value)


def test_artifact_classes_rejects_empty_list() -> None:
    """§3.2 — empty artifact_classes is also rejected (min_length=2)."""
    kw = _base_kwargs()
    kw["artifact_classes"] = []
    with pytest.raises(ValidationError) as exc_info:
        Finding(**kw)
    assert "artifact_classes" in str(exc_info.value)


def test_artifact_classes_accepts_two_entries() -> None:
    """Boundary: exactly two artifact classes is the minimum permitted."""
    Finding(**_base_kwargs())


def test_artifact_classes_accepts_three_entries() -> None:
    """More than two artifact classes is permitted."""
    kw = _base_kwargs()
    kw["artifact_classes"] = [
        ArtifactClass.PROCESS_MEMORY,
        ArtifactClass.SYSMON_1,
        ArtifactClass.EVTX_4688,
    ]
    Finding(**kw)


def test_artifact_classes_typed_as_artifact_class_enum() -> None:
    """artifact_classes entries must be valid ArtifactClass enum values.
    Bare strings that do not map to an enum member are rejected."""
    kw = _base_kwargs()
    kw["artifact_classes"] = ["not_a_real_class", "also_invalid"]
    with pytest.raises(ValidationError):
        Finding(**kw)
