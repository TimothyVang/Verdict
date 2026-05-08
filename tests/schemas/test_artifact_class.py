from __future__ import annotations

from verdict.schemas.artifact_class import ArtifactClass


def test_enum_has_required_members_for_tier_1_caveat_triggers() -> None:
    assert {member.value for member in ArtifactClass} == {
        "prefetch",
        "amcache",
        "shimcache",
        "evtx_4624",
        "evtx_4688",
        "sysmon_1",
        "network",
        "registry_run",
        "task_scheduler",
        "wmi_subscription",
        "mft",
        "usnjrnl",
        "process_memory",
        "yara_hit",
        "sigma_hit",
    }
