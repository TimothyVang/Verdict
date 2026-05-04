---
description: Quick commit and push using the Verdict qc workflow
---

Run the Verdict quick-commit workflow for this repository.

Arguments supplied to this command: `$ARGUMENTS`

Behavior:
- If `$ARGUMENTS` is empty, commit and push the current branch.
- If `$ARGUMENTS` is `main`, switch to the default branch, commit, and push there only if safe.

Required process:
- Follow `CLAUDE.md` and `.claude/skills/verdict-house-rules/SKILL.md` hard rules.
- Follow `.claude/skills/qc/SKILL.md` as the authoritative `/qc` procedure.
- Inspect `git status`, `git diff --stat`, `git diff --cached`, and recent commit history before staging.
- Stage only relevant files by path unless the user explicitly asked to commit everything.
- Use Conventional Commit format with required task ID: `<type>(scope): summary [W#.#.#]`.
- Never use `--no-verify`, `--no-gpg-sign`, `git commit --amend`, force push, or AI attribution lines.
- Push with `git push -u origin HEAD` unless the current branch already has an upstream.
