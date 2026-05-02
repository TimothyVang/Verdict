---
description: Merge the current branch's PR (squash + delete branch). Refuses on main, requires CI green, asks before merging.
argument-hint: [pr-number]   — optional; defaults to PR for current branch
allowed-tools: Bash(git rev-parse:*), Bash(git fetch:*), Bash(gh pr view:*), Bash(gh pr checks:*), Bash(gh pr merge:*), AskUserQuestion
---

# /ship — merge the current branch's PR

Squash-merge the PR for the current branch into its base, delete the branch, and pull the result. **Conflicts with multiple house rules** (`scripts/run-swarm.sh:87` "humans merge"; `scripts/run-swarm.sh:89` "Never run gh pr merge" — that rule applies to *swarm subagents*, not to this human-driven slash command). Use sparingly.

## Hard rules

- REFUSE on `main` (no PR to merge; merging main into itself is nonsense).
- REFUSE on any branch under `worktrees/` (those belong to swarm subagents).
- REFUSE if the swarm conductor (`scripts/run-swarm.sh`) is currently running — check via `pgrep -f "claude.*run-swarm"` or `ls cases/swarm-*/conductor.log` for a recently-touched (< 5 min) log. The swarm depends on draft-PR-only state; merging mid-run desyncs its expectations.
- REFUSE if PR has unresolved review threads (`gh pr view --json reviewDecision` not `APPROVED` or `null`).
- REFUSE if CI is failing or pending. Wait for green.
- ALWAYS ask the user `Merge PR #N (<title>) now? [y/N]` via AskUserQuestion before invoking `gh pr merge`. No silent merges.
- ALWAYS use `--squash --delete-branch` (single tidy commit on base, branch removed). Never `--merge` (creates noisy merge commits) or `--rebase` (rewrites history, kills the swarm's GPG signatures on the original commits).
- NEVER force-merge (`--admin` flag) — if branch protection blocks the merge, the protection is correct; surface and stop.

## Workflow

1. **Branch check.** `git rev-parse --abbrev-ref HEAD`. If `main` or under `worktrees/` → REFUSE.

2. **Swarm-running check.** If `cases/swarm-*/conductor.log` was modified in the last 5 minutes (`find cases/ -name conductor.log -mmin -5`), surface it and REFUSE — the swarm is mid-run and merging now will desync its state.

3. **Find PR.** Use `$1` if supplied; else `gh pr view --json number,title,state,reviewDecision,mergeable,mergeStateStatus,baseRefName`. If no PR → REFUSE ("create one with `/qc` first").

4. **State check.**
   - `state` must be `OPEN` (not `DRAFT`, `MERGED`, `CLOSED`).
     - If `DRAFT`: ask the user "Mark PR #N ready and merge? [y/N]" via AskUserQuestion. If yes, run `gh pr ready <N>` then continue.
   - `reviewDecision` must be `APPROVED` or `null` (no required reviewers).
     - `CHANGES_REQUESTED` → REFUSE; surface review URL.
   - `mergeable` must be `MERGEABLE`.
     - `CONFLICTING` → REFUSE; tell the user to resolve.
     - `UNKNOWN` → wait 5s, retry once.
   - `mergeStateStatus` must be `CLEAN`, `HAS_HOOKS`, or `UNSTABLE`.
     - `BEHIND` → REFUSE; tell the user to update the branch (`gh pr update-branch <N>`, no auto).
     - `BLOCKED` → REFUSE; print the blocker reason.
     - `DIRTY` → REFUSE; conflicts.

5. **CI check.** `gh pr checks <N> --required`. If any required check is `FAIL`/`PENDING`/`CANCELLED` → REFUSE. Tell the user which check; offer to wait (sleep 30s, recheck — max 3 retries) or to abort.

6. **Confirm with user.** AskUserQuestion: `Merge PR #<N> "<title>" into <baseRefName> (squash + delete branch)? [y/N]`. Only proceed on explicit `y`.

7. **Merge.** `gh pr merge <N> --squash --delete-branch`. On success, `git fetch --prune` and `git checkout <baseRefName>` and `git pull --ff-only` to sync the local base.

8. **Confirm.** Print: `Merged PR #<N> as <new-base-sha>. Local <baseRefName> updated. Branch <head> deleted.`

## What this command will NEVER do

- Force-merge (`--admin`).
- Force-push.
- Bypass branch protection.
- Merge without an explicit `y` from the user.
- Merge while the swarm is mid-run (would desync `cases/swarm-*/log.jsonl`).
- Merge a PR you didn't author and aren't on (no shared-state surprises).
