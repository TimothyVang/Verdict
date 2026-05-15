from __future__ import annotations

from enum import StrEnum


class ArtifactClass(StrEnum):
    """Evidence artifact classes used for corroborating findings."""

    PREFETCH = "prefetch"
    POWERSHELL_TRANSCRIPT = "powershell_transcript"
    AMCACHE = "amcache"
    SHIMCACHE = "shimcache"
    EVTX_4624 = "evtx_4624"
    EVTX_4688 = "evtx_4688"
    SYSMON_1 = "sysmon_1"
    NETWORK = "network"
    REGISTRY_RUN = "registry_run"
    TASK_SCHEDULER = "task_scheduler"
    WMI_SUBSCRIPTION = "wmi_subscription"
    MFT = "mft"
    USNJRNL = "usnjrnl"
    PROCESS_MEMORY = "process_memory"
    YARA_HIT = "yara_hit"
    SIGMA_HIT = "sigma_hit"
