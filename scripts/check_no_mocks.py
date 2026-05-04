"""Reject mocks, replay libraries, and test-only branches in VERDICT code."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True)
class Violation:
    """One policy violation found in a Python source file."""

    path: Path
    line_no: int
    message: str


@dataclass(frozen=True)
class ScanResult:
    """Complete result of scanning one or more paths."""

    violations: list[Violation]


FORBIDDEN_MODULES = {
    "unittest.mock": "unittest.mock is forbidden by CLAUDE.md §3.10",
    "responses": "HTTP replay libraries are forbidden by CLAUDE.md §3.10",
    "vcr": "HTTP replay libraries are forbidden by CLAUDE.md §3.10",
    "betamax": "HTTP replay libraries are forbidden by CLAUDE.md §3.10",
    "httpx_mock": "HTTP replay libraries are forbidden by CLAUDE.md §3.10",
}

MOCK_BRANCH_RE = re.compile(r"^\s*if\b.*\b(MOCK|TEST_MODE)\b.*:\s*(?:#.*)?$")
VERDICT_TEST_RE = re.compile(r"os\.environ\.get\(['\"]VERDICT_TEST['\"]")


def scan(paths: list[Path]) -> ScanResult:
    """Scan Python files below the supplied paths for forbidden patterns."""
    violations: list[Violation] = []
    for path in _iter_python_files(paths):
        text = path.read_text(encoding="utf-8")
        violations.extend(_scan_ast(path, text))
        violations.extend(_scan_lines(path, text))
    return ScanResult(violations=violations)


def _iter_python_files(paths: list[Path]) -> Iterator[Path]:
    for path in paths:
        if path.is_dir():
            yield from sorted(path.rglob("*.py"))
        elif path.suffix == ".py":
            yield path


def _scan_ast(path: Path, text: str) -> list[Violation]:
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        return [Violation(path=path, line_no=exc.lineno or 1, message=f"invalid Python: {exc.msg}")]

    violations: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                message = _forbidden_import_message(alias.name)
                if message:
                    violations.append(Violation(path=path, line_no=node.lineno, message=message))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            message = _forbidden_import_message(module)
            if message:
                violations.append(Violation(path=path, line_no=node.lineno, message=message))
    return violations


def _forbidden_import_message(module: str) -> str | None:
    for forbidden, message in FORBIDDEN_MODULES.items():
        if module == forbidden or module.startswith(f"{forbidden}."):
            return message
    return None


def _scan_lines(path: Path, text: str) -> list[Violation]:
    violations: list[Violation] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if MOCK_BRANCH_RE.search(line):
            violations.append(
                Violation(
                    path=path,
                    line_no=line_no,
                    message="MOCK/TEST_MODE conditional branches are forbidden by CLAUDE.md §3.10",
                ),
            )
        if VERDICT_TEST_RE.search(line):
            violations.append(
                Violation(
                    path=path,
                    line_no=line_no,
                    message="VERDICT_TEST validator bypasses are forbidden by CLAUDE.md §3.10",
                ),
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    """Run the no-mocks scanner as a command-line policy hook."""
    parser = argparse.ArgumentParser(description="Reject mocks and test-only code paths.")
    parser.add_argument("--exclude-regex", default="")
    parser.add_argument("paths", nargs="*", type=Path, default=[Path("verdict"), Path("tests")])
    args = parser.parse_args(argv)

    result = scan(args.paths)
    if args.exclude_regex:
        exclude_re = re.compile(args.exclude_regex)
        result = ScanResult(
            violations=[
                violation
                for violation in result.violations
                if not exclude_re.search(violation.path.as_posix())
            ],
        )
    for violation in result.violations:
        sys.stderr.write(f"{violation.path}:{violation.line_no}: {violation.message}\n")
    return 1 if result.violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
