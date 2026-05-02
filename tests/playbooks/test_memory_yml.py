"""W1.F.2 — verdict/playbooks/memory.yml structural tests.

RED: runs before memory.yml exists.
GREEN: passes after memory.yml is authored.

SANS canonical Volatility 3 memory sequence requirements:
- first_move must be windows.info
- DKOM divergence rule on psscan step (order 3)
- All 11 canonical steps present (windows.info through callbacks)
- LOLBIN_match rule on cmdline step
- malfind step carries malfind process-injection rules
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PLAYBOOKS_DIR = Path(__file__).resolve().parents[2] / "verdict" / "playbooks"
MEMORY_YML = PLAYBOOKS_DIR / "memory.yml"


@pytest.fixture(scope="module")
def memory_playbook() -> dict:
    assert MEMORY_YML.exists(), f"memory.yml not found at {MEMORY_YML}"
    return yaml.safe_load(MEMORY_YML.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def memory_playbook_schema():
    from verdict.schemas.playbook import Playbook

    return Playbook.from_yaml(MEMORY_YML)


def test_memory_yml_exists() -> None:
    assert MEMORY_YML.exists(), f"verdict/playbooks/memory.yml not found"


def test_evidence_type_is_memory(memory_playbook: dict) -> None:
    assert memory_playbook["evidence_type"] == "memory"


def test_first_move_is_windows_info(memory_playbook: dict) -> None:
    """SANS canonical first move for memory images is windows.info."""
    assert memory_playbook["first_move"] == "windows.info"


def test_memory_playbook_has_dkom_rule(memory_playbook: dict) -> None:
    """psscan step (order 3) must carry the DKOM divergence rule (v4.6 F4)."""
    steps = memory_playbook["steps"]
    psscan_steps = [s for s in steps if s.get("tool") == "vol3.windows.psscan"]
    assert psscan_steps, "No psscan step found in memory.yml"
    psscan = psscan_steps[0]
    rule = psscan.get("rule", "")
    assert "DKOM_divergence" in rule, (
        f"psscan step must carry DKOM_divergence rule; got: {rule!r}"
    )
    assert "T1014" in rule, "DKOM rule must reference T1014"
    assert "PROCESS_MEMORY" in rule, "DKOM rule must reference PROCESS_MEMORY artifact class"


def test_psscan_order_after_pslist(memory_playbook: dict) -> None:
    """pslist must come before psscan (orders 2 and 3 per Appendix C.1)."""
    steps = {s["tool"]: s["order"] for s in memory_playbook["steps"]}
    assert "vol3.windows.pslist" in steps, "pslist must be in memory.yml"
    assert "vol3.windows.psscan" in steps, "psscan must be in memory.yml"
    assert steps["vol3.windows.pslist"] < steps["vol3.windows.psscan"], (
        "pslist must precede psscan"
    )


def test_windows_info_is_first_step(memory_playbook: dict) -> None:
    """windows.info must be order=1 (canonical first move)."""
    steps = memory_playbook["steps"]
    first = min(steps, key=lambda s: s["order"])
    assert first["tool"] == "vol3.windows.info", (
        f"First step tool must be vol3.windows.info; got {first['tool']!r}"
    )


def test_all_eleven_canonical_tools_present(memory_playbook: dict) -> None:
    """All 11 canonical Volatility 3 steps must be present."""
    tools = {s["tool"] for s in memory_playbook["steps"]}
    required = {
        "vol3.windows.info",
        "vol3.windows.pslist",
        "vol3.windows.psscan",
        "vol3.windows.pstree",
        "vol3.windows.cmdline",
        "vol3.windows.dlllist",
        "vol3.windows.malfind",
        "vol3.windows.netscan",
        "vol3.windows.svcscan",
        "vol3.windows.handles",
        "vol3.windows.callbacks",
    }
    missing = required - tools
    assert not missing, f"memory.yml missing tools: {sorted(missing)}"


def test_lolbin_rule_on_cmdline_step(memory_playbook: dict) -> None:
    """cmdline step must carry the LOLBIN_match rule."""
    steps = memory_playbook["steps"]
    cmdline_steps = [s for s in steps if s.get("tool") == "vol3.windows.cmdline"]
    assert cmdline_steps, "No cmdline step found in memory.yml"
    rule = cmdline_steps[0].get("rule", "")
    assert "LOLBIN_match" in rule, (
        f"cmdline step must carry LOLBIN_match rule; got: {rule!r}"
    )
    assert "T1218" in rule, "LOLBIN_match rule must reference T1218"


def test_malfind_injection_rules(memory_playbook: dict) -> None:
    """malfind step must reference process-injection sub-techniques."""
    steps = memory_playbook["steps"]
    malfind_steps = [s for s in steps if s.get("tool") == "vol3.windows.malfind"]
    assert malfind_steps, "No malfind step found in memory.yml"
    rule = malfind_steps[0].get("rule", "")
    # T1055.012 = Process Hollowing, T1055.002 = PE Injection, T1055.001 = DLL injection
    for sub in ("T1055.012", "T1055.002", "T1055.001"):
        assert sub in rule, f"malfind rule must reference {sub}; got: {rule!r}"


def test_memory_playbook_validates_against_schema(memory_playbook_schema) -> None:
    """memory.yml must parse cleanly through the Playbook Pydantic schema."""
    from verdict.schemas.playbook import Playbook

    assert isinstance(memory_playbook_schema, Playbook)
    assert memory_playbook_schema.schema_version == "v1"


def test_step_orders_unique_and_sequential(memory_playbook: dict) -> None:
    """Step order values must be unique."""
    orders = [s["order"] for s in memory_playbook["steps"]]
    assert len(orders) == len(set(orders)), "Duplicate step orders in memory.yml"
