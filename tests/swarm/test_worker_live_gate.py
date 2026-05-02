"""swarm.worker.cmd_run gate matrix.

Three branches before the SDK call site lands:
  1. VERDICT_SWARM_LIVE != "1"        -> Phase-0 stub, exit 2.
  2. VERDICT_SWARM_LIVE == "1" + no credential -> exit 2 with auth message.
  3. VERDICT_SWARM_LIVE == "1" + credential present -> exit 2 with
     "live-mode not yet implemented" message (placeholder until Phase C).

The gate exists so flipping VERDICT_SWARM_LIVE=1 is a single, reviewable
change rather than something tangled into the SDK call site.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from swarm.worker import cmd_run

CRED_VARS = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API")


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    for var in CRED_VARS + ("VERDICT_SWARM_LIVE",):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


def _args() -> argparse.Namespace:
    return argparse.Namespace(task_id="W0.S.0")


def test_flag_unset_returns_phase_zero_stub(
    isolated_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cmd_run(_args())
    assert rc == 2
    err = capsys.readouterr().err
    assert "Phase 0" in err or "not implemented" in err.lower()


def test_flag_set_no_credential_blocks(
    isolated_env: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("VERDICT_SWARM_LIVE", "1")
    rc = cmd_run(_args())
    assert rc == 2
    err = capsys.readouterr().err
    assert "credential" in err.lower()


def test_flag_set_with_credential_reaches_live_placeholder(
    isolated_env: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("VERDICT_SWARM_LIVE", "1")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-test")
    rc = cmd_run(_args())
    assert rc == 2
    err = capsys.readouterr().err
    assert "live-mode" in err.lower()
    assert "not yet implemented" in err.lower()
