"""W2.B.1 — `build_graph(mode)` compiles the 9-node topology.

Per BUILD_PLAN W2.B.1.a the gate test asserts that the five **core** nodes
(`planner`, `executor_fanout`, `quorum`, `replan`, `finalize`) exist on the
compiled graph. Per CLAUDE.md §4 / ARCHITECTURE.md §2 the actual topology is
**9 nodes**, so we extend the gate to assert all 9.

We assert against the compiled-graph node registry directly rather than
inspecting `graph.get_graph()`'s mermaid output — the registry is the
source of truth and doesn't depend on rendering helpers.
"""

from __future__ import annotations

import pytest

from verdict.graph.topology import NINE_NODES, build_graph
from verdict.schemas.mode import Mode


def _node_names(compiled) -> set[str]:
    """Return the set of node names registered on a compiled LangGraph.

    LangGraph exposes the node registry on the compiled graph; START/END
    are framework-internal and we strip them so the assertion compares
    user-defined nodes only.
    """
    raw_names = set(compiled.get_graph().nodes.keys())
    return {n for n in raw_names if n not in {"__start__", "__end__"}}


@pytest.mark.parametrize("mode", [Mode.CLOUD, Mode.AIRGAP, Mode.DUAL])
def test_five_core_nodes_present(mode: Mode) -> None:
    """W2.B.1.a — five core nodes present on the compiled graph."""
    compiled = build_graph(mode)
    names = _node_names(compiled)
    five_core = {"planner", "executor_fanout", "quorum", "replan", "finalize"}
    assert five_core.issubset(names), (
        f"missing core nodes {five_core - names} in {mode.value} mode; "
        f"found {sorted(names)}"
    )


@pytest.mark.parametrize("mode", [Mode.CLOUD, Mode.AIRGAP, Mode.DUAL])
def test_all_nine_nodes_present(mode: Mode) -> None:
    """ARCHITECTURE.md §2 — full 9-node topology is mode-invariant."""
    compiled = build_graph(mode)
    names = _node_names(compiled)
    expected = set(NINE_NODES)
    assert names == expected, (
        f"node set mismatch in {mode.value}; "
        f"missing={expected - names}, extra={names - expected}"
    )


def test_build_graph_rejects_str_mode() -> None:
    """`build_graph` must refuse a raw 'cloud' string — a frequent typo
    that silently bypasses Mode-enum invariants downstream.
    """
    with pytest.raises(TypeError, match="Mode enum"):
        build_graph("cloud")  # type: ignore[arg-type]


def test_planner_is_entry_point() -> None:
    """START must connect to `planner` per ARCHITECTURE.md §2."""
    compiled = build_graph(Mode.CLOUD)
    edges = compiled.get_graph().edges
    # LangGraph edge tuples are (source, target). The framework-internal
    # source for START is "__start__".
    sources_of_planner = {e.source for e in edges if e.target == "planner"}
    assert "__start__" in sources_of_planner, (
        f"START is not connected to planner; sources_of_planner={sources_of_planner}"
    )


def test_finalize_and_unverifiable_finalize_terminate() -> None:
    """Both terminal nodes must connect to END; otherwise UNVERIFIABLE
    cases would loop forever (CLAUDE.md §3.6 — UNVERIFIABLE is a
    first-class outcome, not a hidden failure)."""
    compiled = build_graph(Mode.CLOUD)
    edges = compiled.get_graph().edges
    end_sources = {e.source for e in edges if e.target == "__end__"}
    assert {"finalize", "unverifiable_finalize"}.issubset(end_sources), (
        f"terminal nodes do not connect to END; end_sources={end_sources}"
    )
