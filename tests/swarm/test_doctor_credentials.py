"""swarm.doctor.check_credential_present contract.

Asserts that doctor fails fast when no Anthropic credential is configured
(ANTHROPIC_API_KEY / CLAUDE_CODE_OAUTH_TOKEN / ~/.claude/credentials.json /
ANTHROPIC_API), matching the precedence documented in .env.example. This is
the gate that prevents `swarm.worker run` from dispatching only to fail late
on auth.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from swarm.doctor import check_credential_present

CRED_VARS = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API")


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    for var in CRED_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


def test_no_credentials_returns_false(isolated_env: Path) -> None:
    ok, detail = check_credential_present()
    assert ok is False
    assert "no credential" in detail.lower()


def test_anthropic_api_key_returns_true(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    ok, detail = check_credential_present()
    assert ok is True
    assert detail == "ANTHROPIC_API_KEY"


def test_oauth_token_returns_true(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-test")
    ok, detail = check_credential_present()
    assert ok is True
    assert detail == "CLAUDE_CODE_OAUTH_TOKEN"


def test_credentials_json_returns_true(isolated_env: Path) -> None:
    claude_dir = isolated_env / ".claude"
    claude_dir.mkdir()
    (claude_dir / "credentials.json").write_text('{"x":1}', encoding="utf-8")
    ok, detail = check_credential_present()
    assert ok is True
    assert "credentials.json" in detail


def test_legacy_anthropic_api_returns_true(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API", "legacy-test")
    ok, detail = check_credential_present()
    assert ok is True
    assert detail == "ANTHROPIC_API"


def test_precedence_api_key_over_oauth(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-test")
    ok, detail = check_credential_present()
    assert ok is True
    assert detail == "ANTHROPIC_API_KEY"


def test_precedence_oauth_over_credentials_json(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-test")
    claude_dir = isolated_env / ".claude"
    claude_dir.mkdir()
    (claude_dir / "credentials.json").write_text('{"x":1}', encoding="utf-8")
    ok, detail = check_credential_present()
    assert ok is True
    assert detail == "CLAUDE_CODE_OAUTH_TOKEN"


def test_precedence_credentials_json_over_legacy_api(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API", "legacy-test")
    claude_dir = isolated_env / ".claude"
    claude_dir.mkdir()
    (claude_dir / "credentials.json").write_text('{"x":1}', encoding="utf-8")
    ok, detail = check_credential_present()
    assert ok is True
    assert "credentials.json" in detail


def test_empty_string_treated_as_unset(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "")
    ok, detail = check_credential_present()
    assert ok is False
    assert "no credential" in detail.lower()
