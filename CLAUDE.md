# CLAUDE.md — VERDICT (FIND EVIL! hackathon entry)

This file is the operating charter for any Claude Code session opened in this workspace. Read it end-to-end before touching code. The hard rules in §3 are load-bearing — violating them invalidates findings, breaks chain of custody, or fails the SANS judge rubric.

## 1. Project identity

**VERDICT** — an autonomous Windows DFIR / incident-response agent built for the SANS *FIND EVIL!* 2026 hackathon. It conducts digital investigations through a Plan-then-Execute LangGraph topology over the SANS SIFT Workstation, with cryptographic chain-of-custody, multi-mode (cloud / air-gap / dual) inference, and forensic discipline encoded at the schema and prompt layers.

**This is a full-stack, real, working tool. No mocks, no stubs, no fixtures-pretending-to-be-real-evidence, no placeholder implementations.** Every layer — planner, executors, microsandbox, SIFT tool wrappers, ledger, verifier strategies, CLI — is wired against real inference engines, real microVMs, real evidence files, and real SIFT binaries from day one. The test surface is end-to-end Inspect AI evals against real ground-truth disk/memory images, not a mock harness. See §3.10.

- **Hackathon:** https://findevil.devpost.com/
- **Submission deadline:** **Jun 14 2026 EOD** (Devpost upload buffer); **Jun 15 22:45 CDT** official.
- **Judging window:** Jun 19 – Jul 3 2026; winners ~Jul 8 2026.
- **Sponsor / judge:** SANS Institute; Rob T. Lee (CAIO).
- **Submission pack:** see §11 plus `docs/hackathon/RULES.md` and `docs/hackathon/OVERVIEW.md`.

VERDICT extends — but does not vendor — the upstream `protocol-sift/` Claude Code config framework cloned in this workspace. License is **MIT** (the hackathon allows MIT or Apache-2.0).

## 2. Authority chain (read in this order)

The design is captured across five docs in `docs/spec/`. They are cumulative, not replacements.

| Doc | Role | When to consult |
|-----|------|-----------------|
| `docs/spec/VERDICT_AUDIT_v4.5.md` | **Canonical architecture.** Latest authoritative system design. v4.5 explicitly **deletes the unit-test mock layer** (`MockExecutor` / `MockSandbox` / `MockLLM`) — VERDICT is built and tested against real inference, real microVMs, and real SIFT tools. Inspect AI end-to-end evals are the only test surface. | Default reference for architecture, schemas, nodes, threat model, verifier strategies. |
| `docs/spec/VERDICT_v4.6_SPEC_PLAN.md` | **Five tactical patches** that overlay v4.5: (F1) `derive_seeds` fix, (F2) PreToolUse Layer-1 caveat + xfail smoke test, (F3) `Finding` schema patches (`artifact_paths` `min_length=2`, `artifact_classes` enum, `caveats_acknowledged`), (F4) `vol3.windows.psscan` + DKOM rule in `playbooks/memory.yml`, (F5) playbook + caveat + `hunt_evil` content. | When a v4.5 statement and v4.6 conflict on a patched item, **v4.6 wins on that item only**. |
| `docs/spec/VERDICT_MASTER_BUILD_PLAN.md` | **Execution sequencing.** 6-week / 75-teammate-day plan with task IDs (W1.A.3.a, W1.B.7, etc.), ownership, hours, acceptance gates. | Use task IDs in commit messages. Use weekly acceptance gates as the definition of done. |
| `docs/spec/VERDICT_AUDIT_v4.4.md` | History — 24 findings (11 agentic + 13 DFIR). All findings remain in force. | Read for *why* a particular schema validator or playbook entry exists. |
| `docs/spec/VERDICT_AUDIT_v4.3.md` | History — 10 system-design fixes. All findings remain in force. | Read for the original mode-detection, verifier-strategy, and checkpointing rationale. |

When in doubt: **v4.6 patches > v4.5 architecture > v4.4 / v4.3 history.** Master plan defines *what* to build *when*, not *what* the system is.

## 3. Hard rules — MUST / MUST NOT

These are non-negotiable. Each ties back to a schema validator, a wrapper, or a CI check; do not propose code that bypasses them.

### 3.1 Evidence integrity

- **Never write to `/evidence/`.** It is a read-only microsandbox mount with `noexec` on data partitions; the host also `chattr +i`s evidence files. Any tool wrapper that writes to evidence is a bug, not a feature.
- **Hash on entry, re-hash periodically.** Every evidence file gets a SHA-256 at `case_init` recorded in the `EvidenceManifest`. The runtime re-hashes every 10 super-steps (`verdict/runtime/evidence_recheck.py`). Mismatch raises `HashMismatchError` and halts the case.
- **Per-invocation hash.** Every tool call records `invocation_hash = blake3(tool_name + tool_version + args + evidence_hash)` in its `ToolOutput` and ledger entry.
- **Per-output-file hash.** `LedgerEntry.output_files_sha256: dict[str, str]` records SHA-256 of every file the tool emits. NIST SP 800-86 §5.1.2 / §5.1.4 compliance.

### 3.2 Multi-artifact corroboration

- `Finding.artifact_paths` and `Finding.artifact_classes` both have `min_length=2`. Single-artifact execution claims are forensically unsound and the validator rejects them.
- **Execution-class MITRE techniques** — T1059, T1106, T1204, T1218, T1543, T1547 — require **≥2 distinct `ArtifactClass` values** (not just two paths in the same class). Validator: `Finding._execution_requires_two_classes`.

### 3.3 Tier-1 caveat acknowledgment

`Finding.caveats_acknowledged: list[CaveatID]` is enforced at the schema layer. Cite the artifact, acknowledge the caveat. The seven Tier-1 caveats (encoded in `verdict/schemas/caveat_id.py` and `verdict/prompts/examiner_caveats.md`):

| CaveatID | Trigger |
|----------|---------|
| `AMCACHE_LASTMODIFIED_NOT_EXEC` | Any Amcache citation. LastModified ≠ execution time. |
| `SHIMCACHE_ORDER_CHANGED_WIN81` | ShimCache ordering on Windows ≥ 8.1 is insertion-order, not LRU. |
| `PREFETCH_SSD_DISABLED` | Prefetch citation when host is SSD-only (Prefetch may be disabled). |
| `MFT_SI_STOMPABLE` | Any `$STANDARD_INFORMATION` timestamp use. Prefer `$FILE_NAME`. |
| `USNJRNL_WRAPS` | USN journal citation older than the journal's wrap window. |
| `LOGON_TYPE_3_VS_10` | Distinguishing network logon (3) from RDP (10). |
| `SYSMON_PROCESSGUID_OVER_PID` | Correlation that uses PID alone instead of `ProcessGuid`. |

### 3.4 Mode lock

- `LedgerEntry.mode_at_case_init` is set once and immutable.
- `verdict resume <case_id>` reads the original mode and refuses to advance if the current `detect_mode()` differs.
- Mode change is via `verdict reverify --mode <m>` only — that creates a **parallel verdict chain**, never mutating the original.
- Cloud-only mode requires `ANTHROPIC_API` reachable; air-gap requires `SGLANG_BASE_URL` reachable; dual requires both. `verdict doctor` is the pre-flight.

### 3.5 MITRE sub-technique precision

- Emit `T1055.012`, never bare `T1055`, when the sub-technique is determinable.
- Regex enforced on `Hypothesis.mitre_technique` and `Finding.mitre_technique`: `^T\d{4}(\.\d{3})?$`.
- Inspect AI scorer `mitre_subtechnique_precision` fails CI if the planner emits a parent technique when the sub was determinable.

### 3.6 Epistemic vocabulary

- Verdict statuses are exactly: `VETTED_CLOUD`, `VETTED_AIRGAP`, `VETTED_DUAL`, `CONTESTED`, `UNVERIFIABLE`, `EXHAUSTED_REPLAN`. No others.
- Findings phrase attribution as **"evidence consistent with X"** — never "X did this". Attribution is for the human IR lead, not the agent.
- Negative hypotheses are required (≥1 per plan). The `_negative_hypothesis_quality` validator deny-lists `cosmic`, `alien`, `nothing`, `not-relevant`, `n-a`. A negative hypothesis must have a non-None `mitre_technique` and non-empty `artifact_families`.
- `Finding.status = UNVERIFIABLE` is a **first-class outcome**, not a failure to be hidden. The 15-item judge rubric specifically rewards explicit UNVERIFIABLE.

### 3.7 TDD + Conventional Commits

- Failing test → RED → implement → GREEN → **one commit per task ID**.
- Commit message format: `feat(scope): summary [W#.#.#]` — task ID is required. Example: `feat(schema): add ArtifactClass enum [W1.B.1]`.
- **Never** `--no-verify`, **never** `--no-gpg-sign`, **never** `git commit --amend`. Pre-commit hook failure means fix and re-stage; do not bypass.
- Allowed commit prefixes: `feat`, `fix`, `test`, `chore`, `docs`, `refactor`. No others without RFC.

### 3.8 Dependency / vendoring policy

**Hard NOs** — these may not be added to `pyproject.toml`, `Cargo.toml`, or `package.json` under any circumstances:

| Forbidden | Reason |
|-----------|--------|
| Daytona | AGPL-3.0 |
| REMnux MCP (vendored) | GPL-3.0 — out-of-process call only, never linked |
| Llama 4 / Gemma 3 | community licenses, not Apache-2.0/MIT |
| Modal | proprietary infra |
| LangSmith | competing observability + license terms |
| Braintrust | competing observability + license terms |
| Arize Phoenix | ELv2 |
| AutoGen v0.4 | maintenance mode |
| Microsoft Agent Framework | premature, license terms |
| AGPL clean-room rewrites | strategic risk |

Every new dependency must be **MIT or Apache-2.0** unless explicitly approved in `docs/PRODUCTION_AUDIT.md`.

### 3.9 Credential isolation

- API keys, OAuth tokens, and bearer tokens **never enter a microVM**. They are injected via TSI on host egress only; tcpdump-verifiable.
- HMAC ledger key is TPM-backed (`/dev/tpmrm0`) when available, else gpg-encrypted at `~/.verdict/key.gpg` with passphrase prompted at gateway init.
- Ledger redaction strips `authorization`, `auth_user`, `api_key` **before** the entry is hashed and HMAC-signed (`verdict/ledger/redaction.py`).
- Anthropic OAuth tokens (Claude Code interactive auth) are not redistributable per Anthropic's commercial terms — do not commit, do not bake into images.

### 3.10 No mocks, no stubs, no placeholders — full-stack real

VERDICT is a working tool, not a demo skeleton. v4.5 explicitly deleted the mock test layer; this is reaffirmed and broadened here as a hard rule that applies to **all code in the repo**, not just tests.

**MUST NOT, anywhere in the codebase:**

- `MockExecutor`, `MockSandbox`, `MockLLM`, `FakeMicrosandbox`, `StubAnthropic`, `DummyLedger`, or any equivalent class.
- `unittest.mock.Mock` / `MagicMock` / `patch` against VERDICT internals. (Patching a third-party library at the system boundary in a single targeted test is acceptable; mocking your own module is not.)
- `responses`, `httpx_mock`, `vcr.py`, `betamax`, or any HTTP-replay library standing in for a real Anthropic / SGLang / Langfuse endpoint during dev or eval.
- Conditional code paths gated on `if MOCK or TEST_MODE: ...` — every code path must run in production.
- Hard-coded synthetic "evidence" embedded in source. Ground-truth cases live as real `.E01`, `.raw`, `.mem`, `.pcap`, `.zip` files under `inspect_ai/ground_truth/case_00*/`.
- "TODO: replace with real implementation" stubs that return canned data. Either implement the real thing or do not commit the file.
- Schema validators that short-circuit when `os.environ.get("VERDICT_TEST")` is set.
- Skipping the microsandbox in tests "for speed" by running tools on the host. Tests run in real microVMs, just like production.

**MUST, instead:**

- Drive every layer against a real backing service from the first commit. Bring up SGLang + Microsandbox + Langfuse locally before any code that depends on them is written; no commit may rely on a service that isn't running for the developer.
- Use **real ground-truth fixtures** for tests: the three engineered cases (`case_001_lolbins/`, `case_002_credtheft/`, `case_003_ransomware/`) ship as actual disk/memory artifacts; tests load them and run the real planner+executor+sandbox+verifier loop end-to-end.
- Treat `verdict doctor` failure as a hard test prerequisite: tests that need SGLang refuse to run if `verdict doctor` reports SGLang unreachable. Skip ≠ pass.
- Air-gap mode is implemented and tested with the cloud lane physically unreachable (`unset ANTHROPIC_API_KEY`, no network egress) — not by mocking the cloud away.
- The dev loop *is* the eval loop *is* the demo loop. `inspect eval inspect_ai/tasks/verdict_eval_{cloud,airgap,dual}.py` runs the same code path the SANS judge sees on stage.

If you find yourself reaching for a mock to make a test fast or hermetic, you are wrong about which test belongs at that layer. Move the assertion to a unit test that doesn't need the dependency, or accept the integration cost.

## 4. Architecture at a glance

VERDICT is a 9-node LangGraph state machine with explicit reducer-merged fanout. Source: `docs/spec/VERDICT_AUDIT_v4.5.md` plus v4.6 patches.

```
                      ┌─────────────┐
                      │   planner   │   InvestigationPlan
                      └──────┬──────┘   (positive + ≥1 negative hypotheses,
                             │           pivot_budget=15, replan_budget=3)
                             ▼
                  ┌─────────────────────┐
                  │ planner_critique    │   CoVe — questions the plan
                  │ (Chain-of-Verify)   │   asks itself, must pass before
                  └──────────┬──────────┘   comprehension_gate
                             │
                             ▼
                  ┌─────────────────────┐
                  │ comprehension_gate  │   collects PlanComprehensionEcho
                  │ (n=4 executors)     │   from all 4; consensus on
                  └──────────┬──────────┘   hypothesis_ids + criteria_hash
                             │
                             ▼
                  ┌─────────────────────┐
                  │   executor_fanout   │   parallel n=4 executors,
                  │   (reducer merge)   │   deterministic merge
                  └──────────┬──────────┘
                             │
                             ▼
        ┌────────────────────┴─────────────────────┐
        │              executor_work               │
        │  ┌────────────┐ ┌──────────┐ ┌────────┐  │
        │  │ DenyRule   │→│ ToolExec │→│Ledger  │  │
        │  │ Wrapper    │ │ (sandbox)│ │Emitter │  │
        │  └────────────┘ └──────────┘ └────────┘  │
        └──────────────────────┬───────────────────┘
                               │
                               ▼
                  ┌─────────────────────┐
                  │     pivot_node      │   ≤15 cheap follow-ups
                  └──────────┬──────────┘   (single-Hypothesis adjustments)
                             │
                             ▼
                  ┌─────────────────────┐
                  │      quorum         │   VerifierStrategy dispatch
                  │ (mode-dependent)    │   (see §8)
                  └──────────┬──────────┘
                             │
                  ┌──────────┴──────────┐
                  ▼                     ▼
          ┌───────────────┐    ┌────────────────────────┐
          │   replan      │    │ unverifiable_finalize  │
          │ (≤3 iters)    │    │ (replan iter 4 →       │
          └──────┬────────┘    │  UNVERIFIABLE +        │
                 │             │  interrupt() for human)│
                 │             └────────────┬───────────┘
                 │                          │
                 └────────┐         ┌───────┘
                          ▼         ▼
                       ┌──────────────┐
                       │   finalize   │   HMAC-signed Findings
                       └──────────────┘
```

### 4.1 Operational modes

Mode is auto-detected at `case_init` (or overridden via `--mode`) and **locked**.

| Mode | Planner | Executor (×4) | Verifier |
|------|---------|---------------|----------|
| `CLOUD` | Claude Code (Anthropic) | local Qwen3-30B-A3B-Thinking | `CloudSelfConsistency` (n=3) |
| `AIRGAP` | local Qwen3-30B-A3B-Thinking | local Qwen3 | `AirGapCrossEngine` (Qwen3 vs GLM-4.5-Air) |
| `DUAL` | parallel cloud + airgap lanes | both | `DualLaneCrossEngine` (cloud + ≥1 local; locals agree) |

### 4.2 Three-layer immutability defense

| Layer | Mechanism | Strength |
|-------|-----------|----------|
| 1 | Claude Code `PreToolUse` hook | **Best-effort.** Per anthropics/claude-code#33106 + #37210, `permissionDecision: "deny"` is buggy for MCP and Edit tools. CI smoke test (xfail-marked) monitors for regression; relying on Layer 1 alone is forbidden. |
| 2 | LangGraph `DenyRuleWrapper` (`verdict/graph/wrappers/deny_rule.py`) | **Architectural guarantee.** Fires in all three modes regardless of which model called. This is the load-bearing layer. |
| 3 | Microsandbox read-only `/evidence` mount + `noexec` | **Kernel-enforced.** Final defense. Even a model+wrapper bypass cannot write through a read-only mount. |

The PreToolUse hook is documented as a deterrent + telemetry source, not a guarantee.

## 5. Tech stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Language (primary) | Python **3.11** | `uv` for env, `pytest` for tests, `ruff` for lint+format (no black/isort split). |
| Language (MCP services) | Rust **1.88** | FastMCP 3.x wrappers. |
| Language (skills, deferred v2) | Node **20** | pnpm workspaces (`mcp-widgets` deferred). |
| Inference (primary local) | **SGLang** (Apache-2.0) | RadixAttention prefix-cache; `--tool-call-parser qwen3_xml` and `--tool-call-parser glm45` (native). |
| Inference (fallback local) | **vLLM** (Apache-2.0) | Pinned to PR #39055 (Qwen3 reasoning-parser). |
| Models | Qwen3-30B-A3B-Thinking-2507 (Apache-2.0); GLM-4.5-Air (MIT) | Qwen3 = planner/executor; GLM-4.5-Air = verifier only. |
| Cloud agent | Claude Agent SDK + Claude Code CLI | OAuth, interactive, or `ANTHROPIC_API_KEY` paths. |
| Orchestration | **LangGraph** (MIT) + `SqliteSaver` | `PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL` for kill-9 resilience. |
| Schemas | **Pydantic v2** + Pydantic-AI (MIT) | All forensic discipline encoded as validators. |
| Tool dispatch | Pydantic-AI `args_validators` | `ModelRetry` flow, retry_max=2, then UNVERIFIABLE. |
| Guardrails | **NeMo Guardrails** (Apache-2.0) | input/output rails. |
| MCP gateway | **FastMCP 3.x** (Apache-2.0) | 12+ SIFT tools surfaced as MCP tools. |
| Sandbox | **Microsandbox** (Apache-2.0, beta) — libkrun microVM | ~200 ms cold start, TSI for credential injection, rootfs SHA-256 pin. Fallback: bubblewrap (LGPL-2.0) + nsjail (Apache-2.0). |
| Hashing | **blake3** (MIT) | Keyed-hash seed derivation, invocation hashing, evidence re-hashing. SHA-256 for per-file evidence hashes. |
| Observability | **Langfuse v2** self-host (MIT) + **OpenLLMetry** (Apache-2.0) | Trace tree cross-linked to JSONL ledger via `trace_id`. |
| Eval harness | **Inspect AI** (MIT, UKGovernmentBEIS) | Three per-mode tasks; five deterministic scorers; 50 ground-truth indicators across 3 cases. |
| CI/CD | GitHub Actions | Workflows: `l0-static`, `l1-unit`, `l2-sift-lite`, `l3-goldens`, `inspect-ai-evals`, `release`, `devpost-submit`. |

See §3.8 for the explicit hard NOs. Anything not on either list needs an entry in `docs/PRODUCTION_AUDIT.md` before adoption.

## 6. Target repo layout

The workspace is currently a planning shell — no code exists yet. The first scaffolding work is **W1.A** of the master plan. Target tree (abridged; full version in `docs/spec/VERDICT_MASTER_BUILD_PLAN.md`):

```
Verdict/
├── CLAUDE.md                     ← this file
├── README.md
├── LICENSE                       ← MIT
├── CONTRIBUTING.md
├── CHANGELOG.md
├── pyproject.toml                ← uv workspace root
├── uv.lock
├── docker-compose.yml            ← Langfuse v2 self-host
├── docker-compose.langfuse-v3.yml
├── docs/
│   ├── README.md                 ← docs index
│   ├── spec/                     ← canonical source docs (do not edit)
│   │   ├── VERDICT_AUDIT_v4.3.md
│   │   ├── VERDICT_AUDIT_v4.4.md
│   │   ├── VERDICT_AUDIT_v4.5.md
│   │   ├── VERDICT_v4.6_SPEC_PLAN.md
│   │   └── VERDICT_MASTER_BUILD_PLAN.md
│   ├── hackathon/
│   │   ├── RULES.md              ← official SANS FIND EVIL! rules
│   │   └── OVERVIEW.md           ← hackathon overview + resource links
│   ├── ARCHITECTURE.md           ← (W1+) project-authored
│   ├── BUILD.md                  ← (W1+)
│   ├── THREAT_MODEL.md           ← (W1+) 4 surfaces: insider, prompt-inj-from-evidence,
│   │                               malicious-tool-output, external-attacker
│   ├── FAILURE_MODES.md          ← (W1+) component × failure × recovery matrix
│   ├── CLI.md                    ← (W1+)
│   ├── CHECKPOINTING.md          ← (W1+) SqliteSaver + WAL + reducer pattern
│   ├── CASE_ISOLATION.md         ← (W1+) RadixAttention prefix-cache vs case data
│   ├── SCOPE.md                  ← (W1+) v1 = Windows DFIR; v2 = macOS / Linux / ESXi
│   ├── SCHEMA_MIGRATION.md       ← (W1+)
│   ├── SANS_JUDGE_CHECKLIST.md   ← (W6) 15-item demo rubric (see §11)
│   ├── PRODUCTION_AUDIT.md       ← (W1+) v4 triage (what landed v1 vs v2)
│   ├── DEMO_SEQUENCE.md          ← (W6) 5-min storyboard with timing
│   ├── ACCURACY_REPORT.md        ← (W6) per-mode tables + correlation analysis
│   └── demo-assets/              ← (W6)
├── downloads/                    ← gitignored; large binaries (manual fetch)
│   ├── sift-workstation/         ← SIFT OVA (8.81 GB)
│   └── evidence-samples/         ← case_001..003 (Slack-distributed)
├── protocol-sift/                ← upstream Claude Code config framework (cloned)
├── verdict/
│   ├── runtime/                  ← mode_detect, gateway, evidence_recheck
│   ├── schemas/                  ← mode, artifact_class, caveat_id, evidence,
│   │                               tool_output, plan, finding, ledger,
│   │                               playbook, hunt_evil, version
│   ├── verification/             ← strategy, derive_seeds, cloud_self_consistency,
│   │                               airgap_cross_engine, dual_lane_cross_engine,
│   │                               universal_self_consistency
│   ├── planning/                 ← planner, planner_critique, playbook_loader,
│   │                               executor_prompt, prompts/
│   ├── playbooks/                ← memory.yml, disk.yml, triage.yml
│   ├── knowledge/                ← hunt_evil.yml, lolbins.yml
│   ├── graph/
│   │   ├── nodes.py / topology.py / reducers.py / checkpoint.py / interrupt.py
│   │   └── wrappers/             ← deny_rule, tool_executor, ledger_emitter
│   ├── tools/
│   │   ├── base.py / args_validators.py / sanitization.py
│   │   ├── vol3/                 ← pslist, psscan, pstree, cmdline, dlllist,
│   │   │                           malfind, netscan, svcscan, handles, callbacks
│   │   ├── hayabusa_csv_timeline.py / hayabusa_filter.py
│   │   ├── plaso_extract.py / psort_filter.py
│   │   ├── mmls.py / fls.py / fsstat.py
│   │   ├── mftecmd.py / recmd.py / pecmd.py
│   │   ├── bulk_extractor.py / exiftool.py / capa.py
│   ├── sandboxes/                ← microsandbox_provider, tsi_provider, rootfs_pin
│   ├── ledger/                   ← writer, chain, hmac_key, redaction
│   ├── observability/            ← langfuse_setup, otel_setup, trace_link
│   ├── cli/                      ← __main__, init, resume, reverify, status,
│   │                               ls, show, export, validate, mode, gc,
│   │                               health, doctor, approve, credentials
│   └── adapters/                 ← opencti_mcp, velociraptor_mcp, ghidrassist_mcp,
│                                   atropos_export, hermes_pager
├── verdict-skills/               ← agentskills.io frontmatter; SKILL.md + KNOWLEDGE.md
│   ├── windows-triage/           ← LOLBins catalog
│   ├── linux-triage/
│   ├── memory-forensics/
│   ├── network-pcap/
│   ├── malware-static/
│   └── report-writing/
├── tests/
│   ├── schemas/ verification/ planning/ playbooks/ prompts/ knowledge/
│   ├── graph/ tools/ sandboxes/ ledger/ observability/ cli/
│   ├── chaos/                    ← test_kill_9_resume.py (100-case zero-loss)
│   ├── smoke/                    ← test_pretooluse_deny.py (xfail), test_amendment_a2_guard.py
│   └── e2e/
├── inspect_ai/
│   ├── tasks/                    ← verdict_eval_cloud / airgap / dual
│   ├── scorers/                  ← step_efficiency, findings_precision,
│   │                               findings_recall, mitre_subtechnique_precision,
│   │                               negative_hypothesis_quality
│   ├── scripts/                  ← measure_disagreement_correlation.py
│   └── ground_truth/
│       ├── case_001_lolbins/     ← 17 indicators
│       ├── case_002_credtheft/   ← 17 indicators
│       └── case_003_ransomware/  ← 16 indicators (Honeynet derivative)
├── scripts/
│   ├── install.sh                ← three-credential-path
│   ├── verdict-install.sh        ← overlay on Protocol SIFT install.sh
│   ├── run-all-tests.sh
│   ├── package-devpost.sh        ← dist/verdict-devpost-v1.zip
│   ├── shoot-demo.sh             ← two-pane recording driver
│   └── healthcheck.sh
├── .github/workflows/            ← l0-static, l1-unit, l2-sift-lite, l3-goldens,
│                                   inspect-ai-evals, release, devpost-submit
└── packer/
    └── sift-microvm.pkr.hcl      ← L3 warm qcow2 from sift-2026.03.24.ova
```

Total target: ~140 first-class files at completion.

## 7. Forensic doctrine

This is the SANS-canonical body of knowledge an agent must internalise. Most of it is encoded in `verdict/playbooks/`, `verdict/knowledge/`, and `verdict/prompts/` — do not duplicate it in code.

### 7.1 Canonical first moves (per evidence type)

| Evidence type | First tool | Then |
|---------------|-----------|------|
| Memory dump | `windows.info` | `pslist` → `psscan` → `pstree` → `cmdline` → `dlllist` → `malfind` → `netscan` → `svcscan` → `handles` → `callbacks` |
| Disk image | `image_hash_verify` → `mmls` → `fsstat` | `fls` → `mftecmd` → `recmd` → `pecmd` → `hayabusa` → `plaso` → `bulk_extractor` |
| Triage zip (KAPE/Velociraptor) | `unzip` → registry hives | prefetch / amcache / shimcache → EVTX → MFT → carving |

### 7.2 DKOM / T1014 detection

Encoded in `verdict/playbooks/memory.yml`: after `pslist` and `psscan` complete, compute `set(psscan_pids) - set(pslist_pids)`. Non-empty difference → emit T1014 hypothesis automatically. v4.6 F4 made this a first-class playbook rule rather than a prompted suggestion.

### 7.3 Hunt Evil — 8 canonical Windows processes

`verdict/knowledge/hunt_evil.yml` carries baselines (parent, path, signing) for: `svchost`, `lsass`, `csrss`, `winlogon`, `services`, `wininit`, `explorer`, `smss`. Any deviation → `ProcessBaselineAnomaly` → MITRE **T1036.005** (Process Masquerading).

### 7.4 LOLBins discrimination

`verdict-skills/windows-triage/KNOWLEDGE.md` carries cmdline-shape catalog (sourced from LOLBAS): `regsvr32` (T1218.010), `rundll32` (T1218.011), `mshta` (T1218.005), `wmic` (T1047), `certutil` (T1140), `bitsadmin` (T1197), and more.

### 7.5 Tool-pair splits

- **Plaso:** split into `plaso_extract` + `psort_filter` MCP tools — never run as a single monolithic call (super-timeline is expensive; filter must be a separate, cacheable step).
- **Hayabusa:** split into `hayabusa_csv_timeline` + `hayabusa_filter` for the same reason.

### 7.6 Timestamp discipline

- All datetimes in schemas are `datetime` with `tzinfo=UTC`; serialised with trailing `Z`.
- `$STANDARD_INFORMATION` (`$SI`) is user-mode-stompable on NTFS — prefer `$FILE_NAME` (`$FN`). Any `$SI`-only timeline claim must carry `MFT_SI_STOMPABLE`.

### 7.7 Negative hypothesis discipline

- Each `InvestigationPlan` requires ≥1 negative hypothesis.
- Validator deny-list rejects degenerate phrasings (`cosmic`, `alien`, `nothing`, `not-relevant`, `n-a`).
- Negative hypotheses must have a non-None `mitre_technique` and a non-empty `artifact_families` list.
- Inspect AI scorer `negative_hypothesis_quality` fails CI if the score < 0.5.

## 8. Verifier strategies

`verdict/verification/strategy.py` defines a `VerifierStrategy` Protocol; the quorum node dispatches one of three concrete strategies based on locked mode.

| Strategy | Mode | Mechanism | Pass condition |
|----------|------|-----------|----------------|
| `CloudSelfConsistency` | `CLOUD` | n=3 samples with three blake3-keyed seeds at `temp=0.7` (NOT temp=0 — that collapses to n=1; this is v4.6 F1) | ≥2-of-3 agree → `VETTED_CLOUD` |
| `AirGapCrossEngine` | `AIRGAP` | Qwen3 + GLM-4.5-Air both execute | Jaccard ≥0.80 on `artifact_paths` AND identical `mitre_technique` → `VETTED_AIRGAP` |
| `DualLaneCrossEngine` | `DUAL` | cloud + both locals | cloud agrees with ≥1 local AND locals agree with each other → `VETTED_DUAL` |
| `UniversalSelfConsistency` (Chen 2023) | any | judge of last resort | Used when above strategies disagree, before declaring `CONTESTED`. |

Budgets:
- `pivot_max = 15` — cheap single-Hypothesis follow-ups inside `pivot_node`.
- `replan_max = 3` — full plan rewrites. **Iteration 4** routes to `unverifiable_finalize_node` which writes `Finding(status=UNVERIFIABLE)` + an `exhausted_replan` ledger event and calls `interrupt()` for human review.
- `tool_arg_retry_max = 2` — Pydantic-AI `args_validator` failures bounded; then `UNVERIFIABLE`.

## 9. Ledger discipline

`verdict/ledger/writer.py` + `verdict/ledger/chain.py`. The ledger is the chain-of-custody artifact a SANS judge will scrutinise.

- **Format:** JSONL append-only at `cases/<id>/ledger.jsonl`.
- **Chain integrity:** each `LedgerEntry.prev_entry_hash` references the prior entry's hash; `verdict validate <case_id>` walks the chain.
- **Three-tier ID hierarchy:** `case_id` (eternal) → `langfuse_trace_id` (per `graph.invoke`) → `langgraph_checkpoint_id` (per super-step). All three on every entry.
- **Examination-environment metadata:** `microsandbox_version`, `rootfs_sha256`, `tool_version`, `kernel_version` recorded per tool invocation. NIST SP 800-86 compliance.
- **Per-output-file hashes:** `output_files_sha256: dict[str, str]`.
- **HMAC signing:** every entry signed with HMAC key (TPM-backed or gpg-encrypted). Findings additionally signed over `(Finding + approver + timestamp)`.
- **Redaction discipline:** auth fields stripped from `payload` (and recorded in `payload_redactions`) **before** the entry is hashed and HMAC-signed. Order matters.
- **Write discipline:** `write() + fsync() + verify-readback` in `LedgerEmitter`. No buffered writes.
- **Cross-link:** Langfuse trace tree carries `case_id` + `ledger_entry_id`; ledger carries `langfuse_trace_id`. Bidirectional.

Ledger event types: `case_init`, `tool_call`, `finding`, `approval`, `rejection`, `mode_lock`, `comprehension_check`, `critique_verdict`, `pivot`, `exhausted_replan`, `evidence_hash_recheck`, `sandbox_failure`, `planner_cot`.

## 10. Key commands

### 10.1 Install / serve

```bash
# Microsandbox
curl -sSL https://get.microsandbox.dev | sh

# Bootstrap (three-credential-path detection)
bash scripts/install.sh

# Python env
uv sync

# SGLang serving (air-gap planner/executor)
sglang_server_v1 --model-path /path/to/qwen3 --tool-call-parser qwen3_xml --port 30000

# SGLang serving (verifier-only)
sglang_server_v1 --model-path /path/to/glm45  --tool-call-parser glm45  --port 30001

# Langfuse v2 self-host
docker-compose up -d
curl http://localhost:3000/api/public/health   # expect 200
```

### 10.2 CLI surface

```bash
verdict doctor                                  # pre-flight: API, SGLang, microsandbox, Langfuse, HMAC key
verdict mode                                    # show detected + locked mode
verdict init  <evidence_path> [--mode {cloud,airgap,dual}]
verdict resume   <case_id>
verdict reverify <case_id> --mode dual          # parallel re-run; non-mutating
verdict status
verdict ls
verdict show     <case_id>
verdict export   <case_id> [--format {json,csv,sigtools_triage}]
verdict validate <case_id>                      # ledger chain + HMAC integrity
verdict approve  <finding_id>                   # HMAC-signed approval w/ timestamp
verdict gc                                      # garbage-collect old cases
verdict health
```

### 10.3 Test

```bash
# Schema/playbook/knowledge gates (W1)
uv run --directory services/agent pytest tests/schemas/    -v
uv run pytest tests/playbooks/  -v
uv run pytest tests/knowledge/  -v

# Tool wrapper tests
uv run pytest tests/tools/test_vol_psscan.py -v

# Smoke tests (xfail markers expected)
pytest tests/smoke/

# Chaos (kill-9 resume — must be 100/100 zero-loss)
pytest tests/chaos/test_kill_9_resume.py -v

# Inference smoke (tool-call parse rate ≥ 98%)
python scripts/inference-smoke.py

# Full per-service run
bash scripts/run-all-tests.sh

# Per-mode end-to-end evals (THIS IS THE TEST SURFACE — see §3.10).
# Real Anthropic API / real SGLang / real microVMs / real .E01 + .mem fixtures.
# No mocks. If a service is down, the eval fails — that is the correct behaviour.
inspect eval inspect_ai/tasks/verdict_eval_cloud.py
inspect eval inspect_ai/tasks/verdict_eval_airgap.py
inspect eval inspect_ai/tasks/verdict_eval_dual.py
```

CI hard gate: hallucination rate ≤10% in every mode by end of week 4, else freeze tool count and spend week 5 on prompt/skill refinement. Every CI job runs against real backing services in ephemeral runners — there is no `MOCK=true` fast path.

### 10.4 Package + submit

```bash
bash scripts/package-devpost.sh                 # → dist/verdict-devpost-v1.zip
git tag v-submit && git push origin v-submit    # fires .github/workflows/devpost-submit.yml
```

## 11. Submission deliverables

### 11.1 The 15-item SANS judge checklist

Encoded in `docs/SANS_JUDGE_CHECKLIST.md`. Every item must demonstrably pass in the demo recording:

1. Image hash verified before opening evidence.
2. SANS-canonical first move (`windows.info` for memory; `mmls` + `fsstat` for disk).
3. `pslist` and `psscan` both run; divergence checked.
4. ≥2 artifact classes per execution claim, **named in rationale**.
5. Amcache caveat acknowledged when Amcache cited.
6. UTC `Z` suffix on all timestamps.
7. At least one pivot fired (response to a prior tool output, not part of initial plan).
8. Epistemic vocabulary spoken aloud (hypothesis / inferred / confirmed mapped to verdict status).
9. MITRE sub-techniques (`T1055.012`, never bare `T1055`).
10. Hunt Evil baseline catches a process-name masquerade.
11. Never asserts attribution ("Evidence consistent with X" not "X did this").
12. Ledger records tool version + rootfs SHA + microsandbox version per call.
13. End-to-end <20 minutes per case.
14. Agent gives up explicitly (`UNVERIFIABLE` + `interrupt()`) when it cannot resolve.
15. `planner_critique_node` fires visibly in the Langfuse trace.

### 11.2 Demo video (5-min cut, `docs/DEMO_SEQUENCE.md`)

- **0:00 – 0:30** cold open + architecture diagram flash.
- **0:30 – 1:30** cloud-only mode: n=3 with three distinct seeds, Langfuse sibling spans visible.
- **1:30 – 3:00** air-gap hero shot: DKOM divergence catch, Hunt Evil masquerade catch, Amcache caveat acknowledged, pivot fires, Qwen3-vs-GLM disagreement resolved, tcpdump TSI proof, kill-9 resume.
- **3:00 – 4:00** dual mode (new case, mode-locked): three-way verification.
- **4:00 – 5:00** architecture recap + accuracy tables.

### 11.3 Eight submission docs

1. `README.md` — problem statement, architecture, demo link, install, mode reference, license, contributing.
2. `docs/ARCHITECTURE.md`
3. `docs/BUILD.md` — exact build steps from a fresh SIFT VM, verified on a second VM.
4. `CONTRIBUTING.md` + `LICENSE` (MIT)
5. `docs/PRODUCTION_AUDIT.md` — v4 triage: what landed v1 vs v2.
6. `docs/SANS_JUDGE_CHECKLIST.md`
7. `docs/ACCURACY_REPORT.md` — per-mode hallucination rate, executor agreement, findings precision/recall, sub-technique precision, negative-hypothesis quality, step efficiency, contested-resolution rate, Qwen3-vs-GLM disagreement-correlation across 50 findings.
8. `docs/DEMO_SEQUENCE.md` — 5-min sequence with timing per beat.

## 12. Pointers (read these directly, do not summarise from memory)

| When you need… | Read |
|----------------|------|
| Canonical architecture, locked decisions | `docs/spec/VERDICT_AUDIT_v4.5.md` |
| Five tactical patches over v4.5 | `docs/spec/VERDICT_v4.6_SPEC_PLAN.md` |
| Sequencing, ownership, weekly acceptance gates, task IDs | `docs/spec/VERDICT_MASTER_BUILD_PLAN.md` |
| Why a particular DFIR validator or playbook entry exists | `docs/spec/VERDICT_AUDIT_v4.4.md` |
| Why mode-detect / verifier-strategy / checkpointing look the way they do | `docs/spec/VERDICT_AUDIT_v4.3.md` |
| Hackathon eligibility, judging, prizes | `docs/hackathon/RULES.md` |
| Hackathon overview + resource links | `docs/hackathon/OVERVIEW.md` |
| The upstream Claude Code config framework being extended | `protocol-sift/` |

When in doubt about precedence: **v4.6 patches > v4.5 architecture > v4.4 / v4.3 history.** Master plan defines *what* and *when*, not *what is*.

## 13. Working-mode reminders for Claude Code sessions

- This workspace is **not yet a git repo.** Initialising it (`git init`, `LICENSE`, `.gitignore`) is W1.A work — get user confirmation before doing it.
- The `docs/spec/` directory is the **canonical source** for VERDICT design. Do not edit those files; treat them as read-only specifications.
- The five forbidden destructive git operations (see §3.7) apply once the repo exists.
- New dependencies require a license check against §3.8 before installation.
- Any rule in §3 that you find yourself wanting to bend is almost certainly load-bearing — surface the conflict to the user instead of working around it.
- **No mocks (§3.10).** If a piece of code is hard to write because the underlying service isn't running, bring the service up — do not invent a mock. If you genuinely cannot bring it up in the current environment, stop and tell the user; do not paper over it.
- Hackathon submission is a hard deadline. **Jun 14 EOD** for the Devpost upload; do not slip silently.
