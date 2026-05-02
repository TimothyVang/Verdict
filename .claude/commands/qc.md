---
description: Quick commit + push + draft PR (CLAUDE.md §3.7 — never force-push, never merge; use /ship for merge)
argument-hint: [task-id] [message]   — both optional, inferred from branch + diff if omitted
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git rev-parse:*), Bash(git symbolic-ref:*), Bash(git fetch:*), Bash(gh pr view:*), Bash(gh pr create:*), Read, Grep
---

# /qc — quick commit + push + (optional) draft PR

Commit the working tree, push to the current branch, and open a draft PR if one doesn't exist. CLAUDE.md §3.7-compliant. **Never** `--force`, `--amend`, `--no-verify`, `--no-gpg-sign`, `gh pr merge`. For merge, use `/ship`.

## Input

`$ARGUMENTS` is everything after `/qc`. Both fields optional:

  `[task-id] [conventional-commit-subject]`

If either is missing, infer:

- **task-id** missing → derive from current branch name. Match `^(feat|fix|chore|test|docs|refactor)/(W\d+\.[A-Z]+\.\d+)-`. If the branch is `main` or doesn't match, refuse and ask the user for the task-id.
- **subject** missing → infer from the diff:
  - **type** — new file under `tests/` → `test`; pyproject/Cargo/package.json deps → `chore(deps)`; doc-only (`*.md`, `docs/`) → `docs`; new file under `verdict/` or `swarm/` → `feat`; bug fix per diff intent → `fix`; structural rewrite no behavior change → `refactor`; script/config/CI → `chore`.
  - **scope** — directory closest to the changed files (`swarm`, `schema`, `mcp`, `runtime`, `tooling`, `env`, `tests`, …).
  - **summary** — one-line factual description of the diff. Read the diff with `git diff --cached` (after staging) or `git diff` (before). Don't fabricate; if the diff is unclear, refuse and ask the user.

## Hard rules (CLAUDE.md §3.7 — non-negotiable)

- Final subject MUST match: `^(feat|fix|test|chore|docs|refactor)(\([a-z0-9-]+\))?: .+ \[W\d+\.[A-Z]+\.\d+\]$`
- NEVER pass `--no-verify`, `--no-gpg-sign`, `--amend`, `--allow-empty`.
- NEVER pass `--force`, `-f`, `+<ref>` to `git push`.
- NEVER call `gh pr merge`, `gh pr close`, `gh pr ready` (use `/ship` for merge).
- NO Claude watermarks: no `Co-Authored-By: Claude …`, no `🤖 Generated with [Claude Code]`, no "Generated with Claude Code" footer.

## Workflow

1. **Inspect.** `git status --porcelain` + `git diff --stat`. Empty → "nothing to commit, working tree clean" and stop.

2. **Confirm branch.** `git rev-parse --abbrev-ref HEAD`. State it.
   - If `main`: warn that direct pushes to `main` may be blocked by harness rule. Continue anyway — the push step will surface the denial.
   - If matches `^(feat|fix|chore|test|docs|refactor)/(W\d+\.[A-Z]+\.\d+)-`: extract `<task-id>` for use if user didn't supply one.

3. **Cross-check task-id vs branch.** If user-supplied task-id ≠ branch-derived task-id, surface the mismatch and ask before continuing — committing W0.L work to a `feat/W1.B.1-...` branch will pollute that branch's PR. Do not auto-resolve.

4. **Stage deliberately.** Never `git add -A` / `git add .` blanket.
   - User named files in `$ARGUMENTS`? Stage only those.
   - Else: `git add -u` for tracked-file modifications. List untracked files in the change set; **ask before staging untracked**. **Refuse** to stage anything matching `.env`, `.env.*` (except `.env.example`), `*.key`, `*.pem`, `*.gpg`, `cases/`, `downloads/`, `*.log`, `*.jsonl.bak`, `__pycache__/`, `worktrees/`, `swarm/swarm.db*`.

5. **Build the message.**
   - Subject = `<type>(<scope>): <summary> [<task-id>]` — verify regex BEFORE committing. If it fails, stop and explain which part is wrong.
   - Body (only if non-trivial): 1–4 short lines on *why*, never *what*. Diff shows what.

6. **Commit** via HEREDOC:
   ```
   git commit -m "$(cat <<'EOF'
   <subject>

   <optional body>
   EOF
   )"
   ```

7. **Pre-commit hook failure** → fix the underlying issue, re-stage, NEW commit. NEVER `--amend`.

8. **Push.** `git push origin HEAD`. If branch has no upstream, use `git push -u origin HEAD`. On denial:
   - Harness "no push to main" rule → tell the user; offer to move the commit to a feature branch + open a draft PR (do not do this without confirmation).
   - Branch protection → tell the user; suggest opening a PR.
   - Non-fast-forward → `git fetch` + `git status` to show divergence; **never** `--force`.
   - Explicit user request to `--force` after denial → REFUSE. Cite §3.7 + `scripts/run-swarm.sh:89`.

9. **Draft PR (if not on main and no PR yet).**
   - `gh pr view --json number,state` to check if a PR exists for the current branch.
   - If none and current branch ≠ `main`:
     ```
     gh pr create --draft \
       --title "<commit subject>" \
       --body "$(cat <<'EOF'
     ## Summary
     <commit body or 1-line restatement of the subject>

     ## Task
     [<task-id>] — see docs/BUILD_PLAN.md

     ## Test plan
     - [ ] (auto-fill if you can infer; otherwise leave blank for the human)
     EOF
     )"
     ```
   - If a PR already exists, just print its URL — push step already updated it.

10. **Confirm.** Print three lines: `<short-sha> <subject>`, push result, PR URL (or "no PR — on main").

## Hard refusals

If `$ARGUMENTS` contains any of: `--force`, ` -f `, `--no-verify`, `--no-gpg-sign`, `--amend`, `--allow-empty`, `+main`, `+HEAD`, `--auto`, `merge` (as a flag, not in subject text):
→ Refuse. Cite §3.7 and `scripts/run-swarm.sh:89`. Suggest `/ship` for merge.

If the task-id (supplied or branch-derived) doesn't match `^W\d+\.[A-Z]+\.\d+$`:
→ Refuse. Ask for the BUILD_PLAN task-id. Phase-0 swarm bootstrap may use any `W0.<letter>.<n>` per `swarm/agents/auditor.md:52`.

If the inferred prefix isn't in `feat|fix|test|chore|docs|refactor`:
→ Refuse. Ask the user to pick one.

If the diff genuinely cannot be summarized (binary, mixed-concern, > 200 lines across unrelated files):
→ Refuse. Ask the user for an explicit subject — don't guess on a sprawling diff.

## Examples

- `/qc` on branch `feat/W1.B.1-artifactclass-enum` with a new schema file → infers `W1.B.1` from branch + `feat(schema): add ArtifactClass enum [W1.B.1]` from diff.
- `/qc W0.L.4` on a script edit → infers `chore(swarm): <summary> [W0.L.4]`.
- `/qc W0.L.4 chore(swarm): bump turn budget to 80` → uses message verbatim.
- `/qc W0.L.5 fix typo --force` → REFUSED (`--force` in args). Cites §3.7.
- `/qc` on `main` with mixed W0.L + W1.B.1 changes staged → REFUSED. Surface the cross-task mixing; ask user to split.
