# VERDICT Failure Modes (v1)

**Document type:** Operational failure analysis for VERDICT DFIR agent.
**Authority:** Per BUILD_PLAN.md Phase W1.G.2.
**Scope:** Failure detection and recovery strategies for production deployment.

---

## Executive summary

VERDICT is a distributed multi-component system with fallbacks designed for forensic chain-of-custody. This document catalogs six failure modes for v1:

1. Microsandbox spawn timeout (30s limit + 1 retry)
2. SGLang server crash (graceful fallback to cloud or replan)
3. Langfuse backend fail-open (traces dropped, case continues)
4. Partial ledger write (recovery via checkpoint and re-hash)
5. Claude API rate-limit (exponential backoff + replan with local inference)
6. OpenCTI service unreachable (graceful degradation, no enrichment)

---

## Failure modes table

| Component | Failure Mode | Detection | Recovery | Escalation |
|-----------|-------------|-----------|----------|------------|
| Microsandbox | Spawn timeout (>30s) | RuntimeError timeout | Retry once. On 2nd timeout: mark failed, pivot | If pivot_max exhausted, interrupt |
| Microsandbox | Network egress | stderr ECONNREFUSED | Log flag, mark failed | Escalate like timeout |
| SGLang (planner) | Crash or OOM | HTTP 503 | Fallback to cloud (DUAL) or exponential backoff | Interrupt if backoff exhausted |
| SGLang (executor) | Crash or OOM | HTTP 503 | Fallback to cloud (DUAL) or pivot | Escalate on pivot_max |
| Langfuse | Connection refused | HTTP 502/504 | Fail-open, continue, retry background | Log warning, operator check |
| Ledger writer | Partial write (kill -9) | Hash-chain mismatch on resume | Checkpoint + WAL recovery | If checkpoint corrupt, unrecoverable |
| Claude API | Rate limit 429 | HTTP 429 | Exponential backoff, switch to local Qwen3 | Check quota, tier upgrade |
| Claude API | Auth failure 401 | HTTP 401 | Log, abort, no retry | Update ANTHROPIC_API_KEY |
| OpenCTI | Service unreachable | HTTP 502/503/504 | Graceful degradation, skip enrichment | Case continues |
| Planner | Underspecified plan | Validator rejects | Replan with focused prompt | After replan_max, escalate |

---

## Recovery strategies by component

### Microsandbox spawn timeout

Symptom: Tool call hangs >30s waiting for microVM boot.

Detection: Explicit timeout check: `time_elapsed > 30s`.

Recovery:
- Retry spawn once (30s limit). If successful, continue.
- If 2nd timeout: mark tool failed. ToolExecutor returns failed ToolOutput.
- LangGraph continues to pivot: next tool or hypothesis.

Escalation:
- If pivot_max (15) exhausted: replan.
- If replan_max (3) exhausted: unverifiable_finalize. Finding.status = UNVERIFIABLE. interrupt().

Ledger entry: LedgerEntry(event_type='tool_call', status='TIMEOUT', recovery_action='marked_failed_pivot_to_next_tool')

---

### SGLang server crash

Symptom: HTTP 503 Service Unavailable on planner or executor POST.

Detection: HTTPError(status_code=503).

Recovery (planner):
- DUAL or fallback: switch to cloud planner.
- AIRGAP: exponential backoff (1s, 2s, 4s, 8s, max 3). After exhaustion: interrupt.

Recovery (executor):
- DUAL: switch to cloud executor.
- AIRGAP: pivot to next tool after backoff exhaustion.

Escalation: If recovery fails and replan_max=3 exhausted, escalate to UNVERIFIABLE.

---

### Langfuse fail-open

Symptom: POST to Langfuse /api/events fails (502, 503, TCP timeout).

Detection: HTTPError or timeout in OpenLLMetry exporter.

Recovery: Fail-open.
- Log warning to stderr.
- Continue case. Do NOT block on tracing.
- Background thread retries with exponential backoff.

Escalation: None. Case continues. Operator receives warning.

---

### Partial ledger write recovery

Symptom: Process killed during ledger.write() + fsync(). Truncation detected on resume.

Detection:
- SHA-256 hash-chain validation fails.
- JSONDecodeError on partial line at EOF.

Recovery:
- SqliteSaver checkpoint consulted: last valid checkpoint read.
- Ledger truncated at last valid entry.
- verdict resume skips truncated entries, resumes from checkpoint.
- All prior findings retained.

Escalation: If checkpoint corrupt, case unrecoverable. Human reviews backup at ledger.jsonl.bak.

---

### Claude API rate-limit (429)

Symptom: HTTP 429 Too Many Requests from Anthropic API.

Detection: anthropic.RateLimitError or HTTP 429.

Recovery:
- Exponential backoff: 1s, 2s, 4s, 8s, 16s, 32s (max 5 retries).
- Respects Retry-After header.
- After 5 retries: switch to local Qwen3 if available.
  - DUAL: use local for re-plan.
  - CLOUD-only: interrupt.

Escalation: Human reviews quota on Anthropic console. Consider tier upgrade or limit increase.

---

### OpenCTI enrichment failure

Symptom: HTTP 502/503/504 from OpenCTI /graphql or TCP timeout.

Detection: HTTPError or socket.timeout.

Recovery: Graceful degradation.
- Log warning.
- Continue case without CTI context.
- CTI is best-effort for v1; not a blocker.

Escalation: Operator checks OpenCTI health. Case continues; human enriches later.

---

## Failure handling in CI/testing

By end of W1, pytest tests/chaos/test_kill_9_resume.py MUST pass 100/100 with zero data loss:
- Spin up case (planner + first tool).
- Send SIGKILL mid-checkpoint write.
- Call verdict resume immediately.
- Assert all prior findings and ledger entries intact and re-hash succeeds.

This demonstrates WAL + checkpoint recovery correctness.

---

## Document history

| Version | Date | Notes |
|---------|------|-------|
| 1.0 | 2026-05-02 | Initial draft per BUILD_PLAN.md W1.G.2. Six failure modes with detection, recovery, escalation. |
