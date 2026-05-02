"""LangGraph topology helpers — W2.C.4.

This module provides build_executor_work(), the factory that composes the
three executor_work wrappers into the inner-branch callable used by each of
the four parallel executor branches in executor_fanout.

Composition order (ARCHITECTURE.md §2 + CLAUDE.md §4):

    executor_fanout branch N:
        LedgerEmitter.run()
            └── DenyRuleWrapper.run()       ← deny rule fires FIRST
                    └── ToolExecutor.run()  ← microsandbox spawn (W2.B)

The three wrappers are separate classes (separate owners in BUILD_PLAN per
W2.C.1/W2.C.2/W2.C.3) — this module wires them together.

The full LangGraph StateGraph (9 nodes) is out of scope for W2.C; it lands in
W2.B.4 (fanout reducer) and W2.A (planner/critique nodes).  This module
provides only the executor_work factory needed to make each fanout branch's
inner callable composable and testable in isolation.

Usage (within executor_fanout node function)::

    chain = build_executor_work(
        wrappers=[pslist, psscan, malfind, netscan],
        evidence_path=...,
        work_dir=...,
        ledger_writer=...,
        hmac_provider=...,
        case_id=state.case_id,
        mode=state.mode_at_case_init,
        verifier_strategy=state.verifier_strategy,
        langfuse_trace_id=...,
        langfuse_root_span_id=...,
        langgraph_thread_id=state.case_id,
        langgraph_checkpoint_id=...,
    )
    tool_output = chain(tool_name, args)
"""

from __future__ import annotations

from pathlib import Path

from verdict.graph.wrappers.deny_rule import DenyRuleWrapper
from verdict.graph.wrappers.ledger_emitter import LedgerEmitter
from verdict.graph.wrappers.tool_executor import ToolExecutor
from verdict.ledger.hmac_key import HMACKeyProvider
from verdict.ledger.writer import LedgerWriter
from verdict.tools.base import ToolWrapper


def build_executor_work(
    *,
    wrappers: list[ToolWrapper],
    evidence_path: Path,
    work_dir: Path,
    ledger_writer: LedgerWriter,
    hmac_provider: HMACKeyProvider,
    case_id: str,
    mode: str,
    verifier_strategy: str,
    langfuse_trace_id: str,
    langfuse_root_span_id: str,
    langgraph_thread_id: str,
    langgraph_checkpoint_id: str,
    microsandbox_version: str | None = None,
    rootfs_sha256: str | None = None,
    kernel_version: str | None = None,
) -> LedgerEmitter:
    """Compose DenyRuleWrapper → ToolExecutor → LedgerEmitter.

    This is the canonical factory for the executor_work inner callable used
    in each parallel branch of executor_fanout (ARCHITECTURE.md §2).

    Composition from inside out:
      1. ToolExecutor — owns the registry and the _execute() dispatch.
      2. DenyRuleWrapper — wraps ToolExecutor; fires deny rules before dispatch.
      3. LedgerEmitter — wraps DenyRuleWrapper; writes ledger after execution.

    Args:
        wrappers:               List of ToolWrapper subclasses to register.
        evidence_path:          Read-only evidence file path inside the microsandbox.
        work_dir:               Writable work dir inside the microsandbox.
        ledger_writer:          LedgerWriter bound to this case's ledger.jsonl.
        hmac_provider:          HMACKeyProvider for HMAC signing.
        case_id:                ROOT case ID.
        mode:                   Locked operational mode ("cloud"|"airgap"|"dual").
        verifier_strategy:      Strategy name for ledger entries.
        langfuse_trace_id:      Current graph.invoke() trace ID.
        langfuse_root_span_id:  The planner_node span for this trace.
        langgraph_thread_id:    = case_id.
        langgraph_checkpoint_id: Super-step checkpoint ID.
        microsandbox_version:   Microsandbox version for NIST SP 800-86 metadata.
        rootfs_sha256:          Rootfs image hash for NIST metadata.
        kernel_version:         MicroVM kernel version for NIST metadata.

    Returns:
        A LedgerEmitter instance.  Call it as:
            tool_output = chain(tool_name, args)
        or use the .run() method to get both ToolOutput and LedgerEntry:
            tool_output, ledger_entry = chain.run(tool_name=..., args=...)
    """
    # Layer 1 (innermost): ToolExecutor — dispatch to registered wrappers
    tool_executor = ToolExecutor(
        wrappers=wrappers,
        evidence_path=evidence_path,
        work_dir=work_dir,
    )

    # Layer 2: DenyRuleWrapper — deny /evidence/ writes before any execution
    deny_wrapper = DenyRuleWrapper(
        executor=tool_executor,
        mode=mode,
    )

    # Layer 3 (outermost): LedgerEmitter — write + fsync + verify-readback
    return LedgerEmitter(
        executor=deny_wrapper,
        ledger_writer=ledger_writer,
        hmac_provider=hmac_provider,
        case_id=case_id,
        mode_at_case_init=mode,
        verifier_strategy=verifier_strategy,
        langfuse_trace_id=langfuse_trace_id,
        langfuse_root_span_id=langfuse_root_span_id,
        langgraph_thread_id=langgraph_thread_id,
        langgraph_checkpoint_id=langgraph_checkpoint_id,
        microsandbox_version=microsandbox_version,
        rootfs_sha256=rootfs_sha256,
        kernel_version=kernel_version,
    )
