"""Operational mode enum.

`Mode` is the locked-at-case_init enum that drives verifier-strategy dispatch
and node selection (see `docs/ARCHITECTURE.md` §1, `CLAUDE.md` §3.4 mode lock).

Auto-detection lives in `verdict/runtime/mode_detect.py` (W5.A.1). Once a case
is initialised under a mode, the value is written to
`LedgerEntry.mode_at_case_init` and is **immutable** for the lifetime of the
case. `verdict resume <case_id>` refuses to advance under a different mode.
"""

from __future__ import annotations

from enum import Enum


class Mode(str, Enum):
    """Locked operational mode for a Verdict case.

    The three modes are total — every supported deployment maps to exactly one.
    Adding a 4th "test" mode is explicitly forbidden (see
    `swarm/agents/planning-engineer.md` anti-patterns).
    """

    CLOUD = "cloud"
    AIRGAP = "airgap"
    DUAL = "dual"
