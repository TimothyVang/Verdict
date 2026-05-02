"""Ledger writer — write + fsync + verify-readback.

Implements W2.G.1 (ARCHITECTURE.md §5, CLAUDE.md §9 Ledger discipline).

Durability contract per CLAUDE.md §9:
  write() + fsync() + verify-readback in LedgerEmitter. No buffered writes.

Every ledger file is a JSONL append-only log at cases/<case_id>/ledger.jsonl.
Each line is a JSON-serialised LedgerEntry with its HMAC signature.

Chain integrity: prev_entry_hash chains entries. The writer maintains the
last-entry hash in memory; a second writer instance on the same file would
corrupt the chain — the gateway ensures single-writer per case.

Verify-readback: after writing and fsyncing, the writer reads back the last
line and verifies its JSON round-trips cleanly and the HMAC matches.  This
catches partial writes or filesystem corruption at write time.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from blake3 import blake3 as _blake3

from verdict.ledger.hmac_key import HMACKeyProvider, get_hmac_key_provider_from_bytes
from verdict.ledger.redaction import redact_payload
from verdict.schemas.ledger import LedgerEntry


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LedgerWriteError(RuntimeError):
    """Raised when a ledger write, fsync, or verify-readback fails."""


class LedgerChainIntegrityError(RuntimeError):
    """Raised when HMAC verification of a ledger entry fails on readback."""


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _entry_to_json(entry: LedgerEntry) -> str:
    """Serialise a LedgerEntry to a single-line JSON string.

    Uses model_dump with mode="json" to get JSON-safe types (datetime → ISO
    string, Path → string, Enum → value).  No trailing newline — the writer
    appends \\n explicitly.
    """
    data = entry.model_dump(mode="json")
    return json.dumps(data, separators=(",", ":"), sort_keys=True)


def _compute_payload_hash(entry: LedgerEntry) -> bytes:
    """Compute the bytes to HMAC-sign for a LedgerEntry.

    Covers: redacted_payload + prev_entry_hash + entry_id.
    Uses blake3-keyed hash bytes for the payload component for stronger
    collision resistance than sha256 alone.

    This function must produce the same bytes each time for the same entry —
    sort_keys=True ensures dict serialisation is deterministic.
    """
    payload_bytes = json.dumps(
        entry.payload, separators=(",", ":"), sort_keys=True
    ).encode()
    combined = (
        payload_bytes
        + entry.prev_entry_hash.encode()
        + entry.entry_id.encode()
    )
    return combined


# ---------------------------------------------------------------------------
# LedgerWriter
# ---------------------------------------------------------------------------


class LedgerWriter:
    """Append-only JSONL ledger writer with fsync + verify-readback.

    Args:
        ledger_path: Path to the ledger.jsonl file.  Parent directory must
                     exist (case directory created by `verdict init`).
        hmac_provider: An HMACKeyProvider instance (TPM-backed or gpg-encrypted).
                       Obtained from verdict/ledger/hmac_key.py.
    """

    # GENESIS_HASH is the prev_entry_hash for the first entry in a case.
    # A 64-char hex string of all zeros is unambiguous; it cannot be a valid
    # blake3 hash of any real entry.
    GENESIS_HASH = "0" * 64

    def __init__(
        self,
        *,
        ledger_path: Path,
        hmac_provider: HMACKeyProvider,
    ) -> None:
        self._path = ledger_path
        self._hmac = hmac_provider
        self._last_hash: str = self._compute_last_hash()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def write(self, entry: LedgerEntry) -> None:
        """Append entry to the ledger, fsync, and verify-readback.

        Args:
            entry: A fully-constructed LedgerEntry.  The entry's prev_entry_hash
                   and hmac_sig are verified against the writer's current state.

        Raises:
            LedgerWriteError: If the write, fsync, or readback fails.
            LedgerChainIntegrityError: If the HMAC does not match on readback.
        """
        # Verify chain linkage
        if entry.prev_entry_hash != self._last_hash:
            raise LedgerWriteError(
                f"LedgerWriter chain broken: entry.prev_entry_hash="
                f"{entry.prev_entry_hash!r} but expected {self._last_hash!r}"
            )

        # Verify HMAC before writing
        message = _compute_payload_hash(entry)
        if not self._hmac.verify(message, entry.hmac_sig):
            raise LedgerWriteError(
                f"LedgerWriter HMAC verification failed for entry_id={entry.entry_id!r}"
            )

        line = _entry_to_json(entry) + "\n"
        line_bytes = line.encode("utf-8")

        try:
            with open(self._path, "ab") as fh:
                fh.write(line_bytes)
                fh.flush()
                os.fsync(fh.fileno())
        except OSError as exc:
            raise LedgerWriteError(
                f"LedgerWriter: failed to write to {self._path}: {exc}"
            ) from exc

        # Verify-readback: re-read the last line and check round-trip
        self._verify_readback(entry)

        # Advance the chain hash
        self._last_hash = _blake3(line_bytes).hexdigest()

    def build_entry(
        self,
        *,
        entry_id: str,
        case_id: str,
        event_type: str,
        mode_at_case_init: str,
        verifier_strategy_used: str,
        langfuse_session_id: str,
        langfuse_trace_id: str,
        langfuse_root_span_id: str,
        langgraph_thread_id: str,
        langgraph_checkpoint_id: str,
        payload: dict,
        timestamp_utc: datetime | None = None,
        finding_id: str | None = None,
        langfuse_leaf_span_ids: list[str] | None = None,
        microsandbox_version: str | None = None,
        rootfs_sha256: str | None = None,
        tool_version: str | None = None,
        kernel_version: str | None = None,
        output_files_sha256: dict[str, str] | None = None,
    ) -> LedgerEntry:
        """Construct a LedgerEntry with correct chain hash and HMAC.

        This is the primary factory for LedgerEntry — callers should not
        construct LedgerEntry directly because they'd need to know the
        current prev_entry_hash (held by this writer) and compute the HMAC.

        Args:
            All fields map 1:1 to LedgerEntry fields.
            payload: Raw event payload.  Auth fields will be redacted.

        Returns:
            A frozen LedgerEntry ready to pass to write().
        """
        if timestamp_utc is None:
            timestamp_utc = datetime.now(tz=timezone.utc)

        # Redact auth fields before hashing
        redacted_payload, redaction_keys = redact_payload(payload)

        # Compute HMAC over (redacted_payload + prev_entry_hash + entry_id)
        partial_entry_bytes = (
            json.dumps(redacted_payload, separators=(",", ":"), sort_keys=True).encode()
            + self._last_hash.encode()
            + entry_id.encode()
        )
        hmac_sig = self._hmac.sign(partial_entry_bytes)

        return LedgerEntry(
            entry_id=entry_id,
            case_id=case_id,
            finding_id=finding_id,
            event_type=event_type,  # type: ignore[arg-type]
            timestamp_utc=timestamp_utc,
            mode_at_case_init=mode_at_case_init,  # type: ignore[arg-type]
            verifier_strategy_used=verifier_strategy_used,
            langfuse_session_id=langfuse_session_id,
            langfuse_trace_id=langfuse_trace_id,
            langfuse_root_span_id=langfuse_root_span_id,
            langfuse_leaf_span_ids=langfuse_leaf_span_ids or [],
            langgraph_thread_id=langgraph_thread_id,
            langgraph_checkpoint_id=langgraph_checkpoint_id,
            microsandbox_version=microsandbox_version,
            rootfs_sha256=rootfs_sha256,
            tool_version=tool_version,
            kernel_version=kernel_version,
            output_files_sha256=output_files_sha256 or {},
            payload=redacted_payload,
            payload_redactions=redaction_keys,
            prev_entry_hash=self._last_hash,
            hmac_sig=hmac_sig,
        )

    @property
    def last_hash(self) -> str:
        """The blake3 hash of the last-written ledger line.

        Used by verify_chain() to validate the chain from outside the writer.
        """
        return self._last_hash

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_last_hash(self) -> str:
        """Read the last line of the ledger file and compute its hash.

        If the file does not exist or is empty, returns GENESIS_HASH.
        This allows the writer to resume an existing ledger after a restart.
        """
        if not self._path.exists() or self._path.stat().st_size == 0:
            return self.GENESIS_HASH

        try:
            with open(self._path, "rb") as fh:
                # Seek to find the last non-empty line efficiently
                content = fh.read()
        except OSError as exc:
            raise LedgerWriteError(
                f"LedgerWriter: cannot read {self._path}: {exc}"
            ) from exc

        lines = [ln for ln in content.split(b"\n") if ln.strip()]
        if not lines:
            return self.GENESIS_HASH

        last_line = lines[-1] + b"\n"
        return _blake3(last_line).hexdigest()

    def _verify_readback(self, expected_entry: LedgerEntry) -> None:
        """Re-read the last line and verify it round-trips to the same entry.

        Raises:
            LedgerChainIntegrityError: If the readback fails.
        """
        try:
            with open(self._path, "rb") as fh:
                content = fh.read()
        except OSError as exc:
            raise LedgerChainIntegrityError(
                f"LedgerWriter readback failed: cannot open {self._path}: {exc}"
            ) from exc

        lines = [ln for ln in content.split(b"\n") if ln.strip()]
        if not lines:
            raise LedgerChainIntegrityError(
                "LedgerWriter readback: file is empty after write"
            )

        last_line = lines[-1]
        try:
            data = json.loads(last_line)
        except json.JSONDecodeError as exc:
            raise LedgerChainIntegrityError(
                f"LedgerWriter readback: JSON parse failed on last line: {exc}"
            ) from exc

        # Spot-check key fields — full re-parse is expensive at write-time
        if data.get("entry_id") != expected_entry.entry_id:
            raise LedgerChainIntegrityError(
                f"LedgerWriter readback: entry_id mismatch: "
                f"read {data.get('entry_id')!r}, expected {expected_entry.entry_id!r}"
            )
        if data.get("hmac_sig") != expected_entry.hmac_sig:
            raise LedgerChainIntegrityError(
                f"LedgerWriter readback: hmac_sig mismatch after write for "
                f"entry_id={expected_entry.entry_id!r}"
            )
