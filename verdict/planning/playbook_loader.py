"""verdict/planning/playbook_loader.py — inject playbook into planner prompt.

`load_playbook_prompt(manifest)` selects the appropriate YAML playbook for the
evidence type declared in the manifest and returns a formatted string suitable
for inclusion in the planner system prompt.

Evidence-type → playbook mapping:
    "memory"      → verdict/playbooks/memory.yml
    "disk_image"  → verdict/playbooks/disk.yml
    "triage"      → verdict/playbooks/triage.yml

Any other evidence_type raises ValueError so unknown types fail loudly at
case_init rather than silently selecting no playbook.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

import yaml

_PLAYBOOKS_DIR = Path(__file__).resolve().parents[1] / "playbooks"

_EVIDENCE_TYPE_MAP: dict[str, str] = {
    "memory": "memory.yml",
    "disk_image": "disk.yml",
    "triage": "triage.yml",
}


class _HasEvidenceType(Protocol):
    """Minimal structural type for manifest — any object with evidence_type."""

    evidence_type: str


def load_playbook_prompt(manifest: _HasEvidenceType) -> str:
    """Return a planner-prompt string for the given evidence type.

    The returned string embeds the full playbook YAML plus a header so the
    planner can orient itself before constructing its investigation plan.

    Args:
        manifest: Any object with an `evidence_type` attribute. In production
                  this will be an `EvidenceManifest` instance; in tests any
                  object with the attribute is accepted.

    Returns:
        A non-empty string containing the playbook methodology for injection
        into the planner system prompt.

    Raises:
        ValueError: If `manifest.evidence_type` is not one of the three
                    supported types.
    """
    evidence_type = manifest.evidence_type
    filename = _EVIDENCE_TYPE_MAP.get(evidence_type)
    if filename is None:
        supported = sorted(_EVIDENCE_TYPE_MAP.keys())
        raise ValueError(
            f"Unknown evidence_type {evidence_type!r}. "
            f"Supported: {supported}. "
            f"Check EvidenceManifest.evidence_type at case_init."
        )

    playbook_path = _PLAYBOOKS_DIR / filename
    raw_yaml = playbook_path.read_text(encoding="utf-8")

    # Parse to validate, then re-serialize for canonical representation
    data = yaml.safe_load(raw_yaml)
    canonical = yaml.dump(data, default_flow_style=False, allow_unicode=True)

    return (
        f"## Investigation Playbook — evidence_type: {evidence_type}\n\n"
        f"Apply the following SANS-canonical tool sequence for this evidence type.\n"
        f"Each step's `rule` field is a mandatory decision rule — not a suggestion.\n\n"
        f"```yaml\n{canonical}```\n"
    )
