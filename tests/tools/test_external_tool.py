from __future__ import annotations

import verdict.tools as tools
from verdict.tools import external
from verdict.tools.registry import available_tools


def test_registered_forensic_tools_do_not_expose_host_execution_wrapper() -> None:
    assert not hasattr(external, "ExternalToolWrapper")
    assert "build_tool_wrapper" not in tools.__all__


def test_available_tools_does_not_probe_host_path(monkeypatch) -> None:
    def run(*args, **kwargs):  # pragma: no cover - should never be called by this test
        raise AssertionError("available_tools must not execute host or sandbox probes")

    monkeypatch.setattr("subprocess.run", run)

    assert available_tools() == {
        "vol3.info": False,
        "vol3.pslist": False,
        "vol3.psscan": False,
        "mmls": False,
        "fsstat": False,
        "fls": False,
    }
