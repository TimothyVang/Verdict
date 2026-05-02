# CLAUDE.md — VERDICT (FIND EVIL! hackathon entry)

This file is the operating charter for any Claude Code session opened in this workspace. Read it end-to-end before touching code. The hard rules in §3 are load-bearing — violating them invalidates findings, breaks chain of custody, or fails the SANS judge rubric.

## 1. Project identity

**VERDICT** — an autonomous Windows DFIR / incident-response agent built for the SANS *FIND EVIL!* 2026 hackathon. It conducts digital investigations through a Plan-then-Execute LangGraph topology over the SANS SIFT Workstation, with cryptographic chain-of-custody, multi-mode (cloud / air-gap / dual) inference, and forensic discipline encoded at the schema and prompt layers.

**This is a full-stack, real, working tool. No mocks, no stubs, no fixtures-pretending-to-be-real-evidence, no placeholder implementations.** Every layer — planner, executors, microsandbox, SIFT tool wrappers, ledger, verifier strategies, CLI — is wired against real inference engines, real microVMs, real evidence files, and real SIFT binaries from day one. The test surface is end-to-end Inspect AI evals against real ground-truth disk/memory images, not a mock harness. See §3.10.

- **Hackathon:** https://findevil.devpost.com/
- **Submission deadline:** **Jun 14 2026 EOD** (Devpost upload buffer); **Jun 15 22:45 CDT** official.
- **Judging window:** Jun 19 – Jul 3 2026; winners ~Jul 8 2026.
- **Sponsor / judge:** SANS Institute; Rob T. Lee (CAIO).
- **Submission pack:** see §11 plus `docs/DEVPOST_COMPLIANCE.md` and the live page at https://findevil.devpost.com/.

VERDICT extends — but does not vendor — the upstream `protocol-sift/` Claude Code config framework cloned in this workspace. License is **MIT** (the hackathon allows MIT or Apache-2.0).

## 2. Authority chain (read in this order)

`docs/README.md` is the **wiki front door** — every doc under `docs/` is indexed there with role + when-to-read. Every doc under `docs/` (except the frozen `spec/` archive) also carries a one-line `> **Wiki:** [Index](README.md) · …` nav strip directly under its H1, so any page is one hop from the index and from its closest siblings. The table below is the load-bearing subset that governs runtime behavior and submission compliance.

### Entry points

| Doc | Role | When to consult |
|-----|------|-----------------|
| `README.md` | **Project entry point.** What VERDICT does, three modes, agent loop, three-layer immutability — at a glance. ASCII diagrams. | First read for any contributor. |
| `docs/README.md` | **Doc wiki index.** Every file under `docs/` with role, audience, when-to-read. | Before opening any other doc; as the navigational map. |
| `docs/TLDR.md` | ~5-min visual primer. Living, teammate-shareable. | Hand to a new human teammate. |

### Current authority (single sources of truth)

| Doc | Role | When to consult |
|-----|------|-----------------|
| `docs/ARCHITECTURE.md` | **Current authoritative architecture.** Supersedes everything in `docs/spec/`. Single source of truth for components, data flow, schemas, verifier strategies, threat model. | Default reference for any code or design question. |
| `docs/BUILD_PLAN.md` | **Execution sequencing.** 6-week / 75-teammate-day TDD plan with task IDs (W1.A.3.a, W1.B.7, …), ownership, hours, acceptance gates. | Pick your next task; use task IDs in commits; use weekly gates as the definition of done. |
| `docs/DEVPOST_COMPLIANCE.md` | **Submission rule-to-artifact mapping.** Every Devpost requirement traced to the file/commit that satisfies it. | Before any submission packaging. |

### Audits (cross-doc consistency)

| Doc | Role | When to consult |
|-----|------|-----------------|
| `docs/DOCS_ACCURACY_REPORT.md` | Cross-doc consistency audit (counts, labels, MITRE IDs, version pins, terminology). | When docs appear to contradict each other; before a major doc edit. |
| `docs/AGENTIC_WORKFLOW_REVIEW.md` | Sister audit: runtime LangGraph loop *and* dev TDD loop. Filtered to not overlap with the accuracy report. | When evaluating coherence between §3 hard rules and the runtime topology. |

### Engineering frameworks (scaffolding — *not* runtime authority)

These sit **below `BUILD_PLAN.md` and this `CLAUDE.md`**. They describe how dev tooling is wired; they do not extend the runtime topology and never override §3.

| Doc | Role | When to consult |
|-----|------|-----------------|
| `docs/AGENT_SWARM.md` | Build-side LLM swarm spec — conductor / worker / reviewer / auditor agents that take `BUILD_PLAN.md` task IDs and open PRs. The `swarm/` source tree is its executable skeleton. | Before reading anything under `swarm/`; before reviewing a PR authored by a `swarm:*` worker. |
| `docs/MCP_FRAMEWORK.md` | MCP server allowlist + credential-isolation discipline. Every entry in `.mcp.json` traces here. License-gated by §3.8; egress-gated by §3.9. | Before adding/removing an MCP server, or when reviewing `.mcp.json`. |
| `docs/SKILLS_FRAMEWORK.md` | How vendored skills under `.claude/skills/` compose into a Plan → TDD → subagent-driven-dev → Review → Commit pipeline. `verdict-house-rules` overlays §3 on upstream skill defaults. | Before authoring a workflow; before vendoring a new skill. |
| `docs/SKILLS_LICENSE_AUDIT.md` | Per-skill license audit log. Every artifact under `.claude/skills/` (and any future MCP, hook, vendored artifact) gets a row per §3.8. | Before vendoring anything new; when answering "is X license-clean?". |

### Hackathon context

| Doc | Role | When to consult |
|-----|------|-----------------|
| `docs/hackathon/RULES.md` | Official SANS *FIND EVIL!* 2026 rules, scraped from Devpost on 2026-05-02. Upstream of `DEVPOST_COMPLIANCE.md`. | Before any submission decision. |
| `docs/hackathon/OVERVIEW.md` | Hackathon overview + resource links (judge bios, prize structure, timeline). | Context-setting; not load-bearing. |

### Frozen archive

| Doc | Role | When to consult |
|-----|------|-----------------|
| `docs/spec/` (audit history) | Archive — v4.3 → v4.4 → v4.5 audits + v4.6 spec patches. **Reference only**, not authority. See `docs/spec/README.md` for what each captured. | Reading "why did we decide X" — never to override `ARCHITECTURE.md`. |

**Authority order when docs disagree:** Devpost rules → `docs/DEVPOST_COMPLIANCE.md` → `docs/ARCHITECTURE.md` → `docs/BUILD_PLAN.md` → this `CLAUDE.md` → `docs/spec/` archive. Code and lockfiles win over docs; if code is right and a doc is wrong, fix the doc, don't roll back the code.

**`protocol-sift/` is a git submodule** pinned to upstream `teamdfir/protocol-sift`. The two `CLAUDE.md` files inside it (`global/CLAUDE.md`, `case-templates/CLAUDE.md`) are upstream Claude Code framework templates, **not** Verdict authority — do not edit in place (it dirties the submodule). Verdict-side overrides go in this `CLAUDE.md` or in `.claude/skills/verdict-house-rules/SKILL.md`.

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

`Finding.caveats_acknowledged: list[CaveatID]` is enforced at the schema layer. Cite the artifact, acknowledge the caveat. Caveat triggers are keyed by `Finding.artifact_classes` membership unless otherwise noted; `LOGON_TYPE_3_VS_10` is the named exception (triggered by `EVTX_4624` artifact_class AND the `EvtxRecord.LogonType` field equaling 3 or 10). The seven Tier-1 caveats (encoded in `verdict/schemas/caveat_id.py` and `verdict/prompts/examiner_caveats.md`):

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
- `verdict resume <case_id>` reads the original mode and refuses to advance if the current `detect_mode()` differs. On mismatch it raises `ModeLockedError`, exits 2, and prints to stderr: `Case {case_id} was initialized in mode={original_mode}; current environment is mode={detected_mode}. To re-run under the new mode, use: verdict reverify {case_id} --mode {detected_mode}`.
- Mode change is via `verdict reverify --mode <m>` only — that creates a **parallel verdict chain**, never mutating the original.
- Cloud-only mode requires `ANTHROPIC_API` reachable; air-gap requires `SGLANG_BASE_URL` reachable; dual requires both. `verdict doctor` is the pre-flight.

### 3.5 MITRE sub-technique precision

- Emit `T1055.012`, never bare `T1055`, when the sub-technique is determinable.
- Regex enforced on `Hypothesis.mitre_technique` and `Finding.mitre_technique`: `^T\d{4}(\.\d{3})?$`.
- Inspect AI scorer `mitre_subtechnique_precision` fails CI if the planner emits a parent technique when the sub was determinable.
- Sub-technique precision applies equally to positive and negative hypotheses. Bare technique is acceptable only when no sub-technique exists upstream (e.g., `T1014` Rootkit, `T1106` Native API); the regex `^T\d{4}(\.\d{3})?$` enforces shape but not sub-technique-required.

### 3.6 Epistemic vocabulary

- Verdict statuses are exactly: `VETTED_CLOUD`, `VETTED_AIRGAP`, `VETTED_DUAL`, `CONTESTED`, `UNVERIFIABLE`, `EXHAUSTED_REPLAN`. No others. This list is the canonical `VerdictStatus` enum; `ARCHITECTURE.md` §1 and `DEVPOST_COMPLIANCE.md` derive from it. **Engine-quorum verdict** (the immediate output of a `VerifierStrategy`) and **case verdict** (the persisted `Finding.status`) share the same enum but live on different objects: a `VerifierStrategy` returns `(VETTED_*, CONTESTED, UNVERIFIABLE)` per finding, while finalize_node maps `EXHAUSTED_REPLAN` from the replan budget. `Finding.review_state` (separate field, values `DRAFT / APPROVED / REJECTED`) tracks human approval state and is orthogonal to `VerdictStatus`.
- Findings phrase attribution as **"evidence consistent with X"** — never "X did this". Attribution is for the human IR lead, not the agent.
- Negative hypotheses are required (≥1 per plan). The `_negative_hypothesis_quality` validator deny-lists `cosmic`, `alien`, `nothing`, `not-relevant`, `n-a`. A negative hypothesis must have a non-None `mitre_technique` and non-empty `artifact_families`.
- `Finding.status = UNVERIFIABLE` is a **first-class outcome**, not a failure to be hidden. The 15-item judge rubric specifically rewards explicit UNVERIFIABLE.

### 3.7 TDD + Conventional Commits

- Failing test → RED → implement → GREEN → **one commit per task ID**.
- Commit message format: `feat(scope): summary [W#.#.#]` — task ID is required. Example: `feat(schema): add ArtifactClass enum [W1.B.1]`.
- **Never** `--no-verify`, **never** `--no-gpg-sign`, **never** `git commit --amend`. Pre-commit hook failure means fix and re-stage; do not bypass.
- Allowed commit prefixes: `feat`, `fix`, `test`, `chore`, `docs`, `refactor`. No others without RFC.
- **No Claude Code watermarks** in any commit message, PR title, PR body, or generated file. Do not append `Co-Authored-By: Claude …`, `🤖 Generated with [Claude Code]`, or any equivalent attribution line. This overrides the built-in Claude Code commit/PR templates. Authorship is recorded via git committer + GPG signature only.

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

9-node LangGraph state machine: **planner → planner_critique (CoVe) → comprehension_gate → executor_fanout (n=4; each branch composed of DenyRuleWrapper / ToolExecutor / LedgerEmitter) → pivot (≤15) → quorum → replan (≤3) → unverifiable_finalize → finalize**.

Three operational modes, auto-detected at `case_init` and **locked**:

- `CLOUD` — Claude Code planner + local Qwen3 executor + `CloudSelfConsistency` (n=3, blake3-keyed seeds, temp=0.7).
- `AIRGAP` — Qwen3 planner+executor + `AirGapCrossEngine` (Qwen3 vs GLM-4.5-Air, Jaccard ≥ 0.80).
- `DUAL` — parallel cloud+airgap lanes + `DualLaneCrossEngine` (cloud + ≥1 local; locals agree).

Three-layer immutability defense: (1) Claude `PreToolUse` hook (best-effort, per #33106/#37210); (2) LangGraph `DenyRuleWrapper` (architectural guarantee, all modes); (3) microsandbox read-only `/evidence` mount + `noexec` (kernel-enforced).

→ Full topology, mode tables, defense-in-depth rationale: **`docs/ARCHITECTURE.md` §1–§3**.

## 5. Tech stack (one line each)

Python 3.11 (`uv` / `pytest` / `ruff`); Rust 1.88 for FastMCP 3.x; Node 20 (pnpm, deferred v2). Inference: SGLang primary, vLLM fallback; models Qwen3-30B-A3B-Thinking-2507 (Apache-2.0) + GLM-4.5-Air (MIT, verifier only). Orchestration: LangGraph + SqliteSaver (WAL+fsync). Schemas: Pydantic v2 + Pydantic-AI. Sandbox: Microsandbox (libkrun, ~200 ms cold). Hashing: blake3. Observability: Langfuse v2 self-host + OpenLLMetry. Eval: Inspect AI. CI: GitHub Actions.

→ Full version pins, license notes, hard-NO list: **`docs/ARCHITECTURE.md` §7** (and §3.8 above for forbidden deps).

## 6. Target repo layout

Today the workspace holds docs only — code scaffolding is **W1.A** of `docs/BUILD_PLAN.md`. Active layout:

```
Verdict/
├── CLAUDE.md  README.md  CONTRIBUTING.md  SECURITY.md  LICENSE  .env.example
├── docs/
│   ├── ARCHITECTURE.md  BUILD_PLAN.md  DEVPOST_COMPLIANCE.md  DOCS_ACCURACY_REPORT.md
│   └── spec/           ← frozen audit archive (01..05 + README)
├── downloads/          ← SIFT OVA, evidence samples (gitignored)
└── protocol-sift/      ← upstream submodule
```

Code surface to land in W1+ (target ~140 files; full tree in `docs/BUILD_PLAN.md` §file-layout):

```
verdict/
├── runtime/        schemas/        verification/    planning/
├── playbooks/      knowledge/      graph/wrappers/  tools/vol3/
├── sandboxes/      ledger/         observability/   cli/         adapters/
verdict-skills/  tests/{schemas,graph,tools,chaos,smoke,e2e,…}
inspect_ai/{tasks,scorers,ground_truth/case_00{1..3}_*}
scripts/  .github/workflows/  packer/
```

## 7. Forensic doctrine (one-paragraph summaries)

The SANS-canonical knowledge an agent must internalise. Encoded in `verdict/playbooks/`, `verdict/knowledge/`, `verdict/prompts/` — never duplicated in narrative code comments. Full discipline (with rationale, validators, schema field references): **`docs/ARCHITECTURE.md` §4**.

- **Canonical first moves.** Memory → `windows.info`. Disk → `image_hash_verify` → `mmls` → `fsstat`. Triage zip → registry hives first.
- **DKOM / T1014.** `set(psscan_pids) - set(pslist_pids)` non-empty → emit T1014 hypothesis. First-class playbook rule (v4.6 F4), not a prompt suggestion.
- **Hunt Evil 8.** Baselines for `svchost`, `lsass`, `csrss`, `winlogon`, `services`, `wininit`, `explorer`, `smss`. Deviation → `ProcessBaselineAnomaly` → **T1036.005**.
- **LOLBins.** Cmdline-shape catalog (LOLBAS-sourced) maps each binary to its T1218.* sub-technique.
- **Tool-pair splits.** `plaso_extract` + `psort_filter`; `hayabusa_csv_timeline` + `hayabusa_filter`. Never monolithic.
- **Timestamps.** UTC + trailing `Z`. Prefer `$FN` over stompable `$SI`; `$SI`-only claims carry `MFT_SI_STOMPABLE`.
- **Negative hypotheses.** ≥1 per plan. Deny-list rejects `cosmic`/`alien`/`nothing`/`not-relevant`/`n-a`. Must have `mitre_technique` + non-empty `artifact_families`. Inspect AI fails CI if score < 0.5.

## 8. Verifier strategies (one-line each)

`verdict/verification/strategy.py` — `VerifierStrategy` Protocol; quorum dispatches per locked mode.

- `CloudSelfConsistency` — n=3 with three blake3-keyed seeds at `temp=0.7` (v4.6 F1; **never** temp=0, that collapses to n=1). ≥ 2-of-3 → `VETTED_CLOUD`.
- `AirGapCrossEngine` — Qwen3 + GLM-4.5-Air both execute. Jaccard ≥ 0.80 on `artifact_paths` AND identical `mitre_technique` → `VETTED_AIRGAP`.
- `DualLaneCrossEngine` — cloud + both locals. Cloud agrees with ≥1 local AND locals agree → `VETTED_DUAL`.
- `UniversalSelfConsistency` (Chen 2023) — judge of last resort before declaring `CONTESTED`.

**Budgets:** `pivot_max=15`; `replan_max=3` (iteration 4 → `unverifiable_finalize_node` → `Finding(status=UNVERIFIABLE)` + `interrupt()` for human); `tool_arg_retry_max=2`.

→ Strategy details, dispatch logic, scorer wiring: **`docs/ARCHITECTURE.md` §1, §4**.

## 9. Ledger discipline

`verdict/ledger/writer.py` + `chain.py`. The ledger is the chain-of-custody artifact a SANS judge will scrutinise.

- JSONL append-only at `cases/<id>/ledger.jsonl`. `prev_entry_hash` chains entries; `verdict validate <case_id>` walks them.
- Three-tier IDs on every entry: `case_id` → `langfuse_trace_id` → `langgraph_checkpoint_id`.
- Per-call examination metadata: `microsandbox_version`, `rootfs_sha256`, `tool_version`, `kernel_version` (NIST SP 800-86).
- Per-output-file `output_files_sha256: dict[str, str]`.
- HMAC-signed entries (TPM-backed or gpg-encrypted key); Findings additionally signed over `(Finding + approver + timestamp)`.
- Redaction strips auth fields **before** hashing/signing — order matters.
- `write() + fsync() + verify-readback` in `LedgerEmitter`. No buffered writes.
- Bidirectional cross-link with Langfuse trace tree via `trace_id`.

Event types: `case_init`, `tool_call`, `finding`, `approval`, `rejection`, `mode_lock`, `comprehension_check`, `critique_verdict`, `pivot`, `exhausted_replan`, `evidence_hash_recheck`, `sandbox_failure`, `planner_cot`.

→ Schema fields, validation flow, key-management decisions: **`docs/ARCHITECTURE.md` §5**.

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

## 12. Pointers (read directly, do not summarise from memory)

`docs/README.md` is the wiki index — every doc under `docs/` is listed there. The pointers below are the most-asked questions.

| When you need… | Read |
|----------------|------|
| The doc map (what lives where, who reads what) | `docs/README.md` |
| 5-min visual primer for a new teammate | `docs/TLDR.md` |
| Architecture, schemas, ledger, threat model, tool surface | `docs/ARCHITECTURE.md` |
| Sequencing, ownership, weekly acceptance gates, task IDs | `docs/BUILD_PLAN.md` |
| Submission rule-to-artifact mapping, judge-facing checklist | `docs/DEVPOST_COMPLIANCE.md` |
| Cross-doc consistency audit + critical-fix log | `docs/DOCS_ACCURACY_REPORT.md` |
| Agentic-workflow audit (runtime + dev TDD loop) | `docs/AGENTIC_WORKFLOW_REVIEW.md` |
| Build-side LLM swarm spec (consumer of `BUILD_PLAN.md` task IDs) | `docs/AGENT_SWARM.md` (executable in `swarm/`) |
| MCP server allowlist + credential isolation | `docs/MCP_FRAMEWORK.md` (allowlist in `.mcp.json`) |
| Vendored skill stack composition + house-rules overlay | `docs/SKILLS_FRAMEWORK.md` (stack in `.claude/skills/`) |
| License audit for vendored skills/hooks/MCPs | `docs/SKILLS_LICENSE_AUDIT.md` |
| Audit-history rationale ("why was X decided?") | `docs/spec/` (`01..04` + `README.md`) |
| Official hackathon rules (scraped) | `docs/hackathon/RULES.md` |
| Hackathon overview + resource links | `docs/hackathon/OVERVIEW.md` + https://findevil.devpost.com/ + `downloads/README.md` |
| Upstream Claude Code config framework (read-only submodule) | `protocol-sift/` |

**Authority order when docs disagree:** Devpost rules → `DEVPOST_COMPLIANCE.md` → `ARCHITECTURE.md` → `BUILD_PLAN.md` → this `CLAUDE.md` → `docs/spec/`. Code wins over docs; if code is right, fix the doc.

## 13. Working-mode reminders for Claude Code sessions

- The `docs/spec/` directory is the **frozen audit archive**. Do not edit; cite from `ARCHITECTURE.md`.
- The five forbidden destructive git operations (see §3.7) apply once the repo exists.
- New dependencies require a license check against §3.8 before installation.
- Any rule in §3 that you find yourself wanting to bend is almost certainly load-bearing — surface the conflict to the user instead of working around it.
- **No mocks (§3.10).** If a piece of code is hard to write because the underlying service isn't running, bring the service up — do not invent a mock. If you genuinely cannot bring it up in the current environment, stop and tell the user; do not paper over it.
- Hackathon submission is a hard deadline. **Jun 14 EOD** for the Devpost upload; do not slip silently.
