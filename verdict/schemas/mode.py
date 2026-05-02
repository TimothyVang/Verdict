"""Mode enum — operational mode for VERDICT cases.

Three modes, auto-detected at case_init and locked (CLAUDE.md §3.4).
"""

from __future__ import annotations

from enum import Enum


class Mode(str, Enum):
    """Operational mode locked at case_init.

    Inherits from str for JSON/JSONL serialisation compatibility.
    """

    CLOUD = "cloud"
    AIRGAP = "airgap"
    DUAL = "dual"
