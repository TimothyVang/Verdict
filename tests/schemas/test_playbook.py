"""W1.F.1 — Playbook + Step Pydantic schema tests.

RED: runs before verdict/schemas/playbook.py exists.
GREEN: passes after implementation.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


def test_playbook_loads_yaml() -> None:
    """Schema must parse a minimal YAML playbook dict."""
    from verdict.schemas.playbook import Playbook, Step

    raw = yaml.safe_load("""
evidence_type: memory
first_move: windows.info
steps:
  - order: 1
    tool: vol3.windows.info
""")
    pb = Playbook.model_validate(raw)
    assert pb.evidence_type == "memory"
    assert pb.first_move == "windows.info"
    assert len(pb.steps) == 1
    assert pb.steps[0].order == 1
    assert pb.steps[0].tool == "vol3.windows.info"


def test_step_optional_fields_default() -> None:
    """Step.rule, depends_on, and mitre_technique_hint should be optional."""
    from verdict.schemas.playbook import Step

    s = Step(order=1, tool="vol3.windows.pslist")
    assert s.rule is None
    assert s.depends_on == []
    assert s.mitre_technique_hint is None


def test_step_rule_captured() -> None:
    """Step.rule captures the DKOM divergence rule string."""
    from verdict.schemas.playbook import Step

    rule = "DKOM_divergence: set(psscan_pids) - set(pslist_pids) ≠ ∅ → Hypothesis(T1014, high, [PROCESS_MEMORY])"
    s = Step(order=3, tool="vol3.windows.psscan", rule=rule)
    assert s.rule == rule


def test_playbook_requires_at_least_one_step() -> None:
    """A Playbook with zero steps must be rejected."""
    from pydantic import ValidationError

    from verdict.schemas.playbook import Playbook

    with pytest.raises(ValidationError):
        Playbook(evidence_type="memory", first_move="windows.info", steps=[])


def test_step_order_positive_int() -> None:
    """Step.order must be a positive integer."""
    from pydantic import ValidationError

    from verdict.schemas.playbook import Step

    with pytest.raises(ValidationError):
        Step(order=0, tool="vol3.windows.pslist")


def test_playbook_step_depends_on_list() -> None:
    """depends_on is a list of step order ints."""
    from verdict.schemas.playbook import Step

    s = Step(order=4, tool="vol3.windows.pstree", depends_on=[2])
    assert s.depends_on == [2]


def test_playbook_schema_version_present() -> None:
    """Playbook must carry schema_version field."""
    from verdict.schemas.playbook import Playbook

    pb = Playbook(
        evidence_type="memory",
        first_move="windows.info",
        steps=[{"order": 1, "tool": "vol3.windows.info"}],
    )
    assert pb.schema_version == "v1"


def test_playbook_loads_from_real_yaml_file(tmp_path: Path) -> None:
    """Playbook.from_yaml classmethod loads from a YAML file path."""
    from verdict.schemas.playbook import Playbook

    content = """
evidence_type: disk_image
first_move: image_hash_verify
steps:
  - order: 1
    tool: image_hash_verify
    rule: "verify against case_init manifest"
  - order: 2
    tool: mmls
  - order: 3
    tool: fsstat
    depends_on: [2]
"""
    f = tmp_path / "disk.yml"
    f.write_text(content, encoding="utf-8")
    pb = Playbook.from_yaml(f)
    assert pb.evidence_type == "disk_image"
    assert pb.first_move == "image_hash_verify"
    assert len(pb.steps) == 3
    assert pb.steps[2].depends_on == [2]
