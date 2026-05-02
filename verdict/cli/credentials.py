"""Three-credential-path detection for the Verdict CLI (W1.A.1).

Credential precedence, highest to lowest:
  1. ANTHROPIC_API_KEY env var      → CredentialMode.API_KEY
  2. CLAUDE_CODE_OAUTH_TOKEN env var → CredentialMode.OAUTH
  3. ~/.claude/credentials.json      → CredentialMode.OAUTH_INTERACTIVE
  4. ANTHROPIC_API env var (legacy)  → CredentialMode.API_KEY

Callers that need a mode string suitable for stdout output should use
``mode.value`` (e.g. ``"api_key"``, ``"oauth"``, ``"oauth_interactive"``).

Security note (CLAUDE.md §3.9):
- This module reads credentials to *detect* which mode to use.
- It never logs, prints, or stores credential values.
- Credential values never enter a microVM — only the *mode* does.
"""

from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path


class CredentialMode(str, Enum):
    """Detected credential mode, maps to install.sh ``mode=`` output."""

    API_KEY = "api_key"
    OAUTH = "oauth"
    OAUTH_INTERACTIVE = "oauth_interactive"


def detect_credential_mode(
    *,
    claude_dir: Path | None = None,
) -> CredentialMode | None:
    """Detect which credential mode is available, returning the highest-priority match.

    Args:
        claude_dir: Directory to search for ``credentials.json``.  Defaults to
            ``~/.claude/``.  Override in tests to point at a ``tmp_path``
            without touching the real home directory.

    Returns:
        The highest-priority ``CredentialMode`` found, or ``None`` when no
        credential source is configured.

    Precedence (first match wins):
        1. ``ANTHROPIC_API_KEY``       → ``API_KEY``
        2. ``CLAUDE_CODE_OAUTH_TOKEN`` → ``OAUTH``
        3. ``{claude_dir}/credentials.json`` with ``oauth_token`` key → ``OAUTH_INTERACTIVE``
        4. ``ANTHROPIC_API`` (legacy)  → ``API_KEY``
    """
    if claude_dir is None:
        claude_dir = Path.home() / ".claude"

    # Path 1 — canonical API key env var (highest precedence)
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return CredentialMode.API_KEY

    # Path 2 — OAuth bearer token in env
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip():
        return CredentialMode.OAUTH

    # Path 3 — interactive OAuth: ~/.claude/credentials.json
    credentials_path = claude_dir / "credentials.json"
    if credentials_path.is_file():
        try:
            data = json.loads(credentials_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        if data.get("oauth_token", ""):
            return CredentialMode.OAUTH_INTERACTIVE

    # Path 4 — legacy ANTHROPIC_API alias (lowest precedence, kept for back-compat)
    if os.environ.get("ANTHROPIC_API", "").strip():
        return CredentialMode.API_KEY

    return None
