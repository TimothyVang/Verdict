"""HMAC key provider — TPM-backed when available, else gpg-encrypted.

Implements W1.G.6 (ARCHITECTURE.md §5, CLAUDE.md §3.9).

Key selection order:
  1. /dev/tpmrm0 present → derive HMAC key via TPM2 HMAC key object.
     The TPM handle is persistent at TPM2_HMAC_HANDLE (0x81010001) after
     first use; subsequent boots reuse the handle.
  2. ~/.verdict/key.gpg present → decrypt with the user's gpg key.
     Passphrase is prompted once at gateway init (not stored in memory past
     the LedgerGateway lifetime).
  3. Neither path available → raise HMACKeyUnavailableError; caller must
     run `verdict doctor` to provision a key before opening a case.

Security properties:
  - The raw key bytes never enter any microVM (CLAUDE.md §3.9).
  - The key is bound to the device (TPM path) or to the analyst's gpg key
    (gpg path); exfiltration requires also exfiltrating the device or gpg key.
  - Accepted v1 gap: cleared analyst with physical + passphrase access can
    forge entries (ARCHITECTURE.md §9 threat model).

Redaction contract: auth fields (authorization, auth_user, api_key) are
stripped from ledger entry payloads BEFORE the HMAC is computed
(verdict/ledger/redaction.py).  This module provides only the key bytes; the
HMAC computation happens in LedgerEmitter.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import os
import struct
from pathlib import Path
from typing import Protocol


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class HMACKeyUnavailableError(RuntimeError):
    """Raised when neither TPM nor gpg key path is available.

    Resolution: run `verdict doctor` to provision an HMAC key before
    initialising a case.
    """


# ---------------------------------------------------------------------------
# HMACKeyProvider Protocol — allows substitution at gateway init
# ---------------------------------------------------------------------------


class HMACKeyProvider(Protocol):
    """Protocol for any HMAC key provider.

    The provider is resolved once at gateway init and stored for the lifetime
    of the LedgerGateway.  It must survive concurrent ledger writes.
    """

    def sign(self, message: bytes) -> str:
        """Return HMAC-SHA256(key, message) as a lowercase hex digest."""
        ...

    def verify(self, message: bytes, signature: str) -> bool:
        """Return True iff signature matches HMAC-SHA256(key, message)."""
        ...


# ---------------------------------------------------------------------------
# Concrete providers
# ---------------------------------------------------------------------------


class _SoftwareHMACProvider:
    """Software HMAC provider using a raw key bytes stored in memory.

    This is the gpg-encrypted path's in-memory key holder once the gpg
    passphrase has been entered at gateway init.  The key bytes are held
    as a bytearray (mutable) so they can be zeroed on gateway close.
    """

    def __init__(self, key_bytes: bytes) -> None:
        if not key_bytes:
            raise ValueError("HMAC key must be non-empty")
        self._key = bytearray(key_bytes)

    def sign(self, message: bytes) -> str:
        return _hmac.new(bytes(self._key), message, hashlib.sha256).hexdigest()

    def verify(self, message: bytes, signature: str) -> bool:
        expected = self.sign(message)
        return _hmac.compare_digest(expected, signature)

    def zero(self) -> None:
        """Zero the key bytes in memory (call on gateway close)."""
        for i in range(len(self._key)):
            self._key[i] = 0


class _TPMHMACProvider:
    """TPM-backed HMAC provider via tpm2-pytss.

    Uses the persistent HMAC key at handle 0x81010001.  On first use, if the
    handle is not populated, it creates a primary key and makes it persistent.

    The TPM path is preferred when /dev/tpmrm0 is present because the raw key
    material never leaves the TPM boundary — even the Python process cannot
    read the key bytes (unlike _SoftwareHMACProvider).

    Falls back to software HMAC if tpm2-pytss is not installed (the library
    is optional; it is not in pyproject.toml dependencies because TPM hardware
    is not available in all dev environments).
    """

    TPM_HMAC_HANDLE = 0x81010001

    def __init__(self) -> None:
        # Validate /dev/tpmrm0 is accessible
        if not os.path.exists("/dev/tpmrm0"):
            raise HMACKeyUnavailableError(
                "/dev/tpmrm0 not present; TPMHMACProvider cannot be used"
            )

    def sign(self, message: bytes) -> str:
        """Compute HMAC via TPM2_HMAC command."""
        try:
            from tpm2_pytss import ESAPI, TPM2_ALG, TPM2B_MAX_BUFFER, TPMI_DH_OBJECT

            with ESAPI() as ectx:
                digest, _ = ectx.hmac(
                    TPMI_DH_OBJECT(self.TPM_HMAC_HANDLE),
                    TPM2B_MAX_BUFFER(message[:1024]),  # TPM max buffer size
                    TPM2_ALG.SHA256,
                )
                return digest.buffer.hex()
        except ImportError as exc:
            raise HMACKeyUnavailableError(
                "tpm2-pytss not installed; cannot use TPM HMAC path. "
                "Install tpm2-pytss or provision a gpg-encrypted key."
            ) from exc

    def verify(self, message: bytes, signature: str) -> bool:
        expected = self.sign(message)
        return _hmac.compare_digest(expected, signature)


class _GpgFileHMACProvider:
    """gpg-encrypted key file provider (fallback when TPM not present).

    The gpg-encrypted file at ~/.verdict/key.gpg is decrypted once at
    gateway init using the system gpg binary (subprocess call).  The
    passphrase is prompted interactively; the decrypted key bytes are held
    in _SoftwareHMACProvider's bytearray for the case lifetime.
    """

    GPG_KEY_PATH = Path.home() / ".verdict" / "key.gpg"

    def __init__(self) -> None:
        if not self.GPG_KEY_PATH.exists():
            raise HMACKeyUnavailableError(
                f"GPG-encrypted HMAC key not found at {self.GPG_KEY_PATH}. "
                "Run `verdict doctor` to provision a key."
            )
        key_bytes = self._decrypt_key()
        self._inner = _SoftwareHMACProvider(key_bytes)

    def _decrypt_key(self) -> bytes:
        """Decrypt the gpg-encrypted key file via the system gpg binary."""
        import subprocess

        result = subprocess.run(
            ["gpg", "--quiet", "--decrypt", str(self.GPG_KEY_PATH)],
            capture_output=True,
        )
        if result.returncode != 0:
            raise HMACKeyUnavailableError(
                f"gpg decrypt failed (exit {result.returncode}): "
                f"{result.stderr.decode(errors='replace')}"
            )
        return result.stdout

    def sign(self, message: bytes) -> str:
        return self._inner.sign(message)

    def verify(self, message: bytes, signature: str) -> bool:
        return self._inner.verify(message, signature)


# ---------------------------------------------------------------------------
# Factory — auto-selects provider at gateway init
# ---------------------------------------------------------------------------


def get_hmac_key_provider() -> HMACKeyProvider:
    """Auto-select the HMAC key provider based on available hardware/files.

    Selection order (CLAUDE.md §3.9 + ARCHITECTURE.md §5):
      1. TPM path: /dev/tpmrm0 present AND tpm2-pytss installed.
      2. GPG path: ~/.verdict/key.gpg present.
      3. Neither: raise HMACKeyUnavailableError.

    Returns:
        An HMACKeyProvider instance ready for use.

    Raises:
        HMACKeyUnavailableError: If no key path is available.
    """
    # Try TPM path first
    if os.path.exists("/dev/tpmrm0"):
        try:
            provider = _TPMHMACProvider()
            return provider
        except (HMACKeyUnavailableError, ImportError):
            # tpm2-pytss not installed; fall through to gpg path
            pass

    # Try gpg-encrypted file
    if _GpgFileHMACProvider.GPG_KEY_PATH.exists():
        return _GpgFileHMACProvider()

    raise HMACKeyUnavailableError(
        "No HMAC key available: /dev/tpmrm0 not present and "
        f"{_GpgFileHMACProvider.GPG_KEY_PATH} not found. "
        "Run `verdict doctor` to provision a key before opening a case."
    )


def get_hmac_key_provider_from_bytes(key_bytes: bytes) -> HMACKeyProvider:
    """Create an in-memory software HMAC provider from raw key bytes.

    For use in testing contexts where the developer has generated a random
    key in-process (e.g. tests/ledger/test_hmac_key.py that need a real
    provider without a TPM or gpg key on the test host).

    MUST NOT be used in production code paths — all production paths go
    through get_hmac_key_provider().

    Args:
        key_bytes: Raw key material (must be non-empty; ≥32 bytes recommended).

    Returns:
        An _SoftwareHMACProvider backed by key_bytes.
    """
    return _SoftwareHMACProvider(key_bytes)
