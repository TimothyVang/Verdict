---
name: verdict-house-rules
description: Re-states the load-bearing CLAUDE.md §3 hard rules so they apply in every session. Triggers on session start, before any code edit, before any commit, and on any reach for a vendored skill. Authoritative override when this skill conflicts with a vendored upstream skill.
---

# Verdict house rules

This skill is the project-specific overlay on top of the vendored Superpowers and mattpocock skills under `.claude/skills/`. **When this skill conflicts with anything in a vendored skill, this skill wins.** That is the entire point of having it — upstream skills are general-purpose; Verdict has hard forensic and licensing constraints they can't know about.

The full charter lives in `CLAUDE.md` (project root). Read it end-to-end before touching code. The seven rules below are the ones most likely to be violated by a generic agent acting on instinct.

## 1. No mocks, ever — §3.10

Tests run against real services: real SGLang, real Microsandbox, real Anthropic API, real `.E01` evidence. **Do not** introduce `unittest.mock`, `MagicMock`, `patch` against Verdict-internal modules, `responses`/`httpx_mock`/`vcr.py`, hard-coded synthetic evidence, or `if MOCK or TEST_MODE:` branches. If a service is down, the test fails — that is correct behavior. If you find yourself reaching for a mock, you are wrong about which test belongs at that layer; surface the conflict instead of papering over it.

Patching a third-party library at the system boundary in a single targeted test is allowed. Mocking your own module is not.

## 2. Conventional Commits with `[W#.#.#]` task ID — §3.7

Every commit in this repo follows: `<type>(scope): summary [W#.#.#]`.

- `type` ∈ {`feat`, `fix`, `test`, `chore`, `docs`, `refactor`}. No others.
- `[W#.#.#]` task ID is **required**. Find it from a `BUILD_PLAN.md` reference in the diff, recent commit log (`git log -10 | grep '\[W'`), or fall back to `[W1.A.0]` for repo-wide foundational work.
- **Never** `--no-verify`, `--no-gpg-sign`, or `git commit --amend`. Pre-commit hook failure means fix and re-stage; do not bypass.

This rule layers **on top of** the Superpowers `test-driven-development` skill and the mattpocock `tdd` skill. The RED → GREEN cycle is theirs; the commit format is ours.

## 3. Multi-artifact corroboration — §3.2

`Finding.artifact_paths` and `Finding.artifact_classes` both have `min_length=2`. Execution-class MITRE techniques (T1059, T1106, T1204, T1218, T1543, T1547) require **≥2 distinct `ArtifactClass` values** — not just two paths in the same class. The validator `Finding._execution_requires_two_classes` enforces this; do not propose schema changes that relax it.

## 4. MITRE sub-technique precision — §3.5

Emit `T1055.012`, never bare `T1055`, when the sub-technique is determinable. Regex enforced: `^T\d{4}(\.\d{3})?$`. Inspect AI scorer `mitre_subtechnique_precision` fails CI if a parent technique is emitted when the sub was determinable.

## 5. Tier-1 caveats are non-optional — §3.3

Cite the artifact, acknowledge the caveat. The seven Tier-1 caveats live in `verdict/schemas/caveat_id.py` and `verdict/prompts/examiner_caveats.md`. Schema validates `Finding.caveats_acknowledged` at load time. Do not propose Findings that cite Amcache without `AMCACHE_LASTMODIFIED_NOT_EXEC`, ShimCache on Win 8.1+ without `SHIMCACHE_ORDER_CHANGED_WIN81`, `$STANDARD_INFORMATION` timestamps without `MFT_SI_STOMPABLE`, etc.

## 6. Epistemic vocabulary — §3.6

Verdict statuses are exactly: `VETTED_CLOUD`, `VETTED_AIRGAP`, `VETTED_DUAL`, `CONTESTED`, `UNVERIFIABLE`, `EXHAUSTED_REPLAN`. No others. Findings phrase attribution as **"evidence consistent with X"** — never "X did this". `Finding.status = UNVERIFIABLE` is a **first-class outcome**, not a failure to be hidden.

## 7. License hygiene — §3.8

Every new dependency, every vendored skill, every MCP server, must be **MIT or Apache-2.0**. The hard-NO list (Daytona AGPL, REMnux MCP GPL-3.0, Llama 4 / Gemma 3 community, Modal / LangSmith / Braintrust / Phoenix / AutoGen / MS Agent Framework) is final. CC-BY-SA, GPL, and AGPL are share-alike incompatible with this repo's MIT distribution.

When in doubt, audit the LICENSE file directly before adding the artifact. Record the audit in `docs/SKILLS_LICENSE_AUDIT.md` (skills) or `docs/RELEASE.md` (runtime deps).

## How this skill composes with the vendored stack

See `docs/SKILLS_FRAMEWORK.md` for the full pipeline. In one line: **brainstorming → grill-me / grill-with-docs → writing-plans → test-driven-development (Verdict-extended) → executing-plans → subagent-driven-development → systematic-debugging (on red) → verification-before-completion → requesting-code-review → finishing-a-development-branch → /qc.** This skill enforces the rules; the vendored skills enforce the discipline; `/qc` does the commit + auto-push.

## When this skill triggers

- **Session start** — before any other skill loads, so house rules win on conflict.
- **Before any code edit** — to assert the no-mocks rule and Conventional Commits rule.
- **Before any commit** — to verify `[W#.#.#]` task ID is present and no `--no-verify` flags are about to be used.
- **Before adding a dependency, skill, or MCP** — to assert the MIT/Apache-2.0 license check.
- **On any reach for a vendored skill** — to remind the agent that this overlay supersedes upstream.

If a vendored skill instructs the agent to do something that conflicts with these rules — for instance, an `executing-plans` instruction that suggests `git commit --no-verify` to unblock a hook failure — refuse, explain why, and fix the underlying issue instead.
