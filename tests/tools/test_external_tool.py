from __future__ import annotations

import verdict.tools as tools
from verdict.tools import external
from verdict.tools.registry import available_tools, microsandbox_command


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
        "icat": False,
    }


def test_first_pass_fls_uses_stable_root_listing() -> None:
    assert microsandbox_command("fls", evidence_name="disk.E01") == [
        "fls",
        "/evidence/disk.E01",
    ]


def test_icat_places_metadata_address_after_evidence() -> None:
    assert microsandbox_command("icat", evidence_name="disk.E01", extra_args=("128986-128-4",)) == [
        "icat",
        "/evidence/disk.E01",
        "128986-128-4",
    ]


def test_vol3_command_uses_configured_symbol_and_cache_paths() -> None:
    assert microsandbox_command(
        "vol3.info",
        evidence_name="memory.mem",
        volatility_symbol_dir="/volatility-symbols",
        volatility_cache_path="/volatility-cache",
    ) == [
        "vol3",
        "--symbol-dirs",
        "/volatility-symbols",
        "--cache-path",
        "/volatility-cache",
        "-f",
        "/evidence/memory.mem",
        "windows.info",
    ]
