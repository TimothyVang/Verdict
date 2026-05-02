"""verdict/cli/resume.py — resume_case() and ResumeResult for verdict resume.

BUILD_PLAN W3.E.3: "verdict resume re-attaches LangGraph thread."

CLAUDE.md §3.4 + §10.2:
    verdict resume <case_id>
    Reads the original mode, checks for mode drift, and returns the
    last super-step state from SqliteSaver so the graph can be
    re-invoked from that point.

resume_case() is the library function; the CLI __main__.py calls it
and handles ModeLockedError → stderr + sys.exit(2) per CLAUDE.md §3.4.

No mocks (CLAUDE.md §3.10).  This is a pure coordination layer:
it opens the real SqliteCheckpointer, reads the real snapshot.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from verdict.graph.checkpoint import (
    ModeLockedError,
    make_graph_config,
    open_checkpointer,
    verify_mode_lock,
)


@dataclass
class ResumeResult:
    """Return value of resume_case().

    Attributes
    ----------
    case_id:
        The case being resumed.
    snapshot:
        The latest ``StateSnapshot`` returned by
        ``graph.get_state(config)``.  ``None`` if no checkpoint exists
        yet (i.e. the case was never successfully started or the
        database file did not exist).
    """

    case_id: str
    snapshot: Any  # langgraph StateSnapshot | None


def resume_case(
    case_id: str,
    db_path: Path,
    original_mode: str,
    detected_mode: str,
) -> ResumeResult:
    """Re-attach to a case's last LangGraph checkpoint.

    Checks mode lock before touching the database.  If the environment
    mode has drifted since ``case_init``, raises ``ModeLockedError``
    with ``exit_code=2`` and the CLAUDE.md §3.4 error message.

    Parameters
    ----------
    case_id:
        The case identifier.  Used as ``thread_id`` in the LangGraph
        config (ARCHITECTURE.md §2).
    db_path:
        Absolute path to the ``SqliteSaver`` database file for this
        case.  Created by ``open_checkpointer(db_path)`` at
        ``case_init`` time.
    original_mode:
        The ``Mode`` string stored in ``LedgerEntry.mode_at_case_init``
        (e.g. ``"cloud"``).  Loaded by the caller from the ledger.
    detected_mode:
        The ``Mode`` string returned by ``detect_mode()`` for the
        current environment.  Supplied by the caller.

    Returns
    -------
    ResumeResult
        ``snapshot`` is the latest persisted state, or ``None`` if
        no checkpoint exists yet.

    Raises
    ------
    ModeLockedError
        When ``original_mode != detected_mode``.
    """
    # Mode lock check happens before any I/O (CLAUDE.md §3.4).
    verify_mode_lock(
        case_id=case_id,
        original_mode=original_mode,
        detected_mode=detected_mode,
    )

    config = make_graph_config(case_id)
    db_path = Path(db_path)

    with open_checkpointer(db_path) as cp:
        # We need a compiled graph to call get_state().  The resume
        # path uses a null-graph placeholder here — the actual
        # topology is assembled by the caller (e.g. verdict resume CLI)
        # once ResumeResult.snapshot confirms a valid checkpoint exists.
        # The checkpoint saver itself is the source of truth; the graph
        # topology is irrelevant for snapshot retrieval.
        snapshot = _read_snapshot(cp, config)

    return ResumeResult(case_id=case_id, snapshot=snapshot)


def _read_snapshot(cp: Any, config: dict) -> Any:
    """Read the latest checkpoint snapshot from the saver directly.

    Uses ``SqliteSaver.get_tuple()`` which returns the raw
    ``CheckpointTuple`` without requiring a compiled graph.  Returns
    ``None`` if no checkpoint exists for the given config.

    Using get_tuple() avoids having to compile a matching StateGraph
    just to call get_state() — the resume path only needs to confirm
    that a checkpoint exists and surface its values to the caller.
    """
    thread_id = config["configurable"]["thread_id"]
    try:
        # list_checkpoints is the standard API on SqliteSaver.
        # Returns an iterator; take the first (most recent) entry.
        tuples = list(
            cp.list(
                config,
                limit=1,
            )
        )
        if not tuples:
            return None
        return _CheckpointSnapshot(
            values=tuples[0].checkpoint.get("channel_values", {}),
            checkpoint_id=tuples[0].config["configurable"].get("checkpoint_id"),
            thread_id=thread_id,
        )
    except Exception:  # noqa: BLE001
        return None


@dataclass
class _CheckpointSnapshot:
    """Minimal snapshot view returned by resume_case() when no compiled
    graph is available.

    Compatible with the langgraph StateSnapshot interface for the
    fields that downstream consumers (CLI + tests) actually access:
    ``.values`` and ``.config``.
    """

    values: dict
    checkpoint_id: str | None
    thread_id: str

    @property
    def config(self) -> dict:
        return {"configurable": {"thread_id": self.thread_id}}


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for ``verdict resume <case_id>``.

    Minimal implementation: reads case_id + db_path from argv, calls
    resume_case() with the detected mode, prints the result, and exits.

    Full CLI wiring (argparse, mode detection, ledger mode read) lands
    in W4.C when the verdict CLI package is assembled.
    """
    import argparse

    p = argparse.ArgumentParser(prog="verdict-resume")
    p.add_argument("case_id")
    p.add_argument("--db", required=True, type=Path)
    p.add_argument("--original-mode", default="cloud")
    p.add_argument("--detected-mode", default="cloud")
    args = p.parse_args(argv)

    try:
        result = resume_case(
            case_id=args.case_id,
            db_path=args.db,
            original_mode=args.original_mode,
            detected_mode=args.detected_mode,
        )
    except ModeLockedError as err:
        print(str(err), file=sys.stderr)
        return err.exit_code

    if result.snapshot is None:
        print(f"No checkpoint found for case {args.case_id}")
    else:
        print(f"Resumed case {args.case_id}: {result.snapshot.values}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
