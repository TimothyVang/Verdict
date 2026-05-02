"""LedgerEmitter — third wrapper in the executor_work composition.

Position in the three-wrapper composition (ARCHITECTURE.md §2 + CLAUDE.md §4):

    DenyRuleWrapper → ToolExecutor → LedgerEmitter

Responsibilities (this module only):

  1. Receive the ToolOutput returned by ToolExecutor.
  2. Build a LedgerEntry from the ToolOutput + LangGraph context IDs.
  3. Write the entry to the append-only ledger with write + fsync +
     verify-readback (CLAUDE.md §9 durability contract).
  4. Emit the bidirectional cross-link to the Langfuse trace_id
     (ARCHITECTURE.md §5).

Explicitly NOT in scope:
  - Writing to /evidence/ (Layer 2 deny — DenyRuleWrapper's job).
  - Tool dispatch (ToolExecutor's job).
  - Microsandbox spawn (concrete _execute() implementations, W2.B).

HMAC key: obtained from verdict/ledger/hmac_key.py via get_hmac_key_provider()
at LedgerEmitter construction time (wired once at gateway init).  The emitter
does NOT create a new key provider per call — the provider is injected at
construction so the TPM handle / gpg passphrase is entered once per session.

Chain integrity: the LedgerEmitter holds a LedgerWriter instance per case.
The writer maintains prev_entry_hash state; LedgerEmitter delegates all
durability and chain management to the writer.

Langfuse cross-link: every LedgerEntry records langfuse_trace_id (and the
leaf span IDs from the executor fanout).  The Langfuse span itself records
ledger_entry_id as an attribute — that wiring happens in
verdict/observability/trace_link.py (W3.E.5), not here.  LedgerEmitter's
job is to record the IDs; the Langfuse client call happens in the node
function.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from verdict.ledger.hmac_key import HMACKeyProvider
from verdict.ledger.writer import LedgerWriter
from verdict.schemas.ledger import LedgerEntry
from verdict.schemas.tool_output import ToolOutput


# ---------------------------------------------------------------------------
# LedgerEmitter
# ---------------------------------------------------------------------------


class LedgerEmitter:
    """Wraps a tool executor call, writes the result to the append-only ledger.

    Args:
        executor:            Callable with signature ``(tool_name, args) -> ToolOutput``.
                             Typically a ToolExecutor instance.
        ledger_writer:       A LedgerWriter bound to the current case's ledger.jsonl.
        hmac_provider:       HMACKeyProvider — used by the LedgerWriter; injected
                             here for traceability (the writer may be constructed
                             externally and shared).
        case_id:             ROOT case ID (eternal, never changes).
        mode_at_case_init:   Locked mode ("cloud" | "airgap" | "dual").
        verifier_strategy:   Strategy name string for the ledger entry.
        langfuse_trace_id:   Current graph.invoke() trace ID.
        langfuse_root_span_id: The planner_node span for this trace.
        langgraph_thread_id: = case_id.
        langgraph_checkpoint_id: Current super-step checkpoint ID.
        microsandbox_version: Version string of the microsandbox runtime.
        rootfs_sha256:       SHA-256 of the rootfs image used in this call.
        kernel_version:      Kernel version of the microVM host.
    """

    def __init__(
        self,
        *,
        executor: Callable[[str, dict], ToolOutput],
        ledger_writer: LedgerWriter,
        hmac_provider: HMACKeyProvider,
        case_id: str,
        mode_at_case_init: str,
        verifier_strategy: str,
        langfuse_trace_id: str,
        langfuse_root_span_id: str,
        langgraph_thread_id: str,
        langgraph_checkpoint_id: str,
        microsandbox_version: str | None = None,
        rootfs_sha256: str | None = None,
        kernel_version: str | None = None,
    ) -> None:
        self._executor = executor
        self._writer = ledger_writer
        self._hmac = hmac_provider
        self._case_id = case_id
        self._mode = mode_at_case_init
        self._verifier_strategy = verifier_strategy
        self._langfuse_trace_id = langfuse_trace_id
        self._langfuse_root_span_id = langfuse_root_span_id
        self._langgraph_thread_id = langgraph_thread_id
        self._langgraph_checkpoint_id = langgraph_checkpoint_id
        self._microsandbox_version = microsandbox_version
        self._rootfs_sha256 = rootfs_sha256
        self._kernel_version = kernel_version

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, *, tool_name: str, args: dict) -> tuple[ToolOutput, LedgerEntry]:
        """Execute the tool, write the ledger entry, return both.

        The returned LedgerEntry has been written to disk with fsync +
        verify-readback before this method returns.  The ToolOutput is the
        direct result from the executor.

        Args:
            tool_name: Dotted tool identifier.
            args:       Validated tool invocation arguments.

        Returns:
            (ToolOutput, LedgerEntry) — the executor result and the ledger row.

        Raises:
            Any exception from the executor propagates unchanged.
            LedgerWriteError: If the ledger write fails (fsync / readback).
        """
        # Call the executor (DenyRuleWrapper + ToolExecutor if composed)
        tool_output: ToolOutput = self._executor(tool_name, args)

        # Build a ULID-style entry ID (timestamp-based UUID4 hex for now;
        # replace with python-ulid in W2.G.1 when dependency is pinned)
        entry_id = str(uuid.uuid4()).replace("-", "")

        # Compute per-output-file hashes from ToolOutput
        output_files_sha256 = dict(tool_output.output_files_sha256)

        # Build ledger payload — all chain-of-custody fields
        payload: dict[str, Any] = {
            "tool_name": tool_output.tool_name,
            "tool_version": tool_output.tool_version,
            "invocation_hash": tool_output.invocation_hash,
            "evidence_hash": tool_output.evidence_hash,
            "stdout_sha256": tool_output.stdout_sha256,
            "parsed_artifact_count": len(tool_output.parsed_artifacts),
            "parse_warnings": tool_output.parse_warnings,
            "sanitization_flags": tool_output.sanitization_flags,
            # Bidirectional Langfuse cross-link
            "langfuse_trace_id": self._langfuse_trace_id,
        }

        # Write entry to ledger with write + fsync + verify-readback
        entry = self._writer.build_entry(
            entry_id=entry_id,
            case_id=self._case_id,
            event_type="tool_call",
            mode_at_case_init=self._mode,
            verifier_strategy_used=self._verifier_strategy,
            langfuse_session_id=self._case_id,
            langfuse_trace_id=self._langfuse_trace_id,
            langfuse_root_span_id=self._langfuse_root_span_id,
            langgraph_thread_id=self._langgraph_thread_id,
            langgraph_checkpoint_id=self._langgraph_checkpoint_id,
            payload=payload,
            microsandbox_version=self._microsandbox_version,
            rootfs_sha256=self._rootfs_sha256,
            tool_version=tool_output.tool_version,
            kernel_version=self._kernel_version,
            output_files_sha256=output_files_sha256,
        )

        self._writer.write(entry)

        return tool_output, entry

    # Make callable so it can be composed as an executor by a higher-level
    # wrapper (though LedgerEmitter is typically the outermost wrapper in
    # the composition).
    def __call__(self, tool_name: str, args: dict) -> ToolOutput:
        tool_output, _entry = self.run(tool_name=tool_name, args=args)
        return tool_output
