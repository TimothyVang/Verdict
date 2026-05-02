"""W2.D.3 — Planner CoT capture: gzipped ledger entry + 8KB Langfuse span.

Tests per BUILD_PLAN W2.D.3.a:

1. ``test_gzipped_cot_in_ledger`` — after ``capture_planner_cot(cot_text, ledger)``
   the ledger contains a ``planner_cot`` entry with:
   - ``payload["cot_gzip"]`` — base64-encoded gzip of the CoT text.
   - ``payload["cot_gzip_sha256"]`` — SHA-256 of the compressed bytes.
   - Decompressing ``base64.b64decode(payload["cot_gzip"])`` yields the
     original CoT text.

2. ``test_8kb_attached_to_langfuse_span`` — ``capture_planner_cot`` returns
   a ``CotCaptureResult`` whose ``langfuse_span_payload`` field contains at
   most 8192 bytes of the original CoT text (first 8 KB, not gzipped).

Supporting tests:
- ``test_extract_cloud_cot_from_response_text`` — ``extract_cot(response_text, mode="cloud")``
  returns the full response text (no ``<think>`` stripping for cloud).
- ``test_extract_airgap_cot_strips_think_tags`` — ``extract_cot(text, mode="airgap")``
  strips Qwen3 ``<think>…</think>`` wrapper and returns inner content.
- ``test_extract_airgap_cot_passthrough_if_no_think_tags`` — no ``<think>`` →
  return text as-is (Qwen3 non-thinking mode / GLM-4.5).
- ``test_cot_sha256_is_over_compressed_bytes`` — hash is computed over the
  gzip bytes, not the original text (matches ARCHITECTURE.md §5 discipline).

ARCHITECTURE.md §9 — "planner_cot" is one of the 13 canonical event types.
CLAUDE.md §3.9 — CoT capture does NOT leak to Langfuse unless self-hosted
  (air-gap side CoT never leaves the box).  The span payload is advisory —
  it flows only when Langfuse is reachable; the ledger entry is mandatory.
CLAUDE.md §3.10 — no mocks; Langfuse attach raises NotImplementedError for
  live API calls; extraction + gzip + hash are pure Python.
"""

from __future__ import annotations

import base64
import gzip
import hashlib

from verdict.ledger.memory import InMemoryLedger
from verdict.planning.cot_capture import CotCaptureResult, capture_planner_cot, extract_cot

# ---------------------------------------------------------------------------
# W2.D.3 — CoT extraction tests
# ---------------------------------------------------------------------------

_SAMPLE_COT = (
    "Let me think through this step by step.\n"
    "First I note the memory image has Windows 10 headers.\n"
    "pslist shows 45 processes, psscan shows 47 — DKOM delta = 2 hidden PIDs.\n"
    "This strongly suggests T1014 (Rootkit) via EPROCESS unlinking.\n"
    "I should run malfind on the hidden PIDs to look for process hollowing.\n"
    "No evidence of lateral movement artifacts yet — network logs are clean.\n"
)

_SAMPLE_THINK_WRAPPED = (
    "<think>\n"
    "I am analyzing the Windows memory image.\n"
    "The psscan / pslist delta indicates DKOM activity.\n"
    "Hypothesis H1 (T1014) looks strong.\n"
    "</think>\n"
    "Based on my analysis, I recommend the following investigation plan..."
)


def test_extract_cloud_cot_returns_full_text() -> None:
    """extract_cot(text, mode='cloud') returns the full response text.
    Cloud (Claude) does not wrap reasoning in <think> tags.
    """
    result = extract_cot(_SAMPLE_COT, mode="cloud")
    assert result == _SAMPLE_COT


def test_extract_airgap_cot_strips_think_tags() -> None:
    """extract_cot(text, mode='airgap') strips Qwen3 <think>…</think> wrapper.
    The returned text is the inner reasoning content, not the outer response.
    """
    result = extract_cot(_SAMPLE_THINK_WRAPPED, mode="airgap")
    assert "<think>" not in result
    assert "</think>" not in result
    assert "DKOM activity" in result
    # The outer response text should NOT be included
    assert "Based on my analysis" not in result


def test_extract_airgap_cot_passthrough_if_no_think_tags() -> None:
    """If no <think> tags are present (non-thinking mode), text passes through."""
    plain_text = "The evidence summary indicates a ransomware incident."
    result = extract_cot(plain_text, mode="airgap")
    assert result == plain_text


def test_extract_cloud_cot_empty_string() -> None:
    """extract_cot handles empty string without error."""
    result = extract_cot("", mode="cloud")
    assert result == ""


def test_extract_airgap_cot_nested_think_uses_innermost() -> None:
    """Malformed nested <think> tags — extract_cot uses first open to last close."""
    nested = "<think>outer<think>inner</think></think>response"
    result = extract_cot(nested, mode="airgap")
    # Should extract from first <think> to last </think>
    assert "<think>" not in result
    assert "</think>" not in result


# ---------------------------------------------------------------------------
# W2.D.3 — gzip + hash tests
# ---------------------------------------------------------------------------


def test_gzipped_cot_in_ledger() -> None:
    """After capture_planner_cot, the ledger has a planner_cot entry with:
    - payload["cot_gzip"]: base64-encoded gzip of cot_text
    - payload["cot_gzip_sha256"]: SHA-256 of the compressed bytes
    Decompressing cot_gzip yields the original text.
    """
    ledger = InMemoryLedger()
    capture_planner_cot(
        cot_text=_SAMPLE_COT,
        case_id="case-w2d3-001",
        ledger=ledger,
    )
    assert len(ledger.entries) == 1
    entry = ledger.entries[0]
    assert entry.event_type == "planner_cot"
    assert entry.case_id == "case-w2d3-001"
    assert "cot_gzip" in entry.payload
    assert "cot_gzip_sha256" in entry.payload

    # Decompress and verify round-trip
    compressed = base64.b64decode(entry.payload["cot_gzip"])
    recovered = gzip.decompress(compressed).decode("utf-8")
    assert recovered == _SAMPLE_COT

    # Verify hash is over compressed bytes
    expected_hash = hashlib.sha256(compressed).hexdigest()
    assert entry.payload["cot_gzip_sha256"] == expected_hash


def test_cot_sha256_is_over_compressed_bytes() -> None:
    """The cot_gzip_sha256 is SHA-256 over the gzip-compressed bytes,
    not over the original text (ARCHITECTURE.md §5 discipline).
    """
    ledger = InMemoryLedger()
    cot_text = "step 1: examine prefetch. step 2: cross-check amcache."
    capture_planner_cot(cot_text=cot_text, case_id="case-hash-check", ledger=ledger)
    entry = ledger.entries[0]

    compressed = base64.b64decode(entry.payload["cot_gzip"])
    hash_of_compressed = hashlib.sha256(compressed).hexdigest()
    hash_of_original = hashlib.sha256(cot_text.encode()).hexdigest()

    assert entry.payload["cot_gzip_sha256"] == hash_of_compressed
    assert entry.payload["cot_gzip_sha256"] != hash_of_original


def test_cot_capture_result_8kb_span_payload() -> None:
    """capture_planner_cot returns CotCaptureResult.langfuse_span_payload
    containing at most 8192 bytes of the original CoT (first 8KB, uncompressed).
    """
    long_cot = "A" * 20_000  # 20 KB of text
    ledger = InMemoryLedger()
    result = capture_planner_cot(
        cot_text=long_cot,
        case_id="case-8kb",
        ledger=ledger,
    )
    assert isinstance(result, CotCaptureResult)
    span_bytes = result.langfuse_span_payload.encode("utf-8")
    assert len(span_bytes) <= 8192, (
        f"langfuse_span_payload must be ≤8192 bytes, got {len(span_bytes)}"
    )
    # Must be the START of the CoT, not a random slice
    assert result.langfuse_span_payload == long_cot[:8192]


def test_cot_capture_short_cot_not_truncated() -> None:
    """Short CoT (< 8KB) is not truncated in langfuse_span_payload."""
    short_cot = "The evidence is consistent with T1014."
    ledger = InMemoryLedger()
    result = capture_planner_cot(
        cot_text=short_cot,
        case_id="case-short",
        ledger=ledger,
    )
    assert result.langfuse_span_payload == short_cot


def test_cot_capture_result_has_entry_id() -> None:
    """CotCaptureResult.ledger_entry_id matches the written ledger entry."""
    ledger = InMemoryLedger()
    result = capture_planner_cot(
        cot_text=_SAMPLE_COT,
        case_id="case-entry-id",
        ledger=ledger,
    )
    assert result.ledger_entry_id == ledger.entries[0].entry_id


def test_8kb_attached_to_langfuse_span() -> None:
    """The CotCaptureResult.langfuse_span_payload is the first 8KB of
    the original (uncompressed) CoT text.  This is what the graph node
    attaches to the Langfuse span attribute.
    """
    cot = "X" * 16_384  # 16 KB
    ledger = InMemoryLedger()
    result = capture_planner_cot(cot_text=cot, case_id="case-langfuse", ledger=ledger)
    assert len(result.langfuse_span_payload) == 8192
    assert result.langfuse_span_payload == "X" * 8192
