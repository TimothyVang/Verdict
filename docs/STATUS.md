# VERDICT — Build Status

**Snapshot date:** 2026-05-02 (Saturday, Day 1 of W1).
**Current branch:** `feat/W2.C.4-compose-executor-work` (active accumulator).
**Authority:** This doc tracks *as-built* state. For the plan, see `BUILD_PLAN.md` (index) → `build/week-N.md`. For architecture, see `ARCHITECTURE.md`. This doc has no authority over either; it just records what exists on disk and on which branch.

> Rebuild this doc by walking `git ls-tree -r HEAD --name-only` for the file inventory and `git log --oneline --all` for task ID coverage, then mapping `[W#.#.#]` tags to the BUILD_PLAN index.

---

## What's landed on the current branch

### Schemas — `verdict/schemas/`

| File | Task ID | Notes |
|---|---|---|
| `artifact_class.py` | W1.B.1 | `ArtifactClass` enum (note: count drift — test asserts 13, code has 15; tracked as a pre-existing test failure) |
| `tool_output.py` | W1.B.4 | `Artifact` + `ToolOutput` base; both re-exported from `verdict.__init__` |
| `mode.py` | (W3.C-related) | `Mode` enum (CLOUD / AIRGAP / DUAL) |
| `ledger.py` | (W3-related) | `LedgerEntry` schema fragments |

`verdict/__init__.py` exports `ArtifactClass`, `Artifact`, `ToolOutput`.

### Graph topology + wrappers — `verdict/graph/`

| File | Task ID |
|---|---|
| `topology.py` | W2.B (LangGraph state machine skeleton) |
| `wrappers/deny_rule.py` | W2.C.1 (Layer 2 of three-layer immutability) |
| `wrappers/tool_executor.py` | W2.C.2 |
| `wrappers/ledger_emitter.py` | W2.C.3 (write + fsync + verify-readback) |

W2.C.4 (composition into `executor_work`) is the current branch's most recent commit (`6ea7f9c`).

### Ledger — `verdict/ledger/`

| File | Task ID |
|---|---|
| `writer.py` | W2.C.3 area (write + fsync + verify-readback contract) |
| `hmac_key.py` | TPM-backed / gpg-fallback key handling (W1.G.6 territory; ruff-cleaned in `3721741`) |
| `redaction.py` | W3.B.3 (redact `authorization` / `auth_user` / `api_key` *before* hash + sign) |

### Tools — `verdict/tools/`

| File | Task ID |
|---|---|
| `base.py` | W1.E.2 — `ToolWrapper` base class |
| `vol3/__init__.py` | W1.E.* placeholder (vol3 wrappers proper land in W1.E.1 + W2.A.1–9) |

No vol3 plugin wrappers yet. `vol_psscan` (W1.E.1) is in flight on a separate branch.

### Swarm — `swarm/` (Phase-0 build orchestrator, W0.* + W1.A.0)

Full Phase-0 operator landed:

- `conductor.py` — parses build plan, builds DAG, identifies ready-to-dispatch (now reads `docs/build/` directory)
- `worker.py` — runs a Claude Agent SDK subagent per task (Phase-1+ wires real dispatch)
- `reviewer.py` — runs ruff + pytest + pre-commit gates per branch
- `auditor.py` — scans diff for §3 hard-rule violations (no-mocks, conventional commits, forbidden deps)
- `doctor.py` — preflight: API keys, SGLang, microsandbox, Langfuse, HMAC key
- `state.py` — SQLite (WAL + fsync) — same durability discipline as the runtime ledger
- `runtime/{gh.py, worktree.py}` — git/gh/worktree helpers
- `agents/` — 8 role markdown files: `_prefix.md` + auditor / conductor / eval-engineer / planning-engineer / reviewer / sandbox-engineer / schema-engineer / tool-wrapper-engineer
- `deps.yaml` — cross-phase dependencies + `requires_human` list

`python -m swarm.conductor dry-run` parses 150 tasks across 37 phases, identifies 35 ready-to-dispatch.

### Tests — `tests/`

- `tests/schemas/` — `test_artifact_class.py`, `test_tool_output.py`
- `tests/tools/` — `test_tool_base.py`
- `tests/graph/wrappers/` — `test_deny_rule_wrapper.py`, `test_tool_executor.py`, `test_ledger_emitter.py`, `test_executor_composition.py`
- `tests/swarm/` — `test_agent_definitions.py`, `test_mcp_config.py`, `test_worker_definition.py`

167 of 167 cleanly-collected tests pass. Two known pre-existing failures: `test_worker_definition.py` (collection error — imports `AgentDef` not exported), `test_artifact_class.py::test_enum_has_13_required_members` (asserts 13, code has 15).

### Scripts — `scripts/`

- `bootstrap-dev.sh` — installs uv + Python 3.11 + Node 20 + pnpm + Microsandbox (Linux only) at pinned versions. Idempotent.
- `run-swarm.sh` — autonomous build-swarm launcher (`claude -p` harness with 4-hour budget, 50-task ceiling, 60-turns-per-task cap).

### Docs — `docs/` (restructured 2026-05-02)

This session reshaped the docs for LLM/human ingestion:

- `BUILD_PLAN.md` sliced 1777 → 302 lines (preamble + INDEX); per-week phases moved to `build/week-{1..6}.md` + `build/teammates.md` + `build/appendices.md` (1483 lines total). `swarm/conductor.py:parse_plan` updated to walk the directory.
- `docs/spec/` renamed to `docs/archive/` (matches the README inside it; 6 files moved with `git mv`, 18 references updated across 7 files).
- All stale `services/agent/`, `services/mcp/`, `services/agent_mcp/` paths removed (code never lived there; docs were misleading).
- All Rust-toolchain references removed (FastMCP is Python; no Rust crate exists or is planned).
- LOW (verified-accurate) sections trimmed from `DOCS_ACCURACY_REPORT.md` and `AGENTIC_WORKFLOW_REVIEW.md`.

---

## In flight on the current branch

`feat/W2.C.4-compose-executor-work` is one commit ahead of pushed remote. Recent commits:

```
6ea7f9c  feat(graph): compose 3-wrapper executor_work [W2.C.4]
7c2ffa3  test(graph): compose 3-wrapper executor_work end-to-end RED [W2.C.4]
3721741  fix(graph): ruff clean ledger_emitter + hmac_key + writer [W2.C.3]
6c09ff5  feat(ledger): LedgerEmitter wrapper with write+fsync+verify-readback [W2.C.3]
89d49ee  test(ledger): LedgerEmitter write+fsync+chain-integrity RED [W2.C.3]
```

Working tree has uncommitted edits to ~25 files from this session's docs-restructuring work (services/ cleanup + Rust removal + BUILD_PLAN slice + spec→archive rename + docs/STATUS.md creation).

## Branches with work that hasn't merged into the current branch

`git branch -a` shows ~25 task-ID-named branches. Notable ones not yet integrated here:

- `feat/W1.B.{2,3,4,10,11,12,13}` — schema bundle (CaveatID, EvidenceItem, Hypothesis-related, finding validators, ledger schema, schema versioning, VerdictStatus)
- `feat/W1.A.{1,8,9}` — install script, Inspect AI hello-world, mechanical hard-rule enforcement
- `docs/W1.G.{1,2,3,4}` — THREAT_MODEL, FAILURE_MODES, CLI, SCHEMA_MIGRATION (none of the target docs exist on this branch yet)
- `feat/W2.B.*` — comprehension_gate consensus, fanout reducer, ComprehensionMismatch event, langgraph version pin
- `feat/W3.B.*` — TSI Pattern 2, ledger redaction
- `feat/W3.E.*` — SqliteSaver WAL+FULL, thread_id wiring, verdict resume, kill-9 chaos test, trace_id↔ledger cross-link

These will need integration before they appear here.

---

## What's next (per `BUILD_PLAN.md` INDEX)

The conductor identifies 35 ready-to-dispatch tasks. The first 10 by phase order:

```
W1.A.1  scripts/install.sh with three credential paths
W1.B.1  ArtifactClass enum                   ← landed
W1.C.1  derive_seeds(case_id) helper          (Beaver, blake3 derive_key_context)
W1.D.1  CI smoke-test scaffold (xfail-marked)
W1.E.1  vol_psscan MCP tool wrapper
W1.F.1  Playbook Pydantic schema              (KP)
W1.G.1  docs/THREAT_MODEL.md
W2.B.1  Five core LangGraph nodes             (Beaver)
W2.C.1  DenyRuleWrapper                       ← landed (composed in W2.C.4)
W2.D.1  CoVe / planner_critique_node          (Beaver)
```

Critical path: schemas freeze May 8, tool surface freeze May 15, verifier loop freeze May 22, evals freeze May 29, demo footage May 30, final cut June 14.

---

## Acceptance gates (Week 1, due May 8)

From `docs/build/week-1.md`:

| Gate | Status |
|---|---|
| All 13 (or 15?) `ArtifactClass` members defined | ⚠ test/code drift (13 vs 15) |
| `Finding.artifact_paths` rejects len < 2 | ⛌ no `Finding` schema yet (W1.B.6) |
| `Finding.caveats_acknowledged` enforces 7 Tier-1 rules | ⛌ no `Finding` schema yet |
| `tests/schemas/` all green | ✗ 1 pre-existing failure (`test_enum_has_13_required_members`) |
| `tests/playbooks/` all green | ⛌ no playbook schema yet (W1.F.1) |
| Microsandbox spawns on a sample image | ⛌ provider not implemented (W1.A.6) |
| `verdict doctor` passes | ⛌ CLI not implemented (W5.A.4) |
| Conventional Commits enforced (no `--no-verify`) | ✓ commit history clean (grep audit) |

Most week-1 gates are still red — the foundation work is largely on feature branches not yet integrated to main.

---

## How to refresh this doc

```bash
git ls-tree -r HEAD --name-only | grep -E "^(verdict|swarm|tests|scripts)/"  # files
git log --oneline --all | head -50                                            # task IDs
git log --oneline main | head -30                                             # what's actually on main
python -m swarm.conductor dry-run --show 10                                   # ready-to-dispatch
```

Re-walk those four queries, update the tables above, commit as `docs: refresh STATUS.md`. No magic — this is just a snapshot.
