"""W3.E.2 — thread_id = case_id wiring at the gateway invocation layer.

BUILD_PLAN W3.E.2: "Failing test: gateway invocation passes
config={"configurable": {"thread_id": case_id}}."

The gateway is the entrypoint that calls graph.invoke() / graph.stream()
for a given case. This test verifies that:

  1. CaseGateway.invoke() passes thread_id=case_id in its config.
  2. CaseGateway.stream() passes thread_id=case_id in its config.
  3. CaseGateway.get_state() passes thread_id=case_id in its config.

Tests use a real LangGraph StateGraph with SqliteCheckpointer (real
SQLite in tmp_path) and a real CaseGateway.  No mocks against
verdict.* internals (CLAUDE.md §3.10).
"""
from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import pytest
from langgraph.graph import END, START, StateGraph

from verdict.graph.gateway import CaseGateway
from verdict.graph.checkpoint import make_graph_config, open_checkpointer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class SimpleState(TypedDict):
    value: int


def double(state: SimpleState) -> SimpleState:
    return {"value": state["value"] * 2}


def _build_simple_graph(cp):
    builder = StateGraph(SimpleState)
    builder.add_node("double", double)
    builder.add_edge(START, "double")
    builder.add_edge("double", END)
    return builder.compile(checkpointer=cp)


# ---------------------------------------------------------------------------
# W3.E.2 — CaseGateway passes thread_id=case_id
# ---------------------------------------------------------------------------


def test_case_gateway_invoke_uses_case_id_as_thread_id(tmp_path: Path) -> None:
    """CaseGateway.invoke() must pass thread_id=case_id so SqliteSaver
    stores the checkpoint under the case's stable identifier."""
    db_path = tmp_path / "gw_invoke.db"
    case_id = "case-gw-invoke-001"

    with open_checkpointer(db_path) as cp:
        graph = _build_simple_graph(cp)
        gw = CaseGateway(graph=graph, case_id=case_id, checkpointer=cp)

        result = gw.invoke({"value": 3})
        assert result["value"] == 6, f"Expected 6, got {result['value']}"

        # Verify the checkpoint was stored under thread_id=case_id
        config = make_graph_config(case_id)
        snapshot = graph.get_state(config)
        assert snapshot is not None, (
            f"Expected a checkpoint under thread_id={case_id!r}"
        )
        assert snapshot.values["value"] == 6


def test_case_gateway_get_state_uses_case_id(tmp_path: Path) -> None:
    """CaseGateway.get_state() returns the state stored under case_id."""
    db_path = tmp_path / "gw_state.db"
    case_id = "case-gw-state-002"

    with open_checkpointer(db_path) as cp:
        graph = _build_simple_graph(cp)
        gw = CaseGateway(graph=graph, case_id=case_id, checkpointer=cp)

        gw.invoke({"value": 10})
        snapshot = gw.get_state()

        assert snapshot is not None, "get_state() must return the persisted checkpoint"
        assert snapshot.values["value"] == 20


def test_case_gateway_stream_uses_case_id(tmp_path: Path) -> None:
    """CaseGateway.stream() iterates output and stores under case_id."""
    db_path = tmp_path / "gw_stream.db"
    case_id = "case-gw-stream-003"

    with open_checkpointer(db_path) as cp:
        graph = _build_simple_graph(cp)
        gw = CaseGateway(graph=graph, case_id=case_id, checkpointer=cp)

        chunks = list(gw.stream({"value": 4}))
        assert chunks, "stream() must yield at least one chunk"

        # Final persisted state must be under thread_id=case_id
        config = make_graph_config(case_id)
        snapshot = graph.get_state(config)
        assert snapshot is not None
        assert snapshot.values["value"] == 8


def test_case_gateway_different_cases_isolated(tmp_path: Path) -> None:
    """Two gateways with different case_ids must write to distinct thread rows."""
    db_path = tmp_path / "gw_isolation.db"
    case_a = "case-isolation-A"
    case_b = "case-isolation-B"

    with open_checkpointer(db_path) as cp:
        graph = _build_simple_graph(cp)
        gw_a = CaseGateway(graph=graph, case_id=case_a, checkpointer=cp)
        gw_b = CaseGateway(graph=graph, case_id=case_b, checkpointer=cp)

        gw_a.invoke({"value": 2})
        gw_b.invoke({"value": 7})

        snap_a = gw_a.get_state()
        snap_b = gw_b.get_state()

        assert snap_a.values["value"] == 4, f"Case A: expected 4, got {snap_a.values['value']}"
        assert snap_b.values["value"] == 14, f"Case B: expected 14, got {snap_b.values['value']}"
