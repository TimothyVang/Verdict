"""W1.C.1 — `derive_seeds(case_id)` helper.

Test surface for the seed-derivation invariants demanded by v4.6 Patch F1
(spec/04 §Phase 2, BUILD_PLAN W1.C.1, ARCHITECTURE.md §1):

- Three distinct ints per case (otherwise n=3 self-consistency collapses to
  three identical samples — Wang et al. 2022 requires diverse paths).
- Deterministic given the same `case_id` (audit-friendly: re-running the
  case yields the same three samples).
- Case-isolated: different `case_id` -> different tuple (no cross-case
  seed leakage between investigations sharing the same VERDICT install).
- 32-bit positive ints (Anthropic API `seed` parameter is uint32-shaped).
"""
from __future__ import annotations

import pytest
from verdict.verification.derive_seeds import derive_seeds


def test_three_distinct_deterministic_per_case() -> None:
    seeds = derive_seeds("case_001_lolbins")

    # Three-tuple, not a list, not a set.
    assert isinstance(seeds, tuple), f"expected tuple, got {type(seeds).__name__}"
    assert len(seeds) == 3, f"expected 3 seeds, got {len(seeds)}"

    # All distinct — the load-bearing invariant. Same seed across the three
    # samples means three identical Claude completions, which is n=1 with
    # extra steps.
    assert len(set(seeds)) == 3, f"seeds must be distinct, got {seeds}"

    # Determinism — re-running the case must reproduce the same three seeds
    # (chain-of-custody + audit replay).
    again = derive_seeds("case_001_lolbins")
    assert seeds == again, f"derive_seeds is non-deterministic: {seeds} != {again}"


def test_case_isolation() -> None:
    a = derive_seeds("case_001_lolbins")
    b = derive_seeds("case_002_credtheft")
    # Cross-case seed reuse would mean two unrelated investigations share
    # the same Claude sampling trajectory — undesirable for audit, and a
    # subtle correlation leak. blake3(case_id) is collision-safe, so any
    # overlap here is an implementation bug.
    assert a != b, "different case_ids must produce different seed tuples"


def test_seeds_are_uint32_compatible() -> None:
    """Anthropic `seed` parameter must fit a 32-bit unsigned int."""
    seeds = derive_seeds("case_001_lolbins")
    for s in seeds:
        assert isinstance(s, int), f"seed must be int, got {type(s).__name__}"
        assert 0 <= s <= 0xFFFFFFFF, f"seed {s} out of uint32 range"


def test_empty_case_id_rejected() -> None:
    """Empty case_id is a programming error — refuse rather than silently
    derive a constant tuple that would alias every empty-id call."""
    with pytest.raises(ValueError):
        derive_seeds("")
