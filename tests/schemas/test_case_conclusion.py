from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from verdict.schemas.case_conclusion import CaseConclusion
from verdict.schemas.verdict_status import VerdictStatus


def test_no_evil_found_requires_playbook_steps() -> None:
    with pytest.raises(ValidationError):
        CaseConclusion(
            status="NO_EVIL_FOUND",
            playbook_steps_executed=[],
            evidence_hashes={Path("/evidence/memory.raw"): "a" * 64},
            rationale="No evil found after canonical memory triage.",
        )

    conclusion = CaseConclusion(
        status="NO_EVIL_FOUND",
        playbook_steps_executed=["windows.info"],
        evidence_hashes={Path("/evidence/memory.raw"): "a" * 64},
        rationale="No evil found after canonical memory triage.",
    )

    assert conclusion.status == "NO_EVIL_FOUND"
    assert "NO_EVIL_FOUND" not in {member.value for member in VerdictStatus}
