from __future__ import annotations

from verdict.schemas.caveat_id import CaveatID


def test_enum_has_seven_tier_1_caveats() -> None:
    assert {member.value for member in CaveatID} == {
        "AMCACHE_LASTMODIFIED_NOT_EXEC",
        "SHIMCACHE_ORDER_CHANGED_WIN81",
        "PREFETCH_SSD_DISABLED",
        "MFT_SI_STOMPABLE",
        "USNJRNL_WRAPS",
        "LOGON_TYPE_3_VS_10",
        "SYSMON_PROCESSGUID_OVER_PID",
    }
