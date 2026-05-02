"""GraphState — TypedDict carried through every super-step.

Per `docs/ARCHITECTURE.md` §2 and CLAUDE.md §3, the graph state encodes:

- the locked operational `Mode` (immutable post case_init),
- the `case_id` that doubles as the `langgraph_thread_id`,
- the current `InvestigationPlan` (refined by `planner_node` /
  `planner_critique_node` / `replan_node`),
- the running `executor_results` list (appended by the fanout reducer —
  see `verdict/graph/reducers.py`, W2.B.4),
- the pivot + replan iteration counters bounded by `pivot_max=15` and
  `replan_max=3`,
- a CONTESTED hint plumbed through by `quorum_node` to `replan_node`.

This file is the schema for the LangGraph store; node functions in
`verdict/graph/nodes.py` consume and update it.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from verdict.graph.reducers import append_executor_results
from verdict.schemas.mode import Mode


class GraphState(TypedDict, total=False):
    """Mutable per-case state carried through the LangGraph topology.

    Fields are `total=False` because not every super-step populates every
    field (e.g., `quorum_verdict` is only set after `quorum_node` runs).
    Reducer-annotated fields (`executor_results`) are merged across parallel
    fanout branches — see W2.B.4.
    """

    # Identity (immutable post case_init)
    case_id: str
    mode: Mode

    # Plan-then-Execute artifacts (mutable across replans)
    plan: dict[str, Any] | None
    plan_critique: dict[str, Any] | None
    comprehension_consensus: bool | None

    # Fanout merge — reducer-annotated so 4 branches concatenate
    # deterministically rather than racing.
    executor_results: Annotated[list[dict[str, Any]], append_executor_results]

    # Pivot + replan budgets
    pivot_count: int
    replan_count: int

    # Quorum outcome (one of VerdictStatus values; see CLAUDE.md §3.6)
    quorum_verdict: str | None
    contested_hint: str | None

    # Final findings (post-finalize)
    findings: list[dict[str, Any]]
