# Archive — VERDICT audit history

These docs capture the evolution of VERDICT's design between May 1–2, 2026. They are **not** the current architecture authority — that's `../ARCHITECTURE.md`. Read these only when you need historical context for *why* a design decision was made.

## Files in chronological order

| File | What it captured | Superseded by |
|---|---|---|
| `01-audit-v4.3.md` | Initial Tim audit. Architecture v4 (three-mode verifier-gateway) + ten v4.3 cross-team interaction-surface fixes. Stack locked. | Subsumed into `../ARCHITECTURE.md` §1–§7 |
| `02-audit-v4.4.md` | Agentic design pass (depth C, ~2h literature review) + DFIR practitioner pass (depth A, FOR508/FOR500/FOR572 methodology). 24 findings: 6 BLOCKERS, 12 SHOULD-FIX, 6 NICE-TO-HAVE. Cited Wang 2022 self-consistency, Dhuliawala 2023 CoVe, Khan 2025 multi-agent debate failure modes, NIST SP 800-86, SANS Hunt Evil poster, etc. | Findings carried into `../ARCHITECTURE.md` §4 (forensic discipline as schema), §5 (chain-of-custody), §11 (open concerns) |
| `03-audit-v4.5.md` | Tim's architecture-review pass. Added threat model, Planner Protocol, executor_work split into 3 wrappers, ToolOutput base + EvidenceManifest + Artifact schemas, planner CoT capture, schema versioning, evidence manifest periodic re-hash, /health endpoint, FAILURE_MODES.md, CLI.md, sanitization for prompt injection. Removed unit-test mock layer. | Subsumed into `../ARCHITECTURE.md` §3 (three-layer immutability), §6 (tool surface), §9 (threat model) |
| `04-spec-plan-v4.6.md` | TDD-executable spec plan for the v4.4 BLOCKERS that v4.5 didn't pick up: seed-derivation fix (n=3 actually diverse), PreToolUse Layer-1 caveat, Finding schema patches (artifact_paths min_length=2, artifact_classes, caveats_acknowledged + validators), psscan + DKOM detection, three playbook YAMLs, examiner_caveats.md system-prompt include, hunt_evil.yml process baselines. Targeted Week 1. | Tasks integrated into `../BUILD_PLAN.md` Phase W1.B / W1.C / W1.D / W1.E / W1.F |

The original v4.6 visual TL;DR was promoted to `../TLDR.md` as a living, teammate-shareable primer (with refreshed Devpost deadlines, corrected verdict status vocabulary per `../../CLAUDE.md` §3.6, and required-skills/MCP/software section). The archive copy was deleted on 2026-05-02 to avoid drift.

## Why we keep these

1. **Decision rationale.** The v4.5 audit explains *why* we chose Microsandbox over Daytona, SGLang over vLLM, agentskills.io over Hermes-internal format, etc. If a teammate proposes "let's switch to Daytona," the answer lives in v4.5 (AGPL-3.0, clean-room rewrites don't strip copyright).

2. **Research provenance.** v4.4 has the full citation chain for cross-engine verification, Plan-then-Execute literature, hallucination defense, NIST SP 800-86, SANS posters. The current ARCHITECTURE.md refers to these without re-citing inline.

3. **Audit credibility.** Showing the document evolved through six numbered versions with explicit deltas demonstrates engineering rigor. Useful in the Devpost submission writeup if judges ask "how did you arrive at this design?"

## Authority

These archive docs do **not** override `../ARCHITECTURE.md`. If they conflict, ARCHITECTURE.md wins. If a fact in an archive doc is no longer true, leave the archive doc as-is — it captures what was true *at that time*.

For active work: read `../README.md` first, then `../ARCHITECTURE.md`, then `../BUILD_PLAN.md`. The archive is for "why," not "what to do next."
