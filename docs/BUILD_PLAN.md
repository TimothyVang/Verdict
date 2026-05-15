# VERDICT — Master Build Plan (v1)

> **Wiki:** [Index](README.md) · [Architecture](ARCHITECTURE.md) · [Build Plan](BUILD_PLAN.md) · [Devpost](DEVPOST_COMPLIANCE.md) · root [CLAUDE.md](../CLAUDE.md)

**Document type:** Comprehensive 6-week TDD execution plan. Covers every task from v4.5 architecture + v4.6 schema patches + v4.4 deferred items + foundational infrastructure. This document is the single source of truth from May 2 through June 14, 2026.
**Authority chain:** Devpost rules (always win) + `DEVPOST_COMPLIANCE.md` (rule-to-artifact mapping) + v4.5 (architecture) + v4.6 (schema amendments) + this document (execution). Where execution details disagree with v4.5, this plan wins for execution; v4.5 wins for architecture rationale.
**Owner:** Tim (lead) + Beaver (LangGraph) + Haley (inference) + KP (forensics).
**Deadline:** End of day June 14, 2026 (Devpost official deadline is **Jun 15, 2026 11:45 PM EDT** = ~28h buffer). Judging period Jun 19 – Jul 3; winners announced ~Jul 8.
**Status:** Ready to execute. Schemas freeze May 8; tool surface freezes May 15; verifier loop freezes May 22; evals freeze May 29; demo footage shoot begins May 30; final cut June 14.

---

## Document metadata

- **Today:** Saturday May 2, 2026.
- **Total team-days available:** ~6 weeks × 4 teammates × 5 working-days/week ≈ 120 teammate-days. Realistic budget after slack/sleep/CI-pain: ~80 productive teammate-days.
- **Total team-days planned in this document:** ~76 (Tim ~23, Beaver ~22, Haley ~10, KP ~21) — Tim +1 day for the Devpost-required W6.C.7-C.10 + W6.D.0 deliverables. Leaves ~4 days of slack distributed across teammates for unplanned blockers. Slack budget is per-week, not cumulative — week 6 budget cannot rescue week 2 slip.
- **Hard rule on conventions** (per project `CLAUDE.md`): TDD failing test → RED → implement → GREEN → commit. One commit per task. Conventional Commits format. Never `--no-verify`, `--no-gpg-sign`, or `git commit --amend`. Pinned versions in lockfiles. Python 3.11 + uv + pytest + ruff. Rust 1.88 (project ships 1.88, Spec #2's 1.83 pin superseded). Node 20 + pnpm.

## Task ID convention

Every task in this document has a unique grep-able ID of the form `Wk.Phase.Task[.subtask]`:

- `W1.B.3` — Week 1, Phase B (Schema bundle), Task 3
- `W1.B.3.a` — same task, subtask a (typically the failing-test step)

Use the ID in commit messages: `feat(schema): add ArtifactClass enum [W1.B.1]`. This makes git log archeology trivial. CI gates reference task IDs in PR templates.

**RED-line policy:** every `*.a` "Failing test" sub-task names a test path AND the literal failing assertion (e.g., `assert result.status == VerdictStatus.VETTED_DUAL`, `assert ledger_writer.write(...) raises HashMismatchError`). A test name like `test_does_X` is descriptive but ambiguous; the RED assertion is contractual. New `*.a` lines added to this plan must follow this format.

---

## TL;DR — what gets built

VERDICT is a mode-aware verifier-gateway for forensic LLM agents. By June 14:

1. **Three operational modes** (cloud-only / air-gap-only / dual) auto-selected by infrastructure detection; operator overrides via `--mode={cloud,airgap,dual}`. Mode locked at `case_init`.
2. **Plan-then-Execute LangGraph topology** (8 nodes) with named nodes: `planner` → `planner_critique` (CoVe) → `comprehension_gate` → `executor_fanout` (per-branch composition: `DenyRuleWrapper → ToolExecutor → LedgerEmitter`; the composition is referred to internally as `executor_work` and is a sub-state of fanout, not a separate top-level node) → `pivot_node` → `quorum` → `replan` → `finalize`. (`unverifiable_finalize_node` is a helper called from `replan_node`, not a registered graph node.)
3. **12 SIFT tool wrappers** as MCP tools running in per-call ephemeral microsandbox VMs: `mmls`, `fls`, `fsstat`, `vol3` (10 plugins), `hayabusa` (split: csv-timeline + filter), `plaso` (split: extract + filter), `MFTECmd`, `RECmd`, `PECmd`, `bulk_extractor`, `exiftool`, `capa`.
4. **Three-layer immutability defense**: Layer 1 = Claude PreToolUse hook (best-effort, version-dependent caveat per #33106/#37210); Layer 2 = LangGraph `DenyRuleWrapper` (architectural guarantee, all modes); Layer 3 = Microsandbox read-only mount (kernel-enforced).
5. **Cryptographic chain-of-custody**: HMAC-signed append-only JSONL ledger with `prev_entry_hash`, three-tier ID hierarchy (`case_id` / `langfuse_trace_id` / `langgraph_checkpoint_id`), per-output-file SHA-256, examination-environment metadata (`microsandbox_version`, `rootfs_sha256`, `tool_version`, `kernel_version`).
6. **Forensic discipline encoded in code**: `Finding.artifact_paths min_length=2`, `Finding.artifact_classes min_length=2`, `Finding.caveats_acknowledged` field with model_validators, three playbook YAMLs (memory/disk/triage), `examiner_caveats.md` system-prompt include, `hunt_evil.yml` with 8 process baselines, DKOM/T1014 detection via pslist+psscan divergence, sub-technique-aware MITRE field validation.
7. **Observability**: Langfuse self-hosted (MIT) with OTel via OpenLLMetry; trace tree UI cross-linked to JSONL ledger via `trace_id`; SqliteSaver checkpointer with `PRAGMA journal_mode=WAL; synchronous=FULL` for kill-9 resilience.
8. **Eval harness**: Inspect AI with three per-mode tasks (`verdict_eval_cloud`, `verdict_eval_airgap`, `verdict_eval_dual`); five scorers (`step_efficiency`, `findings_precision`, `findings_recall`, `mitre_subtechnique_precision`, `negative_hypothesis_quality`); 50 ground-truth indicators across 3 engineered cases (lol-bins compromise, credential theft, ransomware).
9. **5-minute demo video** recorded May 30 (rough cut) and June 14 (final), two-pane (terminal + Langfuse trace tree), all three modes against the Honeynet ransomware image, hero beats: pslist/psscan DKOM divergence, Hunt Evil masquerade catch (`scvhost.exe` parent=`cmd.exe`), Amcache-caveat acknowledgment, pivot-vs-replan distinction, TSI tcpdump proof, kill -9 + resume, planner_critique CoVe.
10. **Submission docs**: README, ARCHITECTURE.md, DEVPOST_COMPLIANCE.md, RELEASE.md, FAILURE_MODES.md, LICENSE (MIT), CONTRIBUTING.md, plus final submission-only docs restored in week 6.

---

## Authorities — what to read when stuck

| Need | Read |
|---|---|
| Architecture rationale | `docs/ARCHITECTURE.md` |
| Schema patches + DFIR rule encoding | `docs/ARCHITECTURE.md` §4 |
| Project-level conventions | `CLAUDE.md` (this repo) |
| Tier-1 examiner caveats | `CLAUDE.md` §3.3 and planned `src/verdict/planning/prompts/examiner_caveats.md` |
| Per-evidence-type tool sequencing | `docs/ARCHITECTURE.md` §4 and planned `src/verdict/playbooks/*.yml` |
| Tool surface | `src/verdict/tools/` |
| Decision history | `CHANGELOG.md` + `git log --oneline` |
| Why we picked X over Y | v4.5 §"Lock-In Decisions" + v4.5 §"Per-Tool Deep Dives" |

If two authorities conflict: **code + lockfiles win** over docs (per `CLAUDE.md` §"Spec/code divergences"). Update the doc rather than rolling back the code, unless the code is wrong.

---

## Stack lock-in (one paragraph each — full rationale in v4.5)

- **Cloud agent:** Claude Code + Claude Agent SDK (Python). Used in cloud-only and dual modes. Credential paths: `CLAUDE_CODE_OAUTH_TOKEN` env var, interactive `~/.claude/`, `ANTHROPIC_API_KEY`, or optional host-side `OPENROUTER_API_KEY` fallback for build-side AI agents. OAuth/API tokens are NOT redistributable and never enter microsandboxes.
- **Local inference primary:** SGLang (Apache-2.0). RadixAttention prefix cache; native `--tool-call-parser glm` and `qwen` families per current SGLang docs. Used in air-gap and dual modes.
- **Local inference fallback:** vLLM (Apache-2.0). Pinned to a release containing PR #39055 (Qwen3 reasoning-parser fix).
- **Local Model A:** Qwen3-30B-A3B-Thinking-2507 (Apache-2.0). Air-gap planner/executor; dual-mode local executor/verifier lane. Cloud-only remains Claude Code/Agent SDK only because the mode trigger is GPU absent.
- **Local Model B (verifier):** GLM-4.5-Air (MIT). Verifier only; never planner. Cross-family verification partner for air-gap and dual modes.
- **Orchestration:** LangGraph (MIT) state machine. Five core nodes per Plan-then-Execute, plus comprehension_gate (v4.3), planner_critique (v4.4 SHOULD-FIX), pivot_node (v4.4 SHOULD-FIX), unverifiable_finalize (v4.4 SHOULD-FIX).
- **Schema layer:** Pydantic v2 + Pydantic-AI (MIT) for typed tool args + `ModelRetry` flow.
- **MCP gateway:** FastMCP 3.x (Apache-2.0).
- **Sandbox primary:** Microsandbox (Apache-2.0, beta). libkrun microVM, sub-200ms cold start, built-in MCP server, TSI for credential injection.
- **Sandbox secondary:** bubblewrap (LGPL-2.0, linking-clean) for non-microVM tools.
- **Sandbox tertiary:** nsjail (Apache-2.0).
- **Eval harness:** Inspect AI (MIT) — UKGovernmentBEIS/inspect_ai.
- **Tracing:** Langfuse self-hosted (core MIT) + OpenLLMetry (Apache-2.0). Cross-linked to JSONL ledger.
- **Durable execution:** LangGraph SqliteSaver (MIT). Single-writer; reducer pattern handles fanout.
- **Rails:** NeMo Guardrails (Apache-2.0) for input/output rails.
- **Skills:** agentskills.io standard (open standard) — portable across Claude Code, Hermes, Cursor, Codex.

**Hard nos:** Daytona (AGPL-3.0), REMnux MCP for vendoring (GPL-3.0; network-call only allowed), Llama 4 / Gemma 3 (community licenses, not OSI), Modal (closed), LangSmith / Braintrust (closed), Arize Phoenix (ELv2). AutoGen v0.4 migration (maintenance mode Oct 2025; succeeded by Microsoft Agent Framework which is Azure-coupled and late). Microsoft Agent Framework. AGPL clean-room rewrites.

---

## File / module tree

By June 14 the repo will have this shape:

```
.
├── LICENSE                                 # MIT
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── CLAUDE.md                               # Project conventions
├── pyproject.toml                          # Workspace root (uv)
├── uv.lock
├── package.json                            # Root for pnpm workspaces (mcp-widgets deferred V2)
├── docker-compose.yml                      # Langfuse v2 self-host (default)
├── docker-compose.langfuse-v3.yml          # ClickHouse-backed alt for >=16GB RAM hosts
├── docs/
│   ├── ARCHITECTURE.md
│   ├── RELEASE.md                          # build, scope, CLI, demo, accuracy, dataset, novelty
│   ├── FAILURE_MODES.md                    # Component × failure × recovery (W1.G.2)
├── src/verdict/                           # Python application source package
│   ├── __init__.py
│   ├── runtime/
│   │   ├── mode_detect.py                  # detect_mode() (W5.A.1)
│   │   └── gateway.py                      # FastMCP gateway init
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── mode.py                         # Mode enum
│   │   ├── artifact_class.py               # ArtifactClass enum (W1.B.1)
│   │   ├── caveat_id.py                    # CaveatID enum (W1.B.2)
│   │   ├── evidence.py                     # EvidenceItem + EvidenceManifest (W1.B.3)
│   │   ├── tool_output.py                  # Artifact + ToolOutput base (W1.B.4)
│   │   ├── plan.py                         # Hypothesis + InvestigationPlan + PlanComprehensionEcho + PlannerCritiqueVerdict
│   │   ├── finding.py                      # Finding + validators (W1.B.6 - W1.B.10)
│   │   ├── ledger.py                       # LedgerEntry (W1.B.11)
│   │   ├── playbook.py                     # Playbook + Step (W1.F.1)
│   │   ├── hunt_evil.py                    # HuntEvilBaseline + ProcessBaselineAnomaly (W1.F.8)
│   │   └── version.py                      # SCHEMA_VERSION constant + migration helpers
│   ├── verification/
│   │   ├── strategy.py                     # VerifierStrategy Protocol
│   │   ├── derive_seeds.py                 # blake3-keyed seed derivation (W1.C.1)
│   │   ├── cloud_self_consistency.py       # CloudSelfConsistency (W1.C.2)
│   │   ├── airgap_cross_engine.py          # AirGapCrossEngine (W3.A.1)
│   │   ├── dual_lane_cross_engine.py       # DualLaneCrossEngine (W3.A.2)
│   │   └── universal_self_consistency.py   # USC judge (Chen 2023)
│   ├── planning/
│   │   ├── planner.py                      # Planner Protocol + CloudPlanner + LocalPlanner (W1.G.5)
│   │   ├── planner_critique.py             # CoVe critique (W2.D.1)
│   │   ├── playbook_loader.py              # Inject playbook into planner system prompt (W1.F.6)
│   │   ├── executor_prompt.py              # Executor system prompt with caveats include (W1.F.10)
│   │   └── prompts/
│   │       ├── planner_system.md
│   │       ├── examiner_caveats.md         # Tier-1 caveats (W1.F.7)
│   │       ├── negative_hypothesis_examples.md  # Few-shots (W4.F.1)
│   │       └── adversarial_reasoning.md    # Attacker-mindset hints (W4.F.2)
│   ├── playbooks/
│   │   ├── memory.yml                      # SANS canonical Volatility 3 sequence + DKOM (W1.F.2)
│   │   ├── disk.yml                        # mmls→fsstat→fls→MFT→registry→Prefetch→EVTX→plaso (W1.F.3)
│   │   └── triage.yml                      # KAPE/Velociraptor zip flow (W1.F.4)
│   ├── knowledge/
│   │   ├── hunt_evil.yml                   # 8 canonical process baselines (W1.F.9)
│   │   └── lolbins.yml                     # LOLBin cmdline shapes (W4.F.3)
│   ├── graph/
│   │   ├── nodes.py                        # All LangGraph node functions
│   │   ├── topology.py                     # build_graph(mode) → CompiledGraph
│   │   ├── reducers.py                     # State reducers for fanout merge
│   │   ├── checkpoint.py                   # SqliteSaver setup + WAL pragmas (W3.E.1)
│   │   └── interrupt.py                    # interrupt() helpers + unverifiable_finalize wiring (W3.D.4)
│   ├── tools/
│   │   ├── base.py                         # ToolWrapper abstract
│   │   ├── args_validators.py              # Pydantic-AI args_validator framework (W2.E.1)
│   │   ├── vol3/                           # 10 Volatility plugin wrappers
│   │   │   ├── pslist.py
│   │   │   ├── psscan.py                   # NEW (W1.E.1)
│   │   │   ├── pstree.py
│   │   │   ├── cmdline.py
│   │   │   ├── dlllist.py
│   │   │   ├── malfind.py
│   │   │   ├── netscan.py
│   │   │   ├── svcscan.py
│   │   │   ├── handles.py
│   │   │   └── callbacks.py
│   │   ├── hayabusa_csv_timeline.py        # Phase 1 (W2.F.1)
│   │   ├── hayabusa_filter.py              # Phase 2 (W2.F.2)
│   │   ├── plaso_extract.py                # Phase 1 (W2.F.3)
│   │   ├── psort_filter.py                 # Phase 2 (W2.F.4)
│   │   ├── mmls.py / fls.py / fsstat.py    # Sleuth Kit
│   │   ├── mftecmd.py / recmd.py / pecmd.py
│   │   ├── bulk_extractor.py
│   │   ├── exiftool.py
│   │   ├── capa.py
│   │   └── sanitization.py                 # Prompt-injection scanner (W2.E.4)
│   ├── sandboxes/
│   │   ├── microsandbox_provider.py        # Pattern 1 ephemeral VM (W1.A.6)
│   │   ├── tsi_provider.py                 # Pattern 2 TSI enrichment (W3.B.1)
│   │   └── rootfs_pin.py                   # SHA-256 pin verification
│   ├── ledger/
│   │   ├── writer.py                       # write + fsync + verify-readback (W2.G.1)
│   │   ├── chain.py                        # prev_entry_hash chain verification
│   │   ├── hmac_key.py                     # TPM-backed or gpg-encrypted (W1.G.6)
│   │   └── redaction.py                    # Auth-field stripping (W3.B.3)
│   ├── observability/
│   │   ├── langfuse_setup.py               # Self-host wiring (W1.A.7)
│   │   ├── otel_setup.py                   # OpenLLMetry config (W2.G.2)
│   │   └── trace_link.py                   # trace_id ↔ ledger cross-link (W3.E.5)
│   ├── cli/
│   │   ├── __main__.py
│   │   ├── init.py / resume.py / reverify.py / status.py
│   │   ├── ls.py / show.py / export.py / validate.py
│   │   ├── mode.py / gc.py / health.py
│   │   └── doctor.py                       # Pre-flight checks (W5.A.4)
│   └── adapters/
│       ├── opencti_mcp.py                  # OpenCTI enrichment (W5.B.1)
│       ├── velociraptor_mcp.py             # Live-endpoint mode (W5.B.2)
│       ├── ghidrassist_mcp.py              # RE workflows (optional, W5.C.1)
│       ├── atropos_export.py               # Trajectory export (optional, W5.C.2)
│       └── hermes_pager.py                 # Telegram/Signal pager (optional, W5.C.3)
├── verdict-skills/
│   ├── windows-triage/
│   │   ├── SKILL.md                        # agentskills.io frontmatter with required_tools (W4.A.1)
│   │   └── KNOWLEDGE.md                    # LOLBins, registry persistence, EVTX patterns (W4.A.2)
│   ├── linux-triage/
│   ├── memory-forensics/
│   ├── network-pcap/
│   ├── malware-static/
│   └── report-writing/
├── tests/
│   ├── schemas/                            # Phase 1 schema tests
│   ├── verification/                       # Phase 2 verifier tests
│   ├── planning/                           # Planner + critique tests
│   ├── playbooks/                          # YAML load tests
│   ├── prompts/                            # Caveat injection tests
│   ├── knowledge/                          # hunt_evil load tests
│   ├── graph/                              # LangGraph topology tests + fanout race
│   ├── tools/                              # Each tool wrapper integration test
│   ├── sandboxes/                          # Microsandbox + TSI tests
│   ├── ledger/                             # Chain integrity + HMAC tests
│   ├── observability/                      # Langfuse + OTel tests
│   ├── cli/                                # CLI tests
│   ├── chaos/                              # kill-9 chaos tests (W3.E.6)
│   ├── smoke/                              # Cross-cutting smoke tests
│   │   ├── test_pretooluse_deny.py         # xfail-marked (W1.D.1)
│   │   └── test_amendment_a2_guard.py      # CI guard for cli.py reappearance (per CLAUDE.md)
│   └── e2e/                                # End-to-end against fixtures
├── inspect_ai/
│   ├── tasks/
│   │   ├── verdict_eval_cloud.py           # (W4.D.1)
│   │   ├── verdict_eval_airgap.py          # (W4.D.2)
│   │   └── verdict_eval_dual.py            # (W4.D.3)
│   ├── scorers/
│   │   ├── step_efficiency.py              # (W4.E.1)
│   │   ├── findings_precision.py           # (W4.E.2)
│   │   ├── findings_recall.py              # (W4.E.3)
│   │   ├── mitre_subtechnique_precision.py # (W4.E.4)
│   │   └── negative_hypothesis_quality.py  # (W4.E.5)
│   └── ground_truth/
│       ├── case_001_lolbins/               # 17 indicators (W4.C.1)
│       ├── case_002_credtheft/             # 17 indicators (W4.C.2)
│       └── case_003_ransomware/            # 16 indicators (Honeynet derivative) (W4.C.3)
├── scripts/
│   ├── install.sh                          # Three-credential-path install (W1.A.1)
│   ├── verdict-install.sh                  # Layer over Protocol SIFT install.sh
│   ├── run-all-tests.sh                    # Per-service pytest + cargo test
│   ├── package-devpost.sh                  # Submission zip (W6.D.1)
│   ├── shoot-demo.sh                       # Two-pane recording driver (W6.A.2)
│   └── healthcheck.sh                      # Continuous /health probe (W3.F.1)
├── .github/
│   └── workflows/
│       ├── l0-static.yml                   # ruff + cargo check
│       ├── l1-unit.yml                     # uv run pytest per service + cargo test
│       ├── l2-sift-lite.yml                # Sysbox advisory
│       ├── l3-goldens.yml                  # QEMU microvm + qcow2 (releases only)
│       ├── inspect-ai-evals.yml            # Three per-mode CI jobs (W4.D)
│       ├── release.yml                     # On `v<N>` tag
│       └── devpost-submit.yml              # On `v-submit` tag
└── packer/
    └── sift-microvm.pkr.hcl                # L3 warm qcow2 from sift-2026.03.24.ova
```

Total: ~140 first-class files. Each phase lists which files it creates or touches.

---

## Per-week phases — task-by-task

The plan below is exhaustive. Every task has owner, hours, and TDD substeps. Tasks are sequenced; do them in order within a phase. Phases within a week can parallelize across teammates.

---

# WEEK 1 (May 2 – May 8): Foundations + Schemas

**Theme:** Lock the contracts. Stand up infrastructure. Hardware-validate inference. Author all DFIR content.
**Critical-path output:** Schemas frozen; SGLang + Microsandbox + Langfuse all responding to a smoke test by Thursday May 8.
**If this week slips:** Week 2 cannot begin. Drop Phase G (architecture-review docs) before slipping the schema deadline.
**Cumulative team-days:** Tim ~5, Beaver ~1.5, Haley ~2, KP ~5.

## Phase W1.A — Infrastructure stand-up (Tim, ~2 days)

### W1.A.1 — `scripts/install.sh` with cloud credential detection
- [ ] **W1.A.1.a** — Write failing test `tests/cli/test_install_credentials.py::test_detects_oauth_token_first`. Launch the credentials helper in a subprocess with only `CLAUDE_CODE_OAUTH_TOKEN` set in that subprocess environment; assert install reports `mode=oauth`. Run → RED.
- [ ] **W1.A.1.b** — Write credential detection logic (`CLAUDE_CODE_OAUTH_TOKEN` env → interactive `~/.claude/` → `ANTHROPIC_API_KEY` → optional `OPENROUTER_API_KEY`) in `scripts/install.sh` + Python helper `src/verdict/cli/credentials.py`. Run → GREEN. `OPENROUTER_API_KEY` is host-side only for AI-agent fallback; `verdict doctor` must fail if any cloud credential would be passed into a microsandbox env.
- [ ] **W1.A.1.c** — Commit: `feat(cli): three-credential-path install per A1 [W1.A.1]`

### W1.A.2 — SIFT VM provisioning (manual + scripted)
- [ ] **W1.A.2.a** — Document VM specs in `docs/RELEASE.md`: 32GB RAM, 8 vCPU, 200GB disk, KVM enabled. Convert `sift-2026.03.24.ova` to VMware Workstation per project's existing `scripts/sift-vm-bootstrap.sh`.
- [ ] **W1.A.2.b** — Smoke test: `vol3 -h` runs inside VM. Verify Python 3.11 present.
- [ ] **W1.A.2.c** — Commit: `docs(build): SIFT VM provisioning checklist [W1.A.2]`

### W1.A.3 — Microsandbox install
- [ ] **W1.A.3.a** — Run `curl -fsSL https://install.microsandbox.dev | sh` inside SIFT VM. Verify `microsandbox --version` returns. Verify `microsandbox-mcp` binary present.
- [ ] **W1.A.3.b** — Smoke test: spawn an Ubuntu 22.04 microVM, run `vol3 -h`, destroy. Document spawn time in `docs/RELEASE.md` (target <500ms).
- [ ] **W1.A.3.c** — Build `verdict-sift-tools` rootfs Docker image with the 12 forensic tools pinned to versions: `vol3==2.10.0`, `hayabusa==2.18.0`, `plaso==20260427`, `MFTECmd==1.2.x`, etc. Push as `verdict-sift-tools:v0.1` and capture SHA-256.
- [ ] **W1.A.3.d** — Commit: `feat(sandbox): microsandbox install + verdict-sift-tools rootfs pinned [W1.A.3]`

### W1.A.4 — SGLang + Qwen3 + GLM-4.5-Air on dev rig (Haley, ~1 day)
- [ ] **W1.A.4.a** — Install SGLang per upstream docs. Verify GPU detected (target: 80GB H100 or 2× A100).
- [ ] **W1.A.4.b** — Serve Qwen3-30B-A3B-Thinking-2507 with `--tool-call-parser qwen` at port 30000. Verify `/v1/models` lists the model and a 10-call smoke test returns non-empty `tool_calls`.
- [ ] **W1.A.4.c** — Serve GLM-4.5-Air with `--tool-call-parser glm` at port 30001 (or colocate behind the same SGLang server with model_name routing). Verify `/v1/models` lists the model and a 10-call smoke test returns non-empty structured output.
- [ ] **W1.A.4.d** — Parser-name verification spike. Run `python -m sglang.launch_server --help` on the pinned SGLang version and record the accepted parser names in `docs/RELEASE.md`; if the installed version differs from current docs, update launch commands and lockfiles in the same task before any wrapper work lands.
- [ ] **W1.A.4.d** — Run synthetic 100-call tool-parse harness against each model. **Gate:** ≥98% non-empty `tool_calls` on both. If <98% → escalate; consider switching primary to GLM, or defer air-gap mode to v2.
- [ ] **W1.A.4.e** — Commit: `feat(inference): SGLang + Qwen3 + GLM-4.5-Air serving with tool-call parsers [W1.A.4]`

### W1.A.5 — FastMCP gateway skeleton (Tim)
- [ ] **W1.A.5.a** — Write failing test `tests/runtime/test_gateway_case_init.py::test_case_init_returns_handle`. Start the real FastMCP gateway process and call the real `case_init` tool against a temporary case directory and read-only sample evidence path; assert it returns `{case_id, mode}` and writes a `case_init` ledger entry. Run → RED.
- [ ] **W1.A.5.b** — Implement `src/verdict/runtime/gateway.py` with FastMCP, single tool `case_init`. Wire the real `detect_mode()` contract from day one: cloud requires Anthropic reachability, air-gap requires SGLang reachability, dual requires both. If neither prerequisite is reachable, fail closed with a diagnostic rather than returning a default mode.
- [ ] **W1.A.5.c** — Commit: `feat(runtime): FastMCP gateway skeleton with case_init [W1.A.5]`

### W1.A.6 — Microsandbox provider Pattern 1 (per-tool ephemeral microVM)
- [ ] **W1.A.6.a** — Write failing test `tests/sandboxes/test_microsandbox_provider.py::test_per_call_ephemeral_microvm`. Spawn sandbox with read-only `/evidence` mount, run `cat /etc/os-release`, destroy. Assert `network=False` enforced. Run → RED.
- [ ] **W1.A.6.b** — Implement `src/verdict/sandboxes/microsandbox_provider.py` per v4.5 line 461 sketch. Network=False default; `mounts=[ReadOnly(...)]`; SHA-256 stdout.
- [ ] **W1.A.6.c** — Commit: `feat(sandbox): per-tool ephemeral microsandbox provider Pattern 1 [W1.A.6]`

### W1.A.7 — Langfuse self-host (Tim)
- [ ] **W1.A.7.a** — Stand up `docker-compose.yml` with Langfuse v2 (Postgres-only, ~1.5GB RAM). Verify UI loads on `http://localhost:3000`. **Threshold:** if v2 deployment hits 4-hour blocker, fall back to OpenLLMetry → local Tempo viewer; document why in `docs/RELEASE.md`.
- [ ] **W1.A.7.b** — Write smoke test `tests/observability/test_langfuse_smoke.py::test_one_trace_renders`. Send one synthetic trace via SDK; assert `/api/public/traces/{id}` returns 200.
- [ ] **W1.A.7.c** — Commit: `feat(observability): Langfuse v2 self-host + smoke trace [W1.A.7]`

### W1.A.8 — Inspect AI hello-world
- [ ] **W1.A.8.a** — `pip install inspect-ai` per CLAUDE.md. Author `inspect_ai/tasks/hello_world.py` minimal task. Run `inspect eval inspect_ai/tasks/hello_world.py`. Assert pass.
- [ ] **W1.A.8.b** — Commit: `feat(eval): Inspect AI hello-world task [W1.A.8]`

### W1.A.9 — Mechanical hard-rule enforcement (Tim, ~3 hours)
Pulls forward what `CONTRIBUTING.md` already promises and what `CLAUDE.md` §3.7 + §3.10 require. Without this task, the hard rules are rules of prose only.

- [ ] **W1.A.9.a** — Failing test `tests/policy/test_no_mocks_hook.py::test_rejects_unittest_mock_import`. Assertion: `check_no_mocks.scan(["tests/policy/fixtures/has_mock_import.py"]).violations` is non-empty AND the offending line is reported. Plus `test_allows_third_party_boundary_patch` — patching `httpx` in a single targeted test passes.
- [ ] **W1.A.9.b** — Implement `scripts/check_no_mocks.py` (~40 LOC AST walker). Rejects: `import unittest.mock`, `from unittest import mock`, `import responses`, `import vcr`, `import betamax`, `import httpx_mock`, regex `^\s*if .*(MOCK|TEST_MODE).*:\s*$`, regex `os\.environ\.get\(['"]VERDICT_TEST`. Walks all `.py` under `src/verdict/` and `tests/`.
- [ ] **W1.A.9.c** — Author `.pre-commit-config.yaml` at repo root with hooks: (1) `commitizen check` enforcing `^(feat|fix|test|chore|docs|refactor)\(\w+\): .* \[W\d+\.[A-Z]\.\d+(\.[a-z])?\]$` on commit message; (2) `ruff check --select ALL`; (3) the local `check-no-mocks` hook from W1.A.9.b; (4) `cargo fmt --check`. Run `pre-commit install --install-hooks` in `scripts/install.sh`.
- [ ] **W1.A.9.d** — Add `.github/workflows/eval-hallucination-gate.yml`: on PR, runs `inspect eval inspect_ai/tasks/verdict_eval_cloud.py --score hallucination_rate` against the real evaluator once `verdict doctor --mode cloud` succeeds. Until the real scorer exists in W4.D.1, the workflow must fail with `scorer_not_implemented` rather than returning a passing score.
- [ ] **W1.A.9.e** — Drop the `test -f .pre-commit-config.yaml &&` short-circuit at `CONTRIBUTING.md` line 140 (file exists now; the guard is no longer needed and silently masks a missing config).
- [ ] **W1.A.9.f** — Commit: `feat(policy): mechanical enforcement of §3.7 + §3.10 (no-mocks AST hook + commit-msg regex + hallucination CI gate) [W1.A.9]`

## Phase W1.B — Schema bundle (Tim, ~2 hours)

This is the contract every teammate will code against. **Lock by Sunday May 4.** All schema work must reconcile against `docs/ARCHITECTURE.md` §4.

### W1.B.1 — `ArtifactClass` enum
- [ ] **W1.B.1.a** — Write failing test `tests/schemas/test_artifact_class.py::test_enum_has_13_required_members`. Run → RED.
- [ ] **W1.B.1.b** — Implement `src/verdict/schemas/artifact_class.py` per Appendix A.1.
- [ ] **W1.B.1.c** — Commit: `feat(schema): ArtifactClass enum (FOR500 corroboration) [W1.B.1]`

### W1.B.2 — `CaveatID` enum
- [ ] **W1.B.2.a** — Write failing test `tests/schemas/test_caveat_id.py::test_enum_covers_tier1_examiner_caveats`. Assert all 7 from the current planned caveat source `src/verdict/planning/prompts/examiner_caveats.md` and the root `CLAUDE.md` §3.3 table. Run → RED.
- [ ] **W1.B.2.b** — Implement `src/verdict/schemas/caveat_id.py` per Appendix A.2.
- [ ] **W1.B.2.c** — Commit: `feat(schema): CaveatID enum from project MEMORY.md Tier-1 [W1.B.2]`

### W1.B.3 — `EvidenceItem` + `EvidenceManifest`
- [ ] **W1.B.3.a** — Write failing test `tests/schemas/test_evidence.py::test_manifest_hash_is_blake3_of_sorted_pairs`. Run → RED.
- [ ] **W1.B.3.b** — Implement `src/verdict/schemas/evidence.py` per v4.5 lines 153–168 + Appendix A.3.
- [ ] **W1.B.3.c** — Commit: `feat(schema): EvidenceItem + EvidenceManifest schemas [W1.B.3]`

### W1.B.4 — `Artifact` + `ToolOutput` base
- [ ] **W1.B.4.a** — Write failing test `tests/schemas/test_tool_output.py::test_invocation_hash_combines_name_version_args_evidence`. Run → RED.
- [ ] **W1.B.4.b** — Implement `src/verdict/schemas/tool_output.py` per v4.5 lines 170–193 + Appendix A.4.
- [ ] **W1.B.4.c** — Commit: `feat(schema): Artifact + ToolOutput base for tool wrapper contract [W1.B.4]`

### W1.B.5 — `Hypothesis` + `InvestigationPlan` + `PlanComprehensionEcho` + `PlannerCritiqueVerdict`
- [ ] **W1.B.5.a** — Write failing tests in `tests/schemas/test_plan.py`: `test_mitre_subtechnique_regex_validates_T1055_012` (passes) and `test_mitre_invalid_format_rejected` (raises). Plus `test_negative_hypothesis_quality_rejects_degenerate`. Run → RED.
- [ ] **W1.B.5.b** — Implement `src/verdict/schemas/plan.py` with all four classes + the `mitre_technique` regex validator (`^T\d{4}(\.\d{3})?$`) + `_negative_hypothesis_quality` validator (deny-list: cosmic/alien/nothing/not-relevant/n-a; require non-None mitre_technique; require non-empty artifact_families).
- [ ] **W1.B.5.c** — Commit: `feat(schema): Hypothesis + InvestigationPlan + comprehension/critique schemas [W1.B.5]`

### W1.B.6 — `Finding` skeleton
- [ ] **W1.B.6.a** — Write failing test `tests/schemas/test_finding.py::test_finding_round_trips_through_json`. Run → RED.
- [ ] **W1.B.6.b** — Implement `src/verdict/schemas/finding.py` skeleton: all v4.5 fields plus the new ones (`artifact_classes`, `caveats_acknowledged`).
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
- [ ] **W1.B.11.b** — Implement `src/verdict/schemas/ledger.py` per v4.5 lines 245–278 plus the v4.4 environment-metadata fields. Add `output_files_sha256: dict[str, str] = {}` field.
- [ ] **W1.B.11.c** — Commit: `feat(schema): LedgerEntry with three-ID hierarchy + exam-env metadata [W1.B.11]`

### W1.B.12 — `schema_version` discipline + `src/verdict/schemas/version.py`
- [ ] **W1.B.12.a** — Failing test: `test_schema_version_is_1_on_all_top_level_models`. Loop through `[InvestigationPlan, Finding, LedgerEntry, EvidenceManifest, ToolOutput]`; assert `.schema_version == 1`.
- [ ] **W1.B.12.b** — Implement: add `schema_version: int = 1` to all five top-level schemas; centralize in `src/verdict/schemas/version.py`.
- [ ] **W1.B.12.c** — Commit: `feat(schema): schema_version discipline across top-level models [W1.B.12]`

### W1.B.13 — `VerdictStatus` enum
- [ ] **W1.B.13.a** — Failing test: `test_verdict_status_has_canonical_states`. Assert exactly the six statuses from `CLAUDE.md` §3.6: `VETTED_CLOUD`, `VETTED_AIRGAP`, `VETTED_DUAL`, `CONTESTED`, `UNVERIFIABLE`, `EXHAUSTED_REPLAN`. Assert `DRAFT`, `APPROVED`, and `REJECTED` live only on the separate `Finding.review_state` enum.
- [ ] **W1.B.13.b** — Implement.
- [ ] **W1.B.13.c** — Commit: `feat(schema): VerdictStatus enum [W1.B.13]`

### W1.B.14 — `CaseConclusion` for no-evil terminal cases
- [ ] **W1.B.14.a** — Failing test `tests/schemas/test_case_conclusion.py::test_no_evil_found_requires_playbook_steps`. Assert `CaseConclusion(status="NO_EVIL_FOUND", playbook_steps_executed=[])` raises validation error, and a conclusion with at least one playbook step plus evidence hashes validates.
- [ ] **W1.B.14.b** — Implement `src/verdict/schemas/case_conclusion.py` with status values `NO_EVIL_FOUND`, `EVIL_FOUND`, `UNVERIFIABLE`; require `playbook_steps_executed: list[str] = Field(min_length=1)`, `evidence_hashes: dict[Path, str]`, and `rationale: str`. Do not add `NO_EVIL_FOUND` to `VerdictStatus`.
- [ ] **W1.B.14.c** — Commit: `feat(schema): CaseConclusion for no-evil terminal cases [W1.B.14]`

## Phase W1.C — Verifier strategy seed-derivation fix (Beaver, ~1 hour)

### W1.C.1 — `derive_seeds(case_id)` helper
- [ ] **W1.C.1.a** — Failing test `tests/verification/test_derive_seeds.py::test_three_distinct_deterministic_per_case`. Run → RED.
- [ ] **W1.C.1.b** — Implement `src/verdict/verification/derive_seeds.py` using blake3 keyed-hash pattern.
- [ ] **W1.C.1.c** — Commit: `feat(verification): derive_seeds(case_id) for n=3 self-consistency [W1.C.1]`

### W1.C.2 — `CloudSelfConsistency` impl
- [ ] **W1.C.2.a** — Failing integration test `tests/verification/test_cloud_self_consistency.py::test_three_distinct_seeds_in_api_calls`. Require `verdict doctor --mode cloud` first; execute the real Anthropic/Claude client in a bounded smoke request and assert 3 calls, 3 distinct seeds, `temperature=0.7`, and non-empty verifier outputs. Run → RED.
- [ ] **W1.C.2.b** — Implement `src/verdict/verification/cloud_self_consistency.py` per Appendix A.5.
- [ ] **W1.C.2.c** — Commit: `fix(verification): CloudSelfConsistency samples 3 diverse paths (Wang 2022) [W1.C.2]`

### W1.C.3 — `VerifierStrategy` Protocol + Universal Self-Consistency baseline
- [ ] **W1.C.3.a** — Failing test `tests/verification/test_strategy_protocol.py::test_strategy_returns_verdict_result`. Define a tiny in-test concrete strategy that computes its result from supplied verifier outputs; assert it conforms to the `VerifierStrategy` Protocol without any hardcoded production verdict. Run → RED.
- [ ] **W1.C.3.b** — Implement `src/verdict/verification/strategy.py` (Protocol) + a real `universal_self_consistency.py` fallback that takes already-produced verifier candidates, groups by `(artifact_paths, mitre_technique)`, and returns `CONTESTED` or the matching `VETTED_*`/`UNVERIFIABLE` result according to the documented quorum rule. No placeholder implementation lands.
- [ ] **W1.C.3.c** — Commit: `feat(verification): VerifierStrategy Protocol + USC baseline [W1.C.3]`

## Phase W1.D — PreToolUse caveat + smoke scaffold (Tim, ~30 min)

### W1.D.1 — CI smoke-test scaffold (xfail-marked)
- [ ] **W1.D.1.a** — Author `tests/smoke/test_pretooluse_deny.py` marked `pytest.mark.xfail(reason="anthropics/claude-code#33106 + #37210")`. Test invokes `claude` subprocess with a PreToolUse hook returning `permissionDecision: "deny"` for an MCP write; asserts the call is blocked.
- [ ] **W1.D.1.b** — Add `[smoke]` marker to `pyproject.toml` so `pytest -m smoke` finds it.
- [ ] **W1.D.1.c** — Commit: `test(smoke): PreToolUse deny scaffold (xfail per #33106 #37210) [W1.D.1]`

### W1.D.2 — Apply v4.6 P2 to v4.5 audit doc
- [ ] **W1.D.2.a** — Append the Layer-1 caveat paragraph to v4.5 architecture caption (line 144).
- [ ] **W1.D.2.b** — Commit: `docs(audit): v4.6 P2 — Layer-1 PreToolUse version-dependence caveat [W1.D.2]`

## Phase W1.E — Tool surface scaffolding (Tim, ~2 hours)

The 12 tool wrappers ship in W2.E. This phase ships the schema scaffolding + `psscan` per v4.6 P3.

### W1.E.1 — `vol_psscan` MCP tool wrapper
- [ ] **W1.E.1.a** — Failing integration test `tests/tools/test_vol_psscan.py::test_psscan_returns_pids`. Require `verdict doctor --mode airgap` and a real memory image from `inspect_ai/ground_truth/case_001_lolbins/`; invoke `vol3 windows.psscan` through the real microsandbox provider; assert returned `ToolOutput` contains process artifacts and a valid invocation hash. Run → RED.
- [ ] **W1.E.1.b** — Implement `src/verdict/tools/vol3/psscan.py` mirroring `vol_pslist` shape from project's `services/mcp/`.
- [ ] **W1.E.1.c** — Commit: `feat(tools): vol_psscan wrapper for DKOM/T1014 cross-validation [W1.E.1]`

### W1.E.2 — Tool wrapper base class
- [ ] **W1.E.2.a** — Failing test `tests/tools/test_tool_base.py::test_base_records_invocation_hash`. Assert any wrapper extending `ToolWrapper` records `invocation_hash = blake3(tool_name + tool_version + args + evidence_hash)`.
- [ ] **W1.E.2.b** — Implement `src/verdict/tools/base.py` abstract `ToolWrapper` with `pre_run` (compute invocation hash) + `run` (subclass impl) + `post_run` (sandbox destroy + ledger write hooks).
- [ ] **W1.E.2.c** — Commit: `feat(tools): ToolWrapper abstract base with invocation hashing [W1.E.2]`

### W1.E.3 — Apply v4.6 P3 + P4 to v4.5 audit doc
- [ ] **W1.E.3.a** — Update v4.5 line 796 tool list to include 10 vol3 plugins.
- [ ] **W1.E.3.b** — Append DKOM caveat per P4.
- [ ] **W1.E.3.c** — Commit: `docs(audit): v4.6 P3 + P4 — psscan in tool list, DKOM rationale [W1.E.3]`

## Phase W1.F — KP content authoring (KP, ~1.5 days)

### W1.F.1 — `Playbook` Pydantic schema
- [ ] **W1.F.1.a** — Failing test `tests/schemas/test_playbook.py::test_playbook_loads_yaml`. Run → RED.
- [ ] **W1.F.1.b** — Implement `src/verdict/schemas/playbook.py` with `Step` + `Playbook` classes per v4.6.
- [ ] **W1.F.1.c** — Commit: `feat(schema): Playbook + Step for planner methodology injection [W1.F.1]`

### W1.F.2 — Author `src/verdict/playbooks/memory.yml`
- [ ] **W1.F.2.a** — Failing test `tests/playbooks/test_memory_yml.py::test_memory_playbook_has_dkom_rule`. Run → RED.
- [ ] **W1.F.2.b** — Author per Appendix C.1.
- [ ] **W1.F.2.c** — Commit: `feat(playbooks): memory.yml — Volatility 3 sequence + DKOM rule [W1.F.2]`

### W1.F.3 — Author `src/verdict/playbooks/disk.yml`
- [ ] **W1.F.3.a** — Failing test `tests/playbooks/test_disk_yml.py::test_plaso_after_lighter_tools`. Run → RED.
- [ ] **W1.F.3.b** — Author per Appendix C.2.
- [ ] **W1.F.3.c** — Commit: `feat(playbooks): disk.yml [W1.F.3]`

### W1.F.4 — Author `src/verdict/playbooks/triage.yml`
- [ ] **W1.F.4.a** — Failing test `tests/playbooks/test_triage_yml.py::test_registry_first`. Run → RED.
- [ ] **W1.F.4.b** — Author per Appendix C.3.
- [ ] **W1.F.4.c** — Commit: `feat(playbooks): triage.yml [W1.F.4]`

### W1.F.5 — Apply v4.6 P5 to v4.5 audit doc
- [ ] **W1.F.5** — Append multi-artifact corroboration caveat. Commit: `docs(audit): v4.6 P5 — multi-artifact corroboration [W1.F.5]`

### W1.F.6 — `playbook_loader` injects into planner prompt
- [ ] **W1.F.6.a** — Failing test `tests/planning/test_playbook_loader.py::test_loader_picks_by_evidence_type`. Run → RED.
- [ ] **W1.F.6.b** — Implement `src/verdict/planning/playbook_loader.py::load_playbook_prompt(manifest: EvidenceManifest) -> str`.
- [ ] **W1.F.6.c** — Commit: `feat(planning): playbook_loader injects methodology by evidence type [W1.F.6]`

### W1.F.7 — Author `src/verdict/planning/prompts/examiner_caveats.md`
- [ ] **W1.F.7.a** — Failing test `tests/prompts/test_examiner_caveats.py::test_all_seven_caveats_present`. Run → RED.
- [ ] **W1.F.7.b** — Author per Appendix B.1.
- [ ] **W1.F.7.c** — Commit: `feat(prompts): examiner_caveats.md — Tier-1 caveats include [W1.F.7]`

### W1.F.8 — `HuntEvilBaseline` schema + `ProcessBaselineAnomaly` Hypothesis subtype
- [ ] **W1.F.8.a** — Failing test `tests/schemas/test_hunt_evil.py::test_baseline_loads`. Plus `test_anomaly_maps_to_T1036_005`.
- [ ] **W1.F.8.b** — Implement `src/verdict/schemas/hunt_evil.py` with both classes.
- [ ] **W1.F.8.c** — Commit: `feat(schema): HuntEvilBaseline + ProcessBaselineAnomaly (T1036.005) [W1.F.8]`

### W1.F.9 — Author `src/verdict/knowledge/hunt_evil.yml`
- [ ] **W1.F.9.a** — Failing test `tests/knowledge/test_hunt_evil_yml.py::test_eight_canonical_processes`. Run → RED.
- [ ] **W1.F.9.b** — Author per Appendix C.4 — 8 processes (svchost, lsass, csrss, winlogon, services, wininit, explorer, smss).
- [ ] **W1.F.9.c** — Commit: `feat(knowledge): hunt_evil.yml — 8 canonical Windows process baselines [W1.F.9]`

### W1.F.10 — Executor system-prompt include
- [ ] **W1.F.10.a** — Failing test `tests/planning/test_executor_prompt.py::test_includes_caveats_and_hunt_evil`. Assert prompt contains `AMCACHE_LASTMODIFIED_NOT_EXEC` and `svchost.exe`.
- [ ] **W1.F.10.b** — Implement `src/verdict/planning/executor_prompt.py::render_executor_prompt(role: str) -> str` that composes examiner_caveats.md + relevant hunt_evil entries.
- [ ] **W1.F.10.c** — Commit: `feat(planning): executor system prompt with caveats + hunt evil [W1.F.10]`

### W1.F.11 — Apply v4.6 P6 to v4.5 audit doc
- [ ] **W1.F.11** — Append Tier-1 caveat caveat. Commit: `docs(audit): v4.6 P6 — Tier-1 caveats encoded [W1.F.11]`

## Phase W1.G — Architecture-review docs + ops surface (Tim, ~1 day)

### W1.G.1 — `docs/RELEASE.md` threat model section
- [ ] **W1.G.1.a** — Author per v4.5 line 369 (4 surfaces: insider, prompt-injection-from-evidence, malicious-tool-output, external-attacker). Mitigations + residual risks per surface. Microsandbox escape documented as accepted v1 risk.
- [ ] **W1.G.1.b** — Commit: `docs(release): document 4 adversary surfaces [W1.G.1]`

### W1.G.2 — `docs/FAILURE_MODES.md`
- [ ] **W1.G.2.a** — Author component × failure × detection × recovery × escalation table. Cover: microsandbox spawn timeout (30s + 1 retry), SGLang server crash, Langfuse fail-open, partial ledger write recovery, Claude API rate-limit, OpenCTI unreachable.
- [ ] **W1.G.2.b** — Commit: `docs: FAILURE_MODES.md [W1.G.2]`

### W1.G.3 — `docs/RELEASE.md` CLI section
- [ ] **W1.G.3.a** — Author full CLI surface: `verdict {init, resume, reverify, status, ls, show <id>, export <id>, validate <id>, mode, gc, health, doctor}`. Commands not implemented in v1 must be listed only in a clearly marked roadmap table, not exposed as callable placeholders.
- [ ] **W1.G.3.b** — Commit: `docs(release): enumerate verdict commands [W1.G.3]`

### W1.G.4 — `docs/RELEASE.md` schema migration section
- [ ] **W1.G.4** — Author migration policy: `schema_version` field on all top-level schemas; breaking changes ship a `migrations/v{N}_to_v{N+1}.py` script. Commit: `docs(release): document schema migration policy [W1.G.4]`

### W1.G.5 — `Planner` Protocol + `CloudPlanner` + `LocalPlanner` (Beaver collaborates)
- [ ] **W1.G.5.a** — Failing test `tests/planning/test_planner_protocol.py::test_protocol_returns_investigation_plan`. Plus `test_planner_bound_at_gateway_init` — assert mode-switching code lives in `runtime/mode_detect.py`, not in `planner_node`.
- [ ] **W1.G.5.b** — Implement `src/verdict/planning/planner.py` with the Protocol + two impls.
- [ ] **W1.G.5.c** — Commit: `feat(planning): Planner Protocol + CloudPlanner + LocalPlanner [W1.G.5]`

### W1.G.6 — HMAC key handling (TPM-backed if present, else gpg-encrypted)
- [ ] **W1.G.6.a** — Failing integration tests: `tests/ledger/test_hmac_key.py::test_tpm_path_when_dev_tpmrm0_present` runs only on hosts with `/dev/tpmrm0` and verifies the TPM-backed path; `test_gpg_path_when_dev_tpmrm0_absent` runs in the CI environment that lacks `/dev/tpmrm0` and verifies the gpg-encrypted fallback. If the host does not match a test prerequisite, fail with a prerequisite diagnostic rather than simulating the device.
- [ ] **W1.G.6.b** — Implement `src/verdict/ledger/hmac_key.py` with both paths. Passphrase prompt at gateway init for the gpg path.
- [ ] **W1.G.6.c** — Commit: `feat(ledger): HMAC key TPM-backed or gpg-encrypted [W1.G.6]`

### W1.G.7 — Evidence manifest with periodic re-hash check
- [ ] **W1.G.7.a** — Failing test `tests/runtime/test_evidence_recheck.py::test_recheck_every_10_super_steps`. Plus `test_mismatch_writes_ledger_entry_and_halts`.
- [ ] **W1.G.7.b** — Implement re-hash loop in `src/verdict/runtime/evidence_recheck.py`. Mismatch → `LedgerEntry(event_type="evidence_hash_recheck")` with both hashes + halt with `HashMismatchError`.
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
| Architecture-review docs present | `ls docs/{RELEASE,FAILURE_MODES}.md` |
| `examiner_caveats.md` includes all 7 CaveatID values | `grep -c "## " src/verdict/planning/prompts/examiner_caveats.md` returns 7 |
| `hunt_evil.yml` has 8 canonical processes | `python -c "import yaml; print(len(yaml.safe_load(open('src/verdict/knowledge/hunt_evil.yml'))))"` returns 8 |
| Schema and DFIR rule patches represented in current architecture | `docs/ARCHITECTURE.md` cites the current decisions |
| Conventional Commits enforced (no `--no-verify`) | `git log --oneline -50 | grep -c '^[a-f0-9]\+ \(feat\|test\|fix\|docs\|chore\)' = 50` |

If any gate is RED on May 8: **descope before slipping**. Drop in this priority order: W1.G.7 → W1.G.6 → W1.A.7 (Langfuse v2; ship without it, fall back to OTel-only) → W1.G.1-3 (push docs to W6).

---

# WEEK 2 (May 9 – May 15): Tool surface + Plan-then-Execute refactor

**Theme:** Wrap all 12 SIFT tools as MCP tools. Refactor LangGraph topology to explicit Plan-then-Execute. Add `planner_critique_node`. Wire per-tool args validators. Split plaso/Hayabusa.
**Critical-path output:** All 12 tools callable through gateway. LangGraph compiles with 8 nodes: `planner` → `planner_critique` → `comprehension_gate` → `executor_fanout` (composes DenyRuleWrapper / ToolExecutor / LedgerEmitter per branch) → `pivot` → `quorum` → `replan` → `finalize`. (`unverifiable_finalize_node` is a helper called from `replan_node`, not a registered graph node.)
**If this week slips:** week 3 verifier work pushes; cut pivot_node + unverifiable_finalize from v1; ship pure replan_max=3 → quietly stuck CONTESTED (v4.4 SHOULD-FIX leaks back in).
**Cumulative team-days:** Tim ~5, Beaver ~5, Haley ~1, KP ~3.

## Phase W2.A — 12 SIFT tool wrappers (Tim + KP, ~3 days each)

For each tool:
- [ ] Failing integration test in `tests/tools/test_<tool>.py` against a fixture.
- [ ] Implement `src/verdict/tools/<tool>.py` extending `ToolWrapper`.
- [ ] Add to gateway tool registry.
- [ ] Commit: `feat(tools): <tool> wrapper [W2.A.<n>]`

| ID | Tool | Owner | Hours |
|---|---|---|---|
| W2.A.1 | `vol3.pslist` | Tim | 3 |
| W2.A.2 | `vol3.pstree` | Tim | 2 |
| W2.A.3 | `vol3.cmdline` | Tim | 2 |
| W2.A.4 | `vol3.dlllist` | Tim | 2 |
| W2.A.5 | `vol3.malfind` | Tim | 3 |
| W2.A.6 | `vol3.netscan` | Tim | 2 |
| W2.A.7 | `vol3.svcscan` | Tim | 2 |
| W2.A.8 | `vol3.handles` | Tim | 2 |
| W2.A.9 | `vol3.callbacks` | Tim | 2 |
| W2.A.10 | `mmls` | KP | 1 |
| W2.A.11 | `fls` | KP | 1 |
| W2.A.12 | `fsstat` | KP | 1 |
| W2.A.13 | `MFTECmd` | KP | 3 |
| W2.A.14 | `RECmd` | KP | 3 |
| W2.A.15 | `PECmd` (Prefetch) | KP | 2 |
| W2.A.16 | `bulk_extractor` | KP | 2 |
| W2.A.17 | `exiftool` | KP | 1 |
| W2.A.18 | `capa` | KP | 2 |

`vol3.psscan` already in W1.E.1.

## Phase W2.B — Plan-then-Execute LangGraph refactor (Beaver, ~2 days)

### W2.B.1 — Five core nodes
- [ ] **W2.B.1.a** — Failing test `tests/graph/test_topology_compiles.py::test_five_nodes_present`. Assert nodes `planner`, `executor_fanout`, `quorum`, `replan`, `finalize` exist on the compiled graph.
- [ ] **W2.B.1.b** — Implement `src/verdict/graph/topology.py::build_graph(mode: Mode) -> CompiledGraph` and `src/verdict/graph/nodes.py` with real minimal node bodies for all five. Each node must read/write typed state and raise explicit `NotImplementedError` only for dependencies that are scheduled in a later task and never on the production happy path.
- [ ] **W2.B.1.c** — Commit: `feat(graph): five-node Plan-then-Execute topology [W2.B.1]`

### W2.B.2 — `comprehension_gate` node (v4.3)
- [ ] **W2.B.2.a** — Failing test `tests/graph/test_comprehension_gate.py::test_consensus_advances_executor_work` and `test_mismatch_routes_to_clarify`.
- [ ] **W2.B.2.b** — Implement gate node. Collects `PlanComprehensionEcho`s; validates consensus on `parsed_positive_hypothesis_ids`, `parsed_negative_hypothesis_ids`, `parsed_success_criteria_hash`.
- [ ] **W2.B.2.c** — Commit: `feat(graph): comprehension_gate validates executor consensus [W2.B.2]`

### W2.B.3 — `ComprehensionMismatch` ledger entry on disagreement
- [ ] **W2.B.3.a** — Failing test: ledger contains structured per-executor diff on mismatch.
- [ ] **W2.B.3.b** — Implement event type + payload schema.
- [ ] **W2.B.3.c** — Commit: `feat(ledger): ComprehensionMismatch event with per-executor diff [W2.B.3]`

### W2.B.4 — Reducer pattern for fanout merge + race test
- [ ] **W2.B.4.a** — Failing test `tests/graph/test_fanout_race.py::test_4_executors_merge_deterministically`. 4 executors, randomized 0–500ms sleep each; assert final state contains all 4 outputs in deterministic order.
- [ ] **W2.B.4.b** — Implement `src/verdict/graph/reducers.py` with `Annotated[..., reducer]` for `executor_results` field.
- [ ] **W2.B.4.c** — Commit: `feat(graph): reducer pattern for parallel-executor merge [W2.B.4]`

### W2.B.5 — Pin LangGraph version
- [ ] **W2.B.5** — Pin in `pyproject.toml`. Commit: `chore(deps): pin langgraph version that passes fanout-race test [W2.B.5]`

## Phase W2.C — `executor_work` split into 3 wrappers (v4.5 fix from architecture review)

### W2.C.1 — `DenyRuleWrapper` (Layer 2 of three-layer immutability)
- [ ] **W2.C.1.a** — Failing test `tests/graph/test_deny_rule_wrapper.py::test_blocks_evidence_writes_in_all_modes`. Test args denied for cloud, airgap, dual.
- [ ] **W2.C.1.b** — Implement `src/verdict/graph/wrappers/deny_rule.py`. Layer 2 of three-layer defense — fires regardless of model. Owns deny-rule list (Tim).
- [ ] **W2.C.1.c** — Commit: `feat(graph): DenyRuleWrapper Layer 2 immutability [W2.C.1]`

### W2.C.2 — `ToolExecutor` (Beaver owns)
- [ ] **W2.C.2.a** — Failing test for typed dispatch + microsandbox spawn + result parsing into ToolOutput.
- [ ] **W2.C.2.b** — Implement.
- [ ] **W2.C.2.c** — Commit: `feat(graph): ToolExecutor wrapper [W2.C.2]`

### W2.C.3 — `LedgerEmitter` (Tim owns)
- [ ] **W2.C.3.a** — Failing test for write+fsync+verify-readback. Plus chain-integrity assertion.
- [ ] **W2.C.3.b** — Implement `src/verdict/graph/wrappers/ledger_emitter.py` + `src/verdict/ledger/writer.py` with the durability discipline.
- [ ] **W2.C.3.c** — Commit: `feat(ledger): LedgerEmitter wrapper with write+fsync+verify-readback [W2.C.3]`

### W2.C.4 — Compose three wrappers + replace executor_work
- [ ] **W2.C.4.a** — Failing test: end-to-end through composed `DenyRuleWrapper → ToolExecutor → LedgerEmitter`.
- [ ] **W2.C.4.b** — Wire composition in `src/verdict/graph/topology.py`.
- [ ] **W2.C.4.c** — Commit: `feat(graph): compose 3-wrapper executor_work [W2.C.4]`

## Phase W2.D — `planner_critique_node` (Beaver, ~1 day)

### W2.D.1 — CoVe (Chain-of-Verification, Dhuliawala 2023)
- [ ] **W2.D.1.a** — Failing test `tests/planning/test_planner_critique.py::test_failed_questions_route_back_to_planner`. Plus `test_all_pass_advances_to_comprehension_gate`.
- [ ] **W2.D.1.b** — Implement `src/verdict/planning/planner_critique.py`. Same model drafts CoVe questions ABOUT THE PLAN ITSELF (does plan cover most-likely attacker techniques given evidence type? does it have positive AND negative for each artifact family? are success criteria measurable?). Answers them against case_init evidence summary; failed questions route back to planner with hint.
- [ ] **W2.D.1.c** — Commit: `feat(planning): planner_critique_node CoVe [W2.D.1]`

### W2.D.2 — `PlannerCritiqueVerdict` schema + `critique_verdict` ledger event
- [ ] **W2.D.2.a** — Failing test `tests/planning/test_planner_critique_verdict.py::test_schema_rejects_missing_failed_questions_when_route_back`. Plus `test_ledger_emits_critique_verdict_event_with_route_decision`. Assertions: `PlannerCritiqueVerdict(route="planner", failed_questions=[]).model_validate()` raises `ValidationError`; `ledger.last_entry.event_type == "critique_verdict"` after `planner_critique_node` runs.
- [ ] **W2.D.2.b** — Wire into LangGraph + ledger.
- [ ] **W2.D.2.c** — Commit: `feat(graph): planner_critique_node wired between planner + comprehension_gate [W2.D.2]`

### W2.D.3 — Planner CoT capture
- [ ] **W2.D.3.a** — Failing test `tests/planning/test_cot_capture.py::test_gzipped_cot_in_ledger`. Plus `test_8kb_attached_to_langfuse_span`.
- [ ] **W2.D.3.b** — Implement extraction (Claude Agent SDK responses for cloud, Qwen3-Thinking `<think>` blocks for airgap), gzip, hash via `planner_cot_gzip_hash`, store via LedgerEmitter, attach first 8KB to Langfuse span attribute.
- [ ] **W2.D.3.c** — Commit: `feat(observability): planner CoT capture (gzipped ledger + 8KB Langfuse) [W2.D.3]`

### W2.D.4 — MCP mode-gating hook
- [ ] **W2.D.4.a** — Failing smoke test `tests/smoke/test_mcp_mode_gating.py::test_airgap_blocks_fetch_and_filesystem`. Launch Claude Code with `VERDICT_MODE=airgap` and assert attempts to call `fetch` or `filesystem` are blocked before tool execution; assert `.mcp.json` lists only `sequential-thinking`.
- [ ] **W2.D.4.b** — Implement `.claude/settings.json` PreToolUse mode-gating hook and helper script. In air-gap mode, block `fetch`, `filesystem`, `github`, `mitre-attack`, and `context7`; in cloud/dual mode, permit only the explicit mode config named by the operator. Do not rely on prompts for this boundary.
- [ ] **W2.D.4.c** — Commit: `feat(hooks): mode-gate MCP configs by Verdict mode [W2.D.4]`

## Phase W2.E — Per-tool args validators (Beaver + Tim, ~1.5 days)

### W2.E.1 — `args_validators` framework
- [ ] **W2.E.1.a** — Failing test `tests/tools/test_args_validator.py::test_unknown_flag_raises_modelretry`. Plus `test_invalid_pid_type_raises`.
- [ ] **W2.E.1.b** — Implement `src/verdict/tools/args_validators.py` with Pydantic-AI `args_validator` framework. `tool_arg_retry_max=2`, then UNVERIFIABLE.
- [ ] **W2.E.1.c** — Commit: `feat(tools): args_validator framework with retry budget 2 [W2.E.1]`

### W2.E.2 — `vol3` validators (parse `vol3 --help` once at startup; allow-list of 26 plugins)
- [ ] **W2.E.2.a** — Failing test: reject `vol3 --foo` and `vol3 windows.invalid_plugin`.
- [ ] **W2.E.2.b** — Implement parse-help-at-startup + hash-pinned allow-list.
- [ ] **W2.E.2.c** — Commit: `feat(tools): vol3 args_validator with hash-pinned plugin allow-list [W2.E.2]`

### W2.E.3 — `plaso` filter pre-validator
- [ ] **W2.E.3.a** — Failing test: malformed filter expression caught before main run.
- [ ] **W2.E.3.b** — Implement: spawn ephemeral sandbox with `psteal --validate-filter` first.
- [ ] **W2.E.3.c** — Commit: `feat(tools): plaso filter pre-validator via psteal [W2.E.3]`

### W2.E.4 — `Hayabusa` flag-matrix validator
- [ ] **W2.E.4.a** — Failing test: invalid timeline-flag combinations rejected.
- [ ] **W2.E.4.b** — Implement against the matrix in `src/verdict/playbooks/memory.yml` rules section.
- [ ] **W2.E.4.c** — Commit: `feat(tools): hayabusa flag-matrix validator [W2.E.4]`

### W2.E.5 — Sanitization scanner for prompt injection in tool stdout
- [ ] **W2.E.5.a** — Failing test `tests/tools/test_sanitization.py::test_detects_ignore_previous_instructions`. Plus standard jailbreak suffixes.
- [ ] **W2.E.5.b** — Implement `src/verdict/tools/sanitization.py`. Patterns include `IGNORE PREVIOUS`, `SYSTEM:`, `</tool_call>`, `[INST]`, `### Instruction`. Detected → `ToolOutput.sanitization_flags` populated; surface to planner.
- [ ] **W2.E.5.c** — Commit: `feat(tools): sanitization scanner for prompt-injection patterns [W2.E.5]`

## Phase W2.F — Plaso/Hayabusa split (Beaver, ~0.5 day)

### W2.F.1 — `hayabusa_csv_timeline` (extract phase)
- [ ] **W2.F.1.a** — Failing test for csv-timeline extraction.
- [ ] **W2.F.1.b** — Implement.
- [ ] **W2.F.1.c** — Commit: `feat(tools): hayabusa_csv_timeline extract phase [W2.F.1]`

### W2.F.2 — `hayabusa_filter` (filter phase)
- [ ] **W2.F.2.a** — Failing test for sigma_level + time_range filtering.
- [ ] **W2.F.2.b** — Implement.
- [ ] **W2.F.2.c** — Commit: `feat(tools): hayabusa_filter [W2.F.2]`

### W2.F.3 — `plaso_extract`
- [ ] **W2.F.3.a** — Failing test for `.plaso` storage path return.
- [ ] **W2.F.3.b** — Implement.
- [ ] **W2.F.3.c** — Commit: `feat(tools): plaso_extract phase [W2.F.3]`

### W2.F.4 — `psort_filter`
- [ ] **W2.F.4.a** — Failing test for time_range + filter_expr.
- [ ] **W2.F.4.b** — Implement.
- [ ] **W2.F.4.c** — Commit: `feat(tools): psort_filter phase [W2.F.4]`

## Phase W2.G — Observability instrumentation (Tim + Haley, ~1 day)

### W2.G.1 — Ledger writer hardened
- [ ] **W2.G.1.a** — Failing test `tests/ledger/test_writer.py::test_write_fsync_verify_readback`. Plus `test_invalid_hmac_refuses_load`.
- [ ] **W2.G.1.b** — Implement.
- [ ] **W2.G.1.c** — Commit: `feat(ledger): writer hardened with verify-readback [W2.G.1]`

### W2.G.2 — OpenLLMetry instrumentation across FastMCP + tool wrappers (Tim)
- [ ] **W2.G.2.a** — Failing test `tests/observability/test_otel_setup.py::test_one_span_per_tool_call`. Plus `test_streaming_chunks_aggregated_to_one_span`.
- [ ] **W2.G.2.b** — Configure `traceloop_telemetry.sdk.streaming_aggregation=True`; wire callbacks; verify.
- [ ] **W2.G.2.c** — Commit: `feat(observability): OpenLLMetry instrumentation [W2.G.2]`

### W2.G.3 — SGLang client uses OpenAI-compat path (Haley)
- [ ] **W2.G.3.a** — Failing integration test asserts `prompt_tokens > 0` on a known SGLang call. Plus assertion that wrapper uses `openai.OpenAI(base_url=sglang_url)` not raw `httpx`.
- [ ] **W2.G.3.b** — Implement / verify.
- [ ] **W2.G.3.c** — Commit: `feat(inference): SGLang via OpenAI-compat client for OTel [W2.G.3]`

## Week 2 — acceptance gates

| Gate | Verification |
|---|---|
| All 23 tool wrappers callable via gateway | `pytest tests/tools/ -v` green |
| LangGraph compiles in all three modes | `pytest tests/graph/test_topology_compiles.py` green for cloud/airgap/dual |
| `comprehension_gate` + `planner_critique_node` integrated | Inspect AI smoke run shows both nodes in trace |
| `executor_work` is composition of 3 wrappers, three owners | `git blame` shows distinct authors on `deny_rule.py`, `tool_executor.py`, `ledger_emitter.py` |
| Plaso + Hayabusa split into extract+filter | `grep -c "extract" src/verdict/tools/plaso_*.py` returns ≥1 each |
| Args validators reject unknown flags | `pytest tests/tools/test_args_validator.py` green |
| Sanitization flags detected on injection patterns | `pytest tests/tools/test_sanitization.py` green |
| Langfuse spans show real prompt_tokens > 0 | Manual UI check + integration test |
| Fanout race test passes on pinned LangGraph version | `pytest tests/graph/test_fanout_race.py -v` green 100/100 runs |

If RED: drop W2.D.3 (planner CoT capture, push to W3) → drop W2.E.3-4 (plaso/Hayabusa validators, push to W3) → drop W2.F (split, ship as combined tools) → drop W2.D.1-2 (planner_critique, accept the wrong-plan failure mode for v1).

---

# WEEK 3 (May 16 – May 22): Verifier strategies + TSI + Checkpointing

**Theme:** Cross-engine verification; TSI secret injection; durable execution; mode lock; pivot vs replan distinction; unverifiable_finalize.
**Critical-path output:** All three verifier strategies live; SqliteSaver with WAL/synchronous=FULL; kill-9 chaos test green; mode lock enforced; tcpdump proves TSI; trace_id ↔ ledger cross-link.
**Cumulative team-days:** Tim ~5, Beaver ~5, Haley ~1, KP ~2.

## Phase W3.A — Verifier strategy implementations (Beaver, ~2 days)

### W3.A.1 — `AirGapCrossEngine`
- [ ] **W3.A.1.a** — Failing test `tests/verification/test_airgap_cross_engine.py::test_both_must_agree_on_jaccard_080_artifact_set`. Plus `test_disagreement_returns_contested`.
- [ ] **W3.A.1.b** — Implement: Qwen3 plans (or GLM if Qwen unavailable); both Qwen3 + GLM execute in parallel; both must agree on `(artifact_paths, mitre_technique)` with Jaccard ≥0.80.
- [ ] **W3.A.1.c** — Commit: `feat(verification): AirGapCrossEngine [W3.A.1]`

### W3.A.2 — `DualLaneCrossEngine`
- [ ] **W3.A.2.a** — Failing test: cloud agrees with at least one local; locals agree with each other.
- [ ] **W3.A.2.b** — Implement.
- [ ] **W3.A.2.c** — Commit: `feat(verification): DualLaneCrossEngine three-way verification [W3.A.2]`

### W3.A.3 — Universal Self-Consistency full impl (Chen 2023)
- [ ] **W3.A.3.a** — Failing test `tests/verification/test_universal_self_consistency.py::test_judge_picks_most_consistent_rationale_among_n3`. Assertion: given three Findings with rationale strings differing in structure but agreeing in substance on two of three, `UniversalSelfConsistency.judge(findings).selected_index in {0, 1}` (the two-of-three majority) and `result.status == VerdictStatus.CONTESTED` is NOT returned (USC is the judge of last resort before CONTESTED).
- [ ] **W3.A.3.b** — Extend the W1.C.3 baseline into the full Chen 2023 judge implementation.
- [ ] **W3.A.3.c** — Commit: `feat(verification): Universal Self-Consistency judge [W3.A.3]`

## Phase W3.B — TSI enrichment (Tim, ~1.5 days)

### W3.B.1 — TSI provider Pattern 2
- [ ] **W3.B.1.a** — Failing test `tests/sandboxes/test_tsi_provider.py::test_credentials_never_enter_microvm`. Use tcpdump capture comparison: bearer header on egress to `opencti.local:8080`, NOT inside microvm.
- [ ] **W3.B.1.b** — Implement `src/verdict/sandboxes/tsi_provider.py` per v4.5 lines 482–489.
- [ ] **W3.B.1.c** — Commit: `feat(sandbox): TSI Pattern 2 with credential injection [W3.B.1]`

### W3.B.2 — TSI demo prep (Tim's W4.3 carryover)
- [ ] **W3.B.2.a** — Set up tcpdump filters on host + inside microvm. Produce reproducible side-by-side recording.
- [ ] **W3.B.2.b** — Document in `docs/RELEASE.md` (see W6.A.1).
- [ ] **W3.B.2.c** — Commit: `chore(demo): TSI tcpdump demonstration assets [W3.B.2]`

### W3.B.3 — Ledger redaction pass
- [ ] **W3.B.3.a** — Failing test: `test_redacts_authorization_header_before_hash`. Plus `auth_user`, `api_key`.
- [ ] **W3.B.3.b** — Implement `src/verdict/ledger/redaction.py`. Strip + record in `payload_redactions` field.
- [ ] **W3.B.3.c** — Commit: `feat(ledger): redact auth fields before hash + write [W3.B.3]`

## Phase W3.C — Mode lock (Beaver, ~0.5 day)

### W3.C.1 — Mode-lock enforcement at `case_init`
- [ ] **W3.C.1.a** — Failing test `tests/runtime/test_mode_lock.py::test_resume_with_different_mode_refuses`. Plus `test_mode_at_case_init_immutable`.
- [ ] **W3.C.1.b** — Implement: write `mode_at_case_init` to ledger; refuse to advance if resume detects mode mismatch with current autodetect.
- [ ] **W3.C.1.c** — Commit: `feat(runtime): mode lock at case_init enforced on resume [W3.C.1]`

### W3.C.2 — `verdict reverify` command
- [ ] **W3.C.2.a** — Failing test: `verdict reverify <case_id> --mode dual` produces parallel verdict chain without mutating original.
- [ ] **W3.C.2.b** — Implement in `src/verdict/cli/reverify.py`. Fork a new parallel chain with the original `EvidenceManifest`, a new `chain_id`, the requested `mode_at_case_init`, and fresh mode-appropriate planner/executor/quorum ledger entries. Never mutate the original chain.
- [ ] **W3.C.2.c** — Commit: `feat(cli): verdict reverify produces parallel verdict chain [W3.C.2]`

## Phase W3.D — Pivot + replan + unverifiable_finalize (Beaver, ~1 day)

### W3.D.1 — `pivot_node` (cheap follow-up)
- [ ] **W3.D.1.a** — Failing test `tests/graph/test_pivot_node.py::test_adds_one_hypothesis_within_pivot_max_15`. Plus `test_pivot_does_not_re_enter_planner`.
- [ ] **W3.D.1.b** — Implement. Bounded `pivot_max=15` in `InvestigationPlan.pivot_budget`.
- [ ] **W3.D.1.c** — Commit: `feat(graph): pivot_node distinct from replan_node (max=15) [W3.D.1]`

### W3.D.2 — `replan_max=3` explicit budget on `InvestigationPlan`
- [ ] **W3.D.2.a** — Failing test: `replan_budget` field defaults to 3.
- [ ] **W3.D.2.b** — Implement.
- [ ] **W3.D.2.c** — Commit: `feat(schema): InvestigationPlan.replan_budget=3 explicit [W3.D.2]`

### W3.D.3 — `unverifiable_finalize_node`
- [ ] **W3.D.3.a** — Failing test `tests/graph/test_unverifiable_finalize.py::test_writes_unverifiable_finding_at_replan_iteration_4`. Plus `test_writes_exhausted_replan_ledger_event`, `test_calls_interrupt`, and `test_resume_does_not_duplicate_exhausted_replan_ledger_entry`.
- [ ] **W3.D.3.b** — Implement. Use deterministic idempotency key `case_id + chain_id + hypothesis_id + replan_iteration + "exhausted_replan"`; before writing the ledger entry, check whether that key already exists and skip the write on resume. No non-idempotent side effects may occur before `interrupt()`.
- [ ] **W3.D.3.c** — Commit: `feat(graph): unverifiable_finalize_node + exhausted_replan event [W3.D.3]`

### W3.D.4 — Wire `interrupt()` properly
- [ ] **W3.D.4.a** — Failing test: analyst can `update_state` and resume after interrupt.
- [ ] **W3.D.4.b** — Implement `src/verdict/graph/interrupt.py` with helpers for resume-from-interrupt path.
- [ ] **W3.D.4.c** — Commit: `feat(graph): interrupt() helpers for HITL resume [W3.D.4]`

## Phase W3.E — Checkpointing (Beaver, ~1 day)

### W3.E.1 — `SqliteSaver` with WAL + synchronous=FULL
- [ ] **W3.E.1.a** — Failing test `tests/graph/test_checkpoint.py::test_pragma_journal_mode_wal`. Plus `test_pragma_synchronous_full`.
- [ ] **W3.E.1.b** — Implement `src/verdict/graph/checkpoint.py` with `PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;`.
- [ ] **W3.E.1.c** — Commit: `feat(graph): SqliteSaver with WAL + synchronous=FULL [W3.E.1]`

### W3.E.2 — `thread_id = case_id` everywhere
- [ ] **W3.E.2.a** — Failing test: gateway invocation passes `config={"configurable": {"thread_id": case_id}}`.
- [ ] **W3.E.2.b** — Implement.
- [ ] **W3.E.2.c** — Commit: `feat(graph): thread_id = case_id wiring [W3.E.2]`

### W3.E.3 — `verdict resume <case_id>` command
- [ ] **W3.E.3.a** — Failing test: kill -9 + restart picks up from last super-step.
- [ ] **W3.E.3.b** — Implement.
- [ ] **W3.E.3.c** — Commit: `feat(cli): verdict resume re-attaches LangGraph thread [W3.E.3]`

### W3.E.4 — `docs/RELEASE.md` checkpointing section
- [ ] **W3.E.4** — Author. Document single-writer + reducer pattern; per-case sqlite file rotation; WAL/fsync rationale. Commit: `docs(release): document checkpointing [W3.E.4]`

### W3.E.5 — `trace_id` ↔ ledger cross-link
- [ ] **W3.E.5.a** — Failing test `tests/observability/test_trace_link.py::test_ledger_entry_has_langfuse_trace_id`. Plus `test_langfuse_span_has_ledger_entry_id_attribute`.
- [ ] **W3.E.5.b** — Implement `src/verdict/observability/trace_link.py` — bi-directional linking.
- [ ] **W3.E.5.c** — Commit: `feat(observability): trace_id ↔ ledger bidirectional cross-link [W3.E.5]`

### W3.E.6 — Kill-9 chaos test
- [ ] **W3.E.6.a** — Failing test `tests/chaos/test_kill_9_resume.py::test_100_cases_zero_super_step_loss`. 100 cases, kill -9 between super-steps, assert zero loss.
- [ ] **W3.E.6.b** — Implement chaos harness.
- [ ] **W3.E.6.c** — Commit: `test(chaos): kill -9 100-case zero-loss assertion [W3.E.6]`

## Phase W3.F — `/health` endpoint + healthcheck loop (Tim, ~0.5 day)

### W3.F.1 — `/health` endpoint
- [ ] **W3.F.1.a** — Failing test: returns `{mode, components: {langfuse, sglang, microsandbox, ledger}, last_healthcheck_utc}`.
- [ ] **W3.F.1.b** — Implement `src/verdict/cli/health.py`.
- [ ] **W3.F.1.c** — Commit: `feat(cli): /health endpoint [W3.F.1]`

### W3.F.2 — Continuous healthcheck loop (30s interval)
- [ ] **W3.F.2.a** — Failing test: degradation writes ledger entry.
- [ ] **W3.F.2.b** — Implement.
- [ ] **W3.F.2.c** — Commit: `feat(runtime): continuous healthcheck loop with degradation logging [W3.F.2]`

## Phase W3.G — Cross-cutting docs (Tim, ~0.5 day)

### W3.G.1 — Case isolation notes
- [ ] **W3.G.1** — Document SGLang RadixAttention prefix-cache vs case-data in the retained architecture/release docs. Audit assertion: case_id in user message, not system prompt. Commit: `docs(architecture): document case isolation boundaries [W3.G.1]`

## Week 3 — acceptance gates

| Gate | Verification |
|---|---|
| All three verifier strategies live | `pytest tests/verification/ -v` green |
| TSI tcpdump proves credential isolation | Manual recording in `docs/demo-assets/` |
| Mode lock refuses cross-mode resume | `pytest tests/runtime/test_mode_lock.py` green |
| Pivot + replan distinct, both bounded | `pytest tests/graph/test_pivot_node.py` + `test_replan_budget.py` green |
| `unverifiable_finalize_node` fires at replan iteration 4 | `pytest tests/graph/test_unverifiable_finalize.py` green |
| SqliteSaver WAL + fsync set | `pragma_check.sh` returns ok |
| Kill-9 chaos: 100 cases, 0 loss | `pytest tests/chaos/ -v` green |
| trace_id ↔ ledger cross-link visible in Langfuse UI | Manual UI check |
| `/health` endpoint returns all components | `curl localhost:8080/health \| jq` |

If RED: drop W3.E.6 (chaos test, ship without quantified guarantee) → drop W3.B.2 (TSI demo recording, do later) → drop W3.F.2 (continuous healthcheck loop).

---

# WEEK 4 (May 23 – May 29): Skills, hooks, evals

**Theme:** 6 agentskills.io skills with `required_tools` declarations. Inspect AI regression suite per-mode. 5 scorers. 50 ground-truth indicators. Demo case engineering.
**Critical-path output:** Three CI per-mode scorers green; demo Case 001 produces a clean Qwen3-vs-GLM disagreement; sub-technique mapping enforced; Qwen3-vs-GLM disagreement correlation measured.
**Cumulative team-days:** Tim ~3, Beaver ~2, Haley ~0.5, KP ~5.

## Phase W4.A — agentskills.io skills (KP, ~2 days)

### W4.A.1 — `windows-triage/SKILL.md` with `required_tools` frontmatter
- [ ] **W4.A.1.a** — Failing test `tests/skills/test_required_tools_filter.py::test_windows_triage_loads_only_required`. Assert gateway filters tool list when skill activates: only vol3.{pslist,psscan,pstree,cmdline,malfind,svcscan} + MFTECmd + RECmd + PECmd + Hayabusa available.
- [ ] **W4.A.1.b** — Author SKILL.md frontmatter per Appendix B.2.
- [ ] **W4.A.1.c** — Commit: `feat(skills): windows-triage with required_tools declaration [W4.A.1]`

### W4.A.2 — `windows-triage/KNOWLEDGE.md` with LOLBin catalog
- [ ] **W4.A.2.a** — Failing test: `KNOWLEDGE.md` includes ≥6 LOLBins (rundll32, regsvr32, mshta, wmic, certutil, bitsadmin) with cmdline-shape patterns.
- [ ] **W4.A.2.b** — Author per Appendix B.3.
- [ ] **W4.A.2.c** — Commit: `feat(skills): windows-triage/KNOWLEDGE.md with LOLBin catalog [W4.A.2]`

### W4.A.3 — `linux-triage/`, `memory-forensics/`, `network-pcap/`, `malware-static/`, `report-writing/`
- [ ] **W4.A.3.a** — Failing tests for each.
- [ ] **W4.A.3.b** — Author each.
- [ ] **W4.A.3.c** — Commits one per skill.

### W4.A.4 — Forensic-discipline SessionStart hook
- [ ] **W4.A.4.a** — Failing test: hook fires; injects examiner_caveats.md + epistemic vocabulary into session prompt.
- [ ] **W4.A.4.b** — Implement hook config in `.claude/settings.json` + corresponding agentskills hook for non-Claude engines.
- [ ] **W4.A.4.c** — Commit: `feat(hooks): forensic-discipline SessionStart hook [W4.A.4]`

## Phase W4.B — `lolbins.yml` knowledge file (KP, ~0.5 day)

### W4.B.1 — `src/verdict/knowledge/lolbins.yml`
- [ ] **W4.B.1.a** — Failing test: ≥6 LOLBins with shape patterns + MITRE technique mapping (T1218 sub-techniques).
- [ ] **W4.B.1.b** — Author per Appendix C.5.
- [ ] **W4.B.1.c** — Commit: `feat(knowledge): lolbins.yml with cmdline shapes + T1218 mapping [W4.B.1]`

### W4.B.2 — `cmdline_executor` LOLBin matching
- [ ] **W4.B.2.a** — Failing test: vol3.cmdline output containing `regsvr32 /s /u /n /i:http://...` triggers `T1218.010` Hypothesis.
- [ ] **W4.B.2.b** — Implement matcher.
- [ ] **W4.B.2.c** — Commit: `feat(planning): cmdline LOLBin matcher emits T1218 sub-techniques [W4.B.2]`

## Phase W4.C — Ground truth (KP, ~1.5 days)

### W4.C.1 — Case 001: lol-bins compromise (17 indicators)
- [ ] **W4.C.1.a** — Engineer Hetzner-range scenario with regsvr32+http persistence. 17 indicators including 5 red herrings.
- [ ] **W4.C.1.b** — Run draft against both Qwen3 and GLM. Tune until disagreement on ≥1 finding (one model hallucinates a registry path or process name; other catches it). **Hard gate:** if Case 001 doesn't produce reproducible disagreement by end of week 4, escalate.
- [ ] **W4.C.1.c** — Commit ground-truth fixture: `feat(eval): case_001 lolbins (17 indicators, engineered disagreement) [W4.C.1]`

### W4.C.2 — Case 002: credential theft (17 indicators)
- [ ] **W4.C.2** — Same shape. Mimikatz dumps + Sysmon detection chain. Commit: `feat(eval): case_002 credtheft [W4.C.2]`

### W4.C.3 — Case 003: ransomware (Honeynet derivative, 16 indicators)
- [ ] **W4.C.3** — Honeynet image with engineered persistence + LOLBin staging. Commit: `feat(eval): case_003 ransomware [W4.C.3]`

## Phase W4.D — Inspect AI per-mode tasks (KP + Tim, ~1 day)

### W4.D.1 — `verdict_eval_cloud`
- [ ] **W4.D.1.a** — Failing test: task runs end-to-end against Case 001 in cloud mode; reports per-finding precision/recall.
- [ ] **W4.D.1.b** — Implement `inspect_ai/tasks/verdict_eval_cloud.py`.
- [ ] **W4.D.1.c** — Commit: `feat(eval): verdict_eval_cloud task [W4.D.1]`

### W4.D.2 — `verdict_eval_airgap`
- [ ] **W4.D.2** — Same. Commit: `feat(eval): verdict_eval_airgap [W4.D.2]`

### W4.D.3 — `verdict_eval_dual`
- [ ] **W4.D.3** — Same. Commit: `feat(eval): verdict_eval_dual [W4.D.3]`

### W4.D.4 — Three CI jobs (one per mode) in `.github/workflows/inspect-ai-evals.yml`
- [ ] **W4.D.4.a** — Failing CI: workflow fails if any mode hallucination_rate > 0.05 or agreement < 0.85. Earlier W1-W3 jobs may run an advisory ≤10% trend report, but W4+ release gates are hard ≤5%.
- [ ] **W4.D.4.b** — Implement.
- [ ] **W4.D.4.c** — Commit: `chore(ci): per-mode Inspect AI eval gates [W4.D.4]`

## Phase W4.E — Five Inspect AI scorers (KP, ~1 day)

### W4.E.1 — `step_efficiency` (deterministic v1)
- [ ] **W4.E.1.a** — Failing test: count tool-calls per finding > 2× median = inefficient.
- [ ] **W4.E.1.b** — Implement `inspect_ai/scorers/step_efficiency.py` reading `os.environ["LANGFUSE_TRACE_ID"]`.
- [ ] **W4.E.1.c** — Commit: `feat(eval): step_efficiency scorer [W4.E.1]`

### W4.E.2 — `findings_precision`
- [ ] **W4.E.2** — Standard precision against ground-truth. Commit: `feat(eval): findings_precision [W4.E.2]`

### W4.E.3 — `findings_recall`
- [ ] **W4.E.3** — Standard recall. Commit: `feat(eval): findings_recall [W4.E.3]`

### W4.E.4 — `mitre_subtechnique_precision`
- [ ] **W4.E.4.a** — Failing test: scorer fails if planner emits parent technique (`T1055`) when sub-technique was determinable (`T1055.012`).
- [ ] **W4.E.4.b** — Implement.
- [ ] **W4.E.4.c** — Commit: `feat(eval): mitre_subtechnique_precision scorer [W4.E.4]`

### W4.E.5 — `negative_hypothesis_quality`
- [ ] **W4.E.5.a** — Failing test: deny-list patterns + missing mitre_technique + empty artifact_families = score < 0.5.
- [ ] **W4.E.5.b** — Implement.
- [ ] **W4.E.5.c** — Commit: `feat(eval): negative_hypothesis_quality scorer [W4.E.5]`

## Phase W4.F — Prompt engineering (Beaver + KP, ~1 day)

### W4.F.1 — Negative-hypothesis few-shot examples
- [ ] **W4.F.1.a** — Author `src/verdict/planning/prompts/negative_hypothesis_examples.md` with 5 high-quality few-shots demonstrating: T1547 ruling out T1055; T1543.003 ruling out T1543.001; etc.
- [ ] **W4.F.1.b** — Wire into planner system prompt.
- [ ] **W4.F.1.c** — Commit: `feat(prompts): 5 negative-hypothesis few-shot examples [W4.F.1]`

### W4.F.2 — Adversarial-reasoning prompt
- [ ] **W4.F.2.a** — Author `src/verdict/planning/prompts/adversarial_reasoning.md`. Inject "if I were the attacker, where would I hide?" — Scheduled Tasks `\Microsoft\Windows\` namespace, WMI event subscriptions, IFEO debugger keys (per project MEMORY.md persistence top-5).
- [ ] **W4.F.2.b** — Wire into planner system prompt.
- [ ] **W4.F.2.c** — Commit: `feat(prompts): adversarial-reasoning planner injection [W4.F.2]`

### W4.F.3 — Prompt budget CI assertion
- [ ] **W4.F.3.a** — Failing test: rendered planner ≤30K tokens; executor ≤20K; critic ≤15K.
- [ ] **W4.F.3.b** — Implement assertion in `tests/planning/test_prompt_budget.py`.
- [ ] **W4.F.3.c** — Commit: `test(planning): prompt budget CI assertion [W4.F.3]`

## Phase W4.G — Disagreement-correlation measurement (KP, ~0.5 day)

### W4.G.1 — Measure Qwen3-vs-GLM disagreement correlation across 50 findings
- [ ] **W4.G.1.a** — Author analysis script `inspect_ai/scripts/measure_disagreement_correlation.py`. Run both models against the 50-indicator ground truth; compute correlation matrix on disagreements.
- [ ] **W4.G.1.b** — Output number to `docs/RELEASE.md`.
- [ ] **W4.G.1.c** — Commit: `feat(eval): Qwen3-vs-GLM disagreement-correlation measurement [W4.G.1]`

## Week 4 — acceptance gates

| Gate | Verification |
|---|---|
| All 6 skills load with required_tools | `pytest tests/skills/ -v` green |
| 50 ground-truth indicators across 3 cases | `ls inspect_ai/ground_truth/case_00{1,2,3}/` |
| Case 001 produces engineered Qwen3-vs-GLM disagreement | Manual verification recorded in `docs/demo-assets/case_001.md` |
| Three per-mode Inspect AI tasks green in CI | `.github/workflows/inspect-ai-evals.yml` runs green |
| Hallucination rate ≤ 5% in all three modes | `inspect view <run>` + scorer report |
| Agreement ≥ 0.85 in all three modes | Same |
| MITRE sub-technique precision measurable + reported | `cat docs/RELEASE.md` |
| Disagreement correlation number in accuracy report | `grep -c "disagreement_correlation" docs/RELEASE.md` ≥ 1 |
| Prompt budget CI assertion enforces ≤30K planner | `pytest tests/planning/test_prompt_budget.py -v` green |

If RED: drop W4.B (LOLBin catalog → push to W5) → drop W4.F.2 (adversarial reasoning prompt) → cut Case 003 → freeze tool count + spend remainder on prompt refinement.

---

# WEEK 5 (May 30 – Jun 5): Mode autodetect + adapters + polish

**Theme:** Mode autodetect logic; OpenCTI/Velociraptor/REMnux adapters; demo flow; one Langfuse dashboard; HMAC approval; scope statement; doctor command. Begin demo footage shoots so by Friday Jun 5 you have rough cut.
**Critical-path output:** Mode autodetect + override; demo flow rehearsed in all 3 modes; rough demo cut.
**Cumulative team-days:** Tim ~2.5, Beaver ~1, Haley ~0.5, KP ~1.5.

## Phase W5.A — Mode autodetect (Tim + Beaver, ~1 day)

### W5.A.1 — `detect_mode()` impl
- [ ] **W5.A.1.a** — Failing test `tests/runtime/test_mode_detect.py::test_detects_dual_when_both_available`. Plus 3 other paths (cloud-only, airgap-only, neither).
- [ ] **W5.A.1.b** — Implement per v4.5 lines 30–43.
- [ ] **W5.A.1.c** — Commit: `feat(runtime): detect_mode() autodetect [W5.A.1]`

### W5.A.2 — `--mode` override flag
- [ ] **W5.A.2.a** — Failing test: `--mode dual` overrides autodetect even when only cloud reachable.
- [ ] **W5.A.2.b** — Implement.
- [ ] **W5.A.2.c** — Commit: `feat(cli): --mode override flag [W5.A.2]`

### W5.A.3 — Per-mode startup banner
- [ ] **W5.A.3.a** — Failing test: gateway startup logs `Mode: AIRGAP (autodetected)` or `Mode: DUAL (--mode override)`.
- [ ] **W5.A.3.b** — Implement.
- [ ] **W5.A.3.c** — Commit: `feat(cli): startup banner with mode + source [W5.A.3]`

### W5.A.4 — `verdict doctor` pre-flight
- [ ] **W5.A.4.a** — Failing test: reports each component status (Anthropic API, SGLang, Microsandbox, Langfuse, ledger key).
- [ ] **W5.A.4.b** — Implement.
- [ ] **W5.A.4.c** — Commit: `feat(cli): verdict doctor pre-flight [W5.A.4]`

## Phase W5.B — Adapters (Tim, ~1 day)

### W5.B.1 — OpenCTI MCP integration
- [ ] **W5.B.1.a** — Failing integration test `tests/sandboxes/test_malware_vm_tsi.py::test_opencti_enrichment_via_tsi_keeps_key_out_of_vm`. Assertions: `tcpdump_capture(microvm_iface).bearer_count == 0` AND `tcpdump_capture(host_egress_to_opencti).bearer_count == 1` AND the resulting `Finding.enrichment` dict contains the OpenCTI threat-actor metadata.
- [ ] **W5.B.1.b** — Implement `src/verdict/adapters/opencti_mcp.py`.
- [ ] **W5.B.1.c** — Commit: `feat(adapters): OpenCTI MCP via TSI [W5.B.1]`

### W5.B.2 — Velociraptor MCP via socfortress server
- [ ] **W5.B.2.a** — Failing test: live-endpoint mode fetches Velociraptor artifacts.
- [ ] **W5.B.2.b** — Implement out-of-band callable adapter.
- [ ] **W5.B.2.c** — Commit: `feat(adapters): Velociraptor MCP [W5.B.2]`

### W5.B.3 — REMnux MCP (network-call only — GPL-3.0)
- [ ] **W5.B.3.a** — Failing test: never vendored; network-call works.
- [ ] **W5.B.3.b** — Implement.
- [ ] **W5.B.3.c** — Commit: `feat(adapters): REMnux MCP network-callable adapter [W5.B.3]`

## Phase W5.C — Optional adapters (Tim if scope allows, ~0.5 day)

### W5.C.1 — GhidrAssistMCP for RE workflows
- [ ] **W5.C.1** — Optional. Drop if scope tight.

### W5.C.2 — Atropos trajectory export
- [ ] **W5.C.2.a** — Failing test: export from microsandbox session logs to Atropos format.
- [ ] **W5.C.2.b** — Implement.
- [ ] **W5.C.2.c** — Commit: `feat(adapters): Atropos trajectory exporter [W5.C.2]`

### W5.C.3 — Hermes Telegram pager
- [ ] **W5.C.3** — Optional. Drop if scope tight. Telegram bot fires on `interrupt()` from `unverifiable_finalize`.

## Phase W5.D — Polish docs (Tim, ~0.5 day)

### W5.D.1 — `docs/RELEASE.md` scope section
- [ ] **W5.D.1** — Author. v1 = Windows DFIR; macOS / Linux / Win11-specific (SRUM/ETW/Cortana) / ESXi = v2 roadmap. Network forensics (FOR572) = v2. Examiner workflow integrations (Axiom XML, EnCase EWF, FTK CSV) = v2. Commit: `docs: SCOPE.md [W5.D.1]`

### W5.D.2 — Update `docs/ARCHITECTURE.md` with all v4.4-v4.6 additions
- [ ] **W5.D.2** — Bring it current. Reference v4.5 + v4.6 + this plan.

## Phase W5.E — Demo prep (Beaver + Tim, ~1 day)

### W5.E.1 — `docs/RELEASE.md` accuracy final draft
- [ ] **W5.E.1.a** — Tables: per-mode hallucination, agreement, FP rates, step_efficiency by tool, contested-resolution rate, MITRE sub-technique precision, negative-hypothesis quality, Qwen3-vs-GLM disagreement correlation.
- [ ] **W5.E.1.b** — Two charts: Step Efficiency by tool, Contested-Finding Resolution per-mode.
- [ ] **W5.E.1.c** — Commit: `docs(release): add accuracy report [W5.E.1]`

### W5.E.2 — Time-travel demo flow
- [ ] **W5.E.2.a** — Beaver builds demo flow using `get_state_history()` to walk through a contested verdict. Recorded as a separate ~30s clip.
- [ ] **W5.E.2.b** — Commit: `chore(demo): time-travel demo clip [W5.E.2]`

### W5.E.3 — One Langfuse dashboard for the demo
- [ ] **W5.E.3.a** — Author `Contested Findings` + `Step Efficiency by Tool` panels in Langfuse.
- [ ] **W5.E.3.b** — Export dashboard JSON to `docs/demo-assets/langfuse-dashboard.json`.
- [ ] **W5.E.3.c** — Commit: `feat(observability): Langfuse demo dashboard [W5.E.3]`

### W5.E.4 — HMAC-signed approval flow
- [ ] **W5.E.4.a** — Failing test: `verdict approve <finding_id>` produces ledger entry with HMAC sig over Finding+approver+timestamp.
- [ ] **W5.E.4.b** — Implement.
- [ ] **W5.E.4.c** — Commit: `feat(cli): verdict approve with HMAC signing [W5.E.4]`

## Phase W5.F — Rough demo cut (Tim records, all teammates review, ~0.5 day)

### W5.F.1 — Record rough cut against rehearsed flow
- [ ] **W5.F.1.a** — Two-pane recording (terminal + Langfuse) of all 3 modes against Case 003 ransomware. ~5 min total.
- [ ] **W5.F.1.b** — Review: does it land on each of the 6 official Devpost judging criteria (Autonomous Execution Quality, IR Accuracy, Breadth and Depth of Analysis, Constraint Implementation, Audit Trail Quality, Usability and Documentation)? Cross-reference `DEVPOST_COMPLIANCE.md` Part 3.
- [ ] **W5.F.1.c** — Commit: `chore(demo): rough cut May 30 [W5.F.1]`

## Week 5 — acceptance gates

| Gate | Verification |
|---|---|
| Mode autodetect works in all 4 paths | `pytest tests/runtime/test_mode_detect.py` green |
| `--mode` override works | `pytest tests/cli/test_mode_override.py` green |
| `verdict doctor` returns ok on dev rig | `verdict doctor \| tail -1` says `all components OK` |
| OpenCTI + Velociraptor + REMnux adapters callable | `pytest tests/adapters/ -v` green |
| `docs/RELEASE.md` shipped with all required accuracy tables | manual review |
| Langfuse demo dashboard JSON committed | `ls docs/demo-assets/langfuse-dashboard.json` |
| Rough demo cut exists | `ls docs/demo-assets/rough-cut.mp4` |
| Time-travel clip exists | `ls docs/demo-assets/time-travel.mp4` |
| HMAC approval emits valid ledger entry | `pytest tests/cli/test_approve.py` green |

If RED: drop W5.C optional adapters first → drop W5.B.3 (REMnux) → drop W5.E.2 (time-travel clip; defer to v2).

---

# WEEK 6 (Jun 6 – Jun 14): Demo + docs + submission

**Theme:** Final demo cut. Submission docs (README, ARCHITECTURE.md, BUILD.md, etc.). Devpost upload by Jun 14 EOD (24h before official deadline).
**Critical-path output:** Final demo video; full doc suite; Devpost submission live with the v-submit tag.
**Cumulative team-days:** Tim ~2.5, Beaver ~1.5, Haley ~0.5, KP ~1.

## Phase W6.A — Demo final (Tim + Beaver, ~2 days)

### W6.A.1 — `docs/RELEASE.md` demo sequence section
- [ ] **W6.A.1** — Author the 5-min sequence with timing per beat (cold open 30s, cloud 60s, airgap 90s with hero beats, dual 60s, recap 60s). Beat list per v4.5 lines 855–865 plus v4.4 hero beats (DKOM divergence, Hunt Evil masquerade, Amcache caveat acknowledgment, pivot vs replan, planner_critique CoVe). Commit: `docs(release): add demo sequence [W6.A.1]`

### W6.A.2 — Final cut
- [ ] **W6.A.2.a** — Re-record against rehearsed flow. Each hero beat must land cleanly.
- [ ] **W6.A.2.b** — Caption file with timestamps.
- [ ] **W6.A.2.c** — Commit: `chore(demo): final cut Jun 12 [W6.A.2]`

## Phase W6.B — Judge checklist + dry runs (Beaver, ~0.5 day)

### W6.B.1 — `docs/RELEASE.md` judge checklist section
- [ ] **W6.B.1** — 15-item checklist from v4.4 (image hash verify; SANS-canonical first move; pslist+psscan divergence; ≥2 artifact classes per execution claim; Amcache caveat acknowledged; UTC `Z` timestamps; pivot in action; epistemic vocabulary; sub-techniques; Hunt Evil masquerade; never asserts attribution; ledger records environment metadata; <20 min end-to-end; explicit UNVERIFIABLE; planner_critique fires visibly). Commit: `docs(release): add SANS judge checklist [W6.B.1]`

### W6.B.2 — Three dry runs
- [ ] **W6.B.2** — Dry run final demo against checklist three times. Iterate until all 15 tick green. Commit: `chore(demo): three dry runs against judge checklist [W6.B.2]`

## Phase W6.C — Submission docs (Tim + KP, ~2 days)

### W6.C.1 — `README.md`
- [ ] **W6.C.1** — Front page: one-paragraph problem statement; one-paragraph architecture; demo video link; install instructions (`scripts/install.sh`); 3-mode quick reference; license badge; contributing link. Commit: `docs: README.md [W6.C.1]`

### W6.C.2 — `docs/ARCHITECTURE.md`
- [ ] **W6.C.2** — Full system diagram + node-by-node walkthrough. Reference v4.5 + v4.6 + this plan as authorities. Commit: `docs: ARCHITECTURE.md [W6.C.2]`

### W6.C.3 — `docs/RELEASE.md` build section
- [ ] **W6.C.3** — Exact build steps from a fresh SIFT VM. Verified by reproducing on a second VM. Commit: `docs(release): add fresh VM build steps [W6.C.3]`

### W6.C.4 — `CONTRIBUTING.md` + `LICENSE` (MIT)
- [ ] **W6.C.4** — Standard MIT + project-specific contributing notes. Commit: `docs: CONTRIBUTING.md + LICENSE [W6.C.4]`

### W6.C.5 — `docs/RELEASE.md` production audit section
- [ ] **W6.C.5** — The v4 triage doc enumerating what landed in v1 vs deferred to v2. Reference v4.5 §Production-maturity audit. Commit: `docs: PRODUCTION_AUDIT.md [W6.C.5]`

### W6.C.6 — Submission writeup
- [ ] **W6.C.6** — 500-word writeup for Devpost summarizing: problem, architecture, three innovations, accuracy results, demo video. References all 6 official judging criteria explicitly per `DEVPOST_COMPLIANCE.md` Part 3. Commit: `docs: Devpost submission writeup [W6.C.6]`

### W6.C.7 — rendered architecture visual (Devpost-required)
- [ ] **W6.C.7.a** — Author Mermaid or draw.io source covering: Examiner CLI, FastMCP gateway, Mode autodetect, Planner Protocol (CloudPlanner/LocalPlanner), planner_critique_node, comprehension_gate, executor_fanout (4 branches), executor_work split (DenyRuleWrapper → ToolExecutor → LedgerEmitter), pivot_node, quorum_node, replan/unverifiable_finalize, Microsandbox VMs, Evidence Vault (chattr +i, read-only mount), HMAC ledger, Langfuse, SqliteSaver checkpoint, optional out-of-band services.
- [ ] **W6.C.7.b** — Render to SVG + PNG fallback for the final submission package.
- [ ] **W6.C.7.c** — Reference from README + ARCHITECTURE.md + Devpost form.
- [ ] **W6.C.7.d** — Commit: `docs(submission): add rendered architecture visual [W6.C.7]`

### W6.C.8 — `docs/RELEASE.md` evidence dataset section (Devpost-required)
- [ ] **W6.C.8.a** — Author. Sections: (1) Datasets used (NIST CFReDS Hacking Case, Honeynet ransomware, 3 engineered cases). (2) Source attribution per dataset (URL, license, hash). (3) What VERDICT was tested against per case. (4) What VERDICT found per case (with finding_ids referencing accuracy report). (5) Limitations: Windows-only; no live-response; no Win11/macOS/Linux/network.
- [ ] **W6.C.8.b** — Cross-reference from README + ACCURACY_REPORT.md + Devpost form.
- [ ] **W6.C.8.c** — Commit: `docs: EVIDENCE_DATASET.md [W6.C.8]`

### W6.C.9 — Agent Execution Logs export (Devpost-required)
- [ ] **W6.C.9.a** — Failing test `tests/cli/test_export_execution_logs.py::test_includes_agent_to_agent_messages_with_timestamps`. Plus `test_includes_token_usage`. Plus `test_traces_finding_to_tool_call_id`. Plus `test_persistent_loop_iteration_n_field_present`. Run → RED.
- [ ] **W6.C.9.b** — Implement `verdict export <case_id> --format execution-logs` emitting Devpost-compliant JSONL: each line `{ts_utc, event_type, agent_id?, target_agent_id?, tool_name?, tool_call_id?, prompt_tokens?, completion_tokens?, finding_id?, iteration_n?, langfuse_trace_id, langgraph_checkpoint_id}`. Distillation of HMAC ledger + Langfuse trace + planner CoT, packaged for judge consumption (NOT a tar of raw ledger).
- [ ] **W6.C.9.c** — Run against all three demo cases; produce `submission/execution-logs/case_{001,002,003}.jsonl`; commit alongside accuracy report.
- [ ] **W6.C.9.d** — Commit: `feat(cli): export execution-logs format for Devpost compliance [W6.C.9]`

### W6.C.10 — `docs/RELEASE.md` novel contribution section (Devpost-required)
- [ ] **W6.C.10.a** — Author. Sections: (1) Project timeline (started 2026-05-02; substantially new work per Devpost rules §4 New & Existing). (2) What we built (mode-aware verifier, three-layer immutability, encoded forensic discipline, planner_critique CoVe, pivot vs replan distinction, schema-enforced caveat acknowledgment, DKOM/T1014 auto-detection, Hunt Evil masquerade catch, LOLBin matcher, agentskills.io skill bundle, custom Inspect AI scorers). (3) Pre-existing open source enumerated with license + source URL each (SIFT, Volatility 3, Hayabusa, plaso, EZ Tools, Microsandbox, SGLang, vLLM, LangGraph, Langfuse, OpenLLMetry, Inspect AI, Pydantic, Pydantic-AI, FastMCP, NeMo Guardrails, Claude Agent SDK, blake3). (4) What we extended vs replaced.
- [ ] **W6.C.10.b** — Cross-reference from README + Devpost form.
- [ ] **W6.C.10.c** — Commit: `docs: NOVEL_CONTRIBUTION.md [W6.C.10]`

## Phase W6.D — Devpost submission (Tim, ~0.5 day)

### W6.D.0 — GitHub repo public + License badge in About section (Devpost-required)
- [ ] **W6.D.0.a** — Set repo Public visibility on GitHub.
- [ ] **W6.D.0.b** — Verify LICENSE file at repo root is standard MIT text.
- [ ] **W6.D.0.c** — Set repo About section: description, license auto-detected as MIT, topics include `dfir`, `incident-response`, `claude-code`, `sift-workstation`, `mcp`, `agentic`, `forensics`.
- [ ] **W6.D.0.d** — Verify license badge visible at top of repo on a fresh logged-out browser session (Devpost rules §4 require license "detectable and visible at top of the repository page in the About section").
- [ ] **W6.D.0.e** — Commit if any docs reference the repo URL: `chore(release): GitHub repo public + MIT badge in About [W6.D.0]`

### W6.D.1 — `scripts/package-devpost.sh`
- [ ] **W6.D.1.a** — Failing test: produces a valid Devpost zip including source code, README, LICENSE, retained v0 docs, final submission docs/assets, and `submission/execution-logs/case_{001,002,003}.jsonl`. Run → RED.
- [ ] **W6.D.1.b** — Implement.
- [ ] **W6.D.1.c** — Commit: `feat(scripts): package-devpost.sh [W6.D.1]`

### W6.D.2 — Cut `v-submit` tag → fires `devpost-submit.yml` workflow
- [ ] **W6.D.2** — `git tag v-submit && git push origin v-submit`. Commit before tag: `chore(release): cut v-submit for SANS Find Evil! 2026 [W6.D.2]`

### W6.D.3 — Manual Devpost upload Jun 14 EOD
- [ ] **W6.D.3.a** — Run `DEVPOST_COMPLIANCE.md` Part 6 — verify every checklist item is ticked.
- [ ] **W6.D.3.b** — Upload zip + writeup + demo video link. Submit. Confirm receipt email. **Target Jun 14 EOD = ~28h before official deadline of Jun 15 11:45 PM EDT.**
- [ ] **W6.D.3.c** — If Jun 14 21:00 EDT and any compliance box still unchecked: abort, resolve, retry Jun 15 morning.

## Week 6 — acceptance gates

| Gate | Verification |
|---|---|
| Final 5-min demo video | `ls docs/demo-assets/final-cut.mp4` |
| Demo shows ≥1 self-correction sequence (Devpost-required) | Manual review of cut against air-gap hero beat ⓹ |
| Demo is screencast + narration, NOT slides (Devpost-required) | Manual review |
| Three green dry runs against `SANS_JUDGE_CHECKLIST.md` | Beaver's notes |
| All Devpost-required documentation present | Final submission package contains retained v0 docs plus restored submission-only docs/assets |
| README + LICENSE + CONTRIBUTING | `ls README.md LICENSE CONTRIBUTING.md` |
| Repo public + MIT badge in GitHub About section (Devpost-required) | Manual browser check, logged-out |
| Agent execution logs exported per case (Devpost-required) | `ls submission/execution-logs/case_{001,002,003}.jsonl` |
| Devpost zip produced | `ls dist/verdict-devpost-v1.zip` |
| Devpost compliance Part 6 checklist fully ticked | Manual review |
| Devpost upload confirmed | Receipt email |
| `v-submit` tag pushed | `git tag --list 'v-submit'` |

---

## Per-teammate cumulative summary (grep-friendly)

### Tim — ~22 teammate-days

**Week 1 (~5 days):**
- W1.A.1, W1.A.2, W1.A.3, W1.A.5, W1.A.6, W1.A.7, W1.A.8 (infrastructure)
- W1.B.1–W1.B.13 (schema bundle)
- W1.D.1, W1.D.2 (PreToolUse caveat)
- W1.E.1, W1.E.2, W1.E.3 (psscan + tool base)
- W1.G.1, W1.G.2, W1.G.3, W1.G.4, W1.G.6, W1.G.7 (architecture-review docs + ops)

**Week 2 (~5 days):**
- W2.A.1–W2.A.9 (9 vol3 wrappers)
- W2.C.1, W2.C.3 (DenyRuleWrapper + LedgerEmitter)
- W2.E.1, W2.E.2 (args validators framework + vol3)
- W2.E.5 (sanitization scanner)
- W2.G.1, W2.G.2 (ledger writer + OpenLLMetry)

**Week 3 (~5 days):**
- W3.B.1, W3.B.2, W3.B.3 (TSI + redaction)
- W3.E.5 (trace_id ↔ ledger cross-link)
- W3.F.1, W3.F.2 (/health endpoint + healthcheck loop)
- W3.G.1 (case isolation notes)

**Week 4 (~3 days):**
- W4.D.4 (CI gates per mode)
- General CI hardening + flaky-test triage

**Week 5 (~2.5 days):**
- W5.A.1, W5.A.2, W5.A.3, W5.A.4 (mode autodetect + doctor)
- W5.B.1, W5.B.2, W5.B.3 (adapters)
- W5.D.1, W5.D.2 (SCOPE + ARCHITECTURE update)

**Week 6 (~3.5 days):**
- W6.C.1–W6.C.6 (submission docs)
- W6.C.7 (rendered architecture visual — Devpost-required)
- W6.C.8 (EVIDENCE_DATASET.md — Devpost-required, KP collaborates)
- W6.C.9 (Agent execution logs export — Devpost-required)
- W6.C.10 (NOVEL_CONTRIBUTION.md — Devpost-required)
- W6.D.0 (GitHub repo public + License badge — Devpost-required)
- W6.D.1, W6.D.2, W6.D.3 (Devpost packaging + upload)

### Beaver — ~22 teammate-days

**Week 1 (~1.5 days):**
- W1.C.1, W1.C.2, W1.C.3 (seed-fix + verifier strategy protocol)
- W1.G.5 (Planner Protocol + impls — collaborates with Tim)

**Week 2 (~5 days):**
- W2.B.1–W2.B.5 (Plan-then-Execute LangGraph refactor + reducer)
- W2.C.2, W2.C.4 (ToolExecutor + composition)
- W2.D.1, W2.D.2, W2.D.3 (planner_critique + CoT capture)
- W2.E.3, W2.E.4 (plaso + Hayabusa validators)
- W2.F.1–W2.F.4 (plaso/Hayabusa split)

**Week 3 (~5 days):**
- W3.A.1, W3.A.2, W3.A.3 (verifier strategies + USC)
- W3.C.1, W3.C.2 (mode lock + reverify)
- W3.D.1, W3.D.2, W3.D.3, W3.D.4 (pivot + replan + unverifiable_finalize + interrupt)
- W3.E.1, W3.E.2, W3.E.3, W3.E.4, W3.E.6 (SqliteSaver + WAL + chaos)

**Week 4 (~2 days):**
- W4.F.1, W4.F.2 (negative-hypothesis few-shots + adversarial reasoning)
- General prompt-engineering iteration + Inspect AI agent harness debugging

**Week 5 (~1 day):**
- W5.E.2 (time-travel demo)

**Week 6 (~1.5 days):**
- W6.A.1, W6.A.2 (demo sequence + final cut)
- W6.B.1, W6.B.2 (judge checklist + dry runs)

### Haley — ~10 teammate-days

**Week 1 (~2 days):**
- W1.A.4 (SGLang + Qwen3 + GLM serving)

**Week 2 (~1 day):**
- W2.G.3 (SGLang OpenAI-compat client wiring)

**Week 3 (~1 day):**
- Inference reliability monitoring during verifier-strategy load test

**Week 4 (~0.5 day):**
- Inspect AI agent under-load tuning

**Week 5 (~0.5 day):**
- Inference health during demo rehearsal

**Slack:** ~5 days reserved for inference firefighting, parser bug fallback, FP8 stability tuning. **Threshold:** if Qwen3 parse rate drops below 95% in any week, escalate immediately — fall back to GLM as primary local model + downgrade air-gap to single-engine self-consistency.

### KP — ~21 teammate-days

**Week 1 (~5 days):**
- W1.B.3, W1.B.4 (Evidence + ToolOutput schemas — week 1 since they pin tool wrapper contract)
- W1.F.1–W1.F.11 (playbooks + caveats + hunt_evil + executor prompt include)

**Week 2 (~3 days):**
- W2.A.10–W2.A.18 (9 non-vol3 tool wrappers: mmls/fls/fsstat/MFTECmd/RECmd/PECmd/bulk_extractor/exiftool/capa)

**Week 3 (~2 days):**
- Carryover: tool-wrapper finalization + integration tests

**Week 4 (~5 days):**
- W4.A.1–W4.A.4 (6 skills + SessionStart hook)
- W4.B.1, W4.B.2 (LOLBins knowledge + matcher)
- W4.C.1, W4.C.2, W4.C.3 (3 ground-truth cases — 50 indicators)
- W4.E.1–W4.E.5 (5 Inspect AI scorers)
- W4.G.1 (Qwen3-vs-GLM disagreement-correlation measurement)

**Week 5 (~1.5 days):**
- W5.E.1 (ACCURACY_REPORT.md final draft)
- W5.E.4 collaboration (HMAC approval flow integration with Finding schema)

**Week 6 (~1 day):**
- Final accuracy-report polish
- Demo dry-run participation

---

## Risk register + descope thresholds

| Risk | Likelihood | Impact | Detection | Mitigation | Descope path |
|---|---|---|---|---|---|
| Microsandbox blocking bug in week 4+ | M | H | Smoke test fails in CI | bubblewrap+nsjail combo covers ~80% | Drop microVM, use bubblewrap; lose <500ms cold-start brag |
| Langfuse v2 RAM pressure on SIFT | L | M | OOM at startup | Fall back to OTel → Tempo viewer | Document "trace tree visible in OTel native; Langfuse-self-host = v2" |
| SGLang FP8 instability with Qwen3-Thinking | M | H | Tool-call parse rate drops | Switch to FP16 + reduce concurrency | Air-gap → single-engine self-consistency only |
| Claude OAuth policy change pre-Jun 15 | L | M | API auth failures | Three-mode framing degrades to air-gap | Demo only air-gap + dual segments |
| Anthropic ships PreToolUse fix mid-build | L | L | Smoke test flips green | Update README caveat | None needed |
| Case 001 doesn't produce reproducible Qwen3-vs-GLM disagreement by W4 end | M | H | KP escalation | Engineer Case 002 to do so by W5 mid-week | Demo recorded against the scoring case that did disagree |
| L3 sandbox too slow on GHA runners | M | M | CI timeout | L3 nightly only, not per-PR | L3 advisory only |
| Devpost upload fails Jun 14 | L | H | Upload error | Submit Jun 13 evening as second buffer | Email Devpost support |
| Team member loses ≥2 days to outside-of-work emergency | M | M | Standup reports | Reassign tasks per cumulative summary above | Use slack budget; sequentially descope by week-acceptance gates |
| Schemas freeze slips past May 8 | M | XH | Phase 1 tasks not all green by EOD May 8 | **Hard descope:** drop W1.G.1-3, W1.G.7; ship without those docs | Defer threat model + failure modes to W6 |

**Master descope priorities (across all weeks):** in this order, drop first to last as scope tightens:
1. W5.C.* (optional adapters: GhidrAssist, Atropos, Hermes pager)
2. W5.B.3 (REMnux MCP)
3. W3.E.6 (kill -9 chaos test 100/100; ship with 10/10 sample)
4. W4.A.3 (5 of 6 skills; ship windows-triage + memory-forensics + report-writing only)
5. W2.D.3 (planner CoT capture)
6. W2.D.1-2 (planner_critique_node — accept "successfully-quorumed wrong plan" as v1 risk)
7. W3.D.1 (pivot_node — fold pivots back into replan loop)

**Do NOT descope under any circumstances:** schema bundle (W1.B), seed-fix (W1.C), playbooks (W1.F), psscan + DKOM (W1.E.1, W1.F.2), executor_work split with three owners (W2.C), at least one verifier strategy (W3.A.1 minimum), kill-9 resume working at all (W3.E.3), demo video (W6.A), Devpost submission (W6.D). These are the rubric anchors.

---

## Out of scope — v2 roadmap (don't touch in v1)

| Item | Source | Why deferred |
|---|---|---|
| Examiner Portal UI | v4.5 line 802 | CLI + Langfuse UI replaces |
| PostgresSaver multi-worker checkpointer | v4.5 line 553 | SqliteSaver sufficient single-host |
| Atropos RL fine-tuning loop | v4.5 line 268 | v2 — optional export ships, training does not |
| Hermes Telegram pager | v4.5 line 269 | optional v2 |
| macOS / Linux / Win11 SRUM/ETW / ESXi | W5.D.1 | Out of scope for Honeynet ransomware demo |
| FOR572 network forensics (Zeek, Suricata, tshark) | W5.D.1 | Fifth executor branch in v2 |
| Examiner workflow integrations (Axiom XML, EnCase EWF, FTK CSV) | v4.5 line 970 | Architecture supports export interface, format-specific adapters in v2 |
| LLM-as-judge `step_efficiency` upgrade | v4.5 line 866 | Deterministic v1 ships; LLM upgrade v2 |
| Microsoft Agent Framework migration | v4.5 line 322 | Late + Azure-coupled |
| AutoGen v0.4 | v4.5 line 322 | Maintenance mode |
| Examiner Portal | v4.5 line 802 | CLI + JSONL + Langfuse UI is sufficient |
| Multi-tenant deployment | this doc | Single-host v1 |
| OpenSearch evidence indexing | (Valhuntir comparison) | Not needed for 3 demo cases |
| Anthropic Constitutional Classifiers integration | (research consideration) | NeMo Guardrails sufficient v1 |

---

## How to execute this plan

1. **Saturday May 2 (today):** apply v4.6 patches P1–P6 to v4.5 audit doc (W1.B.7-W1.E.3 prep). Spin up SIFT VM scaffolding (W1.A.2). Send a message to teammates linking this doc + v4.6 spec plan.
2. **Sunday May 3:** Tim does Phase W1.A through W1.B end-to-end. Beaver does Phase W1.C. KP does Phase W1.F.1-F.4 (playbooks). Haley standing by for W1.A.4 inference setup.
3. **Monday May 4 — Thursday May 7:** parallel execution. Daily 10-min standup at 9am. Each teammate reports: yesterday's task IDs completed, today's task IDs in flight, any blockers.
4. **Friday May 8:** week 1 acceptance gate review. If ALL green, lock schemas. Open issue tracker for v4.7 deferred items. Tim merges all week-1 PRs.
5. **Weekly cadence:** Monday standup + scope review. Wednesday mid-week check. Friday acceptance gate review + descope if needed.
6. **Final week:** May 30 rough demo cut (Beaver records, all teammates review). Jun 6 final docs draft. Jun 12 final demo cut. Jun 13 evening Devpost upload as buffer. Jun 14 EOD final submission.

---

## Bottom line

This plan is 75 teammate-days of work distributed across 4 teammates over 6 weeks. The acceptance gates per week are the load-bearing structure — meeting them in order means the demo lands. The descope priorities are the safety net — work them in order if scope tightens.

Every task has a unique grep-able ID, a TDD substep sequence, and an acceptance check. Reference IDs in commits (`feat(schema): foo [W1.B.3]`) so git log is searchable.

When in doubt, fall back to v4.5 for architecture rationale, v4.6 for schema patches, and project `CLAUDE.md` for conventions. This document supersedes neither — it sequences both into execution.

---

# Appendix A — Schema bundle (copy-paste ready)

## A.1 — `src/verdict/schemas/artifact_class.py`

```python
from enum import Enum

class ArtifactClass(str, Enum):
    """Multi-artifact corroboration vocabulary.
    SANS FOR500 doctrine: no single artifact proves execution.
    Cited from CLAUDE.md §3.2 and docs/ARCHITECTURE.md §4."""
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

## A.2 — `src/verdict/schemas/caveat_id.py`

```python
from enum import Enum

class CaveatID(str, Enum):
    """Tier-1 caveats from CLAUDE.md §3.3 and examiner_caveats.md.
    These are the misreads Rob Lee uses to spot a fake examiner."""
    AMCACHE_LASTMODIFIED_NOT_EXEC = "amcache_lastmodified_neq_execution"
    SHIMCACHE_ORDER_CHANGED_WIN81 = "shimcache_order_lru_pre81_insertion_post81"
    PREFETCH_SSD_DISABLED = "prefetch_disabled_on_ssd_or_gpo"
    MFT_SI_STOMPABLE = "mft_si_timestomp_use_fn"
    USNJRNL_WRAPS = "usnjrnl_wraps_treat_gaps_carefully"
    LOGON_TYPE_3_VS_10 = "evtx_4624_type3_network_neq_type10_rdp"
    SYSMON_PROCESSGUID_OVER_PID = "sysmon_processguid_correlation_key_not_pid"
```

## A.3 — `src/verdict/schemas/evidence.py`

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

## A.4 — `src/verdict/schemas/tool_output.py`

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

## A.5 — `src/verdict/verification/cloud_self_consistency.py`

`derive_seeds` is already shipped in `src/verdict/verification/derive_seeds.py`
(W1.C.1). Implement `CloudSelfConsistency` here to use it:

```python
from blake3 import blake3
import asyncio
from verdict.verification.derive_seeds import derive_seeds

class CloudSelfConsistency:
    async def verify(self, plan, evidence_hash):
        s1, s2, s3 = derive_seeds(plan.case_id)
        samples = await asyncio.gather(*[
            self.claude.complete(plan, temperature=0.7, seed=s)
            for s in (s1, s2, s3)
        ])
        return await self.usc_judge(samples, plan)  # Chen 2023
```

`derive_seeds` uses a keyed blake3 digest (`key=b"VERDICT self-consistency seeds\0\0"`,
`digest(length=12)`) — do not inline a copy. See `docs/ARCHITECTURE.md` §1 for the
rationale and the shipping implementation.

(Other schemas — Hypothesis, InvestigationPlan, Finding, LedgerEntry — are large; reference v4.5 lines 195–290 + v4.6 schema patch sections.)

---

# Appendix B — System prompt templates

## B.1 — `src/verdict/planning/prompts/examiner_caveats.md`

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

## C.1 — `src/verdict/playbooks/memory.yml`

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

## C.2 — `src/verdict/playbooks/disk.yml`

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

## C.3 — `src/verdict/playbooks/triage.yml`

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

## C.4 — `src/verdict/knowledge/hunt_evil.yml`

(Per W1.F.9 task body. 8 entries: svchost, lsass, csrss, winlogon, services, wininit, explorer, smss.)

## C.5 — `src/verdict/knowledge/lolbins.yml`

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

Per W6.A.1 task. References v4.5 lines 855–865 plus v4.4 hero beats. See `docs/RELEASE.md` post-W6.A.1 for full timing.

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
