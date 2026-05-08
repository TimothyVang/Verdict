from __future__ import annotations

from dataclasses import dataclass

from verdict.runtime.mode_detect import Mode

WRITE_FLAGS = {
    "--csv",
    "--dir",
    "--dump-dir",
    "--export",
    "--output",
    "--output-dir",
    "--out",
    "--write",
    "-o",
}


class DeniedToolCallError(RuntimeError):
    """Raised when a tool invocation would violate evidence immutability."""


@dataclass(frozen=True)
class DenyRuleWrapper:
    """Layer-2 evidence immutability guard that applies in every mode."""

    mode: Mode

    def validate(self, *, tool_name: str, args: list[str]) -> None:
        del tool_name
        for index, arg in enumerate(args):
            if arg in WRITE_FLAGS and index + 1 < len(args):
                _deny_evidence_output(args[index + 1])
            if "=" in arg:
                flag, value = arg.split("=", 1)
                if flag in WRITE_FLAGS:
                    _deny_evidence_output(value)


def _deny_evidence_output(path: str) -> None:
    if path == "/evidence" or path.startswith("/evidence/"):
        raise DeniedToolCallError("Tool invocation attempts to write under /evidence")
