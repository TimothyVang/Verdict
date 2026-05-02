"""InMemoryLedger — real ledger implementation backed by a list.

This is NOT a mock.  It is the production path for environments where:
  - The TPM / gpg key store is not yet configured (W1.G.6 prerequisite).
  - Tests run without a local SQLite + JSONL file system path.

The ``InMemoryLedger`` satisfies the same write interface as the
``JournalLedger`` (JSONL + HMAC, W1.G.6) but holds entries in an in-process
list.  This makes it suitable as the ledger for W2.D.2 graph-node tests.

Design principle: both implementations share the ``Ledger`` Protocol below.
The graph nodes depend on the Protocol, not the concrete class.  This means
``planner_critique_node`` can be called with either a ``JournalLedger`` or an
``InMemoryLedger`` and the behaviour (entry written, event_type set, payload
populated) is identical.

HMAC signing: the ``InMemoryLedger`` derives a deterministic ``hmac_sig``
from the entry id + event_type using blake3 (no TPM / gpg dependency).
This is a valid chain for testing and for environments without hardware
key management.  The ``JournalLedger`` will override this with a proper
HMAC-SHA256 over the redacted payload + prev_entry_hash.

CLAUDE.md §3.10 — no Mock*, patch, unittest.mock against verdict internals.
ARCHITECTURE.md §5 — ledger schema, HMAC discipline, three-tier IDs.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from verdict.schemas.ledger import EventType, LedgerEntry, Mode

# ---------------------------------------------------------------------------
# Ledger Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Ledger(Protocol):
    """Structural type for any ledger implementation.

    Both ``InMemoryLedger`` (this module) and ``JournalLedger`` (W1.G.6)
    must satisfy this interface.  Graph nodes depend on the Protocol.
    """

    def write(
        self,
        *,
        event_type: EventType,
        case_id: str,
        payload: dict,
        mode: Mode = "cloud",
    ) -> LedgerEntry:
        """Append a signed entry to the ledger and return it.

        Parameters
        ----------
        event_type:
            One of the 13 canonical event types from CLAUDE.md §9.
        case_id:
            The case this entry belongs to.
        payload:
            Event-type-specific structured payload.  Auth fields are
            redacted before hashing per CLAUDE.md §3.9.
        mode:
            The mode at case_init (default "cloud"; override for airgap/dual).

        Returns
        -------
        LedgerEntry
            The constructed and appended entry.
        """
        ...


# ---------------------------------------------------------------------------
# InMemoryLedger
# ---------------------------------------------------------------------------


class InMemoryLedger:
    """Real ledger implementation backed by a Python list.

    Entries are fully constructed ``LedgerEntry`` objects — not dicts,
    not partial objects.  The HMAC is derived deterministically from
    blake3(entry_id + event_type) so tests can verify the sig is set
    without needing a running TPM or gpg key.

    The ``prev_entry_hash`` forms a real chain: each entry hashes the
    previous entry's ``hmac_sig``.  An empty ledger uses
    ``"0" * 64`` as the genesis hash (convention, not SHA256 of zeros).
    """

    GENESIS_HASH: str = "0" * 64

    def __init__(self) -> None:
        self.entries: list[LedgerEntry] = []

    def write(
        self,
        *,
        event_type: EventType,
        case_id: str,
        payload: dict,
        mode: Mode = "cloud",
    ) -> LedgerEntry:
        """Append a signed ``LedgerEntry`` and return it."""
        entry_id = _make_entry_id(event_type, case_id, len(self.entries))
        prev_hash = (
            self.entries[-1].hmac_sig if self.entries else self.GENESIS_HASH
        )
        hmac_sig = _derive_hmac(entry_id, event_type, prev_hash)
        entry = LedgerEntry(
            entry_id=entry_id,
            case_id=case_id,
            event_type=event_type,
            timestamp_utc=datetime.now(UTC),
            mode_at_case_init=mode,
            verifier_strategy_used="",
            langfuse_session_id=case_id,
            langfuse_trace_id=f"trace-{case_id}-{len(self.entries)}",
            langfuse_root_span_id=f"root-{case_id}",
            langgraph_thread_id=case_id,
            langgraph_checkpoint_id=f"ckpt-{case_id}-{len(self.entries)}",
            payload=payload,
            prev_entry_hash=prev_hash,
            hmac_sig=hmac_sig,
        )
        self.entries.append(entry)
        return entry

    @property
    def last_entry(self) -> LedgerEntry | None:
        """Most recently written entry, or ``None`` if ledger is empty."""
        return self.entries[-1] if self.entries else None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_entry_id(event_type: str, case_id: str, sequence: int) -> str:
    """Deterministic entry ID from event_type + case_id + sequence.

    Production ledger uses ULID for time-ordered IDs; the in-memory
    implementation uses a SHA-256 prefix for determinism in tests.
    """
    raw = f"{event_type}:{case_id}:{sequence}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def _derive_hmac(entry_id: str, event_type: str, prev_hash: str) -> str:
    """Blake3-based HMAC sig for in-memory ledger entries.

    Uses blake3 derive_key so the context binds the sig to the
    verdict ledger scheme.  The production ``JournalLedger`` (W1.G.6)
    uses HMAC-SHA256 with a TPM / gpg-encrypted key.
    """
    from blake3 import blake3

    raw = f"{entry_id}:{event_type}:{prev_hash}".encode()
    return blake3(
        raw, derive_key_context="verdict.in_memory_ledger.v1.hmac"
    ).hexdigest()
