from __future__ import annotations

from verdict.schemas.finding import ReviewState
from verdict.schemas.verdict_status import VerdictStatus


def test_verdict_status_has_canonical_states() -> None:
    assert {member.value for member in VerdictStatus} == {
        "VETTED_CLOUD",
        "VETTED_AIRGAP",
        "VETTED_DUAL",
        "CONTESTED",
        "UNVERIFIABLE",
        "EXHAUSTED_REPLAN",
    }
    assert {member.value for member in ReviewState} == {"DRAFT", "APPROVED", "REJECTED"}
    assert not ({"DRAFT", "APPROVED", "REJECTED"} & {member.value for member in VerdictStatus})
