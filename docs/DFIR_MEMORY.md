# DFIR Self-Evolving Memory (SANS-Aligned)

> **Wiki:** [Index](README.md) · [Architecture](ARCHITECTURE.md) · [Failure Modes](FAILURE_MODES.md) · [Case Isolation](CASE_ISOLATION.md) · root [CLAUDE.md](../CLAUDE.md)

This document defines VERDICT's memory model for **evidence-first** incident response. It is intentionally conservative: memory is allowed to evolve, but only through governed, auditable mutations.

## Goals

- Keep memory useful across investigations without contaminating conclusions.
- Ensure persistent memory remains tied to evidence references.
- Separate **facts**, **inference**, and **unknowns** in every update path.

## Memory Layers

1. **Case memory** (`case`) — short-lived incident context, may be ephemeral.
2. **Technique memory** (`technique`) — reusable investigative methods and checklists.
3. **Pattern memory** (`pattern`) — observed evidence patterns with confidence scoring.
4. **Meta memory** (`meta`) — policy, governance, and validation behavior.

## Controlled Evolution Rules

Only these operations are allowed:

- `strengthen` — raise confidence with corroborating evidence.
- `weaken` — reduce confidence due to counterevidence.
- `fork` — split a memory pattern into scoped variants.
- `deprecate` — retire stale/invalid memory using tombstones.
- `revalidate` — refresh confidence and timestamp without rewriting lineage.

## Validation Requirements

For persistent classes (`technique`, `pattern`, `meta`):

- At least one `evidence_ref` is required.
- `last_validated_at` must be on/after `created_at`.
- `expiry`, when present, must be after `created_at`.
- Versioning is monotonic (`version >= 1`) and lineage is retained.

## Write Path

1. Agent creates a `MemoryUpdateProposal`.
2. Schema/policy gate validates structure + evidence linkage.
3. Approval state transitions (`proposed` → `approved` / `rejected`).
4. Approved entries are persisted with incremented version metadata.

This keeps memory evolution aligned to DFIR chain-of-custody principles.
