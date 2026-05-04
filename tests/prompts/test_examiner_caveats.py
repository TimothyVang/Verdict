from __future__ import annotations

from pathlib import Path

from verdict.schemas.caveat_id import CaveatID


def test_all_seven_caveats_present() -> None:
    text = Path("src/verdict/planning/prompts/examiner_caveats.md").read_text()

    for caveat in CaveatID:
        assert f"## {caveat.value}" in text
    assert text.count("## ") == 7
