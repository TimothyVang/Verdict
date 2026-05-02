# VERDICT CLI Reference (v1)

**Document type:** Command-line interface documentation for VERDICT DFIR agent.
**Authority:** Per BUILD_PLAN.md Phase W1.G.3.
**Scope:** v1 CLI surface. Commands marked (v2 roadmap) are documented but not implemented.

---

## Overview

VERDICT exposes a single-command CLI: verdict. Each subcommand corresponds to a case lifecycle stage (init, resume, reverify), query (status, ls, show), or operational task (validate, export, gc, health, doctor).

All commands output structured data: JSON for machine consumption, human-readable tables where appropriate. Exit codes follow standard POSIX conventions: 0 = success, 1 = general error, 2 = mode-lock error, 3 = unrecoverable case error.

---

## Command reference

### verdict init

**Usage:** `verdict init <evidence_path> [--mode {cloud,airgap,dual}] [--case-id <id>]`

**Description:** Initialize a new case from an evidence file or directory.

**Arguments:**
- evidence_path (required): Path to disk image (.E01, .raw, .img), memory dump (.mem), or triage zip.
- --mode (optional): Inference mode. Default: auto-detect.
  - cloud: Claude Code planner + local Qwen3 executor + CloudSelfConsistency verifier.
  - airgap: Qwen3 planner + executor + AirGapCrossEngine verifier (no cloud).
  - dual: Parallel cloud + airgap lanes + DualLaneCrossEngine verifier.
- --case-id (optional): Human-readable case identifier. Default: UUID-4.

**Exit codes:** 0 = success, 1 = evidence not found, 2 = mode-lock failure.

**Example:**
```
verdict init /evidence/case_2026_0501.E01 --mode dual
```

---

### verdict resume

**Usage:** `verdict resume <case_id>`

**Description:** Resume an incomplete case from the last checkpoint.

**Arguments:** case_id (required): Case ID from verdict init.

**Exit codes:** 0 = success, 1 = case not found, 2 = mode-lock mismatch, 3 = ledger unrecoverable.

**Example:**
```
verdict resume 4f5a8c2e-1d9b-40e2-9d1c-7a2b6f4e5c1a
```

---

### verdict reverify

**Usage:** `verdict reverify <case_id> --mode {cloud,airgap,dual}`

**Description:** Create a parallel verdict chain by re-verifying all findings under a different mode.

**Arguments:**
- case_id (required): Case ID to re-verify.
- --mode (required): Target mode. Must differ from the original.

**Exit codes:** 0 = reverify launched, 1 = case not found, 2 = mode identical.

**Example:**
```
verdict reverify 4f5a8c2e-1d9b-40e2-9d1c-7a2b6f4e5c1a --mode cloud
```

---

### verdict status

**Usage:** `verdict status [--case <id>]`

**Description:** Show status of all active cases or a single case.

**Arguments:** --case (optional): Single case ID. If omitted, list all.

**Exit codes:** 0 = success, 1 = case not found.

**Example:**
```
verdict status
verdict status --case 4f5a8c2e-1d9b-40e2-9d1c-7a2b6f4e5c1a
```

---

### verdict ls

**Usage:** `verdict ls [--limit <n>] [--format {json,table}]`

**Description:** List all cases, ordered by creation date (newest first).

**Arguments:**
- --limit (optional): Max cases to display. Default: 50.
- --format (optional): Output format. Default: table.

**Exit codes:** 0 = success.

**Example:**
```
verdict ls --limit 20 --format json
```

---

### verdict show

**Usage:** `verdict show <case_id> [--include {findings,ledger,summary}] [--format {json,text,html}]`

**Description:** Display detailed information about a single case.

**Arguments:**
- case_id (required): Case ID.
- --include (optional): What to display. Default: summary.
  - summary: case metadata and verdict statistics.
  - findings: all findings with status and rationale.
  - ledger: full JSONL ledger.
- --format (optional): Output format. Default: json.

**Exit codes:** 0 = success, 1 = case not found.

**Example:**
```
verdict show 4f5a8c2e-1d9b-40e2-9d1c-7a2b6f4e5c1a --include findings
```

---

### verdict export

**Usage:** `verdict export <case_id> [--format {json,csv,sigtools_triage,html}] [--output <file>]`

**Description:** Export case findings in a standard format.

**Arguments:**
- case_id (required): Case ID.
- --format (optional): Output format. Default: json.
  - json: Full case JSON.
  - csv: CSV table for Excel.
  - sigtools_triage: SigTools Triage XML import format.
  - html: HTML report (v2 roadmap).
- --output (optional): Write to file instead of stdout.

**Exit codes:** 0 = success, 1 = case not found or format not supported.

**Example:**
```
verdict export 4f5a8c2e-1d9b-40e2-9d1c-7a2b6f4e5c1a --format csv --output findings.csv
```

---

### verdict validate

**Usage:** `verdict validate <case_id>`

**Description:** Verify ledger integrity by walking the hash chain and validating HMAC signatures.

**Arguments:** case_id (required): Case ID.

**Exit codes:** 0 = all valid, 1 = entries invalid; hash chain broken, 3 = ledger unrecoverable.

**Example:**
```
verdict validate 4f5a8c2e-1d9b-40e2-9d1c-7a2b6f4e5c1a
```

---

### verdict approve

**Usage:** `verdict approve <finding_id> [--message <msg>]`

**Description:** Manually approve a finding. Appends a signed approval entry to the ledger.

**Arguments:**
- finding_id (required): Finding ID from the case ledger.
- --message (optional): Approver notes.

**Exit codes:** 0 = approval recorded, 1 = finding not found.

**Example:**
```
verdict approve finding_001 --message "Verified with string search in full memory dump"
```

---

### verdict mode

**Usage:** `verdict mode [--detect] [--case <id>]`

**Description:** Display the current inference mode or the locked mode of a case.

**Arguments:**
- --detect (optional): Re-run mode auto-detection.
- --case (optional): Show locked mode of a specific case.

**Exit codes:** 0 = success, 1 = mode detection failed.

**Example:**
```
verdict mode --detect
verdict mode --case 4f5a8c2e-1d9b-40e2-9d1c-7a2b6f4e5c1a
```

---

### verdict gc

**Usage:** `verdict gc [--older-than <days>] [--dry-run]`

**Description:** Garbage-collect old, completed cases to free disk space.

**Arguments:**
- --older-than (optional): Only delete cases completed >N days ago. Default: 90 days.
- --dry-run (optional): Show what would be deleted without deleting.

**Exit codes:** 0 = GC completed, 1 = GC failed.

**Example:**
```
verdict gc --older-than 90 --dry-run
verdict gc --older-than 90
```

---

### verdict health

**Usage:** `verdict health`

**Description:** Show health status of VERDICT and all backend services.

**Exit codes:** 0 = all healthy, 1 = one or more services down or degraded.

**Example:**
```
verdict health
```

---

### verdict doctor

**Usage:** `verdict doctor`

**Description:** Comprehensive pre-flight check for all VERDICT infrastructure (APIs, SGLang, microsandbox, Langfuse, HMAC key).

**Exit codes:** 0 = all checks passed, 1 = critical checks failed, 2 = non-critical checks failed.

**Example:**
```
verdict doctor
```

---

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error (case not found, invalid argument, service unreachable) |
| 2 | Mode-lock error (attempted operation under different mode) |
| 3 | Unrecoverable case error (ledger corrupt, checkpoint lost) |

---

## Environment variables

| Variable | Purpose |
|----------|---------|
| ANTHROPIC_API_KEY | Anthropic API credentials (cloud mode) |
| SGLANG_BASE_URL | SGLang server URL (air-gap mode) |
| VERDICT_CASE_DIR | Override default case directory (default: ~/.verdict/cases) |
| VERDICT_LEDGER_KEY_PATH | Override default ledger key path (default: ~/.verdict/key.gpg) |

---

## Document history

| Version | Date | Notes |
|---------|------|-------|
| 1.0 | 2026-05-02 | Initial CLI reference per BUILD_PLAN.md W1.G.3. Full command surface enumeration. |
