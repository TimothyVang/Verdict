# Cloud Proof Harness Implementation Plan

> **Wiki:** [Index](../../README.md) · [Architecture](../../ARCHITECTURE.md) · [Build Plan](../../BUILD_PLAN.md) · root [CLAUDE.md](../../../CLAUDE.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cloud-only Claude Agent SDK v0 proof path that generates a schema-valid VERDICT investigation plan and writes visual-proof artifacts under `proof/runs/`.

**Architecture:** Keep SGLang, GPU, air-gap, and dual mode out of scope. Add a focused cloud planner wrapper around the real `claude-agent-sdk`, a proof-run module that creates timestamped artifact folders, and a script entrypoint for recording demos.

**Tech Stack:** Python 3.11+, `claude-agent-sdk` (MIT), Pydantic v2 schemas, existing HMAC ledger writer, `uv`, pytest, ruff.

---

### Task 1: Cloud Planner SDK Wrapper

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/verdict/planning/planner.py`
- Test: `tests/planning/test_cloud_planner.py`

- [ ] Write tests for extracting text from Claude messages and parsing JSON plans into `InvestigationPlan`.
- [ ] Add `claude-agent-sdk` dependency after verifying the PyPI classifier is MIT.
- [ ] Implement `CloudPlanner.plan()` as a synchronous wrapper around `claude_agent_sdk.query()`.
- [ ] Require real SDK import at runtime; if unavailable, raise a clear setup error.
- [ ] Save raw Claude text only through the proof runner, not from the planner itself.

### Task 2: Cloud Proof Runner

**Files:**
- Create: `src/verdict/proof/cloud.py`
- Create: `src/verdict/proof/__init__.py`
- Create: `scripts/run_cloud_proof.py`
- Test: `tests/proof/test_cloud_proof.py`

- [ ] Write tests for creating `proof/runs/<timestamp>/` with logs, screenshots, video, and review files.
- [ ] Implement readiness checks for `ANTHROPIC_API_KEY` or Claude CLI auth without printing secrets.
- [ ] Implement a default evidence summary that is clearly an operator summary, not a fake evidence file.
- [ ] Call the real `CloudPlanner`, validate the plan, write `investigation-plan.json`, `cloud-agent-response.raw.txt`, `validation.log`, and `run-summary.md`.
- [ ] Write a HMAC ledger event for planner success or blocker status.

### Task 3: Visual Proof Assets And Docs

**Files:**
- Create: `proof/README.md`
- Modify: `docs/RELEASE.md`
- Test: `tests/proof/test_cloud_proof.py`

- [ ] Document `proof/runs/` and the screenshot/video review checklist.
- [ ] Update release docs to say v0 is Claude cloud-only and SGLang/GPU is postponed.
- [ ] Add proof review text that requires screenshots/video to show command launch, cloud readiness, Claude response, schema validation, and generated proof files.

### Task 4: Verification

**Files:**
- Existing test and source files only.

- [ ] Run `uv run pytest tests/proof tests/planning/test_cloud_planner.py -v`.
- [ ] Run `uv run pytest tests -v`.
- [ ] Run `uv run ruff check src tests scripts`.
- [ ] Run `uv run python scripts/run_cloud_proof.py` if cloud credentials are configured; otherwise confirm it writes a blocker proof run without leaking secrets.

---

Self-review: The plan covers the approved cloud-only v0 proof path, explicitly postpones SGLang/GPU, avoids mocks, records visual proof structure, and includes verification commands. No placeholders remain.
