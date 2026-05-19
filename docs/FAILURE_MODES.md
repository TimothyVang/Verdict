# VERDICT — Failure Modes

> **Wiki:** [Index](README.md) · [Architecture](ARCHITECTURE.md) · [Build Plan](BUILD_PLAN.md) · [Case Isolation](CASE_ISOLATION.md) · root [CLAUDE.md](../CLAUDE.md)

**Status:** Current. Runtime failure semantics for sandbox, tool, branch, verifier, and observability failures.
**Authority:** Below `ARCHITECTURE.md`; implements its §1, §2, §5, and §6 failure contracts.

---

## Principles

- Evidence integrity failures halt the case.
- Tool, sandbox, verifier, and network failures produce explicit ledger events and route to `CONTESTED` or `UNVERIFIABLE`; they never silently become negative findings.
- Empty `parsed_artifacts` from any quorum participant is disagreement, not a null vote.
- Nodes that call `interrupt()` after writing ledger entries must be idempotent.

## Runtime Matrix

| Component | Failure | Detection | Recovery | Ledger event | Terminal behavior |
|---|---|---|---|---|---|
| Evidence vault | SHA-256 mismatch against `EvidenceManifest` | Periodic re-hash every 10 super-steps | None; stop immediately | `evidence_hash_recheck` with mismatch detail | Raise `HashMismatchError`; halt case |
| Mode lock | Current `detect_mode()` differs from `mode_at_case_init` on resume | `verdict resume` pre-flight | Operator runs `verdict reverify <case_id> --mode <detected>` | `mode_lock` | Exit 2 with documented `ModeLockedError` stderr |
| Tool args | Invalid tool name, flag, PID, filter, or timeline option | `ArgsValidator` (Pydantic v2) before sandbox spawn | `ModelRetry`, max 2 | `tool_call` with validation error | After retry exhaustion, `Finding(status=UNVERIFIABLE, failure_reason="tool_args_failed_validation_after_2_retries")` |
| Microsandbox spawn | libkrun/KVM unavailable, image missing, host disk full, resource exhaustion | Exception or spawn timeout | No retry for kernel/resource failures | `sandbox_failure` with `error_detail` | `UNVERIFIABLE`, `failure_reason="sandbox_spawn_failed"` |
| Tool execution | Tool exits nonzero with stderr | Process exit status | One retry only if wrapper marks failure transient | `tool_call` with `is_error=true` | Retry exhaustion produces `UNVERIFIABLE`, `failure_reason="tool_execution_failed"` |
| Branch timeout | One executor branch hangs | Branch wall-clock reaches `branch_timeout=900s` | Reducer proceeds with timeout output | `sandbox_failure` or `tool_call` with timeout detail | Timed-out branch emits `ToolOutput(status=TIMEOUT, parsed_artifacts=[])`; quorum treats as disagreement |
| TSI proxy | Proxy origin unavailable or credential injection fails | `NetworkProxyError`, connection refused, DNS fail | Counts against `tool_arg_retry_max=2` only for TSI-enabled tools | `tool_call` with `error_detail` | Retry exhaustion produces `UNVERIFIABLE`, `failure_reason="tsi_proxy_unreachable"` |
| Verifier disagreement | Engines disagree on artifact set or MITRE technique | Quorum dispatch table | Route to `replan_node`, max 3 | `finding` with `status=CONTESTED` or `exhausted_replan` | Iteration 4 routes to `unverifiable_finalize_node` |
| Langfuse unavailable | Health check or span write fails | Exception / non-200 health | Fail open for investigation; write local ledger anyway | `tool_call` payload notes `langfuse_write_failed=true` | Case continues; local ledger written; Langfuse traces unavailable until service restored |
| Ledger write | Write, fsync, or verify-readback fails | `LedgerEmitter` post-write readback | None; preserving chain integrity wins | Best-effort stderr only if write failed before event persisted | Halt case; operator must repair filesystem or start a new case |

## Fanout Reducer Rule

`executor_fanout` completes when all four branches return or when `branch_timeout=900s` elapses, whichever happens first. Branches that have not returned by timeout emit `ToolOutput(status=TIMEOUT, parsed_artifacts=[])`. The reducer appends all completed and timeout outputs to state and never blocks past `branch_timeout`.

## UNVERIFIABLE Schema Exemption

`Finding.artifact_paths` and `Finding.artifact_classes` currently enforce `min_length=2` for **all** findings, including those with `status == UNVERIFIABLE`. The `Finding` schema does not yet have a `failure_reason` field or a `_unverifiable_relaxes_corroboration` validator.

**Planned:** add `failure_reason: str | None` to `Finding` with a validator that relaxes the `min_length=2` constraint when `status == UNVERIFIABLE` and `failure_reason` is one of:

- `tool_args_failed_validation_after_2_retries`
- `sandbox_spawn_failed`
- `tool_execution_failed`
- `tsi_proxy_unreachable`
- `branch_timeout`

Until that field is implemented, UNVERIFIABLE findings from tool or sandbox failures must cite whatever artifact paths were collected before the failure, and case-level terminal failures should use `CaseConclusion(status="UNVERIFIABLE")` instead.
