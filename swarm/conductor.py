"""Conductor — parses BUILD_PLAN.md, builds the dependency DAG, dispatches tasks.

Phase-0: dry-run only. Reads BUILD_PLAN.md, populates SQLite, prints which tasks
are ready to dispatch. Real Agent SDK invocations land in a later PR after
token-budget and model-tier sign-off (docs/AGENT_SWARM.md §12).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

from swarm import state

# Maps phase prefix → worker specialization (docs/AGENT_SWARM.md §4.2).
PHASE_TO_SPECIALIZATION: dict[str, str] = {
    "W1.A": "tool-wrapper",      # infra glue routes through tool-wrapper-engineer
    "W1.B": "schema",
    "W1.C": "schema",
    "W1.D": "tool-wrapper",
    "W1.E": "tool-wrapper",
    "W1.F": "schema",            # playbook YAML schemas
    "W1.G": "planning",
    "W2.A": "planning",
    "W2.B": "tool-wrapper",
    "W2.C": "planning",
    "W2.D": "sandbox",
    "W3.A": "tool-wrapper",
    "W3.B": "tool-wrapper",
    "W3.C": "tool-wrapper",
    "W3.D": "tool-wrapper",      # ledger; HMAC-key tasks marked requires_human in deps.yaml
    "W3.E": "tool-wrapper",
    "W3.F": "tool-wrapper",
    "W4.A": "tool-wrapper",
    "W4.B": "tool-wrapper",
    "W4.C": "eval",
    "W4.D": "eval",
    "W4.E": "eval",
    "W4.F": "eval",
    "W4.G": "eval",
    "W5":   "tool-wrapper",
    "W6":   "tool-wrapper",
}

TASK_HEADING_RE = re.compile(r"^### (W\d+\.[A-Z](?:\.\d+)+(?:\.[a-z])?)\s+—\s+(.+)$")
PHASE_HEADING_RE = re.compile(r"^## Phase (W\d+\.[A-Z])\b")


def parse_plan(plan_path: Path) -> list[tuple[str, str, str]]:
    """Yield (task_id, phase, title) for every task heading in BUILD_PLAN.md."""
    tasks: list[tuple[str, str, str]] = []
    current_phase = ""
    for line in plan_path.read_text(encoding="utf-8").splitlines():
        m = PHASE_HEADING_RE.match(line)
        if m:
            current_phase = m.group(1)
            continue
        m = TASK_HEADING_RE.match(line)
        if m:
            task_id, title = m.group(1), m.group(2).strip()
            tasks.append((task_id, current_phase or task_id.rsplit(".", 1)[0], title))
    return tasks


def specialization_for(phase: str) -> str:
    """Map a phase like 'W1.B' to a worker specialization."""
    if phase in PHASE_TO_SPECIALIZATION:
        return PHASE_TO_SPECIALIZATION[phase]
    week_prefix = phase.split(".")[0]
    return PHASE_TO_SPECIALIZATION.get(week_prefix, "tool-wrapper")


def load_deps(deps_path: Path) -> tuple[dict[str, list[str]], set[str]]:
    """Return (cross_phase_deps, requires_human_set)."""
    if not deps_path.exists():
        return {}, set()
    data = yaml.safe_load(deps_path.read_text(encoding="utf-8")) or {}
    requires_human = set(data.pop("requires_human", []) or [])
    deps = {k: list(v) for k, v in data.items()}
    return deps, requires_human


def detect_cycle(deps: dict[str, list[str]]) -> list[str] | None:
    """DFS-based cycle detection. Returns the cycle path, or None."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = defaultdict(lambda: WHITE)
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = GRAY
        stack.append(node)
        for nxt in deps.get(node, []):
            if color[nxt] == GRAY:
                idx = stack.index(nxt)
                return stack[idx:] + [nxt]
            if color[nxt] == WHITE:
                cyc = visit(nxt)
                if cyc:
                    return cyc
        stack.pop()
        color[node] = BLACK
        return None

    for n in list(deps):
        if color[n] == WHITE:
            cyc = visit(n)
            if cyc:
                return cyc
    return None


def implicit_deps(tasks: list[tuple[str, str, str]]) -> dict[str, list[str]]:
    """Within a phase, each task depends on all earlier-suffix tasks in same phase."""
    by_phase: dict[str, list[str]] = defaultdict(list)
    for task_id, phase, _ in tasks:
        by_phase[phase].append(task_id)
    out: dict[str, list[str]] = {}
    for phase, ids in by_phase.items():
        ordered = sorted(ids, key=_sort_key)
        for i, tid in enumerate(ordered):
            if i > 0:
                out[tid] = [ordered[i - 1]]
    return out


def _sort_key(task_id: str) -> tuple:
    """Stable sort key for task IDs like W1.B.10 < W1.B.11 (lexicographic would fail)."""
    parts = task_id.split(".")
    out: list[object] = []
    for p in parts:
        if p.isdigit():
            out.append((0, int(p)))
        else:
            out.append((1, p))
    return tuple(out)


def merge_deps(implicit: dict[str, list[str]], cross: dict[str, list[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {k: list(v) for k, v in implicit.items()}
    for k, v in cross.items():
        out.setdefault(k, []).extend(v)
    return out


def ready_tasks(
    all_tasks: list[tuple[str, str, str]],
    deps: dict[str, list[str]],
    requires_human: set[str],
    merged: set[str],
) -> list[str]:
    ready = []
    for tid, _, _ in all_tasks:
        if tid in requires_human or tid in merged:
            continue
        blockers = deps.get(tid, [])
        if all(b in merged for b in blockers):
            ready.append(tid)
    return ready


def cmd_dry_run(args: argparse.Namespace) -> int:
    plan_path: Path = args.plan
    deps_path: Path = args.deps
    if not plan_path.exists():
        print(f"error: plan not found: {plan_path}", file=sys.stderr)
        return 2
    tasks = parse_plan(plan_path)
    if not tasks:
        print(f"error: no tasks parsed from {plan_path}", file=sys.stderr)
        return 2

    cross_deps, requires_human = load_deps(deps_path)
    deps = merge_deps(implicit_deps(tasks), cross_deps)
    cyc = detect_cycle(deps)
    if cyc:
        print(f"error: dependency cycle: {' → '.join(cyc)}", file=sys.stderr)
        return 2

    print(f"plan:           {plan_path}")
    print(f"tasks:          {len(tasks)}")
    print(f"phases:         {len({t[1] for t in tasks})}")
    print(f"requires_human: {len(requires_human)}")
    print()

    by_spec: dict[str, int] = defaultdict(int)
    for _, phase, _ in tasks:
        by_spec[specialization_for(phase)] += 1
    print("specialization distribution:")
    for spec, n in sorted(by_spec.items()):
        print(f"  {spec:<15} {n:>3} tasks")
    print()

    ready = ready_tasks(tasks, deps, requires_human, merged=set())
    print(f"ready now (no merged tasks yet): {len(ready)}")
    for tid in ready[: args.show]:
        spec = specialization_for(next(p for t, p, _ in tasks if t == tid))
        title = next(t for tt, _, t in tasks if tt == tid)
        marker = " [requires_human]" if tid in requires_human else ""
        print(f"  {tid:<10} ({spec:<13}) {title}{marker}")
    if len(ready) > args.show:
        print(f"  ... {len(ready) - args.show} more")
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    """Populate SQLite with parsed tasks. Idempotent on re-run."""
    plan_path: Path = args.plan
    deps_path: Path = args.deps
    db_path: Path = args.db
    state.init(db_path)
    tasks = parse_plan(plan_path)
    cross_deps, requires_human = load_deps(deps_path)
    conn = state.connect(db_path)
    try:
        conn.execute("BEGIN")
        for tid, phase, _ in tasks:
            spec = specialization_for(phase)
            initial = "requires_human" if tid in requires_human else "pending"
            state.upsert_task(conn, tid, phase, spec, status=initial)
        conn.execute("COMMIT")
    finally:
        conn.close()
    print(f"loaded {len(tasks)} tasks into {db_path}")
    print(f"  cross-phase deps:  {len(cross_deps)}")
    print(f"  requires_human:    {len(requires_human)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="swarm.conductor")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_dry = sub.add_parser("dry-run", help="parse plan, print DAG summary, don't touch DB")
    p_dry.add_argument("--plan", type=Path, default=Path("docs/BUILD_PLAN.md"))
    p_dry.add_argument("--deps", type=Path, default=Path("swarm/deps.yaml"))
    p_dry.add_argument("--show", type=int, default=10)
    p_dry.set_defaults(func=cmd_dry_run)

    p_load = sub.add_parser("load", help="parse plan and populate SQLite")
    p_load.add_argument("--plan", type=Path, default=Path("docs/BUILD_PLAN.md"))
    p_load.add_argument("--deps", type=Path, default=Path("swarm/deps.yaml"))
    p_load.add_argument("--db", type=Path, default=Path("swarm/swarm.db"))
    p_load.set_defaults(func=cmd_load)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
