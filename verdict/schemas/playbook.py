"""verdict/schemas/playbook.py — Playbook + Step Pydantic v2 schemas.

These schemas represent the KP-authored YAML playbooks in verdict/playbooks/.
A Playbook is loaded at case_init by the playbook_loader (W1.F.6) and
injected into the planner system prompt to encode SANS-canonical tool
sequencing.

Schema-layer constraints:
- Playbook.steps must have ≥1 entry.
- Step.order must be a positive integer (≥1).
- Step.depends_on is a list of prior step order-values (defaults empty).
- Step.rule is a free-form string encoding the detection/divergence rule.
- Step.mitre_technique_hint is an optional MITRE ATT&CK technique reference.
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Step(BaseModel):
    """A single tool invocation step within a playbook."""

    model_config = ConfigDict(frozen=True)

    order: Annotated[int, Field(ge=1)]
    tool: str
    rule: str | None = None
    depends_on: list[int] = Field(default_factory=list)
    mitre_technique_hint: str | None = None


class Playbook(BaseModel):
    """SANS-canonical tool sequencing playbook for a specific evidence type.

    Evidence types: "memory", "disk_image", "triage".
    Each Playbook carries a first_move (the mandatory initial tool call)
    and an ordered sequence of Steps.
    """

    model_config = ConfigDict(frozen=True)

    evidence_type: str
    first_move: str
    steps: Annotated[list[Step], Field(min_length=1)]
    schema_version: Literal["v1"] = "v1"

    @field_validator("steps", mode="before")
    @classmethod
    def _coerce_step_dicts(cls, v: object) -> object:
        """Accept list of dicts (from YAML load) alongside Step instances."""
        if isinstance(v, list):
            return [Step.model_validate(item) if isinstance(item, dict) else item for item in v]
        return v

    @classmethod
    def from_yaml(cls, path: Path) -> "Playbook":
        """Load and validate a Playbook from a YAML file."""
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls.model_validate(raw)
