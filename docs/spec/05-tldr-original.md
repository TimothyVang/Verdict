# VERDICT — TL;DR with diagrams

**One sentence:** A forensic LLM agent that catches its own hallucinations using two AI models cross-checking each other, encodes SANS investigative discipline as code (not prompts), and produces a courtroom-grade audit trail. Built for the SANS Find Evil! hackathon, June 14, 2026 deadline.

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
   │  4. Quorum decides verdict    │   VERIFIED / CONTESTED / UNVERIFIABLE
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
│  │ → VETTED     │    │ → VERIFIED_  │    │ → VERIFIED_  │      │
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
        │VERIFIED │ │CONTESTED│ │UNVERIFI-│
        │         │ │         │ │ ABLE    │
        │ HMAC-   │ │ Replan  │ │ Agent   │
        │ sign &  │ │ (max 3) │ │ gives up│
        │ finalize│ │ then    │ │ explicit│
        │         │ │ unverif.│ │ ly      │
        └─────────┘ └─────────┘ └─────────┘
```

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
   │  (cloud + dual modes only; air-gap = no Claude)     │
   │                                                      │
   │  ⚠️  Best-effort: anthropics/claude-code #33106     │
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
│ TIM ── Gateway / Microsandbox / Ledger / Hooks         │
│         ~22 teammate-days                              │
│                                                        │
│  • Schema bundle (Mode, ArtifactClass, CaveatID,       │
│    Finding, LedgerEntry, EvidenceManifest, ToolOutput) │
│  • FastMCP gateway + microsandbox provider             │
│  • HMAC ledger + write+fsync+verify-readback           │
│  • OpenLLMetry / Langfuse instrumentation              │
│  • TSI secret injection + tcpdump demo                 │
│  • Mode autodetect + verdict CLI                       │
│  • THREAT_MODEL.md + FAILURE_MODES.md + CLI.md         │
│  • Devpost packaging + submission                      │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ BEAVER ── LangGraph / Verifiers / Agent loop           │
│            ~22 teammate-days                            │
│                                                        │
│  • Plan-then-Execute LangGraph topology (9 nodes)      │
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
│                                                        │
│  • SGLang serving both models with proper parsers      │
│  • 100-call tool-call parse rate ≥98% (gate)           │
│  • OpenAI-compat client wiring for OTel                │
│  • Inference firefighting reserve                      │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ KP ── Forensics / Tools / Eval / Content               │
│        ~21 teammate-days                                │
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
       │     → automatic Hypothesis(T1014.001)
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
       │     → VERIFIED_AIRGAP (HMAC-signed)
       │
       │  ⓺ TSI proof: tcpdump shows API key on host egress,
       │     NOT inside microvm. Credentials never enter VM.
       │
       │  ⓻ Kill -9 + resume: yank gateway between super-steps,
       │     restart, verdict resume picks up from checkpoint.
       │
3:00 ─┤ DUAL MODE (60s)
       │  • Plug cable back. New case (mode locked at init).
       │  • Three-way verification → VERIFIED_DUAL
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

## What could kill us (top 3 risks)

```
┌─────────────────────────────────────────────────────────┐
│ RISK #1 — Microsandbox hits a blocker week 4+           │
│                                                         │
│  Likelihood: MEDIUM (it's beta)                         │
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
│      techniques, VETTED_CLOUD vs VERIFIED honesty,         │
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
│      Reproducible from fresh SIFT VM. verdict doctor       │
│      pre-flight. 16 doc files. Conventional Commits        │
│      with task IDs. agentskills.io portable skills.        │
│                                                            │
│  Cost: ~76 teammate-days over 6 weeks, 4 people.           │
│  Risk: ~4 days slack budget. Microsandbox is beta.         │
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

## Where to read more

```
  Need:                                  Read:
  ─────                                  ─────
  Devpost rule-to-artifact mapping       DEVPOST_COMPLIANCE_CHECKLIST.md
  Why we picked X over Y                 VERDICT_AUDIT_v4.5.md
  Schema patches + DFIR rules            VERDICT_v4.6_SPEC_PLAN.md
  Day-by-day TDD task plan               VERDICT_MASTER_BUILD_PLAN.md
  Tier-1 examiner caveats                agent-config/MEMORY.md
  Tool sequencing playbooks              agent-config/PLAYBOOK.md
  Project conventions                    CLAUDE.md
```

**Authority order for "are we satisfying the rules?":**
1. Devpost rules at findevil.devpost.com (always wins)
2. DEVPOST_COMPLIANCE_CHECKLIST.md (rule-to-artifact mapping)
3. VERDICT_MASTER_BUILD_PLAN.md (task sequencing)
4. VERDICT_AUDIT_v4.5.md + VERDICT_v4.6_SPEC_PLAN.md (architecture rationale)
