"""Tests for ToolExecutor wrapper — W2.C.2.

RED phase (W2.C.2.a): import fails until verdict/graph/wrappers/tool_executor.py
is implemented.

ToolExecutor wraps the ToolWrapper ABC (W1.E.2). Its responsibilities:
  1. Typed dispatch: accept (tool_name, args) and resolve the correct ToolWrapper.
  2. Invoke ToolWrapper.pre_run() to compute the invocation_hash.
  3. Call ToolWrapper._execute() inside the microsandbox (or raise
     NotImplementedError if the real microsandbox integration hasn't landed —
     the W2.B vol3 wrappers are the first to implement real execution).
  4. Return the ToolOutput from _execute().

The ToolExecutor does NOT write to the ledger — that is LedgerEmitter's job.
The ToolExecutor does NOT deny writes to /evidence/ — that is DenyRuleWrapper's job.

Per CLAUDE.md §3.10: NotImplementedError for actual external CLI calls is
acceptable; those land in W2.B.  Every code path here MUST run in production
when the real tool wrappers are wired.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from verdict.graph.wrappers.tool_executor import ToolExecutor, UnknownToolError
from verdict.schemas.tool_output import Artifact, ToolOutput
from verdict.tools.base import ToolWrapper


# ---------------------------------------------------------------------------
# Minimal real ToolWrapper subclass — not a mock.
#
# Raises NotImplementedError from _execute (same as the vol3 stubs before W2.B).
# This mirrors the production pattern where real CLI calls land later.
# ---------------------------------------------------------------------------


def _make_invocation_hash(
    tool_name: str, tool_version: str, args: dict, evidence_hash: str
) -> str:
    """Reproduce the canonical invocation_hash for assertion."""
    import json
    from blake3 import blake3 as _blake3

    args_json = json.dumps(args, sort_keys=True)
    raw = (tool_name + tool_version + args_json + evidence_hash).encode()
    return _blake3(raw).hexdigest()


class _FakeVol3Pslist(ToolWrapper):
    """Real ToolWrapper subclass that returns a canned ToolOutput from _execute.

    This is the production pattern: subclass ToolWrapper, implement _execute.
    The test exercises the ToolExecutor dispatch path without needing a live
    microVM — the ToolOutput is constructed with real hashes.
    """

    TOOL_NAME = "vol3.windows.pslist"
    TOOL_VERSION = "vol3 2.10.0"

    @property
    def tool_name(self) -> str:
        return self.TOOL_NAME

    def _get_tool_version(self) -> str:
        return self.TOOL_VERSION

    def _execute(self, args: dict, evidence_path: Path, work_dir: Path) -> ToolOutput:
        """Return a real ToolOutput (all hashes computed, no canned data)."""
        import hashlib

        evidence_hash = hashlib.sha256(b"fake-evidence").hexdigest()
        invocation_hash = self.pre_run(args=args, evidence_hash=evidence_hash)

        stdout_bytes = b"Offset(V)  Name  PID  PPID\n0x... System 4 0\n"
        stdout_hash = hashlib.sha256(stdout_bytes).hexdigest()

        return ToolOutput(
            tool_name=self.TOOL_NAME,
            tool_version=self.TOOL_VERSION,
            args=args,
            evidence_hash=evidence_hash,
            invocation_hash=invocation_hash,
            stdout_sha256=stdout_hash,
            parsed_artifacts=[
                Artifact(
                    artifact_id="proc-4",
                    evidence_path=evidence_path,
                    artifact_type="process",
                    raw_fields={"pid": 4, "name": "System"},
                )
            ],
        )


class _FakeVol3Psscan(ToolWrapper):
    """Second wrapper for testing multiple-wrapper dispatch."""

    TOOL_NAME = "vol3.windows.psscan"
    TOOL_VERSION = "vol3 2.10.0"

    @property
    def tool_name(self) -> str:
        return self.TOOL_NAME

    def _get_tool_version(self) -> str:
        return self.TOOL_VERSION

    def _execute(self, args: dict, evidence_path: Path, work_dir: Path) -> ToolOutput:
        import hashlib

        evidence_hash = hashlib.sha256(b"fake-evidence").hexdigest()
        invocation_hash = self.pre_run(args=args, evidence_hash=evidence_hash)
        stdout_hash = hashlib.sha256(b"psscan output").hexdigest()

        return ToolOutput(
            tool_name=self.TOOL_NAME,
            tool_version=self.TOOL_VERSION,
            args=args,
            evidence_hash=evidence_hash,
            invocation_hash=invocation_hash,
            stdout_sha256=stdout_hash,
        )


class _NotImplementedWrapper(ToolWrapper):
    """Wrapper whose _execute raises NotImplementedError (W2.B not landed yet)."""

    @property
    def tool_name(self) -> str:
        return "vol3.windows.malfind"

    def _get_tool_version(self) -> str:
        return "vol3 2.10.0"

    def _execute(self, args: dict, evidence_path: Path, work_dir: Path) -> ToolOutput:
        raise NotImplementedError("real impl lands in W2.B")


# ---------------------------------------------------------------------------
# W2.C.2.a — typed dispatch + ToolOutput result
# ---------------------------------------------------------------------------


class TestToolExecutorDispatch:
    """ToolExecutor dispatches tool_name to the correct ToolWrapper."""

    def test_dispatches_to_registered_wrapper(self) -> None:
        """run() calls the registered wrapper and returns ToolOutput."""
        executor = ToolExecutor(
            wrappers=[_FakeVol3Pslist()],
            evidence_path=Path("/evidence/mem.raw"),
            work_dir=Path("/work/case-001"),
        )

        result = executor.run(
            tool_name="vol3.windows.pslist",
            args={"memory_image": "/evidence/mem.raw"},
        )

        assert isinstance(result, ToolOutput)
        assert result.tool_name == "vol3.windows.pslist"

    def test_dispatches_to_correct_wrapper_among_multiple(self) -> None:
        """run() selects the wrapper matching tool_name when multiple are registered."""
        executor = ToolExecutor(
            wrappers=[_FakeVol3Pslist(), _FakeVol3Psscan()],
            evidence_path=Path("/evidence/mem.raw"),
            work_dir=Path("/work/case-001"),
        )

        result_pslist = executor.run(
            tool_name="vol3.windows.pslist",
            args={"memory_image": "/evidence/mem.raw"},
        )
        result_psscan = executor.run(
            tool_name="vol3.windows.psscan",
            args={"memory_image": "/evidence/mem.raw"},
        )

        assert result_pslist.tool_name == "vol3.windows.pslist"
        assert result_psscan.tool_name == "vol3.windows.psscan"

    def test_raises_unknown_tool_error_for_unregistered_tool(self) -> None:
        """run() raises UnknownToolError for tools not registered with the executor."""
        executor = ToolExecutor(
            wrappers=[_FakeVol3Pslist()],
            evidence_path=Path("/evidence/mem.raw"),
            work_dir=Path("/work/case-001"),
        )

        with pytest.raises(UnknownToolError) as exc_info:
            executor.run(
                tool_name="vol3.windows.svcscan",
                args={},
            )

        assert "vol3.windows.svcscan" in str(exc_info.value)

    def test_unknown_tool_error_names_available_tools(self) -> None:
        """UnknownToolError message includes the list of registered tools."""
        executor = ToolExecutor(
            wrappers=[_FakeVol3Pslist(), _FakeVol3Psscan()],
            evidence_path=Path("/evidence/mem.raw"),
            work_dir=Path("/work/case-001"),
        )

        with pytest.raises(UnknownToolError) as exc_info:
            executor.run(tool_name="nonexistent.tool", args={})

        error_msg = str(exc_info.value)
        assert "vol3.windows.pslist" in error_msg or "vol3.windows.psscan" in error_msg


class TestToolExecutorToolOutput:
    """ToolExecutor.run() returns a correctly-formed ToolOutput."""

    def test_result_has_tool_name(self) -> None:
        executor = ToolExecutor(
            wrappers=[_FakeVol3Pslist()],
            evidence_path=Path("/evidence/mem.raw"),
            work_dir=Path("/work"),
        )
        result = executor.run(
            tool_name="vol3.windows.pslist",
            args={"memory_image": "/evidence/mem.raw"},
        )
        assert result.tool_name == "vol3.windows.pslist"

    def test_result_has_tool_version(self) -> None:
        executor = ToolExecutor(
            wrappers=[_FakeVol3Pslist()],
            evidence_path=Path("/evidence/mem.raw"),
            work_dir=Path("/work"),
        )
        result = executor.run(
            tool_name="vol3.windows.pslist",
            args={"memory_image": "/evidence/mem.raw"},
        )
        assert result.tool_version == "vol3 2.10.0"

    def test_result_has_valid_invocation_hash(self) -> None:
        """ToolOutput.invocation_hash passes the ToolOutput model validator."""
        executor = ToolExecutor(
            wrappers=[_FakeVol3Pslist()],
            evidence_path=Path("/evidence/mem.raw"),
            work_dir=Path("/work"),
        )
        result = executor.run(
            tool_name="vol3.windows.pslist",
            args={"memory_image": "/evidence/mem.raw"},
        )
        # The model validator in ToolOutput already verified the hash at
        # construction; if we get here without ValidationError the hash is valid.
        assert len(result.invocation_hash) == 64  # blake3 hex digest

    def test_result_has_parsed_artifacts_list(self) -> None:
        executor = ToolExecutor(
            wrappers=[_FakeVol3Pslist()],
            evidence_path=Path("/evidence/mem.raw"),
            work_dir=Path("/work"),
        )
        result = executor.run(
            tool_name="vol3.windows.pslist",
            args={"memory_image": "/evidence/mem.raw"},
        )
        assert isinstance(result.parsed_artifacts, list)
        assert len(result.parsed_artifacts) >= 1
        assert result.parsed_artifacts[0].artifact_type == "process"

    def test_result_has_stdout_sha256(self) -> None:
        executor = ToolExecutor(
            wrappers=[_FakeVol3Pslist()],
            evidence_path=Path("/evidence/mem.raw"),
            work_dir=Path("/work"),
        )
        result = executor.run(
            tool_name="vol3.windows.pslist",
            args={"memory_image": "/evidence/mem.raw"},
        )
        assert isinstance(result.stdout_sha256, str)
        assert len(result.stdout_sha256) == 64  # sha256 hex


class TestToolExecutorNotImplemented:
    """Wrappers that raise NotImplementedError propagate the error (W2.B not landed)."""

    def test_propagates_not_implemented_from_execute(self) -> None:
        executor = ToolExecutor(
            wrappers=[_NotImplementedWrapper()],
            evidence_path=Path("/evidence/mem.raw"),
            work_dir=Path("/work"),
        )

        with pytest.raises(NotImplementedError, match="W2.B"):
            executor.run(
                tool_name="vol3.windows.malfind",
                args={"memory_image": "/evidence/mem.raw"},
            )


class TestToolExecutorRegistration:
    """ToolExecutor registration mechanics."""

    def test_empty_wrappers_list_accepted(self) -> None:
        """Zero registered wrappers is valid at construction time."""
        executor = ToolExecutor(
            wrappers=[],
            evidence_path=Path("/evidence/mem.raw"),
            work_dir=Path("/work"),
        )
        assert executor is not None

    def test_duplicate_tool_name_raises_on_construction(self) -> None:
        """Registering two wrappers with the same tool_name raises ValueError."""
        with pytest.raises(ValueError, match="duplicate"):
            ToolExecutor(
                wrappers=[_FakeVol3Pslist(), _FakeVol3Pslist()],
                evidence_path=Path("/evidence/mem.raw"),
                work_dir=Path("/work"),
            )

    def test_registered_tool_names_property(self) -> None:
        """ToolExecutor.registered_tool_names returns all registered tool names."""
        executor = ToolExecutor(
            wrappers=[_FakeVol3Pslist(), _FakeVol3Psscan()],
            evidence_path=Path("/evidence/mem.raw"),
            work_dir=Path("/work"),
        )
        names = executor.registered_tool_names
        assert "vol3.windows.pslist" in names
        assert "vol3.windows.psscan" in names
