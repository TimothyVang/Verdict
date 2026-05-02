from verdict.schemas.artifact_class import ArtifactClass


def test_enum_has_13_required_members() -> None:
    expected = {
        "PREFETCH",
        "AMCACHE",
        "SHIMCACHE",
        "EVTX_4688",
        "SYSMON_1",
        "NETWORK",
        "REGISTRY_RUN",
        "TASK_SCHEDULER",
        "WMI_SUBSCRIPTION",
        "MFT",
        "PROCESS_MEMORY",
        "YARA_HIT",
        "SIGMA_HIT",
    }
    actual = {member.name for member in ArtifactClass}
    assert len(ArtifactClass) == 13, f"Expected 13 members, got {len(ArtifactClass)}"
    assert actual == expected, f"Missing: {expected - actual}, Extra: {actual - expected}"
