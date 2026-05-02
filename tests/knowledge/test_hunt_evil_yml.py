"""W1.F.9 — verdict/knowledge/hunt_evil.yml structural tests.

RED: runs before hunt_evil.yml exists.
GREEN: passes after hunt_evil.yml is authored.

Requirements per BUILD_PLAN.md W1.F.9 and ARCHITECTURE.md §4:
- 8 canonical Windows process entries
- Each entry has: process_name, expected_parent, expected_path
- Optional: expected_signing, expected_instance_count, notes
- Every entry validates against HuntEvilBaseline schema
- Covers: svchost, lsass, csrss, winlogon, services, wininit, explorer, smss
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "verdict" / "knowledge"
HUNT_EVIL_YML = KNOWLEDGE_DIR / "hunt_evil.yml"

EIGHT_CANONICAL_PROCESSES = {
    "svchost.exe",
    "lsass.exe",
    "csrss.exe",
    "winlogon.exe",
    "services.exe",
    "wininit.exe",
    "explorer.exe",
    "smss.exe",
}


@pytest.fixture(scope="module")
def baselines() -> list[dict]:
    assert HUNT_EVIL_YML.exists(), f"hunt_evil.yml not found at {HUNT_EVIL_YML}"
    data = yaml.safe_load(HUNT_EVIL_YML.read_text(encoding="utf-8"))
    assert isinstance(data, list), "hunt_evil.yml root must be a YAML list"
    return data


def test_hunt_evil_yml_exists() -> None:
    assert HUNT_EVIL_YML.exists(), "verdict/knowledge/hunt_evil.yml not found"


def test_eight_canonical_processes(baselines: list[dict]) -> None:
    """All 8 canonical Windows processes must be present."""
    names = {entry["process_name"] for entry in baselines}
    missing = EIGHT_CANONICAL_PROCESSES - names
    assert not missing, f"hunt_evil.yml missing processes: {sorted(missing)}"


def test_exactly_eight_entries(baselines: list[dict]) -> None:
    """hunt_evil.yml should have exactly 8 entries."""
    assert len(baselines) == 8, (
        f"Expected 8 entries, got {len(baselines)}"
    )


def test_each_entry_has_required_fields(baselines: list[dict]) -> None:
    """Every entry must have process_name, expected_parent, expected_path."""
    for entry in baselines:
        name = entry.get("process_name", "<missing>")
        assert "process_name" in entry, f"Entry missing process_name: {entry}"
        assert "expected_parent" in entry, f"{name} missing expected_parent"
        assert "expected_path" in entry, f"{name} missing expected_path"


def test_all_entries_validate_against_schema(baselines: list[dict]) -> None:
    """Every entry must parse cleanly through HuntEvilBaseline schema."""
    from verdict.schemas.hunt_evil import HuntEvilBaseline

    for entry in baselines:
        baseline = HuntEvilBaseline.model_validate(entry)
        assert baseline.process_name in EIGHT_CANONICAL_PROCESSES, (
            f"Unexpected process: {baseline.process_name}"
        )
        assert baseline.schema_version == "v1"


def test_svchost_parent_is_services(baselines: list[dict]) -> None:
    """svchost.exe expected_parent must be services.exe."""
    svc = next(e for e in baselines if e["process_name"] == "svchost.exe")
    assert svc["expected_parent"] == "services.exe", (
        f"svchost expected_parent must be services.exe; got {svc['expected_parent']!r}"
    )


def test_lsass_parent_is_wininit(baselines: list[dict]) -> None:
    """lsass.exe expected_parent must be wininit.exe."""
    lsass = next(e for e in baselines if e["process_name"] == "lsass.exe")
    assert lsass["expected_parent"] == "wininit.exe", (
        f"lsass expected_parent must be wininit.exe; got {lsass['expected_parent']!r}"
    )


def test_smss_parent_is_system(baselines: list[dict]) -> None:
    """smss.exe expected_parent must be System."""
    smss = next(e for e in baselines if e["process_name"] == "smss.exe")
    assert smss["expected_parent"] == "System", (
        f"smss expected_parent must be System; got {smss['expected_parent']!r}"
    )


def test_explorer_expected_path_in_windows(baselines: list[dict]) -> None:
    """explorer.exe expected_path must reference Windows directory."""
    explorer = next(e for e in baselines if e["process_name"] == "explorer.exe")
    path = explorer["expected_path"]
    assert "Windows" in path, (
        f"explorer.exe expected_path must reference Windows directory; got {path!r}"
    )


def test_each_process_has_expected_path_in_system32_or_windows(baselines: list[dict]) -> None:
    """Most processes should live in System32 or Windows root."""
    # explorer.exe is in Windows root, others in System32
    exceptions = {"explorer.exe"}
    for entry in baselines:
        name = entry["process_name"]
        path = entry.get("expected_path", "")
        if name not in exceptions:
            assert "System32" in path or "system32" in path, (
                f"{name} expected_path should reference System32; got {path!r}"
            )
