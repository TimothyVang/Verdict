"""W1.F.7 — verdict/planning/prompts/examiner_caveats.md structural tests.

RED: runs before examiner_caveats.md exists.
GREEN: passes after the prompt file is authored per Appendix B.1.

Requirements per CLAUDE.md §3.3 and BUILD_PLAN.md Appendix B.1:
- All 7 CaveatID names must be present as headings
- Each caveat must carry its trigger condition description
- File must be loadable as plain Markdown (no invalid syntax)
"""
from __future__ import annotations

from pathlib import Path

import pytest

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "verdict" / "planning" / "prompts"
CAVEATS_MD = PROMPTS_DIR / "examiner_caveats.md"

ALL_SEVEN_CAVEAT_IDS = [
    "AMCACHE_LASTMODIFIED_NOT_EXEC",
    "SHIMCACHE_ORDER_CHANGED_WIN81",
    "PREFETCH_SSD_DISABLED",
    "MFT_SI_STOMPABLE",
    "USNJRNL_WRAPS",
    "LOGON_TYPE_3_VS_10",
    "SYSMON_PROCESSGUID_OVER_PID",
]


def test_examiner_caveats_file_exists() -> None:
    assert CAVEATS_MD.exists(), f"examiner_caveats.md not found at {CAVEATS_MD}"


@pytest.fixture(scope="module")
def caveats_content() -> str:
    assert CAVEATS_MD.exists(), f"examiner_caveats.md not found at {CAVEATS_MD}"
    return CAVEATS_MD.read_text(encoding="utf-8")


def test_all_seven_caveats_present(caveats_content: str) -> None:
    """All 7 Tier-1 CaveatIDs from CLAUDE.md §3.3 must appear in the file."""
    missing = [cid for cid in ALL_SEVEN_CAVEAT_IDS if cid not in caveats_content]
    assert not missing, (
        f"examiner_caveats.md missing CaveatIDs: {missing}"
    )


def test_each_caveat_is_a_heading(caveats_content: str) -> None:
    """Each CaveatID must appear as a Markdown heading (## CAVEAT_ID)."""
    lines = caveats_content.splitlines()
    heading_lines = {line.strip().lstrip("#").strip() for line in lines if line.startswith("#")}
    missing_headings = [cid for cid in ALL_SEVEN_CAVEAT_IDS if cid not in heading_lines]
    assert not missing_headings, (
        f"These CaveatIDs must be Markdown headings: {missing_headings}"
    )


def test_amcache_trigger_description(caveats_content: str) -> None:
    """AMCACHE caveat must explain LastModified vs execution time distinction."""
    assert "LastModified" in caveats_content, (
        "AMCACHE caveat must mention LastModified"
    )
    assert "execution" in caveats_content.lower(), (
        "AMCACHE caveat must describe execution time context"
    )


def test_shimcache_win81_mentioned(caveats_content: str) -> None:
    """SHIMCACHE caveat must mention Windows ≥8.1 / insertion-order."""
    shimcache_idx = caveats_content.find("SHIMCACHE_ORDER_CHANGED_WIN81")
    assert shimcache_idx >= 0
    # Check the surrounding text for key terms
    surrounding = caveats_content[shimcache_idx: shimcache_idx + 300]
    assert "8.1" in surrounding or "insertion" in surrounding.lower(), (
        f"SHIMCACHE caveat must mention Windows 8.1 or insertion-order; got: {surrounding!r}"
    )


def test_prefetch_ssd_mention(caveats_content: str) -> None:
    """PREFETCH_SSD_DISABLED caveat must mention SSD."""
    prefetch_idx = caveats_content.find("PREFETCH_SSD_DISABLED")
    assert prefetch_idx >= 0
    surrounding = caveats_content[prefetch_idx: prefetch_idx + 300]
    assert "SSD" in surrounding or "disabled" in surrounding.lower(), (
        f"PREFETCH_SSD caveat must mention SSD or disabled; got: {surrounding!r}"
    )


def test_mft_si_stompable_fn_reference(caveats_content: str) -> None:
    """MFT_SI_STOMPABLE must reference $FILE_NAME / $FN preference."""
    mft_idx = caveats_content.find("MFT_SI_STOMPABLE")
    assert mft_idx >= 0
    surrounding = caveats_content[mft_idx: mft_idx + 700]
    assert "FILE_NAME" in surrounding or "$FN" in surrounding, (
        f"MFT_SI caveat must reference $FILE_NAME or $FN; got: {surrounding!r}"
    )


def test_usnjrnl_wraps_circular_buffer_mention(caveats_content: str) -> None:
    """USNJRNL_WRAPS must mention circular buffer / wrapping."""
    usn_idx = caveats_content.find("USNJRNL_WRAPS")
    assert usn_idx >= 0
    surrounding = caveats_content[usn_idx: usn_idx + 300]
    assert "circular" in surrounding.lower() or "wrap" in surrounding.lower(), (
        f"USNJRNL_WRAPS caveat must mention circular or wrap; got: {surrounding!r}"
    )


def test_logon_type_3_vs_10_evtx_mention(caveats_content: str) -> None:
    """LOGON_TYPE_3_VS_10 must distinguish type 3 (network) from type 10 (RDP)."""
    logon_idx = caveats_content.find("LOGON_TYPE_3_VS_10")
    assert logon_idx >= 0
    surrounding = caveats_content[logon_idx: logon_idx + 700]
    assert "3" in surrounding and "10" in surrounding, (
        "LOGON_TYPE_3_VS_10 caveat must mention logon type 3 and type 10"
    )
    assert "RDP" in surrounding or "RemoteInteractive" in surrounding, (
        f"LOGON_TYPE_3_VS_10 caveat must mention RDP or RemoteInteractive; got: {surrounding!r}"
    )


def test_sysmon_processguid_pid_distinction(caveats_content: str) -> None:
    """SYSMON_PROCESSGUID_OVER_PID must explain ProcessGuid vs PID reuse."""
    sysmon_idx = caveats_content.find("SYSMON_PROCESSGUID_OVER_PID")
    assert sysmon_idx >= 0
    surrounding = caveats_content[sysmon_idx: sysmon_idx + 400]
    assert "ProcessGuid" in surrounding or "GUID" in surrounding.upper(), (
        f"SYSMON caveat must mention ProcessGuid; got: {surrounding!r}"
    )
    assert "PID" in surrounding or "pid" in surrounding.lower(), (
        f"SYSMON caveat must mention PID reuse; got: {surrounding!r}"
    )


def test_file_is_nonempty_markdown(caveats_content: str) -> None:
    """File must have meaningful content (not just blank)."""
    assert len(caveats_content.strip()) > 200, (
        "examiner_caveats.md seems too short — expected detailed caveat descriptions"
    )
    assert "#" in caveats_content, "examiner_caveats.md must contain Markdown headings"
