"""LangGraph topology for VERDICT's Plan-then-Execute state machine.

The 9 nodes (see `docs/ARCHITECTURE.md` §2):

    planner -> planner_critique -> comprehension_gate
        -> executor_fanout (n=4 parallel branches)
        -> pivot -> quorum
        -> {finalize | replan -> planner | unverifiable_finalize}

Use `build_graph(mode)` to compile a graph for a locked operational mode.
"""

from verdict.graph.topology import build_graph

__all__ = ["build_graph"]
