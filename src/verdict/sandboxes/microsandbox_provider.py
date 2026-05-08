from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Literal


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
    timeout_seconds: int = 600,
) -> MicrosandboxRunResult:
    status = microsandbox_status()
    if status.binary is None:
        raise RuntimeError("microsandbox binary is required for forensic tool execution")

    result = _run_msb(
        status=status,
        args=[
            "run",
            "--no-net",
            "--pull",
            "never",
            "-v",
            f"{_volume_source(status, host_evidence_path.parent)}:/evidence",
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
) -> MicrosandboxRunResult:
    status = microsandbox_status()
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
    command = [status.binary, *args]
    if status.runner == "wsl":
        binary_path = Path(status.binary)
        bin_dir = str(binary_path.parent)
        lib_dir = str(binary_path.parent.parent / "lib")
        command = [
            "wsl.exe",
            "--exec",
            "/usr/bin/env",
            f"PATH={bin_dir}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            f"LD_LIBRARY_PATH={lib_dir}",
            status.binary,
            *args,
        ]
    return subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=text,
        timeout=timeout_seconds,
    )


def _volume_source(status: MicrosandboxStatus, host_path: Path) -> str:
    if status.runner == "wsl":
        return _windows_path_to_wsl(host_path)
    return str(host_path)


def _windows_path_to_wsl(path: Path) -> str:
    result = subprocess.run(
        ["wsl.exe", "wslpath", "-a", str(path)],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "wslpath failed")
    return result.stdout.strip()


def _wsl_microsandbox_binary() -> str | None:
    if which("wsl.exe") is None:
        return None
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
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return None
    binary = result.stdout.strip().splitlines()[0] if result.stdout.strip() else None
    return binary or None


def _image_sha256(image: str) -> str:
    marker = "@sha256:"
    if marker not in image:
        raise ValueError("microsandbox image must be pinned with @sha256:<digest>")
    digest = image.split(marker, 1)[1]
    if not re.fullmatch(r"[A-Fa-f0-9]{64}", digest):
        raise ValueError("microsandbox image digest must be 64 hex characters")
    return digest.lower()
