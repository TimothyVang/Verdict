#!/usr/bin/env python3
r"""Enforce CLAUDE.md §3.7 commit-message contract.

Pre-commit's ``commit-msg`` stage invokes this script with the path to
the commit-message file as the first positional argument. The first
non-empty line is matched against::

    ^(feat|fix|test|chore|docs|refactor)\(\w+\): .* \[W\d+\.[A-Z]\.\d+(\.[a-z])?\]$

Examples that pass:

    feat(schema): add ArtifactClass enum [W1.B.1]
    test(policy): assert no-mocks AST hook flags unittest.mock [W1.A.9.a]

Examples that fail:

    chore: bump deps                         (no scope, no task id)
    feat(schema): add CaveatID enum          (no task id suffix)
    Fix(schema): typo                        (capitalised type)
    perf(schema): cache lookups [W1.B.1]     (forbidden type)

CLAUDE.md §3.7 also forbids Claude Code watermark lines anywhere in
the commit body; this script rejects messages that contain any of
``Co-Authored-By: Claude``, ``Generated with [Claude Code]``, or the
robot emoji + Claude Code marker.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SUBJECT_RE = re.compile(
    r"^(feat|fix|test|chore|docs|refactor)\(\w+\): .* \[W\d+\.[A-Z]\.\d+(\.[a-z])?\]$",
)

WATERMARK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Co-Authored-By:\s*Claude", re.IGNORECASE),
    re.compile(r"Generated with \[Claude Code\]", re.IGNORECASE),
    re.compile(r"\U0001f916\s*Generated with"),  # robot emoji + Generated with
)


def _first_nonempty_line(text: str) -> str:
    for raw in text.splitlines():
        stripped = raw.rstrip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def check(message: str) -> list[str]:
    """Return a list of human-readable error strings (empty == OK)."""
    errors: list[str] = []
    subject = _first_nonempty_line(message)
    if not subject:
        errors.append("commit message is empty")
        return errors
    if not SUBJECT_RE.match(subject):
        errors.append(
            "subject does not match "
            r"^(feat|fix|test|chore|docs|refactor)\(\w+\): .* "
            r"\[W\d+\.[A-Z]\.\d+(\.[a-z])?\]$ "
            f"(got: {subject!r})",
        )
    for pattern in WATERMARK_PATTERNS:
        if pattern.search(message):
            errors.append(
                "commit body contains a Claude Code watermark "
                f"(matched /{pattern.pattern}/) -- forbidden by CLAUDE.md §3.7",
            )
            break
    return errors


def main(argv: list[str] | None = None) -> int:
    """Console entry point. Returns 1 on any violation."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        sys.stderr.write("usage: check_commit_msg.py <COMMIT_EDITMSG>\n")
        return 2
    msg_path = Path(args[0])
    if not msg_path.is_file():
        sys.stderr.write(f"commit-msg file not found: {msg_path}\n")
        return 2
    text = msg_path.read_text(encoding="utf-8")
    errors = check(text)
    for err in errors:
        sys.stderr.write(f"commit-msg: {err}\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
