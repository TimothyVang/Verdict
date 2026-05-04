"""Validate VERDICT commit message subjects."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_PATTERN = (
    r"^(feat|fix|test|chore|docs|refactor)\([a-z0-9_-]+\): .+ "
    r"\[W\d+\.[A-Z]\.\d+(?:\.[a-z])?\]$"
)


def main(argv: list[str] | None = None) -> int:
    """Validate the first line of a commit message file."""
    parser = argparse.ArgumentParser(description="Validate VERDICT commit subject format.")
    parser.add_argument("--pattern", default=DEFAULT_PATTERN)
    parser.add_argument("commit_msg_file", type=Path)
    args = parser.parse_args(argv)

    subject = args.commit_msg_file.read_text(encoding="utf-8").splitlines()[0]
    if re.compile(args.pattern).match(subject):
        return 0
    sys.stderr.write(
        "commit subject must match: <type>(scope): summary [W#.#.#], "
        "with type feat|fix|test|chore|docs|refactor\n",
    )
    sys.stderr.write(f"got: {subject}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
