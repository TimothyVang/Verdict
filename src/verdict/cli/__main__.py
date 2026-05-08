from __future__ import annotations

import argparse
import getpass
import html
import json
import os
import platform
import re
import sys
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from verdict.ledger.hmac_key import load_or_create_hmac_key
from verdict.ledger.writer import LedgerWriter, verify_ledger_chain
from verdict.runtime.mode_detect import (
    Mode,
    ModeDetectionError,
    detect_mode,
    has_local_inference_endpoint,
    mode_is_available,
    parse_mode,
)
from verdict.sandboxes.microsandbox_provider import (
    MicrosandboxStatus,
    microsandbox_status,
    run_in_microsandbox,
    run_microsandbox_command,
)
from verdict.schemas.case_conclusion import CaseConclusion
from verdict.schemas.evidence import EvidenceItem, EvidenceManifest, EvidenceType
from verdict.schemas.tool_output import ToolOutput
from verdict.tools.parsers import parse_tool_stdout
from verdict.tools.registry import TOOL_SPECS, available_tools, microsandbox_command
from verdict.tools.sanitization import scan_tool_stdout


class CliError(RuntimeError):
    """Command failed due to operator input or missing local prerequisites."""


DEVPOST_REQUIRED_PATHS = (
    "README.md",
    "LICENSE",
    "docs/ARCHITECTURE.md",
    "docs/ARCHITECTURE_DIAGRAM.svg",
    "docs/DEVPOST_COMPLIANCE.md",
    "docs/FAILURE_MODES.md",
    "docs/CASE_ISOLATION.md",
    "docs/RELEASE.md",
    "submission/execution-logs/case_001.jsonl",
    "submission/execution-logs/case_002.jsonl",
    "submission/execution-logs/case_003.jsonl",
)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (CliError, ModeDetectionError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="verdict")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a case and hash evidence")
    init_parser.add_argument("evidence_path", type=Path)
    init_parser.add_argument("--case-id")
    init_parser.add_argument("--cases-dir", default=Path("cases"), type=Path)
    init_parser.add_argument("--mode", choices=["cloud", "airgap", "dual"])
    init_parser.set_defaults(func=_cmd_init)

    export_parser = subparsers.add_parser("export", help="Export case ledger artifacts")
    export_parser.add_argument("case_id")
    export_parser.add_argument("--cases-dir", default=Path("cases"), type=Path)
    export_parser.add_argument(
        "--format",
        choices=["jsonl", "execution-logs", "html"],
        default="jsonl",
    )
    export_parser.add_argument("--output", type=Path)
    export_parser.set_defaults(func=_cmd_export)

    ls_parser = subparsers.add_parser("ls", help="List local cases")
    ls_parser.add_argument("--cases-dir", default=Path("cases"), type=Path)
    ls_parser.set_defaults(func=_cmd_ls)

    status_parser = subparsers.add_parser("status", help="Print machine-readable case status")
    status_parser.add_argument("case_id")
    status_parser.add_argument("--cases-dir", default=Path("cases"), type=Path)
    status_parser.set_defaults(func=_cmd_status)

    show_parser = subparsers.add_parser("show", help="Show a human-readable case summary")
    show_parser.add_argument("case_id")
    show_parser.add_argument("--cases-dir", default=Path("cases"), type=Path)
    show_parser.set_defaults(func=_cmd_show)

    run_tool_parser = subparsers.add_parser("run-tool", help="Run a registered real SIFT tool")
    run_tool_parser.add_argument("case_id")
    run_tool_parser.add_argument("tool", choices=sorted(TOOL_SPECS))
    run_tool_parser.add_argument("--cases-dir", default=Path("cases"), type=Path)
    run_tool_parser.add_argument("--evidence-index", default=0, type=int)
    run_tool_parser.set_defaults(func=_cmd_run_tool)

    run_case_parser = subparsers.add_parser(
        "run-case",
        help="Run the canonical real-tool triage sequence for a case",
    )
    run_case_parser.add_argument("case_id")
    run_case_parser.add_argument("--cases-dir", default=Path("cases"), type=Path)
    run_case_parser.set_defaults(func=_cmd_run_case)

    resume_parser = subparsers.add_parser("resume", help="Verify mode lock before resuming a case")
    resume_parser.add_argument("case_id")
    resume_parser.add_argument("--cases-dir", default=Path("cases"), type=Path)
    resume_parser.set_defaults(func=_cmd_resume)

    reverify_parser = subparsers.add_parser(
        "reverify",
        help="Create a parallel mode-specific chain",
    )
    reverify_parser.add_argument("case_id")
    reverify_parser.add_argument("--cases-dir", default=Path("cases"), type=Path)
    reverify_parser.add_argument("--mode", required=True, choices=["cloud", "airgap", "dual"])
    reverify_parser.set_defaults(func=_cmd_reverify)

    approve_parser = subparsers.add_parser("approve", help="Append a signed approval event")
    approve_parser.add_argument("case_id")
    approve_parser.add_argument("finding_id")
    approve_parser.add_argument("--approver", required=True)
    approve_parser.add_argument("--cases-dir", default=Path("cases"), type=Path)
    approve_parser.set_defaults(func=_cmd_approve)

    gc_parser = subparsers.add_parser("gc", help="List local cases eligible for manual cleanup")
    gc_parser.add_argument("--cases-dir", default=Path("cases"), type=Path)
    gc_parser.set_defaults(func=_cmd_gc)

    package_parser = subparsers.add_parser(
        "package-check",
        help="Validate and optionally zip required Devpost artifacts",
    )
    package_parser.add_argument("--root", default=Path.cwd(), type=Path)
    package_parser.add_argument("--output", type=Path)
    package_parser.set_defaults(func=_cmd_package_check)

    validate_parser = subparsers.add_parser("validate", help="Verify the latest ledger entry HMAC")
    validate_parser.add_argument("case_id")
    validate_parser.add_argument("--cases-dir", default=Path("cases"), type=Path)
    validate_parser.set_defaults(func=_cmd_validate)

    mode_parser = subparsers.add_parser("mode", help="Print detected operating mode")
    mode_parser.set_defaults(func=_cmd_mode)

    doctor_parser = subparsers.add_parser("doctor", help="Check local CLI prerequisites")
    doctor_parser.add_argument("--mode", choices=["cloud", "airgap", "dual"])
    doctor_parser.set_defaults(func=_cmd_doctor)

    health_parser = subparsers.add_parser("health", help="Print machine-readable health status")
    health_parser.set_defaults(func=_cmd_health)
    return parser


def _cmd_init(args: argparse.Namespace) -> int:
    mode = parse_mode(args.mode) if args.mode else detect_mode()
    _ensure_mode_available(mode)
    items = _evidence_items(args.evidence_path)
    case_id = args.case_id or _default_case_id(items)
    _validate_case_id(case_id)
    case_dir = args.cases_dir / case_id
    if case_dir.exists():
        raise CliError(f"case already exists: {case_id}")

    case_dir.mkdir(parents=True)
    manifest = EvidenceManifest.from_items(case_id=case_id, items=items)
    manifest_path = case_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    writer = LedgerWriter(case_dir / "ledger.jsonl", hmac_key=_hmac_key())
    timestamp = _utc_now()
    writer.write(
        {
            "entry_id": f"{case_id}:case_init:{timestamp}",
            "case_id": case_id,
            "finding_id": None,
            "event_type": "case_init",
            "timestamp_utc": timestamp,
            "mode_at_case_init": mode.value,
            "verifier_strategy_used": "not_run_case_init",
            "langfuse_session_id": case_id,
            "langfuse_trace_id": "local-cli",
            "langfuse_root_span_id": "local-cli-root",
            "langfuse_leaf_span_ids": [],
            "langgraph_thread_id": case_id,
            "langgraph_checkpoint_id": "case_init",
            "microsandbox_version": "not_invoked",
            "rootfs_sha256": "not_invoked",
            "tool_version": "verdict-cli",
            "kernel_version": platform.platform(),
            "output_files_sha256": {"manifest.json": _sha256_file(manifest_path)},
            "payload": {
                "manifest_hash": manifest.manifest_hash,
                "evidence_items": [item.model_dump(mode="json") for item in items],
            },
        }
    )
    print(f"initialized case {case_id} at {case_dir}")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    entries = verify_ledger_chain(
        args.cases_dir / args.case_id / "ledger.jsonl",
        hmac_key=_hmac_key(),
    )
    if args.format == "jsonl":
        payload = "\n".join(json.dumps(entry, sort_keys=True) for entry in entries) + "\n"
    elif args.format == "execution-logs":
        payload = "\n".join(
            json.dumps(_execution_log_entry(entry), sort_keys=True) for entry in entries
        )
        payload += "\n"
    else:
        payload = _html_export(args.case_id, entries)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


def _cmd_ls(args: argparse.Namespace) -> int:
    cases = []
    if args.cases_dir.exists():
        for case_dir in sorted(path for path in args.cases_dir.iterdir() if path.is_dir()):
            try:
                summary = _case_status(args.cases_dir, case_dir.name)
            except (CliError, KeyError, json.JSONDecodeError):
                continue
            cases.append(
                {
                    "case_id": summary["case_id"],
                    "mode": summary["mode"],
                    "events": summary["event_count"],
                }
            )
    print(json.dumps(cases, sort_keys=True))
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    print(json.dumps(_case_status(args.cases_dir, args.case_id), sort_keys=True))
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    summary = _case_status(args.cases_dir, args.case_id)
    manifest = _read_manifest(args.cases_dir, args.case_id)
    print(f"Case: {summary['case_id']}")
    print(f"Mode: {summary['mode']}")
    print(f"Ledger valid: {summary['ledger_valid']}")
    print(f"Events: {summary['event_count']}")
    print("Evidence:")
    for item in manifest.get("items", []):
        print(
            f"- {item['evidence_type']} {item['path']} "
            f"sha256={item['sha256_at_init']} size={item['size_bytes']}"
        )
    return 0


def _cmd_run_tool(args: argparse.Namespace) -> int:
    output = _run_registered_tool(
        cases_dir=args.cases_dir,
        case_id=args.case_id,
        tool_key=args.tool,
        evidence_index=args.evidence_index,
        extra_args=(),
    )
    print(output.model_dump_json())
    return output.exit_code


def _cmd_run_case(args: argparse.Namespace) -> int:
    manifest = _read_manifest(args.cases_dir, args.case_id)
    items = manifest.get("items", [])
    if not items:
        raise CliError(f"case has no evidence items: {args.case_id}")

    outputs: list[ToolOutput] = []
    playbook_steps: list[str] = []
    unsupported_types: set[str] = set()
    stop_after_failure = False
    for evidence_index, item in enumerate(items):
        sequence = _case_tool_sequence(item.get("evidence_type", ""))
        if not sequence:
            unsupported_types.add(item.get("evidence_type", "unknown"))
            continue
        if item.get("evidence_type") == "disk_image":
            disk_outputs, disk_steps, disk_failed = _run_disk_case_sequence(
                cases_dir=args.cases_dir,
                case_id=args.case_id,
                evidence_index=evidence_index,
            )
            outputs.extend(disk_outputs)
            playbook_steps.extend(disk_steps)
            if disk_failed:
                stop_after_failure = True
                break
            continue
        for tool_key in sequence:
            output = _run_registered_tool(
                cases_dir=args.cases_dir,
                case_id=args.case_id,
                tool_key=tool_key,
                evidence_index=evidence_index,
                extra_args=(),
            )
            outputs.append(output)
            playbook_steps.append(tool_key)
            if output.exit_code != 0:
                stop_after_failure = True
                break
        if stop_after_failure:
            break

    if not playbook_steps:
        playbook_steps.append("unsupported_evidence_type")
    conclusion = _build_case_conclusion(
        manifest=manifest,
        outputs=outputs,
        playbook_steps=playbook_steps,
        unsupported_types=unsupported_types,
    )
    _write_case_conclusion(args.cases_dir, args.case_id, conclusion, supporting_outputs=outputs)
    print(conclusion.model_dump_json())
    return 0


def _run_registered_tool(
    *,
    cases_dir: Path,
    case_id: str,
    tool_key: str,
    evidence_index: int,
    extra_args: tuple[str, ...],
) -> ToolOutput:
    sandbox = microsandbox_status()
    if not sandbox.available:
        raise CliError("microsandbox is required for forensic tool execution")

    manifest = _read_manifest(cases_dir, case_id)
    items = manifest.get("items", [])
    if evidence_index < 0 or evidence_index >= len(items):
        raise CliError(f"evidence index out of range: {evidence_index}")

    case_dir = cases_dir / case_id
    hmac_key = _hmac_key()
    entries = verify_ledger_chain(case_dir / "ledger.jsonl", hmac_key=hmac_key)
    evidence_item = items[evidence_index]
    evidence_path = Path(evidence_item["path"])
    if not evidence_path.is_file():
        raise CliError(f"evidence file no longer exists: {evidence_path}")
    actual_hash = _sha256_file(evidence_path)
    if actual_hash != evidence_item["sha256_at_init"]:
        raise CliError(f"evidence hash mismatch before tool execution: {evidence_path}")

    image = _pinned_microsandbox_image()
    spec = TOOL_SPECS[tool_key]
    command = microsandbox_command(
        tool_key,
        evidence_name=evidence_path.name,
        extra_args=extra_args,
    )
    sandbox_result = run_in_microsandbox(
        image=image,
        host_evidence_path=evidence_path,
        command=command,
    )
    parsed = parse_tool_stdout(tool_key, evidence_path=evidence_path, stdout=sandbox_result.stdout)
    stdout_text = sandbox_result.stdout.decode(errors="replace")
    parse_warnings = [*parsed.warnings]
    if sandbox_result.exit_code != 0:
        parse_warnings.append(f"tool exited with code {sandbox_result.exit_code}")
    output = ToolOutput.from_invocation(
        tool_name=spec.tool_name,
        tool_version=command[0],
        invocation_args=command[1:],
        evidence_hash=actual_hash,
        stdout=sandbox_result.stdout,
        stderr=sandbox_result.stderr,
        exit_code=sandbox_result.exit_code,
        parsed_artifacts=parsed.artifacts,
    ).model_copy(
        update={
            "parse_warnings": parse_warnings,
            "sanitization_flags": scan_tool_stdout(stdout_text),
        }
    )
    timestamp = _utc_now()
    safe_tool = tool_key.replace(".", "_")
    output_dir = case_dir / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{safe_tool}-{timestamp.replace(':', '')}.json"
    output_path.write_text(output.model_dump_json(indent=2), encoding="utf-8")

    writer = LedgerWriter(case_dir / "ledger.jsonl", hmac_key=hmac_key)
    writer.write(
        {
            "entry_id": f"{case_id}:tool_call:{safe_tool}:{timestamp}",
            "case_id": case_id,
            "finding_id": None,
            "event_type": "tool_call",
            "timestamp_utc": timestamp,
            "mode_at_case_init": entries[-1]["mode_at_case_init"],
            "verifier_strategy_used": entries[-1].get("verifier_strategy_used", "not_run"),
            "langfuse_session_id": case_id,
            "langfuse_trace_id": "local-cli",
            "langfuse_root_span_id": "local-cli-root",
            "langfuse_leaf_span_ids": [],
            "langgraph_thread_id": case_id,
            "langgraph_checkpoint_id": f"tool_call:{safe_tool}",
            "microsandbox_version": sandbox_result.microsandbox_version,
            "rootfs_sha256": sandbox_result.rootfs_sha256,
            "tool_version": output.tool_version,
            "kernel_version": platform.platform(),
            "output_files_sha256": {
                str(output_path.relative_to(case_dir)): _sha256_file(output_path)
            },
            "payload": {
                "tool_name": output.tool_name,
                "tool_call_id": output.invocation_hash,
                "invocation_args": output.invocation_args,
                "tool_output_path": str(output_path),
                "exit_code": output.exit_code,
                "stdout_hash": output.stdout_hash,
                "stderr_hash": output.stderr_hash,
                "parsed_artifacts": [
                    artifact.model_dump(mode="json") for artifact in output.parsed_artifacts
                ],
                "artifact_ids": [artifact.artifact_id for artifact in output.parsed_artifacts],
                "sanitization_flags": output.sanitization_flags,
            },
        }
    )
    return output


def _cmd_resume(args: argparse.Namespace) -> int:
    entries = verify_ledger_chain(
        args.cases_dir / args.case_id / "ledger.jsonl",
        hmac_key=_hmac_key(),
    )
    locked_mode = Mode(entries[-1]["mode_at_case_init"])
    detected_mode = detect_mode()
    if locked_mode is not detected_mode:
        raise CliError(
            f"Case {args.case_id} was initialized in mode={locked_mode.value}; "
            f"current environment is mode={detected_mode.value}. "
            f"Use verdict reverify {args.case_id} --mode {detected_mode.value}."
        )
    print(json.dumps({"case_id": args.case_id, "mode": locked_mode.value, "resume": "ok"}))
    return 0


def _cmd_reverify(args: argparse.Namespace) -> int:
    target_mode = parse_mode(args.mode)
    _ensure_mode_available(target_mode)
    source_manifest = _read_manifest(args.cases_dir, args.case_id)
    source_entries = verify_ledger_chain(
        args.cases_dir / args.case_id / "ledger.jsonl",
        hmac_key=_hmac_key(),
    )
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    new_case_id = f"{args.case_id}-reverify-{target_mode.value.lower()}-{timestamp}"
    new_case_dir = args.cases_dir / new_case_id
    new_case_dir.mkdir(parents=True, exist_ok=False)
    manifest = {**source_manifest, "case_id": new_case_id}
    manifest_path = new_case_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    event_time = _utc_now()
    LedgerWriter(new_case_dir / "ledger.jsonl", hmac_key=_hmac_key()).write(
        {
            "entry_id": f"{new_case_id}:reverify_init:{event_time}",
            "case_id": new_case_id,
            "finding_id": None,
            "event_type": "mode_lock",
            "timestamp_utc": event_time,
            "mode_at_case_init": target_mode.value,
            "verifier_strategy_used": f"reverify_from:{source_entries[-1]['mode_at_case_init']}",
            "langfuse_session_id": new_case_id,
            "langfuse_trace_id": "local-cli",
            "langfuse_root_span_id": "local-cli-root",
            "langfuse_leaf_span_ids": [],
            "langgraph_thread_id": new_case_id,
            "langgraph_checkpoint_id": "reverify_init",
            "microsandbox_version": "not_invoked",
            "rootfs_sha256": "not_invoked",
            "tool_version": "verdict-cli",
            "kernel_version": platform.platform(),
            "output_files_sha256": {"manifest.json": _sha256_file(manifest_path)},
            "payload": {"source_case_id": args.case_id, "target_mode": target_mode.value},
        }
    )
    print(json.dumps({"case_id": new_case_id, "source_case_id": args.case_id}, sort_keys=True))
    return 0


def _cmd_approve(args: argparse.Namespace) -> int:
    case_dir = args.cases_dir / args.case_id
    entries = verify_ledger_chain(case_dir / "ledger.jsonl", hmac_key=_hmac_key())
    timestamp = _utc_now()
    LedgerWriter(case_dir / "ledger.jsonl", hmac_key=_hmac_key()).write(
        {
            "entry_id": f"{args.case_id}:approval:{args.finding_id}:{timestamp}",
            "case_id": args.case_id,
            "finding_id": args.finding_id,
            "event_type": "approval",
            "timestamp_utc": timestamp,
            "mode_at_case_init": entries[-1]["mode_at_case_init"],
            "verifier_strategy_used": entries[-1].get("verifier_strategy_used", "not_run"),
            "langfuse_session_id": args.case_id,
            "langfuse_trace_id": "local-cli",
            "langfuse_root_span_id": "local-cli-root",
            "langfuse_leaf_span_ids": [],
            "langgraph_thread_id": args.case_id,
            "langgraph_checkpoint_id": "approval",
            "microsandbox_version": "not_invoked",
            "rootfs_sha256": "not_invoked",
            "tool_version": "verdict-cli",
            "kernel_version": platform.platform(),
            "output_files_sha256": {},
            "payload": {"approver": args.approver, "finding_id": args.finding_id},
        }
    )
    print(json.dumps({"case_id": args.case_id, "finding_id": args.finding_id, "approved": True}))
    return 0


def _cmd_gc(args: argparse.Namespace) -> int:
    cases = []
    if args.cases_dir.exists():
        cases = sorted(path.name for path in args.cases_dir.iterdir() if path.is_dir())
    print(json.dumps({"cases_dir": str(args.cases_dir), "cases": cases}, sort_keys=True))
    return 0


def _cmd_package_check(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    missing = [path for path in DEVPOST_REQUIRED_PATHS if not (root / path).is_file()]
    result = {"root": str(root), "missing": missing, "ok": not missing}
    if missing:
        print(json.dumps(result, sort_keys=True))
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for rel_path in DEVPOST_REQUIRED_PATHS:
                archive.write(root / rel_path, rel_path)
        result["output"] = str(args.output)
    print(json.dumps(result, sort_keys=True))
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    verify_ledger_chain(args.cases_dir / args.case_id / "ledger.jsonl", hmac_key=_hmac_key())
    print(f"ledger valid for {args.case_id}")
    return 0


def _case_status(cases_dir: Path, case_id: str) -> dict[str, Any]:
    manifest = _read_manifest(cases_dir, case_id)
    entries = verify_ledger_chain(cases_dir / case_id / "ledger.jsonl", hmac_key=_hmac_key())
    latest = entries[-1]
    return {
        "case_id": case_id,
        "event_count": len(entries),
        "last_event_type": latest.get("event_type"),
        "ledger_valid": True,
        "manifest_hash": manifest.get("manifest_hash"),
        "manifest_items": len(manifest.get("items", [])),
        "mode": latest.get("mode_at_case_init"),
    }


def _case_tool_sequence(evidence_type: str) -> tuple[str, ...]:
    if evidence_type == "memory":
        return ("vol3.info", "vol3.pslist", "vol3.psscan")
    if evidence_type == "disk_image":
        return ("mmls", "fsstat", "fls")
    return ()


def _run_disk_case_sequence(
    *,
    cases_dir: Path,
    case_id: str,
    evidence_index: int,
) -> tuple[list[ToolOutput], list[str], bool]:
    outputs: list[ToolOutput] = []
    steps: list[str] = []
    mmls_output = _run_registered_tool(
        cases_dir=cases_dir,
        case_id=case_id,
        tool_key="mmls",
        evidence_index=evidence_index,
        extra_args=(),
    )
    outputs.append(mmls_output)
    steps.append("mmls")
    if mmls_output.exit_code != 0:
        return outputs, steps, True

    offsets = _filesystem_partition_offsets(mmls_output)
    if not offsets:
        steps.append("disk_partition_offset_not_found")
        return outputs, steps, False

    for offset in offsets:
        extra_args = ("-o", str(offset))
        for tool_key in ("fsstat", "fls"):
            output = _run_registered_tool(
                cases_dir=cases_dir,
                case_id=case_id,
                tool_key=tool_key,
                evidence_index=evidence_index,
                extra_args=extra_args,
            )
            outputs.append(output)
            steps.append(f"{tool_key}:-o:{offset}")
            if output.exit_code != 0:
                return outputs, steps, True
    return outputs, steps, False


def _filesystem_partition_offsets(mmls_output: ToolOutput) -> list[int]:
    offsets: list[int] = []
    for artifact in mmls_output.parsed_artifacts:
        if artifact.artifact_type != "partition_table_entry":
            continue
        description = str(artifact.raw_fields.get("description", "")).lower()
        if not any(marker in description for marker in ("ntfs", "fat", "exfat")):
            continue
        start = artifact.raw_fields.get("start_sector")
        if isinstance(start, int) and start > 0:
            offsets.append(start)
    return sorted(set(offsets))


def _build_case_conclusion(
    *,
    manifest: dict[str, Any],
    outputs: list[ToolOutput],
    playbook_steps: list[str],
    unsupported_types: set[str],
) -> CaseConclusion:
    evidence_hashes = {
        Path(item["path"]): item["sha256_at_init"] for item in manifest.get("items", [])
    }
    if unsupported_types:
        unsupported = ", ".join(sorted(unsupported_types))
        return CaseConclusion(
            status="UNVERIFIABLE",
            playbook_steps_executed=playbook_steps,
            evidence_hashes=evidence_hashes,
            rationale=(
                "Unsupported evidence type(s) prevented full canonical triage: "
                f"{unsupported}."
            ),
        )

    if "disk_partition_offset_not_found" in playbook_steps:
        return CaseConclusion(
            status="UNVERIFIABLE",
            playbook_steps_executed=playbook_steps,
            evidence_hashes=evidence_hashes,
            rationale=(
                "mmls did not produce a supported filesystem partition offset; "
                "fsstat and fls were not run against an inferred offset."
            ),
        )

    failed_output = next((output for output in outputs if output.exit_code != 0), None)
    if failed_output is not None:
        return CaseConclusion(
            status="UNVERIFIABLE",
            playbook_steps_executed=playbook_steps,
            evidence_hashes=evidence_hashes,
            rationale=(
                f"{failed_output.tool_name} exited with code {failed_output.exit_code}; "
                "VERDICT cannot support a case-level finding from incomplete tool output."
            ),
        )

    unparsed_tools = sorted(output.tool_name for output in outputs if not output.parsed_artifacts)
    if unparsed_tools:
        return CaseConclusion(
            status="UNVERIFIABLE",
            playbook_steps_executed=playbook_steps,
            evidence_hashes=evidence_hashes,
            rationale=(
                "Parser produced no structured artifacts for required tool(s): "
                f"{', '.join(unparsed_tools)}."
            ),
        )

    divergent_pids = _process_scan_divergence(outputs)
    if divergent_pids:
        return CaseConclusion(
            status="EVIL_FOUND",
            playbook_steps_executed=playbook_steps,
            evidence_hashes=evidence_hashes,
            rationale=(
                "Evidence is consistent with hidden process activity: "
                f"psscan PID(s) absent from pslist: {', '.join(map(str, divergent_pids))}."
            ),
        )

    return CaseConclusion(
        status="UNVERIFIABLE",
        playbook_steps_executed=playbook_steps,
        evidence_hashes=evidence_hashes,
        rationale=(
            "Canonical first-pass SIFT triage completed without a parser-supported evil "
            "indicator, but the verifier/finding workflow has not run enough negative "
            "criteria to support NO_EVIL_FOUND."
        ),
    )


def _process_scan_divergence(outputs: list[ToolOutput]) -> list[int]:
    pslist_pids: set[int] = set()
    psscan_pids: set[int] = set()
    for output in outputs:
        for artifact in output.parsed_artifacts:
            pid = _artifact_pid(artifact.raw_fields)
            if pid is None:
                continue
            if artifact.artifact_type == "process_listing":
                pslist_pids.add(pid)
            elif artifact.artifact_type == "process_scan":
                psscan_pids.add(pid)
    if not psscan_pids:
        return []
    return sorted(psscan_pids - pslist_pids)


def _artifact_pid(raw_fields: dict[str, Any]) -> int | None:
    pid = raw_fields.get("pid", raw_fields.get("PID"))
    if isinstance(pid, int):
        return pid
    if isinstance(pid, str):
        try:
            return int(pid.strip(), 0)
        except ValueError:
            return None
    return None


def _write_case_conclusion(
    cases_dir: Path,
    case_id: str,
    conclusion: CaseConclusion,
    *,
    supporting_outputs: list[ToolOutput],
) -> None:
    case_dir = cases_dir / case_id
    hmac_key = _hmac_key()
    entries = verify_ledger_chain(case_dir / "ledger.jsonl", hmac_key=hmac_key)
    timestamp = _utc_now()
    output_dir = case_dir / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"case-conclusion-{timestamp.replace(':', '')}.json"
    output_path.write_text(conclusion.model_dump_json(indent=2), encoding="utf-8")

    LedgerWriter(case_dir / "ledger.jsonl", hmac_key=hmac_key).write(
        {
            "entry_id": f"{case_id}:case_conclusion:{timestamp}",
            "case_id": case_id,
            "finding_id": None,
            "event_type": "case_conclusion",
            "timestamp_utc": timestamp,
            "mode_at_case_init": entries[-1]["mode_at_case_init"],
            "verifier_strategy_used": entries[-1].get("verifier_strategy_used", "not_run"),
            "langfuse_session_id": case_id,
            "langfuse_trace_id": "local-cli",
            "langfuse_root_span_id": "local-cli-root",
            "langfuse_leaf_span_ids": [],
            "langgraph_thread_id": case_id,
            "langgraph_checkpoint_id": "case_conclusion",
            "microsandbox_version": "not_invoked",
            "rootfs_sha256": "not_invoked",
            "tool_version": "verdict-cli",
            "kernel_version": platform.platform(),
            "output_files_sha256": {
                str(output_path.relative_to(case_dir)): _sha256_file(output_path)
            },
            "payload": {
                **conclusion.model_dump(mode="json"),
                "case_conclusion_path": str(output_path),
                "supporting_tool_outputs": _supporting_tool_outputs(entries, supporting_outputs),
            },
        }
    )


def _supporting_tool_outputs(
    entries: list[dict[str, Any]],
    outputs: list[ToolOutput],
) -> list[dict[str, Any]]:
    output_hashes = {output.invocation_hash for output in outputs}
    supporting: list[dict[str, Any]] = []
    for entry in entries:
        payload = entry.get("payload", {})
        if (
            entry.get("event_type") != "tool_call"
            or payload.get("tool_call_id") not in output_hashes
        ):
            continue
        supporting.append(
            {
                "tool_name": payload.get("tool_name"),
                "tool_call_id": payload.get("tool_call_id"),
                "invocation_args": payload.get("invocation_args"),
                "tool_output_path": payload.get("tool_output_path"),
                "output_files_sha256": entry.get("output_files_sha256", {}),
                "stdout_hash": payload.get("stdout_hash"),
                "stderr_hash": payload.get("stderr_hash"),
                "artifact_ids": payload.get("artifact_ids", []),
            }
        )
    return supporting


def _read_manifest(cases_dir: Path, case_id: str) -> dict[str, Any]:
    manifest_path = cases_dir / case_id / "manifest.json"
    if not manifest_path.is_file():
        raise CliError(f"manifest not found for case: {case_id}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _cmd_mode(_args: argparse.Namespace) -> int:
    print(detect_mode().value)
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    if args.mode:
        requested_mode = parse_mode(args.mode)
        mode = requested_mode.value if mode_is_available(requested_mode) else "UNCONFIGURED"
    else:
        try:
            mode = detect_mode().value
        except ModeDetectionError:
            mode = "UNCONFIGURED"
    sandbox = microsandbox_status()
    tools = _forensic_tool_availability(sandbox)
    sglang_reachable = _sglang_reachable()
    if mode in {Mode.AIRGAP.value, Mode.DUAL.value} and not sglang_reachable:
        mode = "UNCONFIGURED"
    image = _configured_pinned_microsandbox_image()
    blockers = _doctor_blockers(
        mode=mode,
        sandbox=sandbox,
        image_pinned=image is not None,
        hmac_configured=_has_any_hmac_key_config(),
        tools=tools,
    )
    ready = not blockers
    checks = {
        "mode": mode,
        "ready": ready,
        "blockers": blockers,
        "tools": tools,
        "microsandbox_available": sandbox.available,
        "microsandbox_binary": sandbox.binary,
        "microsandbox_runner": sandbox.runner,
        "microsandbox_image_pinned": image is not None,
        "hmac_key_hex_present": bool(os.environ.get("VERDICT_HMAC_KEY_HEX")),
        "hmac_passphrase_present": bool(os.environ.get("VERDICT_HMAC_PASSPHRASE")),
        "anthropic_api_key_present": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "claude_code_oauth_present": bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")),
        "sglang_base_url_present": bool(os.environ.get("SGLANG_BASE_URL")),
        "sglang_reachable": sglang_reachable,
    }
    print(json.dumps(checks, sort_keys=True))
    return 0 if ready else 1


def _cmd_health(_args: argparse.Namespace) -> int:
    try:
        mode = detect_mode().value
    except ModeDetectionError:
        print(
            json.dumps(
                {"status": "degraded", "mode": "UNCONFIGURED", "blockers": ["mode_unconfigured"]},
                sort_keys=True,
            )
        )
        return 1
    sandbox = microsandbox_status()
    tools = _forensic_tool_availability(sandbox)
    sandbox_available = sandbox.available
    sglang_reachable = _sglang_reachable()
    local_mode_ready = mode == Mode.CLOUD.value or sglang_reachable
    ready = all(tools.values()) and sandbox_available and local_mode_ready
    blockers = _health_blockers(
        tools=tools,
        sandbox_available=sandbox_available,
        local_mode_ready=local_mode_ready,
    )
    print(
        json.dumps(
            {
                "status": "ok" if ready else "degraded",
                "mode": mode,
                "blockers": blockers,
                "tools": tools,
                "microsandbox": sandbox_available,
                "microsandbox_runner": sandbox.runner,
                "microsandbox_image_pinned": _configured_pinned_microsandbox_image() is not None,
                "sglang_reachable": sglang_reachable,
            },
            sort_keys=True,
        )
    )
    return 0 if ready else 1


def _doctor_blockers(
    *,
    mode: str,
    sandbox: MicrosandboxStatus,
    image_pinned: bool,
    hmac_configured: bool,
    tools: dict[str, bool],
) -> list[str]:
    blockers: list[str] = []
    if mode == "UNCONFIGURED":
        blockers.append("mode_unconfigured")
    if not hmac_configured:
        blockers.append("hmac_key_unconfigured")
    if not sandbox.available:
        blockers.append("microsandbox_unavailable")
    if not image_pinned:
        blockers.append("microsandbox_image_unpinned")
    missing_tools = sorted(name for name, available in tools.items() if not available)
    blockers.extend(f"tool_unavailable:{tool}" for tool in missing_tools)
    return blockers


def _health_blockers(
    *,
    tools: dict[str, bool],
    sandbox_available: bool,
    local_mode_ready: bool,
) -> list[str]:
    blockers: list[str] = []
    if not sandbox_available:
        blockers.append("microsandbox_unavailable")
    if not local_mode_ready:
        blockers.append("local_inference_unreachable")
    missing_tools = sorted(name for name, available in tools.items() if not available)
    blockers.extend(f"tool_unavailable:{tool}" for tool in missing_tools)
    return blockers


def _evidence_items(path: Path) -> list[EvidenceItem]:
    files = list(_iter_evidence_files(path))
    if not files:
        raise CliError(f"no evidence files found: {path}")
    discovered_at = datetime.now(UTC)
    return [
        EvidenceItem(
            path=file.resolve(),
            sha256_at_init=_sha256_file(file),
            size_bytes=file.stat().st_size,
            discovered_at=discovered_at,
            evidence_type=_infer_evidence_type(file),
        )
        for file in files
    ]


def _iter_evidence_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    if path.is_dir():
        yield from sorted(file for file in path.rglob("*") if file.is_file())
        return
    raise CliError(f"evidence path does not exist: {path}")


def _infer_evidence_type(path: Path) -> EvidenceType:
    suffix = path.suffix.lower()
    if suffix in {".mem", ".raw", ".vmem"}:
        return "memory"
    if suffix in {".e01", ".dd", ".img"}:
        return "disk_image"
    if suffix == ".evtx":
        return "event_log"
    if suffix in {".pcap", ".pcapng"}:
        return "pcap"
    if suffix in {".dat", ".hiv"}:
        return "registry_hive"
    return "other"


def _default_case_id(items: list[EvidenceItem]) -> str:
    manifest_hash = EvidenceManifest.from_items(case_id="pending", items=items).manifest_hash
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"case-{timestamp}-{manifest_hash[:8]}"


def _validate_case_id(case_id: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", case_id):
        raise CliError("case_id must be 1-128 chars of letters, digits, dot, underscore, or hyphen")
    if case_id in {".", ".."}:
        raise CliError("case_id cannot be a path traversal segment")


def _execution_log_entry(entry: dict[str, Any]) -> dict[str, Any]:
    payload = entry.get("payload", {})
    return {
        "ts_utc": entry.get("timestamp_utc"),
        "event_type": entry.get("event_type"),
        "agent_id": payload.get("agent_id"),
        "target_agent_id": payload.get("target_agent_id"),
        "tool_name": payload.get("tool_name"),
        "tool_call_id": payload.get("tool_call_id"),
        "tool_exit_code": payload.get("exit_code"),
        "case_conclusion_status": payload.get("status"),
        "prompt_tokens": payload.get("prompt_tokens"),
        "completion_tokens": payload.get("completion_tokens"),
        "finding_id": entry.get("finding_id") or payload.get("finding_id"),
        "langfuse_trace_id": entry.get("langfuse_trace_id"),
        "langgraph_checkpoint_id": entry.get("langgraph_checkpoint_id"),
        "mode_at_case_init": entry.get("mode_at_case_init"),
    }


def _html_export(case_id: str, entries: list[dict[str, Any]]) -> str:
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(entry.get('timestamp_utc')))}</td>"
        f"<td>{html.escape(str(entry.get('event_type')))}</td>"
        f"<td>{html.escape(str(entry.get('langgraph_checkpoint_id')))}</td>"
        "</tr>"
        for entry in entries
    )
    return (
        "<!doctype html>\n"
        f"<title>VERDICT {html.escape(case_id)}</title>\n"
        f"<h1>VERDICT case {html.escape(case_id)}</h1>\n"
        "<table><thead><tr><th>UTC</th><th>Event</th><th>Checkpoint</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>\n"
    )


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hmac_key() -> bytes:
    key_hex = os.environ.get("VERDICT_HMAC_KEY_HEX")
    if key_hex:
        return _hmac_key_from_hex(key_hex)

    passphrase = os.environ.get("VERDICT_HMAC_PASSPHRASE")
    if passphrase is None and sys.stdin.isatty():
        passphrase = getpass.getpass("VERDICT HMAC key passphrase: ")
    if passphrase:
        key_path = Path(os.environ.get("VERDICT_HMAC_KEY_PATH", Path.home() / ".verdict/key.gpg"))
        gnupg_home = Path(os.environ.get("VERDICT_GNUPG_HOME", Path.home() / ".verdict/gnupg"))
        return load_or_create_hmac_key(
            key_path=key_path,
            passphrase=passphrase,
            gnupg_home=gnupg_home,
        )

    raise CliError("VERDICT_HMAC_PASSPHRASE or VERDICT_HMAC_KEY_HEX must be set for ledger HMAC")


def _hmac_key_from_hex(key_hex: str) -> bytes:
    if not key_hex:
        raise CliError(
            "VERDICT_HMAC_PASSPHRASE or VERDICT_HMAC_KEY_HEX must be set for ledger HMAC"
        )
    try:
        key = bytes.fromhex(key_hex)
    except ValueError as exc:
        raise CliError("VERDICT_HMAC_KEY_HEX must be valid hex") from exc
    if len(key) != 32:
        raise CliError("VERDICT_HMAC_KEY_HEX must decode to exactly 32 bytes")
    return key


def _has_any_hmac_key_config() -> bool:
    return bool(os.environ.get("VERDICT_HMAC_PASSPHRASE") or os.environ.get("VERDICT_HMAC_KEY_HEX"))


def _ensure_mode_available(mode: Mode) -> None:
    if mode_is_available(mode):
        return
    if mode is Mode.CLOUD:
        raise CliError("cloud mode requires ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN")
    if mode is Mode.AIRGAP:
        raise CliError("airgap mode requires SGLANG_BASE_URL")
    raise CliError("dual mode requires cloud credentials and SGLANG_BASE_URL")


def _pinned_microsandbox_image() -> str:
    image = _configured_pinned_microsandbox_image()
    if image is None:
        raise CliError("VERDICT_MICROSANDBOX_IMAGE must be pinned as IMAGE@sha256:<digest>")
    return image


def _configured_pinned_microsandbox_image() -> str | None:
    image = os.environ.get("VERDICT_MICROSANDBOX_IMAGE")
    if not image or not re.search(r"@sha256:[A-Fa-f0-9]{64}$", image):
        return None
    return image


def _forensic_tool_availability(sandbox: MicrosandboxStatus) -> dict[str, bool]:
    image = _configured_pinned_microsandbox_image()
    if sandbox.available and image is not None:
        return _sandbox_image_tools_available(image)
    return available_tools()


def _sandbox_image_tools_available(image: str) -> dict[str, bool]:
    checks = {name: False for name in TOOL_SPECS}
    script = " && ".join(
        [
            "check() { name=$1; shift; if \"$@\" >/dev/null 2>&1; "
            "then printf '%s=1\\n' \"$name\"; else printf '%s=0\\n' \"$name\"; fi; }",
            "check vol3.info vol3 -h",
            "check vol3.pslist vol3 -h",
            "check vol3.psscan vol3 -h",
            "check mmls mmls -V",
            "check fsstat fsstat -V",
            "check fls fls -V",
        ]
    )
    try:
        result = run_microsandbox_command(
            image=image,
            command=["sh", "-lc", script],
            timeout_seconds=120,
        )
    except RuntimeError:
        return checks
    if result.exit_code != 0:
        return checks
    for line in result.stdout.decode(errors="replace").splitlines():
        if "=" not in line:
            continue
        name, value = line.strip().split("=", 1)
        if name in checks:
            checks[name] = value == "1"
    return checks


def _sglang_reachable() -> bool:
    return has_local_inference_endpoint(timeout_seconds=2)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
