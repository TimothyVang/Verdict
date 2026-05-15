from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from verdict.schemas.tool_output import Artifact

LOLBIN_EXECUTABLES = {"regsvr32.exe", "rundll32.exe"}


@dataclass(frozen=True)
class ParsedToolOutput:
    artifacts: list[Artifact]
    warnings: list[str]


@dataclass(frozen=True)
class ParsedTable:
    headers: list[str]
    rows: list[dict[str, str]]


def parse_tool_stdout(tool_key: str, *, evidence_path: Path, stdout: bytes) -> ParsedToolOutput:
    text = stdout.decode(errors="replace")
    if tool_key == "vol3.info":
        return _with_empty_warning(tool_key, _parse_vol3_info(evidence_path, text))
    if tool_key == "vol3.pslist":
        return _with_empty_warning(
            tool_key,
            _parse_vol3_process_table(
                tool_key,
                evidence_path=evidence_path,
                text=text,
                artifact_type="process_listing",
            ),
        )
    if tool_key == "vol3.psscan":
        return _with_empty_warning(
            tool_key,
            _parse_vol3_process_table(
                tool_key,
                evidence_path=evidence_path,
                text=text,
                artifact_type="process_scan",
            ),
        )
    if tool_key == "mmls":
        return _with_empty_warning(tool_key, _parse_mmls(evidence_path, text))
    if tool_key == "fsstat":
        return _with_empty_warning(tool_key, _parse_fsstat(evidence_path, text))
    if tool_key == "fls":
        return _with_empty_warning(tool_key, _parse_fls(evidence_path, text))
    if tool_key == "icat":
        return _with_empty_warning(tool_key, _parse_icat(evidence_path, text))
    return ParsedToolOutput(artifacts=[], warnings=[f"no parser registered for {tool_key}"])


def _with_empty_warning(tool_key: str, parsed: ParsedToolOutput) -> ParsedToolOutput:
    if parsed.artifacts:
        return parsed
    return ParsedToolOutput(
        artifacts=[],
        warnings=[*parsed.warnings, f"parser produced no structured artifacts for {tool_key}"],
    )


def _parse_vol3_info(evidence_path: Path, text: str) -> ParsedToolOutput:
    table = _parse_table(text, required_headers=("Variable", "Value"))
    fields: dict[str, Any] = {}
    warnings: list[str] = []
    if not table and "Unsatisfied requirement" in text:
        return ParsedToolOutput(
            artifacts=[],
            warnings=["vol3 reported unsatisfied requirements"],
        )
    for row in table:
        variable = row.get("Variable")
        if variable:
            fields[_safe_key(variable)] = row.get("Value", "")

    if not fields:
        for line in _content_lines(text):
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            if key:
                fields[_safe_key(key)] = value.strip()

    if not fields:
        return ParsedToolOutput(artifacts=[], warnings=warnings)
    return ParsedToolOutput(
        artifacts=[
            _artifact(
                tool_key="vol3.info",
                evidence_path=evidence_path,
                artifact_type="memory_image_info",
                raw_fields=fields,
                index=0,
            )
        ],
        warnings=warnings,
    )


def _parse_vol3_process_table(
    tool_key: str,
    *,
    evidence_path: Path,
    text: str,
    artifact_type: str,
) -> ParsedToolOutput:
    table = _parse_table_result(text, required_headers=("PID", "ImageFileName"))
    artifacts: list[Artifact] = []
    for index, row in enumerate(table.rows):
        pid = _parse_int(row.get("PID"))
        if pid is None:
            continue
        ppid = _parse_int(row.get("PPID"))
        raw_fields: dict[str, Any] = {
            **row,
            "pid": pid,
            "image_file_name": row.get("ImageFileName", ""),
        }
        if ppid is not None:
            raw_fields["ppid"] = ppid
        artifacts.append(
            _artifact(
                tool_key=tool_key,
                evidence_path=evidence_path,
                artifact_type=artifact_type,
                raw_fields=raw_fields,
                index=index,
            )
        )
    if artifacts:
        return ParsedToolOutput(artifacts=artifacts, warnings=[])
    if table.headers:
        return ParsedToolOutput(
            artifacts=[
                _artifact(
                    tool_key=tool_key,
                    evidence_path=evidence_path,
                    artifact_type=f"{artifact_type}_summary",
                    raw_fields={"headers": table.headers, "row_count": 0},
                    index=0,
                )
            ],
            warnings=[],
        )
    return ParsedToolOutput(artifacts=[], warnings=["vol3 process table header not found"])


def _parse_mmls(evidence_path: Path, text: str) -> ParsedToolOutput:
    artifacts: list[Artifact] = []
    for index, line in enumerate(_content_lines(text)):
        if not re.match(r"^\d{3}:", line):
            continue
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        start = _parse_int(parts[2])
        end = _parse_int(parts[3])
        length = _parse_int(parts[4])
        raw_fields: dict[str, Any] = {
            "slot": f"{parts[0]} {parts[1]}",
            "start_sector": start if start is not None else parts[2],
            "end_sector": end if end is not None else parts[3],
            "length_sectors": length if length is not None else parts[4],
            "description": parts[5].strip(),
        }
        artifacts.append(
            _artifact(
                tool_key="mmls",
                evidence_path=evidence_path,
                artifact_type="partition_table_entry",
                raw_fields=raw_fields,
                index=index,
            )
        )
    return ParsedToolOutput(artifacts=artifacts, warnings=[])


def _parse_fsstat(evidence_path: Path, text: str) -> ParsedToolOutput:
    fields: dict[str, Any] = {}
    for line in _content_lines(text):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key:
            fields[_safe_key(key)] = value.strip()
    if not fields:
        return ParsedToolOutput(artifacts=[], warnings=[])
    return ParsedToolOutput(
        artifacts=[
            _artifact(
                tool_key="fsstat",
                evidence_path=evidence_path,
                artifact_type="filesystem_metadata",
                raw_fields=fields,
                index=0,
            )
        ],
        warnings=[],
    )


def _parse_fls(evidence_path: Path, text: str) -> ParsedToolOutput:
    artifacts: list[Artifact] = []
    pattern = re.compile(
        r"^(?P<depth>\+*)\s*"
        r"(?P<file_type>[-A-Za-z]/[-A-Za-z])\s+"
        r"(?P<deleted>\*)?\s*"
        r"(?P<metadata_address>[^:]+):\s*"
        r"(?P<name>.+)$"
    )
    for index, line in enumerate(_content_lines(text)):
        match = pattern.match(line)
        if not match:
            continue
        raw_fields = {
            "file_type": match.group("file_type"),
            "deleted": bool(match.group("deleted")),
            "metadata_address": match.group("metadata_address").strip(),
            "name": match.group("name").strip(),
        }
        artifacts.append(
            _artifact(
                tool_key="fls",
                evidence_path=evidence_path,
                artifact_type="filesystem_listing_entry",
                raw_fields=raw_fields,
                index=index,
            )
        )
        prefetch_match = re.fullmatch(
            r"(?P<executable>[A-Za-z0-9_.-]+?\.EXE)-[A-Fa-f0-9]+\.pf",
            raw_fields["name"],
            re.IGNORECASE,
        )
        if prefetch_match is None:
            continue
        executable = prefetch_match.group("executable").lower()
        if executable not in LOLBIN_EXECUTABLES:
            continue
        metadata_address = raw_fields["metadata_address"]
        artifacts.append(
            _artifact(
                tool_key="fls",
                evidence_path=evidence_path,
                artifact_type="prefetch_listing_entry",
                raw_fields={
                    "executable": executable,
                    "prefetch_name": raw_fields["name"],
                    "metadata_address": metadata_address,
                    "artifact_path": f"{evidence_path}#fls_prefetch:{metadata_address}",
                },
                index=len(artifacts),
            )
        )
    return ParsedToolOutput(artifacts=artifacts, warnings=[])


def _parse_icat(evidence_path: Path, text: str) -> ParsedToolOutput:
    artifacts: list[Artifact] = []
    start_time = _line_value(text, "Start time")
    username = _line_value(text, "Username")
    command_pattern = re.compile(r"CommandInvocation\((?P<executable>[^)]+\.exe)\)", re.IGNORECASE)
    for index, match in enumerate(command_pattern.finditer(text)):
        executable = match.group("executable").lower()
        if executable not in LOLBIN_EXECUTABLES:
            continue
        raw_fields: dict[str, Any] = {
            "executable": executable,
            "artifact_path": f"{evidence_path}#powershell_transcript_command:{index}",
        }
        if start_time:
            raw_fields["start_time"] = start_time
        if username:
            raw_fields["username"] = username
        artifacts.append(
            _artifact(
                tool_key="icat",
                evidence_path=evidence_path,
                artifact_type="powershell_transcript_command",
                raw_fields=raw_fields,
                index=len(artifacts),
            )
        )

    prefetch_pattern = re.compile(
        r"(?P<prefetch_path>[A-Za-z]:\\WINDOWS\\Prefetch\\"
        r"(?P<executable>[A-Za-z0-9_.-]+?\.EXE)-[A-Fa-f0-9]+\.pf)\s+"
        r"(?P<creation_time_utc>\d{4}-\d{2}-\d{2}T\S+Z)\s+"
        r"(?P<last_access_time_utc>\d{4}-\d{2}-\d{2}T\S+Z)",
        re.IGNORECASE,
    )
    for index, match in enumerate(prefetch_pattern.finditer(text)):
        executable = match.group("executable").lower()
        if executable not in LOLBIN_EXECUTABLES:
            continue
        raw_fields = {
            "executable": executable,
            "prefetch_path": match.group("prefetch_path"),
            "creation_time_utc": match.group("creation_time_utc"),
            "last_access_time_utc": match.group("last_access_time_utc"),
            "artifact_path": f"{evidence_path}#prefetch_listing_entry:{index}",
        }
        artifacts.append(
            _artifact(
                tool_key="icat",
                evidence_path=evidence_path,
                artifact_type="prefetch_listing_entry",
                raw_fields=raw_fields,
                index=len(artifacts),
            )
        )

    return ParsedToolOutput(artifacts=artifacts, warnings=[])


def _parse_table(text: str, *, required_headers: tuple[str, ...]) -> list[dict[str, str]]:
    return _parse_table_result(text, required_headers=required_headers).rows


def _parse_table_result(text: str, *, required_headers: tuple[str, ...]) -> ParsedTable:
    lines = _content_lines(text)
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if all(header in _split_row(line) for header in required_headers)
        ),
        None,
    )
    if header_index is None:
        return ParsedTable(headers=[], rows=[])
    headers = _split_row(lines[header_index])
    rows: list[dict[str, str]] = []
    for line in lines[header_index + 1 :]:
        if set(line) <= {"-", " ", "\t"}:
            continue
        values = _split_row(line, maxsplit=len(headers) - 1)
        if len(values) < len(headers):
            continue
        rows.append(dict(zip(headers, values, strict=False)))
    return ParsedTable(headers=headers, rows=rows)


def _split_row(line: str, *, maxsplit: int = -1) -> list[str]:
    if "\t" in line:
        return [part.strip() for part in line.split("\t") if part.strip()]
    return [part.strip() for part in re.split(r"\s{2,}", line.strip(), maxsplit=maxsplit) if part]


def _content_lines(text: str) -> list[str]:
    ignored_prefixes = ("Volatility 3 Framework", "Progress:")
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith(ignored_prefixes)
    ]


def _safe_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _line_value(text: str, label: str) -> str | None:
    prefix = f"{label}:"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped.split(":", 1)[1].strip()
    return None


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = value.strip().replace(",", "")
    if not cleaned or cleaned in {"-", "N/A"}:
        return None
    try:
        if cleaned.isdigit():
            return int(cleaned, 10)
        return int(cleaned, 0)
    except ValueError:
        return None


def _artifact(
    *,
    tool_key: str,
    evidence_path: Path,
    artifact_type: str,
    raw_fields: dict[str, Any],
    index: int,
) -> Artifact:
    artifact_payload = json.dumps(raw_fields, sort_keys=True, default=str)
    artifact_hash = sha256(
        f"{tool_key}\0{artifact_type}\0{evidence_path}\0{index}\0{artifact_payload}".encode()
    ).hexdigest()
    return Artifact(
        artifact_id=f"{tool_key}:{artifact_hash}",
        evidence_path=evidence_path,
        artifact_type=artifact_type,
        raw_fields=raw_fields,
    )
