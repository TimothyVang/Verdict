"""Planner CoT capture — W2.D.3.

Extracts, compresses, hashes, and stores the planner's chain-of-thought
(CoT) reasoning in the ledger.  Attaches the first 8 KB to a Langfuse
span attribute for interactive trace inspection.

Two CoT formats (ARCHITECTURE.md §9 + BUILD_PLAN W2.D.3.b):

- **Cloud** (Claude via Agent SDK): the CoT is the model's full response
  text before any tool calls or structured JSON output.  Claude does NOT
  wrap reasoning in ``<think>`` tags.
- **Air-gap** (Qwen3 in thinking mode): CoT appears inside
  ``<think>…</think>`` tags in the raw model output.  GLM-4.5-Air (verifier
  only) may or may not use ``<think>`` tags; absent tags → passthrough.

Ledger storage:
  ``LedgerEntry(event_type="planner_cot")`` with payload:
  - ``"cot_gzip"``: base64-encoded gzip of the UTF-8 CoT text.
  - ``"cot_gzip_sha256"``: SHA-256 of the *compressed* bytes (per
    ARCHITECTURE.md §5 per-output-file hash discipline — hash the bytes
    you store, not the bytes you discard).

Langfuse span:
  ``CotCaptureResult.langfuse_span_payload`` = first 8192 bytes of the
  original (uncompressed) CoT text.  ARCHITECTURE.md §9 specifies "first
  8KB to Langfuse span attribute".  The live Langfuse attach call is not
  wired here — it lives in the graph node that wraps this function.

CLAUDE.md §3.9 — CoT never leaves the box in air-gap mode; Langfuse must
  be self-hosted on the air-gap side.  This module is side-effect-free
  on the Langfuse wire.
CLAUDE.md §3.10 — no mocks; pure Python logic is real; live Langfuse API
  calls raise NotImplementedError per §3.10.
"""

from __future__ import annotations

import base64
import dataclasses
import gzip
import hashlib
import re

from verdict.ledger.memory import InMemoryLedger, Ledger
from verdict.schemas.ledger import Mode

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Maximum bytes attached to a Langfuse span attribute for CoT preview.
#: ARCHITECTURE.md §9: "first 8KB to Langfuse span attribute".
LANGFUSE_SPAN_MAX_BYTES: int = 8192

#: Qwen3 <think>…</think> pattern.  Greedy to capture full block (including
#: any nested malformed tags).  re.DOTALL because reasoning spans multiple
#: lines.
_THINK_RE: re.Pattern[str] = re.compile(
    r"<think>(.*)</think>", re.DOTALL | re.IGNORECASE
)


# ---------------------------------------------------------------------------
# CotCaptureResult — returned by capture_planner_cot
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CotCaptureResult:
    """Result of a single CoT capture operation.

    Attributes
    ----------
    ledger_entry_id:
        The ``entry_id`` of the ``planner_cot`` ``LedgerEntry`` written.
    langfuse_span_payload:
        First 8192 bytes of the original (uncompressed) CoT text.  The
        graph node attaches this to the Langfuse span attribute.  Empty
        string if the original CoT was empty.
    cot_gzip_sha256:
        SHA-256 of the gzip-compressed CoT bytes.  Matches
        ``ledger_entry.payload["cot_gzip_sha256"]``.
    """

    ledger_entry_id: str
    langfuse_span_payload: str
    cot_gzip_sha256: str


# ---------------------------------------------------------------------------
# extract_cot — strip <think> tags for air-gap models
# ---------------------------------------------------------------------------


def extract_cot(response_text: str, *, mode: str) -> str:
    """Extract the reasoning CoT from a model response.

    Parameters
    ----------
    response_text:
        Raw model output (cloud: full text; airgap: may have ``<think>``).
    mode:
        ``"cloud"`` — return ``response_text`` as-is (Claude SDK responses
        don't use ``<think>`` tags).
        ``"airgap"`` — strip Qwen3 ``<think>…</think>`` wrapper and return
        the inner reasoning.  If no tags are present, return text as-is.

    Returns
    -------
    str
        Extracted reasoning text.
    """
    if mode == "cloud":
        return response_text

    # air-gap: try to extract <think> block.
    # Greedy match captures from first <think> to last </think>, which means
    # nested <think> tags end up in group(1).  Strip any residual tags so
    # the result is clean reasoning text only.
    m = _THINK_RE.search(response_text)
    if m:
        inner = m.group(1).strip()
        # Remove any nested <think> / </think> tags left by greedy match
        inner = re.sub(r"</?think>", "", inner, flags=re.IGNORECASE).strip()
        return inner

    # No <think> tags found (non-thinking mode / GLM-4.5-Air passthrough)
    return response_text


# ---------------------------------------------------------------------------
# capture_planner_cot — main entry point
# ---------------------------------------------------------------------------


def capture_planner_cot(
    cot_text: str,
    *,
    case_id: str,
    ledger: Ledger | None = None,
    mode: Mode = "cloud",
) -> CotCaptureResult:
    """Compress, hash, and store the planner CoT in the ledger.

    Steps:
    1. gzip-compress the CoT text (UTF-8).
    2. SHA-256 the compressed bytes.
    3. base64-encode the compressed bytes for JSON-safe ledger storage.
    4. Write a ``planner_cot`` ``LedgerEntry`` with the payload.
    5. Return a ``CotCaptureResult`` with the entry id, the first 8KB
       of the original text, and the hash.

    Parameters
    ----------
    cot_text:
        The reasoning chain to capture.  May be empty string (safe to
        call; writes an entry with an empty CoT).
    case_id:
        The case this CoT belongs to.
    ledger:
        Ledger to write the ``planner_cot`` event to.  Defaults to a
        fresh ``InMemoryLedger`` when not supplied.
    mode:
        Mode at case_init — propagated to the ledger entry.

    Returns
    -------
    CotCaptureResult
        Contains ``ledger_entry_id``, ``langfuse_span_payload``, and
        ``cot_gzip_sha256``.
    """
    active_ledger: Ledger = ledger if ledger is not None else InMemoryLedger()

    compressed = gzip.compress(cot_text.encode("utf-8"), compresslevel=9)
    cot_gzip_sha256 = hashlib.sha256(compressed).hexdigest()
    cot_gzip_b64 = base64.b64encode(compressed).decode("ascii")

    langfuse_span_payload = cot_text[:LANGFUSE_SPAN_MAX_BYTES]

    entry = active_ledger.write(
        event_type="planner_cot",
        case_id=case_id,
        payload={
            "cot_gzip": cot_gzip_b64,
            "cot_gzip_sha256": cot_gzip_sha256,
            "cot_length_chars": len(cot_text),
            "langfuse_span_bytes": len(langfuse_span_payload),
        },
        mode=mode,
    )

    return CotCaptureResult(
        ledger_entry_id=entry.entry_id,
        langfuse_span_payload=langfuse_span_payload,
        cot_gzip_sha256=cot_gzip_sha256,
    )
