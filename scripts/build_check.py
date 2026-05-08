"""Resumable build blocker checker for VERDICT."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from time import monotonic

SCHEMA_VERSION = 1
DEFAULT_STATE_PATH = Path("build/build-check-state.json")
FAST_TIERS = {"fast"}


class Status(StrEnum):
    """Checker status values with blocker-aware semantics."""

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    WARN = "WARN"
    SKIP = "SKIP"


@dataclass(frozen=True)
class CheckResult:
    """Result of one build-check gate."""

    name: str
    tier: str
    status: Status
    task_id: str
    detail: str
    command: tuple[str, ...] = ()
    exit_code: int | None = None
    elapsed_ms: int = 0
    stdout: str = ""
    stderr: str = ""

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["command"] = list(self.command)
        return payload


@dataclass(frozen=True)
class Gate:
    """One executable or in-process checker gate."""

    name: str
    tier: str
    task_id: str
    command: tuple[str, ...] = ()
    timeout_seconds: float = 120
    check: Callable[[], CheckResult] | None = None
    nonzero_status: Status = Status.FAIL


def run_gate(gate: Gate) -> CheckResult:
    """Run one gate and classify failures without throwing on command failures."""
    if gate.check is not None:
        return gate.check()
    if not gate.command:
        return CheckResult(
            name=gate.name,
            tier=gate.tier,
            status=Status.FAIL,
            task_id=gate.task_id,
            detail="gate has neither command nor check callable",
        )

    start = monotonic()
    try:
        completed = subprocess.run(
            gate.command,
            capture_output=True,
            check=False,
            text=True,
            timeout=gate.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return CheckResult(
            name=gate.name,
            tier=gate.tier,
            status=Status.BLOCKED,
            task_id=gate.task_id,
            detail=f"command timed out after {gate.timeout_seconds:g}s",
            command=gate.command,
            elapsed_ms=_elapsed_ms(start),
            stdout=_decode_timeout_output(exc.stdout),
            stderr=_decode_timeout_output(exc.stderr),
        )
    except FileNotFoundError as exc:
        return CheckResult(
            name=gate.name,
            tier=gate.tier,
            status=Status.BLOCKED,
            task_id=gate.task_id,
            detail=f"required command not found: {exc.filename}",
            command=gate.command,
            elapsed_ms=_elapsed_ms(start),
        )

    status = Status.PASS if completed.returncode == 0 else gate.nonzero_status
    detail = (
        "command exited 0" if status is Status.PASS else f"command exited {completed.returncode}"
    )
    return CheckResult(
        name=gate.name,
        tier=gate.tier,
        status=status,
        task_id=gate.task_id,
        detail=detail,
        command=gate.command,
        exit_code=completed.returncode,
        elapsed_ms=_elapsed_ms(start),
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def run_gates(gates: Iterable[Gate], *, state_path: Path, resume: bool) -> list[CheckResult]:
    """Run gates, persisting after each gate so a later session can resume."""
    state = _load_state(state_path) if resume else _empty_state()
    results: list[CheckResult] = []
    for gate in gates:
        previous = state["gates"].get(gate.name)
        if resume and previous and previous.get("status") == Status.PASS.value:
            results.append(
                CheckResult(
                    name=gate.name,
                    tier=gate.tier,
                    status=Status.SKIP,
                    task_id=gate.task_id,
                    detail="previously passed; use --no-resume or delete state to rerun",
                )
            )
            continue

        result = run_gate(gate)
        state["gates"][gate.name] = result.to_json()
        state["updated_at"] = _utc_now()
        _save_state(state_path, state)
        results.append(result)
    return results


def select_gates(tiers: list[str]) -> list[Gate]:
    """Select gates by tier, expanding all into every known tier."""
    selected_tiers = set(tiers or ["fast"])
    if "all" in selected_tiers:
        selected_tiers = {"fast", "runtime", "forensic"}
    return [gate for gate in _all_gates() if gate.tier in selected_tiers]


def check_policy_config(path: Path) -> CheckResult:
    """Validate that local hooks cover the real source tree and hard-rule checks."""
    start = monotonic()
    if not path.is_file():
        return CheckResult(
            name="policy-config",
            tier="fast",
            status=Status.FAIL,
            task_id="W1.A.9",
            detail=f"pre-commit config missing: {path}",
            elapsed_ms=_elapsed_ms(start),
        )

    config = path.read_text(encoding="utf-8")
    missing: list[str] = []
    if "id: verdict-commit-msg" not in config:
        missing.append("verdict commit-message hook")
    if "id: check-no-mocks" not in config or "src/verdict" not in config:
        missing.append("no-mocks hook must scan src/verdict")
    if "ruff check src tests scripts" not in config:
        missing.append("ruff hook must lint src tests scripts")

    if missing:
        return CheckResult(
            name="policy-config",
            tier="fast",
            status=Status.FAIL,
            task_id="W1.A.9",
            detail="; ".join(missing),
            elapsed_ms=_elapsed_ms(start),
        )
    return CheckResult(
        name="policy-config",
        tier="fast",
        status=Status.PASS,
        task_id="W1.A.9",
        detail="policy hooks cover source, tests, and commit messages",
        elapsed_ms=_elapsed_ms(start),
    )


def check_required_files() -> CheckResult:
    """Check repository files that should exist before deeper build work."""
    start = monotonic()
    required = [
        Path("CLAUDE.md"),
        Path("pyproject.toml"),
        Path("src/verdict/__init__.py"),
        Path("docs/BUILD_PLAN.md"),
        Path("docs/ARCHITECTURE.md"),
        Path("docs/DEVPOST_COMPLIANCE.md"),
    ]
    missing = [path.as_posix() for path in required if not path.is_file()]
    if missing:
        return CheckResult(
            name="repo-required-files",
            tier="fast",
            status=Status.FAIL,
            task_id="W1.A.9",
            detail="missing required file(s): " + ", ".join(missing),
            elapsed_ms=_elapsed_ms(start),
        )
    return CheckResult(
        name="repo-required-files",
        tier="fast",
        status=Status.PASS,
        task_id="W1.A.9",
        detail="required repository files are present",
        elapsed_ms=_elapsed_ms(start),
    )


def format_summary(results: list[CheckResult]) -> str:
    """Format a human-readable checker summary."""
    lines = ["VERDICT build blocker check"]
    for result in results:
        lines.append(
            f"[{result.status.value}] {result.name} ({result.task_id}) - {result.detail}"
        )
    non_passing = {Status.FAIL, Status.BLOCKED, Status.WARN}
    next_result = next((result for result in results if result.status in non_passing), None)
    if next_result is not None:
        lines.append(f"Next: fix {next_result.name} under {next_result.task_id}")
        lines.append("Resume: python scripts/build_check.py --resume")
    else:
        lines.append("Next: fast build gates are clear")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run resumable VERDICT build blocker checks.")
    parser.add_argument(
        "--tier",
        action="append",
        choices=["fast", "runtime", "forensic", "all"],
        default=None,
        help="Gate tier to run. Repeat for multiple tiers. Default: fast.",
    )
    parser.add_argument("--resume", action="store_true", help="Skip gates that previously passed.")
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--json", action="store_true", help="Print machine-readable result JSON.")
    args = parser.parse_args(argv)

    results = run_gates(
        select_gates(args.tier or ["fast"]),
        state_path=args.state_path,
        resume=args.resume,
    )
    if args.json:
        print(json.dumps({"results": [result.to_json() for result in results]}, sort_keys=True))
    else:
        print(format_summary(results))
    return _exit_code(results)


def _all_gates() -> list[Gate]:
    return [
        Gate(name="repo-required-files", tier="fast", task_id="W1.A.9", check=check_required_files),
        Gate(
            name="policy-config",
            tier="fast",
            task_id="W1.A.9",
            check=lambda: check_policy_config(Path(".pre-commit-config.yaml")),
        ),
        Gate(
            name="policy-no-mocks",
            tier="fast",
            task_id="W1.A.9",
            command=(
                sys.executable,
                "scripts/check_no_mocks.py",
                "--exclude-regex",
                "^tests/policy/fixtures/",
                "src/verdict",
                "tests",
                "scripts",
                "swarm",
            ),
            timeout_seconds=60,
        ),
        Gate(
            name="python-import",
            tier="fast",
            task_id="W1.A.9",
            command=(sys.executable, "-c", "import verdict; print(verdict.__name__)"),
            timeout_seconds=30,
        ),
        Gate(
            name="lint",
            tier="fast",
            task_id="W1.A.9",
            command=("uv", "run", "ruff", "check", "src", "tests", "scripts"),
            timeout_seconds=120,
        ),
        Gate(
            name="tests",
            tier="fast",
            task_id="W1.A.9",
            command=("uv", "run", "pytest", "-q"),
            timeout_seconds=300,
        ),
        Gate(
            name="doctor",
            tier="runtime",
            task_id="W1.A.5",
            command=("uv", "run", "verdict", "doctor"),
            timeout_seconds=180,
            nonzero_status=Status.BLOCKED,
        ),
        Gate(
            name="health",
            tier="runtime",
            task_id="W1.A.5",
            command=("uv", "run", "verdict", "health"),
            timeout_seconds=180,
            nonzero_status=Status.BLOCKED,
        ),
        Gate(
            name="package-check",
            tier="forensic",
            task_id="W6.C.9",
            command=("uv", "run", "verdict", "package-check"),
            timeout_seconds=60,
            nonzero_status=Status.BLOCKED,
        ),
    ]


def _load_state(path: Path) -> dict[str, object]:
    if not path.is_file():
        return _empty_state()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("gates"), dict):
        return _empty_state()
    return data


def _save_state(path: Path, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _empty_state() -> dict[str, object]:
    return {"schema_version": SCHEMA_VERSION, "updated_at": _utc_now(), "gates": {}}


def _exit_code(results: list[CheckResult]) -> int:
    if any(result.status is Status.FAIL for result in results):
        return 1
    if any(result.status is Status.BLOCKED for result in results):
        return 2
    return 0


def _decode_timeout_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def _elapsed_ms(start: float) -> int:
    return int((monotonic() - start) * 1000)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
