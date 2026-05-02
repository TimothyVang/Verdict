#!/usr/bin/env python3
# ruff: noqa: T201
r"""Mechanical enforcement of CLAUDE.md §3.10 (no mocks / stubs / placeholders).

Walks Python source under ``verdict/`` and ``tests/`` (or an explicit
list of files) and rejects:

* ``import unittest.mock`` and ``from unittest import mock`` -- these
  are blanket mock imports rather than targeted boundary patching.
* ``import responses``, ``import vcr``, ``import betamax``,
  ``import httpx_mock`` -- HTTP-replay libraries standing in for real
  Anthropic / SGLang / Langfuse endpoints.
* Lines matching ``^\s*if .*(MOCK|TEST_MODE).*:\s*$`` -- code paths
  gated on test-mode flags.
* Lines matching ``os\.environ\.get\(['"]VERDICT_TEST`` -- schema
  validators that short-circuit under VERDICT_TEST.

``from unittest.mock import patch`` (etc.) is NOT flagged: §3.10
explicitly permits patching a third-party library at the system
boundary in a single targeted test. Mocking ``verdict.*`` internals
is forbidden by other means (review).

CLI: ``python scripts/check_no_mocks.py [path ...]``. Exit 1 on
violations. Public Python API: ``scan(paths) -> Report``.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOTS = ("verdict", "tests")
EXCLUDED_DIRS = ("tests/policy/fixtures",)

FORBIDDEN_MODULES = frozenset(
    {"unittest.mock", "responses", "vcr", "betamax", "httpx_mock"},
)
FORBIDDEN_FROM_PAIRS = frozenset({("unittest", "mock")})

MOCK_GUARD_RE = re.compile(r"^\s*if .*(MOCK|TEST_MODE).*:\s*$")
VERDICT_TEST_ENV_RE = re.compile(r"""os\.environ\.get\(['"]VERDICT_TEST""")


@dataclass(frozen=True)
class Violation:
    """A single §3.10 rule hit: file, line, rule id, and offending snippet."""

    path: str
    line: int
    rule: str
    snippet: str


@dataclass
class Report:
    """Aggregate scan result. Truthy if any violations were collected."""

    violations: list[Violation] = field(default_factory=list)


def _scan_ast(path: Path, source: str, report: Report) -> None:
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        report.violations.append(
            Violation(str(path), exc.lineno or 1, "syntax-error", str(exc)),
        )
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in FORBIDDEN_MODULES:
                    report.violations.append(
                        Violation(
                            str(path),
                            node.lineno,
                            "forbidden-import",
                            alias.name,
                        ),
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            for alias in node.names:
                if (node.module, alias.name) in FORBIDDEN_FROM_PAIRS:
                    report.violations.append(
                        Violation(
                            str(path),
                            node.lineno,
                            "forbidden-from-import",
                            f"from {node.module} import {alias.name}",
                        ),
                    )


def _scan_lines(path: Path, source: str, report: Report) -> None:
    for lineno, line in enumerate(source.splitlines(), start=1):
        if MOCK_GUARD_RE.match(line):
            report.violations.append(
                Violation(str(path), lineno, "mock-guard", line.strip()),
            )
        if VERDICT_TEST_ENV_RE.search(line):
            report.violations.append(
                Violation(str(path), lineno, "verdict-test-env", line.strip()),
            )


def _iter_targets(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for child in p.rglob("*.py"):
                rel = child.resolve().as_posix()
                if any(excl in rel for excl in EXCLUDED_DIRS):
                    continue
                out.append(child)
        elif p.is_file() and p.suffix == ".py":
            out.append(p)
    return out


def scan(paths: list[str]) -> Report:
    """Scan ``paths`` (files or directories) and return a :class:`Report`."""
    report = Report()
    for target in _iter_targets(paths):
        try:
            source = target.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - I/O failures are environmental
            report.violations.append(
                Violation(str(target), 1, "io-error", str(exc)),
            )
            continue
        _scan_ast(target, source, report)
        _scan_lines(target, source, report)
    return report


def _default_paths() -> list[str]:
    return [str(REPO_ROOT / root) for root in DEFAULT_ROOTS]


def main(argv: list[str] | None = None) -> int:
    """Console entry point. Returns 1 on any violation, 0 otherwise."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "paths",
        nargs="*",
        help="Files or directories to scan (default: verdict/, tests/).",
    )
    args = parser.parse_args(argv)
    paths = args.paths or _default_paths()
    report = scan(paths)
    for violation in report.violations:
        print(
            f"{violation.path}:{violation.line}: {violation.rule}: {violation.snippet}",
            file=sys.stderr,
        )
    return 1 if report.violations else 0


if __name__ == "__main__":
    sys.exit(main())
