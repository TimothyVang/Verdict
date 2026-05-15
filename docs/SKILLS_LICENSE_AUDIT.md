# Skills License Audit

> **Wiki:** [Index](README.md) · [TL;DR](TLDR.md) · [Architecture](ARCHITECTURE.md) · [Build Plan](BUILD_PLAN.md) · [Skills Framework](SKILLS_FRAMEWORK.md) · [MCP Framework](MCP_FRAMEWORK.md) · root [CLAUDE.md](../CLAUDE.md)

Per CLAUDE.md §3.8, every vendored skill, hook, MCP, or external artifact requires an MIT or Apache-2.0 license. This file is the audit log.

**Date:** 2026-05-02 (Week 1, Day 1).
**Auditor:** Claude (auto, on `Verdict` session). Verified by reading each upstream `LICENSE` file and pinning the source commit hash.

## Audit table

| Pack / artifact | Origin | Source commit / release | License | License-compatible with Verdict (MIT)? | Status |
|---|---|---|---|---|---|
| Superpowers | [obra/superpowers](https://github.com/obra/superpowers) | `e7a2d16` (2026-04-27) | **MIT** © Jesse Vincent | ✅ | **Vendored** — 14 skills under `.claude/skills/` |
| mattpocock skills | [mattpocock/skills](https://github.com/mattpocock/skills) | `b843cb5` (2026-04-30) | **MIT** © Matt Pocock | ✅ | **Vendored** — `grill-me/`, `grill-with-docs/` |
| qc (custom) | Verdict — no upstream | n/a | **MIT** (Verdict) | ✅ | **Custom** — Verdict-specific quick-commit + docs-sweep slash command; `.claude/skills/qc/` |
| tdd-guard | [nizos/tdd-guard](https://github.com/nizos/tdd-guard) | `2c82daa` (2026-05-02, v1.6.7) | **MIT** © Nizar Selander | ✅ | **Deferred** — Node tool + hook (separate workstream; not yet integrated, will be wired via `scripts/bootstrap-dev.sh` + `.claude/settings.json`) |
| filesystem MCP | [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) | npm package resolved by `.mcp.cloud.json` / `.mcp.dual.json`; pin exact package version before W6 release | **MIT** | ✅ | **Allowed with safety caveat** — excluded from safe default because upstream exposes write-capable tools; see `MCP_FRAMEWORK.md` §2 |
| fetch MCP | [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | npm package resolved by `.mcp.cloud.json` / `.mcp.dual.json`; pin exact package version before W6 release | **MIT** | ✅ | **Allowed with mode caveat** — cloud/dual configs only; omitted from `.mcp.json` and `.mcp.airgap.json` |
| sequential-thinking MCP | [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | npm package resolved by `.mcp.json`; pin exact package version before W6 release | **MIT** | ✅ | **Allowed** — planner_critique CoVe support |
| GitHub MCP | [github/github-mcp-server](https://github.com/github/github-mcp-server) | package resolved by `.mcp.cloud.json` / `.mcp.dual.json`; pin exact package version before W6 release | **Apache-2.0** | ✅ | **Allowed** — PR review and commit/task audit; token injected via env only |
| MITRE ATT&CK MCP | [stoyky/mitre-attack-mcp](https://github.com/stoyky/mitre-attack-mcp) | uvx package resolved by `.mcp.cloud.json` / `.mcp.dual.json`; pin exact package version before W6 release | **MIT** | ✅ | **Allowed** — technique lookup and sub-technique validation in connected modes |
| Context7 MCP | [upstash/context7](https://github.com/upstash/context7) | `@upstash/context7-mcp@2.2.3` observed 2026-05-02; configured in `.mcp.cloud.json` / `.mcp.dual.json`; pin before W6 release | **MIT** | ✅ | **Allowed** — up-to-date library/API docs; no credentials configured |
| Trail of Bits skills | [trailofbits/skills](https://github.com/trailofbits/skills) | n/a | **CC-BY-SA-4.0** © Trail of Bits | ❌ | **Rejected** — share-alike copyleft incompatible with vendoring into a MIT-distributed repo. Useful as reference reading; never to be vendored. |
| Daytona MCP | (vendor) | n/a | AGPL-3.0 | ❌ | **Forbidden** — CLAUDE.md §3.8 hard-NO. |
| REMnux MCP | (vendor) | n/a | GPL-3.0 | ❌ | **Forbidden** — CLAUDE.md §3.8 hard-NO. Out-of-process call only, never linked, never vendored. |

## Notes

- MIT requires the copyright notice and license text to be preserved alongside the work. We satisfy this via `.claude/skills/THIRD_PARTY_NOTICES.md`, which carries the full text of each upstream LICENSE plus the source-commit pin.
- "Vendored" means we copy the SKILL.md (and supporting files) into `.claude/skills/<name>/` rather than referencing them remotely. This gives us repo-controlled review, deterministic builds, and no run-time fetch dependency. **Do not edit vendored files in place** — pull updates from upstream and re-vendor on a tracked commit.
- "Rejected" means we read it, learned from it, **did not** copy it. Reading copyleft-licensed material does not contaminate; redistributing it does.
- Update this file every time a new skill, hook, or MCP is added, even if the license is the obvious-MIT case. The audit log is the artifact a SANS judge or future contributor will check.
- MCP package versions are not all pinned in `.mcp*.json` yet. That is acceptable for Phase 0 documentation only; W6 release packaging must pin or otherwise record the resolved versions in the submission audit trail.

## Re-audit cadence

Re-verify upstream licenses **before each `re-vendor` PR** (when pulling updates from upstream Superpowers / mattpocock-skills). Maintainers can change license terms; pinning the commit hash protects us against silent re-licensing.
