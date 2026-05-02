"""Thin wrapper over the `gh` CLI for PR creation, labeling, and review.

We shell out instead of using a Python GitHub client because:
  - `gh` already handles auth via the user's PAT or OAuth (CONTRIBUTING.md Step 1).
  - The swarm uses the same auth path humans use; one trust model.
  - `gh pr create --body-file` accepts large bodies cleanly.

See docs/AGENT_SWARM.md §6.5.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


class GhError(RuntimeError):
    pass


def _run(cmd: list[str], *, cwd: Path | None = None, input_text: str | None = None) -> str:
    res = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, input=input_text,
    )
    if res.returncode != 0:
        raise GhError(f"{' '.join(cmd)}: {res.stderr.strip()}")
    return res.stdout


def auth_status() -> bool:
    try:
        _run(["gh", "auth", "status"])
        return True
    except (GhError, FileNotFoundError):
        return False


def repo_view_permission(slug: str = "TimothyVang/Verdict") -> str | None:
    """Returns the viewer's permission level (READ|WRITE|MAINTAIN|ADMIN) or None."""
    try:
        out = _run(["gh", "repo", "view", slug, "--json", "viewerPermission"])
    except (GhError, FileNotFoundError):
        return None
    return json.loads(out).get("viewerPermission")


def pr_create(
    *,
    title: str,
    body: str,
    branch: str,
    base: str = "main",
    draft: bool = True,
    labels: list[str] | None = None,
    cwd: Path | None = None,
) -> str:
    """Open a PR; returns the PR URL."""
    cmd = [
        "gh", "pr", "create",
        "--title", title,
        "--body-file", "-",
        "--head", branch,
        "--base", base,
    ]
    if draft:
        cmd.append("--draft")
    for lbl in labels or []:
        cmd.extend(["--label", lbl])
    out = _run(cmd, cwd=cwd, input_text=body)
    return out.strip().splitlines()[-1]


def pr_view(pr: str, *, cwd: Path | None = None) -> dict:
    out = _run(
        ["gh", "pr", "view", pr, "--json", "state,reviews,labels,mergeable,statusCheckRollup"],
        cwd=cwd,
    )
    return json.loads(out)


def pr_review(pr: str, *, action: str, body: str, cwd: Path | None = None) -> None:
    """action ∈ {approve, request-changes, comment}."""
    flag = {"approve": "--approve", "request-changes": "--request-changes", "comment": "--comment"}[action]
    _run(["gh", "pr", "review", pr, flag, "--body", body], cwd=cwd)


def pr_label(pr: str, *, add: list[str] | None = None, remove: list[str] | None = None, cwd: Path | None = None) -> None:
    cmd = ["gh", "pr", "edit", pr]
    for lbl in add or []:
        cmd.extend(["--add-label", lbl])
    for lbl in remove or []:
        cmd.extend(["--remove-label", lbl])
    _run(cmd, cwd=cwd)
