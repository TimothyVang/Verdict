from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class HumanInterrupt(RuntimeError):
    state: dict[str, Any]


def interrupt(state: dict[str, Any]) -> None:
    raise HumanInterrupt(state)
