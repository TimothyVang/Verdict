from __future__ import annotations

from enum import StrEnum


class VerdictStatus(StrEnum):
    """Canonical forensic verdict status values."""

    VETTED_CLOUD = "VETTED_CLOUD"
    VETTED_AIRGAP = "VETTED_AIRGAP"
    VETTED_DUAL = "VETTED_DUAL"
    CONTESTED = "CONTESTED"
    UNVERIFIABLE = "UNVERIFIABLE"
    EXHAUSTED_REPLAN = "EXHAUSTED_REPLAN"
