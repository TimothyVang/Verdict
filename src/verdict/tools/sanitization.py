from __future__ import annotations

import re

from verdict.schemas.tool_output import ToolOutput

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("IGNORE_PREVIOUS", re.compile(r"IGNORE\s+PREVIOUS", re.IGNORECASE)),
    ("SYSTEM", re.compile(r"(^|\n)\s*SYSTEM\s*:", re.IGNORECASE)),
    ("TOOL_CALL_CLOSE", re.compile(r"</tool_call>", re.IGNORECASE)),
    ("INST", re.compile(r"\[INST\]", re.IGNORECASE)),
    ("INSTRUCTION_HEADER", re.compile(r"###\s*Instruction", re.IGNORECASE)),
)


def scan_tool_stdout(stdout: str) -> list[str]:
    return [flag for flag, pattern in _PATTERNS if pattern.search(stdout)]


def apply_sanitization_flags(output: ToolOutput, *, stdout: str) -> ToolOutput:
    return output.model_copy(update={"sanitization_flags": scan_tool_stdout(stdout)})
