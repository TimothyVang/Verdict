from __future__ import annotations

from verdict.schemas.artifact_class import ArtifactClass


def test_enum_has_13_required_members() -> None:
    assert {member.value for member in ArtifactClass} == {
        "prefetch",
        "amcache",
        "shimcache",
        "evtx_4688",
        "sysmon_1",
        "network",
        "registry_run",
        "task_scheduler",
        "wmi_subscription",
        "mft",
        "process_memory",
        "yara_hit",
        "sigma_hit",
    }
