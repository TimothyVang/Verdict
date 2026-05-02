"""Tests for ToolWrapper abstract base class — W1.E.2.

RED phase: import will fail until verdict/tools/base.py is implemented.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from blake3 import blake3 as _blake3

from verdict.tools.base import ToolWrapper
from verdict.schemas.tool_output import ToolOutput


# ---------------------------------------------------------------------------
# Concrete minimal subclass (not a mock — a real subclass that raises
# NotImplementedError for _execute, mirroring a wrapper whose external CLI
# integration lands in W2.B).
# ---------------------------------------------------------------------------


class _MinimalWrapper(ToolWrapper):
    """Concrete subclass that raises NotImplementedError until W2.B."""

    @property
    def tool_name(self) -> str:
        return "vol3.windows.test_tool"

    def _get_tool_version(self) -> str:  # noqa: D401
        """Return a pinned version string (no subprocess needed for the base test)."""
        return "vol3 2.10.0"

    def _execute(self, args: dict, evidence_path: Path, work_dir: Path) -> ToolOutput:
        raise NotImplementedError("real implementation lands in W2.B")


# ---------------------------------------------------------------------------
# W1.E.2.a — failing test: ToolWrapper base records invocation_hash correctly
# ---------------------------------------------------------------------------


def test_base_records_invocation_hash():
    """ToolWrapper.pre_run() must compute and expose the canonical invocation_hash.

    Per CLAUDE.md §3.1:
        invocation_hash = blake3(tool_name + tool_version + args_json + evidence_hash)

    This test does NOT call _execute (which raises NotImplementedError); it
    exercises only the pre_run hook so the contract can be verified without a
    live microVM.
    """
    wrapper = _MinimalWrapper()

    args = {"plugin": "windows.psscan", "pid": None}
    evidence_hash = "a" * 64  # canonical SHA-256 hex placeholder
    tool_version = "vol3 2.10.0"
    tool_name = "vol3.windows.test_tool"

    # Reproduce the expected hash using the same algorithm
    args_json = json.dumps(args, sort_keys=True)
    raw = (tool_name + tool_version + args_json + evidence_hash).encode()
    expected_hash = _blake3(raw).hexdigest()

    result_hash = wrapper.pre_run(args=args, evidence_hash=evidence_hash)

    assert result_hash == expected_hash, (
        f"invocation_hash mismatch: got {result_hash!r}, expected {expected_hash!r}"
    )


def test_pre_run_is_deterministic():
    """Same inputs must always produce the same invocation_hash."""
    wrapper = _MinimalWrapper()
    args = {"plugin": "windows.psscan"}
    evidence_hash = "b" * 64

    h1 = wrapper.pre_run(args=args, evidence_hash=evidence_hash)
    h2 = wrapper.pre_run(args=args, evidence_hash=evidence_hash)
    assert h1 == h2


def test_pre_run_differs_on_different_args():
    """Different args must produce different invocation_hash values."""
    wrapper = _MinimalWrapper()
    evidence_hash = "c" * 64

    h1 = wrapper.pre_run(args={"pid": 1}, evidence_hash=evidence_hash)
    h2 = wrapper.pre_run(args={"pid": 2}, evidence_hash=evidence_hash)
    assert h1 != h2


def test_pre_run_differs_on_different_evidence():
    """Different evidence hashes must produce different invocation_hash values."""
    wrapper = _MinimalWrapper()
    args = {"plugin": "windows.psscan"}

    h1 = wrapper.pre_run(args=args, evidence_hash="a" * 64)
    h2 = wrapper.pre_run(args=args, evidence_hash="b" * 64)
    assert h1 != h2


def test_tool_wrapper_is_abstract():
    """ToolWrapper cannot be instantiated directly (it is abstract)."""
    with pytest.raises(TypeError):
        ToolWrapper()  # type: ignore[abstract]


def test_execute_raises_not_implemented():
    """Concrete stub wrapper raises NotImplementedError on _execute until W2.B."""
    wrapper = _MinimalWrapper()
    with pytest.raises(NotImplementedError, match="W2.B"):
        wrapper._execute(
            args={},
            evidence_path=Path("/evidence/test.E01"),
            work_dir=Path("/work/test"),
        )


def test_tool_name_property():
    """Subclass must expose tool_name as a string property."""
    wrapper = _MinimalWrapper()
    assert wrapper.tool_name == "vol3.windows.test_tool"
    assert isinstance(wrapper.tool_name, str)


def test_get_tool_version_returns_string():
    """_get_tool_version() must return a non-empty string."""
    wrapper = _MinimalWrapper()
    version = wrapper._get_tool_version()
    assert isinstance(version, str)
    assert len(version) > 0
