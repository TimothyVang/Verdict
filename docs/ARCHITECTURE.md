# VERDICT — Architecture (current authoritative)

**Status:** Current. This document supersedes all VERDICT_AUDIT_v4.x docs in `spec/`. Read `spec/03-audit-v4.5.md` only for historical decision rationale; this doc is the single architecture authority going forward.
**Date:** May 2, 2026.
**For Devpost compliance:** see `DEVPOST_COMPLIANCE.md`. For week-by-week build sequencing: `BUILD_PLAN.md`. For hard rules an agent must obey: see `../CLAUDE.md` §3.

### How to edit this doc
- This is the **single architectural authority.** Never duplicate decisions into other docs; cross-link instead.
- **Never edit `spec/`** — those files capture point-in-time audits and are cited from here.
- **`BUILD_PLAN.md` task IDs** are immutable once a contributor has committed against them. New work gets a new ID.

---

## 1. Operational modes

VERDICT detects available infrastructure at startup and selects one of three modes. Operators override via `--mode={cloud,airgap,dual}`. Mode is **locked at case_init** and immutable thereafter — `verdict resume <case_id>` always uses the original mode; mode upgrades happen via `verdict reverify <case_id> --mode <new>` which produces a parallel verdict chain rather than mutating the original audit trail.

| Mode | Trigger | Engines | Verifier strategy | Use case |
|---|---|---|---|---|
| **cloud-only** | Internet ✓ + GPU ✗ | Claude Code (Agent SDK) | n=3 self-consistency at temperature=0.7 with three case_id-derived blake3 seeds. ≥2-of-3 → `VETTED_CLOUD`; below → `DRAFT_CLOUD`. **Best-effort vetting, not true verification** — same model shares failure modes. | SOC analyst on corporate laptop |
| **air-gap-only** | Internet ✗ + GPU ✓ | SGLang serving Qwen3-30B-A3B-Thinking + GLM-4.5-Air | Cross-family quorum: both engines must independently agree on artifact set (Jaccard ≥0.80) and identical MITRE technique. Independence is **partial-not-absolute** (overlapping web pretraining); empirical disagreement-correlation measured in W4.G.1. | DCO operator on classified network |
| **dual** | Internet ✓ + GPU ✓ | Claude + Qwen3 + GLM-4.5-Air | Three-way: cloud agrees with at least one local + locals agree with each other. Strongest verification. | Forensic lab |

### Why diverse seeds matter (cloud-only)

Same seed + same temperature + same prompt = three identical outputs. Wang et al. 2022 self-consistency (arXiv:2203.11171) requires *diverse* reasoning paths. The implementation derives three blake3-keyed seeds per case:

```python
from blake3 import blake3

def derive_seeds(case_id: str) -> tuple[int, int, int]:
    """Three reproducible-but-diverse seeds per case via blake3 derive_key contexts."""
    return tuple(
        int.from_bytes(
            blake3(
                case_id.encode(),
                derive_key_context=f"verdict.seeds.v1.{label}",
            ).digest(length=4),
            "big",
        )
        for label in ("a", "b", "c")
    )
```

Reproducibility-with-diversity: re-running the case yields the same three samples (audit-friendly), but the three samples differ from each other (verifier-friendly).

---

## 2. Plan-then-Execute LangGraph topology

```
START
  ▼
┌─────────────────┐
│ planner_node    │  Claude (cloud) or Qwen3 (airgap)
│                 │  Output: InvestigationPlan with positive
│                 │  hypotheses, NEGATIVE hypotheses (quality-
│                 │  validated), tool budget, success criteria
└────────┬────────┘
         ▼
┌─────────────────┐
│ planner_critique│  CoVe (Dhuliawala 2023, arXiv:2309.11495)
│ (CoVe)          │  Same model drafts verification questions
│                 │  ABOUT THE PLAN ITSELF, answers them against
│                 │  case_init evidence summary. Failed questions
│                 │  → loop back to planner with hint.
└────────┬────────┘
         ▼
┌─────────────────┐
│ comprehension_  │  All 4 executors echo their parsed view of
│ gate            │  the plan. Gate validates consensus on
│                 │  parsed_positive_hypothesis_ids,
│                 │  parsed_negative_hypothesis_ids,
│                 │  parsed_success_criteria_hash. Mismatch
│                 │  → clarify_node.
└────────┬────────┘
         ▼  (fanout — 4 parallel branches)
┌─────────────────┐
│ executor_fanout │  vol_exec / hay_exec / pls_exec / mft_exec
│                 │  Each runs in microsandbox VM
│                 │  Composed: DenyRuleWrapper → ToolExecutor → LedgerEmitter
└────────┬────────┘
         ▼
┌─────────────────┐
│ pivot_node      │  Cheap follow-up: ONE Hypothesis added on
│                 │  basis of executor finding. Re-enters
│                 │  executor_work; does NOT re-enter planner.
│                 │  Bounded pivot_max=15.
└────────┬────────┘
         ▼
┌─────────────────┐
│ quorum_node     │  Apply VerifierStrategy. Reject Findings
│                 │  with len(set(artifact_classes)) < 2 for
│                 │  execution claims (FOR500 corroboration).
└────────┬────────┘
         │
    VERIFIED        CONTESTED                  UNVERIFIABLE
         │              │                           │
         ▼              ▼                           ▼
   finalize_node   replan_node                unverifiable_
   (HMAC sign)     (max 3, then               finalize_node
                   unverifiable_              (writes status,
                   finalize)                   ledger event,
                                               interrupt() for HITL)
```

### Pivot vs. replan distinction

Real DFIR pivots 8–15 times per investigation; v4.4 research showed that bounded `replan_max=3` is a research-paper budget, not a DFIR budget. Two distinct flows:

- **PIVOT** (cheap, `pivot_max=15`): single Hypothesis added on basis of an executor's output. Re-enters `executor_work` only. Use when "tool emitted weird parent process → check parent's hash."
- **REPLAN** (expensive, `replan_max=3`): full plan rewrite. Re-enters `planner_node` with conflict surfaced as hint. Use only on quorum CONTESTED.
- **At replan iteration 4:** `unverifiable_finalize_node` writes `Finding(status=UNVERIFIABLE)`, writes `LedgerEntry(event_type="exhausted_replan")`, calls `interrupt()` for HITL. Analyst can `update_state` and resume, or accept UNVERIFIABLE.

### Checkpointing

Graph is checkpointed at every super-step via SqliteSaver with `PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL` so kill-9 between sqlite txn-commit and fsync doesn't lose the most recent super-step. `thread_id = case_id` everywhere. Demo `kill -9` happens between super-steps for clean visible resume.

---

## 3. Three-layer immutability defense

```
Layer 1: Claude Code PreToolUse hook
  • cloud + dual modes only (air-gap = no Claude in loop)
  • Best-effort: anthropics/claude-code #33106 + #37210
    means deny is buggy for MCP tools and Edit tool.
  • Logged in ledger but NOT the architectural guarantee.
  • CI smoke test verifies installed Claude CLI version
    actually denies an MCP write; build fails on regression.

Layer 2: LangGraph DenyRuleWrapper (composition wrapper)
  • Fires in ALL three modes regardless of model.
  • Validates typed tool args against deny-rule list.
  • THE architectural guarantee.
  • Composed with ToolExecutor and LedgerEmitter — three
    distinct concerns, three distinct owners (Tim/Beaver/Tim).

Layer 3: Microsandbox read-only mount
  • /evidence mounted read-only at libkrun kernel level.
  • Defense-in-depth even if Layers 1-2 are bypassed.
  • Plus chattr +i on evidence vault at case_init.
```

Why three layers? Each catches what the others miss. Claude hooks don't fire in air-gap. Microsandbox alone doesn't catch tool-arg validation. Wrapper alone doesn't survive a sandbox escape.

---

## 4. Forensic discipline encoded as schema

The differentiator vs. competitors. Schema validators reject sloppy findings before quorum sees them.

### Artifact-pair corroboration

```python
class Finding(BaseModel):
    artifact_paths: list[Path] = Field(min_length=2)
    artifact_classes: list[ArtifactClass] = Field(min_length=2)
    caveats_acknowledged: list[CaveatID] = []
    mitre_technique: str | None  # validated against ^T\d{4}(\.\d{3})?$

    @model_validator(mode="after")
    def _execution_claims_need_two_classes(self):
        is_exec = any(
            self.mitre_technique and self.mitre_technique.startswith(p)
            for p in ("T1059", "T1106", "T1204", "T1218", "T1543", "T1547")
        )
        if is_exec and len(set(self.artifact_classes)) < 2:
            raise ValueError(f"execution claim needs ≥2 distinct artifact classes")
        return self

    @model_validator(mode="after")
    def _amcache_caveat_required(self):
        if ArtifactClass.AMCACHE in self.artifact_classes:
            if CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC not in self.caveats_acknowledged:
                raise ValueError("Finding cites Amcache without LastModified caveat")
        return self
```

### CaveatID — Tier-1 examiner caveats from `agent-config/MEMORY.md`

```python
class CaveatID(str, Enum):
    AMCACHE_LASTMODIFIED_NOT_EXEC = "amcache_lastmodified_neq_execution"
    SHIMCACHE_ORDER_CHANGED_WIN81 = "shimcache_order_lru_pre81_insertion_post81"
    PREFETCH_SSD_DISABLED = "prefetch_disabled_on_ssd_or_gpo"
    MFT_SI_STOMPABLE = "mft_si_timestomp_use_fn"
    USNJRNL_WRAPS = "usnjrnl_wraps_treat_gaps_carefully"
    LOGON_TYPE_3_VS_10 = "evtx_4624_type3_network_neq_type10_rdp"
    SYSMON_PROCESSGUID_OVER_PID = "sysmon_processguid_correlation_key_not_pid"
```

Loaded into every executor system prompt via `verdict/planning/prompts/examiner_caveats.md`.

### ArtifactClass — multi-source corroboration vocabulary

```python
class ArtifactClass(str, Enum):
    PREFETCH = "prefetch"
    AMCACHE = "amcache"
    SHIMCACHE = "shimcache"
    EVTX_4688 = "evtx_4688"
    SYSMON_1 = "sysmon_1"
    NETWORK = "network"
    REGISTRY_RUN = "registry_run"
    TASK_SCHEDULER = "task_scheduler"
    WMI_SUBSCRIPTION = "wmi_subscription"
    MFT = "mft"
    PROCESS_MEMORY = "process_memory"
    YARA_HIT = "yara_hit"
    SIGMA_HIT = "sigma_hit"
```

### Playbooks — SANS canonical tool sequencing

Three YAMLs in `verdict/playbooks/` (memory.yml / disk.yml / triage.yml) ported from project `agent-config/PLAYBOOK.md`. Loaded into planner system prompt at case_init based on detected evidence type.

`memory.yml` example rule (DKOM detection):
```yaml
- order: 3
  tool: vol3.windows.psscan
  rule: "DKOM_divergence: set(psscan_pids) - set(pslist_pids) ≠ ∅
         → Hypothesis(T1014, high, [PROCESS_MEMORY])"
```

This is one of the architecture's clearest moats — DKOM/T1014 detection auto-fires from the divergence between `pslist` (active list walk) and `psscan` (EPROCESS pool memory signature scan). Free in code, encoded as schema, and a 30-second demo segment.

### Hunt Evil baseline

`verdict/knowledge/hunt_evil.yml` keyed by process name with expected parent / path / signing / instance count for 8 canonical Windows processes (svchost, lsass, csrss, winlogon, services, wininit, explorer, smss). `ProcessBaselineAnomaly` Hypothesis subtype maps to `T1036.005` (Match Legitimate Name or Location). Catches `scvhost.exe` with parent `cmd.exe` automatically.

---

## 5. Cryptographic chain-of-custody

### Three-tier ID hierarchy in LedgerEntry

```python
class LedgerEntry(BaseModel):
    entry_id: str                              # ULID
    case_id: str                               # ROOT — eternal
    finding_id: str | None
    event_type: Literal[
        "case_init", "tool_call", "finding", "approval", "rejection",
        "mode_lock", "comprehension_check", "critique_verdict",
        "pivot", "exhausted_replan", "evidence_hash_recheck",
        "sandbox_failure", "planner_cot",
    ]
    timestamp_utc: datetime

    # Mode lock
    mode_at_case_init: Mode
    verifier_strategy_used: str

    # Langfuse cross-references
    langfuse_session_id: str                   # = case_id
    langfuse_trace_id: str                     # one per graph.invoke()
    langfuse_root_span_id: str
    langfuse_leaf_span_ids: list[str]

    # LangGraph cross-references
    langgraph_thread_id: str                   # = case_id
    langgraph_checkpoint_id: str

    # Examination-environment metadata (NIST SP 800-86 §5.1.4)
    microsandbox_version: str | None = None
    rootfs_sha256: str | None = None
    tool_version: str | None = None
    kernel_version: str | None = None

    # Per-output-file hashes (NIST SP 800-86 §5.1.2)
    output_files_sha256: dict[str, str] = {}

    # Ledger chain integrity
    payload: dict
    payload_redactions: list[str] = []
    prev_entry_hash: str
    hmac_sig: str
    schema_version: int = 1
```

### Bidirectional cross-link

Every ledger entry is reachable from a Langfuse trace, and every Langfuse trace span has a `ledger_entry_id` attribute. Judges can drill in either direction: ledger → trace → tool call → microsandbox version → file hash; or trace → ledger entry → finding rationale.

### HMAC key handling

TPM-backed if `/dev/tpmrm0` present. Otherwise gpg-encrypted at `~/.verdict/key.gpg` with passphrase prompted at gateway init. Ledger writes are `write + fsync + verify-readback`. On startup, gateway verifies last entry's HMAC; if invalid, refuses to load case.

### Periodic evidence re-hash

Every 10 super-steps, re-hash all `EvidenceItem` files against the manifest. Mismatch → `LedgerEntry(event_type="evidence_hash_recheck")` + halt with `HashMismatchError`. Catches anything that bypasses the three-layer immutability gate.

---

## 6. Tool surface (12 SIFT tools, 19 wrappers)

| Tool family | Wrappers |
|---|---|
| Volatility 3 | `windows.{info,pslist,psscan,pstree,cmdline,dlllist,malfind,netscan,svcscan,handles,callbacks}` (10 plugins) |
| Hayabusa | Split: `hayabusa_csv_timeline` (extract) + `hayabusa_filter` (analyst-driven filter by sigma_level + time_range) |
| Plaso | Split: `plaso_extract` (log2timeline.py → .plaso) + `psort_filter` (psort.py + filter expression) |
| Sleuth Kit | `mmls`, `fls`, `fsstat` |
| EZ Tools | `MFTECmd`, `RECmd`, `PECmd` |
| Other | `bulk_extractor`, `exiftool`, `capa` |

Every wrapper extends `ToolWrapper` base; emits typed `ToolOutput` with `parsed_artifacts: list[Artifact]`. `parsed_artifacts` is the discriminator surface for cross-engine quorum's Jaccard comparison.

### Pattern 1 — per-tool ephemeral microVM

```python
async def vol3_pslist(memory_image: Path, output_dir: Path) -> ToolOutput:
    image_hash = sha256_file(memory_image)
    sandbox = await microsandbox.spawn(
        image="verdict-sift-tools@sha256:<pin>",
        mounts=[ReadOnly("/evidence", memory_image.parent)],
        network=False,
        timeout=600,
    )
    result = await sandbox.run(["vol3", "-f", str(memory_image), "windows.pslist"])
    output_hash = sha256(result.stdout)
    await sandbox.destroy()
    return ToolOutput(
        tool_name="vol3.windows.pslist",
        tool_version="vol3 2.28.0",  # current at W2.A pin time; update at build
        invocation_args=[...],
        invocation_hash=blake3(...),
        stdout_hash=output_hash,
        ...
    )
```

### Pattern 2 — TSI for credential injection

```python
sandbox = await microsandbox.spawn(
    image="verdict-malware-tools@sha256:<pin>",
    network_policy=TSI(
        proxy_origin="opencti.local:8080",
        inject_header={"Authorization": f"Bearer {os.environ['OPENCTI_KEY']}"},
    ),
)
```

API key never enters the VM. Proven via tcpdump comparison: bearer header on egress to `opencti.local:8080`, NOT inside the microvm.

### Tool-call argument validation

Pydantic-AI `args_validator` runs *before* `microsandbox.spawn`:
- vol3: validate plugin against allow-list (parse `vol3 --help` once at startup, hash-pin); `--pid` is positive int; reject unknown flags.
- plaso: pre-validate filter expression with `psteal --validate-filter` in ephemeral sandbox.
- Hayabusa: validate timeline-flag combinations against playbook matrix.

On validation failure: raise `ModelRetry`, bounded by `tool_arg_retry_max=2`, then UNVERIFIABLE.

### Sanitization for prompt injection

`verdict/tools/sanitization.py` scans tool stdout for prompt-injection patterns (`IGNORE PREVIOUS`, `SYSTEM:`, `</tool_call>`, `[INST]`, `### Instruction`, common jailbreak suffixes). Detected → `ToolOutput.sanitization_flags` populated; surfaced to planner. Defense against malicious memory images where attacker-controlled strings end up in `vol3.cmdline` output.

---

## 7. Stack lock-in

| Layer | Choice | License |
|---|---|---|
| Cloud agent | Claude Code + Agent SDK | Anthropic Commercial Terms (your code MIT) |
| Local inference primary | SGLang | Apache-2.0 |
| Local inference fallback | vLLM | Apache-2.0 |
| Local Model A | Qwen3-30B-A3B-Thinking-2507 | Apache-2.0 |
| Local Model B (verifier) | GLM-4.5-Air | MIT |
| Orchestration | LangGraph | MIT |
| Schema layer | Pydantic v2 + Pydantic-AI | MIT |
| MCP gateway | FastMCP 3.x | Apache-2.0 |
| Sandbox primary | Microsandbox (libkrun microVM) | Apache-2.0 (beta) |
| Sandbox secondary | bubblewrap | LGPL-2.0 (linking-clean) |
| Sandbox tertiary | nsjail | Apache-2.0 |
| Eval harness | Inspect AI | MIT |
| Tracing | Langfuse self-hosted (core) + OpenLLMetry | MIT + Apache-2.0 |
| Durable execution | LangGraph SqliteSaver | MIT |
| Rails | NeMo Guardrails | Apache-2.0 |
| Skills | agentskills.io standard | open standard |

**Hard nos** (license-incompatible or architecturally rejected): Daytona (AGPL-3.0), REMnux MCP for vendoring (GPL-3.0; network-call only allowed), Llama 4 / Gemma 3 (community licenses, not OSI), Modal (closed), LangSmith / Braintrust (closed), Arize Phoenix (ELv2), AutoGen v0.4 migration (maintenance mode Oct 2025), Microsoft Agent Framework (Azure-coupled, late). AGPL clean-room rewrites do not strip copyright.

---

## 8. Scope (v1)

**v1 ships Windows-DFIR-depth-first.** Devpost rubric: "Depth on fewer types beats shallow coverage of many."

**In scope:**
- Memory imaging analysis (Volatility 3)
- Disk image analysis (.E01 via libewf, NTFS-focused)
- EVTX log analysis (Hayabusa)
- Triage zip parsing (KAPE/Velociraptor offline)
- 50 ground-truth indicators across 3 engineered cases (lol-bins, credtheft, ransomware)

**Explicitly out of scope (v2 architectural extension points):**
- macOS (FileVault, Endpoint Security Framework, Unified Logs) — needs `MacOSCaveatID` enum
- Linux (auditd, ext4, no SHIMCACHE) — needs `LinuxCaveatID` enum + `linux_baseline.yml`
- Win11-specific (SRUM, ETW persistent providers, Cortana, Windows Search Index)
- ESXi / VMware-specific forensics
- Network forensics (FOR572: Zeek, Suricata, tshark) — needs **5th `net_executor` fanout branch**
- Live-endpoint mode (Velociraptor, GRR core flow) — needs **5th `live_executor` fanout branch**; live-evidence chain-of-custody differs from offline (NIST SP 800-86 §5.1.4 different requirements)
- Examiner-workflow integrations (Axiom XML, EnCase EWF, FTK CSV) — architecture supports export interface; format adapters in v2

The 4-fixed-branch fanout topology in v1 is an explicit architectural constraint. v2 expansion to 5+ branches is supported by the LangGraph reducer pattern. See `BUILD_PLAN.md` Phase W5.D.1 for `docs/SCOPE.md` deliverable.

---

## 9. Threat model (4 surfaces)

Documented in `docs/THREAT_MODEL.md` per `BUILD_PLAN.md` Phase W1.G.1.

| Surface | Mitigation | Residual risk |
|---|---|---|
| **Insider analyst** with HMAC key access | TPM-backed key if `/dev/tpmrm0`, else gpg-encrypted with passphrase | Cleared analyst with both physical access + passphrase can forge ledger; out of scope for v1 |
| **Prompt injection from evidence** (malicious cmdline/path strings in memory image) | Sanitization scanner on tool stdout; `ToolOutput.sanitization_flags` surfaced to planner; structured-output parsing as primary defense | Novel jailbreak patterns may evade sanitization |
| **Malicious tool output** (forensic tool exploited via crafted memory image) | Microsandbox isolation (libkrun microVM, network=False, read-only evidence mount, destroyed after each call) | Microsandbox escape — accepted v1 risk; v2 evaluates kata-containers |
| **External attacker on SIFT box** | Out of scope for v1 — accept SIFT as trusted host | Standard host-hardening responsibility of operator |

**Known gap:** the model itself as adversary (CoT exfiltration via gzipped reasoning ledger entries or Atropos trajectory exports) is not addressed in v1. Planner CoT capture goes to ledger AND first 8KB to Langfuse span. With Langfuse self-hosted air-gap-side, the CoT never leaves the box. If any operator exports an Atropos trajectory for fine-tuning, evidence-derived data leaks. Documented as accepted v1 risk; v2 addresses via CoT redaction pipeline.

---

## 10. Demo sequence (5 min, two-pane recording)

Detailed in `BUILD_PLAN.md` W6.A.1 + `archive/03-audit-v4.5.md` lines 855–865.

```
0:00–0:30  Cold open + architecture flash
0:30–1:30  CLOUD-ONLY (60s) — n=3 self-consistency, three seeds
1:30–3:00  AIR-GAP (90s) — 7 hero beats:
           ⓵ DKOM divergence (pslist+psscan) → T1014 auto
           ⓶ Hunt Evil masquerade (scvhost.exe parent=cmd.exe)
           ⓷ Amcache caveat acknowledged in rationale
           ⓸ Pivot in action (1 pivot, 0 replans)
           ⓹ Disagreement → CONTESTED → replan → VERIFIED ★
              (Devpost-required "self-correction sequence")
           ⓺ TSI tcpdump proof
           ⓻ Kill -9 between super-steps + verdict resume
3:00–4:00  DUAL (60s) — three-way verification → VERIFIED_DUAL
4:00–5:00  Architecture recap + per-mode accuracy table
```

Every hero beat must land cleanly; record beats as separate clips during weeks 4-5 (one beat per session, locked when good), then assemble in week 6.

---

## 11. Open architectural concerns (worth Tim's eye)

These were raised during the v4.4 research and v4.5 system-design review. They're not blockers; they're worth thinking through during build.

1. **Cross-family verification's epistemic foundation has a known weakness:** correlated false negatives. If both Qwen3 and GLM miss a rare LOLBin pattern (post-pretraining-cutoff persistence technique) because their training corpora share the same gap, both agree "no evil found" and quorum fires green on a wrong-negative. Empirical disagreement-correlation measurement in W4.G.1 will show this; no architectural fix in v1, just honest disclosure in `docs/ACCURACY_REPORT.md`.

2. **Schema strictness vs recall tradeoff.** `Finding` validators reject sloppy findings — good for credibility, but each invariant is a place a *legitimate* finding gets rejected for the wrong reason. Mitigation: have `executor_work` *infer* `artifact_classes` deterministically from `artifact_paths` (e.g. paths matching `\Prefetch\*.pf` → `PREFETCH`) so the LLM never has to know the enum exists. Validator-as-projection rather than validator-as-gate.

3. **"No evil found" verdict is unmodeled.** `Finding.artifact_paths min_length=2` rejects null findings. Some engineered cases will be benign-with-red-herrings. Need a `NegativeFinding` schema variant citing playbook *steps executed* rather than artifact paths. Currently a v1 gap.

4. **Plan-then-Execute is fundamentally batch; DFIR is fundamentally adaptive.** `pivot_max=15` recreates ReAct in a more constrained form. If demo runs show 90% sequential pivots, the topology pays overhead for a parallelism that doesn't materialize. Lean the demo narrative on the *audit-trail review story* (sequential is fine; structure is what reviewability needs) rather than runtime parallelism.

5. **The 4-fixed-fanout cap is real but documented.** `docs/SCOPE.md` names the v2 extension points (5th `net_executor`, 5th `live_executor`).

---

## 12. What's NOT in this doc — see other authorities

| Need | Doc |
|---|---|
| Day-by-day TDD task list | `BUILD_PLAN.md` |
| Devpost rule mapping | `DEVPOST_COMPLIANCE.md` |
| "Why we picked X over Y" decision rationale | `archive/03-audit-v4.5.md` |
| v4.4 agentic + DFIR research findings (raw) | `archive/02-audit-v4.4.md` |
| v4.6 schema patches (raw spec) | `archive/04-spec-plan-v4.6.md` |
| Project-wide build conventions | `../CLAUDE.md` |
| Tier-1 examiner caveat source | `../agent-config/MEMORY.md` |
| Tool sequencing playbook source | `../agent-config/PLAYBOOK.md` |
