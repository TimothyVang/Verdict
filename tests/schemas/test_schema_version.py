"""Tests for schema_version discipline — W1.B.12.

BUILD_PLAN W1.B.12.a: test_schema_version_is_1_on_all_top_level_models.
Loop through [InvestigationPlan, Finding, LedgerEntry, EvidenceManifest, ToolOutput];
assert .schema_version == 1.

Also verifies verdict/schemas/version.py centralises the constant.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import blake3
import pytest

from verdict.schemas.version import SCHEMA_VERSION
from verdict.schemas.investigation_plan import InvestigationPlan
from verdict.schemas.finding import Finding
from verdict.schemas.ledger import LedgerEntry
from verdict.schemas.evidence import EvidenceManifest
from verdict.schemas.tool_output import ToolOutput


# ---------------------------------------------------------------------------
# Helpers — minimal valid constructors
# ---------------------------------------------------------------------------

def _make_investigation_plan() -> InvestigationPlan:
    return InvestigationPlan(plan_id="plan-001")


def _make_finding() -> Finding:
    return Finding(
        finding_id="f-001",
        title="Suspicious PowerShell",
        description="Evidence consistent with PowerShell execution via LOLBin",
        mitre_technique="T1059.001",
        artifact_paths=["/evidence/disk.E01", "/evidence/mem.raw"],
        artifact_classes=["PREFETCH", "MEMORY_DUMP"],
        caveats_acknowledged=["PREFETCH_SSD_DISABLED"],
        status="vetted_cloud",
    )


def _make_ledger_entry() -> LedgerEntry:
    return LedgerEntry(
        entry_id="01HV000000000000000000001A",
        case_id="case-001",
        event_type="case_init",
        timestamp_utc=datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc),
        mode_at_case_init="cloud",
        verifier_strategy_used="CloudSelfConsistency",
        langfuse_session_id="case-001",
        langfuse_trace_id="trace-abc-001",
        langfuse_root_span_id="span-root-001",
        langgraph_thread_id="case-001",
        langgraph_checkpoint_id="ckpt-001",
        payload={"note": "case opened"},
        prev_entry_hash="a" * 64,
        hmac_sig="b" * 64,
    )


def _make_evidence_manifest() -> EvidenceManifest:
    return EvidenceManifest(
        case_id="case-001",
        items=[],
        manifest_hash="c" * 64,
    )


def _make_tool_output() -> ToolOutput:
    tool_name = "vol3.windows.pslist"
    tool_version = "vol3 2.10.0"
    args: dict = {}
    evidence_hash = "d" * 64
    args_json = json.dumps(args, sort_keys=True)
    raw = (tool_name + tool_version + args_json + evidence_hash).encode()
    invocation_hash = blake3.blake3(raw).hexdigest()
    return ToolOutput(
        tool_name=tool_name,
        tool_version=tool_version,
        args=args,
        evidence_hash=evidence_hash,
        invocation_hash=invocation_hash,
        stdout_sha256="e" * 64,
    )


# ---------------------------------------------------------------------------
# W1.B.12.a — named test as per BUILD_PLAN
# ---------------------------------------------------------------------------

class TestSchemaVersionIs1OnAllTopLevelModels:
    """BUILD_PLAN W1.B.12.a: assert schema_version == 1 on all five models."""

    def test_schema_version_is_1_on_all_top_level_models(self) -> None:
        """All five top-level schemas must expose schema_version == 1."""
        models = [
            _make_investigation_plan(),
            _make_finding(),
            _make_ledger_entry(),
            _make_evidence_manifest(),
            _make_tool_output(),
        ]
        for model in models:
            assert model.schema_version == 1, (
                f"{type(model).__name__}.schema_version expected 1, "
                f"got {model.schema_version!r}"
            )

    def test_investigation_plan_schema_version_is_1(self) -> None:
        assert _make_investigation_plan().schema_version == 1

    def test_finding_schema_version_is_1(self) -> None:
        assert _make_finding().schema_version == 1

    def test_ledger_entry_schema_version_is_1(self) -> None:
        assert _make_ledger_entry().schema_version == 1

    def test_evidence_manifest_schema_version_is_1(self) -> None:
        assert _make_evidence_manifest().schema_version == 1

    def test_tool_output_schema_version_is_1(self) -> None:
        assert _make_tool_output().schema_version == 1

    def test_schema_version_constant_in_version_module(self) -> None:
        """verdict/schemas/version.py must export SCHEMA_VERSION == 1."""
        assert SCHEMA_VERSION == 1

    def test_all_models_use_version_module_constant(self) -> None:
        """Every model's schema_version must equal the central SCHEMA_VERSION."""
        models = [
            _make_investigation_plan(),
            _make_finding(),
            _make_ledger_entry(),
            _make_evidence_manifest(),
            _make_tool_output(),
        ]
        for model in models:
            assert model.schema_version == SCHEMA_VERSION, (
                f"{type(model).__name__}.schema_version {model.schema_version!r} "
                f"!= SCHEMA_VERSION {SCHEMA_VERSION!r}"
            )
