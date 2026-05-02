"""CaveatID — Tier-1 examiner caveats (CLAUDE.md §3.3).

The seven canonical caveats every examiner is expected to acknowledge when
citing the relevant artifact class. Encoded as a string-valued enum so
serialised LedgerEntry / Finding payloads carry the human-readable id, and
schema validators in `Finding` enforce per-class acknowledgment.
"""

from __future__ import annotations

from enum import Enum


class CaveatID(str, Enum):
    """Tier-1 examiner caveats (CLAUDE.md §3.3)."""

    # Amcache LastModified is bucket-rollover time, not execution time.
    AMCACHE_LASTMODIFIED_NOT_EXEC = "amcache_lastmodified_neq_execution"

    # ShimCache ordering: insertion-order on Win >=8.1, LRU on Win <8.1.
    SHIMCACHE_ORDER_CHANGED_WIN81 = "shimcache_order_lru_pre81_insertion_post81"

    # Prefetch may be disabled on SSD-only hosts or by GPO.
    PREFETCH_SSD_DISABLED = "prefetch_disabled_on_ssd_or_gpo"

    # $STANDARD_INFORMATION timestamps are timestompable; prefer $FILE_NAME.
    MFT_SI_STOMPABLE = "mft_si_timestomp_use_fn"

    # USN journal wraps; gaps are not absence of activity.
    USNJRNL_WRAPS = "usnjrnl_wraps_treat_gaps_carefully"

    # 4624 LogonType 3 (network) is not LogonType 10 (RDP).
    LOGON_TYPE_3_VS_10 = "evtx_4624_type3_network_neq_type10_rdp"

    # Sysmon ProcessGuid is the correlation key, not PID.
    SYSMON_PROCESSGUID_OVER_PID = "sysmon_processguid_correlation_key_not_pid"
