"""LangGraph state reducers for fanout merge — naive append (W2.B.1 pre-race)."""

from __future__ import annotations

from typing import Any


def append_executor_results(
    left: list[dict[str, Any]] | None,
    right: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Naive concat — no determinism guarantee yet."""
    merged: list[dict[str, Any]] = []
    if left:
        merged.extend(left)
    if right:
        merged.extend(right)
    return merged
