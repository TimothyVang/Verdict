"""Tests for vol_psscan ToolWrapper — W1.E.1.

RED phase: import will fail until verdict/tools/vol3/psscan.py is implemented.

Per BUILD_PLAN W1.E.1.a:
  - Assert wrapper invokes vol3 windows.psscan with correct args.
  - Assert returns ToolOutput with parsed_artifacts: list[Artifact] of type
    "process".
  - Assert DKOM cross-validation contract: psscan must expose a pid_set()
    method so executor can compute set(psscan_pids) - set(pslist_pids).

§3.10 note: _execute() raises NotImplementedError (unimplemented real method,
NOT a mock). Tests exercise the TYPE CONTRACT without a live microVM.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from blake3 import blake3 as _blake3

from verdict.tools.base import ToolWrapper
from verdict.tools.vol3.psscan import VolPsscanArgs, VolPsscanWrapper
from verdict.schemas.tool_output import Artifact, ToolOutput


# ---------------------------------------------------------------------------
# W1.E.1 — wrapper identity and inheritance contract
# ---------------------------------------------------------------------------


def test_psscan_is_tool_wrapper():
    """VolPsscanWrapper must extend ToolWrapper (§3.1 framework contract)."""
    wrapper = VolPsscanWrapper()
    assert isinstance(wrapper, ToolWrapper)


def test_psscan_tool_name():
    """tool_name must identify the Volatility plugin unambiguously."""
    wrapper = VolPsscanWrapper()
    assert wrapper.tool_name == "vol3.windows.psscan"


def test_psscan_version_string():
    """_get_tool_version() must return a non-empty string (stub)."""
    wrapper = VolPsscanWrapper()
    version = wrapper._get_tool_version()
    assert isinstance(version, str)
    assert len(version) > 0
    # Stub pinning: vol3 2.x series expected per rootfs in W1.A.3.c
    assert version.startswith("vol3")


# ---------------------------------------------------------------------------
# W1.E.1 — VolPsscanArgs model
# ---------------------------------------------------------------------------


def test_psscan_args_minimal():
    """VolPsscanArgs must be constructable with just an evidence_path."""
    args = VolPsscanArgs(evidence_path=Path("/evidence/mem.raw"))
    assert args.evidence_path == Path("/evidence/mem.raw")
    assert args.plugin == "windows.psscan"  # canonical plugin name


def test_psscan_args_plugin_locked():
    """The plugin field must always be 'windows.psscan' — it is not user-configurable."""
    args = VolPsscanArgs(evidence_path=Path("/evidence/mem.raw"))
    assert args.plugin == "windows.psscan"


def test_psscan_args_to_dict_contains_plugin():
    """args.model_dump() must include 'plugin' so invocation_hash covers it."""
    args = VolPsscanArgs(evidence_path=Path("/evidence/mem.raw"))
    d = args.model_dump()
    assert "plugin" in d
    assert d["plugin"] == "windows.psscan"


def test_psscan_args_evidence_path_is_path():
    """evidence_path must be a Path (not a string) so wrappers handle it uniformly."""
    args = VolPsscanArgs(evidence_path=Path("/evidence/mem.raw"))
    assert isinstance(args.evidence_path, Path)


# ---------------------------------------------------------------------------
# W1.E.1 — invocation_hash computed from psscan args
# ---------------------------------------------------------------------------


def test_psscan_pre_run_hash():
    """pre_run() with psscan args must produce the expected invocation_hash."""
    wrapper = VolPsscanWrapper()
    evidence_hash = "d" * 64
    args_dict = {"plugin": "windows.psscan", "evidence_path": "/evidence/mem.raw"}

    expected = _blake3(
        (
            "vol3.windows.psscan"
            + wrapper._get_tool_version()
            + json.dumps(args_dict, sort_keys=True)
            + evidence_hash
        ).encode()
    ).hexdigest()

    result = wrapper.pre_run(args=args_dict, evidence_hash=evidence_hash)
    assert result == expected


# ---------------------------------------------------------------------------
# W1.E.1 — DKOM cross-validation surface
# ---------------------------------------------------------------------------


def test_psscan_has_pid_set_method():
    """VolPsscanWrapper must expose pid_set(output) for DKOM cross-validation.

    Per CLAUDE.md §7 / BUILD_PLAN W1.E.1:
        set(psscan_pids) - set(pslist_pids) ≠ ∅  →  T1014 hypothesis

    pid_set() extracts PIDs from a ToolOutput so the planner can compute
    the DKOM divergence without parsing the raw stdout again.
    """
    wrapper = VolPsscanWrapper()
    assert callable(getattr(wrapper, "pid_set", None)), (
        "VolPsscanWrapper must expose pid_set(output: ToolOutput) -> frozenset[int]"
    )


def test_pid_set_from_tool_output():
    """pid_set() must extract PIDs from parsed_artifacts of type 'process'."""
    # Build a synthetic ToolOutput with known PIDs (no microVM needed)
    evidence_hash = "e" * 64
    tool_version = "vol3 2.10.0"
    tool_name = "vol3.windows.psscan"
    args = {"plugin": "windows.psscan", "evidence_path": "/evidence/mem.raw"}
    args_json = json.dumps(args, sort_keys=True)
    inv_hash = _blake3(
        (tool_name + tool_version + args_json + evidence_hash).encode()
    ).hexdigest()

    import hashlib

    stdout_bytes = b"synthetic psscan output"
    stdout_sha256 = hashlib.sha256(stdout_bytes).hexdigest()

    artifacts = [
        Artifact(
            artifact_id="proc_4",
            evidence_path=Path("/evidence/mem.raw"),
            artifact_type="process",
            raw_fields={"PID": 4, "ImageFileName": "System", "PPID": 0},
        ),
        Artifact(
            artifact_id="proc_816",
            evidence_path=Path("/evidence/mem.raw"),
            artifact_type="process",
            raw_fields={"PID": 816, "ImageFileName": "svchost.exe", "PPID": 680},
        ),
        Artifact(
            artifact_id="proc_hidden_999",
            evidence_path=Path("/evidence/mem.raw"),
            artifact_type="process",
            raw_fields={"PID": 999, "ImageFileName": "evil.exe", "PPID": 4},
        ),
        # Non-process artifact — must be excluded from pid_set
        Artifact(
            artifact_id="conn_001",
            evidence_path=Path("/evidence/mem.raw"),
            artifact_type="network_connection",
            raw_fields={"LocalAddr": "10.0.0.1", "RemoteAddr": "1.2.3.4"},
        ),
    ]

    output = ToolOutput(
        tool_name=tool_name,
        tool_version=tool_version,
        args=args,
        evidence_hash=evidence_hash,
        invocation_hash=inv_hash,
        stdout_sha256=stdout_sha256,
        parsed_artifacts=artifacts,
    )

    wrapper = VolPsscanWrapper()
    pids = wrapper.pid_set(output)

    assert isinstance(pids, frozenset)
    assert pids == frozenset({4, 816, 999}), (
        f"Expected {{4, 816, 999}}, got {pids}"
    )


# ---------------------------------------------------------------------------
# W1.E.1 — _execute raises NotImplementedError until W2.B
# ---------------------------------------------------------------------------


def test_psscan_execute_raises_not_implemented():
    """_execute() must raise NotImplementedError until W2.B wires the microVM."""
    wrapper = VolPsscanWrapper()
    with pytest.raises(NotImplementedError, match="W2.B"):
        wrapper._execute(
            args={"plugin": "windows.psscan", "evidence_path": "/evidence/mem.raw"},
            evidence_path=Path("/evidence/mem.raw"),
            work_dir=Path("/work/case_001"),
        )
