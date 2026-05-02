"""W1.F.10 — executor system-prompt include tests.

RED: runs before verdict/planning/executor_prompt.py exists.
GREEN: passes after implementation.

render_executor_prompt(role) -> str must:
- Include the full examiner_caveats.md content (AMCACHE_LASTMODIFIED_NOT_EXEC, etc.)
- Include Hunt Evil baseline entries for svchost.exe
- Return a non-empty string that composes both sources
- Accept a role parameter ("vol_exec", "hay_exec", "pls_exec", "mft_exec")
"""
from __future__ import annotations

import pytest


def test_includes_caveats_and_hunt_evil() -> None:
    """Prompt must contain AMCACHE_LASTMODIFIED_NOT_EXEC and svchost.exe."""
    from verdict.planning.executor_prompt import render_executor_prompt

    prompt = render_executor_prompt("vol_exec")
    assert "AMCACHE_LASTMODIFIED_NOT_EXEC" in prompt, (
        "Executor prompt must include Tier-1 caveats (AMCACHE_LASTMODIFIED_NOT_EXEC)"
    )
    assert "svchost.exe" in prompt, (
        "Executor prompt must include hunt_evil baselines (svchost.exe)"
    )


def test_all_seven_caveats_in_prompt() -> None:
    """All 7 Tier-1 CaveatIDs must appear in the executor prompt."""
    from verdict.planning.executor_prompt import render_executor_prompt

    prompt = render_executor_prompt("hay_exec")
    for cav in [
        "AMCACHE_LASTMODIFIED_NOT_EXEC",
        "SHIMCACHE_ORDER_CHANGED_WIN81",
        "PREFETCH_SSD_DISABLED",
        "MFT_SI_STOMPABLE",
        "USNJRNL_WRAPS",
        "LOGON_TYPE_3_VS_10",
        "SYSMON_PROCESSGUID_OVER_PID",
    ]:
        assert cav in prompt, f"Executor prompt missing caveat: {cav}"


def test_all_eight_processes_in_prompt() -> None:
    """All 8 canonical Hunt Evil processes must appear in the prompt."""
    from verdict.planning.executor_prompt import render_executor_prompt

    prompt = render_executor_prompt("mft_exec")
    for proc in [
        "svchost.exe", "lsass.exe", "csrss.exe", "winlogon.exe",
        "services.exe", "wininit.exe", "explorer.exe", "smss.exe",
    ]:
        assert proc in prompt, f"Executor prompt missing process baseline: {proc}"


def test_prompt_nonempty_string() -> None:
    """render_executor_prompt must return a non-empty string."""
    from verdict.planning.executor_prompt import render_executor_prompt

    result = render_executor_prompt("pls_exec")
    assert isinstance(result, str) and len(result.strip()) > 100


def test_prompt_contains_role_header() -> None:
    """Prompt should identify the executor role for clarity."""
    from verdict.planning.executor_prompt import render_executor_prompt

    prompt = render_executor_prompt("vol_exec")
    assert "vol_exec" in prompt or "Executor" in prompt, (
        "Prompt must identify executor role"
    )


def test_prompt_contains_dkom_hint() -> None:
    """vol_exec prompt must mention DKOM/T1014 divergence."""
    from verdict.planning.executor_prompt import render_executor_prompt

    prompt = render_executor_prompt("vol_exec")
    assert "T1014" in prompt or "DKOM" in prompt, (
        "vol_exec prompt must mention T1014 or DKOM for DKOM detection"
    )
