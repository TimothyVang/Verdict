# CONTRIBUTING — Verdict

New-contributor setup guide. If you've already done the SANS Find Evil! 2026 team-onboarding (Devpost join, SIFT VM, Protocol SIFT install, starter case data), pick up at **Step 4**. Otherwise start at the top.

**Repo:** https://github.com/TimothyVang/Verdict
**Default branch:** `main`
**License:** MIT
**Deadline gate:** 2026-06-15 22:45 CDT (team-internal target: 2026-06-14 EOD = ~28 h buffer)

Authority chain when docs disagree: Devpost rules → `DEVPOST_COMPLIANCE.md` → `ARCHITECTURE.md` → `BUILD_PLAN.md` → this file. Code + lockfiles win over docs (per `CLAUDE.md`); update the doc, don't roll back the code, unless the code is wrong.

---

## Step 0 — Accounts and access

You need all four before you can push:

1. **GitHub account** with 2FA enabled. Required for PAT issuance and signed commits.
2. **Devpost account** joined to the team submission. Confirm your name shows on the submission page.
3. **Anthropic API key** (or Claude Code OAuth) for cloud-mode and dual-mode runs. Air-gap mode does not require this. OAuth tokens are *not* redistributable per Anthropic commercial terms — each contributor uses their own.
4. **Write access to `TimothyVang/Verdict`.** PUG (TSgt Vang) adds you. Confirm with `gh repo view TimothyVang/Verdict --json viewerPermission` after install — should report `WRITE` or higher.

---

## Step 1 — Create a GitHub PAT (read + write)

PUG's recommendation: fine-grained PAT scoped to this repo so revocation doesn't disrupt your other work.

1. https://github.com/settings/tokens?type=beta → **Generate new token** (fine-grained).
2. **Token name:** `verdict-contrib-<your-handle>`
3. **Expiration:** 90 days. Diary it; the hackathon ends 2026-06-15, so a single 90-day token covers the whole sprint plus a slack week.
4. **Repository access:** *Only select repositories* → `TimothyVang/Verdict`.
5. **Repository permissions** (set the dropdowns to **Read and write**):
   - Contents — Read and write
   - Pull requests — Read and write
   - Issues — Read and write
   - Workflows — Read and write *(needed once `.github/workflows/` lands)*
   - Metadata — Read-only (auto-selected, leave it)
   - Everything else — No access
6. **Generate**, copy the token *once*, store it in a credential manager (1Password, `pass`, `gopass`, `bw`, Bitwarden Secrets — whatever your shop uses). Do **not** paste it into a `.env` that ships with the repo.
7. Verify scope:
   ```bash
   curl -sH "Authorization: Bearer ${VERDICT_GH_PAT}" https://api.github.com/repos/TimothyVang/Verdict \
     | jq '.permissions'
   # Expect: {"admin": false, "maintain": false, "push": true, "triage": true, "pull": true}
   ```

### Hand the PAT to git

Two valid paths. Pick one — **don't mix them**, you'll create credential-helper conflicts.

**Path A — git credential helper (Linux/SIFT VM, recommended):**
```bash
git config --global credential.helper 'cache --timeout=28800'   # 8h
git config --global credential.https://github.com.username YOUR_GH_USERNAME
# First push will prompt for password — paste the PAT once, helper caches it.
```

**Path B — gh CLI (Windows host, macOS, or anywhere `gh` is already installed):**
```bash
gh auth login --hostname github.com --git-protocol https --with-token < /path/to/pat.txt
gh auth setup-git
```

**SSH alternative:** if you'd rather use an ed25519 SSH key, that's fine — skip the PAT entirely for git and use the PAT only for `gh` API calls and CI. Generate with `ssh-keygen -t ed25519 -C "verdict-<handle>"`, add to https://github.com/settings/keys, and clone with `git@github.com:TimothyVang/Verdict.git`.

---

## Step 2 — Local toolchain

Verdict ships three runtimes. Pin everything; no `latest`.

**Quick path — one command:**
```bash
bash scripts/bootstrap-dev.sh
```
Idempotent. Installs uv + Python 3.11, Node 20 + pnpm, and Microsandbox (Linux only) at the pinned versions in the table below. Skips anything already at the right version. Re-run any time you want to re-verify the toolchain.

**Manual path** (use this if `bootstrap-dev.sh` fails on your platform — macOS host, exotic distro, etc., and tell PUG so the script gets a fix):

| Component | Pinned version | Install |
|---|---|---|
| Python | 3.11.x | `uv python install 3.11` (https://github.com/astral-sh/uv) |
| Python pkg mgr | `uv` (latest) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node | 20.x LTS | `nvm install 20 && nvm use 20` |
| Node pkg mgr | `pnpm` (corepack) | `corepack enable && corepack use pnpm` |
| Microsandbox | v0.4.x | `curl -fsSL https://install.microsandbox.dev \| sh` (Linux/SIFT VM only) |
| Linters | `ruff`, `eslint` | wired via pre-commit; see Step 5 |

**Where to develop.** Two supported configurations:

- **Inside the SIFT VM** (canonical). All forensic tools, microsandbox, SGLang resolve here. Required for any work touching the executor branches, the microsandbox layer, or evidence I/O.
- **On the host with the SIFT VM as a runtime target** (faster edit loop). Use VS Code Remote-SSH or `Develop on a Container` into the VM. Acceptable for schema, planner, MCP gateway, and unit-test work that doesn't actually shell out to forensic tools.

If your work touches `mcp/src/tools/`, `verdict/tools/`, or anything under a microsandbox path, you must run integration tests inside the VM before opening a PR.

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
# Pick the path you set up in Step 1
git clone https://github.com/TimothyVang/Verdict.git verdict     # PAT
# OR
git clone git@github.com:TimothyVang/Verdict.git verdict          # SSH

cd verdict

# Hooks + dev deps (will land in the repo over Week 1; if missing, skip)
test -f pyproject.toml && uv sync --all-extras
test -f .pre-commit-config.yaml && uv run pre-commit install --install-hooks
test -f pnpm-lock.yaml && pnpm install --frozen-lockfile
```

Sanity check:
```bash
uv run pytest -q             # must pass on a clean clone — if it doesn't, that's a P0
pnpm test
```

If the workspace files don't exist yet (we're early in Week 1), clone is enough — the scaffold lands per `BUILD_PLAN.md` Phase W1.A.

---

## Step 5 — Conventions you must follow

**The hard rules live in `CLAUDE.md` §3** (TDD loop, Conventional Commits with `[W?.?.?]` task IDs, forbidden git flags, dependency policy, no-mocks, evidence-integrity invariants). Read them once; CI rejects PRs that violate them.

This section is contributor-specific workflow on top of those rules.

### Branches
Format: `<type>/<task-id>-<slug>` — e.g. `feat/W1-B-1-artifact-class-enum`. Branch from `main`, rebase before PR, squash on merge only if the branch was a single logical task. Otherwise preserve the TDD red→green commits — they're the audit trail.

### PRs
Open a **draft PR as soon as you have a failing test pushed**. Title mirrors the eventual squash-merge commit. PR body must include:
- Task ID + link to the `docs/BUILD_PLAN.md` line
- Which mode(s) it affects (`cloud`, `airgap`, `dual`, or `all`)
- Test evidence (paste the failing-then-passing run, or attach the log)
- Schema changes? Call out the migration plan — schemas freeze 2026-05-08.

### Linters
`ruff check . && ruff format --check .` for Python. `eslint .` for Node. Pre-commit runs both; CI re-runs them. No `# noqa` without an inline justification.

### Secrets in commits
The `.gitignore` already covers `.env*`, `*.vmem`, `*.E0*`, `*.dd`, `*.raw`, `*.gpg`, `cases/`. If you add a new evidence-bearing extension, update `.gitignore` in the same commit. Never paste PATs, OAuth tokens, or HMAC keys into PR descriptions or commit messages.

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

Do not paste PAT tokens, OAuth tokens, case data, or HMAC keys into any of the above. NotebookLM and chat are *not* secret-cleared channels.

If you see a PR authored by a `swarm:*` worker, read [`docs/AGENT_SWARM.md`](docs/AGENT_SWARM.md) — it explains the build swarm, the reviewer/auditor agents, and the human merge gate that makes those PRs land safely. Swarm PRs follow the same branch + commit + signing rules you do; the only difference is that they have agent reviews stacked under your human approval.

---

## First-day checklist

Copy into your notes and tick as you go.

- [ ] GitHub 2FA on, PAT issued with read+write on `TimothyVang/Verdict`, stored in a secret manager
- [ ] Git credential helper or `gh auth` configured; can `gh repo view TimothyVang/Verdict`
- [ ] Commit signing verified (`git log --show-signature` shows good signature on a smoke commit)
- [ ] Python 3.11 + uv, Node 20 + pnpm installed and on `PATH`
- [ ] Repo cloned; `uv sync`, `pnpm install` all succeed (or scaffold not yet landed — confirm with PUG)
- [ ] Pre-commit hooks installed; `pre-commit run --all-files` green
- [ ] SIFT VM `clean-install` and `protocol-sift-installed` snapshots taken
- [ ] First `investigate <case>` produces a Finding + ledger entry inside the VM
- [ ] `BUILD_PLAN.md` skimmed; you know which task ID you're picking up first
- [ ] `ARCHITECTURE.md` §1 (modes) and §2 (LangGraph topology) read end-to-end

Welcome to the team. Push small, push often, sign everything.
