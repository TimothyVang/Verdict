"""Worker — single-task TDD driver. Phase-0 skeleton.

Loads the shared system-prompt prefix + the role override + the task's
BUILD_PLAN entry, then would invoke the Claude Agent SDK to drive the
RED → GREEN → push → PR loop. The SDK call itself is stubbed in Phase 0;
this file establishes the orchestration surface.

See docs/AGENT_SWARM.md §4.2 + §7.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROLE_FILES: dict[str, str] = {
    "schema": "schema-engineer.md",
    "planning": "planning-engineer.md",
    "sandbox": "sandbox-engineer.md",
    "tool-wrapper": "tool-wrapper-engineer.md",
    "eval": "eval-engineer.md",
}

PROMPT_DIR = Path(__file__).parent / "agents"


@dataclass(frozen=True)
class TaskBrief:
    task_id: str
    phase: str
    specialization: str
    title: str
    plan_excerpt: str

    @property
    def branch(self) -> str:
        slug = self.title.lower()
        for ch in (" ", "/", "_", "—", "–", "`"):
            slug = slug.replace(ch, "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-").strip("-")
        # Heuristic: schema/eval tasks use feat/, infra docs use chore/.
        prefix = "feat" if self.specialization in {"schema", "planning", "tool-wrapper", "sandbox", "eval"} else "chore"
        return f"{prefix}/{self.task_id}-{slug[:60]}"


@dataclass(frozen=True)
class AgentDef:
    name: str
    description: str
    model: str
    allowed_tools: tuple[str, ...]
    skills: tuple[str, ...]
    mcp_servers: tuple[str, ...]
    system_prompt: str


def load_prompt(specialization: str) -> str:
    """Compose system prompt = shared prefix + role override."""
    prefix = (PROMPT_DIR / "_prefix.md").read_text(encoding="utf-8")
    role_filename = ROLE_FILES.get(specialization)
    if role_filename is None:
        raise ValueError(f"unknown specialization: {specialization}")
    role = (PROMPT_DIR / role_filename).read_text(encoding="utf-8")
    return f"{prefix}\n\n---\n\n{role}"


ROLE_ALIASES: dict[str, str] = {
    "schema": "schema-engineer",
    "planning": "planning-engineer",
    "sandbox": "sandbox-engineer",
    "tool-wrapper": "tool-wrapper-engineer",
    "eval": "eval-engineer",
}


def _agent_path(role: str) -> Path:
    canonical = ROLE_ALIASES.get(role, role)
    path = PROMPT_DIR / f"{canonical}.md"
    if not path.exists():
        raise KeyError(f"unknown role: {role}")
    return path


def _split_frontmatter(path: Path) -> tuple[dict[str, object], str]:
    import frontmatter

    post = frontmatter.load(path)
    return dict(post.metadata), post.content


def load_agent_definition(role: str) -> AgentDef:
    """Load a typed swarm agent definition from frontmatter + prompt body."""
    path = _agent_path(role)
    metadata, role_prompt = _split_frontmatter(path)
    prefix = (PROMPT_DIR / "_prefix.md").read_text(encoding="utf-8")
    name = str(metadata["name"])
    return AgentDef(
        name=name,
        description=str(metadata["description"]),
        model=str(metadata["model"]),
        allowed_tools=tuple(metadata["allowed_tools"]),  # type: ignore[arg-type]
        skills=tuple(metadata["skills"]),  # type: ignore[arg-type]
        mcp_servers=tuple(metadata["mcp_servers"]),  # type: ignore[arg-type]
        system_prompt=f"{prefix}\n\n---\n\n{role_prompt}",
    )


def extract_plan_excerpt(plan_path: Path, task_id: str) -> str:
    """Return the BUILD_PLAN section for `task_id` (heading + body until next ###)."""
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    capture = False
    for line in lines:
        if line.startswith(f"### {task_id} "):
            capture = True
        elif capture and line.startswith("### "):
            break
        if capture:
            out.append(line)
    if not out:
        raise KeyError(f"task {task_id} not found in {plan_path}")
    return "\n".join(out)


def cmd_show(args: argparse.Namespace) -> int:
    """Print the assembled prompt + task brief without invoking the SDK. Phase-0 path."""
    brief = TaskBrief(
        task_id=args.task_id,
        phase=args.task_id.rsplit(".", 1)[0],
        specialization=args.specialization,
        title=args.title or "(title unspecified)",
        plan_excerpt=extract_plan_excerpt(args.plan, args.task_id) if args.plan.exists() else "",
    )
    prompt = load_prompt(args.specialization)
    print(f"--- branch ---")
    print(brief.branch)
    print()
    print(f"--- system prompt ({len(prompt)} chars) ---")
    print(prompt[:400] + ("..." if len(prompt) > 400 else ""))
    print()
    print(f"--- plan excerpt ({len(brief.plan_excerpt)} chars) ---")
    print(brief.plan_excerpt)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Phase-0 stub: refuses to execute. Placeholder for the SDK invocation."""
    print(
        "swarm.worker run: not implemented in Phase 0. The Agent SDK invocation "
        "lands in a follow-up PR after token-budget and model-tier sign-off "
        "(docs/AGENT_SWARM.md §12, §14).",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="swarm.worker")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="print assembled prompt + task brief (no SDK call)")
    p_show.add_argument("--task-id", required=True)
    p_show.add_argument("--specialization", required=True, choices=sorted(ROLE_FILES))
    p_show.add_argument("--title", default=None)
    p_show.add_argument("--plan", type=Path, default=Path("docs/BUILD_PLAN.md"))
    p_show.set_defaults(func=cmd_show)

    p_run = sub.add_parser("run", help="(Phase-0 stub) drive a task end-to-end")
    p_run.add_argument("--task-id", required=True)
    p_run.set_defaults(func=cmd_run)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
