"""W1.F.3 — verdict/playbooks/disk.yml structural tests.

RED: runs before disk.yml exists.
GREEN: passes after disk.yml is authored.

SANS canonical disk image sequence requirements per Appendix C.2:
- first_move must be image_hash_verify
- image_hash_verify is order 1 (NIST SP 800-86 §5.1.2 compliance)
- mmls precedes fsstat precedes fls
- mftecmd carries $FN over $SI timestamp caveat rule
- recmd carries T1547 persistence hint
- pecmd carries T1059 execution corroboration hint
- plaso tools come AFTER lighter tools (hayabusa → plaso)
- hayabusa_csv_timeline precedes hayabusa_filter
- plaso.extract precedes psort.filter
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PLAYBOOKS_DIR = Path(__file__).resolve().parents[2] / "verdict" / "playbooks"
DISK_YML = PLAYBOOKS_DIR / "disk.yml"


@pytest.fixture(scope="module")
def disk_playbook() -> dict:
    assert DISK_YML.exists(), f"disk.yml not found at {DISK_YML}"
    return yaml.safe_load(DISK_YML.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def disk_playbook_schema():
    from verdict.schemas.playbook import Playbook

    return Playbook.from_yaml(DISK_YML)


def test_disk_yml_exists() -> None:
    assert DISK_YML.exists(), "verdict/playbooks/disk.yml not found"


def test_evidence_type_is_disk_image(disk_playbook: dict) -> None:
    assert disk_playbook["evidence_type"] == "disk_image"


def test_first_move_is_image_hash_verify(disk_playbook: dict) -> None:
    """SANS canonical first move for disk images is image_hash_verify."""
    assert disk_playbook["first_move"] == "image_hash_verify"


def test_image_hash_verify_is_first_step(disk_playbook: dict) -> None:
    """image_hash_verify must be order=1."""
    steps = disk_playbook["steps"]
    first = min(steps, key=lambda s: s["order"])
    assert first["tool"] == "image_hash_verify", (
        f"First step must be image_hash_verify; got {first['tool']!r}"
    )


def test_mmls_before_fsstat_before_fls(disk_playbook: dict) -> None:
    """SANS canonical order: mmls → fsstat → fls."""
    orders = {s["tool"]: s["order"] for s in disk_playbook["steps"]}
    for tool in ("mmls", "fsstat", "fls"):
        assert tool in orders, f"{tool} missing from disk.yml"
    assert orders["mmls"] < orders["fsstat"], "mmls must precede fsstat"
    assert orders["fsstat"] < orders["fls"], "fsstat must precede fls"


def test_mftecmd_has_fn_si_rule(disk_playbook: dict) -> None:
    """mftecmd step must carry the $FN/$SI timestomp caveat rule."""
    steps = disk_playbook["steps"]
    mft_steps = [s for s in steps if s.get("tool") == "mftecmd"]
    assert mft_steps, "mftecmd step missing from disk.yml"
    rule = mft_steps[0].get("rule", "")
    assert "$FN" in rule, f"mftecmd rule must reference $FN; got: {rule!r}"
    assert "$SI" in rule, f"mftecmd rule must reference $SI; got: {rule!r}"
    assert "stompable" in rule.lower(), (
        f"mftecmd rule must warn about stomping; got: {rule!r}"
    )


def test_recmd_has_t1547_hint(disk_playbook: dict) -> None:
    """recmd step must carry T1547 (persistence via registry)."""
    steps = disk_playbook["steps"]
    recmd_steps = [s for s in steps if s.get("tool") == "recmd"]
    assert recmd_steps, "recmd step missing from disk.yml"
    hint = recmd_steps[0].get("mitre_technique_hint") or recmd_steps[0].get("rule", "")
    assert "T1547" in str(hint), (
        f"recmd must reference T1547; got hint={hint!r}"
    )


def test_pecmd_has_t1059_hint(disk_playbook: dict) -> None:
    """pecmd step (Prefetch) must carry T1059 execution corroboration."""
    steps = disk_playbook["steps"]
    pecmd_steps = [s for s in steps if s.get("tool") == "pecmd"]
    assert pecmd_steps, "pecmd step missing from disk.yml"
    hint = pecmd_steps[0].get("mitre_technique_hint") or pecmd_steps[0].get("rule", "")
    assert "T1059" in str(hint), (
        f"pecmd must reference T1059; got hint={hint!r}"
    )


def test_plaso_after_lighter_tools(disk_playbook: dict) -> None:
    """plaso_extract must run after hayabusa_csv_timeline (heavy tools last)."""
    orders = {s["tool"]: s["order"] for s in disk_playbook["steps"]}
    assert "hayabusa.csv_timeline" in orders, "hayabusa.csv_timeline missing from disk.yml"
    assert "plaso.extract" in orders, "plaso.extract missing from disk.yml"
    assert orders["hayabusa.csv_timeline"] < orders["plaso.extract"], (
        "hayabusa.csv_timeline must precede plaso.extract"
    )


def test_hayabusa_csv_before_hayabusa_filter(disk_playbook: dict) -> None:
    """hayabusa_csv_timeline (extract) must precede hayabusa_filter (analyst filter)."""
    orders = {s["tool"]: s["order"] for s in disk_playbook["steps"]}
    assert "hayabusa.csv_timeline" in orders
    assert "hayabusa.filter" in orders
    assert orders["hayabusa.csv_timeline"] < orders["hayabusa.filter"], (
        "hayabusa extract must precede hayabusa filter"
    )


def test_plaso_extract_before_psort_filter(disk_playbook: dict) -> None:
    """plaso.extract must precede psort.filter (tool-pair split)."""
    orders = {s["tool"]: s["order"] for s in disk_playbook["steps"]}
    assert "plaso.extract" in orders, "plaso.extract missing"
    assert "psort.filter" in orders, "psort.filter missing"
    assert orders["plaso.extract"] < orders["psort.filter"], (
        "plaso.extract must precede psort.filter"
    )


def test_required_tools_present(disk_playbook: dict) -> None:
    """All required disk analysis tools must appear."""
    tools = {s["tool"] for s in disk_playbook["steps"]}
    required = {
        "image_hash_verify",
        "mmls",
        "fsstat",
        "fls",
        "mftecmd",
        "recmd",
        "pecmd",
        "hayabusa.csv_timeline",
        "hayabusa.filter",
        "plaso.extract",
        "psort.filter",
    }
    missing = required - tools
    assert not missing, f"disk.yml missing required tools: {sorted(missing)}"


def test_disk_playbook_validates_against_schema(disk_playbook_schema) -> None:
    """disk.yml must parse cleanly through the Playbook Pydantic schema."""
    from verdict.schemas.playbook import Playbook

    assert isinstance(disk_playbook_schema, Playbook)
    assert disk_playbook_schema.schema_version == "v1"


def test_step_orders_unique(disk_playbook: dict) -> None:
    orders = [s["order"] for s in disk_playbook["steps"]]
    assert len(orders) == len(set(orders)), "Duplicate step orders in disk.yml"
