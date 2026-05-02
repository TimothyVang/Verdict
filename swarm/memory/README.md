# swarm/memory/ — self-evolving lessons + distilled patterns

Two-tier memory the VERDICT Agent Team accumulates across runs:

- **`lessons.jsonl`** — append-only raw log. Each teammate writes one line on task complete: `{ts, task_id, role, lesson, evidence}`. Use `jq -nc` to compose; `>>` to append. Never edited or rewritten — history is the audit trail.
- **`patterns.md`** — distilled wisdom. The team lead refreshes this at every cleanup (see `scripts/run-team.sh` Phase 3.5) by reading the last ~200 lessons and synthesizing into "What works", "What to avoid", "Open questions" sections. Refreshes land as `chore(swarm): memory distill <date> [W0.X]` in a draft PR.

Every spawned teammate's prompt requires reading both files before writing any test or code. That's how the swarm gets smarter run-over-run without a memory MCP dependency.

Authority: `docs/AGENT_SWARM.md` §13 (file layout) — note this directory was added in v2 of the plan at `~/.claude/plans/plan-build-with-opus-claude-haiku-dazzling-lerdorf.md`.
