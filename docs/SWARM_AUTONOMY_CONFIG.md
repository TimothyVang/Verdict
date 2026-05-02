# SWARM_AUTONOMY_CONFIG

Reference doc for **flipping `VERDICT_SWARM_LIVE=1`** — the gate that takes the agent swarm from dry-run to actually invoking the Claude Agent SDK against real tasks. Read this end-to-end before flipping the flag. The PR that wires the SDK call site (Phase C below) **must** cite this document in its description.

Authority: this file refines `docs/AGENT_SWARM.md §12, §14` open questions with concrete defaults. CLAUDE.md §3 hard rules are non-negotiable and override anything here on conflict.

## 1. Credential path

The swarm worker reads credentials from the host environment in this order (matches `.env.example`):

1. `ANTHROPIC_API_KEY` — pay-per-token API key. Highest precedence. Usage shows up in the Anthropic console as API.
2. `CLAUDE_CODE_OAUTH_TOKEN` — long-lived OAuth from `claude setup-token`. Charges against the user's Claude Pro/Max subscription, **not** the API meter. Cheapest path for sustained autonomous runs.
3. `~/.claude/credentials.json` — interactive Claude Code OAuth login. Lower precedence because it's intended for human sessions, not headless runs.
4. `ANTHROPIC_API` — legacy alias. Lowest precedence.

`swarm.doctor` enforces presence (`check_credential_present`); the worker enforces it again at the gate so flipping `VERDICT_SWARM_LIVE=1` without a credential fails fast with a useful message.

OAuth tokens are **not redistributable** per Anthropic commercial terms (CLAUDE.md §3.9). They live in `.env` (gitignored) and never enter a microVM.

## 2. Per-role skill allowlist

This is what each role's `swarm/agents/*.md` frontmatter already encodes. Documented here as the canonical authorized set; do not add to it without a PR.

| Role                     | Skills                                                                                                                                                                                                |
|--------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| schema-engineer          | verdict-house-rules, using-superpowers, test-driven-development, systematic-debugging, verification-before-completion, requesting-code-review, finishing-a-development-branch, using-git-worktrees   |
| planning-engineer        | + claude-api                                                                                                                                                                                          |
| sandbox-engineer         | (base set above)                                                                                                                                                                                      |
| tool-wrapper-engineer    | (base set above)                                                                                                                                                                                      |
| eval-engineer            | + claude-api                                                                                                                                                                                          |
| reviewer                 | verdict-house-rules, verification-before-completion                                                                                                                                                   |
| auditor                  | verdict-house-rules, verification-before-completion                                                                                                                                                   |
| conductor                | verdict-house-rules, dispatching-parallel-agents                                                                                                                                                      |

**Explicitly rejected for autonomous use** (would block on human input or target a different topology):

| Skill                       | Why                                                                                                  |
|-----------------------------|------------------------------------------------------------------------------------------------------|
| brainstorming               | Requires user clarifying questions before implementation.                                            |
| grill-me, grill-with-docs   | Interactive interview loops.                                                                         |
| executing-plans             | Designed for human-reviewed plan execution in a separate session.                                    |
| receiving-code-review       | Workers dispatch *to* reviewers; they do not receive feedback in this async model.                   |
| subagent-driven-development | Workers *are* subagents — this skill is for parent agents dispatching subagents.                     |
| writing-plans               | Plans are pre-authored in `docs/BUILD_PLAN.md`. Workers consume entries, not author them.            |
| writing-skills              | Out of scope for workers executing BUILD_PLAN tasks.                                                 |

## 3. Per-role MCP allowlist

Six servers in `.mcp.json` cover the autonomous-ops use case for the hackathon window. All MIT/Apache-2.0; tokens injected via `${VAR}` substitution from the host shell, never literals (CLAUDE.md §3.9).

| Role                  | MCPs                                              |
|-----------------------|---------------------------------------------------|
| schema-engineer       | filesystem                                        |
| planning-engineer     | filesystem, sequential-thinking, context7         |
| sandbox-engineer      | filesystem                                        |
| tool-wrapper-engineer | filesystem                                        |
| eval-engineer         | filesystem, sequential-thinking, context7         |
| conductor             | github                                            |
| auditor               | github                                            |
| reviewer              | github                                            |

**Post-hackathon candidates** (do not add tonight): an MIT-licensed web-search MCP for live bug research, an `sqlite` MCP for cross-role ledger reads. Anything AGPL/GPL/ELv2/proprietary — see CLAUDE.md §3.8 hard-NO list — stays out.

## 4. Authorization checklist for `VERDICT_SWARM_LIVE=1`

These are the §14 open questions, resolved as defaults. Override via env var or per-task only with an explicit PR.

- **Token budget per task** — default `$2`. Buys roughly one Haiku 4.5 task plus retries. The `$5`/`$20` AGENT_SWARM.md §14 options remain available; this default is conservative on purpose. Override with `VERDICT_TASK_BUDGET_USD=<n>`.
- **Per-role model tier** — defaults:
  - workers (schema, sandbox, tool-wrapper) → `claude-haiku-4-5-20251001`
  - eval-engineer → `claude-haiku-4-5-20251001`
  - reviewer → `claude-haiku-4-5-20251001`
  - planning-engineer → `claude-sonnet-4-6` (the `claude-opus-4-7` hardcoding in `swarm/agents/planning-engineer.md` is preserved as an opt-in override only)
  - auditor → `claude-haiku-4-5-20251001`
  - conductor → `claude-haiku-4-5-20251001`
- **Cumulative spend ceiling** — hard kill at `$50` per overnight run. Failsafe, not a target. Override with `VERDICT_NIGHT_CEILING_USD=<n>`.
- **HMAC-key tasks (W3.D.3)** — stay `requires_human` in `swarm/deps.yaml`. Reaffirmed.
- **Conductor cadence** — 30 s polling on PR state (AGENT_SWARM.md §4.1). Unchanged.
- **Reviewer attempt cap** — fourth rejection → task marked `blocked` with reason `red_loop_exhausted` (AGENT_SWARM.md §5). Unchanged.

## 5. What flipping `VERDICT_SWARM_LIVE=1` authorizes

In plain language. By setting this flag with a valid credential present you are authorizing the swarm to:

1. Invoke the Claude Agent SDK against real Anthropic endpoints, billed against whichever credential resolved per §1. Watch your console / subscription quota.
2. Create branches, push commits, and open pull requests on `https://github.com/TimothyVang/Verdict` using `${GITHUB_TOKEN}` from `.env`.
3. Run real `pytest` / `ruff` / Inspect AI evals on the host filesystem (CLAUDE.md §3.10 — no mocks; tests run for real).
4. Spin up real Microsandbox microVMs for tool wrappers that need them.
5. Post `gh pr review` verdicts (approve / request-changes) from the reviewer + auditor.
6. Mark tasks `blocked` and stop on `requires_human` items rather than attempt them.

You are **not** authorizing:

- Force-push, history rewrite, or branch deletion. The swarm only ever creates new branches and opens PRs.
- Touching `requires_human` tasks (HMAC keys, hardware-bound work).
- Adding dependencies outside the §3.8 license allowlist.
- Skipping pre-commit hooks or signing (CLAUDE.md §3.7).

## 6. Smoke-test recipe (run before sleeping)

```bash
# 1. Doctor must pass cleanly with .env loaded.
set -a; source .env; set +a
python -m swarm.doctor                    # expect all-green

# 2. Worker gate without flag → still stubbed.
python -m swarm.worker run --task-id W0.S.0   # exit 2, "Phase 0"

# 3. Worker gate with flag, real credential.
VERDICT_SWARM_LIVE=1 python -m swarm.worker run --task-id W0.S.0
# Once Phase C lands: should drive a single low-budget task end-to-end and
# open a draft PR. Until then: exit 2, "live-mode not yet implemented".

# 4. Negative — flag set, credential stripped:
unset ANTHROPIC_API_KEY CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_API
VERDICT_SWARM_LIVE=1 HOME=/tmp/no-creds python -m swarm.worker run --task-id W0.S.0
# expect: exit 2, "no credential"
```

## 7. Phase C — what's still missing for true overnight autonomy

Implementing the live SDK call inside `cmd_run()`. Concretely:

- `claude_agent_sdk.query()` invocation with assembled prompt, `allowed_tools` list per role, `mcp_servers` per role, model selection per role.
- Cost-tracking integration — read response usage, accumulate against `VERDICT_TASK_BUDGET_USD` and `VERDICT_NIGHT_CEILING_USD`.
- Failure handling — SDK exceptions, rate limits, budget exceeded → mark task `blocked` not `failed`.
- Conductor wiring — actually invoke `swarm.worker run` for ready tasks (currently dry-run only).
- Reviewer + Auditor PR loop closure (`gh pr review` posting from worker subagents).
- `tests/swarm/test_worker_live_smoke.py` — real Anthropic call against a single tiny task per CLAUDE.md §3.10.

This is a multi-PR Phase-1 effort and explicitly out of scope for the PR that introduces this document. Phase C requires a separate, named "yes, build the live runner" approval with a budget number.
