# DFIR Agentic Workflow V1 Plan (SANS-Aligned, Anti-Bloat)

## Why now

VERDICT has evidence-backed memory primitives, but not a complete SANS phase runner with explicit gate contracts. This plan sequences the minimum implementation to ship a defensible v1 without overbuilding.

## 2-week implementation plan

### Week 1 — Phase orchestration + memory integration

- **Day 1 (Mon):** Define workflow contract types for 6 SANS phases.
  - Inputs/outputs, allowed tools, pass/fail gates, emitted artifacts.
- **Day 2 (Tue):** Implement minimal phase runner state machine.
  - Deterministic transitions, failure reasons, checkpoint payload shape.
- **Day 3 (Wed):** Integrate memory retrieval per phase.
  - Use scoped retrieval with confidence threshold.
- **Day 4 (Thu):** Integrate proposal generation and approval gate hooks.
  - Enforce proposal-before-persist for persistent memory classes.
- **Day 5 (Fri):** Add unit tests for phase-gate transitions and memory hooks.

### Week 2 — Reports + deterministic eval + sample case

- **Day 6 (Mon):** Implement executive + technical report templates.
- **Day 7 (Tue):** Add structured fact/inference/unknown output model.
- **Day 8 (Wed):** Add deterministic evaluation harness for 2 playbooks.
- **Day 9 (Thu):** Build sample case run path from init → lessons learned.
- **Day 10 (Fri):** Stabilization, test hardening, CI integration gates.

## Exact task breakdown

1. Add schemas for phase contracts and state snapshots.
2. Add phase runner with strict transition map.
3. Add memory integration adapters (retrieve/propose/approve hooks).
4. Add report generators (executive + technical).
5. Add eval fixtures and deterministic scoring runner.
6. Add end-to-end test for one happy path + one failed approval path.

## First smallest commit

Create this plan document as the implementation anchor and acceptance checklist.

### Acceptance criteria for this commit

- Plan exists under `docs/`.
- Contains explicit day-by-day sequence for 2 weeks.
- Defines minimal v1 scope and anti-bloat intent.

