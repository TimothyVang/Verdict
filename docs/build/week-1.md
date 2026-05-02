# WEEK 1 (May 2 – May 8): Foundations + Schemas

**Theme:** Lock the contracts. Stand up infrastructure. Hardware-validate inference. Author all DFIR content.
**Critical-path output:** Schemas frozen; SGLang + Microsandbox + Langfuse all responding to a smoke test by Thursday May 8.
**If this week slips:** Week 2 cannot begin. Drop Phase G (architecture-review docs) before slipping the schema deadline.
**Cumulative team-days:** Tim ~5, Beaver ~1.5, Haley ~2, KP ~5.

## Phase W1.A — Infrastructure stand-up (Tim, ~2 days)

### W1.A.1 — `scripts/install.sh` with three credential paths
- [ ] **W1.A.1.a** — Write failing test `tests/cli/test_install_credentials.py::test_detects_oauth_token_first`. Mock env with `CLAUDE_CODE_OAUTH_TOKEN`; assert install reports `mode=oauth`. Run → RED.
- [ ] **W1.A.1.b** — Write the three-path detection logic (oauth env → interactive `~/.claude/` → `ANTHROPIC_API_KEY`) in `scripts/install.sh` + Python helper `verdict/cli/credentials.py`. Run → GREEN.
- [ ] **W1.A.1.c** — Commit: `feat(cli): three-credential-path install per A1 [W1.A.1]`

### W1.A.2 — SIFT VM provisioning (manual + scripted)
- [ ] **W1.A.2.a** — Document VM specs in `docs/BUILD.md`: 32GB RAM, 8 vCPU, 200GB disk, KVM enabled. Convert `sift-2026.03.24.ova` to VMware Workstation per project's existing `scripts/sift-vm-bootstrap.sh`.
- [ ] **W1.A.2.b** — Smoke test: `vol3 -h` runs inside VM. Verify Python 3.11 present.
- [ ] **W1.A.2.c** — Commit: `docs(build): SIFT VM provisioning checklist [W1.A.2]`

### W1.A.3 — Microsandbox install
- [ ] **W1.A.3.a** — Run `curl -sSL https://get.microsandbox.dev | sh` inside SIFT VM. Verify `microsandbox --version` returns. Verify `microsandbox-mcp` binary present.
- [ ] **W1.A.3.b** — Smoke test: spawn an Ubuntu 22.04 microVM, run `vol3 -h`, destroy. Document spawn time in `docs/BUILD.md` (target <500ms).
- [ ] **W1.A.3.c** — Build `verdict-sift-tools` rootfs Docker image with the 12 forensic tools pinned to versions: `vol3==2.10.0`, `hayabusa==2.18.0`, `plaso==20260427`, `MFTECmd==1.2.x`, etc. Push as `verdict-sift-tools:v0.1` and capture SHA-256.
- [ ] **W1.A.3.d** — Commit: `feat(sandbox): microsandbox install + verdict-sift-tools rootfs pinned [W1.A.3]`

### W1.A.4 — SGLang + Qwen3 + GLM-4.5-Air on dev rig (Haley, ~1 day)
- [ ] **W1.A.4.a** — Install SGLang per upstream docs. Verify GPU detected (target: 80GB H100 or 2× A100).
- [ ] **W1.A.4.b** — Serve Qwen3-30B-A3B-Thinking-2507 with `--tool-call-parser qwen3_xml` at port 30000. Verify `/v1/models` lists the model.
- [ ] **W1.A.4.c** — Serve GLM-4.5-Air with `--tool-call-parser glm45` at port 30001 (or colocate behind the same SGLang server with model_name routing).
- [ ] **W1.A.4.d** — Run synthetic 100-call tool-parse harness against each model. **Gate:** ≥98% non-empty `tool_calls` on both. If <98% → escalate; consider switching primary to GLM, or defer air-gap mode to v2.
- [ ] **W1.A.4.e** — Commit: `feat(inference): SGLang + Qwen3 + GLM-4.5-Air serving with tool-call parsers [W1.A.4]`

### W1.A.5 — FastMCP gateway skeleton (Tim)
- [ ] **W1.A.5.a** — Write failing test `tests/runtime/test_gateway_skeleton.py::test_case_init_returns_handle`. Stub gateway with single tool `case_init`; assert it returns `{case_id, mode}`. Run → RED.
- [ ] **W1.A.5.b** — Implement `verdict/runtime/gateway.py` with FastMCP, single tool `case_init`. Wire mode autodetect stub (returns hardcoded `Mode.CLOUD` for now; full impl in W5.A.1).
- [ ] **W1.A.5.c** — Commit: `feat(runtime): FastMCP gateway skeleton with case_init [W1.A.5]`

### W1.A.6 — Microsandbox provider Pattern 1 (per-tool ephemeral microVM)
- [ ] **W1.A.6.a** — Write failing test `tests/sandboxes/test_microsandbox_provider.py::test_per_call_ephemeral_microvm`. Spawn sandbox with read-only `/evidence` mount, run `cat /etc/os-release`, destroy. Assert `network=False` enforced. Run → RED.
- [ ] **W1.A.6.b** — Implement `verdict/sandboxes/microsandbox_provider.py` per v4.5 line 461 sketch. Network=False default; `mounts=[ReadOnly(...)]`; SHA-256 stdout.
- [ ] **W1.A.6.c** — Commit: `feat(sandbox): per-tool ephemeral microsandbox provider Pattern 1 [W1.A.6]`

### W1.A.7 — Langfuse self-host (Tim)
- [ ] **W1.A.7.a** — Stand up `docker-compose.yml` with Langfuse v2 (Postgres-only, ~1.5GB RAM). Verify UI loads on `http://localhost:3000`. **Threshold:** if v2 deployment hits 4-hour blocker, fall back to OpenLLMetry → local Tempo viewer; document why in `docs/BUILD.md`.
- [ ] **W1.A.7.b** — Write smoke test `tests/observability/test_langfuse_smoke.py::test_one_trace_renders`. Send one synthetic trace via SDK; assert `/api/public/traces/{id}` returns 200.
- [ ] **W1.A.7.c** — Commit: `feat(observability): Langfuse v2 self-host + smoke trace [W1.A.7]`

### W1.A.8 — Inspect AI hello-world
- [ ] **W1.A.8.a** — `pip install inspect-ai` per CLAUDE.md. Author `inspect_ai/tasks/hello_world.py` minimal task. Run `inspect eval inspect_ai/tasks/hello_world.py`. Assert pass.
- [ ] **W1.A.8.b** — Commit: `feat(eval): Inspect AI hello-world task [W1.A.8]`

### W1.A.9 — Mechanical hard-rule enforcement (Tim, ~3 hours)
Pulls forward what `CONTRIBUTING.md` line 220 already promises and what `CLAUDE.md` §3.7 + §3.10 require. Without this task, the hard rules are rules of prose only — see `docs/AGENTIC_WORKFLOW_REVIEW.md` D1 + D3 + D4.

- [ ] **W1.A.9.a** — Failing test `tests/policy/test_no_mocks_hook.py::test_rejects_unittest_mock_import`. Assertion: `check_no_mocks.scan(["tests/policy/fixtures/has_mock_import.py"]).violations` is non-empty AND the offending line is reported. Plus `test_allows_third_party_boundary_patch` — patching `httpx` in a single targeted test passes.
- [ ] **W1.A.9.b** — Implement `scripts/check_no_mocks.py` (~40 LOC AST walker). Rejects: `import unittest.mock`, `from unittest import mock`, `import responses`, `import vcr`, `import betamax`, `import httpx_mock`, regex `^\s*if .*(MOCK|TEST_MODE).*:\s*$`, regex `os\.environ\.get\(['"]VERDICT_TEST`. Walks all `.py` under `verdict/` and `tests/`.
- [ ] **W1.A.9.c** — Author `.pre-commit-config.yaml` at repo root with hooks: (1) `commitizen check` enforcing `^(feat|fix|test|chore|docs|refactor)\(\w+\): .* \[W\d+\.[A-Z]\.\d+(\.[a-z])?\]$` on commit message; (2) `ruff check --select ALL`; (3) the local `check-no-mocks` hook from W1.A.9.b. Run `pre-commit install --install-hooks` in `scripts/install.sh`.
- [ ] **W1.A.9.d** — Stub `.github/workflows/eval-hallucination-gate.yml`: on PR, runs `inspect eval inspect_ai/tasks/verdict_eval_cloud.py --score hallucination_rate`, fails on >10%. Scorer stub returns 0.0 (always pass) until W4.D.1 implements the real scorer. Wires the gate into CI so the metric is measured before any hallucination-producing code lands.
- [ ] **W1.A.9.e** — Drop the `test -f .pre-commit-config.yaml &&` short-circuit at `CONTRIBUTING.md` line 140 (file exists now; the guard is no longer needed and silently masks a missing config).
- [ ] **W1.A.9.f** — Commit: `feat(policy): mechanical enforcement of §3.7 + §3.10 (no-mocks AST hook + commit-msg regex + hallucination CI stub) [W1.A.9]`

## Phase W1.B — Schema bundle (Tim, ~2 hours)

This is the contract every teammate will code against. **Lock by Sunday May 4.** All tasks from `archive/04-spec-plan-v4.6.md` Phase 1 plus the v4.5-architecture-review schemas.

### W1.B.1 — `ArtifactClass` enum
- [ ] **W1.B.1.a** — Write failing test `tests/schemas/test_artifact_class.py::test_enum_has_13_required_members`. Run → RED.
- [ ] **W1.B.1.b** — Implement `verdict/schemas/artifact_class.py` per Appendix A.1.
- [ ] **W1.B.1.c** — Commit: `feat(schema): ArtifactClass enum (FOR500 corroboration) [W1.B.1]`

### W1.B.2 — `CaveatID` enum
- [ ] **W1.B.2.a** — Write failing test `tests/schemas/test_caveat_id.py::test_enum_covers_tier1_memory_md`. Assert all 7 from `agent-config/MEMORY.md`. Run → RED.
- [ ] **W1.B.2.b** — Implement `verdict/schemas/caveat_id.py` per Appendix A.2.
- [ ] **W1.B.2.c** — Commit: `feat(schema): CaveatID enum from project MEMORY.md Tier-1 [W1.B.2]`

### W1.B.3 — `EvidenceItem` + `EvidenceManifest`
- [ ] **W1.B.3.a** — Write failing test `tests/schemas/test_evidence.py::test_manifest_hash_is_blake3_of_sorted_pairs`. Run → RED.
- [ ] **W1.B.3.b** — Implement `verdict/schemas/evidence.py` per v4.5 lines 153–168 + Appendix A.3.
- [ ] **W1.B.3.c** — Commit: `feat(schema): EvidenceItem + EvidenceManifest schemas [W1.B.3]`

### W1.B.4 — `Artifact` + `ToolOutput` base
- [ ] **W1.B.4.a** — Write failing test `tests/schemas/test_tool_output.py::test_invocation_hash_combines_name_version_args_evidence`. Run → RED.
- [ ] **W1.B.4.b** — Implement `verdict/schemas/tool_output.py` per v4.5 lines 170–193 + Appendix A.4.
- [ ] **W1.B.4.c** — Commit: `feat(schema): Artifact + ToolOutput base for tool wrapper contract [W1.B.4]`

### W1.B.5 — `Hypothesis` + `InvestigationPlan` + `PlanComprehensionEcho` + `PlannerCritiqueVerdict`
- [ ] **W1.B.5.a** — Write failing tests in `tests/schemas/test_plan.py`: `test_mitre_subtechnique_regex_validates_T1055_012` (passes) and `test_mitre_invalid_format_rejected` (raises). Plus `test_negative_hypothesis_quality_rejects_degenerate`. Run → RED.
- [ ] **W1.B.5.b** — Implement `verdict/schemas/plan.py` with all four classes + the `mitre_technique` regex validator (`^T\d{4}(\.\d{3})?$`) + `_negative_hypothesis_quality` validator (deny-list: cosmic/alien/nothing/not-relevant/n-a; require non-None mitre_technique; require non-empty artifact_families).
- [ ] **W1.B.5.c** — Commit: `feat(schema): Hypothesis + InvestigationPlan + comprehension/critique schemas [W1.B.5]`

### W1.B.6 — `Finding` skeleton
- [ ] **W1.B.6.a** — Write failing test `tests/schemas/test_finding.py::test_finding_round_trips_through_json`. Run → RED.
- [ ] **W1.B.6.b** — Implement `verdict/schemas/finding.py` skeleton: all v4.5 fields plus the new ones (`artifact_classes`, `caveats_acknowledged`).
- [ ] **W1.B.6.c** — Commit: `feat(schema): Finding skeleton [W1.B.6]`

### W1.B.7 — Patch `Finding.artifact_paths` to `Field(min_length=2)`
- [ ] **W1.B.7.a** — Failing test: `test_artifact_paths_min_length_2`. Run → RED.
- [ ] **W1.B.7.b** — Implement.
- [ ] **W1.B.7.c** — Commit: `feat(schema): require ≥2 artifact paths per Finding (FOR500) [W1.B.7]`

### W1.B.8 — `Finding.artifact_classes` field
- [ ] **W1.B.8.a** — Failing test: `test_artifact_classes_min_length_2`. Run → RED.
- [ ] **W1.B.8.b** — Implement.
- [ ] **W1.B.8.c** — Commit: `feat(schema): Finding.artifact_classes min_length=2 [W1.B.8]`

### W1.B.9 — `Finding.caveats_acknowledged` field
- [ ] **W1.B.9.a** — Failing test: `test_caveats_acknowledged_default_empty`. Run → RED.
- [ ] **W1.B.9.b** — Implement.
- [ ] **W1.B.9.c** — Commit: `feat(schema): Finding.caveats_acknowledged field [W1.B.9]`

### W1.B.10 — Execution-claim validator + Amcache-caveat validator + 6 other caveat validators
- [ ] **W1.B.10.a** — Failing tests: `test_execution_claim_requires_two_classes` (T1059, T1106, T1204, T1218, T1543, T1547 prefixes), `test_amcache_requires_caveat`, plus one test per remaining CaveatID (`test_shimcache_caveat_required_when_shimcache_cited`, etc.). Run → RED.
- [ ] **W1.B.10.b** — Implement `_execution_claims_need_two_classes` + `_amcache_caveat_required` + 6 sibling validators (one per CaveatID where the artifact_class triggers the caveat).
- [ ] **W1.B.10.c** — Commit: `feat(schema): Finding validators enforce caveat acknowledgment [W1.B.10]`

### W1.B.11 — `LedgerEntry` schema
- [ ] **W1.B.11.a** — Failing test: `test_ledger_entry_three_id_hierarchy`. Assert `case_id`, `langfuse_trace_id`, `langgraph_checkpoint_id` are distinct fields. Plus `test_ledger_entry_records_examination_environment` for `microsandbox_version`/`rootfs_sha256`/`tool_version`/`kernel_version`.
- [ ] **W1.B.11.b** — Implement `verdict/schemas/ledger.py` per v4.5 lines 245–278 plus the v4.4 environment-metadata fields. Add `output_files_sha256: dict[str, str] = {}` field.
- [ ] **W1.B.11.c** — Commit: `feat(schema): LedgerEntry with three-ID hierarchy + exam-env metadata [W1.B.11]`

### W1.B.12 — `schema_version` discipline + `verdict/schemas/version.py`
- [ ] **W1.B.12.a** — Failing test: `test_schema_version_is_1_on_all_top_level_models`. Loop through `[InvestigationPlan, Finding, LedgerEntry, EvidenceManifest, ToolOutput]`; assert `.schema_version == 1`.
- [ ] **W1.B.12.b** — Implement: add `schema_version: int = 1` to all five top-level schemas; centralize in `verdict/schemas/version.py`.
- [ ] **W1.B.12.c** — Commit: `feat(schema): schema_version discipline across top-level models [W1.B.12]`

### W1.B.13 — `VerdictStatus` enum
- [ ] **W1.B.13.a** — Failing test: `test_verdict_status_has_all_v45_states`. Assert all 9 states from v4.5 line 295.
- [ ] **W1.B.13.b** — Implement.
- [ ] **W1.B.13.c** — Commit: `feat(schema): VerdictStatus enum [W1.B.13]`

## Phase W1.C — Verifier strategy seed-derivation fix (Beaver, ~1 hour)

### W1.C.1 — `derive_seeds(case_id)` helper
- [ ] **W1.C.1.a** — Failing test `tests/verification/test_derive_seeds.py::test_three_distinct_deterministic_per_case`. Run → RED.
- [ ] **W1.C.1.b** — Implement `verdict/verification/derive_seeds.py` using blake3 keyed-hash pattern.
- [ ] **W1.C.1.c** — Commit: `feat(verification): derive_seeds(case_id) for n=3 self-consistency [W1.C.1]`

### W1.C.2 — `CloudSelfConsistency` impl
- [ ] **W1.C.2.a** — Failing test `tests/verification/test_cloud_self_consistency.py::test_three_distinct_seeds_in_api_calls`. Mock Claude client; assert 3 calls, 3 distinct seeds, `temperature=0.7`. Run → RED.
- [ ] **W1.C.2.b** — Implement `verdict/verification/cloud_self_consistency.py` per Appendix A.5.
- [ ] **W1.C.2.c** — Commit: `fix(verification): CloudSelfConsistency samples 3 diverse paths (Wang 2022) [W1.C.2]`

### W1.C.3 — `VerifierStrategy` Protocol + Universal Self-Consistency stub
- [ ] **W1.C.3.a** — Failing test `tests/verification/test_strategy_protocol.py::test_strategy_returns_verdict_result`. Stub returns hardcoded VETTED_CLOUD. Run → RED.
- [ ] **W1.C.3.b** — Implement `verdict/verification/strategy.py` (Protocol) + `universal_self_consistency.py` (Chen et al. 2023 — stub for now, full impl in W3.A.3).
- [ ] **W1.C.3.c** — Commit: `feat(verification): VerifierStrategy Protocol + USC stub [W1.C.3]`

## Phase W1.D — PreToolUse caveat + smoke scaffold (Tim, ~30 min)

### W1.D.1 — CI smoke-test scaffold (xfail-marked)
- [ ] **W1.D.1.a** — Author `tests/smoke/test_pretooluse_deny.py` marked `pytest.mark.xfail(reason="anthropics/claude-code#33106 + #37210")`. Test invokes `claude` subprocess with a PreToolUse hook returning `permissionDecision: "deny"` for an MCP write; asserts the call is blocked.
- [ ] **W1.D.1.b** — Add `[smoke]` marker to `pyproject.toml` so `pytest -m smoke` finds it.
- [ ] **W1.D.1.c** — Commit: `test(smoke): PreToolUse deny scaffold (xfail per #33106 #37210) [W1.D.1]`

### W1.D.2 — Apply v4.6 P2 to v4.5 audit doc
- [ ] **W1.D.2.a** — Append the Layer-1 caveat paragraph to v4.5 architecture caption (line 144).
- [ ] **W1.D.2.b** — Commit: `docs(audit): v4.6 P2 — Layer-1 PreToolUse version-dependence caveat [W1.D.2]`

## Phase W1.E — Tool surface stubs (Tim, ~2 hours)

The 12 tool wrappers ship in W2.E. This phase ships the schema scaffolding + `psscan` per v4.6 P3.

### W1.E.1 — `vol_psscan` MCP tool wrapper
- [ ] **W1.E.1.a** — Failing test `tests/tools/test_vol_psscan.py::test_psscan_returns_pids`. Mock microsandbox; assert wrapper invokes `vol3 windows.psscan` with correct args; assert returns `ToolOutput` with `parsed_artifacts: list[Artifact]` of type `process`. Run → RED.
- [ ] **W1.E.1.b** — Implement `verdict/tools/vol3/psscan.py` mirroring `vol_pslist` shape.
- [ ] **W1.E.1.c** — Commit: `feat(tools): vol_psscan wrapper for DKOM/T1014 cross-validation [W1.E.1]`

### W1.E.2 — Tool wrapper base class
- [ ] **W1.E.2.a** — Failing test `tests/tools/test_tool_base.py::test_base_records_invocation_hash`. Assert any wrapper extending `ToolWrapper` records `invocation_hash = blake3(tool_name + tool_version + args + evidence_hash)`.
- [ ] **W1.E.2.b** — Implement `verdict/tools/base.py` abstract `ToolWrapper` with `pre_run` (compute invocation hash) + `run` (subclass impl) + `post_run` (sandbox destroy + ledger write hooks).
- [ ] **W1.E.2.c** — Commit: `feat(tools): ToolWrapper abstract base with invocation hashing [W1.E.2]`

### W1.E.3 — Apply v4.6 P3 + P4 to v4.5 audit doc
- [ ] **W1.E.3.a** — Update v4.5 line 796 tool list to include 10 vol3 plugins.
- [ ] **W1.E.3.b** — Append DKOM caveat per P4.
- [ ] **W1.E.3.c** — Commit: `docs(audit): v4.6 P3 + P4 — psscan in tool list, DKOM rationale [W1.E.3]`

## Phase W1.F — KP content authoring (KP, ~1.5 days)

### W1.F.1 — `Playbook` Pydantic schema
- [ ] **W1.F.1.a** — Failing test `tests/schemas/test_playbook.py::test_playbook_loads_yaml`. Run → RED.
- [ ] **W1.F.1.b** — Implement `verdict/schemas/playbook.py` with `Step` + `Playbook` classes per v4.6.
- [ ] **W1.F.1.c** — Commit: `feat(schema): Playbook + Step for planner methodology injection [W1.F.1]`

### W1.F.2 — Author `verdict/playbooks/memory.yml`
- [ ] **W1.F.2.a** — Failing test `tests/playbooks/test_memory_yml.py::test_memory_playbook_has_dkom_rule`. Run → RED.
- [ ] **W1.F.2.b** — Author per Appendix C.1.
- [ ] **W1.F.2.c** — Commit: `feat(playbooks): memory.yml — Volatility 3 sequence + DKOM rule [W1.F.2]`

### W1.F.3 — Author `verdict/playbooks/disk.yml`
- [ ] **W1.F.3.a** — Failing test `tests/playbooks/test_disk_yml.py::test_plaso_after_lighter_tools`. Run → RED.
- [ ] **W1.F.3.b** — Author per Appendix C.2.
- [ ] **W1.F.3.c** — Commit: `feat(playbooks): disk.yml [W1.F.3]`

### W1.F.4 — Author `verdict/playbooks/triage.yml`
- [ ] **W1.F.4.a** — Failing test `tests/playbooks/test_triage_yml.py::test_registry_first`. Run → RED.
- [ ] **W1.F.4.b** — Author per Appendix C.3.
- [ ] **W1.F.4.c** — Commit: `feat(playbooks): triage.yml [W1.F.4]`

### W1.F.5 — Apply v4.6 P5 to v4.5 audit doc
- [ ] **W1.F.5** — Append multi-artifact corroboration caveat. Commit: `docs(audit): v4.6 P5 — multi-artifact corroboration [W1.F.5]`

### W1.F.6 — `playbook_loader` injects into planner prompt
- [ ] **W1.F.6.a** — Failing test `tests/planning/test_playbook_loader.py::test_loader_picks_by_evidence_type`. Run → RED.
- [ ] **W1.F.6.b** — Implement `verdict/planning/playbook_loader.py::load_playbook_prompt(manifest: EvidenceManifest) -> str`.
- [ ] **W1.F.6.c** — Commit: `feat(planning): playbook_loader injects methodology by evidence type [W1.F.6]`

### W1.F.7 — Author `verdict/planning/prompts/examiner_caveats.md`
- [ ] **W1.F.7.a** — Failing test `tests/prompts/test_examiner_caveats.py::test_all_seven_caveats_present`. Run → RED.
- [ ] **W1.F.7.b** — Author per Appendix B.1.
- [ ] **W1.F.7.c** — Commit: `feat(prompts): examiner_caveats.md — Tier-1 caveats include [W1.F.7]`

### W1.F.8 — `HuntEvilBaseline` schema + `ProcessBaselineAnomaly` Hypothesis subtype
- [ ] **W1.F.8.a** — Failing test `tests/schemas/test_hunt_evil.py::test_baseline_loads`. Plus `test_anomaly_maps_to_T1036_005`.
- [ ] **W1.F.8.b** — Implement `verdict/schemas/hunt_evil.py` with both classes.
- [ ] **W1.F.8.c** — Commit: `feat(schema): HuntEvilBaseline + ProcessBaselineAnomaly (T1036.005) [W1.F.8]`

### W1.F.9 — Author `verdict/knowledge/hunt_evil.yml`
- [ ] **W1.F.9.a** — Failing test `tests/knowledge/test_hunt_evil_yml.py::test_eight_canonical_processes`. Run → RED.
- [ ] **W1.F.9.b** — Author per Appendix C.4 — 8 processes (svchost, lsass, csrss, winlogon, services, wininit, explorer, smss).
- [ ] **W1.F.9.c** — Commit: `feat(knowledge): hunt_evil.yml — 8 canonical Windows process baselines [W1.F.9]`

### W1.F.10 — Executor system-prompt include
- [ ] **W1.F.10.a** — Failing test `tests/planning/test_executor_prompt.py::test_includes_caveats_and_hunt_evil`. Assert prompt contains `AMCACHE_LASTMODIFIED_NOT_EXEC` and `svchost.exe`.
- [ ] **W1.F.10.b** — Implement `verdict/planning/executor_prompt.py::render_executor_prompt(role: str) -> str` that composes examiner_caveats.md + relevant hunt_evil entries.
- [ ] **W1.F.10.c** — Commit: `feat(planning): executor system prompt with caveats + hunt evil [W1.F.10]`

### W1.F.11 — Apply v4.6 P6 to v4.5 audit doc
- [ ] **W1.F.11** — Append Tier-1 caveat caveat. Commit: `docs(audit): v4.6 P6 — Tier-1 caveats encoded [W1.F.11]`

## Phase W1.G — Architecture-review docs + ops surface (Tim, ~1 day)

### W1.G.1 — `docs/THREAT_MODEL.md`
- [ ] **W1.G.1.a** — Author per v4.5 line 369 (4 surfaces: insider, prompt-injection-from-evidence, malicious-tool-output, external-attacker). Mitigations + residual risks per surface. Microsandbox escape documented as accepted v1 risk.
- [ ] **W1.G.1.b** — Commit: `docs: THREAT_MODEL.md with 4 adversary surfaces [W1.G.1]`

### W1.G.2 — `docs/FAILURE_MODES.md`
- [ ] **W1.G.2.a** — Author component × failure × detection × recovery × escalation table. Cover: microsandbox spawn timeout (30s + 1 retry), SGLang server crash, Langfuse fail-open, partial ledger write recovery, Claude API rate-limit, OpenCTI unreachable.
- [ ] **W1.G.2.b** — Commit: `docs: FAILURE_MODES.md [W1.G.2]`

### W1.G.3 — `docs/CLI.md`
- [ ] **W1.G.3.a** — Author full CLI surface: `verdict {init, resume, reverify, status, ls, show <id>, export <id>, validate <id>, mode, gc, health, doctor}`. Stub commands marked `(v2 roadmap)` allowed but the surface contracts in v1.
- [ ] **W1.G.3.b** — Commit: `docs: CLI.md enumerating verdict commands [W1.G.3]`

### W1.G.4 — `docs/SCHEMA_MIGRATION.md`
- [ ] **W1.G.4** — Author migration policy: `schema_version` field on all top-level schemas; breaking changes ship a `migrations/v{N}_to_v{N+1}.py` script. Commit: `docs: SCHEMA_MIGRATION.md [W1.G.4]`

### W1.G.5 — `Planner` Protocol + `CloudPlanner` + `LocalPlanner` (Beaver collaborates)
- [ ] **W1.G.5.a** — Failing test `tests/planning/test_planner_protocol.py::test_protocol_returns_investigation_plan`. Plus `test_planner_bound_at_gateway_init` — assert mode-switching code lives in `runtime/mode_detect.py`, not in `planner_node`.
- [ ] **W1.G.5.b** — Implement `verdict/planning/planner.py` with the Protocol + two impls.
- [ ] **W1.G.5.c** — Commit: `feat(planning): Planner Protocol + CloudPlanner + LocalPlanner [W1.G.5]`

### W1.G.6 — HMAC key handling (TPM-backed if present, else gpg-encrypted)
- [ ] **W1.G.6.a** — Failing test `tests/ledger/test_hmac_key.py::test_tpm_path_when_dev_tpmrm0_present`. Mock `/dev/tpmrm0` → use TPM. Mock absence → fall back to gpg-encrypted at `~/.verdict/key.gpg`. Run → RED.
- [ ] **W1.G.6.b** — Implement `verdict/ledger/hmac_key.py` with both paths. Passphrase prompt at gateway init for the gpg path.
- [ ] **W1.G.6.c** — Commit: `feat(ledger): HMAC key TPM-backed or gpg-encrypted [W1.G.6]`

### W1.G.7 — Evidence manifest with periodic re-hash check
- [ ] **W1.G.7.a** — Failing test `tests/runtime/test_evidence_recheck.py::test_recheck_every_10_super_steps`. Plus `test_mismatch_writes_ledger_entry_and_halts`.
- [ ] **W1.G.7.b** — Implement re-hash loop in `verdict/runtime/evidence_recheck.py`. Mismatch → `LedgerEntry(event_type="evidence_hash_recheck")` with both hashes + halt with `HashMismatchError`.
- [ ] **W1.G.7.c** — Commit: `feat(runtime): periodic evidence re-hash check (10 super-steps) [W1.G.7]`

## Week 1 — acceptance gates

By end of day Thursday May 8 ALL the following must be true. If any is FALSE on Friday morning, week 2 doesn't start.

| Gate | Verification command |
|---|---|
| All schema tests pass | `uv run pytest tests/schemas/ -v` |
| All playbook tests pass | `uv run pytest tests/playbooks/ -v` |
| All knowledge tests pass | `uv run pytest tests/knowledge/ -v` |
| Microsandbox spawns + runs vol3 -h on a sample image | `bash scripts/healthcheck.sh microsandbox` |
| SGLang serves both Qwen3 + GLM with ≥98% tool-call parse rate | Output of `python scripts/inference-smoke.py` |
| Langfuse UI loads + smoke trace renders | `curl http://localhost:3000/api/public/health` returns 200 |
| Inspect AI hello-world passes | `inspect eval inspect_ai/tasks/hello_world.py` |
| `vol_psscan` wrapper integration test passes | `uv run pytest tests/tools/test_vol_psscan.py -v` |
| Three architecture-review docs present | `ls docs/{THREAT_MODEL,FAILURE_MODES,CLI,SCHEMA_MIGRATION}.md` |
| `examiner_caveats.md` includes all 7 CaveatID values | `grep -c "## " verdict/planning/prompts/examiner_caveats.md` returns 7 |
| `hunt_evil.yml` has 8 canonical processes | `python -c "import yaml; print(len(yaml.safe_load(open('verdict/knowledge/hunt_evil.yml'))))"` returns 8 |
| All 6 v4.6 patches applied to v4.5 audit doc | `grep -c "v4.6 P[1-6]" archive/03-audit-v4.5.md` returns ≥6 |
| Conventional Commits enforced (no `--no-verify`) | `git log --oneline -50 | grep -c '^[a-f0-9]\+ \(feat\|test\|fix\|docs\|chore\)' = 50` |

If any gate is RED on May 8: **descope before slipping**. Drop in this priority order: W1.G.7 → W1.G.6 → W1.A.7 (Langfuse v2; ship without it, fall back to OTel-only) → W1.G.1-3 (push docs to W6).

---

