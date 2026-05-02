# VERDICT Checkpointing — SqliteSaver + WAL + Reducer Pattern

**Status:** Current.  Authority: `docs/ARCHITECTURE.md` §2.  Task: W3.E.4.

---

## 1. Why checkpointing matters for DFIR

An investigation can run for minutes.  A kill-9 (OS restart, power loss,
OOM kill) between graph super-steps would lose every tool output gathered
so far.  VERDICT uses LangGraph's `SqliteSaver` to persist the full
agent state after every super-step, so `verdict resume <case_id>`
re-enters the graph exactly where it was interrupted.

For SANS judges this also means the chain-of-custody ledger and the
LangGraph checkpoint file jointly record an auditable step-by-step trace
of the investigation — even across process restarts.

---

## 2. Durability design

### 2.1 WAL + synchronous=FULL

```
PRAGMA journal_mode=WAL;      -- write-ahead log; readers don't block writers
PRAGMA synchronous=FULL;      -- fsync after every sqlite txn-commit
```

`PRAGMA synchronous=FULL` (integer value 2) ensures that a kill-9
between the SQLite transaction commit and the filesystem fsync does **not**
lose the most recent super-step.  The tradeoff is roughly 2× write
latency vs `synchronous=NORMAL` — acceptable because super-steps are
bounded at 15 pivots × 3 replans and each super-step is already
microsandbox-latency-dominated (≥200 ms cold).

`PRAGMA journal_mode=WAL` keeps readers (e.g. `verdict validate`,
`verdict show`) from blocking the writer (the graph loop).

These pragmas are applied once per `open_checkpointer(db_path)` call
on the same connection that `SqliteSaver` uses, before any checkpoint
write.  See `verdict/graph/checkpoint.py::_apply_pragmas()`.

### 2.2 Single-writer constraint

LangGraph `SqliteSaver` is **synchronous and single-threaded** (it uses
a `threading.Lock` internally).  VERDICT runs one `graph.invoke()` at a
time per case.  Two concurrent resumes of the same case_id are not
supported — the second would see a corrupt partial state.  The CLI
enforces this via the ledger's `mode_lock` event (only one active
`case_init` per case_id at a time).

### 2.3 Per-case SQLite file rotation

Each case gets its own SQLite file at:

```
cases/<case_id>/checkpoint.db
```

This gives us:
- **Isolation:** one case's WAL never blocks another case.
- **Garbage collection:** `verdict gc` deletes old `cases/<id>/`
  directories atomically.
- **Export:** the checkpoint file is a self-contained SQLite database
  that can be shipped alongside `ledger.jsonl` for offline review.

`open_checkpointer(db_path)` creates `db_path.parent` if it does not
exist, so the caller does not need to pre-create the directory.

---

## 3. LangGraph config wiring

**`thread_id = case_id` everywhere** (ARCHITECTURE.md §2).

Every LangGraph call that touches a checkpoint must pass:

```python
config = {"configurable": {"thread_id": case_id}}
```

The helper `make_graph_config(case_id)` in `verdict/graph/checkpoint.py`
produces this dict.  `CaseGateway` (in `verdict/graph/gateway.py`) wraps
every `graph.invoke()` / `graph.stream()` / `graph.get_state()` call and
injects the config automatically so callers cannot accidentally write to
the wrong thread.

---

## 4. Reducer pattern for fanout merge

The 4-branch `executor_fanout` node uses LangGraph's reducer pattern to
merge findings from parallel branches into a single `case.findings` list
without race conditions.

```python
from typing import Annotated
import operator

class CaseState(TypedDict):
    findings: Annotated[list[Finding], operator.add]   # reducer: append
    hypotheses: list[Hypothesis]                        # last-write-wins
    ...
```

The `operator.add` reducer means each executor branch **appends** its
findings to the shared list; LangGraph merges them atomically at the
super-step boundary.  The `quorum_node` then groups findings by
`hypothesis_id` for per-hypothesis verdict computation.

Re-running prior hypotheses on a pivot would double-count findings in the
checkpoint.  `executor_fanout` passes only the **single new hypothesis**
added by `pivot_node` to the branches — prior findings already in the
checkpoint are untouched.  (ARCHITECTURE.md §2 pivot state-merge
contract.)

---

## 5. Resume flow

```
verdict resume <case_id>
  │
  ├── read mode_at_case_init from ledger (first "mode_lock" entry)
  ├── detect_mode() → current environment
  ├── verify_mode_lock(original, detected)
  │     └── ModeLockedError(exit_code=2) if drift
  │
  ├── open_checkpointer(cases/<case_id>/checkpoint.db)
  ├── SqliteSaver.list(config, limit=1) → latest CheckpointTuple
  │
  └── ResumeResult(case_id, snapshot)
        │
        └── caller re-compiles graph + graph.invoke(snapshot.values,
            config=make_graph_config(case_id))
            → continues from last super-step
```

`verdict resume` is a **read + re-enter**, not a replay.  The graph
re-enters at `__start__` using the stored state as initial input — the
exact nodes re-executed depend on `next` in the snapshot, which
LangGraph populates from the interrupt point.

---

## 6. Mode lock on resume

CLAUDE.md §3.4 is absolute: if the environment at resume time differs
from the mode recorded at `case_init`, we **refuse to advance** and
print:

```
Case <id> was initialized in mode=<original>;
current environment is mode=<detected>.
To re-run under the new mode, use: verdict reverify <id> --mode <detected>
```

Exit code 2.  The only valid way to change mode is
`verdict reverify <case_id> --mode <new_mode>`, which creates a
**parallel verdict chain** in `cases/<case_id>-reverify-<new_mode>/`
without mutating the original audit trail.

---

## 7. Relevant files

| File | Role |
|------|------|
| `verdict/graph/checkpoint.py` | `open_checkpointer`, `make_graph_config`, `verify_mode_lock`, `ModeLockedError` |
| `verdict/graph/gateway.py` | `CaseGateway` — wraps every graph call with `thread_id=case_id` |
| `verdict/cli/resume.py` | `resume_case()`, `ResumeResult` — library function called by CLI |
| `tests/graph/test_checkpoint.py` | W3.E.1 — WAL pragmas, resume, mode-lock unit tests |
| `tests/graph/test_thread_id_wiring.py` | W3.E.2 — CaseGateway isolation tests |
| `tests/cli/test_resume.py` | W3.E.3 — CLI resume tests |
| `tests/chaos/test_kill_9_resume.py` | W3.E.6 — kill-9 chaos harness |
