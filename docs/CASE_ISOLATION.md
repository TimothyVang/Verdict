# VERDICT — Case Isolation

> **Wiki:** [Index](README.md) · [Architecture](ARCHITECTURE.md) · [Build Plan](BUILD_PLAN.md) · [Failure Modes](FAILURE_MODES.md) · root [CLAUDE.md](../CLAUDE.md)

**Status:** Current. Defines case, chain, checkpoint, and reverify boundaries.
**Authority:** Below `ARCHITECTURE.md`; implements mode-lock and parallel verdict-chain semantics.

---

## Identifiers

| Identifier | Scope | Mutability | Purpose |
|---|---|---|---|
| `case_id` | Evidence set | Immutable | Root identifier for evidence manifest, ledger directory, and Langfuse session |
| `chain_id` | One mode-locked investigation chain | Immutable after chain creation | Distinguishes original run from reverify runs |
| `langgraph_thread_id` | One executable graph thread | Immutable | Checkpointer key; equals `chain_id` for all non-initial chains |
| `langgraph_checkpoint_id` | One super-step snapshot | Append-only | Resume and audit time-travel cursor |
| `finding_id` | One finding in one chain | Immutable | Human approval and export target |

## Original Chain

`verdict init <evidence_path>` creates:

- `case_id = <ulid>`
- `chain_id = f"{case_id}-original"`
- `mode_at_case_init = detect_mode()` or operator override
- `langgraph_thread_id = chain_id`
- `EvidenceManifest` with SHA-256 for every evidence file

The original chain owns the first append-only ledger sequence for the case. It is never mutated by `reverify`.

## Reverify Chain

`verdict reverify <case_id> --mode <mode>` creates a fresh parallel chain:

- `chain_id = f"{case_id}-reverify-{mode}-{utc_iso}"`
- `mode_at_case_init = <mode>`
- `langgraph_thread_id = chain_id`
- Evidence manifest copied by reference and re-hashed before execution
- Fresh planner, executor, verifier, and finalization ledger entries

The fork point is before `planner_node`, not at quorum. Reverify reruns the full mode-appropriate graph against the same evidence manifest so mode changes do not mix verifier strategies inside one chain.

## CLI Behavior

| Command | Behavior with multiple chains |
|---|---|
| `verdict show <case_id>` | Lists all `chain_id` values, modes, statuses, created timestamps, and finding counts |
| `verdict export <case_id>` | Defaults to `chain_id={case_id}-original`; accepts `--chain-id <id>` or `--chain-id all` |
| `verdict approve <case_id> <finding_id> --approver <approver>` | If the finding ID exists in more than one chain, fails and requires `--chain-id <id>` |
| `verdict validate <case_id>` | Validates every chain unless `--chain-id <id>` narrows scope |
| `verdict resume <case_id>` | Resumes only the latest interrupted chain if unambiguous; otherwise requires `--chain-id <id>` |

## Mode Lock

Each chain has exactly one `mode_at_case_init`. `verdict resume` refuses to advance a chain when current `detect_mode()` differs from that chain's mode. Mode changes always create a new chain through `verdict reverify`; they never alter an existing ledger sequence.

## Approval Isolation

Human approval signs `(finding_id, chain_id, approver, timestamp_utc, finding_hash)`. A finding approved in a cloud chain is not implicitly approved in a dual chain, even if both cite the same artifacts.
