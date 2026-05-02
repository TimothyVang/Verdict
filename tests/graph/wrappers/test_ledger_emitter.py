"""Tests for LedgerEmitter wrapper — W2.C.3.

RED phase (W2.C.3.a): import fails until verdict/graph/wrappers/ledger_emitter.py
is implemented.

LedgerEmitter is the third wrapper in the executor_work composition:
    DenyRuleWrapper → ToolExecutor → LedgerEmitter

Responsibility: receive ToolOutput from the executor, write a LedgerEntry with
write + fsync + verify-readback (CLAUDE.md §9), and return both.

Tests in this module exercise:
  1. write + fsync + verify-readback — ledger.jsonl grows after run().
  2. Chain integrity — prev_entry_hash of N+1 entry == blake3 of entry N line.
  3. HMAC signature — present and verifiable with the same key.
  4. Bidirectional Langfuse cross-link — langfuse_trace_id in both payload and
     LedgerEntry fields.
  5. NIST SP 800-86 metadata — tool_version, rootfs_sha256, microsandbox_version
     present in the entry.
  6. Output files SHA-256 — forwarded from ToolOutput.output_files_sha256.
  7. Mode lock — mode_at_case_init locked to the value passed at construction.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from blake3 import blake3 as _blake3

from verdict.graph.wrappers.ledger_emitter import LedgerEmitter
from verdict.ledger.hmac_key import get_hmac_key_provider_from_bytes
from verdict.ledger.writer import LedgerWriter
from verdict.schemas.ledger import LedgerEntry
from verdict.schemas.tool_output import Artifact, ToolOutput


# ---------------------------------------------------------------------------
# Test fixtures — real ToolOutput + real key material
# ---------------------------------------------------------------------------


def _make_tool_output(
    tool_name: str = "vol3.windows.pslist",
    tool_version: str = "vol3 2.10.0",
    args: dict | None = None,
) -> ToolOutput:
    """Construct a real ToolOutput with valid invocation_hash."""
    if args is None:
        args = {"memory_image": "/evidence/mem.raw"}

    evidence_hash = hashlib.sha256(b"test-evidence").hexdigest()

    import json as _json
    from blake3 import blake3 as _b3

    args_json = _json.dumps(args, sort_keys=True)
    raw = (tool_name + tool_version + args_json + evidence_hash).encode()
    invocation_hash = _b3(raw).hexdigest()
    stdout_hash = hashlib.sha256(b"fake stdout").hexdigest()

    return ToolOutput(
        tool_name=tool_name,
        tool_version=tool_version,
        args=args,
        evidence_hash=evidence_hash,
        invocation_hash=invocation_hash,
        stdout_sha256=stdout_hash,
        output_files_sha256={"pslist.csv": hashlib.sha256(b"csv content").hexdigest()},
        parsed_artifacts=[
            Artifact(
                artifact_id="proc-4",
                evidence_path=Path("/evidence/mem.raw"),
                artifact_type="process",
                raw_fields={"pid": 4, "name": "System"},
            )
        ],
    )


def _make_executor(output: ToolOutput):
    """Return a real callable that returns output."""

    def executor(tool_name: str, args: dict) -> ToolOutput:
        return output

    return executor


def _make_ledger_emitter(
    ledger_path: Path,
    tool_output: ToolOutput,
    *,
    mode: str = "cloud",
    trace_id: str = "trace-abc-123",
) -> LedgerEmitter:
    """Build a real LedgerEmitter with a real key and real writer."""
    key_bytes = os.urandom(32)
    hmac_provider = get_hmac_key_provider_from_bytes(key_bytes)
    writer = LedgerWriter(ledger_path=ledger_path, hmac_provider=hmac_provider)
    executor = _make_executor(tool_output)

    return LedgerEmitter(
        executor=executor,
        ledger_writer=writer,
        hmac_provider=hmac_provider,
        case_id="case-001",
        mode_at_case_init=mode,
        verifier_strategy="CloudSelfConsistency",
        langfuse_trace_id=trace_id,
        langfuse_root_span_id="span-root-001",
        langgraph_thread_id="case-001",
        langgraph_checkpoint_id="ckpt-001",
        microsandbox_version="0.9.0",
        rootfs_sha256="a" * 64,
        kernel_version="5.15.0-118-generic",
    )


# ---------------------------------------------------------------------------
# W2.C.3.a assertions — write + fsync + verify-readback
# ---------------------------------------------------------------------------


class TestLedgerEmitterWrite:
    """LedgerEmitter writes to ledger.jsonl with fsync + verify-readback."""

    def test_ledger_file_grows_after_run(self, tmp_path: Path) -> None:
        """run() appends exactly one line to ledger.jsonl."""
        ledger_path = tmp_path / "ledger.jsonl"
        output = _make_tool_output()
        emitter = _make_ledger_emitter(ledger_path, output)

        assert not ledger_path.exists() or ledger_path.stat().st_size == 0

        emitter.run(tool_name="vol3.windows.pslist", args={"memory_image": "/evidence/mem.raw"})

        assert ledger_path.exists()
        lines = [ln for ln in ledger_path.read_bytes().split(b"\n") if ln.strip()]
        assert len(lines) == 1

    def test_run_returns_tool_output_and_ledger_entry(self, tmp_path: Path) -> None:
        """run() returns (ToolOutput, LedgerEntry) tuple."""
        ledger_path = tmp_path / "ledger.jsonl"
        output = _make_tool_output()
        emitter = _make_ledger_emitter(ledger_path, output)

        result = emitter.run(
            tool_name="vol3.windows.pslist",
            args={"memory_image": "/evidence/mem.raw"},
        )

        assert isinstance(result, tuple)
        tool_output, ledger_entry = result
        assert isinstance(tool_output, ToolOutput)
        assert isinstance(ledger_entry, LedgerEntry)

    def test_ledger_entry_has_tool_version(self, tmp_path: Path) -> None:
        """LedgerEntry.tool_version matches ToolOutput.tool_version."""
        ledger_path = tmp_path / "ledger.jsonl"
        output = _make_tool_output()
        emitter = _make_ledger_emitter(ledger_path, output)

        _, entry = emitter.run(
            tool_name="vol3.windows.pslist",
            args={"memory_image": "/evidence/mem.raw"},
        )

        assert entry.tool_version == "vol3 2.10.0"

    def test_ledger_entry_has_nist_metadata(self, tmp_path: Path) -> None:
        """NIST SP 800-86 fields are present in the LedgerEntry."""
        ledger_path = tmp_path / "ledger.jsonl"
        output = _make_tool_output()
        emitter = _make_ledger_emitter(ledger_path, output)

        _, entry = emitter.run(
            tool_name="vol3.windows.pslist",
            args={"memory_image": "/evidence/mem.raw"},
        )

        assert entry.microsandbox_version == "0.9.0"
        assert entry.rootfs_sha256 == "a" * 64
        assert entry.kernel_version == "5.15.0-118-generic"

    def test_ledger_entry_output_files_sha256_from_tool_output(self, tmp_path: Path) -> None:
        """output_files_sha256 in LedgerEntry mirrors ToolOutput.output_files_sha256."""
        ledger_path = tmp_path / "ledger.jsonl"
        output = _make_tool_output()
        emitter = _make_ledger_emitter(ledger_path, output)

        _, entry = emitter.run(
            tool_name="vol3.windows.pslist",
            args={"memory_image": "/evidence/mem.raw"},
        )

        assert "pslist.csv" in entry.output_files_sha256
        assert len(entry.output_files_sha256["pslist.csv"]) == 64  # sha256 hex


class TestLedgerEmitterChainIntegrity:
    """Chain integrity: prev_entry_hash links entries correctly."""

    def test_first_entry_prev_hash_is_genesis(self, tmp_path: Path) -> None:
        """First entry has prev_entry_hash == GENESIS_HASH (all zeros)."""
        ledger_path = tmp_path / "ledger.jsonl"
        output = _make_tool_output()
        emitter = _make_ledger_emitter(ledger_path, output)

        _, entry = emitter.run(
            tool_name="vol3.windows.pslist",
            args={"memory_image": "/evidence/mem.raw"},
        )

        assert entry.prev_entry_hash == LedgerWriter.GENESIS_HASH

    def test_second_entry_prev_hash_equals_blake3_of_first_line(
        self, tmp_path: Path
    ) -> None:
        """Second entry prev_entry_hash == blake3(first line bytes including newline)."""
        ledger_path = tmp_path / "ledger.jsonl"

        # Use the same key for both calls by sharing the writer
        key_bytes = os.urandom(32)
        hmac_provider = get_hmac_key_provider_from_bytes(key_bytes)
        writer = LedgerWriter(ledger_path=ledger_path, hmac_provider=hmac_provider)

        output1 = _make_tool_output("vol3.windows.pslist")
        output2 = _make_tool_output("vol3.windows.psscan")

        emitter = LedgerEmitter(
            executor=_make_executor(output1),
            ledger_writer=writer,
            hmac_provider=hmac_provider,
            case_id="case-001",
            mode_at_case_init="cloud",
            verifier_strategy="CloudSelfConsistency",
            langfuse_trace_id="trace-001",
            langfuse_root_span_id="span-001",
            langgraph_thread_id="case-001",
            langgraph_checkpoint_id="ckpt-001",
        )

        _, entry1 = emitter.run(
            tool_name="vol3.windows.pslist",
            args={"memory_image": "/evidence/mem.raw"},
        )

        # Swap executor to second output
        emitter._executor = _make_executor(output2)
        _, entry2 = emitter.run(
            tool_name="vol3.windows.psscan",
            args={"memory_image": "/evidence/mem.raw"},
        )

        # Compute expected prev hash from the first written line
        lines = [ln for ln in ledger_path.read_bytes().split(b"\n") if ln.strip()]
        assert len(lines) == 2
        expected_prev = _blake3(lines[0] + b"\n").hexdigest()
        assert entry2.prev_entry_hash == expected_prev

    def test_two_entries_written_to_file(self, tmp_path: Path) -> None:
        """Two run() calls produce two lines in ledger.jsonl."""
        ledger_path = tmp_path / "ledger.jsonl"
        key_bytes = os.urandom(32)
        hmac_provider = get_hmac_key_provider_from_bytes(key_bytes)
        writer = LedgerWriter(ledger_path=ledger_path, hmac_provider=hmac_provider)
        output = _make_tool_output()

        emitter = LedgerEmitter(
            executor=_make_executor(output),
            ledger_writer=writer,
            hmac_provider=hmac_provider,
            case_id="case-001",
            mode_at_case_init="airgap",
            verifier_strategy="AirGapCrossEngine",
            langfuse_trace_id="trace-001",
            langfuse_root_span_id="span-001",
            langgraph_thread_id="case-001",
            langgraph_checkpoint_id="ckpt-001",
        )

        emitter.run(tool_name="vol3.windows.pslist", args={})
        emitter.run(tool_name="vol3.windows.pslist", args={})

        lines = [ln for ln in ledger_path.read_bytes().split(b"\n") if ln.strip()]
        assert len(lines) == 2


class TestLedgerEmitterHMAC:
    """HMAC signature is present and verifiable in every entry."""

    def test_entry_has_hmac_sig(self, tmp_path: Path) -> None:
        """LedgerEntry.hmac_sig is a non-empty hex string."""
        ledger_path = tmp_path / "ledger.jsonl"
        output = _make_tool_output()
        emitter = _make_ledger_emitter(ledger_path, output)

        _, entry = emitter.run(
            tool_name="vol3.windows.pslist",
            args={"memory_image": "/evidence/mem.raw"},
        )

        assert isinstance(entry.hmac_sig, str)
        assert len(entry.hmac_sig) > 0

    def test_hmac_sig_verifiable_with_same_key(self, tmp_path: Path) -> None:
        """The HMAC signature in the ledger entry verifies with the same key."""
        ledger_path = tmp_path / "ledger.jsonl"
        key_bytes = os.urandom(32)
        hmac_provider = get_hmac_key_provider_from_bytes(key_bytes)
        writer = LedgerWriter(ledger_path=ledger_path, hmac_provider=hmac_provider)
        output = _make_tool_output()

        emitter = LedgerEmitter(
            executor=_make_executor(output),
            ledger_writer=writer,
            hmac_provider=hmac_provider,
            case_id="case-001",
            mode_at_case_init="dual",
            verifier_strategy="DualLaneCrossEngine",
            langfuse_trace_id="trace-001",
            langfuse_root_span_id="span-001",
            langgraph_thread_id="case-001",
            langgraph_checkpoint_id="ckpt-001",
        )

        _, entry = emitter.run(
            tool_name="vol3.windows.pslist",
            args={},
        )

        # Re-derive the message that was signed
        import json as _json
        message = (
            _json.dumps(entry.payload, separators=(",", ":"), sort_keys=True).encode()
            + entry.prev_entry_hash.encode()
            + entry.entry_id.encode()
        )
        assert hmac_provider.verify(message, entry.hmac_sig)

    def test_hmac_sig_does_not_verify_with_different_key(self, tmp_path: Path) -> None:
        """HMAC signature fails verification with a different key."""
        ledger_path = tmp_path / "ledger.jsonl"
        key_bytes = os.urandom(32)
        hmac_provider = get_hmac_key_provider_from_bytes(key_bytes)
        writer = LedgerWriter(ledger_path=ledger_path, hmac_provider=hmac_provider)
        output = _make_tool_output()

        emitter = LedgerEmitter(
            executor=_make_executor(output),
            ledger_writer=writer,
            hmac_provider=hmac_provider,
            case_id="case-001",
            mode_at_case_init="cloud",
            verifier_strategy="CloudSelfConsistency",
            langfuse_trace_id="trace-001",
            langfuse_root_span_id="span-001",
            langgraph_thread_id="case-001",
            langgraph_checkpoint_id="ckpt-001",
        )

        _, entry = emitter.run(
            tool_name="vol3.windows.pslist",
            args={},
        )

        # Verify with a DIFFERENT key — must fail
        different_key = get_hmac_key_provider_from_bytes(os.urandom(32))

        import json as _json
        message = (
            _json.dumps(entry.payload, separators=(",", ":"), sort_keys=True).encode()
            + entry.prev_entry_hash.encode()
            + entry.entry_id.encode()
        )
        assert not different_key.verify(message, entry.hmac_sig)


class TestLedgerEmitterLangfuseCrossLink:
    """Bidirectional Langfuse cross-link is encoded in every entry."""

    def test_entry_has_langfuse_trace_id(self, tmp_path: Path) -> None:
        """LedgerEntry.langfuse_trace_id matches the trace_id passed at construction."""
        ledger_path = tmp_path / "ledger.jsonl"
        output = _make_tool_output()
        emitter = _make_ledger_emitter(
            ledger_path, output, trace_id="trace-xyz-789"
        )

        _, entry = emitter.run(
            tool_name="vol3.windows.pslist",
            args={},
        )

        assert entry.langfuse_trace_id == "trace-xyz-789"

    def test_payload_contains_langfuse_trace_id(self, tmp_path: Path) -> None:
        """The entry payload also records langfuse_trace_id for Langfuse→ledger link."""
        ledger_path = tmp_path / "ledger.jsonl"
        output = _make_tool_output()
        emitter = _make_ledger_emitter(
            ledger_path, output, trace_id="trace-xyz-789"
        )

        _, entry = emitter.run(
            tool_name="vol3.windows.pslist",
            args={},
        )

        assert entry.payload.get("langfuse_trace_id") == "trace-xyz-789"

    def test_entry_langfuse_session_id_equals_case_id(self, tmp_path: Path) -> None:
        """langfuse_session_id == case_id (one session per case)."""
        ledger_path = tmp_path / "ledger.jsonl"
        output = _make_tool_output()
        emitter = _make_ledger_emitter(ledger_path, output)

        _, entry = emitter.run(
            tool_name="vol3.windows.pslist",
            args={},
        )

        assert entry.langfuse_session_id == entry.case_id


class TestLedgerEmitterModeLock:
    """mode_at_case_init is locked to the value passed at construction."""

    @pytest.mark.parametrize("mode", ["cloud", "airgap", "dual"])
    def test_mode_locked_in_entry(self, tmp_path: Path, mode: str) -> None:
        """LedgerEntry.mode_at_case_init matches the mode passed at construction."""
        ledger_path = tmp_path / "ledger.jsonl"
        output = _make_tool_output()
        emitter = _make_ledger_emitter(ledger_path, output, mode=mode)

        _, entry = emitter.run(
            tool_name="vol3.windows.pslist",
            args={},
        )

        assert entry.mode_at_case_init == mode

    def test_entry_event_type_is_tool_call(self, tmp_path: Path) -> None:
        """LedgerEntry.event_type is 'tool_call' for executor invocations."""
        ledger_path = tmp_path / "ledger.jsonl"
        output = _make_tool_output()
        emitter = _make_ledger_emitter(ledger_path, output)

        _, entry = emitter.run(
            tool_name="vol3.windows.pslist",
            args={},
        )

        assert entry.event_type == "tool_call"


class TestLedgerEmitterCallable:
    """LedgerEmitter is callable and returns only the ToolOutput."""

    def test_callable_returns_tool_output(self, tmp_path: Path) -> None:
        """Calling the emitter directly returns the ToolOutput (not the tuple)."""
        ledger_path = tmp_path / "ledger.jsonl"
        output = _make_tool_output()
        emitter = _make_ledger_emitter(ledger_path, output)

        result = emitter("vol3.windows.pslist", {"memory_image": "/evidence/mem.raw"})

        assert isinstance(result, ToolOutput)
        assert result.tool_name == "vol3.windows.pslist"

    def test_callable_still_writes_ledger(self, tmp_path: Path) -> None:
        """Calling the emitter directly also writes the ledger entry."""
        ledger_path = tmp_path / "ledger.jsonl"
        output = _make_tool_output()
        emitter = _make_ledger_emitter(ledger_path, output)

        emitter("vol3.windows.pslist", {})

        lines = [ln for ln in ledger_path.read_bytes().split(b"\n") if ln.strip()]
        assert len(lines) == 1
