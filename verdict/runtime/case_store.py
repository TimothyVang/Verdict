"""CaseStore — minimal read layer over cases/<id>/ledger.jsonl.

Used by ``verdict resume`` to read the ``mode_at_case_init`` from the first
``case_init`` LedgerEntry of a case.

The write path (LedgerWriter, HMAC signing, fsync, verify-readback) is
implemented in W3.B (``verdict/ledger/writer.py``).  This module is strictly
read-only and is scoped to what W3.C needs.

Case storage layout (ARCHITECTURE.md §9 / §5):
    cases/
      <case_id>/
        ledger.jsonl      ← one JSON object per line
        (other files added by later phases)

The ``cases/`` root defaults to ``~/.verdict/cases`` and can be overridden
via the ``VERDICT_CASES_DIR`` environment variable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from verdict.schemas.ledger import LedgerEntry
from verdict.schemas.mode import Mode


def _cases_root() -> Path:
    """Return the root directory for case data.

    Defaults to ``~/.verdict/cases``.  Override with ``VERDICT_CASES_DIR``.
    """
    env_val = os.environ.get("VERDICT_CASES_DIR", "")
    if env_val:
        return Path(env_val)
    return Path.home() / ".verdict" / "cases"


def ledger_path(case_id: str) -> Path:
    """Return the path to ``ledger.jsonl`` for the given case."""
    return _cases_root() / case_id / "ledger.jsonl"


def read_case_init_mode(case_id: str) -> Mode:
    """Read the ``mode_at_case_init`` from the first ``case_init`` ledger entry.

    Scans ``ledger.jsonl`` for the first entry whose ``event_type`` is
    ``"case_init"`` and returns its ``mode_at_case_init`` field.

    Parameters
    ----------
    case_id:
        The case ID to look up.

    Returns
    -------
    Mode
        The mode locked at case initialisation.

    Raises
    ------
    FileNotFoundError
        If ``ledger.jsonl`` does not exist for the given case.
    ValueError
        If no ``case_init`` entry is found in the ledger, or if the entry
        cannot be parsed as a ``LedgerEntry``.
    """
    path = ledger_path(case_id)
    if not path.exists():
        raise FileNotFoundError(
            f"Ledger not found for case {case_id!r}. "
            f"Expected: {path}"
        )

    with path.open("r", encoding="utf-8") as fh:
        for line_no, raw_line in enumerate(fh, start=1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Malformed JSON on line {line_no} of {path}: {exc}"
                ) from exc

            if obj.get("event_type") == "case_init":
                entry = LedgerEntry.model_validate(obj)
                return entry.mode_at_case_init

    raise ValueError(
        f"No 'case_init' entry found in ledger for case {case_id!r} ({path})."
    )


def write_case_init_entry(entry: LedgerEntry) -> None:
    """Append a ``case_init`` LedgerEntry to the ledger for its case.

    Creates the case directory if it does not exist.  This is the minimal
    write path needed by the W3.C test fixtures; the production write path
    (with HMAC, fsync, verify-readback) is implemented in W3.B.

    Parameters
    ----------
    entry:
        A ``LedgerEntry`` with ``event_type == "case_init"``.

    Raises
    ------
    ValueError
        If ``entry.event_type != "case_init"``.
    """
    if entry.event_type != "case_init":
        raise ValueError(
            f"write_case_init_entry() only accepts case_init entries; "
            f"got event_type={entry.event_type!r}"
        )

    path = ledger_path(entry.case_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as fh:
        fh.write(entry.model_dump_json() + "\n")
        fh.flush()
        os.fsync(fh.fileno())
