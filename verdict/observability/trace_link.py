"""verdict/observability/trace_link.py — bidirectional trace_id ↔ ledger cross-link.

ARCHITECTURE.md §5:
    "Every ledger entry is reachable from a Langfuse trace, and every
    Langfuse trace span has a ledger_entry_id attribute. Judges can
    drill in either direction: ledger → trace → tool call → microsandbox
    version → file hash; or trace → ledger entry → finding rationale."

BUILD_PLAN W3.E.5:
    make_ledger_link()   — produces LedgerLink (for ledger writer)
    make_span_link()     — produces SpanLink (for Langfuse span attrs)

This module is pure data — no Langfuse HTTP calls, no SQLite I/O.
The Langfuse client (verdict/observability/langfuse_setup.py, W1.A.7)
consumes SpanLink.to_span_attributes() to annotate spans.  The ledger
writer (verdict/ledger/writer.py, W2.G.1) stores LedgerLink fields in
LedgerEntry.

Public API:
    LedgerLink        — frozen dataclass; ledger-side cross-reference
    SpanLink          — frozen dataclass; span-side cross-reference
    make_ledger_link  — factory for LedgerLink
    make_span_link    — factory for SpanLink
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, eq=True)
class LedgerLink:
    """Ledger-side cross-reference to a Langfuse trace span.

    Stored as fields on every ``LedgerEntry`` so a judge can navigate
    from a ledger entry to the matching Langfuse trace without full-text
    search (ARCHITECTURE.md §5 bidirectional link).

    Fields
    ------
    ledger_entry_id:
        ULID of the ``LedgerEntry`` this link belongs to.
    langfuse_trace_id:
        Langfuse trace ID (one per ``graph.invoke()`` call, per
        ARCHITECTURE.md §5).
    langgraph_checkpoint_id:
        The LangGraph checkpoint ID at the time this ledger entry was
        written, for precise timeline reconstruction.
    case_id:
        Root case identifier (``thread_id`` in LangGraph terms).
    """

    ledger_entry_id: str
    langfuse_trace_id: str
    langgraph_checkpoint_id: str
    case_id: str


@dataclass(frozen=True, eq=True)
class SpanLink:
    """Span-side cross-reference to a VERDICT ledger entry.

    Attached to every Langfuse span via ``span.update(metadata=...)``
    or ``span.score(...)`` so a judge can navigate from a Langfuse span
    to the matching ledger entry (ARCHITECTURE.md §5 bidirectional link).

    Fields
    ------
    ledger_entry_id:
        ULID of the matching ``LedgerEntry``.  This is the primary
        "span has ledger_entry_id" attribute required by ARCHITECTURE.md §5.
    langfuse_trace_id:
        Langfuse trace ID (same value on both sides of the link).
    langgraph_checkpoint_id:
        LangGraph checkpoint ID, enabling timeline reconstruction.
    case_id:
        Root case identifier.
    """

    ledger_entry_id: str
    langfuse_trace_id: str
    langgraph_checkpoint_id: str
    case_id: str

    def to_span_attributes(self) -> dict[str, str]:
        """Return a metadata dict suitable for attaching to a Langfuse span.

        Keys are prefixed with ``verdict.`` to namespace them in the
        Langfuse UI and avoid collisions with built-in Langfuse metadata.

        Example::

            span.update(metadata=link.to_span_attributes())
        """
        return {
            "verdict.ledger_entry_id": self.ledger_entry_id,
            "verdict.langfuse_trace_id": self.langfuse_trace_id,
            "verdict.langgraph_checkpoint_id": self.langgraph_checkpoint_id,
            "verdict.case_id": self.case_id,
        }

    def to_ledger_link(self) -> LedgerLink:
        """Return the matching LedgerLink for this span.

        Enables round-trip testing: ``make_span_link(...).to_ledger_link()``
        must equal ``make_ledger_link(...)`` with the same arguments.
        """
        return LedgerLink(
            ledger_entry_id=self.ledger_entry_id,
            langfuse_trace_id=self.langfuse_trace_id,
            langgraph_checkpoint_id=self.langgraph_checkpoint_id,
            case_id=self.case_id,
        )


def make_ledger_link(
    *,
    ledger_entry_id: str,
    langfuse_trace_id: str,
    langgraph_checkpoint_id: str,
    case_id: str,
) -> LedgerLink:
    """Factory for LedgerLink.

    Called by ``verdict/ledger/writer.py::LedgerEmitter`` when
    constructing each ``LedgerEntry``.

    All arguments are keyword-only to prevent positional confusion
    between the four ID strings.
    """
    return LedgerLink(
        ledger_entry_id=ledger_entry_id,
        langfuse_trace_id=langfuse_trace_id,
        langgraph_checkpoint_id=langgraph_checkpoint_id,
        case_id=case_id,
    )


def make_span_link(
    *,
    ledger_entry_id: str,
    langfuse_trace_id: str,
    langgraph_checkpoint_id: str,
    case_id: str,
) -> SpanLink:
    """Factory for SpanLink.

    Called by ``verdict/observability/langfuse_setup.py`` (W1.A.7)
    when creating or updating a Langfuse span so the span carries
    the ``verdict.ledger_entry_id`` metadata attribute required by
    ARCHITECTURE.md §5.

    All arguments are keyword-only.
    """
    return SpanLink(
        ledger_entry_id=ledger_entry_id,
        langfuse_trace_id=langfuse_trace_id,
        langgraph_checkpoint_id=langgraph_checkpoint_id,
        case_id=case_id,
    )


__all__ = [
    "LedgerLink",
    "SpanLink",
    "make_ledger_link",
    "make_span_link",
]
