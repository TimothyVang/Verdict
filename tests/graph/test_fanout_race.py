"""W2.B.4 — fanout reducer race test.

Per BUILD_PLAN W2.B.4.a: build a graph with 4 executor branches, each
sleeping a randomized 0-500ms, and assert the final merged state
contains all 4 outputs in deterministic order regardless of who
finished first.

This is the critical invariant the HMAC ledger chain depends on: if two
runs of the same case produce different `executor_results` orderings,
they hash to different bytes and the chain integrity check fails. The
reducer in `verdict/graph/reducers.py` sorts by
`(branch_name, sequence_id)` so racing branches always merge to a
byte-identical list.

The race is exercised against a **real LangGraph fanout** (no mocks),
using LangGraph's `Send` API to dispatch the 4 parallel branches.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Annotated, Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from typing_extensions import TypedDict

from verdict.graph.reducers import append_executor_results

BRANCH_NAMES = ("vol_exec", "hay_exec", "pls_exec", "mft_exec")


class _RaceState(TypedDict, total=False):
    """Minimal state for the race test — only the reducer-annotated
    list is exercised."""

    pending_branches: list[str]
    executor_results: Annotated[list[dict[str, Any]], append_executor_results]


# ---------------------------------------------------------------------------
# Race graph: dispatcher -> 4 parallel `branch` workers (Send fanout) -> END.
# ---------------------------------------------------------------------------


def _dispatch(state: _RaceState) -> list[Send]:
    """Conditional-edge router that fans out to N parallel `branch`
    invocations via Send."""
    return [Send("branch", {"branch_name": name}) for name in state["pending_branches"]]


async def _branch(payload: dict[str, Any]) -> dict[str, Any]:
    """One executor branch — sleeps a random 0-500ms then emits a
    single result dict.

    The result includes `branch_name` and `sequence_id` so the reducer
    can produce a deterministic order regardless of completion time.
    """
    branch_name = payload["branch_name"]
    # Real wall-clock sleep — exercising the actual race window.
    delay_ms = random.randint(0, 500)
    await asyncio.sleep(delay_ms / 1000.0)
    return {
        "executor_results": [
            {
                "branch_name": branch_name,
                "sequence_id": 0,
                "completed_at_ns": time.monotonic_ns(),
            }
        ]
    }


def _build_race_graph():
    g: StateGraph = StateGraph(_RaceState)
    g.add_node("branch", _branch)
    # `add_conditional_edges` with a `Send`-returning router is the
    # documented LangGraph fanout idiom.
    g.add_conditional_edges(START, _dispatch, ["branch"])
    g.add_edge("branch", END)
    return g.compile()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_4_executors_merge_deterministically() -> None:
    """W2.B.4.a — 4 executors, randomized 0-500ms sleep each; assert
    final state contains all 4 outputs in deterministic order."""
    compiled = _build_race_graph()

    # Run the same fanout TWICE. Each run randomizes sleeps fresh, so
    # the wall-clock completion order will almost certainly differ.
    # Both final `executor_results` orderings must still be byte-
    # identical because the reducer sorts deterministically.
    random.seed(1)
    out_a = await compiled.ainvoke({"pending_branches": list(BRANCH_NAMES)})
    random.seed(2)
    out_b = await compiled.ainvoke({"pending_branches": list(BRANCH_NAMES)})

    names_a = [r["branch_name"] for r in out_a["executor_results"]]
    names_b = [r["branch_name"] for r in out_b["executor_results"]]

    assert names_a == sorted(BRANCH_NAMES), (
        f"merged order is not deterministic on run A: got {names_a}"
    )
    assert names_b == sorted(BRANCH_NAMES), (
        f"merged order is not deterministic on run B: got {names_b}"
    )
    # The names list must be identical across runs even though the
    # completion timestamps differ — that's the HMAC chain invariant.
    assert names_a == names_b


async def test_all_4_branches_present() -> None:
    """No branch is dropped on the merge — partial results would
    masquerade as a successful 4-way fanout and bypass the
    ARCHITECTURE.md §1 empty-set rule.
    """
    compiled = _build_race_graph()
    out = await compiled.ainvoke({"pending_branches": list(BRANCH_NAMES)})
    assert len(out["executor_results"]) == len(BRANCH_NAMES)
    assert {r["branch_name"] for r in out["executor_results"]} == set(BRANCH_NAMES)


async def test_reducer_idempotent_on_double_invoke() -> None:
    """Calling .ainvoke() twice on the same compiled graph with the
    same input must yield the same merged result — the reducer cannot
    accumulate cross-invocation state.
    """
    compiled = _build_race_graph()
    random.seed(42)
    out1 = await compiled.ainvoke({"pending_branches": list(BRANCH_NAMES)})
    random.seed(7)  # different seed, different wall-clock order
    out2 = await compiled.ainvoke({"pending_branches": list(BRANCH_NAMES)})
    assert [r["branch_name"] for r in out1["executor_results"]] == [
        r["branch_name"] for r in out2["executor_results"]
    ]


# ---------------------------------------------------------------------------
# Pure-reducer unit tests (no LangGraph) — pin the contract independently.
# ---------------------------------------------------------------------------


def test_reducer_handles_none_left_and_right() -> None:
    """First write (left=None) and no-update (right=None) must not crash."""
    assert append_executor_results(None, None) == []
    assert append_executor_results(None, [{"branch_name": "x", "sequence_id": 0}]) == [
        {"branch_name": "x", "sequence_id": 0}
    ]
    assert append_executor_results([{"branch_name": "x", "sequence_id": 0}], None) == [
        {"branch_name": "x", "sequence_id": 0}
    ]


def test_reducer_sorts_by_branch_then_sequence() -> None:
    """Reducer deterministic order: (branch_name, sequence_id)."""
    items = [
        {"branch_name": "vol_exec", "sequence_id": 1},
        {"branch_name": "hay_exec", "sequence_id": 0},
        {"branch_name": "vol_exec", "sequence_id": 0},
        {"branch_name": "mft_exec", "sequence_id": 0},
    ]
    merged = append_executor_results([], items)
    assert [r["branch_name"] for r in merged] == [
        "hay_exec", "mft_exec", "vol_exec", "vol_exec"
    ]
    # Within vol_exec, sequence_id 0 sorts before 1.
    vol_seqs = [r["sequence_id"] for r in merged if r["branch_name"] == "vol_exec"]
    assert vol_seqs == [0, 1]


def test_reducer_keyless_items_sort_to_tail_in_insertion_order() -> None:
    """Items missing branch_name keep stable insertion order at the
    tail of the merged list."""
    items = [
        {"foo": "first"},          # no branch_name
        {"branch_name": "vol_exec", "sequence_id": 0},
        {"foo": "second"},         # no branch_name
    ]
    merged = append_executor_results([], items)
    assert merged[0] == {"branch_name": "vol_exec", "sequence_id": 0}
    # Stable insertion order at the tail.
    assert merged[1] == {"foo": "first"}
    assert merged[2] == {"foo": "second"}
