# Appendix A — Schema bundle (copy-paste ready)

## A.1 — `verdict/schemas/artifact_class.py`

```python
from enum import Enum

class ArtifactClass(str, Enum):
    """Multi-artifact corroboration vocabulary.
    SANS FOR500 doctrine: no single artifact proves execution.
    Cited from project agent-config/MEMORY.md ≥2-artifact rule."""
    PREFETCH = "prefetch"
    AMCACHE = "amcache"
    SHIMCACHE = "shimcache"
    EVTX_4688 = "evtx_4688"               # Process Creation
    SYSMON_1 = "sysmon_1"                 # Sysmon ProcessCreate
    NETWORK = "network"                   # netscan, conn logs
    REGISTRY_RUN = "registry_run"
    TASK_SCHEDULER = "task_scheduler"
    WMI_SUBSCRIPTION = "wmi_subscription"
    MFT = "mft"                           # $MFT, $J/UsnJrnl
    PROCESS_MEMORY = "process_memory"     # malfind/RWX/hollowed
    YARA_HIT = "yara_hit"
    SIGMA_HIT = "sigma_hit"
```

## A.2 — `verdict/schemas/caveat_id.py`

```python
from enum import Enum

class CaveatID(str, Enum):
    """Tier-1 caveats from project agent-config/MEMORY.md.
    These are the misreads Rob Lee uses to spot a fake examiner."""
    AMCACHE_LASTMODIFIED_NOT_EXEC = "amcache_lastmodified_neq_execution"
    SHIMCACHE_ORDER_CHANGED_WIN81 = "shimcache_order_lru_pre81_insertion_post81"
    PREFETCH_SSD_DISABLED = "prefetch_disabled_on_ssd_or_gpo"
    MFT_SI_STOMPABLE = "mft_si_timestomp_use_fn"
    USNJRNL_WRAPS = "usnjrnl_wraps_treat_gaps_carefully"
    LOGON_TYPE_3_VS_10 = "evtx_4624_type3_network_neq_type10_rdp"
    SYSMON_PROCESSGUID_OVER_PID = "sysmon_processguid_correlation_key_not_pid"
```

## A.3 — `verdict/schemas/evidence.py`

```python
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel
from typing import Literal

EvidenceType = Literal["memory", "disk_image", "event_log", "pcap", "registry_hive", "other"]

class EvidenceItem(BaseModel):
    path: Path
    sha256_at_init: str
    size_bytes: int
    discovered_at: datetime
    evidence_type: EvidenceType

class EvidenceManifest(BaseModel):
    case_id: str
    items: list[EvidenceItem]
    manifest_hash: str  # blake3 of sorted (path, sha256) pairs
    schema_version: int = 1
```

## A.4 — `verdict/schemas/tool_output.py`

```python
from pathlib import Path
from pydantic import BaseModel, Field

class Artifact(BaseModel):
    artifact_id: str       # ULID
    evidence_path: Path
    artifact_type: str     # "process" | "registry_value" | "event" | etc.
    raw_fields: dict
    extraction_confidence: float = 1.0

class ToolOutput(BaseModel):
    tool_name: str         # "vol3.windows.pslist"
    tool_version: str      # "vol3 2.10.0"
    invocation_args: list[str]
    invocation_hash: str   # blake3(name + version + args + evidence_hash)
    stdout_hash: str       # SHA-256 of raw stdout
    stderr_hash: str
    exit_code: int
    parsed_artifacts: list[Artifact]
    parse_warnings: list[str] = []
    sanitization_flags: list[str] = []  # prompt-injection patterns detected
    schema_version: int = 1
```

## A.5 — `verdict/verification/cloud_self_consistency.py`

```python
from blake3 import blake3
import asyncio

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

class CloudSelfConsistency:
    async def verify(self, plan, evidence_hash):
        s1, s2, s3 = derive_seeds(plan.case_id)
        samples = await asyncio.gather(*[
            self.claude.complete(plan, temperature=0.7, seed=s)
            for s in (s1, s2, s3)
        ])
        return await self.usc_judge(samples, plan)  # Chen 2023
```

(Other schemas — Hypothesis, InvestigationPlan, Finding, LedgerEntry — are large; reference v4.5 lines 195–290 + v4.6 schema patch sections.)

---

# Appendix B — System prompt templates

## B.1 — `verdict/planning/prompts/examiner_caveats.md`

```markdown
# Examiner Caveats — Tier-1 (always loaded)

## AMCACHE_LASTMODIFIED_NOT_EXEC
Amcache `LastModified` reflects catalog registration time, NOT execution time. Execution claims based on Amcache alone are unsafe; require corroboration from Prefetch, EVTX 4688, or Sysmon EID 1.

## SHIMCACHE_ORDER_CHANGED_WIN81
ShimCache ordering is LRU on Windows ≤8 and insertion-order on Windows ≥8.1. Do not assume chronological order on modern Windows.

## PREFETCH_SSD_DISABLED
Prefetch may be disabled on SSDs by GPO or driver default. Absence of a Prefetch entry is not evidence of non-execution.

## MFT_SI_STOMPABLE
`$STANDARD_INFORMATION` timestamps are stompable by user-mode malware (e.g. timestomp). Prefer `$FILE_NAME` timestamps for evidentiary claims.

## USNJRNL_WRAPS
The USN Journal is a circular buffer; gaps may reflect wrapping rather than tampering. Treat absence carefully.

## LOGON_TYPE_3_VS_10
EVTX 4624 Logon Type 3 = network logon (SMB / API). Type 10 = RemoteInteractive (RDP). Conflating these mis-attributes intrusion vectors.

## SYSMON_PROCESSGUID_OVER_PID
Sysmon EID 1 `ProcessGuid` is the correlation key. PID is reused; never use PID across time windows.
```

## B.2 — `verdict-skills/windows-triage/SKILL.md`

```markdown
---
name: windows-triage
description: Windows host triage — registry persistence, EVTX, Prefetch/Amcache, MFT, process baselines.
required_tools:
  - vol3.windows.pslist
  - vol3.windows.psscan
  - vol3.windows.pstree
  - vol3.windows.cmdline
  - vol3.windows.malfind
  - vol3.windows.svcscan
  - mftecmd
  - recmd
  - pecmd
  - hayabusa.csv_timeline
  - hayabusa.filter
optional_tools:
  - vol3.windows.dlllist
  - vol3.windows.handles
  - bulk_extractor
  - exiftool
mitre_techniques_in_scope: [T1055, T1543.003, T1547, T1218, T1036.005, T1059, T1014]
---

# Windows Triage skill

Investigate a Windows endpoint compromise. Apply Tier-1 caveats. Cross-corroborate execution claims against ≥2 artifact classes.
...
```

## B.3 — `verdict-skills/windows-triage/KNOWLEDGE.md`

LOLBin cmdline-shape catalog. Includes regsvr32 (T1218.010), rundll32 (T1218.011), mshta (T1218.005), wmic (T1047), certutil (T1140), bitsadmin (T1197) with example invocation patterns and expected legitimate vs malicious indicators.

---

# Appendix C — Playbook + knowledge YAMLs

## C.1 — `verdict/playbooks/memory.yml`

```yaml
evidence_type: memory
first_move: windows.info
steps:
  - {order: 1,  tool: vol3.windows.info,     mitre_technique_hint: null}
  - {order: 2,  tool: vol3.windows.pslist,   mitre_technique_hint: null}
  - {order: 3,  tool: vol3.windows.psscan,   mitre_technique_hint: null,
                rule: "DKOM_divergence: set(psscan_pids) - set(pslist_pids) ≠ ∅ → Hypothesis(T1014, high, [PROCESS_MEMORY])"}
  - {order: 4,  tool: vol3.windows.pstree,   depends_on: [2]}
  - {order: 5,  tool: vol3.windows.cmdline,  depends_on: [2],
                rule: "LOLBIN_match: cmdline pattern in lolbins.yml → Hypothesis(T1218.<sub>, high)"}
  - {order: 6,  tool: vol3.windows.dlllist,  depends_on: [5]}
  - {order: 7,  tool: vol3.windows.malfind,  mitre_technique_hint: T1055,
                rule: "RWX_no_pe: T1055.002; hollowed_pe: T1055.012; reflective: T1055.001"}
  - {order: 8,  tool: vol3.windows.netscan,  mitre_technique_hint: T1071}
  - {order: 9,  tool: vol3.windows.svcscan,  mitre_technique_hint: T1543.003}
  - {order: 10, tool: vol3.windows.handles,  depends_on: [2]}
  - {order: 11, tool: vol3.windows.callbacks, mitre_technique_hint: T1014}
```

## C.2 — `verdict/playbooks/disk.yml`

```yaml
evidence_type: disk_image
first_move: image_hash_verify
steps:
  - {order: 1,  tool: image_hash_verify,    rule: "verify against case_init manifest"}
  - {order: 2,  tool: mmls,                 mitre_technique_hint: null}
  - {order: 3,  tool: fsstat,               depends_on: [2]}
  - {order: 4,  tool: fls,                  depends_on: [3]}
  - {order: 5,  tool: mftecmd,              depends_on: [4],
                rule: "use $FN timestamps for evidentiary claims; $SI is stompable"}
  - {order: 6,  tool: recmd,                mitre_technique_hint: T1547,
                rule: "Run/RunOnce/IFEO/Services hives = persistence top-5"}
  - {order: 7,  tool: pecmd,                mitre_technique_hint: T1059,
                rule: "Prefetch ≥1 run + last_run within evidence window = execution corroboration"}
  - {order: 8,  tool: hayabusa.csv_timeline, depends_on: [4]}
  - {order: 9,  tool: hayabusa.filter,       depends_on: [8],
                rule: "filter by time_range from prior findings via pivot"}
  - {order: 10, tool: plaso.extract,         depends_on: [9]}
  - {order: 11, tool: psort.filter,          depends_on: [10]}
  - {order: 12, tool: bulk_extractor,        depends_on: [4]}
```

## C.3 — `verdict/playbooks/triage.yml`

```yaml
evidence_type: triage
first_move: unzip_to_readonly_mount
steps:
  - {order: 1,  tool: unzip_to_readonly_mount, rule: "KAPE/Velociraptor zip → /evidence read-only"}
  - {order: 2,  tool: recmd,                   mitre_technique_hint: T1547}
  - {order: 3,  tool: pecmd,                   mitre_technique_hint: T1059}
  - {order: 4,  tool: amcache_parse,           mitre_technique_hint: null,
                rule: "ALWAYS acknowledge AMCACHE_LASTMODIFIED_NOT_EXEC caveat"}
  - {order: 5,  tool: hayabusa.csv_timeline,   depends_on: [1]}
  - {order: 6,  tool: hayabusa.filter,         depends_on: [5]}
  - {order: 7,  tool: mftecmd,                 depends_on: [1]}
  - {order: 8,  tool: bulk_extractor,          depends_on: [1]}
```

## C.4 — `verdict/knowledge/hunt_evil.yml`

(Per W1.F.9 task body. 8 entries: svchost, lsass, csrss, winlogon, services, wininit, explorer, smss.)

## C.5 — `verdict/knowledge/lolbins.yml`

```yaml
- binary: regsvr32.exe
  mitre_technique: T1218.010
  legitimate_shapes:
    - 'regsvr32 /s <vendor_dll>'
  malicious_shapes:
    - 'regsvr32 /s /u /n /i:http*'
    - 'regsvr32 /s /u /n /i:\\\\*'
  detection_hint: "scrobj.dll on cmdline = scriptlet abuse"

- binary: rundll32.exe
  mitre_technique: T1218.011
  legitimate_shapes:
    - 'rundll32 <vendor_dll>,<exported_func>'
  malicious_shapes:
    - 'rundll32 javascript:'
    - 'rundll32 *,DllRegisterServer'
  detection_hint: "rundll32 with no comma + DLL = suspicious"

- binary: mshta.exe
  mitre_technique: T1218.005
  malicious_shapes: ['mshta http*', 'mshta vbscript:']

- binary: wmic.exe
  mitre_technique: T1047
  malicious_shapes: ['wmic process call create*', 'wmic /node:* process call create']

- binary: certutil.exe
  mitre_technique: T1140
  malicious_shapes: ['certutil -urlcache -split -f http*', 'certutil -decode*']

- binary: bitsadmin.exe
  mitre_technique: T1197
  malicious_shapes: ['bitsadmin /transfer * http*']
```

---

# Appendix D — Demo sequence (refined for v4.6)

Per W6.A.1 task. References v4.5 lines 855–865 plus v4.4 hero beats. See `docs/DEMO_SEQUENCE.md` post-W6.A.1 for full timing.

Key beats for the 5-min cut:

- **0:00–0:30** Cold open + architecture diagram flash with v4.6 node sequence (planner → planner_critique → comprehension_gate → executor_fanout → pivot → quorum → replan/unverifiable_finalize).
- **0:30–1:30** Cloud-only mode, n=3 with three distinct seeds at temp=0.7 (narrate "different seeds, same case ID for reproducibility"). Three Langfuse sibling spans converging.
- **1:30–3:00** Air-gap hero shot. Pull the cable. Comprehension gate fires. Hero beat 1: pslist+psscan DKOM divergence → T1014. Hero beat 2: Hunt Evil masquerade catch (`scvhost.exe` parent=cmd.exe). Hero beat 3: Amcache caveat acknowledgment in Finding rationale. Hero beat 4: pivot in action (1 pivot, 0 replans). Hero beat 5: Qwen3-vs-GLM disagreement → CONTESTED → replan → VETTED_AIRGAP. Hero beat 6: tcpdump TSI proof. Hero beat 7: kill -9 between super-steps + `verdict resume`.
- **3:00–4:00** Dual mode (new case, mode-locked). Three-way verification → VETTED_DUAL.
- **4:00–5:00** Architecture recap + accuracy table per mode (hallucination, agreement, FP rates, step_efficiency, MITRE sub-technique precision, negative-hypothesis quality, Qwen3-vs-GLM disagreement correlation).

---

# Appendix E — SANS judge credibility checklist

(15-item list per W6.B.1. Record demo against this; iterate dry runs until all 15 tick green.)

1. Image hash verified before opening evidence
2. SANS-canonical first move (`windows.info` for memory; `mmls`+`fsstat` for disk)
3. pslist + psscan run, divergence checked
4. ≥2 artifact classes per execution claim, named in rationale
5. Amcache caveat acknowledged when Amcache cited
6. UTC `Z` suffix on all timestamps
7. At least one pivot fired (response to prior tool output, not initial plan)
8. Epistemic vocabulary spoken aloud (hypothesis / inferred / confirmed mapped to verdict status)
9. MITRE sub-techniques (`T1055.012` not `T1055`)
10. Hunt Evil baseline catches process-name masquerade
11. Never asserts attribution ("Evidence consistent with X" not "X did this")
12. Ledger records tool version + rootfs SHA + microsandbox version per call
13. End-to-end <20 minutes
14. Agent gives up explicitly (UNVERIFIABLE + interrupt) when it can't resolve
15. planner_critique_node fires visibly in Langfuse trace
