"""Git-worktree manager — one worktree per active task.

Layout:
    <repo>/worktrees/<task-id>/   →   branch <type>/<task-id>-<slug>

See docs/AGENT_SWARM.md §6.4.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def repo_root(start: Path | None = None) -> Path:
    res = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start or Path.cwd(), capture_output=True, text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"not in a git repository: {res.stderr.strip()}")
    return Path(res.stdout.strip())


def worktree_path(repo: Path, task_id: str) -> Path:
    return repo / "worktrees" / task_id


def create(task_id: str, branch: str, base: str = "origin/main") -> Path:
    repo = repo_root()
    wt = worktree_path(repo, task_id)
    wt.parent.mkdir(parents=True, exist_ok=True)
    if wt.exists():
        raise FileExistsError(f"worktree already exists: {wt}")
    res = subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(wt), base],
        cwd=repo, capture_output=True, text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"git worktree add failed: {res.stderr.strip()}")
    return wt


def cleanup(task_id: str, *, force: bool = False) -> None:
    repo = repo_root()
    wt = worktree_path(repo, task_id)
    if not wt.exists():
        return
    cmd = ["git", "worktree", "remove", str(wt)]
    if force:
        cmd.append("--force")
    res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    if res.returncode != 0 and not force:
        # try the forceful path; uncommitted state in the worktree shouldn't trap us
        cleanup(task_id, force=True)
        return
    # belt and braces
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)


def list_worktrees() -> list[tuple[str, str]]:
    repo = repo_root()
    res = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo, capture_output=True, text=True,
    )
    if res.returncode != 0:
        return []
    out: list[tuple[str, str]] = []
    cur_path = ""
    for line in res.stdout.splitlines():
        if line.startswith("worktree "):
            cur_path = line[len("worktree "):]
        elif line.startswith("branch "):
            out.append((cur_path, line[len("branch "):]))
    return out


def cmd_create(args: argparse.Namespace) -> int:
    wt = create(args.task_id, args.branch, args.base)
    print(f"created {wt} on branch {args.branch}")
    return 0


def cmd_cleanup(args: argparse.Namespace) -> int:
    cleanup(args.task_id, force=args.force)
    print(f"cleaned up worktree for {args.task_id}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    for path, branch in list_worktrees():
        print(f"{branch}\t{path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="swarm.runtime.worktree")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_c = sub.add_parser("create")
    p_c.add_argument("--task-id", required=True)
    p_c.add_argument("--branch", required=True)
    p_c.add_argument("--base", default="origin/main")
    p_c.set_defaults(func=cmd_create)

    p_r = sub.add_parser("cleanup")
    p_r.add_argument("--task-id", required=True)
    p_r.add_argument("--force", action="store_true")
    p_r.set_defaults(func=cmd_cleanup)

    p_l = sub.add_parser("list")
    p_l.set_defaults(func=cmd_list)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
