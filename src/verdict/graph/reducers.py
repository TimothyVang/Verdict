from __future__ import annotations

from pydantic import BaseModel


class ExecutorResult(BaseModel):
    """Single executor branch result merged by fanout reducer."""

    executor_id: str
    output_id: str


def merge_executor_results(
    existing: list[ExecutorResult], incoming: list[ExecutorResult]
) -> list[ExecutorResult]:
    merged = {result.executor_id: result for result in existing}
    merged.update({result.executor_id: result for result in incoming})
    return [merged[executor_id] for executor_id in sorted(merged)]
