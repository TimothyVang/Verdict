"""W2.B.2 — comprehension_gate node consensus + clarify sub-state.

The gate collects `PlanComprehensionEcho`s from all 4 executors and validates
consensus on three keys:

- `parsed_positive_hypothesis_ids` (set)
- `parsed_negative_hypothesis_ids` (set)
- `parsed_success_criteria_hash`   (string)

If all 4 agree, the gate emits `comprehension_consensus=True` and routes to
`executor_fanout`. On disagreement the gate increments
`clarify_iterations` and re-prompts; once the budget
`max_clarify_iterations=2` is exhausted the gate emits
`comprehension_consensus=False` plus a `contested_hint` and routes to
`replan_node` per ARCHITECTURE.md §2.

These tests are pure consensus logic — no LLM, no microsandbox — so they
run in CI without external services.
"""

from __future__ import annotations

import pytest

from verdict.graph.nodes import (
    MAX_CLARIFY_ITERATIONS,
    ROUTE_GATE_PASS,
    ROUTE_GATE_REPLAN,
    comprehension_gate_node,
    route_after_gate,
)


def _echo(
    branch: str,
    pos: list[str],
    neg: list[str],
    succ_hash: str,
) -> dict:
    """Build a synthetic `PlanComprehensionEcho` payload for the gate."""
    return {
        "branch_name": branch,
        "parsed_positive_hypothesis_ids": pos,
        "parsed_negative_hypothesis_ids": neg,
        "parsed_success_criteria_hash": succ_hash,
    }


def _state(echoes: list[dict], clarify_iterations: int = 0) -> dict:
    return {
        "comprehension_echoes": echoes,
        "clarify_iterations": clarify_iterations,
    }


def test_consensus_advances_executor_work() -> None:
    """All 4 executors echo identically -> consensus=True -> executor_fanout."""
    pos, neg, hsh = ["H1", "H2"], ["N1"], "abc123"
    echoes = [
        _echo("vol_exec", pos, neg, hsh),
        _echo("hay_exec", pos, neg, hsh),
        _echo("pls_exec", pos, neg, hsh),
        _echo("mft_exec", pos, neg, hsh),
    ]
    state = _state(echoes)
    update = comprehension_gate_node(state)

    assert update["comprehension_consensus"] is True, (
        f"4-way agreement must yield consensus=True; got {update}"
    )
    # Routing decision uses the merged state.
    merged = {**state, **update}
    assert route_after_gate(merged) == ROUTE_GATE_PASS


def test_mismatch_routes_to_clarify_then_replan() -> None:
    """One executor disagrees -> clarify until budget exhausted -> replan."""
    pos, neg, hsh = ["H1", "H2"], ["N1"], "abc123"
    echoes = [
        _echo("vol_exec", pos, neg, hsh),
        _echo("hay_exec", pos, neg, hsh),
        _echo("pls_exec", pos, neg, hsh),
        _echo("mft_exec", ["H1"], neg, hsh),  # missing H2
    ]

    # Iteration 1: gate notices mismatch, increments clarify_iterations.
    update1 = comprehension_gate_node(_state(echoes, clarify_iterations=0))
    assert update1["clarify_iterations"] == 1
    assert update1.get("comprehension_consensus") is None or update1["comprehension_consensus"] is None
    # Gate should NOT yet emit replan — clarify budget not exhausted.

    # Iteration 2: still mismatch, increments to 2 (== MAX), still clarify.
    update2 = comprehension_gate_node(_state(echoes, clarify_iterations=1))
    assert update2["clarify_iterations"] == 2

    # Iteration 3 (>= MAX): gate gives up, sets consensus=False + hint.
    update3 = comprehension_gate_node(_state(echoes, clarify_iterations=MAX_CLARIFY_ITERATIONS))
    assert update3["comprehension_consensus"] is False, (
        f"after {MAX_CLARIFY_ITERATIONS} clarify rounds, gate must concede; got {update3}"
    )
    assert "contested_hint" in update3
    assert "comprehension" in update3["contested_hint"].lower()

    merged = {"clarify_iterations": MAX_CLARIFY_ITERATIONS, **update3}
    assert route_after_gate(merged) == ROUTE_GATE_REPLAN


def test_disagreement_field_named_in_hint() -> None:
    """The contested_hint must name WHICH consensus key disagreed —
    'positive_hypothesis_ids' / 'negative_hypothesis_ids' /
    'success_criteria_hash'. The hint flows into replan_node so the
    planner can remediate the actual disagreement.
    """
    pos, neg, hsh = ["H1"], ["N1"], "deadbeef"
    echoes_neg_disagree = [
        _echo("vol_exec", pos, neg, hsh),
        _echo("hay_exec", pos, neg, hsh),
        _echo("pls_exec", pos, neg, hsh),
        _echo("mft_exec", pos, ["DIFFERENT"], hsh),
    ]
    update = comprehension_gate_node(
        _state(echoes_neg_disagree, clarify_iterations=MAX_CLARIFY_ITERATIONS)
    )
    assert update["comprehension_consensus"] is False
    assert "negative" in update["contested_hint"].lower(), (
        f"hint must name the disagreeing field; got {update['contested_hint']!r}"
    )


def test_missing_executor_blocks_consensus() -> None:
    """Only 3 of 4 executors echoed (e.g., branch timeout) -> still
    treated as disagreement per ARCHITECTURE.md §1 empty-set rule.
    A silent-crash executor is NEVER a free pass for the others.
    """
    pos, neg, hsh = ["H1"], ["N1"], "abc"
    only_three = [
        _echo("vol_exec", pos, neg, hsh),
        _echo("hay_exec", pos, neg, hsh),
        _echo("pls_exec", pos, neg, hsh),
        # mft_exec missing
    ]
    update = comprehension_gate_node(
        _state(only_three, clarify_iterations=MAX_CLARIFY_ITERATIONS)
    )
    assert update["comprehension_consensus"] is False, (
        "3-of-4 echoes must NOT produce consensus — missing branch is "
        "treated as disagreement per ARCHITECTURE.md §1 empty-set rule"
    )


def test_no_echoes_blocks_consensus() -> None:
    """All 4 executors crashed -> consensus=False, not silently True."""
    update = comprehension_gate_node(
        _state([], clarify_iterations=MAX_CLARIFY_ITERATIONS)
    )
    assert update["comprehension_consensus"] is False
    assert "contested_hint" in update


@pytest.mark.parametrize("count", [1, 2, 3, 5])
def test_only_four_branches_count_for_consensus(count: int) -> None:
    """Even with 5 echoes (e.g., a stale pivot echo lingering), only a
    quorum of 4 distinct branch_names counts. Anything fewer than 4
    distinct branches present -> not consensus.
    """
    pos, neg, hsh = ["H1"], ["N1"], "abc"
    # `count` distinct branch_names, all agreeing.
    echoes = [
        _echo(f"branch_{i}", pos, neg, hsh) for i in range(count)
    ]
    update = comprehension_gate_node(
        _state(echoes, clarify_iterations=MAX_CLARIFY_ITERATIONS)
    )
    if count >= 4:
        assert update["comprehension_consensus"] is True, (
            f"{count} agreeing distinct branches should pass; got {update}"
        )
    else:
        assert update["comprehension_consensus"] is False, (
            f"{count} branches < 4 must NOT pass consensus; got {update}"
        )
