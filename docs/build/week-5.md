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
- [ ] **W5.B.1.b** — Implement `verdict/adapters/opencti_mcp.py`.
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

### W5.D.1 — `docs/SCOPE.md`
- [ ] **W5.D.1** — Author. v1 = Windows DFIR; macOS / Linux / Win11-specific (SRUM/ETW/Cortana) / ESXi = v2 roadmap. Network forensics (FOR572) = v2. Examiner workflow integrations (Axiom XML, EnCase EWF, FTK CSV) = v2. Commit: `docs: SCOPE.md [W5.D.1]`

### W5.D.2 — Update `docs/ARCHITECTURE.md` with all v4.4-v4.6 additions
- [ ] **W5.D.2** — Bring it current. Reference v4.5 + v4.6 + this plan.

## Phase W5.E — Demo prep (Beaver + Tim, ~1 day)

### W5.E.1 — `docs/ACCURACY_REPORT.md` final draft
- [ ] **W5.E.1.a** — Tables: per-mode hallucination, agreement, FP rates, step_efficiency by tool, contested-resolution rate, MITRE sub-technique precision, negative-hypothesis quality, Qwen3-vs-GLM disagreement correlation.
- [ ] **W5.E.1.b** — Two charts: Step Efficiency by tool, Contested-Finding Resolution per-mode.
- [ ] **W5.E.1.c** — Commit: `docs: ACCURACY_REPORT.md [W5.E.1]`

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
| `docs/ACCURACY_REPORT.md` shipped with all required tables | manual review |
| Langfuse demo dashboard JSON committed | `ls docs/demo-assets/langfuse-dashboard.json` |
| Rough demo cut exists | `ls docs/demo-assets/rough-cut.mp4` |
| Time-travel clip exists | `ls docs/demo-assets/time-travel.mp4` |
| HMAC approval emits valid ledger entry | `pytest tests/cli/test_approve.py` green |

If RED: drop W5.C optional adapters first → drop W5.B.3 (REMnux) → drop W5.E.2 (time-travel clip; defer to v2).

---

