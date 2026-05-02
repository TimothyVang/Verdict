# VERDICT — Master Build Plan (v1)

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
- **Hard rule on conventions** (per project `CLAUDE.md`): TDD failing test → RED → implement → GREEN → commit. One commit per task. Conventional Commits format. Never `--no-verify`, `--no-gpg-sign`, or `git commit --amend`. Pinned versions in lockfiles. Python 3.11 + uv + pytest + ruff. Node 20 + pnpm.

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
2. **Plan-then-Execute LangGraph topology** (9 nodes) with named nodes: `planner` → `planner_critique` (CoVe) → `comprehension_gate` → `executor_fanout` (per-branch composition: `DenyRuleWrapper → ToolExecutor → LedgerEmitter`; the composition is referred to internally as `executor_work` and is a sub-state of fanout, not a separate top-level node) → `pivot_node` → `quorum` → `replan` → `unverifiable_finalize` → `finalize`.
3. **12 SIFT tool wrappers** as MCP tools running in per-call ephemeral microsandbox VMs: `mmls`, `fls`, `fsstat`, `vol3` (10 plugins), `hayabusa` (split: csv-timeline + filter), `plaso` (split: extract + filter), `MFTECmd`, `RECmd`, `PECmd`, `bulk_extractor`, `exiftool`, `capa`.
4. **Three-layer immutability defense**: Layer 1 = Claude PreToolUse hook (best-effort, version-dependent caveat per #33106/#37210); Layer 2 = LangGraph `DenyRuleWrapper` (architectural guarantee, all modes); Layer 3 = Microsandbox read-only mount (kernel-enforced).
5. **Cryptographic chain-of-custody**: HMAC-signed append-only JSONL ledger with `prev_entry_hash`, three-tier ID hierarchy (`case_id` / `langfuse_trace_id` / `langgraph_checkpoint_id`), per-output-file SHA-256, examination-environment metadata (`microsandbox_version`, `rootfs_sha256`, `tool_version`, `kernel_version`).
6. **Forensic discipline encoded in code**: `Finding.artifact_paths min_length=2`, `Finding.artifact_classes min_length=2`, `Finding.caveats_acknowledged` field with model_validators, three playbook YAMLs (memory/disk/triage), `examiner_caveats.md` system-prompt include, `hunt_evil.yml` with 8 process baselines, DKOM/T1014 detection via pslist+psscan divergence, sub-technique-aware MITRE field validation.
7. **Observability**: Langfuse self-hosted (MIT) with OTel via OpenLLMetry; trace tree UI cross-linked to JSONL ledger via `trace_id`; SqliteSaver checkpointer with `PRAGMA journal_mode=WAL; synchronous=FULL` for kill-9 resilience.
8. **Eval harness**: Inspect AI with three per-mode tasks (`verdict_eval_cloud`, `verdict_eval_airgap`, `verdict_eval_dual`); five scorers (`step_efficiency`, `findings_precision`, `findings_recall`, `mitre_subtechnique_precision`, `negative_hypothesis_quality`); 50 ground-truth indicators across 3 engineered cases (lol-bins compromise, credential theft, ransomware).
9. **5-minute demo video** recorded May 30 (rough cut) and June 14 (final), two-pane (terminal + Langfuse trace tree), all three modes against the Honeynet ransomware image, hero beats: pslist/psscan DKOM divergence, Hunt Evil masquerade catch (`scvhost.exe` parent=`cmd.exe`), Amcache-caveat acknowledgment, pivot-vs-replan distinction, TSI tcpdump proof, kill -9 + resume, planner_critique CoVe.
10. **Submission docs**: README, ARCHITECTURE.md, BUILD.md, THREAT_MODEL.md, FAILURE_MODES.md, CLI.md, CHECKPOINTING.md, CASE_ISOLATION.md, SCOPE.md, SCHEMA_MIGRATION.md, SANS_JUDGE_CHECKLIST.md, PRODUCTION_AUDIT.md, LICENSE (MIT), CONTRIBUTING.md.

---

## Authorities — what to read when stuck

| Need | Read |
|---|---|
| Architecture rationale | `archive/03-audit-v4.5.md` |
| Schema patches + DFIR rule encoding | `archive/04-spec-plan-v4.6.md` |
| Project-level conventions | `CLAUDE.md` (this repo) |
| Tier-1 examiner caveats | `agent-config/MEMORY.md` |
| Per-evidence-type tool sequencing | `agent-config/PLAYBOOK.md` |
| Tool surface (FastMCP, Python) | `verdict/tools/` |
| Decision history | `CHANGELOG.md` + `git log --oneline` |
| Why we picked X over Y | v4.5 §"Lock-In Decisions" + v4.5 §"Per-Tool Deep Dives" |

If two authorities conflict: **code + lockfiles win** over docs (per `CLAUDE.md` §"Spec/code divergences"). Update the doc rather than rolling back the code, unless the code is wrong.

---

## Stack lock-in (one paragraph each — full rationale in v4.5)

- **Cloud agent:** Claude Code + Claude Agent SDK (Python). Used in cloud-only and dual modes. Three credential paths: `CLAUDE_CODE_OAUTH_TOKEN` env var, interactive `~/.claude/`, or `ANTHROPIC_API_KEY`. OAuth tokens are NOT redistributable per Anthropic commercial terms.
- **Local inference primary:** SGLang (Apache-2.0). RadixAttention prefix cache; native `--tool-call-parser glm45` and `qwen3_xml`. Used in air-gap and dual modes.
- **Local inference fallback:** vLLM (Apache-2.0). Pinned to a release containing PR #39055 (Qwen3 reasoning-parser fix).
- **Local Model A:** Qwen3-30B-A3B-Thinking-2507 (Apache-2.0). Air-gap planner; executor in all modes.
- **Local Model B (verifier):** GLM-4.5-Air (MIT). Always executor, never planner. Cross-family verification partner.
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
│   ├── BUILD.md
│   ├── THREAT_MODEL.md                     # 4 surfaces (W1.G.1)
│   ├── FAILURE_MODES.md                    # Component × failure × recovery (W1.G.2)
│   ├── CLI.md                              # verdict CLI surface (W1.G.3)
│   ├── CHECKPOINTING.md                    # SqliteSaver + WAL + reducer (W3.E.4)
│   ├── CASE_ISOLATION.md                   # RadixAttention prefix-cache vs case data (W3.G.1)
│   ├── SCOPE.md                            # v1 = Windows DFIR (W5.D.1)
│   ├── SCHEMA_MIGRATION.md                 # schema_version migration story (W1.G.4)
│   ├── SANS_JUDGE_CHECKLIST.md             # Demo recorded against this (W6.B.1)
│   ├── PRODUCTION_AUDIT.md                 # The v4 triage doc
│   ├── DEMO_SEQUENCE.md                    # 5-min sequence (W6.A.1)
│   └── ACCURACY_REPORT.md                  # Per-mode tables + correlation analysis (W5.E.1)
├── verdict/
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
│   ├── run-all-tests.sh                    # Per-service pytest
│   ├── package-devpost.sh                  # Submission zip (W6.D.1)
│   ├── shoot-demo.sh                       # Two-pane recording driver (W6.A.2)
│   └── healthcheck.sh                      # Continuous /health probe (W3.F.1)
├── .github/
│   └── workflows/
│       ├── l0-static.yml                   # ruff
│       ├── l1-unit.yml                     # uv run pytest per service
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

## Per-week phases — sliced into `docs/build/`

The detailed task plan was sliced into per-week files for easier ingestion (LLM and human). Each week file is self-contained: theme block, phases (`W{N}.A` through `W{N}.G`), acceptance gates, descope-priority. The conductor (`swarm/conductor.py`) parses all files in `docs/build/week-*.md` in sorted order; per-task parsing semantics are unchanged.

| Week | Dates | Theme | File |
|---|---|---|---|
| 1 | May 2–8 | Foundations + Schemas | [`build/week-1.md`](build/week-1.md) |
| 2 | May 9–15 | Tool surface + Plan-then-Execute refactor | [`build/week-2.md`](build/week-2.md) |
| 3 | May 16–22 | Verifier strategies + TSI + Checkpointing | [`build/week-3.md`](build/week-3.md) |
| 4 | May 23–29 | Skills, hooks, evals | [`build/week-4.md`](build/week-4.md) |
| 5 | May 30 – Jun 5 | Mode autodetect + adapters + polish | [`build/week-5.md`](build/week-5.md) |
| 6 | Jun 6–14 | Demo + docs + submission | [`build/week-6.md`](build/week-6.md) |
| supplemental | — | Per-teammate cumulative day budget | [`build/teammates.md`](build/teammates.md) |
| supplemental | — | Schema bundle, system prompts, YAML scaffolds, demo + judge checklist | [`build/appendices.md`](build/appendices.md) |

### Task ID lookup

A task ID like `W2.C.5` resolves to `build/week-2.md` (the digit before the first dot is the week). Search the file for `### W2.C.5` to find the task body. Acceptance gates for the week live at the bottom of the same file.

### For the swarm conductor

`swarm/conductor.py:parse_plan` accepts either a single `.md` file (legacy) or a directory. Default is now `docs/build/`, which globs `week-*.md` in sorted order. Phase headings (`## Phase W{N}.X`) and task headings (`### W{N}.X.Y — title`) are recognised identically across both modes.
