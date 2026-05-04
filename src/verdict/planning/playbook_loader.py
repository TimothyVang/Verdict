from __future__ import annotations

from pathlib import Path

from verdict.schemas.evidence import EvidenceManifest
from verdict.schemas.playbook import Playbook

PACKAGE_ROOT = Path(__file__).resolve().parents[1]

PLAYBOOK_BY_EVIDENCE_TYPE = {
    "memory": PACKAGE_ROOT / "playbooks/memory.yml",
    "disk_image": PACKAGE_ROOT / "playbooks/disk.yml",
    "other": PACKAGE_ROOT / "playbooks/triage.yml",
    "registry_hive": PACKAGE_ROOT / "playbooks/triage.yml",
    "event_log": PACKAGE_ROOT / "playbooks/triage.yml",
}


def load_playbook_prompt(manifest: EvidenceManifest) -> str:
    evidence_type = manifest.items[0].evidence_type if manifest.items else "other"
    playbook_path = PLAYBOOK_BY_EVIDENCE_TYPE.get(evidence_type, PLAYBOOK_BY_EVIDENCE_TYPE["other"])
    playbook = Playbook.from_yaml_text(playbook_path.read_text())

    lines = [
        f"Evidence type: {playbook.evidence_type}",
        f"First move: {playbook.first_move}",
        "Steps:",
    ]
    for step in playbook.steps:
        suffix = f" rule={step.rule}" if step.rule else ""
        lines.append(f"{step.order}. {step.tool}{suffix}")
    return "\n".join(lines)
