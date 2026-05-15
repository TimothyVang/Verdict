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
        base_args=("{evidence}",),
        artifact_type="filesystem_listing",
        version_args=("-V",),
    ),
    "icat": ExternalToolSpec(
        tool_name="icat",
        executable_candidates=("icat",),
        base_args=("{evidence}", "{metadata_address}"),
        artifact_type="file_content",
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
    volatility_symbol_dir: str | None = None,
    volatility_cache_path: str | None = None,
) -> list[str]:
    if tool_key not in TOOL_SPECS:
        raise ValueError(f"unknown tool: {tool_key}")
    spec = TOOL_SPECS[tool_key]
    executable = spec.executable_candidates[0]
    global_args: list[str] = []
    if tool_key.startswith("vol3."):
        if volatility_symbol_dir:
            global_args.extend(["--symbol-dirs", volatility_symbol_dir])
        if volatility_cache_path:
            global_args.extend(["--cache-path", volatility_cache_path])
    if "{metadata_address}" in spec.base_args:
        if len(extra_args) != 1:
            raise ValueError(f"{tool_key} requires exactly one metadata address")
        metadata_address = extra_args[0]
        return [
            executable,
            *global_args,
            *(
                f"/evidence/{evidence_name}"
                if arg == "{evidence}"
                else metadata_address
                if arg == "{metadata_address}"
                else arg
                for arg in spec.base_args
            ),
        ]
    return [
        executable,
        *global_args,
        *extra_args,
        *(f"/evidence/{evidence_name}" if arg == "{evidence}" else arg for arg in spec.base_args),
    ]
