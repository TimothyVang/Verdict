#!/usr/bin/env bash
# run-team.sh — launch a Claude Code Agent Team for the next batch of READY tasks.
#
# Authority: docs/AGENT_SWARM.md, CLAUDE.md §3, swarm/deps.yaml requires_human.
# Replaces scripts/run-swarm.sh as the primary entrypoint. run-swarm.sh remains
# as a subagent-driven fallback for cases where Agent Teams glitches.
#
# Per docs (https://code.claude.com/docs/en/agent-teams):
#   - Recommended team size: 3-5 teammates per launch; we use 4-5.
#   - Sequential batches; ~6-10 launches drain the remaining ~70-task backlog.
#   - Quality gate runs as TaskCompleted hook (.claude/hooks/task-completed.sh).
#   - Teammate model + tools come from .claude/agents/<role>.md frontmatter.
#
# Usage:
#   bash scripts/run-team.sh                  # headless, tail the log
#   bash scripts/run-team.sh --interactive    # type to monitor; Shift+Down to cycle teammates
#   BATCH_SIZE=4 bash scripts/run-team.sh     # cap batch at 4 ready tasks
#   MAX_SECONDS=3600 bash scripts/run-team.sh # 1h budget instead of default 2h

set -euo pipefail

cd "$(dirname "$0")/.."

# ─── Pre-flight ───────────────────────────────────────────────────────────
[[ -f .env ]] || { echo "no .env file at repo root"; exit 1; }

set -a; source .env; set +a

[[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]] || { echo "CLAUDE_CODE_OAUTH_TOKEN missing in .env"; exit 1; }
[[ -n "${GITHUB_TOKEN:-}" ]]            || { echo "GITHUB_TOKEN missing in .env";            exit 1; }
command -v claude >/dev/null            || { echo "claude CLI not on PATH";                  exit 1; }
command -v gh >/dev/null                || { echo "gh CLI not on PATH";                      exit 1; }
gh auth status >/dev/null 2>&1          || { echo "gh not authenticated";                    exit 1; }

# Agent Teams feature flag (v2.1.32+ required; we have v2.1.126)
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

# ─── Run dir + sentinels ──────────────────────────────────────────────────
RUN_DATE="$(date +%F-%H%M)"
RUN_DIR="cases/team-${RUN_DATE}"
LOGFILE="${RUN_DIR}/lead.log"
START_TS="$(date +%s)"
MAX_SECONDS="${MAX_SECONDS:-7200}"   # 2 hours default per batch
BATCH_SIZE="${BATCH_SIZE:-6}"        # target 5-8 ready tasks per team

mkdir -p "${RUN_DIR}"
echo "${START_TS}"        >  "${RUN_DIR}/START"
echo "${MAX_SECONDS}"     >  "${RUN_DIR}/MAX_SECONDS"
echo "$(date -Iseconds)"  >  "${RUN_DIR}/START_ISO"

# ─── Mode flags ───────────────────────────────────────────────────────────
HEADLESS=1
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --interactive)  HEADLESS=0; shift ;;
    --headless)     HEADLESS=1; shift ;;
    --batch)        BATCH_SIZE="$2"; shift 2 ;;
    *)              echo "unknown flag: $1"; exit 1 ;;
  esac
done

# ─── Lead-session prompt ──────────────────────────────────────────────────
PROMPT=$(cat <<EOF
You are the team lead for VERDICT (FIND EVIL! 2026 SANS hackathon entry). Read CLAUDE.md fully, then create a Claude Code Agent Team to drain the next batch of READY tasks from docs/BUILD_PLAN.md.

# Authority order (lower yields to higher)
CLAUDE.md → docs/ARCHITECTURE.md → docs/BUILD_PLAN.md → docs/AGENT_SWARM.md → swarm/agents/*.md → swarm/deps.yaml. CLAUDE.md §3 hard rules are NEVER bent.

# Phase 0: Resume — recompute live state, do NOT trust prior summaries
1. SHIPPED  = task IDs whose branch has a CLOSED-or-MERGED PR per \`gh pr list --state all --limit 200 --json number,title,state,headRefName\`. Parse [W#.#.#] from PR titles. Treat MERGED + CLOSED as terminal.
2. IN_FLIGHT = task IDs with an OPEN-or-DRAFT PR (same query, state filter).
3. WORKTREE_LOCKED = task IDs with a worktrees/ directory but no SHIPPED ∪ IN_FLIGHT match. Land their PRs before claiming new tasks.
4. BLOCKED = task IDs whose blockers in swarm/deps.yaml ⊄ SHIPPED, OR that appear in deps.yaml requires_human (W1.A.4, W1.A.7, W4.C.1, W4.C.2, W4.C.3, W3.D.3 — never claim).

READY = (all task IDs in BUILD_PLAN.md) − SHIPPED − IN_FLIGHT − WORKTREE_LOCKED − BLOCKED. Sort by phase prefix then numeric suffix. Write the first 30 to ${RUN_DIR}/resume-snapshot.txt with set sizes for context.

If READY is empty, recover WORKTREE_LOCKED first (one PR each); if still empty, write ${RUN_DIR}/summary.md and exit. Do not invent work.

# Phase 1: Spawn the team (4-5 teammates)
Pick the first ${BATCH_SIZE} tasks from READY. Tally roles via swarm/conductor.py:specialization_for (W1.B → schema, W1.A.9 → tool-wrapper, W1.G/W2.A/W2.C → planning, W2.D → sandbox, W4.C/W4.D/W4.E → eval, default tool-wrapper).

Choose 4-5 teammates that match the role distribution. Example: if the batch is 3 schema + 2 tool-wrapper + 1 sandbox, spawn 2× schema-engineer, 1× tool-wrapper-engineer, 1× sandbox-engineer (4 teammates). Use these subagent types from .claude/agents/: schema-engineer, planning-engineer, sandbox-engineer, tool-wrapper-engineer, eval-engineer. Each carries its own model (Sonnet for schema/sandbox/tool-wrapper/eval; Opus for planning) and tools allowlist.

BEFORE spawning each teammate, set up its first task's worktree:
  1. \`git worktree add worktrees/<task-id> -b feat/<task-id>-<slug> origin/main\` (chore/ prefix for docs-only tasks)
  2. Verify \`git -C worktrees/<task-id> status --porcelain\` is empty.

Then spawn each teammate with a prompt that includes:
  - The CLAUDE.md §3 hard rules verbatim (TDD, no mocks, no Claude watermarks; no --no-verify/--no-gpg-sign/--amend; GPG-signed conventional commits with [W#.#.#] task ID; allowed types feat|fix|test|chore|docs|refactor).
  - The teammate's worktree path: worktrees/<task-id>/.
  - The verbatim BUILD_PLAN entry (from \`### <task-id>\` heading to next \`### \`).
  - "Self-claim additional READY tasks of your role from the shared task list as you finish."

Spawn all teammates in a single message so they start concurrently.

# Phase 2: Coordinate, do not implement
Wait for teammates. Do NOT implement tasks yourself. The shared task list coordinates work; teammates self-claim follow-ons. If a teammate stalls, message them directly (Shift+Down) or spawn a replacement of the same role.

The .claude/hooks/task-completed.sh hook fires \`python -m swarm.reviewer review\` + \`python -m swarm.auditor scan\` automatically when a teammate marks a task complete. If the hook exits 2 with BLOCKING findings, the task stays in-progress and the teammate is told to revise. Review their fix; do not bypass the gate.

# Phase 3: Cleanup
When the shared task list is drained for this batch:
  1. Verify each completed task has a draft PR via \`gh pr list --draft\`.
  2. Append per-task lines to ${RUN_DIR}/log.jsonl: {ts, task_id, role, branch, pr_url, status, notes}.
  3. Write ${RUN_DIR}/summary.md: tasks attempted, status breakdown, PR URLs, worktrees still on disk, open questions for the human.
  4. Ask Claude to "Clean up the team" so ~/.claude/teams/<team-name>/ and ~/.claude/tasks/<team-name>/ are removed. Verify with \`ls ~/.claude/teams/ ~/.claude/tasks/\`.

# Hard rules (non-negotiable; the TaskCompleted hook enforces these mechanically)
- §3.7 TDD: failing test FIRST, run RED, implement, run GREEN, ONE commit. Subject \`<type>(scope): summary [W#.#.#]\` — task ID mandatory. NO --no-verify, --no-gpg-sign, --amend. NO Claude watermarks (no Co-Authored-By: Claude, no 🤖 footer, no "Generated with Claude Code"). GPG- or SSH-signed.
- §3.10 No mocks of VERDICT internals. No Mock*/Fake*/Stub*/Dummy* against verdict.*. No httpx_mock/responses/vcr standing in for Anthropic/SGLang/Langfuse. Patching a third-party at the system boundary in a single targeted test is OK.
- §3.8 New deps must be MIT or Apache-2.0. Forbidden list binding: Daytona, REMnux MCP linked, Llama 4, Gemma 3, Modal, LangSmith, Braintrust, Arize Phoenix, AutoGen v0.4, Microsoft Agent Framework, AGPL clean-rooms.
- §3.9 API keys / OAuth tokens never in committed files, microVMs, or code literals — \${VAR} substitution only.
- swarm/deps.yaml requires_human is BINDING. Re-read at every dispatch.
- Swarm has NO merge authority. Draft PRs only. Humans merge.
- Never modify CLAUDE.md, .env, .env.example, protocol-sift/, or another worktree.
- Never run: git push --force, git reset --hard on shared refs, gh pr merge, gh pr close, rm -rf, git branch -D, git config changes, git rebase -i.

# Wall budget
Read ${RUN_DIR}/START and ${RUN_DIR}/MAX_SECONDS at every coordination cycle. If \$(date +%s) - START >= MAX_SECONDS, finish in-flight teammates' current commits, write summary.md, clean up the team, exit.

# Begin
Run Phase 0, then Phase 1, then Phase 2, then Phase 3. Do not ask clarifying questions; the plan above is complete. If a teammate fails in a way the plan doesn't cover, log it as \`failed\` with notes and move on; do not retry indefinitely.
EOF
)

# ─── Launch ───────────────────────────────────────────────────────────────
echo "── VERDICT Agent Team launching at $(date -Iseconds) ──"   | tee -a "${LOGFILE}"
echo "   experimental    : CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=${CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS}" | tee -a "${LOGFILE}"
echo "   batch size      : ${BATCH_SIZE}"                        | tee -a "${LOGFILE}"
echo "   wall budget     : ${MAX_SECONDS}s ($(( MAX_SECONDS / 3600 ))h)" | tee -a "${LOGFILE}"
echo "   run dir         : ${RUN_DIR}"                           | tee -a "${LOGFILE}"
echo "   tail this log   : tail -f ${LOGFILE}"                   | tee -a "${LOGFILE}"
echo "   mode            : $([[ ${HEADLESS} -eq 1 ]] && echo 'headless (claude -p)' || echo 'interactive (Shift+Down cycles teammates)')" | tee -a "${LOGFILE}"
echo                                                             | tee -a "${LOGFILE}"

if [[ ${HEADLESS} -eq 1 ]]; then
  claude --teammate-mode in-process -p "${PROMPT}" >> "${LOGFILE}" 2>&1
else
  claude --teammate-mode in-process "${PROMPT}"
fi
EXIT_CODE=$?

END_TS="$(date +%s)"
ELAPSED=$(( END_TS - START_TS ))
echo                                                             | tee -a "${LOGFILE}"
echo "── team exited at $(date -Iseconds), code=${EXIT_CODE}, elapsed=${ELAPSED}s ──" | tee -a "${LOGFILE}"

exit "${EXIT_CODE}"
