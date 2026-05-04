# VERDICT

Mode-aware verifier-gateway for forensic LLM agents. Built for the SANS *FIND EVIL!* hackathon (deadline **Jun 15 2026 11:45 PM EDT**; team-internal target **Jun 14 EOD** = ~28 h buffer).

**One sentence:** Two AI models cross-check each other against forensic evidence, encoding SANS investigative discipline as schema rules (not prompts), producing a tamper-evident HMAC-signed audit trail that maps every finding back to a specific tool execution.

**Hackathon context:** *FIND EVIL!* is the SANS Institute's 2,447-participant DFIR-AI hackathon. Sponsor: SANS Institute. Judge: Rob T. Lee (CAIO). The goal is to "make Protocol SIFT a fully autonomous incident response agent" — IR agents that go from initial access to verdict in under 8 minutes, the same window an AI-powered adversary needs to reach domain control.

---

## Where to read what

Source code lives under `src/verdict/`. The outer `Verdict/` directory is the repository root;
`src/verdict/` is the importable Python application package.

| If you're working on… | Read in this order |
|---|---|
| **Anything for the first time** | this README → `CLAUDE.md` §3 (hard rules) → `docs/ARCHITECTURE.md` |
| **Schemas / validators** | `CLAUDE.md` §3.2–3.6 → `docs/ARCHITECTURE.md` §4 → `docs/BUILD_PLAN.md` W1.B–W1.E |
| **Planner / orchestration** | `CLAUDE.md` §4 → `docs/ARCHITECTURE.md` §2 → `docs/BUILD_PLAN.md` W2.B–W2.C |
| **Tool wrappers** | `docs/ARCHITECTURE.md` §6 → `docs/BUILD_PLAN.md` W2.A + W2.F |
| **Verifier strategies** | `CLAUDE.md` §8 → `docs/ARCHITECTURE.md` §1 → `docs/BUILD_PLAN.md` W3.A–W3.C |
| **Ledger / audit trail** | `CLAUDE.md` §9 → `docs/ARCHITECTURE.md` §5 → `docs/BUILD_PLAN.md` W2.D |
| **CLI / submission** | `CLAUDE.md` §10 → `docs/BUILD_PLAN.md` W6.* → `docs/DEVPOST_COMPLIANCE.md` |
| **Setting up your machine** | `CONTRIBUTING.md` §0–4 → `downloads/README.md` |

**Authority order when docs disagree:** Devpost rules → `DEVPOST_COMPLIANCE.md` → `ARCHITECTURE.md` → `BUILD_PLAN.md` → `CLAUDE.md`. Code wins over docs; if code is right, fix the doc.

**Release docs:** setup, reproducibility, scope, CLI, demo, judge checklist, dataset, accuracy, production audit, and novelty live in [`docs/RELEASE.md`](docs/RELEASE.md). Devpost rule traceability lives in [`docs/DEVPOST_COMPLIANCE.md`](docs/DEVPOST_COMPLIANCE.md).

---

## What VERDICT does

```
   Memory image / disk image / EVTX bundle
                 │
                 ▼
   ┌───────────────────────────────┐
   │  VERDICT Gateway              │
   │  1. Plans the investigation   │   "Where would evil hide?"
   │  2. Runs forensic tools       │   vol3, hayabusa, plaso, MFTECmd...
   │  3. Two models cross-check    │   Qwen3 vs GLM-4.5-Air
   │  4. Quorum decides verdict    │   VERIFIED / CONTESTED / UNVERIFIABLE
   │  5. HMAC-signs the audit log  │   Tamper-evident chain
   └───────────────────────────────┘
                 │
                 ▼
   Findings + Audit Trail
   - Each finding cites ≥2 artifact classes (FOR500)
   - Caveats acknowledged (Amcache ≠ execution etc.)
   - MITRE sub-technique IDs
   - Tamper-evident HMAC chain
   - Trace tree in Langfuse
```

Three modes auto-detected by environment (Internet ✓/✗, GPU ✓/✗) and **locked at case_init**: `cloud-only` (SOC laptop), `airgap-only` (DCO), `dual` (forensic lab). Full mode tables, agent-loop topology, and three-layer immutability defense in `docs/ARCHITECTURE.md` §1–§3.

---

## What makes us different (the moat)

```
  Single LLM                       VS  Two engines cross-check
  Human gates AFTER AI             VS  AI gates AGAINST AI
  No verification                  VS  Cross-family quorum
  No durable checkpointing         VS  Kill-9 resilient resume
  No trace observability           VS  Langfuse trace tree UI
  Forensic rules in prompts        VS  Forensic rules in TYPES
  Single mode                      VS  Cloud / air-gap / dual
```

**Three things competitors don't have:**

1. **Forensic discipline encoded in code, not prompts.** Schema *rejects* a Finding citing Amcache without acknowledging the LastModified caveat. Schema *rejects* an execution claim with only one artifact class. Hunt Evil baselines + DKOM divergence detection fire automatically.
2. **Bidirectional audit trail.** Ledger entry → Langfuse trace → tool call → microsandbox version → file hash. And reverse: trace → ledger entry → finding. Judges can drill in either direction.
3. **Mode-locked verification.** No mid-case mode switching. Resume always uses original mode. Mode upgrades happen via explicit `verdict reverify` producing a parallel verdict chain.

---

## 6-week roadmap (summary; full plan in `docs/BUILD_PLAN.md`)

```
WEEK 1 ── May 2–8  ── FOUNDATIONS + SCHEMAS                ★ Schemas freeze May 8
WEEK 2 ── May 9–15 ── TOOL SURFACE + LANGGRAPH
WEEK 3 ── May 16–22── VERIFIERS + TSI + CHECKPOINTING
WEEK 4 ── May 23–29── SKILLS + EVALS                       ★ Case 001 disagreement
WEEK 5 ── May 30–Jun 5 ── MODE AUTODETECT + POLISH         ★ Rough demo cut May 30
WEEK 6 ── Jun 6–14 ── DEMO + DOCS + SUBMIT                 ★ Submit Jun 14 EOD
```

Roles: Tim (infra, ledger, ops), Beaver (orchestration, verifiers), Haley (inference, observability), KP (playbooks, skills, evals).

---

## Demo (5 min, 7 hero beats)

```
0:00 ─┬─ Cold open + architecture flash
0:30 ─┤ CLOUD-ONLY MODE (60s) — three Claude samples → 2-of-3 → VETTED_CLOUD
1:30 ─┤ AIR-GAP MODE (90s) — THE HERO SHOT
       │  ⓵ DKOM divergence (pslist+psscan) → T1014 auto
       │  ⓶ Hunt Evil masquerade (scvhost.exe parent=cmd.exe)
       │  ⓷ Amcache caveat acknowledged in rationale
       │  ⓸ Pivot in action (1 pivot, 0 replans)
       │  ⓹ Disagreement → CONTESTED → replan → VERIFIED ★ (Devpost-required self-correction)
       │  ⓺ TSI tcpdump proof (key never enters VM)
       │  ⓻ Kill -9 + verdict resume
3:00 ─┤ DUAL MODE (60s) — three-way verification → VETTED_DUAL
4:00 ─┤ Architecture recap + per-mode accuracy table
5:00 ─┴─ End card: repo URL + MIT license
```

---

## Mapped to the 6 Devpost judging criteria

1. **Autonomous Execution Quality** *(tiebreaker)* — Mode-aware verifier strategy. Plan-then-Execute with planner_critique CoVe + comprehension_gate + pivot vs replan + unverifiable_finalize. Self-correction via cross-engine quorum.
2. **IR Accuracy** — Artifact-pair rule, Tier-1 caveats, MITRE sub-techniques, VETTED_CLOUD vs VERIFIED honesty, Hunt Evil masquerade, DKOM auto-detection. Five Inspect AI scorers per mode.
3. **Breadth and Depth of Analysis** — "Depth on fewer types beats shallow coverage of many" — Devpost rubric line we lean on directly. Windows-DFIR-depth-first; v2 extension points named (5th `net_executor` + `live_executor` branches).
4. **Constraint Implementation** — Three-layer immutability (PreToolUse + DenyRule + microsandbox kernel mount). HMAC ledger. TSI. Mode lock at case_init. **Architectural, not prompt.**
5. **Audit Trail Quality** — HMAC ledger ↔ Langfuse bidirectional. Three-tier ID hierarchy. Per-output-file SHA-256. Examination-environment metadata (NIST SP 800-86).
6. **Usability and Documentation** — Reproducible from a fresh SIFT VM. `verdict doctor` pre-flight. Conventional Commits with task IDs. agentskills.io portable skills.

**Tie-breaker awareness:** rules break ties by criterion order. Push hardest on Autonomous Execution Quality (#1) — the self-correction beat must land cleanly.

---

## Top 3 risks

```
RISK #1 — Microsandbox hits a blocker week 4+
  Likelihood: MEDIUM (pre-1.0; latest 0.1.x).  Impact: HIGH (kills TSI hero shot).
  Mitigation: Test it HARD in week 2, not week 4.

RISK #2 — Case 001 doesn't disagree by end of week 4
  Likelihood: MEDIUM.  Impact: HIGH (no air-gap demo without disagreement).
  Mitigation: KP starts engineering W1; engineer Case 002 if 001 fails.

RISK #3 — Schemas slip past May 8
  Likelihood: MEDIUM.  Impact: EXTREME (cascades into every later week).
  Mitigation: Hard descope on May 6 if Phase W1.B not 80% done.
```

**Master descope priority** (cut in order under pressure): optional adapters → REMnux MCP → kill-9 chaos test 100/100 → 5 of 6 skills → planner CoT capture → planner_critique_node → pivot_node.

**Never cut:** schema bundle, seed-fix, playbooks, psscan+DKOM, executor split, ≥1 verifier strategy, kill-9 resume, demo video, Devpost submission.

---

## Contributing

Outside contributions are welcome before the **Jun 14 EOD** submission cut. In-team work is tracked by `W#.#.#` task IDs in [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md); outside PRs should pick from the same backlog and respect the §3 hard rules in [`CLAUDE.md`](CLAUDE.md).

### Get involved

| Channel | Use it for |
|---|---|
| [GitHub Discussions](https://github.com/TimothyVang/Verdict/discussions) | Q&A, ideas, hero-beat captures, polls. Category routing in the [welcome post](https://github.com/TimothyVang/Verdict/discussions/1). |
| [GitHub Issues](https://github.com/TimothyVang/Verdict/issues) | Bug reports, regressions, tracked work. Cite the `W#.#.#` task ID if it maps to one. |
| [`SECURITY.md`](SECURITY.md) | Vulnerabilities — **never** post privately exploitable detail in Discussions or Issues. |

### Quickstart with an LLM agent

This codebase is built to be navigated by an LLM coding agent. [`CLAUDE.md`](CLAUDE.md) is the operating charter — Claude Code auto-loads it on session start; Cursor / Continue / Cline / Aider behave similarly when pointed at the repo root.

1. **Clone & cd**
   ```bash
   git clone https://github.com/TimothyVang/Verdict.git && cd Verdict
   ```
2. **Open the repo in your LLM agent.** It will auto-read [`CLAUDE.md`](CLAUDE.md) — §3 contains the hard rules, §10 documents the CLI + commands, and §2 is the authority chain when docs disagree.
3. **Bring up real backing services** before touching code that depends on them (no mocks — see §3.10). Install dependencies:
   ```bash
   uv sync --all-extras
   ```
   See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full toolchain table.
4. **Pick a task** from [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md) by `W#.#.#` ID. Filter for unchecked `[ ]` boxes; respect ownership (Tim / Beaver / Haley / KP). Surface the relevant `W#.#.#` task body to your agent so it has the failing-test spec and acceptance gate.
5. **Run the TDD loop** per `CLAUDE.md` §3.7: failing test → RED → implement → GREEN → one commit per task ID, format `feat(scope): summary [W#.#.#]`. **Never** `--no-verify`, **never** `git commit --amend`, **never** mock VERDICT-internal modules (§3.10).
6. **Commit and push manually** with the Conventional Commit format in `CLAUDE.md` §3.7. Do not bypass hooks, signing, or history rules.
7. **Open a PR** with the `W#.#.#` task ID in the title — `gh pr create --draft --title "<commit-title>" --body "<task-id> + summary + RED/GREEN snippets>"`.

**Hard rules to surface to your agent before it edits code** (these are the load-bearing ones — full list in `CLAUDE.md` §3):

- §3.1 — Evidence integrity (read-only `/evidence`, hash on entry, per-invocation hash, per-output-file SHA-256).
- §3.2 — Multi-artifact corroboration (`Finding.artifact_paths` and `artifact_classes` both `min_length=2`; execution-class techniques need ≥2 distinct `ArtifactClass` values).
- §3.5 — MITRE sub-technique precision (regex `^T\d{4}(\.\d{3})?$`; emit `T1055.012`, not bare `T1055`, when the sub is determinable).
- §3.7 — Conventional Commits with `[W#.#.#]` task ID; no `--no-verify`, no `--amend`.
- §3.8 — License allow-list: MIT or Apache-2.0 only. The Hard NOs table (Daytona AGPL, REMnux GPL, Llama 4 / Gemma 3 community, Modal / LangSmith / Braintrust / Phoenix / AutoGen / MS Agent Framework) is final.
- §3.10 — No mocks anywhere in the codebase. Every layer wires against real services from the first commit.

### Without an LLM

Follow [`CONTRIBUTING.md`](CONTRIBUTING.md) Step 0–7 for the full human-at-keyboard onboarding (account access → `gh auth login` → toolchain → GPG/SSH signing → clone → smoke investigation).

---

## Quick reference

| Need | Read |
|---|---|
| Architecture details, schemas, threat model | `docs/ARCHITECTURE.md` |
| Day-by-day TDD task plan, task IDs, ownership | `docs/BUILD_PLAN.md` |
| Devpost rule-to-artifact mapping, judge checklist | `docs/DEVPOST_COMPLIANCE.md` |
| Hard rules an agent must obey | `CLAUDE.md` §3 |
| Contributor onboarding (`gh auth`, GPG, clone, smoke test) | `CONTRIBUTING.md` |
| Community Q&A, ideas, hero-beat captures | [GitHub Discussions](https://github.com/TimothyVang/Verdict/discussions) |
| Bug reports + tracked work | [GitHub Issues](https://github.com/TimothyVang/Verdict/issues) |
| Vulnerability reporting | `SECURITY.md` |
| What large binaries to fetch and where | `downloads/README.md` |

### CLI surface (one-liner)

```
verdict {doctor, mode, init, resume, reverify, status, ls, show, export, validate, approve, gc, health}
```

`verdict reverify <case_id> --mode <cloud|airgap|dual>` re-runs verification under a new mode and writes a *parallel* verdict chain — the original ledger is never mutated. Full CLI reference in `CLAUDE.md` §10.2; flag spec in `docs/BUILD_PLAN.md` W3.C.2.
