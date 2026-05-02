from enum import Enum


class CaveatID(str, Enum):
    """Tier-1 caveats from project agent-config/MEMORY.md.

    These are the misreads Rob Lee uses to spot a fake examiner.
    Each value is the schema-layer identifier that
    `Finding.caveats_acknowledged` accepts (CLAUDE.md Sec 3.3).
    """

    AMCACHE_LASTMODIFIED_NOT_EXEC = "amcache_lastmodified_neq_execution"
    SHIMCACHE_ORDER_CHANGED_WIN81 = "shimcache_order_lru_pre81_insertion_post81"
    PREFETCH_SSD_DISABLED = "prefetch_disabled_on_ssd_or_gpo"
    MFT_SI_STOMPABLE = "mft_si_timestomp_use_fn"
    USNJRNL_WRAPS = "usnjrnl_wraps_treat_gaps_carefully"
    LOGON_TYPE_3_VS_10 = "evtx_4624_type3_network_neq_type10_rdp"
    SYSMON_PROCESSGUID_OVER_PID = "sysmon_processguid_correlation_key_not_pid"
