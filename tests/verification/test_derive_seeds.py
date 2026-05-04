from __future__ import annotations

from verdict.verification.derive_seeds import derive_seeds


def test_three_distinct_deterministic_per_case() -> None:
    seeds = derive_seeds("case-001")

    assert seeds == derive_seeds("case-001")
    assert seeds != derive_seeds("case-002")
    assert len(seeds) == 3
    assert len(set(seeds)) == 3
    assert all(0 <= seed <= 2**32 - 1 for seed in seeds)
