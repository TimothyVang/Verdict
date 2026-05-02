"""W1.B.9 — Finding.caveats_acknowledged field.

Tests the §3.3 invariant: `caveats_acknowledged` must exist as a
list[CaveatID] field with a default of [] (empty). The field is typed so
that bare strings not in the CaveatID enum are rejected by Pydantic.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from verdict.schemas.artifact_class import ArtifactClass
from verdict.schemas.caveat_id import CaveatID
from verdict.schemas.finding import Finding, VerdictStatus


def _base_kwargs() -> dict:
    """Minimal valid kwargs once caveats_acknowledged exists on Finding."""
    return {
        "finding_id": "F-W1B9-001",
        "title": "evidence consistent with process injection",
        "description": "Two artifact classes corroborate the finding",
        "mitre_technique": "T1014",
        "artifact_paths": [
            "/evidence/case_001/memory.raw::pid=4112",
            "/evidence/case_001/sysmon.evtx::record=8842",
        ],
        "artifact_classes": [
            ArtifactClass.PROCESS_MEMORY,
            ArtifactClass.SYSMON_1,
        ],
        "caveats_acknowledged": [],
        "status": VerdictStatus.VETTED_CLOUD,
    }


def test_caveats_acknowledged_default_empty() -> None:
    """§3.3 — caveats_acknowledged defaults to an empty list.

    A Finding constructed without explicitly supplying caveats_acknowledged
    must have an empty list, not None and not raise an error.
    """
    kw = _base_kwargs()
    kw.pop("caveats_acknowledged")  # omit the field — must default to []
    f = Finding(**kw)
    assert f.caveats_acknowledged == []


def test_caveats_acknowledged_accepts_valid_caveat_id() -> None:
    """A Finding with a valid CaveatID in caveats_acknowledged constructs."""
    kw = _base_kwargs()
    kw["caveats_acknowledged"] = [CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC]
    Finding(**kw)


def test_caveats_acknowledged_accepts_multiple_caveats() -> None:
    """Multiple CaveatID values in the list are all accepted."""
    kw = _base_kwargs()
    kw["caveats_acknowledged"] = [
        CaveatID.MFT_SI_STOMPABLE,
        CaveatID.USNJRNL_WRAPS,
    ]
    Finding(**kw)


def test_caveats_acknowledged_rejects_invalid_string() -> None:
    """The field is typed list[CaveatID]. Bare strings not in the enum
    must be rejected by Pydantic before any validator runs."""
    kw = _base_kwargs()
    kw["caveats_acknowledged"] = ["not_a_real_caveat"]
    with pytest.raises(ValidationError):
        Finding(**kw)


def test_caveats_acknowledged_accepts_all_seven_tier1_caveats() -> None:
    """All seven Tier-1 CaveatID values must be valid list entries."""
    kw = _base_kwargs()
    kw["caveats_acknowledged"] = list(CaveatID)
    Finding(**kw)


def test_caveats_acknowledged_is_list_not_none() -> None:
    """Setting caveats_acknowledged=None must be rejected (not Optional)."""
    kw = _base_kwargs()
    kw["caveats_acknowledged"] = None
    with pytest.raises(ValidationError):
        Finding(**kw)
