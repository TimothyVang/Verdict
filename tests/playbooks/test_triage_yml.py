"""W1.F.4 — verdict/playbooks/triage.yml structural tests.

RED: runs before triage.yml exists.
GREEN: passes after triage.yml is authored.

KAPE/Velociraptor triage zip flow requirements per Appendix C.3:
- first_move: unzip_to_readonly_mount
- Registry hives (recmd) FIRST among analysis tools
- Prefetch (pecmd) after registry
- Amcache step must carry AMCACHE_LASTMODIFIED_NOT_EXEC caveat reminder
- hayabusa_csv_timeline before hayabusa_filter
- mftecmd present
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PLAYBOOKS_DIR = Path(__file__).resolve().parents[2] / "verdict" / "playbooks"
TRIAGE_YML = PLAYBOOKS_DIR / "triage.yml"


@pytest.fixture(scope="module")
def triage_playbook() -> dict:
    assert TRIAGE_YML.exists(), f"triage.yml not found at {TRIAGE_YML}"
    return yaml.safe_load(TRIAGE_YML.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def triage_playbook_schema():
    from verdict.schemas.playbook import Playbook

    return Playbook.from_yaml(TRIAGE_YML)


def test_triage_yml_exists() -> None:
    assert TRIAGE_YML.exists(), "verdict/playbooks/triage.yml not found"


def test_evidence_type_is_triage(triage_playbook: dict) -> None:
    assert triage_playbook["evidence_type"] == "triage"


def test_first_move_is_unzip(triage_playbook: dict) -> None:
    """KAPE/Velociraptor zip must be extracted to read-only mount first."""
    assert triage_playbook["first_move"] == "unzip_to_readonly_mount"


def test_unzip_is_first_step(triage_playbook: dict) -> None:
    steps = triage_playbook["steps"]
    first = min(steps, key=lambda s: s["order"])
    assert first["tool"] == "unzip_to_readonly_mount", (
        f"First step must be unzip_to_readonly_mount; got {first['tool']!r}"
    )


def test_registry_first(triage_playbook: dict) -> None:
    """Registry hives (recmd) must come first among analysis tools (order 2)."""
    steps = triage_playbook["steps"]
    orders = {s["tool"]: s["order"] for s in steps}
    # recmd must be the lowest-ordered analysis tool (after unzip which is order 1)
    assert "recmd" in orders, "recmd must be in triage.yml"
    analysis_tools = {t: o for t, o in orders.items() if t != "unzip_to_readonly_mount"}
    first_analysis = min(analysis_tools, key=lambda t: analysis_tools[t])
    assert first_analysis == "recmd", (
        f"recmd must be first analysis tool; got {first_analysis!r} at order "
        f"{analysis_tools[first_analysis]}, recmd at {orders['recmd']}"
    )


def test_pecmd_after_recmd(triage_playbook: dict) -> None:
    """Prefetch (pecmd) must follow registry (recmd)."""
    orders = {s["tool"]: s["order"] for s in triage_playbook["steps"]}
    assert "recmd" in orders, "recmd missing"
    assert "pecmd" in orders, "pecmd missing"
    assert orders["recmd"] < orders["pecmd"], "recmd must precede pecmd"


def test_amcache_has_caveat_rule(triage_playbook: dict) -> None:
    """Amcache parse step must explicitly remind examiner of AMCACHE_LASTMODIFIED_NOT_EXEC caveat."""
    steps = triage_playbook["steps"]
    amcache_steps = [s for s in steps if "amcache" in s.get("tool", "").lower()]
    assert amcache_steps, "No amcache step found in triage.yml"
    rule = amcache_steps[0].get("rule", "")
    assert "AMCACHE_LASTMODIFIED_NOT_EXEC" in rule, (
        f"amcache step must carry AMCACHE_LASTMODIFIED_NOT_EXEC caveat; got: {rule!r}"
    )


def test_hayabusa_csv_before_filter(triage_playbook: dict) -> None:
    """hayabusa_csv_timeline (extract) must precede hayabusa_filter."""
    orders = {s["tool"]: s["order"] for s in triage_playbook["steps"]}
    assert "hayabusa.csv_timeline" in orders, "hayabusa.csv_timeline missing from triage.yml"
    assert "hayabusa.filter" in orders, "hayabusa.filter missing from triage.yml"
    assert orders["hayabusa.csv_timeline"] < orders["hayabusa.filter"], (
        "hayabusa extract must precede hayabusa filter"
    )


def test_mftecmd_present(triage_playbook: dict) -> None:
    """mftecmd must be present for $MFT timeline analysis."""
    tools = {s["tool"] for s in triage_playbook["steps"]}
    assert "mftecmd" in tools, "mftecmd missing from triage.yml"


def test_required_tools_present(triage_playbook: dict) -> None:
    """All required triage analysis tools must appear."""
    tools = {s["tool"] for s in triage_playbook["steps"]}
    required = {
        "unzip_to_readonly_mount",
        "recmd",
        "pecmd",
        "hayabusa.csv_timeline",
        "hayabusa.filter",
        "mftecmd",
    }
    # amcache_parse is required — check via partial match
    amcache_present = any("amcache" in t.lower() for t in tools)
    assert amcache_present, "amcache_parse tool missing from triage.yml"
    missing = required - tools
    assert not missing, f"triage.yml missing required tools: {sorted(missing)}"


def test_triage_playbook_validates_against_schema(triage_playbook_schema) -> None:
    """triage.yml must parse cleanly through the Playbook Pydantic schema."""
    from verdict.schemas.playbook import Playbook

    assert isinstance(triage_playbook_schema, Playbook)
    assert triage_playbook_schema.schema_version == "v1"


def test_step_orders_unique(triage_playbook: dict) -> None:
    orders = [s["order"] for s in triage_playbook["steps"]]
    assert len(orders) == len(set(orders)), "Duplicate step orders in triage.yml"
