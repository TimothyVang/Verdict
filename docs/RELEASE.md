# VERDICT - Release and Submission Guide

> **Wiki:** [Index](README.md) · [Architecture](ARCHITECTURE.md) · [Build Plan](BUILD_PLAN.md) · [Devpost](DEVPOST_COMPLIANCE.md) · root [CLAUDE.md](../CLAUDE.md)

**Status:** Living release guide. Replace TODO cells only after real evidence, real services, and measured evals. Latest local readiness snapshot: 2026-05-09 on the Windows/WSL development host; second-VM and Inspect AI metrics remain unfilled until separately measured.
**Authority:** Consolidates W5.E.1, W6.A.1, W6.B.1, W6.C.3, W6.C.5, W6.C.8, W6.C.9, W6.C.10, and W6.D.1 release artifacts unless a separate doc is explicitly reintroduced.

---

## Scope

VERDICT v1 is Windows DFIR depth-first. It focuses on memory images, disk images, Windows event/log artifacts, registry artifacts, and triage bundles.

In scope:

- Windows memory forensics with Volatility 3.
- Windows disk and filesystem artifacts through Sleuth Kit and EZ Tools.
- Windows execution and persistence artifacts: Prefetch, Amcache, ShimCache, registry run keys, scheduled tasks, WMI, EVTX/Sysmon.
- DKOM/T1014 detection through `pslist` and `psscan` divergence.
- Hunt Evil process-baseline anomalies and LOLBin command shapes.

Deferred to v2:

- macOS and Linux triage.
- Win11-specific SRUM/ETW/Cortana/Search Index depth.
- ESXi forensics.
- Network forensics with Zeek, Suricata, or tshark.
- Examiner-suite imports such as Axiom XML, EnCase EWF workflows, and FTK CSV.
- Live endpoint collection beyond documented adapter experiments.

## Build And Reproducibility

Canonical build target: SANS SIFT Workstation on Linux with KVM.

| Component | Requirement |
|---|---|
| CPU | 8 vCPU minimum |
| RAM | 32 GB minimum |
| Disk | 200 GB minimum |
| Virtualization | KVM enabled and visible to the guest |
| OS | SIFT Workstation VM or Ubuntu 22.04/24.04 compatible SIFT host |
| Python | 3.11 via `uv` |
| Rust | 1.88.0 |
| Node | 20.x LTS |

Fresh VM procedure:

1. Import the SIFT OVA into the local hypervisor.
2. Allocate 8 vCPU, 32 GB RAM, 200 GB disk, and nested virtualization/KVM.
3. Confirm `uname -a`, `python3 --version`, and `test -e /dev/kvm`.
4. Clone VERDICT and run `uv sync --all-extras`.
5. Run `uv sync --all-extras` and `uv run pytest`.

Forensic smoke checks: `vol3 -h`, `mmls -V`, `fls -V`, `fsstat -V`.

Microsandbox smoke check: `msb run ubuntu:22.04 -- cat /etc/os-release`.

Air-gap and dual mode require SGLang endpoints for Qwen3 and GLM:

| Model | Endpoint | Parser | Verification status |
|---|---|---|---|
| Qwen3-30B-A3B-Thinking-2507 | `http://localhost:30000/v1` | TODO | TODO |
| GLM-4.5-Air | `http://localhost:30001/v1` | TODO | TODO |

Second-VM verification table:

| Check | Result | Notes |
|---|---|---|
| Clone and bootstrap | TODO | TODO |
| `uv run pytest` | TODO | TODO |
| SIFT tool smoke checks | TODO | TODO |
| Microsandbox smoke check | TODO | TODO |
| `verdict doctor` | TODO | TODO |

Current local readiness snapshot, captured 2026-05-09 after `wsl.exe --shutdown` recovered WSL/Microsandbox availability. This is dev-host evidence only; it does not replace the second-VM table above.

| Check | Result | Evidence |
|---|---|---|
| `uv run verdict doctor` | PASS | `ready=true`, mode `CLOUD`, Microsandbox via WSL available, pinned image present, SIFT tools `fls`, `fsstat`, `icat`, `mmls`, `vol3.info`, `vol3.pslist`, and `vol3.psscan` available. SGLang not configured/reachable, so air-gap and dual remain unproven. |
| `uv run verdict health` | PASS | `status=ok`, no blockers, mode `CLOUD`, Microsandbox and SIFT tools available, `sglang_reachable=false`. |
| `uv run python scripts/build_check.py --tier fast --json --state-path build/autoresearch-build-check-state.json` | PASS | Required files, policy config, no-mocks scan with policy-fixture exclusion, import check, `ruff check src tests scripts`, and `pytest -q` all passed. Test summary: `204 passed, 2 skipped, 1 xfailed`. |
| `uv run verdict package-check` | PASS | `ok=true`, `missing=[]`, `invalid=[]`. |
| `uv run verdict validate case_001` | PASS | `ledger valid for case_001`. |
| `uv run verdict validate case_002` | PASS | `ledger valid for case_002`. |
| `uv run verdict validate case_003` | PASS | `ledger valid for case_003`. |

## CLI And Persistence Contracts

Planned v1 command surface. Commands remain documentation-only until their implementation task lands; incomplete commands must not be exposed as callable placeholders.

| Command | Purpose | Status |
|---|---|---|
| `verdict init <evidence>` | Create case, hash evidence, detect/lock mode | Implemented locally; rejects unavailable requested modes and invalid case IDs |
| `verdict investigate <evidence> [--export-dir <path>]` | Autonomous evidence-to-report run: init, case workflow, ledger validation, execution-log/report/manifest exports, and human approval boundary | Implemented locally; local tooling blockers become auditable `UNVERIFIABLE` conclusions |
| `verdict run-case <case_id>` | Run the canonical local real-tool case workflow for an initialized case | Implemented locally; unsupported evidence returns `UNVERIFIABLE` without inventing findings |
| `verdict run-tool <case_id> <tool>` | Run one registered real SIFT tool through the configured sandbox path | Implemented locally; requires Microsandbox/tool prerequisites |
| `verdict resume <case_id>` | Verify mode lock before resuming a case | Implemented locally; rejects mode mismatch and invalid case IDs |
| `verdict reverify <case_id> --mode <mode>` | Create parallel verification chain | Implemented locally; writes a separate reverify case chain without mutating the source case |
| `verdict status <case_id>` | Show current graph/checkpoint status | Implemented locally; prints machine-readable case, manifest, ledger, and mode summary |
| `verdict ls` | List local cases | Implemented locally; lists readable case summaries from the configured case directory |
| `verdict show <case_id>` | Render findings/chains | Implemented locally; prints a human-readable case and evidence summary |
| `verdict export <case_id>` | Export report, JSONL, PDF, or execution logs | Implemented locally; package-check covers generated execution logs and PDFs |
| `verdict validate <case_id>` | Verify ledger HMAC/chain and hashes | Implemented locally; case_001, case_002, and case_003 pass on 2026-05-09 |
| `verdict mode` | Explain detected mode and prerequisites | Implemented locally; prints detected operating mode |
| `verdict gc` | List local cases eligible for manual cleanup | Implemented locally; non-destructive list-only behavior |
| `verdict health` | Machine-readable health endpoint/check | Implemented locally; `status=ok` on 2026-05-09 |
| `verdict doctor` | Human pre-flight for dependencies/secrets/services | Implemented locally; `ready=true` on 2026-05-09 for cloud-mode dev host |
| `verdict approve <case_id> <finding_id> --approver <name>` | HMAC-sign human approval for the latest non-superseded finding entry | Implemented locally; nonexistent or superseded findings are rejected without appending approval entries |

Export formats:

| Format | Output | Required fields |
|---|---|---|
| `jsonl` | Raw or normalized ledger events | case/checkpoint/trace IDs |
| `html` | Analyst report for human review | executive summary, timeline, findings, citations, evidence figures, caveats, evidence hashes |
| `pdf` | Professional DFIR writeup PDF for final human review | executive assessment, key findings, evidence/citation summary, superseded-run history, ledger evidence appendix, chain-of-custody appendix |
| `execution-logs` | Devpost judge artifact | timestamps, agent/tool events, token usage when present, finding-to-tool-call traceability |

`verdict investigate` writes `manifest.json` beside its execution log and analyst report; the manifest records the source ledger path/hash plus exported artifact paths and SHA-256 values for operator handoff provenance.

Disk-image investigation stops with `UNVERIFIABLE` and `disk_partition_offset_not_found` when `mmls` runs but does not produce a supported filesystem partition offset, preventing offsetless `fsstat`/`fls` from masking an unknown partition boundary.

Checkpointing: each chain uses a LangGraph thread ID and per-case SQLite checkpoint store with WAL and `synchronous=FULL`. `resume` continues the same mode-locked chain; `reverify` creates a parallel chain.

Schema migration policy: persisted top-level schemas carry `schema_version: int = 1` in v1. Breaking changes must add `migrations/v{N}_to_v{N+1}.py`, tests over prior-version fixtures, a release-note entry in this guide, and a refusal path for unsupported newer schemas. Migrations never rewrite evidence; they only transform persisted VERDICT metadata and ledger-derived exports.

## Threat Model

VERDICT assumes adversaries may control evidence content, tool output bytes, local host access, or network availability. The v1 security goal is forensic discipline and chain-of-custody preservation, not perfect compromise containment.

| Surface | Threat | Mitigations | Residual risk |
|---|---|---|---|
| Insider/operator | Operator attempts to mutate evidence, bypass mode lock, or hide contested findings | Read-only `/evidence`, evidence hash rechecks, append-only HMAC ledger, mode-locked resume, explicit `CONTESTED`/`UNVERIFIABLE` statuses | Host root can still destroy local working copies; custody relies on external evidence preservation too |
| Prompt injection from evidence | Malicious filenames, logs, registry values, or document text instruct the agent to ignore rules | Tool wrappers sanitize output flags, prompts include examiner caveats and epistemic vocabulary, graph wrappers deny evidence writes, findings require multi-artifact corroboration | Novel prompt-injection strings may still influence planner priorities; verifier lanes and human review remain required |
| Malicious tool output | Parser confusion, forged stdout, or adversarial artifacts mislead quorum | Raw stdout/stderr hashes, `ToolOutput` schema, parsed artifact lists, invocation hashes, quorum disagreement handling, ledger traceability | A trusted SIFT binary bug can still produce plausible wrong artifacts; cross-tool corroboration limits but does not eliminate this |
| External attacker/service outage | Cloud API rate limits, SGLang crashes, Langfuse outages, or OpenCTI/network failures disrupt investigation | `verdict doctor`, failure-mode table, explicit `UNVERIFIABLE`, Langfuse fail-open to local ledger, air-gap and dual modes | Availability failures can prevent verification; v1 reports uncertainty instead of inventing findings |

Microsandbox escape is an accepted v1 residual risk. Defense in depth comes from read-only evidence mounts, short-lived per-tool sandboxes, output hashing, and host-side ledger verification, but a kernel or hypervisor escape remains outside the v1 containment guarantee.

## Accuracy And Evidence

Current eval gate status: `inspect_ai/tasks/verdict_eval_{cloud,airgap,dual}.py` exists only as
fail-closed scaffolding. Each task refuses to construct an eval unless every required case under
`inspect_ai/ground_truth/` contains real evidence and then refuses to proceed until the task is
wired to real VERDICT execution. `.github/workflows/eval-hallucination-gate.yml` checks that the
three evaluator files and real `inspect_ai/scorers/hallucination_rate.py` scorer exist before it
runs `verdict doctor` and per-mode Inspect AI evals. Missing evaluator/scorer files fail with
`scorer_not_implemented`; missing real evidence or unwired mode tasks fail closed rather than
publishing a fake passing hallucination score. The hallucination scorer itself fails closed unless
the proof run contains a `Status: PASS` summary, a schema-valid `investigation-plan.json` with a
matching case ID and negative hypotheses, a `validation.log` recording schema validation success,
a non-empty `cloud-agent-response.raw.txt` model-output artifact, and a non-empty `ledger.jsonl`
proof ledger.

Per-mode metrics:

The table below is still TODO because no Inspect AI per-mode eval run has been captured in `build/inspect-ai/` yet. The local case-run table that follows is real CLI evidence, but it is not a substitute for measured hallucination/precision/recall metrics.

| Mode | Cases | Hallucination rate | Findings precision | Findings recall | MITRE sub-technique precision | Contested resolution rate |
|---|---:|---:|---:|---:|---:|---:|
| cloud | TODO | TODO | TODO | TODO | TODO | TODO |
| airgap | TODO | TODO | TODO | TODO | TODO | TODO |
| dual | TODO | TODO | TODO | TODO | TODO | TODO |

Measured local case-run status, captured from `verdict status`, `verdict validate`, and regenerated `submission/` artifacts on 2026-05-09:

| Case | Mode | Evidence items | Ledger events | Case conclusion | Primary rationale | Validation/report artifacts |
|---|---|---:|---:|---|---|---|
| `case_001` | CLOUD | 2 | 10 | `EVIL_FOUND` | Evidence consistent with `rundll32` LOLBin execution; PowerShell transcript invocation corroborated by Prefetch listing evidence. | Ledger valid; `submission/execution-logs/case_001.jsonl`; `submission/reports/case_001.html`; `submission/reports/case_001.pdf`. |
| `case_002` | CLOUD | 2 | 60 | `EVIL_FOUND` | Evidence consistent with hidden process activity through `psscan` PID(s) absent from `pslist`. | Ledger valid; `submission/execution-logs/case_002.jsonl`; `submission/reports/case_002.html`; `submission/reports/case_002.pdf`. |
| `case_003` | CLOUD | 4 | 61 | `EVIL_FOUND` | Evidence consistent with hidden process activity through `psscan` PID(s) absent from `pslist`, including PIDs 7132, 9936, 10368, and 11936. | Ledger valid; `submission/execution-logs/case_003.jsonl`; `submission/reports/case_003.html`; `submission/reports/case_003.pdf`. |

Human review remains required before treating any generated PDF/HTML report as final. The report artifacts are evidence binders for review, not a replacement for examiner judgment.

Scorer results:

| Scorer | Cloud | Air-gap | Dual | Notes |
|---|---:|---:|---:|---|
| `step_efficiency` | TODO | TODO | TODO | TODO |
| `findings_precision` | TODO | TODO | TODO | TODO |
| `findings_recall` | TODO | TODO | TODO | TODO |
| `mitre_subtechnique_precision` | TODO | TODO | TODO | TODO |
| `negative_hypothesis_quality` | TODO | TODO | TODO | TODO |

Datasets:

| Dataset | Source URL | License/usage | Hash | Used for |
|---|---|---|---|---|
| NIST CFReDS Hacking Case | TODO | TODO | TODO | Disk artifact validation |
| Honeynet ransomware image | TODO | TODO | TODO | Final demo case |
| Case 001 lol-bins | Engineered real disk and memory artifacts under `inspect_ai/ground_truth/case_001_lolbins/` | Project-generated | Manifest hash `1fe226a2db026306aec3dbb80f5a81e42c0fcc8a57d026b9d6f9f4f7ad162217` | LOLBin and masquerade evaluation |
| Case 002 credential theft | Engineered real disk and memory artifacts under `inspect_ai/ground_truth/case_002_credtheft/` | Project-generated | Manifest hash `1bfc93f3cd83e2b536e4b6e686225470aac6719737ebf77dc982f2ee07a165f5` | Credential-access evaluation |
| Case 003 ransomware | Engineered real disk and memory artifacts under `inspect_ai/ground_truth/case_003_ransomware/` | Project-generated | Manifest hash `0aed9f7fade317877d81c455cf1ff9a8cefcbac6b33c8dcc7d6cb277f8091dc3` | Demo and recovery flow |

Known errors stay visible in the final report. `disagreement_correlation`: TODO.

## Demo Checklist

v0 demo scope is cloud-only Claude Agent SDK. SGLang, GPU-backed air-gap mode, and dual mode are postponed until the Claude path produces repeatable proof artifacts.

Cloud proof artifacts live under `proof/runs/<timestamp>/`; timestamp collisions allocate
deterministic suffixes such as `<timestamp>-2`. A successful run includes
`cloud-agent-response.raw.txt`, `investigation-plan.json`, `validation.log`, `ledger.jsonl`,
`run-summary.md`, plus `screenshots/` and `video/` folders for visual review.
Blocked cloud proof runs write `service-checks.log` and `run-summary.md` with the requested
`case_id`, plus a `cloud_proof_blocked` ledger entry that preserves the same case ID for
auditability.

Current cloud proof run, captured 2026-05-09: `proof/runs/20260509T223520Z` passed with `InvestigationPlan` schema validation, 3 positive hypotheses, 3 negative hypotheses, HMAC ledger entry `cloud_proof_plan_validated`, and screenshot artifact `screenshots/browser-cloud-proof-summary.png`. This is a cloud-planning proof artifact only; it does not replace full Inspect AI per-mode eval metrics.

Five-minute cut:

| Time | Segment | Required beat |
|---|---|---|
| 0:00-0:30 | Cold open | Problem, evidence hash, mode table flash |
| 0:30-1:30 | Cloud mode | Claude lane, 3-sample self-consistency, `VETTED_CLOUD` wording |
| 1:30-3:00 | Air-gap mode | DKOM divergence, Hunt Evil masquerade, Amcache caveat, pivot vs replan, self-correction |
| 3:00-4:00 | Dual mode | Cloud/local cross-check and `VETTED_DUAL` |
| 4:00-5:00 | Recap | Six judging criteria, ledger-to-trace drilldown, build docs |

Judge dry-run checklist:

- [ ] Evidence image hash is verified on screen.
- [ ] First move follows the SANS-canonical playbook.
- [ ] `pslist` plus `psscan` divergence is shown for DKOM/T1014.
- [ ] Execution claims cite at least two artifact classes.
- [ ] Amcache LastModified caveat is acknowledged.
- [ ] Timestamps are UTC with `Z`.
- [ ] Pivot is shown separately from replan.
- [ ] Epistemic vocabulary distinguishes vetted, contested, and unverifiable.
- [ ] MITRE sub-techniques are used when determinable.
- [ ] Hunt Evil masquerade catch is visible.
- [ ] Attribution is not asserted without evidence.
- [ ] Ledger records examination-environment metadata.
- [ ] End-to-end case run stays under 20 minutes.
- [ ] `UNVERIFIABLE` is explicit when evidence/tooling cannot support a claim.
- [ ] `planner_critique` visibly fires before execution.

## Production Audit And Novelty

Landed in v1:

- Mode-aware verifier gateway.
- Plan-then-execute LangGraph topology.
- Schema-enforced evidence and finding discipline.
- HMAC-signed append-only ledger.
- Three-layer evidence immutability design.
- Langfuse/OpenLLMetry observability.
- SqliteSaver checkpointing design.
- Windows DFIR playbook scope.

New work built for this submission:

- Mode-aware verifier gateway with cloud, air-gap, and dual operation.
- Three-layer evidence immutability design.
- Schema-enforced forensic corroboration and caveat acknowledgment.
- Planner critique, comprehension gate, pivot, replan, and unverifiable-finalize flow.
- DKOM/T1014 detection through process-list divergence.
- Hunt Evil and LOLBin knowledge integration.
- Custom Inspect AI scorers and disagreement-correlation reporting.
- Devpost-oriented execution-log export and audit documentation.

Pre-existing open source used:

| Component | Role | License/source to verify |
|---|---|---|
| SIFT Workstation | Forensic base environment | TODO |
| Volatility 3 | Memory forensics | TODO |
| Hayabusa | Windows event timeline | TODO |
| plaso | Timeline extraction | TODO |
| EZ Tools | Windows artifacts | TODO |
| Microsandbox | Per-tool microVM isolation | TODO |
| SGLang | Local inference serving | TODO |
| vLLM | Local inference fallback | TODO |
| LangGraph | Runtime graph | TODO |
| Langfuse | Trace UI | TODO |
| OpenLLMetry | OTel instrumentation | TODO |
| Inspect AI | Evaluation harness | TODO |
| Pydantic / Pydantic-AI | Schemas and typed retries | TODO |
| FastMCP | MCP gateway | TODO |
| NeMo Guardrails | Rails | TODO |
| Claude Agent SDK / Claude Code | Cloud execution lane | TODO |
| blake3 | Invocation/ledger hashing | TODO |

## Packaging

`scripts/package-devpost.sh --check` validates the required release bundle. `--output dist/verdict-devpost-v1.zip` writes the zip.

Current local package gate, captured 2026-05-09: `uv run verdict package-check` returned `ok=true`, `missing=[]`, and `invalid=[]` for the required execution logs and PDF reports.

Required release paths:

- `README.md`
- `LICENSE`
- `docs/ARCHITECTURE.md`
- `docs/ARCHITECTURE.md`
- `docs/DEVPOST_COMPLIANCE.md`
- `docs/RELEASE.md`
- `submission/execution-logs/case_001.jsonl`
- `submission/execution-logs/case_002.jsonl`
- `submission/execution-logs/case_003.jsonl`
- `submission/reports/case_001.pdf`
- `submission/reports/case_002.pdf`
- `submission/reports/case_003.pdf`
