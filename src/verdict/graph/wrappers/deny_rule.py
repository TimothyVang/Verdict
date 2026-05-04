from __future__ import annotations

from dataclasses import dataclass

from verdict.runtime.mode_detect import Mode


class DeniedToolCallError(RuntimeError):
    """Raised when a tool invocation would violate evidence immutability."""


@dataclass(frozen=True)
class DenyRuleWrapper:
    """Layer-2 evidence immutability guard that applies in every mode."""

    mode: Mode

    def validate(self, *, tool_name: str, args: list[str]) -> None:
        del tool_name
        for arg in args:
            if arg == "/evidence" or arg.startswith("/evidence/"):
                raise DeniedToolCallError("Tool invocation attempts to write under /evidence")
