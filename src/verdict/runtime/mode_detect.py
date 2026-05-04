from __future__ import annotations

from enum import Enum

from verdict.planning.planner import CloudPlanner, LocalPlanner, Planner


class Mode(str, Enum):
    """Operational mode detected at case initialization and locked thereafter."""

    CLOUD = "CLOUD"
    AIRGAP = "AIRGAP"
    DUAL = "DUAL"


def bind_planner_at_gateway_init(mode: Mode) -> Planner:
    if mode is Mode.AIRGAP:
        return LocalPlanner()
    return CloudPlanner()
