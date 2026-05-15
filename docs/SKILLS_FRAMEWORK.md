# SKILLS_FRAMEWORK — using the vendored skill stack in tandem

> **Wiki:** [Index](README.md) · [TL;DR](TLDR.md) · [Architecture](ARCHITECTURE.md) · [Build Plan](BUILD_PLAN.md) · [MCP Framework](MCP_FRAMEWORK.md) · [Skills License Audit](SKILLS_LICENSE_AUDIT.md) · root [CLAUDE.md](../CLAUDE.md)

**Status:** Phase 0 (vendored, documented; per-task wiring lands as W2+ tasks are taken). This doc is **engineering scaffolding**, not part of Verdict's runtime authority chain. The Verdict runtime topology lives in `ARCHITECTURE.md`.

**Authority:** below `BUILD_PLAN.md` and `CLAUDE.md`. The skill stack obeys every rule in `CLAUDE.md` §3 — `verdict-house-rules` is the overlay that enforces this. Nothing in this doc supersedes either.

**Date:** 2026-05-02 (Week 1, Day 1).

---

## 1. Why a tandem framework

Sixteen skills under `.claude/skills/` is more than any single task should pull on. Without composition discipline, a generic agent will skip planning, jump to code, and skip the review/commit gate. The framework below pins down **which skill fires when**, **which Verdict hard rule each skill enforces**, and **which subagent_type runs it**, so a session opened against the Verdict charter executes the same loop every time.

The composition is a single-pass pipeline. Each phase has a defined input, output, the skill that runs it, and the gate that admits it to the next phase. Iteration happens **inside** a phase (e.g. RED → GREEN → REFACTOR inside test-driven-development), not by jumping back across the pipeline.

## 2. The tandem pipeline

```
                          verdict-house-rules (ALWAYS — overlay, session start)
                                          │
                                          ▼
   ┌───────────────────────────────────────────────────────────────────────────┐
   │                                                                           │
   │  Phase 1.  understand        ──▶  brainstorming  +  grill-me  +  grill-with-docs
   │            (Socratic)              ARCHITECTURE.md / BUILD_PLAN.md as ground truth
   │                                          │
   │                                          ▼
   │  Phase 2.  plan              ──▶  writing-plans
   │            (decompose)              file paths + tests-before-code, 2–5 min tasks
   │                                          │
   │                                          ▼
   │  Phase 3.  implement (TDD)   ──▶  test-driven-development  (verdict-house-rules
   │            (RED→GREEN→REFACTOR)     adds [W#.#.#] task-ID + no-mocks check)
   │                                          │
   │                                  ┌───────┴───────┐
   │                                  ▼               ▼
   │  Phase 3a. parallel       dispatching-parallel-  using-git-worktrees
   │            fan-out        agents                  (worktree per branch)
   │                                          │
   │                                          ▼
   │  Phase 3b. subagent-       subagent-driven-development
   │            driven dev      (impl in fresh subagent; review in second)
   │                                          │
   │                                          ▼
   │  Phase 4.  debug (on RED)  ──▶  systematic-debugging  (4-phase root-cause)
   │            ↑ loop back to phase 3 if root cause requires plan change
   │                                          │
   │                                          ▼
   │  Phase 5.  verify          ──▶  verification-before-completion
   │            (proof landed)              executing-plans (checkpoints)
   │                                          │
   │                                          ▼
   │  Phase 6.  review          ──▶  requesting-code-review  +  receiving-code-review
   │            (severity gate)          merge / discard / keep
   │                                          │
   │                                          ▼
   │  Phase 7.  commit + push   ──▶  finishing-a-development-branch  →  /qc
   │            (gates pass)             Conventional Commits w/ [W#.#.#], auto-push
   │                                                                           │
   └───────────────────────────────────────────────────────────────────────────┘
```

## 3. Phase-by-phase: skill, hard rule, gate

| Phase | Skill(s) | CLAUDE.md hard rule(s) enforced | Output (gate to next phase) |
|---|---|---|---|
| 0. Always-on overlay | `verdict-house-rules` | All §3 rules | Loaded at session start. Wins on conflict with vendored skills. |
| 1. Understand | `brainstorming`, `grill-me`, `grill-with-docs` | §3.6 epistemic vocabulary, §3.3 caveat awareness | A bullet list of resolved decisions. If architecture or build sequencing must move, `grill-with-docs` drafts the proposed doc change for human-reviewed PR; it does not silently mutate authority docs. |
| 2. Plan | `writing-plans` | §3.7 task-ID discipline, §3.10 real-services-first | A plan: `<task_id>`, files to touch, **tests written first**, acceptance gate. |
| 3. Implement (TDD) | `test-driven-development` + `verdict-house-rules` | §3.7 RED→GREEN→commit, §3.10 no mocks, §3.2 multi-artifact corroboration in schemas | Failing test, then passing test, with diff staged. **One commit per task ID**. |
| 3a. Parallel fan-out (optional) | `dispatching-parallel-agents`, `using-git-worktrees` | §3.7 (one task per worktree) | Independent worktrees per branch; merge order documented. |
| 3b. Subagent-driven (optional) | `subagent-driven-development` | §3.10 real-services in the subagent's microsandbox too | Two-stage review: spec compliance, then code quality. This is a local development pattern only; it is not a separate source-code automation product surface. |
| 4. Debug (on RED) | `systematic-debugging` | §3.6 (UNVERIFIABLE is a first-class outcome — give up explicitly), §3.10 (don't mock to make red go away) | Root cause documented; fix is targeted. If root cause requires a plan change, return to phase 2. |
| 5. Verify | `verification-before-completion`, `executing-plans` | §3.1 evidence integrity (re-hashing), §3.10 (services up before passing) | All tests green against real services; `verdict doctor` is part of the gate. |
| 6. Review | `requesting-code-review`, `receiving-code-review` | §3.7 (no `--amend`, no `--no-verify`), §3.8 (no forbidden deps slipped in) | Severity-ranked review; merge / discard / keep decision. |
| 7. Commit + push | `finishing-a-development-branch` → `/qc` | §3.7 Conventional Commits w/ `[W#.#.#]`, no destructive flags | Code commit + optional docs-sync commit (same task ID), both auto-pushed. The docs-sync step (Step 5.5 of `/qc`) is the local counterpart to the `verdict-doc-drift` cron routine. |

## 4. Skill conflict resolution

When a vendored skill conflicts with a Verdict hard rule, **`verdict-house-rules` wins**. Examples we expect:

| Conflict | Vendored guidance | Verdict override |
|---|---|---|
| Pre-commit hook fails on a TDD commit | A generic `executing-plans` instruction might suggest `git commit --no-verify` to unblock | **§3.7 forbids `--no-verify`.** Fix the underlying lint/test issue, re-stage, create a NEW commit. |
| Test is hard to write because a service isn't running | A generic `test-driven-development` instruction might suggest mocking the service | **§3.10 forbids it.** Bring the service up; re-run. If unable to in the current environment, surface the conflict to the human; do not paper over. |
| New dependency speeds development | A generic `writing-plans` instruction might add it casually | **§3.8 audit gate.** License must be MIT or Apache-2.0; if not, refuse. Update `docs/SKILLS_LICENSE_AUDIT.md` or `docs/RELEASE.md`. |
| Commit message doesn't carry a task ID | A generic `finishing-a-development-branch` instruction might omit it | **§3.7 task-ID required.** Look up `BUILD_PLAN.md`; fall back to `[W1.A.0]` only for repo-wide foundational work. |

## 5. Skill triggers (hooks)

Auto-trigger discipline matters because Superpowers' skills can fire at any prompt. We constrain via `.claude/settings.json` hooks (Phase 1 wiring; not yet committed):

| Hook | Skill triggered | Why |
|---|---|---|
| `SessionStart` | `verdict-house-rules`, `using-superpowers` | Overlay loads first, then the vendored framework's index. |
| `UserPromptSubmit` (matches "plan", "design", "feature") | `brainstorming` → `grill-me` → `writing-plans` | Plan-first pattern (Reddit consensus #1 failure mode is solving the wrong problem). |
| `PreToolUse` (Write/Edit) | `test-driven-development` + `verdict-house-rules` | Block code writes that don't follow a failing test. (See also: `tdd-guard` integration in §6.) |
| `PreToolUse` (Bash with `git commit`) | `finishing-a-development-branch` + `/qc` | Conventional Commits format check before the commit lands. |

## 6. Future workstreams

The framework is intentionally Phase 0 — skills are vendored and documented, but **automatic triggering** lands later as we wire `.claude/settings.json` hooks. Tracked follow-ups:

- **`tdd-guard` integration.** MIT-licensed Node tool that hard-blocks code edits without a failing test (CLAUDE.md §3.7 in code form). Install pin via `scripts/bootstrap-dev.sh`; wire `PreToolUse` hook in `.claude/settings.json`. Tracked under `[W1.A.0]` follow-on.
- **MCP allowlist enforcement.** Pair this skill stack with the mode-scoped `.mcp*.json` configs — see `docs/MCP_FRAMEWORK.md`.
- **Skill-trigger telemetry.** Langfuse traces should record which skill fired for which decision so we can audit drift between framework intent and observed behavior.
- **Per-skill hard-rule citation.** Audit each vendored SKILL.md for places where a Verdict hard rule applies but isn't restated; add a citation in `verdict-house-rules` rather than editing upstream.

## 7. Anti-patterns (what NOT to do)

- **Don't edit vendored skill files in place.** All Verdict-specific behavior goes in `verdict-house-rules` so `git pull upstream main` re-vendoring stays mechanical.
- **Don't pile on more skills.** The Reddit consensus is "2–3 plugins max + a precise CLAUDE.md beats 50 generic plugins". We have 16; that is already at the upper end. New skills require the §3.8 audit gate **and** a clear pipeline-phase justification.
- **Don't skip phases.** The pipeline is single-pass on purpose. If you find yourself jumping from phase 1 to phase 7, you're rationalizing vibe-coding.
- **Don't mock to satisfy a skill.** `test-driven-development` will pass with mocked tests; `verdict-house-rules` will fail the commit. The mock is the bug.
