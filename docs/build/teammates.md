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
- W3.G.1 (CASE_ISOLATION.md)

**Week 4 (~3 days):**
- W4.D.4 (CI gates per mode)
- General CI hardening + flaky-test triage

**Week 5 (~2.5 days):**
- W5.A.1, W5.A.2, W5.A.3, W5.A.4 (mode autodetect + doctor)
- W5.B.1, W5.B.2, W5.B.3 (adapters)
- W5.D.1, W5.D.2 (SCOPE + ARCHITECTURE update)

**Week 6 (~3.5 days):**
- W6.C.1–W6.C.6 (submission docs)
- W6.C.7 (ARCHITECTURE_DIAGRAM.svg rendered visual — Devpost-required)
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

