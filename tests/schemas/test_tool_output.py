"""Tests for verdict/schemas/tool_output.py — W1.B.7.

All assertions are against real Pydantic v2 instantiation; no mocks (CLAUDE.md §3.10).
"""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from verdict.schemas.tool_output import Artifact, ToolOutput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_artifact(**overrides) -> dict:
    base = {
        "artifact_id": "01JXXXXXXXXXXXXXXXXXXXXXXX",
        "evidence_path": "/evidence/mem.raw",
        "artifact_type": "process",
        "raw_fields": {"pid": 4, "name": "System"},
    }
    base.update(overrides)
    return base


def _make_tool_output(**overrides) -> dict:
    """Minimal valid ToolOutput payload; overrides replace keys.

    Computes invocation_hash = blake3(tool_name + tool_version + args_json + evidence_hash)
    where args_json = json.dumps(args, sort_keys=True) — matching the validator exactly.
    """
    from blake3 import blake3 as _b3

    tool_name = "vol3.windows.pslist"
    tool_version = "vol3 2.10.0"
    args = {"argv": ["-f", "/evidence/mem.raw", "windows.pslist"]}
    evidence_hash = "a" * 64  # fake SHA-256 hex, 64 chars

    # Must match json.dumps(self.args, sort_keys=True) in the validator
    args_json = json.dumps(args, sort_keys=True)
    raw = (tool_name + tool_version + args_json + evidence_hash).encode()
    invocation_hash = _b3(raw).hexdigest()

    stdout_bytes = b"PID PPID Name\n4 0 System\n"
    stdout_sha256 = hashlib.sha256(stdout_bytes).hexdigest()

    base = {
        "tool_name": tool_name,
        "tool_version": tool_version,
        "args": args,
        "evidence_hash": evidence_hash,
        "invocation_hash": invocation_hash,
        "output_files_sha256": {"pslist.csv": "b" * 64},
        "stdout_sha256": stdout_sha256,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Field-presence tests
# ---------------------------------------------------------------------------

def test_tool_output_has_tool_name_field() -> None:
    payload = _make_tool_output()
    obj = ToolOutput(**payload)
    assert isinstance(obj.tool_name, str)


def test_tool_output_has_tool_version_field() -> None:
    obj = ToolOutput(**_make_tool_output())
    assert isinstance(obj.tool_version, str)


def test_tool_output_has_args_field() -> None:
    obj = ToolOutput(**_make_tool_output())
    assert isinstance(obj.args, dict)


def test_tool_output_has_evidence_hash_field() -> None:
    obj = ToolOutput(**_make_tool_output())
    assert isinstance(obj.evidence_hash, str)


def test_tool_output_has_invocation_hash_field() -> None:
    obj = ToolOutput(**_make_tool_output())
    assert isinstance(obj.invocation_hash, str)


def test_tool_output_has_output_files_sha256_field() -> None:
    obj = ToolOutput(**_make_tool_output())
    assert isinstance(obj.output_files_sha256, dict)


def test_tool_output_has_stdout_sha256_field() -> None:
    obj = ToolOutput(**_make_tool_output())
    assert isinstance(obj.stdout_sha256, str)


# ---------------------------------------------------------------------------
# Core: invocation_hash = blake3(tool_name + tool_version + args + evidence_hash)
# CLAUDE.md §3.1 — per-invocation hash is load-bearing chain-of-custody.
# ---------------------------------------------------------------------------

def test_invocation_hash_combines_name_version_args_evidence() -> None:
    """The invocation_hash must equal blake3(tool_name + tool_version + args_json + evidence_hash).

    This is the core §3.1 requirement; the validator must REJECT a mismatched hash.
    """
    from blake3 import blake3 as _b3

    tool_name = "vol3.windows.pslist"
    tool_version = "vol3 2.10.0"
    args = {"argv": ["-f", "/evidence/mem.raw", "windows.pslist"]}
    evidence_hash = "dead" * 16  # 64-char hex
    args_json = json.dumps(args, sort_keys=True)
    expected_hash = _b3(
        (tool_name + tool_version + args_json + evidence_hash).encode()
    ).hexdigest()

    stdout_sha256 = hashlib.sha256(b"output").hexdigest()
    obj = ToolOutput(
        tool_name=tool_name,
        tool_version=tool_version,
        args=args,
        evidence_hash=evidence_hash,
        invocation_hash=expected_hash,
        output_files_sha256={},
        stdout_sha256=stdout_sha256,
    )
    assert obj.invocation_hash == expected_hash


def test_invocation_hash_rejects_tampered_value() -> None:
    """A hash that does not match the computed value must be rejected."""
    payload = _make_tool_output(invocation_hash="0" * 64)
    with pytest.raises(ValidationError):
        ToolOutput(**payload)


def test_invocation_hash_rejects_wrong_args() -> None:
    """Changing args without recomputing the hash must be rejected."""
    from blake3 import blake3 as _b3

    # Build a valid payload with args_a, then swap args to args_b without rehashing.
    tool_name = "vol3.windows.pslist"
    tool_version = "vol3 2.10.0"
    evidence_hash = "a" * 64
    args_a = {"argv": ["-f", "/evidence/mem.raw", "windows.pslist"]}
    args_json_a = json.dumps(args_a, sort_keys=True)
    good_hash = _b3(
        (tool_name + tool_version + args_json_a + evidence_hash).encode()
    ).hexdigest()

    # args_b is different — hash is now stale
    args_b = {"argv": ["-f", "/evidence/OTHER.raw", "windows.pslist"]}
    with pytest.raises(ValidationError):
        ToolOutput(
            tool_name=tool_name,
            tool_version=tool_version,
            args=args_b,
            evidence_hash=evidence_hash,
            invocation_hash=good_hash,
            output_files_sha256={},
            stdout_sha256=hashlib.sha256(b"").hexdigest(),
        )


# ---------------------------------------------------------------------------
# output_files_sha256 — per-output-file hash map (CLAUDE.md §3.1 / NIST SP 800-86 §5.1.2)
# ---------------------------------------------------------------------------

def test_output_files_sha256_accepts_empty_dict() -> None:
    obj = ToolOutput(**_make_tool_output(output_files_sha256={}))
    assert obj.output_files_sha256 == {}


def test_output_files_sha256_accepts_multiple_entries() -> None:
    files = {
        "pslist.csv": "c" * 64,
        "pslist.json": "d" * 64,
    }
    obj = ToolOutput(**_make_tool_output(output_files_sha256=files))
    assert obj.output_files_sha256 == files


# ---------------------------------------------------------------------------
# stdout_sha256 field
# ---------------------------------------------------------------------------

def test_stdout_sha256_round_trips() -> None:
    digest = hashlib.sha256(b"hello world").hexdigest()
    payload = _make_tool_output(stdout_sha256=digest)
    obj = ToolOutput(**payload)
    assert obj.stdout_sha256 == digest


# ---------------------------------------------------------------------------
# Artifact sub-schema
# ---------------------------------------------------------------------------

def test_artifact_fields_present() -> None:
    a = Artifact(**_make_artifact())
    assert a.artifact_id == "01JXXXXXXXXXXXXXXXXXXXXXXX"
    assert a.evidence_path == Path("/evidence/mem.raw")
    assert a.artifact_type == "process"
    assert isinstance(a.raw_fields, dict)


def test_artifact_extraction_confidence_defaults_to_1() -> None:
    a = Artifact(**_make_artifact())
    assert a.extraction_confidence == 1.0


def test_artifact_extraction_confidence_accepts_float() -> None:
    a = Artifact(**_make_artifact(extraction_confidence=0.8))
    assert a.extraction_confidence == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# ToolOutput.parsed_artifacts integration
# ---------------------------------------------------------------------------

def test_tool_output_accepts_parsed_artifacts() -> None:
    artifact = Artifact(**_make_artifact())
    payload = _make_tool_output()
    payload["parsed_artifacts"] = [artifact.model_dump()]
    obj = ToolOutput(**payload)
    assert len(obj.parsed_artifacts) == 1
    assert obj.parsed_artifacts[0].artifact_type == "process"


def test_tool_output_parsed_artifacts_defaults_empty() -> None:
    obj = ToolOutput(**_make_tool_output())
    assert obj.parsed_artifacts == []


# ---------------------------------------------------------------------------
# Optional list fields default to empty lists
# ---------------------------------------------------------------------------

def test_parse_warnings_defaults_empty() -> None:
    obj = ToolOutput(**_make_tool_output())
    assert obj.parse_warnings == []


def test_sanitization_flags_defaults_empty() -> None:
    obj = ToolOutput(**_make_tool_output())
    assert obj.sanitization_flags == []


# ---------------------------------------------------------------------------
# schema_version field (W1.B.12 prep — ToolOutput carries schema_version=1)
# ---------------------------------------------------------------------------

def test_schema_version_defaults_to_1() -> None:
    obj = ToolOutput(**_make_tool_output())
    assert obj.schema_version == 1
