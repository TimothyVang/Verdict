#!/usr/bin/env bash
# run-swarm.sh — FALLBACK swarm path (subagent-driven, 20-wide).
#
# PRIMARY ENTRYPOINT IS scripts/run-team.sh (Claude Code Agent Teams, 4-5
# teammates per launch, sequential batches). This script remains as a fallback
# for cases where the experimental Agent Teams feature glitches (no /resume
# for in-process teammates, lead-shutdown-before-done, orphaned tmux, etc.).
#
# Architecture difference: run-team.sh creates a real Agent Team where
# teammates self-claim from a shared task list and message each other.
# run-swarm.sh (this file) drives an in-prompt Opus orchestrator that
# dispatches general-purpose Agent tool calls — same model tiering via
# subagent_type, but no inter-teammate messaging and no native task list.
#
# Authority: docs/AGENT_SWARM.md, CLAUDE.md §3 hard rules, swarm/deps.yaml
# requires_human list.
#
# Uses Claude Code (`claude -p`) as the harness. Auth via CLAUDE_CODE_OAUTH_TOKEN
# from .env (Claude Pro/Max subscription billing).
#
# Usage:
#   bash scripts/run-swarm.sh                  # foreground, watch live
#   nohup bash scripts/run-swarm.sh &          # overnight, detached
#   bash scripts/run-swarm.sh --skip-perms     # autonomous, no prompts (only after smoke)
#   N_PARALLEL=10 bash scripts/run-swarm.sh    # cap parallelism
#
# Resume-aware: discovers SHIPPED/IN_FLIGHT/BLOCKED/READY from `gh pr list` +
# swarm/deps.yaml at boot. Kill switches inside the prompt: TASK_CEILING new
# tasks max, PER_TASK_TURNS turns/task, halt on 5 consecutive failures, exit
# at MAX_SECONDS wall-clock. Override via env: N_PARALLEL, TASK_CEILING,
# PER_TASK_TURNS, MAX_SECONDS.

set -euo pipefail

cd "$(dirname "$0")/.."   # repo root

# ─── Pre-flight ───────────────────────────────────────────────────────────
[[ -f .env ]] || { echo "no .env file at repo root"; exit 1; }

set -a; source .env; set +a

[[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]] || { echo "CLAUDE_CODE_OAUTH_TOKEN missing in .env"; exit 1; }
[[ -n "${GITHUB_TOKEN:-}" ]]            || { echo "GITHUB_TOKEN missing in .env";            exit 1; }
command -v claude >/dev/null            || { echo "claude CLI not on PATH";                  exit 1; }
command -v gh >/dev/null                || { echo "gh CLI not on PATH";                      exit 1; }
gh auth status >/dev/null 2>&1          || { echo "gh not authenticated";                    exit 1; }

# ─── Run dir + sentinels ──────────────────────────────────────────────────
RUN_DATE="$(date +%F)"
RUN_DIR="cases/swarm-${RUN_DATE}"
LOGFILE="${RUN_DIR}/conductor.log"
START_TS="$(date +%s)"
MAX_SECONDS=14400   # 4 hours

# ─── Tunables (override via env) ─────────────────────────────────────────
N_PARALLEL="${N_PARALLEL:-20}"        # max concurrent task-workers
TASK_CEILING="${TASK_CEILING:-80}"    # absolute ceiling per run
PER_TASK_TURNS="${PER_TASK_TURNS:-60}"

mkdir -p "${RUN_DIR}"
echo "${START_TS}"               >  "${RUN_DIR}/START"
echo "${MAX_SECONDS}"            >  "${RUN_DIR}/MAX_SECONDS"
echo "$(date -Iseconds)"         >  "${RUN_DIR}/START_ISO"

# ─── Permission mode ──────────────────────────────────────────────────────
PERM_MODE="acceptEdits"
EXTRA_FLAGS=()
if [[ "${1:-}" == "--skip-perms" ]]; then
  EXTRA_FLAGS+=("--dangerously-skip-permissions")
  echo "WARNING: --dangerously-skip-permissions enabled — gh pr create / git push run unattended"
else
  EXTRA_FLAGS+=("--permission-mode" "${PERM_MODE}")
fi

# ─── Prompt ───────────────────────────────────────────────────────────────
PROMPT=$(cat <<EOF
You are operating as the autonomous build swarm for VERDICT (FIND EVIL! 2026 SANS hackathon entry). You are RESUMING a multi-day build, not starting fresh. Many tasks are already shipped; many PRs are open in draft awaiting human review; the rest of BUILD_PLAN.md is the work. You have a ${MAX_SECONDS}s wall-clock budget and a hard ceiling of ${TASK_CEILING} new tasks.

# Wall-clock & ceiling
Read ${RUN_DIR}/START (epoch seconds) and ${RUN_DIR}/MAX_SECONDS at the start of every dispatch decision. If \$(date +%s) - START >= MAX_SECONDS, finish in-flight workers, write ${RUN_DIR}/summary.md, exit cleanly. If new-tasks-claimed >= ${TASK_CEILING}, do the same.

# Authority order (lower yields to higher)
CLAUDE.md → docs/ARCHITECTURE.md → docs/BUILD_PLAN.md → docs/AGENT_SWARM.md → swarm/agents/*.md → swarm/deps.yaml. CLAUDE.md §3 hard rules are NEVER bent.

# ── Phase 0: Resume — discover state before claiming anything ────────────
Before any subagent dispatch, build four disjoint sets from live state. Do NOT trust prior summaries; recompute every run.

1. SHIPPED  = task IDs whose branch has a CLOSED-or-MERGED PR per \`gh pr list --state all --limit 200 --json number,title,state,headRefName\`. Parse [W#.#.#] from PR titles. Treat MERGED and CLOSED both as terminal.
2. IN_FLIGHT = task IDs with an OPEN-or-DRAFT PR (same query, state filter). Do not re-claim these.
3. WORKTREE_LOCKED = task IDs that have a directory under worktrees/ AND a remote branch \`feat/W#.#.#-*\` that is NOT in SHIPPED ∪ IN_FLIGHT. These are abandoned mid-run; reuse the worktree, push current state, and try to land a draft PR before claiming anything new.
4. BLOCKED = task IDs whose blockers in swarm/deps.yaml ⊄ SHIPPED, OR that appear in deps.yaml requires_human. Never claim BLOCKED.

READY = (all task IDs in BUILD_PLAN.md) − SHIPPED − IN_FLIGHT − WORKTREE_LOCKED − BLOCKED.

Order READY by phase prefix sort (W1.A < W1.B < … < W6.D), then numeric suffix. This is your work queue. Print READY's first 30 entries and the size of every set to ${RUN_DIR}/resume-snapshot.txt before dispatching.

If READY is empty, recover WORKTREE_LOCKED (one PR each), then write summary.md and exit. Do not invent work.

# ── Phase 1: Bounded parallel dispatch ───────────────────────────────────
You are NOT one agent — you are a swarm orchestrator. Maintain a semaphore of up to ${N_PARALLEL} concurrent task-workers. A "task-worker" is a single Agent dispatch (subagent_type="general-purpose") owning one task end-to-end: role-engineer → reviewer → auditor → log line.

Dispatch loop:
  while READY is non-empty AND not over budget AND not over ceiling:
    while in_flight < ${N_PARALLEL} AND READY non-empty:
      pop next task_id from READY
      compute role from swarm/conductor.py:PHASE_TO_SPECIALIZATION (W1.B→schema, W1.A.9→tool-wrapper, W1.G/W2.A/W2.C→planning, W2.D→sandbox, W4.C/W4.D/W4.E→eval, default tool-wrapper)
      compute branch = feat/{task_id}-{slug} (chore/ for docs-only tasks)
      run setup OUTSIDE the subagent (you do this):
        git worktree add worktrees/{task_id} -b {branch} origin/main
        cd worktrees/{task_id}; git status --porcelain must be empty
      dispatch ONE Agent call (run_in_background=true) with:
        system prompt = swarm/agents/_prefix.md + "\\n\\n---\\n\\n" + swarm/agents/{role}-engineer.md
        user prompt = the per-task template below, with placeholders filled and BUILD_PLAN entry quoted verbatim
      record (task_id, agent_id, started_at, branch) in your in-flight table
    Issue Agent tool calls for ALL freshly-popped tasks IN A SINGLE MESSAGE so they actually run concurrently.
    Wait for any worker to complete (you'll be notified). On completion:
      run reviewer subagent (sync) — system = _prefix.md + reviewer.md, user = "review PR \${pr_url}; run gh pr diff, pytest, ruff; post findings via gh pr review --comment"
      run auditor subagent (sync) — system = _prefix.md + auditor.md, user = "scan diff for §3.7 commit-msg shape, §3.8 forbidden deps, §3.10 mocks; gh pr review --comment"
      append one JSONL line to ${RUN_DIR}/log.jsonl: {ts, task_id, role, branch, pr_url, status, turns_used, commit_sha, notes}
      git worktree remove worktrees/{task_id} only if status == shipped
      free the semaphore slot
    re-check budget + ceiling

You MAY interleave: while waiting on slow workers, dispatch reviewers/auditors for already-completed ones. Reviewer + auditor stay sync (cheap, fast). Only the role-engineer pass uses run_in_background.

# Hard rules (non-negotiable — copied from CLAUDE.md §3, do not paraphrase to subagents)
- §3.7 TDD: failing test FIRST, run RED, implement, run GREEN, then ONE commit. Subject \`<type>(scope): summary [W#.#.#]\` — task ID mandatory. Allowed types: feat | fix | test | chore | docs | refactor. NO --no-verify, --no-gpg-sign, --amend. NO Claude watermarks (no Co-Authored-By: Claude, no 🤖 footer, no "Generated with Claude Code"). GPG- or SSH-signed.
- §3.10 No mocks of VERDICT internals. No Mock*/Fake*/Stub*/Dummy* against verdict.*. No httpx_mock/responses/vcr against Anthropic/SGLang/Langfuse. Patching a third-party at the system boundary in a single targeted test is OK.
- §3.8 New deps must be MIT or Apache-2.0. Forbidden list binding: Daytona, REMnux MCP linked, Llama 4, Gemma 3, Modal, LangSmith, Braintrust, Arize Phoenix, AutoGen v0.4, Microsoft Agent Framework, AGPL clean-rooms.
- §3.9 API keys / OAuth tokens never in committed files, microVMs, or code literals — \${VAR} substitution only.
- swarm/deps.yaml requires_human is BINDING (W1.A.4, W1.A.7, W4.C.1, W4.C.2, W4.C.3, W3.D.3). Re-read at every dispatch — the file may have changed since last run.
- Swarm has NO merge authority. Draft PRs only. Humans merge.
- Never modify CLAUDE.md, .env, .env.example, protocol-sift/, or another worktree.
- Never run: git push --force, git reset --hard on shared refs, gh pr merge, gh pr close, rm -rf, git branch -D, git config changes, git rebase -i.

# Kill switches (binding)
- Maximum ${TASK_CEILING} new tasks claimed in this run.
- Per task-worker: ${PER_TASK_TURNS} turns max. Exceeded → mark \`turn_budget_exceeded\`, free slot, move on.
- Per task-worker: 30 min wall-clock from dispatch. Exceeded → mark \`worker_timeout\`, free slot, leave the worktree under worktrees/ for next-run recovery.
- 5 consecutive worker failures (any reason except policy_violation) within a 20-task window → HALT. Write ${RUN_DIR}/HALT.md with last 5 task IDs, failure reasons, open worktree paths, exit. Reviewer/auditor failures do not count.
- Wall-clock check at every dispatch decision: if now - START >= MAX_SECONDS → finish in-flight, write summary.md, exit.
- Policy violation by a worker (force-push attempt, edit to CLAUDE.md/.env, forbidden dep, --no-verify, --no-gpg-sign, --amend, gh pr merge) → kill that worker as failed; log to ${RUN_DIR}/policy_violations.jsonl with the offending command/diff; do NOT count toward consecutive-failure ceiling; continue.

# Per-task user prompt template (substitute placeholders, paste BUILD_PLAN entry verbatim)
  You are the {role} for VERDICT. Read CLAUDE.md fully before any code. Implement task {task_id} per the entry in docs/BUILD_PLAN.md (quoted in full below).

  You are checked out at worktrees/{task_id} on branch {branch}. Do NOT cd elsewhere; do NOT git switch; do NOT touch other worktrees.

  Discipline:
  - TDD per CLAUDE.md §3.7. Failing test FIRST. Run it. See RED. Implement. Run again. See GREEN.
  - Conventional commit \`<type>(scope): summary [{task_id}]\`. NO Claude watermarks. NO --no-verify, --no-gpg-sign, --amend.
  - No mocks of VERDICT internals (§3.10). No new deps unless MIT/Apache-2.0 (§3.8).

  Workflow:
  1. Write the failing test exactly as named in the BUILD_PLAN entry.
  2. Run it; verify RED. Capture the output.
  3. Implement the smallest code that makes it pass.
  4. Run the test; verify GREEN. Capture the output.
  5. Run \`pytest tests/{relevant_dir}/ -q\` for regressions in your area.
  6. Run \`ruff check {touched_files}\` and fix.
  7. Stage only your touched files. Commit with the conventional message.
  8. Push: \`git push -u origin HEAD\`.
  9. Open a draft PR: \`gh pr create --draft --title "<commit-title>" --body "<task_id> + 3-line summary + RED snippet + GREEN snippet">\`.
  10. Print the PR URL on the LAST line of your output. Nothing after it.

  BUILD_PLAN entry (verbatim):
  <paste the full task block, from \`### {task_id}\` heading to the next \`### \`>

# Branch / worktree naming
For task T_id with title T, branch = \`feat/{T_id}-{slug}\` where slug = T.lower().replace(' ', '-')[:60], stripped of non-alphanumeric except '-'. Use \`chore/\` for docs-only (W*.G.*, any title containing "doc"/"checklist"). Worktree path is always \`worktrees/{T_id}\`. Never reuse a worktree across task IDs.

# Logging
Per task: one JSONL line to ${RUN_DIR}/log.jsonl. Fields: ts (ISO8601), task_id, role, branch, pr_url (or null), status (shipped | blocked | failed | policy_violation | turn_budget_exceeded | worker_timeout), turns_used, commit_sha (or null), reviewer_pr_comment_url (or null), auditor_pr_comment_url (or null), notes.

At HALT, ceiling, or wall-clock cutoff, write ${RUN_DIR}/summary.md:
- Sets at start: |SHIPPED|, |IN_FLIGHT|, |BLOCKED|, |WORKTREE_LOCKED|, |READY|.
- Tasks attempted this run with breakdown by status.
- Total worker turns consumed, peak parallelism reached.
- PR URLs grouped by status.
- Worktrees still on disk (recovery hints for next run).
- Open questions / blockers for the human.

# Begin
1. Run Phase 0. Write ${RUN_DIR}/resume-snapshot.txt. If READY is empty after WORKTREE_LOCKED recovery, write summary.md and exit.
2. Otherwise enter the dispatch loop. Saturate to ${N_PARALLEL} concurrent workers within the first three iterations.
3. Do not ask clarifying questions. If a task fails in a way the plan doesn't cover, log it as \`failed\` with notes, count it toward the consecutive-failure ceiling, and move on.
EOF
)

# ─── Launch ───────────────────────────────────────────────────────────────
echo "── VERDICT swarm launching at $(date -Iseconds) ──"        | tee -a "${LOGFILE}"
echo "   permission mode: ${EXTRA_FLAGS[*]}"                     | tee -a "${LOGFILE}"
echo "   wall budget    : ${MAX_SECONDS}s ($(( MAX_SECONDS / 3600 ))h)" | tee -a "${LOGFILE}"
echo "   run dir        : ${RUN_DIR}"                            | tee -a "${LOGFILE}"
echo "   tail this log  : tail -f ${LOGFILE}"                    | tee -a "${LOGFILE}"
echo                                                             | tee -a "${LOGFILE}"

claude "${EXTRA_FLAGS[@]}" -p "${PROMPT}" >> "${LOGFILE}" 2>&1
EXIT_CODE=$?

END_TS="$(date +%s)"
ELAPSED=$(( END_TS - START_TS ))
echo                                                             | tee -a "${LOGFILE}"
echo "── swarm exited at $(date -Iseconds), code=${EXIT_CODE}, elapsed=${ELAPSED}s ──" | tee -a "${LOGFILE}"

exit "${EXIT_CODE}"
