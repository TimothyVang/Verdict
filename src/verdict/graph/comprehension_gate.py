from __future__ import annotations

from typing import Literal

from verdict.schemas.plan import PlanComprehensionEcho


def comprehension_gate(echoes: list[PlanComprehensionEcho]) -> Literal["executor_work", "clarify"]:
    if not echoes:
        return "clarify"

    first = _consensus_key(echoes[0])
    if all(_consensus_key(echo) == first for echo in echoes[1:]):
        return "executor_work"
    return "clarify"


def _consensus_key(echo: PlanComprehensionEcho) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    return (
        tuple(echo.parsed_positive_hypothesis_ids),
        tuple(echo.parsed_negative_hypothesis_ids),
        echo.parsed_success_criteria_hash,
    )


def build_comprehension_mismatch_event(echoes: list[PlanComprehensionEcho]) -> dict:
    if not echoes:
        return {"event_type": "comprehension_mismatch", "plan_id": None, "diffs": []}

    baseline = echoes[0]
    diffs = []
    for echo in echoes[1:]:
        diffs.extend(_diff_echo(baseline, echo))

    return {"event_type": "comprehension_mismatch", "plan_id": baseline.plan_id, "diffs": diffs}


def _diff_echo(baseline: PlanComprehensionEcho, echo: PlanComprehensionEcho) -> list[dict]:
    fields = (
        "parsed_positive_hypothesis_ids",
        "parsed_negative_hypothesis_ids",
        "parsed_success_criteria_hash",
    )
    diffs = []
    for field in fields:
        expected = getattr(baseline, field)
        actual = getattr(echo, field)
        if actual != expected:
            diffs.append(
                {
                    "executor_id": echo.executor_id,
                    "field": field,
                    "expected": expected,
                    "actual": actual,
                },
            )
    return diffs
