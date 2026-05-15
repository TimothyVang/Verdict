# AGENTS.md

Compact OpenCode guide for VERDICT. `CLAUDE.md` is still the full operating charter; this file only calls out repo facts agents commonly miss.

## Start Here

- Read order for new work: `README.md` -> `CLAUDE.md` §3 -> `docs/ARCHITECTURE.md` -> `docs/BUILD_PLAN.md` -> the exact task ID.
- Authority order: Devpost rules -> `docs/DEVPOST_COMPLIANCE.md` -> `docs/ARCHITECTURE.md` -> `docs/BUILD_PLAN.md` -> `CLAUDE.md`; executable code/config/lockfiles win over prose.
- `docs/README.md` is the docs index. `docs/spec/` is frozen audit history; cite it for rationale, do not edit it.
- Pick or confirm a `W#.#.#` task ID from `docs/BUILD_PLAN.md` before code work; commits and PR titles must carry it.

## Layout And Entrypoints

- The importable Python package is `src/verdict/`; do not create a root `verdict/` package. `tests/policy/test_source_layout.py` enforces this.
- CLI entrypoint is `verdict = verdict.cli.__main__:main` from `pyproject.toml`; run it as `uv run verdict ...`.
- Local case state, ledgers, evidence, eval logs, proof runs, worktrees, `.env*`, and large forensic artifacts are intentionally gitignored. Do not commit them.
- `protocol-sift/` is a git submodule for upstream templates. Verdict overrides belong in root `CLAUDE.md` or `.claude/skills/verdict-house-rules/`, not in upstream files.

## Setup And Services

- Canonical full-stack environment is SANS SIFT VM or Linux with KVM. Native Windows is not supported for forensic/Microsandbox work; use WSL2/Linux/SIFT.
- Toolchain bootstrap: `bash scripts/bootstrap-dev.sh`, then `uv sync --all-extras` and `uv run pre-commit install --install-hooks`.
- Devcontainer is toolchain-only. Microsandbox, SGLang, Langfuse, evidence, and HMAC keys stay host-side; see `.devcontainer/README.md`.
- Langfuse local stack: `cd infra/langfuse && docker compose up -d`; generate required secrets with `bash scripts/gen-langfuse-secrets.sh`.
- SIFT Microsandbox image must be digest-pinned in `VERDICT_MICROSANDBOX_IMAGE` as `IMAGE@sha256:<64 hex>`; tag-only images are rejected.
- `.env` is loaded by the CLI but is secret material. Never read, print, or commit it; use `.env.example` for variable names.

## Verification Commands

- Fast repo gate used by CI/pre-commit logic: `uv run python scripts/build_check.py --tier fast`.
- Focused Python test: `uv run pytest tests/path/test_file.py::test_name -q`.
- Full local unit run: `uv run pytest -q`.
- Lint: `uv run ruff check src tests scripts`.
- Runtime pre-flight: `uv run verdict doctor --mode cloud`, `uv run verdict doctor --mode airgap`, or `uv run verdict doctor --mode dual`.
- Health and packaging checks: `uv run verdict health`; `uv run verdict package-check`.
- Per-mode evals use real services and real evidence only: `uv run inspect eval inspect_ai/tasks/verdict_eval_cloud.py`, `uv run inspect eval inspect_ai/tasks/verdict_eval_airgap.py`, `uv run inspect eval inspect_ai/tasks/verdict_eval_dual.py`.

## Non-Negotiable Rules

- No mocks, stubs, placeholders, replay libraries, or test-only branches. The hook scans `src/verdict`, `tests`, `scripts`, and `swarm` for `unittest.mock`, `responses`, `vcr`, `betamax`, `httpx_mock`, `MOCK`, `TEST_MODE`, and `VERDICT_TEST` bypasses.
- Tests that need Anthropic, SGLang, Langfuse, Microsandbox, SIFT tools, or evidence must hit the real dependency. If a service is down, report BLOCKED; do not fake it.
- Never write to `/evidence`; evidence is read-only/noexec and hash-checked. Tool outputs belong in case/output directories, not evidence mounts.
- Do not relax forensic validators: findings need >=2 artifact paths and >=2 artifact classes; execution claims need distinct artifact classes; Tier-1 caveats are mandatory; MITRE sub-techniques must be precise when determinable.
- Verdict statuses are exactly `VETTED_CLOUD`, `VETTED_AIRGAP`, `VETTED_DUAL`, `CONTESTED`, `UNVERIFIABLE`, `EXHAUSTED_REPLAN`; attribution wording is "evidence consistent with X", not "X did this".
- New dependencies, vendored skills, or MCP servers must be MIT or Apache-2.0 unless explicitly approved. Check `CLAUDE.md` §3.8 before adding anything.

## Workflow Gotchas

- TDD is required for code tasks: failing test -> implement -> green -> one commit per task ID.
- Commit format is enforced: `<type>(scope): summary [W#.#.#]`, with type in `feat`, `fix`, `test`, `chore`, `docs`, `refactor`.
- Never use `--no-verify`, `--no-gpg-sign`, `git commit --amend`, destructive git resets/checkouts, or Claude/AI watermark footers.
- Do not commit unless the user explicitly asks. When committing is requested, stage only relevant files and preserve unrelated dirty work.
- Docs must follow code changes. If you change schema, CLI, modes, verifier logic, tool wrappers, dependencies, skills, or MCP config, update the doc named in `CONTRIBUTING.md`'s docs-follow-research table.
- New docs under `docs/` need a row in `docs/README.md` and a wiki nav strip; never update `docs/spec/` for current behavior.

## Autopilot 8h Rule

- In this repo, `/autopilot 8h` must run continuously until the timebox expires or the user explicitly stops it.
- Do not stop because the current goal completed, tests passed, a final-report checkpoint was written, a hard blocker was parked, or the queue looks empty.
- Treat `continue_required=true` or `stop_allowed=false` as a hard ban on final responses; rerun the driver and keep working.
- When one goal completes, create another safe local follow-up from repo evidence: docs drift, stale verification, TODOs, residual risks, proof/report artifacts, policy gaps, tests, packaging/readiness checks, or reversible cleanup.
- If safe work appears exhausted before the deadline, prove it with a logged discovery sweep across docs, TODOs, stale checks, `.omx` reports, failure logs, tests, policy gaps, and residual risks. If anything safe remains, continue. If nothing remains, keep doing safe maintenance and verification loops until `stop_timebox_expired`.

## MCP And Mode Config

- Default `.mcp.json` and `.mcp.airgap.json` are air-gap safe: no filesystem-write server, no fetch, no credentialed GitHub.
- `.mcp.cloud.json` and `.mcp.dual.json` include network/write-capable developer tools; use only for connected development, not air-gap investigations.
- MCP credentials must be `${VAR}` references only. If editing MCP config, update `docs/MCP_FRAMEWORK.md` and the relevant license audit docs.
