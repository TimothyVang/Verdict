# WEEK 3 (May 16 – May 22): Verifier strategies + TSI + Checkpointing

**Theme:** Cross-engine verification; TSI secret injection; durable execution; mode lock; pivot vs replan distinction; unverifiable_finalize.
**Critical-path output:** All three verifier strategies live; SqliteSaver with WAL/synchronous=FULL; kill-9 chaos test green; mode lock enforced; tcpdump proves TSI; trace_id ↔ ledger cross-link.
**Cumulative team-days:** Tim ~5, Beaver ~5, Haley ~1, KP ~2.

## Phase W3.A — Verifier strategy implementations (Beaver, ~2 days)

### W3.A.1 — `AirGapCrossEngine`
- [ ] **W3.A.1.a** — Failing test `tests/verification/test_airgap_cross_engine.py::test_both_must_agree_on_jaccard_080_artifact_set`. Plus `test_disagreement_returns_contested`.
- [ ] **W3.A.1.b** — Implement: Qwen3 plans (or GLM if Qwen unavailable); both Qwen3 + GLM execute in parallel; both must agree on `(artifact_paths, mitre_technique)` with Jaccard ≥0.80.
- [ ] **W3.A.1.c** — Commit: `feat(verification): AirGapCrossEngine [W3.A.1]`

### W3.A.2 — `DualLaneCrossEngine`
- [ ] **W3.A.2.a** — Failing test: cloud agrees with at least one local; locals agree with each other.
- [ ] **W3.A.2.b** — Implement.
- [ ] **W3.A.2.c** — Commit: `feat(verification): DualLaneCrossEngine three-way verification [W3.A.2]`

### W3.A.3 — Universal Self-Consistency full impl (Chen 2023)
- [ ] **W3.A.3.a** — Failing test `tests/verification/test_universal_self_consistency.py::test_judge_picks_most_consistent_rationale_among_n3`. Assertion: given three Findings with rationale strings differing in structure but agreeing in substance on two of three, `UniversalSelfConsistency.judge(findings).selected_index in {0, 1}` (the two-of-three majority) and `result.status == VerdictStatus.CONTESTED` is NOT returned (USC is the judge of last resort before CONTESTED).
- [ ] **W3.A.3.b** — Implement upgrade from W1.C.3 stub.
- [ ] **W3.A.3.c** — Commit: `feat(verification): Universal Self-Consistency judge [W3.A.3]`

## Phase W3.B — TSI enrichment (Tim, ~1.5 days)

### W3.B.1 — TSI provider Pattern 2
- [ ] **W3.B.1.a** — Failing test `tests/sandboxes/test_tsi_provider.py::test_credentials_never_enter_microvm`. Use tcpdump capture comparison: bearer header on egress to `opencti.local:8080`, NOT inside microvm.
- [ ] **W3.B.1.b** — Implement `verdict/sandboxes/tsi_provider.py` per v4.5 lines 482–489.
- [ ] **W3.B.1.c** — Commit: `feat(sandbox): TSI Pattern 2 with credential injection [W3.B.1]`

### W3.B.2 — TSI demo prep (Tim's W4.3 carryover)
- [ ] **W3.B.2.a** — Set up tcpdump filters on host + inside microvm. Produce reproducible side-by-side recording.
- [ ] **W3.B.2.b** — Document in `docs/DEMO_SEQUENCE.md` (see W6.A.1).
- [ ] **W3.B.2.c** — Commit: `chore(demo): TSI tcpdump demonstration assets [W3.B.2]`

### W3.B.3 — Ledger redaction pass
- [ ] **W3.B.3.a** — Failing test: `test_redacts_authorization_header_before_hash`. Plus `auth_user`, `api_key`.
- [ ] **W3.B.3.b** — Implement `verdict/ledger/redaction.py`. Strip + record in `payload_redactions` field.
- [ ] **W3.B.3.c** — Commit: `feat(ledger): redact auth fields before hash + write [W3.B.3]`

## Phase W3.C — Mode lock (Beaver, ~0.5 day)

### W3.C.1 — Mode-lock enforcement at `case_init`
- [ ] **W3.C.1.a** — Failing test `tests/runtime/test_mode_lock.py::test_resume_with_different_mode_refuses`. Plus `test_mode_at_case_init_immutable`.
- [ ] **W3.C.1.b** — Implement: write `mode_at_case_init` to ledger; refuse to advance if resume detects mode mismatch with current autodetect.
- [ ] **W3.C.1.c** — Commit: `feat(runtime): mode lock at case_init enforced on resume [W3.C.1]`

### W3.C.2 — `verdict reverify` command
- [ ] **W3.C.2.a** — Failing test: `verdict reverify <case_id> --mode dual` produces parallel verdict chain without mutating original.
- [ ] **W3.C.2.b** — Implement in `verdict/cli/reverify.py`. Re-runs ONLY quorum_nodes against existing executor outputs.
- [ ] **W3.C.2.c** — Commit: `feat(cli): verdict reverify produces parallel verdict chain [W3.C.2]`

## Phase W3.D — Pivot + replan + unverifiable_finalize (Beaver, ~1 day)

### W3.D.1 — `pivot_node` (cheap follow-up)
- [ ] **W3.D.1.a** — Failing test `tests/graph/test_pivot_node.py::test_adds_one_hypothesis_within_pivot_max_15`. Plus `test_pivot_does_not_re_enter_planner`.
- [ ] **W3.D.1.b** — Implement. Bounded `pivot_max=15` in `InvestigationPlan.pivot_budget`.
- [ ] **W3.D.1.c** — Commit: `feat(graph): pivot_node distinct from replan_node (max=15) [W3.D.1]`

### W3.D.2 — `replan_max=3` explicit budget on `InvestigationPlan`
- [ ] **W3.D.2.a** — Failing test: `replan_budget` field defaults to 3.
- [ ] **W3.D.2.b** — Implement.
- [ ] **W3.D.2.c** — Commit: `feat(schema): InvestigationPlan.replan_budget=3 explicit [W3.D.2]`

### W3.D.3 — `unverifiable_finalize_node`
- [ ] **W3.D.3.a** — Failing test `tests/graph/test_unverifiable_finalize.py::test_writes_unverifiable_finding_at_replan_iteration_4`. Plus `test_writes_exhausted_replan_ledger_event`. Plus `test_calls_interrupt`.
- [ ] **W3.D.3.b** — Implement.
- [ ] **W3.D.3.c** — Commit: `feat(graph): unverifiable_finalize_node + exhausted_replan event [W3.D.3]`

### W3.D.4 — Wire `interrupt()` properly
- [ ] **W3.D.4.a** — Failing test: analyst can `update_state` and resume after interrupt.
- [ ] **W3.D.4.b** — Implement `verdict/graph/interrupt.py` with helpers for resume-from-interrupt path.
- [ ] **W3.D.4.c** — Commit: `feat(graph): interrupt() helpers for HITL resume [W3.D.4]`

## Phase W3.E — Checkpointing (Beaver, ~1 day)

### W3.E.1 — `SqliteSaver` with WAL + synchronous=FULL
- [ ] **W3.E.1.a** — Failing test `tests/graph/test_checkpoint.py::test_pragma_journal_mode_wal`. Plus `test_pragma_synchronous_full`.
- [ ] **W3.E.1.b** — Implement `verdict/graph/checkpoint.py` with `PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;`.
- [ ] **W3.E.1.c** — Commit: `feat(graph): SqliteSaver with WAL + synchronous=FULL [W3.E.1]`

### W3.E.2 — `thread_id = case_id` everywhere
- [ ] **W3.E.2.a** — Failing test: gateway invocation passes `config={"configurable": {"thread_id": case_id}}`.
- [ ] **W3.E.2.b** — Implement.
- [ ] **W3.E.2.c** — Commit: `feat(graph): thread_id = case_id wiring [W3.E.2]`

### W3.E.3 — `verdict resume <case_id>` command
- [ ] **W3.E.3.a** — Failing test: kill -9 + restart picks up from last super-step.
- [ ] **W3.E.3.b** — Implement.
- [ ] **W3.E.3.c** — Commit: `feat(cli): verdict resume re-attaches LangGraph thread [W3.E.3]`

### W3.E.4 — `docs/CHECKPOINTING.md`
- [ ] **W3.E.4** — Author. Document single-writer + reducer pattern; per-case sqlite file rotation; WAL/fsync rationale. Commit: `docs: CHECKPOINTING.md [W3.E.4]`

### W3.E.5 — `trace_id` ↔ ledger cross-link
- [ ] **W3.E.5.a** — Failing test `tests/observability/test_trace_link.py::test_ledger_entry_has_langfuse_trace_id`. Plus `test_langfuse_span_has_ledger_entry_id_attribute`.
- [ ] **W3.E.5.b** — Implement `verdict/observability/trace_link.py` — bi-directional linking.
- [ ] **W3.E.5.c** — Commit: `feat(observability): trace_id ↔ ledger bidirectional cross-link [W3.E.5]`

### W3.E.6 — Kill-9 chaos test
- [ ] **W3.E.6.a** — Failing test `tests/chaos/test_kill_9_resume.py::test_100_cases_zero_super_step_loss`. 100 cases, kill -9 between super-steps, assert zero loss.
- [ ] **W3.E.6.b** — Implement chaos harness.
- [ ] **W3.E.6.c** — Commit: `test(chaos): kill -9 100-case zero-loss assertion [W3.E.6]`

## Phase W3.F — `/health` endpoint + healthcheck loop (Tim, ~0.5 day)

### W3.F.1 — `/health` endpoint
- [ ] **W3.F.1.a** — Failing test: returns `{mode, components: {langfuse, sglang, microsandbox, ledger}, last_healthcheck_utc}`.
- [ ] **W3.F.1.b** — Implement `verdict/cli/health.py`.
- [ ] **W3.F.1.c** — Commit: `feat(cli): /health endpoint [W3.F.1]`

### W3.F.2 — Continuous healthcheck loop (30s interval)
- [ ] **W3.F.2.a** — Failing test: degradation writes ledger entry.
- [ ] **W3.F.2.b** — Implement.
- [ ] **W3.F.2.c** — Commit: `feat(runtime): continuous healthcheck loop with degradation logging [W3.F.2]`

## Phase W3.G — Cross-cutting docs (Tim, ~0.5 day)

### W3.G.1 — `docs/CASE_ISOLATION.md`
- [ ] **W3.G.1** — Author. SGLang RadixAttention prefix-cache vs case-data. Audit assertion: case_id in user message, not system prompt. Commit: `docs: CASE_ISOLATION.md [W3.G.1]`

## Week 3 — acceptance gates

| Gate | Verification |
|---|---|
| All three verifier strategies live | `pytest tests/verification/ -v` green |
| TSI tcpdump proves credential isolation | Manual recording in `docs/demo-assets/` |
| Mode lock refuses cross-mode resume | `pytest tests/runtime/test_mode_lock.py` green |
| Pivot + replan distinct, both bounded | `pytest tests/graph/test_pivot_node.py` + `test_replan_budget.py` green |
| `unverifiable_finalize_node` fires at replan iteration 4 | `pytest tests/graph/test_unverifiable_finalize.py` green |
| SqliteSaver WAL + fsync set | `pragma_check.sh` returns ok |
| Kill-9 chaos: 100 cases, 0 loss | `pytest tests/chaos/ -v` green |
| trace_id ↔ ledger cross-link visible in Langfuse UI | Manual UI check |
| `/health` endpoint returns all components | `curl localhost:8080/health \| jq` |

If RED: drop W3.E.6 (chaos test, ship without quantified guarantee) → drop W3.B.2 (TSI demo recording, do later) → drop W3.F.2 (continuous healthcheck loop).

---

