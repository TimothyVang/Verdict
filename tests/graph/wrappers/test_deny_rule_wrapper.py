"""Tests for DenyRuleWrapper — W2.C.1.

RED phase (W2.C.1.a): import fails until verdict/graph/wrappers/deny_rule.py
is implemented.

DenyRuleWrapper is Layer 2 of the three-layer immutability defense (ARCHITECTURE.md §3).
It fires in ALL three modes (cloud, airgap, dual) regardless of model, and validates
typed tool args against a deny-rule list BEFORE any microsandbox spawn or execution.

The key rule: writes to /evidence/ are architecturally forbidden (CLAUDE.md §3.1).
Any tool invocation that would write to /evidence/ is denied with
DenyRuleViolation before reaching the ToolExecutor.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from verdict.graph.wrappers.deny_rule import DenyRuleViolation, DenyRuleWrapper


# ---------------------------------------------------------------------------
# Minimal concrete ToolExecutor stub (not a mock — a real callable that
# records whether it was called, used to assert the deny gate fires before
# execution).  Per §3.10: this is a real collaborator subclass, not a Mock.
# ---------------------------------------------------------------------------


class _RecordingExecutor:
    """Real callable that records its invocations; raises if unexpectedly called."""

    def __init__(self, *, should_be_called: bool = True):
        self._should_be_called = should_be_called
        self.call_count = 0
        self.last_call: tuple | None = None

    def __call__(self, tool_name: str, args: dict) -> dict:
        if not self._should_be_called:
            raise AssertionError(
                f"Executor should NOT have been called but was called with "
                f"tool_name={tool_name!r}, args={args!r}"
            )
        self.call_count += 1
        self.last_call = (tool_name, args)
        return {"status": "ok", "tool_name": tool_name}


# ---------------------------------------------------------------------------
# W2.C.1.a assertions — the deny gate fires in all three modes
# ---------------------------------------------------------------------------


class TestDenyRuleWrapperBlocksEvidenceWrites:
    """W2.C.1.a — Failing test: test_blocks_evidence_writes_in_all_modes.

    Assertion: DenyRuleWrapper raises DenyRuleViolation when args contain any
    path under /evidence/ as a write target, in each of the three modes.
    """

    MODES = ("cloud", "airgap", "dual")

    @pytest.mark.parametrize("mode", MODES)
    def test_blocks_output_path_under_evidence(self, mode: str) -> None:
        """Any tool arg with output_path under /evidence/ is denied."""
        executor = _RecordingExecutor(should_be_called=False)
        wrapper = DenyRuleWrapper(executor=executor, mode=mode)

        with pytest.raises(DenyRuleViolation) as exc_info:
            wrapper.run(
                tool_name="vol3.windows.pslist",
                args={"output_path": "/evidence/out.txt"},
            )

        assert "/evidence/" in str(exc_info.value).lower() or "evidence" in str(
            exc_info.value
        ).lower()
        assert executor.call_count == 0, "Executor must not be called when rule fires"

    @pytest.mark.parametrize("mode", MODES)
    def test_blocks_write_to_path_under_evidence(self, mode: str) -> None:
        """A write_path arg pointing under /evidence/ is denied."""
        executor = _RecordingExecutor(should_be_called=False)
        wrapper = DenyRuleWrapper(executor=executor, mode=mode)

        with pytest.raises(DenyRuleViolation):
            wrapper.run(
                tool_name="some.tool",
                args={"write_path": "/evidence/subdir/file.bin"},
            )

        assert executor.call_count == 0

    @pytest.mark.parametrize("mode", MODES)
    def test_blocks_evidence_path_variation(self, mode: str) -> None:
        """Nested paths under /evidence/ are also blocked."""
        executor = _RecordingExecutor(should_be_called=False)
        wrapper = DenyRuleWrapper(executor=executor, mode=mode)

        with pytest.raises(DenyRuleViolation):
            wrapper.run(
                tool_name="mftecmd",
                args={"output_dir": "/evidence/subdir/"},
            )

        assert executor.call_count == 0

    @pytest.mark.parametrize("mode", MODES)
    def test_allows_reads_from_evidence(self, mode: str) -> None:
        """Read-only access to /evidence/ is permitted — only writes are denied."""
        executor = _RecordingExecutor(should_be_called=True)
        wrapper = DenyRuleWrapper(executor=executor, mode=mode)

        result = wrapper.run(
            tool_name="vol3.windows.pslist",
            args={"memory_image": "/evidence/memory.raw"},
        )

        assert executor.call_count == 1
        assert result["status"] == "ok"

    @pytest.mark.parametrize("mode", MODES)
    def test_allows_work_dir_writes(self, mode: str) -> None:
        """Writes to /work/ (not /evidence/) pass through to executor."""
        executor = _RecordingExecutor(should_be_called=True)
        wrapper = DenyRuleWrapper(executor=executor, mode=mode)

        result = wrapper.run(
            tool_name="vol3.windows.pslist",
            args={"output_path": "/work/output.csv"},
        )

        assert executor.call_count == 1
        assert result["status"] == "ok"


class TestDenyRuleWrapperViolationDetails:
    """The DenyRuleViolation carries structured metadata for the ledger."""

    def test_violation_records_tool_name(self) -> None:
        """DenyRuleViolation.tool_name is set from the attempted call."""
        executor = _RecordingExecutor(should_be_called=False)
        wrapper = DenyRuleWrapper(executor=executor, mode="cloud")

        with pytest.raises(DenyRuleViolation) as exc_info:
            wrapper.run(
                tool_name="hayabusa.csv_timeline",
                args={"output_path": "/evidence/result.csv"},
            )

        assert exc_info.value.tool_name == "hayabusa.csv_timeline"

    def test_violation_records_violated_arg(self) -> None:
        """DenyRuleViolation.violated_arg names the offending argument key."""
        executor = _RecordingExecutor(should_be_called=False)
        wrapper = DenyRuleWrapper(executor=executor, mode="cloud")

        with pytest.raises(DenyRuleViolation) as exc_info:
            wrapper.run(
                tool_name="plaso.extract",
                args={"write_path": "/evidence/case.plaso"},
            )

        assert exc_info.value.violated_arg == "write_path"

    def test_violation_records_denied_value(self) -> None:
        """DenyRuleViolation.denied_value holds the offending path string."""
        executor = _RecordingExecutor(should_be_called=False)
        wrapper = DenyRuleWrapper(executor=executor, mode="airgap")

        with pytest.raises(DenyRuleViolation) as exc_info:
            wrapper.run(
                tool_name="vol3.windows.malfind",
                args={"output_path": "/evidence/malfind_out/"},
            )

        assert "/evidence/" in exc_info.value.denied_value

    def test_violation_records_mode(self) -> None:
        """DenyRuleViolation.mode matches the mode the wrapper was created with."""
        executor = _RecordingExecutor(should_be_called=False)
        wrapper = DenyRuleWrapper(executor=executor, mode="dual")

        with pytest.raises(DenyRuleViolation) as exc_info:
            wrapper.run(
                tool_name="recmd",
                args={"output_path": "/evidence/registry_out.csv"},
            )

        assert exc_info.value.mode == "dual"

    def test_violation_is_exception(self) -> None:
        """DenyRuleViolation must be an exception (raises, not a return value)."""
        assert issubclass(DenyRuleViolation, Exception)


class TestDenyRuleWrapperPassThrough:
    """Non-denied calls are passed through to the executor unchanged."""

    def test_passes_tool_name_unchanged(self) -> None:
        executor = _RecordingExecutor(should_be_called=True)
        wrapper = DenyRuleWrapper(executor=executor, mode="cloud")

        wrapper.run(tool_name="vol3.windows.psscan", args={"pid": 1234})

        assert executor.last_call is not None
        assert executor.last_call[0] == "vol3.windows.psscan"

    def test_passes_args_unchanged(self) -> None:
        executor = _RecordingExecutor(should_be_called=True)
        wrapper = DenyRuleWrapper(executor=executor, mode="airgap")

        args = {"memory_image": "/evidence/mem.raw", "output_dir": "/work/out/"}
        wrapper.run(tool_name="vol3.windows.malfind", args=args)

        assert executor.last_call is not None
        assert executor.last_call[1] == args

    def test_returns_executor_result(self) -> None:
        """DenyRuleWrapper returns whatever the executor returns (transparent)."""
        executor = _RecordingExecutor(should_be_called=True)
        wrapper = DenyRuleWrapper(executor=executor, mode="dual")

        result = wrapper.run(tool_name="mmls", args={"image": "/evidence/disk.E01"})

        assert result == {"status": "ok", "tool_name": "mmls"}


class TestDenyRuleWrapperPathEdgeCases:
    """Edge cases in path matching — canonicalization, relative paths, symlinks."""

    def test_blocks_path_object_output_path(self) -> None:
        """Path objects (not just strings) as output paths are also denied."""
        executor = _RecordingExecutor(should_be_called=False)
        wrapper = DenyRuleWrapper(executor=executor, mode="cloud")

        with pytest.raises(DenyRuleViolation):
            wrapper.run(
                tool_name="vol3.windows.cmdline",
                args={"output_path": Path("/evidence/cmdline.txt")},
            )

        assert executor.call_count == 0

    def test_blocks_string_with_evidence_prefix(self) -> None:
        """Strings that resolve to /evidence/... are denied regardless of trailing slash."""
        executor = _RecordingExecutor(should_be_called=False)
        wrapper = DenyRuleWrapper(executor=executor, mode="cloud")

        with pytest.raises(DenyRuleViolation):
            wrapper.run(
                tool_name="bulk_extractor",
                args={"output_dir": "/evidence"},
            )

        assert executor.call_count == 0

    def test_does_not_block_evidence_in_input_field_names(self) -> None:
        """A field named 'evidence_path' pointing to /evidence/ is a read — allowed."""
        executor = _RecordingExecutor(should_be_called=True)
        wrapper = DenyRuleWrapper(executor=executor, mode="cloud")

        result = wrapper.run(
            tool_name="vol3.windows.psscan",
            args={"evidence_path": "/evidence/disk.E01"},
        )

        # read-only field names allowed through
        assert executor.call_count == 1
        assert result["status"] == "ok"
