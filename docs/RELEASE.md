# VERDICT - Release and Submission Guide

> **Wiki:** [Index](README.md) · [Architecture](ARCHITECTURE.md) · [Build Plan](BUILD_PLAN.md) · [Devpost](DEVPOST_COMPLIANCE.md) · root [CLAUDE.md](../CLAUDE.md)

**Status:** Consolidated release skeleton. Replace TODO cells only after real evidence, real services, and measured evals.
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

## CLI And Persistence Contracts

Planned v1 command surface. Commands remain documentation-only until their implementation task lands; incomplete commands must not be exposed as callable placeholders.

| Command | Purpose | Status |
|---|---|---|
| `verdict init <evidence>` | Create case, hash evidence, detect/lock mode | Roadmap W1/W5 |
| `verdict resume <case_id>` | Resume interrupted chain from checkpoint | Roadmap W3 |
| `verdict reverify <case_id> --mode <mode>` | Create parallel verification chain | Roadmap W5 |
| `verdict status <case_id>` | Show current graph/checkpoint status | Roadmap |
| `verdict ls` | List local cases | Roadmap |
| `verdict show <case_id>` | Render findings/chains | Roadmap |
| `verdict export <case_id>` | Export report, JSONL, or execution logs | Roadmap |
| `verdict validate <case_id>` | Verify ledger HMAC/chain and hashes | Roadmap W3 |
| `verdict mode` | Explain detected mode and prerequisites | Roadmap W5 |
| `verdict gc` | Rotate local logs and old traces | Roadmap |
| `verdict health` | Machine-readable health endpoint/check | Roadmap |
| `verdict doctor` | Human pre-flight for dependencies/secrets/services | Roadmap W5 |
| `verdict approve <case_id> <finding_id> --approver <approver>` | HMAC-sign human approval | Roadmap W5 |

Export formats:

| Format | Output | Required fields |
|---|---|---|
| `jsonl` | Raw or normalized ledger events | case/checkpoint/trace IDs |
| `html` | Narrative report for humans | findings, caveats, evidence hashes |
| `execution-logs` | Devpost judge artifact | timestamps, agent/tool events, token usage when present, finding-to-tool-call traceability |

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
fail-closed scaffolding. Each task refuses to construct an eval unless real evidence exists under
`inspect_ai/ground_truth/` and then refuses to proceed until the task is wired to real VERDICT
execution. `.github/workflows/eval-hallucination-gate.yml` fails with `scorer_not_implemented`
until `inspect_ai/scorers/hallucination_rate.py` lands; CI must not publish a fake passing
hallucination score.

Per-mode metrics:

| Mode | Cases | Hallucination rate | Findings precision | Findings recall | MITRE sub-technique precision | Contested resolution rate |
|---|---:|---:|---:|---:|---:|---:|
| cloud | TODO | TODO | TODO | TODO | TODO | TODO |
| airgap | TODO | TODO | TODO | TODO | TODO | TODO |
| dual | TODO | TODO | TODO | TODO | TODO | TODO |

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
| Case 001 lol-bins | Engineered | Project-generated | TODO | LOLBin and masquerade evaluation |
| Case 002 credential theft | Engineered | Project-generated | TODO | Credential-access evaluation |
| Case 003 ransomware | Engineered | Project-generated | TODO | Demo and recovery flow |

Known errors stay visible in the final report. `disagreement_correlation`: TODO.

## Demo Checklist

v0 demo scope is cloud-only Claude Agent SDK. SGLang, GPU-backed air-gap mode, and dual mode are postponed until the Claude path produces repeatable proof artifacts.

Cloud proof artifacts live under `proof/runs/<timestamp>/`. A successful run includes
`cloud-agent-response.raw.txt`, `investigation-plan.json`, `validation.log`, `ledger.jsonl`,
`run-summary.md`, plus `screenshots/` and `video/` folders for visual review.

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
