"""verdict reverify <case_id> --mode <mode> — parallel verdict chain re-run.

Creates a NEW case with a derived ID (``<original_case_id>.reverify-<mode>``)
and re-runs ONLY the quorum nodes against the existing executor outputs from
the original case.  NEVER mutates the original case's ledger.

CLAUDE.md §3.4:
  "Mode change is via ``verdict reverify --mode <m>`` only — that creates a
  **parallel verdict chain**, never mutating the original."

Full quorum-node wiring is implemented in W3.A; this module provides the
CLI entry point and the case-forking logic needed for W3.C.
"""

from __future__ import annotations

import typer

from verdict.runtime.case_store import ledger_path, write_case_init_entry
from verdict.schemas.ledger import LedgerEntry
from verdict.schemas.mode import Mode

try:
    from ulid import ULID

    def _new_ulid() -> str:
        return str(ULID())

except ImportError:  # pragma: no cover — python-ulid always present per pyproject.toml
    import uuid

    def _new_ulid() -> str:  # type: ignore[misc]
        return str(uuid.uuid4())


app = typer.Typer(add_completion=False)

# ---------------------------------------------------------------------------
# Parallel chain ID convention
# ---------------------------------------------------------------------------

REVERIFY_SUFFIX_FMT = "{original_case_id}.reverify-{mode}"


def derive_reverify_case_id(original_case_id: str, mode: Mode) -> str:
    """Return the derived case ID for a reverify run.

    Format: ``<original_case_id>.reverify-<mode>``

    Examples
    --------
    >>> derive_reverify_case_id("01HX3A", Mode.DUAL)
    '01HX3A.reverify-dual'
    """
    return REVERIFY_SUFFIX_FMT.format(
        original_case_id=original_case_id,
        mode=mode.value,
    )


# ---------------------------------------------------------------------------
# Reverify logic
# ---------------------------------------------------------------------------


def create_reverify_chain(original_case_id: str, mode: Mode) -> str:
    """Fork a new parallel verdict chain from an existing case.

    Steps:
    1.  Derive a new case ID: ``<original>.<reverify-mode>``.
    2.  Assert the original case's ledger exists and is untouched.
    3.  Write a ``case_init`` LedgerEntry for the new case with the
        requested mode.  (Full quorum re-run is W3.A; this step seeds the
        ledger for the new chain.)
    4.  Return the new case ID.

    The original case is **never written to**.

    Parameters
    ----------
    original_case_id:
        The case ID of the original case whose executor outputs will be
        re-verified.
    mode:
        The target ``Mode`` for the parallel chain.

    Returns
    -------
    str
        The new case ID for the reverify chain.

    Raises
    ------
    FileNotFoundError
        If the original case's ledger does not exist.
    FileExistsError
        If a reverify chain for this ``(original_case_id, mode)`` pair already
        exists (to prevent accidental overwrites).
    """
    # 1. Confirm original case exists.
    original_ledger = ledger_path(original_case_id)
    if not original_ledger.exists():
        raise FileNotFoundError(
            f"Original case ledger not found: {original_ledger}. "
            f"Cannot create reverify chain."
        )

    # 2. Derive new case ID.
    new_case_id = derive_reverify_case_id(original_case_id, mode)

    # 3. Guard against re-creation.
    new_ledger = ledger_path(new_case_id)
    if new_ledger.exists():
        raise FileExistsError(
            f"Reverify chain {new_case_id!r} already exists at {new_ledger}. "
            f"Delete it first if you want to re-run."
        )

    # 4. Write the case_init entry for the new chain.
    import datetime

    entry = LedgerEntry(
        entry_id=_new_ulid(),
        case_id=new_case_id,
        event_type="case_init",
        timestamp_utc=datetime.datetime.now(datetime.UTC),
        mode_at_case_init=mode,
        verifier_strategy_used="",
        langfuse_session_id=new_case_id,
        langgraph_thread_id=new_case_id,
        payload={
            "reverify_of": original_case_id,
            "reverify_mode": mode.value,
        },
    )
    write_case_init_entry(entry)

    return new_case_id


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


@app.command()
def reverify(
    case_id: str = typer.Argument(..., help="Original case ID to re-verify"),
    mode: Mode = typer.Option(..., "--mode", help="Mode to run the reverify chain in"),
) -> None:
    """Create a parallel verdict chain and re-run quorum under a new mode.

    Does NOT mutate the original case.  Creates a new case ID of the form
    ``<case_id>.reverify-<mode>`` and writes a fresh ledger for that chain.
    """
    try:
        new_case_id = create_reverify_chain(case_id, mode)
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    except FileExistsError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(
        f"Reverify chain created: {new_case_id}\n"
        f"Original case {case_id!r} is untouched.\n"
        f"Run 'verdict status {new_case_id}' to monitor progress."
    )
    # TODO(W3.A): invoke quorum_node(s) against original executor outputs.
