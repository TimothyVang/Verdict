# VERDICT — TL;DR with diagrams

> **Wiki:** [Index](README.md) · [TL;DR](TLDR.md) · [Architecture](ARCHITECTURE.md) · [Build Plan](BUILD_PLAN.md) · [Devpost](DEVPOST_COMPLIANCE.md) · root [CLAUDE.md](../CLAUDE.md)

> **Share this with new human teammates. Read it first.**
> One file, ~5-minute read, ASCII diagrams only — no install, no jargon-up-front.
> When you're done, the rest of the doc tree (`docs/ARCHITECTURE.md`, `docs/BUILD_PLAN.md`, `CLAUDE.md`) makes sense in context.

**One sentence:** A forensic LLM agent that catches its own hallucinations using two AI models cross-checking each other, encodes SANS investigative discipline as code (not prompts), and produces a courtroom-grade audit trail. Built for the SANS *FIND EVIL!* hackathon — Devpost upload **Jun 14 2026 EOD** (team target); official deadline **Jun 15 2026 11:45 PM EDT**.

---

## What VERDICT actually does

```
   Memory image / disk image / EVTX bundle
                 │
                 ▼
   ┌───────────────────────────────┐
   │  VERDICT Gateway              │
   │                               │
   │  1. Plans the investigation   │   "Where would evil hide?"
   │  2. Runs forensic tools       │   vol3, hayabusa, plaso, MFTECmd...
   │  3. Two models cross-check    │   Qwen3 vs GLM-4.5-Air
   │  4. Quorum decides verdict    │   VETTED / CONTESTED / UNVERIFIABLE
   │  5. HMAC-signs the audit log  │   Tamper-evident chain
   └───────────────────────────────┘
                 │
                 ▼
   ┌───────────────────────────────┐
   │  Findings + Audit Trail       │
   │  - Each finding cites ≥2      │
   │    artifact classes (FOR500)  │
   │  - Caveats acknowledged       │
   │    (Amcache ≠ execution etc.) │
   │  - MITRE sub-technique IDs    │
   │  - Tamper-evident HMAC chain  │
   │  - Trace tree in Langfuse     │
   └───────────────────────────────┘
```

**Release artifact status:** `docs/RELEASE.md`, `docs/ARCHITECTURE_DIAGRAM.svg`, and `submission/execution-logs/*.jsonl` are the consolidated release deliverables. Do not claim submission readiness until `docs/DEVPOST_COMPLIANCE.md` Part 6 is fully checked.

---

## Three modes — pick by environment, not config

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ CLOUD ONLY   │    │ AIR-GAP ONLY │    │ DUAL         │      │
│  ├──────────────┤    ├──────────────┤    ├──────────────┤      │
│  │ SOC analyst  │    │ DCO operator │    │ Forensic lab │      │
│  │ on laptop    │    │ on classified│    │ full rig     │      │
│  │              │    │ network      │    │              │      │
│  │ Internet ✓   │    │ Internet ✗   │    │ Both ✓       │      │
│  │ GPU      ✗   │    │ GPU      ✓   │    │              │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                    │              │
│         ▼                   ▼                    ▼              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ Claude n=3   │    │ Qwen3 + GLM  │    │ Claude +     │      │
│  │ self-        │    │ cross-engine │    │ Qwen3 + GLM  │      │
│  │ consistency  │    │ quorum       │    │ three-way    │      │
│  │              │    │              │    │              │      │
│  │ → VETTED     │    │ → VETTED_    │    │ → VETTED_    │      │
│  │   _CLOUD     │    │   AIRGAP     │    │   DUAL       │      │
│  │ (best-effort)│    │ (true cross- │    │ (strongest)  │      │
│  │              │    │   family)    │    │              │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

  Gateway autodetects mode at startup. Mode locks at case_init —
  no mid-investigation switching. Audit trail stays consistent.
```

---

## The agent loop (Plan-then-Execute)

```
                START
                  │
                  ▼
        ┌──────────────────┐
        │  Planner         │   "Investigate process injection.
        │  (Claude/Qwen3)  │    Negative: rule out persistence.
        │                  │    Use vol3.malfind, RECmd."
        └────────┬─────────┘
                 │
                 ▼
        ┌──────────────────┐
        │ Planner Critique │   "Does plan cover most-likely
        │ (CoVe — same     │    attacker techniques given the
        │  model checks    │    evidence type? Yes/no/replan."
        │  its own plan)   │
        └────────┬─────────┘
                 │
                 ▼
        ┌──────────────────┐
        │ Comprehension    │   "Do all 4 executors agree on
        │ Gate             │    what the plan said?"
        └────────┬─────────┘
                 │
            ┌────┴────┬────────┬────────┐
            ▼         ▼        ▼        ▼
         ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐
         │vol3 │  │haya │  │plaso│  │MFTec│   FANOUT — 4 parallel
         │exec │  │busa │  │exec │  │ exec│   executor branches
         │     │  │exec │  │     │  │     │   running in microVMs
         └──┬──┘  └──┬──┘  └──┬──┘  └──┬──┘
            │        │        │        │
            └────────┴───┬────┴────────┘
                         ▼
                ┌──────────────────┐
                │ Pivot Node       │   "Tool output suggests a
                │ (cheap follow-   │    new hypothesis — add 1
                │  up; max 15)     │    Hypothesis, re-run."
                └────────┬─────────┘
                         │
                         ▼
                ┌──────────────────┐
                │ Quorum           │   "Do both engines agree on
                │                  │    artifact set + technique?"
                └────────┬─────────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
        ┌─────────┐ ┌─────────┐ ┌─────────┐
        │ VETTED  │ │CONTESTED│ │UNVERIFI-│
        │         │ │         │ │ ABLE    │
        │ HMAC-   │ │ Replan  │ │ Agent   │
        │ sign &  │ │ (max 3) │ │ gives up│
        │ finalize│ │ then    │ │ explicit│
        │         │ │ unverif.│ │ ly      │
        └─────────┘ └─────────┘ └─────────┘
```

VETTED is the schema's vetted-by-quorum outcome; the persisted Finding carries the mode-specific status `VETTED_CLOUD` / `VETTED_AIRGAP` / `VETTED_DUAL` per `CLAUDE.md §3.6`.

---

## Three-layer immutability defense

```
   ┌─────────────────────────────────────────────────────┐
   │  Agent attempts tool call                            │
   │  e.g. "vol3 -f /evidence/mem.vmem windows.malfind"  │
   └──────────────────┬──────────────────────────────────┘
                      │
                      ▼
   ┌─────────────────────────────────────────────────────┐
   │  LAYER 1 — Claude PreToolUse hook                    │
   │  (cloud + dual modes; air-gap relies on layers 2-3)  │
   │                                                      │
   │  ⚠  Best-effort: anthropics/claude-code #33106      │
   │      means deny is buggy for MCP tools. Logged but  │
   │      not the architectural guarantee.               │
   └──────────────────┬──────────────────────────────────┘
                      │
                      ▼
   ┌─────────────────────────────────────────────────────┐
   │  LAYER 2 — LangGraph DenyRuleWrapper                 │
   │  (fires in ALL modes, regardless of model)          │
   │                                                      │
   │  ✓  Validates typed tool args against deny-rule     │
   │     list. Architectural guarantee.                  │
   └──────────────────┬──────────────────────────────────┘
                      │
                      ▼
   ┌─────────────────────────────────────────────────────┐
   │  LAYER 3 — Microsandbox read-only mount              │
   │  (kernel-enforced, even if Layers 1-2 bypassed)     │
   │                                                      │
   │  ✓  /evidence mounted read-only at the libkrun      │
   │     microVM kernel level. Cannot be written.        │
   └──────────────────┬──────────────────────────────────┘
                      │
                      ▼
              Tool runs in ephemeral
              microVM, dies after call
```

**Why three layers?** Defense-in-depth. Claude hooks don't fire in air-gap mode (no Claude in loop). Microsandbox alone doesn't catch tool-arg validation. Each layer catches what the others miss.

---

## What makes us different (the moat)

```
  Valhuntir (the bar to beat):              VERDICT:
  ────────────────────────────              ──────────────
  Single LLM                       VS       Two engines cross-check
  Human gates AFTER AI             VS       AI gates AGAINST AI
  No verification                  VS       Cross-family quorum
  No durable checkpointing         VS       Kill-9 resilient resume
  No trace observability           VS       Langfuse trace tree UI
  Forensic rules in prompts        VS       Forensic rules in TYPES
  Single mode                      VS       Cloud / air-gap / dual
```

**Three things competitors don't have:**

1. **Forensic discipline encoded in code, not prompts.** Schema *rejects* a Finding that cites Amcache without acknowledging the LastModified caveat. Schema *rejects* an execution claim with only one artifact class. Hunt Evil baselines + DKOM divergence detection fire automatically.

2. **Bidirectional audit trail.** Ledger entry → Langfuse trace → tool call → microsandbox version → file hash. And reverse: trace → ledger entry → finding. Judges can drill in either direction.

3. **Mode-locked verification.** No mid-case mode switching. Resume always uses original mode. Mode upgrades happen via explicit `verdict reverify` producing a parallel verdict chain.

---

## 6-week roadmap

> **Where we are now — 2026-05-02 (W1 Day 1):** Vang has solo-shipped ~190 commits across **W0** (bootstrap, swarm, skills, devcontainer, Langfuse), **W1.A** (doc wiki, infra), **W1.B** partial (`ArtifactClass`, `ToolOutput` w/ blake3), **W1.E.2** (`ToolWrapper` base), and **all of W2.C** (`DenyRuleWrapper` + `ToolExecutor` + `LedgerEmitter` + composed `executor_work`). That's ~3 nominal-weeks of solo throughput, ahead of the planned Tim track. **Beaver / Haley / KP are at 0 commits.** The Gantt below is the *planned* 4-person allocation; if the team stays solo, the descope priority list at the bottom of "What could kill us" kicks in by W4.

```
WEEK 1 ── May 2-8 ── FOUNDATIONS + SCHEMAS
─────────────────────────────────────────────────────
 Tim    │████████████████│  Infra + schemas + ops docs
 Beaver │████│             Seed-fix + Planner Protocol
 Haley  │██████│           SGLang + Qwen3 + GLM
 KP     │████████████████│ Playbooks + caveats + hunt_evil

  ★ HARD GATE: Schemas freeze May 8. No slip allowed.

WEEK 2 ── May 9-15 ── TOOL SURFACE + LANGGRAPH
─────────────────────────────────────────────────────
 Tim    │████████████████│  9 vol3 wrappers + ledger
 Beaver │████████████████│  Plan-then-Execute + critique
 Haley  │████│             OpenLLMetry wiring
 KP     │██████████│       9 non-vol3 wrappers

WEEK 3 ── May 16-22 ── VERIFIERS + TSI + CHECKPOINTING
─────────────────────────────────────────────────────
 Tim    │████████████████│  TSI + ledger writer + /health
 Beaver │████████████████│  3 verifier strategies + pivot
 Haley  │████│             Inference monitoring
 KP     │██████│           Tool wrapper polish

WEEK 4 ── May 23-29 ── SKILLS + EVALS
─────────────────────────────────────────────────────
 Tim    │██████████│       CI gates per mode
 Beaver │████████│         Prompt engineering iteration
 Haley  │██│               Inspect AI under-load tuning
 KP     │████████████████│ 6 skills + 50 indicators + 5 scorers

  ★ HARD GATE: Case 001 produces engineered Qwen3-vs-GLM
    disagreement by week-end (otherwise demo is a probability bet)

WEEK 5 ── May 30-Jun 5 ── MODE AUTODETECT + POLISH
─────────────────────────────────────────────────────
 Tim    │████████████│     Mode detect + adapters + docs
 Beaver │████│             Time-travel demo
 Haley  │██│               Demo rehearsal inference
 KP     │██████│           Accuracy report

  ★ Rough demo cut May 30 — find the shot before week 6

WEEK 6 ── Jun 6-14 ── DEMO + DOCS + SUBMIT
─────────────────────────────────────────────────────
 Tim    │████████████│     README + ARCHITECTURE + Devpost
 Beaver │██████│           Final cut + dry runs
 Haley  │██│               Demo support
 KP     │████│             Final accuracy polish

  ★ Submit Jun 14 EOD (24h before official deadline)
```

---

## Who does what (in one panel)

```
┌────────────────────────────────────────────────────────┐
│ TIM (VANG) ── Gateway / Microsandbox / Ledger / Hooks  │
│         ~22 teammate-days                              │
│  GIAC: GCFA · Solo lead, sole git author to date.      │
│                                                        │
│  • Schema bundle (Mode, ArtifactClass, CaveatID,       │
│    Finding, LedgerEntry, EvidenceManifest, ToolOutput) │
│  • FastMCP gateway + microsandbox provider             │
│  • HMAC ledger + write+fsync+verify-readback           │
│  • OpenLLMetry / Langfuse instrumentation              │
│  • TSI secret injection + tcpdump demo                 │
│  • Mode autodetect + verdict CLI                       │
│  • Threat model (ARCHITECTURE.md §9) + FAILURE_MODES.md│
│    + CLI reference (RELEASE.md)                        │
│  • Devpost packaging + submission                      │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ BEAVER ── LangGraph / Verifiers / Agent loop           │
│           ~22 teammate-days                            │
│  GIAC: GNFA, GCFA, GMLE · runs HW+local LLMs at home   │
│                                                        │
│  • Plan-then-Execute LangGraph topology (8 nodes)      │
│  • Three verifier strategies (Cloud/Airgap/Dual)       │
│  • Seed-derivation fix (n=3 actually diverse paths)    │
│  • planner_critique_node (CoVe)                        │
│  • comprehension_gate (executor consensus)             │
│  • pivot_node + replan_node + unverifiable_finalize    │
│  • SqliteSaver with WAL + synchronous=FULL             │
│  • Mode lock + verdict reverify                        │
│  • Final demo cut + judge checklist dry runs           │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ HALEY ── SGLang / Qwen3 / GLM-4.5-Air / vLLM           │
│           ~10 teammate-days (5 reserved as slack)      │
│  GIAC: GXPEN, GNFA · Hermes/agents + local LLM + CC    │
│                                                        │
│  • SGLang serving both models with proper parsers      │
│  • 100-call tool-call parse rate ≥98% (gate)           │
│  • OpenAI-compat client wiring for OTel                │
│  • Inference firefighting reserve                      │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ KP ── Forensics / Tools / Eval / Content               │
│        ~21 teammate-days                               │
│  GIAC: GREM · new to stack; installing Claude Code     │
│                                                        │
│  • Three playbook YAMLs (memory/disk/triage)           │
│  • examiner_caveats.md + hunt_evil.yml + lolbins.yml   │
│  • 9 non-vol3 tool wrappers (Sleuth Kit, EZ Tools...)  │
│  • 6 agentskills.io skills with required_tools         │
│  • 50 ground-truth indicators across 3 cases           │
│  • 5 Inspect AI scorers                                │
│  • Demo Case 001 engineered for Qwen3-vs-GLM disagree  │
│  • Qwen3-vs-GLM disagreement-correlation measurement   │
│  • ACCURACY_REPORT.md                                  │
└────────────────────────────────────────────────────────┘
```

---

## First pickups — tasks matched to background

Each ID is from [`BUILD_PLAN.md`](BUILD_PLAN.md). Pick the one that lines up with what you already know — track ownership stays as above, but **the first PR should ride your strongest asymmetry**, not the hardest open task. Vang has the rest of his track in flight (`W1.B`, `W2.A`, `W1.G.6`); the entries below are the **suggested first commits for everyone else** so that the first green CI run is also a domain-fit win.

| Owner | Task ID | What it is | Why this fits |
|-------|---------|------------|---------------|
| **Vang** *(in flight)* | `W1.B.5` | `Hypothesis` + `InvestigationPlan` + `PlannerCritiqueVerdict` schemas | Continues the schema bundle he's been driving since `W1.B.1`/`W1.B.7`. |
| **Vang** | `W2.A.1` | `vol3.pslist` MCP tool wrapper | First vol3 wrapper — exercises the `ToolWrapper` base just landed (`W1.E.2`) and the composed `executor_work` (`W2.C.4`). |
| **Vang** | `W1.G.6` | HMAC key handling (TPM-backed, gpg fallback) | Closes the ledger trust chain alongside the `LedgerEmitter` (`W2.C.3`). GCFA discipline keeps the chain-of-custody story honest. |
| **Beaver** | `W1.A.4` | SGLang + Qwen3 + GLM-4.5-Air on the dev rig | Runs HW + local LLMs at home — bring-up is his strongest asymmetry. Unblocks every air-gap and dual-mode task downstream. |
| **Beaver** | `W1.C.1` → `W1.C.3` | `derive_seeds(case_id)` + `CloudSelfConsistency` + `VerifierStrategy` Protocol | Verifier track is his ownership; seed-derivation fix is a one-day schema-touching warmup before the bigger nodes. |
| **Beaver** | `W4.G.1` | Measure Qwen3-vs-GLM disagreement-correlation across 50 findings | GMLE cert + dual-model home rig = he can run both engines and produce the stats. The single number that lets the demo claim "true cross-family verification". |
| **Beaver** | `W3.E.6` | Kill-9 chaos test (100/100 zero-loss) | Bare-metal chaos beats VM chaos — his home rig is the correct test environment. |
| **Haley** | `W2.D.1` → `W2.D.3` | CoVe (Chain-of-Verification) planner critique node + CoT capture | Hermes/agents background + Claude Code fluency align with planner-side agent design. CoVe is `planner_critique_node` from `ARCHITECTURE.md` §1. |
| **Haley** | `W4.F.1` → `W4.F.3` | Negative-hypothesis few-shot, adversarial-reasoning prompt, prompt-budget CI assertion | GXPEN red-team thinking fits adversarial prompt design — most teams skip this and lose hallucination-rate budget. |
| **Haley** | `W2.G.3` | SGLang client uses OpenAI-compat path (for OTel) | Small, well-scoped wiring task in her primary track — good week-1 ramp before agent work. |
| **KP** | `W1.B.2` | `CaveatID` enum | Smallest schema-only first PR — green CI, first `[W#.#.#]` commit, no Claude Code wrestling. |
| **KP** | `W1.F.7` + `W1.F.9` | `examiner_caveats.md` + `hunt_evil.yml` | Pure forensic-discipline content, zero infra friction. The seven Tier-1 caveats are CLAUDE.md §3.3; this codifies them. |
| **KP** | `W2.A.18` | `capa` MCP tool wrapper | **GREM-shape directly.** capa is malware capability detection — exactly his cert. |
| **KP** | `W4.A.3` | `malware-static/` skill (1 of 6 agentskills) | GREM informs the skill's `KNOWLEDGE.md` (PE structure, packers, anti-analysis). No LangGraph touchpoints; pure content. |

**Rule of thumb:** if a teammate's first PR doesn't ride a domain strength, swap it for one that does. Hackathon time is the wrong context to learn a track *and* a stack *and* the conventions in `CLAUDE.md` §3 simultaneously.

---

## The 5-minute demo (7 hero beats)

```
0:00 ─┬─ Cold open + architecture flash
       │
0:30 ─┤ CLOUD-ONLY MODE (60s)
       │  • Three Claude samples at temp=0.7, three seeds
       │  • Langfuse pane: 3 sibling spans converging
       │  • 2-of-3 agree → VETTED_CLOUD (honest framing)
       │
1:30 ─┤ AIR-GAP MODE (90s) — THE HERO SHOT
       │  Pull network cable on camera. Mode re-detects → airgap.
       │
       │  ⓵ DKOM divergence: pslist + psscan diverge
       │     → automatic Hypothesis(T1014)
       │     "textbook rootkit signature"
       │
       │  ⓶ Hunt Evil masquerade: scvhost.exe parent=cmd.exe
       │     → automatic Hypothesis(T1036.005)
       │     "process baseline anomaly"
       │
       │  ⓷ Amcache caveat: Finding rationale acknowledges
       │     "LastModified ≠ execution; corroborated by
       │      Prefetch + EVTX 4688"
       │
       │  ⓸ Pivot in action: weird-parent finding triggers
       │     pivot_node → 1 new Hypothesis, no replan
       │
       │  ⓹ Disagreement: Qwen3 hallucinates path; GLM
       │     disagrees → CONTESTED → replan → both agree
       │     → VETTED_AIRGAP (HMAC-signed)
       │
       │  ⓺ TSI proof: tcpdump shows API key on host egress,
       │     NOT inside microvm. Credentials never enter VM.
       │
       │  ⓻ Kill -9 + resume: yank gateway between super-steps,
       │     restart, verdict resume picks up from checkpoint.
       │
3:00 ─┤ DUAL MODE (60s)
       │  • Plug cable back. New case (mode locked at init).
       │  • Three-way verification → VETTED_DUAL
       │
4:00 ─┤ Architecture recap + per-mode accuracy table
       │  • Hallucination rate per mode
       │  • MITRE sub-technique precision
       │  • Negative-hypothesis quality
       │  • Qwen3-vs-GLM disagreement correlation
       │
5:00 ─┴─ End card: repo URL + MIT license
```

---

## What could kill us (top 4 risks)

```
┌─────────────────────────────────────────────────────────┐
│ RISK #1 — Microsandbox hits a blocker week 4+           │
│                                                         │
│  Likelihood: MEDIUM (pre-1.0; pinned 0.4.x line)        │
│  Impact:     HIGH (kills TSI hero shot)                 │
│  Mitigation: Test it HARD in week 2 (chaos exercise),   │
│              not week 4. Have bubblewrap+nsjail         │
│              fallback rehearsed. Accept loss of TSI.    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ RISK #2 — Case 001 doesn't disagree by end of week 4    │
│                                                         │
│  Likelihood: MEDIUM                                      │
│  Impact:     HIGH (no air-gap demo without disagreement)│
│  Mitigation: KP starts engineering W1, not W4. If 001   │
│              won't disagree, engineer 002 to. Both done │
│              by mid-W5 latest.                          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ RISK #3 — Schemas slip past May 8                       │
│                                                         │
│  Likelihood: MEDIUM                                      │
│  Impact:     EXTREME (cascades into every later week)   │
│  Mitigation: HARD descope on May 6 if Phase W1.B not 80%│
│              done. Drop W1.G architecture-review docs   │
│              first (they can land in W6).               │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ RISK #4 — Solo execution (Vang is sole git author)      │
│                                                         │
│  Likelihood: HIGH (state at W1 Day 1; ~190 commits all  │
│              by Vang; Beaver/Haley/KP at 0)             │
│  Impact:     EXTREME (one sick week and the 4-person    │
│              Gantt becomes a 1-person Gantt; Case 001   │
│              disagreement work has no owner without KP) │
│  Mitigation: Each teammate ships a first PR from the    │
│              First-pickups table by W1 EOD. Beaver:     │
│              W1.A.4 (rig bring-up). Haley: W2.G.3 then  │
│              W2.D.1. KP: W1.B.2 (CaveatID enum).        │
│              Vang stops being the only path to every    │
│              domain by W2 Day 1.                        │
└─────────────────────────────────────────────────────────┘

  Master descope priority (cut in this order under pressure):
    1. Optional adapters (Atropos, Hermes pager, GhidrAssist)
    2. REMnux MCP
    3. kill-9 chaos test 100/100 → 10/10 sample
    4. 5 of 6 skills (keep windows-triage + memory + report)
    5. Planner CoT capture
    6. planner_critique_node (accept wrong-plan v1 risk)
    7. pivot_node (fold pivots into replan loop)

  NEVER cut: schema bundle, seed-fix, playbooks,
             psscan+DKOM, executor split, ≥1 verifier,
             kill-9 resume, demo video, Devpost submission.
```

---

## Bottom line — mapped to all 6 official Devpost judging criteria

Judging criteria are separate from submission artifacts. The eight required Devpost artifacts and the 19-item internal release checklist live in `docs/DEVPOST_COMPLIANCE.md`.

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│  Six equally-weighted judging criteria. We score on each:  │
│                                                            │
│   1. AUTONOMOUS EXECUTION QUALITY                          │
│      Mode-aware verifier strategy. Plan-then-Execute       │
│      with planner_critique CoVe + comprehension_gate +     │
│      pivot vs replan + unverifiable_finalize.              │
│      Self-correction via cross-engine quorum.              │
│                                                            │
│   2. IR ACCURACY                                           │
│      Artifact-pair rule, Tier-1 caveats, MITRE sub-        │
│      techniques, VETTED_CLOUD vs VETTED honesty,           │
│      Hunt Evil masquerade, DKOM auto-detection.            │
│      Five Inspect AI scorers per mode.                     │
│                                                            │
│   3. BREADTH AND DEPTH OF ANALYSIS                         │
│      "Depth on fewer types beats shallow coverage of       │
│      many" — Devpost rubric line we lean on directly.      │
│      Windows-DFIR-depth-first; v2 extension points         │
│      named (5th net_executor + live_executor branches).    │
│                                                            │
│   4. CONSTRAINT IMPLEMENTATION                             │
│      Three-layer immutability (PreToolUse + DenyRule       │
│      + microsandbox kernel mount). HMAC ledger. TSI.       │
│      Mode lock at case_init. Architectural, not prompt.    │
│                                                            │
│   5. AUDIT TRAIL QUALITY                                   │
│      HMAC ledger ↔ Langfuse bidirectional. Three-tier      │
│      ID hierarchy. Per-output-file SHA-256. Exam-          │
│      environment metadata (NIST SP 800-86).                │
│                                                            │
│   6. USABILITY AND DOCUMENTATION                           │
│      Reproducible from a fresh SIFT VM. verdict doctor     │
│      pre-flight. Reproducible doc set. Conventional        │
│      Commits with task IDs. agentskills.io portable        │
│      skills.                                               │
│                                                            │
│  Cost: ~76 teammate-days over 6 weeks, 4 people.           │
│  Risk: ~4 days slack budget. Microsandbox is pre-1.0.      │
│                                                            │
│  Hard deadline: Jun 15, 2026 11:45 PM EDT.                 │
│  Team target:   Jun 14 EOD = ~28h buffer.                  │
│                                                            │
│  Winnable? YES — if schemas lock May 8 and Case 001        │
│  disagrees by end of W4. Those are the load bearers.       │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

**Tie-breaker awareness:** rules break ties by criterion order (1 before 2 before 3...). If we're competing for placement, push hardest on Autonomous Execution Quality (criterion #1) — the self-correction beat must land cleanly in the demo.

---

## What you need to run / contribute

Three layers — **toolchain** (host), **services** (lab/cloud), **agent surface** (Claude Code session). All three are pinned; nothing is `latest`. The fastest path is `bash scripts/bootstrap-dev.sh` (idempotent), then `verdict doctor` to verify.

### Toolchain (host)

| Component | Pin | Why |
|---|---|---|
| **OS** | SIFT Workstation 24.04 (Ubuntu) — canonical | Forensic tools, microsandbox, libkrun resolve here |
| **Python** | 3.11 (via `uv`) | Runtime for `verdict` agent, schemas, planner |
| **Rust** | 1.88 | FastMCP 3.x gateway |
| **Node** | 20.x LTS + `pnpm` | MCP servers (deferred v2) |
| **Microsandbox** | v0.4.x (libkrun-based) | Read-only `/evidence` mount, ~200 ms cold microVM |
| **Linters** | `ruff`, `cargo clippy`, `eslint` | Pre-commit + CI gates |
| **Git signing** | GPG or SSH ed25519 | Every commit on `main` must be verified |

### Services (run-time)

| Service | Required for | How |
|---|---|---|
| **SGLang** serving Qwen3-30B-A3B-Thinking-2507 (Apache-2.0) | Air-gap + dual modes (planner/executor) | `sglang_server_v1 --model-path … --tool-call-parser qwen --port 30000` |
| **SGLang** serving GLM-4.5-Air (MIT) | Air-gap + dual modes (verifier only) | `sglang_server_v1 --model-path … --tool-call-parser glm --port 30001` |
| **Anthropic / OpenRouter API** | Cloud + dual modes | `ANTHROPIC_API_KEY` preferred; `OPENROUTER_API_KEY` optional host-side AI-agent fallback. OAuth/API tokens are per-contributor and never enter microVMs. |
| **Langfuse v2 (self-host)** | Trace observability, ledger ↔ trace cross-link | `docker-compose -f infra/langfuse/docker-compose.yml up -d` |
| **HMAC signing key** | Ledger integrity (CLAUDE.md §3.9) | TPM (`/dev/tpmrm0`) when available, else gpg-encrypted at `~/.verdict/key.gpg` |

`verdict doctor` is the one-command pre-flight: API reachable, SGLang up, microsandbox installed, Langfuse healthy, HMAC key resolvable. CI fails closed if it fails.

### Skills — `.claude/skills/` (auto-loaded by Claude Code)

18 skills compose into a Plan → TDD → Subagent-driven-dev → Review → Commit pipeline (`docs/SKILLS_FRAMEWORK.md`). Skill and MCP licenses are tracked in `docs/SKILLS_LICENSE_AUDIT.md`.

```
verdict-house-rules        ← Verdict (custom). Re-states CLAUDE.md §3 hard rules
                              as a skill so the agent obeys them on every action.
                              Auto-triggers on every session.

using-superpowers          ← obra/superpowers — index of the framework

  brainstorming            ← Socratic refinement before any code
  writing-plans            ← Decompose feature → 2–5 min tasks
  executing-plans          ← Batch-execute with human checkpoints
  test-driven-development  ← RED → GREEN → REFACTOR (with [W#.#.#] task ID overlay)
  subagent-driven-development  ← Dispatch to subagent + review subagent
  dispatching-parallel-agents  ← Concurrent subagent workflows
  using-git-worktrees      ← Isolated parallel branches
  systematic-debugging     ← 4-phase root-cause loop
  verification-before-completion  ← Confirm fix landed before "done"
  requesting-code-review   ← Pre-review checklist
  receiving-code-review    ← Structured response to feedback
  finishing-a-development-branch  ← Merge / PR decision → /qc commit + push
  writing-skills           ← How to author additional skills

grill-me                   ← mattpocock/skills — relentless interview on a plan
grill-with-docs            ← mattpocock/skills — same, but cross-checks ARCH.md
```

### MCPs — mode-scoped configs (MIT/Apache-2.0 only)

```
filesystem            modelcontextprotocol/servers (MIT)
                      Local workspace access to ledger / evidence manifest / case meta.
                      Excluded from safe default because upstream exposes write-capable
                      tools; cloud/dual developer configs only.

fetch                 modelcontextprotocol/servers (MIT)
                      Threat-intel + MITRE live lookup. Cloud/dual configs only;
                      omitted from `.mcp.json` and `.mcp.airgap.json`.

sequential-thinking   modelcontextprotocol/servers (MIT)
                      Structured multi-step reasoning for planner_critique CoVe.

github                github/github-mcp-server (Apache-2.0)
                      PR review + commit chain audit + [W#.#.#] correlation.
                      env: GITHUB_PERSONAL_ACCESS_TOKEN=${GITHUB_TOKEN}

mitre-attack          stoyky/mitre-attack-mcp (MIT)
                      Technique lookup + sub-technique validation (CLAUDE.md §3.5).

context7              upstash/context7-mcp (MIT)
                      Up-to-date library/API docs (Pydantic v2, LangGraph,
                      Inspect AI, Anthropic SDK). Cloud/dual configs only.
```

Safe default: `.mcp.json` loads only `sequential-thinking`. Use `.mcp.cloud.json` or `.mcp.dual.json` explicitly for research sessions that need `filesystem`, `fetch`, `github`, `mitre-attack`, or `context7`.

**Forbidden:** any MCP that's not MIT or Apache-2.0 — Daytona MCP (AGPL-3.0), REMnux MCP (GPL-3.0). Full disqualified-candidates table in `docs/MCP_FRAMEWORK.md` §3.

### Environment variables

```bash
# Required for cloud / dual mode
export ANTHROPIC_API_KEY="<your-anthropic-api-key>"
export OPENROUTER_API_KEY="<your-openrouter-api-key>"  # optional host-side AI-agent fallback

# Required for the github MCP (PAT scoped to TimothyVang/Verdict)
export GITHUB_TOKEN="ghp_..."

# Required for air-gap / dual mode (after SGLang is up)
export SGLANG_BASE_URL="http://localhost:30000"
export SGLANG_GLM_BASE_URL="http://localhost:30001"

# Required: microsandbox network closed by default
export MICROSANDBOX_NETWORK_DEFAULT=false

# Optional — Langfuse self-host (if observability is on)
export LANGFUSE_HOST="http://localhost:3000"
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."
```

Full template in `.env.example`. **Never** commit `.env` — `.gitignore` covers `.env*`, `*.vmem`, `*.E0*`, `*.dd`, `*.raw`, `*.gpg`, `cases/`.

### One-command bootstrap

```bash
bash scripts/bootstrap-dev.sh   # toolchain (uv, rustup, nvm, microsandbox), pinned versions, idempotent
uv sync                         # Python deps
docker-compose -f infra/langfuse/docker-compose.yml up -d  # Langfuse v2
verdict doctor                  # pre-flight: all of the above must be green
```

Then pick a `[W#.#.#]` task from `docs/BUILD_PLAN.md` and follow the TDD loop in `CLAUDE.md` §3.7.

---

## Where to read more

```
  Need:                                  Read:
  ─────                                  ─────
  Devpost rule-to-artifact mapping       docs/DEVPOST_COMPLIANCE.md
  Architecture, schemas, threat model    docs/ARCHITECTURE.md
  Day-by-day TDD task plan               docs/BUILD_PLAN.md
  Hard rules an agent must obey          CLAUDE.md  (§3 in particular)
  Tier-1 examiner caveats                CLAUDE.md  §3.3
  Why we picked X over Y                 docs/spec/  (frozen audit history)
  Contributor onboarding                 CONTRIBUTING.md
  Vulnerability reporting                SECURITY.md
```

**Authority order for "are we satisfying the rules?":**
1. Devpost rules at https://findevil.devpost.com/ (always wins)
2. `docs/DEVPOST_COMPLIANCE.md` (rule-to-artifact mapping)
3. `docs/ARCHITECTURE.md` (current architectural authority)
4. `docs/BUILD_PLAN.md` (task sequencing)
5. `CLAUDE.md` (project conventions + hard rules)
6. `docs/spec/` (frozen audit history — reference only)

Code wins over docs. If code is right and a doc disagrees, fix the doc.
