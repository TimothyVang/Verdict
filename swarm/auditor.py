"""Auditor — scans diffs for CLAUDE.md §3 violations.

Phase-0: pattern-based scan over a unified diff or a worktree. Posts findings
as structured records (PR-comment integration is Phase-1+). Each rule has a
severity: BLOCKING (sets the merge-block label) or ADVISORY (informational).

Default blocking set: §3.1, §3.2, §3.7, §3.8, §3.10
Default advisory set: §3.5, §3.6  (CLAUDE.md changes may promote these)

See docs/AGENT_SWARM.md §4.4 + §8.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

BLOCKING = "BLOCKING"
ADVISORY = "ADVISORY"


@dataclass(frozen=True)
class Rule:
    rule_id: str          # CLAUDE.md §3.X anchor
    severity: str         # BLOCKING | ADVISORY
    description: str
    pattern: re.Pattern[str]
    # If set: pattern must match a line that ALSO contains this antimatter to flag.
    # (Used for §3.5: bare T1055 is fine if it's a parent-only technique like T1014.)
    parent_only_techniques: tuple[str, ...] = ()


def _re(p: str) -> re.Pattern[str]:
    return re.compile(p, re.MULTILINE)


# Techniques without sub-techniques upstream — bare form is acceptable per CLAUDE.md §3.5.
PARENT_ONLY = ("T1014", "T1106", "T1204", "T1497", "T1583", "T1584", "T1587", "T1588", "T1591", "T1592", "T1593", "T1594", "T1595", "T1596", "T1597", "T1598")

RULES: list[Rule] = [
    # §3.1 — evidence is read-only
    Rule("§3.1", BLOCKING,
         "writing to /evidence/ is forbidden",
         _re(r"""open\s*\(\s*['"][^'"]*?/evidence/""")),
    Rule("§3.1", BLOCKING,
         "writing to /evidence/ via Path.write_*",
         _re(r"""Path\s*\(\s*['"][^'"]*?/evidence/[^'"]*?['"]\s*\)\s*\.\s*write_""")),

    # §3.7 — TDD + Conv. Commits + git discipline
    Rule("§3.7", BLOCKING,
         "--no-verify on commit/push",
         _re(r"--no-verify\b")),
    Rule("§3.7", BLOCKING,
         "--no-gpg-sign on commit",
         _re(r"--no-gpg-sign\b")),
    Rule("§3.7", BLOCKING,
         "git commit --amend",
         _re(r"git\s+commit\s+(?:[^#\n]*\s+)?--amend\b")),

    # §3.8 — dependency hard-NO list
    Rule("§3.8", BLOCKING,
         "forbidden dependency (license/strategic risk)",
         _re(r"\b(?:daytona|langsmith|braintrust|arize-phoenix|modal|autogen[-_]agentchat|llama[_-]?4|gemma[_-]?3)\b", )),

    # §3.10 — no mocks, no stubs, no placeholders
    Rule("§3.10", BLOCKING,
         "mock executor / sandbox / LLM class",
         _re(r"\b(?:Mock|Fake|Stub|Dummy)(?:Executor|Sandbox|LLM|Anthropic|Microsandbox|Ledger|Planner)\b")),
    Rule("§3.10", BLOCKING,
         "unittest.mock against verdict internals",
         _re(r"@(?:patch|patch\.object)\s*\(\s*['\"]verdict\.")),
    Rule("§3.10", BLOCKING,
         "HTTP-replay library standing in for real service",
         _re(r"^\s*import\s+(?:responses|httpx_mock|vcr|betamax)\b|^\s*from\s+(?:responses|httpx_mock|vcr|betamax)\b")),
    Rule("§3.10", BLOCKING,
         "MOCK / TEST_MODE conditional code path",
         _re(r"if\s+(?:MOCK|TEST_MODE|os\.environ\.get\(\s*['\"]VERDICT_TEST['\"])")),
    Rule("§3.10", BLOCKING,
         "TODO replace-with-real-implementation stub",
         _re(r"#\s*TODO[:\s].*replace.*real\s+implementation", )),

    # §3.5 — MITRE sub-technique precision (advisory; promote after first 20 audits if drift)
    Rule("§3.5", ADVISORY,
         "bare MITRE technique without sub-technique (verify upstream has none)",
         _re(r"\bT\d{4}\b(?!\.\d{3})"),
         parent_only_techniques=PARENT_ONLY),
]


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    description: str
    file: str
    line: int
    snippet: str


def _scan_text(text: str, file_label: str, rules: list[Rule]) -> list[Finding]:
    out: list[Finding] = []
    lines = text.splitlines()
    for rule in rules:
        for m in rule.pattern.finditer(text):
            # Find line number
            line_no = text.count("\n", 0, m.start()) + 1
            line_text = lines[line_no - 1] if 0 < line_no <= len(lines) else ""
            # §3.5 carve-out: bare technique is fine if it's a known parent-only technique
            if rule.parent_only_techniques:
                hit = m.group(0)
                if hit in rule.parent_only_techniques:
                    continue
            out.append(Finding(
                rule_id=rule.rule_id,
                severity=rule.severity,
                description=rule.description,
                file=file_label,
                line=line_no,
                snippet=line_text.strip()[:200],
            ))
    return out


def scan_paths(paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        findings.extend(_scan_text(text, str(path), RULES))
    return findings


def scan_commit_subjects(repo: Path, base: str = "origin/main") -> list[Finding]:
    """§3.7: every commit subject on the branch must contain [W#.#.#]."""
    res = subprocess.run(
        ["git", "log", "--format=%H%n%s", f"{base}..HEAD"],
        cwd=repo, capture_output=True, text=True,
    )
    if res.returncode != 0:
        return []
    out: list[Finding] = []
    pattern = re.compile(r"\[W\d+\.[A-Z](?:\.\d+)+(?:\.[a-z])?\]")
    chunks = res.stdout.strip().split("\n")
    for i in range(0, len(chunks) - 1, 2):
        sha = chunks[i]
        subject = chunks[i + 1] if i + 1 < len(chunks) else ""
        if not pattern.search(subject):
            out.append(Finding(
                rule_id="§3.7",
                severity=BLOCKING,
                description="commit subject missing [W#.#.#] task ID",
                file=f"git:{sha[:8]}",
                line=0,
                snippet=subject,
            ))
    return out


def scan_worktree_diff(repo: Path, base: str = "origin/main") -> list[Finding]:
    """Scan files changed on this branch vs base."""
    res = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=repo, capture_output=True, text=True,
    )
    if res.returncode != 0:
        return []
    paths = [repo / p for p in res.stdout.splitlines() if p.strip()]
    return scan_paths(paths)


def cmd_scan(args: argparse.Namespace) -> int:
    findings: list[Finding] = []
    if args.paths:
        findings.extend(scan_paths([Path(p) for p in args.paths]))
    if args.diff:
        findings.extend(scan_worktree_diff(Path.cwd(), args.base))
        findings.extend(scan_commit_subjects(Path.cwd(), args.base))

    if not findings:
        print("auditor: no findings")
        return 0
    blocking = [f for f in findings if f.severity == BLOCKING]
    advisory = [f for f in findings if f.severity == ADVISORY]
    for f in findings:
        print(f"[{f.severity}] {f.rule_id} {f.file}:{f.line}  {f.description}")
        if f.snippet:
            print(f"           {f.snippet}")
    print()
    print(f"summary: {len(blocking)} blocking, {len(advisory)} advisory")
    return 1 if blocking else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="swarm.auditor")
    sub = p.add_subparsers(dest="cmd", required=True)
    p_scan = sub.add_parser("scan", help="scan files or a branch diff")
    p_scan.add_argument("paths", nargs="*", help="explicit files to scan")
    p_scan.add_argument("--diff", action="store_true",
                        help="scan files changed on HEAD vs base + commit subjects")
    p_scan.add_argument("--base", default="origin/main")
    p_scan.set_defaults(func=cmd_scan)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
