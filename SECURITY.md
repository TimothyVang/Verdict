# Security policy

## Reporting a vulnerability

Please **do not** open a public issue. Email **aihackathon@sans.org** with subject `VERDICT: <one-line summary>`, or DM the maintainer in the SANS AI Hackathon Slack (https://join.slack.com/t/sansaihackathon/shared_invite/zt-3srjz86zo-bwHi_v1aKTg2IJAU4_4OwA).

Include:

- Affected version / commit SHA
- Repro steps (minimal evidence + commands)
- Threat surface (see `docs/spec/02-audit-v4.4.md` — insider, prompt-injection-from-evidence, malicious-tool-output, external-attacker)
- Suggested mitigation if you have one

## Scope

VERDICT is a forensic agent that touches **evidence** — disk images, memory captures, packet captures, registry hives, event logs. Even though all tool execution happens inside read-only microsandboxes (`CLAUDE.md` §4), evidence integrity is the highest-value asset; we treat **any** path that lets a writer reach `/evidence/` as critical.

In scope:

- Bypass of the three-layer immutability defense (PreToolUse hook, `DenyRuleWrapper`, microsandbox read-only mount)
- Prompt injection from evidence content that drives the planner or executor to malicious behaviour
- Credential leakage into a microVM (`CLAUDE.md` §3.9 — credentials must never enter)
- HMAC ledger forgery / chain-of-custody breakage
- Mode-lock bypass on resume
- Any path that allows write to a host evidence file

Out of scope:

- DoS against your own SGLang or Langfuse instance
- Vulnerabilities in upstream dependencies (report to the upstream)
- Issues that require physical access to the host

## What we will do

- Acknowledge within 5 business days
- Coordinate on a fix and a disclosure timeline
- Credit you in the release notes (or stay anonymous, your choice)

## Hard rules already enforced

See `CLAUDE.md` §3 for the load-bearing rules built into the codebase. If a reported issue is a violation of one of those rules, it gets prioritized accordingly.

## Known security issues

Issues discovered by internal review and disclosed here so contributors and judges can see what is in flight. All open items are tracked in `docs/BUILD_PLAN.md` and addressed before submission.

### VERDICT-2026-001 — Layer-2 deny rule bypassable by `..`-traversal and `//`-prefix

* **Severity:** High
* **Affected:** `src/verdict/graph/wrappers/deny_rule.py:41-43` (`_deny_evidence_output`)
* **Discovered:** 2026-05-02 (internal security review of `feat/W2.C.4-compose-executor-work`)
* **Status:** Open — fix tracked under W2.C.1.b (deny-rule normalization hardening)
* **Scope mapping:** "Bypass of the three-layer immutability defense" (in-scope §)

`_deny_evidence_output` checks `path == "/evidence" or path.startswith("/evidence/")` using a plain string prefix match without normalising `..` segments or collapsing leading `//`. Inputs like `/work/../evidence/out.txt`, `/tmp/../evidence/out.txt`, and `//evidence/out.txt` slip past Layer 2 even though the kernel resolves them to `/evidence/out.txt` at syscall time. Layer 3 (read-only mount + `noexec` + host `chattr +i`) is the actual write blocker in correctly-configured deployments, but `CLAUDE.md` §3.1 designates Layer 2 as the architectural guarantee that fires in all three modes — defense-in-depth must hold even if Layer 3 is degraded.

**Remediation:** replace the plain `startswith` check with `os.path.normpath` (lexical `..` collapse) plus an explicit double-slash strip, then compare via `pathlib.PurePosixPath` parents rather than string prefix. Add RED tests for `..` traversal, `//`-prefix, NUL injection, and symlink-style siblings of `/evidence`.

### VERDICT-2026-002 — TPM HMAC silently truncates ledger message to 1024 bytes

* **Severity:** High
* **Affected:** `src/verdict/ledger/hmac_key.py:9-11` (TPM guard in `load_or_create_hmac_key`)
* **Discovered:** 2026-05-02 (internal security review of `feat/W2.C.4-compose-executor-work`)
* **Status:** Open — fix tracked under W2.C.3.b (TPM HMAC sequencing); `_TPMHMACProvider` not yet implemented
* **Scope mapping:** "HMAC ledger forgery / chain-of-custody breakage" (in-scope §)

`_TPMHMACProvider` was not implemented in the current codebase. The TPM path in `load_or_create_hmac_key` raises `RuntimeError("TPM-backed HMAC key path is not implemented on this host yet")`, so the specific truncation vulnerability described in the original report does not currently exist. However, when TPM HMAC IS implemented, the same risk applies: signing code must not truncate the ledger entry message silently. `LedgerWriter._compute_payload_hash` appends `prev_entry_hash` and `entry_id` **after** the JSON payload — any TPM `TPM2B_MAX_BUFFER` truncation that falls short of those fields leaves chain-linkage bytes unauthenticated. Software (`hmac.HMAC`) and gpg-derived paths are unaffected.

**Remediation:** when implementing `_TPMHMACProvider`, raise an explicit `HMACMessageTooLargeError` for inputs > `TPM2B_MAX_BUFFER` until sequenced-HMAC is implemented; then implement `TPM2_HMAC_Start` / `SequenceUpdate` / `SequenceComplete` chunking. Mirror in `verify`. Add a unit test (the §3.10 single-system-boundary mock exception applies at the `tpm2_pytss` boundary) that signs a ≥ 4 KB message and asserts that two messages differing only in bytes after position 1024 produce different signatures.
