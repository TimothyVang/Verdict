from __future__ import annotations

from verdict.schemas.hunt_evil import HuntEvilBaseline, ProcessBaselineAnomaly


def test_baseline_loads() -> None:
    baseline = HuntEvilBaseline(
        process_name="svchost.exe",
        expected_parent_names=["services.exe"],
        expected_path_prefixes=["C:\\Windows\\System32"],
        expected_user_names=["NT AUTHORITY\\SYSTEM"],
    )

    assert baseline.process_name == "svchost.exe"
    assert baseline.expected_parent_names == ["services.exe"]


def test_anomaly_maps_to_t1036_005() -> None:
    anomaly = ProcessBaselineAnomaly(
        process_name="svchost.exe",
        observed_parent_name="cmd.exe",
        observed_path="C:\\Users\\Public\\svchost.exe",
        reason="Unexpected parent and path for svchost.exe",
    )

    assert anomaly.mitre_technique == "T1036.005"
