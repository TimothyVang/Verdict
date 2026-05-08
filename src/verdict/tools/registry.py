from __future__ import annotations

from verdict.tools.external import ExternalToolSpec

TOOL_SPECS: dict[str, ExternalToolSpec] = {
    "vol3.info": ExternalToolSpec(
        tool_name="vol3.windows.info",
        executable_candidates=("vol3", "vol"),
        base_args=("-f", "{evidence}", "windows.info"),
        artifact_type="memory_image_info",
    ),
    "vol3.pslist": ExternalToolSpec(
        tool_name="vol3.windows.pslist",
        executable_candidates=("vol3", "vol"),
        base_args=("-f", "{evidence}", "windows.pslist"),
        artifact_type="process_listing",
    ),
    "vol3.psscan": ExternalToolSpec(
        tool_name="vol3.windows.psscan",
        executable_candidates=("vol3", "vol"),
        base_args=("-f", "{evidence}", "windows.psscan"),
        artifact_type="process_scan",
    ),
    "mmls": ExternalToolSpec(
        tool_name="mmls",
        executable_candidates=("mmls",),
        base_args=("{evidence}",),
        artifact_type="partition_table",
        version_args=("-V",),
    ),
    "fsstat": ExternalToolSpec(
        tool_name="fsstat",
        executable_candidates=("fsstat",),
        base_args=("{evidence}",),
        artifact_type="filesystem_metadata",
        version_args=("-V",),
    ),
    "fls": ExternalToolSpec(
        tool_name="fls",
        executable_candidates=("fls",),
        base_args=("-r", "{evidence}"),
        artifact_type="filesystem_listing",
        version_args=("-V",),
    ),
}


def available_tools() -> dict[str, bool]:
    return {name: False for name in TOOL_SPECS}


def microsandbox_command(
    tool_key: str,
    *,
    evidence_name: str,
    extra_args: tuple[str, ...] = (),
) -> list[str]:
    if tool_key not in TOOL_SPECS:
        raise ValueError(f"unknown tool: {tool_key}")
    spec = TOOL_SPECS[tool_key]
    executable = spec.executable_candidates[0]
    return [
        executable,
        *extra_args,
        *(f"/evidence/{evidence_name}" if arg == "{evidence}" else arg for arg in spec.base_args),
    ]
