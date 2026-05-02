"""W3.E.3 — verdict resume <case_id> CLI command tests.

BUILD_PLAN W3.E.3: "Failing test: kill -9 + restart picks up from
last super-step."

Tests verify that verdict/cli/resume.py:
  - resume_case(case_id, db_path) re-attaches to the last checkpoint
    written before the simulated kill-9
  - resume_case() raises ModeLockedError (exit 2) when original mode
    no longer matches the detected environment
  - The returned ResumeResult carries case_id + latest_checkpoint_id

No mocks against verdict.* internals (CLAUDE.md §3.10).
Tests use a real SqliteCheckpointer + real StateGraph in tmp_path.
"""
from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import pytest
from langgraph.graph import END, START, StateGraph

from verdict.cli.resume import ResumeResult, resume_case
from verdict.graph.checkpoint import ModeLockedError, open_checkpointer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class StepState(TypedDict):
    steps: int


def tick(state: StepState) -> StepState:
    return {"steps": state["steps"] + 1}


def _build_tick_graph(cp):
    builder = StateGraph(StepState)
    builder.add_node("tick", tick)
    builder.add_edge(START, "tick")
    builder.add_edge("tick", END)
    return builder.compile(checkpointer=cp)


# ---------------------------------------------------------------------------
# W3.E.3.a — resume picks up from last super-step
# ---------------------------------------------------------------------------


def test_resume_case_picks_up_from_last_checkpoint(tmp_path: Path) -> None:
    """resume_case() returns a ResumeResult whose snapshot reflects the last
    checkpoint written before the 'kill-9'."""
    db_path = tmp_path / "checkpoint.db"
    case_id = "case-resume-cli-001"

    # --- Phase 1: run the graph (simulates the initial verdict init run) ---
    with open_checkpointer(db_path) as cp:
        graph = _build_tick_graph(cp)
        graph.invoke({"steps": 0}, config={"configurable": {"thread_id": case_id}})

    # --- Phase 2: simulate process restart + verdict resume ---
    result = resume_case(
        case_id=case_id,
        db_path=db_path,
        original_mode="cloud",
        detected_mode="cloud",
    )

    assert isinstance(result, ResumeResult)
    assert result.case_id == case_id
    assert result.snapshot is not None, "resume_case must find the persisted checkpoint"
    assert result.snapshot.values["steps"] == 1, (
        f"Expected steps=1 from checkpoint, got {result.snapshot.values['steps']}"
    )


def test_resume_case_returns_none_snapshot_when_no_checkpoint_exists(tmp_path: Path) -> None:
    """resume_case() returns snapshot=None when there is no checkpoint yet."""
    db_path = tmp_path / "fresh.db"
    case_id = "case-resume-fresh"

    result = resume_case(
        case_id=case_id,
        db_path=db_path,
        original_mode="airgap",
        detected_mode="airgap",
    )

    assert result.case_id == case_id
    # No prior checkpoint → snapshot is None (not an error)
    assert result.snapshot is None


def test_resume_case_result_has_case_id(tmp_path: Path) -> None:
    """ResumeResult.case_id equals the passed case_id."""
    db_path = tmp_path / "id_check.db"
    case_id = "case-id-check-xyz"

    with open_checkpointer(db_path) as cp:
        graph = _build_tick_graph(cp)
        graph.invoke({"steps": 5}, config={"configurable": {"thread_id": case_id}})

    result = resume_case(
        case_id=case_id,
        db_path=db_path,
        original_mode="dual",
        detected_mode="dual",
    )
    assert result.case_id == case_id


# ---------------------------------------------------------------------------
# W3.E.3 + W3.E.4 — mode-lock check on resume
# ---------------------------------------------------------------------------


def test_resume_case_raises_mode_locked_error_on_mode_drift(tmp_path: Path) -> None:
    """resume_case() raises ModeLockedError when original_mode != detected_mode."""
    db_path = tmp_path / "mode_drift.db"
    case_id = "case-mode-drift"

    # Write a checkpoint first.
    with open_checkpointer(db_path) as cp:
        graph = _build_tick_graph(cp)
        graph.invoke({"steps": 0}, config={"configurable": {"thread_id": case_id}})

    with pytest.raises(ModeLockedError) as exc_info:
        resume_case(
            case_id=case_id,
            db_path=db_path,
            original_mode="cloud",
            detected_mode="airgap",
        )

    err = exc_info.value
    assert err.exit_code == 2
    assert case_id in str(err)
    assert "mode=cloud" in str(err)
    assert "mode=airgap" in str(err)
    assert f"verdict reverify {case_id} --mode airgap" in str(err)


def test_resume_case_mode_locked_error_is_exit_2(tmp_path: Path) -> None:
    """ModeLockedError.exit_code == 2 so the CLI handler can sys.exit(2)."""
    db_path = tmp_path / "exit2.db"
    case_id = "case-exit2"

    with pytest.raises(ModeLockedError) as exc_info:
        resume_case(
            case_id=case_id,
            db_path=db_path,
            original_mode="dual",
            detected_mode="cloud",
        )

    assert exc_info.value.exit_code == 2
