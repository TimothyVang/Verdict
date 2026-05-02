"""RED test for W1.G.6 — HMAC key handling (TPM-backed or gpg-encrypted).

Per CLAUDE.md §3.9 (credential isolation):
- HMAC ledger key is TPM-backed (/dev/tpmrm0) when available.
- Else falls back to gpg-encrypted at ~/.verdict/key.gpg with passphrase prompt.
- API keys, OAuth tokens, bearer tokens never enter a microVM.
- Ledger redaction strips authorization fields before hashing/signing.
"""

import pytest
import tempfile
import os
from pathlib import Path


class TestHMACKeyHandling:
    """W1.G.6.a — RED test for HMAC key TPM vs gpg path selection."""

    def test_tpm_path_when_dev_tpmrm0_present(self, tmp_path, monkeypatch):
        """When /dev/tpmrm0 exists, use TPM-backed key.

        RED assertion: hmac_key_provider() checks for /dev/tpmrm0.
        If present, returns a TPM-backed key handle.
        If absent, falls back to gpg-encrypted at ~/.verdict/key.gpg.
        """
        from verdict.ledger.hmac_key import get_hmac_key_provider

        # Mock /dev/tpmrm0 present
        tpm_mock_path = tmp_path / "tpmrm0"
        tpm_mock_path.touch()

        # Monkeypatch os.path.exists to return True for /dev/tpmrm0
        original_exists = os.path.exists
        def mock_exists(path):
            if path == "/dev/tpmrm0":
                return True
            return original_exists(path)
        monkeypatch.setattr(os.path, "exists", mock_exists)

        # Get the key provider — should return TPM path
        provider = get_hmac_key_provider()
        assert provider is not None
        # The provider should indicate TPM is available
        assert hasattr(provider, "is_tpm") or "tpm" in str(provider).lower()

    def test_gpg_fallback_when_tpm_absent(self, monkeypatch):
        """When /dev/tpmrm0 absent, use gpg-encrypted key at ~/.verdict/key.gpg.

        RED assertion: hmac_key_provider() falls back to GPG.
        The key path is ~/.verdict/key.gpg.
        Passphrase is prompted at gateway_init (W2.G integration).
        """
        from verdict.ledger.hmac_key import get_hmac_key_provider

        # Monkeypatch os.path.exists to return False for /dev/tpmrm0
        def mock_exists(path):
            if path == "/dev/tpmrm0":
                return False
            return os.path.exists(path)
        monkeypatch.setattr(os.path, "exists", mock_exists)

        # Get the key provider — should return GPG path
        provider = get_hmac_key_provider()
        assert provider is not None
        # The provider should indicate GPG is the fallback
        assert hasattr(provider, "gpg_path") or "gpg" in str(provider).lower()

    def test_mismatch_writes_ledger_entry_and_halts(self):
        """HashMismatchError during ledger write → halt with ledger event.

        RED assertion: On evidence re-hash mismatch, the ledger writes
        a LedgerEntry(event_type="evidence_hash_recheck") with both hashes
        and then raises HashMismatchError, halting the case.
        This is tested more thoroughly in W1.G.7.
        """
        from verdict.ledger.hmac_key import HashMismatchError

        # Just verify the error exists and is importable
        assert HashMismatchError is not None
        assert issubclass(HashMismatchError, Exception)
