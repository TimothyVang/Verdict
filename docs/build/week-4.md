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

### W4.B.1 — `verdict/knowledge/lolbins.yml`
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
- [ ] **W4.D.4.a** — Failing CI: workflow fails if any mode hallucination_rate > 0.05 or agreement < 0.85.
- [ ] **W4.D.4.b** — Implement.
- [ ] **W4.D.4.c** — Commit: `ci: per-mode Inspect AI eval CI gates [W4.D.4]`

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
- [ ] **W4.F.1.a** — Author `verdict/planning/prompts/negative_hypothesis_examples.md` with 5 high-quality few-shots demonstrating: T1547 ruling out T1055; T1543.003 ruling out T1543.001; etc.
- [ ] **W4.F.1.b** — Wire into planner system prompt.
- [ ] **W4.F.1.c** — Commit: `feat(prompts): 5 negative-hypothesis few-shot examples [W4.F.1]`

### W4.F.2 — Adversarial-reasoning prompt
- [ ] **W4.F.2.a** — Author `verdict/planning/prompts/adversarial_reasoning.md`. Inject "if I were the attacker, where would I hide?" — Scheduled Tasks `\Microsoft\Windows\` namespace, WMI event subscriptions, IFEO debugger keys (per project MEMORY.md persistence top-5).
- [ ] **W4.F.2.b** — Wire into planner system prompt.
- [ ] **W4.F.2.c** — Commit: `feat(prompts): adversarial-reasoning planner injection [W4.F.2]`

### W4.F.3 — Prompt budget CI assertion
- [ ] **W4.F.3.a** — Failing test: rendered planner ≤30K tokens; executor ≤20K; critic ≤15K.
- [ ] **W4.F.3.b** — Implement assertion in `tests/planning/test_prompt_budget.py`.
- [ ] **W4.F.3.c** — Commit: `test(planning): prompt budget CI assertion [W4.F.3]`

## Phase W4.G — Disagreement-correlation measurement (KP, ~0.5 day)

### W4.G.1 — Measure Qwen3-vs-GLM disagreement correlation across 50 findings
- [ ] **W4.G.1.a** — Author analysis script `inspect_ai/scripts/measure_disagreement_correlation.py`. Run both models against the 50-indicator ground truth; compute correlation matrix on disagreements.
- [ ] **W4.G.1.b** — Output number to `docs/ACCURACY_REPORT.md`.
- [ ] **W4.G.1.c** — Commit: `feat(eval): Qwen3-vs-GLM disagreement-correlation measurement [W4.G.1]`

## Week 4 — acceptance gates

| Gate | Verification |
|---|---|
| All 6 skills load with required_tools | `pytest tests/skills/ -v` green |
| 50 ground-truth indicators across 3 cases | `ls inspect_ai/ground_truth/case_00{1,2,3}/` |
| Case 001 produces engineered Qwen3-vs-GLM disagreement | Manual verification recorded in `docs/demo-assets/case_001.md` |
| Three per-mode Inspect AI tasks green in CI | `.github/workflows/inspect-ai-evals.yml` runs green |
| Hallucination rate ≤ 0.05 in all three modes | `inspect view <run>` + scorer report |
| Agreement ≥ 0.85 in all three modes | Same |
| MITRE sub-technique precision measurable + reported | `cat docs/ACCURACY_REPORT.md` |
| Disagreement correlation number in accuracy report | `grep -c "disagreement_correlation" docs/ACCURACY_REPORT.md` ≥ 1 |
| Prompt budget CI assertion enforces ≤30K planner | `pytest tests/planning/test_prompt_budget.py -v` green |

If RED: drop W4.B (LOLBin catalog → push to W5) → drop W4.F.2 (adversarial reasoning prompt) → cut Case 003 → freeze tool count + spend remainder on prompt refinement.

---

