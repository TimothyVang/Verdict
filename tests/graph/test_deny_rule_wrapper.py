from __future__ import annotations

import pytest

from verdict.graph.wrappers.deny_rule import DeniedToolCallError, DenyRuleWrapper
from verdict.runtime.mode_detect import Mode


@pytest.mark.parametrize("mode", [Mode.CLOUD, Mode.AIRGAP, Mode.DUAL])
def test_blocks_evidence_writes_in_all_modes(mode: Mode) -> None:
    wrapper = DenyRuleWrapper(mode=mode)

    with pytest.raises(DeniedToolCallError):
        wrapper.validate(tool_name="mftecmd", args=["--out", "/evidence/modified.csv"])


def test_allows_case_output_writes() -> None:
    wrapper = DenyRuleWrapper(mode=Mode.AIRGAP)

    wrapper.validate(tool_name="mftecmd", args=["--out", "/cases/case-001/mft.csv"])


def test_allows_evidence_read_arguments() -> None:
    wrapper = DenyRuleWrapper(mode=Mode.AIRGAP)

    wrapper.validate(tool_name="vol3", args=["-f", "/evidence/memory.raw", "windows.psscan"])
