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


def test_runtime_gate_nonzero_json_stdout_surfaces_blocker_codes() -> None:
    gate = build_check.Gate(
        name="runtime-prereq",
        tier="runtime",
        task_id="W1.A.5",
        command=(
            sys.executable,
            "-c",
            (
                "import json; "
                "print(json.dumps({'blockers': "
                "['mode_unconfigured', 'hmac_key_unconfigured']})); "
                "raise SystemExit(1)"
            ),
        ),
        timeout_seconds=5,
        nonzero_status=build_check.Status.BLOCKED,
    )

    result = build_check.run_gate(gate)
    summary = build_check.format_summary([result])

    assert result.status is build_check.Status.BLOCKED
    assert result.detail == "blocked: mode_unconfigured, hmac_key_unconfigured"
    assert "blocked: mode_unconfigured, hmac_key_unconfigured" in summary


def test_runtime_gate_nonzero_json_stderr_surfaces_blocker_codes() -> None:
    gate = build_check.Gate(
        name="runtime-prereq",
        tier="runtime",
        task_id="W1.A.5",
        command=(
            sys.executable,
            "-c",
            (
                "import json, sys; "
                "print(json.dumps({'blockers': ['local_inference_unreachable']}), "
                "file=sys.stderr); "
                "raise SystemExit(1)"
            ),
        ),
        timeout_seconds=5,
        nonzero_status=build_check.Status.BLOCKED,
    )

    result = build_check.run_gate(gate)

    assert result.status is build_check.Status.BLOCKED
    assert result.detail == "blocked: local_inference_unreachable"


def test_runtime_gate_nonzero_invalid_json_keeps_exit_code_fallback() -> None:
    gate = build_check.Gate(
        name="runtime-prereq",
        tier="runtime",
        task_id="W1.A.5",
        command=(sys.executable, "-c", "print('not json'); raise SystemExit(7)"),
        timeout_seconds=5,
        nonzero_status=build_check.Status.BLOCKED,
    )

    result = build_check.run_gate(gate)

    assert result.status is build_check.Status.BLOCKED
    assert result.detail == "command exited 7"


def test_runtime_gate_scans_past_json_without_blockers() -> None:
    gate = build_check.Gate(
        name="runtime-prereq",
        tier="runtime",
        task_id="W1.A.5",
        command=(
            sys.executable,
            "-c",
            (
                "import json; "
                "print(json.dumps({'ready': False})); "
                "print(json.dumps({'blockers': ['mode_unconfigured']})); "
                "raise SystemExit(1)"
            ),
        ),
        timeout_seconds=5,
        nonzero_status=build_check.Status.BLOCKED,
    )

    result = build_check.run_gate(gate)

    assert result.status is build_check.Status.BLOCKED
    assert result.detail == "blocked: mode_unconfigured"


def test_runtime_gate_prefers_json_with_blockers_over_later_json_without_blockers() -> None:
    gate = build_check.Gate(
        name="runtime-prereq",
        tier="runtime",
        task_id="W1.A.5",
        command=(
            sys.executable,
            "-c",
            (
                "import json; "
                "print(json.dumps({'blockers': ['hmac_key_unconfigured']})); "
                "print(json.dumps({'ready': False})); "
                "raise SystemExit(1)"
            ),
        ),
        timeout_seconds=5,
        nonzero_status=build_check.Status.BLOCKED,
    )

    result = build_check.run_gate(gate)

    assert result.status is build_check.Status.BLOCKED
    assert result.detail == "blocked: hmac_key_unconfigured"


def test_runtime_gate_ignores_empty_blocker_lists() -> None:
    gate = build_check.Gate(
        name="runtime-prereq",
        tier="runtime",
        task_id="W1.A.5",
        command=(
            sys.executable,
            "-c",
            (
                "import json, sys; "
                "print(json.dumps({'blockers': []})); "
                "print(json.dumps({'blockers': ['microsandbox_unavailable']}), file=sys.stderr); "
                "raise SystemExit(1)"
            ),
        ),
        timeout_seconds=5,
        nonzero_status=build_check.Status.BLOCKED,
    )

    result = build_check.run_gate(gate)

    assert result.status is build_check.Status.BLOCKED
    assert result.detail == "blocked: microsandbox_unavailable"


def test_policy_config_covers_src_verdict() -> None:
    result = build_check.check_policy_config(Path(".pre-commit-config.yaml"))

    assert result.status is build_check.Status.PASS


def test_select_gates_expands_fast_tier() -> None:
    gates = build_check.select_gates(["fast"])

    gate_names = {gate.name for gate in gates}
    assert "policy-no-mocks" in gate_names
    assert "lint" in gate_names
    assert "tests" in gate_names
