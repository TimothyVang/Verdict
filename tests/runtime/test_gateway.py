from __future__ import annotations

import inspect
from importlib.util import find_spec
from pathlib import Path

import pytest

from verdict.runtime.mode_detect import Mode


def test_fastmcp_gateway_reports_missing_dependency_when_unavailable() -> None:
    from verdict.runtime.gateway import FastMCPUnavailableError, build_fastmcp_gateway

    if find_spec("fastmcp") is not None:
        pytest.skip("FastMCP is installed in this environment")

    with pytest.raises(FastMCPUnavailableError, match="FastMCP is not installed"):
        build_fastmcp_gateway()


def test_fastmcp_tool_does_not_accept_caller_controlled_cases_dir() -> None:
    from verdict.runtime.gateway import build_fastmcp_gateway

    signature = inspect.signature(build_fastmcp_gateway)
    source = inspect.getsource(build_fastmcp_gateway)

    assert "cases_dir" in signature.parameters
    assert "cases_dir: str" not in source


def test_case_init_requested_airgap_fails_closed_without_reachable_sglang(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from verdict.runtime.gateway import GatewayModeUnavailableError, _ensure_mode_available

    monkeypatch.delenv("SGLANG_BASE_URL", raising=False)

    with pytest.raises(GatewayModeUnavailableError, match="airgap mode requires SGLANG_BASE_URL"):
        _ensure_mode_available(Mode.AIRGAP, timeout_seconds=0.01)


def test_case_init_missing_evidence_fails_before_case_directory(tmp_path: Path) -> None:
    from verdict.runtime.gateway import GatewayEvidenceError, case_init

    with pytest.raises(GatewayEvidenceError, match="evidence path does not exist"):
        case_init(
            evidence_path=tmp_path / "missing.E01",
            cases_dir=tmp_path / "cases",
            requested_mode=None,
            hmac_key=b"k" * 32,
            mode_timeout_seconds=0.01,
        )

    assert not (tmp_path / "cases").exists()
