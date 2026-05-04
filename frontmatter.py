"""Minimal frontmatter reader used by the local swarm tests.

This intentionally supports only the simple YAML subset used by
`swarm/agents/*.md`: scalar strings and block lists. It avoids adding a runtime
dependency for a tiny metadata contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Post:
    metadata: dict[str, Any]
    content: str


def _parse_metadata(lines: list[str]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in lines:
        line = raw_line.rstrip()
        if not line:
            continue
        if line.startswith("  - "):
            if current_key is None:
                raise ValueError("frontmatter list item without a key")
            value = line[4:].strip()
            metadata.setdefault(current_key, []).append(value)
            continue
        if ":" not in line:
            raise ValueError(f"unsupported frontmatter line: {line!r}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_key = key
        metadata[key] = [] if value == "" else value
    return metadata


def load(path: str | Path) -> Post:
    text = Path(path).read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return Post(metadata={}, content=text)
    _, rest = text.split("---\n", 1)
    header, content = rest.split("\n---\n", 1)
    return Post(metadata=_parse_metadata(header.splitlines()), content=content.lstrip("\n"))

