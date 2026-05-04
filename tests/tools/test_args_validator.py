from __future__ import annotations

import pytest
from pydantic import BaseModel

from verdict.schemas.verdict_status import VerdictStatus
from verdict.tools.args_validators import ArgsValidationExhausted, ArgsValidator, ModelRetry


class VolPsScanArgs(BaseModel):
    pid: int | None = None


def test_unknown_flag_raises_modelretry() -> None:
    validator = ArgsValidator(
        tool_name="vol3.windows.psscan",
        args_model=VolPsScanArgs,
        allowed_flags={"--pid"},
    )

    with pytest.raises(ModelRetry, match="unknown flag: --foo"):
        validator.validate(["--foo", "1234"])


def test_invalid_pid_type_raises() -> None:
    validator = ArgsValidator(
        tool_name="vol3.windows.psscan",
        args_model=VolPsScanArgs,
        allowed_flags={"--pid"},
    )

    with pytest.raises(ModelRetry, match="pid"):
        validator.validate(["--pid", "not-an-int"])


def test_retry_budget_two_then_unverifiable() -> None:
    validator = ArgsValidator(
        tool_name="vol3.windows.psscan",
        args_model=VolPsScanArgs,
        allowed_flags={"--pid"},
    )

    for _ in range(2):
        with pytest.raises(ModelRetry):
            validator.validate(["--pid", "not-an-int"])

    with pytest.raises(ArgsValidationExhausted) as exc_info:
        validator.validate(["--pid", "not-an-int"])

    assert exc_info.value.status is VerdictStatus.UNVERIFIABLE
