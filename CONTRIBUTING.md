# Contributing to VERDICT

VERDICT is the SANS *FIND EVIL!* 2026 hackathon entry; submission deadline **Jun 14 2026 EOD** (Devpost) / Jun 15 22:45 CDT (official). Until then this repo is on hackathon time — fast iteration, focused scope.

## Before you contribute

1. **Read `CLAUDE.md` end-to-end.** It is the operating charter — hard rules in §3 are load-bearing.
2. **Read `docs/spec/VERDICT_AUDIT_v4.5.md`** for canonical architecture and `docs/spec/VERDICT_v4.6_SPEC_PLAN.md` for tactical patches.
3. **Find your task ID** in `docs/spec/VERDICT_MASTER_BUILD_PLAN.md` (e.g. `W1.B.7`). Every commit references one.

## Workflow

1. **TDD.** Failing test → RED → implement → GREEN → one commit per task. (`CLAUDE.md` §3.7)
2. **Conventional Commits with task IDs:**
   ```
   feat(schema): add ArtifactClass enum [W1.B.1]
   fix(verifier): seed derivation collapses at temp=0 [W1.C.2 / v4.6 F1]
   test(graph): kill-9 resume across super-step boundary [W3.E.4]
   docs(arch): document three-layer immutability [W1.G.3]
   ```
3. **Never** `--no-verify`, `--no-gpg-sign`, or `git commit --amend`. Pre-commit hook failures get fixed and re-staged.
4. **One PR per task ID.** PR title = the commit subject. PR body = what changed + which acceptance gate this satisfies.

## What you must NOT do

These are hard rules — see `CLAUDE.md` §3:

- Add a mock anywhere (§3.10 — VERDICT is full-stack, real services).
- Add a forbidden dependency (§3.8 — Daytona, Modal, LangSmith, AutoGen v0.4, …).
- Bypass the deny-rule wrapper or microsandbox read-only mount (§3.1, §4.2).
- Emit a `Finding` with `<2` artifact paths or classes (§3.2).
- Cite Amcache without acknowledging `AMCACHE_LASTMODIFIED_NOT_EXEC` (§3.3).
- Use bare MITRE techniques (`T1055`) when a sub-technique is determinable (§3.5).
- Commit secrets (`.env`, `*.gpg`, evidence files). The `.gitignore` covers most; double-check.

## Local dev

```bash
git clone --recurse-submodules https://github.com/TimothyVang/Verdict.git
cd Verdict
cp .env.example .env       # fill in API keys, Langfuse keys, etc.
uv sync                    # once pyproject.toml lands (W1.A)
verdict doctor             # pre-flight: every service, every key
```

If `verdict doctor` fails, **fix the underlying service** — do not work around it with a mock.

## Testing

The eval harness IS the test surface (§10.3):

```bash
inspect eval inspect_ai/tasks/verdict_eval_cloud.py
inspect eval inspect_ai/tasks/verdict_eval_airgap.py
inspect eval inspect_ai/tasks/verdict_eval_dual.py
```

Plus per-area pytest:

```bash
uv run pytest tests/schemas/ tests/playbooks/ tests/knowledge/ -v
pytest tests/chaos/test_kill_9_resume.py -v   # 100/100 zero-loss
```

## Reporting issues

Open an issue with:
- Mode (cloud / airgap / dual)
- `verdict doctor` output
- Relevant ledger excerpt (`verdict show <case_id>` — redact secrets)
- Langfuse trace link if applicable

## License

By contributing you agree your work is licensed under the MIT License (see `LICENSE`).
