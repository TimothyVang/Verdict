# WEEK 2 (May 9 – May 15): Tool surface + Plan-then-Execute refactor

**Theme:** Wrap all 12 SIFT tools as MCP tools. Refactor LangGraph topology to explicit Plan-then-Execute. Add `planner_critique_node`. Wire per-tool args validators. Split plaso/Hayabusa.
**Critical-path output:** All 12 tools callable through gateway. LangGraph compiles with 9 nodes: `planner` → `planner_critique` → `comprehension_gate` → `executor_fanout` (composes DenyRuleWrapper / ToolExecutor / LedgerEmitter per branch) → `pivot` → `quorum` → `replan` → `unverifiable_finalize` → `finalize`.
**If this week slips:** week 3 verifier work pushes; cut pivot_node + unverifiable_finalize from v1; ship pure replan_max=3 → quietly stuck CONTESTED (v4.4 SHOULD-FIX leaks back in).
**Cumulative team-days:** Tim ~5, Beaver ~5, Haley ~1, KP ~3.

## Phase W2.A — 12 SIFT tool wrappers (Tim + KP, ~3 days each)

For each tool:
- [ ] Failing integration test in `tests/tools/test_<tool>.py` against a fixture.
- [ ] Implement `verdict/tools/<tool>.py` extending `ToolWrapper`.
- [ ] Add to gateway tool registry.
- [ ] Commit: `feat(tools): <tool> wrapper [W2.A.<n>]`

| ID | Tool | Owner | Hours |
|---|---|---|---|
| W2.A.1 | `vol3.pslist` | Tim | 3 |
| W2.A.2 | `vol3.pstree` | Tim | 2 |
| W2.A.3 | `vol3.cmdline` | Tim | 2 |
| W2.A.4 | `vol3.dlllist` | Tim | 2 |
| W2.A.5 | `vol3.malfind` | Tim | 3 |
| W2.A.6 | `vol3.netscan` | Tim | 2 |
| W2.A.7 | `vol3.svcscan` | Tim | 2 |
| W2.A.8 | `vol3.handles` | Tim | 2 |
| W2.A.9 | `vol3.callbacks` | Tim | 2 |
| W2.A.10 | `mmls` | KP | 1 |
| W2.A.11 | `fls` | KP | 1 |
| W2.A.12 | `fsstat` | KP | 1 |
| W2.A.13 | `MFTECmd` | KP | 3 |
| W2.A.14 | `RECmd` | KP | 3 |
| W2.A.15 | `PECmd` (Prefetch) | KP | 2 |
| W2.A.16 | `bulk_extractor` | KP | 2 |
| W2.A.17 | `exiftool` | KP | 1 |
| W2.A.18 | `capa` | KP | 2 |

`vol3.psscan` already in W1.E.1.

## Phase W2.B — Plan-then-Execute LangGraph refactor (Beaver, ~2 days)

### W2.B.1 — Five core nodes
- [ ] **W2.B.1.a** — Failing test `tests/graph/test_topology_compiles.py::test_five_nodes_present`. Assert nodes `planner`, `executor_fanout`, `quorum`, `replan`, `finalize` exist on the compiled graph.
- [ ] **W2.B.1.b** — Implement `verdict/graph/topology.py::build_graph(mode: Mode) -> CompiledGraph` and `verdict/graph/nodes.py` with stubs for all five.
- [ ] **W2.B.1.c** — Commit: `feat(graph): five-node Plan-then-Execute topology [W2.B.1]`

### W2.B.2 — `comprehension_gate` node (v4.3)
- [ ] **W2.B.2.a** — Failing test `tests/graph/test_comprehension_gate.py::test_consensus_advances_executor_work` and `test_mismatch_routes_to_clarify`.
- [ ] **W2.B.2.b** — Implement gate node. Collects `PlanComprehensionEcho`s; validates consensus on `parsed_positive_hypothesis_ids`, `parsed_negative_hypothesis_ids`, `parsed_success_criteria_hash`.
- [ ] **W2.B.2.c** — Commit: `feat(graph): comprehension_gate validates executor consensus [W2.B.2]`

### W2.B.3 — `ComprehensionMismatch` ledger entry on disagreement
- [ ] **W2.B.3.a** — Failing test: ledger contains structured per-executor diff on mismatch.
- [ ] **W2.B.3.b** — Implement event type + payload schema.
- [ ] **W2.B.3.c** — Commit: `feat(ledger): ComprehensionMismatch event with per-executor diff [W2.B.3]`

### W2.B.4 — Reducer pattern for fanout merge + race test
- [ ] **W2.B.4.a** — Failing test `tests/graph/test_fanout_race.py::test_4_executors_merge_deterministically`. 4 executors, randomized 0–500ms sleep each; assert final state contains all 4 outputs in deterministic order.
- [ ] **W2.B.4.b** — Implement `verdict/graph/reducers.py` with `Annotated[..., reducer]` for `executor_results` field.
- [ ] **W2.B.4.c** — Commit: `feat(graph): reducer pattern for parallel-executor merge [W2.B.4]`

### W2.B.5 — Pin LangGraph version
- [ ] **W2.B.5** — Pin in `pyproject.toml`. Commit: `chore(deps): pin langgraph version that passes fanout-race test [W2.B.5]`

## Phase W2.C — `executor_work` split into 3 wrappers (v4.5 fix from architecture review)

### W2.C.1 — `DenyRuleWrapper` (Layer 2 of three-layer immutability)
- [ ] **W2.C.1.a** — Failing test `tests/graph/test_deny_rule_wrapper.py::test_blocks_evidence_writes_in_all_modes`. Test args denied for cloud, airgap, dual.
- [ ] **W2.C.1.b** — Implement `verdict/graph/wrappers/deny_rule.py`. Layer 2 of three-layer defense — fires regardless of model. Owns deny-rule list (Tim).
- [ ] **W2.C.1.c** — Commit: `feat(graph): DenyRuleWrapper Layer 2 immutability [W2.C.1]`

### W2.C.2 — `ToolExecutor` (Beaver owns)
- [ ] **W2.C.2.a** — Failing test for typed dispatch + microsandbox spawn + result parsing into ToolOutput.
- [ ] **W2.C.2.b** — Implement.
- [ ] **W2.C.2.c** — Commit: `feat(graph): ToolExecutor wrapper [W2.C.2]`

### W2.C.3 — `LedgerEmitter` (Tim owns)
- [ ] **W2.C.3.a** — Failing test for write+fsync+verify-readback. Plus chain-integrity assertion.
- [ ] **W2.C.3.b** — Implement `verdict/graph/wrappers/ledger_emitter.py` + `verdict/ledger/writer.py` with the durability discipline.
- [ ] **W2.C.3.c** — Commit: `feat(ledger): LedgerEmitter wrapper with write+fsync+verify-readback [W2.C.3]`

### W2.C.4 — Compose three wrappers + replace executor_work
- [ ] **W2.C.4.a** — Failing test: end-to-end through composed `DenyRuleWrapper → ToolExecutor → LedgerEmitter`.
- [ ] **W2.C.4.b** — Wire composition in `verdict/graph/topology.py`.
- [ ] **W2.C.4.c** — Commit: `feat(graph): compose 3-wrapper executor_work [W2.C.4]`

## Phase W2.D — `planner_critique_node` (Beaver, ~1 day)

### W2.D.1 — CoVe (Chain-of-Verification, Dhuliawala 2023)
- [ ] **W2.D.1.a** — Failing test `tests/planning/test_planner_critique.py::test_failed_questions_route_back_to_planner`. Plus `test_all_pass_advances_to_comprehension_gate`.
- [ ] **W2.D.1.b** — Implement `verdict/planning/planner_critique.py`. Same model drafts CoVe questions ABOUT THE PLAN ITSELF (does plan cover most-likely attacker techniques given evidence type? does it have positive AND negative for each artifact family? are success criteria measurable?). Answers them against case_init evidence summary; failed questions route back to planner with hint.
- [ ] **W2.D.1.c** — Commit: `feat(planning): planner_critique_node CoVe [W2.D.1]`

### W2.D.2 — `PlannerCritiqueVerdict` schema + `critique_verdict` ledger event
- [ ] **W2.D.2.a** — Failing test `tests/planning/test_planner_critique_verdict.py::test_schema_rejects_missing_failed_questions_when_route_back`. Plus `test_ledger_emits_critique_verdict_event_with_route_decision`. Assertions: `PlannerCritiqueVerdict(route="planner", failed_questions=[]).model_validate()` raises `ValidationError`; `ledger.last_entry.event_type == "critique_verdict"` after `planner_critique_node` runs.
- [ ] **W2.D.2.b** — Wire into LangGraph + ledger.
- [ ] **W2.D.2.c** — Commit: `feat(graph): planner_critique_node wired between planner + comprehension_gate [W2.D.2]`

### W2.D.3 — Planner CoT capture
- [ ] **W2.D.3.a** — Failing test `tests/planning/test_cot_capture.py::test_gzipped_cot_in_ledger`. Plus `test_8kb_attached_to_langfuse_span`.
- [ ] **W2.D.3.b** — Implement extraction (Claude Agent SDK responses for cloud, Qwen3-Thinking `<think>` blocks for airgap), gzip, hash via `planner_cot_gzip_hash`, store via LedgerEmitter, attach first 8KB to Langfuse span attribute.
- [ ] **W2.D.3.c** — Commit: `feat(observability): planner CoT capture (gzipped ledger + 8KB Langfuse) [W2.D.3]`

## Phase W2.E — Per-tool args validators (Beaver + Tim, ~1.5 days)

### W2.E.1 — `args_validators` framework
- [ ] **W2.E.1.a** — Failing test `tests/tools/test_args_validator.py::test_unknown_flag_raises_modelretry`. Plus `test_invalid_pid_type_raises`.
- [ ] **W2.E.1.b** — Implement `verdict/tools/args_validators.py` with Pydantic-AI `args_validator` framework. `tool_arg_retry_max=2`, then UNVERIFIABLE.
- [ ] **W2.E.1.c** — Commit: `feat(tools): args_validator framework with retry budget 2 [W2.E.1]`

### W2.E.2 — `vol3` validators (parse `vol3 --help` once at startup; allow-list of 26 plugins)
- [ ] **W2.E.2.a** — Failing test: reject `vol3 --foo` and `vol3 windows.invalid_plugin`.
- [ ] **W2.E.2.b** — Implement parse-help-at-startup + hash-pinned allow-list.
- [ ] **W2.E.2.c** — Commit: `feat(tools): vol3 args_validator with hash-pinned plugin allow-list [W2.E.2]`

### W2.E.3 — `plaso` filter pre-validator
- [ ] **W2.E.3.a** — Failing test: malformed filter expression caught before main run.
- [ ] **W2.E.3.b** — Implement: spawn ephemeral sandbox with `psteal --validate-filter` first.
- [ ] **W2.E.3.c** — Commit: `feat(tools): plaso filter pre-validator via psteal [W2.E.3]`

### W2.E.4 — `Hayabusa` flag-matrix validator
- [ ] **W2.E.4.a** — Failing test: invalid timeline-flag combinations rejected.
- [ ] **W2.E.4.b** — Implement against the matrix in `verdict/playbooks/memory.yml` rules section.
- [ ] **W2.E.4.c** — Commit: `feat(tools): hayabusa flag-matrix validator [W2.E.4]`

### W2.E.5 — Sanitization scanner for prompt injection in tool stdout
- [ ] **W2.E.5.a** — Failing test `tests/tools/test_sanitization.py::test_detects_ignore_previous_instructions`. Plus standard jailbreak suffixes.
- [ ] **W2.E.5.b** — Implement `verdict/tools/sanitization.py`. Patterns include `IGNORE PREVIOUS`, `SYSTEM:`, `</tool_call>`, `[INST]`, `### Instruction`. Detected → `ToolOutput.sanitization_flags` populated; surface to planner.
- [ ] **W2.E.5.c** — Commit: `feat(tools): sanitization scanner for prompt-injection patterns [W2.E.5]`

## Phase W2.F — Plaso/Hayabusa split (Beaver, ~0.5 day)

### W2.F.1 — `hayabusa_csv_timeline` (extract phase)
- [ ] **W2.F.1.a** — Failing test for csv-timeline extraction.
- [ ] **W2.F.1.b** — Implement.
- [ ] **W2.F.1.c** — Commit: `feat(tools): hayabusa_csv_timeline extract phase [W2.F.1]`

### W2.F.2 — `hayabusa_filter` (filter phase)
- [ ] **W2.F.2.a** — Failing test for sigma_level + time_range filtering.
- [ ] **W2.F.2.b** — Implement.
- [ ] **W2.F.2.c** — Commit: `feat(tools): hayabusa_filter [W2.F.2]`

### W2.F.3 — `plaso_extract`
- [ ] **W2.F.3.a** — Failing test for `.plaso` storage path return.
- [ ] **W2.F.3.b** — Implement.
- [ ] **W2.F.3.c** — Commit: `feat(tools): plaso_extract phase [W2.F.3]`

### W2.F.4 — `psort_filter`
- [ ] **W2.F.4.a** — Failing test for time_range + filter_expr.
- [ ] **W2.F.4.b** — Implement.
- [ ] **W2.F.4.c** — Commit: `feat(tools): psort_filter phase [W2.F.4]`

## Phase W2.G — Observability instrumentation (Tim + Haley, ~1 day)

### W2.G.1 — Ledger writer hardened
- [ ] **W2.G.1.a** — Failing test `tests/ledger/test_writer.py::test_write_fsync_verify_readback`. Plus `test_invalid_hmac_refuses_load`.
- [ ] **W2.G.1.b** — Implement.
- [ ] **W2.G.1.c** — Commit: `feat(ledger): writer hardened with verify-readback [W2.G.1]`

### W2.G.2 — OpenLLMetry instrumentation across FastMCP + tool wrappers (Tim)
- [ ] **W2.G.2.a** — Failing test `tests/observability/test_otel_setup.py::test_one_span_per_tool_call`. Plus `test_streaming_chunks_aggregated_to_one_span`.
- [ ] **W2.G.2.b** — Configure `traceloop_telemetry.sdk.streaming_aggregation=True`; wire callbacks; verify.
- [ ] **W2.G.2.c** — Commit: `feat(observability): OpenLLMetry instrumentation [W2.G.2]`

### W2.G.3 — SGLang client uses OpenAI-compat path (Haley)
- [ ] **W2.G.3.a** — Failing integration test asserts `prompt_tokens > 0` on a known SGLang call. Plus assertion that wrapper uses `openai.OpenAI(base_url=sglang_url)` not raw `httpx`.
- [ ] **W2.G.3.b** — Implement / verify.
- [ ] **W2.G.3.c** — Commit: `feat(inference): SGLang via OpenAI-compat client for OTel [W2.G.3]`

## Week 2 — acceptance gates

| Gate | Verification |
|---|---|
| All 19 tool wrappers callable via gateway | `pytest tests/tools/ -v` green |
| LangGraph compiles in all three modes | `pytest tests/graph/test_topology_compiles.py` green for cloud/airgap/dual |
| `comprehension_gate` + `planner_critique_node` integrated | Inspect AI smoke run shows both nodes in trace |
| `executor_work` is composition of 3 wrappers, three owners | `git blame` shows distinct authors on `deny_rule.py`, `tool_executor.py`, `ledger_emitter.py` |
| Plaso + Hayabusa split into extract+filter | `grep -c "extract" verdict/tools/plaso_*.py` returns ≥1 each |
| Args validators reject unknown flags | `pytest tests/tools/test_args_validator.py` green |
| Sanitization flags detected on injection patterns | `pytest tests/tools/test_sanitization.py` green |
| Langfuse spans show real prompt_tokens > 0 | Manual UI check + integration test |
| Fanout race test passes on pinned LangGraph version | `pytest tests/graph/test_fanout_race.py -v` green 100/100 runs |

If RED: drop W2.D.3 (planner CoT capture, push to W3) → drop W2.E.3-4 (plaso/Hayabusa validators, push to W3) → drop W2.F (split, ship as combined tools) → drop W2.D.1-2 (planner_critique, accept the wrong-plan failure mode for v1).

---

