# Verdict

Workspace for **VERDICT**, an autonomous Windows DFIR / incident-response agent built for the SANS [FIND EVIL!](https://findevil.devpost.com/) 2026 hackathon.

> Plan-then-Execute LangGraph agent over the SANS SIFT Workstation, with cryptographic chain-of-custody, multi-mode (cloud / air-gap / dual) inference, and forensic discipline encoded at the schema and prompt layers. **Full-stack, real-services, no mocks** — see `CLAUDE.md` §3.10.

## Layout

```
Verdict/
├── CLAUDE.md                ← operating charter (read first)
├── README.md                ← this file
├── docs/
│   ├── README.md            ← docs index
│   ├── spec/                ← canonical VERDICT design docs (read-only)
│   │   ├── VERDICT_AUDIT_v4.3.md
│   │   ├── VERDICT_AUDIT_v4.4.md
│   │   ├── VERDICT_AUDIT_v4.5.md          ← canonical architecture
│   │   ├── VERDICT_v4.6_SPEC_PLAN.md      ← five tactical patches
│   │   └── VERDICT_MASTER_BUILD_PLAN.md   ← 6-week / 75-day execution plan
│   └── hackathon/
│       ├── RULES.md         ← official rules (eligibility, judging, prizes)
│       └── OVERVIEW.md      ← hackathon overview + resource links
├── downloads/               ← gitignored; manual large-binary fetches
│   ├── README.md
│   ├── sift-workstation/    ← SIFT OVA (8.81 GB; SANS Portal login)
│   └── evidence-samples/    ← case evidence (Slack-distributed)
└── protocol-sift/           ← cloned upstream Claude Code config framework
```

VERDICT source code (`verdict/`, `verdict-skills/`, `tests/`, `inspect_ai/`, `scripts/`, `.github/`, `packer/`) does not exist yet — its scaffolding is W1.A of the master build plan. See `CLAUDE.md` §6 for the target tree.

## Quick links

- Hackathon: https://findevil.devpost.com/
- Rules: `docs/hackathon/RULES.md`
- Overview: `docs/hackathon/OVERVIEW.md`
- Operating charter: `CLAUDE.md`
- Canonical architecture: `docs/spec/VERDICT_AUDIT_v4.5.md`
- Execution plan: `docs/spec/VERDICT_MASTER_BUILD_PLAN.md`
- Slack: https://join.slack.com/t/sansaihackathon/shared_invite/zt-3srjz86zo-bwHi_v1aKTg2IJAU4_4OwA
- Upstream config framework: `protocol-sift/` (https://github.com/teamdfir/protocol-sift)

## Items still requiring manual download

- **SIFT Workstation OVA (8.81 GB)** — SANS Portal login required. Save to `downloads/sift-workstation/`. See `downloads/README.md`.
- **Sample case evidence** (disk images, memory captures, pcaps) — distributed via the hackathon Slack, not via a public URL. Save to `downloads/evidence-samples/`.

## Deadlines

- Submission: **Jun 14 2026 EOD** (Devpost upload buffer); Jun 15 22:45 CDT official.
- Judging: Jun 19 – Jul 3 2026.
- Winners: ~Jul 8 2026.
