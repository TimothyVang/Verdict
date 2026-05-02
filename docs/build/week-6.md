# WEEK 6 (Jun 6 – Jun 14): Demo + docs + submission

**Theme:** Final demo cut. Submission docs (README, ARCHITECTURE.md, BUILD.md, etc.). Devpost upload by Jun 14 EOD (24h before official deadline).
**Critical-path output:** Final demo video; full doc suite; Devpost submission live with the v-submit tag.
**Cumulative team-days:** Tim ~2.5, Beaver ~1.5, Haley ~0.5, KP ~1.

## Phase W6.A — Demo final (Tim + Beaver, ~2 days)

### W6.A.1 — `docs/DEMO_SEQUENCE.md`
- [ ] **W6.A.1** — Author the 5-min sequence with timing per beat (cold open 30s, cloud 60s, airgap 90s with hero beats, dual 60s, recap 60s). Beat list per v4.5 lines 855–865 plus v4.4 hero beats (DKOM divergence, Hunt Evil masquerade, Amcache caveat acknowledgment, pivot vs replan, planner_critique CoVe). Commit: `docs: DEMO_SEQUENCE.md [W6.A.1]`

### W6.A.2 — Final cut
- [ ] **W6.A.2.a** — Re-record against rehearsed flow. Each hero beat must land cleanly.
- [ ] **W6.A.2.b** — Caption file with timestamps.
- [ ] **W6.A.2.c** — Commit: `chore(demo): final cut Jun 12 [W6.A.2]`

## Phase W6.B — Judge checklist + dry runs (Beaver, ~0.5 day)

### W6.B.1 — `docs/SANS_JUDGE_CHECKLIST.md`
- [ ] **W6.B.1** — 15-item checklist from v4.4 (image hash verify; SANS-canonical first move; pslist+psscan divergence; ≥2 artifact classes per execution claim; Amcache caveat acknowledged; UTC `Z` timestamps; pivot in action; epistemic vocabulary; sub-techniques; Hunt Evil masquerade; never asserts attribution; ledger records environment metadata; <20 min end-to-end; explicit UNVERIFIABLE; planner_critique fires visibly). Commit: `docs: SANS_JUDGE_CHECKLIST.md [W6.B.1]`

### W6.B.2 — Three dry runs
- [ ] **W6.B.2** — Dry run final demo against checklist three times. Iterate until all 15 tick green. Commit: `chore(demo): three dry runs against judge checklist [W6.B.2]`

## Phase W6.C — Submission docs (Tim + KP, ~2 days)

### W6.C.1 — `README.md`
- [ ] **W6.C.1** — Front page: one-paragraph problem statement; one-paragraph architecture; demo video link; install instructions (`scripts/install.sh`); 3-mode quick reference; license badge; contributing link. Commit: `docs: README.md [W6.C.1]`

### W6.C.2 — `docs/ARCHITECTURE.md`
- [ ] **W6.C.2** — Full system diagram + node-by-node walkthrough. Reference v4.5 + v4.6 + this plan as authorities. Commit: `docs: ARCHITECTURE.md [W6.C.2]`

### W6.C.3 — `docs/BUILD.md`
- [ ] **W6.C.3** — Exact build steps from a fresh SIFT VM. Verified by reproducing on a second VM. Commit: `docs: BUILD.md [W6.C.3]`

### W6.C.4 — `CONTRIBUTING.md` + `LICENSE` (MIT)
- [ ] **W6.C.4** — Standard MIT + project-specific contributing notes. Commit: `docs: CONTRIBUTING.md + LICENSE [W6.C.4]`

### W6.C.5 — `docs/PRODUCTION_AUDIT.md`
- [ ] **W6.C.5** — The v4 triage doc enumerating what landed in v1 vs deferred to v2. Reference v4.5 §Production-maturity audit. Commit: `docs: PRODUCTION_AUDIT.md [W6.C.5]`

### W6.C.6 — Submission writeup
- [ ] **W6.C.6** — 500-word writeup for Devpost summarizing: problem, architecture, three innovations, accuracy results, demo video. References all 6 official judging criteria explicitly per `DEVPOST_COMPLIANCE.md` Part 3. Commit: `docs: Devpost submission writeup [W6.C.6]`

### W6.C.7 — `docs/ARCHITECTURE_DIAGRAM.svg` rendered visual (Devpost-required)
- [ ] **W6.C.7.a** — Author Mermaid or draw.io source covering: Examiner CLI, FastMCP gateway, Mode autodetect, Planner Protocol (CloudPlanner/LocalPlanner), planner_critique_node, comprehension_gate, executor_fanout (4 branches), executor_work split (DenyRuleWrapper → ToolExecutor → LedgerEmitter), pivot_node, quorum_node, replan/unverifiable_finalize, Microsandbox VMs, Evidence Vault (chattr +i, read-only mount), HMAC ledger, Langfuse, SqliteSaver checkpoint, optional out-of-band services.
- [ ] **W6.C.7.b** — Render to SVG + PNG fallback at `docs/ARCHITECTURE_DIAGRAM.{svg,png}`.
- [ ] **W6.C.7.c** — Reference from README + ARCHITECTURE.md + Devpost form.
- [ ] **W6.C.7.d** — Commit: `docs: ARCHITECTURE_DIAGRAM rendered visual [W6.C.7]`

### W6.C.8 — `docs/EVIDENCE_DATASET.md` (Devpost-required)
- [ ] **W6.C.8.a** — Author. Sections: (1) Datasets used (NIST CFReDS Hacking Case, Honeynet ransomware, 3 engineered cases). (2) Source attribution per dataset (URL, license, hash). (3) What VERDICT was tested against per case. (4) What VERDICT found per case (with finding_ids referencing accuracy report). (5) Limitations: Windows-only; no live-response; no Win11/macOS/Linux/network.
- [ ] **W6.C.8.b** — Cross-reference from README + ACCURACY_REPORT.md + Devpost form.
- [ ] **W6.C.8.c** — Commit: `docs: EVIDENCE_DATASET.md [W6.C.8]`

### W6.C.9 — Agent Execution Logs export (Devpost-required)
- [ ] **W6.C.9.a** — Failing test `tests/cli/test_export_execution_logs.py::test_includes_agent_to_agent_messages_with_timestamps`. Plus `test_includes_token_usage`. Plus `test_traces_finding_to_tool_call_id`. Plus `test_persistent_loop_iteration_n_field_present`. Run → RED.
- [ ] **W6.C.9.b** — Implement `verdict export <case_id> --format execution-logs` emitting Devpost-compliant JSONL: each line `{ts_utc, event_type, agent_id?, target_agent_id?, tool_name?, tool_call_id?, prompt_tokens?, completion_tokens?, finding_id?, iteration_n?, langfuse_trace_id, langgraph_checkpoint_id}`. Distillation of HMAC ledger + Langfuse trace + planner CoT, packaged for judge consumption (NOT a tar of raw ledger).
- [ ] **W6.C.9.c** — Run against all three demo cases; produce `submission/execution-logs/case_{001,002,003}.jsonl`; commit alongside accuracy report.
- [ ] **W6.C.9.d** — Commit: `feat(cli): export execution-logs format for Devpost compliance [W6.C.9]`

### W6.C.10 — `docs/NOVEL_CONTRIBUTION.md` (Devpost-required)
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
- [ ] **W6.D.1.a** — Failing test: produces a valid Devpost zip including: source code, README, LICENSE, ARCHITECTURE.md, ARCHITECTURE_DIAGRAM.svg, BUILD.md, EVIDENCE_DATASET.md, ACCURACY_REPORT.md, NOVEL_CONTRIBUTION.md, DEMO_SEQUENCE.md, THREAT_MODEL.md, CLI.md, FAILURE_MODES.md, SCHEMA_MIGRATION.md, CASE_ISOLATION.md, SCOPE.md, SANS_JUDGE_CHECKLIST.md, PRODUCTION_AUDIT.md, submission/execution-logs/case_{001,002,003}.jsonl. Run → RED.
- [ ] **W6.D.1.b** — Implement.
- [ ] **W6.D.1.c** — Commit: `feat(scripts): package-devpost.sh [W6.D.1]`

### W6.D.2 — Cut `v-submit` tag → fires `devpost-submit.yml` workflow
- [ ] **W6.D.2** — `git tag v-submit && git push origin v-submit`. Commit before tag: `chore(release): cut v-submit for SANS Find Evil! 2026 [W6.D.2]`

### W6.D.3 — Manual Devpost upload Jun 14 EOD
- [ ] **W6.D.3.a** — Run `DEVPOST_COMPLIANCE.md` Part 6 — verify all 18 boxes ticked.
- [ ] **W6.D.3.b** — Upload zip + writeup + demo video link. Submit. Confirm receipt email. **Target Jun 14 EOD = ~28h before official deadline of Jun 15 11:45 PM EDT.**
- [ ] **W6.D.3.c** — If Jun 14 21:00 EDT and any compliance box still unchecked: abort, resolve, retry Jun 15 morning.

## Week 6 — acceptance gates

| Gate | Verification |
|---|---|
| Final 5-min demo video | `ls docs/demo-assets/final-cut.mp4` |
| Demo shows ≥1 self-correction sequence (Devpost-required) | Manual review of cut against air-gap hero beat ⓹ |
| Demo is screencast + narration, NOT slides (Devpost-required) | Manual review |
| Three green dry runs against `SANS_JUDGE_CHECKLIST.md` | Beaver's notes |
| All Devpost-required documentation present | `ls docs/{ARCHITECTURE,ARCHITECTURE_DIAGRAM.svg,BUILD,EVIDENCE_DATASET,ACCURACY_REPORT,NOVEL_CONTRIBUTION,THREAT_MODEL,FAILURE_MODES,CLI,CHECKPOINTING,CASE_ISOLATION,SCOPE,SCHEMA_MIGRATION,SANS_JUDGE_CHECKLIST,PRODUCTION_AUDIT,DEMO_SEQUENCE}.md` |
| README + LICENSE + CONTRIBUTING | `ls README.md LICENSE CONTRIBUTING.md` |
| Repo public + MIT badge in GitHub About section (Devpost-required) | Manual browser check, logged-out |
| Agent execution logs exported per case (Devpost-required) | `ls submission/execution-logs/case_{001,002,003}.jsonl` |
| Devpost zip produced | `ls dist/verdict-devpost-v1.zip` |
| Devpost compliance Part 6 checklist 18/18 ticked | Manual review |
| Devpost upload confirmed | Receipt email |
| `v-submit` tag pushed | `git tag --list 'v-submit'` |

---

