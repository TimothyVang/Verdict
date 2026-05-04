from __future__ import annotations

from verdict.schemas.playbook import Playbook


def test_playbook_loads_yaml() -> None:
    playbook = Playbook.from_yaml_text(
        """
        evidence_type: memory
        first_move: windows.info
        steps:
          - order: 1
            tool: vol3.windows.info
            mitre_technique_hint: null
          - order: 2
            tool: vol3.windows.psscan
            depends_on: [1]
            rule: "DKOM_divergence: set(psscan_pids) - set(pslist_pids)"
        """,
    )

    assert playbook.evidence_type == "memory"
    assert playbook.first_move == "windows.info"
    assert playbook.steps[1].depends_on == [1]
    assert "DKOM_divergence" in playbook.steps[1].rule
