"""`build_graph(mode)` — compile the 9-node Plan-then-Execute LangGraph.

Topology (per `docs/ARCHITECTURE.md` §2):

    START
      v
    planner_node
      v
    planner_critique_node
      |   `--(fail)--> planner_node
      v
    comprehension_gate_node
      |   `--(disagreement)--> replan_node
      v
    executor_fanout_node            (4 parallel branches merged via reducer)
      v
    pivot_node
      |   `--(pending hypothesis & budget)--> executor_fanout_node
      v
    quorum_node
      |--(VETTED_*)--> finalize_node --> END
      |--(CONTESTED)--> replan_node
      |       |--(<= replan_max)--> planner_node
      |       `--(> replan_max)--> unverifiable_finalize_node
      `--(UNVERIFIABLE)--> unverifiable_finalize_node --> END

Mode argument selects the verifier strategy used by `quorum_node` but does
NOT change the topology — the 9 nodes and the routing edges are identical
across cloud / airgap / dual. (CLAUDE.md §3.4 mode-lock invariance.)
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from verdict.graph.nodes import (
    ROUTE_CRITIQUE_FAIL,
    ROUTE_CRITIQUE_PASS,
    ROUTE_GATE_PASS,
    ROUTE_GATE_REPLAN,
    ROUTE_REPLAN_EXHAUSTED,
    ROUTE_REPLAN_RETRY,
    ROUTE_UNVERIFIABLE,
    ROUTE_VETTED,
    comprehension_gate_node,
    executor_fanout_node,
    finalize_node,
    pivot_node,
    planner_critique_node,
    planner_node,
    quorum_node,
    replan_node,
    route_after_critique,
    route_after_gate,
    route_after_pivot,
    route_after_quorum,
    route_after_replan,
    unverifiable_finalize_node,
)
from verdict.graph.state import GraphState
from verdict.schemas.mode import Mode

# The canonical 9-node set. Order is documentation-only — LangGraph stores
# nodes in an unordered dict and edges define the actual flow.
NINE_NODES: tuple[str, ...] = (
    "planner",
    "planner_critique",
    "comprehension_gate",
    "executor_fanout",
    "pivot",
    "quorum",
    "replan",
    "unverifiable_finalize",
    "finalize",
)


def build_graph(mode: Mode) -> CompiledStateGraph:
    """Compile the 9-node Plan-then-Execute graph for `mode`.

    `mode` is carried through to runtime via initial state; quorum_node
    uses it to dispatch the right `VerifierStrategy`. The topology itself
    is mode-invariant.
    """

    if not isinstance(mode, Mode):  # narrow: catches "cloud" str typo
        raise TypeError(
            f"build_graph(mode) expects Mode enum, got {type(mode).__name__}"
        )

    graph: StateGraph = StateGraph(GraphState)

    # 1. planner
    graph.add_node("planner", planner_node)
    # 2. planner_critique
    graph.add_node("planner_critique", planner_critique_node)
    # 3. comprehension_gate
    graph.add_node("comprehension_gate", comprehension_gate_node)
    # 4. executor_fanout
    graph.add_node("executor_fanout", executor_fanout_node)
    # 5. pivot
    graph.add_node("pivot", pivot_node)
    # 6. quorum
    graph.add_node("quorum", quorum_node)
    # 7. replan
    graph.add_node("replan", replan_node)
    # 8. unverifiable_finalize
    graph.add_node("unverifiable_finalize", unverifiable_finalize_node)
    # 9. finalize
    graph.add_node("finalize", finalize_node)

    # Entry
    graph.add_edge(START, "planner")

    # planner -> planner_critique
    graph.add_edge("planner", "planner_critique")

    # planner_critique -> {planner | comprehension_gate}
    graph.add_conditional_edges(
        "planner_critique",
        route_after_critique,
        {
            ROUTE_CRITIQUE_FAIL: "planner",
            ROUTE_CRITIQUE_PASS: "comprehension_gate",
        },
    )

    # comprehension_gate -> {executor_fanout | replan}
    graph.add_conditional_edges(
        "comprehension_gate",
        route_after_gate,
        {
            ROUTE_GATE_PASS: "executor_fanout",
            ROUTE_GATE_REPLAN: "replan",
        },
    )

    # executor_fanout -> pivot
    graph.add_edge("executor_fanout", "pivot")

    # pivot -> {executor_fanout | quorum}
    graph.add_conditional_edges(
        "pivot",
        route_after_pivot,
        {
            "executor_fanout": "executor_fanout",
            "quorum": "quorum",
        },
    )

    # quorum -> {finalize | replan | unverifiable_finalize}
    graph.add_conditional_edges(
        "quorum",
        route_after_quorum,
        {
            ROUTE_VETTED: "finalize",
            "replan": "replan",
            ROUTE_UNVERIFIABLE: "unverifiable_finalize",
        },
    )

    # replan -> {planner | unverifiable_finalize}
    graph.add_conditional_edges(
        "replan",
        route_after_replan,
        {
            ROUTE_REPLAN_RETRY: "planner",
            ROUTE_REPLAN_EXHAUSTED: "unverifiable_finalize",
        },
    )

    # Terminal nodes
    graph.add_edge("finalize", END)
    graph.add_edge("unverifiable_finalize", END)

    return graph.compile()
