from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from shutil import which
from typing import Literal

SAFE_MSB_ENV_KEYS = {"COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "WINDIR"}


@dataclass(frozen=True)
class MicrosandboxStatus:
    available: bool
    binary: str | None
    runner: Literal["native", "wsl"] | None = None


@dataclass(frozen=True)
class MicrosandboxRunResult:
    stdout: bytes
    stderr: bytes
    exit_code: int
    microsandbox_version: str
    rootfs_sha256: str


@dataclass(frozen=True)
class MicrosandboxMount:
    host_path: Path
    guest_path: str


@dataclass(frozen=True)
class MicrosandboxImageReady:
    ready: bool
    image: str
    reason: str
    microsandbox_version: str | None = None
    rootfs_sha256: str | None = None


def microsandbox_status() -> MicrosandboxStatus:
    binary = which("msb") or which("microsandbox")
    if binary is not None:
        return MicrosandboxStatus(available=True, binary=binary, runner="native")
    wsl_binary = _wsl_microsandbox_binary()
    if wsl_binary is not None:
        return MicrosandboxStatus(available=True, binary=wsl_binary, runner="wsl")
    return MicrosandboxStatus(available=False, binary=None, runner=None)


def run_in_microsandbox(
    *,
    image: str,
    host_evidence_path: Path,
    command: list[str],
    extra_mounts: tuple[MicrosandboxMount, ...] = (),
    timeout_seconds: int = 600,
    status: MicrosandboxStatus | None = None,
) -> MicrosandboxRunResult:
    status = microsandbox_status() if status is None else status
    if status.binary is None:
        raise RuntimeError("microsandbox binary is required for forensic tool execution")

    volume_args = [
        "-v",
        f"{_volume_source(status, host_evidence_path.parent)}:/evidence",
    ]
    for mount in extra_mounts:
        volume_args.extend(
            [
                "-v",
                f"{_volume_source(status, mount.host_path)}:{mount.guest_path}",
            ]
        )

    result = _run_msb(
        status=status,
        args=[
            "run",
            "--no-net",
            "--pull",
            "never",
            *volume_args,
            "--timeout",
            f"{timeout_seconds}s",
            image,
            "--",
            *command,
        ],
        timeout_seconds=timeout_seconds + 30,
    )
    return MicrosandboxRunResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.returncode,
        microsandbox_version=_microsandbox_version(status),
        rootfs_sha256=_image_sha256(image),
    )


def run_microsandbox_command(
    *,
    image: str,
    command: list[str],
    timeout_seconds: int = 120,
    status: MicrosandboxStatus | None = None,
) -> MicrosandboxRunResult:
    status = microsandbox_status() if status is None else status
    if status.binary is None:
        raise RuntimeError("microsandbox binary is required for forensic tool execution")
    result = _run_msb(
        status=status,
        args=[
            "run",
            "--no-net",
            "--pull",
            "never",
            "--timeout",
            f"{timeout_seconds}s",
            image,
            "--",
            *command,
        ],
        timeout_seconds=timeout_seconds + 30,
    )
    return MicrosandboxRunResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.returncode,
        microsandbox_version=_microsandbox_version(status),
        rootfs_sha256=_image_sha256(image),
    )


def check_microsandbox_image_ready(
    image: str,
    *,
    status: MicrosandboxStatus | None = None,
    timeout_seconds: int = 120,
) -> MicrosandboxImageReady:
    try:
        rootfs_sha256 = _image_sha256(image)
    except ValueError as exc:
        return MicrosandboxImageReady(ready=False, image=image, reason=str(exc))

    status = microsandbox_status() if status is None else status
    if status.binary is None:
        return MicrosandboxImageReady(
            ready=False,
            image=image,
            reason="microsandbox binary is required for image readiness checks",
            rootfs_sha256=rootfs_sha256,
        )

    try:
        result = run_microsandbox_command(
            image=image,
            command=[
                "sh",
                "-lc",
                "test -r /etc/os-release && command -v sh >/dev/null && printf READY",
            ],
            timeout_seconds=timeout_seconds,
            status=status,
        )
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        return MicrosandboxImageReady(
            ready=False,
            image=image,
            reason=str(exc),
            rootfs_sha256=rootfs_sha256,
        )

    if result.exit_code != 0:
        reason = (result.stderr or result.stdout).decode(errors="replace").strip()
        return MicrosandboxImageReady(
            ready=False,
            image=image,
            reason=reason or f"readiness command exited {result.exit_code}",
            microsandbox_version=result.microsandbox_version,
            rootfs_sha256=rootfs_sha256,
        )

    return MicrosandboxImageReady(
        ready=True,
        image=image,
        reason="ready",
        microsandbox_version=result.microsandbox_version,
        rootfs_sha256=rootfs_sha256,
    )


def _microsandbox_version(status: MicrosandboxStatus) -> str:
    if status.binary is None:
        return "unavailable"
    result = _run_msb(
        status=status,
        args=["--version"],
        timeout_seconds=30,
        text=True,
    )
    return (result.stdout or result.stderr).strip() or Path(status.binary).name


def _run_msb(
    *,
    status: MicrosandboxStatus,
    args: list[str],
    timeout_seconds: int,
    text: bool = False,
) -> subprocess.CompletedProcess:
    if status.binary is None:
        raise RuntimeError("microsandbox binary is required for forensic tool execution")
    command = _build_msb_command(status=status, args=args)
    return subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=text,
        timeout=timeout_seconds,
        env=_scrubbed_msb_env(os.environ),
    )


def _build_msb_command(*, status: MicrosandboxStatus, args: list[str]) -> list[str]:
    if status.binary is None:
        raise RuntimeError("microsandbox binary is required for forensic tool execution")
    if status.runner != "wsl":
        return [status.binary, *args]

    binary_path = Path(status.binary)
    bin_dir = str(binary_path.parent)
    lib_dir = str(binary_path.parent.parent / "lib")
    return [
        "wsl.exe",
        "--exec",
        "/usr/bin/env",
        f"PATH={bin_dir}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        f"LD_LIBRARY_PATH={lib_dir}",
        status.binary,
        *args,
    ]


def _scrubbed_msb_env(source_env: os._Environ[str] | dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in source_env.items() if key.upper() in SAFE_MSB_ENV_KEYS}


def _volume_source(status: MicrosandboxStatus, host_path: Path) -> str:
    if status.runner == "wsl":
        return _wsl_mount_source(_windows_path_to_wsl(host_path))
    return str(host_path)


def _wsl_mount_source(wsl_path: str) -> str:
    if not any(char.isspace() for char in wsl_path):
        return wsl_path
    link_path = f"/tmp/verdict-msb-mounts/{sha256(wsl_path.encode()).hexdigest()[:16]}"
    result = subprocess.run(
        [
            "wsl.exe",
            "--exec",
            "/bin/sh",
            "-lc",
            "mkdir -p /tmp/verdict-msb-mounts && ln -sfn -- \"$1\" \"$2\" && test -e \"$2\"",
            "verdict-msb-mount",
            wsl_path,
            link_path,
        ],
        capture_output=True,
        check=False,
        env=_scrubbed_msb_env(os.environ),
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "WSL mount symlink failed")
    return link_path


def _windows_path_to_wsl(path: Path) -> str:
    result = subprocess.run(
        ["wsl.exe", "wslpath", "-a", str(path)],
        capture_output=True,
        check=False,
        env=_scrubbed_msb_env(os.environ),
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "wslpath failed")
    return result.stdout.strip()


def _wsl_microsandbox_binary() -> str | None:
    if which("wsl.exe") is None:
        return None
    for _attempt in range(2):
        try:
            result = subprocess.run(
                [
                    "wsl.exe",
                    "--exec",
                    "/bin/sh",
                    "-lc",
                    (
                        "if [ -x \"$HOME/.microsandbox/bin/msb\" ]; then "
                        "printf '%s\\n' \"$HOME/.microsandbox/bin/msb\"; "
                        "elif command -v msb >/dev/null 2>&1; then command -v msb; "
                        "else command -v microsandbox; fi"
                    ),
                ],
                capture_output=True,
                check=False,
                env=_scrubbed_msb_env(os.environ),
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0]
    return None


def _image_sha256(image: str) -> str:
    marker = "@sha256:"
    if marker not in image:
        raise ValueError("microsandbox image must be pinned with @sha256:<digest>")
    digest = image.split(marker, 1)[1]
    if not re.fullmatch(r"[A-Fa-f0-9]{64}", digest):
        raise ValueError("microsandbox image digest must be 64 hex characters")
    return digest.lower()
