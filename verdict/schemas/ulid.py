"""ULID generation — minimal pure-Python implementation.

ULID (https://github.com/ulid/spec) is the canonical event_id shape for
LedgerEntry per ARCHITECTURE.md §5: 26-character Crockford-base32,
lexicographically sortable by timestamp, with 80 bits of randomness.

We avoid adding a third-party `python-ulid` direct dep — pyproject is
already MIT/Apache-only and CLAUDE.md §3.8 wants every direct dep
license-checked. This implementation is ~25 lines of stdlib + os.urandom.

If a downstream consumer wants the canonical implementation, swap this
module for `python-ulid` (MIT) — the public API matches.
"""

from __future__ import annotations

import os
import time

# Crockford base32 alphabet (excludes I, L, O, U to avoid ambiguity).
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
assert len(_CROCKFORD) == 32


def _encode_crockford(value: int, length: int) -> str:
    """Encode `value` (an int) as Crockford base32 of fixed `length`."""
    if value < 0:
        raise ValueError("ULID component must be non-negative")
    out = [""] * length
    for i in range(length - 1, -1, -1):
        out[i] = _CROCKFORD[value & 0b11111]
        value >>= 5
    if value:
        raise ValueError(f"value too large for {length} crockford chars")
    return "".join(out)


def new_ulid() -> str:
    """Generate a fresh 26-char ULID.

    Layout: 10 chars timestamp (48-bit ms) + 16 chars randomness (80 bits).
    Lexicographically sortable: a ULID minted later sorts after one minted
    earlier (within ms granularity).
    """
    ts_ms = int(time.time() * 1000)  # 48-bit unix ms
    rand_bits = int.from_bytes(os.urandom(10), "big")  # 80 bits
    return _encode_crockford(ts_ms, 10) + _encode_crockford(rand_bits, 16)
