from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from yaml import safe_load

EvidenceType = Literal["memory", "disk_image", "triage"]


class Step(BaseModel):
    """Single ordered forensic playbook step."""

    order: int
    tool: str
    mitre_technique_hint: str | None = None
    depends_on: list[int] = []
    rule: str = ""


class Playbook(BaseModel):
    """Forensic methodology playbook injected into planner prompts."""

    evidence_type: EvidenceType
    first_move: str
    steps: list[Step]

    @classmethod
    def from_yaml_text(cls, text: str) -> Playbook:
        return cls.model_validate(safe_load(text))
