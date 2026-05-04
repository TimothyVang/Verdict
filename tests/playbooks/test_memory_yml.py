from __future__ import annotations

from pathlib import Path

from verdict.schemas.playbook import Playbook


def test_memory_playbook_has_dkom_rule() -> None:
    playbook = Playbook.from_yaml_text(Path("src/verdict/playbooks/memory.yml").read_text())

    psscan_step = next(step for step in playbook.steps if step.tool == "vol3.windows.psscan")

    assert playbook.evidence_type == "memory"
    assert playbook.first_move == "windows.info"
    assert psscan_step.order == 3
    assert psscan_step.mitre_technique_hint is None
    assert "DKOM_divergence" in psscan_step.rule
    assert "T1014" in psscan_step.rule
