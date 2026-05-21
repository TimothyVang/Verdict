# Devpost Compliance Checklist — SANS Find Evil! 2026

> **Wiki:** [Index](README.md) · [TL;DR](TLDR.md) · [Architecture](ARCHITECTURE.md) · [Build Plan](BUILD_PLAN.md) · [Devpost](DEVPOST_COMPLIANCE.md) · [Hackathon Rules](hackathon/RULES.md) · root [CLAUDE.md](../CLAUDE.md)

**Authority:** Official Devpost rules at findevil.devpost.com (retrieved May 2, 2026).
**Hard deadline:** **Submission Period closes Jun 15, 2026 at 11:45 PM EDT** (= Jun 15 23:45 EDT = Jun 16 03:45 UTC). Team-internal target: Jun 14 EOD = ~28-hour buffer.
**Judging Period:** Jun 19, 2026 12:00 AM EDT – Jul 3, 2026 12:00 AM EDT.
**Winners announced:** ~Jul 8, 2026.
**Sponsor:** SANS Institute.

This is the single source of truth for "are we satisfying the rules?" Run against this weekly during weeks 4–6 and every day during week 6.

---

## Part 1 — Project Requirements (mandatory demonstrations)

The rules require the Project to use Claude Code or OpenClaw as the primary execution engine and demonstrate **all three** autonomy qualities below. Failure to demonstrate any one = Stage One pass/fail elimination.

| Required demonstration | What rules say | How VERDICT satisfies | Where shown | Status |
|---|---|---|---|---|
| **Primary execution engine** | "Uses Claude Code or OpenClaw as primary execution engine" | VERDICT is submitted as a Claude Code / Protocol SIFT extension. Claude Code drives the operator workflow, gateway invocation, ledger review, and cloud/dual planner lane. Air-gap mode is a local-inference lane for classified/offline operation, not a separate non-Claude product; it preserves the same VERDICT graph, tool contracts, ledger, and submission artifacts. | Architecture §1 mode table; TLDR mode diagram; demo shows cloud and dual Claude Code lanes plus air-gap local lane under the same CLI/runtime. | GATED on W1.A.5 + W2.B |
| **Self-correction** | "the agent detects and resolves errors or inconsistencies in its own output without human intervention" | Cross-engine quorum CONTESTED → replan_node loops back to planner with conflict surfaced as hint; both engines re-converge on corrected finding. Also: planner_critique_node (CoVe) catches wrong plans before execution. | Demo air-gap segment hero beat ⓹ (Qwen3 hallucinates path → GLM disagrees → CONTESTED → replan → VETTED_AIRGAP). Architecture: v4.5 §LangGraph topology + v4.6 planner_critique. | GATED on W2.D.1 + W3.A.1 |
| **Accuracy validation** | "all findings are traceable to specific artifacts, files, offsets, or log entries" | `Finding.artifact_paths: list[Path]` (min 2), `Finding.evidence_hashes: dict[Path, str]` (SHA-256 per artifact), `Finding.artifact_classes: list[ArtifactClass]` (FOR500 corroboration). Every finding cites both the file path AND the cryptographic hash AND the artifact class. | Schema: v4.6 §Phase 1. Demo: every Finding rendered shows `[file:path][sha256:abc...][class:PREFETCH]` chips. | GATED on W1.B.6–W1.B.10 |
| **Analytical reasoning** | "output is presented as a structured investigative narrative, not a raw execution log" | `Finding.rationale` is natural-language narrative ("Amcache lists evil.exe at 2024-03-14T15:32Z; per FOR500, Amcache LastModified reflects catalog registration not execution. Execution corroborated by Prefetch run-count=1 + EVTX 4688 at 2024-03-14T15:34Z."). Plus planner CoT capture (gzipped in ledger; first 8KB on Langfuse span). | `verdict export <case_id> --format html` produces narrative report. v4.5 architecture + W2.D.3. | GATED on W2.D.3 |

**Verification before submission:** the demo video MUST show at least one self-correction sequence (the Qwen3-vs-GLM disagreement → replan beat). This is explicit in the demo-video rules, not just judging criteria.

---

## Part 2 — Submission Requirements (artifact checklist)

Every item must be present or the submission is incomplete.

| Required artifact | Source rule | Where in our doc set | Owner | Status |
|---|---|---|---|---|
| **Public repository URL** | "Provide a URL to your code repository" | GitHub repo (TBD: `github.com/<org>/verdict`); set up W6.D.1 | Tim | TODO |
| **Public + open source** | "The repository must be public and open source" | Repo settings: Public; LICENSE file with MIT | Tim | TODO |
| **MIT or Apache 2.0 license** | "by including an MIT or Apache 2.0 open source license file" | `LICENSE` file at repo root with MIT text | Tim (W6.C.4) | GATED |
| **License visible at top of repo (About section)** | "This license should be detectable and visible at the top of the repository page (in the About section)" | GitHub repo About metadata: License = "MIT" badge displayed | Tim (NEW: W6.D.0) | **MISSING — added below** |
| **README with setup** | "The repository must contain a README with setup instructions" | `README.md` at repo root | Tim (W6.C.1) | GATED |
| **Live deployment URL OR step-by-step local instructions** | "Include either a live deployment URL or step-by-step instructions that let judges run your agent locally against provided evidence. If local setup requires specific tools or dependencies, document them clearly in the README." | No live deployment (air-gap intent makes hosted demo wrong). Step-by-step in `docs/RELEASE.md` + README quickstart. | Tim (W6.C.3) | GATED |
| **Text description** | "explain the features and functionality of your Project" | Devpost submission form text + repo README | Tim (W6.C.6) | GATED |
| **Demo video < 5 min** | "should be less than five (5) minutes" | `docs/RELEASE.md` five-minute cut | Beaver (W6.A.2) | GATED |
| **Demo screencast of live terminal + audio narration** | "should include a screencast of live terminal execution with audio narration. Not slides. Not marketing videos." | Two-pane recording: left = terminal, right = Langfuse trace tree. Audio narration throughout. NO marketing slides. | Beaver (W6.A.2) | GATED |
| **Demo shows real evidence** | "Show the agent working against real evidence" | Honeynet ransomware image (Case 003) + 2 engineered cases (lol-bins, credtheft) | KP (W4.C) + Beaver (W6.A.2) | GATED |
| **Demo shows ≥1 self-correction sequence** | "including at least one self-correction sequence" | Air-gap mode hero beat ⓹ — Qwen3-vs-GLM disagreement → CONTESTED → replan → VETTED_AIRGAP. Narrator calls it out: "this is self-correction." | Beaver (W6.A.2) | **MUST verify on every cut** |
| **Demo on YouTube/Vimeo/Youku, public** | "must be uploaded to and made publicly visible on YouTube, Vimeo, or Youku" | YouTube unlisted-then-public on Jun 14 | Tim (W6.D.3) | GATED |
| **Demo no third-party trademarks/copyrighted music** | "must not include third party trademarks, or copyrighted music or other material unless the Entrant has permission" | Use royalty-free / CC0 audio. No corporate logos beyond fair-use citation of Volatility/Hayabusa logos for tool identification. | Beaver (W6.A.2) | GATED |
| **Architecture Diagram (visual file)** | "Include an Architecture Diagram — A clear visual showing how components connect — the agent, SIFT tools, MCP servers, evidence sources, output pipeline" | `docs/ARCHITECTURE_DIAGRAM.svg` rendered visual (NOT just ASCII). Shows: Examiner CLI → Gateway → Mode selector → Planner/Verifier → Microsandbox VMs → 12 SIFT tools → Evidence Vault + Ledger + Langfuse. | Tim (W6.C.7) | **SVG present** (`docs/ARCHITECTURE_DIAGRAM.svg`); README and ARCHITECTURE.md embed present; PNG fallback pending W6.C.7.b |
| **Evidence Dataset Documentation** | "Evidence Dataset Documentation — What the agent was tested against, source of the data, and what the agent found" | `docs/RELEASE.md` dataset section covering NIST CFReDS Hacking Case, Honeynet ransomware image, 3 engineered cases, source attribution, and summary findings. | KP (NEW: W6.C.8) | GATED |
| **Accuracy Report** | "Self-assessment of findings accuracy. False positives, missed artifacts, hallucinated claims identified during testing. Honesty valued over perfection." | `docs/RELEASE.md` accuracy section with per-mode hallucination rate, false positives, missed artifacts, MITRE sub-technique precision, and Qwen3-vs-GLM disagreement correlation. | KP (W5.E.1) | GATED |
| **Agent Execution Logs** | "Structured logs showing the full agent communication and tool execution sequence... Multi-agent: agent-to-agent message logs with timestamps. Single-agent: tool execution logs with timestamps and token usage. Persistent loop: iteration-over-iteration traces showing how the agent's approach changed. Judges must be able to trace any finding back to the specific tool execution that produced it." | VERDICT is **multi-agent** (Qwen3 + GLM + Claude in dual mode). Required: agent-to-agent logs with timestamps. Plus tool execution logs with timestamps + token usage. Plus replan iteration traces. **Package as `submission/execution-logs/<case_id>.jsonl`** — distilled view of HMAC ledger + Langfuse traces + planner CoT, formatted for judge consumption. NOT just a tar of the raw ledger. | Tim (NEW: W6.C.9) | **MISSING — added below** |
| **Novel contribution clearly documented** | "Projects must be substantially new work created during the hackathon period... The novel contribution must be clearly documented." | `docs/RELEASE.md` novelty section distinguishing what VERDICT built from pre-existing open source. | Tim (NEW: W6.C.10) | GATED |

---

## Part 3 — Judging Criteria (six, equally weighted)

The rules list **six equally weighted** criteria. Earlier doc-set passes claimed "5 of 6" — that was wrong. Every doc and the demo must map to all six explicitly.

### Criterion 1: Autonomous Execution Quality
> "Does the agent reason about next steps, handle failures, and self-correct in real time?"

**How VERDICT scores:**
- Mode-aware verifier strategy (cloud-only/airgap/dual auto-detected, mode-locked at case_init)
- Plan-then-Execute LangGraph with 8 registered nodes (planner, planner_critique, comprehension_gate, executor_fanout, pivot, quorum, replan, finalize); `unverifiable_finalize_node` is a helper called from `replan_node`, not a registered graph node
- Self-correction via cross-engine quorum CONTESTED → replan loop
- Bounded recovery: pivot_max=15 (cheap), replan_max=3 (expensive), then explicit UNVERIFIABLE + interrupt()
- Tool-call argument hallucination caught by args_validator (Pydantic v2) before sandbox spawn (W2.E.1)

**Demo segment:** air-gap hero beat ⓹ (Qwen3-vs-GLM disagreement → replan → re-converge).

### Criterion 2: IR Accuracy
> "Are findings correct? Hallucinations caught and flagged? Confirmed findings distinguished from inferences?"

**How VERDICT scores:**
- Cross-family verification (Qwen3 + GLM-4.5-Air; different model families, partial-not-absolute independence empirically measured in W4.G.1)
- VerdictStatus enum (canonical per `CLAUDE.md` §3.6): VETTED_CLOUD / VETTED_AIRGAP / VETTED_DUAL / CONTESTED / UNVERIFIABLE / EXHAUSTED_REPLAN
- Honest framing: VETTED_CLOUD is not VERIFIED (same-model self-consistency != true verification); VETTED_AIRGAP and VETTED_DUAL are cross-family verified
- Human-review state is a separate `Finding.review_state` field (DRAFT / APPROVED / REJECTED), orthogonal to VerdictStatus
- Tier-1 examiner caveats encoded in schema validators (Amcache LastModified ≠ execution; ShimCache order changed Win 8.1; etc.)
- Artifact-pair corroboration: Finding requires ≥2 artifact_classes for execution claims (FOR500)
- MITRE sub-technique granularity required (T1055.012 not just T1055)
- Inspect AI per-mode scorers: hallucination_rate, findings_precision, findings_recall, mitre_subtechnique_precision, negative_hypothesis_quality. Current scaffold fails closed until real evidence and scorer implementations land; no CI job may publish a placeholder hallucination score.

**Demo segment:** air-gap hero beats ⓵ (DKOM divergence → automatic T1014), ⓶ (Hunt Evil masquerade → T1036.005), ⓷ (Amcache caveat acknowledgment in rationale).

### Criterion 3: Breadth and Depth of Analysis
> "How much case data can the agent handle? **Depth on fewer types beats shallow coverage of many.**"

**How VERDICT scores:**
- **Explicit scope decision: Windows-DFIR-depth-first.** macOS / Linux / Win11 SRUM-ETW / ESXi / FOR572 network forensics deferred to v2 with named architectural extension points (5th `net_executor` and `live_executor` fanout branches).
- 23 tool wrappers (10 vol3 plugins + Hayabusa split into csv-timeline+filter + plaso split into extract+filter + 9 Sleuth Kit/EZ Tools/bulk_extractor/exiftool/capa)
- Three evidence types covered with depth: memory image, disk image, triage zip. Three playbook YAMLs encode SANS-canonical sequencing per type.
- 50 ground-truth indicators across 3 engineered cases (lol-bins, credential theft, ransomware)
- DKOM/T1014 detection via pslist+psscan divergence — encoded, not LLM-recalled
- Hunt Evil baseline catalog covering 8 canonical Windows processes
- LOLBin cmdline catalog covering 6 binaries with MITRE sub-technique mapping

**Defending the scope:** the Devpost rubric explicitly states "depth on fewer types beats shallow coverage." `docs/RELEASE.md` frames Windows-DFIR-depth as architectural intent (constrained scope sharpens cross-engine verifier signal), not as a budget excuse. v2 expansion path is documented (per-platform CaveatID enums, parallel playbooks).

**Demo segment:** all hero beats hit Windows DFIR depth. Architecture recap names the v2 extension points.

### Criterion 4: Constraint Implementation
> "Are guardrails architectural or prompt-based? Judges evaluate where security boundaries are enforced and whether they were tested for bypass."

**How VERDICT scores:**
- **Three-layer immutability defense** (architectural):
  - Layer 1 = Claude PreToolUse hook (best-effort, version-dependent caveat per anthropics/claude-code #33106 + #37210)
  - Layer 2 = LangGraph DenyRuleWrapper (architectural guarantee, fires in all three modes regardless of model)
  - Layer 3 = Microsandbox read-only mount of /evidence at libkrun kernel level
- HMAC-signed append-only JSONL ledger with prev_entry_hash chain (tamper-evident)
- Per-tool ephemeral microVM (Microsandbox libkrun); VM destroyed after each call
- TSI (Transparent Socket Impersonation) for credential injection — API keys never enter the VM, proven via tcpdump
- Mode lock at case_init: refuses to advance if resume detects mode mismatch
- chattr +i on evidence vault at case_init
- Sanitization scanner on tool output for prompt-injection patterns (IGNORE PREVIOUS, SYSTEM:, etc.)
- args_validator (Pydantic v2) rejects unknown flags before sandbox spawn
- Periodic evidence re-hash check (every 10 super-steps) catches anything that bypasses the three-layer gate
- HMAC key TPM-backed if /dev/tpmrm0 present, else gpg-encrypted with passphrase

**Bypass testing:** CI smoke test in `tests/smoke/test_pretooluse_deny.py` (xfail-marked pending Anthropic fix #33106). Plus chaos test 100 cases of kill -9 between super-steps (W3.E.6) — zero ledger corruption.

**Demo segment:** air-gap hero beats ⓺ (TSI tcpdump proof) + ⓻ (kill -9 + resume).

### Criterion 5: Audit Trail Quality
> "Can judges trace any finding back to the specific tool execution that produced it?"

**How VERDICT scores:**
- Three-tier ID hierarchy in LedgerEntry: `case_id` (eternal) / `langfuse_trace_id` (per graph.invoke) / `langgraph_checkpoint_id` (per super-step)
- Bidirectional cross-link: ledger entry → Langfuse trace → tool call; reverse: trace → ledger entry → finding
- HMAC-signed JSONL chain with prev_entry_hash; tamper-evident
- Per-output-file SHA-256 (NIST SP 800-86 §5.1.2 logical-extract preservation)
- Examination-environment metadata per call: `microsandbox_version`, `rootfs_sha256`, `tool_version`, `kernel_version` (NIST SP 800-86 §5.1.4)
- `verdict export <case_id> --format jsonl` produces submission-grade execution log
- `verdict validate <case_id>` verifies HMAC chain offline
- Planner CoT captured: gzipped in ledger via `planner_cot` event; first 8KB attached to Langfuse span attribute (forensic admissibility — reasoning matters as much as conclusion)
- `verdict reverify <case_id> --mode dual` produces parallel verdict chain without mutating original (mode-elevation honesty)

**Demo segment:** Langfuse pane visible throughout 5 minutes. Architecture recap walks one finding from rationale → Langfuse span → ledger entry → tool_call_id → microsandbox version → file hash.

### Criterion 6: Usability and Documentation
> "Can another practitioner deploy and build on this?"

**How VERDICT scores:**
- `scripts/install.sh` with cloud credential detection (`CLAUDE_CODE_OAUTH_TOKEN`, interactive Claude Code OAuth, `ANTHROPIC_API_KEY`, optional host-side `OPENROUTER_API_KEY`); auto-detects and configures without passing secrets into microVMs
- `verdict doctor` pre-flight (W5.A.4) reports each component status before first use
- `docs/RELEASE.md` reproducible-build section verified from a fresh SIFT VM and second VM in W6.C.3
- Full CLI surface: `verdict {doctor, mode, init, run-tool, run-case, resume, reverify, status, ls, show, export, validate, approve, gc, package-check, health}`
- Consolidated documentation set: README, ARCHITECTURE, DEVPOST_COMPLIANCE, RELEASE, FAILURE_MODES, CASE_ISOLATION, and the docs wiki index
- Conventional Commits with task ID embedded (e.g. `feat(schema): foo [W1.B.1]`) — git log archeology trivial
- Architecture diagram as rendered visual (`docs/ARCHITECTURE_DIAGRAM.svg`)
- Skill format: agentskills.io standard — portable across Claude Code, Hermes, Cursor, Codex
- Pinned dependency versions; lockfiles committed
- Three-mode operator override: `--mode={cloud,airgap,dual}`

**Demo segment:** architecture recap shows file tree + `verdict --help` + 30s of `docs/RELEASE.md` walkthrough at the end.

---

## Part 4 — Tie-breaker awareness

Per rules: ties are broken by score on the criterion order listed above (Autonomous Execution → IR Accuracy → Breadth/Depth → Constraint → Audit → Usability). If we're competing for 1st/2nd/3rd, the criterion order tells us where to push hardest:

1. **Autonomous Execution Quality** — ranked first. The self-correction story (Qwen3-vs-GLM CONTESTED → replan) must land cleanly. **No demo cut without this beat.**
2. **IR Accuracy** — second. Hallucination-caught story (artifact-pair rule rejects single-source claims; Tier-1 caveats; sub-technique granularity) must be visible.
3. **Breadth/Depth** — third. The "depth beats breadth" defense must be quoted in the writeup, not just implied.

Push effort in this priority order during weeks 5-6 polish.

---

## Part 5 — Disqualification risks

| Risk | Source rule | Likelihood | Mitigation |
|---|---|---|---|
| Submission past Jun 15 23:45 EDT | §1 | LOW (we target Jun 14 EOD = 28h buffer) | Submit Jun 13 evening as second buffer |
| Repo not public on submission | §4 | LOW | W6.D.0 task — flip public, set License badge, before tagging v-submit |
| License not in About section | §4 | MEDIUM (easy to forget) | W6.D.0 task explicit |
| Third-party copyrighted music in demo | §4 | LOW | Use CC0 audio (or no music) |
| Pre-existing project not "substantially new" | §4 | LOW | Project started May 2; novel-contribution doc enumerates additions |
| Project received financial/preferential support from Sponsor (SANS) | §4 | LOW | We have no financial relationship with SANS |
| OAuth token redistributed | §7 + Anthropic ToS | LOW | scripts/install.sh prompts user for own token; never bundles | 
| GPL/AGPL code linked into project | §4 IP rights | MEDIUM (Daytona, REMnux, GPL Sigma) | Already audited in v4.5; REMnux network-call only; Daytona excluded; GPL Sigma rules referenced not vendored |
| Video > 5 min substantive content | §4 | MEDIUM (demo timing tight) | Hard 5-min cut; judges not required to watch >10 min, but >5 min content not graded |
| AGPL clean-room rewrite mistakenly used | §4 IP + hackathon AGPL prohibition | LOW (we documented this trap explicitly in v4.5) | Microsandbox is Apache-2.0, not Daytona |

---

## Part 6 — Submission checklist (run during Jun 14)

Three hours before pushing the v-submit tag, verify ALL of the following are TRUE:

- [ ] Repo is public on GitHub
- [ ] LICENSE file at repo root with MIT text
- [ ] Repo About section shows MIT badge
- [ ] README.md at repo root with quickstart
- [ ] `docs/RELEASE.md` reproducible-build section verified from fresh SIFT VM and second VM
- [x] `docs/ARCHITECTURE_DIAGRAM.svg` rendered visual present
- [ ] `docs/RELEASE.md` documents what we tested against + sources + findings
- [ ] `docs/RELEASE.md` includes honest false-positive / missed-artifact / hallucination tally per mode
- [ ] `submission/execution-logs/case_001.jsonl`, `case_002.jsonl`, `case_003.jsonl` distilled execution-log artifacts
- [ ] `docs/RELEASE.md` documents what's substantially new vs. pre-existing
- [ ] Demo video on YouTube, public, < 5:00 runtime
- [ ] Demo video shows live terminal screencast with audio narration (NO slides, NO marketing)
- [ ] Demo video shows ≥ 1 self-correction sequence (Qwen3-vs-GLM CONTESTED → replan beat)
- [ ] Demo video has no third-party trademarks beyond fair-use tool identification, no copyrighted music
- [ ] All 8 Devpost submission components uploaded or linked in the Devpost form
- [ ] Submission writeup text references all 6 judging criteria
- [ ] No CLAUDE_CODE_OAUTH_TOKEN, no ANTHROPIC_API_KEY, no OPENROUTER_API_KEY, no HMAC private key, no `.env` committed to repo
- [ ] `git tag v-submit && git push origin v-submit` triggered
- [ ] Devpost submission form Submitted, receipt email confirmed

If ANY checkbox is unchecked at Jun 14 21:00 EDT, abort the v-submit tag push and resolve before retrying.

---

## Tasks mirrored from master build plan (Week 6 amendments)

These amendments have been patched into `BUILD_PLAN.md`; they remain here so every Devpost-specific artifact has a nearby compliance trace.

### W6.D.0 — GitHub repo metadata
- [ ] **W6.D.0.a** — Set repo Public visibility.
- [ ] **W6.D.0.b** — Verify LICENSE file at repo root contains MIT text (OSI-canonical MIT, SPDX identifier `MIT`; not custom).
- [ ] **W6.D.0.c** — Set repo About section: description, license badge auto-detected as MIT, topics include `dfir`, `incident-response`, `claude-code`, `sift-workstation`, `mcp`, `agentic`.
- [ ] **W6.D.0.d** — Verify license badge visible at top of repo on a fresh logged-out browser session.
- [ ] **W6.D.0.e** — Commit if any docs reference the repo URL: `chore(release): GitHub repo public + MIT badge in About [W6.D.0]`

### W6.C.7 — `docs/ARCHITECTURE_DIAGRAM.svg` rendered visual
- [x] **W6.C.7.a** — Author Mermaid or draw.io source for system diagram covering: Examiner CLI, FastMCP gateway, Mode autodetect, Planner Protocol (CloudPlanner/LocalPlanner), planner_critique_node, comprehension_gate, executor_fanout (4 branches; each branch composes DenyRuleWrapper → ToolExecutor → LedgerEmitter as the per-branch `executor_work` sub-state), pivot_node, quorum_node, replan/unverifiable_finalize, Microsandbox VMs (per-tool), Evidence Vault (chattr +i, read-only mount), HMAC ledger, Langfuse, SqliteSaver checkpoint, optional out-of-band services (Velociraptor, OpenCTI, REMnux).
- [ ] **W6.C.7.b** — Render to SVG (preferred — scales) and PNG fallback. Place at `docs/ARCHITECTURE_DIAGRAM.svg` and `docs/ARCHITECTURE_DIAGRAM.png`.
- [x] **W6.C.7.c** — Reference from README + ARCHITECTURE.md.
- [x] **W6.C.7.d** — Commit: `docs: ARCHITECTURE_DIAGRAM.svg rendered visual [W6.C.7]`

### W6.C.8 — `docs/RELEASE.md` dataset section
- [ ] **W6.C.8.a** — Author. Sections: (1) Datasets used (NIST CFReDS Hacking Case, Honeynet ransomware image, 3 engineered cases). (2) Source attribution per dataset (URL, license, hash). (3) What VERDICT was tested against per case. (4) What VERDICT found per case (summary of findings, with finding_ids referencing the accuracy report). (5) Limitations: Windows-only; no live-response; no Win11-specific; no macOS/Linux.
- [ ] **W6.C.8.b** — Cross-reference from README and accuracy section.
- [ ] **W6.C.8.c** — Commit: `docs(release): add dataset documentation [W6.C.8]`

### W6.C.9 — `submission/execution-logs/<case_id>.jsonl` artifact export
- [ ] **W6.C.9.a** — Failing test `tests/cli/test_export_execution_logs.py::test_includes_agent_to_agent_messages_with_timestamps`. Plus `test_includes_token_usage`. Plus `test_traces_finding_to_tool_call_id`. Run → RED.
- [ ] **W6.C.9.b** — Implement `verdict export <case_id> --format execution-logs` that emits a Devpost-compliant JSONL: each line is one event with `{ts_utc, event_type, agent_id?, target_agent_id?, tool_name?, tool_call_id?, prompt_tokens?, completion_tokens?, finding_id?, langfuse_trace_id, langgraph_checkpoint_id}`. Distillation of HMAC ledger + Langfuse trace + planner CoT. Multi-agent agent-to-agent messages have explicit `agent_id` + `target_agent_id`. Persistent loop iterations have `iteration_n` field showing how approach changed.
- [ ] **W6.C.9.c** — Run against all three demo cases; produce `submission/execution-logs/case_001.jsonl`, `case_002.jsonl`, `case_003.jsonl` and commit.
- [ ] **W6.C.9.d** — Commit: `feat(cli): export execution-logs format for Devpost compliance [W6.C.9]`

### W6.C.10 — `docs/RELEASE.md` novelty section
- [ ] **W6.C.10.a** — Author. Sections: (1) Project timeline (started 2026-05-02; substantially new work per Devpost rules). (2) What we built (mode-aware verifier, three-layer immutability, encoded forensic discipline, planner_critique CoVe, pivot vs replan, schema-enforced caveat acknowledgment, DKOM/T1014 auto-detection, Hunt Evil masquerade catch, LOLBin matcher with T1218 sub-techniques, agentskills.io skill bundle, custom Inspect AI scorers including step_efficiency + mitre_subtechnique_precision + negative_hypothesis_quality + Qwen3-vs-GLM disagreement-correlation analysis). (3) What was pre-existing open source (with license + source URL each: SIFT Workstation, Volatility 3, Hayabusa, plaso, EZ Tools, Microsandbox, SGLang, vLLM, LangGraph, Langfuse, OpenLLMetry, Inspect AI, Pydantic, FastMCP, Claude Agent SDK, blake3). (4) What we extended vs replaced.
- [ ] **W6.C.10.b** — Cross-reference from README.
- [ ] **W6.C.10.c** — Commit: `docs(release): document novel contribution [W6.C.10]`

### W6.D.4 — Submission packet stage
- [ ] **W6.D.4.a** — Run Part 6 checklist of this document; all 19 boxes ticked.
- [ ] **W6.D.4.b** — Stage submission packet under `submission/` directory: video URL, repo URL (post-public flip), all 4 doc artifacts, 3 execution-log JSONL files, accuracy report.
- [ ] **W6.D.4.c** — Devpost form fields drafted (text description, all upload links, team metadata).
- [ ] **W6.D.4.d** — Submit. Confirm receipt email. Commit: `chore(release): Devpost submission Jun 14 [W6.D.4]`

---

## Authority chain

When in doubt about a Devpost requirement, this is the resolution order:

1. Devpost rules at `findevil.devpost.com` (always wins)
2. `DEVPOST_COMPLIANCE.md` (this doc — interprets rules into our artifacts)
3. `BUILD_PLAN.md` (sequences artifacts into TDD tasks)
4. `docs/spec/03-audit-v4.5.md` + `docs/spec/04-spec-plan-v4.6.md` (architecture rationale)
5. Project `CLAUDE.md` (build conventions)

If Devpost amends rules between now and Jun 15, this doc updates first; everything downstream follows.
