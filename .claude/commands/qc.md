---
description: Quick commit and push using the Verdict qc skill
argument-hint: "[main]"
allowed-tools: Skill, Bash, Read
---

Use the project-local `qc` skill to execute this slash command.

Invocation:
- `/qc` commits and pushes the current branch.
- `/qc main` switches to the default branch, commits, and pushes there.

Arguments supplied to this command: `$ARGUMENTS`

Required behavior:
- Load `verdict-house-rules` first.
- Load `qc` second.
- Follow the loaded `qc` skill exactly, including inspection, selective staging, Conventional Commit message with `[W#.#.#]`, no `--no-verify`, no `--no-gpg-sign`, no `--amend`, and push.
- Do not add Claude/AI attribution lines.
