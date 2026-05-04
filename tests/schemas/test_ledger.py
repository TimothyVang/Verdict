from __future__ import annotations

from datetime import UTC, datetime

from verdict.schemas.ledger import LedgerEntry


def _ledger_entry() -> LedgerEntry:
    return LedgerEntry(
        entry_id="01HX0000000000000000000000",
        case_id="case-001",
        finding_id=None,
        event_type="tool_call",
        timestamp_utc=datetime(2026, 5, 2, tzinfo=UTC),
        mode_at_case_init="AIRGAP",
        verifier_strategy_used="AirGapCrossEngine",
        langfuse_session_id="case-001",
        langfuse_trace_id="trace-001",
        langfuse_root_span_id="span-root",
        langfuse_leaf_span_ids=["span-tool"],
        langgraph_thread_id="case-001",
        langgraph_checkpoint_id="checkpoint-001",
        microsandbox_version="0.1.0",
        rootfs_sha256="r" * 64,
        tool_version="vol3 2.10.0",
        kernel_version="6.8.0",
        output_files_sha256={"/case/out/psscan.json": "o" * 64},
        payload={"tool": "vol3.windows.psscan"},
        prev_entry_hash="p" * 64,
        hmac_sig="h" * 64,
    )


def test_ledger_entry_three_id_hierarchy() -> None:
    entry = _ledger_entry()

    assert entry.case_id == "case-001"
    assert entry.langfuse_trace_id == "trace-001"
    assert entry.langgraph_checkpoint_id == "checkpoint-001"


def test_ledger_entry_records_examination_environment() -> None:
    entry = _ledger_entry()

    assert entry.microsandbox_version == "0.1.0"
    assert entry.rootfs_sha256 == "r" * 64
    assert entry.tool_version == "vol3 2.10.0"
    assert entry.kernel_version == "6.8.0"
    assert entry.output_files_sha256 == {"/case/out/psscan.json": "o" * 64}
