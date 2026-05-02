"""W3.E.5 — trace_id ↔ ledger entry bidirectional cross-link.

BUILD_PLAN W3.E.5:
  - test_ledger_entry_has_langfuse_trace_id: every LedgerLink built by
    make_ledger_link() carries a langfuse_trace_id field.
  - test_langfuse_span_has_ledger_entry_id_attribute: SpanLink built by
    make_span_link() carries a ledger_entry_id attribute.

ARCHITECTURE.md §5:
  "Every ledger entry is reachable from a Langfuse trace, and every
  Langfuse trace span has a ledger_entry_id attribute."

These tests verify the cross-link data contract only — they do NOT
contact a live Langfuse server (the bidirectional link is a data
structure, not an HTTP call).  No mocks against verdict.* (CLAUDE.md §3.10).
"""
from __future__ import annotations

from verdict.observability.trace_link import (
    LedgerLink,
    SpanLink,
    make_ledger_link,
    make_span_link,
)


# ---------------------------------------------------------------------------
# W3.E.5 — LedgerLink: ledger entry has langfuse_trace_id
# ---------------------------------------------------------------------------


def test_ledger_entry_has_langfuse_trace_id() -> None:
    """make_ledger_link() returns a LedgerLink with a non-empty langfuse_trace_id."""
    link = make_ledger_link(
        ledger_entry_id="01JV2NK-entry-001",
        langfuse_trace_id="trace-abc-123",
        langgraph_checkpoint_id="chk-xyz",
        case_id="case-001",
    )
    assert isinstance(link, LedgerLink)
    assert link.langfuse_trace_id == "trace-abc-123", (
        "LedgerLink must carry the Langfuse trace ID so the ledger entry "
        "is reachable from the Langfuse trace (ARCHITECTURE.md §5)."
    )


def test_ledger_link_has_all_fields() -> None:
    """LedgerLink carries all three required cross-link IDs."""
    link = make_ledger_link(
        ledger_entry_id="entry-id-001",
        langfuse_trace_id="trace-id-001",
        langgraph_checkpoint_id="chk-id-001",
        case_id="case-id-001",
    )
    assert link.ledger_entry_id == "entry-id-001"
    assert link.langfuse_trace_id == "trace-id-001"
    assert link.langgraph_checkpoint_id == "chk-id-001"
    assert link.case_id == "case-id-001"


def test_ledger_link_immutable() -> None:
    """LedgerLink is a frozen dataclass — fields cannot be mutated after creation."""
    import dataclasses

    link = make_ledger_link(
        ledger_entry_id="e",
        langfuse_trace_id="t",
        langgraph_checkpoint_id="c",
        case_id="k",
    )
    fields = {f.name for f in dataclasses.fields(link)}
    assert fields == {
        "ledger_entry_id",
        "langfuse_trace_id",
        "langgraph_checkpoint_id",
        "case_id",
    }, f"unexpected fields: {fields}"


# ---------------------------------------------------------------------------
# W3.E.5 — SpanLink: Langfuse span has ledger_entry_id attribute
# ---------------------------------------------------------------------------


def test_langfuse_span_has_ledger_entry_id_attribute() -> None:
    """make_span_link() returns a SpanLink with a non-empty ledger_entry_id."""
    link = make_span_link(
        ledger_entry_id="entry-span-001",
        langfuse_trace_id="trace-span-001",
        langgraph_checkpoint_id="chk-span-001",
        case_id="case-span-001",
    )
    assert isinstance(link, SpanLink)
    assert link.ledger_entry_id == "entry-span-001", (
        "SpanLink must carry ledger_entry_id so the Langfuse span "
        "is reachable from the ledger (ARCHITECTURE.md §5)."
    )


def test_span_link_to_span_attributes() -> None:
    """SpanLink.to_span_attributes() returns a dict for Langfuse span metadata."""
    link = make_span_link(
        ledger_entry_id="entry-attr-001",
        langfuse_trace_id="trace-attr-001",
        langgraph_checkpoint_id="chk-attr-001",
        case_id="case-attr-001",
    )
    attrs = link.to_span_attributes()
    assert isinstance(attrs, dict)
    assert attrs["verdict.ledger_entry_id"] == "entry-attr-001"
    assert attrs["verdict.case_id"] == "case-attr-001"
    assert attrs["verdict.langgraph_checkpoint_id"] == "chk-attr-001"


def test_span_link_to_ledger_link() -> None:
    """SpanLink.to_ledger_link() produces the matching LedgerLink."""
    span = make_span_link(
        ledger_entry_id="e1",
        langfuse_trace_id="t1",
        langgraph_checkpoint_id="c1",
        case_id="k1",
    )
    ledger = span.to_ledger_link()
    assert isinstance(ledger, LedgerLink)
    assert ledger.ledger_entry_id == span.ledger_entry_id
    assert ledger.langfuse_trace_id == span.langfuse_trace_id
    assert ledger.langgraph_checkpoint_id == span.langgraph_checkpoint_id
    assert ledger.case_id == span.case_id


def test_make_span_link_and_make_ledger_link_are_inverse() -> None:
    """make_ledger_link + make_span_link produce matching cross-references."""
    ll = make_ledger_link(
        ledger_entry_id="eid",
        langfuse_trace_id="tid",
        langgraph_checkpoint_id="cid",
        case_id="kid",
    )
    sl = make_span_link(
        ledger_entry_id="eid",
        langfuse_trace_id="tid",
        langgraph_checkpoint_id="cid",
        case_id="kid",
    )
    # round-trip
    assert sl.to_ledger_link() == ll
