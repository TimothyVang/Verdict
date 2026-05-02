---
name: qc
description: Quick commit + auto-push. Stages changes, drafts a Conventional Commit per CLAUDE.md §3.7 (`<type>(scope): summary [W#.#.#]`), commits, and pushes. `/qc` pushes the current branch; `/qc main` switches to main first and pushes there (solo-speed flow — skips PR review). No `--no-verify`, no `--no-gpg-sign`, no `--amend`, no Claude Code watermarks.
---

# qc — quick commit + push

Terminal step in the Verdict skill pipeline (`verdict-house-rules` §"How this skill composes"). Assumes the work has already been verified (`verification-before-completion` ran green); this skill only handles staging, message drafting, commit, and push.

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
6. **Push** — `git push -u origin HEAD`. If the branch already tracks an upstream, plain `git push` is fine. Force-push is **not** part of `/qc`; if upstream rejects with non-fast-forward, stop and surface to the user.

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
