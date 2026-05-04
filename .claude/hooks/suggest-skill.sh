#!/usr/bin/env bash
# suggest-skill.sh — UserPromptSubmit hook. Calls Opus to read the user prompt
# + the available skills under .claude/skills/ and ~/.claude/skills/, then
# emits a one-screen suggestion (skill, how to use it, 2-3 follow-up prompt
# variants) as the hook's additionalContext. Falls back to a static reminder
# if Opus is unavailable, slow, or errors.
#
# Authority: docs/AGENT_SWARM.md (hook discipline), CLAUDE.md §3 hard rules.

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
LOG_DIR="${PROJECT_DIR}/cases/hooks"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/suggest-skill-$(date +%F).log"
TIMEOUT_SECS=30

log() { echo "[$(date -Iseconds)] $*" >> "$LOG"; }

# ─── Read hook payload ───────────────────────────────────────────────────
PAYLOAD="$(cat)"
USER_PROMPT="$(printf '%s' "$PAYLOAD" | jq -r '.prompt // empty')"

# ─── Static-fallback reminder (if Opus call fails / times out / no claude on PATH) ─
emit_static() {
  local reason="$1"
  log "fallback: $reason"
  jq -n --arg ctx "Before responding, scan the available-skills list in this turn's system reminder and pick the single most relevant skill. Print one line at the top of your response: \`**Suggested skill:** /skill-name — why\` (or \`none\` if nothing fits). Do NOT auto-invoke. (dynamic-suggestion fallback: $reason)" \
    '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$ctx}}'
}

# ─── Skip empty prompts (slash-only commands, etc.) ──────────────────────
if [[ -z "$USER_PROMPT" || "${#USER_PROMPT}" -lt 3 ]]; then
  emit_static "prompt too short or empty"
  exit 0
fi

# ─── Need claude CLI ──────────────────────────────────────────────────────
if ! command -v claude >/dev/null 2>&1; then
  emit_static "claude CLI not on PATH"
  exit 0
fi

# ─── Build the catalogue of available skills (project + global) ──────────
catalog=""
for dir in "$PROJECT_DIR/.claude/skills" "$HOME/.claude/skills"; do
  [[ -d "$dir" ]] || continue
  for skill_md in "$dir"/*/SKILL.md; do
    [[ -f "$skill_md" ]] || continue
    name="$(basename "$(dirname "$skill_md")")"
    desc="$(awk '/^description:/{sub(/^description: */,""); print; exit}' "$skill_md")"
    catalog+="- /${name}: ${desc}"$'\n'
  done
done

if [[ -z "$catalog" ]]; then
  emit_static "no skills catalogue found"
  exit 0
fi

# ─── Build the meta-prompt for Opus ──────────────────────────────────────
META_PROMPT=$(cat <<EOF
You are a hook helper, not the user's main coding agent. Your job: in <=120 words total, advise the user's PRIMARY agent on what skill to suggest and what follow-up prompts to offer.

USER'S CURRENT PROMPT:
${USER_PROMPT}

AVAILABLE SKILLS (project-local + global, name + description):
${catalog}

Output EXACTLY this template — no preamble, no closing remarks:

**Suggested skill:** \`/skill-name\` — <one-sentence why it fits>
**How to use:** <one or two sentences on the right invocation form (\`/name\` slash command, or "tell Claude to use it inline">
**Try a sharper prompt:**
- "<concrete prompt variant 1, ≤140 chars>"
- "<concrete prompt variant 2, ≤140 chars>"
- "<concrete prompt variant 3, ≤140 chars>"

Rules:
- Pick exactly one skill from the AVAILABLE SKILLS list. If literally nothing fits (greeting / thanks / typo), set Suggested skill to \`none\` and skip How-to-use; still propose 2-3 sharper prompts.
- Sharper prompts must be more specific than what the user wrote — name a file, scope, or success criterion they left implicit.
- Do NOT execute the skill. Do NOT call any tool. Just emit the template.
EOF
)

# ─── Call Opus, capture output, time-bound ───────────────────────────────
# Pipe META_PROMPT via stdin to avoid ARG_MAX (the skills catalogue alone can
# push the arg vector past the limit on small embedded shells).
SUGGESTION=""
if SUGGESTION="$(printf '%s' "$META_PROMPT" | timeout "${TIMEOUT_SECS}s" claude -p --model claude-opus-4-7 2>>"$LOG")"; then
  if [[ -n "$SUGGESTION" ]]; then
    log "ok: $(printf '%s' "$SUGGESTION" | wc -c) chars from Opus"
    jq -n --arg ctx "$SUGGESTION" \
      '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$ctx}}'
    exit 0
  fi
fi

emit_static "Opus call failed or empty"
