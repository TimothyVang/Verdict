"""Ledger payload redaction — W3.B.3.

Implements CLAUDE.md §3.9 at the ledger layer:

  Auth fields are stripped from the payload **BEFORE** the entry is hashed
  and HMAC-signed.  Stripping after hashing would allow a reconstructed
  pre-hash payload to leak credentials; order matters.

ARCHITECTURE.md §5 ``payload_redactions``:
  The ``LedgerEntry.payload_redactions: list[str]`` field records which keys
  were stripped for auditability.  The values themselves are never stored.

Redaction contract:
  - Keys matched **case-insensitively** (``Authorization`` → ``authorization``).
  - Matched keys are replaced with ``REDACTION_SENTINEL = "<redacted>"``.
  - Only **top-level** keys are redacted (depth=1).  Nested auth fields are
    an undocumented edge case; top-level is the mandatory contract.
  - The original ``payload`` dict is **never mutated**; a new dict is returned.
  - ``redacted_keys`` lists only keys that were actually present and stripped
    (keys in REDACT_KEYS but absent from the payload are not listed).

Usage (LedgerEmitter, W2.C.2):

    from verdict.ledger.redaction import redact_payload

    result = redact_payload(raw_payload)
    entry = LedgerEntry(
        ...
        payload=result.redacted_payload,
        payload_redactions=result.redacted_keys,
        ...
    )
    # hash + HMAC over result.redacted_payload — credentials not present
"""

from __future__ import annotations

import copy
from typing import Final

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Credential field names to redact.  All lowercase; matching is
#: case-insensitive.  Expanding this set is a deliberate, visible change —
#: the ``TestRedactKeysConstant.test_no_extra_expansions_without_doc`` test
#: will fail if a key is added without updating the test.
REDACT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "authorization",  # HTTP Authorization header value (Bearer / Basic / etc.)
        "auth_user",      # username portion of an authentication context
        "api_key",        # API key / service token (e.g. VirusTotal, OpenCTI)
    }
)

#: Sentinel value that replaces the original credential value in the redacted
#: payload.  Must be a non-empty string so JSON serialisation is safe and the
#: ledger is auditable (auditor can see a field was stripped, not that it is
#: absent).  NEVER change this value without a schema migration.
REDACTION_SENTINEL: Final[str] = "<redacted>"


# ---------------------------------------------------------------------------
# RedactionResult — typed return value
# ---------------------------------------------------------------------------


class RedactionResult(BaseModel):
    """Result of a payload redaction pass.

    Fields
    ------
    redacted_payload
        A copy of the original payload with credential values replaced by
        ``REDACTION_SENTINEL``.  Safe to hash and HMAC-sign.
    redacted_keys
        List of keys that were actually present in the payload and stripped.
        Keys in REDACT_KEYS that were absent from the payload are NOT listed.
        Populated into ``LedgerEntry.payload_redactions`` for auditability.
    """

    redacted_payload: dict
    redacted_keys: list[str]


# ---------------------------------------------------------------------------
# redact_payload — the single public function
# ---------------------------------------------------------------------------


def redact_payload(payload: dict) -> RedactionResult:
    """Strip credential fields from ``payload`` and return a new clean dict.

    The function operates on **top-level keys only** (depth=1).  This matches
    the documented contract; nested auth fields are a non-standard edge case
    and are explicitly out of scope for v1.

    Matching is **case-insensitive**: a key ``Authorization`` is treated the
    same as ``authorization``.  The *original* key name is preserved in the
    output dict (we replace the value, not the key).

    Parameters
    ----------
    payload
        The raw event payload dict.  Not mutated by this function.

    Returns
    -------
    RedactionResult
        ``redacted_payload``: a deep copy of ``payload`` with credential values
        replaced by ``REDACTION_SENTINEL``.
        ``redacted_keys``: sorted list of lowercased key names that were stripped.
    """
    # Deep-copy so the original is not mutated
    cleaned: dict = copy.deepcopy(payload)
    stripped: list[str] = []

    for key in list(cleaned.keys()):
        if key.lower() in REDACT_KEYS:
            cleaned[key] = REDACTION_SENTINEL
            stripped.append(key.lower())

    return RedactionResult(
        redacted_payload=cleaned,
        redacted_keys=sorted(stripped),
    )
