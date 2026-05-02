"""verdict resume <case_id> — re-attach to a running or paused case.

Enforces mode lock (CLAUDE.md §3.4):
  - Reads ``mode_at_case_init`` from the first ``case_init`` ledger entry.
  - Calls ``detect_mode()`` to probe the current environment.
  - If they differ, writes the canonical error message to stderr and exits 2.

Full LangGraph thread re-attachment is implemented in W3.E.3; this module
provides the mode-lock gate that sits at the top of that flow.
"""

from __future__ import annotations

import sys

import typer

from verdict.runtime.case_store import read_case_init_mode
from verdict.runtime.mode_detect import detect_mode
from verdict.runtime.mode_lock import ModeLockedError, assert_mode_lock

app = typer.Typer(add_completion=False)


@app.command()
def resume(
    case_id: str = typer.Argument(..., help="Case ID to resume"),
) -> None:
    """Re-attach to an existing case, enforcing mode lock.

    Exits 2 with a canonical error message if the current environment's
    mode differs from the mode locked at case_init.
    """
    # 1. Read the mode that was locked at case_init.
    try:
        original_mode = read_case_init_mode(case_id)
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    # 2. Detect the current environment's mode.
    try:
        current_mode = detect_mode()
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    # 3. Enforce mode lock — raises ModeLockedError on mismatch.
    try:
        assert_mode_lock(case_id, original_mode, current_mode)
    except ModeLockedError as exc:
        sys.stderr.write(str(exc) + "\n")
        sys.stderr.flush()
        raise typer.Exit(2) from exc

    # 4. Mode matches — proceed to re-attach the LangGraph thread (W3.E.3).
    typer.echo(f"Resuming case {case_id} in mode={original_mode.value} …")
    # TODO(W3.E.3): re-attach SqliteSaver thread and invoke graph.
