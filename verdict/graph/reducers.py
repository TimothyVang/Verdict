"""LangGraph state reducers for fanout merge.

Per `docs/ARCHITECTURE.md` §2 and BUILD_PLAN W2.B.4, the executor fanout has
**4 parallel branches** (`vol_exec`, `hay_exec`, `pls_exec`, `mft_exec`).
Each branch returns an updated `GraphState["executor_results"]`. LangGraph
merges these via the `Annotated[..., reducer]` pattern; without a reducer,
the four parallel writes would race and only the last writer would win.

The reducer here is **append-with-deterministic-ordering** rather than
LangGraph's built-in `operator.add`: branches finishing out-of-order on a
slow run (network jitter, micro-VM cold starts, GIL contention) must still
produce a byte-identical merged list so HMAC chain hashes are reproducible.

Determinism is achieved by sorting on `(branch_name, sequence_id)` after
concatenation; branches that omit those keys (legacy / pivot-injected
results) sort to the end in stable insertion order.
"""

from __future__ import annotations

from typing import Any


def append_executor_results(
    left: list[dict[str, Any]] | None,
    right: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Merge two parallel-branch result lists into a deterministic order.

    LangGraph passes ``left`` (existing state) and ``right`` (the branch's
    update) on every super-step. We:

    1. Treat ``None`` as an empty list (first write).
    2. Concatenate.
    3. Sort by ``(branch_name, sequence_id)`` so racing branches produce a
       byte-identical merged list. Items missing those keys are placed at
       the tail in **stable** insertion order (Python's sort is stable).

    The deterministic key is `(branch_name or chr(0x10FFFF), sequence_id or 0)`
    so missing-key items reliably sort last; the actual ordering choice is
    arbitrary, but it must be **total** so quorum's Jaccard comparison and
    the HMAC ledger chain hash to identical bytes across runs.
    """

    merged: list[dict[str, Any]] = []
    if left:
        merged.extend(left)
    if right:
        merged.extend(right)

    # Stable sort — items without branch_name/sequence_id keep their
    # insertion order at the tail.
    def _key(item: dict[str, Any]) -> tuple[str, int]:
        # chr(0x10FFFF) is the highest valid Unicode codepoint; any real
        # branch_name string sorts before it.
        bn = item.get("branch_name") or "\U0010ffff"
        sid = item.get("sequence_id")
        return (bn, sid if isinstance(sid, int) else 0)

    merged.sort(key=_key)
    return merged
