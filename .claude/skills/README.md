# `.claude/skills/` — Verdict skill stack

Project-scoped skills loaded automatically by every Claude Code session in this repo. Composed by `docs/SKILLS_FRAMEWORK.md` into a Plan → TDD → Subagent-driven-dev → Review → Commit pipeline.

## Layout

| Skill | Origin | Role |
|---|---|---|
| `verdict-house-rules/` | **Verdict** | Top-level overlay. Re-states CLAUDE.md §3 hard rules in skill form so Claude obeys them on every action. **Auto-triggers on every session.** |
| `using-superpowers/` | obra/superpowers | Index of the Superpowers framework — tells Claude which skill to reach for, when. |
| `brainstorming/` | obra/superpowers | Socratic refinement before any code is written. |
| `grill-me/` | mattpocock/skills | Relentless interview that walks the decision tree of a plan. |
| `grill-with-docs/` | mattpocock/skills | Same interview loop, but cross-checks against existing docs (ARCHITECTURE.md, BUILD_PLAN.md) and writes decisions back as ADR-style notes. |
| `writing-plans/` | obra/superpowers | Decompose feature into 2–5-min tasks with file paths + tests-before-code. |
| `executing-plans/` | obra/superpowers | Batch-execute a plan with human checkpoints between steps. |
| `test-driven-development/` | obra/superpowers | Strict RED → GREEN → REFACTOR. Verdict-house-rules adds `[W#.#.#]` requirement on top. |
| `subagent-driven-development/` | obra/superpowers | Dispatch implementation to a fresh subagent (plan + tests only); a second subagent reviews. Maps onto `swarm/` topology. |
| `dispatching-parallel-agents/` | obra/superpowers | Concurrent subagent workflows. |
| `using-git-worktrees/` | obra/superpowers | Isolated parallel branches. |
| `systematic-debugging/` | obra/superpowers | 4-phase root-cause loop. Forbids fixing what isn't understood. |
| `verification-before-completion/` | obra/superpowers | Confirms the fix landed before declaring done. |
| `requesting-code-review/` | obra/superpowers | Pre-review checklist enforcement. |
| `receiving-code-review/` | obra/superpowers | Structured response to feedback. |
| `finishing-a-development-branch/` | obra/superpowers | Merge / PR decision workflow. Hands off to `/qc` for the actual commit + push. |
| `writing-skills/` | obra/superpowers | How to author additional skills following the framework's conventions. |

## Provenance and updates

- License attribution: `THIRD_PARTY_NOTICES.md`
- License audit (full): `../../docs/SKILLS_LICENSE_AUDIT.md`
- Tandem composition + workflow: `../../docs/SKILLS_FRAMEWORK.md`
- **Do not edit vendored skill files in place.** Behavior changes go in `verdict-house-rules/` so upstream updates can be pulled cleanly.

## Adding a new skill

1. License-check: must be MIT or Apache-2.0 per CLAUDE.md §3.8.
2. Update `THIRD_PARTY_NOTICES.md` with source URL, vendored commit, and license text.
3. Update `docs/SKILLS_LICENSE_AUDIT.md` with the audit row.
4. Update this README and `docs/SKILLS_FRAMEWORK.md` with where the skill plugs into the pipeline.
5. Single commit per skill: `chore(skills): vendor <name> from <upstream> [W1.A.0]`.
