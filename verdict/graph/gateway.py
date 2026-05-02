"""verdict/graph/gateway.py — CaseGateway: graph invocation with thread_id=case_id.

ARCHITECTURE.md §2 (Checkpointing):
    "thread_id = case_id everywhere."

BUILD_PLAN W3.E.2: gateway invocation passes
    config={"configurable": {"thread_id": case_id}}.

CaseGateway wraps a compiled LangGraph graph and ensures every
invocation (invoke / stream / get_state) pins the LangGraph
configurable thread_id to the case's stable identifier.  This is the
single place in the codebase that calls make_graph_config() — callers
should never construct their own config dicts.

No mocks (CLAUDE.md §3.10).  CaseGateway is a pure coordination
object; its contract is testable with a real StateGraph + real
SqliteCheckpointer.
"""
from __future__ import annotations

from typing import Any, Iterator

from verdict.graph.checkpoint import make_graph_config


class CaseGateway:
    """Wraps a compiled LangGraph and pins every call to thread_id=case_id.

    Parameters
    ----------
    graph:
        A ``CompiledGraph`` (returned by ``StateGraph.compile(checkpointer=…)``).
        The graph must already be compiled with a real ``SqliteCheckpointer``
        so checkpoints are persisted across invocations.
    case_id:
        The VERDICT case identifier.  Used verbatim as LangGraph's
        ``thread_id``.  Must be unique per investigation.
    checkpointer:
        The ``SqliteCheckpointer`` the graph was compiled with.
        Stored here for future use by ``verdict validate`` and
        ``verdict gc`` — not used in the invoke/stream/get_state path
        directly (the graph holds the reference).

    Usage::

        with open_checkpointer(db_path) as cp:
            graph = builder.compile(checkpointer=cp)
            gw = CaseGateway(graph=graph, case_id=case_id, checkpointer=cp)
            result = gw.invoke(initial_state)
            snapshot = gw.get_state()
    """

    def __init__(
        self,
        graph: Any,
        case_id: str,
        checkpointer: Any,
    ) -> None:
        self._graph = graph
        self._case_id = case_id
        self._checkpointer = checkpointer
        self._config = make_graph_config(case_id)

    @property
    def case_id(self) -> str:
        """The case identifier this gateway is bound to."""
        return self._case_id

    @property
    def config(self) -> dict:
        """The LangGraph config dict (``{"configurable": {"thread_id": case_id}}``)."""
        return self._config

    def invoke(self, state: Any, **kwargs: Any) -> Any:
        """Invoke the graph with thread_id=case_id.

        Parameters
        ----------
        state:
            Initial state dict passed to ``graph.invoke()``.
        **kwargs:
            Extra keyword arguments forwarded to ``graph.invoke()``.
            A ``config`` kwarg will be merged with the gateway's own
            config (gateway's thread_id takes precedence).

        Returns
        -------
        The final state dict returned by the graph.
        """
        config = {**kwargs.pop("config", {}), **self._config}
        return self._graph.invoke(state, config=config, **kwargs)

    def stream(self, state: Any, **kwargs: Any) -> Iterator[Any]:
        """Stream the graph with thread_id=case_id.

        Yields each chunk emitted by ``graph.stream()``.

        Parameters
        ----------
        state:
            Initial state dict.
        **kwargs:
            Extra keyword arguments forwarded to ``graph.stream()``.
        """
        config = {**kwargs.pop("config", {}), **self._config}
        yield from self._graph.stream(state, config=config, **kwargs)

    def get_state(self) -> Any:
        """Return the latest persisted checkpoint for this case.

        Delegates to ``graph.get_state(config)`` using the gateway's
        thread_id.  Returns ``None`` if no checkpoint exists yet.
        """
        return self._graph.get_state(self._config)


__all__ = ["CaseGateway"]
