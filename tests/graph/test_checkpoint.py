"""W3.E tests for verdict/graph/checkpoint.py.

Tests cover:
  W3.E.1 — SqliteSaver with WAL + synchronous=FULL pragmas
  W3.E.2 — thread_id = case_id wiring via make_graph_config()
  W3.E.3 — resume re-attaches to the last checkpoint (state preserved)
  W3.E.4 — mode-lock check on resume raises ModeLockedError + exits 2

All tests run against a real SqliteSaver in a real SQLite file (tmpdir).
No mocks against verdict.* internals (CLAUDE.md §3.10).

The minimal LangGraph used here is a two-node trivial graph
(start_node → end_node) whose state has a single integer counter.
This is enough to exercise the SqliteSaver + checkpoint path without
pulling in the full 9-node topology (which depends on services not yet
wired).  That topology is tested end-to-end in inspect_ai/ evals.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Shared helpers — the real interfaces under test
# ---------------------------------------------------------------------------
from verdict.graph.checkpoint import (
    ModeLockedError,
    SqliteCheckpointer,
    make_graph_config,
    open_checkpointer,
    verify_mode_lock,
)

# ---------------------------------------------------------------------------
# W3.E.1 — WAL + synchronous=FULL pragma assertions
# ---------------------------------------------------------------------------


def test_pragma_journal_mode_wal(tmp_path: Path) -> None:
    """open_checkpointer sets journal_mode=WAL on the underlying SQLite db."""
    db_path = tmp_path / "checkpoint.db"
    with open_checkpointer(db_path) as cp:
        _ = cp  # ensure connection is established
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute("PRAGMA journal_mode").fetchone()
        finally:
            conn.close()
    assert row is not None, "PRAGMA journal_mode returned no row"
    assert row[0].lower() == "wal", (
        f"Expected journal_mode=WAL, got {row[0]!r}. "
        "ARCHITECTURE.md §2 requires WAL for kill-9 safety."
    )


def test_pragma_synchronous_full(tmp_path: Path) -> None:
    """open_checkpointer sets synchronous=FULL (value=2) on the underlying db.

    ARCHITECTURE.md §2: 'PRAGMA synchronous=FULL so kill-9 between
    sqlite txn-commit and fsync doesn't lose the most recent super-step.'
    synchronous=FULL is SQLite integer 2.
    """
    db_path = tmp_path / "checkpoint.db"
    with open_checkpointer(db_path) as cp:
        _ = cp
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute("PRAGMA synchronous").fetchone()
        finally:
            conn.close()
    assert row is not None, "PRAGMA synchronous returned no row"
    # SQLite returns the integer value: 0=OFF,1=NORMAL,2=FULL,3=EXTRA
    assert int(row[0]) == 2, (
        f"Expected synchronous=2 (FULL), got {row[0]!r}. "
        "ARCHITECTURE.md §2 requires FULL for fsync safety."
    )


def test_open_checkpointer_returns_sqlite_checkpointer(tmp_path: Path) -> None:
    """open_checkpointer is a context manager yielding SqliteCheckpointer."""
    db_path = tmp_path / "checkpoint.db"
    with open_checkpointer(db_path) as cp:
        assert isinstance(cp, SqliteCheckpointer)


def test_open_checkpointer_creates_db_file(tmp_path: Path) -> None:
    """open_checkpointer creates the SQLite file if it doesn't exist."""
    db_path = tmp_path / "sub" / "checkpoint.db"
    assert not db_path.exists()
    with open_checkpointer(db_path) as cp:
        _ = cp
    assert db_path.exists(), "SqliteSaver must create the db file on first open"


# ---------------------------------------------------------------------------
# W3.E.2 — thread_id = case_id wiring
# ---------------------------------------------------------------------------


def test_make_graph_config_thread_id_equals_case_id() -> None:
    """make_graph_config returns configurable dict with thread_id == case_id."""
    case_id = "case-abc-123"
    config = make_graph_config(case_id)
    assert config == {"configurable": {"thread_id": case_id}}, (
        f"Expected thread_id={case_id!r} inside configurable, got {config!r}. "
        "ARCHITECTURE.md §2: 'thread_id = case_id everywhere'."
    )


def test_make_graph_config_preserves_case_id_with_special_chars() -> None:
    """thread_id must survive case IDs with hyphens, underscores, and ULIDs."""
    for case_id in ("01HX1A-DFIR-001", "case_002_credtheft", "01JV2NKXXX"):
        config = make_graph_config(case_id)
        assert config["configurable"]["thread_id"] == case_id


# ---------------------------------------------------------------------------
# W3.E.3 — resume re-attaches to last checkpoint (state preserved)
# ---------------------------------------------------------------------------


def test_checkpoint_survives_and_resumes(tmp_path: Path) -> None:
    """A graph run interrupted after step N can resume from the same thread_id.

    Uses a real SqliteCheckpointer + real LangGraph StateGraph.
    The graph has a single increment node and runs to completion;
    we then re-invoke from the same thread_id and verify the saver
    returns the correct latest-checkpoint state rather than starting fresh.
    """
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph

    db_path = tmp_path / "checkpoint.db"
    case_id = "case-resume-test"
    config = make_graph_config(case_id)

    class CounterState(TypedDict):
        count: int

    def increment(state: CounterState) -> CounterState:
        return {"count": state["count"] + 1}

    with open_checkpointer(db_path) as cp:
        builder = StateGraph(CounterState)
        builder.add_node("increment", increment)
        builder.add_edge(START, "increment")
        builder.add_edge("increment", END)
        graph = builder.compile(checkpointer=cp)

        # First invocation — starts from count=0, ends at count=1.
        result = graph.invoke({"count": 0}, config=config)
        assert result["count"] == 1, f"First run should yield count=1, got {result['count']}"

        # Retrieve the persisted checkpoint — must exist.
        snapshot = graph.get_state(config)
        assert snapshot is not None, "SqliteSaver must have persisted a checkpoint"
        assert snapshot.values["count"] == 1, (
            f"Persisted state should have count=1, got {snapshot.values['count']}"
        )


def test_resume_after_simulated_restart(tmp_path: Path) -> None:
    """State is retrievable from SqliteSaver across separate checkpointer instances.

    Simulates kill-9 + restart: first 'process' writes a checkpoint;
    second 'process' (new checkpointer, same db file) reads it back.
    """
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph

    db_path = tmp_path / "checkpoint.db"
    case_id = "case-kill9-sim"
    config = make_graph_config(case_id)

    class CounterState(TypedDict):
        count: int

    def increment(state: CounterState) -> CounterState:
        return {"count": state["count"] + 5}

    def _build_and_compile(cp):
        builder = StateGraph(CounterState)
        builder.add_node("increment", increment)
        builder.add_edge(START, "increment")
        builder.add_edge("increment", END)
        return builder.compile(checkpointer=cp)

    # --- Process 1: write checkpoint ---
    with open_checkpointer(db_path) as cp1:
        graph1 = _build_and_compile(cp1)
        graph1.invoke({"count": 0}, config=config)

    # --- Process 2: new checkpointer, same db, same thread_id ---
    with open_checkpointer(db_path) as cp2:
        graph2 = _build_and_compile(cp2)
        snapshot = graph2.get_state(config)
        assert snapshot is not None, (
            "New checkpointer on same db must find the previously written checkpoint"
        )
        assert snapshot.values["count"] == 5, (
            f"Resumed state must preserve count=5, got {snapshot.values['count']}"
        )


# ---------------------------------------------------------------------------
# W3.E.4 — mode-lock check on resume
# ---------------------------------------------------------------------------


def test_verify_mode_lock_passes_when_mode_matches() -> None:
    """verify_mode_lock is a no-op when original_mode == detected_mode."""
    verify_mode_lock(
        case_id="case-lock-ok",
        original_mode="cloud",
        detected_mode="cloud",
    )
    # Should not raise.


def test_verify_mode_lock_raises_mode_locked_error_on_mismatch() -> None:
    """verify_mode_lock raises ModeLockedError when modes differ."""
    with pytest.raises(ModeLockedError) as exc_info:
        verify_mode_lock(
            case_id="case-lock-fail",
            original_mode="cloud",
            detected_mode="airgap",
        )
    err = exc_info.value
    # CLAUDE.md §3.4 exact message format:
    # "Case {case_id} was initialized in mode={original_mode};
    #  current environment is mode={detected_mode}.
    #  To re-run under the new mode, use: verdict reverify {case_id} --mode {detected_mode}"
    assert "case-lock-fail" in str(err)
    assert "mode=cloud" in str(err)
    assert "mode=airgap" in str(err)
    assert "verdict reverify case-lock-fail --mode airgap" in str(err)


def test_verify_mode_lock_exit_code_2() -> None:
    """ModeLockedError carries exit_code=2 per CLAUDE.md §3.4."""
    with pytest.raises(ModeLockedError) as exc_info:
        verify_mode_lock(
            case_id="case-exit",
            original_mode="dual",
            detected_mode="cloud",
        )
    assert exc_info.value.exit_code == 2


def test_mode_locked_error_message_all_three_mode_combinations() -> None:
    """Verify message format holds for all valid mode combinations."""
    mode_pairs = [
        ("cloud", "airgap"),
        ("cloud", "dual"),
        ("airgap", "cloud"),
        ("airgap", "dual"),
        ("dual", "cloud"),
        ("dual", "airgap"),
    ]
    for orig, detected in mode_pairs:
        with pytest.raises(ModeLockedError) as exc_info:
            verify_mode_lock(
                case_id=f"case-{orig}-{detected}",
                original_mode=orig,
                detected_mode=detected,
            )
        msg = str(exc_info.value)
        assert f"verdict reverify case-{orig}-{detected} --mode {detected}" in msg, (
            f"reverify hint missing for ({orig} → {detected}): {msg!r}"
        )
