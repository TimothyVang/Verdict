# VERDICT — Agent swarm (engineering scaffolding)

> **Wiki:** [Index](README.md) · [TL;DR](TLDR.md) · [Architecture](ARCHITECTURE.md) · [Build Plan](BUILD_PLAN.md) · [Skills Framework](SKILLS_FRAMEWORK.md) · [MCP Framework](MCP_FRAMEWORK.md) · root [CLAUDE.md](../CLAUDE.md)

**Status:** Phase 0 (skeleton landed; SDK calls deferred). This doc is **engineering scaffolding**, not part of the Verdict runtime authority chain. The Verdict *runtime* topology — the planner → fanout → quorum LangGraph — lives in [`ARCHITECTURE.md`](ARCHITECTURE.md) and is out of scope here. The two are different "agents": runtime executors are tool-call dispatchers operating on evidence; this swarm is LLM workers operating on source code.

**Authority:** below `BUILD_PLAN.md` and `CLAUDE.md`. The swarm consumes `BUILD_PLAN.md` task IDs read-only and obeys every rule in `CLAUDE.md` §3. Nothing in this doc supersedes or modifies either.

**Date:** 2026-05-02 (Week 1, Day 1).

---

## 1. Why a swarm

`BUILD_PLAN.md` lays out **75 teammate-days** of TDD work across ~140 first-class files in **6 weeks**, against a hard 2026-06-14 EOD Devpost deadline. The team is four humans: Tim (PUG), Beaver, Haley, KP. Even with weekend burn the arithmetic is tight. The swarm is leverage, not replacement: humans review, ratify, and merge; LLMs handle the bounded write-failing-test → implement → green-test → push loop.

Two structural facts make per-task agent work tractable in this codebase:

1. **No mocks (CLAUDE.md §3.10).** Every test runs against real services (SGLang, Microsandbox, Anthropic API, real `.E01` evidence). Green/red is unambiguous. There is no "the test passes but the integration is broken" failure mode an agent can paper over.
2. **TDD with task IDs (§3.7).** Every commit is `<type>(scope): summary [W#.#.#]`. Provenance is mechanical to verify. Auditor agent grep-checks compliance per diff.

Risks acknowledged up front: API cost, prompt-driven hallucination, drift between agent output and architectural intent. Mitigations: per-task token budget, reviewer + auditor agents, human merge gate, Langfuse traces for every call, daily cost digest. The swarm has no autonomous merge authority; GitHub CODEOWNERS/branch protection is the target enforcement layer and remains a release blocker until configured.

---

## 2. Substrate

**Claude Code Agent Teams, headless, Python helper modules.** Primary entrypoint is `scripts/run-team.sh` — a Claude Code session opens with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and creates a 4–5 teammate team per launch. Sequential batches (~6–10 launches drain the remaining backlog). Each teammate is a full Claude Code session with its own context window, model, and tool allowlist.

A subagent-driven fallback path lives in `scripts/run-swarm.sh` for cases where Agent Teams' experimental quirks bite (no `/resume` for in-process teammates, lead-shutdown-before-done).

| Decision | Choice | Why |
|---|---|---|
| Dispatch | Claude Code Agent Teams (experimental, v2.1.32+) | Native shared task list with file-locked self-claim, mailbox messaging, TaskCompleted hook gate. No bespoke async pool. |
| Pool size per launch | 4–5 teammates | Per Agent Teams docs — "three focused teammates often outperform five scattered ones." Diminishing returns above 5; file-conflict risk on shared edits. |
| Model — orchestrator (lead session) | `claude-opus-4-7` (1M ctx) | Long-running coordination, resume-set diffing, multi-task synthesis. |
| Model — `planning-engineer` | `claude-opus-4-7` | LangGraph topology, CoVe critique, replan budgets — reasoning-heavy. |
| Model — `schema/sandbox/tool-wrapper/eval-engineer` | `claude-sonnet-4-6` | Bulk implementation work; mechanical with judgment. ~5× cheaper than Opus, fits §14 budget. |
| Model — reviewer (TaskCompleted hook) | `claude-sonnet-4-6` | Mechanical pass/fail on lint/test output. Runs as a hook script, not a teammate. |
| Model — auditor (TaskCompleted hook) | `claude-haiku-4-5` | Pattern-match scan over a diff. Cheapest tier. Runs as a hook script, not a teammate. |
| Storage (cross-launch state) | SQLite WAL + fsync (`swarm/swarm.db`) | Same discipline as the runtime ledger (CLAUDE.md §9). Agent Teams' shared task list lives at `~/.claude/tasks/<team>/` and does NOT survive cleanup; persistent state belongs in `swarm/swarm.db`. |
| Auth | `CLAUDE_CODE_OAUTH_TOKEN` (Pro/Max subscription) | Each teammate is a full Claude Code session inheriting the lead's auth. `ANTHROPIC_API_KEY` is the direct API fallback; `OPENROUTER_API_KEY` is an optional host-side fallback for build-side AI agents if direct Anthropic quota is constrained. |
| Per-task token ceiling | $20 USD | Tracked in `swarm/state.py:tasks.token_spend_usd`. Worker exceeds → exits `turn_budget_exceeded`. |

Why not bespoke `asyncio` SDK pool: Agent Teams already provides shared task list + mailbox + TaskCompleted hook + file-locked claim. Reimplementing those in `swarm/worker.py` is duplication; the SDK path is the *fallback*, not the default.

Why not GitHub Actions: per-job container spin-up is 30–60 s and runners cost more per minute than direct subscription calls when the unit of work is a single TDD loop. GHA may host CI later (W1.A.1 includes `.github/workflows/`); it's the wrong substrate for the worker pool itself.

---

## 3. Topology

```
    BUILD_PLAN.md ──read──▶ Conductor ──┬──▶ Worker[schema]      ─┐
    (ground truth)        (SQLite     │
                           state)     ├──▶ Worker[planning]      │
                                      │                          │
                                      ├──▶ Worker[sandbox]       ├──▶ Reviewer ──┐
                                      │                          │   (CI gate)   │
                                      ├──▶ Worker[tool-wrap]     │               │
                                      │                          │               ▼
                                      └──▶ Worker[eval]          ─┘    Auditor ──▶ PR
                                                                    (rules scan)   │
                                                                                   ▼
                                                                            Human merge
                                                                        (CODEOWNERS once configured)
```

Five worker specializations, one of each Conductor / Reviewer / Auditor. Workers parallelise; coordinator and reviewers are singletons (a second reviewer is fine, two conductors is a bug — atomic claim still works, but state ownership becomes a footgun).

---

## 4. Roles

### 4.1 Conductor

Single instance. Long-running. Reads `BUILD_PLAN.md` at startup and on `swarm reload-plan`. Builds dependency DAG (within-phase: sequential by task ID; cross-phase: from `swarm/deps.yaml`, human-curated). Picks ready tasks (status `pending`, all blockers `merged`, not `requires_human`). Dispatches to a worker matching the task's specialization. Monitors PR state via `gh pr view` polling at 30 s cadence. Owns SQLite state. **Never edits code.**

CLI surface: `swarm start`, `swarm pause`, `swarm status`, `swarm reload-plan`, `swarm unblock <task-id>`, `swarm doctor`.

### 4.2 Worker pool

N=2–4 parallel workers (cap configurable; CI worker count and Anthropic rate-limit drive the ceiling). On claim:

1. `git worktree add worktrees/<task-id> -b <type>/<task-id>-<slug> origin/main`
2. Load shared system prompt + role-specialized override + the task's BUILD_PLAN entry verbatim
3. Run TDD loop via Agent SDK: write failing test → observe RED → implement → observe GREEN → run linters → make one final commit for the task ID
4. Push branch, open PR via `gh pr create` with template body
5. Hand to Reviewer; status → `review`

**Five specializations** map to BUILD_PLAN phase ownership:

| Worker | BUILD_PLAN phases owned | Key authority refs |
|---|---|---|
| `schema-engineer` | W1.B, W1.C, W1.B.10 caveat validators | CLAUDE.md §3.1–§3.6, ARCHITECTURE.md §5 schemas |
| `planning-engineer` | W1.G, W2.A planner + critique | ARCHITECTURE.md §1, §4 verifier strategies |
| `sandbox-engineer` | W1.A.3, W1.A.6, W2.D microsandbox + rootfs | CLAUDE.md §3.1 (read-only `/evidence`, noexec), §3.9 |
| `tool-wrapper-engineer` | W1.E, W2.B, W3.A tool wrappers + infra glue | ARCHITECTURE.md §4 tool-pair splits, CLAUDE.md §3.2 |
| `eval-engineer` | W4.D, W4.E, W4.G Inspect AI tasks + scorers | CLAUDE.md §3.10 (no-mocks), BUILD_PLAN W4 |

A generalist `infra-engineer` is folded into `tool-wrapper-engineer` (with a `mode: infra` switch) to keep the role surface tight; tasks under W3.F (healthcheck), W6.A (demo scripts) route here.

### 4.3 Reviewer

Single instance. Sonnet 4.6. On `review`:

1. Fetch worker branch into a clean worktree
2. Run the local CI gate: `ruff check`, `ruff format --check`, `cargo clippy --all-targets --all-features -- -D warnings` (if Cargo.toml present), `eslint .` (if applicable), `uv run pytest -q`, `uv run pre-commit run --all-files`
3. Verify `git log --show-signature` shows good signatures on every new commit
4. Verify TDD audit: PR body includes RED and GREEN command output, and the branch has one final Conventional Commit for the task ID
5. On all-green: `gh pr review --approve` with summary; status → `audit`
6. On any-red: `gh pr review --request-changes` with the failing log; status → `claimed` (worker retries up to 3 times, then escalates)

Reviewer **never** writes code. It runs tools, reads output, posts structured feedback.

### 4.4 Auditor

Single instance. Haiku 4.5. Passive on every PR after Reviewer approves. Scans the full diff for CLAUDE.md §3 violations:

| Hard rule | Auditor check |
|---|---|
| §3.1 evidence integrity | Any new file path matching `^evidence/` written from code → flag |
| §3.2 multi-artifact corroboration | `Finding(...)` constructions with `artifact_paths=[...]` containing <2 entries → flag |
| §3.3 caveat acknowledgment | Amcache cite without `AMCACHE_LASTMODIFIED_NOT_EXEC` in `caveats_acknowledged` → flag |
| §3.5 MITRE precision | Bare `T1055` (no sub-technique) → flag, unless the technique has no sub-techniques upstream (`T1014`, `T1106`, etc.). Auditor ships a parent-only allowlist mirroring CLAUDE.md §3.5. |
| §3.7 git discipline | Commit subject missing `[W#.#.#]` task ID → flag; `--no-verify` / `--no-gpg-sign` / `--amend` traces in reflog → flag |
| §3.8 dependency hard-NO | Any new `daytona`, `langsmith`, `braintrust`, `arize-phoenix`, `modal`, or AGPL-licensed pkg in lockfiles → flag |
| §3.10 no mocks | `MockExecutor`, `MockSandbox`, `MockLLM`, `unittest.mock.MagicMock` against `verdict.*`, `responses`, `httpx_mock`, `vcr.py`, `if MOCK or TEST_MODE`, `os.environ.get("VERDICT_TEST")` → flag |

Findings posted as PR comments. **Blocking** on §3.1, §3.2, §3.7, §3.8, §3.10 (sets `blocking: true` label; CODEOWNERS and branch protection make this non-bypassable once W1/W3 GitHub scaffolding lands). **Advisory** on §3.5, §3.6 (informational comment; does not block).

### 4.5 Human gate

PUG (Tim) / Beaver / Haley / KP. Target state: CODEOWNERS plus branch protection requires at least one human approval before every merge. Until the CODEOWNERS file and branch rule are present, this is a human process gate, not an enforced GitHub control. Swarm has **no merge authority**, ever; any swarm-token PAT must be configured so `gh pr merge` returns 403.

When humans review a swarm PR they read: (1) Reviewer's checks summary, (2) Auditor's findings, (3) the diff itself. If the swarm did its job, that's the entire mental load — no archeology, no reproduction.

---

## 5. Task lifecycle

```
                            ┌────────── escalate ─────────┐
                            │                             │
   pending ──claim──▶ claimed ──RED──▶ red ──GREEN──▶ green ──push──▶ review
                                                                        │
                                                                        ▼
                                                                       audit
                                                                        │
                              merged ◀── approve ── human_review ◀──────┘
                                                        │
                                                    (or reject)
                                                        │
                                                        ▼
                                                     blocked
                                                        │
                                              ┌─ swarm unblock <id>
                                              ▼
                                            pending
```

Transitions:

- `pending → claimed`: atomic SQL `UPDATE … WHERE status='pending' AND owner IS NULL`. Exactly one winner per row.
- `claimed → red`: worker has pushed a failing test commit.
- `red → green`: worker has pushed an implementation commit that turns the test green.
- `green → review`: branch pushed, PR opened. Teammate signals task complete; Claude Code's `TaskCompleted` hook fires `.claude/hooks/task-completed.sh`, which runs Reviewer + Auditor in one pass against the worktree. (When using the SDK fallback in `run-swarm.sh`, Reviewer + Auditor are dispatched as separate subagent calls instead.)
- `review → audit`: Reviewer (in-hook) reports clean.
- `review → claimed`: Reviewer reports failures; hook exits with `{"decision":"block"}` and the teammate revises (`attempts` increments).
- `audit → human_review`: Auditor (in-hook) finds nothing blocking. Hook exits 0; task marks complete.
- `audit → blocked`: Auditor finds a BLOCKING violation; hook exits with `{"decision":"block"}` and the teammate revises before the task can re-complete.
- `human_review → merged`: human approves and merges.
- `human_review → blocked`: human requests changes the swarm cannot resolve.
- `blocked` is terminal until `swarm unblock <task-id>` clears the reason and resets to `pending`.
- `requires_human`: set at startup for tasks the swarm should never claim (W1.A.4 needs an H100; W1.A.7 needs Docker on the host; W3 hardware-bound work). Documented in `swarm/deps.yaml` under `requires_human:`.

`attempts` cap = 3. On the fourth Reviewer rejection, status → `blocked` with reason `red_loop_exhausted`; conductor pages humans.

---

## 6. Coordination protocol

### 6.1 SQLite state schema

```sql
CREATE TABLE tasks (
  task_id           TEXT PRIMARY KEY,    -- e.g. "W1.B.7"
  phase             TEXT NOT NULL,       -- e.g. "W1.B"
  specialization    TEXT NOT NULL,       -- "schema" | "planning" | "sandbox" | "tool-wrapper" | "eval"
  status            TEXT NOT NULL,       -- pending|claimed|red|green|review|audit|human_review|merged|blocked|requires_human
  owner             TEXT,                -- worker ID, NULL if unclaimed
  branch            TEXT,                -- e.g. "feat/W1.B.7-min-length-2-artifact-paths"
  worktree_path     TEXT,
  pr_url            TEXT,
  attempts          INTEGER DEFAULT 0,
  last_event_ts     TEXT NOT NULL,       -- ISO8601 UTC
  blocked_reason    TEXT,
  token_spend_usd   REAL DEFAULT 0.0,
  langfuse_trace_id TEXT
) STRICT;

CREATE TABLE events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id       TEXT NOT NULL REFERENCES tasks(task_id),
  ts            TEXT NOT NULL,
  event_type    TEXT NOT NULL,           -- claim|red|green|push|approve|reject|audit_finding|merge|block|unblock
  details_json  TEXT NOT NULL
) STRICT;
```

WAL + `PRAGMA synchronous=NORMAL` (matches the runtime ledger discipline — CLAUDE.md §9).

### 6.2 Atomic claim

```sql
UPDATE tasks
   SET status='claimed', owner=:worker, last_event_ts=:now
 WHERE task_id=:task_id AND status='pending' AND owner IS NULL;
```

`cursor.rowcount == 1` → win. `0` → another worker got it; pick another candidate.

### 6.3 Dependency resolution

Within a phase: tasks are ordered by suffix (`W1.B.1 < W1.B.2 < … < W1.B.13`); a task is ready iff all earlier-suffix tasks in the same phase are `merged`.

Across phases: declared in `swarm/deps.yaml`:

```yaml
# W1.A.5 needs schemas to bind to:
W1.A.5: [W1.B.4, W1.B.6]
# eval scaffolding needs ground-truth fixtures:
W4.D.1: [W4.C.1]
requires_human:
  - W1.A.4   # SGLang on H100 — needs Haley + GPU box
  - W1.A.7   # Langfuse docker-compose — needs Docker on dev host
  - W4.C.1   # Engineered case_001 — humans curate ground truth
  - W4.C.2
  - W4.C.3
```

The conductor refuses to start if `deps.yaml` declares a cycle.

### 6.4 Worktree layout

```
<repo_root>/
├── .git/
├── ... (working tree on main)
└── worktrees/
    ├── W1.B.7/        # branch: feat/W1.B.7-min-length-2-artifact-paths
    ├── W1.B.8/        # branch: feat/W1.B.8-artifact-classes-field
    └── W1.E.1/        # branch: feat/W1.E.1-vol-psscan-wrapper
```

`worktrees/` is in `.gitignore`. Conductor cleans up via `git worktree remove` after merge (or after `blocked` for ≥24 h).

### 6.5 PR template

Title: matches the eventual squash-merge subject — `<type>(scope): summary [W#.#.#]`.

Body:

```markdown
## Task
[W1.B.7](BUILD_PLAN.md#L371)

## Mode(s) affected
all  <!-- or cloud / airgap / dual -->

## TDD evidence
- RED: `<command>` failed with `<short failure>` before implementation
- GREEN: `<command>` passed after implementation

## Reviewer checks
- [x] ruff
- [x] cargo clippy
- [x] pytest
- [x] signed commits
- [x] task ID in subject

## Auditor scan
No CLAUDE.md §3 violations detected.
```

---

## 7. System prompts

Every agent's system prompt is composed from a **shared prefix** (`swarm/agents/_prefix.md`) plus a role override (`swarm/agents/<role>.md`).

### 7.1 Shared prefix (~80 lines)

Embeds, verbatim where possible:

- The CLAUDE.md authority chain (Devpost → DEVPOST_COMPLIANCE → ARCHITECTURE → BUILD_PLAN → CLAUDE → spec/).
- All of CLAUDE.md §3 (hard rules) — copied in, not summarized. Drift between summary and source is the failure mode this avoids.
- The TDD loop contract: red → green → one commit per task ID.
- Forbidden git operations: `--no-verify`, `--no-gpg-sign`, `--amend`, `git rebase -i`, `git add -i`, force-push to main, hard-reset on shared refs.
- Dependency hard-NO list (Daytona, LangSmith, Braintrust, Arize Phoenix, Modal, AutoGen 0.4, Llama 4, Gemma 3, AGPL clean-room rewrites).
- The seven Tier-1 caveats (CLAUDE.md §3.3 table).
- Available tools: `Read`, `Write`, `Edit`, `Bash` (scoped allowlist), `gh` CLI, `git` CLI. Reads outside the worktree are forbidden by sandbox config.
- Escape valve: `swarm escalate <reason>` writes a structured note to the events table and ends the task in `blocked` rather than guessing.
- Self-test before commit: every worker MUST run the relevant test command and capture pass/fail in the commit body.

### 7.2 Per-role overrides (~40–80 lines each)

Eight files in `swarm/agents/`:

| File | Specialization | Domain context loaded |
|---|---|---|
| `conductor.md` | (orchestrator) | BUILD_PLAN parser; SQLite schema; deps.yaml format; PR-state polling. |
| `reviewer.md` | (gate) | Exact CI commands for each language; signed-commit verification; rerunnable fail-log format. |
| `auditor.md` | (compliance) | Full grep regex set per §3.X rule; advisory vs blocking matrix. |
| `schema-engineer.md` | Pydantic v2, validators | ARCHITECTURE.md §5 schema doc; the 7 caveat enums; `Finding` + `LedgerEntry` field discipline. |
| `planning-engineer.md` | LangGraph nodes, prompts | ARCHITECTURE.md §1 mode lock; §4 verifier strategies; CoVe critique node spec. |
| `sandbox-engineer.md` | Microsandbox, libkrun | CLAUDE.md §3.1 evidence invariants; §3.9 credential isolation; rootfs build pinning. |
| `tool-wrapper-engineer.md` | SIFT tool wrappers | ARCHITECTURE.md §4 tool-pair splits (plaso_extract + psort_filter; never monolithic); per-tool Pydantic IO contracts. |
| `eval-engineer.md` | Inspect AI, scorers | CLAUDE.md §3.10 (no mocks — eval IS the test surface); ground-truth case structure under `inspect_ai/ground_truth/case_00*/`. |

Per-role files do **not** restate the shared prefix. They specify: "files to read first," "common pitfalls," "domain-specific patterns to follow," "domain-specific anti-patterns to refuse."

---

## 8. Hard rules → enforcement matrix

Every CLAUDE.md §3 rule has at least one enforcement point. Defense in depth: a rule encoded only in a prompt is one model-mistake away from broken; rules also live in reviewer checks, auditor scans, and CI.

| Rule | Prompt | Reviewer | Auditor | CI |
|---|:-:|:-:|:-:|:-:|
| §3.1 evidence read-only | ✓ | | ✓ | ✓ (pre-commit hook on `evidence/` writes) |
| §3.2 multi-artifact ≥2 | ✓ | | ✓ | ✓ (Pydantic validator) |
| §3.3 caveat acknowledgment | ✓ | | ✓ | ✓ (Pydantic validator) |
| §3.4 mode lock | ✓ | | | ✓ (Pydantic validator) |
| §3.5 MITRE sub-technique | ✓ | | ✓ (advisory) | ✓ (Inspect scorer) |
| §3.6 epistemic vocabulary | ✓ | | ✓ (advisory) | ✓ (Inspect scorer) |
| §3.7 TDD + Conv. Commits | ✓ | ✓ | ✓ | ✓ (commitlint) |
| §3.8 dep hard-NO | ✓ | | ✓ | ✓ (license-check job) |
| §3.9 credential isolation | ✓ | | ✓ (PAT in diff) | ✓ (gitleaks) |
| §3.10 no mocks | ✓ | ✓ (test runs against real svc) | ✓ | ✓ (no `MOCK=true` path exists) |

If a row has zero CI columns checked, the swarm is the only thing standing between a bad commit and `main`. Audit periodically.

---

## 9. Verification gates

**Per-task** (Reviewer + Auditor): lint clean; build clean; test green; signed commit; RED and GREEN command output recorded in the PR body; exactly one final task commit unless the human explicitly approves a split; task ID `[W#.#.#]` in every commit subject; no forbidden imports; no mock patterns.

**Per-phase** (humans): the weekly acceptance gate already defined in BUILD_PLAN.md — schemas frozen by 2026-05-08, etc. Swarm does not redefine these. Conductor reports phase rollup ("W1.B: 11/13 merged, 2 blocked") in `swarm status`.

**Cumulative** (Inspect AI evals): hallucination rate ≤10% per mode by end of Week 4 (BUILD_PLAN W4.G.2). The swarm does not introduce a separate eval surface. `inspect_ai/tasks/verdict_eval_{cloud,airgap,dual}.py` is THE test surface, per CLAUDE.md §3.10. Per-PR CI runs the relevant subset; nightly runs the full set.

---

## 10. Observability

All Agent SDK calls flow through Langfuse v2 (the same instance Verdict's runtime uses, ARCHITECTURE.md §6). Trace tags differentiate namespaces:

- `swarm.task=W1.B.7` `swarm.role=schema-engineer` `swarm.attempt=1` — engineering swarm
- `verdict.case_id=...` `verdict.mode=cloud` — Verdict runtime

One Langfuse instance, two namespaces, no overlap. Cost dashboards filter by `swarm.*` or `verdict.*` tag.

`swarm doctor`: prints a green/red table mirroring `verdict doctor`'s style — Anthropic API reachable, `gh auth status` green, `gh repo view TimothyVang/Verdict` returns `WRITE`, worktree dir writable, SQLite WAL on, `bash scripts/bootstrap-dev.sh --check` exit 0.

Daily 0800 CDT digest posted to team chat (Slack webhook configured in `swarm/config.yaml`):

```
SWARM DIGEST — 2026-05-04
Merged today:  3   (W1.A.5, W1.B.1, W1.B.2)
In review:     2   (W1.B.3, W1.B.4)
Blocked:       1   (W1.A.4 — requires_human)
Spend:         $4.20  ($0.84 avg/task; budget $20)
Drift signal:  none
```

---

## 11. Failure modes + escalation

| Failure | Detection | Action |
|---|---|---|
| Worker stuck in red loop | `attempts >= 3` after Reviewer rejection | status → `blocked`, page humans |
| Hardware-gated task claimed by mistake | dep `requires_human` ignored | conductor refuses to dispatch; logs assertion error |
| Cyclic dependency | DAG build at startup | conductor halts, prints cycle, exit 2 |
| Cost runaway | task `token_spend_usd > 2 * budget` | conductor pauses pool, alerts |
| API rate-limit / 5xx | SDK exception | exponential backoff with jitter; after 5 min, status → `pending`, requeue |
| Anthropic outage | `swarm doctor` red | conductor pauses; resumes when healthy |
| `git worktree add` fails (lock held, disk full) | subprocess exit ≠ 0 | task → `blocked` with `worktree_failure`; surfaces to humans |
| Reviewer wrongly approves a broken PR | rare; surfaces in CI on `main` | post-merge revert PR; tighten Reviewer check |

`swarm escalate <task-id> --reason <text>` is the universal manual escape: any human can mark a task blocked from the CLI without reading SQLite directly.

---

## 12. Bootstrap sequence

| Phase | What | Who writes it |
|---|---|---|
| **Phase 0** (now) | Conductor + worker skeleton; SQLite state; agent prompt files; this doc | Humans, hand-authored |
| **Phase 1** | Swarm tackles W1.A.5 (FastMCP gateway), W1.A.6 (microsandbox provider), W1.A.7-related glue under heavy human supervision; first 5–10 PRs | Swarm; humans review every line |
| **Phase 2** | Reviewer agent comes online; swarm picks up W1.B schemas (~13 tasks, well-bounded) | Swarm; humans review every PR but not every commit |
| **Phase 3** | Auditor online; full autonomy on phases W2+; humans only review at PR level | Swarm; humans gate merges |

A swarm task that fails in Phase 1 with low-novelty (schema typo, lint miss) is signal that prompts need tightening. A swarm task that fails on architectural intent is signal that *humans* need to write the architectural part by hand and let the swarm do the wrapping. Trust accrues task-by-task.

---

## 13. File layout

```
swarm/                              # Python helper modules + role specs (canonical)
├── README.md                       # 5-line pointer to docs/AGENT_SWARM.md
├── conductor.py                    # plan parser + dep DAG (used by lead session)
├── worker.py                       # single-task TDD driver — fallback path only
├── reviewer.py                     # local CI gate runner — invoked from hook
├── auditor.py                      # rule-compliance scanner — invoked from hook
├── doctor.py                       # health-check (mirrors verdict doctor)
├── state.py                        # SQLite schema + atomic claim (cross-launch state)
├── deps.yaml                       # cross-phase deps + requires_human list
├── requirements.txt                # Phase-0 deps (anthropic, gitpython, langfuse)
├── runtime/
│   ├── worktree.py                 # git worktree manager
│   └── gh.py                       # PR + label helpers
└── agents/                         # canonical role specs (long-form discipline)
    ├── _prefix.md                  # shared system-prompt prefix
    ├── conductor.md                # advisory only; lead session is the conductor
    ├── reviewer.md
    ├── auditor.md
    ├── schema-engineer.md
    ├── planning-engineer.md
    ├── sandbox-engineer.md
    ├── tool-wrapper-engineer.md
    └── eval-engineer.md

.claude/                            # Claude Code harness handles
├── settings.local.json             # CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 + hooks block
├── agents/                         # subagent overlays (referenced as teammate types)
│   ├── schema-engineer.md          # frontmatter: model + tools; body points at swarm/agents/
│   ├── planning-engineer.md
│   ├── sandbox-engineer.md
│   ├── tool-wrapper-engineer.md
│   ├── eval-engineer.md
│   ├── reviewer.md                 # fallback; primary path is the TaskCompleted hook
│   └── auditor.md                  # fallback; primary path is the TaskCompleted hook
└── hooks/
    ├── suggest-skill.sh            # UserPromptSubmit skill suggestion helper; static fallback on failure
    └── task-completed.sh           # runs reviewer + auditor; exit-2 blocks completion

.github/workflows/
└── claude-pr-review.yml            # PR-side CLAUDE.md §3 review using Claude Code Action

scripts/
├── run-team.sh                     # PRIMARY entrypoint (Claude Code Agent Teams)
└── run-swarm.sh                    # FALLBACK (subagent-driven 20-wide pool)

swarm/memory/
├── README.md                       # memory protocol
├── lessons.jsonl                   # append-only raw lessons; intentionally not committed after bootstrap
└── patterns.md                     # distilled lessons read by teammates before code
```

The two `agents/` directories are **not duplicates** — `swarm/agents/*.md` holds canonical long-form role specs (~60–105 lines each: discipline, blocking matrix, common pitfalls); `.claude/agents/*.md` are thin harness overlays whose frontmatter exposes `model` + `tools` to Claude Code and whose body is a pointer instructing the teammate to load the swarm/agents/ spec for full discipline. Edit specs in `swarm/agents/`; edit model tiering or tool allowlists in `.claude/agents/`.

Phase-0 code remains minimal. The lead session does Phase-0 resume discovery + Phase-1 dispatch in-prompt (see `scripts/run-team.sh`). The SDK fallback worker command is not part of the supported surface until W1/W3 scaffolding implements it end-to-end; do not ship placeholder command paths.

Agent-Team launches now pre-filter tasks for non-overlapping file scopes, start teammates concurrently with `--permission-mode auto`, require SendMessage checkpoints (`RED`, `GREEN`, `PR`, `BLOCKED`, `DONE`), and distill `swarm/memory/lessons.jsonl` into `patterns.md` during cleanup.

---

## 14. Open questions

Time-stamped; ratify before each phase transition.

- **Should the swarm have its own task IDs?** A `W0.X` family for swarm work itself (state schema migrations, prompt revisions) would make swarm changes auditable in BUILD_PLAN.md. Decision needed by **2026-05-04** (before Phase 1).
- **Token budget per task.** ✅ **Closed 2026-05-02: $20 USD/task.** Tracked in `swarm/state.py:tasks.token_spend_usd`. Worker exceeds → exits `turn_budget_exceeded`, slot frees. Engineer-tier shift to Sonnet (below) keeps the average per-task burn well under the cap.
- **Reviewer model.** ✅ **Closed 2026-05-02: `claude-sonnet-4-6`** for the in-hook reviewer. Auditor settled at `claude-haiku-4-5` (was Sonnet, decided cheaper tier sufficient for pattern-match scans).
- **Engineer model tier.** ✅ **Closed 2026-05-02: Sonnet 4.6 for `schema/sandbox/tool-wrapper/eval-engineer`**, Opus 4.7 retained only for `planning-engineer` (LangGraph topology + CoVe critique). Earlier table assigned Opus to all five — empirically too expensive at ~70 tasks remaining; departure from the prior §2 line is recorded in the updated substrate table above.
- **HMAC-key handling for ledger work (W3.D).** Default: humans only. The swarm should not hold the runtime ledger HMAC key. Confirm with PUG before W3 starts.
- **OAuth vs API key.** Per CLAUDE.md §3.9 OAuth and API tokens are not redistributable and never enter microVMs. **Active mode (2026-05-02): `CLAUDE_CODE_OAUTH_TOKEN`** (Pro/Max subscription) for both lead and teammates — Tim's solo-developer rig, no redistribution. `ANTHROPIC_API_KEY` is the direct API fallback; `OPENROUTER_API_KEY` is an optional host-side fallback for build-side AI agents if subscription/API rate limits throttle 4–5 concurrent workers. Re-evaluate if rate-limit interruptions become recurring.
- **Auditor blocking power.** Default: blocking on §3.1, §3.2, §3.7, §3.8, §3.10; advisory on §3.5, §3.6. Re-evaluate after first 20 audits — if advisory rules drift unchecked, promote.
- **CODEOWNERS file.** Needed in W1 to enforce "no swarm self-merge." Add as part of `.github/` scaffolding when CI lands (BUILD_PLAN W3.F).
- **What happens if the swarm finds a bug in `BUILD_PLAN.md` itself?** Default: open a PR against the plan with the proposed fix, blocked on human review. Plan changes are not in any worker's prompt scope.

---

## 15. Pointers

| For… | Read |
|---|---|
| Verdict's runtime architecture (NOT this swarm) | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| The task IDs the swarm consumes | [`BUILD_PLAN.md`](BUILD_PLAN.md) |
| Hard rules every agent must obey | [`../CLAUDE.md`](../CLAUDE.md) §3 |
| Human contributor flow that the swarm mirrors | [`../CONTRIBUTING.md`](../CONTRIBUTING.md) |
| Dev toolchain `swarm doctor` shells out to | [`../scripts/bootstrap-dev.sh`](../scripts/bootstrap-dev.sh) |

This doc is engineering scaffolding. When in doubt about runtime behavior, defer to `ARCHITECTURE.md` — it wins.
