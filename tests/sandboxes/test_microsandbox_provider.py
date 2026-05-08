from __future__ import annotations

import subprocess
from pathlib import Path

from verdict.sandboxes import microsandbox_provider
from verdict.sandboxes.microsandbox_provider import (
    MicrosandboxStatus,
    _build_msb_command,
    _scrubbed_msb_env,
    _windows_path_to_wsl,
    check_microsandbox_image_ready,
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


def test_wsl_path_conversion_uses_scrubbed_environment(monkeypatch) -> None:
    captured_env: dict[str, str] = {}

    def run(*args, **kwargs):
        nonlocal captured_env
        captured_env = kwargs["env"]
        return subprocess.CompletedProcess(args[0], 0, stdout="/mnt/c/evidence\n", stderr="")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "secret")
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", "ab" * 32)
    monkeypatch.setattr(subprocess, "run", run)

    assert _windows_path_to_wsl(Path("C:/evidence")) == "/mnt/c/evidence"
    assert "ANTHROPIC_API_KEY" not in captured_env
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in captured_env
    assert "VERDICT_HMAC_KEY_HEX" not in captured_env


def test_check_microsandbox_image_ready_requires_pinned_digest() -> None:
    result = check_microsandbox_image_ready("verdict/sift:latest")

    assert not result.ready
    assert "pinned" in result.reason


def test_check_microsandbox_image_ready_runs_inside_microsandbox(monkeypatch) -> None:
    captured_command: list[str] = []

    def run(*args, **kwargs):
        nonlocal captured_command
        command = args[0]
        if "--version" in command:
            return subprocess.CompletedProcess(captured_command, 0, stdout=b"msb 0.1", stderr=b"")
        captured_command = command
        return subprocess.CompletedProcess(command, 0, stdout=b"READY", stderr=b"")

    monkeypatch.setattr(subprocess, "run", run)

    result = check_microsandbox_image_ready(
        "registry.local/verdict-sift@sha256:" + "a" * 64,
        status=MicrosandboxStatus(available=True, binary="msb", runner="native"),
    )

    assert result.ready
    assert captured_command[:6] == ["msb", "run", "--no-net", "--pull", "never", "--timeout"]
