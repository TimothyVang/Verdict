# MCP_FRAMEWORK — Model Context Protocol allowlist + isolation discipline

**Status:** Phase 0 (allowlist landed; credential-isolation hooks deferred to W2). Engineering scaffolding, **not** part of the runtime authority chain. The Verdict runtime topology lives in `ARCHITECTURE.md`.

**Authority:** below `BUILD_PLAN.md` and `CLAUDE.md`. Every MCP server in the allowlist obeys CLAUDE.md §3.8 (MIT/Apache-2.0 only) and §3.9 (credentials never enter a microsandbox). Nothing in this doc supersedes either.

**Date:** 2026-05-02 (Week 1, Day 1).

---

## 1. Why a tight allowlist

The MCP ecosystem in 2026 is large — 9,400+ servers in the public registry, growing fast. Most are:
- Trendy but low-impact for an autonomous DFIR agent.
- Licensed in ways that conflict with our MIT distribution (AGPL, GPL, CC-BY-SA, ELv2).
- Architected around credentials passed in plaintext via config files — directly incompatible with §3.9.

We therefore vendor an **explicit allowlist** in `.mcp.json` rather than relying on user-level config. This gives us:
- **License audit** — every server in the file has been verified MIT/Apache-2.0.
- **Reproducibility** — every contributor gets the same MCP surface.
- **Credential isolation** — env-var refs only; secrets stay in the OS env, never in the file, never in the repo.
- **Forensic chain-of-custody** — the MCP set in use during a case is recorded by Langfuse alongside the trace.

## 2. The five-MCP allowlist

| MCP | Origin | License | Transport | Purpose |
|---|---|---|---|---|
| `filesystem` | modelcontextprotocol/servers | **MIT** | stdio | Read-only access to ledger / evidence manifest / case metadata under the working tree. |
| `fetch` | modelcontextprotocol/servers | **MIT** | stdio | Threat-intel enrichment, live MITRE ATT&CK lookup, SANS docs. **Cloud/dual mode only** — TSI-audited egress. |
| `sequential-thinking` | modelcontextprotocol/servers | **MIT** | stdio | Structured multi-step reasoning for the planner_critique_node (CoVe). Reduces tool-call rounds. |
| `github` | github/github-mcp-server | **Apache-2.0** | stdio | PR review, commit chain audit, `[W#.#.#]` task-ID correlation. |
| `mitre-attack` | stoyky/mitre-attack-mcp | **MIT** | stdio | Technique lookup + §3.5 sub-technique validation. Hypothesis MITRE mapping. |

Five — not six, not ten. The Reddit consensus in 2026 is "the best Claude Code users run 2–3 plugins max"; we're doubling that, but only because each one maps to a concrete CLAUDE.md hard rule or a documented Verdict workflow. Anything more bloats prompt caches and dilutes the agent's attention budget.

## 3. Disqualified candidates (recorded so we don't re-evaluate)

| MCP | Issue | Disposition |
|---|---|---|
| **Daytona MCP** | AGPL-3.0 | **Forbidden**, CLAUDE.md §3.8 hard-NO. |
| **REMnux MCP** | GPL-3.0 vendored | **Forbidden**, CLAUDE.md §3.8 hard-NO. Out-of-process call only — never linked, never vendored. |
| **PostgreSQL MCP** (any flavor) | Verdict's runtime is SQLite-only (CLAUDE.md §9). Adding a Postgres MCP would imply Postgres in scope. | **Deferred** until/unless a case is genuinely backed by Postgres. SQLite MCP candidates exist (modelcontextprotocol/servers archived `sqlite` plus several community forks); track separately if needed. |
| **Slack MCP** | Out of scope for closed hackathon; team coordination handled via the Telegram Hermes adapter (`HERMES_TELEGRAM_*` in `.env.example`). | **Deferred.** |
| **Sentry MCP** | Observability stack is Langfuse v2 self-hosted (CLAUDE.md §5). | **Skip** — Langfuse covers this. |
| **Linear MCP** | Build plan is in `docs/BUILD_PLAN.md`, not Linear. | **Skip.** |
| **Puppeteer / Playwright MCPs** | DFIR agent has no UI to drive; browser-based evidence is parsed via tool wrappers in the microsandbox. | **Skip.** |

## 4. Credential isolation (§3.9 compliance)

This is the load-bearing constraint. Anthropic OAuth tokens, GitHub PATs, Langfuse keys — **none** of them enter a microsandbox. Ever.

### How `.mcp.json` references secrets

```jsonc
"github": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"],
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"   // <-- env-var ref, NOT the literal token
  }
}
```

The literal token lives in the developer's shell env (`export GITHUB_TOKEN=ghp_...`) or in `.env` (gitignored). Claude Code substitutes `${GITHUB_TOKEN}` at MCP startup. Three guarantees flow from this:

1. **The repo never carries a secret.** `grep -i 'token\|key\|secret\|password' .mcp.json` returns env-var refs only.
2. **The microsandbox never sees the secret.** MCP servers run on the host as Claude Code subprocesses; tool execution runs in microVMs with separate env isolation. Tokens stay on the host side of the boundary.
3. **TSI egress audit covers MCP-bound traffic too.** The host-level egress filter logs every outbound request keyed by token; tcpdump at the bridge shows zero traffic from microVMs carrying these tokens.

### MCP credential checklist (run before each case)

```bash
# 1. No literal secrets in .mcp.json
grep -E -i '(api[_-]?key|secret|token|password|BEGIN.*PRIVATE)' .mcp.json
# Should match only ${VAR_NAME} refs.

# 2. Required env vars exported
for v in GITHUB_TOKEN; do
  [[ -n "${!v:-}" ]] && echo "✓ $v set" || echo "✗ $v missing"
done

# 3. Microsandbox network default is closed
grep MICROSANDBOX_NETWORK_DEFAULT .env
# Expect: MICROSANDBOX_NETWORK_DEFAULT=false

# 4. Verdict doctor pre-flight
verdict doctor   # checks all of the above + SGLang + Langfuse + HMAC key
```

## 5. Install pattern

`.mcp.json` lives at the **repo root** and is committed. It loads automatically when Claude Code starts in this directory.

```bash
# 1. Set required env vars (in shell or .env)
export GITHUB_TOKEN="ghp_..."   # required for the github MCP

# 2. Verify
claude mcp list   # should show: filesystem, fetch, sequential-thinking, github, mitre-attack

# 3. Adding a new MCP — gate
#    a. License check (MIT / Apache-2.0)?              → CLAUDE.md §3.8
#    b. Carries credentials? Are they env-var-injected? → CLAUDE.md §3.9
#    c. Maps to a hard rule or documented workflow?    → this doc §2
#    d. Update .mcp.json + this doc + .env.example
```

User-level `~/.claude.json` is **not** used for project MCPs — it would create per-developer drift. Personal experiments belong there; project commitments belong in `.mcp.json`.

## 6. Future workstreams

- **Hook-level credential check.** A `PreToolUse` hook in `.claude/settings.json` that runs the §4 checklist before every MCP call. Tracked under `[W2.D.4]` (observability + ops).
- **MCP trace correlation.** Langfuse spans should record the MCP server, version, and call args alongside microsandbox tool calls — same `langfuse_trace_id` thread.
- **SQLite MCP evaluation.** If/when ledger queries become more frequent than `verdict validate`, evaluate SQLite MCPs against §3.8 and §3.9. Until then, direct `sqlite3` on the host is sufficient.
- **MITRE ATT&CK pinning.** `mitre-attack-mcp` queries the live framework. Pin to a Navigator JSON snapshot for deterministic eval reproducibility (Inspect AI ground-truth requirement).

## 7. Anti-patterns

- **Don't put literal secrets in `.mcp.json`.** Even briefly. Even "I'll edit it back out before commit". The pre-commit hook will not save you from a typo.
- **Don't add a GPL/AGPL/CC-BY-SA MCP "just for development".** License contamination is permanent; reject at the door.
- **Don't add an MCP that wraps a forbidden runtime dep.** A Daytona MCP wrapper is still Daytona. The §3.8 hard-NOs apply transitively.
- **Don't pile on.** Five MCPs is the upper end. New entries require a clear hard-rule or documented-workflow justification, not "this looks useful".

## 8. Sources

The 2026 ecosystem digest behind this allowlist:

- [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) — official reference servers
- [github/github-mcp-server](https://github.com/github/github-mcp-server) — official GitHub MCP
- [stoyky/mitre-attack-mcp](https://github.com/stoyky/mitre-attack-mcp) — MITRE ATT&CK MCP, MIT
- [50+ Best MCP Servers for Claude Code in 2026](https://claudefa.st/blog/tools/mcp-extensions/best-addons)
- [Connect Claude Code to tools via MCP — official docs](https://code.claude.com/docs/en/mcp)
- [MCP Security Checklist 2026 — networkintelligence.ai](https://www.networkintelligence.ai/blogs/model-context-protocol-mcp-security-checklist/)
- [MCP Server Sandbox Isolation Guide — claudecodeguides.com](https://claudecodeguides.com/mcp-server-sandbox-isolation-security-guide/)
