from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from shutil import which

from verdict.schemas.tool_output import ToolOutput
from verdict.tools.base import ToolWrapper
from verdict.tools.sanitization import scan_tool_stdout


class ToolUnavailableError(RuntimeError):
    """Raised when a required forensic binary is not installed on this host."""


@dataclass(frozen=True)
class ExternalToolSpec:
    tool_name: str
    executable_candidates: tuple[str, ...]
    base_args: tuple[str, ...]
    artifact_type: str
    version_args: tuple[str, ...] = ("--version",)


class ExternalToolWrapper(ToolWrapper):
    """Run a real external forensic command and emit the shared ToolOutput contract."""

    def __init__(self, spec: ExternalToolSpec, *, evidence_path: Path, timeout_seconds: int = 600):
        self.spec = spec
        self.evidence_path = evidence_path
        self.timeout_seconds = timeout_seconds
        self.executable = _resolve_executable(spec.executable_candidates)
        self.tool_name = spec.tool_name
        self.tool_version = _tool_version(self.executable, spec.version_args)

    def invocation_args(self) -> list[str]:
        return [*self.spec.base_args]

    def execute_for_evidence(self, *, evidence_hash: str) -> ToolOutput:
        return self.execute(invocation_args=self.invocation_args(), evidence_hash=evidence_hash)

    def run(self, *, invocation_args: list[str], evidence_hash: str) -> ToolOutput:
        result = subprocess.run(
            [self.executable, *invocation_args],
            capture_output=True,
            check=False,
            timeout=self.timeout_seconds,
        )
        stdout_text = result.stdout.decode(errors="replace")
        return ToolOutput.from_invocation(
            tool_name=self.tool_name,
            tool_version=self.tool_version,
            invocation_args=invocation_args,
            evidence_hash=evidence_hash,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            parsed_artifacts=[],
        ).model_copy(
            update={
                "parse_warnings": [
                    "raw external output captured; no per-tool parser has claimed artifacts"
                ],
                "sanitization_flags": scan_tool_stdout(stdout_text),
            }
        )


def _resolve_executable(candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        resolved = which(candidate)
        if resolved:
            return resolved
    raise ToolUnavailableError(f"required tool not found; tried: {', '.join(candidates)}")


def _tool_version(executable: str, version_args: tuple[str, ...]) -> str:
    result = subprocess.run(
        [executable, *version_args],
        capture_output=True,
        check=False,
        timeout=30,
        text=True,
    )
    version = (result.stdout or result.stderr).strip().splitlines()
    return version[0] if version else Path(executable).name
