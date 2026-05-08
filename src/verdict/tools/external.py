from __future__ import annotations

from dataclasses import dataclass


class ToolUnavailableError(RuntimeError):
    """Raised when a required forensic binary is not installed on this host."""


@dataclass(frozen=True)
class ExternalToolSpec:
    tool_name: str
    executable_candidates: tuple[str, ...]
    base_args: tuple[str, ...]
    artifact_type: str
    version_args: tuple[str, ...] = ("--version",)
