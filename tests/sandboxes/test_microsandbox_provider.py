from __future__ import annotations

import subprocess
from pathlib import Path

from verdict.sandboxes import microsandbox_provider
from verdict.sandboxes.microsandbox_provider import (
    MicrosandboxMount,
    MicrosandboxStatus,
    _build_msb_command,
    _scrubbed_msb_env,
    _volume_source,
    _windows_path_to_wsl,
    check_microsandbox_image_ready,
    microsandbox_status,
    run_in_microsandbox,
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


def test_microsandbox_status_retries_transient_wsl_probe_failure(monkeypatch) -> None:
    def which(name: str) -> str | None:
        return "C:/Windows/System32/wsl.exe" if name == "wsl.exe" else None

    calls = 0

    def run(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return subprocess.CompletedProcess(args[0], 1, stdout="", stderr="starting")
        return subprocess.CompletedProcess(
            args[0],
            0,
            stdout="/home/newbi/.microsandbox/bin/msb\n",
            stderr="",
        )

    monkeypatch.setattr(microsandbox_provider, "which", which)
    monkeypatch.setattr(microsandbox_provider.subprocess, "run", run)

    assert microsandbox_status() == MicrosandboxStatus(
        available=True,
        binary="/home/newbi/.microsandbox/bin/msb",
        runner="wsl",
    )
    assert calls == 2


def test_microsandbox_command_uses_source_destination_volume_syntax() -> None:
    command = _build_msb_command(
        status=MicrosandboxStatus(available=True, binary="msb", runner="native"),
        args=[
            "run",
            "--no-net",
            "--pull",
            "never",
            "-v",
            f"{Path('evidence').resolve()}:/evidence",
            "image@sha256:" + "a" * 64,
        ],
    )

    assert any(arg.endswith(":/evidence") for arg in command)
    assert not any(arg.endswith(":/evidence:ro,noexec") for arg in command)


def test_run_in_microsandbox_mounts_plain_guest_evidence_path(monkeypatch, tmp_path) -> None:
    evidence_file = tmp_path / "memory.mem"
    evidence_file.write_bytes(b"")
    captured_commands: list[list[str]] = []

    def which(name: str) -> str | None:
        return "msb" if name == "msb" else None

    def run(command, **kwargs):
        captured_commands.append(command)
        if "--version" in command:
            return subprocess.CompletedProcess(command, 0, stdout="msb 0.4.5", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout=b"ok", stderr=b"")

    monkeypatch.setattr(microsandbox_provider, "which", which)
    monkeypatch.setattr(subprocess, "run", run)

    run_in_microsandbox(
        image="registry.local/verdict-sift@sha256:" + "a" * 64,
        host_evidence_path=evidence_file,
        command=["true"],
    )

    volume_arg = captured_commands[0][captured_commands[0].index("-v") + 1]
    assert volume_arg.endswith(":/evidence")
    assert not volume_arg.endswith(":/evidence:ro,noexec")


def test_run_in_microsandbox_mounts_additional_forensic_workdirs(monkeypatch, tmp_path) -> None:
    evidence_file = tmp_path / "memory.mem"
    symbols_dir = tmp_path / "symbols"
    cache_dir = tmp_path / "cache"
    evidence_file.write_bytes(b"")
    symbols_dir.mkdir()
    cache_dir.mkdir()
    captured_commands: list[list[str]] = []

    def which(name: str) -> str | None:
        return "msb" if name == "msb" else None

    def run(command, **kwargs):
        captured_commands.append(command)
        if "--version" in command:
            return subprocess.CompletedProcess(command, 0, stdout="msb 0.4.5", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout=b"ok", stderr=b"")

    monkeypatch.setattr(microsandbox_provider, "which", which)
    monkeypatch.setattr(subprocess, "run", run)

    run_in_microsandbox(
        image="registry.local/verdict-sift@sha256:" + "a" * 64,
        host_evidence_path=evidence_file,
        command=["true"],
        extra_mounts=(
            MicrosandboxMount(host_path=symbols_dir, guest_path="/volatility-symbols"),
            MicrosandboxMount(host_path=cache_dir, guest_path="/volatility-cache"),
        ),
    )

    volumes = [
        captured_commands[0][index + 1]
        for index, value in enumerate(captured_commands[0])
        if value == "-v"
    ]
    assert any(volume.endswith(":/evidence") for volume in volumes)
    assert any(volume.endswith(":/volatility-symbols") for volume in volumes)
    assert any(volume.endswith(":/volatility-cache") for volume in volumes)


def test_run_in_microsandbox_reuses_resolved_status(monkeypatch, tmp_path) -> None:
    evidence_file = tmp_path / "memory.mem"
    evidence_file.write_bytes(b"")
    captured_commands: list[list[str]] = []

    def which(name: str) -> str | None:
        raise AssertionError("run_in_microsandbox must not re-probe when status is supplied")

    def run(command, **kwargs):
        captured_commands.append(command)
        if "--version" in command:
            return subprocess.CompletedProcess(command, 0, stdout="msb 0.4.5", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout=b"ok", stderr=b"")

    monkeypatch.setattr(microsandbox_provider, "which", which)
    monkeypatch.setattr(subprocess, "run", run)

    run_in_microsandbox(
        image="registry.local/verdict-sift@sha256:" + "a" * 64,
        host_evidence_path=evidence_file,
        command=["true"],
        status=MicrosandboxStatus(available=True, binary="msb", runner="native"),
    )

    assert captured_commands[0][0] == "msb"


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


def test_wsl_volume_source_uses_space_free_symlink_for_paths_with_spaces(monkeypatch) -> None:
    captured_commands: list[list[str]] = []

    def run(command, **kwargs):
        captured_commands.append(command)
        if command[:3] == ["wsl.exe", "wslpath", "-a"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="/mnt/c/Users/newbi/Desktop/PUG Projects/verdict-code/evidence\n",
                stderr="",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", run)

    source = _volume_source(
        MicrosandboxStatus(available=True, binary="/home/newbi/.microsandbox/bin/msb", runner="wsl"),
        Path("C:/Users/newbi/Desktop/PUG Projects/verdict-code/evidence"),
    )

    assert source.startswith("/tmp/verdict-msb-mounts/")
    assert " " not in source
    assert captured_commands[1][-2:] == [
        "/mnt/c/Users/newbi/Desktop/PUG Projects/verdict-code/evidence",
        source,
    ]


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
