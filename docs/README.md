# docs/

Project documentation. The root `README.md` is the entry point and includes the canonical doc map; this file is a flat index of what lives here.

## Authority order

Devpost rules → `DEVPOST_COMPLIANCE.md` → `ARCHITECTURE.md` → `BUILD_PLAN.md` → root `CLAUDE.md` → `archive/`.

If a doc and the code disagree, code wins. Fix the doc.

## Layout

```
docs/
├── README.md                    ← this file
├── ARCHITECTURE.md              ← current authoritative architecture
├── BUILD_PLAN.md                ← 6-week TDD execution plan (slim INDEX → build/week-N.md)
├── STATUS.md                    ← as-built snapshot (refresh from git ls-tree + git log)
├── build/                       ← per-week phases + teammates + appendices
├── DEVPOST_COMPLIANCE.md        ← submission rule-to-artifact mapping
├── DOCS_ACCURACY_REPORT.md      ← cross-doc consistency audit
├── archive/                     ← audit history (older docs — reference only)
│   ├── README.md                ← what each archive doc captured
│   ├── 01-audit-v4.3.md
│   ├── 02-audit-v4.4.md
│   ├── 03-audit-v4.5.md
│   ├── 04-spec-plan-v4.6.md
│   └── 05-tldr-original.md
└── hackathon/
    ├── RULES.md                 ← official SANS FIND EVIL! rules
    └── OVERVIEW.md              ← hackathon overview + resource links
```

## Coming soon (W1+ deliverables — see `BUILD_PLAN.md`)

These are referenced by `CLAUDE.md` and `BUILD_PLAN.md` but not yet authored:

- `THREAT_MODEL.md` — four threat surfaces (insider, prompt-injection-from-evidence, malicious-tool-output, external-attacker)
- `FAILURE_MODES.md` — component × failure × recovery matrix
- `CLI.md` — full `verdict` command surface
- `CHECKPOINTING.md` — SqliteSaver + WAL + reducer pattern
- `CASE_ISOLATION.md` — RadixAttention prefix-cache vs case data
- `SCOPE.md` — v1 = Windows DFIR; v2 roadmap (macOS / Linux / ESXi)
- `SCHEMA_MIGRATION.md` — breaking-change migration policy
- `SANS_JUDGE_CHECKLIST.md` — 15-item demo rubric (W6)
- `PRODUCTION_AUDIT.md` — v4 triage (v1 vs v2)
- `DEMO_SEQUENCE.md` — 5-min storyboard with timing (W6)
- `ACCURACY_REPORT.md` — per-mode tables + correlation analysis (W6)

## Editing rules

- **Never edit `archive/`.** Those files capture point-in-time decisions; they're cited from `ARCHITECTURE.md` and would lose meaning if rewritten.
- **`ARCHITECTURE.md` is the single architectural authority.** If you change a component, update it here, not in `archive/`.
- **`BUILD_PLAN.md` task IDs** are immutable once a contributor has committed against them. New work gets a new ID.
