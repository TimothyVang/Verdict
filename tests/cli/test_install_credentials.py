"""Tests for three-credential-path detection (W1.A.1).

Credential precedence (highest to lowest):
  1. ANTHROPIC_API_KEY env var         → mode=api_key
  2. CLAUDE_CODE_OAUTH_TOKEN env var   → mode=oauth
  3. ~/.claude/credentials.json        → mode=oauth_interactive
  4. ANTHROPIC_API env var (legacy)    → mode=api_key (legacy alias)

ENV manipulation via monkeypatch is not mocking a VERDICT internal
(§3.10 allows patching a third-party at the system boundary, and env
vars are the OS boundary for credential injection per §3.9).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from verdict.cli.credentials import CredentialMode, detect_credential_mode


class TestDetectCredentialMode:
    """Unit tests for detect_credential_mode() precedence rules."""

    # ------------------------------------------------------------------
    # Path 1 — ANTHROPIC_API_KEY highest precedence
    # ------------------------------------------------------------------

    def test_detects_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        monkeypatch.delenv("ANTHROPIC_API", raising=False)

        result = detect_credential_mode(claude_dir=Path("/nonexistent"))
        assert result == CredentialMode.API_KEY

    def test_api_key_beats_oauth_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ANTHROPIC_API_KEY must win when both env vars are set."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "bearer-token")
        monkeypatch.delenv("ANTHROPIC_API", raising=False)

        result = detect_credential_mode(claude_dir=Path("/nonexistent"))
        assert result == CredentialMode.API_KEY

    # ------------------------------------------------------------------
    # Path 2 — CLAUDE_CODE_OAUTH_TOKEN
    # ------------------------------------------------------------------

    def test_detects_oauth_token_first(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLAUDE_CODE_OAUTH_TOKEN → mode=oauth (the W1.A.1.a RED assertion)."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "bearer-token")
        monkeypatch.delenv("ANTHROPIC_API", raising=False)

        result = detect_credential_mode(claude_dir=Path("/nonexistent"))
        assert result == CredentialMode.OAUTH

    def test_oauth_token_beats_credentials_file(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """CLAUDE_CODE_OAUTH_TOKEN beats ~/.claude/credentials.json."""
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({"oauth_token": "stored-token"}))

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "bearer-token")
        monkeypatch.delenv("ANTHROPIC_API", raising=False)

        result = detect_credential_mode(claude_dir=tmp_path)
        assert result == CredentialMode.OAUTH

    # ------------------------------------------------------------------
    # Path 3 — ~/.claude/credentials.json interactive OAuth
    # ------------------------------------------------------------------

    def test_detects_oauth_interactive_from_credentials_file(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({"oauth_token": "stored-interactive"}))

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        monkeypatch.delenv("ANTHROPIC_API", raising=False)

        result = detect_credential_mode(claude_dir=tmp_path)
        assert result == CredentialMode.OAUTH_INTERACTIVE

    def test_credentials_file_empty_json_not_detected(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """credentials.json present but lacks oauth_token key → not detected."""
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({}))

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        monkeypatch.delenv("ANTHROPIC_API", raising=False)

        result = detect_credential_mode(claude_dir=tmp_path)
        assert result is None

    def test_missing_credentials_file_not_detected(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        monkeypatch.delenv("ANTHROPIC_API", raising=False)

        result = detect_credential_mode(claude_dir=Path("/nonexistent"))
        assert result is None

    # ------------------------------------------------------------------
    # Path 4 — ANTHROPIC_API legacy alias
    # ------------------------------------------------------------------

    def test_detects_legacy_api_key_alias(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        monkeypatch.setenv("ANTHROPIC_API", "sk-legacy")

        result = detect_credential_mode(claude_dir=Path("/nonexistent"))
        assert result == CredentialMode.API_KEY

    def test_api_key_beats_legacy_alias(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ANTHROPIC_API_KEY overrides ANTHROPIC_API (legacy)."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-primary")
        monkeypatch.setenv("ANTHROPIC_API", "sk-legacy")
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)

        result = detect_credential_mode(claude_dir=Path("/nonexistent"))
        assert result == CredentialMode.API_KEY

    def test_oauth_beats_legacy_alias(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "bearer")
        monkeypatch.setenv("ANTHROPIC_API", "sk-legacy")

        result = detect_credential_mode(claude_dir=Path("/nonexistent"))
        assert result == CredentialMode.OAUTH

    # ------------------------------------------------------------------
    # No credentials detected
    # ------------------------------------------------------------------

    def test_returns_none_when_no_credentials(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        monkeypatch.delenv("ANTHROPIC_API", raising=False)

        result = detect_credential_mode(claude_dir=Path("/nonexistent"))
        assert result is None

    # ------------------------------------------------------------------
    # Mode string representation
    # ------------------------------------------------------------------

    def test_credential_mode_strings(self) -> None:
        assert CredentialMode.API_KEY.value == "api_key"
        assert CredentialMode.OAUTH.value == "oauth"
        assert CredentialMode.OAUTH_INTERACTIVE.value == "oauth_interactive"
