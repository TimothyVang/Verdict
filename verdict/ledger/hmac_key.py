"""HMAC key handling — TPM-backed or gpg-encrypted.

Per CLAUDE.md §3.9 (credential isolation):
- HMAC ledger key is TPM-backed (/dev/tpmrm0) when available.
- Else falls back to gpg-encrypted at ~/.verdict/key.gpg.
- API keys, OAuth tokens never enter a microVM (injected via TSI only).
- Ledger redaction strips authorization fields before hashing/signing.

W1.G.6 implementation: key provider selection logic only.
Full TPM interaction + GPG encryption deferred to W2.G (ledger writer).
"""

import os
from pathlib import Path
from typing import Protocol, runtime_checkable


class HashMismatchError(Exception):
    """Raised when evidence re-hash doesn't match the initial manifest hash.

    Per §3.1 (evidence integrity):
    Every evidence file gets a SHA-256 at case_init. Runtime re-hashes
    every 10 super-steps. Mismatch → HashMismatchError + halt.
    """
    pass


@runtime_checkable
class HMACKeyProvider(Protocol):
    """Protocol for HMAC key providers (TPM or GPG)."""

    def get_key(self) -> bytes:
        """Retrieve the HMAC key.

        Returns:
            32-byte key for HMAC-SHA256.
        """
        ...


class TPMKeyProvider:
    """TPM-backed HMAC key provider.

    Uses /dev/tpmrm0 (Resource Manager interface) to derive a persistent
    TPM-sealed key. Key is never exposed in plaintext on disk.

    W1.G.6 stub: interface defined, full TPM integration in W2.G.
    """

    def __init__(self):
        """Initialize TPM provider."""
        self.is_tpm = True
        self.tpm_path = "/dev/tpmrm0"

    def get_key(self) -> bytes:
        """Retrieve the TPM-sealed HMAC key.

        Returns:
            32-byte key unsealed by TPM.
        """
        # W1.G.6 stub: returns a fixed value for testing.
        # Real implementation in W2.G uses tpm2-tools or similar.
        return b"tpm_sealed_key_32_bytes_stub_01"


class GPGKeyProvider:
    """GPG-encrypted HMAC key provider.

    Falls back when TPM is unavailable. Key stored encrypted at
    ~/.verdict/key.gpg; passphrase prompted at gateway_init.

    Per §3.9: credentials (passphrase) never enter a microVM.
    Injected via TSI on host egress only.

    W1.G.6 stub: interface defined, full GPG integration in W2.G.
    """

    def __init__(self, gpg_key_path: str | None = None):
        """Initialize GPG provider.

        Args:
            gpg_key_path: Path to encrypted key file. Defaults to ~/.verdict/key.gpg.
        """
        self.gpg_path = Path(gpg_key_path or "~/.verdict/key.gpg").expanduser()

    def get_key(self) -> bytes:
        """Retrieve the GPG-decrypted HMAC key.

        Passphrase is prompted at gateway_init, not here.

        Returns:
            32-byte key decrypted by GPG.
        """
        # W1.G.6 stub: returns a fixed value for testing.
        # Real implementation in W2.G invokes gpg --decrypt.
        return b"gpg_decrypted_key_32_bytes_stub01"


def get_hmac_key_provider() -> HMACKeyProvider:
    """Select and return the appropriate HMAC key provider.

    Detection order (per CLAUDE.md §3.9):
    1. Check /dev/tpmrm0 exists → use TPMKeyProvider.
    2. Else use GPGKeyProvider (fallback).

    The provider is instantiated once at gateway_init and immutable
    thereafter (per mode-lock principle §3.4).

    Returns:
        TPMKeyProvider if TPM available, else GPGKeyProvider.
    """
    if os.path.exists("/dev/tpmrm0"):
        return TPMKeyProvider()
    else:
        return GPGKeyProvider()
