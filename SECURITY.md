# Security policy

## Reporting a vulnerability

Please **do not** open a public issue. Email **aihackathon@sans.org** with subject `VERDICT: <one-line summary>`, or DM the maintainer in the SANS AI Hackathon Slack (https://join.slack.com/t/sansaihackathon/shared_invite/zt-3srjz86zo-bwHi_v1aKTg2IJAU4_4OwA).

Include:

- Affected version / commit SHA
- Repro steps (minimal evidence + commands)
- Threat surface (see `docs/spec/VERDICT_AUDIT_v4.4.md` — insider, prompt-injection-from-evidence, malicious-tool-output, external-attacker)
- Suggested mitigation if you have one

## Scope

VERDICT is a forensic agent that touches **evidence** — disk images, memory captures, packet captures, registry hives, event logs. Even though all tool execution happens inside read-only microsandboxes (`CLAUDE.md` §4.2), evidence integrity is the highest-value asset; we treat **any** path that lets a writer reach `/evidence/` as critical.

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
