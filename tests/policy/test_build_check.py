from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts import build_check


def test_command_timeout_is_blocked() -> None:
    gate = build_check.Gate(
        name="slow-command",
        tier="fast",
        task_id="W1.A.9",
        command=(sys.executable, "-c", "import time; time.sleep(2)"),
        timeout_seconds=0.1,
    )

    result = build_check.run_gate(gate)

    assert result.status is build_check.Status.BLOCKED
    assert result.exit_code is None
    assert "timed out" in result.detail


def test_resume_skips_previously_passing_gate(tmp_path: Path) -> None:
    state_path = tmp_path / "build-check-state.json"
    gate = build_check.Gate(
        name="python-ok",
        tier="fast",
        task_id="W1.A.9",
        command=(sys.executable, "-c", "print('ok')"),
        timeout_seconds=5,
    )

    first = build_check.run_gates([gate], state_path=state_path, resume=False)
    second = build_check.run_gates([gate], state_path=state_path, resume=True)

    assert [result.status for result in first] == [build_check.Status.PASS]
    assert [result.status for result in second] == [build_check.Status.SKIP]
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["gates"]["python-ok"]["status"] == "PASS"


def test_runtime_gate_nonzero_can_be_classified_as_blocked() -> None:
    gate = build_check.Gate(
        name="runtime-prereq",
        tier="runtime",
        task_id="W1.A.5",
        command=(sys.executable, "-c", "raise SystemExit(1)"),
        timeout_seconds=5,
        nonzero_status=build_check.Status.BLOCKED,
    )

    result = build_check.run_gate(gate)

    assert result.status is build_check.Status.BLOCKED
    assert result.exit_code == 1


def test_policy_config_covers_src_verdict() -> None:
    result = build_check.check_policy_config(Path(".pre-commit-config.yaml"))

    assert result.status is build_check.Status.PASS


def test_select_gates_expands_fast_tier() -> None:
    gates = build_check.select_gates(["fast"])

    gate_names = {gate.name for gate in gates}
    assert "policy-no-mocks" in gate_names
    assert "lint" in gate_names
    assert "tests" in gate_names
