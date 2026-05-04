from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from verdict.schemas.verdict_status import VerdictStatus

TOOL_ARG_RETRY_MAX = 2


class ModelRetry(ValueError):
    """Recoverable tool-argument validation error for planner retry."""


class ArgsValidationExhausted(RuntimeError):
    """Raised when invalid tool args exceed the retry budget."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.status = VerdictStatus.UNVERIFIABLE


@dataclass
class ArgsValidator:
    tool_name: str
    args_model: type[BaseModel]
    allowed_flags: set[str]
    retry_budget: int = TOOL_ARG_RETRY_MAX
    _failed_attempts: int = field(default=0, init=False)

    def validate(self, invocation_args: Sequence[str]) -> BaseModel:
        try:
            parsed = self._parse_flags(invocation_args)
            return self.args_model.model_validate(parsed)
        except (ModelRetry, ValidationError) as exc:
            self._failed_attempts += 1
            message = f"{self.tool_name} args invalid: {exc}"
            if self._failed_attempts > self.retry_budget:
                raise ArgsValidationExhausted(message) from exc
            raise ModelRetry(message) from exc

    def _parse_flags(self, invocation_args: Sequence[str]) -> dict[str, Any]:
        parsed: dict[str, Any] = {}
        index = 0
        while index < len(invocation_args):
            flag = invocation_args[index]
            if not flag.startswith("--"):
                raise ModelRetry(f"expected flag, got: {flag}")
            if flag not in self.allowed_flags:
                raise ModelRetry(f"unknown flag: {flag}")
            if index + 1 >= len(invocation_args) or invocation_args[index + 1].startswith("--"):
                raise ModelRetry(f"missing value for flag: {flag}")
            parsed[flag.removeprefix("--").replace("-", "_")] = invocation_args[index + 1]
            index += 2
        return parsed
