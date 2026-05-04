from __future__ import annotations

from typing import TYPE_CHECKING

from verdict.proof.cloud import create_proof_run, write_blocker_run

if TYPE_CHECKING:
    from pathlib import Path


def test_create_proof_run_makes_visual_artifact_structure(tmp_path: Path) -> None:
    run = create_proof_run(tmp_path, timestamp="20260504T120000Z")

    assert run.path == tmp_path / "runs" / "20260504T120000Z"
    assert (run.path / "screenshots").is_dir()
    assert (run.path / "video").is_dir()
    assert (run.path / "review.md").is_file()
    assert "Claude Agent SDK" in (run.path / "review.md").read_text()


def test_write_blocker_run_records_missing_cloud_readiness_without_secret(tmp_path: Path) -> None:
    run = create_proof_run(tmp_path, timestamp="20260504T120000Z")

    write_blocker_run(run, reason="ANTHROPIC_API_KEY is not configured")

    summary = (run.path / "run-summary.md").read_text()
    service_checks = (run.path / "service-checks.log").read_text()
    ledger = (run.path / "ledger.jsonl").read_text()
    assert "BLOCKED" in summary
    assert "ANTHROPIC_API_KEY is not configured" in service_checks
    assert "sk-ant" not in summary
    assert "cloud_proof_blocked" in ledger
