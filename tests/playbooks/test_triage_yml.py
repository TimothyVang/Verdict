from __future__ import annotations

from pathlib import Path

from verdict.schemas.playbook import Playbook


def test_registry_first() -> None:
    playbook = Playbook.from_yaml_text(Path("src/verdict/playbooks/triage.yml").read_text())
    steps_by_tool = {step.tool: step for step in playbook.steps}

    assert playbook.evidence_type == "triage"
    assert playbook.first_move == "unzip_to_readonly_mount"
    assert steps_by_tool["recmd"].order == 2
    assert steps_by_tool["pecmd"].order == 3
    assert steps_by_tool["amcache_parse"].order == 4
    assert "AMCACHE_LASTMODIFIED_NOT_EXEC" in steps_by_tool["amcache_parse"].rule
