# VERDICT v4.6 — Spec Plan

**Document type:** Spec amendment + TDD execution plan (not another audit doc).
**Status:** Ready to execute.
**Deadline:** End of week 1 (May 8, 2026). Schemas freeze before week 2.
**Authority:** v4.5 remains the architecture document; v4.6 is amendments-in-place plus a TDD task list. Where v4.6 contradicts v4.5, v4.6 wins for the items it touches and v4.5 stands for everything else. For Devpost rule compliance (final submission deadline Jun 15 11:45 PM EDT), authority is `DEVPOST_COMPLIANCE_CHECKLIST.md` — v4.6 covers the schema/forensic-discipline subset only.

## What v4.6 fixes

Five items dropped between v4.4 → v4.5 that materially affect either correctness (the n=3 seed bug → silent n=1) or judge-credibility (no artifact-pair rule, no Tier-1 caveats, no DKOM, no playbooks). Each is small in code or content; the cluster is the difference between "AI agent doing forensics" and "forensic agent that survives Rob Lee's gut-check."

| ID | Type | What | Owner | Estimate |
|---|---|---|---|---|
| F1 | code | Seed-derivation fix (CloudSelfConsistency) | Beaver | 1h |
| F2 | code + docs | PreToolUse Layer-1 caveat + CI smoke test scaffold | Tim | 30m |
| F3 | code | `Finding` schema patches (artifact_paths min_length=2, artifact_classes enum, caveats_acknowledged, two validators) | Tim | 2h |
| F4 | docs + content | Add `windows.psscan` to tool list + DKOM divergence rule in `playbooks/memory.yml` | Tim + KP | 30m |
| F5 | content | Three playbook YAMLs (memory/disk/triage), `examiner_caveats.md`, `hunt_evil.yml` | KP | 1.5d |

**Net cost:** ~2 teammate-days. Tim 0.5, KP 1.5, Beaver 0.1.
**Net benefit:** five rubric-aligned credibility hits + one silent-bug elimination. All five hit `agent-config/MEMORY.md` Tier-1 rules the project already encodes — v4.6 surfaces them in the audit doc and the schemas.

## Spec amendments to v4.5 (in-place text patches)

Apply these to `VERDICT_AUDIT_v4.5.md` before any code lands. They keep v4.5's narrative coherent with the v4.6 schema changes.

### Patch P1 — Verifier strategy (v4.5 line 52-56)

REPLACE:
```python
class CloudSelfConsistency(VerifierStrategy):
    """n=3 samples from Claude with deterministic seeds, ≥2-of-3 must agree.
    NOT TRUE VERIFICATION — same model shares failure modes. Returns VETTED_CLOUD
    on agreement, DRAFT_CLOUD otherwise. Findings remain DRAFT pending human review.
    Internally: Claude plans, Claude executes 3× with different seeds, Claude grades."""
```

WITH:
```python
class CloudSelfConsistency(VerifierStrategy):
    """n=3 samples from Claude at temperature=0.7 with three case_id-derived
    seeds (NOT deterministic-temp-0; that collapses to n=1 because same seed +
    same prompt = identical output — Wang et al. 2022 self-consistency requires
    diverse paths). Reproducibility-with-diversity: re-running the case yields
    the same three samples (audit-friendly), but the three samples differ from
    each other (verifier-friendly). ≥2-of-3 agreement → VETTED_CLOUD; below
    threshold → DRAFT_CLOUD. NOT TRUE VERIFICATION — same model shares failure
    modes."""
```

### Patch P2 — Architecture caption (v4.5 line 144)

APPEND to existing caption:
> Layer 1 (Claude Code PreToolUse hook) is best-effort given anthropics/claude-code issues #33106 (`permissionDecision: "deny"` not enforced for MCP server tool calls) and #37210 (deny ignored for Edit tool). Since the entire SIFT toolset is wired through FastMCP + microsandbox-mcp, this is not a corner case. The architectural guarantee carries on Layer 2 (LangGraph `executor_work`/`DenyRuleWrapper` — fires regardless of model) and Layer 3 (Microsandbox read-only mount — kernel-enforced). Tim ships a CI smoke test in week 2 that verifies the installed Claude CLI version actually denies a sample MCP write; build fails on regression.

### Patch P3 — Tool list (v4.5 line 796)

REPLACE:
> `vol3 (pslist, malfind, netscan)`

WITH:
> `vol3 (pslist, psscan, pstree, cmdline, dlllist, malfind, netscan, svcscan, handles, callbacks)`

(Matches what `services/mcp/` already ships per project `CLAUDE.md`.)

### Patch P4 — New caveat (append to v4.5 caveats section)

> **(v4.6) DKOM/T1014 detection wired explicitly.** v4.5's tool list omitted `psscan`. Project `CLAUDE.md` ships `vol_pslist` + `vol_psscan` deliberately as a redundant pair — pslist walks the active list, psscan signature-scans EPROCESS pool memory; divergence between them is the textbook DKOM/T1014 (Rootkit) signature. v4.6 adds psscan to the wrapper set and encodes the divergence check in `playbooks/memory.yml`: `set(psscan_pids) - set(pslist_pids) ≠ ∅` emits `Hypothesis(mitre_technique="T1014.001", confidence=high, artifact_classes=[PROCESS_MEMORY])`. Free demo segment.

### Patch P5 — New caveat (append to v4.5 caveats section)

> **(v4.6) Multi-artifact corroboration enforced at schema layer.** v4.5's `Finding.artifact_paths: list[Path]` accepted `len() == 1`; SANS FOR500 doctrine requires ≥2 artifact classes for execution claims; project `agent-config/MEMORY.md` codifies the rule. v4.6 adds `artifact_paths: Field(min_length=2)`, `artifact_classes: list[ArtifactClass] = Field(min_length=2)`, and a model_validator that rejects single-class execution claims (T1059/T1106/T1204/T1218/T1543/T1547 family). Pairs with `caveats_acknowledged: list[CaveatID]` so any Amcache-citing finding without `AMCACHE_LASTMODIFIED_NOT_EXEC` is rejected at the validator. Forensic-discipline encoded in code, not prompts.

### Patch P6 — New caveat (append to v4.5 caveats section)

> **(v4.6) Tier-1 examiner caveats encoded as system-prompt include.** Project `agent-config/MEMORY.md` lists 7 caveats (Amcache LastModified ≠ execution; ShimCache LRU pre-Win8 vs insertion-order post-Win8.1; Prefetch SSD-disabled; `$MFT $SI` stompable use `$FN`; UsnJrnl wraps; EVTX 4624 Type 3 ≠ Type 10; Sysmon ProcessGuid > PID). v4.6 ships `verdict/prompts/examiner_caveats.md` as an executor system-prompt include and `CaveatID` enum + `Finding.caveats_acknowledged` schema field. Validator enforces caveat acknowledgment when the relevant artifact class is cited.

---

## TDD task plan

Project conventions (per `CLAUDE.md`):
- Write failing test → run RED → implement → run GREEN → commit. One commit per task.
- Conventional Commits: `feat(scope):`, `test(scope):`, `chore(scope):`, `fix(scope):`, `docs(scope):`.
- Never `--no-verify`, `--no-gpg-sign`, or `git commit --amend`.
- Python: `uv` for envs, `pytest` for tests, `ruff` for lint/format. Python 3.11.
- Pinned versions: Pydantic v2, Pydantic-AI MIT, blake3 PyPI.

### Phase 1 — Schema patches (Tim, ~2 hours)

Goal: `Finding` enforces multi-artifact corroboration and caveat acknowledgment at schema layer. Locked before week 2 so all teammates code against the same contract.

**Task 1.1: Add `ArtifactClass` enum**

- [ ] 1.1.a — Write failing test `services/agent/tests/schemas/test_artifact_class.py::test_enum_has_required_members`. Assert all 13 members exist: `PREFETCH`, `AMCACHE`, `SHIMCACHE`, `EVTX_4688`, `SYSMON_1`, `NETWORK`, `REGISTRY_RUN`, `TASK_SCHEDULER`, `WMI_SUBSCRIPTION`, `MFT`, `PROCESS_MEMORY`, `YARA_HIT`, `SIGMA_HIT`. Run `uv run --directory services/agent pytest tests/schemas/test_artifact_class.py -v` → RED.
- [ ] 1.1.b — Implement `verdict/schemas/artifact_class.py` with the enum. Run test → GREEN.
- [ ] 1.1.c — Commit: `feat(schema): add ArtifactClass enum for multi-artifact corroboration`

**Task 1.2: Add `CaveatID` enum**

- [ ] 1.2.a — Write failing test `tests/schemas/test_caveat_id.py::test_enum_covers_tier1_memory_md`. Assert all 7 caveats from `agent-config/MEMORY.md`: `AMCACHE_LASTMODIFIED_NOT_EXEC`, `SHIMCACHE_ORDER_CHANGED_WIN81`, `PREFETCH_SSD_DISABLED`, `MFT_SI_STOMPABLE`, `USNJRNL_WRAPS`, `LOGON_TYPE_3_VS_10`, `SYSMON_PROCESSGUID_OVER_PID`. Run → RED.
- [ ] 1.2.b — Implement `verdict/schemas/caveat_id.py`. Run → GREEN.
- [ ] 1.2.c — Commit: `feat(schema): add CaveatID enum from project MEMORY.md Tier-1 caveats`

**Task 1.3: Patch `Finding.artifact_paths` to `Field(min_length=2)`**

- [ ] 1.3.a — Write failing test `tests/schemas/test_finding.py::test_artifact_paths_min_length_2`. Assert `Finding(artifact_paths=[Path("/a")], ...)` raises `ValidationError`. Run → RED.
- [ ] 1.3.b — Patch `verdict/schemas/finding.py`: `artifact_paths: list[Path] = Field(min_length=2)`. Run → GREEN.
- [ ] 1.3.c — Commit: `feat(schema): require ≥2 artifact paths per Finding (FOR500 corroboration rule)`

**Task 1.4: Add `Finding.artifact_classes` field**

- [ ] 1.4.a — Write failing test `tests/schemas/test_finding.py::test_artifact_classes_min_length_2`. Assert `Finding(..., artifact_classes=[ArtifactClass.PREFETCH])` raises. Assert `Finding(..., artifact_classes=[ArtifactClass.PREFETCH, ArtifactClass.AMCACHE])` does not raise. Run → RED.
- [ ] 1.4.b — Add field to `Finding`: `artifact_classes: list[ArtifactClass] = Field(min_length=2)`. Run → GREEN.
- [ ] 1.4.c — Commit: `feat(schema): add Finding.artifact_classes field with min_length=2`

**Task 1.5: Add `Finding.caveats_acknowledged` field**

- [ ] 1.5.a — Write failing test `tests/schemas/test_finding.py::test_caveats_acknowledged_default_empty`. Assert default is `[]`; assert can construct with non-empty list. Run → RED.
- [ ] 1.5.b — Add field: `caveats_acknowledged: list[CaveatID] = []`. Run → GREEN.
- [ ] 1.5.c — Commit: `feat(schema): add Finding.caveats_acknowledged field`

**Task 1.6: Add execution-claim validator**

- [ ] 1.6.a — Write failing test `tests/schemas/test_finding.py::test_execution_claim_requires_two_classes`. Assert `Finding(mitre_technique="T1059.001", artifact_classes=[ArtifactClass.PREFETCH, ArtifactClass.PREFETCH])` raises ValidationError because `len(set(...)) < 2`. Assert distinct classes pass. Test for each prefix: T1059, T1106, T1204, T1218, T1543, T1547. Run → RED.
- [ ] 1.6.b — Add `@model_validator(mode="after") _execution_claims_need_two_classes` to `Finding`. Run → GREEN.
- [ ] 1.6.c — Commit: `feat(schema): require ≥2 distinct artifact classes for execution-class MITRE techniques`

**Task 1.7: Add Amcache-caveat validator**

- [ ] 1.7.a — Write failing test `tests/schemas/test_finding.py::test_amcache_requires_caveat`. Assert `Finding` with `ArtifactClass.AMCACHE` in classes but `CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC` NOT in caveats_acknowledged raises. Assert it passes when caveat is present. Run → RED.
- [ ] 1.7.b — Add `@model_validator(mode="after") _amcache_caveat_required` to `Finding`. Run → GREEN.
- [ ] 1.7.c — Commit: `feat(schema): require AMCACHE_LASTMODIFIED_NOT_EXEC caveat acknowledgment when Amcache cited`

### Phase 2 — Seed-derivation fix (Beaver, ~1 hour)

Goal: `CloudSelfConsistency` actually samples three diverse paths.

**Task 2.1: Add `derive_seeds(case_id)` helper**

- [ ] 2.1.a — Write failing test `tests/verification/test_derive_seeds.py::test_three_distinct_seeds`. Assert `derive_seeds("case_001")` returns 3 ints, all distinct. Assert `derive_seeds("case_001") == derive_seeds("case_001")` (deterministic). Assert `derive_seeds("case_001") != derive_seeds("case_002")` (case-isolated). Run → RED.
- [ ] 2.1.b — Implement in `verdict/verification/cloud_self_consistency.py`:
  ```python
  def derive_seeds(case_id: str) -> tuple[int, int, int]:
      h = blake3(case_id.encode())
      return tuple(
          int.from_bytes(h.derive_key(f"seed_{k}").digest()[:4], "big")
          for k in ("a", "b", "c")
      )
  ```
- [ ] 2.1.c — Commit: `feat(verification): add derive_seeds(case_id) helper for n=3 self-consistency`

**Task 2.2: Update `CloudSelfConsistency.verify()` to use temp=0.7 + three seeds**

- [ ] 2.2.a — Write failing test `tests/verification/test_cloud_self_consistency.py::test_three_distinct_seeds_in_api_calls`. Mock the Claude API client; assert three `complete()` calls happen with three distinct seeds and `temperature=0.7`. Run → RED.
- [ ] 2.2.b — Implement: parameterize `claude.complete()` calls with `seed=s_n, temperature=0.7` for each of the three derived seeds. Run → GREEN.
- [ ] 2.2.c — Commit: `fix(verification): n=3 self-consistency now samples three diverse paths (Wang 2022)`

**Task 2.3: Apply Patch P1 to v4.5 audit doc**

- [ ] 2.3 — Apply text replacement in `VERDICT_AUDIT_v4.5.md` per Patch P1 above. Commit: `docs(audit): correct v4.5 CloudSelfConsistency docstring per v4.6 P1`

### Phase 3 — PreToolUse Layer-1 caveat + CI scaffold (Tim, ~30 min)

Goal: judges asking about Layer 1's reliability get a confident answer; CI catches Anthropic CLI version drift.

**Task 3.1: CI smoke-test scaffold (xfail-marked)**

- [ ] 3.1.a — Write `tests/smoke/test_pretooluse_deny.py::test_pretooluse_deny_blocks_mcp_write`. Use `pytest.mark.xfail(reason="anthropics/claude-code#33106 — re-evaluate per Claude CLI release")` so it doesn't break CI today but flips green when Anthropic ships the fix. Test invokes `claude` subprocess, configures a PreToolUse hook returning `permissionDecision: "deny"` for an MCP tool call, asserts the call is blocked.
- [ ] 3.1.b — Commit: `test(smoke): scaffold PreToolUse deny verification (xfail pending #33106 + #37210)`

**Task 3.2: Apply Patch P2 to v4.5 audit doc**

- [ ] 3.2 — Append the Layer-1 caveat paragraph to v4.5 architecture caption per Patch P2. Commit: `docs(audit): add v4.6 P2 Layer-1 PreToolUse version-dependence caveat`

### Phase 4 — psscan + DKOM (Tim, ~30 min; KP wires the playbook entry in Phase 5)

Goal: explicit DKOM/T1014 detection. Free demo segment.

**Task 4.1: Add `vol3 windows.psscan` MCP tool wrapper**

- [ ] 4.1.a — Write failing test `services/mcp/tests/test_vol_psscan.rs` (or Python equivalent — match the existing `vol_pslist` wrapper's location/style). Assert wrapper accepts a memory image path and returns a list of PIDs from `vol3 windows.psscan`. Run → RED.
- [ ] 4.1.b — Implement `vol_psscan` wrapper mirroring `vol_pslist`. Run → GREEN.
- [ ] 4.1.c — Commit: `feat(mcp): add vol_psscan wrapper for DKOM/T1014 cross-validation`

**Task 4.2: Apply Patches P3 + P4 to v4.5 audit doc**

- [ ] 4.2 — Update tool list per P3; append DKOM caveat per P4. Commit: `docs(audit): v4.6 P3 + P4 — psscan in tool list, DKOM detection rationale`

### Phase 5 — KP content authoring (~1.5 days)

Goal: planner has a real DFIR methodology to follow; executors carry Tier-1 caveats and Hunt Evil baselines into every prompt.

**Task 5.1: `Playbook` Pydantic schema**

- [ ] 5.1.a — Write failing test `tests/schemas/test_playbook.py::test_playbook_loads_canonical_yaml`. Assert `Playbook.from_yaml("verdict/playbooks/memory.yml")` returns a valid object with at least one `Step`. Run → RED (no schema, no YAML yet).
- [ ] 5.1.b — Implement `verdict/schemas/playbook.py`:
  ```python
  class Step(BaseModel):
      order: int
      tool: str                            # "vol3.windows.pslist"
      depends_on: list[int] = []           # step.order references
      mitre_technique_hint: str | None = None
      rule: str | None = None              # e.g. "DKOM divergence"

  class Playbook(BaseModel):
      evidence_type: Literal["memory", "disk_image", "triage"]
      first_move: str                      # "windows.info" / "mmls"
      steps: list[Step]

      @classmethod
      def from_yaml(cls, path: Path) -> "Playbook": ...
  ```
- [ ] 5.1.c — Commit: `feat(schema): add Playbook + Step schemas for planner methodology injection`

**Task 5.2: Author `verdict/playbooks/memory.yml`**

Required steps in order (port from project `agent-config/PLAYBOOK.md`):
```yaml
evidence_type: memory
first_move: windows.info
steps:
  - {order: 1,  tool: vol3.windows.info,     mitre_technique_hint: null}
  - {order: 2,  tool: vol3.windows.pslist,   mitre_technique_hint: null}
  - {order: 3,  tool: vol3.windows.psscan,   mitre_technique_hint: null,
                rule: "DKOM_divergence: set(psscan_pids) - set(pslist_pids) ≠ ∅ → Hypothesis(T1014.001, high)"}
  - {order: 4,  tool: vol3.windows.pstree,   depends_on: [2]}
  - {order: 5,  tool: vol3.windows.cmdline,  depends_on: [2]}
  - {order: 6,  tool: vol3.windows.dlllist,  depends_on: [5]}
  - {order: 7,  tool: vol3.windows.malfind,  mitre_technique_hint: T1055}
  - {order: 8,  tool: vol3.windows.netscan,  mitre_technique_hint: T1071}
  - {order: 9,  tool: vol3.windows.svcscan,  mitre_technique_hint: T1543.003}
  - {order: 10, tool: vol3.windows.handles,  depends_on: [2]}
  - {order: 11, tool: vol3.windows.callbacks, mitre_technique_hint: T1014}
```
- [ ] 5.2.a — Write failing test `tests/playbooks/test_memory_yml.py::test_memory_playbook_loads_and_has_dkom_rule`. Assert load succeeds; assert step 3 has `rule` containing "DKOM"; assert ordering is contiguous 1..11. Run → RED.
- [ ] 5.2.b — Author `verdict/playbooks/memory.yml`. Run → GREEN.
- [ ] 5.2.c — Commit: `feat(playbooks): memory.yml — SANS canonical Volatility 3 sequence + DKOM divergence rule`

**Task 5.3: Author `verdict/playbooks/disk.yml`**

Required steps:
1. `image_hash_verify` (case_init prerequisite)
2. `mmls`
3. `fsstat`
4. `fls -r`
5. `MFTECmd`
6. `RECmd` registry hives (Run keys, Services, IFEO)
7. `PECmd` Prefetch
8. `hayabusa.csv_timeline` over EVTX
9. `plaso.log2timeline` (last — expensive)
10. `bulk_extractor` for IOCs in slack/unallocated

- [ ] 5.3.a — Write failing test `tests/playbooks/test_disk_yml.py::test_disk_playbook_orders_plaso_after_lighter_tools`. Assert plaso step.order > all of {mmls, fls, MFTECmd, RECmd, PECmd, hayabusa}. Run → RED.
- [ ] 5.3.b — Author `verdict/playbooks/disk.yml`. Run → GREEN.
- [ ] 5.3.c — Commit: `feat(playbooks): disk.yml — registry/MFT/Prefetch before plaso super-timeline`

**Task 5.4: Author `verdict/playbooks/triage.yml`**

Required steps for KAPE/Velociraptor zip extracts:
1. `unzip_to_readonly_mount`
2. registry first (fastest signal)
3. Prefetch / Amcache / ShimCache
4. EVTX
5. MFT
6. unallocated/carving (last)

- [ ] 5.4.a — Write failing test `tests/playbooks/test_triage_yml.py::test_triage_playbook_registry_first`. Assert registry step.order == 2 (after unzip). Run → RED.
- [ ] 5.4.b — Author `verdict/playbooks/triage.yml`. Run → GREEN.
- [ ] 5.4.c — Commit: `feat(playbooks): triage.yml — registry-first sequence for KAPE/Velociraptor zips`

**Task 5.5: Planner system-prompt loader**

- [ ] 5.5.a — Write failing test `tests/planning/test_playbook_loader.py::test_loader_picks_playbook_by_evidence_type`. Given `EvidenceItem(evidence_type="memory")`, assert returned prompt fragment contains "windows.info" and "DKOM". Given `evidence_type="disk_image"`, assert it contains "mmls" but not "DKOM". Run → RED.
- [ ] 5.5.b — Implement `verdict/planning/playbook_loader.py::load_playbook_prompt(evidence_manifest) -> str`. Returns a markdown-formatted system-prompt fragment for injection into `planner_node`. Run → GREEN.
- [ ] 5.5.c — Commit: `feat(planning): playbook loader injects evidence-type-specific methodology into planner prompt`

**Task 5.6: `verdict/prompts/examiner_caveats.md`**

Content template (one section per CaveatID, with the exact text from `agent-config/MEMORY.md`):
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

- [ ] 5.6.a — Write failing test `tests/prompts/test_examiner_caveats.py::test_all_seven_caveats_present`. Load `verdict/prompts/examiner_caveats.md`; assert each `CaveatID.value` appears as an `## ` heading. Run → RED.
- [ ] 5.6.b — Author the markdown file. Run → GREEN.
- [ ] 5.6.c — Commit: `feat(prompts): examiner_caveats.md — Tier-1 caveats from agent-config/MEMORY.md as system-prompt include`

**Task 5.7: Executor system-prompt include**

- [ ] 5.7.a — Write failing test `tests/planning/test_executor_prompt.py::test_executor_prompt_includes_caveats`. Construct an executor prompt; assert it contains "AMCACHE_LASTMODIFIED_NOT_EXEC". Run → RED.
- [ ] 5.7.b — Update `verdict/planning/executor_prompt.py` to include the rendered `examiner_caveats.md` content. Run → GREEN.
- [ ] 5.7.c — Commit: `feat(planning): executor system prompt includes Tier-1 examiner caveats`

**Task 5.8: `verdict/knowledge/hunt_evil.yml`**

Eight canonical Windows process baselines (port from SANS Hunt Evil poster):
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

- process: csrss.exe
  expected_parent: smss.exe
  expected_path_glob: "%SystemRoot%\\System32\\csrss.exe"
  expected_signing: "Microsoft Windows"
  multiple_instances: true   # one per session

- process: winlogon.exe
  expected_parent: smss.exe
  expected_path_glob: "%SystemRoot%\\System32\\winlogon.exe"
  expected_signing: "Microsoft Windows"
  multiple_instances: true   # one per session

- process: services.exe
  expected_parent: wininit.exe
  expected_path_glob: "%SystemRoot%\\System32\\services.exe"
  expected_signing: "Microsoft Windows"
  multiple_instances: false

- process: wininit.exe
  expected_parent: smss.exe   # parent exits, appears orphaned
  expected_path_glob: "%SystemRoot%\\System32\\wininit.exe"
  expected_signing: "Microsoft Windows"
  multiple_instances: false

- process: explorer.exe
  expected_parent: userinit.exe   # parent exits
  expected_path_glob: "%SystemRoot%\\explorer.exe"
  expected_signing: "Microsoft Windows"
  multiple_instances: true   # one per logged-in user

- process: smss.exe
  expected_parent: System
  expected_path_glob: "%SystemRoot%\\System32\\smss.exe"
  expected_signing: "Microsoft Windows"
  multiple_instances: false   # plus transient children
```

- [ ] 5.8.a — Write failing test `tests/knowledge/test_hunt_evil_yml.py::test_eight_canonical_processes_present`. Assert load returns 8 entries; assert each has `process`, `expected_parent`, `expected_path_glob`, `expected_signing`, `multiple_instances`. Run → RED.
- [ ] 5.8.b — Author `verdict/knowledge/hunt_evil.yml`. Run → GREEN.
- [ ] 5.8.c — Commit: `feat(knowledge): hunt_evil.yml — 8 canonical Windows process baselines (SANS Hunt Evil poster)`

**Task 5.9: `ProcessBaselineAnomaly` Hypothesis subtype**

- [ ] 5.9.a — Write failing test `tests/schemas/test_process_baseline_anomaly.py::test_anomaly_records_baseline_diff`. Construct a `ProcessBaselineAnomaly(actual_parent="cmd.exe", expected_parent="services.exe", process="svchost.exe")`; assert `mitre_technique == "T1036.005"`. Run → RED.
- [ ] 5.9.b — Implement in `verdict/schemas/hypothesis.py`. Run → GREEN.
- [ ] 5.9.c — Commit: `feat(schema): ProcessBaselineAnomaly hypothesis subtype maps to T1036.005`

---

## Acceptance criteria — when v4.6 is done

All of these must be true before week 2 begins:

1. [ ] All Phase 1 schema validators reject invalid inputs in unit tests; tests pass against pinned Pydantic v2.
2. [ ] `Finding(artifact_paths=[Path("/a")])` raises `ValidationError`. So does `Finding(..., artifact_classes=[ArtifactClass.PREFETCH])`. So does `Finding(mitre_technique="T1059.001", artifact_classes=[ArtifactClass.PREFETCH, ArtifactClass.PREFETCH])`. So does `Finding(..., artifact_classes=[ArtifactClass.AMCACHE, ArtifactClass.PREFETCH], caveats_acknowledged=[])`.
3. [ ] `derive_seeds("case_001")` returns three distinct ints; calling twice with same case_id returns identical tuple; calling with different case_ids returns different tuples.
4. [ ] `CloudSelfConsistency.verify()` makes three Claude API calls with three distinct `seed=` values and `temperature=0.7`. Verified by mock-call assertion.
5. [ ] CI smoke test scaffold exists at `tests/smoke/test_pretooluse_deny.py`; `pytest -v -m smoke` finds it and reports xfail; smoke job is added to L0 workflow.
6. [ ] `vol_psscan` MCP tool wrapper exists alongside `vol_pslist`; both expose typed Input/Output schemas; integration test runs both against a fixture memory image.
7. [ ] Three playbook YAMLs load through `Playbook.from_yaml()`; `memory.yml` step 3 contains the DKOM divergence rule; `disk.yml` orders plaso after the lighter tools; `triage.yml` has registry as step 2.
8. [ ] `verdict/prompts/examiner_caveats.md` contains all 7 CaveatID values as `## ` headings.
9. [ ] `verdict/knowledge/hunt_evil.yml` contains 8 process entries; each has the 5 required fields.
10. [ ] `VERDICT_AUDIT_v4.5.md` has all six in-place patches (P1–P6) applied; documents and code agree.
11. [ ] `bash scripts/run-all-smokes.sh` (or your equivalent project-level test runner) is fully green.
12. [ ] Single git log line per task; conventional-commits format; no force-pushes; no `--no-verify`.

When all twelve are checked, week 1 schemas are locked. Week 2 begins.

---

## Out of scope — explicitly deferred to v4.7+

Don't do these in v4.6. Each is a real improvement; none is week-1 critical-path. Cluster them into a v4.7 spec plan if scope allows after week 2.

| Item | Source | Defer-to | Cost |
|---|---|---|---|
| `planner_critique_node` (CoVe between planner and comprehension_gate) | v4.4 F5 | v4.7 (week 2) | Beaver 1d |
| Per-tool Pydantic-AI `args_validator` framework | v4.4 F6 | v4.7 (week 2) | Beaver 1.5d |
| `pivot_node` distinct from `replan_node` (`pivot_max=15`, `replan_max=3`) | v4.4 F7 | v4.7 (week 2-3) | Beaver 1d |
| `unverifiable_finalize_node` at replan iteration 4 + `interrupt()` | v4.4 F7 | v4.7 (week 3) | Beaver 0.5d |
| Plaso/Hayabusa split into extract+filter MCP tools | v4.4 F-DFIR-5 | v4.7 (week 2) | Beaver 0.5d |
| `PRAGMA journal_mode=WAL; synchronous=FULL` on SqliteSaver | v4.4 F11 | v4.7 (week 3) | Beaver 0.25d |
| LangGraph fanout/reducer race unit test | v4.4 F10 | v4.7 (week 3) | Beaver 0.25d |
| Timezone Pydantic field validator (UTC-only) | v4.4 F-DFIR-6 | v4.7 (week 2) | KP 0.25d |
| LOLBin cmdline catalog in `verdict-skills/windows-triage/KNOWLEDGE.md` | v4.4 F-DFIR-8 | v4.7 (week 4) | KP 0.5d |
| MITRE sub-technique STIX validation against `github.com/mitre/cti` | v4.5 inherited | v4.7 (week 2) | KP 0.25d |
| `docs/SCOPE.md` (v1 = Windows DFIR; macOS/Linux/Win11/ESXi = v2) | v4.4 F-DFIR-NICE-2 | v4.7 (week 5) | Tim 0.5h |
| `docs/CASE_ISOLATION.md` (RadixAttention prefix-cache vs case-data) | v4.4 F-DFIR-7 | v4.7 (week 3) | Tim 0.5h |
| Per-prompt-budget CI assertion (planner ≤30K, executor ≤20K, critic ≤15K tokens) | v4.4 F9 | v4.7 (week 5) | Tim 0.5d |
| Negative-hypothesis quality validator + Inspect AI scorer | v4.4 F4 | v4.7 (week 4) | KP 0.5d |
| Qwen3-vs-GLM disagreement-correlation measurement on 50-finding ground truth | v4.4 F3 | v4.7 (week 4) | KP 0.5d |
| `Finding.caveats_acknowledged` validators for the other 6 caveats (not just Amcache) | v4.6 follow-on | v4.7 (week 2) | Tim 1h |

---

## How to execute this plan

1. **Today (May 2):** Apply Patches P1, P2, P3, P4, P5, P6 to `VERDICT_AUDIT_v4.5.md` in place. Six text edits, ~30 minutes. Commit per patch.
2. **May 3 (Sat):** Tim does Phase 1 (Tasks 1.1–1.7) end-to-end. Two hours of TDD against the schema module. Beaver does Phase 2 (Tasks 2.1–2.3) — one hour. Tim does Phase 3 (3.1, 3.2) — 30 min.
3. **May 4 (Sun):** Tim does Phase 4 (4.1, 4.2). KP starts Phase 5 (Tasks 5.1, 5.2 — schema + memory.yml).
4. **May 5–7 (Mon–Wed):** KP completes Phase 5 (Tasks 5.3–5.9). Beaver and Tim begin week-2 work against the now-locked schemas.
5. **May 8 (Thu):** Run acceptance criteria checklist. If all 12 green, schemas are locked. Open a tracking issue for v4.7 with the deferred items.

If you slip past May 8, the cascade hits week 2 prompt-engineering and week 3 verifier-strategy work — Beaver and KP will be coding against an unstable schema. Hold the line on the May 8 deadline; descope from v4.6 (drop Phase 5 Tasks 5.5, 5.7, 5.9 if forced — they can move to v4.7) before slipping it.

---

## What changes vs. v4.5

- v4.5's `CloudSelfConsistency` docstring → v4.6 P1 fixed text.
- v4.5's three-layer-immutability claim → v4.6 P2 honest Layer-1 caveat.
- v4.5's tool list line 796 → v4.6 P3 includes `psscan` and 6 other plugins.
- v4.5's `Finding` schema (line 233) → v4.6 Phase 1 patches add `min_length=2`, `artifact_classes`, `caveats_acknowledged`, two validators.
- v4.5's `verdict/playbooks/` → v4.6 creates `memory.yml`, `disk.yml`, `triage.yml`.
- v4.5's `verdict/prompts/` → v4.6 creates `examiner_caveats.md` + executor system-prompt loader.
- v4.5's `verdict/knowledge/` → v4.6 creates `hunt_evil.yml` + `ProcessBaselineAnomaly` schema.
- v4.5's caveats section → v4.6 appends P4, P5, P6.

Everything else in v4.5 stands. Lock-in decisions, mode topology, Plan-then-Execute graph, Langfuse + SqliteSaver + Plan-then-Execute production-maturity additions, the threat model doc, the Planner protocol, the executor_work split, the ToolOutput base, the planner CoT capture, the schema versioning discipline, the evidence manifest, the sanitization pass — all retained.

---

## Bottom line

v4.6 is two days of work that closes the five v4.4 BLOCKERS v4.5 left on the floor. After v4.6, the schemas are locked, the planner has a real DFIR methodology to follow, every executor carries Tier-1 caveats, the Hunt Evil baseline catches process masquerading, and DKOM/T1014 detection is wired explicitly. The remaining v4.4 SHOULD-FIX items defer to v4.7 (week 2-3) without blocking week 1.
