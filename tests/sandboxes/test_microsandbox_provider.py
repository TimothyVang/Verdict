from __future__ import annotations

import subprocess
from pathlib import Path

from verdict.sandboxes import microsandbox_provider
from verdict.sandboxes.microsandbox_provider import (
    MicrosandboxStatus,
    _build_msb_command,
    _scrubbed_msb_env,
    microsandbox_status,
)


def test_microsandbox_status_reports_boolean_availability() -> None:
    status = microsandbox_status()

    assert isinstance(status.available, bool)
    assert status.binary is None or status.binary


def test_microsandbox_status_treats_wsl_probe_timeout_as_unavailable(monkeypatch) -> None:
    def which(name: str) -> str | None:
        return "C:/Windows/System32/wsl.exe" if name == "wsl.exe" else None

    def run(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs.get("timeout"))

    monkeypatch.setattr(microsandbox_provider, "which", which)
    monkeypatch.setattr(microsandbox_provider.subprocess, "run", run)

    assert microsandbox_status() == MicrosandboxStatus(available=False, binary=None, runner=None)


def test_microsandbox_command_mounts_evidence_readonly() -> None:
    command = _build_msb_command(
        status=MicrosandboxStatus(available=True, binary="msb", runner="native"),
        args=[
            "run",
            "--no-net",
            "--pull",
            "never",
            "-v",
            f"{Path('evidence').resolve()}:/evidence:ro,noexec",
            "image@sha256:" + "a" * 64,
        ],
    )

    assert any(arg.endswith(":/evidence:ro,noexec") for arg in command)


def test_microsandbox_env_drops_credentials_and_hmac_keys() -> None:
    env = _scrubbed_msb_env(
        {
            "PATH": "C:/bin",
            "ANTHROPIC_API_KEY": "secret",
            "CLAUDE_CODE_OAUTH_TOKEN": "secret",
            "OPENROUTER_API_KEY": "secret",
            "VERDICT_HMAC_KEY_HEX": "ab" * 32,
            "SYSTEMROOT": "C:/Windows",
        }
    )

    assert env == {"PATH": "C:/bin", "SYSTEMROOT": "C:/Windows"}
