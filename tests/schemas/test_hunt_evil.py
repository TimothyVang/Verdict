"""W1.F.8 — HuntEvilBaseline + ProcessBaselineAnomaly schema tests.

RED: runs before verdict/schemas/hunt_evil.py exists.
GREEN: passes after implementation.

Requirements per BUILD_PLAN.md W1.F.8 and ARCHITECTURE.md §4:
- HuntEvilBaseline: keyed by process name with expected parent/path/signing/
  instance_count baselines for 8 canonical Windows processes
- ProcessBaselineAnomaly: Hypothesis subtype that maps to T1036.005
  (Match Legitimate Name or Location)
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_baseline_loads() -> None:
    """HuntEvilBaseline can be instantiated with all required fields."""
    from verdict.schemas.hunt_evil import HuntEvilBaseline

    b = HuntEvilBaseline(
        process_name="svchost.exe",
        expected_parent="services.exe",
        expected_path=r"C:\Windows\System32\svchost.exe",
        expected_signing=True,
        expected_instance_count="1+",
        notes="Multiple instances expected; each must have -k argument",
    )
    assert b.process_name == "svchost.exe"
    assert b.expected_parent == "services.exe"
    assert b.expected_signing is True


def test_anomaly_maps_to_T1036_005() -> None:
    """ProcessBaselineAnomaly must carry T1036.005 (process masquerade)."""
    from verdict.schemas.hunt_evil import ProcessBaselineAnomaly

    anomaly = ProcessBaselineAnomaly(
        process_name="scvhost.exe",
        observed_parent="cmd.exe",
        expected_parent="services.exe",
        observed_path=r"C:\Users\Public\scvhost.exe",
        expected_path=r"C:\Windows\System32\svchost.exe",
        deviation_description="Process name misspelling + wrong parent + wrong path",
        mitre_technique="T1036.005",
    )
    assert anomaly.mitre_technique == "T1036.005"
    assert "T1036" in anomaly.mitre_technique


def test_anomaly_mitre_technique_locked_to_T1036_005() -> None:
    """ProcessBaselineAnomaly.mitre_technique must always be T1036.005."""
    from verdict.schemas.hunt_evil import ProcessBaselineAnomaly

    # Default value should be T1036.005
    anomaly = ProcessBaselineAnomaly(
        process_name="lsass.exe",
        observed_parent="cmd.exe",
        expected_parent="wininit.exe",
        observed_path=r"C:\Windows\Temp\lsass.exe",
        expected_path=r"C:\Windows\System32\lsass.exe",
        deviation_description="Wrong parent process",
    )
    assert anomaly.mitre_technique == "T1036.005", (
        "ProcessBaselineAnomaly must default mitre_technique to T1036.005"
    )


def test_anomaly_wrong_technique_rejected() -> None:
    """ProcessBaselineAnomaly must reject techniques other than T1036.005."""
    from verdict.schemas.hunt_evil import ProcessBaselineAnomaly

    with pytest.raises(ValidationError):
        ProcessBaselineAnomaly(
            process_name="lsass.exe",
            observed_parent="cmd.exe",
            expected_parent="wininit.exe",
            observed_path=r"C:\Windows\Temp\lsass.exe",
            expected_path=r"C:\Windows\System32\lsass.exe",
            deviation_description="Wrong parent",
            mitre_technique="T1059",  # wrong — must be T1036.005
        )


def test_baseline_requires_process_name() -> None:
    """HuntEvilBaseline must require process_name."""
    from verdict.schemas.hunt_evil import HuntEvilBaseline

    with pytest.raises((ValidationError, TypeError)):
        HuntEvilBaseline(
            expected_parent="services.exe",
            expected_path=r"C:\Windows\System32\svchost.exe",
        )


def test_baseline_schema_version() -> None:
    """HuntEvilBaseline must carry schema_version field."""
    from verdict.schemas.hunt_evil import HuntEvilBaseline

    b = HuntEvilBaseline(
        process_name="explorer.exe",
        expected_parent="userinit.exe",
        expected_path=r"C:\Windows\explorer.exe",
        expected_signing=True,
        expected_instance_count="1",
    )
    assert b.schema_version == "v1"


def test_anomaly_schema_version() -> None:
    """ProcessBaselineAnomaly must carry schema_version field."""
    from verdict.schemas.hunt_evil import ProcessBaselineAnomaly

    anomaly = ProcessBaselineAnomaly(
        process_name="smss.exe",
        observed_parent="svchost.exe",
        expected_parent="System",
        observed_path=r"C:\Temp\smss.exe",
        expected_path=r"C:\Windows\System32\smss.exe",
        deviation_description="Wrong parent",
    )
    assert anomaly.schema_version == "v1"


def test_baseline_optional_fields_default() -> None:
    """notes and expected_instance_count should be optional."""
    from verdict.schemas.hunt_evil import HuntEvilBaseline

    b = HuntEvilBaseline(
        process_name="csrss.exe",
        expected_parent="smss.exe",
        expected_path=r"C:\Windows\System32\csrss.exe",
    )
    assert b.notes is None
    assert b.expected_instance_count is None
    assert b.expected_signing is None
