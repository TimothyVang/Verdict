from __future__ import annotations

from enum import Enum


class ArtifactClass(str, Enum):
    """Evidence artifact classes used for corroborating findings."""

    PREFETCH = "prefetch"
    AMCACHE = "amcache"
    SHIMCACHE = "shimcache"
    EVTX_4688 = "evtx_4688"
    SYSMON_1 = "sysmon_1"
    NETWORK = "network"
    REGISTRY_RUN = "registry_run"
    TASK_SCHEDULER = "task_scheduler"
    WMI_SUBSCRIPTION = "wmi_subscription"
    MFT = "mft"
    PROCESS_MEMORY = "process_memory"
    YARA_HIT = "yara_hit"
    SIGMA_HIT = "sigma_hit"
