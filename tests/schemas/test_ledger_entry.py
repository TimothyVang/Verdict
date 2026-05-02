"""Tests for LedgerEntry schema — W1.B.6.

Covers:
  - Three-tier ID hierarchy: case_id / langfuse_trace_id / langgraph_checkpoint_id
  - mode_at_case_init: Literal["cloud","airgap","dual"] immutable post-init (CLAUDE.md §3.4)
  - prev_entry_hash: str for chain integrity
  - output_files_sha256: dict[str, str] per-output-file hashes (CLAUDE.md §3.1 / NIST SP 800-86 §5.1.2)
  - NIST SP 800-86 §5.1.4 examination-environment metadata:
      microsandbox_version, rootfs_sha256, tool_version, kernel_version
  - event_type: Literal of all 13 valid event types (CLAUDE.md §9 Ledger discipline)
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from verdict.schemas.ledger_entry import LedgerEntry


# ---------------------------------------------------------------------------
# Minimal valid constructor helper
# ---------------------------------------------------------------------------

def _valid_kwargs(**overrides) -> dict:
    """Return a dict of minimal valid LedgerEntry kwargs, with optional overrides."""
    base = {
        "entry_id": "01HV000000000000000000001A",
        "case_id": "case-001",
        "finding_id": None,
        "event_type": "case_init",
        "timestamp_utc": datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc),
        "mode_at_case_init": "cloud",
        "verifier_strategy_used": "CloudSelfConsistency",
        "langfuse_session_id": "case-001",
        "langfuse_trace_id": "trace-abc-001",
        "langfuse_root_span_id": "span-root-001",
        "langfuse_leaf_span_ids": [],
        "langgraph_thread_id": "case-001",
        "langgraph_checkpoint_id": "ckpt-001",
        "payload": {"note": "case opened"},
        "prev_entry_hash": "a" * 64,
        "hmac_sig": "b" * 64,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Three-tier ID hierarchy
# ---------------------------------------------------------------------------

class TestThreeTierIDHierarchy:
    """NIST SP 800-86 + ARCHITECTURE.md §5 — three distinct ID scopes."""

    def test_case_id_is_distinct_field(self) -> None:
        entry = LedgerEntry(**_valid_kwargs())
        assert entry.case_id == "case-001"

    def test_langfuse_trace_id_is_distinct_field(self) -> None:
        entry = LedgerEntry(**_valid_kwargs(langfuse_trace_id="trace-xyz-999"))
        assert entry.langfuse_trace_id == "trace-xyz-999"

    def test_langgraph_checkpoint_id_is_distinct_field(self) -> None:
        entry = LedgerEntry(**_valid_kwargs(langgraph_checkpoint_id="ckpt-super-42"))
        assert entry.langgraph_checkpoint_id == "ckpt-super-42"

    def test_three_ids_are_separate_not_aliased(self) -> None:
        entry = LedgerEntry(**_valid_kwargs(
            case_id="case-A",
            langfuse_trace_id="trace-B",
            langgraph_checkpoint_id="ckpt-C",
        ))
        assert entry.case_id != entry.langfuse_trace_id
        assert entry.langfuse_trace_id != entry.langgraph_checkpoint_id
        assert entry.case_id != entry.langgraph_checkpoint_id

    def test_entry_id_present(self) -> None:
        entry = LedgerEntry(**_valid_kwargs())
        assert entry.entry_id == "01HV000000000000000000001A"

    def test_langfuse_session_id_is_present(self) -> None:
        entry = LedgerEntry(**_valid_kwargs())
        assert entry.langfuse_session_id == "case-001"

    def test_langgraph_thread_id_is_present(self) -> None:
        entry = LedgerEntry(**_valid_kwargs())
        assert entry.langgraph_thread_id == "case-001"


# ---------------------------------------------------------------------------
# Mode lock (CLAUDE.md §3.4)
# ---------------------------------------------------------------------------

class TestModeLock:
    """mode_at_case_init must be one of {"cloud","airgap","dual"} and immutable."""

    def test_mode_cloud_accepted(self) -> None:
        entry = LedgerEntry(**_valid_kwargs(mode_at_case_init="cloud"))
        assert entry.mode_at_case_init == "cloud"

    def test_mode_airgap_accepted(self) -> None:
        entry = LedgerEntry(**_valid_kwargs(mode_at_case_init="airgap"))
        assert entry.mode_at_case_init == "airgap"

    def test_mode_dual_accepted(self) -> None:
        entry = LedgerEntry(**_valid_kwargs(mode_at_case_init="dual"))
        assert entry.mode_at_case_init == "dual"

    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LedgerEntry(**_valid_kwargs(mode_at_case_init="online"))

    def test_mode_immutable_post_init(self) -> None:
        """LedgerEntry is frozen — mutation must raise."""
        entry = LedgerEntry(**_valid_kwargs(mode_at_case_init="cloud"))
        with pytest.raises(Exception):
            entry.mode_at_case_init = "dual"  # type: ignore[misc]

    def test_case_id_immutable_post_init(self) -> None:
        entry = LedgerEntry(**_valid_kwargs())
        with pytest.raises(Exception):
            entry.case_id = "evil-mutation"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Chain integrity — prev_entry_hash
# ---------------------------------------------------------------------------

class TestChainIntegrity:
    """prev_entry_hash must be present for ledger chaining."""

    def test_prev_entry_hash_present(self) -> None:
        entry = LedgerEntry(**_valid_kwargs(prev_entry_hash="c" * 64))
        assert entry.prev_entry_hash == "c" * 64

    def test_prev_entry_hash_required(self) -> None:
        kwargs = _valid_kwargs()
        del kwargs["prev_entry_hash"]
        with pytest.raises(ValidationError):
            LedgerEntry(**kwargs)

    def test_hmac_sig_present(self) -> None:
        entry = LedgerEntry(**_valid_kwargs(hmac_sig="d" * 64))
        assert entry.hmac_sig == "d" * 64

    def test_hmac_sig_required(self) -> None:
        kwargs = _valid_kwargs()
        del kwargs["hmac_sig"]
        with pytest.raises(ValidationError):
            LedgerEntry(**kwargs)


# ---------------------------------------------------------------------------
# Per-output-file hashes (CLAUDE.md §3.1 / NIST SP 800-86 §5.1.2)
# ---------------------------------------------------------------------------

class TestOutputFilesHashes:
    """output_files_sha256 maps output-file path → SHA-256 digest."""

    def test_output_files_sha256_defaults_to_empty_dict(self) -> None:
        entry = LedgerEntry(**_valid_kwargs())
        assert entry.output_files_sha256 == {}

    def test_output_files_sha256_accepts_populated_dict(self) -> None:
        hashes = {
            "/tmp/pslist.json": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "/tmp/psscan.txt": "da39a3ee5e6b4b0d3255bfef95601890afd80709000000000000000000000000",
        }
        entry = LedgerEntry(**_valid_kwargs(output_files_sha256=hashes))
        assert entry.output_files_sha256 == hashes

    def test_output_files_sha256_rejects_non_dict(self) -> None:
        with pytest.raises(ValidationError):
            LedgerEntry(**_valid_kwargs(output_files_sha256=["not", "a", "dict"]))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# NIST SP 800-86 §5.1.4 examination-environment metadata
# ---------------------------------------------------------------------------

class TestExaminationEnvironment:
    """microsandbox_version, rootfs_sha256, tool_version, kernel_version."""

    def test_all_exam_env_fields_default_to_none(self) -> None:
        entry = LedgerEntry(**_valid_kwargs())
        assert entry.microsandbox_version is None
        assert entry.rootfs_sha256 is None
        assert entry.tool_version is None
        assert entry.kernel_version is None

    def test_microsandbox_version_can_be_set(self) -> None:
        entry = LedgerEntry(**_valid_kwargs(microsandbox_version="0.9.1"))
        assert entry.microsandbox_version == "0.9.1"

    def test_rootfs_sha256_can_be_set(self) -> None:
        digest = "sha256:" + "f" * 64
        entry = LedgerEntry(**_valid_kwargs(rootfs_sha256=digest))
        assert entry.rootfs_sha256 == digest

    def test_tool_version_can_be_set(self) -> None:
        entry = LedgerEntry(**_valid_kwargs(tool_version="volatility3 2.10.0"))
        assert entry.tool_version == "volatility3 2.10.0"

    def test_kernel_version_can_be_set(self) -> None:
        entry = LedgerEntry(**_valid_kwargs(kernel_version="5.15.0-118-generic"))
        assert entry.kernel_version == "5.15.0-118-generic"

    def test_records_examination_environment(self) -> None:
        """Combined: all four fields populated in one entry."""
        entry = LedgerEntry(**_valid_kwargs(
            microsandbox_version="0.9.1",
            rootfs_sha256="sha256:" + "a" * 64,
            tool_version="vol3 2.10.0",
            kernel_version="5.15.0-118-generic",
        ))
        assert entry.microsandbox_version == "0.9.1"
        assert entry.rootfs_sha256 is not None
        assert entry.tool_version == "vol3 2.10.0"
        assert entry.kernel_version == "5.15.0-118-generic"


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

class TestEventType:
    """All 13 event types from CLAUDE.md §9 Ledger discipline must be accepted."""

    VALID_EVENT_TYPES = [
        "case_init",
        "tool_call",
        "finding",
        "approval",
        "rejection",
        "mode_lock",
        "comprehension_check",
        "critique_verdict",
        "pivot",
        "exhausted_replan",
        "evidence_hash_recheck",
        "sandbox_failure",
        "planner_cot",
    ]

    @pytest.mark.parametrize("event_type", VALID_EVENT_TYPES)
    def test_valid_event_type_accepted(self, event_type: str) -> None:
        entry = LedgerEntry(**_valid_kwargs(event_type=event_type))
        assert entry.event_type == event_type

    def test_invalid_event_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LedgerEntry(**_valid_kwargs(event_type="unknown_event"))

    def test_all_13_event_types_defined(self) -> None:
        assert len(self.VALID_EVENT_TYPES) == 13

    def test_event_type_enum_covers_all_13(self) -> None:
        """EventType Literal must match the CLAUDE.md §9 event list."""
        for et in self.VALID_EVENT_TYPES:
            # should not raise
            LedgerEntry(**_valid_kwargs(event_type=et))


# ---------------------------------------------------------------------------
# Payload and redaction fields
# ---------------------------------------------------------------------------

class TestPayload:
    def test_payload_required(self) -> None:
        kwargs = _valid_kwargs()
        del kwargs["payload"]
        with pytest.raises(ValidationError):
            LedgerEntry(**kwargs)

    def test_payload_redactions_defaults_to_empty_list(self) -> None:
        entry = LedgerEntry(**_valid_kwargs())
        assert entry.payload_redactions == []

    def test_payload_redactions_accepts_list(self) -> None:
        entry = LedgerEntry(**_valid_kwargs(
            payload_redactions=["authorization", "api_key"]
        ))
        assert "authorization" in entry.payload_redactions

    def test_finding_id_optional(self) -> None:
        entry = LedgerEntry(**_valid_kwargs(finding_id="finding-abc-123"))
        assert entry.finding_id == "finding-abc-123"

    def test_finding_id_none_accepted(self) -> None:
        entry = LedgerEntry(**_valid_kwargs(finding_id=None))
        assert entry.finding_id is None


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

class TestSchemaVersion:
    def test_schema_version_defaults_to_1(self) -> None:
        entry = LedgerEntry(**_valid_kwargs())
        assert entry.schema_version == 1


# ---------------------------------------------------------------------------
# Round-trip JSON serialization
# ---------------------------------------------------------------------------

class TestJsonRoundTrip:
    def test_round_trips_through_json(self) -> None:
        entry = LedgerEntry(**_valid_kwargs(
            microsandbox_version="0.9.1",
            tool_version="vol3 2.10.0",
            output_files_sha256={"/tmp/out.json": "e3b0" * 16},
        ))
        json_str = entry.model_dump_json()
        restored = LedgerEntry.model_validate_json(json_str)
        assert restored == entry

    def test_serialization_includes_all_required_fields(self) -> None:
        entry = LedgerEntry(**_valid_kwargs())
        data = entry.model_dump()
        required_keys = {
            "entry_id", "case_id", "langfuse_trace_id", "langgraph_checkpoint_id",
            "mode_at_case_init", "prev_entry_hash", "hmac_sig",
            "output_files_sha256", "microsandbox_version", "rootfs_sha256",
            "tool_version", "kernel_version", "event_type", "schema_version",
        }
        assert required_keys.issubset(data.keys())
