from enum import Enum


class ArtifactClass(str, Enum):
    """Multi-artifact corroboration vocabulary.
    SANS FOR500 doctrine: no single artifact proves execution.
    Cited from project agent-config/MEMORY.md >=2-artifact rule."""

    PREFETCH = "prefetch"
    AMCACHE = "amcache"
    SHIMCACHE = "shimcache"
    EVTX_4688 = "evtx_4688"               # Process Creation
    SYSMON_1 = "sysmon_1"                 # Sysmon ProcessCreate
    NETWORK = "network"                   # netscan, conn logs
    REGISTRY_RUN = "registry_run"
    TASK_SCHEDULER = "task_scheduler"
    WMI_SUBSCRIPTION = "wmi_subscription"
    MFT = "mft"                           # $MFT, $J/UsnJrnl
    EVTX_4624 = "evtx_4624"              # Security/4624 logon events; LOGON_TYPE_3_VS_10 caveat trigger
    USNJRNL = "usnjrnl"                  # USN Change Journal ($J); USNJRNL_WRAPS caveat trigger
    PROCESS_MEMORY = "process_memory"     # malfind/RWX/hollowed
    YARA_HIT = "yara_hit"
    SIGMA_HIT = "sigma_hit"
