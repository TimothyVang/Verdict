from __future__ import annotations

from verdict.graph.topology import build_graph
from verdict.runtime.mode_detect import Mode


def test_planner_critique_is_wired_before_comprehension_gate() -> None:
    graph = build_graph(Mode.AIRGAP)

    assert set(graph.nodes) == {
        "planner",
        "planner_critique",
        "comprehension_gate",
        "executor_fanout",
        "pivot",
        "quorum",
        "replan",
        "finalize",
    }
    assert graph.entrypoint == "planner"
    assert graph.edges["planner"] == "planner_critique"
    assert graph.edges["planner_critique"] == "comprehension_gate"
    assert graph.edges["comprehension_gate"] == "executor_fanout"
    assert graph.edges["executor_fanout"] == "pivot"
    assert graph.edges["pivot"] == "quorum"
    assert graph.edges["quorum"] == "finalize"
