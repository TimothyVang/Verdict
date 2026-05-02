# docs/ — VERDICT documentation wiki

> **Wiki home.** Project root: [README](../README.md) · [CLAUDE.md](../CLAUDE.md) · [CONTRIBUTING](../CONTRIBUTING.md) · [SECURITY](../SECURITY.md) · [LICENSE](../LICENSE)

Single front door for everything in `docs/`. The repo root `README.md` is the project entry point; this file is the **doc index** — every file under `docs/` has a row here with its role, audience, and when to read it.

Every doc under `docs/` (except `spec/` archive) carries a one-line `> **Wiki:** …` nav strip directly under its H1, linking back here plus to its closest siblings. That makes any page a one-hop jump from the index — no need to climb back manually.

If you are an LLM/Claude Code session, read this file before opening anything else under `docs/`.

## Authority order

Devpost rules → [`DEVPOST_COMPLIANCE.md`](DEVPOST_COMPLIANCE.md) → [`ARCHITECTURE.md`](ARCHITECTURE.md) → [`BUILD_PLAN.md`](BUILD_PLAN.md) → root [`../CLAUDE.md`](../CLAUDE.md) → [`spec/`](spec/) archive.

Code wins over docs. If code is right and a doc is wrong, fix the doc — don't roll back the code.

`AGENT_SWARM.md`, `MCP_FRAMEWORK.md`, `SKILLS_FRAMEWORK.md`, `SKILLS_LICENSE_AUDIT.md`, and `AGENTIC_WORKFLOW_REVIEW.md` are **engineering scaffolding** — they sit *below* `BUILD_PLAN.md` / `CLAUDE.md` and never override the runtime authority chain (each says so in its own header).

## Where to start

| You are… | Read in this order |
|----------|--------------------|
| A new human teammate | root [`../README.md`](../README.md) → [`TLDR.md`](TLDR.md) → [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| A Claude Code session picking up work | root [`../CLAUDE.md`](../CLAUDE.md) → [`ARCHITECTURE.md`](ARCHITECTURE.md) → [`BUILD_PLAN.md`](BUILD_PLAN.md) → the task ID you were assigned |
| Asking "why was X decided?" | [`spec/README.md`](spec/README.md) → the relevant numbered audit |
| Preparing the Devpost submission | [`DEVPOST_COMPLIANCE.md`](DEVPOST_COMPLIANCE.md) → [`hackathon/RULES.md`](hackathon/RULES.md) → [`hackathon/OVERVIEW.md`](hackathon/OVERVIEW.md) |
| Wiring an MCP server, skill, or swarm worker | [`MCP_FRAMEWORK.md`](MCP_FRAMEWORK.md) / [`SKILLS_FRAMEWORK.md`](SKILLS_FRAMEWORK.md) / [`AGENT_SWARM.md`](AGENT_SWARM.md) (whichever applies) |
| Auditing cross-doc consistency | [`DOCS_ACCURACY_REPORT.md`](DOCS_ACCURACY_REPORT.md) → [`AGENTIC_WORKFLOW_REVIEW.md`](AGENTIC_WORKFLOW_REVIEW.md) |

## Index — every doc, grouped by role

### Entry points

| File | Role | When to read |
|------|------|--------------|
| [`TLDR.md`](TLDR.md) | ~5-minute visual primer with ASCII diagrams. Living, teammate-shareable. Refreshed Devpost deadlines, verdict-status vocabulary per `../CLAUDE.md` §3.6, required skills/MCP/software section. | First read for a new human. Hand to anyone joining. |

### Current authority (single sources of truth)

| File | Role | When to read |
|------|------|--------------|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Canonical architecture — components, data flow, schemas, verifier strategies, threat model, tool surface. Supersedes everything in `spec/`. | Default reference for any code or design question. |
| [`BUILD_PLAN.md`](BUILD_PLAN.md) | 6-week / 75-teammate-day TDD execution plan. Task IDs (`W1.A.3.a`, `W1.B.7`, …), ownership, hours, weekly acceptance gates. | Pick your next task; cite the ID in commits; treat the weekly gate as definition-of-done. |
| [`DEVPOST_COMPLIANCE.md`](DEVPOST_COMPLIANCE.md) | Submission rule-to-artifact mapping. Every Devpost requirement traced to the file/commit that satisfies it. | Before any submission packaging; before any merge that touches a submission deliverable. |
| [`FAILURE_MODES.md`](FAILURE_MODES.md) | Runtime failure matrix: sandbox spawn, tool errors, fanout timeout, TSI failure, ledger write failures, and UNVERIFIABLE semantics. | Before implementing error paths or explaining graceful degradation to judges. |
| [`CASE_ISOLATION.md`](CASE_ISOLATION.md) | Case, chain, checkpoint, reverify, export, approval, and mode-lock boundaries. | Before implementing `verdict reverify`, `resume`, `export`, `approve`, or `validate`. |

### Audits (cross-doc consistency)

| File | Role | When to read |
|------|------|--------------|
| [`DOCS_ACCURACY_REPORT.md`](DOCS_ACCURACY_REPORT.md) | Cross-doc consistency audit — counts, labels, MITRE IDs, version pins, terminology. | When docs appear to contradict each other, or before a major doc edit. |
| [`AGENTIC_WORKFLOW_REVIEW.md`](AGENTIC_WORKFLOW_REVIEW.md) | Sister audit covering the agentic workflow itself — runtime LangGraph loop *and* the dev TDD loop. Filtered to not overlap with `DOCS_ACCURACY_REPORT.md`. | When evaluating whether the workflow rules in `../CLAUDE.md` §3 are coherent with the runtime topology in `ARCHITECTURE.md`. |

### Engineering frameworks (scaffolding — *not* runtime authority)

Each of these explicitly subordinates itself to `BUILD_PLAN.md` and `../CLAUDE.md`. They describe how dev tooling is wired; they do not extend the runtime topology.

| File | Role | When to read |
|------|------|--------------|
| [`AGENT_SWARM.md`](AGENT_SWARM.md) | Build-side LLM swarm spec — conductor / worker / reviewer / auditor agents that take `BUILD_PLAN.md` task IDs and open PRs. State machine, role contracts, coordination protocol. The `swarm/` source tree is its executable skeleton. | Before reading anything under `swarm/`; before reviewing a PR authored by a `swarm:*` worker. |
| [`MCP_FRAMEWORK.md`](MCP_FRAMEWORK.md) | Mode-scoped MCP allowlists + credential-isolation discipline. Every entry in `.mcp*.json` traces here. License-gated by `../CLAUDE.md` §3.8; egress-gated by §3.9. | Before adding/removing an MCP server, or when reviewing `.mcp*.json`. |
| [`SKILLS_FRAMEWORK.md`](SKILLS_FRAMEWORK.md) | How the vendored skills under `.claude/skills/` compose into a Plan → TDD → subagent-driven-dev → Review → Commit pipeline. `verdict-house-rules` is the overlay that enforces `../CLAUDE.md` §3 over upstream skill defaults. | Before authoring a new workflow, before vendoring a new skill. |
| [`SKILLS_LICENSE_AUDIT.md`](SKILLS_LICENSE_AUDIT.md) | Per-skill license audit log. Every entry under `.claude/skills/` (and any future MCP, hook, vendored artifact) gets a row here per `../CLAUDE.md` §3.8. | Before vendoring anything new; when answering "is X license-clean?". |

### Hackathon context

| File | Role | When to read |
|------|------|--------------|
| [`hackathon/RULES.md`](hackathon/RULES.md) | Official SANS *FIND EVIL!* 2026 rules, scraped from Devpost on 2026-05-02. | Before any submission decision — these are the upstream of `DEVPOST_COMPLIANCE.md`. |
| [`hackathon/OVERVIEW.md`](hackathon/OVERVIEW.md) | Hackathon overview + resource links (judge bios, prize structure, timeline). | Context-setting; not load-bearing. |

### Frozen archive (audit history)

[`spec/`](spec/) — point-in-time decision records. **Do not edit.** Cite from `ARCHITECTURE.md` instead. See [`spec/README.md`](spec/README.md) for what each numbered audit captured. Files: `01-audit-v4.3.md`, `02-audit-v4.4.md`, `03-audit-v4.5.md`, `04-spec-plan-v4.6.md`. (The original v4.6 TL;DR was promoted to `TLDR.md` and removed from the archive on 2026-05-02 to avoid drift.)

## Coming soon — referenced but not yet authored

These are cited by `../CLAUDE.md` and `BUILD_PLAN.md` but not yet written. Each has a task ID in `BUILD_PLAN.md`.

| Doc | Task ID |
|-----|---------|
| `BUILD.md` — exact build steps from a fresh SIFT VM, verified on a second VM | W1.A.2.a |
| `THREAT_MODEL.md` — four threat surfaces (insider, prompt-injection-from-evidence, malicious-tool-output, external-attacker) | W1.G.1 |
| `CLI.md` — full `verdict` command surface | W1.G (TBD) |
| `CHECKPOINTING.md` — SqliteSaver + WAL + reducer pattern | W1.G (TBD) |
| `SCOPE.md` — v1 = Windows DFIR; v2 roadmap (macOS / Linux / ESXi) | W1.G (TBD) |
| `SCHEMA_MIGRATION.md` — breaking-change migration policy | W1.G (TBD) |
| `SANS_JUDGE_CHECKLIST.md` — 15-item demo rubric | W6 |
| `PRODUCTION_AUDIT.md` — v4 triage (v1 vs v2) | W6 |
| `DEMO_SEQUENCE.md` — 5-min storyboard with timing | W6 |
| `ACCURACY_REPORT.md` — per-mode tables + correlation analysis | W6 |
| `ARCHITECTURE_DIAGRAM.svg` — rendered Devpost architecture diagram | W6.C.7 |
| `EVIDENCE_DATASET.md` — sources, hashes, and findings per test dataset | W6.C.8 |
| `NOVEL_CONTRIBUTION.md` — new hackathon work vs. pre-existing OSS | W6.C.10 |

## Editing rules

- **Never edit `spec/`.** Those files capture point-in-time decisions; they are cited from `ARCHITECTURE.md` and lose meaning if rewritten.
- **`ARCHITECTURE.md` is the single architectural authority.** If a component changes, update it here, not in the spec archive.
- **`BUILD_PLAN.md` task IDs are immutable** once a contributor has committed against them. New work gets a new ID.
- **Keep this index in sync.** Any new file under `docs/` needs a row above; any rename or deletion needs to be reflected here. Same for the authority table in `../CLAUDE.md` §2.
- **Wiki-nav header on every new doc.** Any new `docs/*.md` (except files under `spec/`) must carry a one-line `> **Wiki:** [Index](README.md) · …` strip directly under its H1, linking to the index plus 4–6 closest siblings. Subdirectory docs use `../` prefixes (see `hackathon/RULES.md` for the pattern).
- **Engineering-scaffolding docs (`AGENT_SWARM.md`, `MCP_FRAMEWORK.md`, `SKILLS_FRAMEWORK.md`, `SKILLS_LICENSE_AUDIT.md`, `AGENTIC_WORKFLOW_REVIEW.md`)** must keep their "below `BUILD_PLAN.md` and `CLAUDE.md`" disclaimer in their headers — they are not allowed to drift into supplanting authority.

## Note on `protocol-sift/`

`protocol-sift/` at the repo root is a **git submodule** pinned to upstream `teamdfir/protocol-sift`. Verdict keeps the upstream framework templates renamed as `global/CLAUDE.protocol-sift.md` and `case-templates/CLAUDE.protocol-sift.md` so they are not mistaken for Verdict authority. Do not edit them in place unless the change is intentionally made on the submodule's local `verdict-overrides` branch. When Verdict needs to override upstream behavior, do it in our root `../CLAUDE.md` or in `.claude/skills/verdict-house-rules/SKILL.md`.
