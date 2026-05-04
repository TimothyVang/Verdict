#!/usr/bin/env bash
# task-completed.sh — TaskCompleted hook for VERDICT Agent Teams.
#
# Fires when a teammate marks a task complete. Runs swarm.reviewer (CI gate)
# + swarm.auditor (CLAUDE.md §3 scan) against the teammate's worktree. Emits
# {"decision": "block", "reason": "..."} on stdout if either gate fails, which
# rolls back the task completion and feeds the reason back to the teammate.
#
# Hook input (stdin JSON, per docs):
#   { session_id, transcript_path, cwd, permission_mode, hook_event_name }
# Task-specific fields are not documented; we infer worktree + branch from `cwd`
# (or the most-recently-modified worktrees/* directory as a fallback).
#
# Authority: docs/AGENT_SWARM.md §5 (review + audit gates), CLAUDE.md §3.

set -euo pipefail

# ─── Read hook payload ───────────────────────────────────────────────────
PAYLOAD="$(cat)"
HOOK_CWD="$(printf '%s' "$PAYLOAD" | jq -r '.cwd // empty')"
SESSION_ID="$(printf '%s' "$PAYLOAD" | jq -r '.session_id // "unknown"')"

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
LOG_DIR="${PROJECT_DIR}/cases/hooks"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/task-completed-$(date +%F).log"

log() { echo "[$(date -Iseconds)] [${SESSION_ID:0:8}] $*" >> "$LOG"; }

# ─── Resolve worktree + branch ───────────────────────────────────────────
WORKTREE=""
case "$HOOK_CWD" in
  */worktrees/*) WORKTREE="$HOOK_CWD" ;;
esac

if [[ -z "$WORKTREE" ]]; then
  # Fallback: most-recently-modified worktree directory
  WORKTREE="$(find "$PROJECT_DIR/worktrees" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' 2>/dev/null \
              | sort -rn | head -1 | cut -d' ' -f2- || true)"
fi

if [[ -z "$WORKTREE" || ! -d "$WORKTREE" ]]; then
  log "no worktree resolved (cwd=$HOOK_CWD); allowing task completion"
  exit 0
fi

BRANCH="$(git -C "$WORKTREE" branch --show-current 2>/dev/null || true)"
if [[ -z "$BRANCH" ]]; then
  log "no branch resolved at $WORKTREE; allowing task completion"
  exit 0
fi

log "gating worktree=$WORKTREE branch=$BRANCH"

# ─── Reviewer gate ───────────────────────────────────────────────────────
REVIEW_OUT=""
REVIEW_RC=0
if REVIEW_OUT="$(cd "$PROJECT_DIR" && python -m swarm.reviewer review \
                   --worktree "$WORKTREE" --branch "$BRANCH" 2>&1)"; then
  REVIEW_RC=0
else
  REVIEW_RC=$?
fi
log "reviewer rc=$REVIEW_RC"

# ─── Auditor gate ────────────────────────────────────────────────────────
AUDIT_OUT=""
AUDIT_RC=0
if AUDIT_OUT="$(cd "$WORKTREE" && python -m swarm.auditor scan --diff --base origin/main 2>&1)"; then
  AUDIT_RC=0
else
  AUDIT_RC=$?
fi
log "auditor rc=$AUDIT_RC"

# ─── Decide ──────────────────────────────────────────────────────────────
BLOCK_REASONS=()
if [[ $REVIEW_RC -ne 0 ]]; then
  BLOCK_REASONS+=("Reviewer (CI gate) failed: $(printf '%s' "$REVIEW_OUT" | tail -20)")
fi
if [[ $AUDIT_RC -ne 0 ]] || printf '%s' "$AUDIT_OUT" | grep -qE 'BLOCKING|severity=BLOCKING'; then
  BLOCK_REASONS+=("Auditor flagged BLOCKING §3 violations: $(printf '%s' "$AUDIT_OUT" | tail -20)")
fi

if [[ ${#BLOCK_REASONS[@]} -gt 0 ]]; then
  REASON_TEXT="$(printf '%s\n\n' "${BLOCK_REASONS[@]}")"
  REASON_TEXT+="Worktree: $WORKTREE  Branch: $BRANCH

Fix the issue(s) above and try marking the task complete again. Do NOT bypass with --no-verify or --amend; revise and re-commit per CLAUDE.md §3.7."
  log "BLOCKING completion; reasons: ${BLOCK_REASONS[*]}"
  jq -n --arg reason "$REASON_TEXT" '{decision: "block", reason: $reason}'
  exit 0
fi

log "PASS — review + audit clean"
exit 0
