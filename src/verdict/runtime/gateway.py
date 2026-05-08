from __future__ import annotations

import platform
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from verdict.ledger.writer import LedgerWriter
from verdict.runtime.mode_detect import Mode, detect_mode, mode_is_available, parse_mode
from verdict.schemas.evidence import EvidenceItem, EvidenceManifest, EvidenceType


class GatewayError(RuntimeError):
    """Base error for gateway-local case lifecycle failures."""


class FastMCPUnavailableError(GatewayError):
    """Raised when the FastMCP gateway cannot be built from installed dependencies."""


class GatewayEvidenceError(GatewayError):
    """Raised when case initialization receives no readable evidence path."""


class GatewayModeUnavailableError(GatewayError):
    """Raised when requested mode prerequisites are unavailable."""


class GatewayCaseExistsError(GatewayError):
    """Raised when a case directory already exists."""


@dataclass(frozen=True)
class CaseInitResult:
    case_id: str
    case_dir: Path
    manifest_path: Path
    manifest_hash: str
    mode: Mode
    case_init_entry: dict[str, Any]
    mode_lock_entry: dict[str, Any]


def build_fastmcp_gateway(*, cases_dir: Path = Path("cases")) -> Any:
    """Build the FastMCP app if the optional FastMCP dependency is installed."""
    trusted_cases_dir = cases_dir.resolve()
    if find_spec("fastmcp") is None:
        raise FastMCPUnavailableError(
            "FastMCP is not installed; add the approved FastMCP dependency before "
            "serving gateway tools"
        )

    from fastmcp import FastMCP  # type: ignore[import-not-found]

    mcp = FastMCP("verdict-gateway")


    @mcp.tool
    def case_init_tool(
        evidence_path: str,
        requested_mode: str | None = None,
        case_id: str | None = None,
    ) -> dict[str, Any]:
        mode = parse_mode(requested_mode) if requested_mode else None
        result = case_init(
            evidence_path=Path(evidence_path),
            cases_dir=trusted_cases_dir,
            requested_mode=mode,
            case_id=case_id,
            hmac_key=_hmac_key_from_environment(),
        )
        return {
            "case_id": result.case_id,
            "case_dir": str(result.case_dir),
            "manifest_path": str(result.manifest_path),
            "manifest_hash": result.manifest_hash,
            "mode": result.mode.value,
        }

    return mcp


def case_init(
    *,
    evidence_path: Path,
    cases_dir: Path,
    hmac_key: bytes,
    requested_mode: Mode | None = None,
    case_id: str | None = None,
    mode_timeout_seconds: float = 2.0,
) -> CaseInitResult:
    """Initialize a VERDICT case from real evidence and append locked lifecycle ledger rows."""
    items = _evidence_items(evidence_path)
    mode = requested_mode or detect_mode(timeout_seconds=mode_timeout_seconds)
    _ensure_mode_available(mode, timeout_seconds=mode_timeout_seconds)

    resolved_case_id = case_id or _default_case_id(items)
    _validate_case_id(resolved_case_id)
    case_dir = cases_dir / resolved_case_id
    if case_dir.exists():
        raise GatewayCaseExistsError(f"case already exists: {resolved_case_id}")

    case_dir.mkdir(parents=True)
    manifest = EvidenceManifest.from_items(case_id=resolved_case_id, items=items)
    manifest_path = case_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    writer = LedgerWriter(case_dir / "ledger.jsonl", hmac_key=hmac_key)
    case_init_entry = writer.write(
        _lifecycle_entry(
            case_id=resolved_case_id,
            event_type="case_init",
            checkpoint_id="case_init",
            mode=mode,
            output_files_sha256={"manifest.json": _sha256_file(manifest_path)},
            payload={
                "manifest_hash": manifest.manifest_hash,
                "evidence_items": [item.model_dump(mode="json") for item in items],
            },
        )
    )
    mode_lock_entry = writer.write(
        _lifecycle_entry(
            case_id=resolved_case_id,
            event_type="mode_lock",
            checkpoint_id="mode_lock",
            mode=mode,
            output_files_sha256={},
            payload={"mode_at_case_init": mode.value},
        )
    )
    return CaseInitResult(
        case_id=resolved_case_id,
        case_dir=case_dir,
        manifest_path=manifest_path,
        manifest_hash=manifest.manifest_hash,
        mode=mode,
        case_init_entry=case_init_entry,
        mode_lock_entry=mode_lock_entry,
    )


def _lifecycle_entry(
    *,
    case_id: str,
    event_type: str,
    checkpoint_id: str,
    mode: Mode,
    output_files_sha256: dict[str, str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return {
        "entry_id": f"{case_id}:{event_type}:{timestamp}",
        "event_type": event_type,
        "case_id": case_id,
        "finding_id": None,
        "timestamp_utc": timestamp,
        "mode_at_case_init": mode.value,
        "verifier_strategy_used": f"not_run_{event_type}",
        "langfuse_session_id": case_id,
        "langfuse_trace_id": "local-gateway",
        "langfuse_root_span_id": "local-gateway-root",
        "langfuse_leaf_span_ids": [],
        "langgraph_thread_id": case_id,
        "langgraph_checkpoint_id": checkpoint_id,
        "microsandbox_version": "not_invoked",
        "rootfs_sha256": "not_invoked",
        "tool_version": "verdict-gateway",
        "kernel_version": platform.platform(),
        "output_files_sha256": output_files_sha256,
        "payload": payload,
    }


def _evidence_items(path: Path) -> list[EvidenceItem]:
    files = list(_iter_evidence_files(path))
    if not files:
        raise GatewayEvidenceError(f"no evidence files found: {path}")
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
    raise GatewayEvidenceError(f"evidence path does not exist: {path}")


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
        raise GatewayError(
            "case_id must be 1-128 chars of letters, digits, dot, underscore, or hyphen"
        )
    if case_id in {".", ".."}:
        raise GatewayError("case_id cannot be a path traversal segment")


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_mode_available(mode: Mode, *, timeout_seconds: float) -> None:
    if mode_is_available(mode, timeout_seconds=timeout_seconds):
        return
    if mode is Mode.CLOUD:
        raise GatewayModeUnavailableError(
            "cloud mode requires ANTHROPIC_API_KEY, CLAUDE_CODE_OAUTH_TOKEN, or OPENROUTER_API_KEY"
        )
    if mode is Mode.AIRGAP:
        raise GatewayModeUnavailableError("airgap mode requires SGLANG_BASE_URL")
    raise GatewayModeUnavailableError("dual mode requires cloud credentials and SGLANG_BASE_URL")


def _hmac_key_from_environment() -> bytes:
    import os

    key_hex = os.environ.get("VERDICT_HMAC_KEY_HEX")
    if not key_hex:
        raise GatewayError("VERDICT_HMAC_KEY_HEX must be set for gateway ledger HMAC")
    try:
        key = bytes.fromhex(key_hex)
    except ValueError as exc:
        raise GatewayError("VERDICT_HMAC_KEY_HEX must be valid hex") from exc
    if len(key) != 32:
        raise GatewayError("VERDICT_HMAC_KEY_HEX must decode to exactly 32 bytes")
    return key
