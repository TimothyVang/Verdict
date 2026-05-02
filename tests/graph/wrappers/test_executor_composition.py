"""Tests for the composed DenyRuleWrapper → ToolExecutor → LedgerEmitter chain — W2.C.4.

RED phase (W2.C.4.a): import fails until verdict/graph/topology.py provides
build_executor_work().

This test exercises the full three-wrapper composition end-to-end:
  1. A write to /evidence/ is denied by DenyRuleWrapper before reaching the
     other wrappers — no executor call, no ledger entry.
  2. A valid tool call dispatches through ToolExecutor, writes a LedgerEntry,
     and returns ToolOutput.
  3. An unknown tool raises UnknownToolError (from ToolExecutor, not swallowed
     by DenyRuleWrapper or LedgerEmitter).
  4. The composition is mode-aware: the same deny behavior fires in all three
     modes.

The factory function under test is:
    verdict.graph.topology.build_executor_work(
        wrappers, ledger_writer, hmac_provider, case_id, mode, ...
    ) -> LedgerEmitter

Calling the returned LedgerEmitter directly exercises the full chain because
LedgerEmitter wraps ToolExecutor which wraps DenyRuleWrapper (from the inside
out in terms of execution order — DenyRuleWrapper fires first).

Composition order clarification (ARCHITECTURE.md §2 + CLAUDE.md §4):
  - DenyRuleWrapper composes around ToolExecutor as its executor callable.
  - LedgerEmitter composes around DenyRuleWrapper as its executor callable.
  - So the call chain is:
      LedgerEmitter.run() → DenyRuleWrapper.run() → ToolExecutor.run()
    and DenyRuleViolation short-circuits before any execution or ledger write.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from verdict.graph.topology import build_executor_work
from verdict.graph.wrappers.deny_rule import DenyRuleViolation
from verdict.graph.wrappers.tool_executor import UnknownToolError
from verdict.ledger.hmac_key import get_hmac_key_provider_from_bytes
from verdict.ledger.writer import LedgerWriter
from verdict.schemas.tool_output import Artifact, ToolOutput
from verdict.tools.base import ToolWrapper


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_tool_output(tool_name: str = "vol3.windows.pslist") -> ToolOutput:
    """Build a real ToolOutput with valid hashes."""
    import json
    from blake3 import blake3 as _b3

    tool_version = "vol3 2.10.0"
    args: dict = {"memory_image": "/evidence/mem.raw"}
    evidence_hash = hashlib.sha256(b"test-evidence").hexdigest()
    args_json = json.dumps(args, sort_keys=True)
    invocation_hash = _b3((tool_name + tool_version + args_json + evidence_hash).encode()).hexdigest()
    stdout_hash = hashlib.sha256(b"stdout").hexdigest()

    return ToolOutput(
        tool_name=tool_name,
        tool_version=tool_version,
        args=args,
        evidence_hash=evidence_hash,
        invocation_hash=invocation_hash,
        stdout_sha256=stdout_hash,
    )


class _RealPslistWrapper(ToolWrapper):
    """Real ToolWrapper that returns a constructed ToolOutput."""

    @property
    def tool_name(self) -> str:
        return "vol3.windows.pslist"

    def _get_tool_version(self) -> str:
        return "vol3 2.10.0"

    def _execute(self, args: dict, evidence_path: Path, work_dir: Path) -> ToolOutput:
        import json
        from blake3 import blake3 as _b3

        tool_version = "vol3 2.10.0"
        evidence_hash = hashlib.sha256(b"test-evidence").hexdigest()
        args_json = json.dumps(args, sort_keys=True)
        invocation_hash = _b3(
            (self.tool_name + tool_version + args_json + evidence_hash).encode()
        ).hexdigest()
        stdout_hash = hashlib.sha256(b"pslist output").hexdigest()

        return ToolOutput(
            tool_name=self.tool_name,
            tool_version=tool_version,
            args=args,
            evidence_hash=evidence_hash,
            invocation_hash=invocation_hash,
            stdout_sha256=stdout_hash,
            parsed_artifacts=[
                Artifact(
                    artifact_id="proc-4",
                    evidence_path=evidence_path,
                    artifact_type="process",
                    raw_fields={"pid": 4},
                )
            ],
        )


def _make_chain(tmp_path: Path, mode: str = "cloud"):
    """Build a real composed chain from build_executor_work()."""
    key_bytes = os.urandom(32)
    hmac_provider = get_hmac_key_provider_from_bytes(key_bytes)
    ledger_path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(ledger_path=ledger_path, hmac_provider=hmac_provider)

    return build_executor_work(
        wrappers=[_RealPslistWrapper()],
        evidence_path=Path("/evidence/mem.raw"),
        work_dir=Path("/work"),
        ledger_writer=writer,
        hmac_provider=hmac_provider,
        case_id="case-001",
        mode=mode,
        verifier_strategy="CloudSelfConsistency",
        langfuse_trace_id="trace-001",
        langfuse_root_span_id="span-001",
        langgraph_thread_id="case-001",
        langgraph_checkpoint_id="ckpt-001",
    ), ledger_path


# ---------------------------------------------------------------------------
# W2.C.4.a — end-to-end through DenyRuleWrapper → ToolExecutor → LedgerEmitter
# ---------------------------------------------------------------------------


class TestCompositionEndToEnd:
    """Full chain: deny → execute → emit."""

    MODES = ["cloud", "airgap", "dual"]

    @pytest.mark.parametrize("mode", MODES)
    def test_deny_fires_before_executor_and_ledger(
        self, tmp_path: Path, mode: str
    ) -> None:
        """DenyRuleViolation propagates from the composed chain for /evidence/ writes.

        No ledger entry must be written when the deny rule fires.
        """
        chain, ledger_path = _make_chain(tmp_path, mode=mode)

        with pytest.raises(DenyRuleViolation):
            chain("vol3.windows.pslist", {"output_path": "/evidence/out.txt"})

        # No ledger entry written
        if ledger_path.exists():
            lines = [ln for ln in ledger_path.read_bytes().split(b"\n") if ln.strip()]
            assert len(lines) == 0, "No ledger entry should exist when deny fires"

    def test_valid_call_returns_tool_output(self, tmp_path: Path) -> None:
        """Valid tool call through composition returns ToolOutput."""
        chain, _ = _make_chain(tmp_path)

        result = chain(
            "vol3.windows.pslist",
            {"memory_image": "/evidence/mem.raw"},
        )

        assert isinstance(result, ToolOutput)
        assert result.tool_name == "vol3.windows.pslist"

    def test_valid_call_writes_ledger_entry(self, tmp_path: Path) -> None:
        """Valid tool call through composition writes exactly one ledger entry."""
        chain, ledger_path = _make_chain(tmp_path)

        chain("vol3.windows.pslist", {"memory_image": "/evidence/mem.raw"})

        lines = [ln for ln in ledger_path.read_bytes().split(b"\n") if ln.strip()]
        assert len(lines) == 1

    def test_unknown_tool_raises_unknown_tool_error(self, tmp_path: Path) -> None:
        """UnknownToolError propagates through the composition for unregistered tools."""
        chain, ledger_path = _make_chain(tmp_path)

        with pytest.raises(UnknownToolError):
            chain("vol3.windows.svcscan", {"memory_image": "/evidence/mem.raw"})

        # No ledger entry written for unknown tools either
        if ledger_path.exists():
            lines = [ln for ln in ledger_path.read_bytes().split(b"\n") if ln.strip()]
            assert len(lines) == 0

    def test_two_valid_calls_chain_ledger_entries(self, tmp_path: Path) -> None:
        """Two calls produce two chained ledger entries."""
        chain, ledger_path = _make_chain(tmp_path)

        chain("vol3.windows.pslist", {"memory_image": "/evidence/mem.raw"})
        chain("vol3.windows.pslist", {"memory_image": "/evidence/mem.raw"})

        lines = [ln for ln in ledger_path.read_bytes().split(b"\n") if ln.strip()]
        assert len(lines) == 2

    def test_deny_then_valid_does_not_corrupt_ledger(self, tmp_path: Path) -> None:
        """A denied call followed by a valid call produces one clean ledger entry."""
        chain, ledger_path = _make_chain(tmp_path)

        # First call denied
        with pytest.raises(DenyRuleViolation):
            chain("vol3.windows.pslist", {"output_path": "/evidence/bad.txt"})

        # Second call valid
        chain("vol3.windows.pslist", {"memory_image": "/evidence/mem.raw"})

        lines = [ln for ln in ledger_path.read_bytes().split(b"\n") if ln.strip()]
        assert len(lines) == 1


class TestBuildExecutorWorkFactory:
    """build_executor_work() returns a callable with the right interface."""

    def test_returns_callable(self, tmp_path: Path) -> None:
        """build_executor_work() returns a callable."""
        chain, _ = _make_chain(tmp_path)
        assert callable(chain)

    def test_returns_ledger_emitter(self, tmp_path: Path) -> None:
        """build_executor_work() returns a LedgerEmitter instance."""
        from verdict.graph.wrappers.ledger_emitter import LedgerEmitter

        chain, _ = _make_chain(tmp_path)
        assert isinstance(chain, LedgerEmitter)

    def test_factory_accepts_empty_wrappers(self, tmp_path: Path) -> None:
        """build_executor_work() with zero wrappers is valid at construction."""
        key_bytes = os.urandom(32)
        hmac_provider = get_hmac_key_provider_from_bytes(key_bytes)
        ledger_path = tmp_path / "ledger.jsonl"
        writer = LedgerWriter(ledger_path=ledger_path, hmac_provider=hmac_provider)

        chain = build_executor_work(
            wrappers=[],
            evidence_path=Path("/evidence/mem.raw"),
            work_dir=Path("/work"),
            ledger_writer=writer,
            hmac_provider=hmac_provider,
            case_id="case-001",
            mode="airgap",
            verifier_strategy="AirGapCrossEngine",
            langfuse_trace_id="trace-001",
            langfuse_root_span_id="span-001",
            langgraph_thread_id="case-001",
            langgraph_checkpoint_id="ckpt-001",
        )
        assert chain is not None
