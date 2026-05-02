"""W1.C.1 — derive three reproducible-but-diverse seeds per case.

Wang et al. 2022 self-consistency (arXiv:2203.11171) requires *diverse*
reasoning paths, not just `n` calls with the same seed. Three identical
seeds at a fixed temperature collapse the n=3 quorum to n=1 because the
sampler is deterministic given (model, prompt, temperature, seed).

We use blake3's keyed-hash (`derive_key`) construction to get three
independent 32-bit ints from a single `case_id`:

    derive_seeds("case_001") -> (s_a, s_b, s_c)

Properties:

- **Distinct** — `len({s_a, s_b, s_c}) == 3` for every realistic input.
  Three independent contexts ("verdict.seeds.v1.a/b/c") through blake3's
  KDF mode produce three independent 32-bit slices; collision probability
  for 32-bit slices in a single 3-tuple is ~3.5e-10 in the worst case
  and not realisable for these contexts.
- **Deterministic** — same `case_id` always yields the same tuple. This
  is the audit-replay guarantee in CLAUDE.md §3.4 and ARCHITECTURE.md §1.
- **Case-isolated** — different `case_id` yields a different tuple.
  blake3 is collision-safe; cross-case alias would be a cryptographic
  break.

Why uint32 (4 bytes) and not uint64? Anthropic's `seed` request parameter
maps onto a non-negative int and most server-side samplers seed a 32-bit
PRNG state. Truncating to 4 bytes keeps the wire format portable and
sidesteps Python `int.from_bytes` width surprises.

The context label `"verdict.seeds.v1.<a|b|c>"` is versioned. Bumping to
`v2` is a breaking change to the audit trail and requires a coordinated
update to the v4.x audit doc + a parallel verdict chain (CLAUDE.md §3.4
reverify semantics).
"""
from __future__ import annotations

from blake3 import blake3

# Length in bytes of each derived seed slice. 4 bytes -> 32-bit uint, which
# matches the Anthropic `seed` parameter and most sampler PRNG widths.
_SEED_BYTES = 4

# Versioned KDF contexts. NEVER reuse a context across versions; bumping
# the suffix is a breaking change and must be paired with a v_audit doc
# update (see ARCHITECTURE.md §1).
_CTX_A = "verdict.seeds.v1.a"
_CTX_B = "verdict.seeds.v1.b"
_CTX_C = "verdict.seeds.v1.c"


def derive_seeds(case_id: str) -> tuple[int, int, int]:
    """Derive three blake3-keyed seeds for n=3 self-consistency.

    Parameters
    ----------
    case_id:
        The case identifier (e.g. ``"case_001_lolbins"``). Must be a
        non-empty string. Treated as UTF-8 bytes for hashing.

    Returns
    -------
    tuple[int, int, int]
        Three distinct, deterministic, case-isolated 32-bit ints suitable
        for passing as the ``seed`` parameter on three sibling Anthropic
        API calls at ``temperature=0.7``.

    Raises
    ------
    ValueError
        If ``case_id`` is the empty string. An empty case_id would alias
        every empty-id call to the same constant tuple — almost always
        a programming error in the gateway layer.
    """
    if not case_id:
        # Don't silently derive a constant tuple — that aliases every
        # caller that forgot to populate case_id.
        raise ValueError("case_id must be a non-empty string")

    case_bytes = case_id.encode("utf-8")
    return (
        _slice(case_bytes, _CTX_A),
        _slice(case_bytes, _CTX_B),
        _slice(case_bytes, _CTX_C),
    )


def _slice(case_bytes: bytes, context: str) -> int:
    """Run blake3 in keyed-derive-key mode and return the leading uint32.

    blake3's ``derive_key`` produces a key of arbitrary length tied to a
    *context string*; identical inputs across different contexts yield
    independent keys. We hash the case_id under the keyed digest and
    take the leading ``_SEED_BYTES`` bytes as a big-endian unsigned int.
    """
    keyed_digest = blake3(case_bytes, derive_key_context=context).digest(
        length=_SEED_BYTES
    )
    return int.from_bytes(keyed_digest, "big")
