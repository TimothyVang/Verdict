from verdict.schemas.caveat_id import CaveatID


def test_enum_covers_tier1_memory_md() -> None:
    """All seven Tier-1 caveats from CLAUDE.md §3.3 must be present.

    These are the misreads Rob Lee uses to spot a fake examiner.
    Source of truth: CLAUDE.md §3.3 (also project agent-config/MEMORY.md).
    """
    expected = {
        "AMCACHE_LASTMODIFIED_NOT_EXEC",
        "SHIMCACHE_ORDER_CHANGED_WIN81",
        "PREFETCH_SSD_DISABLED",
        "MFT_SI_STOMPABLE",
        "USNJRNL_WRAPS",
        "LOGON_TYPE_3_VS_10",
        "SYSMON_PROCESSGUID_OVER_PID",
    }
    actual = {member.name for member in CaveatID}
    assert len(CaveatID) == 7, f"Expected 7 members, got {len(CaveatID)}"
    assert actual == expected, f"Missing: {expected - actual}, Extra: {actual - expected}"


def test_enum_values_match_appendix_a2() -> None:
    """Wire values per BUILD_PLAN Appendix A.2 (CaveatID is a str-Enum)."""
    assert CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC.value == "amcache_lastmodified_neq_execution"
    assert CaveatID.SHIMCACHE_ORDER_CHANGED_WIN81.value == "shimcache_order_lru_pre81_insertion_post81"
    assert CaveatID.PREFETCH_SSD_DISABLED.value == "prefetch_disabled_on_ssd_or_gpo"
    assert CaveatID.MFT_SI_STOMPABLE.value == "mft_si_timestomp_use_fn"
    assert CaveatID.USNJRNL_WRAPS.value == "usnjrnl_wraps_treat_gaps_carefully"
    assert CaveatID.LOGON_TYPE_3_VS_10.value == "evtx_4624_type3_network_neq_type10_rdp"
    assert CaveatID.SYSMON_PROCESSGUID_OVER_PID.value == "sysmon_processguid_correlation_key_not_pid"


def test_caveat_id_is_str_enum() -> None:
    """Schemas serialise CaveatID via its str value; ensure str-Enum subclass."""
    assert issubclass(CaveatID, str)
    assert CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC == "amcache_lastmodified_neq_execution"
