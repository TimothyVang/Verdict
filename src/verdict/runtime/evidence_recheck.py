from __future__ import annotations

import platform
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from verdict.ledger.writer import LedgerWriter
from verdict.schemas.evidence import EvidenceManifest


class HashMismatchError(RuntimeError):
    """Raised when evidence no longer matches the case-init manifest."""


def recheck_evidence_if_due(
    *,
    super_step: int,
    manifest: EvidenceManifest,
    ledger_path: Path,
    interval: int = 10,
    hmac_key: bytes | None = None,
    mode_at_case_init: str = "CLOUD",
) -> bool:
    if super_step % interval != 0:
        return False

    for item in manifest.items:
        actual_sha256 = sha256(item.path.read_bytes()).hexdigest()
        if actual_sha256 != item.sha256_at_init:
            _write_mismatch_entry(
                ledger_path=ledger_path,
                case_id=manifest.case_id,
                path=item.path,
                expected_sha256=item.sha256_at_init,
                actual_sha256=actual_sha256,
                hmac_key=hmac_key,
                mode_at_case_init=mode_at_case_init,
            )
            raise HashMismatchError(f"Evidence hash mismatch for {item.path}")
    return True


def _write_mismatch_entry(
    *,
    ledger_path: Path,
    case_id: str,
    path: Path,
    expected_sha256: str,
    actual_sha256: str,
    hmac_key: bytes | None,
    mode_at_case_init: str,
) -> None:
    if hmac_key is None:
        raise ValueError("hmac_key is required to ledger evidence hash mismatches")

    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    LedgerWriter(ledger_path, hmac_key=hmac_key).write(
        {
            "entry_id": f"{case_id}:evidence_hash_recheck:{timestamp}",
            "case_id": case_id,
            "finding_id": None,
            "event_type": "evidence_hash_recheck",
            "timestamp_utc": timestamp,
            "mode_at_case_init": mode_at_case_init,
            "verifier_strategy_used": "not_run_evidence_recheck",
            "langfuse_session_id": case_id,
            "langfuse_trace_id": "local-runtime",
            "langfuse_root_span_id": "local-runtime-root",
            "langfuse_leaf_span_ids": [],
            "langgraph_thread_id": case_id,
            "langgraph_checkpoint_id": f"evidence_hash_recheck:{timestamp}",
            "microsandbox_version": "not_invoked",
            "rootfs_sha256": "not_invoked",
            "tool_version": "verdict-runtime",
            "kernel_version": platform.platform(),
            "output_files_sha256": {},
            "payload": {
                "path": str(path),
                "expected_sha256": expected_sha256,
                "actual_sha256": actual_sha256,
            },
        }
    )
