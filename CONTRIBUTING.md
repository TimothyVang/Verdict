# CONTRIBUTING — Verdict

New-contributor setup guide. If you've already done the SANS Find Evil! 2026 team-onboarding (Devpost join, SIFT VM, Protocol SIFT install, starter case data), pick up at **Step 4**. Otherwise start at the top.

**Repo:** https://github.com/TimothyVang/Verdict
**Default branch:** `main`
**License:** MIT
**Deadline gate:** 2026-06-15 22:45 CDT (team-internal target: 2026-06-14 EOD = ~28 h buffer)
**Recommended platform:** SANS **SIFT Workstation VM** (canonical — all forensic tools, Microsandbox, SGLang, evidence mounts work out-of-box) **or** any modern **Linux box** (Ubuntu 22.04+ / Debian 12+ / Fedora 39+ / Arch). **macOS host is acceptable** for schema/planner/MCP/unit-test work that doesn't shell out to forensic tools — but the moment your task touches `verdict/sandboxes/`, `verdict/tools/vol3/`, or anything that runs in Microsandbox, switch into the SIFT VM. **Windows host is not supported** for development; use WSL2 + Ubuntu or pull the SIFT VM (it runs under Hyper-V / VMware / VirtualBox).

Authority chain when docs disagree: Devpost rules → `DEVPOST_COMPLIANCE.md` → `ARCHITECTURE.md` → `BUILD_PLAN.md` → this file. Code + lockfiles win over docs (per `CLAUDE.md`); update the doc, don't roll back the code, unless the code is wrong.

> ## ⚠ REMINDER — update `docs/` before you call a contribution done
>
> **Every contribution must leave `docs/` consistent with the code it ships.** Before you mark a task complete, push your final commit, or flip a draft PR to ready: walk the [Docs-follow-research table](#docs-follow-research-always) below and update **every** matching doc in the same PR.
>
> The minimum sweep:
>
> - Did you add/rename/remove a file under `verdict/`? Grep `docs/` + `CLAUDE.md` + `README.md` for the old path; update every reference.
> - Did you add/change/remove a CLI command, flag, or env var? Update `CLAUDE.md` §10 and `README.md` "CLI surface".
> - Did you add/change/remove a schema field, validator, enum member, or playbook rule? Update `docs/ARCHITECTURE.md` §4 and any `CLAUDE.md` §3.x rule that cites it.
> - Did you add/remove a dependency, change a version pin, or vendor a skill/MCP? Update `CONTRIBUTING.md` §2 toolchain table + `docs/PRODUCTION_AUDIT.md` (deps) or `docs/SKILLS_FRAMEWORK.md` / `docs/MCP_FRAMEWORK.md` + license audit (vendored).
> - Did you change a LangGraph node, verifier strategy, mode behavior, or caveat? Update `docs/ARCHITECTURE.md` §1–§2, `CLAUDE.md` §3.3 / §4 / §8, and `docs/TLDR.md` if cited.
> - Did you discover an audit-history claim in `docs/spec/` is wrong? Log it in `docs/DOCS_ACCURACY_REPORT.md`. **Do NOT edit `spec/`** — it's frozen.
>
> A reviewer will ask "why didn't you update docs?" if your PR touches code without touching the doc that refers to it. The 2-hour `verdict-doc-drift` routine will also open a draft PR if it catches you. Beat both — close the loop yourself in the same PR.

---

## Step 0 — Accounts and access

You need all four before you can push:

1. **GitHub account** with 2FA enabled. Required for `gh auth login` and signed commits.
2. **Devpost account** joined to the team submission. Confirm your name shows on the submission page.
3. **Anthropic API key** or Claude Code OAuth for cloud-mode and dual-mode runs. `OPENROUTER_API_KEY` is an optional host-side fallback for build-side AI agents. Air-gap mode does not require cloud credentials. OAuth/API tokens are *not* redistributable — each contributor uses their own, and secrets never enter microVMs.
4. **Write access to `TimothyVang/Verdict`.** PUG (TSgt Vang) adds you. Confirm with `gh repo view TimothyVang/Verdict --json viewerPermission` after install — should report `WRITE` or higher.

---

## Step 1 — Authenticate with the `gh` CLI

`gh` is the canonical auth path for VERDICT — and the only one. It handles token issuance under the hood, wires git transparently, and gives you the same surface (`gh pr create`, `gh issue list`, `gh repo view`) that your reviewers use.

### 1a. Install `gh` (skip if `gh --version` already prints something)

```bash
# Linux / SIFT VM (apt)
type -p curl >/dev/null || sudo apt install -y curl
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
  | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
sudo apt update && sudo apt install -y gh

# macOS
brew install gh

# Verify
gh --version
```

### 1b. Authenticate and wire git

```bash
gh auth login --hostname github.com --git-protocol https --web
# Opens a browser tab. Accept the requested scopes (repo, read:org, workflow).

gh auth setup-git
# Configures git to delegate auth to gh. No tokens to manage.
```

### 1c. Verify access

```bash
gh auth status                                    # → Logged in to github.com as <you>
gh repo view TimothyVang/Verdict --json viewerPermission
# → {"viewerPermission":"WRITE"}  (or higher)
```

If `viewerPermission` is `READ` or `null`, ping PUG to add you to the repo before continuing.

`gh auth token` prints the token `gh` is currently using if you ever need the raw value. `gh auth refresh -s <scope>` adds scopes to your existing auth without re-doing the browser flow.

### SSH alternative

If you'd rather use an SSH remote:

```bash
gh auth login --hostname github.com --git-protocol ssh --web
# gh prompts to upload an existing key or generate one. Sets the remote to git@github.com:.../...git automatically.
```

---

## Step 2 — Local toolchain

Verdict ships three runtimes. Pin everything; no `latest`.

**Quick path — one command:**
```bash
bash scripts/bootstrap-dev.sh
```
Idempotent. Installs uv + Python 3.11, Rust 1.88, Node 20 + pnpm, and Microsandbox (Linux only) at the pinned versions in the table below. Skips anything already at the right version. Re-run any time you want to re-verify the toolchain.

**Manual path** (use this if `bootstrap-dev.sh` fails on your platform — macOS host, exotic distro, etc., and tell PUG so the script gets a fix):

| Component | Pinned version | Install |
|---|---|---|
| Python | 3.11.x | `uv python install 3.11` (https://github.com/astral-sh/uv) |
| Python pkg mgr | `uv` (latest) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Rust | 1.88 | `rustup install 1.88 && rustup default 1.88` |
| Node | 20.x LTS | `nvm install 20 && nvm use 20` |
| Node pkg mgr | `pnpm` (corepack) | `corepack enable && corepack use pnpm` |
| Microsandbox | v0.4.x | `curl -fsSL https://install.microsandbox.dev \| sh` (Linux/SIFT VM only) |
| Linters | `ruff`, `cargo clippy`, `eslint` | wired via pre-commit; see Step 5 |

**Where to develop.** Three supported configurations, in order of preference:

1. **Inside the SIFT VM** (canonical, recommended for everyone). All forensic tools, Microsandbox, SGLang, and the evidence mounts resolve here without setup. **Required** for any work touching the executor branches, the Microsandbox layer, evidence I/O, or anything under `verdict/sandboxes/`, `verdict/tools/vol3/`, or `services/mcp/src/tools/`. Pull the OVA from `downloads/README.md`; snapshot it as `clean-install` before installing anything.
2. **A modern Linux box** (Ubuntu 22.04+ / Debian 12+ / Fedora 39+ / Arch). Acceptable for the full stack as long as you can install Microsandbox (Linux-only) and run the SIFT toolchain (`apt install sleuthkit volatility ...`). Faster I/O than the VM. Take a `pre-verdict` snapshot of your home before installing forensic tools — they leave state.
3. **macOS host with the SIFT VM as a runtime target** (faster edit loop, smaller surface). Use VS Code Remote-SSH or `Develop on a Container` into the VM. Acceptable for schema, planner, MCP gateway, and unit-test work that doesn't shell out to forensic tools or Microsandbox. The moment your task touches a Microsandbox path or a forensic CLI, switch into the VM.

**Windows host is not supported** for development. Either use WSL2 + Ubuntu (treat as configuration #2) or run the SIFT VM under Hyper-V / VMware / VirtualBox (configuration #1). Native Windows breaks Microsandbox (libkrun is Linux-only), pre-commit hooks (path/exec semantics), and several SIFT tools.

If your work touches `services/mcp/src/tools/`, `services/agent_mcp/`, or anything under a Microsandbox path, you **must** run integration tests inside the SIFT VM (or your Linux box with Microsandbox installed) before opening a PR. macOS-only test runs do not satisfy the gate.

---

## Step 3 — GPG (or SSH) commit signing

Per `CLAUDE.md`, **`--no-gpg-sign` is forbidden.** Every commit on `main` must be verified.

```bash
# GPG path
gpg --full-generate-key                       # ed25519, no expiry or 2y
gpg --armor --export YOUR_KEY_ID              # paste into https://github.com/settings/gpg/new
git config --global user.signingkey YOUR_KEY_ID
git config --global commit.gpgsign true
git config --global tag.gpgsign true

# SSH-signing path (simpler; works with the same ed25519 key from Step 1)
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git config --global commit.gpgsign true
# Add the same pub key at https://github.com/settings/ssh/new with type "Signing Key"
```

Smoke-test before your first real commit:
```bash
git commit --allow-empty -m "test: signing smoke [chore]"
git log --show-signature -1   # expect: gpg: Good signature  OR  Good "git" signature
git reset --soft HEAD~1       # back the smoke commit out
```

---

## Step 4 — Clone and bootstrap

```bash
# gh picks HTTPS or SSH automatically based on your Step 1 setup
gh repo clone TimothyVang/Verdict verdict
cd verdict

# Hooks + dev deps (will land in the repo over Week 1; if missing, skip)
test -f pyproject.toml && uv sync --all-extras
test -f .pre-commit-config.yaml && uv run pre-commit install --install-hooks
test -f Cargo.toml && cargo build --workspace
test -f pnpm-lock.yaml && pnpm install --frozen-lockfile
```

Sanity check:
```bash
uv run pytest -q             # must pass on a clean clone — if it doesn't, that's a P0
cargo test --workspace -q
pnpm test
```

If the workspace files don't exist yet (we're early in Week 1), clone is enough — the scaffold lands per `BUILD_PLAN.md` Phase W1.A.

---

## Step 5 — Conventions you must follow

**The hard rules live in `CLAUDE.md` §3** (TDD loop, Conventional Commits with `[W?.?.?]` task IDs, forbidden git flags, dependency policy, no-mocks, evidence-integrity invariants). Read them once; CI rejects PRs that violate them.

This section is contributor-specific workflow on top of those rules.

### Branches
Format: `<type>/<task-id>-<slug>` — e.g. `feat/W1-B-1-artifact-class-enum`. Branch from `main`, rebase before PR, squash on merge only if the branch was a single logical task. Otherwise preserve the TDD red→green commits — they're the audit trail.

### Commit + push: use `/qc`

`/qc` is the project's quick-commit slash command. It stages your changes, drafts a Conventional Commit per `CLAUDE.md` §3.7 (`<type>(scope): summary [W#.#.#]`), commits, and pushes — without `--no-verify`, `--no-gpg-sign`, `--amend`, or any Claude Code watermark. Use `/qc` for every commit on a working branch; use `/qc main` only if you're soloing a fix straight to `main` (skips PR review).

### PRs (use `gh pr create`)

Open a **draft PR as soon as you have a failing test pushed**. Title mirrors the eventual squash-merge commit. Body must include task ID, mode(s) affected, test evidence, and schema-change notes if any.

```bash
gh pr create \
  --base main \
  --draft \
  --title "feat(scope): summary [W1.B.1]" \
  --body "$(cat <<'EOF'
**Task:** [docs/BUILD_PLAN.md W1.B.1](../blob/main/docs/BUILD_PLAN.md)
**Mode(s):** all   <!-- cloud / airgap / dual / all -->
**Test evidence:**
\`\`\`
<paste the failing-then-passing run, or attach the log>
\`\`\`
**Schema impact:** none   <!-- describe migration plan if non-zero; schemas freeze 2026-05-08 -->
EOF
)"
```

Then iterate: every push uses `/qc`; flip the PR to ready with `gh pr ready` when all gates green; check status with `gh pr status`, CI with `gh pr checks`, review feedback with `gh pr view`.

### Docs follow research, always
<a id="docs-follow-research-always"></a>

When you confirm a fact through investigation — a MITRE technique ID, a tool's actual behavior, a schema constraint, an upstream license, an API surface, a deadline, anything you had to verify — **update the corresponding doc in the same PR**. The doc tree is authority for everything not encoded in code; let it drift behind the code and the next contributor (or the SANS judge) reads a lie.

Authority lives in `docs/` (`ARCHITECTURE.md`, `BUILD_PLAN.md`, `DEVPOST_COMPLIANCE.md`, `DOCS_ACCURACY_REPORT.md`); the `docs/spec/` archive is read-only. Code wins over docs — if the code is right and a doc is wrong, **fix the doc, don't roll back the code**.

Concretely, when a verified fact lands:

| What you confirmed | Update |
|---|---|
| New schema field, validator, or enum member | `docs/ARCHITECTURE.md` §4 (and `CLAUDE.md` §3.x if it's a hard rule) |
| Tool wrapper added or behavior changed | `docs/ARCHITECTURE.md` §6 |
| MITRE technique / sub-technique presence or absence | `CLAUDE.md` §3.5 examples and any doc that cites it |
| Dependency added, removed, or version pinned | this `CONTRIBUTING.md` §2 + `docs/PRODUCTION_AUDIT.md` |
| LangGraph node added / removed / renamed | `docs/ARCHITECTURE.md` §2 + `docs/BUILD_PLAN.md` task body |
| Verifier strategy semantics changed | `docs/ARCHITECTURE.md` §1 + `CLAUDE.md` §8 |
| Caveat list changed | `CLAUDE.md` §3.3 + `docs/TLDR.md` (if cited) + `verdict/prompts/examiner_caveats.md` |
| New skill or MCP vendored | `docs/SKILLS_FRAMEWORK.md` (skills) or `docs/MCP_FRAMEWORK.md` (MCPs) + audit log |
| Audit-history correction (research contradicts a frozen `spec/` claim) | log in `docs/DOCS_ACCURACY_REPORT.md`. Do **not** edit `spec/`. |

If your PR touches code but not the doc the code refers to, expect the reviewer to ask why. Drive-by doc fixes (typos, dead links, outdated commands you noticed in passing) are welcome in their own commit on the same branch — keep them separate from the feature commit so the audit trail stays clean.

### Linters
`ruff check . && ruff format --check .` for Python. `cargo clippy --all-targets --all-features -- -D warnings` for Rust. `eslint .` for Node. Pre-commit runs all three; CI re-runs them. No `# noqa` without an inline justification.

### Secrets in commits
The `.gitignore` already covers `.env*`, `*.vmem`, `*.E0*`, `*.dd`, `*.raw`, `*.gpg`, `cases/`. If you add a new evidence-bearing extension, update `.gitignore` in the same commit. Never paste auth tokens, OAuth tokens, or HMAC keys into PR descriptions or commit messages.

---

## Step 6 — Run a smoke investigation

Inside the SIFT VM, confirm your environment can drive an end-to-end loop before you start writing code:

```bash
cd ~/verdict   # or wherever you cloned
claude         # interactive Claude Code session if you're on cloud/dual mode
> investigate /mnt/hgfs/evidence/hackathon-2026/<case-folder>
```

Air-gap operators: ask PUG for the bridged + Tesla-mode entry point.

Expected output: structured Findings citing tool-call IDs, a quorum verdict, an HMAC-signed ledger entry, and a Langfuse trace (if Langfuse is up — see `ARCHITECTURE.md` §Observability).

If the run fails before producing a Finding, you have a P0 environment problem. Post the trace ID + `verdict doctor` output in team chat before opening a code PR.

---

## Step 7 — Where to ask questions

Authority order (escalate left-to-right):

1. **NotebookLM Q&A:** https://notebooklm.google.com/notebook/f0957a60-6fb2-452b-93d4-ecd73ba47779?authuser=1 — chief location for "how does X work?"
2. **`docs/` and the audit history in `archive/`** — most "why did we choose X?" questions are answered in `archive/03-audit-v4.5.md`.
3. **Team chat** — PUG / Beaver / Haley / KP. Use the appropriate thread; don't DM PUG for things the team should see.
4. **Devpost platform issues only:** https://help.devpost.com/

Do not paste auth tokens, OAuth tokens, case data, or HMAC keys into any of the above. NotebookLM and chat are *not* secret-cleared channels.

If you see a PR authored by a `swarm:*` worker, read [`docs/AGENT_SWARM.md`](docs/AGENT_SWARM.md) — it explains the build swarm, the reviewer/auditor agents, and the human merge gate that makes those PRs land safely. Swarm PRs follow the same branch + commit + signing rules you do; the only difference is that they have agent reviews stacked under your human approval.

---

## First-day checklist

Copy into your notes and tick as you go.

- [ ] GitHub 2FA on
- [ ] `gh auth login --web` complete; `gh repo view TimothyVang/Verdict --json viewerPermission` reports `WRITE` or higher
- [ ] `/qc` skill installed (drop [.claude/skills/qc/SKILL.md](.claude/skills/qc/SKILL.md) at `~/.claude/skills/qc/SKILL.md` for global use, or rely on the project-local copy already vendored under `.claude/skills/qc/`)
- [ ] Commit signing verified (`git log --show-signature` shows good signature on a smoke commit)
- [ ] Python 3.11 + uv, Rust 1.88, Node 20 + pnpm installed and on `PATH`
- [ ] Repo cloned; `uv sync`, `cargo build`, `pnpm install` all succeed (or scaffold not yet landed — confirm with PUG)
- [ ] Pre-commit hooks installed; `pre-commit run --all-files` green
- [ ] SIFT VM `clean-install` and `protocol-sift-installed` snapshots taken
- [ ] First `investigate <case>` produces a Finding + ledger entry inside the VM
- [ ] `BUILD_PLAN.md` skimmed; you know which task ID you're picking up first
- [ ] `ARCHITECTURE.md` §1 (modes) and §2 (LangGraph topology) read end-to-end
- [ ] **You've internalized the top-of-file REMINDER:** every contribution updates `docs/` in the same PR, before "done"

Welcome to the team. Push small, push often, sign everything — **and update the docs every time**.
