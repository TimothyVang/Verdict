"""verdict/graph/checkpoint.py — SqliteSaver with WAL + synchronous=FULL.

ARCHITECTURE.md §2 (Checkpointing):
    "Graph is checkpointed at every super-step via SqliteSaver with
    PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL so kill-9 between
    sqlite txn-commit and fsync doesn't lose the most recent super-step.
    thread_id = case_id everywhere."

CLAUDE.md §3.4 (Mode lock):
    "verdict resume <case_id> reads the original mode and refuses to
    advance if the current detect_mode() differs. On mismatch it raises
    ModeLockedError, exits 2, and prints to stderr:
      Case {case_id} was initialized in mode={original_mode};
      current environment is mode={detected_mode}.
      To re-run under the new mode, use:
        verdict reverify {case_id} --mode {detected_mode}"

Public API (W3.E.1 / W3.E.2 / W3.E.3 / W3.E.4):
    open_checkpointer(db_path)    — context manager → SqliteCheckpointer
    make_graph_config(case_id)    — LangGraph configurable dict
    verify_mode_lock(...)         — raises ModeLockedError on drift
    ModeLockedError               — SystemExit-compatible, exit_code=2
    SqliteCheckpointer            — re-export of the underlying type
"""
from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

# Re-export so callers can isinstance-check without importing langgraph directly.
SqliteCheckpointer = SqliteSaver


# ---------------------------------------------------------------------------
# WAL + synchronous=FULL setup
# ---------------------------------------------------------------------------

_SETUP_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=FULL",
)


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply durability pragmas to an existing sqlite3 connection.

    Runs inside the same connection that SqliteSaver uses, before any
    LangGraph checkpointing activity touches the database.  Called once
    per open_checkpointer() invocation so every write session starts
    with the correct durability posture.

    ARCHITECTURE.md §2: WAL + FULL are the two pragmas required for
    kill-9 safety at super-step granularity.
    """
    for pragma in _SETUP_PRAGMAS:
        conn.execute(pragma)


@contextmanager
def open_checkpointer(db_path: Path) -> Generator[SqliteCheckpointer, None, None]:
    """Open a WAL-backed SqliteSaver for the given database path.

    Creates the database file and all parent directories if needed.
    Applies `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=FULL`
    before yielding the checkpointer so the first LangGraph
    checkpoint write is already durable.

    Usage::

        with open_checkpointer(Path("cases/abc/checkpoint.db")) as cp:
            graph = builder.compile(checkpointer=cp)
            graph.invoke(initial_state, config=make_graph_config(case_id))

    Context manager ensures the underlying connection is closed on exit.

    Implementation note: SqliteSaver.from_conn_string() creates the
    connection internally without exposing it for pragma configuration.
    We therefore create the connection ourselves, apply the durability
    pragmas, then hand it to SqliteSaver (which stores the connection
    as ``saver.conn``).  The connection is closed in the ``finally``
    block regardless of whether the inner work raises.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # check_same_thread=False mirrors SqliteSaver.from_conn_string() —
    # the saver uses a threading.Lock internally for thread safety.
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    try:
        _apply_pragmas(conn)
        saver = SqliteSaver(conn)
        yield saver
    finally:
        with suppress(Exception):
            conn.close()


# ---------------------------------------------------------------------------
# thread_id = case_id wiring (ARCHITECTURE.md §2)
# ---------------------------------------------------------------------------


def make_graph_config(case_id: str) -> dict:
    """Return a LangGraph ``config`` dict that pins ``thread_id`` to ``case_id``.

    Every ``graph.invoke()`` / ``graph.stream()`` / ``graph.get_state()``
    call must pass this config so LangGraph's SqliteSaver stores and
    retrieves checkpoints under the case's stable identifier.

    ARCHITECTURE.md §2: ``thread_id = case_id`` everywhere.

    Example::

        config = make_graph_config("case-001-lolbins")
        graph.invoke(initial_state, config=config)
        snapshot = graph.get_state(config)
    """
    return {"configurable": {"thread_id": case_id}}


# ---------------------------------------------------------------------------
# Mode-lock enforcement (CLAUDE.md §3.4)
# ---------------------------------------------------------------------------


class ModeLockedError(Exception):
    """Raised when resuming a case whose mode no longer matches the environment.

    CLAUDE.md §3.4 exact message format::

        Case {case_id} was initialized in mode={original_mode};
        current environment is mode={detected_mode}.
        To re-run under the new mode, use:
          verdict reverify {case_id} --mode {detected_mode}

    Attributes
    ----------
    exit_code:
        Always 2, per CLAUDE.md §3.4 ("raises ModeLockedError, exits 2").
        The ``verdict resume`` CLI handler calls ``sys.exit(err.exit_code)``
        after printing ``str(err)`` to stderr.
    """

    exit_code: int = 2

    def __init__(
        self,
        case_id: str,
        original_mode: str,
        detected_mode: str,
    ) -> None:
        self.case_id = case_id
        self.original_mode = original_mode
        self.detected_mode = detected_mode
        msg = (
            f"Case {case_id} was initialized in mode={original_mode}; "
            f"current environment is mode={detected_mode}. "
            f"To re-run under the new mode, use: "
            f"verdict reverify {case_id} --mode {detected_mode}"
        )
        super().__init__(msg)


def verify_mode_lock(
    case_id: str,
    original_mode: str,
    detected_mode: str,
) -> None:
    """Assert that the case's original mode matches the current environment.

    Called by ``verdict resume`` after reading ``mode_at_case_init`` from
    the ledger entry and calling ``detect_mode()`` on the live environment.

    Parameters
    ----------
    case_id:
        The case being resumed.
    original_mode:
        The ``Mode`` string stored in ``LedgerEntry.mode_at_case_init``
        (e.g. ``"cloud"``, ``"airgap"``, ``"dual"``).
    detected_mode:
        The ``Mode`` string returned by ``detect_mode()`` for the current
        environment.

    Raises
    ------
    ModeLockedError
        When ``original_mode != detected_mode``.  The exception carries
        ``exit_code=2`` and the CLAUDE.md §3.4 exact message.
    """
    if original_mode != detected_mode:
        raise ModeLockedError(
            case_id=case_id,
            original_mode=original_mode,
            detected_mode=detected_mode,
        )


__all__ = [
    "ModeLockedError",
    "SqliteCheckpointer",
    "make_graph_config",
    "open_checkpointer",
    "verify_mode_lock",
]
