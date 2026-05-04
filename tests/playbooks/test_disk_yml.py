from __future__ import annotations

from pathlib import Path

from verdict.schemas.playbook import Playbook


def test_plaso_after_lighter_tools() -> None:
    playbook = Playbook.from_yaml_text(Path("src/verdict/playbooks/disk.yml").read_text())
    steps_by_tool = {step.tool: step for step in playbook.steps}

    assert playbook.evidence_type == "disk_image"
    assert playbook.first_move == "image_hash_verify"
    assert steps_by_tool["plaso.extract"].order > steps_by_tool["hayabusa.filter"].order
    assert steps_by_tool["psort.filter"].depends_on == [steps_by_tool["plaso.extract"].order]
