# VERDICT — Technical Audit and Build Plan for the SANS "Find Evil!" Hackathon

**Document version 4.4 — May 2, 2026.** v4 added Langfuse + SqliteSaver + Plan-then-Execute. v4.1 patched the Hermes Agent characterization after source review. v4.2 fixed six self-review findings (cloud-only honesty, typed schemas, descope path, demo case engineering, fanout note, negative hypotheses). v4.3 fixed ten cross-team interaction-surface findings (LedgerEntry ID hierarchy, comprehension_gate, three-layer immutability, mode-lock-at-init, OpenLLMetry token integration test, TSI demo prep, per-mode Inspect AI scorers, fanout-checkpoint semantics, ground-truth count). **v4.4 fixes 24 findings from two parallel research passes:**

**Agentic design pass (depth C — deep, ~2 hours of literature review):** 11 findings. Two BLOCKERS (PreToolUse `permissionDecision: "deny"` is buggy for MCP tool calls per anthropics/claude-code issues #33106 + #37210; cloud-only n=3 self-consistency with deterministic seeds collapses to n=1 because Wang et al. 2022 requires diverse paths via temperature > 0). Five SHOULD-FIX (cross-family independence claim is empirically thin; negative-hypothesis schema enforcement is leaky; comprehension_gate solves executor-drift not wrong-plan; tool-call argument hallucination is unmodeled; replan_max=3 termination semantics undefined). Four NICE-TO-HAVE (skill-pack tool affordances; air-gap context budget; single-writer fanout test; sqlite WAL/fsync).

**DFIR practitioner pass (depth A — SANS FOR508/FOR500/FOR572 methodology):** 13 findings. Four BLOCKERS (no artifact-pair corroboration in Finding schema; no tool-sequencing playbook for the planner; Tier-1 examiner caveats from project's `agent-config/MEMORY.md` not encoded in v4.3; DKOM/T1014 `psscan`-vs-`pslist` divergence pattern missing despite project shipping both tools for exactly this). Eight SHOULD-FIX (MITRE sub-technique granularity; replan budget too small for real DFIR pivot count; Hunt Evil process-baseline knowledge missing; logical-extract chain-of-custody incomplete per NIST SP 800-86; plaso/Hayabusa not split into extract+filter phases; timezone discipline not enforced; case isolation vs SGLang RadixAttention; LOLBin discrimination guidance). Three NICE-TO-HAVE (Win11 SRUM/ETW; macOS/Linux/ESXi scope statement; adversarial-reasoning planner prompt).

The ten v4.3 system-design fixes remain in force; v4.4 layers on top, never overwrites.

## TL;DR

- **Stack is locked. Three operational modes.** Cloud-only: Claude Code with **n=3 self-consistency at temperature 0.7 and three blake3-derived seeds** (v4.4 fix). Air-gap-only: SGLang serving Qwen3-30B-A3B-Thinking + GLM-4.5-Air with cross-engine quorum. Dual: all three engines, strongest verification. Gateway autodetects mode at startup; operator overrides via `--mode={cloud,airgap,dual}`.
- **The clinching architecture is a mode-aware verifier-gateway with explicit Plan-then-Execute topology — now plus `planner_critique_node` (CoVe) before fanout and `pivot_node` between executor and quorum (v4.4).** Claude Code (cloud) plans; local Qwen3 + GLM-4.5-Air execute Volatility/Hayabusa/plaso/MFTECmd in parallel microsandbox VMs and grade each other. quorum_node enforces agreement. replan_node closes contested findings. **Pivot budget = 15 per case, replan budget = 3 per case (v4.4).** No public competitor implements any of this.
- **Three production-maturity additions land in v1** (carried from v4): Langfuse (MIT) self-hosted, LangGraph SqliteSaver checkpointing with **WAL + synchronous=FULL** (v4.4 hardening), Plan-then-Execute named pattern.
- **Forensic discipline encoded in code, not prompts (v4.4).** Project `agent-config/MEMORY.md`'s seven Tier-1 caveats (Amcache LastModified ≠ execution; ShimCache ordering changed at Win 8.1; Logon Type 3 vs 10; `$SI` vs `$FN`; UsnJrnl wrapping; Sysmon ProcessGuid > PID; Prefetch SSD-disabled) ship as `verdict/prompts/examiner_caveats.md` injected into every executor system prompt. `Finding.caveats_acknowledged` field is required when the relevant caveat applies. Three playbook YAMLs (`memory.yml`, `disk.yml`, `triage.yml`) port the project's existing `agent-config/PLAYBOOK.md` into the planner prompt.
- **Why three modes beats two engines.** Same as v4.3 — DCO without internet, SOC without GPU, lab with both. Three-mode framing turns infrastructure constraints into a feature.
- **Hard nos** (unchanged from v4.3): Daytona AGPL-3.0, Llama 4 / Gemma 3 community licenses, REMnux MCP GPL-3.0 (network-call only), AutoGen v0.4 maintenance-mode dead-end.

---

## Operational Modes

VERDICT detects available infrastructure at startup and selects one of three modes. Operators can override with `--mode={cloud,airgap,dual}`.

| Mode | Trigger | Engines | Verifier Strategy | Use Case |
|---|---|---|---|---|
| **cloud-only** | Internet reachable, no local GPU | Claude Code (Agent SDK) | **n=3 self-consistency at temperature 0.7 with three case_id-derived seeds** (best-effort vetting, not true verification — same model shares failure modes; ≥2-of-3 agree → `VETTED_CLOUD`, otherwise `DRAFT_CLOUD`). v4.4 corrected: deterministic-seed-with-temp-0 produces n=1, defeating the technique (Wang 2022 self-consistency requires diverse paths). | SOC analyst on corporate laptop, hackathon judges reproducing the demo, fast first-look triage. |
| **air-gap-only** | No internet, local GPU available | SGLang serving Qwen3-30B-A3B-Thinking + GLM-4.5-Air | Cross-engine quorum: both local models must independently agree on artifact set. **v4.4: empirically validate independence — KP measures Qwen3-vs-GLM disagreement correlation across 50 ground-truth findings; partial-independence claim documented honestly in accuracy report.** | DCO on classified network, hospital under HIPAA, financial under PCI. |
| **dual** | Both available | Claude Code + SGLang (Qwen3 + GLM-4.5-Air) | Three-way: cloud agrees with at least one local engine; both local engines agree with each other. | Forensic lab, full-rig deployment. |

All three modes use the same internal **Plan-then-Execute topology**: `planner_node` → `planner_critique_node` (v4.4 CoVe) → `comprehension_gate` (v4.3) → fanout to parallel `executor_nodes` → `pivot_node` (v4.4 cheap follow-ups) → `quorum_node` → `replan_node`/`unverifiable_finalize_node` (v4.4 explicit termination).

### Cloud-only seed derivation (v4.4 fix)

```python
# verdict/verification/cloud_self_consistency.py (v4.4)
def derive_seeds(case_id: str) -> tuple[int, int, int]:
    """Three different seeds, deterministic per case for reproducibility,
    distinct so n=3 actually samples three different reasoning paths.
    Wang et al. 2022 (arXiv:2203.11171) requires diverse paths — temp 0
    + same seed = identical output = n=1 in disguise."""
    h = blake3(case_id.encode())
    return (
        int.from_bytes(h.derive_key("seed_a").digest()[:4], "big"),
        int.from_bytes(h.derive_key("seed_b").digest()[:4], "big"),
        int.from_bytes(h.derive_key("seed_c").digest()[:4], "big"),
    )

class CloudSelfConsistency(VerifierStrategy):
    """n=3 samples from Claude at temperature=0.7 with three case_id-derived
    seeds (NOT deterministic-temp-0; that collapses to n=1).
    Returns VETTED_CLOUD on ≥2-of-3 agreement, DRAFT_CLOUD otherwise.
    NOT TRUE VERIFICATION — same model shares failure modes."""
    async def verify(self, plan, evidence_hash):
        s1, s2, s3 = derive_seeds(plan.case_id)
        samples = await asyncio.gather(*[
            claude.complete(plan, temperature=0.7, seed=s)
            for s in (s1, s2, s3)
        ])
        # Universal Self-Consistency (Chen et al. 2023, arXiv:2311.17311):
        # use LLM to judge agreement on free-form rationale, not just
        # majority-vote on artifact paths.
        return await usc_judge(samples, plan)
```

### LangGraph topology (Plan-then-Execute v4.4)

```
START
  │
  ▼
┌─────────────────────┐
│  planner_node       │  Claude Code (cloud) or Qwen3 (airgap)
│  produces typed     │  Output: InvestigationPlan with hypotheses,
│  InvestigationPlan  │  NEGATIVE hypotheses (quality-validated, v4.4),
│                     │  tool budget, success criteria
└─────────────────────┘
  │
  ▼  v4.4 NEW NODE
┌─────────────────────────────────────┐
│  planner_critique_node              │  CoVe (Dhuliawala 2023)
│  same model drafts verification     │  - Does plan cover most-likely
│  questions ABOUT THE PLAN ITSELF    │    attacker techniques given
│  and answers them against the       │    evidence type?
│  case_init evidence summary.        │  - Does it have positive AND
│  Branches:                          │    negative for each artifact
│  - all-pass → comprehension_gate    │    family?
│  - any-fail → planner with hint     │  - Are success criteria
│                                     │    measurable?
└─────────────────────────────────────┘
  │
  ▼  (fanout — 4 parallel executor branches; v4.3 echoes preserved)
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ vol_executor │ │ hay_executor │ │ pls_executor │ │ mft_executor │
│ ECHO PLAN    │ │ ECHO PLAN    │ │ ECHO PLAN    │ │ ECHO PLAN    │
│ (Qwen3)      │ │ (GLM-4.5-Air)│ │ (Qwen3)      │ │ (GLM-4.5-Air)│
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
  │                │                │                │
  └────────────────┴───┬────────────┴────────────────┘
                       ▼
            ┌──────────────────────┐
            │  comprehension_gate  │  v4.3 — executor parse-consensus
            │  (executors agree    │  Catches plan-comprehension drift
            │   on what plan said) │  (does NOT catch wrong plan; that's
            │                      │   planner_critique_node's job)
            └──────────────────────┘
                       │
        CONSENSUS      │       MISMATCH
            │          │            │
            ▼          ▼            ▼
   ┌──────────────────────┐    ┌──────────────────────┐
   │  executor_work       │    │  clarify_node        │
   │  (run forensic       │    │  (replan with        │
   │   tool calls in      │    │   conflict surfaced  │
   │   microsandbox VMs)  │    │   as a hint)         │
   │  + Pydantic-AI       │    └──────────────────────┘
   │    args_validator    │              │
   │    (v4.4 — rejects   │              ▼
   │    invented flags)   │      (loop back to planner)
   │  + 3-layer immutable │
   │    defense (v4.3)    │
   └──────────────────────┘
            │
            ▼  v4.4 NEW NODE
┌─────────────────────────────────────┐
│  pivot_node (cheap follow-up)       │  Real DFIR investigations pivot
│  ONE Hypothesis added on the basis  │  8-15 times per case. v4.3's
│  of an executor finding (e.g.       │  replan_max=3 was a research
│  weird parent → check parent hash). │  budget. v4.4 distinguishes
│  Bounded `pivot_max=15`.            │  PIVOT (cheap, single Hypothesis
│  Re-enters executor_work; does NOT  │  added) from REPLAN (expensive,
│  re-enter planner.                  │  full plan rewrite).
└─────────────────────────────────────┘
            │
            ▼
            ┌──────────────────────┐
            │  quorum_node         │  Apply VerifierStrategy.
            │  → VerdictStatus     │  Jaccard ≥0.80 on artifact_paths.
            │                      │  Identical mitre_technique
            │                      │  (sub-technique-aware, v4.4).
            │                      │  Reject Findings with
            │                      │  artifact_classes < 2 (v4.4).
            └──────────────────────┘
                       │
        VERIFIED       │       CONTESTED        UNVERIFIABLE / DRAFT_CLOUD
            │          │            │                │
            ▼          ▼            ▼                ▼
       finding_     interrupt   replan_node     finding_
       VERIFIED_*  (HITL)        (loop back     UNVERIFIABLE
       (HMAC)                    to planner;    or remains DRAFT
                                 max 3, then
                                 unverifiable_
                                 finalize_node
                                 + interrupt())
                                 — v4.4
```

**Architecture caption (v4.4):** Checkpoint granularity = super-step boundary. Mid-executor crashes resume from the planner output, not partial executor results — acceptable for forensic re-run determinism. Demo `kill -9` happens between super-steps for a clean visible resume. Three-layer immutability defense (Claude Code PreToolUse hook + LangGraph executor_work wrapper + Microsandbox read-only mount) ensures the evidence-vault guarantee holds in all three modes — **with the v4.4 caveat that Layer 1 is best-effort given anthropics/claude-code issues #33106 (PreToolUse `permissionDecision: "deny"` not enforced for MCP server tools) and #37210 (deny ignored for Edit tool); the architectural guarantee is carried by Layers 2 and 3.** A CI smoke test in week 2 verifies the installed Claude CLI version actually denies a sample MCP write, so version drift surfaces before the demo. Sqlite checkpointer runs `PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;` (v4.4) so kill -9 between sqlite txn-commit and fsync doesn't lose the most recent super-step.

The graph is checkpointed at every super-step via `SqliteSaver`. `interrupt()` is used for CONTESTED findings exceeding `replan_max=3` AND for `unverifiable_finalize_node` so the analyst sees an explicit "agent gave up" beat (v4.4) rather than a quietly-stuck CONTESTED.

### Typed schemas (load-bearing, define in week 1) — v4.4 hardened

```python
# verdict/schemas/plan.py — Beaver owns
class Hypothesis(BaseModel):
    """A claim the investigation is testing — positive OR negative.
    v4.4: validators enforce non-degenerate negatives."""
    id: str                                   # e.g. "h_proc_inject_001"
    polarity: Literal["positive", "negative"] # negative = "evil is NOT here"
    mitre_technique: str | None               # e.g. "T1055.012" (sub-technique-aware, v4.4)
    artifact_families: list[ArtifactFamily]   # which tool families confirm/refute
    success_criteria: str                     # natural-language, judged by quorum

    @field_validator("mitre_technique")
    def _sub_technique_aware(cls, v):
        """v4.4: regex permits T#### or T####.### sub-technique form.
        Empty string and bare 'T1055' (when sub-technique is known) get
        flagged by the planner_critique_node, not the schema."""
        if v is None: return v
        if not re.match(r"^T\d{4}(\.\d{3})?$", v):
            raise ValueError(f"MITRE technique must match T#### or T####.###")
        return v

    @model_validator(mode="after")
    def _negative_hypothesis_quality(self):
        """v4.4: a negative hypothesis must be SPECIFIC. Schema-level
        rejection of degenerate negatives ('evil is not a banana' satisfies
        polarity=negative but proves nothing)."""
        if self.polarity == "negative":
            if self.mitre_technique is None:
                raise ValueError("negative hypothesis must name a MITRE technique it's ruling out")
            if not self.artifact_families:
                raise ValueError("negative hypothesis must name artifact families that would refute it")
            if any(banned in self.success_criteria.lower()
                   for banned in ["cosmic", "alien", "nothing", "not relevant", "n/a"]):
                raise ValueError("negative hypothesis success_criteria looks degenerate")
        return self


class InvestigationPlan(BaseModel):
    """Output of planner_node. Identical bytes-on-the-wire to every executor.
    REQUIRED: at least one negative hypothesis per investigation. v4.4 also
    requires the planner_critique_node verdict before fanout."""
    plan_id: str
    case_id: str
    positive_hypotheses: list[Hypothesis]     # min 1
    negative_hypotheses: list[Hypothesis]     # min 1, REQUIRED
    tool_budget: int                          # max executor calls
    pivot_budget: int = 15                    # v4.4: cheap follow-ups
    replan_budget: int = 3                    # v4.4 explicit
    success_criteria: str
    # v4.3 + v4.4 — comprehension echoes plus critique verdict
    comprehension_echoes: list["PlanComprehensionEcho"] = []
    comprehension_consensus: bool = False
    critique_verdict: "PlannerCritiqueVerdict" | None = None  # v4.4


class PlannerCritiqueVerdict(BaseModel):
    """v4.4 — output of planner_critique_node. Records the CoVe questions
    the planner asked ABOUT ITS OWN PLAN and the answers it gave against
    the evidence summary. The verdict gates whether fanout begins."""
    plan_id: str
    questions_and_answers: list[tuple[str, str]]
    failed_questions: list[str]                # if non-empty, replan
    overall_pass: bool
    timestamp_utc: datetime


# verdict/schemas/finding.py — Beaver + KP own jointly
class ArtifactClass(str, Enum):
    """v4.4 — multi-artifact corroboration vocabulary.
    SANS FOR500 doctrine: no single artifact proves execution."""
    PREFETCH = "prefetch"
    AMCACHE = "amcache"
    SHIMCACHE = "shimcache"
    EVTX_4688 = "evtx_4688"                 # Process Creation
    SYSMON_1 = "sysmon_1"                   # Sysmon ProcessCreate
    NETWORK = "network"                     # netscan, conn logs
    REGISTRY_RUN = "registry_run"
    TASK_SCHEDULER = "task_scheduler"
    WMI_SUBSCRIPTION = "wmi_subscription"
    MFT = "mft"                             # $MFT, $J/UsnJrnl
    PROCESS_MEMORY = "process_memory"       # malfind/RWX/hollowed
    YARA_HIT = "yara_hit"
    SIGMA_HIT = "sigma_hit"


class CaveatID(str, Enum):
    """v4.4 — Tier-1 caveats from project's agent-config/MEMORY.md."""
    AMCACHE_LASTMODIFIED_NOT_EXEC = "amcache_lastmodified_neq_execution"
    SHIMCACHE_ORDER_CHANGED_WIN81 = "shimcache_order_lru_pre81_insertion_post81"
    PREFETCH_SSD_DISABLED = "prefetch_disabled_on_ssd_or_gpo"
    MFT_SI_STOMPABLE = "mft_si_timestomp_use_fn"
    USNJRNL_WRAPS = "usnjrnl_wraps_treat_gaps_carefully"
    LOGON_TYPE_3_VS_10 = "evtx_4624_type3_network_neq_type10_rdp"
    SYSMON_PROCESSGUID_OVER_PID = "sysmon_processguid_correlation_key_not_pid"


class Finding(BaseModel):
    finding_id: str
    case_id: str
    plan_id: str
    hypothesis_ids: list[str]
    # v4.4 — multi-artifact corroboration enforced at schema layer
    artifact_paths: list[Path] = Field(min_length=2)
    artifact_classes: list[ArtifactClass] = Field(min_length=2)
    mitre_technique: str | None
    evidence_hashes: dict[Path, str]          # SHA-256 per artifact
    rationale: str
    status: VerdictStatus
    contested_reasons: list[str] = []
    # v4.4 — caveats acknowledged when relevant artifact class is cited
    caveats_acknowledged: list[CaveatID] = []

    @model_validator(mode="after")
    def _execution_claims_need_two_classes(self):
        """v4.4 — SANS FOR500 doctrine: execution claim requires ≥2 distinct
        artifact classes, ideally drawn from {Prefetch, Amcache, ShimCache,
        EVTX_4688, Sysmon_1, Network}."""
        is_exec_claim = any(
            self.mitre_technique and self.mitre_technique.startswith(prefix)
            for prefix in ("T1059", "T1106", "T1204", "T1218", "T1543", "T1547")
        )
        if is_exec_claim:
            distinct = set(self.artifact_classes)
            if len(distinct) < 2:
                raise ValueError(
                    f"execution claim {self.mitre_technique} needs ≥2 artifact classes; "
                    f"got {distinct}"
                )
        return self

    @model_validator(mode="after")
    def _amcache_caveat_required(self):
        """v4.4 — citing Amcache requires acknowledging LastModified ≠ exec."""
        if ArtifactClass.AMCACHE in self.artifact_classes:
            if CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC not in self.caveats_acknowledged:
                raise ValueError(
                    "Finding cites Amcache but does not acknowledge the "
                    "LastModified ≠ execution caveat (FOR500)"
                )
        return self


# verdict/schemas/ledger.py — Tim owns
class LedgerEntry(BaseModel):
    """Append-only HMAC-signed JSONL row. Three explicit ID hierarchies.
    v4.3: case_id / langfuse_trace_id / langgraph_checkpoint_id.
    v4.4: per-output-file hashes + examination-environment metadata
    (NIST SP 800-86 §5.1.2 + §5.1.4)."""
    entry_id: str                                 # ULID
    case_id: str                                  # ROOT — eternal for case lifetime
    finding_id: str | None
    event_type: Literal[
        "case_init", "tool_call", "finding", "approval", "rejection",
        "mode_lock", "comprehension_check",
        "critique_verdict",        # v4.4
        "pivot",                   # v4.4
        "exhausted_replan",        # v4.4
    ]
    timestamp_utc: datetime

    # Mode lock (v4.3) — set at case_init, immutable thereafter
    mode_at_case_init: Mode
    verifier_strategy_used: str

    # Langfuse cross-references (v4.3)
    langfuse_session_id: str
    langfuse_trace_id: str
    langfuse_root_span_id: str
    langfuse_leaf_span_ids: list[str]

    # LangGraph cross-references (v4.3)
    langgraph_thread_id: str
    langgraph_checkpoint_id: str

    # v4.4 — examination-environment metadata for chain-of-custody
    microsandbox_version: str | None = None
    rootfs_sha256: str | None = None
    tool_version: str | None = None              # e.g. "vol3-2.10.0"
    kernel_version: str | None = None            # `uname -r` inside microvm

    # Ledger chain integrity
    payload: dict
    payload_redactions: list[str] = []
    # v4.4 — per-output-file hashes (NIST SP 800-86)
    output_files_sha256: dict[str, str] = {}     # path → sha256
    prev_entry_hash: str
    hmac_sig: str
```

### Finding verdict status enum

```python
class VerdictStatus(str, Enum):
    DRAFT = "draft"
    DRAFT_CLOUD = "draft_cloud"
    VETTED_CLOUD = "vetted_cloud"
    VERIFIED_AIRGAP = "verified_airgap"
    VERIFIED_DUAL = "verified_dual"
    CONTESTED = "contested"
    UNVERIFIABLE = "unverifiable"   # v4.4: now ALSO emitted by unverifiable_finalize_node
                                    # after replan_max=3 is hit, so the analyst
                                    # sees explicit "agent gave up" rather than
                                    # quietly-stuck CONTESTED
    APPROVED = "approved"
    REJECTED = "rejected"
```

**Honesty about cloud-only mode (carried from v4.2, hardened in v4.4):** `VETTED_CLOUD` is *not* the same epistemic claim as `VERIFIED_AIRGAP` or `VERIFIED_DUAL`. v4.4 also requires the n=3 samples to be *truly diverse* (temperature 0.7, three case_id-derived seeds; deterministic-temp-0 collapses to n=1). Documented in the accuracy report as a separate column.

---

## Lock-In Decisions (v4.4 — unchanged from v4.3)

Stack table is identical to v4.3. The v4.4 fixes are at the *prompt*, *schema*, *graph topology*, and *playbook* layers, not the dependency layer.

---

## Key Findings (v4.3 1-14, v4.4 15-26)

(Items 1-14 carried verbatim from v4.3 — see prior version for full text.)

15. **(v4.4 BLOCKER) PreToolUse `permissionDecision: "deny"` is buggy for MCP server tools and the Edit tool.** Open issues anthropics/claude-code#33106 ("PreToolUse hook permissionDecision 'deny' not enforced for MCP server tool calls") and #37210 ("PreToolUse hook deny ignored for Edit tool") are live. The entire SIFT toolset is wired as MCP tools through FastMCP + microsandbox-mcp, so this is not a corner case — it's the primary path. **Mitigation:** v4.4 reframes Layer 1 as best-effort prompt-level deterrent that ALSO logs the attempt to the audit ledger; the architectural guarantee is carried by Layer 2 (LangGraph `executor_work` wrapper) and Layer 3 (Microsandbox read-only mount). Tim adds a CI smoke test in week 2 that verifies the installed Claude CLI version's PreToolUse deny actually blocks an MCP write — fails the build if not, so version drift surfaces before the demo. README caveat: "Layer 1 depends on Anthropic CLI versions ≥X.Y.Z; layers 2 and 3 are version-independent."

16. **(v4.4 BLOCKER) n=3 self-consistency with deterministic seeds collapses to n=1.** v4.3 line 53 ("n=3 samples from Claude with deterministic seeds") is broken: same seed + same temperature + same prompt = three identical outputs. Wang et al. 2022 (arXiv:2203.11171) requires *diverse* reasoning paths via temperature > 0. Line 313's "deterministic temperature/seed control" confirms the design intent is determinism, which defeats the technique. **Mitigation:** v4.4 derives three blake3-keyed seeds per case (`derive_seeds(case_id)` → `(seed_a, seed_b, seed_c)`) at temperature=0.7. Reproducibility-with-diversity: re-running the case yields the same three samples (audit-friendly), but the three samples differ from each other (verifier-friendly). Switch to Universal Self-Consistency (Chen et al. 2023, arXiv:2311.17311) for free-form rationale judging.

17. **(v4.4 BLOCKER) No artifact-pair corroboration rule in the `Finding` schema.** v4.3's `artifact_paths: list[Path]` accepts `len() == 1`. SANS FOR500 doctrine: no single artifact proves execution. Project's own `agent-config/MEMORY.md` codifies this; v4.3 doesn't enforce. **Mitigation:** `artifact_paths: Field(min_length=2)`, new `artifact_classes: list[ArtifactClass]` field with `min_length=2`, model validator enforces ≥2 distinct artifact classes for execution-class MITRE techniques (T1059/T1106/T1204/T1218/T1543/T1547). Quorum_node rejects sub-threshold findings as CONTESTED. Single biggest credibility win in the document.

18. **(v4.4 BLOCKER) No tool-sequencing playbook for the planner.** v4.3 leaves tool ordering to the LLM. SANS teaches deterministic first-move sequences per evidence type (memory: `windows.info` → `pslist` → `psscan` → divergence check → `pstree` → `cmdline` → `dlllist` → `malfind` → `netscan` → ...; disk: hash verify → `mmls` → `fsstat` → `fls -r` → MFT → registry → Prefetch → EVTX → plaso last → bulk_extractor; triage: registry first → Prefetch/Amcache/ShimCache → EVTX → MFT → carving). **Mitigation:** ship `verdict/playbooks/{memory,disk,triage}.yml` ported from project `agent-config/PLAYBOOK.md`. Loaded into planner system prompt at case_init based on detected evidence type. Without this the planner reinvents methodology every case.

19. **(v4.4 BLOCKER) Tier-1 examiner caveats from project's `agent-config/MEMORY.md` not encoded in v4.3.** Seven caveats — Amcache `LastModified` ≠ execution; ShimCache LRU (≤Win8) vs insertion-order (≥Win8.1); Prefetch SSD/GPO disable; `$MFT $SI` stompable, prefer `$FN`; UsnJrnl wraps; EVTX 4624 Type 3 ≠ Type 10; Sysmon EID 1 ProcessGuid > PID — are exactly the misreads Rob Lee uses to spot a fake examiner. **Mitigation:** v4.4 ships `verdict/prompts/examiner_caveats.md` as a system-prompt include for every executor; `Finding.caveats_acknowledged: list[CaveatID]` field; `_amcache_caveat_required` validator rejects an Amcache-citing Finding that doesn't acknowledge the caveat. Schema-level enforcement; cannot be skipped by sloppy prompt-engineering.

20. **(v4.4 BLOCKER) DKOM/T1014 detection pattern is missing despite the project shipping `vol_pslist` + `vol_psscan` deliberately for it.** Project `CLAUDE.md` is explicit: "the `vol_pslist` + `vol_psscan` pair is deliberately redundant — pslist walks the active list, psscan signature-scans EPROCESS pool memory; divergence between the two is the textbook DKOM/T1014 (Rootkit) signature." v4.3's tool list mentions only `pslist` and never wires the divergence check. **Mitigation:** v4.4 adds `psscan` to the tool surface and to `playbooks/memory.yml`: "ALWAYS run pslist + psscan; if `set(psscan_pids) - set(pslist_pids)` is non-empty, emit `Hypothesis(mitre_technique='T1014', confidence=high, artifact_classes=[PROCESS_MEMORY])`." This is a paragraph of code, a 30-second demo segment, and the single most quotable rootkit detection pattern in memory forensics.

21. **(v4.4 SHOULD-FIX) Cross-family "independence" is undocumented.** v4.3 line 360 asserts "different model family → independent failure modes" without citation. Qwen3 (36T tokens, web + Qwen2.5 synthetic) and GLM-4.5 (23T tokens, web + book + paper + social + code) train on overlapping web corpora; both use MoE/GQA/RoPE/RMSNorm. Khan et al. 2025 (arXiv:2509.05396) explicitly: correlated errors don't average away. **Mitigation:** v4.4 softens to "partial independence — uncorrelated on stylistic/refusal variance, correlated on shared web-corpus factual mistakes." KP measures empirical disagreement correlation in week 4 across the 50 ground-truth findings; the number ships in the accuracy report. Honest claim is itself a credibility signal.

22. **(v4.4 SHOULD-FIX) Negative-hypothesis schema enforcement is leaky.** Pydantic accepts `Hypothesis(polarity="negative", success_criteria="The system is not infected with cosmic rays")` — schema-valid, useless. **Mitigation:** v4.4 adds `_negative_hypothesis_quality` model_validator (deny-list of degenerate phrasings, MITRE technique required, artifact_families non-empty). Add 3-5 few-shot examples in the planner system prompt. Inspect AI scorer `negative_hypothesis_quality` fails CI if any case in the eval suite emits a Pydantic-valid but quality-score < 0.5 negative.

23. **(v4.4 SHOULD-FIX) `comprehension_gate` solves executor drift, not the wrong-plan failure mode.** v4.3 line 297 names the failure ("successfully-quorumed wrong plan") and claims the negative-hypothesis requirement defends against it. The gate catches *executor disagreement on what the plan said*; it doesn't catch *the planner wrote the wrong plan*. **Mitigation:** v4.4 adds `planner_critique_node` between `planner_node` and `comprehension_gate`. Same model drafts CoVe questions ABOUT THE PLAN ITSELF (Dhuliawala 2023, arXiv:2309.11495 — 50-70% hallucination reduction empirically) and answers them against the case_init evidence summary; failed questions route back to planner with the failed question as a hint. Anthropic's multi-agent research system uses a separate verification subagent for the same purpose. Cost: one extra planner round-trip (~3-5s) but kills the failure mode at its source.

24. **(v4.4 SHOULD-FIX) Tool-call argument hallucination is unmodeled.** Microsandbox makes evidence read-only; it does not validate that `vol3 --plugin=windows.malfind --pid=99999` is a real PID or that a plaso filter regex is syntactically valid. The "Reasoning Trap" (arXiv:2510.22977, ICLR 2025/26) shows reasoning-enhanced models hallucinate tool args MORE as task performance grows. Microsandbox running `vol3 --foo bar` returns nonzero exit + empty stdout; quorum sees zero artifacts from both executors and reports a false-negative VERIFIED ("no malware found"). **Mitigation:** Pydantic-AI `args_validator` per tool wrapper, runs *before* `microsandbox.spawn`. For vol3: validate plugin against allow-list (parse `vol3 --help` once at startup, hash-pin), `--pid` is positive int, reject unknown flags. For plaso: pre-validate filter expression with `psteal --validate-filter` in an ephemeral sandbox. For Hayabusa: validate timeline-flag combinations against the matrix in playbooks. Failure raises `ModelRetry`, bounded by `tool_arg_retry_max=2`, then UNVERIFIABLE (failure to invoke ≠ model disagreement).

25. **(v4.4 SHOULD-FIX) `replan_max=3` termination semantics undefined; budget too small for real DFIR.** Two distinct issues. (a) v4.3 line 125 says `interrupt()` fires on exhaustion but line 577 says "bounded by `replan_max=3`" — what happens at iteration 4 is ambiguous. Bounded-recovery literature distinguishes fail-stop (terminate) from escalate (HITL handoff); v4.3's quietly-stuck CONTESTED is neither. (b) Real investigations pivot 8-15 times per case (parent → check parent hash → VirusTotal → ATT&CK → re-query EVTX in new time window). 3 is a research-paper budget. **Mitigation:** v4.4 distinguishes PIVOT (cheap, single-Hypothesis follow-up, `pivot_max=15`, re-enters executor_work) from REPLAN (expensive, full plan rewrite, `replan_max=3`, re-enters planner). At replan iteration 4: route to `unverifiable_finalize_node` which writes `Finding(status=UNVERIFIABLE)`, writes `LedgerEntry(event_type="exhausted_replan")`, calls `interrupt()`. Analyst can `update_state` and resume, or accept UNVERIFIABLE. Demo gets a clean "show what happens when even the agent gives up" beat — Rob Lee will respect it.

26. **(v4.4 SHOULD-FIX) MITRE techniques should be sub-technique-aware.** `mitre_technique: str | None` accepts `"T1055"` — analyst-tier, not senior-tier. Malfind RWX without backing PE → `T1055.002`; hollowed image → `T1055.012`; reflective DLL → `T1055.001`. Same applies to `T1547.001` (Run keys) vs parent `T1547`, `T1543.003` (Windows Service) vs parent `T1543`. **Mitigation:** regex validator `^T\d{4}(\.\d{3})?$`. Planner prompt instructs: "Always select the most specific sub-technique your evidence supports; if ambiguous, emit two hypotheses." KP's ground-truth set encodes sub-techniques.

27. **(v4.4 SHOULD-FIX) Logical-extract chain-of-custody incomplete per NIST SP 800-86.** v4.3 hashes input image and stdout per call. NIST SP 800-86 §5.1.2 requires logical-extract preservation: when `bulk_extractor` writes 12 output files, each is evidence with its own hash. SWGDE 18-F-001 §4.5 requires examination-environment preservation; Microsandbox destruction violates this unless the rootfs is content-addressed and pinned. **Mitigation:** v4.4 expands `LedgerEntry` with `output_files_sha256: dict[str, str]`, `microsandbox_version`, `rootfs_sha256`, `tool_version`, `kernel_version`. Hash every file under `output_dir`, not just stdout.

28. **(v4.4 SHOULD-FIX) Plaso/Hayabusa not split into extract+filter phases.** v4.3 wraps `log2timeline.py` + `psort.py` as one MCP tool. Real workflow: extract once → filter many times by time window from prior findings. **Mitigation:** split into `plaso_extract(image, output_dir) -> .plaso_path` and `psort_filter(plaso_path, time_range, filter_expr) -> csv`. Same for Hayabusa: `hayabusa_csv_timeline(evtx_dir) -> events.csv` then `hayabusa_filter(csv, sigma_level) -> hits.csv`. Planner picks the time window from a previous finding (via pivot_node), then filters.

29. **(v4.4 SHOULD-FIX) Timezone discipline not enforced.** Project `MEMORY.md`: "All timestamps UTC, ISO-8601, trailing Z." v4.3 declares `datetime` types but doesn't enforce. plaso/MFTECmd/EVTX default UTC; RECmd and exiftool can return local TZ. Mixed-TZ findings read as amateur. **Mitigation:** Pydantic field validator on every datetime: must be tzaware, must be `tzinfo == UTC`. Explicit `--timezone UTC` flag on every tool wrapper that supports it. One decorator, zero excuses.

30. **(v4.4 SHOULD-FIX) Hunt Evil process baseline absent.** SANS Hunt Evil poster pitch: "here's what `svchost.exe` should look like — parent `services.exe`, path `%SystemRoot%\System32`, signed by Microsoft, multiple instances." A `svchost.exe` whose parent is `cmd.exe` is evil. v4.3 has no encoding. **Mitigation:** ship `verdict/knowledge/hunt_evil.yml` keyed by process name with expected parent / path / instance count / start time / signing. Inject into malfind/pslist executor prompts. New `process_baseline` Hypothesis type. Single best demo shot: agent flags pseudo-svchost masquerade by parent-process anomaly (`scvhost.exe`, parent=`cmd.exe`) — straight from the poster.

31. **(v4.4 SHOULD-FIX) LOLBin discrimination guidance missing.** Project `MEMORY.md`: "LOLBins to check first: rundll32, regsvr32, mshta, wmic, certutil, bitsadmin." v4.3's `windows-triage` skill is named only — no content. Without LOLBin cmdline-shape catalog the planner asks the LLM to *recall* patterns from training data — fragile. **Mitigation:** each `verdict-skills/<name>/KNOWLEDGE.md` ships LOLBin cmdline-shape catalog (LOLBAS project — lolbas-project.github.io). Executor reading `vol3.cmdline` cross-references against this; emits `T1218` sub-technique on match.

32. **(v4.4 NICE-TO-HAVE) agentskills.io tool-affordance contract unspecified.** v4.3 doesn't say *which tools each skill expects*. All 12 tool wrappers stay in context whether or not the skill needs them — ~30K tokens of overhead in air-gap. **Mitigation:** each `verdict-skills/<name>/SKILL.md` frontmatter declares `required_tools` + `optional_tools`. Gateway filters MCP tool list exposed to model on skill activation.

33. **(v4.4 NICE-TO-HAVE) Air-gap planner context budget uncalibrated.** Qwen3 256K context minus skills + hooks + plan + 4 echoes + tool docs is plausibly >40K tokens *before* evidence. Anthropic's "Effective context engineering" piece warns effective context is much smaller than advertised. **Mitigation:** document `system_prompt_budget` per role (planner ≤30K, executor ≤20K, critic ≤15K). Week-2 CI assertion that token-counts rendered prompts against budget and fails over. Use agentskills.io progressive-disclosure pattern in executor role.

34. **(v4.4 NICE-TO-HAVE) Single-writer fanout claim deserves a unit test.** v4.3 says reducer pattern handles multi-executor fanout; LangGraph fanout/reducer issue #4026 confirms this is exactly the bug class people hit. **Mitigation:** Beaver writes one unit test in week 3 — fan out 4 executors with deliberately racing reducer (each sleeps 0-500ms randomized), assert final state contains all 4 in deterministic order. Pin LangGraph version that passes. Document in `docs/CHECKPOINTING.md`.

35. **(v4.4 NICE-TO-HAVE) Sqlite kill-9 durability uncalibrated.** SqliteSaver writes are durable iff WAL + fsync on commit. Demo's "kill -9 between super-steps" can lose a super-step between txn-commit and fsync. **Mitigation:** explicit `PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;` on SqliteSaver connection. Chaos test: 100 cases, kill -9 between super-steps, assert zero loss.

36. **(v4.4 NICE-TO-HAVE) Adversarial-reasoning planner prompt absent.** "Find Evil!" implies attacker-mindset reasoning. v4.3's planner emits hypotheses; doesn't explicitly red-team. **Mitigation:** add `negative_hypothesis` of shape "if I were the attacker, where would I hide?" — Scheduled Tasks `\Microsoft\Windows\` namespace, WMI event subscriptions, IFEO debugger keys (project MEMORY.md persistence top-5).

37. **(v4.4 NICE-TO-HAVE) Win11/macOS/Linux/ESXi explicitly out of scope.** v4.3's 12 tools are Windows-shaped. Honeynet ransomware is Windows. Acceptable scope cut for v1; *say so* in `docs/SCOPE.md`. "v1 scope = Windows DFIR; macOS / Linux / Win11-specific (SRUM/ETW/Cortana) / ESXi = v2 roadmap."

38. **(v4.4 NICE-TO-HAVE) Case isolation vs SGLang RadixAttention deserves a paragraph.** RadixAttention shares prefix KV cache across cases by design — that's the throughput win. From a forensic-credibility angle this isn't a leak (prefix is system prompt, not case data), but a SANS judge will ask. **Mitigation:** one paragraph in `docs/CASE_ISOLATION.md`: "case_id is in the user message, not the system prompt; case-specific tokens never enter the shared prefix; we audited that no case-specific spans share with other cases."

---

## Per-Tool Deep Dives (deltas from v4.3)

### Volatility 3 (v4.4 expansion)

v4.3 lists `vol3 (pslist, malfind, netscan)`. **v4.4 expands the wrapped-plugin list to 11 plugins** matching the project's existing Rust MCP server: `windows.info`, `windows.pslist`, `windows.psscan`, `windows.pstree`, `windows.cmdline`, `windows.dlllist`, `windows.malfind`, `windows.netscan`, `windows.svcscan`, `windows.handles`, `windows.callbacks`. The pslist+psscan pair is wired with explicit divergence detection per BLOCKER-4. Volatility Foundation Command Reference is the ordering authority.

### Plaso (v4.4 split)

Two MCP tools, not one:
- `plaso_extract(image: Path, output_dir: Path) -> PlasoStorageHandle` — wraps `log2timeline.py`, returns `.plaso` storage path. Expected wall clock: 5-30 min depending on image size.
- `psort_filter(handle: PlasoStorageHandle, time_range: TimeRange, filter_expr: str | None) -> Path` — wraps `psort.py`, fast (seconds), filters and outputs CSV.

### Hayabusa (v4.4 split)

Same pattern:
- `hayabusa_csv_timeline(evtx_dir: Path, output: Path) -> Path` — entry verb per Hayabusa README.
- `hayabusa_filter(csv: Path, sigma_level: SigmaLevel, time_range: TimeRange | None) -> Path` — analyst-driven filtering.

### MITRE ATT&CK navigator pairing (v4.4)

For each Volatility plugin, document the MITRE techniques most likely to surface from its output. KP's ground-truth set in week 4 verifies the planner picks sub-techniques (`T1055.012` not `T1055`).

### Hunt Evil baseline knowledge (v4.4 — new)

`verdict/knowledge/hunt_evil.yml` keyed by process name. Schema:
```yaml
- process: svchost.exe
  expected_parent: services.exe
  expected_path_glob: "%SystemRoot%\\System32\\svchost.exe"
  expected_signing: "Microsoft Windows"
  multiple_instances: true
- process: lsass.exe
  expected_parent: wininit.exe
  expected_path_glob: "%SystemRoot%\\System32\\lsass.exe"
  expected_signing: "Microsoft Windows"
  multiple_instances: false
# ... csrss, winlogon, services, wininit, explorer, smss, etc.
```
Loaded at planner_node. Hypothesis type `process_baseline_anomaly` triggered by parent/path/signing mismatch.

---

## Build Plan (v4.4 — week-by-week deltas)

**Week 1 (May 2-8) — Foundations + Tier-1 caveats + playbooks (v4.4 additions).**
- v4.3 tasks unchanged (SIFT VM, Microsandbox, SGLang+Qwen3+GLM, FastMCP gateway skeleton, LangGraph stub, Inspect AI hello-world, Langfuse self-host).
- **(v4.4) KP authors `verdict/playbooks/{memory,disk,triage}.yml`** by porting project `agent-config/PLAYBOOK.md`. Playbooks load into planner system prompt at case_init based on detected evidence type.
- **(v4.4) KP authors `verdict/prompts/examiner_caveats.md`** from project `agent-config/MEMORY.md` Tier-1 list. System-prompt include for every executor.
- **(v4.4) KP authors `verdict/knowledge/hunt_evil.yml`** with the 8 canonical Windows process baselines from the SANS Hunt Evil poster.
- **(v4.4) Beaver implements `derive_seeds(case_id)`** + `CloudSelfConsistency` at temperature=0.7, blake3-keyed three seeds (BLOCKER fix).

**Week 2 (May 9-15) — Tool surface + schema hardening + critique node + args validators.**
- v4.3 tasks unchanged (12 SIFT tool wrappers as MCP tools, microsandbox per-tool ephemeral VMs, PreToolUse hook, PostToolUse audit JSONL, Plan-then-Execute LangGraph refactor, Pydantic-AI typing, Langfuse instrumentation).
- **(v4.4) Tim adds CI smoke test** verifying installed Claude CLI version's PreToolUse `permissionDecision: "deny"` actually blocks an MCP tool write. Fails build if not. Layer 1 reframed in README as best-effort given anthropics/claude-code#33106 + #37210; architectural guarantee on Layers 2+3.
- **(v4.4) Tim wires `LangGraph executor_work wrapper` (Layer 2)** to validate typed tool args against deny-rule list regardless of which model called. Fires in all three modes including air-gap.
- **(v4.4) Tim wires per-output-file SHA-256** in `LedgerEntry.output_files_sha256` and examination-environment metadata (`microsandbox_version`, `rootfs_sha256`, `tool_version`, `kernel_version`). NIST SP 800-86 alignment.
- **(v4.4) Beaver implements `planner_critique_node`** (CoVe) between planner and comprehension_gate. Cost ~3-5s/plan; kills wrong-plan failure mode at source.
- **(v4.4) Beaver implements per-tool Pydantic-AI `args_validator`** for vol3, plaso, Hayabusa, MFTECmd, etc. `tool_arg_retry_max=2`, then UNVERIFIABLE.
- **(v4.4) Beaver splits plaso into `plaso_extract` + `psort_filter`**; same for Hayabusa.
- **(v4.4) KP adds `Finding._execution_claims_need_two_classes` + `_amcache_caveat_required` validators** to schemas.
- **(v4.4) KP authors LOLBin cmdline-shape catalog** in `verdict-skills/windows-triage/KNOWLEDGE.md` from LOLBAS project.

**Week 3 (May 16-22) — Verifier strategies + TSI + checkpointing + pivot_node.**
- v4.3 tasks unchanged (cross-engine verifier, TSI enrichment, SqliteSaver checkpointer, trace_id ↔ ledger cross-link, comprehension_gate, mode-lock, reverify command).
- **(v4.4) Beaver implements `pivot_node`** between executor_work and quorum_node; `pivot_max=15`. Distinct from replan_node (`replan_max=3`).
- **(v4.4) Beaver implements `unverifiable_finalize_node`** at replan iteration 4 → `Finding(status=UNVERIFIABLE)` + `LedgerEntry(event_type="exhausted_replan")` + `interrupt()`. Demo gets the "agent gave up" beat.
- **(v4.4) Beaver sets `PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;`** on SqliteSaver. Adds chaos test (100 cases, kill -9 between super-steps, zero loss assertion).
- **(v4.4) Beaver adds the LangGraph fanout/reducer race test** — 4 executors with randomized 0-500ms sleeps, deterministic-order assertion. Pin LangGraph version.
- **(v4.4) Tim writes `docs/CASE_ISOLATION.md`** explaining SGLang RadixAttention prefix-cache vs case-specific tokens.

**Week 4 (May 23-29) — Skills, hooks, evals, sub-technique mapping.**
- v4.3 tasks unchanged (6 agentskills.io skills, forensic-discipline hook at SessionStart, Inspect AI regression, KP's three per-mode scorers, ground-truth 50 indicators, LANGFUSE_TRACE_ID exposure, demo case engineering).
- **(v4.4) KP encodes MITRE sub-techniques in ground-truth set.** Inspect AI scorer `mitre_subtechnique_precision` — fails if planner emits parent technique when sub-technique was determinable.
- **(v4.4) KP adds Inspect AI scorer `negative_hypothesis_quality`** — fails CI on Pydantic-valid but quality-score < 0.5.
- **(v4.4) KP measures Qwen3-vs-GLM disagreement correlation** across the 50 ground-truth findings. Number ships in accuracy report. Honest claim is itself a credibility signal.
- **(v4.4) KP authors `Finding.caveats_acknowledged` test cases** — at least one ground-truth Finding per Tier-1 caveat, scorer verifies the agent actually acknowledged when relevant.
- **(v4.4) Each `verdict-skills/<name>/SKILL.md` declares `required_tools` + `optional_tools`** in frontmatter. Gateway filters MCP tool list on skill activation. Saves ~30K tokens of overhead in air-gap.
- **(v4.4) Each skill ships a `KNOWLEDGE.md`** with its domain catalog (LOLBins for windows-triage, Linux persistence shapes for linux-triage, etc.).

**Week 5 (May 30-Jun 5) — Mode autodetect + adapters + polish + scope statement.**
- v4.3 tasks unchanged (mode autodetect, --mode override, OpenCTI/Velociraptor MCP, Atropos, Telegram pager, Beaver's time-travel demo prep, Tim's Langfuse dashboard, HMAC approval).
- **(v4.4) Tim authors `docs/SCOPE.md`**: "v1 scope = Windows DFIR; macOS / Linux / Win11-specific (SRUM/ETW/Cortana) / ESXi = v2 roadmap." Explicit beats inferred.
- **(v4.4) Tim authors per-prompt-budget CI assertion**: planner ≤30K, executor ≤20K, critic ≤15K tokens of system prompt. Fails over budget.
- **(v4.4) Beaver verifies pivot/replan distinction in Honeynet ransomware demo case**: demo case engineered to exercise 8-12 pivots, 1-2 replans.

**Week 6 (Jun 6-14) — Demo & docs.**
- v4.3 tasks unchanged.
- **(v4.4) Demo sequence updated** (see Demo Sequence below). New beats: pslist/psscan DKOM divergence, Hunt Evil masquerade catch, agent-acknowledges-Amcache-caveat, agent-gives-up-explicit-UNVERIFIABLE.
- **(v4.4) `docs/SANS_JUDGE_CHECKLIST.md` shipped** as a checklist file the demo video is recorded against. Use as the scoring rubric for the team's own dry runs.

### Per-teammate v4.4 deltas (cumulative on top of v4.3)

**Tim — +~2 days on top of v4.3's +~4** (net +~6 from v4 baseline):
- Week 2: PreToolUse CI smoke test + LangGraph executor_work wrapper (Layer 2 of three-layer immutability).
- Week 2: per-output-file SHA-256 + examination-environment metadata in LedgerEntry.
- Week 3: `docs/CASE_ISOLATION.md`.
- Week 5: `docs/SCOPE.md` + per-prompt-budget CI assertion.

**Beaver — +~3 days on top of v4.3's +~4** (net +~7 from v4 baseline):
- Week 1: `derive_seeds(case_id)` + CloudSelfConsistency at temp=0.7 with three seeds.
- Week 2: `planner_critique_node` (CoVe).
- Week 2: per-tool Pydantic-AI `args_validator` framework.
- Week 2: split plaso/Hayabusa into extract+filter MCP tools.
- Week 3: `pivot_node` (`pivot_max=15`) + `unverifiable_finalize_node` + WAL/synchronous=FULL pragmas + fanout-race unit test.

**Haley — +~0 days** (already +~1 in v4.3). v4.4 doesn't touch SGLang/Qwen3/GLM client work. Heads up to verify SGLang serves both pslist and psscan plugin output cleanly in the same session (they do — same Volatility binary).

**KP — +~3 days on top of v4.3's +~1.5** (net +~4.5 from v4 baseline):
- Week 1: `verdict/playbooks/{memory,disk,triage}.yml` + `verdict/prompts/examiner_caveats.md` + `verdict/knowledge/hunt_evil.yml`.
- Week 2: `Finding._execution_claims_need_two_classes` + `_amcache_caveat_required` validators + LOLBin catalog.
- Week 4: MITRE sub-technique encoding in ground-truth + `mitre_subtechnique_precision` scorer + `negative_hypothesis_quality` scorer + Qwen3-vs-GLM disagreement-correlation measurement.

**Net change v4.4 only: +~8 teammate-days** on top of v4.3's +~7. Total v4 → v4.4: ~15 teammate-days. All rubric-aligned — every addition maps to one of: artifact-pair corroboration, named architectural pattern, audit-trail completeness, MITRE ATT&CK precision, hallucination defense, evidence-handling NIST alignment.

---

## Demo Sequence (5-minute video, v4.4)

Same case (Honeynet ransomware image). Three modes. Three verification stories. Two-pane recording: left=terminal, right=Langfuse trace tree.

**0:00–0:30 — Cold open + architecture flash.** Title card. One-sentence problem statement ("Protocol SIFT hallucinates"). 5-second architecture diagram flash showing **mode selector + Plan-then-Execute topology with planner_critique → comprehension_gate → fanout → pivot → quorum (v4.4 sequence)**. Cut to two-pane recording.

**0:30–1:30 — CLOUD-ONLY mode (60s).** Internet up, no GPU. `verdict --mode cloud`. Claude Code plans. **Three samples at temp=0.7 with three case_id-derived seeds** (v4.4 — narrate "different seeds, same case ID for reproducibility"). Langfuse pane: three sibling spans converging into vetting span. 2-of-3 agree on artifact set, 1 differs on registry path. `VETTED_CLOUD` for the agreed claim; `DRAFT_CLOUD` for the disputed registry path. Narrator: "same model shares failure modes; this is vetting, not verification." Show audit log entry with trace_id.

**1:30–3:00 — AIR-GAP mode (90s) — the hero shot.** Pull network cable on camera. Claude unreachable. Mode re-detects → `airgap`. `verdict --mode airgap`. Same case. Qwen3 plans. **Planner_critique_node fires (v4.4): same model drafts CoVe questions about its own plan, answers them against evidence summary, all-pass → advance.** Comprehension_gate fires (v4.3): all four executors echo parsed plan, gate validates consensus.

**Hero beat 1 — DKOM divergence (v4.4):** vol_executor runs both `pslist` and `psscan`. `set(psscan_pids) - set(pslist_pids)` is non-empty. Agent emits `Hypothesis(mitre_technique="T1014", confidence=high)`. Narrator: "this is the textbook DKOM signature — pslist walks the active list, psscan signature-scans pool memory; divergence = rootkit." Straight from Volatility Foundation's psxview lineage.

**Hero beat 2 — Hunt Evil masquerade catch (v4.4):** pslist returns `scvhost.exe` (typo) with parent `cmd.exe`. Agent cross-references `verdict/knowledge/hunt_evil.yml` — expected parent is `services.exe`, expected name is `svchost.exe`. Emits `Hypothesis(mitre_technique="T1036.005", confidence=high)`. Narrator: "this is the Hunt Evil poster's process baseline check, encoded in YAML."

**Hero beat 3 — Caveat acknowledgment (v4.4):** agent finds Amcache LastModified for `evil.exe`. Schema validator forces `caveats_acknowledged=[AMCACHE_LASTMODIFIED_NOT_EXEC]` because `ArtifactClass.AMCACHE` is in `artifact_classes`. Finding rationale text reads: "Amcache lists evil.exe at 2024-03-14T15:32Z; per FOR500, Amcache LastModified reflects catalog registration not execution time. Execution corroborated by Prefetch (run count=1, last run=2024-03-14T15:34Z) and EVTX 4688." Two artifact classes, caveat acknowledged. Narrator: "the schema makes the caveat unmissable."

**Hero beat 4 — Pivot in action (v4.4):** weird-parent finding triggers `pivot_node` (not replan). Single Hypothesis added — check parent's hash. New executor call. Total: 1 pivot, 0 replans, plan unchanged. Narrator: "real investigations pivot 8-15 times; the agent tracks pivots distinct from replans."

**Hero beat 5 — Disagreement (carried from v4.3):** Qwen3 hallucinates a malware persistence path. Langfuse pane: Qwen3 and GLM spans in parallel; quorum span lights up red. GLM-4.5-Air independently disagrees. `CONTESTED`. `replan_node` re-enters planner with conflict as hint. Both agree on corrected finding. `VERIFIED_AIRGAP` written, HMAC-signed.

**Hero beat 6 — TSI (carried from v4.3):** `tcpdump` proves OpenCTI API key never entered the malware-analysis VM.

**Hero beat 7 — Kill -9 (carried from v4.3, v4.4 hardened):** kill -9 the gateway between super-steps. Restart. `verdict resume <case_id>` — picks up from planner output via WAL+fsync-durable SqliteSaver. Mode is locked, resume verifies same mode, advances.

**3:00–4:00 — DUAL mode (60s).** Plug cable back in. New case in dual mode against same evidence (mode locked at case_init per v4.3 — no mid-case auto-elevation). Claude joins as planner; Qwen3 + GLM execute. Three-way verification. `VERIFIED_DUAL`. Show Langfuse session view: every finding records strategy, engines voting, tokens, latency.

**4:00–5:00 — Architecture recap + scoreboard.** Inspect AI per-mode accuracy table: hallucination rate per mode, agreement rates, false-positive rates, **MITRE sub-technique precision (v4.4)**, **negative-hypothesis quality (v4.4)**, **Qwen3-vs-GLM disagreement correlation (v4.4)**, step_efficiency. Show diff between Valhuntir's "human-gate-after-AI" and VERDICT's "AI-gate-against-AI." Cite Steve Anson's README admission. End card with repo URL and license.

5 minutes hits all 6 judging criteria explicitly: autonomous execution (mode autodetection, Plan-then-Execute, pivot_node), verification (cross-engine quorum, planner_critique_node CoVe), constraint architecture (mode-aware enforcement, microVM isolation, TSI, three-layer immutability with v4.4 honest Layer-1 caveat), audit trail (Langfuse + JSONL ledger cross-link, examination-environment metadata, output-file hashes, caveat acknowledgments), reproducibility (SqliteSaver kill-9 resilience with WAL/fsync), forensic discipline (DKOM divergence, Hunt Evil baseline, Amcache caveat, sub-technique precision, artifact-pair rule).

---

## v4.4 Anti-Pattern Checklist (weekly self-audit)

Run every Friday end-of-day. If any line drifts, fix before next week.

1. Are n=3 cloud-mode samples generated with **different seeds** at temperature 0.7? (`grep seed=` in CloudSelfConsistency, expect 3 distinct.)
2. Does every `Hypothesis(polarity="negative")` have non-None `mitre_technique` AND non-empty `artifact_families`? Field-validator + Inspect AI scorer both green?
3. Did this week's CI add the smoke test asserting your installed `claude` CLI version's PreToolUse `permissionDecision: "deny"` actually blocks an MCP tool write?
4. Does each tool wrapper have a Pydantic `args_validator` rejecting unknown flags / invalid types BEFORE `microsandbox.spawn`?
5. When `replan_max` is hit, does the run terminate with `status=UNVERIFIABLE` + `LedgerEntry(event_type="exhausted_replan")` + `interrupt()`, not quietly-stuck CONTESTED?
6. Does the planner system prompt explicitly enumerate negative-hypothesis quality criteria with ≥3 few-shot examples?
7. Are tool docs *not* preloaded into the executor system prompt — only loaded when the executor's assigned tool family is referenced?
8. Is sqlite running with `journal_mode=WAL` + `synchronous=FULL`?
9. Has KP measured Qwen3-vs-GLM disagreement *correlation* on the 50 ground-truth findings? Is the number printed in the accuracy report?
10. Does each `verdict-skills/*/SKILL.md` frontmatter list `required_tools` so context-window is bounded per skill activation?
11. Does every `Finding` have `len(set(artifact_classes)) >= 2` for execution-class techniques?
12. Does every Finding citing `ArtifactClass.AMCACHE` have `CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC` in `caveats_acknowledged`?
13. Does the planner pick MITRE sub-techniques (`T1055.012`) not parents (`T1055`) when sub-technique is determinable?
14. Does the LangGraph fanout-race unit test still pass on the pinned LangGraph version?
15. Does pslist+psscan divergence emit a T1014 Hypothesis automatically, no LLM judgment required?

---

## v4.4 SANS-Judge-Credibility Checklist (record demo against this)

A senior examiner watching the 5-min demo will tick or scratch each:

1. Does the agent verify the image hash *before* opening evidence?
2. Does it open with `windows.info` (memory) or `mmls`+`fsstat` (disk) — the SANS-canonical first move?
3. Does it run `pslist` + `psscan` and explicitly check divergence (DKOM/T1014 catch)?
4. Does it cite ≥2 artifact classes per execution claim, with the artifact-pair named in the Finding rationale?
5. Does it acknowledge the Amcache caveat when it cites Amcache?
6. Does any timestamp it emits have `Z` suffix and UTC tzinfo?
7. Does it pivot — at least one tool call spawned in response to a previous tool's output, not just the initial plan?
8. Does it speak the epistemic vocabulary out loud — "hypothesis" / "inferred" / "confirmed" mapped to the verdict status?
9. Does it map findings to MITRE sub-techniques (`T1055.012` not `T1055`)?
10. Does the Hunt Evil baseline detect a process-name masquerade (`scvhost.exe`, parent=`cmd.exe`)?
11. Does it never assert attribution? ("Evidence consistent with X" not "X did this.")
12. Does the ledger record tool version + rootfs SHA + microsandbox version per call?
13. Can the demo case (Honeynet ransomware) be run end-to-end in <20 minutes? (Anything longer, judges lose interest.)
14. Does the agent give up *explicitly* (UNVERIFIABLE + interrupt) when it can't resolve, rather than hanging or hallucinating?
15. Does the planner_critique_node fire visibly in the Langfuse trace, with at least one CoVe question shown to the camera?

---

## Caveats (v4.4 additions)

(v4.3 caveats unchanged.)

- **(v4.4) PreToolUse `permissionDecision: "deny"` is buggy for MCP tools and Edit (anthropics/claude-code#33106 + #37210).** Layer 1 of three-layer immutability is best-effort; Layers 2 and 3 carry the architectural guarantee. CI smoke test catches version drift.
- **(v4.4) n=3 self-consistency requires diverse paths.** Same seed + temp=0 = n=1. Use three blake3-keyed seeds at temp=0.7.
- **(v4.4) Cross-family independence is partial, not absolute.** Qwen3 and GLM share web-corpus pretraining; KP measures empirical disagreement correlation in week 4. Honest claim shipped in accuracy report.
- **(v4.4) `replan_max=3` is a budget, not a guarantee.** Real DFIR investigations pivot 8-15 times. v4.4 distinguishes pivot (cheap, `pivot_max=15`) from replan (expensive, `replan_max=3`). Iteration 4 of replan = explicit UNVERIFIABLE + `interrupt()`.
- **(v4.4) Tool-call argument hallucination is a separate failure mode from finding hallucination.** Microsandbox prevents evidence corruption; it does not validate that `vol3 --foo bar` is a real flag. Pydantic-AI `args_validator` per tool wrapper closes the gap.
- **(v4.4) Microsandbox destruction breaks examination-environment reproducibility unless rootfs is content-addressed and pinned.** v4.4 records `rootfs_sha256`, `microsandbox_version`, `tool_version`, `kernel_version` per ledger entry per NIST SP 800-86 §5.1.4.
- **(v4.4) v1 scope = Windows DFIR.** macOS / Linux / Win11-specific artifacts (SRUM, ETW, Cortana, Windows Search Index) / ESXi forensics = v2 roadmap. Stated in `docs/SCOPE.md`.

---

## Citations (v4.4 additions)

Beyond the v4.3 citation set:

**Agentic literature:**
- Wang et al. 2022 — "Self-Consistency Improves Chain of Thought Reasoning" — arXiv:2203.11171
- Chen et al. 2023 — "Universal Self-Consistency for LLMs" — arXiv:2311.17311
- Dhuliawala et al. 2023 — "Chain-of-Verification Reduces Hallucination" — arXiv:2309.11495
- Du et al. 2024 — "Improving Factuality and Reasoning through Multiagent Debate" — arXiv:2305.14325
- Wang et al. 2024 — "Mixture-of-Agents Enhances LLM Capabilities" — arXiv:2406.04692
- Manakul et al. 2023 — "SelfCheckGPT" — arXiv:2303.08896
- Shinn et al. 2023 — "Reflexion" — arXiv:2303.11366
- Huang et al. 2024 — "LLMs Cannot Self-Correct Reasoning Yet" — arXiv:2310.01798
- Kim et al. 2024 — "LLMCompiler" — arXiv:2312.04511
- Khan et al. 2025 — "Talk Isn't Always Cheap: Failure Modes in MAD" — arXiv:2509.05396
- Cao et al. 2025 — "The Reasoning Trap: How Enhancing LLM Reasoning Amplifies Tool Hallucination" — arXiv:2510.22977
- "LLM-Based Agents Suffer from Hallucinations: A Survey" — arXiv:2509.18970
- "Variation in Verification: Verification Dynamics in LLMs" — arXiv:2509.17995
- "LLM Output Drift: Cross-Provider Validation for Financial Workflows" — arXiv:2511.07585
- "Architecting Resilient LLM Agents: Plan-then-Execute" — arXiv:2509.08646
- Anthropic — "Building Effective Agents" — anthropic.com/research/building-effective-agents
- Anthropic — "How we built our multi-agent research system" — anthropic.com/engineering/multi-agent-research-system
- Anthropic — "Effective context engineering for AI agents" — anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Anthropic — "Equipping agents for the real world with Agent Skills" — anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- anthropics/claude-code issue #33106 — github.com/anthropics/claude-code/issues/33106
- anthropics/claude-code issue #37210 — github.com/anthropics/claude-code/issues/37210
- LangGraph fanout/reducer issue #4026 — github.com/langchain-ai/langgraph/issues/4026
- Pydantic-AI Function Tools — ai.pydantic.dev/tools/

**DFIR / SANS literature:**
- SANS Hunt Evil poster — sans.org/posters/hunt-evil
- SANS Windows Forensic Analysis poster (FOR500) — sans.org/posters/windows-forensic-analysis
- SANS Windows Forensic Analysis Playbook — sans.org/posters/windows-forensic-analysis-playbook
- SANS DFIR Memory Forensics poster — sans.org/posters/dfir-memory-forensics
- SANS FOR508 — sans.org/cyber-security-courses/advanced-incident-response-threat-hunting-training
- SANS FOR500 — sans.org/cyber-security-courses/windows-forensic-analysis
- Rob T. Lee profile — sans.org/profiles/rob-lee
- Volatility Foundation Command Reference — github.com/volatilityfoundation/volatility/wiki/Command-Reference
- Volatility Command Reference (Mal) — github.com/volatilityfoundation/volatility/wiki/Command-Reference-Mal
- Plaso 20260427 documentation — plaso.readthedocs.io
- Hayabusa — github.com/Yamato-Security/hayabusa
- MITRE ATT&CK T1055 Process Injection — attack.mitre.org/techniques/T1055/
- MITRE ATT&CK T1014 Rootkit — attack.mitre.org/techniques/T1014/
- MITRE CAR-2021-04-001 (process masquerading) — car.mitre.org/analytics/CAR-2021-04-001/
- NIST SP 800-86 — nvlpubs.nist.gov/nistpubs/legacy/sp/nistspecialpublication800-86.pdf
- SWGDE 18-F-001 — swgde.org/wp-content/uploads/2024/05/2018-07-11-SWGDE-Best-Practices-for-Computer-Fo.pdf
- SWGDE 22-F-003 — swgde.org/wp-content/uploads/2024/11/2024-11-22-Best-Practices-for-Remote-Collection-of-Digital-Evidence-from-an-Endpoint-22-F-003-2.0.pdf
- Magnet Forensics ShimCache vs AmCache — magnetforensics.com/blog/shimcache-vs-amcache-key-windows-forensic-artifacts/
- H. Carvey "ShimCache/AmCache Myth" — windowsir.blogspot.com/2024/11/program-execution-shimcacheamcache-myth.html
- Velociraptor "Evidence of Execution" — docs.velociraptor.app/docs/forensic/evidence_of_execution/
- LOLBAS project — lolbas-project.github.io
- Project local: `agent-config/MEMORY.md` (Tier-1 caveats, ≥2-artifact rule)
- Project local: `CLAUDE.md` (DKOM `vol_pslist`+`vol_psscan` redundancy rationale)

---

**Bottom line for Tim:** v4.3 was a strong AI-systems architecture document. v4.4 layers in (a) two BLOCKER bug-fixes (PreToolUse-deny is buggy, n=3 needs diverse seeds), (b) the artifact-pair corroboration rule + caveat acknowledgments + DKOM divergence + playbooks + Hunt Evil baseline + LOLBin catalog (turns it into a *forensic* agent a SANS judge respects), (c) prompt-engineering and schema validators that close the wrong-plan / tool-arg-hallucination / replan-termination gaps, and (d) ~15 teammate-days of week-1-through-week-4 work spread across the team. None of this requires re-locking the stack; v4.3's lock-in decisions hold.
