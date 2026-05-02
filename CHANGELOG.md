# CHANGELOG

Build progress for VERDICT, optimised for LLM / agent consumption.

## How to read this file

- **Newest first.** `[Unreleased]` lists in-flight branches/PRs not yet on `main`. Below that, sections are reverse-chronological by build phase (W0 → W1 → W2 …). See `docs/BUILD_PLAN.md` for the forward-looking sequence; this file is its retrospective shadow.
- **One entry per merged commit.** Format: `- [TASK_ID] type(scope): summary — <short-sha>` and, where relevant, ` · PR #N`. Task IDs come from `docs/BUILD_PLAN.md` (e.g. `W0.W.2` = Phase 0, Worker sub-track, step 2).
- **What `git log` already tells you, this file does not repeat.** Diffs, authorship, timestamps → use `git`. This file groups by sub-track and surfaces unmerged work + cross-PR context that `git log` cannot.
- **Authority.** Code and `docs/ARCHITECTURE.md` win over this file. If an entry here disagrees with current code, the entry is stale — fix it via PR, do not reverse the code.
- **Update rule.** Every PR that lands on `main` must add or update an entry here in the same commit. CI will eventually enforce this; for now it is on the author.

Sub-track key (Phase 0 / W0):

| Code  | Sub-track                                         |
|-------|---------------------------------------------------|
| W0.A  | Workspace bootstrap (skills, MCP, settings)       |
| W0.S  | Swarm scaffolding — agent definitions + frontmatter |
| W0.M  | MCP allowlist + per-role wiring                   |
| W0.W  | Swarm worker (loader, live gate, SDK call site)   |

Phase 1+ sub-tracks (`W1.A`, `W1.B`, …) are listed in `docs/BUILD_PLAN.md`.

---

## [Unreleased]

In-flight branches and open PRs against `main`.

- [W0.W.2] feat(swarm): gate worker behind `VERDICT_SWARM_LIVE` + 4-path credential precedence (`ANTHROPIC_API_KEY` → `CLAUDE_CODE_OAUTH_TOKEN` → `~/.claude/credentials.json` → `ANTHROPIC_API`). Adds `swarm.doctor.check_credential_present()` and `docs/SWARM_AUTONOMY_CONFIG.md` (authority doc for flipping the live flag). — `baa237e` · PR #2

---

## Phase 0 — Swarm scaffolding (W0)

The autonomous engineering swarm: agent definitions, MCP wiring, worker loader. Lands the dry-run substrate that `[W0.W.2]` will eventually flip to live.

### W0.W — Worker

- [W0.W.1] test(swarm): assert `load_agent_definition` AgentDef contract — `f226173`

### W0.M — MCP

- [W0.M.2] feat(mcp): add `context7` to `.mcp.json` for planning + eval agents — `d707942`
- [W0.M.1] test(swarm): assert `.mcp.json` contract + cross-ref to agent frontmatter — `6162ff0`

### W0.S — Swarm agents

- [W0.S.2] feat(swarm): wire skills + `mcp_servers` via per-role frontmatter — `3d678f8`
- [W0.S.1] test(swarm): assert agent frontmatter contract for every role — `6b62dbe`
- [W0.S.0] chore(swarm): pin `python-frontmatter` + `claude-agent-sdk` + `anthropic` — `ea11f2e`

---

## Phase 1.A — Workspace bootstrap (W1.A)

> Note: `W1.A.0` predates the W0 sub-tracks because the swarm was carved out of W1 mid-Phase-0; the numbering is preserved for traceability with `docs/BUILD_PLAN.md`.

- [W1.A.0] docs(claude): ban Claude Code watermarks in commits/PRs (CLAUDE.md §3.7) — `3c3fbbc`
- [W1.A.0] chore(mcp): pin 5-server allowlist + isolation framework — `97f8767`
- [W1.A.0] chore(skills): vendor superpowers + grill-me + tandem framework — `e8a317e`
- [W1.A.0] chore(swarm): flesh out Phase 0 with workflow-review sweep — `ecdb5e6`
- [W1.A.0] chore(swarm): scaffold engineering agent swarm (Phase 0) — `9056fe7`
- [W1.A.1] chore(onboarding): add `bootstrap-dev.sh` + LLM-agent quickstart — `6765b91`
- [W1.A.2] docs: close `DOCS_ACCURACY_REPORT` punchlist (H1–H6, M2–M4) — `c9356f2`
- [W1.A.2] docs: integrate `verdict.zip` bundle (ARCHITECTURE / BUILD_PLAN / DEVPOST_COMPLIANCE / DOCS_ACCURACY) — `9cba45d`
- [W1.A.1] chore: add `.env.example`, CONTRIBUTING, SECURITY — `c79fed7`
- [W1.A.0] chore: initial workspace — `97d3207`
