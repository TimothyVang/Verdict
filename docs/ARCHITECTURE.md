# VERDICT — Architecture (current authoritative)

> **Wiki:** [Index](README.md) · [TL;DR](TLDR.md) · [Architecture](ARCHITECTURE.md) · [Build Plan](BUILD_PLAN.md) · [Devpost](DEVPOST_COMPLIANCE.md) · root [CLAUDE.md](../CLAUDE.md)

**Status:** Current. This document supersedes all VERDICT_AUDIT_v4.x docs in `spec/`. Read `spec/03-audit-v4.5.md` only for historical decision rationale; this doc is the single architecture authority going forward.
**Date:** May 2, 2026.
**For Devpost compliance:** see `DEVPOST_COMPLIANCE.md`. For week-by-week build sequencing: `BUILD_PLAN.md`. For hard rules an agent must obey: see `../CLAUDE.md` §3.
**Rendered diagram:** [`ARCHITECTURE_DIAGRAM.svg`](ARCHITECTURE_DIAGRAM.svg) with Mermaid source in [`ARCHITECTURE_DIAGRAM.mmd`](ARCHITECTURE_DIAGRAM.mmd).

### How to edit this doc
- This is the **single architectural authority.** Never duplicate decisions into other docs; cross-link instead.
- **Never edit `spec/`** — those files capture point-in-time audits and are cited from here.
- **`BUILD_PLAN.md` task IDs** are immutable once a contributor has committed against them. New work gets a new ID.

---

## 1. Operational modes

VERDICT detects available infrastructure at startup and selects one of three modes. Operators override via `--mode={cloud,airgap,dual}`. Mode is **locked at case_init** and immutable thereafter — `verdict resume <case_id>` always uses the original mode; mode upgrades happen via `verdict reverify <case_id> --mode <new>` which produces a parallel verdict chain rather than mutating the original audit trail. The Devpost submission remains a Claude Code / Protocol SIFT extension: Claude Code is the primary operator and cloud/dual execution surface; air-gap mode is the local-inference lane for offline environments, preserving the same graph, tool, ledger, and verification contracts.

| Mode | Trigger | Engines | Verifier strategy | Use case |
|---|---|---|---|---|
| **cloud-only** | Internet ✓ + GPU ✗ | Claude Code (Agent SDK) | n=3 self-consistency at temperature=0.7 with three case_id-derived blake3 seeds. ≥2-of-3 → `VETTED_CLOUD`; below → `CONTESTED` (escalates to `replan_node`). **Best-effort vetting, not true verification** — same model shares failure modes. | SOC analyst on corporate laptop |
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

### Quorum dispatch table

`quorum_node` applies the locked mode's `VerifierStrategy` and emits one of the canonical `VerdictStatus` values (defined in `CLAUDE.md` §3.6). The dispatch is total — every input lands in exactly one row.

| Strategy | Engine outcome | `VerdictStatus` | Next node |
|---|---|---|---|
| `CloudSelfConsistency` (n=3) | ≥2 samples agree on `(mitre_technique, parsed_artifacts)` | `VETTED_CLOUD` | `finalize_node` |
| `CloudSelfConsistency` (n=3) | <2 samples agree | `CONTESTED` | `replan_node` |
| `AirGapCrossEngine` | Jaccard(`parsed_artifacts`) ≥0.80 AND identical `mitre_technique` | `VETTED_AIRGAP` | `finalize_node` |
| `AirGapCrossEngine` | Jaccard ≥0.80, divergent `mitre_technique` | `CONTESTED` | `replan_node` |
| `AirGapCrossEngine` | Jaccard <0.80 (incl. empty-set case below) | `CONTESTED` | `replan_node` |
| `DualLaneCrossEngine` | cloud agrees with ≥1 local AND locals agree with each other | `VETTED_DUAL` | `finalize_node` |
| `DualLaneCrossEngine` | cloud disagrees with both locals | `CONTESTED` | `replan_node` |
| `DualLaneCrossEngine` | cloud agrees with 1 local, locals disagree with each other | `CONTESTED` | `replan_node` |
| any | After `replan_max=3` exhaustion | `EXHAUSTED_REPLAN` | `unverifiable_finalize_node` |
| any | Tool / sandbox / args exhaustion (see §6 + `FAILURE_MODES.md`) | `UNVERIFIABLE` | `finalize_node` (with `failure_reason` set) |

**Empty-set rule:** if any quorum participant returns `parsed_artifacts=[]` (zero findings — e.g., GLM crashed silently, executor branch timed out per R6), it is treated as DISAGREEMENT for Jaccard / pair-agreement purposes. Empty-set is **never** a null vote that lets the non-empty engine win by default. Otherwise an executor that crashes silently becomes a free pass for the other lane and destroys the cross-engine guarantee.

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
│                 │  → clarify sub-state (re-prompts within
│                 │  the same node, not a separate top-level
│                 │  node — total node count stays 8).
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
    VETTED_*        CONTESTED                  UNVERIFIABLE
         │              │                           │
         ▼              ▼                           ▼
   finalize_node   replan_node                unverifiable_
   (HMAC sign)     (max 3, then               finalize_node
                   unverifiable_              (writes status,
                   finalize)                   ledger event,
                                               interrupt() for HITL)
```

### Comprehension-gate clarify budget

The clarify sub-state is bounded by `max_clarify_iterations=2`. After two re-prompts with persistent executor mismatch on `(parsed_positive_hypothesis_ids, parsed_negative_hypothesis_ids, parsed_success_criteria_hash)`, the gate emits `CONTESTED` and routes to `replan_node` with hint `comprehension_persistent_mismatch: executors disagreed on {field} after 2 clarify rounds`. Without this cap, the gate could re-prompt indefinitely; the graph would never reach `replan_max=3` and would simply hang.

### Pivot vs. replan distinction

Real DFIR pivots 8–15 times per investigation; v4.4 research showed that bounded `replan_max=3` is a research-paper budget, not a DFIR budget. Two distinct flows:

- **PIVOT** (cheap, `pivot_max=15`): single Hypothesis added on basis of an executor's output. Re-enters `executor_work` only. Use when "tool emitted weird parent process → check parent's hash."
- **REPLAN** (expensive, `replan_max=3`): full plan rewrite. Re-enters `planner_node` with conflict surfaced as hint. Use only on quorum CONTESTED.
- **At replan iteration 4:** `unverifiable_finalize_node` writes `Finding(status=UNVERIFIABLE)`, writes `LedgerEntry(event_type="exhausted_replan")`, calls `interrupt()` for HITL. Analyst can `update_state` and resume, or accept UNVERIFIABLE.

### Pivot state-merge contract

When `pivot_node` adds a hypothesis it appends one entry to `InvestigationPlan.hypotheses` and re-enters `executor_fanout`. The fanout runs the 4 branches against the **single new hypothesis only** (not the full hypothesis list — re-running prior hypotheses would inflate the ledger and double-count for quorum). The fanout reducer **appends** the new findings to `case.findings` with no deduplication; downstream `quorum_node` does the per-hypothesis grouping. State invariant after N pivots: `len(case.findings) ≈ 4 × (initial_hypotheses + N)`, modulo branch timeouts (see `FAILURE_MODES.md`).

### Interrupt idempotency contract

LangGraph restarts a node from the beginning after `interrupt()` resumes. Therefore any node that performs side effects before calling `interrupt()` must be idempotent. `unverifiable_finalize_node` writes its `exhausted_replan` ledger entry with a deterministic idempotency key: `case_id + chain_id + hypothesis_id + replan_iteration + "exhausted_replan"`. On resume, it first checks the ledger for that key; if present, it skips the write and only re-emits the interrupt payload. Non-idempotent ledger writes before `interrupt()` are forbidden.

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

### CaveatID — Tier-1 examiner caveats from `CLAUDE.md` §3.3

```python
class CaveatID(StrEnum):
    AMCACHE_LASTMODIFIED_NOT_EXEC = "AMCACHE_LASTMODIFIED_NOT_EXEC"
    SHIMCACHE_ORDER_CHANGED_WIN81 = "SHIMCACHE_ORDER_CHANGED_WIN81"
    PREFETCH_SSD_DISABLED = "PREFETCH_SSD_DISABLED"
    MFT_SI_STOMPABLE = "MFT_SI_STOMPABLE"
    USNJRNL_WRAPS = "USNJRNL_WRAPS"
    LOGON_TYPE_3_VS_10 = "LOGON_TYPE_3_VS_10"
    SYSMON_PROCESSGUID_OVER_PID = "SYSMON_PROCESSGUID_OVER_PID"
```

Loaded into every executor system prompt via `src/verdict/planning/prompts/examiner_caveats.md`.

### ArtifactClass — multi-source corroboration vocabulary

```python
class ArtifactClass(StrEnum):
    PREFETCH = "prefetch"
    AMCACHE = "amcache"
    SHIMCACHE = "shimcache"
    EVTX_4624 = "evtx_4624"
    EVTX_4688 = "evtx_4688"
    SYSMON_1 = "sysmon_1"
    NETWORK = "network"
    REGISTRY_RUN = "registry_run"
    TASK_SCHEDULER = "task_scheduler"
    WMI_SUBSCRIPTION = "wmi_subscription"
    MFT = "mft"
    USNJRNL = "usnjrnl"
    PROCESS_MEMORY = "process_memory"
    YARA_HIT = "yara_hit"
    SIGMA_HIT = "sigma_hit"
```

### Playbooks — SANS canonical tool sequencing

Three YAMLs in `src/verdict/playbooks/` (memory.yml / disk.yml / triage.yml) encode the SANS-canonical sequencing summarized in `CLAUDE.md` §7 and this document's forensic doctrine. Loaded into planner system prompt at case_init based on detected evidence type.

`memory.yml` example rule (DKOM detection):
```yaml
- order: 3
  tool: vol3.windows.psscan
  rule: "DKOM_divergence: set(psscan_pids) - set(pslist_pids) ≠ ∅
         → Hypothesis(T1014, high, [PROCESS_MEMORY])"
```

This is one of the architecture's clearest moats — DKOM/T1014 detection auto-fires from the divergence between `pslist` (active list walk) and `psscan` (EPROCESS pool memory signature scan). Free in code, encoded as schema, and a 30-second demo segment.

### Hunt Evil baseline

`src/verdict/knowledge/hunt_evil.yml` keyed by process name with expected parent / path / signing / instance count for 8 canonical Windows processes (svchost, lsass, csrss, winlogon, services, wininit, explorer, smss). `ProcessBaselineAnomaly` Hypothesis subtype maps to `T1036.005` (Match Legitimate Name or Location). Catches `scvhost.exe` with parent `cmd.exe` automatically.

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
        "sandbox_failure", "planner_cot", "case_conclusion",
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
    microsandbox_version: str
    rootfs_sha256: str
    tool_version: str
    kernel_version: str

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

## 6. Tool surface (12 SIFT tools, 23 wrappers)

| Tool family | Wrappers |
|---|---|
| Volatility 3 | `windows.{pslist,psscan,pstree,cmdline,dlllist,malfind,netscan,svcscan,handles,callbacks}` (10 typed plugin wrappers; `windows.info` is invoked through the generic vol3 allow-list — see §6 *Tool-call argument validation*) |
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

Microsandbox is Apache-2.0 and is the primary v1 sandbox, but it is beta software. VERDICT treats it as a tested isolation layer, not an infallible production boundary: every release run must verify read-only `/evidence` mounts, `network=False` defaults, rootfs SHA pinning, and the fallback path to bubblewrap/nsjail for hosts where libkrun/KVM is unavailable.

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

Pattern 2 intentionally allows TSI-mediated egress to a single allowlisted origin; nothing else. Specifying `network_policy=TSI(...)` implicitly enables network at the libkrun layer (vsock-routed to the host TSI proxy) — this is *not* a contradiction with Pattern 1's `network=False`, it's the explicit opposite case for the narrow set of tools that need outbound HTTPS. API key never enters the VM. Proven via tcpdump comparison: bearer header on egress to `opencti.local:8080`, NOT inside the microvm.

### Tool-call argument validation

Pydantic-AI `args_validator` runs *before* `microsandbox.spawn`:
- vol3: validate plugin against allow-list (parse `vol3 --help` once at startup, hash-pin); `--pid` is positive int; reject unknown flags.
- plaso: pre-validate filter expression with `psteal --validate-filter` in ephemeral sandbox.
- Hayabusa: validate timeline-flag combinations against playbook matrix.

On validation failure: raise `ModelRetry`, bounded by `tool_arg_retry_max=2`, then UNVERIFIABLE.

When `tool_arg_retry_max` exhausts, the executor emits `Finding(status=UNVERIFIABLE, artifact_paths=[], caveats_acknowledged=[], failure_reason="tool_args_failed_validation_after_2_retries")`. This would normally fail the `Finding._artifact_paths_min_length=2` and execution-class corroboration validators; the schema exempts UNVERIFIABLE findings via the `_unverifiable_relaxes_corroboration` validator branch — when `Finding.status == UNVERIFIABLE` AND `Finding.failure_reason` is set, `artifact_paths` and `caveats_acknowledged` may be empty. The same exemption covers `failure_reason ∈ {sandbox_spawn_failed, tsi_proxy_unreachable, branch_timeout}` (see `FAILURE_MODES.md`).

### No-evil case conclusion

Benign or red-herring cases do not produce a `Finding` with empty artifacts. They produce a separate `CaseConclusion` object:

```python
class CaseConclusion(BaseModel):
    status: Literal["NO_EVIL_FOUND", "EVIL_FOUND", "UNVERIFIABLE"]
    playbook_steps_executed: list[str] = Field(min_length=1)
    evidence_hashes: dict[Path, str]
    rationale: str
```

`NO_EVIL_FOUND` must cite completed playbook steps and evidence hashes, not absent artifacts. This keeps `Finding.artifact_paths min_length=2` intact for positive claims while giving benign evals a first-class, auditable terminal state. `NO_EVIL_FOUND` is a case-level conclusion, not a `VerdictStatus` enum value.

### Sanitization for prompt injection

`src/verdict/tools/sanitization.py` scans tool stdout for prompt-injection patterns (`IGNORE PREVIOUS`, `SYSTEM:`, `</tool_call>`, `[INST]`, `### Instruction`, common jailbreak suffixes). Detected → `ToolOutput.sanitization_flags` populated; surfaced to planner. Defense against malicious memory images where attacker-controlled strings end up in `vol3.cmdline` output.

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
| Sandbox primary | Microsandbox (libkrun microVM; beta, verified per release) | Apache-2.0 |
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

The 4-fixed-branch fanout topology in v1 is an explicit architectural constraint. v2 expansion to 5+ branches is supported by the LangGraph reducer pattern. See `RELEASE.md` for the current v1 scope and v2 deferrals.

---

## 9. Threat model (4 surfaces)

Documented in `RELEASE.md` per `BUILD_PLAN.md` Phase W1.G.1.

| Surface | Mitigation | Residual risk |
|---|---|---|
| **Insider analyst** with HMAC key access | TPM-backed key if `/dev/tpmrm0`, else gpg-encrypted with passphrase | Cleared analyst with both physical access + passphrase can forge ledger; out of scope for v1 |
| **Prompt injection from evidence** (malicious cmdline/path strings in memory image) | Sanitization scanner on tool stdout; `ToolOutput.sanitization_flags` surfaced to planner; structured-output parsing as primary defense | Novel jailbreak patterns may evade sanitization |
| **Malicious tool output** (forensic tool exploited via crafted memory image) | Microsandbox isolation (libkrun microVM, network=False, read-only evidence mount, destroyed after each call) | Microsandbox escape — accepted v1 risk; v2 evaluates kata-containers |
| **External attacker on SIFT box** | Out of scope for v1 — accept SIFT as trusted host | Standard host-hardening responsibility of operator |

**Known gap:** the model itself as adversary (CoT exfiltration via gzipped reasoning ledger entries or Atropos trajectory exports) is not addressed in v1. Planner CoT capture goes to ledger AND first 8KB to Langfuse span. With Langfuse self-hosted air-gap-side, the CoT never leaves the box. If any operator exports an Atropos trajectory for fine-tuning, evidence-derived data leaks. Documented as accepted v1 risk; v2 addresses via CoT redaction pipeline.

---

## 10. Demo sequence (5 min, two-pane recording)

Detailed in `BUILD_PLAN.md` W6.A.1 + `docs/spec/03-audit-v4.5.md` lines 855–865.

```
0:00–0:30  Cold open + architecture flash
0:30–1:30  CLOUD-ONLY (60s) — n=3 self-consistency, three seeds
1:30–3:00  AIR-GAP (90s) — 7 hero beats:
           ⓵ DKOM divergence (pslist+psscan) → T1014 auto
           ⓶ Hunt Evil masquerade (scvhost.exe parent=cmd.exe)
           ⓷ Amcache caveat acknowledged in rationale
           ⓸ Pivot in action (1 pivot, 0 replans)
           ⓹ Disagreement → CONTESTED → replan → VETTED_AIRGAP ★
              (Devpost-required "self-correction sequence")
           ⓺ TSI tcpdump proof
           ⓻ Kill -9 between super-steps + verdict resume
3:00–4:00  DUAL (60s) — three-way verification → VETTED_DUAL
4:00–5:00  Architecture recap + per-mode accuracy table
```

Every hero beat must land cleanly; record beats as separate clips during weeks 4-5 (one beat per session, locked when good), then assemble in week 6.

---

## 11. Open architectural concerns (worth Tim's eye)

These were raised during the v4.4 research and v4.5 system-design review. They're not blockers; they're worth thinking through during build.

1. **Cross-family verification's epistemic foundation has a known weakness:** correlated false negatives. If both Qwen3 and GLM miss a rare LOLBin pattern (post-pretraining-cutoff persistence technique) because their training corpora share the same gap, both agree "no evil found" and quorum fires green on a wrong-negative. Empirical disagreement-correlation measurement in W4.G.1 will show this; no architectural fix in v1, just honest disclosure in `RELEASE.md`.

2. **Schema strictness vs recall tradeoff.** `Finding` validators reject sloppy findings — good for credibility, but each invariant is a place a *legitimate* finding gets rejected for the wrong reason. Mitigation: have `executor_work` *infer* `artifact_classes` deterministically from `artifact_paths` (e.g. paths matching `\Prefetch\*.pf` → `PREFETCH`) so the LLM never has to know the enum exists. Validator-as-projection rather than validator-as-gate.

3. **"No evil found" verdict is unmodeled.** `Finding.artifact_paths min_length=2` rejects null findings. Some engineered cases will be benign-with-red-herrings. Need a `NegativeFinding` schema variant citing playbook *steps executed* rather than artifact paths. Currently a v1 gap.

4. **Plan-then-Execute is fundamentally batch; DFIR is fundamentally adaptive.** `pivot_max=15` recreates ReAct in a more constrained form. If demo runs show 90% sequential pivots, the topology pays overhead for a parallelism that doesn't materialize. Lean the demo narrative on the *audit-trail review story* (sequential is fine; structure is what reviewability needs) rather than runtime parallelism.

5. **The 4-fixed-fanout cap is real but documented.** `RELEASE.md` names the v2 extension points (5th `net_executor`, 5th `live_executor`).

---

## 12. What's NOT in this doc — see other authorities

| Need | Doc |
|---|---|
| Day-by-day TDD task list | `BUILD_PLAN.md` |
| Devpost rule mapping | `DEVPOST_COMPLIANCE.md` |
| Failure-mode semantics | `FAILURE_MODES.md` |
| Case / reverify chain isolation | `CASE_ISOLATION.md` |
| "Why we picked X over Y" decision rationale | `docs/spec/03-audit-v4.5.md` |
| v4.4 agentic + DFIR research findings (raw) | `docs/spec/02-audit-v4.4.md` |
| v4.6 schema patches (raw spec) | `docs/spec/04-spec-plan-v4.6.md` |
| Project-wide build conventions | `../CLAUDE.md` |
| Tier-1 examiner caveat source | `../CLAUDE.md` §3.3 and `../src/verdict/planning/prompts/examiner_caveats.md` |
| Tool sequencing playbook source | `../src/verdict/playbooks/*.yml` and `docs/ARCHITECTURE.md` §4 |
