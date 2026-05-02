"""W1.C.2 — `CloudSelfConsistency` strategy invariants.

The load-bearing v4.6 Patch F1 fix: n=3 cloud self-consistency MUST sample
three diverse paths. That requires:

1. ``temperature == 0.7`` on every sample. ``temperature=0`` collapses
   the strategy to n=1 (Wang et al. 2022 §3 — diverse-path requirement).
2. Three *distinct* seeds, derived from the case_id via blake3
   (W1.C.1 helper). The strategy must wire each seed into the per-call
   payload so the resulting completions can actually differ.
3. Reproducibility: same (case_id, hypothesis) inputs -> same three
   payloads (audit-friendly replay; CLAUDE.md §3.4 mode-lock).

These tests inspect the *outgoing API call payload* (a plain ``dict``)
that ``CloudSelfConsistency`` constructs for each of the n=3 samples.
We do NOT instantiate or stub the Anthropic SDK — that is reserved for
the Inspect AI eval suite (CLAUDE.md §3.10). The request-construction
layer is a pure function and is the right granularity for unit testing
the seed-distinctness invariant.
"""
from __future__ import annotations

import pytest

from verdict.verification.cloud_self_consistency import (
    CloudSelfConsistency,
    InvalidTemperatureError,
)
from verdict.verification.derive_seeds import derive_seeds


def _hypothesis_kwargs() -> dict[str, str]:
    """Minimal hypothesis-shaped payload the strategy can build a prompt from.

    Schema-stable enough for the request-construction tests without
    pulling in the full `Hypothesis` schema (W1.B.4) which is owned by
    a different sub-task.
    """
    return {
        "case_id": "case_001_lolbins",
        "hypothesis": (
            "Evidence consistent with rundll32 invoking comsvcs.MiniDump "
            "for credential access (T1003.001)."
        ),
        "mitre_technique": "T1003.001",
        "evidence_summary": (
            "Sysmon ID 1: rundll32.exe -> comsvcs.dll MiniDump 624 ...; "
            "Prefetch RUNDLL32.EXE-... last-run 2026-04-21T13:42Z"
        ),
    }


def test_three_distinct_seeds_in_api_calls() -> None:
    """W1.C.2.a — three sibling API call payloads, three distinct seeds, temp=0.7."""
    h = _hypothesis_kwargs()
    strategy = CloudSelfConsistency()

    payloads = strategy.build_call_payloads(**h)

    # n=3 sibling calls. NOT 2 (single-flip), NOT 5 (over-spend).
    assert len(payloads) == 3, f"expected 3 payloads, got {len(payloads)}"

    # Every payload at temperature=0.7. The W1.C.2 patch's whole point.
    for i, p in enumerate(payloads):
        assert p["temperature"] == 0.7, (
            f"payload[{i}] has temperature={p['temperature']!r}; must be 0.7 "
            f"(temp=0 collapses n=3 to n=1 per Wang 2022)"
        )

    # The three seeds must be distinct -- otherwise temp=0.7 + identical
    # seed would still collide on cache-routed servers, and the audit
    # ledger would record three identical samples.
    seeds = [p["_verdict_seed"] for p in payloads]
    assert len(set(seeds)) == 3, f"three payloads must carry three distinct seeds, got {seeds}"

    # Seeds must match what derive_seeds(case_id) produces -- the audit
    # invariant: the strategy and the helper agree on the seed trio for
    # this case_id, so a re-run reproduces the same three samples.
    assert tuple(seeds) == derive_seeds(h["case_id"]), (
        "strategy seeds diverge from derive_seeds(case_id); breaks audit replay"
    )


def test_seeds_anchored_in_user_prompt() -> None:
    """Seed must affect the wire payload, not just sit in metadata.

    Anthropic's public Messages API does not expose a server-side `seed`
    parameter, so the strategy salts each sample's user message with the
    seed. That guarantees three observably-distinct prompts even if a
    transparent caching layer collapses identical prompts.
    """
    h = _hypothesis_kwargs()
    payloads = CloudSelfConsistency().build_call_payloads(**h)
    user_messages = [
        next(m["content"] for m in p["messages"] if m["role"] == "user")
        for p in payloads
    ]
    # All three user messages must differ -- if any two prompts collide,
    # a caching layer can serve identical completions and the n=3 quorum
    # is not actually n=3.
    assert len(set(user_messages)) == 3, (
        "three samples produced identical user prompts; cache would collapse them"
    )


def test_refuses_temperature_zero() -> None:
    """The strategy must refuse temp=0 at construction time.

    temp=0 + same prompt + same seed = three identical completions,
    which collapses the n=3 quorum. Surface this as a configuration
    error rather than silently producing a useless verdict.
    """
    with pytest.raises(InvalidTemperatureError):
        CloudSelfConsistency(temperature=0.0)


def test_refuses_temperature_outside_unit_interval() -> None:
    """Temperature must be in (0, 1] -- nonsensical values rejected up front."""
    with pytest.raises(InvalidTemperatureError):
        CloudSelfConsistency(temperature=-0.1)
    with pytest.raises(InvalidTemperatureError):
        CloudSelfConsistency(temperature=1.5)


def test_default_temperature_is_zero_point_seven() -> None:
    """The default must be 0.7, codified in v4.6 Patch F1."""
    s = CloudSelfConsistency()
    assert s.temperature == 0.7


def test_n_samples_is_three() -> None:
    """n=3 is the hard contract -- bumping it is a separate RFC."""
    h = _hypothesis_kwargs()
    payloads = CloudSelfConsistency().build_call_payloads(**h)
    assert CloudSelfConsistency.N_SAMPLES == 3
    assert len(payloads) == 3


def test_payloads_are_deterministic() -> None:
    """Same inputs -> same three payloads on repeat invocation (audit replay)."""
    h = _hypothesis_kwargs()
    s = CloudSelfConsistency()
    a = s.build_call_payloads(**h)
    b = s.build_call_payloads(**h)
    assert a == b, "build_call_payloads must be deterministic for audit replay"


def test_accepts_temperature_one_point_zero() -> None:
    """Boundary: temperature=1.0 must NOT raise.

    The guard is 0 < temp <= 1 -- 1.0 is the upper inclusive bound.
    Without this test, a future refactor that accidentally tightens to
    temp < 1.0 would pass all existing tests and silently break the
    contract (reviewer finding BLOCK 2).
    """
    # Must not raise InvalidTemperatureError or any other exception.
    strategy = CloudSelfConsistency(temperature=1.0)
    assert strategy.temperature == 1.0

