from __future__ import annotations

from verdict.graph.reducers import ExecutorResult, merge_executor_results


def test_4_executors_merge_deterministically() -> None:
    results = [
        ExecutorResult(executor_id="executor-3", output_id="out-3"),
        ExecutorResult(executor_id="executor-1", output_id="out-1"),
        ExecutorResult(executor_id="executor-4", output_id="out-4"),
        ExecutorResult(executor_id="executor-2", output_id="out-2"),
    ]
    merged = merge_executor_results([], results)

    assert [result.executor_id for result in merged] == [
        "executor-1",
        "executor-2",
        "executor-3",
        "executor-4",
    ]
