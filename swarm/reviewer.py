"""Reviewer — local CI gate runner.

Runs ruff / cargo clippy / pytest / pre-commit / signed-commit verify against
a worker's branch (in its worktree), captures pass/fail, and returns a
structured report. The actual `gh pr review` call is Phase-1+; this file
establishes the check surface.

See docs/AGENT_SWARM.md §4.3.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Ordered: cheaper checks first so failures cut feedback latency.
DEFAULT_CHECKS: list[tuple[str, list[str]]] = [
    ("ruff-check",   ["ruff", "check", "."]),
    ("ruff-format",  ["ruff", "format", "--check", "."]),
    ("pytest",       ["uv", "run", "pytest", "-q"]),
    ("clippy",       ["cargo", "clippy", "--all-targets", "--all-features", "--", "-D", "warnings"]),
    ("pre-commit",   ["uv", "run", "pre-commit", "run", "--all-files"]),
]


@dataclass
class CheckResult:
    name: str
    passed: bool
    exit_code: int
    stdout: str
    stderr: str


@dataclass
class ReviewReport:
    branch: str
    worktree: Path
    checks: list[CheckResult] = field(default_factory=list)
    signed_ok: bool = False
    tdd_ok: bool = False
    task_id_ok: bool = False

    @property
    def all_green(self) -> bool:
        return (
            all(c.passed for c in self.checks)
            and self.signed_ok
            and self.tdd_ok
            and self.task_id_ok
        )


def _run(cmd: list[str], cwd: Path) -> CheckResult:
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=600)
    except FileNotFoundError as e:
        return CheckResult(cmd[0], False, 127, "", str(e))
    except subprocess.TimeoutExpired:
        return CheckResult(cmd[0], False, 124, "", "timed out")
    return CheckResult(cmd[0], res.returncode == 0, res.returncode, res.stdout, res.stderr)


def check_signed_commits(worktree: Path, base: str = "origin/main") -> bool:
    """Every new commit on this branch must show a good signature."""
    res = subprocess.run(
        ["git", "log", "--show-signature", f"{base}..HEAD"],
        cwd=worktree, capture_output=True, text=True,
    )
    if res.returncode != 0:
        return False
    out = res.stdout
    # Each commit prints a "gpg: Good signature" or 'Good "git" signature' line.
    bad_markers = ("BAD signature", "no signature", "Can't check signature", "expired")
    if any(m in out for m in bad_markers):
        return False
    return ("Good signature" in out) or ("good \"git\" signature" in out.lower())


def check_tdd_history(worktree: Path, base: str = "origin/main") -> bool:
    """At least one commit on the branch must precede a later commit (RED→GREEN evidence).

    Phase-0 heuristic: branch has ≥2 commits where the first introduces a test file
    or a `test_*` function and a later commit modifies non-test source. A real TDD
    audit is harder; this catches the common 'one big commit' anti-pattern.
    """
    res = subprocess.run(
        ["git", "log", "--reverse", "--name-status", "--format=%H", f"{base}..HEAD"],
        cwd=worktree, capture_output=True, text=True,
    )
    if res.returncode != 0:
        return False
    blocks = [b for b in res.stdout.split("\n\n") if b.strip()]
    if len(blocks) < 2:
        return False
    first_files = blocks[0].splitlines()[1:]  # skip the SHA line
    later_files = "\n".join(blocks[1:])
    first_touches_tests = any("/tests/" in f or "test_" in f for f in first_files)
    later_touches_src = any(line and "/tests/" not in line and "test_" not in line for line in later_files.splitlines())
    return first_touches_tests and later_touches_src


def check_task_id_in_subjects(worktree: Path, base: str = "origin/main") -> bool:
    """Every commit subject on the branch must contain a [W#.#.#] task ID."""
    import re

    res = subprocess.run(
        ["git", "log", "--format=%s", f"{base}..HEAD"],
        cwd=worktree, capture_output=True, text=True,
    )
    if res.returncode != 0:
        return False
    pattern = re.compile(r"\[W\d+\.[A-Z](?:\.\d+)+(?:\.[a-z])?\]")
    return all(pattern.search(line) for line in res.stdout.splitlines() if line.strip())


def review(worktree: Path, branch: str, base: str = "origin/main") -> ReviewReport:
    report = ReviewReport(branch=branch, worktree=worktree)
    for name, cmd in DEFAULT_CHECKS:
        # Skip language-specific checks if the relevant build file is absent.
        if name == "clippy" and not (worktree / "Cargo.toml").exists():
            continue
        if name in {"pytest", "pre-commit"} and not (worktree / "pyproject.toml").exists():
            continue
        report.checks.append(_run(cmd, worktree))
    report.signed_ok = check_signed_commits(worktree, base)
    report.tdd_ok = check_tdd_history(worktree, base)
    report.task_id_ok = check_task_id_in_subjects(worktree, base)
    return report


def cmd_review(args: argparse.Namespace) -> int:
    rep = review(args.worktree, args.branch, args.base)
    print(f"branch:        {rep.branch}")
    print(f"worktree:      {rep.worktree}")
    print(f"signed:        {'ok' if rep.signed_ok else 'FAIL'}")
    print(f"tdd_history:   {'ok' if rep.tdd_ok else 'FAIL'}")
    print(f"task_id_subj:  {'ok' if rep.task_id_ok else 'FAIL'}")
    for c in rep.checks:
        status = "ok" if c.passed else "FAIL"
        print(f"{c.name:<14} {status:<5} (exit={c.exit_code})")
    print(f"\nverdict: {'APPROVE' if rep.all_green else 'REQUEST_CHANGES'}")
    return 0 if rep.all_green else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="swarm.reviewer")
    sub = p.add_subparsers(dest="cmd", required=True)
    p_rev = sub.add_parser("review", help="run CI gate against a worktree")
    p_rev.add_argument("--worktree", required=True, type=Path)
    p_rev.add_argument("--branch", required=True)
    p_rev.add_argument("--base", default="origin/main")
    p_rev.set_defaults(func=cmd_review)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
