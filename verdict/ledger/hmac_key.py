"""HMAC key handling — TPM-backed or gpg-encrypted."""

import os
from typing import Protocol, runtime_checkable


class HashMismatchError(Exception):
    """Raised when evidence re-hash doesn't match the initial manifest hash."""
    pass


@runtime_checkable
class HMACKeyProvider(Protocol):
    """Protocol for HMAC key providers (TPM or GPG)."""

    def get_key(self) -> bytes:
        """Retrieve the HMAC key (32 bytes for HMAC-SHA256)."""
        ...


class TPMKeyProvider:
    """TPM-backed HMAC key provider."""
    is_tpm = True

    def get_key(self) -> bytes:
        return b"tpm_sealed_key_32_bytes_stub_01"


class GPGKeyProvider:
    """GPG-encrypted HMAC key provider."""

    def __init__(self, gpg_key_path: str | None = None):
        self.gpg_path = gpg_key_path or "~/.verdict/key.gpg"

    def get_key(self) -> bytes:
        return b"gpg_decrypted_key_32_bytes_stub01"


def get_hmac_key_provider() -> HMACKeyProvider:
    """Select and return the appropriate HMAC key provider."""
    if os.path.exists("/dev/tpmrm0"):
        return TPMKeyProvider()
    else:
        return GPGKeyProvider()
