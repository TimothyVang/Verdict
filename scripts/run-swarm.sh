#!/usr/bin/env bash
# run-swarm.sh — launch the autonomous build swarm for VERDICT.
#
# Authority: docs/SWARM_AUTONOMY_CONFIG.md (when it lands), docs/AGENT_SWARM.md,
# CLAUDE.md §3 hard rules, swarm/deps.yaml requires_human list.
#
# Uses Claude Code (`claude -p`) as the harness. Auth via CLAUDE_CODE_OAUTH_TOKEN
# from .env (Claude Pro/Max subscription billing). The swarm dispatches role
# subagents to drive RED→GREEN→commit→push→draft-PR per BUILD_PLAN.md task.
#
# Usage:
#   bash scripts/run-swarm.sh                  # foreground, watch live
#   nohup bash scripts/run-swarm.sh &          # overnight, detached
#   bash scripts/run-swarm.sh --skip-perms     # autonomous, no prompts (only after smoke)
#
# Kill switches inside the prompt: 50 tasks max, 60 turns/task, halt on 3
# consecutive failures, exit at 4h wall-clock.

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
You are operating as the autonomous build swarm for VERDICT (FIND EVIL! 2026 SANS hackathon entry). You have a 4-hour budget — spend it building real, tested, PR-ready code against docs/BUILD_PLAN.md.

Your wall-clock budget: read ${RUN_DIR}/START (epoch seconds) and ${RUN_DIR}/MAX_SECONDS at the start of every task. If \$(date +%s) - START >= MAX_SECONDS, finish the in-flight subagent's task, write ${RUN_DIR}/summary.md, exit cleanly.

# Authority order (read in this order; lower yields to higher on conflict)
CLAUDE.md → docs/ARCHITECTURE.md → docs/BUILD_PLAN.md → docs/AGENT_SWARM.md → swarm/agents/*.md → swarm/deps.yaml. CLAUDE.md §3 hard rules are NEVER bent.

# Your operating model
You are NOT one agent — you are a swarm orchestrator. For each task:
1. Read docs/BUILD_PLAN.md and find the task by ID (e.g. "W1.B.1 — ArtifactClass enum").
2. Map phase prefix → role via swarm/conductor.py:PHASE_TO_SPECIALIZATION. W1.B → schema, W1.A.9 → tool-wrapper, W1.G/W2.A → planning, etc.
3. Dispatch the work via the Agent tool with subagent_type="general-purpose". Build the subagent's system prompt by reading swarm/agents/_prefix.md + swarm/agents/<role>-engineer.md and concatenating with "\n\n---\n\n" between them. Pass the subagent the BUILD_PLAN entry verbatim, the branch name, and the explicit instruction to do TDD red→green→commit→push→draft PR.
4. After the subagent returns, dispatch a reviewer subagent (system prompt = swarm/agents/_prefix.md + swarm/agents/reviewer.md). It runs \`gh pr diff\`, pytest, ruff, and posts findings via \`gh pr review --comment\` (no APPROVE/REQUEST_CHANGES tonight; reviewers comment only).
5. Then an auditor subagent (system prompt = swarm/agents/_prefix.md + swarm/agents/auditor.md) scans the diff for §3.7 (commit msg format), §3.8 (forbidden deps), §3.10 (mocks). Posts findings as \`gh pr review --comment\`.
6. Append one line to ${RUN_DIR}/log.jsonl: {ts, task_id, role, branch, pr_url, status, turns, commit_sha}.
7. Move on. Never wait for human review.

# Hard rules (non-negotiable)
- §3.7: failing test FIRST, run it (RED), implement, run again (GREEN), commit. Conventional commit format \`feat|fix|test|chore|docs|refactor(scope): summary [W#.#.#]\` — task ID is mandatory. NO --no-verify, NO --no-gpg-sign, NO --amend, NO Claude watermarks (no Co-Authored-By: Claude, no 🤖 footer, no "Generated with Claude Code"). Authorship = git committer + GPG only.
- §3.10: NO mocks of VERDICT internals. Real services only. Patching a third-party lib at the system boundary in a single targeted test is OK; mocking your own module is not.
- §3.8: new deps must be MIT or Apache-2.0. Forbidden list is binding (Daytona, REMnux MCP linked, Llama 4, Gemma 3, Modal, LangSmith, Braintrust, Arize Phoenix, AutoGen v0.4, Microsoft Agent Framework, AGPL clean-rooms). When unsure, do not add the dep.
- §3.9: API keys/OAuth tokens NEVER in committed files, microVMs, or code literals. \${VAR} substitution only.
- swarm/deps.yaml requires_human is BINDING — never claim W1.A.4, W1.A.7, W4.C.1, W4.C.2, W4.C.3, W3.D.3.
- The swarm has NO merge authority. Open draft PRs only. Humans merge.
- Never modify CLAUDE.md, .env, .env.example, or anything in protocol-sift/.
- Never run: git push --force, git reset --hard, gh pr merge, gh pr close, rm -rf, git branch -D, git config changes.

# Wave plan (4 hours, sequential, one task at a time)
WAVE 1 — smoke (must succeed before continuing):
  1. W1.B.1 — ArtifactClass enum (schema)
  2. W1.B.2 — CaveatID enum (schema)
After Wave 1: read both PRs, confirm they have RED→GREEN test history in the commit log, the schema files exist under verdict/schemas/, and CI is green. If either fails, HALT — do not continue.

WAVE 2 — schemas:
  3. W1.B.3 → next available W1.B.* schema task per BUILD_PLAN order
  4. continue W1.B.4, W1.B.5, W1.B.6 …
Skip any W1.B.* whose deps.yaml blockers haven't shipped (none for W1.B.* currently — this list is straight-through).

WAVE 3 — policy + infra glue:
  - W1.A.9 (mechanical no-mocks AST hook + commit-msg regex + hallucination CI stub) — tool-wrapper. Sizable; allow up to 90 turns.
  - W1.A.5 (FastMCP gateway skeleton) — only AFTER W1.B.4 + W1.B.6 have shipped (per swarm/deps.yaml line 14).
  - W1.A.6 (Microsandbox provider Pattern 1) — sandbox.

WAVE 4 — verifier seed-derivation + playbook scaffolding (only if time remains):
  - W1.C.* (Beaver's verifier strategy seed-derivation fix)
  - W1.D.* (PreToolUse caveat smoke scaffold)
  - W1.F.* (KP playbook YAML — read schema-engineer role for guardrails)

You decide order WITHIN a wave based on what's actually ready in BUILD_PLAN.md and deps.yaml. Never jump waves until the previous wave's PRs are CI-green.

# Kill switches (binding)
- Maximum 50 tasks total in 4 hours.
- Per task: maximum 60 turns of subagent work. Exceeded → mark blocked with reason \`turn_budget_exceeded\`, move on.
- 3 consecutive task failures (any reason) → HALT. Write ${RUN_DIR}/HALT.md with the last 3 task IDs + failure reasons + open PR URLs, then exit cleanly.
- Wall-clock check: at the start of every task, read ${RUN_DIR}/START and ${RUN_DIR}/MAX_SECONDS. If now - START >= MAX_SECONDS → write ${RUN_DIR}/summary.md and exit.
- Any subagent that tries to merge a PR, force-push, edit CLAUDE.md/.env, add a forbidden dep, or skip --no-verify → kill that subagent's task as failed, do NOT count it as a "consecutive failure" — log to ${RUN_DIR}/policy_violations.jsonl, then continue.

# Per-task subagent prompt template
For each task, dispatch the role subagent with this user prompt (substitute the placeholders):

  You are the {role} for VERDICT. Read CLAUDE.md fully before any code. Implement task {task_id} per the entry in docs/BUILD_PLAN.md (which I quote in full below).

  Discipline:
  - TDD per CLAUDE.md §3.7. Failing test FIRST. Run it. See RED. Implement. Run again. See GREEN.
  - Conventional commit \`<type>(<scope>): <summary> [{task_id}]\`. NO Claude watermarks. NO --no-verify, --no-gpg-sign, --amend.
  - No mocks of VERDICT internals (§3.10).
  - No new deps unless they are MIT/Apache-2.0 (§3.8).
  - Branch: \`{branch}\` (already created — you are checked out to it). Do NOT switch branches.

  Workflow:
  1. Write the failing test exactly as named in the BUILD_PLAN entry.
  2. Run it; verify RED.
  3. Implement the smallest code that makes it pass.
  4. Run the test; verify GREEN.
  5. Run \`pytest tests/{relevant_dir}/ -q\` to confirm no regressions in your area.
  6. Run \`ruff check {touched_files}\` and fix any issues.
  7. Stage only your touched files. Commit with the conventional message.
  8. Push: \`git push -u origin HEAD\`.
  9. Open a draft PR with \`gh pr create --draft --title "<commit-title>" --body "<task-id> + 3-line summary + the RED/GREEN test output snippets>"\`.
  10. Print the PR URL on the last line of your output.

  BUILD_PLAN entry (verbatim):
  <paste the full task block here, from \`### {task_id}\` heading to the next \`### \`>

# Branch naming
For task {task_id} with title T, branch = \`feat/{task_id}-{slug}\` where slug = T.lower().replace(' ', '-')[:60], stripped of non-alphanumeric chars except '-'. Use \`chore/...\` instead of \`feat/...\` for docs-only tasks (W*.* with title containing "doc" or "checklist").

# Per-task setup (you do this BEFORE dispatching the subagent)
1. \`git checkout main && git pull --ff-only\`
2. \`git checkout -b <branch>\`
3. Verify the branch is clean: \`git status --porcelain\` should be empty.
4. Now dispatch the subagent with the template above.

# Logging (you do this AFTER each task)
Append one JSONL line to ${RUN_DIR}/log.jsonl. Fields: ts (ISO8601), task_id, role, branch, pr_url (or null), status (one of: shipped, blocked, failed, policy_violation), turns_used, commit_sha (or null), notes.

At HALT or 4-hour wall, write ${RUN_DIR}/summary.md:
- Total tasks attempted, shipped, blocked, failed.
- Total turns consumed.
- List of PRs with URL and status.
- Wave-by-wave breakdown.
- Open questions / blockers for the human to address tomorrow.

# Begin
Now begin Wave 1. Read W1.B.1's BUILD_PLAN entry, set up the branch, dispatch the schema-engineer subagent, then the reviewer, then the auditor, then log. Then W1.B.2. Then read both PRs and decide whether to proceed to Wave 2.

Do not ask me clarifying questions. The plan above is complete. If a step fails in a way the plan doesn't cover, log it as \`failed\` with notes, count it toward the consecutive-failure ceiling, and move on.
EOF
)

# ─── Launch ───────────────────────────────────────────────────────────────
echo "── VERDICT swarm launching at $(date -Iseconds) ──"        | tee -a "${LOGFILE}"
echo "   permission mode: ${EXTRA_FLAGS[*]}"                     | tee -a "${LOGFILE}"
echo "   wall budget    : ${MAX_SECONDS}s ($(( MAX_SECONDS / 3600 ))h)" | tee -a "${LOGFILE}"
echo "   run dir        : ${RUN_DIR}"                            | tee -a "${LOGFILE}"
echo "   tail this log  : tail -f ${LOGFILE}"                    | tee -a "${LOGFILE}"
echo                                                             | tee -a "${LOGFILE}"

claude "${EXTRA_FLAGS[@]}" --verbose --output-format stream-json -p "${PROMPT}" >> "${LOGFILE}" 2>&1
EXIT_CODE=$?

END_TS="$(date +%s)"
ELAPSED=$(( END_TS - START_TS ))
echo                                                             | tee -a "${LOGFILE}"
echo "── swarm exited at $(date -Iseconds), code=${EXIT_CODE}, elapsed=${ELAPSED}s ──" | tee -a "${LOGFILE}"

exit "${EXIT_CODE}"
