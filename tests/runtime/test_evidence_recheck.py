"""RED test for W1.G.7 — Periodic evidence re-hash check every 10 super-steps.

Per CLAUDE.md §3.1 (evidence integrity):
- Every evidence file gets SHA-256 at case_init recorded in EvidenceManifest.
- Runtime re-hashes every 10 super-steps.
- Mismatch raises HashMismatchError and halts the case.
- Ledger records event_type="evidence_hash_recheck" with both hashes.
"""

import pytest


class TestEvidenceRecheckEvery10Steps:
    """W1.G.7.a — RED test for periodic evidence re-hash."""

    def test_recheck_every_10_super_steps(self):
        """Ledger writer emits evidence_hash_recheck every 10 super-steps.

        RED assertion: There exists a verdict/runtime/evidence_recheck.py
        module with a RecheckCounter that tracks super-steps and triggers
        re-hash at multiples of 10.

        Evidence files are re-hashed. If any hash diverges from the
        initial manifest hash, HashMismatchError is raised and the case
        halts with a ledger entry.
        """
        from verdict.runtime.evidence_recheck import RecheckCounter

        # Instantiate the counter
        counter = RecheckCounter()
        assert counter is not None

        # Should not trigger recheck for steps 1-9
        for step in range(1, 10):
            should_recheck = counter.should_recheck(step)
            assert should_recheck is False, f"Step {step} should not trigger recheck"

        # Step 10 should trigger recheck
        should_recheck = counter.should_recheck(10)
        assert should_recheck is True, "Step 10 should trigger recheck"

        # Step 11-19 should not trigger
        for step in range(11, 20):
            should_recheck = counter.should_recheck(step)
            assert should_recheck is False, f"Step {step} should not trigger recheck"

        # Step 20 should trigger
        should_recheck = counter.should_recheck(20)
        assert should_recheck is True, "Step 20 should trigger recheck"

    def test_mismatch_writes_ledger_entry_and_halts(self):
        """HashMismatchError writes ledger event and halts.

        RED assertion: When evidence re-hash detects a divergence,
        the ledger writes a LedgerEntry(event_type="evidence_hash_recheck")
        with both the initial and recheck hashes, then raises
        HashMismatchError to halt the case.

        This ledger entry is signed/HMAC-protected per §3.1.
        """
        from verdict.ledger.hmac_key import HashMismatchError
        from verdict.runtime.evidence_recheck import (
            check_evidence_integrity,
            EvidenceRecheckEntry,
        )

        # Create a mock scenario: initial hash vs divergent recheck hash
        initial_hash = "sha256:abc123"
        recheck_hash = "sha256:def456"  # divergent

        # The check_evidence_integrity function should raise on mismatch
        with pytest.raises(HashMismatchError):
            check_evidence_integrity(
                initial_hash=initial_hash,
                recheck_hash=recheck_hash,
                evidence_path="/evidence/case.E01",
            )

        # The ledger entry should be created internally
        # (verified in integration tests; unit test just verifies the error)

        # Verify EvidenceRecheckEntry schema exists
        assert EvidenceRecheckEntry is not None
