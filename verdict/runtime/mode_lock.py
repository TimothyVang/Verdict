"""Mode-lock enforcement for VERDICT.

CLAUSE.md §3.4 mandate:
  - ``LedgerEntry.mode_at_case_init`` is set once at case_init and immutable.
  - ``verdict resume <case_id>`` reads the original mode and refuses to advance
    if ``detect_mode() != mode_at_case_init``.
  - On mismatch: raise ``ModeLockedError``, exit 2, print canonical error to stderr.
  - Mode change is via ``verdict reverify --mode <m>`` only — that creates a
    parallel verdict chain, never mutating the original.

This module provides:
  - ``ModeLockedError`` — the exception raised on mode mismatch.
  - ``assert_mode_lock(case_id, original_mode, current_mode)`` — the enforcement
    function called by ``verdict resume`` before advancing the LangGraph thread.
"""

from __future__ import annotations

import sys

from verdict.schemas.mode import Mode


class ModeLockedError(RuntimeError):
    """Raised when ``verdict resume`` detects a mode mismatch.

    The caller (``verdict resume``) is responsible for catching this exception,
    printing the canonical message to stderr, and exiting with code 2.

    Attributes
    ----------
    case_id:
        The case being resumed.
    original_mode:
        The ``Mode`` locked at ``case_init``.
    detected_mode:
        The ``Mode`` autodetected in the current environment.
    """

    def __init__(self, case_id: str, original_mode: Mode, detected_mode: Mode) -> None:
        self.case_id = case_id
        self.original_mode = original_mode
        self.detected_mode = detected_mode
        super().__init__(self._canonical_message())

    def _canonical_message(self) -> str:
        return (
            f"Case {self.case_id} was initialized in mode={self.original_mode.value}; "
            f"current environment is mode={self.detected_mode.value}. "
            f"To re-run under the new mode, use: "
            f"verdict reverify {self.case_id} --mode {self.detected_mode.value}"
        )


def assert_mode_lock(case_id: str, original_mode: Mode, current_mode: Mode) -> None:
    """Enforce mode lock before resuming a case.

    Compares the mode stored in the ledger's first ``case_init`` entry against
    the mode autodetected in the current environment.  If they differ, raises
    ``ModeLockedError`` with the canonical error message (CLAUDE.md §3.4).

    Parameters
    ----------
    case_id:
        The case ID being resumed.
    original_mode:
        The ``Mode`` value read from ``LedgerEntry.mode_at_case_init`` of the
        ``case_init`` event for this case.
    current_mode:
        The ``Mode`` value returned by ``detect_mode()`` in the current
        environment.

    Raises
    ------
    ModeLockedError
        When ``original_mode != current_mode``.
    """
    if original_mode != current_mode:
        raise ModeLockedError(
            case_id=case_id,
            original_mode=original_mode,
            detected_mode=current_mode,
        )


def resume_mode_check_and_exit(
    case_id: str, original_mode: Mode, current_mode: Mode
) -> None:
    """Check mode lock and exit(2) with canonical stderr message on mismatch.

    This is the function called by the ``verdict resume`` CLI handler.
    It is a thin wrapper around ``assert_mode_lock`` that catches
    ``ModeLockedError``, writes to stderr, and calls ``sys.exit(2)``.

    If modes match, returns normally (no-op).

    Parameters
    ----------
    case_id:
        The case ID being resumed.
    original_mode:
        Mode locked at ``case_init``.
    current_mode:
        Mode detected in the current environment.
    """
    try:
        assert_mode_lock(case_id, original_mode, current_mode)
    except ModeLockedError as exc:
        sys.stderr.write(str(exc) + "\n")
        sys.stderr.flush()
        sys.exit(2)
