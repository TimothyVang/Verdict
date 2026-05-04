---
name: qc
description: Quick commit + docs-sweep + auto-push. Stages changes, drafts a Conventional Commit per CLAUDE.md §3.7 (`<type>(scope): summary [W#.#.#]`), commits, sweeps docs/ for drift triggered by the diff (per CONTRIBUTING.md "Docs follow research" table), commits any doc updates as a separate same-task-ID commit, then pushes. `/qc` pushes the current branch; `/qc main` switches to main first and pushes there (solo-speed flow — skips PR review). No `--no-verify`, no `--no-gpg-sign`, no `--amend`, no Claude Code watermarks.
---

# qc — quick commit + docs-sweep + push

Terminal step in the Verdict skill pipeline (`verdict-house-rules` §"How this skill composes"). Assumes the work has already been verified (`verification-before-completion` ran green); this skill handles staging, message drafting, commit, docs-sweep, and push.

The docs-sweep step (Step 5.5) is the local, inline counterpart to the `verdict-doc-drift` cron routine — it catches drift the moment you commit the change, before it propagates. Beats waiting for the 2-hour sweep to open a separate PR.

## Two invocations

- **`/qc`** — commit + push the **current branch** to its upstream on origin. Default. Use during normal feature-branch work.
- **`/qc main`** — switch to `main`, commit, push `origin/main` directly. **Solo-speed flow** for the hackathon — skips the PR review path. Only run this when the user is the only reviewer and the change is ready.

If `/qc main` is invoked while on a feature branch with uncommitted changes, carry the changes across with `git stash` → `git checkout main` → `git stash pop` → resolve any conflicts → continue. If conflicts can't be resolved cleanly, **stop** and surface to the user; do not throw away work.

## Prerequisite — `gh` installed and authenticated

`/qc` relies on `gh` having configured git's credential helper so `git push` over HTTPS doesn't prompt. Before staging anything, verify both:

```bash
command -v gh >/dev/null && gh auth status >/dev/null 2>&1
```

If that exits non-zero, bootstrap **before** continuing:

1. **Install `gh` if missing.** Detect platform first:
   - Ubuntu / Debian (this project's host):
     ```bash
     type -p curl >/dev/null || sudo apt install -y curl
     curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
       | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
     sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
     echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
     sudo apt update && sudo apt install -y gh
     ```
   - macOS: `brew install gh`
   - Fedora / RHEL: `sudo dnf install gh`
   - Arch: `sudo pacman -S github-cli`

   `sudo` will prompt the user — that is expected; do not try to bypass.

2. **Authenticate via browser** (one-time):
   ```bash
   gh auth login --hostname github.com --git-protocol https --web
   ```
   This prints a one-time code, opens the browser to `https://github.com/login/device`, and configures git's credential helper on success. If the host is headless and can't open a browser, fall back to:
   ```bash
   gh auth login --hostname github.com --git-protocol https
   ```
   and follow the prompts (paste-the-code flow works without a local browser).

3. **Verify**:
   ```bash
   gh auth status                       # expect "Logged in to github.com account <user>"
   ssh -T git@github.com 2>&1 || true   # only relevant if remote uses SSH
   git push --dry-run                   # confirms credential helper is active
   ```

Re-run the `gh auth status` check after install/auth before continuing to staging. If any step still fails, **stop** and surface the failure to the user — do not commit work that can't be pushed.

## Hard rules (inherited from CLAUDE.md §3.7)

- Format: `<type>(scope): summary [W#.#.#]`
- `type` ∈ {`feat`, `fix`, `test`, `chore`, `docs`, `refactor`} — no others.
- `[W#.#.#]` task ID is **required**. Resolve in this order:
  1. Look for an explicit task ID the user gave in this turn.
  2. `git log -20 --pretty=%s | grep -oE '\[W[0-9].[A-Z].[0-9]+\]' | head -1` — reuse the active task.
  3. Grep `docs/BUILD_PLAN.md` for the touched file path / scope.
  4. Last resort: `[W1.A.0]` for repo-wide foundational work — only with explicit user OK.
- **Never** `--no-verify`, `--no-gpg-sign`, or `git commit --amend`. Pre-commit hook failure → fix the underlying issue, re-stage, new commit. Do not bypass.
- **No Claude Code watermarks.** No `Co-Authored-By: Claude …`, no `🤖 Generated with [Claude Code]`, no equivalent attribution. Authorship is git committer + GPG signature only.

## Steps

1. **Inspect** — run in parallel: `git status`, `git diff --stat`, `git diff --cached`, `git log -5 --oneline`. Read the actual changes; do not commit blindly.
2. **Resolve task ID** per the order above. State the chosen ID + source in one short line so the user can correct before commit.
3. **Stage** — prefer named-path staging (`git add path/to/file.py …`) over `git add -A`/`git add .` to avoid sweeping in `.env`, credentials, or large binaries. If the user said "everything" explicitly, `git add -A` is acceptable.
4. **Draft message** — one sentence, imperative voice, focused on *why* not *what*. No body unless the change is non-obvious. Verb mapping: new capability → `feat`, behavior fix → `fix`, RED test → `test`, version pins / config / tooling → `chore`, docs only → `docs`, no-behavior-change cleanup → `refactor`.
5. **Commit** — `git commit -m "<type>(scope): summary [W#.#.#]"`. If a pre-commit hook fails: read the failure, fix the underlying issue, re-stage, **new** commit (never `--amend`).
5.5. **Docs sweep (Verdict-specific, post-commit, pre-push)** — see "Docs sweep" section below. Mandatory for non-docs commits; skip if the just-made commit was already a `docs(...)` or pure `chore(deps)` lockfile bump.
6. **Push** — `git push -u origin HEAD`. If the branch already tracks an upstream, plain `git push` is fine. Force-push is **not** part of `/qc`; if upstream rejects with non-fast-forward, stop and surface to the user.

## Docs sweep (Step 5.5)

This step exists because `CONTRIBUTING.md` ("⚠ REMINDER" + "Docs follow research") requires every contribution to leave `docs/` consistent with the code it shipped. /qc enforces this inline so you can't push a commit that orphans the docs.

### Triggers — what to scan for

Run `git show HEAD --stat --name-status` on the commit you just made. For each touched path, walk this trigger table — same as the `CONTRIBUTING.md` "Docs follow research" table:

| If the commit… | Scan / propose update to |
|---|---|
| Renamed / moved / deleted a file under `verdict/`, `scripts/`, `tests/`, `inspect_ai/` | `grep -rn '<old-path>' docs/ CLAUDE.md README.md CONTRIBUTING.md` — every hit is drift. Search-and-replace. |
| Added / removed / renamed a CLI flag, command, or env var | `CLAUDE.md` §10 (CLI surface), `README.md` "CLI surface" one-liner |
| Added / changed / removed a schema field, validator, enum member, Pydantic model | `docs/ARCHITECTURE.md` §4 (Schemas), `CLAUDE.md` §3.x rule that cites it (if any) |
| Added / changed / removed a playbook rule, caveat, MITRE technique cite | `CLAUDE.md` §3.3 (caveats) / §3.5 (MITRE) / §7 (doctrine), `docs/TLDR.md` if cited, `verdict/prompts/examiner_caveats.md` |
| Added / removed a dependency, changed a version pin | `CONTRIBUTING.md` §2 toolchain table, `docs/RELEASE.md`, `CLAUDE.md` §5 (tech-stack one-liner) |
| Vendored / removed a skill or MCP server | `docs/SKILLS_FRAMEWORK.md` (skills) or `docs/MCP_FRAMEWORK.md` (MCPs), `docs/SKILLS_LICENSE_AUDIT.md` |
| Added / renamed / removed a LangGraph node | `docs/ARCHITECTURE.md` §1–§2, `CLAUDE.md` §4 |
| Changed a verifier strategy semantics or budget | `docs/ARCHITECTURE.md` §1, `CLAUDE.md` §8 |
| Changed mode autodetect / mode-lock behavior | `docs/ARCHITECTURE.md` §1, `CLAUDE.md` §3.4 |
| Changed ledger schema, event types, or signing flow | `docs/ARCHITECTURE.md` §5, `CLAUDE.md` §9 |
| Touched anything under `.claude/skills/` | `docs/SKILLS_FRAMEWORK.md`, `docs/SKILLS_LICENSE_AUDIT.md` |
| Touched anything under `.mcp.json` | `docs/MCP_FRAMEWORK.md` |

If the commit was purely under `docs/`, `*.md` at root, `protocol-sift/` (submodule), or `docs/spec/` (frozen) — skip the sweep entirely.

### Decide: append vs add

For each detected trigger:

- **Deterministic edit** (path rename, dead link removal, version-pin number change, simple find-and-replace): **append/edit in place** — modify the existing doc lines without prompting. Scope = touch the smallest surface that resolves the drift.
- **Interpretive edit** (new feature gets a new paragraph, new schema field gets a new bullet, new node gets a new diagram entry): **add a new section/bullet** at the natural spot in the doc. Show the proposed diff to the user inline first; apply only after they say go (or confirm by silence in auto mode for low-risk additions).

Heuristics for deciding which doc to touch when multiple are candidates: prefer the most-authoritative doc per `CLAUDE.md` §2 authority order (`ARCHITECTURE.md` > `BUILD_PLAN.md` > `CLAUDE.md` > others). Update the secondary docs (`README.md`, `TLDR.md`) only if they cite the same fact verbatim.

### Hard NOs during the sweep

- **Never edit `docs/spec/`** — frozen archive (`CLAUDE.md` §2). If the commit contradicts a `spec/` claim, log it in `docs/DOCS_ACCURACY_REPORT.md` instead.
- **Never edit anything under `protocol-sift/`** — git submodule (`CLAUDE.md` §2).
- **Never edit `CLAUDE.md`** unless the drift is a verifiable code-vs-doc fact (removed flag, renamed file, changed schema). Style edits to `CLAUDE.md` are out of scope for /qc.
- **Never fabricate.** If you can't trace a doc claim back to a concrete code/config fact, leave the doc alone. Hallucinated "fixes" are worse than missed drift.
- **Cap at 10 doc edits per /qc invocation.** If the commit ripples through more docs than that, surface the count to the user and ask how to proceed — do not silently churn.

### Commit the doc updates separately

If the sweep produced any doc edits:
1. Stage only the touched doc files: `git add <doc-paths>`.
2. Commit with: `git commit -m "docs(<scope>): sync <doc-name(s)> with <prior-commit-summary> [W#.#.#]"`. Use the **same** task ID as the code commit. The `<scope>` is the area the code commit touched (e.g., `schema`, `cli`, `ledger`).
3. The commit goes through the same hook + signing path as the code commit. If a hook fails, fix and re-stage; do NOT bypass.

If the sweep produced no edits (or skipped per the trigger table): silent, proceed to push.

### Push pushes both commits

Step 6's `git push` then ships both the code commit and the docs-sync commit in one upstream update. The reviewer sees code + doc together, in order, on the same branch.

## Multi-commit batches

If the staged changes are obviously two unrelated concerns (e.g. a feat + an unrelated docs fix), split into two commits with two task IDs rather than one mushy commit. State the split plan before staging the first one.

## What `/qc` does *not* do

- Open PRs (`gh pr create --fill`) — that's `finishing-a-development-branch`.
- Run tests / type-check / lint manually — pre-commit hooks own that. If hooks aren't installed, run `pre-commit install` first or surface to the user.
- Force-push, rebase, or rewrite history.
- Skip signing or hooks under any circumstance.

## Failure modes to surface (don't silently swallow)

- Working tree contains unrelated changes the user may not want committed → list them, ask.
- No task ID resolvable from context → ask before defaulting to `[W1.A.0]`.
- Pre-commit hook fails repeatedly on the same issue → stop, root-cause, do not loop.
- `git push` rejected → show the error verbatim; do not `--force` without the user.
