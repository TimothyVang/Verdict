from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from verdict.graph.nodes import (
    comprehension_gate_node,
    GraphState,
    executor_fanout_node,
    finalize_node,
    planner_critique_node,
    planner_node,
    pivot_node,
    quorum_node,
    replan_node,
)
from verdict.runtime.mode_detect import Mode


@dataclass(frozen=True)
class CompiledGraph:
    """License-clean compiled graph surface until LangGraph can be used without LangSmith."""

    mode: Mode
    nodes: dict[str, Callable[[GraphState], GraphState]]
    edges: dict[str, str]
    entrypoint: str

    def invoke_node(self, name: str, state: GraphState) -> GraphState:
        return self.nodes[name](state)


def build_graph(mode: Mode) -> CompiledGraph:
    return CompiledGraph(
        mode=mode,
        nodes={
            "planner": planner_node,
            "planner_critique": planner_critique_node,
            "comprehension_gate": comprehension_gate_node,
            "executor_fanout": executor_fanout_node,
            "pivot": pivot_node,
            "quorum": quorum_node,
            "replan": replan_node,
            "finalize": finalize_node,
        },
        edges={
            "planner": "planner_critique",
            "planner_critique": "comprehension_gate",
            "comprehension_gate": "executor_fanout",
            "executor_fanout": "pivot",
            "pivot": "quorum",
            "quorum": "finalize",
            "replan": "planner",
        },
        entrypoint="planner",
    )
