# VERDICT — Agentic Workflow Review

**Audited:** 2026-05-02
**Scope:** the **agentic workflow** — both the runtime loop the tool runs at investigation time (LangGraph planner → executor → quorum cycle, mode-locked verifier strategies, ledger discipline) and the development loop humans+Claude use to build it (TDD cycle, hard rules in `CLAUDE.md` §3, Conventional Commits, weekly gates). Sister audit: `docs/DOCS_ACCURACY_REPORT.md` (counts/labels/MITRE IDs).
**Methodology:** (1) two parallel agent passes — one for runtime, one for dev workflow — against `README.md`, `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/BUILD_PLAN.md`, `docs/DEVPOST_COMPLIANCE.md`, `CONTRIBUTING.md`, `SECURITY.md`; (2) cross-doc claim verification with grep+read; (3) findings filtered against the prior accuracy report so the two audits don't overlap.

---

## Severity legend

- **CRITICAL** — semantic gap that will cause runtime hang, schema rejection, or judging defence failure. Must fix before W1.B schema freeze (May 8) or W2.B LangGraph compile.
- **HIGH** — internal inconsistency or under-specified contract that will surface as a bug or rework during W2–W3.
- **MEDIUM** — clarity gap that won't break execution but would let a SANS judge ask a question the docs can't answer crisply.
- **LOW** — wording / future-proofing nits. None promoted to this report; sister doc captures these.

Finding IDs are prefixed `R*` (runtime workflow) or `D*` (development workflow) to keep sister-audit pointers grep-able.

---

## CRITICAL — must fix before May 8

### R1. `VerdictStatus` enum — three docs disagree, README mixes both spellings

**Where:** `CLAUDE.md` §3.6 line 77, `docs/ARCHITECTURE.md` §1 line 20, `docs/DEVPOST_COMPLIANCE.md` line 75, `README.md` lines 96 + 105.

**Claims (verbatim):**
- `CLAUDE.md`: "Verdict statuses are exactly: `VETTED_CLOUD`, `VETTED_AIRGAP`, `VETTED_DUAL`, `CONTESTED`, `UNVERIFIABLE`, `EXHAUSTED_REPLAN`. No others."
- `ARCHITECTURE.md` §1: "≥2-of-3 → `VETTED_CLOUD`; below → `DRAFT_CLOUD`."
- `DEVPOST_COMPLIANCE.md`: "VerdictStatus enum distinguishes: DRAFT / VETTED_CLOUD / VERIFIED_AIRGAP / VERIFIED_DUAL / CONTESTED / UNVERIFIABLE / APPROVED / REJECTED"
- `README.md` line 96: "→ 2-of-3 → VETTED_CLOUD" / line 105: "three-way verification → VERIFIED_DUAL"

**Reality:** Three different value sets across three authority docs (`DRAFT_CLOUD` only in ARCH; `DRAFT`, `VERIFIED_*`, `APPROVED`, `REJECTED` only in DEVPOST_COMPLIANCE; `VETTED_*` and `EXHAUSTED_REPLAN` only in CLAUDE.md). README cites both `VETTED_CLOUD` and `VERIFIED_DUAL` in the same demo block. Per the authority chain (`CLAUDE.md` §2: Devpost → DEVPOST_COMPLIANCE → ARCH → BUILD_PLAN → CLAUDE.md), DEVPOST_COMPLIANCE technically wins — but DEVPOST_COMPLIANCE's list is also internally inconsistent (mixes prefixes).

**Impact:** Schema validators in W1.B reference an enum that doesn't exist as a single source of truth. Any agent reading the docs to write a Pydantic `Literal[…]` will pick the wrong values; that error then propagates through ledger event types, scorer code, and the demo's per-mode accuracy table.

**Fix:** Adopt CLAUDE.md's 6-value list (`VETTED_CLOUD`, `VETTED_AIRGAP`, `VETTED_DUAL`, `CONTESTED`, `UNVERIFIABLE`, `EXHAUSTED_REPLAN`) as canonical because (a) it's the operating charter the agents read first; (b) `VETTED_*` is more honest than `VERIFIED_*` for cloud mode (same-model self-consistency is vetting, not verification); (c) `DRAFT/APPROVED/REJECTED` are workflow states for findings-under-review and belong on `Finding.review_state`, a separate field. Update ARCH §1 line 20 (`DRAFT_CLOUD` → `CONTESTED`); rewrite DEVPOST_COMPLIANCE.md line 75; flip README line 105 `VERIFIED_DUAL` → `VETTED_DUAL`. Add a clarifying sentence to CLAUDE.md §3.6 distinguishing **engine-quorum verdict** (the immediate output of a `VerifierStrategy`) from **case verdict** (the stored `Finding.status`).

---

### R2. Quorum tie-breaking rule unspecified when all engines disagree

**Where:** `CLAUDE.md` §8 (verifier strategies), `docs/ARCHITECTURE.md` §1 + §2 quorum_node.

**Claim:** `AirGapCrossEngine` requires "Jaccard ≥ 0.80 AND identical `mitre_technique`". `DualLaneCrossEngine` requires "cloud agrees with ≥1 local AND locals agree". Demo beat ⓹ asserts "Disagreement → CONTESTED → replan → VERIFIED".

**Reality:** No rule defines what happens when (a) cloud returns `{T1055.012, prefetch_hit}`, Qwen3 returns `{T1055.012, registry_hit}`, GLM returns `{T1106, amcache_hit}` — partial MITRE agreement, low Jaccard, three different artifact tuples. Is that CONTESTED (replan) or UNVERIFIABLE (terminate)? Disagreement-level threshold for CONTESTED-vs-UNVERIFIABLE isn't defined.

**Impact:** Without an explicit dispatch table, `quorum_node`'s code path is ambiguous; reviewers will write three subtly different implementations.

**Fix:** Add an explicit dispatch table to `ARCHITECTURE.md` §1 per strategy. Suggested rules:

| Strategy | Result | Status |
|---|---|---|
| Cloud n=3 | ≥2 agree on `(mitre, artifacts)` | `VETTED_CLOUD` |
| Cloud n=3 | <2 agree | `CONTESTED` (replan) |
| AirGap | Jaccard ≥0.80 AND identical MITRE | `VETTED_AIRGAP` |
| AirGap | Jaccard ≥0.80, different MITRE | `CONTESTED` (replan) |
| AirGap | Jaccard <0.80 | `CONTESTED` (replan) |
| Dual | cloud agrees with ≥1 local AND locals agree | `VETTED_DUAL` |
| Dual | cloud disagrees with both locals | `CONTESTED` (replan) |
| Dual | cloud agrees with 1 local, locals disagree with each other | `CONTESTED` (replan) |
| Any | After `replan_max=3` exhaustion | `EXHAUSTED_REPLAN` → `unverifiable_finalize_node` |

---

### R3. Empty-set Jaccard undefined for `AirGapCrossEngine`

**Where:** `docs/ARCHITECTURE.md` §1 AirGap row, `CLAUDE.md` §8 second bullet.

**Claim:** "Jaccard ≥0.80 on `artifact_paths`."

**Reality:** Jaccard(∅, non-∅) = 0 / |non-∅| = 0. The spec doesn't say whether that counts as DISAGREEMENT (Jaccard < 0.80 → CONTESTED) or as a NULL VOTE that lets the non-empty engine "win" by default. The same ambiguity affects `DualLaneCrossEngine` when one lane returns no findings.

**Impact:** Without a rule, an executor that crashes silently (no findings) becomes a free pass for the other engine — destroys the cross-engine guarantee. Also affects R6 (timeout branches).

**Fix:** One-line rule in `ARCHITECTURE.md` §1: **empty-set parsed_artifacts from any participant in any quorum strategy is treated as DISAGREEMENT, never as a null vote.** This propagates to `quorum_node` and to the timeout-branch behavior in R6.

---

### D1. `§3.10 no-mocks` rule has zero mechanical enforcement

**Where:** `CLAUDE.md` §3.10 (full sub-section), `CONTRIBUTING.md` §5 line 220.

**Claim:** No `unittest.mock`, `responses`, `vcr.py`, `betamax`, `httpx_mock`, `if MOCK or TEST_MODE: ...` branches anywhere in the codebase. Schema validators that short-circuit on `os.environ.get("VERDICT_TEST")` are forbidden.

**Reality:** No CI hook, no pre-commit linter, no AST check enforces this. `CONTRIBUTING.md` mentions only `ruff` (which has no built-in rule against mock imports). The rule lives entirely in CLAUDE.md prose; enforcement is "Claude reads the file and feels guilty."

**Impact:** §3.10 is the load-bearing claim for Devpost rubric criterion #4 (Constraint Implementation) and the SANS-judge defence ("how real is the integration?"). A commit at hour 36 that adds `from unittest.mock import patch` for a "quick test" lands without alarm; once it's in, more follow.

**Fix:** Add task to `BUILD_PLAN.md` `W1.A.7` (pre-commit setup): write a ~40-LOC custom AST hook (`scripts/check_no_mocks.py`) that walks all `.py` files under `verdict/` and `tests/` and rejects any of: `import unittest.mock`, `from unittest import mock`, `import responses`, `import vcr`, `import betamax`, `import httpx_mock`, regex `if .*(MOCK|TEST_MODE).*:`, regex `os\.environ\.get\(['"]VERDICT_TEST`. Wire as a `pre-commit` local hook.

---

## HIGH — must fix before W2.B (LangGraph compile)

### R4. Mode-mismatch resume UX undefined

**Where:** `CLAUDE.md` §3.4, no `verdict resume` failure-path doc.

**Claim:** "`verdict resume <case_id>` reads the original mode and refuses to advance if the current `detect_mode()` differs."

**Reality:** "Refuses to advance" is unspecified. Exit code? Stderr message? Suggestion to operator? In the demo a laptop reboot between cases changes detected mode (network bounce); without a clear UX, the demo blanks.

**Fix:** Add to `CLAUDE.md` §3.4 (after the existing sentence): `verdict resume` raises `ModeLockedError`, exits 2, prints to stderr: `Case {case_id} was initialized in mode={original_mode}; current environment is mode={detected_mode}. To re-run under the new mode, use: verdict reverify {case_id} --mode {detected_mode}`.

---

### R5. Comprehension-gate clarify sub-state has no iteration cap

**Where:** `docs/ARCHITECTURE.md` §2 comprehension_gate.

**Claim:** "Mismatch → clarify sub-state (re-prompts within the same node, not a separate top-level node — total node count stays 9)."

**Reality:** No `max_clarify_iterations` budget. If executors persistently disagree on `parsed_positive_hypothesis_ids`, the gate re-prompts indefinitely. The graph never reaches `replan_max=3`; it just hangs. Same risk pattern as `pivot_max=15` and `tool_arg_retry_max=2`, both of which *are* bounded.

**Fix:** Add `max_clarify_iterations=2` to `ARCHITECTURE.md` §2. On exhaustion, treat as CONTESTED → `replan_node` with a hint: `comprehension_persistent_mismatch: executors disagreed on {field} after {N} clarify rounds`.

---

### R6. Executor fanout reducer behavior on branch timeout undefined

**Where:** `docs/ARCHITECTURE.md` §2 executor_fanout, `BUILD_PLAN.md` (no failure-mode doc yet — `FAILURE_MODES.md` is W1.G.2).

**Claim:** Four executor branches in parallel; each tool call has a `timeout=600s` budget.

**Reality:** Reducer behavior on partial completion is unspecified. If 1 of 4 branches hangs at the libkrun layer (microsandbox stuck spawning), does the reducer wait the full 600s? Block forever? Emit a partial result after 3 finish? Mark the hung branch as UNVERIFIABLE? Demo "kill -9 + verdict resume" guarantees nothing if the kill happens *during* a hung fanout because there's no expected reducer outcome to compare against.

**Fix:** Document in `docs/FAILURE_MODES.md` (W1.G.2) and reference from ARCH §2: reducer fires once `timeout` elapses OR all four branches return — whichever first. Hung branch emits `ToolOutput(status=TIMEOUT, parsed_artifacts=[])` and is treated as a CONTESTED contributor (per R3 — empty-set is DISAGREEMENT, not null vote). Reducer never blocks past `branch_timeout = 1.5 × tool_timeout = 900s`.

---

### R7. Pivot re-entry state-merge contract missing

**Where:** `docs/ARCHITECTURE.md` §2 pivot_node + Pivot vs replan distinction subsection.

**Claim:** "PIVOT (cheap, `pivot_max=15`): single Hypothesis added on basis of an executor's output. Re-enters `executor_work` only."

**Reality:** When `pivot_node` adds one hypothesis to `InvestigationPlan.hypotheses` and re-enters `executor_fanout`, does the fanout run on (a) all hypotheses including the previous round's, or (b) only the newly added one? Reducer dedup behavior on `case.findings` isn't defined either — same hypothesis run twice could yield two near-identical Finding rows.

**Fix:** Spec in ARCH §2 Pivot subsection: pivot re-runs the 4 executor branches against the **single new hypothesis only** (not the full hypothesis list). The fanout reducer **appends** results to `case.findings` without deduplication; downstream `quorum_node` does the per-hypothesis grouping. State invariant: after N pivots, `len(case.findings) ≈ 4 × (initial_hypotheses + N)`, modulo branch timeouts.

---

### R8. Reverify "parallel verdict chain" semantics vague

**Where:** `README.md` line 73, `docs/DEVPOST_COMPLIANCE.md` line 134, `CLAUDE.md` §3.4 + §10.

**Claim:** "Mode upgrades happen via explicit `verdict reverify` producing a parallel verdict chain."

**Reality:** "Parallel verdict chain" is undefined. Where does the fork happen — `case_init` or `planner_node`? How does `verdict show <case_id>` distinguish chains? When `verdict approve <finding_id>` runs and a finding exists in both chains, which one gets signed? Export format ambiguity for `verdict export <case_id>` — does it include all chains or default to original?

**Fix:** Author `docs/CASE_ISOLATION.md` (already on the next-turn create list) with: chain forks at `planner_node` (carries forward `case_init`'s evidence manifest, mode lock = the new mode); `thread_id = f"{case_id}-reverify-{new_mode}-{utc_iso}"`; `verdict show <case_id>` lists all chains and their statuses; `verdict approve` requires `--chain-id` when more than one exists; `verdict export` defaults to the original chain, `--chain-id all` for both.

---

### R9. ModelRetry exhaustion produces a Finding the schema will reject

**Where:** `docs/ARCHITECTURE.md` §6 Tool-call argument validation, `CLAUDE.md` §3.2 (artifact_paths min_length=2).

**Claim:** "On validation failure: raise `ModelRetry`, bounded by `tool_arg_retry_max=2`, then UNVERIFIABLE." `Finding.artifact_paths` has `min_length=2`.

**Reality:** When retries exhaust, the executor wants to emit `Finding(status=UNVERIFIABLE, artifact_paths=[], caveats_acknowledged=[], rationale="tool args failed validation after 2 retries")`. The validator rejects this because `artifact_paths` is empty. The current spec is internally contradictory.

**Fix:** Add to `ARCHITECTURE.md` §6 + the Finding schema in §4: validator branch `_unverifiable_relaxes_corroboration` — when `Finding.status == UNVERIFIABLE` AND `Finding.failure_reason` is set, `artifact_paths` and `caveats_acknowledged` may be empty. Add the `failure_reason: Optional[str]` field to the schema.

---

### D2. TDD "Failing test" sub-tasks underspecified for ≥8 tasks

**Where:** `docs/BUILD_PLAN.md` various `*.a` lines (sample: `W2.D.2`, `W2.D.3`, `W3.A.1`, `W3.A.3`, `W3.D.1`, `W5.A.1`, `W5.B.1`, `W6.C.9`).

**Claim:** Per `CLAUDE.md` §3.7: "Failing test → RED → implement → GREEN → one commit per task ID."

**Reality:** Many `*.a` "Failing test" subtasks name a test file but don't pin the single RED assertion. Example: `W3.A.3.a — Failing test 'tests/verification/test_dual_lane_cross_engine.py::test_...'` — the test name is elided. Risk: a Claude agent infers an assertion that's adjacent to the intent, the test passes, the implementation is wrong but the gate is green.

**Fix:** Sweep BUILD_PLAN; every `*.a` subtask must include the literal RED assertion (e.g., `assert result.status == VerdictStatus.VETTED_DUAL` or `assert ledger_writer.write(...) raises HashMismatchError`). Add to BUILD_PLAN intro section: "RED-line policy: every `*.a` subtask names a test path AND the single failing assertion."

---

### D3. Pre-commit hook config doesn't exist; CONTRIBUTING.md silently no-ops

**Where:** `CONTRIBUTING.md` line 140 + line 220, `CLAUDE.md` §3.7, `BUILD_PLAN.md` line 556.

**Claim:** `CONTRIBUTING.md`: "Pre-commit hooks installed; `pre-commit run --all-files` green." `CLAUDE.md` §3.7: "Never `--no-verify`, never `--no-gpg-sign`, never `git commit --amend`. Pre-commit hook failure means fix and re-stage; do not bypass." `BUILD_PLAN.md` line 556: gate `Conventional Commits enforced (no --no-verify)` measured by grep against `git log`.

**Reality:** No `.pre-commit-config.yaml` exists. Line 140 uses `test -f .pre-commit-config.yaml && uv run pre-commit install --install-hooks` — silently no-ops because the file is missing. Line 220's "hooks installed; green" is currently a lie. The grep gate at line 556 only catches missing prefixes after the fact (does not block bad commits). All §3.7 rules are unenforced.

**Fix:** Pull `.pre-commit-config.yaml` creation into the W1.A.7 acceptance criteria (today it's implicit). Bare-minimum config: (a) `commitizen check` against a regex requiring `^(feat|fix|test|chore|docs|refactor)\(\w+\): .* \[W\d+\.[A-Z]\.\d+(\.[a-z])?\]$`; (b) `ruff check --select ALL`; (c) the `scripts/check_no_mocks.py` AST hook from D1. Once the file lands, drop the `test -f` short-circuit in `CONTRIBUTING.md` line 140.

---

## MEDIUM — clarify before judge demo

### R10. Microsandbox `spawn()` failure path unspecified

**Where:** `docs/ARCHITECTURE.md` §6 Pattern 1 + Pattern 2.

**Claim:** Both patterns call `await microsandbox.spawn(...)` — no `try/except` shown.

**Reality:** What happens if `spawn()` fails (kernel resource exhaustion, image missing, libkrun crash, host disk full)? Ledger event_type? Retry logic? Cascade to UNVERIFIABLE?

**Fix:** Add to `docs/FAILURE_MODES.md` (W1.G.2): `microsandbox.spawn()` exception → `ToolExecutor` logs `LedgerEntry(event_type='sandbox_failure', error_detail=...)`, no retry (kernel-level errors are not transient), the associated finding is marked `UNVERIFIABLE` with `failure_reason='sandbox_spawn_failed'`. Reference R9.

---

### R11. TSI proxy unreachable behavior unspecified

**Where:** `docs/ARCHITECTURE.md` §6 Pattern 2.

**Claim:** Pattern 2 routes through `proxy_origin="opencti.local:8080"` for credential injection.

**Reality:** What if the TSI proxy is down (host restarted, port closed, DNS fail)? `microsandbox.spawn()` raises `NetworkProxyError`? Counted against `tool_arg_retry_max`?

**Fix:** Same FAILURE_MODES.md paragraph: `NetworkProxyError` is treated like any other tool failure — logged to ledger with `event_type='tool_call'` + `error_detail`, counts against `tool_arg_retry_max`. After exhaustion → UNVERIFIABLE.

---

### R12. Caveat trigger keying not documented

**Where:** `CLAUDE.md` §3.3 (Tier-1 caveat table).

**Claim:** Triggers like "Any Amcache citation" or "Prefetch citation when host is SSD-only" are listed without saying which schema field they key on.

**Reality:** Most triggers fire on `Finding.artifact_classes` (e.g., `AMCACHE` present → `AMCACHE_LASTMODIFIED_NOT_EXEC` required). But `LOGON_TYPE_3_VS_10` is keyed on the *content* of `EVTX_4624` records (network logon vs RDP), not on the artifact class itself. This is implicit, not stated.

**Fix:** Prepend one sentence to the §3.3 table: "Caveat triggers are keyed by `Finding.artifact_classes` membership unless otherwise noted. `LOGON_TYPE_3_VS_10` is the named exception: triggered by `EVTX_4624` artifact_class AND the EvtxRecord.LogonType field equaling 3 or 10."

---

### R13. Sub-technique precision rule (§3.5) doesn't address negative hypotheses

**Where:** `CLAUDE.md` §3.5, §3.6 (negative hypothesis rules).

**Claim:** §3.5: "Emit `T1055.012`, never bare `T1055`, when the sub-technique is determinable." §3.6: "Negative hypotheses must have a non-None `mitre_technique`."

**Reality:** Two rules; their interaction isn't stated. Can a negative hypothesis emit bare `T1014` (which has no sub-techniques per the FIX in `DOCS_ACCURACY_REPORT` C1)? Or must the validator force sub-technique precision on negatives too?

**Fix:** Append one sentence to §3.5: "Sub-technique precision applies equally to positive and negative hypotheses. Bare technique is acceptable only when no sub-technique exists (e.g., `T1014`, `T1106`); the regex `^T\d{4}(\.\d{3})?$` enforces shape but not sub-technique-required."

---

### D4. CI hallucination-rate gate has no `.github/workflows/` file

**Where:** `CLAUDE.md` §10.3 line 302, `BUILD_PLAN.md` W4.D.4.

**Claim:** "CI hard gate: hallucination rate ≤10% in every mode by end of week 4, else freeze tool count and spend week 5 on prompt/skill refinement."

**Reality:** `BUILD_PLAN.md` schedules the workflow file in W4.D.4 — late week 4. By the time it lands, the metric only retroactively gates the *next* week's commits, not the four weeks of code that produced the >10% rate. No `.github/workflows/` file is staged today.

**Fix:** Stage a stub workflow `.github/workflows/eval-hallucination-gate.yml` in W1.A.7 that runs `inspect eval inspect_ai/tasks/verdict_eval_cloud.py --score hallucination_rate` and fails on >10%. Stub the scorer to return 0.0 (always pass) until W4.D.1 implements the real one. This wires the gate into CI before any hallucination-producing code lands.

---

## Summary punchlist (priority order)

1. **R1** — `VerdictStatus` enum cascade across 4 files. Adopt CLAUDE.md's 6-value list as canonical; rewrite ARCH §1 line 20 (`DRAFT_CLOUD` → `CONTESTED`); rewrite DEVPOST_COMPLIANCE.md line 75; flip README line 105 (`VERIFIED_DUAL` → `VETTED_DUAL`); add engine-quorum-vs-case-verdict distinction to CLAUDE.md §3.6.
2. **R2 + R3** — Add a quorum dispatch table to ARCH §1 covering all three strategies; add empty-set-is-DISAGREEMENT rule.
3. **R4** — Spec `ModeLockedError` exit-code + stderr in CLAUDE.md §3.4.
4. **R5** — Add `max_clarify_iterations=2` to ARCH §2 comprehension_gate.
5. **R7** — Spec pivot state-merge: 4 branches × 1 new hypothesis, append to `case.findings`, no dedup.
6. **R9** — Add `_unverifiable_relaxes_corroboration` validator branch + `failure_reason` field; cite from ARCH §6.
7. **D1 + D3** — Pull `.pre-commit-config.yaml` into W1.A.7 acceptance; add `scripts/check_no_mocks.py` AST hook task.
8. **D2** — BUILD_PLAN sweep: every `*.a` "Failing test" subtask names the literal RED assertion; add RED-line policy to BUILD_PLAN intro.
9. **R12** — Caveat-trigger-keying note at top of CLAUDE.md §3.3 table.
10. **R13** — Sub-technique-applies-to-negatives sentence appended to CLAUDE.md §3.5.
11. **D4** — Stage `.github/workflows/eval-hallucination-gate.yml` stub task in W1.A.7.
12. **R6, R10, R11, R8** — Defer to next-turn doc creation: `docs/FAILURE_MODES.md` (R6 + R10 + R11), `docs/CASE_ISOLATION.md` (R8). These were already on the post-DOCS_ACCURACY_REPORT punchlist.

**Estimated fix effort:** ~75 minutes for items 1–11 (in-place edits to 5 existing docs); items 12 are next-turn doc creation already scoped.
