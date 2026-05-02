# docs/

All project documentation. Two stable subdirectories today; project-authored docs (ARCHITECTURE.md, BUILD.md, THREAT_MODEL.md, etc.) will land here as W1+ master-plan work delivers them.

## Layout

```
docs/
├── README.md            ← this file
├── spec/                ← canonical VERDICT design docs (read-only inputs)
│   ├── VERDICT_AUDIT_v4.3.md            ← system-design review (10 fixes)
│   ├── VERDICT_AUDIT_v4.4.md            ← threat-model + DFIR-discipline review (24 fixes)
│   ├── VERDICT_AUDIT_v4.5.md            ← canonical architecture (drops mock layer)
│   ├── VERDICT_v4.6_SPEC_PLAN.md        ← five tactical patches over v4.5
│   └── VERDICT_MASTER_BUILD_PLAN.md     ← 6-week / 75-teammate-day execution plan
└── hackathon/           ← SANS FIND EVIL! meta
    ├── RULES.md         ← official rules (eligibility, judging, prizes, IP)
    └── OVERVIEW.md      ← deliverables, links, install commands
```

## Authority chain (when specs disagree)

**v4.6 patches > v4.5 architecture > v4.4 / v4.3 history.**
Master build plan defines *what* to build *when*, not *what is*.

See `../CLAUDE.md` §2 for the full table.

## Coming soon (W1.A+ deliverables)

These will land under `docs/` as the master plan executes:

- `ARCHITECTURE.md` — system diagram + node-by-node walkthrough
- `BUILD.md` — exact build steps from a fresh SIFT VM
- `THREAT_MODEL.md` — four threat surfaces
- `FAILURE_MODES.md` — component × failure × recovery matrix
- `CLI.md` — `verdict` command surface
- `CHECKPOINTING.md` — SqliteSaver + WAL + reducer pattern
- `CASE_ISOLATION.md` — RadixAttention prefix-cache vs case data
- `SCOPE.md` — v1 = Windows DFIR; v2 roadmap
- `SCHEMA_MIGRATION.md` — breaking-change migration policy
- `SANS_JUDGE_CHECKLIST.md` — 15-item demo rubric
- `PRODUCTION_AUDIT.md` — v4 triage (v1 vs v2)
- `DEMO_SEQUENCE.md` — 5-minute storyboard
- `ACCURACY_REPORT.md` — per-mode tables + correlation analysis

Do **not** edit anything in `spec/` — those are immutable specifications. Project-authored docs live as siblings of `spec/`.
