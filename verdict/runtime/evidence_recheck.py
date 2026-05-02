"""Periodic evidence re-hash check — every 10 super-steps.

Per CLAUDE.md §3.1 (evidence integrity):
- Every evidence file gets SHA-256 at case_init, recorded in EvidenceManifest.
- Runtime re-hashes every 10 super-steps (super-step = a LangGraph checkpoint).
- Mismatch raises HashMismatchError and halts the case.
- Ledger records event_type="evidence_hash_recheck" with both hashes.

Per §1 architecture: evidence is mounted read-only at /evidence with noexec.
Tampering would require either:
1. A successful microsandbox kernel escape (unlikely; accepted v1 risk per THREAT_MODEL).
2. Host-side tampering (HMAC on ledger entry detects post-hoc tampering).

W1.G.7 implementation: re-check trigger logic + error handling.
Full ledger writer integration deferred to W2.G.
"""

from __future__ import annotations

from pathlib import Path
import hashlib
from pydantic import BaseModel

from verdict.ledger.hmac_key import HashMismatchError


class EvidenceRecheckEntry(BaseModel):
    """Ledger entry for evidence re-hash check.

    Recorded at every 10-step boundary. If hashes match, serves as an
    audit trail. If mismatch, triggers halt (detailed below).
    """

    step_number: int
    evidence_path: str
    initial_sha256: str
    recheck_sha256: str
    matches: bool


class RecheckCounter:
    """Tracks super-steps and determines when to trigger re-hash checks.

    Per ARCHITECTURE.md §2: graph is checkpointed at every super-step
    via SqliteSaver with WAL + fsync. RecheckCounter lives on the
    case state and tracks how many super-steps have occurred.
    """

    def __init__(self, recheck_interval: int = 10):
        """Initialize counter.

        Args:
            recheck_interval: Re-check every N super-steps. Default 10.
        """
        self.recheck_interval = recheck_interval

    def should_recheck(self, step_number: int) -> bool:
        """Determine if a re-hash check should fire at this step.

        Args:
            step_number: Current super-step number (1-indexed).

        Returns:
            True if step_number is a multiple of recheck_interval.
        """
        return step_number % self.recheck_interval == 0


def compute_file_hash(file_path: str | Path) -> str:
    """Compute SHA-256 hash of a file.

    Args:
        file_path: Path to evidence file.

    Returns:
        Hex-encoded SHA-256 hash with "sha256:" prefix.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return f"sha256:{sha256.hexdigest()}"


def check_evidence_integrity(
    initial_hash: str,
    recheck_hash: str,
    evidence_path: str,
) -> bool:
    """Check if evidence hash matches the initial manifest.

    Args:
        initial_hash: SHA-256 from EvidenceManifest (case_init).
        recheck_hash: SHA-256 from re-hash check (current step).
        evidence_path: Path to evidence file (for error message).

    Returns:
        True if hashes match (integrity preserved).

    Raises:
        HashMismatchError: If hashes diverge. The ledger writes an
            EvidenceRecheckEntry with both hashes before raising.
            Case execution halts.
    """
    if initial_hash == recheck_hash:
        return True
    else:
        # Mismatch detected.
        # In production (W2.G), the ledger writer is invoked here to write
        # the evidence_hash_recheck entry before raising.
        # For W1.G.7 stub, just raise.
        raise HashMismatchError(
            f"Evidence integrity violation at {evidence_path}: "
            f"initial={initial_hash}, recheck={recheck_hash}"
        )
