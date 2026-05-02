"""Ledger redaction — strip auth fields before hashing/signing.

CLAUDE.md §3.9: Ledger redaction strips authorization, auth_user, api_key
BEFORE the entry is hashed and HMAC-signed.

Redaction order matters: strip → hash → sign.  If signing happened before
stripping, the HMAC would cover the auth fields, and the ledger would contain
HMAC-verified auth-field values that cannot be independently redacted without
breaking chain integrity.

This module is called by LedgerEmitter before constructing a LedgerEntry.
It is a pure function with no side effects.
"""

from __future__ import annotations

import copy

# ---------------------------------------------------------------------------
# Auth-field deny-list
# ---------------------------------------------------------------------------

# These keys are redacted from the payload dict before it is hashed.
# The list is intentionally short and concrete — no wildcards, no regex.
# Any new auth-field name requires a coordinated addition here AND a schema
# migration note in docs/SCHEMA_MIGRATION.md.
AUTH_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "authorization",
        "auth_user",
        "api_key",
        "api_secret",
        "bearer_token",
        "token",
        "password",
        "secret",
        "credential",
    }
)

# Sentinel value substituted for redacted fields in the stored payload.
_REDACTED_SENTINEL = "<redacted>"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def redact_payload(payload: dict) -> tuple[dict, list[str]]:
    """Strip auth fields from payload; return (redacted_payload, redacted_keys).

    The function performs a shallow redaction: only top-level keys matching
    AUTH_FIELD_NAMES are redacted.  Nested dicts are not recursed into —
    tool args are typed (Pydantic) and auth fields must never appear in
    nested structures per §3.9 design.

    Args:
        payload: The raw event payload dict.

    Returns:
        A tuple of:
          - redacted_payload: A shallow copy of payload with matching keys
            replaced by _REDACTED_SENTINEL.
          - redacted_keys: List of key names that were redacted (for
            LedgerEntry.payload_redactions).

    The original payload dict is NOT mutated.
    """
    redacted = copy.copy(payload)
    redacted_keys: list[str] = []

    for key in list(redacted.keys()):
        if key.lower() in AUTH_FIELD_NAMES:
            redacted[key] = _REDACTED_SENTINEL
            redacted_keys.append(key)

    return redacted, redacted_keys
